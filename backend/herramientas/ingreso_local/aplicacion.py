"""Composición local explícita con servicios reales; nunca importada por app.aplicacion."""

import json
from uuid import UUID

from fastapi import FastAPI, Request
from pydantic import ValidationError
from sqlalchemy import Engine, text
from starlette.concurrency import run_in_threadpool

from app.api.adaptadores_auth import AdaptadorAuth, extraer_cookies
from app.api.adaptadores_tickets import AdaptadorTickets
from app.api.cookies_auth import CookieAmbigua, PerfilCookies
from app.api.dependencias_auth import exigir_origin, obtener_intermediario
from app.api.errores_auth import CodigoHttp, registrar_errores, respuesta_error, traducir_error
from app.api.esquemas_auth import DetalleValidacion, SolicitudLogin, SolicitudLogout
from app.api.salud import router as router_salud
from app.api.busqueda import error_response
from app.api.recomendaciones import router as router_recomendaciones
from app.configuracion import Configuracion
from app.recuperacion.servicio import ErrorRecuperacion
from herramientas.ingreso_local.evidencia import VerificadorIngresoLocal, exigir_testing_propio
from app.tickets.esquemas import TicketCreate, TicketPagination, TicketStatusUpdate


def crear_aplicacion_local(config: Configuracion, motor: Engine, perfil: PerfilCookies,
                           verificador: VerificadorIngresoLocal, *, capacidad_argon2: int,
                           max_cuerpo_bytes: int, recuperacion=None) -> FastAPI:
    exigir_testing_propio(config)
    if type(verificador) is not VerificadorIngresoLocal or not 1 <= max_cuerpo_bytes <= 1048576:
        raise ValueError("Composición local inválida.")
    with motor.connect() as db:
        assert db.execute(text("SELECT current_database(), current_user")).one() == (config.postgres_db, config.postgres_user)
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0007_recomendaciones_rag"
    auth = AdaptadorAuth(motor, config, perfil, capacidad_argon2=capacidad_argon2, procedencia_ip=verificador)
    tickets = AdaptadorTickets(motor, config, perfil)
    app = FastAPI(title="SynapDesk MVP04 — ensayo aislado", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.configuracion, app.state.motor_bd = config, motor
    app.state.recuperacion = recuperacion
    registrar_errores(app)
    app.include_router(router_salud, prefix="/api/v1")

    if config.rag_enabled:
        if config.auth_cookie_profile != "local" or config.rag_public_origin != perfil.origen_publico:
            raise ValueError("El acceso RAG local requiere el origen y las cookies del ensayo.")

        @app.exception_handler(ErrorRecuperacion)
        async def error_rag(request, error):
            return error_response(error.code, error.message, error.status)

        @app.middleware("http")
        async def ingreso_rag(request: Request, siguiente):
            ruta = request.url.path
            if (ruta.startswith("/api/v1/recommendations/") or
                    ruta.startswith("/api/v1/tickets/") and ruta.endswith("/recommendations")):
                try:
                    if request.method == "POST":
                        exigir_origin(request, config)
                    elif request.headers.getlist("origin"):
                        exigir_origin(request, config)
                    obtener_intermediario(request)
                    extraer_cookies(request, perfil)
                    verificador(request)
                except Exception as error:
                    return respuesta_error(request, traducir_error(error))
            return await siguiente(request)

        app.include_router(router_recomendaciones, prefix="/api/v1")

    @app.get("/api/v1/auth/csrf")
    def csrf(request: Request):
        return auth.csrf(request)

    @app.post("/api/v1/auth/login")
    async def login(request: Request):
        try:
            # Controles previos a parsear, sin consumir prueba/cuotas dos veces.
            exigir_origin(request, config)
            obtener_intermediario(request)
            extraer_cookies(request, perfil)
            partes, longitud = [], 0
            async for parte in request.stream():
                longitud += len(parte)
                if longitud > max_cuerpo_bytes:
                    return respuesta_error(request, CodigoHttp.VALIDATION_ERROR)
                partes.append(parte)

            def sin_duplicados(pares):
                resultado = {}
                for nombre, valor in pares:
                    if nombre in resultado:
                        raise ValueError
                    resultado[nombre] = valor
                return resultado

            datos = SolicitudLogin.model_validate(json.loads(b"".join(partes), object_pairs_hook=sin_duplicados))
            return await run_in_threadpool(auth.login, request, datos)
        except (ValidationError, ValueError, UnicodeError):
            return respuesta_error(request, CodigoHttp.VALIDATION_ERROR)
        except Exception as error:
            return respuesta_error(request, traducir_error(error))

    @app.get("/api/v1/auth/me")
    def me(request: Request):
        try:
            # Sello del ingreso local, no una cuota/IP adicional de /me.
            if request.headers.getlist("origin"):
                exigir_origin(request, config)
            obtener_intermediario(request)
            extraer_cookies(request, perfil)
            verificador(request)
            return auth.me(request)
        except Exception as error:
            return respuesta_error(request, traducir_error(error))

    def leer(request: Request, ejecutar):
        try:
            if request.headers.getlist("origin"):
                exigir_origin(request, config)
            obtener_intermediario(request)
            extraer_cookies(request, perfil)
            verificador(request)
            return ejecutar()
        except CookieAmbigua as error:
            return respuesta_error(request, traducir_error(error))
        except (ValueError, ValidationError):
            return respuesta_error(request, CodigoHttp.VALIDATION_ERROR)
        except Exception as error:
            return respuesta_error(request, traducir_error(error))

    async def cuerpo_modelo(request: Request, modelo):
        partes, longitud = [], 0
        async for parte in request.stream():
            longitud += len(parte)
            if longitud > max_cuerpo_bytes:
                raise ValueError
            partes.append(parte)

        def sin_duplicados(pares):
            resultado = {}
            for nombre, valor in pares:
                if nombre in resultado:
                    raise ValueError
                resultado[nombre] = valor
            return resultado

        return modelo.model_validate(json.loads(b"".join(partes), object_pairs_hook=sin_duplicados))

    async def escritura(request: Request, modelo, ejecutar):
        try:
            # La frontera se acredita antes de parsear el JSON y el adaptador vuelve a
            # comprobar sesión, rol y CSRF dentro de la transacción de negocio.
            exigir_origin(request, config)
            obtener_intermediario(request)
            extraer_cookies(request, perfil)
            verificador(request)
            datos = await cuerpo_modelo(request, modelo)
            return await run_in_threadpool(ejecutar, request, datos)
        except CookieAmbigua as error:
            return respuesta_error(request, traducir_error(error))
        except ValidationError as error:
            nombres = {item["loc"][0] for item in error.errors(include_input=False, include_context=False)
                       if item["loc"] and item["loc"][0] in modelo.model_fields
                       and item["loc"][0] in {"title", "description", "status"}}
            return respuesta_error(request, CodigoHttp.VALIDATION_ERROR, detalles=[
                DetalleValidacion(field=nombre, message="El campo no tiene un valor válido.")
                for nombre in sorted(nombres)])
        except (ValueError, UnicodeError):
            return respuesta_error(request, CodigoHttp.VALIDATION_ERROR)
        except Exception as error:
            return respuesta_error(request, traducir_error(error))

    @app.post("/api/v1/auth/logout")
    async def logout(request: Request):
        return await escritura(request, SolicitudLogout, auth.logout)

    @app.get("/api/v1/tickets")
    def listado(request: Request):
        def ejecutar():
            parametros = request.query_params
            if set(parametros) - {"page", "pageSize"} or any(
                    len(parametros.getlist(k)) != 1 for k in parametros):
                raise ValueError
            datos = {}
            for nombre in ("page", "pageSize"):
                if nombre in parametros:
                    valor = parametros[nombre]
                    if not valor.isascii() or not valor.isdecimal():
                        raise ValueError
                    datos[nombre] = int(valor)
            return tickets.listar(request, TicketPagination.model_validate(datos))
        return leer(request, ejecutar)

    @app.post("/api/v1/tickets")
    async def crear(request: Request):
        return await escritura(request, TicketCreate, tickets.crear)

    @app.get("/api/v1/tickets/summary")
    @app.get("/api/v1/metrics/summary")
    def resumen(request: Request):
        return leer(request, lambda: tickets.resumen(request))

    @app.get("/api/v1/tickets/{ticket_id}")
    def detalle(request: Request, ticket_id: str):
        return leer(request, lambda: tickets.detalle(request, UUID(ticket_id)))

    @app.patch("/api/v1/tickets/{ticket_id}")
    async def actualizar_estado(request: Request, ticket_id: str):
        def ejecutar(peticion: Request, datos: TicketStatusUpdate):
            return tickets.actualizar_estado(peticion, UUID(ticket_id), datos)

        return await escritura(request, TicketStatusUpdate, ejecutar)

    return app
