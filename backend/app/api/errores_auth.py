"""Traducciones saneadas; nunca usan str(error), input ni contexto Pydantic."""

from enum import StrEnum

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.esquemas_auth import ApiErrorBody, RespuestaError, DetalleValidacion
from app.api.respuestas_auth import id_peticion, respuesta_auth
from app.seguridad.contrasenas import ErrorContrasena
from app.seguridad.limites import DecisionLimite
from app.seguridad.origenes import ErrorConfiguracionSeguridad
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad


class CodigoHttp(StrEnum):
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    CSRF_INVALID = "CSRF_INVALID"
    ORIGIN_INVALID = "ORIGIN_INVALID"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


CATALOGO = {
    CodigoHttp.AUTHENTICATION_REQUIRED: (401, "Se requiere una sesión válida."),
    CodigoHttp.CSRF_INVALID: (403, "No se pudo validar la solicitud."),
    CodigoHttp.ORIGIN_INVALID: (403, "El origen de la solicitud no está permitido."),
    CodigoHttp.VALIDATION_ERROR: (422, "Revisa los campos de la solicitud."),
    CodigoHttp.RATE_LIMITED: (429, "Se alcanzó el límite de solicitudes."),
    CodigoHttp.SERVICE_UNAVAILABLE: (503, "El servicio no está disponible temporalmente."),
    CodigoHttp.INTERNAL_ERROR: (500, "No se pudo completar la solicitud."),
}


class RechazoAntesDeEfectos(ErrorSeguridad):
    """El adaptador acredita que el control terminó antes de la mutación.

    No envolver errores de operaciones que ya ejecutaron efectos o cuyo estado
    se desconoce. Solo este rechazo CSRF autoriza la recuperación contractual.
    """

    def __init__(self, codigo: C) -> None:
        if codigo not in {C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO, C.ORIGIN_INVALIDO}:
            raise ValueError("El código no corresponde a un control previo.")
        super().__init__(codigo)


def respuesta_error(request: Request, codigo: CodigoHttp, *,
                    detalles: list[DetalleValidacion] | None = None) -> JSONResponse:
    estado, mensaje = CATALOGO[codigo]
    return respuesta_auth(RespuestaError(error=ApiErrorBody(
        code=codigo.value, message=mensaje, details=detalles,
        requestId=id_peticion(request),
    )), estado=estado)


def traducir_error(error: Exception) -> CodigoHttp:
    if isinstance(error, ErrorSeguridad):
        if error.codigo in {C.SESION_INEXISTENTE, C.SESION_VENCIDA, C.SESION_REVOCADA,
                            C.USUARIO_INEXISTENTE, C.USUARIO_INACTIVO}:
            # Solo consulta de identidad; el login requerirá su propia política.
            return CodigoHttp.AUTHENTICATION_REQUIRED
        if (isinstance(error, RechazoAntesDeEfectos)
                and error.codigo in {C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO}):
            # Usar únicamente cuando el control CSRF rechazó antes de efectos.
            return CodigoHttp.CSRF_INVALID
        if error.codigo == C.ORIGIN_INVALIDO:
            return CodigoHttp.ORIGIN_INVALID
        if error.codigo in {C.INFRAESTRUCTURA, C.TRANSACCION, C.CONFLICTO_VERSION,
                            C.IP_NO_VERIFICABLE}:
            return CodigoHttp.SERVICE_UNAVAILABLE
    if isinstance(error, SQLAlchemyError):
        return CodigoHttp.SERVICE_UNAVAILABLE
    # Configuración, Argon2, cuota de tokens sin espera y fallos no clasificados
    # no son credenciales incorrectas ni una cuota HTTP con espera inventada.
    return CodigoHttp.INTERNAL_ERROR


def respuesta_limite(request: Request, decision: DecisionLimite) -> JSONResponse:
    if (decision.permitido or decision.reintentar_en is None
            or decision.observado_en.tzinfo is None or decision.reintentar_en.tzinfo is None
            or decision.retry_after is None or decision.retry_after <= 0):
        raise ErrorConfiguracionSeguridad("No existe una espera verificable del límite.")
    respuesta = respuesta_error(request, CodigoHttp.RATE_LIMITED)
    respuesta.headers["Retry-After"] = str(decision.retry_after)
    return respuesta


def detalles_validacion(request: Request, error: RequestValidationError) -> list[DetalleValidacion]:
    # Solo nombres declarados por el esquema/endpoint, nunca keys del JSON,
    # valores, loc de extra_forbidden, índices ni mensajes de validadores.
    ruta = request.scope.get("route")
    cuerpo = getattr(ruta, "body_field", None)
    modelo = getattr(getattr(cuerpo, "field_info", None), "annotation", None)
    campos = getattr(modelo, "model_fields", {})
    permitidos = {f.alias or nombre for nombre, f in campos.items()}
    dependencias = getattr(ruta, "dependant", None)
    for grupo in ("query_params", "path_params", "header_params", "cookie_params"):
        permitidos.update(f.alias for f in getattr(dependencias, grupo, []))
    detalles = []
    vistos = set()
    for item in error.errors():
        loc = item.get("loc", ())
        nombre = loc[1] if len(loc) > 1 and loc[1] in permitidos else None
        if nombre is not None and nombre not in vistos:
            vistos.add(nombre)
            detalles.append(DetalleValidacion(field=nombre, message="El campo es obligatorio."
                if item.get("type") == "missing" else "El campo no tiene un valor válido."))
    return detalles


async def manejar_validacion(request: Request, error: RequestValidationError) -> JSONResponse:
    return respuesta_error(request, CodigoHttp.VALIDATION_ERROR,
                           detalles=detalles_validacion(request, error))


async def manejar_error(request: Request, error: Exception) -> JSONResponse:
    return respuesta_error(request, traducir_error(error))


def registrar_errores(aplicacion: FastAPI) -> None:
    aplicacion.add_exception_handler(RequestValidationError, manejar_validacion)
    for clase in (ErrorSeguridad, ErrorContrasena, ErrorConfiguracionSeguridad, SQLAlchemyError, Exception):
        aplicacion.add_exception_handler(clase, manejar_error)
