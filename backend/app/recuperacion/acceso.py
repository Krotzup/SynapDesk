"""Sesión y CSRF existentes; no implementa login ni emite nuevas cookies."""

from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.api.adaptadores_auth import extraer_cookies
from app.api.cookies_auth import CookieAmbigua, PerfilCookies
from app.api.dependencias_auth import exigir_origin, obtener_intermediario, obtener_token_csrf
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.origenes import ErrorConfiguracionSeguridad
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad, transaccion_seguridad
from .servicio import ErrorRecuperacion

CONTEXTOS_POR_SESION = {
    "synapdesk_session_dev": "synapdesk_csrf_context_dev",
    "__Host-synapdesk_session": "__Host-synapdesk_csrf_context",
}


def session_credential(request, name: str) -> str:
    profile = PerfilCookies(
        request.app.state.configuracion.app_env,
        request.headers.getlist("origin")[0],
        name,
        CONTEXTOS_POR_SESION.get(name, f"{name}_context"),
    )
    try:
        cookies = extraer_cookies(request, profile)
        if cookies.sesion is None or any(
            cookie is not None and len(cookie.get_secret_value()) > 4096
            for cookie in (cookies.sesion, cookies.contexto)
        ):
            raise CookieAmbigua("La credencial de sesión no es válida.")
    except CookieAmbigua:
        raise ErrorRecuperacion(
            "AUTHENTICATION_REQUIRED", "Debes iniciar sesión para buscar en los documentos.", 401
        ) from None
    return cookies.sesion.get_secret_value()


@contextmanager
def autorizar_busqueda(request):
    config = request.app.state.configuracion
    cookie_name = config.search_cookie_name
    if not cookie_name:
        raise ErrorRecuperacion("SEARCH_UNAVAILABLE", "La búsqueda protegida todavía no está configurada.")
    try:
        exigir_origin(request, config)
        obtener_intermediario(request)
        credential = session_credential(request, cookie_name)
        token = obtener_token_csrf(request)
        motor = request.app.state.motor_bd
        if motor is None:
            raise ErrorRecuperacion("DEPENDENCY_UNAVAILABLE", "No se pudo verificar la sesión temporalmente.")
        # La transacción incluye el trabajo autorizado y termina antes de emitir
        # una respuesta. No se renueva actividad: esa política sigue pendiente.
        with Session(motor) as db, transaccion_seguridad(db):
            identity = ServicioSesiones(db).consultar(credential).usuario
            ServicioCsrf(db, config).validar_token(token.get_secret_value(), sesion=credential)
            yield identity
    except ErrorConfiguracionSeguridad:
        raise ErrorRecuperacion("SEARCH_UNAVAILABLE", "La búsqueda protegida todavía no está configurada.") from None
    except ErrorSeguridad as error:
        if error.codigo == C.ORIGIN_INVALIDO:
            raise ErrorRecuperacion("ORIGIN_INVALID", "El origen de la solicitud no está permitido.", 403) from None
        if error.codigo in {C.INFRAESTRUCTURA, C.TRANSACCION}:
            raise ErrorRecuperacion("DEPENDENCY_UNAVAILABLE", "No se pudo verificar la sesión temporalmente.") from None
        if error.codigo in {C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO}:
            raise ErrorRecuperacion("CSRF_INVALID", "No se pudo validar el contexto de seguridad. Inténtalo nuevamente.", 403) from None
        raise ErrorRecuperacion("AUTHENTICATION_REQUIRED", "Debes iniciar sesión para buscar en los documentos.", 401) from None
