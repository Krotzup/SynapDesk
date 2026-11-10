from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.api.errores_auth import RechazoAntesDeEfectos
from app.configuracion import Configuracion
from app.persistencia.conexion import obtener_motor_bd
from app.seguridad.origenes import ServicioOrigen
from app.seguridad.secretos import digest_secreto
from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad


def obtener_configuracion(request: Request) -> Configuracion:
    return request.app.state.configuracion


def obtener_sesion(request: Request) -> Iterator[Session]:
    """Una Session por petición; cierre/rollback, nunca commit en teardown.

    AUTH-07B debe usar transaccion_seguridad dentro del handler y construir
    su respuesta/cookies después del bloque, cuando el commit ya concluyó.
    No usar tareas en segundo plano ni streaming con esta sesión.
    """
    motor = obtener_motor_bd(request)
    if motor is None:
        raise ErrorSeguridad(CodigoSeguridad.INFRAESTRUCTURA)
    with Session(motor, expire_on_commit=False) as db:
        yield db


SesionHttp = Annotated[Session, Depends(obtener_sesion, scope="function")]
ConfiguracionHttp = Annotated[Configuracion, Depends(obtener_configuracion)]


def exigir_origin(request: Request, configuracion: ConfiguracionHttp) -> None:
    # getlist conserva todas las ocurrencias; no Request.headers.get ni Host.
    try:
        ServicioOrigen(configuracion).validar(request.headers.getlist("origin"))
    except ErrorSeguridad as error:
        raise RechazoAntesDeEfectos(error.codigo) from None


def obtener_ip_verificada(request: Request) -> None:
    """Sin adaptador autenticado/aislado aprobado, no hay IP HTTP verificable.

    Ni loopback ni forwarded headers acreditan Next.js. No pasar request.client
    a AUTH-06: Uvicorn podría haberlo reescrito. Pendiente de AUTH-07B.
    """
    raise ErrorSeguridad(CodigoSeguridad.IP_NO_VERIFICABLE)


def obtener_token_csrf(request: Request) -> SecretStr:
    """Solo representación inequívoca. AUTH-07B debe validar contexto y vigencia."""
    valores = request.headers.getlist("x-csrf-token")
    if len(valores) != 1:
        raise RechazoAntesDeEfectos(CodigoSeguridad.TOKEN_INVALIDO)
    token = SecretStr(valores[0])
    try:
        digest_secreto(token, CodigoSeguridad.TOKEN_INVALIDO)
    except ErrorSeguridad:
        raise RechazoAntesDeEfectos(CodigoSeguridad.TOKEN_INVALIDO) from None
    return token
