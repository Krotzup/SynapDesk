"""Adaptación HTTP parcial: la emisión sigue cerrada hasta aprobar sus límites."""

from fastapi import APIRouter, Depends, Request

from app.api.dependencias_auth import ConfiguracionHttp, obtener_ip_verificada
from app.api.esquemas_auth import RespuestaCsrf, RespuestaError
from app.seguridad.origenes import ServicioOrigen
from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad

router = APIRouter(prefix="/auth", tags=["autenticación"])


def exigir_bootstrap_csrf(request: Request, configuracion: ConfiguracionHttp) -> None:
    """Origin original, o la condición de lectura del navegador del contrato.

    Sec-Fetch-Site limita el bootstrap; no acredita IP, sesión ni proxy.
    Se conservan todas las ocurrencias para rechazar valores ambiguos.
    """
    servicio = ServicioOrigen(configuracion)
    origenes = request.headers.getlist("origin")
    if origenes:
        servicio.validar(origenes)
    elif request.headers.getlist("sec-fetch-site") != ["same-origin"]:
        raise ErrorSeguridad(CodigoSeguridad.ORIGIN_INVALIDO)


@router.get(
    "/csrf",
    response_model=RespuestaCsrf,
    responses={estado: {"model": RespuestaError} for estado in (403, 500, 503)},
    dependencies=[Depends(exigir_bootstrap_csrf)],
)
def obtener_csrf(request: Request) -> RespuestaCsrf:
    """No emitir contexto/token/cookie sin procedencia y cuota verificables.

    AUTH-07A rechaza actualmente la IP HTTP no acreditada. Aun después de
    resolver esa adaptación, falta una política persistente de bootstrap:
    ServicioLimites.reservar exige cuenta e IP; no inventar una cuenta común,
    una IP ni habilitar el flujo solo por reemplazar el adaptador de IP.
    La futura emisión debe reutilizar ServicioCsrf y confirmar antes de
    construir respuesta o cookies. No se inicia una transacción aquí.
    """
    obtener_ip_verificada(request)
    raise ErrorSeguridad(CodigoSeguridad.INFRAESTRUCTURA)
