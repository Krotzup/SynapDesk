from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.api.errores_auth import RechazoAntesDeEfectos
from app.configuracion import Configuracion
from app.persistencia.conexion import obtener_motor_bd
from app.seguridad.origenes import ServicioOrigen
from app.seguridad.intermediario import IdentidadIntermediario, ServicioIntermediario
from app.seguridad.proxies import IpVerificada
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


def obtener_intermediario(request: Request) -> IdentidadIntermediario:
    """TLS directo, sin interpretación de X-Forwarded-Proto o del peer.

    Requiere listener TLS con proxy_headers=False, sin middleware que reescriba
    scheme. ASGI/TestClient por sí solo no demuestra seguridad del transporte.
    """
    reenviadas = any(
        nombre.lower().startswith(b"x-forwarded-")
        or nombre.lower() in {b"forwarded", b"x-real-ip"}
        for nombre, _ in request.scope["headers"]
    )
    return ServicioIntermediario(obtener_configuracion(request)).verificar(
        request.headers.getlist("authorization"),
        esquema=request.scope.get("scheme", ""), cabeceras_reenviadas=reenviadas,
    )


IntermediarioHttp = Annotated[IdentidadIntermediario, Depends(obtener_intermediario)]


def obtener_ip_verificada(request: Request) -> IpVerificada:
    """Servicio autenticado no demuestra la IP original del navegador.

    No hay adaptador HTTP de procedencia aprobado. No leer Request.client ni
    cabeceras internas/reenviadas para construir IpVerificada. Las pruebas
    internas pueden usar ServicioIpConfiable con evidencia sintética del fixture;
    no existe configuración para habilitar ese adaptador en la aplicación.
    """
    obtener_intermediario(request)
    raise ErrorSeguridad(CodigoSeguridad.IP_NO_VERIFICABLE)


IpVerificadaHttp = Annotated[IpVerificada, Depends(obtener_ip_verificada)]


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
