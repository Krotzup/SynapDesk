from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hmac import compare_digest
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.persistencia.modelos import ContextoCsrf, Sesion, TokenCsrf, Usuario
from app.seguridad.secretos import digest_secreto, generar_secreto
from app.seguridad.transacciones import (
    CodigoSeguridad, ErrorSeguridad, Reloj, instante, operacion_bd, reloj_postgresql,
)

DURACION_ABSOLUTA = timedelta(hours=8)
INACTIVIDAD_MAXIMA = timedelta(minutes=30)


@dataclass(frozen=True)
class Identidad:
    id: UUID
    email: str
    role: str


@dataclass(frozen=True)
class SesionConsultada:
    id: UUID
    usuario: Identidad
    ultima_actividad: datetime
    expira_en: datetime


@dataclass(frozen=True)
class SesionEmitida:
    id: UUID
    expira_en: datetime
    credencial: SecretStr = field(repr=False)


def bloquear_contextos(db: Session, sesion_id: UUID) -> list[ContextoCsrf]:
    return list(db.scalars(select(ContextoCsrf).where(
        ContextoCsrf.sesion_id == sesion_id,
    ).order_by(ContextoCsrf.id).with_for_update().execution_options(populate_existing=True)))


def invalidar_contextos(db: Session, contextos: list[ContextoCsrf], ahora: datetime) -> None:
    for contexto in contextos:
        contexto.revocado_en = contexto.revocado_en or max(ahora, contexto.creado_en)
        db.execute(update(TokenCsrf).where(
            TokenCsrf.contexto_id == contexto.id, TokenCsrf.invalidado_en.is_(None),
        ).values(invalidado_en=ahora))


