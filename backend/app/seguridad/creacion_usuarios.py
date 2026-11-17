"""Alta interna aprobada AUTH-07C.2: cuenta y auditoría en un commit.

No acredita el transporte administrativo ni registra rutas HTTP. La captura y
entrega privada de credenciales corresponden a la integración y al operador.
"""

from dataclasses import dataclass, field
from enum import StrEnum
import re
from typing import Literal
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.esquemas_auth import AuthUser, SolicitudLogin
from app.configuracion import Configuracion
from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import Usuario
from app.seguridad.auditoria import (
    ActorUsuario, MotivoEvento as M, ResultadoEvento as R, ServicioAuditoria, TipoEvento as T,
)
from app.seguridad.contrasenas import ErrorContrasena, ServicioContrasenas
from app.seguridad.operaciones_sesion import ReferenciaSesion
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import (
    CodigoSeguridad, ErrorSeguridad, Reloj, operacion_bd, reloj_postgresql,
    transaccion_seguridad,
)


RolNuevoUsuario = Literal["admin", "agent"]


class CodigoCreacionUsuario(StrEnum):
    ENTRADA = "ENTRADA"
    HASH = "HASH"
    NO_AUTORIZADO = "NO_AUTORIZADO"
    CORREO_EXISTENTE = "CORREO_EXISTENTE"
    DESTINO_ENSAYO = "DESTINO_ENSAYO"


class ErrorCreacionUsuario(Exception):
    """Código interno; no es un código HTTP ni incluye datos de entrada."""

    def __init__(self, codigo: CodigoCreacionUsuario) -> None:
        self.codigo = codigo
        super().__init__(f"Creación administrativa rechazada: {codigo.value}.")


def permite_creacion(rol_actual: str | None, rol_solicitado: str) -> bool:
    """Matriz aprobada; el coordinador obtiene rol_actual de PostgreSQL."""
    return rol_actual == "admin" and rol_solicitado in ("admin", "agent")


@dataclass(frozen=True)
class DatosNuevoUsuario:
    nombre: str = field(repr=False)
    correo: str = field(repr=False)
    rol: RolNuevoUsuario
    contrasena: SecretStr = field(repr=False)

    def __post_init__(self) -> None:
        try:
            correo = SolicitudLogin.validar_email(self.correo)
            if (not isinstance(self.nombre, str) or not self.nombre.strip()
                    or "\x00" in self.nombre or self.rol not in ("admin", "agent")
                    or not isinstance(self.contrasena, SecretStr)
                    or not ServicioContrasenas._entrada_valida(self.contrasena.get_secret_value())):
                raise ValueError
            self.nombre.encode("utf-8")
        except (TypeError, ValueError):
            raise ErrorCreacionUsuario(CodigoCreacionUsuario.ENTRADA) from None
        object.__setattr__(self, "correo", correo)


@dataclass(frozen=True)
class UsuarioPreparado:
    """Valor interno de confianza, nunca deserializarlo desde un cliente."""

    nombre: str = field(repr=False)
    correo: str = field(repr=False)
    rol: RolNuevoUsuario
    hash_contrasena: SecretStr = field(repr=False)
    _emisor: object = field(repr=False)


@dataclass(frozen=True)
class EnsayoCreacionUsuario:
    """Cuenta y evento insertados por el flujo real, ambos ya revertidos."""

    usuario: AuthUser
    evento_id: UUID
    persistido: bool = field(default=False, init=False)
    auditoria_registrada: bool = field(default=False, init=False)


