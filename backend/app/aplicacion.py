from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.api.salud import router as router_salud
from app.api.busqueda import error_response, router as router_busqueda
from app.recuperacion.servicio import ErrorRecuperacion
from app.configuracion import Configuracion
from app.persistencia.conexion import crear_motor_bd


def crear_aplicacion(configuracion: Configuracion | None = None) -> FastAPI:
    configuracion = configuracion if configuracion is not None else Configuracion()

    @asynccontextmanager
    async def ciclo_de_vida(aplicacion: FastAPI) -> AsyncIterator[None]:
        motor = (
            crear_motor_bd(configuracion)
            if configuracion.tiene_configuracion_bd
            else None
        )
        aplicacion.state.motor_bd = motor
        aplicacion.state.recuperacion = None
        if configuracion.search_enabled:
            from app.recuperacion.servicio import ServicioRecuperacion
            try:
                aplicacion.state.recuperacion = await run_in_threadpool(ServicioRecuperacion, configuracion)
            except (ValueError, OSError, ImportError, RuntimeError):
                # No emitir URLs, rutas privadas, entradas de configuración ni
                # mensajes de proveedores. La ruta permanece cerrada con 503.
                import logging
                logging.getLogger(__name__).error("No se pudo preparar la recuperación semántica configurada.")
        try:
            yield
        finally:
            if motor is not None:
                await run_in_threadpool(motor.dispose)
            aplicacion.state.motor_bd = None
            aplicacion.state.recuperacion = None

    aplicacion = FastAPI(
        title="SynapDesk API",
        description="API de la plataforma de asistencia para soporte TI.",
        version="0.1.0",
        lifespan=ciclo_de_vida,
    )
    aplicacion.state.motor_bd = None
    aplicacion.state.configuracion = configuracion
    aplicacion.state.recuperacion = None

    @aplicacion.exception_handler(ErrorRecuperacion)
    async def error_recuperacion(request, error):
        return error_response(error.code, error.message, error.status)

    @aplicacion.exception_handler(RequestValidationError)
    async def entrada_invalida(request, error):
        if request.url.path != "/api/v1/search":
            return await request_validation_exception_handler(request, error)
        fields = {str(item["loc"][-1]) for item in error.errors() if item["loc"][-1] in {"query", "limit"}}
        details = [{"field": field, "message": "Usa una consulta de 1–1000 caracteres y un límite entero de 1–20."}
                   for field in sorted(fields or {"request"})]
        return error_response("VALIDATION_ERROR", "Revisa la consulta y la cantidad de resultados.", 422, details)

    aplicacion.add_middleware(
        CORSMiddleware,
        allow_origins=configuracion.backend_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    aplicacion.include_router(router_salud, prefix="/api/v1")
    aplicacion.include_router(router_busqueda, prefix="/api/v1")
    return aplicacion
