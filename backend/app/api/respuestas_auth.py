from uuid import UUID, uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel


def id_peticion(request: Request) -> UUID:
    """UUID del servidor; no adopta X-Request-ID ni otros valores del cliente."""
    if not isinstance(getattr(request.state, "auth_request_id", None), UUID):
        request.state.auth_request_id = uuid4()
    return request.state.auth_request_id


def sin_cache(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    return response


def respuesta_auth(cuerpo: BaseModel, *, estado: int = 200) -> JSONResponse:
    respuesta = JSONResponse(cuerpo.model_dump(mode="json"), status_code=estado)
    sin_cache(respuesta)
    return respuesta
