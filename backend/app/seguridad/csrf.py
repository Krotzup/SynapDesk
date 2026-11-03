from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hmac import compare_digest
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.configuracion import Configuracion
from app.persistencia.modelos import ContextoCsrf, Sesion, TokenCsrf
from app.seguridad.secretos import digest_secreto, generar_secreto
from app.seguridad.sesiones import DURACION_ABSOLUTA, INACTIVIDAD_MAXIMA, ServicioSesiones
from app.seguridad.transacciones import (
    CodigoSeguridad, ErrorSeguridad, Reloj, instante, operacion_bd, reloj_postgresql,
)


@dataclass(frozen=True)
class ContextoConsultado:
    id: UUID
    tipo: str
    expira_en: datetime


@dataclass(frozen=True)
class ContextoEmitido:
    id: UUID
    expira_en: datetime
    secreto: SecretStr = field(repr=False)


@dataclass(frozen=True)
class TokenEmitido:
    contexto_id: UUID
    expira_en: datetime
    token: SecretStr = field(repr=False)


class ServicioCsrf:
    def __init__(self, db: Session, configuracion: Configuracion,
                 reloj: Reloj = reloj_postgresql) -> None:
        self.db = db
        self.reloj = reloj
        self.sesiones = ServicioSesiones(db, reloj)
        self.token_bytes = configuracion.auth_csrf_token_bytes
        self.token_duracion = timedelta(seconds=configuracion.auth_csrf_token_segundos)
        self.contexto_duracion = timedelta(seconds=configuracion.auth_csrf_contexto_segundos)
        self.max_tokens = configuracion.auth_csrf_max_tokens

    @staticmethod
    def _resultado(contexto: ContextoCsrf) -> ContextoConsultado:
        return ContextoConsultado(contexto.id, contexto.tipo, contexto.expira_en)

    def crear_anonimo(self) -> ContextoEmitido:
        with operacion_bd(self.db):
            ahora = instante(self.db, self.reloj)
            secreto = generar_secreto()
            contexto = ContextoCsrf(tipo="anonymous",
                digest_secreto=digest_secreto(secreto, CodigoSeguridad.CONTEXTO_INVALIDO),
                creado_en=ahora, expira_en=ahora + self.contexto_duracion)
            self.db.add(contexto)
            self.db.flush()
            return ContextoEmitido(contexto.id, contexto.expira_en, secreto)

    def _contexto(self, anonimo: str | SecretStr | None,
                  sesion: str | SecretStr | None, *, crear: bool = False
                  ) -> tuple[ContextoCsrf, datetime, Sesion | None]:
        if (anonimo is None) == (sesion is None):
            raise ErrorSeguridad(CodigoSeguridad.CONTEXTO_INVALIDO)
        registro_sesion = usuario = None
        if anonimo is not None:
            digest = digest_secreto(anonimo, CodigoSeguridad.CONTEXTO_INVALIDO)
            contexto = self.db.scalar(select(ContextoCsrf).where(
                ContextoCsrf.tipo == "anonymous", ContextoCsrf.digest_secreto == digest,
            ).with_for_update().execution_options(populate_existing=True))
        else:
            registro_sesion, usuario = self.sesiones._bloquear_credencial(sesion)
            contexto = self.db.scalar(select(ContextoCsrf).where(
                ContextoCsrf.sesion_id == registro_sesion.id,
            ).with_for_update().execution_options(populate_existing=True))
            if contexto is None and crear:
                ahora = instante(self.db, self.reloj)
                self.sesiones._validar(registro_sesion, usuario, ahora)
                contexto = ContextoCsrf(tipo="authenticated", sesion_id=registro_sesion.id,
                    creado_en=ahora, expira_en=min(registro_sesion.expira_en,
                        registro_sesion.creado_en + DURACION_ABSOLUTA))
                self.db.add(contexto)
                self.db.flush()
        # Releer tiempo después de TODOS los locks, incluido contexto.
        ahora = instante(self.db, self.reloj)
        if registro_sesion is not None:
            self.sesiones._validar(registro_sesion, usuario, ahora)
        if contexto is None or contexto.revocado_en is not None or ahora >= contexto.expira_en:
            raise ErrorSeguridad(CodigoSeguridad.CONTEXTO_INVALIDO)
        return contexto, ahora, registro_sesion

    def recuperar_anonimo(self, secreto: str | SecretStr) -> ContextoConsultado:
        with operacion_bd(self.db):
            contexto, _, _ = self._contexto(secreto, None)
            return self._resultado(contexto)

    def obtener_autenticado(self, credencial: str | SecretStr) -> ContextoConsultado:
        with operacion_bd(self.db):
            contexto, _, _ = self._contexto(None, credencial, crear=True)
            return self._resultado(contexto)

    def emitir_token(self, *, anonimo: str | SecretStr | None = None,
                     sesion: str | SecretStr | None = None) -> TokenEmitido:
        with operacion_bd(self.db):
            contexto, ahora, registro_sesion = self._contexto(anonimo, sesion, crear=True)
            cantidad = self.db.scalar(select(func.count(TokenCsrf.id)).where(
                TokenCsrf.contexto_id == contexto.id, TokenCsrf.invalidado_en.is_(None),
                TokenCsrf.expira_en > ahora,
            ))
            if cantidad >= self.max_tokens:
                # No expulsar tokens vigentes de otras pestañas.
                raise ErrorSeguridad(CodigoSeguridad.LIMITE_TOKENS)
            expiracion = min(ahora + self.token_duracion, contexto.expira_en)
            if registro_sesion is not None:
                expiracion = min(expiracion, registro_sesion.expira_en,
                    registro_sesion.creado_en + DURACION_ABSOLUTA,
                    registro_sesion.ultima_actividad + INACTIVIDAD_MAXIMA)
            secreto = generar_secreto(self.token_bytes)
            token = TokenCsrf(contexto_id=contexto.id,
                digest_token=digest_secreto(secreto, CodigoSeguridad.TOKEN_INVALIDO),
                emitido_en=ahora, expira_en=expiracion)
            self.db.add(token)
            self.db.flush()
            return TokenEmitido(contexto.id, token.expira_en, secreto)

    def _token(self, contexto: ContextoCsrf, token: str | SecretStr) -> TokenCsrf:
        digest = digest_secreto(token, CodigoSeguridad.TOKEN_INVALIDO)
        registro = self.db.scalar(select(TokenCsrf).where(
            TokenCsrf.contexto_id == contexto.id, TokenCsrf.digest_token == digest,
        ).execution_options(populate_existing=True))
        if registro is None or not compare_digest(registro.digest_token, digest):
            raise ErrorSeguridad(CodigoSeguridad.TOKEN_INVALIDO)
        return registro

    def validar_token(self, token: str | SecretStr, *, anonimo: str | SecretStr | None = None,
                      sesion: str | SecretStr | None = None) -> ContextoConsultado:
        with operacion_bd(self.db):
            contexto, ahora, _ = self._contexto(anonimo, sesion)
            registro = self._token(contexto, token)
            if registro.invalidado_en is not None:
                raise ErrorSeguridad(CodigoSeguridad.TOKEN_INVALIDO)
            if ahora >= registro.expira_en:
                raise ErrorSeguridad(CodigoSeguridad.TOKEN_VENCIDO)
            return self._resultado(contexto)

    def invalidar_token(self, token: str | SecretStr, *, anonimo: str | SecretStr | None = None,
                        sesion: str | SecretStr | None = None) -> bool:
        with operacion_bd(self.db):
            contexto, ahora, _ = self._contexto(anonimo, sesion)
            registro = self._token(contexto, token)
            if registro.invalidado_en is not None:
                return False
            registro.invalidado_en = ahora
            self.db.flush()
            return True

    def invalidar_contexto(self, *, anonimo: str | SecretStr | None = None,
                           sesion: str | SecretStr | None = None) -> None:
        with operacion_bd(self.db):
            contexto, ahora, _ = self._contexto(anonimo, sesion)
            contexto.revocado_en = ahora
            self.db.execute(update(TokenCsrf).where(
                TokenCsrf.contexto_id == contexto.id, TokenCsrf.invalidado_en.is_(None),
            ).values(invalidado_en=ahora))
            self.db.flush()
