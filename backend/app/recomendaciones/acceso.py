"""Autorización de recomendaciones sobre las sesiones y el canal interno existentes."""

from sqlalchemy.orm import Session

from app.api.dependencias_auth import exigir_origin, obtener_intermediario, obtener_token_csrf
from app.recuperacion.acceso import session_credential
from app.recuperacion.servicio import ErrorRecuperacion
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.origenes import ErrorConfiguracionSeguridad, ServicioOrigen
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad, transaccion_seguridad


def identidad_recomendaciones(request, *, escritura: bool, origen: str | None = None):
    config = request.app.state.configuracion
    origen = origen or config.rag_public_origin
    if not origen or not config.search_cookie_name:
        raise ErrorRecuperacion("RECOMMENDATIONS_UNAVAILABLE", "Falta configurar el acceso a recomendaciones.")
    try:
        ServicioOrigen(config).validar([origen])
        if escritura:
            exigir_origin(request, config)
        elif request.headers.getlist("origin"):
            # En lecturas SSR el proxy no transmite Origin; si existe debe ser válido.
            exigir_origin(request, config)
        obtener_intermediario(request)
        credential = session_credential(request, config.search_cookie_name, origin=origen)
        token = obtener_token_csrf(request) if escritura else None
        motor = request.app.state.motor_bd
        if motor is None:
            raise ErrorRecuperacion("DEPENDENCY_UNAVAILABLE", "No se pudo verificar la sesión temporalmente.")
        with Session(motor) as db, transaccion_seguridad(db):
            identity = ServicioSesiones(db).consultar(credential).usuario
            if token is not None:
                ServicioCsrf(db, config).validar_token(token.get_secret_value(), sesion=credential)
        if identity.role not in {"agent", "admin"}:
            raise ErrorRecuperacion("FORBIDDEN", "No tienes permiso para consultar recomendaciones.", 403)
        return identity
    except ErrorConfiguracionSeguridad:
        raise ErrorRecuperacion("RECOMMENDATIONS_UNAVAILABLE", "Falta configurar el acceso a recomendaciones.") from None
    except ErrorSeguridad as error:
        if error.codigo == C.ORIGIN_INVALIDO:
            raise ErrorRecuperacion("ORIGIN_INVALID", "El origen de la solicitud no está permitido.", 403) from None
        if error.codigo in {C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO}:
            raise ErrorRecuperacion("CSRF_INVALID", "No se pudo validar el contexto de seguridad.", 403) from None
        if error.codigo in {C.INFRAESTRUCTURA, C.TRANSACCION}:
            raise ErrorRecuperacion("DEPENDENCY_UNAVAILABLE", "No se pudo verificar la sesión temporalmente.") from None
        raise ErrorRecuperacion("AUTHENTICATION_REQUIRED", "Debes iniciar sesión para continuar.", 401) from None


def identidad_aplicacion(request, *, escritura: bool):
    """Misma frontera de sesión/CSRF para documentos y predicciones, independiente de Gemini."""
    return identidad_recomendaciones(request, escritura=escritura,
        origen=request.app.state.configuracion.application_public_origin)
