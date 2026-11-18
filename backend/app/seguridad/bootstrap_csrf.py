"""Coordinador interno: admisión durable y emisión confirmada, nunca HTTP.

El lock transaccional común prioriza corrección y capacidad acotada sobre
paralelismo. Todas las escrituras de este coordinador respetan ese lock.
"""

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import UUID

from pydantic import SecretStr, ValidationError
from sqlalchemy import Engine, delete, func, select, text, tuple_
from sqlalchemy.orm import Session

from app.configuracion import Configuracion
from app.persistencia.modelos import ContextoCsrf, CuotaBootstrapCsrf, TokenCsrf
from app.seguridad.csrf import ContextoEmitido, ServicioCsrf, TokenEmitido
from app.seguridad.politica_bootstrap import PoliticaBootstrap
from app.seguridad.proxies import IpVerificada
from app.seguridad.transacciones import (
    CodigoSeguridad as C, ErrorSeguridad, Reloj, instante, operacion_bd, reloj_postgresql,
)

# Namespace estable, independiente de cuenta/IP y de los locks de login.
LOCK_BOOTSTRAP = 0x53594E4353524601
GLOBAL = bytes(32)


class CuotaBootstrapAgotada(Exception):
    """Resultado interno; su traducción HTTP requiere decisión contractual."""

    def __init__(self, ambito: str, observado_en: datetime, fin: datetime) -> None:
        self.ambito = ambito
        self.observado_en = observado_en
        self.reintentar_en = fin
        super().__init__("Cuota de bootstrap agotada.")

    @property
    def retry_after(self) -> int:
        return ceil((self.reintentar_en - self.observado_en).total_seconds())


@dataclass(frozen=True)
class BootstrapEmitido:
    contexto_id: UUID
    token: TokenEmitido = field(repr=False)
    contexto_nuevo: ContextoEmitido | None = field(default=None, repr=False)


