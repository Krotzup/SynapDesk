"""Sesión y CSRF existentes; no implementa login ni emite nuevas cookies."""

import re
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.seguridad.csrf import ServicioCsrf
from app.seguridad.origenes import ServicioOrigen
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad, transaccion_seguridad
from .servicio import ErrorRecuperacion

CONTEXTOS_POR_SESION = {
    "synapdesk_session_dev": "synapdesk_csrf_context_dev",
    "__Host-synapdesk_session": "__Host-synapdesk_csrf_context",
}
NOMBRES_AUTH = frozenset(CONTEXTOS_POR_SESION) | frozenset(CONTEXTOS_POR_SESION.values())


def header_values(request, name: bytes) -> list[str]:
    return [value.decode("latin-1") for key, value in request.scope["headers"] if key.lower() == name]


def session_credential(request, name: str) -> str:
    context_name = CONTEXTOS_POR_SESION.get(name)
    seen: dict[str, str] = {}
    for header in header_values(request, b"cookie"):
        for part in header.split(";"):
            # Solo SP/HTAB antes del par separan cookies. No recortar el valor.
            raw_key, separator, value = part.lstrip(" \t").partition("=")
            key = raw_key.strip()
            if key != name and key not in NOMBRES_AUTH:
                continue
            if (key not in (name, context_name) or key != raw_key or not separator
                    or key in seen or not re.fullmatch(r"[A-Za-z0-9_-]{1,4096}", value)):
                raise ErrorRecuperacion(
                    "AUTHENTICATION_REQUIRED", "Debes iniciar sesión para buscar en los documentos.", 401
                )
            seen[key] = value
    if name not in seen:
        raise ErrorRecuperacion(
            "AUTHENTICATION_REQUIRED", "Debes iniciar sesión para buscar en los documentos.", 401
        )
    return seen[name]


@contextmanager
def autorizar_busqueda(request):
    config = request.app.state.configuracion
    cookie_name = config.search_cookie_name
    if not cookie_name:
        raise ErrorRecuperacion("SEARCH_UNAVAILABLE", "La búsqueda protegida todavía no está configurada.")
    credential = session_credential(request, cookie_name)
    try:
        try:
            origin = ServicioOrigen(config)
        except ValueError:
            raise ErrorRecuperacion("SEARCH_UNAVAILABLE", "La búsqueda protegida todavía no está configurada.") from None
        origin.validar(header_values(request, b"origin"))
        tokens = header_values(request, b"x-csrf-token")
        if len(tokens) != 1 or not tokens[0]:
            raise ErrorRecuperacion("CSRF_INVALID", "No se pudo validar el contexto de seguridad. Inténtalo nuevamente.", 403)
        motor = request.app.state.motor_bd
        if motor is None:
            raise ErrorRecuperacion("DEPENDENCY_UNAVAILABLE", "No se pudo verificar la sesión temporalmente.")
        # La transacción incluye el trabajo autorizado y termina antes de emitir
        # una respuesta. No se renueva actividad: esa política sigue pendiente.
        with Session(motor) as db, transaccion_seguridad(db):
            identity = ServicioSesiones(db).consultar(credential).usuario
            ServicioCsrf(db, config).validar_token(tokens[0], sesion=credential)
            yield identity
    except ErrorSeguridad as error:
        if error.codigo == C.ORIGIN_INVALIDO:
            raise ErrorRecuperacion("ORIGIN_INVALID", "El origen de la solicitud no está permitido.", 403) from None
        if error.codigo in {C.INFRAESTRUCTURA, C.TRANSACCION}:
            raise ErrorRecuperacion("DEPENDENCY_UNAVAILABLE", "No se pudo verificar la sesión temporalmente.") from None
        if error.codigo in {C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO}:
            raise ErrorRecuperacion("CSRF_INVALID", "No se pudo validar el contexto de seguridad. Inténtalo nuevamente.", 403) from None
        raise ErrorRecuperacion("AUTHENTICATION_REQUIRED", "Debes iniciar sesión para buscar en los documentos.", 401) from None