class ServicioCreacionUsuarios:
    def __init__(self, configuracion: Configuracion, *, reloj: Reloj = reloj_postgresql) -> None:
        if not configuracion.tiene_configuracion_bd:
            raise ErrorSeguridad(CodigoSeguridad.INFRAESTRUCTURA)
        self._config = configuracion.model_copy(deep=True)
        self._motor = crear_motor_bd(self._config).execution_options(isolation_level="READ COMMITTED")
        self._contrasenas = ServicioContrasenas(self._config)
        self._reloj = reloj
        self._emisor = object()

    def cerrar(self) -> None:
        self._motor.dispose()

    def preparar(self, datos: DatosNuevoUsuario) -> UsuarioPreparado:
        if type(datos) is not DatosNuevoUsuario:
            raise ErrorCreacionUsuario(CodigoCreacionUsuario.ENTRADA)
        # No abre conexión ni mantiene transacción durante Argon2id.
        try:
            protegido = self._contrasenas.generar_hash(datos.contrasena.get_secret_value())
        except ErrorContrasena:
            raise ErrorCreacionUsuario(CodigoCreacionUsuario.HASH) from None
        return UsuarioPreparado(datos.nombre, datos.correo, datos.rol, SecretStr(protegido), self._emisor)

    def _validar_entrada(self, referencia: ReferenciaSesion | None, preparado: UsuarioPreparado) -> None:
        if type(referencia) is not ReferenciaSesion:
            raise ErrorSeguridad(CodigoSeguridad.SESION_INEXISTENTE)
        if type(preparado) is not UsuarioPreparado or preparado._emisor is not self._emisor:
            raise ErrorCreacionUsuario(CodigoCreacionUsuario.ENTRADA)

    def _insertar(self, db: Session, referencia: ReferenciaSesion,
                  preparado: UsuarioPreparado) -> tuple[AuthUser, UUID]:
        """Único flujo SQL, compartido por creación y ensayo; no hace commit."""
        db.execute(text("SET LOCAL search_path = pg_catalog, public"))
        db.execute(text("SET LOCAL lock_timeout = '3s'"))
        sesiones = ServicioSesiones(db, self._reloj)

        def autorizar():
            # Usuario FOR SHARE → sesión FOR UPDATE, populate_existing y reloj
            # posterior a locks. No aceptar un AuthUser o rol antiguo del cliente.
            actual = sesiones.consultar(referencia.credencial)
            if not permite_creacion(actual.usuario.role, preparado.rol):
                raise ErrorCreacionUsuario(CodigoCreacionUsuario.NO_AUTORIZADO)
            return actual

        autorizar()
        if db.scalar(select(Usuario.id).where(Usuario.correo == preparado.correo)) is not None:
            raise ErrorCreacionUsuario(CodigoCreacionUsuario.CORREO_EXISTENTE)
        usuario = Usuario(nombre=preparado.nombre, correo=preparado.correo,
            rol=preparado.rol, activo=True, hash_contrasena=preparado.hash_contrasena.get_secret_value())
        db.add(usuario)
        try:
            db.flush()
        except IntegrityError as error:
            if getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "uq_usuarios_correo":
                raise ErrorCreacionUsuario(CodigoCreacionUsuario.CORREO_EXISTENTE) from None
            raise
        # Una espera por UNIQUE no congela la vigencia de la sesión.
        actual = autorizar()
        evento = ServicioAuditoria(db, self._reloj).registrar(
            tipo=T.USUARIO_CREADO, resultado=R.EXITO, motivo=M.ALTA_ADMINISTRATIVA,
            request_id=uuid4(), usuario_id=usuario.id, sesion_id=actual.id,
            actor=ActorUsuario(actual.usuario.id), rol_asignado=preparado.rol)
        # También la escritura de auditoría puede haber esperado un lock.
        autorizar()
        return AuthUser(id=usuario.id, email=usuario.correo, role=usuario.rol), evento.id

    def crear(self, referencia: ReferenciaSesion | None, preparado: UsuarioPreparado) -> AuthUser:
        self._validar_entrada(referencia, preparado)
        with Session(self._motor) as db, transaccion_seguridad(db):
            usuario, _ = self._insertar(db, referencia, preparado)
        # Solo después del commit. Sin contraseña, hash, sesión ni envío externo.
        return usuario

    def _exigir_base_temporal(self) -> None:
        c = self._config
        if (c.app_env != "testing" or c.postgres_port != 5433
                or c.postgres_host not in {"localhost", "127.0.0.1", "::1"}
                or not re.fullmatch(r"synapdesk_auth07_sec01a_[a-f0-9]{32}", c.postgres_db or "")):
            raise ErrorCreacionUsuario(CodigoCreacionUsuario.DESTINO_ENSAYO)

    def ensayar(self, referencia: ReferenciaSesion | None,
                preparado: UsuarioPreparado) -> EnsayoCreacionUsuario:
        """Ejecuta exactamente la inserción y auditoría reales, siempre con rollback."""
        self._exigir_base_temporal()
        self._validar_entrada(referencia, preparado)
        with Session(self._motor) as db, operacion_bd(db, exigir_transaccion=False):
            db.begin()
            try:
                identidad = db.execute(text("SELECT current_database(), session_user, current_user")).one()
                if identidad != (self._config.postgres_db, self._config.postgres_user, self._config.postgres_user):
                    raise ErrorCreacionUsuario(CodigoCreacionUsuario.DESTINO_ENSAYO)
                if set(db.scalars(text("SELECT version_num FROM public.alembic_version"))) != {"0006_user_created"}:
                    raise ErrorCreacionUsuario(CodigoCreacionUsuario.DESTINO_ENSAYO)
                usuario, evento_id = self._insertar(db, referencia, preparado)
            finally:
                db.rollback()
        return EnsayoCreacionUsuario(usuario, evento_id)
