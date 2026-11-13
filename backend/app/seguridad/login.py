"""Login interno con admisión durable; no registra rutas ni construye cookies.

Los tipos internos no acreditan un transporte HTTP. Origin y SEC-01B pertenecen
a ese adaptador futuro. Una prueba CSRF se comprueba de nuevo por operación y
tras Argon2: el objeto validado no congela vigencia ni autorización.
"""

import hmac
import secrets
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import BoundedSemaphore
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.configuracion import Configuracion
from app.persistencia.modelos import Usuario
from app.seguridad.auditoria import (
    MotivoEvento as M, ResultadoEvento as R, ServicioAuditoria, TipoEvento as T,
)
from app.seguridad.contrasenas import ErrorContrasena, ServicioContrasenas
from app.seguridad.cuentas import normalizar_cuenta
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.identificadores import ServicioIdentificadores
from app.seguridad.limites import DecisionLimite, ReservaIntento, ServicioLimites
from app.seguridad.proxies import IpVerificada
from app.seguridad.sesiones import Identidad, SesionConsultada, SesionEmitida, ServicioSesiones
from app.seguridad.transacciones import (
    CodigoSeguridad as C, ErrorSeguridad, Reloj, instante, reloj_postgresql,
    transaccion_seguridad,
)


@dataclass(frozen=True)
class CredencialesLogin:
    cuenta: str = field(repr=False)
    contrasena: SecretStr = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cuenta", normalizar_cuenta(self.cuenta))
        if (not isinstance(self.contrasena, SecretStr)
                or not ServicioContrasenas._entrada_valida(self.contrasena.get_secret_value())):
            raise ValueError("Credenciales de login inválidas.")


@dataclass(frozen=True)
class PruebaAnonimaLogin:
    contexto: SecretStr = field(repr=False)
    token: SecretStr = field(repr=False)


@dataclass(frozen=True)
class PruebaSesionLogin:
    sesion: SecretStr = field(repr=False)
    token: SecretStr = field(repr=False)


@dataclass(frozen=True)
class ContextoLoginValidado:
    """Solo lo emite validar_contexto; no aceptar su construcción desde HTTP."""

    _prueba: PruebaAnonimaLogin | PruebaSesionLogin = field(repr=False)
    _ip: IpVerificada = field(repr=False)
    _anterior: SesionConsultada | None = field(repr=False)
    _emisor: object = field(repr=False)


@dataclass(frozen=True)
class LoginConfirmado:
    usuario: Identidad
    sesion: SesionEmitida = field(repr=False)


@dataclass(frozen=True)
class LoginRechazado:
    """Resultado interno uniforme; no añade códigos HTTP al contrato."""

    motivo: M
    limite: DecisionLimite | None = None


@dataclass(frozen=True)
class _Candidato:
    id: UUID
    hash: str = field(repr=False)
    activo: bool
    rol: str
    cuenta: str = field(repr=False)


class _CredencialesRechazadas(Exception):
    pass


