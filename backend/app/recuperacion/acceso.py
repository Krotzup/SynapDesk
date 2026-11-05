"""Sesión y CSRF existentes; no implementa login ni emite nuevas cookies."""

from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.seguridad.csrf import ServicioCsrf
from app.seguridad.origenes import ServicioOrigen
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad, transaccion_seguridad
from .servicio import ErrorRecuperacion


def header_values(request, name: bytes) -> list[str]:
    return [value.decode("latin-1") for key, value in request.scope["headers"] if key.lower() == name]


def session_credential(request, name: str) -> str:
    values = []
    for header in header_values(request, b"cookie"):
        for part in header.split(";"):
            key, separator, value = part.strip().partition("=")
            if separator and key == name:
                values.append(value)
    if len(values) != 1 or not values[0]:
        raise ErrorRecuperacion("AUTHENTICATION_REQUIRED", "Debes iniciar sesión para buscar en los documentos.", 401)
    return values[0]


@contextmanager
def autorizar_busqueda(request):
    config = request.app.state.configuracion
    if not config.search_session_cookie_name:
        raise ErrorRecuperacion("SEARCH_UNAVAILABLE", "La búsqueda protegida todavía no está configurada.")
    credential = session_credential(request, config.search_session_cookie_name)
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
