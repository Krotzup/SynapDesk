"""Candidatos AUTH-07D.1 sin router, registro, flags ni adaptador IP productivo.

La fábrica de FastAPI no importa ni instancia estos adaptadores. La procedencia
HTTP sigue cerrada en obtener_ip_verificada. Los tests sustituyen esa dependencia
solo con evidencia controlada; no hay parámetro que acepte una IP del cliente.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar
from uuid import UUID

from fastapi import Request, Response
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.api.cookies_auth import (
    CookieAmbigua, PerfilCookies, eliminar_cookie, emitir_cookie, leer_cookie, preparar_perfil,
)
from app.api.csrf_auth import exigir_bootstrap_csrf
from app.api.dependencias_auth import exigir_origin, obtener_intermediario, obtener_ip_verificada, obtener_token_csrf
from app.api.errores_auth import (
    CodigoHttp, RechazoAntesDeEfectos, respuesta_error, respuesta_limite, traducir_error,
)
from app.api.esquemas_auth import AuthUser, RespuestaCsrf, RespuestaUsuario, SolicitudLogin, SolicitudLogout
from app.api.respuestas_auth import id_peticion, respuesta_auth, sin_cache
from app.configuracion import Configuracion
from app.seguridad.auditoria import MotivoEvento
from app.seguridad.bootstrap_csrf import CuotaBootstrapAgotada, ServicioBootstrapCsrf
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.intermediario import IdentidadIntermediario
from app.seguridad.limites import DecisionLimite
from app.seguridad.login import (
    CredencialesLogin, LoginConfirmado, LoginRechazado, PruebaAnonimaLogin, PruebaSesionLogin, ServicioLogin,
)
from app.seguridad.operaciones_sesion import ReferenciaSesion, ServicioConsultaSesion, ServicioLogout
from app.seguridad.transacciones import (
    CodigoSeguridad as C, ErrorSeguridad, Reloj, instante, reloj_postgresql, transaccion_seguridad,
)


# Son nombres propuestos existentes, no defaults ni perfiles aprobados.
_NOMBRES_PROPUESTOS = frozenset({
    "synapdesk_session_dev", "synapdesk_csrf_context_dev",
    "__Host-synapdesk_session", "__Host-synapdesk_csrf_context",
})
_T = TypeVar("_T")


@dataclass(frozen=True)
class CookiesAutenticacion:
    sesion: SecretStr | None = field(repr=False)
    contexto: SecretStr | None = field(repr=False)

    def referencia(self) -> ReferenciaSesion | None:
        return ReferenciaSesion(self.sesion) if self.sesion is not None else None


@dataclass(frozen=True)
class ContextoHttpAuth:
    """Correlación y posesión presentadas; no acredita identidad de usuario."""

    request_id: UUID
    intermediario: IdentidadIntermediario
    cookies: CookiesAutenticacion = field(repr=False)


def extraer_cookies(request: Request, perfil: PerfilCookies) -> CookiesAutenticacion:
    permitidas = {perfil.nombre_sesion, perfil.nombre_contexto}
    for cabecera in request.headers.getlist("cookie"):
        for parte in cabecera.split(";"):
            nombre = parte.strip().partition("=")[0].strip()
            if nombre in _NOMBRES_PROPUESTOS - permitidas:
                raise CookieAmbigua("El perfil de cookies no es inequívoco.")
    # AUTH-07A conserva originales, duplicados y representaciones malformadas.
    return CookiesAutenticacion(leer_cookie(request, perfil, "sesion"),
                                leer_cookie(request, perfil, "contexto"))


def prueba_login(cookies: CookiesAutenticacion, token: SecretStr) -> PruebaAnonimaLogin | PruebaSesionLogin:
    # Una sesión presentada siempre selecciona su rama, aunque esté vencida.
    # Nunca recuperar silenciosamente mediante la cookie anónima coexistente.
    if cookies.sesion is not None:
        cookies.referencia()  # Representación canónica antes de persistencia.
        return PruebaSesionLogin(cookies.sesion, token)
    if cookies.contexto is not None:
        return PruebaAnonimaLogin(cookies.contexto, token)
    raise RechazoAntesDeEfectos(C.CONTEXTO_INVALIDO)


def _control_csrf(operacion: Callable[[], _T]) -> _T:
    """Solo coordinadores conocidos que revierten efectos de negocio al fallar."""
    try:
        return operacion()
    except ErrorSeguridad as error:
        if error.codigo in {C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO}:
            raise RechazoAntesDeEfectos(error.codigo) from None
        raise


class AdaptadorAuth:
    """Instancia por worker candidato; una Session propia por operación interna.

    Perfil y capacidad explícitos. No acepta motor/identidad/IP desde HTTP.
    La configuración completa de login debe validarse al preparar el worker.
    """

    def __init__(self, motor: Engine, configuracion: Configuracion, perfil: PerfilCookies, *,
                 capacidad_argon2: int, reloj: Reloj = reloj_postgresql) -> None:
        self._config = configuracion.model_copy(deep=True)
        validado = preparar_perfil(self._config, origen_publico=perfil.origen_publico,
            nombre_sesion=perfil.nombre_sesion, nombre_contexto=perfil.nombre_contexto)
        if perfil != validado:
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        self._perfil = validado
        self._motor = motor
        self._reloj = reloj
        self._login = ServicioLogin(motor, self._config, capacidad_argon2=capacidad_argon2, reloj=reloj)
        self._consulta = ServicioConsultaSesion(motor, reloj=reloj)
        self._logout = ServicioLogout(motor, self._config, reloj=reloj)

    def _frontera(self, request: Request, *, operacion: str) -> ContextoHttpAuth:
        request_id = id_peticion(request)
        if operacion == "csrf":
            exigir_bootstrap_csrf(request, self._config)
        elif operacion in {"login", "logout"}:
            exigir_origin(request, self._config)
        elif request.headers.getlist("origin"):
            exigir_origin(request, self._config)
        intermediario = obtener_intermediario(request)
        return ContextoHttpAuth(request_id, intermediario, extraer_cookies(request, self._perfil))

    def _responder(self, request: Request, operacion: Callable[[], Response]) -> Response:
        id_peticion(request)
        try:
            return sin_cache(operacion())
        except CuotaBootstrapAgotada as error:
            # Misma espera observada por el coordinador, sin cuotas inventadas.
            return respuesta_limite(request, DecisionLimite(False, error.observado_en, error.reintentar_en))
        except Exception as error:
            # Nunca interpolar error, entradas, SQL ni secretos en salida/logs.
            return respuesta_error(request, traducir_error(error))

    def _ahora_cookie(self):
        # Lectura corta posterior al commit; nunca mantiene locks de Argon2.
        # Si falla, no hay respuesta/cookie de éxito: el commit puede ya existir.
        with Session(self._motor) as db, transaccion_seguridad(db):
            return instante(db, self._reloj)

    def login(self, request: Request, solicitud: SolicitudLogin) -> Response:
        def ejecutar():
            contexto = self._frontera(request, operacion="login")
            if type(solicitud) is not SolicitudLogin:
                raise ErrorSeguridad(C.CONTEXTO_INVALIDO)
            ip = obtener_ip_verificada(request)  # Siempre cerrada en producción.
            prueba = prueba_login(contexto.cookies, obtener_token_csrf(request))
            validado = _control_csrf(lambda: self._login.validar_contexto(
                prueba, ip=ip, request_id=contexto.request_id))
            resultado = _control_csrf(lambda: self._login.autenticar(
                CredencialesLogin(solicitud.email, solicitud.password), validado,
                request_id=contexto.request_id))
            if isinstance(resultado, LoginRechazado):
                if resultado.motivo == MotivoEvento.LIMITE and resultado.limite is not None:
                    return respuesta_limite(request, resultado.limite)
                if resultado.motivo == MotivoEvento.CREDENCIALES_INVALIDAS:
                    return respuesta_error(request, CodigoHttp.INVALID_CREDENTIALS)
                raise ErrorSeguridad(C.INFRAESTRUCTURA)
            if type(resultado) is not LoginConfirmado:
                raise ErrorSeguridad(C.INFRAESTRUCTURA)
            respuesta = respuesta_auth(RespuestaUsuario(user=AuthUser(
                id=resultado.usuario.id, email=resultado.usuario.email, role=resultado.usuario.role)))
            emitir_cookie(respuesta, self._perfil, "sesion", resultado.sesion.credencial,
                ahora=self._ahora_cookie(), vence_en=resultado.sesion.expira_en)
            if contexto.cookies.contexto is not None:
                eliminar_cookie(respuesta, self._perfil, "contexto")
            return respuesta
        return self._responder(request, ejecutar)

    def me(self, request: Request) -> Response:
        def ejecutar():
            contexto = self._frontera(request, operacion="me")
            usuario = self._consulta.consultar(contexto.cookies.referencia())
            return respuesta_auth(RespuestaUsuario(user=usuario))
        return self._responder(request, ejecutar)

    def logout(self, request: Request, solicitud: SolicitudLogout) -> Response:
        def ejecutar():
            contexto = self._frontera(request, operacion="logout")
            if type(solicitud) is not SolicitudLogout:
                raise ErrorSeguridad(C.CONTEXTO_INVALIDO)
            referencia = contexto.cookies.referencia()
            try:
                token = obtener_token_csrf(request)
            except RechazoAntesDeEfectos:
                # None representa token rechazado, no permiso. ServicioLogout
                # verifica primero sesión; solo la rama sin sesión válida omite CSRF.
                token = None
            _control_csrf(lambda: self._logout.cerrar(
                referencia, token=token, request_id=contexto.request_id))
            respuesta = Response(status_code=204)
            if referencia is not None:
                eliminar_cookie(respuesta, self._perfil, "sesion")
            # No borrar el contexto anónimo ni simular recuperación no aprobada.
            return respuesta
        return self._responder(request, ejecutar)

    def csrf(self, request: Request) -> Response:
        def ejecutar():
            contexto = self._frontera(request, operacion="csrf")
            ip = obtener_ip_verificada(request)  # No hay fuente HTTP acreditada.
            referencia = contexto.cookies.referencia()
            nuevo = None
            if referencia is None:
                resultado = ServicioBootstrapCsrf(self._motor, self._config, self._reloj).emitir(
                    ip=ip, anonimo=contexto.cookies.contexto)
                token, nuevo = resultado.token, resultado.contexto_nuevo
            else:
                # Reutiliza la primitiva existente y su máximo de tokens; no
                # renueva actividad ni crea un contexto anónimo de reemplazo.
                with Session(self._motor) as db, transaccion_seguridad(db):
                    token = ServicioCsrf(db, self._config, self._reloj).emitir_token(
                        sesion=referencia.credencial)
            respuesta = respuesta_auth(RespuestaCsrf(csrfToken=token.token, expiresAt=token.expira_en))
            if nuevo is not None:
                emitir_cookie(respuesta, self._perfil, "contexto", nuevo.secreto,
                    ahora=self._ahora_cookie(), vence_en=nuevo.expira_en)
            return respuesta
        return self._responder(request, ejecutar)