class ServicioLogin:
    def __init__(self, motor: Engine, configuracion: Configuracion, *,
                 capacidad_argon2: int, reloj: Reloj = reloj_postgresql) -> None:
        # Capacidad explícita por instancia/proceso, sin cola ni certificado de
        # capacidad distribuida. Conservar una instancia por worker al integrar.
        if (type(capacidad_argon2) is not int or capacidad_argon2 < 1
                or motor.dialect.name != "postgresql"):
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        self._config = configuracion.model_copy(deep=True)
        try:
            self._identificadores = ServicioIdentificadores(self._config)
            with Session(motor) as db:
                ServicioLimites(db, self._config, self._identificadores, reloj)
        except ValueError:
            raise ErrorSeguridad(C.INFRAESTRUCTURA) from None
        self._motor = motor.execution_options(isolation_level="READ COMMITTED")
        self._reloj = reloj
        self._emisor = object()
        self._plazas = BoundedSemaphore(capacidad_argon2)
        self._contrasenas = ServicioContrasenas(self._config)
        # No es una cuenta, una contraseña utilizable ni un secreto compartido.
        # Argon2 real para cuentas ausentes; hash efímero generado fuera de BD.
        self._hash_ausente = self._contrasenas.generar_hash(secrets.token_urlsafe(32))

    @contextmanager
    def _transaccion(self):
        with Session(self._motor, expire_on_commit=False) as db, transaccion_seguridad(db):
            yield db

    def _limites(self, db: Session) -> ServicioLimites:
        return ServicioLimites(db, self._config, self._identificadores, self._reloj)

    def _csrf(self, db: Session, prueba: PruebaAnonimaLogin | PruebaSesionLogin
              ) -> SesionConsultada | None:
        csrf = ServicioCsrf(db, self._config, self._reloj)
        if type(prueba) is PruebaAnonimaLogin:
            if not isinstance(prueba.contexto, SecretStr) or not isinstance(prueba.token, SecretStr):
                raise ErrorSeguridad(C.TOKEN_INVALIDO)
            csrf.validar_token(prueba.token, anonimo=prueba.contexto)
            return None
        if type(prueba) is PruebaSesionLogin:
            if not isinstance(prueba.sesion, SecretStr) or not isinstance(prueba.token, SecretStr):
                raise ErrorSeguridad(C.TOKEN_INVALIDO)
            anterior = ServicioSesiones(db, self._reloj).consultar(prueba.sesion)
            csrf.validar_token(prueba.token, sesion=prueba.sesion)
            return anterior
        raise ErrorSeguridad(C.CONTEXTO_INVALIDO)

    @staticmethod
    def _motivo(error: ErrorSeguridad) -> M:
        if error.codigo in {C.CONTEXTO_INVALIDO, C.TOKEN_INVALIDO, C.TOKEN_VENCIDO}:
            return M.CSRF
        if error.codigo in {C.SESION_INEXISTENTE, C.SESION_VENCIDA, C.SESION_REVOCADA,
                            C.USUARIO_INACTIVO, C.USUARIO_INEXISTENTE, C.ROL_INVALIDO}:
            return M.SESION_INVALIDA
        return M.INFRAESTRUCTURA

    def _auditar_rechazo(self, motivo: M, ip: IpVerificada | None, request_id: UUID,
                        reserva: ReservaIntento | None = None) -> None:
        # Nueva transacción después del rollback. Si BD no está disponible,
        # falla cerrada; nunca se afirma un evento que no pudo confirmarse.
        with self._transaccion() as db:
            if reserva is not None:
                self._limites(db).consolidar(reserva)
            ServicioAuditoria(db, self._reloj).registrar(
                tipo=T.LOGIN if motivo == M.CREDENCIALES_INVALIDAS else T.VALIDACION,
                resultado=R.RECHAZO, motivo=motivo, ip=ip, request_id=request_id)

    def validar_contexto(self, prueba: PruebaAnonimaLogin | PruebaSesionLogin, *,
                         ip: IpVerificada) -> ContextoLoginValidado:
        if not isinstance(ip, IpVerificada):
            self._auditar_rechazo(M.IP, None, uuid4())
            raise ErrorSeguridad(C.IP_NO_VERIFICABLE)
        try:
            with self._transaccion() as db:
                anterior = self._csrf(db, prueba)
        except ErrorSeguridad as error:
            self._auditar_rechazo(self._motivo(error), ip, uuid4())
            raise
        return ContextoLoginValidado(prueba, ip, anterior, self._emisor)

    def _admitir(self, credenciales: CredencialesLogin, contexto: ContextoLoginValidado,
                 request_id: UUID) -> tuple[DecisionLimite, _Candidato | None]:
        with self._transaccion() as db:
            decision = self._limites(db).reservar(cuenta=credenciales.cuenta, ip=contexto._ip)
            # Mismo orden que la confirmación: cuotas -> usuarios/sesión/contexto.
            # Un CSRF rechazado revierte esta reserva; nunca se confirma sin él.
            self._csrf(db, contexto._prueba)
            candidato = None
            if not decision.permitido:
                ServicioAuditoria(db, self._reloj).registrar(
                    tipo=T.BLOQUEO, resultado=R.RECHAZO, motivo=M.LIMITE,
                    ip=contexto._ip, request_id=request_id)
            else:
                fila = db.execute(select(Usuario.id, Usuario.hash_contrasena, Usuario.activo,
                                         Usuario.rol, Usuario.correo).where(
                                             Usuario.correo == credenciales.cuenta)).first()
                if fila is not None:
                    candidato = _Candidato(*fila)
        # La reserva ya está confirmada y no hay conexiones/locks durante Argon2.
        return decision, candidato

    def _confirmar(self, candidato: _Candidato, contexto: ContextoLoginValidado,
                   reserva: ReservaIntento, request_id: UUID) -> LoginConfirmado:
        with self._transaccion() as db:
            if not self._limites(db).consolidar(reserva):
                raise ErrorSeguridad(C.RESERVA_INVALIDA)
            sesiones = ServicioSesiones(db, self._reloj)
            ids = {candidato.id}
            if contexto._anterior is not None:
                ids.add(contexto._anterior.usuario.id)
            # Reutilizar el orden AUTH-06: usuarios ordenados, sesión, contextos.
            usuarios = sesiones._usuarios(ids)
            usuario = usuarios.get(candidato.id)
            if (usuario is None or not usuario.activo or usuario.rol not in {"admin", "agent"}
                    or usuario.correo != candidato.cuenta
                    or not hmac.compare_digest(usuario.hash_contrasena.encode("utf-8"),
                                               candidato.hash.encode("utf-8"))):
                raise _CredencialesRechazadas()
            self._csrf(db, contexto._prueba)
            # La espera de locks no puede prolongar la autorización de la reserva.
            if instante(db, self._reloj) >= reserva.vence_en:
                raise ErrorSeguridad(C.RESERVA_INVALIDA)
            previa = contexto._prueba.sesion if type(contexto._prueba) is PruebaSesionLogin else None
            sesion = sesiones.crear(usuario.id, presentada=previa)
            csrf = ServicioCsrf(db, self._config, self._reloj)
            if type(contexto._prueba) is PruebaAnonimaLogin:
                csrf.invalidar_contexto(anonimo=contexto._prueba.contexto)
            csrf.obtener_autenticado(sesion.credencial)
            auditoria = ServicioAuditoria(db, self._reloj)
            if contexto._anterior is not None:
                auditoria.registrar(tipo=T.SESION_REVOCADA, resultado=R.EXITO,
                    motivo=M.REEMPLAZO, usuario_id=contexto._anterior.usuario.id,
                    sesion_id=contexto._anterior.id, ip=contexto._ip, request_id=request_id)
            for tipo, motivo in ((T.LOGIN, M.CREDENCIALES_VALIDAS), (T.SESION_CREADA, M.CREACION)):
                auditoria.registrar(tipo=tipo, resultado=R.EXITO, motivo=motivo,
                    usuario_id=usuario.id, sesion_id=sesion.id, ip=contexto._ip, request_id=request_id)
            resultado = LoginConfirmado(Identidad(usuario.id, usuario.correo, usuario.rol), sesion)
        # Ningún secreto de sesión se devuelve antes del commit de sesión/CSRF/eventos.
        return resultado

    def autenticar(self, credenciales: CredencialesLogin,
                    contexto: ContextoLoginValidado) -> LoginConfirmado | LoginRechazado:
        if (type(credenciales) is not CredencialesLogin or type(contexto) is not ContextoLoginValidado
                or contexto._emisor is not self._emisor or not isinstance(contexto._ip, IpVerificada)):
            raise ErrorSeguridad(C.CONTEXTO_INVALIDO)
        request_id = uuid4()
        if not self._plazas.acquire(blocking=False):
            self._auditar_rechazo(M.INFRAESTRUCTURA, contexto._ip, request_id)
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        reserva = None
        try:
            decision, candidato = self._admitir(credenciales, contexto, request_id)
            if not decision.permitido:
                return LoginRechazado(M.LIMITE, decision)
            reserva = decision.reserva
            if reserva is None:
                raise ErrorSeguridad(C.RESERVA_INVALIDA)
            coincide = self._contrasenas.verificar(
                candidato.hash if candidato is not None else self._hash_ausente,
                credenciales.contrasena.get_secret_value())
            if (not coincide or candidato is None or not candidato.activo
                    or candidato.rol not in {"admin", "agent"}):
                raise _CredencialesRechazadas()
            return self._confirmar(candidato, contexto, reserva, request_id)
        except _CredencialesRechazadas:
            # Mismo resultado/evento sin usuario para cuenta ausente/inactiva/clave errónea.
            self._auditar_rechazo(M.CREDENCIALES_INVALIDAS, contexto._ip, request_id, reserva)
            return LoginRechazado(M.CREDENCIALES_INVALIDAS)
        except ErrorSeguridad as error:
            self._auditar_rechazo(self._motivo(error), contexto._ip, request_id, reserva)
            raise
        except ErrorContrasena:
            self._auditar_rechazo(M.INFRAESTRUCTURA, contexto._ip, request_id, reserva)
            raise
        finally:
            self._plazas.release()
