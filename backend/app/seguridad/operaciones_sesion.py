"""Consulta y logout internos. No extraen cookies ni acreditan el canal HTTP."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.api.esquemas_auth import AuthUser
from app.configuracion import Configuracion
from app.seguridad.auditoria import (
    MotivoEvento as M, ResultadoEvento as R, ServicioAuditoria, TipoEvento as T,
)
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.secretos import digest_secreto
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import (
    CodigoSeguridad as C, ErrorSeguridad, Reloj, reloj_postgresql, transaccion_seguridad,
)


@dataclass(frozen=True)
class ReferenciaSesion:
    """Posesión presentada por una frontera autorizada, NO prueba de vigencia.

    El adaptador futuro debe extraer una única cookie permitida, sin aceptar
    identidad, UUID o booleano del cliente. Toda operación reconsulta PostgreSQL.
    """

    credencial: SecretStr = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.credencial, SecretStr):
            raise ErrorSeguridad(C.SESION_INEXISTENTE)
        digest_secreto(self.credencial, C.SESION_INEXISTENTE)


@dataclass(frozen=True)
class LogoutConfirmado:
    """Resultado post-commit; False no afirma una revocación inexistente."""

    revocada: bool


def _referencia(referencia: ReferenciaSesion | None) -> SecretStr:
    if type(referencia) is not ReferenciaSesion:
        raise ErrorSeguridad(C.SESION_INEXISTENTE)
    return referencia.credencial


def _motor_postgresql(motor: Engine) -> Engine:
    if motor.dialect.name != "postgresql":
        raise ErrorSeguridad(C.INFRAESTRUCTURA)
    return motor.execution_options(isolation_level="READ COMMITTED")


class ServicioConsultaSesion:
    def __init__(self, motor: Engine, *, reloj: Reloj = reloj_postgresql) -> None:
        self._motor = _motor_postgresql(motor)
        self._reloj = reloj

    def consultar(self, referencia: ReferenciaSesion | None) -> AuthUser:
        credencial = _referencia(referencia)
        with Session(self._motor) as db, transaccion_seguridad(db):
            actual = ServicioSesiones(db, self._reloj).consultar(credencial)
            # Proyección explícita del DTO existente, nunca serializar ORM/sesión.
            usuario = AuthUser(id=actual.usuario.id, email=actual.usuario.email,
                               role=actual.usuario.role)
        # Consultar no llama registrar_actividad ni emite credenciales.
        return usuario


class ServicioLogout:
    def __init__(self, motor: Engine, configuracion: Configuracion, *,
                 reloj: Reloj = reloj_postgresql) -> None:
        self._motor = _motor_postgresql(motor)
        self._config = configuracion.model_copy(deep=True)
        self._reloj = reloj

    def _auditar_rechazo(self, error: ErrorSeguridad, request_id: UUID) -> None:
        motivo = M.CSRF if error.codigo in {
            C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO,
        } else M.SESION_INVALIDA if error.codigo in {
            C.USUARIO_INACTIVO, C.USUARIO_INEXISTENTE, C.ROL_INVALIDO,
        } else M.INFRAESTRUCTURA
        # Transacción nueva tras rollback. Un fallo tampoco se oculta aquí.
        with Session(self._motor) as db, transaccion_seguridad(db):
            ServicioAuditoria(db, self._reloj).registrar(
                tipo=T.VALIDACION, resultado=R.RECHAZO, motivo=motivo,
                request_id=request_id)

    def cerrar(self, referencia: ReferenciaSesion | None, *,
               token: SecretStr | None = None, request_id: UUID | None = None) -> LogoutConfirmado:
        # Origin siempre corresponde a la frontera HTTP, incluso en esta rama.
        if request_id is not None and not isinstance(request_id, UUID):
            raise ErrorSeguridad(C.CONTEXTO_INVALIDO)
        if referencia is None:
            return LogoutConfirmado(revocada=False)
        credencial = _referencia(referencia)
        request_id = request_id or uuid4()
        try:
            with Session(self._motor) as db, transaccion_seguridad(db):
                sesiones = ServicioSesiones(db, self._reloj)
                actual = sesiones.consultar(credencial)
                if not isinstance(token, SecretStr):
                    raise ErrorSeguridad(C.TOKEN_INVALIDO)
                ServicioCsrf(db, self._config, self._reloj).validar_token(
                    token, sesion=credencial)
                # Revalidar después de esperar también el lock del contexto.
                sesiones.consultar(credencial)
                revocada = sesiones.revocar(credencial)
                if not revocada:
                    raise ErrorSeguridad(C.SESION_REVOCADA)
                ServicioAuditoria(db, self._reloj).registrar(
                    tipo=T.SESION_REVOCADA, resultado=R.EXITO, motivo=M.LOGOUT,
                    usuario_id=actual.usuario.id, sesion_id=actual.id,
                    request_id=request_id)
        except ErrorSeguridad as error:
            if error.codigo in {C.SESION_INEXISTENTE, C.SESION_VENCIDA, C.SESION_REVOCADA}:
                # Contrato sección 7: ausencia confirmada, sin evento ficticio.
                return LogoutConfirmado(revocada=False)
            self._auditar_rechazo(error, request_id)
            raise
        return LogoutConfirmado(revocada=True)
