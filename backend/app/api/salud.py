import logging
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.persistencia.conexion import obtener_motor_bd

router = APIRouter(tags=["Salud"])
registrador = logging.getLogger(__name__)


class RespuestaSalud(BaseModel):
    status: Literal["ok"]
    service: Literal["synapdesk-backend"]


class RespuestaDisponibilidad(BaseModel):
    status: Literal["ready"]
    service: Literal["synapdesk-backend"]
    database: Literal["ok"]


class DetalleErrorDisponibilidad(BaseModel):
    code: Literal["DATABASE_UNAVAILABLE"]
    message: str
    details: None = None
    requestId: UUID


class ErrorDisponibilidad(BaseModel):
    error: DetalleErrorDisponibilidad


@router.get("/health", response_model=RespuestaSalud)
async def consultar_salud() -> RespuestaSalud:
    """Comprueba que la API puede responder solicitudes."""
    return RespuestaSalud(status="ok", service="synapdesk-backend")


@router.get(
    "/ready",
    response_model=RespuestaDisponibilidad,
    responses={503: {"model": ErrorDisponibilidad}},
)
def consultar_disponibilidad(
    motor: Annotated[Engine | None, Depends(obtener_motor_bd)],
) -> RespuestaDisponibilidad | JSONResponse:
    """Comprueba acceso a PostgreSQL mediante una consulta de solo lectura."""
    disponible = False
    if motor is not None:
        try:
            with motor.connect() as conexion:
                disponible = conexion.execute(text("SELECT 1")).scalar_one() == 1
        except SQLAlchemyError:
            disponible = False

    if not disponible:
        request_id = uuid4()
        # No registrar la excepción del controlador: puede contener datos internos.
        registrador.warning("PostgreSQL no disponible. requestId=%s", request_id)
        error = ErrorDisponibilidad(
            error=DetalleErrorDisponibilidad(
                code="DATABASE_UNAVAILABLE",
                message="La base de datos no está disponible.",
                requestId=request_id,
            )
        )
        return JSONResponse(status_code=503, content=error.model_dump(mode="json"))

    return RespuestaDisponibilidad(
        status="ready", service="synapdesk-backend", database="ok"
    )
