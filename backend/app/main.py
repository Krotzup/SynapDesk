from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.salud import router as router_salud
from app.configuracion import Configuracion


def crear_aplicacion(configuracion: Configuracion | None = None) -> FastAPI:
    configuracion = configuracion if configuracion is not None else Configuracion()

    aplicacion = FastAPI(
        title="SynapDesk API",
        description="API de la plataforma de asistencia para soporte TI.",
        version="0.1.0",
    )

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
