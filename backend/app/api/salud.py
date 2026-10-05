from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Salud"])


class RespuestaSalud(BaseModel):
    status: Literal["ok"]
    service: Literal["synapdesk-backend"]


@router.get("/health", response_model=RespuestaSalud)
async def consultar_salud() -> RespuestaSalud:
    """Comprueba que la API puede responder solicitudes."""
    return RespuestaSalud(
        status="ok",
        service="synapdesk-backend",
    )