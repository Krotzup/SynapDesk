"""Rutas optativas sobre los adaptadores transaccionales existentes."""
import json
from uuid import UUID
from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from app.api.adaptadores_tickets import AdaptadorTickets
from app.api.cookies_auth import preparar_perfil
from app.recuperacion.acceso import CONTEXTOS_POR_SESION
from app.recuperacion.servicio import ErrorRecuperacion
from app.tickets.esquemas import TicketCreate, TicketPagination, TicketStatusUpdate

router = APIRouter()


def adaptador(request):
    config = request.app.state.configuracion
    origin, name = config.application_public_origin, config.search_cookie_name
    if not config.tickets_http_enabled or not origin or name not in CONTEXTOS_POR_SESION or request.app.state.motor_bd is None:
        raise ErrorRecuperacion("SERVICE_UNAVAILABLE", "El acceso a tickets no está preparado.")
    perfil = preparar_perfil(config, origen_publico=origin, nombre_sesion=name,
                            nombre_contexto=CONTEXTOS_POR_SESION[name])
    return AdaptadorTickets(request.app.state.motor_bd, config, perfil)


def pagina_tickets(params):
    if set(params) - set(TicketPagination.model_fields) or any(len(params.getlist(k)) != 1 for k in params):
        raise ErrorRecuperacion("VALIDATION_ERROR", "Los filtros no son válidos.", 422)
    data = dict(params)
    try:
        for name in ("page", "pageSize"):
            if name in data:
                if not data[name].isascii() or not data[name].isdecimal():
                    raise ValueError
                data[name] = int(data[name])
        return TicketPagination.model_validate(data)
    except (ValueError, ValidationError):
        raise ErrorRecuperacion("VALIDATION_ERROR", "Revisa los filtros y la paginación.", 422) from None


async def cuerpo(request, modelo):
    parts, size = [], 0
    async for part in request.stream():
        size += len(part)
        if size > 32768:
            raise ErrorRecuperacion("VALIDATION_ERROR", "La solicitud es demasiado grande.", 413)
        parts.append(part)
    def unicos(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result
    try:
        return modelo.model_validate(json.loads(b"".join(parts), object_pairs_hook=unicos))
    except (ValueError, UnicodeError, ValidationError):
        raise ErrorRecuperacion("VALIDATION_ERROR", "Revisa los datos del ticket.", 422) from None


@router.get("/tickets")
def listar(request: Request):
    adapter = adaptador(request)
    return adapter.listar(request, pagina_tickets(request.query_params))


@router.get("/metrics/summary")
@router.get("/tickets/summary")
def resumen(request: Request):
    return adaptador(request).resumen(request)


@router.get("/tickets/{ticket_id}")
def detalle(ticket_id: UUID, request: Request):
    return adaptador(request).detalle(request, ticket_id)


async def escribir(request, modelo, identifier=None):
    adapter = adaptador(request)
    # Acreditar canal y origen antes de leer cuerpo; sesión/CSRF se comprueban
    # otra vez dentro de la transacción que aplica los efectos.
    from fastapi import Response
    def frontera():
        adapter._frontera(request, request.method)
        return Response(status_code=204)
    resultado = await run_in_threadpool(adapter._responder, request, frontera)
    if resultado.status_code != 204:
        return resultado
    data = await cuerpo(request, modelo)
    if identifier is None:
        return await run_in_threadpool(adapter.crear, request, data)
    return await run_in_threadpool(adapter.actualizar_estado, request, identifier, data)


@router.post("/tickets", status_code=201)
async def crear(request: Request):
    return await escribir(request, TicketCreate)


@router.patch("/tickets/{ticket_id}")
async def estado(ticket_id: UUID, request: Request):
    return await escribir(request, TicketStatusUpdate, ticket_id)
