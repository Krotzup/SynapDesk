"""Bootstrap administrativo explícito. Usuario y actor externo se confirman juntos."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from hmac import compare_digest
import re
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.esquemas_auth import SolicitudLogin
from app.configuracion import Configuracion
from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import EventoAutenticacion, Usuario
from app.seguridad.auditoria import (
    ActorExterno, MotivoEvento as M, ResultadoEvento as R, ServicioAuditoria, TipoEvento as T,
)
from app.seguridad.contrasenas import ErrorContrasena, ServicioContrasenas
from app.seguridad.transacciones import operacion_bd, transaccion_seguridad


class CodigoBootstrap(StrEnum):
    CONFIGURACION = "CONFIGURACION"
    DESTINO = "DESTINO"
    ENTRADA = "ENTRADA"
    CONFIRMACION = "CONFIRMACION"
    HASH = "HASH"
    INSTALACION_NO_VACIA = "INSTALACION_NO_VACIA"
    AUTORIZACION = "AUTORIZACION"
    ESQUEMA = "ESQUEMA"
    CANAL = "CANAL"


class ErrorBootstrap(Exception):
    def __init__(self, codigo: CodigoBootstrap) -> None:
        self.codigo = codigo
        super().__init__(f"Bootstrap rechazado: {codigo.value}.")


REVISION_BOOTSTRAP = "0008_predicciones_ticket"


@dataclass(frozen=True)
class IdentidadDestino:
    cluster: str
    base_oid: int
    operador_oid: int
    usuarios_oid: int
    eventos_oid: int


@dataclass(frozen=True)
class DestinoAutorizado:
    """Evidencia interna emitida por verificar_destino; no aceptar JSON/booleanos.

    Los fixtures pueden construirla tras identificar su base SQL aislada. No hay
    tal adaptador en CLI: siempre verifica TLS y propietario PostgreSQL reales.
    """

    identidad: IdentidadDestino
    confirmacion: str
    _emisor: object = field(repr=False)


@dataclass(frozen=True)
class AdminConfirmado:
    usuario_id: UUID
    evento_id: UUID


@dataclass(frozen=True)
class AdminPreparado:
    nombre: str = field(repr=False)
    correo: str = field(repr=False)
    hash_contrasena: SecretStr = field(repr=False)
    _emisor: object = field(repr=False)


@dataclass(frozen=True)
class EnsayoBootstrap:
    """Comprobación provisional revertida; no es una identidad autenticada."""

    persistido: bool = field(default=False, init=False)


class ServicioBootstrapAdmin:
    def __init__(self, configuracion: Configuracion) -> None:
        if not configuracion.tiene_configuracion_bd:
            raise ErrorBootstrap(CodigoBootstrap.CONFIGURACION)
        self._config = configuracion.model_copy(deep=True)
        self._emisor = object()
        self._contrasenas = ServicioContrasenas(self._config)
        self._motor = crear_motor_bd(self._config).execution_options(
            isolation_level="READ COMMITTED")

    def cerrar(self) -> None:
        self._motor.dispose()

    @property
    def destino(self) -> str:
        c = self._config
        # Metadatos, sin usuario, contraseña, URL ni opciones de conexión.
        return f"{c.app_env}|{c.postgres_host}|{c.postgres_port}|{c.postgres_db}"

    def preparar(self, *, nombre: str, correo: str, contrasena: SecretStr,
                 confirmacion: SecretStr) -> AdminPreparado:
        try:
            # Reutiliza la misma sintaxis/normalización que el login existente.
            correo = SolicitudLogin.validar_email(correo)
            if (not isinstance(nombre, str) or not nombre.strip() or "\x00" in nombre
                    or not isinstance(contrasena, SecretStr)
                    or not isinstance(confirmacion, SecretStr)
                    or not ServicioContrasenas._entrada_valida(contrasena.get_secret_value())
                    or not ServicioContrasenas._entrada_valida(confirmacion.get_secret_value())):
                raise ValueError
            nombre.encode("utf-8")
        except (ValueError, TypeError):
            raise ErrorBootstrap(CodigoBootstrap.ENTRADA) from None
        if not compare_digest(contrasena.get_secret_value().encode("utf-8"),
                              confirmacion.get_secret_value().encode("utf-8")):
            raise ErrorBootstrap(CodigoBootstrap.CONFIRMACION)
        # Argon2 fuera de conexión, transacción y bloqueos.
        try:
            hash_contrasena = self._contrasenas.generar_hash(contrasena.get_secret_value())
        except ErrorContrasena:
            raise ErrorBootstrap(CodigoBootstrap.HASH) from None
        return AdminPreparado(nombre, correo, SecretStr(hash_contrasena), self._emisor)

    def _identificar(self, db: Session) -> IdentidadDestino:
        """Validación SQL real, reutilizada antes y después del bloqueo de alta."""
        db.execute(text("SET LOCAL search_path = pg_catalog, public"))
        fila = db.execute(text(
            "SELECT d.oid::bigint AS base_oid, r.oid::bigint AS operador_oid, "
            "d.datdba::bigint AS propietario_oid, current_database() AS base, "
            "session_user AS operador, current_user AS efectivo "
            "FROM pg_catalog.pg_database d JOIN pg_catalog.pg_roles r ON r.rolname=session_user "
            "WHERE d.datname=current_database()" )).mappings().one()
        if fila["base"] != self._config.postgres_db or fila["operador"] != self._config.postgres_user:
            raise ErrorBootstrap(CodigoBootstrap.DESTINO)
        if fila["operador"] != fila["efectivo"] or fila["operador_oid"] != fila["propietario_oid"]:
            raise ErrorBootstrap(CodigoBootstrap.AUTORIZACION)
        cluster = db.scalar(text("SELECT system_identifier::text FROM pg_catalog.pg_control_system()"))
        if not self._config.auth_bootstrap_cluster_id or cluster != self._config.auth_bootstrap_cluster_id:
            raise ErrorBootstrap(CodigoBootstrap.DESTINO)
        if set(db.scalars(text("SELECT version_num FROM public.alembic_version"))) != {REVISION_BOOTSTRAP}:
            raise ErrorBootstrap(CodigoBootstrap.ESQUEMA)
        oids = db.execute(text("SELECT 'public.usuarios'::regclass::oid::bigint, "
                               "'public.eventos_autenticacion'::regclass::oid::bigint")).one()
        columnas = set(db.execute(text(
            "SELECT table_name,column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name IN ('usuarios','eventos_autenticacion')")))
        necesarias = {("usuarios", c) for c in ("id", "nombre", "correo", "hash_contrasena", "rol", "activo")}
        necesarias |= {("eventos_autenticacion", c) for c in (
            "id", "usuario_id", "tipo_evento", "resultado", "motivo", "actor_tipo", "actor_id")}
        restricciones = set(db.scalars(text(
            "SELECT conname FROM pg_catalog.pg_constraint WHERE convalidated "
            "AND conrelid IN ('public.usuarios'::regclass,'public.eventos_autenticacion'::regclass)")))
        if not necesarias <= columnas or not {
            "uq_usuarios_correo", "ck_usuarios_rol_valido",
            "ck_eventos_autenticacion_actor_externo_valido",
        } <= restricciones:
            raise ErrorBootstrap(CodigoBootstrap.ESQUEMA)
        for tabla in ("public.usuarios", "public.eventos_autenticacion"):
            for permiso in ("SELECT", "INSERT") + (("UPDATE",) if tabla == "public.usuarios" else ()):
                if not db.scalar(text("SELECT has_table_privilege(session_user,:tabla,:permiso)"),
                                 dict(tabla=tabla, permiso=permiso)):
                    raise ErrorBootstrap(CodigoBootstrap.AUTORIZACION)
        return IdentidadDestino(cluster, fila["base_oid"], fila["operador_oid"], *oids)

    def verificar_destino(self) -> DestinoAutorizado:
        # No deducir identidad del servidor desde loopback, puerto o ssl=require.
        if self._config.postgres_sslmode != "verify-full":
            raise ErrorBootstrap(CodigoBootstrap.CANAL)
        if not self._config.auth_bootstrap_cluster_id:
            raise ErrorBootstrap(CodigoBootstrap.CONFIGURACION)
        with Session(self._motor) as db, transaccion_seguridad(db):
            if not db.scalar(text("SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid=pg_backend_pid()")):
                raise ErrorBootstrap(CodigoBootstrap.CANAL)
            identidad = self._identificar(db)
        confirmacion = f"{self.destino}|cluster={identidad.cluster}|db={identidad.base_oid}|{REVISION_BOOTSTRAP}"
        return DestinoAutorizado(identidad, confirmacion, self._emisor)

    def crear(self, preparado: AdminPreparado, *, destino: DestinoAutorizado | None = None,
              confirmar_destino: str | None = None) -> AdminConfirmado:
        if (type(destino) is not DestinoAutorizado or destino._emisor is not self._emisor
                or not isinstance(confirmar_destino, str) or confirmar_destino != destino.confirmacion):
            raise ErrorBootstrap(CodigoBootstrap.DESTINO)
        if type(preparado) is not AdminPreparado or preparado._emisor is not self._emisor:
            raise ErrorBootstrap(CodigoBootstrap.ENTRADA)
        with Session(self._motor) as db, transaccion_seguridad(db):
            db.execute(text("SET LOCAL lock_timeout = '3s'"))
            # SHARE ROW EXCLUSIVE conserva la exclusión probada, incluso frente
            # a INSERT ajenos. El trabajo Argon2 ya terminó antes de esta conexión.
            if self._identificar(db) != destino.identidad:
                raise ErrorBootstrap(CodigoBootstrap.DESTINO)
            db.execute(text("LOCK TABLE public.usuarios IN SHARE ROW EXCLUSIVE MODE"))
            if self._identificar(db) != destino.identidad:
                raise ErrorBootstrap(CodigoBootstrap.DESTINO)
            if db.scalar(select(Usuario.id).limit(1)) is not None:
                raise ErrorBootstrap(CodigoBootstrap.INSTALACION_NO_VACIA)
            if db.scalar(select(EventoAutenticacion.id).where(
                    EventoAutenticacion.tipo_evento == T.ADMIN_BOOTSTRAP.value).limit(1)) is not None:
                # La eliminación posterior de usuarios no convierte bootstrap en recuperación.
                raise ErrorBootstrap(CodigoBootstrap.INSTALACION_NO_VACIA)
            usuario = Usuario(nombre=preparado.nombre, correo=preparado.correo,
                hash_contrasena=preparado.hash_contrasena.get_secret_value(), rol="admin", activo=True)
            db.add(usuario)
            db.flush()
            evento = ServicioAuditoria(db).registrar(tipo=T.ADMIN_BOOTSTRAP, resultado=R.EXITO,
                motivo=M.ADMIN_INICIAL_CREADO, request_id=uuid4(), usuario_id=usuario.id,
                actor=ActorExterno(destino.identidad.operador_oid))
            resultado = AdminConfirmado(usuario.id, evento.id)
        return resultado

    def _destino_ensayo(self, confirmacion: str) -> None:
        c = self._config
        # Ensayos SQL únicamente en bases temporales verificables de testing.
        # No es una excepción que permita confirmar un alta en desarrollo.
        if (c.app_env != "testing" or c.postgres_port != 5433
                or c.postgres_host not in {"localhost", "127.0.0.1", "::1"}
                or not re.fullmatch(r"synapdesk_auth07_sec01a_[a-f0-9]{32}", c.postgres_db or "")
                or not isinstance(confirmacion, str) or confirmacion != self.destino):
            raise ErrorBootstrap(CodigoBootstrap.DESTINO)

    @contextmanager
    def _transaccion_revertida(self):
        with Session(self._motor) as db, operacion_bd(db, exigir_transaccion=False):
            db.begin()
            try:
                yield db
            finally:
                # También ante fallo de SQL, validación o cancelación. Nunca commit.
                db.rollback()

    def ensayar(self, preparado: AdminPreparado, *, confirmar_destino: str) -> EnsayoBootstrap:
        self._destino_ensayo(confirmar_destino)
        if type(preparado) is not AdminPreparado or preparado._emisor is not self._emisor:
            raise ErrorBootstrap(CodigoBootstrap.ENTRADA)
        with self._transaccion_revertida() as db:
            identidad = db.execute(text("SELECT current_database(), current_user")).one()
            if identidad != (self._config.postgres_db, self._config.postgres_user):
                raise ErrorBootstrap(CodigoBootstrap.DESTINO)
            db.execute(text("SET LOCAL search_path = pg_catalog, public"))
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            # Conflicta con INSERT/UPDATE/DELETE, también de procesos que no usan
            # este coordinador. No depende de un COUNT sin exclusión ni de unicidad
            # del email para impedir dos primeros admins con correos diferentes.
            db.execute(text("LOCK TABLE public.usuarios IN SHARE ROW EXCLUSIVE MODE"))
            if db.scalar(select(Usuario.id).limit(1)) is not None:
                raise ErrorBootstrap(CodigoBootstrap.INSTALACION_NO_VACIA)
            db.add(Usuario(nombre=preparado.nombre, correo=preparado.correo,
                           hash_contrasena=preparado.hash_contrasena.get_secret_value(),
                           rol="admin", activo=True))
            db.flush()
        return EnsayoBootstrap()
