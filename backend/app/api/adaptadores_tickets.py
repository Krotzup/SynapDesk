"""MVP02: cinco adaptadores candidatos. Sin APIRouter, registro ni modo inseguro.

La fábrica de aplicación no los importa/instancia. Un router futuro debe cerrar
los contratos pendientes y acreditar listener TLS/canal/sesión reales.
"""

from collections.abc import Callable
from uuid import UUID

from fastapi import Request, Response
from pydantic import ValidationError
from sqlalchemy import Engine

from app.api.adaptadores_auth import extraer_cookies
from app.api.cookies_auth import PerfilCookies, preparar_perfil
from app.api.dependencias_auth import exigir_origin, obtener_intermediario, obtener_token_csrf
from app.api.errores_auth import CodigoHttp, RechazoAntesDeEfectos, respuesta_error, traducir_error
from app.api.esquemas_auth import ApiErrorBody, DetalleValidacion, RespuestaError
from app.api.respuestas_auth import id_peticion, respuesta_auth, sin_cache
from app.configuracion import Configuracion
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad, Reloj, reloj_postgresql
from app.tickets.esquemas import TicketCreate, TicketPagination, TicketStatusUpdate
from app.tickets.repositorio import CodigoTickets, ErrorTickets
from app.tickets.servicio import ServicioTickets


class AdaptadorTickets:
    def __init__(self, motor: Engine, configuracion: Configuracion, perfil: PerfilCookies, *,
                 reloj: Reloj = reloj_postgresql) -> None:
        self._config = configuracion.model_copy(deep=True)
        validado = preparar_perfil(self._config, origen_publico=perfil.origen_publico,
            nombre_sesion=perfil.nombre_sesion, nombre_contexto=perfil.nombre_contexto)
        if validado != perfil:
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        self._perfil = validado
        self._reloj = reloj
        self._servicio = ServicioTickets(motor, reloj=reloj)

    def _frontera(self, request: Request, metodo: str):
        if request.method != metodo:
            raise ErrorTickets(CodigoTickets.ENTRADA)
        if request.app.state.configuracion != self._config:
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        if metodo != "GET" or request.headers.getlist("origin"):
            exigir_origin(request, self._config)
        obtener_intermediario(request)  # SEC-01B y TLS; no es identidad de usuario.
        return extraer_cookies(request, self._perfil).referencia()

    def _control(self, request: Request, referencia):
        def comprobar(db, actual, antes_de_efectos):
            try:
                token = obtener_token_csrf(request)
                ServicioCsrf(db, self._config, self._reloj).validar_token(
                    token, sesion=referencia.credencial)
            except ErrorSeguridad as error:
                if error.codigo in {C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO}:
                    if antes_de_efectos:
                        raise RechazoAntesDeEfectos(error.codigo) from None
                    # Hubo trabajo SQL no confirmado. El coordinador revierte;
                    # no etiquetar como rechazo previo ni autorizar retry.
                    raise ErrorSeguridad(C.INFRAESTRUCTURA) from None
                raise
        return comprobar

    def _responder(self, request: Request, tarea: Callable[[], Response]) -> Response:
        id_peticion(request)
        try:
            return sin_cache(tarea())
        except ValidationError as error:
            nombres = {item["loc"][0] for item in error.errors(include_input=False, include_context=False)
                       if item["loc"] and item["loc"][0] in {"title", "description", "status", "page", "pageSize"}}
            return respuesta_error(request, CodigoHttp.VALIDATION_ERROR, detalles=[
                DetalleValidacion(field=nombre, message="El campo no tiene un valor válido.")
                for nombre in sorted(nombres)])
        except ErrorTickets as error:
            if error.codigo == CodigoTickets.NO_ENCONTRADO:
                return respuesta_auth(RespuestaError(error=ApiErrorBody(
                    code="TICKET_NOT_FOUND", message="No se encontró el ticket solicitado.",
                    details=None, requestId=id_peticion(request))), estado=404)
            if error.codigo == CodigoTickets.NO_AUTORIZADO:
                return respuesta_auth(RespuestaError(error=ApiErrorBody(
                    code="FORBIDDEN", message="No tienes permiso para esta operación.",
                    details=None, requestId=id_peticion(request))), estado=403)
            codigo = (CodigoHttp.VALIDATION_ERROR if error.codigo == CodigoTickets.ENTRADA
                      else CodigoHttp.SERVICE_UNAVAILABLE)
            # Conflicto de estado: sin nuevo código 409/DTO público no aprobado.
            return respuesta_error(request, codigo)
        except Exception as error:
            if isinstance(error, ErrorSeguridad) and error.codigo == C.ROL_INVALIDO:
                return respuesta_auth(RespuestaError(error=ApiErrorBody(
                    code="FORBIDDEN", message="No tienes permiso para esta operación.",
                    details=None, requestId=id_peticion(request))), estado=403)
            return respuesta_error(request, traducir_error(error))

    def crear(self, request: Request, datos: TicketCreate) -> Response:
        def ejecutar():
            referencia = self._frontera(request, "POST")
            resultado = self._servicio.crear(referencia, datos,
                control_escritura=self._control(request, referencia))
            return respuesta_auth(resultado, estado=201)
        return self._responder(request, ejecutar)

    def listar(self, request: Request, pagina: TicketPagination | None = None) -> Response:
        return self._responder(request, lambda: respuesta_auth(self._servicio.listar(
            self._frontera(request, "GET"), pagina)))

    def detalle(self, request: Request, ticket_id: UUID) -> Response:
        return self._responder(request, lambda: respuesta_auth(self._servicio.detalle(
            self._frontera(request, "GET"), ticket_id)))

    def actualizar_estado(self, request: Request, ticket_id: UUID, datos: TicketStatusUpdate) -> Response:
        def ejecutar():
            referencia = self._frontera(request, "PATCH")
            resultado = self._servicio.actualizar_estado(referencia, ticket_id, datos,
                control_escritura=self._control(request, referencia))
            return respuesta_auth(resultado)
        return self._responder(request, ejecutar)

    def resumen(self, request: Request) -> Response:
        return self._responder(request, lambda: respuesta_auth(self._servicio.resumen(
            self._frontera(request, "GET"))))
