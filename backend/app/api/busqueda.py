"""POST /search protegido; no modifica documentos ni implementa autenticación."""

from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.responses import JSONResponse

from app.recuperacion.acceso import autorizar_busqueda
from app.recuperacion.servicio import ErrorRecuperacion

router = APIRouter()


class SolicitudBusqueda(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("query", mode="before")
    @classmethod
    def limpiar_consulta(cls, value):
        return value.strip() if isinstance(value, str) else value


class FragmentoBusqueda(BaseModel):
    documentId: UUID
    documentChunkId: UUID
    title: str
    excerpt: str
    score: float = Field(allow_inf_nan=False)
    sourceUrl: str | None = None
    language: str | None = None


class RespuestaBusqueda(BaseModel):
    status: Literal["results", "no_documents", "insufficient_information"]
    items: list[FragmentoBusqueda]


def error_response(code: str, message: str, status: int, details=None) -> JSONResponse:
    return JSONResponse(status_code=status, headers={"Cache-Control": "no-store"}, content={
        "error": {"code": code, "message": message, "details": details, "requestId": str(uuid4())},
    })


@router.post("/search", response_model=RespuestaBusqueda, response_model_exclude_none=True)
def buscar(entrada: SolicitudBusqueda, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    with autorizar_busqueda(request):
        service = request.app.state.recuperacion
        if service is None:
            raise ErrorRecuperacion("SEARCH_UNAVAILABLE", "La búsqueda todavía no está habilitada o preparada.")
        result = service.buscar(entrada.query, entrada.limit)
    return result
