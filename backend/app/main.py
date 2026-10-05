from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.api.salud import router as router_salud
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
        try:
            yield
        finally:
            if motor is not None:
                await run_in_threadpool(motor.dispose)
            aplicacion.state.motor_bd = None

    aplicacion = FastAPI(
        title="SynapDesk API",
        description="API de la plataforma de asistencia para soporte TI.",
        version="0.1.0",
        lifespan=ciclo_de_vida,
    )
    aplicacion.state.motor_bd = None

    aplicacion.add_middleware(
        CORSMiddleware,
        allow_origins=configuracion.backend_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    aplicacion.include_router(router_salud, prefix="/api/v1")
    return aplicacion


app = crear_aplicacion()