class ServicioSesiones:
    def __init__(self, db: Session, reloj: Reloj = reloj_postgresql) -> None:
        self.db = db
        self.reloj = reloj

    def _usuarios(self, ids: set[UUID]) -> dict[UUID, Usuario]:
        # SHARE permite sesiones independientes y bloquea cambios de rol/estado.
        usuarios = self.db.scalars(select(Usuario).where(Usuario.id.in_(ids)).order_by(
            Usuario.id,
        ).with_for_update(read=True).execution_options(populate_existing=True)).all()
        return {usuario.id: usuario for usuario in usuarios}

    @staticmethod
    def _validar_usuario(usuario: Usuario | None) -> None:
        if usuario is None:
            raise ErrorSeguridad(CodigoSeguridad.USUARIO_INEXISTENTE)
        if not usuario.activo:
            raise ErrorSeguridad(CodigoSeguridad.USUARIO_INACTIVO)
        if usuario.rol not in {"admin", "agent"}:
            raise ErrorSeguridad(CodigoSeguridad.ROL_INVALIDO)

    @staticmethod
    def _validar(sesion: Sesion, usuario: Usuario, ahora: datetime) -> None:
        if sesion.revocada_en is not None:
            raise ErrorSeguridad(CodigoSeguridad.SESION_REVOCADA)
        if ahora >= min(sesion.expira_en, sesion.creado_en + DURACION_ABSOLUTA,
                        sesion.ultima_actividad + INACTIVIDAD_MAXIMA):
            raise ErrorSeguridad(CodigoSeguridad.SESION_VENCIDA)
        ServicioSesiones._validar_usuario(usuario)

    def _bloquear_id(self, sesion_id: UUID) -> tuple[Sesion, Usuario]:
        usuario_id = self.db.scalar(select(Sesion.usuario_id).where(Sesion.id == sesion_id))
        if usuario_id is None:
            raise ErrorSeguridad(CodigoSeguridad.SESION_INEXISTENTE)
        usuarios = self._usuarios({usuario_id})
        sesion = self.db.scalar(select(Sesion).where(Sesion.id == sesion_id).with_for_update(
        ).execution_options(populate_existing=True))
        if sesion is None or sesion.usuario_id != usuario_id:
            raise ErrorSeguridad(CodigoSeguridad.SESION_INEXISTENTE)
        usuario = usuarios.get(usuario_id)
        if usuario is None:
            raise ErrorSeguridad(CodigoSeguridad.USUARIO_INEXISTENTE)
        return sesion, usuario

    def _bloquear_credencial(self, credencial: str | SecretStr) -> tuple[Sesion, Usuario]:
        digest = digest_secreto(credencial, CodigoSeguridad.SESION_INEXISTENTE)
        sesion_id = self.db.scalar(select(Sesion.id).where(Sesion.digest_credencial == digest))
        if sesion_id is None:
            raise ErrorSeguridad(CodigoSeguridad.SESION_INEXISTENTE)
        sesion, usuario = self._bloquear_id(sesion_id)
        if not compare_digest(sesion.digest_credencial, digest):
            raise ErrorSeguridad(CodigoSeguridad.SESION_INEXISTENTE)
        return sesion, usuario

    def crear(self, usuario_id: UUID, *, presentada: str | SecretStr | None = None) -> SesionEmitida:
        """Primitiva interna: el llamador verificó credenciales; no es login."""
        with operacion_bd(self.db):
            anterior_id = anterior_usuario_id = None
            if presentada is not None:
                digest = digest_secreto(presentada, CodigoSeguridad.SESION_INEXISTENTE)
                anterior = self.db.execute(select(Sesion.id, Sesion.usuario_id).where(
                    Sesion.digest_credencial == digest,
                )).first()
                if anterior is None:
                    raise ErrorSeguridad(CodigoSeguridad.SESION_INEXISTENTE)
                anterior_id, anterior_usuario_id = anterior
            ids = {usuario_id}
            if anterior_usuario_id is not None:
                ids.add(anterior_usuario_id)
            usuarios = self._usuarios(ids)
            self._validar_usuario(usuarios.get(usuario_id))
            anterior = None
            if anterior_id is not None:
                anterior = self.db.scalar(select(Sesion).where(Sesion.id == anterior_id).with_for_update(
                ).execution_options(populate_existing=True))
                if (anterior is None or anterior.usuario_id != anterior_usuario_id
                        or not compare_digest(anterior.digest_credencial, digest)):
                    raise ErrorSeguridad(CodigoSeguridad.SESION_INEXISTENTE)
            contextos = bloquear_contextos(self.db, anterior.id) if anterior is not None else []
            ahora = instante(self.db, self.reloj)
            if anterior is not None:
                self._validar(anterior, usuarios[anterior.usuario_id], ahora)
                invalidar_contextos(self.db, contextos, ahora)
                anterior.revocada_en = ahora
                anterior.motivo_revocacion = "reemplazo"
            secreto = generar_secreto()
            sesion = Sesion(usuario_id=usuario_id,
                digest_credencial=digest_secreto(secreto, CodigoSeguridad.SESION_INEXISTENTE),
                creado_en=ahora, ultima_actividad=ahora, expira_en=ahora + DURACION_ABSOLUTA)
            self.db.add(sesion)
            self.db.flush()
            return SesionEmitida(sesion.id, sesion.expira_en, secreto)

    def consultar(self, credencial: str | SecretStr) -> SesionConsultada:
        with operacion_bd(self.db):
            sesion, usuario = self._bloquear_credencial(credencial)
            self._validar(sesion, usuario, instante(self.db, self.reloj))
            return SesionConsultada(sesion.id, Identidad(usuario.id, usuario.correo, usuario.rol),
                                    sesion.ultima_actividad, sesion.expira_en)

    def registrar_actividad(self, credencial: str | SecretStr) -> SesionConsultada:
        """Solo tras autorización del llamador; consultar/CSRF no la invocan."""
        with operacion_bd(self.db):
            sesion, usuario = self._bloquear_credencial(credencial)
            ahora = instante(self.db, self.reloj)
            self._validar(sesion, usuario, ahora)
            sesion.ultima_actividad = max(sesion.ultima_actividad, ahora)
            self.db.flush()
            return SesionConsultada(sesion.id, Identidad(usuario.id, usuario.correo, usuario.rol),
                                    sesion.ultima_actividad, sesion.expira_en)

    def revocar(self, credencial: str | SecretStr) -> bool:
        with operacion_bd(self.db):
            sesion, _ = self._bloquear_credencial(credencial)
            if sesion.revocada_en is not None:
                return False
            contextos = bloquear_contextos(self.db, sesion.id)
            ahora = instante(self.db, self.reloj)
            invalidar_contextos(self.db, contextos, ahora)
            sesion.revocada_en = max(ahora, sesion.creado_en)
            sesion.motivo_revocacion = "individual"
            self.db.flush()
            return True