class ServicioBootstrapCsrf:
    def __init__(self, motor: Engine, configuracion: Configuracion,
                 reloj: Reloj = reloj_postgresql) -> None:
        try:
            if configuracion.auth_bootstrap is None:
                raise ValueError
            self.politica = PoliticaBootstrap.model_validate(
                configuracion.auth_bootstrap.model_dump())
            if self.politica.perfil == "ensayo" and configuracion.app_env != "testing":
                raise ValueError
            if not 32 <= configuracion.auth_csrf_token_bytes <= 128:
                raise ValueError
            # Exigir HMAC aunque el coordinador solo recibe su resultado acreditado.
            configuracion.obtener_clave_hmac()
            if motor.dialect.name != "postgresql":
                raise ValueError
        except (ValueError, ValidationError, AttributeError):
            raise ErrorSeguridad(C.INFRAESTRUCTURA) from None
        self.motor = motor.execution_options(isolation_level="READ COMMITTED")
        # Copia: no permitir cambios de configuración a mitad de una operación.
        self.configuracion = configuracion.model_copy(deep=True)
        self.configuracion.auth_csrf_token_segundos = self.politica.token_segundos
        self.configuracion.auth_csrf_contexto_segundos = self.politica.contexto_segundos
        self.configuracion.auth_csrf_max_tokens = self.politica.max_tokens
        self.reloj = reloj

    @contextmanager
    def _transaccion(self) -> Iterator[Session]:
        with Session(self.motor, expire_on_commit=False) as db:
            # Incluye adquisición de conexión y commit en la traducción saneada.
            with operacion_bd(db, exigir_transaccion=False), db.begin():
                db.execute(text("SELECT set_config('lock_timeout', :v, true)"),
                           {"v": f"{self.politica.lock_timeout_ms}ms"})
                db.execute(text("SELECT set_config('statement_timeout', :v, true)"),
                           {"v": f"{self.politica.statement_timeout_ms}ms"})
                db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": LOCK_BOOTSTRAP})
                yield db

    def _ahora(self, db: Session) -> datetime:
        return instante(db, self.reloj)

    def _limpiar(self, db: Session, ahora: datetime) -> dict[str, int]:
        lote = self.politica.lote_limpieza
        cuotas = select(CuotaBootstrapCsrf.ambito, CuotaBootstrapCsrf.identidad).where(
            CuotaBootstrapCsrf.fin <= ahora).order_by(CuotaBootstrapCsrf.fin).limit(lote)
        # Tupla de PK, sin acumular listas de tamaño no acotado en memoria.
        n_cuotas = db.execute(delete(CuotaBootstrapCsrf).where(
            tuple_(CuotaBootstrapCsrf.ambito, CuotaBootstrapCsrf.identidad).in_(cuotas)
        ).execution_options(synchronize_session=False)).rowcount
        tokens = select(TokenCsrf.id).join(ContextoCsrf).where(
            ContextoCsrf.tipo == "anonymous",
            (TokenCsrf.expira_en <= ahora) | (TokenCsrf.invalidado_en.is_not(None)),
        ).order_by(TokenCsrf.expira_en).limit(lote)
        n_tokens = db.execute(delete(TokenCsrf).where(TokenCsrf.id.in_(tokens))
                             .execution_options(synchronize_session=False)).rowcount
        contextos = select(ContextoCsrf.id).where(
            ContextoCsrf.tipo == "anonymous", ContextoCsrf.expira_en <= ahora,
            ~select(TokenCsrf.id).where(TokenCsrf.contexto_id == ContextoCsrf.id).exists(),
        ).order_by(ContextoCsrf.expira_en).limit(lote)
        n_contextos = db.execute(delete(ContextoCsrf).where(ContextoCsrf.id.in_(contextos))
                                .execution_options(synchronize_session=False)).rowcount
        return dict(cuotas=n_cuotas, tokens=n_tokens, contextos=n_contextos)

    def limpiar(self) -> dict[str, int]:
        """Un lote por llamada; el operador puede programarlo aun sin tráfico."""
        with self._transaccion() as db:
            return self._limpiar(db, self._ahora(db))

    def _consumir(self, db: Session, ambito: str, identidad: bytes,
                 ahora: datetime) -> CuotaBootstrapAgotada | None:
        politica = getattr(self.politica, ambito)
        fila = db.get(CuotaBootstrapCsrf, (ambito, identidad))
        if fila is not None and ahora < fila.inicio:
            # Un reloj que retrocede no reinicia una cuota.
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        if fila is not None and ahora < fila.fin and fila.usados >= politica.cantidad:
            return CuotaBootstrapAgotada(ambito, ahora, fila.fin)
        if fila is None:
            if db.scalar(select(func.count()).select_from(CuotaBootstrapCsrf)) >= self.politica.max_filas_cuota:
                raise ErrorSeguridad(C.INFRAESTRUCTURA)
            fila = CuotaBootstrapCsrf(ambito=ambito, identidad=identidad)
            db.add(fila)
        if fila.fin is None or ahora >= fila.fin:
            segundos = int(ahora.timestamp())
            fila.inicio = datetime.fromtimestamp(
                segundos - segundos % politica.segundos, UTC)
            fila.fin = fila.inicio + timedelta(seconds=politica.segundos)
            fila.usados = 0
        fila.usados += 1
        db.flush()
        return None

    def _reservar_admision(self, ip: IpVerificada, *, nuevo: bool) -> None:
        if not isinstance(ip, IpVerificada):
            raise ErrorSeguridad(C.IP_NO_VERIFICABLE)
        rechazo = None
        with self._transaccion() as db:
            ahora = self._ahora(db)
            self._limpiar(db, ahora)
            # Global primero: rechazos globales no generan filas para nuevas IP.
            ambitos = [("intentos_global", GLOBAL), ("intentos_ip", ip.digest)]
            if nuevo:
                ambitos += [("contextos_global", GLOBAL), ("contextos_ip", ip.digest)]
            for ambito, identidad in ambitos:
                rechazo = self._consumir(db, ambito, identidad, ahora)
                if rechazo is not None:
                    break
        # Rechazo fuera del bloque: confirma los presupuestos ya consumidos.
        if rechazo is not None:
            raise rechazo

    @staticmethod
    def _identidad_contexto(contexto_id: UUID) -> bytes:
        return hashlib.sha256(b"synapdesk:bootstrap:contexto\0" + contexto_id.bytes).digest()

    def _reservar_contexto(self, anonimo: str | SecretStr) -> None:
        rechazo = None
        with self._transaccion() as db:
            csrf = ServicioCsrf(db, self.configuracion, self.reloj)
            contexto = csrf.recuperar_anonimo(anonimo)
            rechazo = self._consumir(db, "emisiones_contexto",
                self._identidad_contexto(contexto.id), self._ahora(db))
        if rechazo is not None:
            raise rechazo

    def emitir(self, *, ip: IpVerificada,
               anonimo: str | SecretStr | None = None) -> BootstrapEmitido:
        """Ningún UUID ni reserva reutilizable se acepta como autoridad.

        Una credencial inválida/saturada nunca activa creación de reemplazo.
        Los intentos y reservas de creación sobreviven a cualquier fallo posterior.
        """
        self._reservar_admision(ip, nuevo=anonimo is None)
        if anonimo is not None:
            self._reservar_contexto(anonimo)
        with self._transaccion() as db:
            ahora = self._ahora(db)
            self._limpiar(db, ahora)
            csrf = ServicioCsrf(db, self.configuracion, self.reloj)
            nuevo = None
            if anonimo is None:
                if db.scalar(select(func.count()).select_from(ContextoCsrf).where(
                    ContextoCsrf.tipo == "anonymous")) >= self.politica.max_contextos:
                    raise ErrorSeguridad(C.INFRAESTRUCTURA)
                nuevo = csrf.crear_anonimo()
                anonimo = nuevo.secreto
                rechazo = self._consumir(db, "emisiones_contexto",
                    self._identidad_contexto(nuevo.id), self._ahora(db))
                if rechazo is not None:
                    raise rechazo
            if db.scalar(select(func.count()).select_from(TokenCsrf).join(ContextoCsrf).where(
                ContextoCsrf.tipo == "anonymous")) >= self.politica.max_filas_tokens:
                raise ErrorSeguridad(C.INFRAESTRUCTURA)
            token = csrf.emitir_token(anonimo=anonimo)
            resultado = BootstrapEmitido(token.contexto_id, token, nuevo)
        # Solo se expone el secreto tras confirmar la emisión.
        return resultado
