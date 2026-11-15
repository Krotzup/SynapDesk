"""Sondas sin identidad de usuario ni emisión HTTP CSRF/login/me/logout.

Solo el runner crea esta aplicación con motor temporal ya migrado y credenciales
efímeras. No se importa desde app. No acepta ni construye IpVerificada.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.aplicacion import crear_aplicacion
from app.api.adaptadores_auth import extraer_cookies
from app.api.cookies_auth import PerfilCookies, emitir_cookie, eliminar_cookie
from app.api.csrf_auth import exigir_bootstrap_csrf
from app.api.dependencias_auth import exigir_origin, obtener_intermediario, obtener_token_csrf
from app.api.errores_auth import RechazoAntesDeEfectos
from app.api.respuestas_auth import id_peticion, sin_cache
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.intermediario import ServicioIntermediario
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad, transaccion_seguridad


ORIGEN = "https://publico.invalid"


def perfil(nombre="local"):
    assert nombre in {"local", "production"}
    if nombre == "production":
        return PerfilCookies("production", ORIGEN, "__Host-synapdesk_session", "__Host-synapdesk_csrf_context")
    return PerfilCookies("testing", "http://localhost:3000", "synapdesk_session_dev", "synapdesk_csrf_context_dev")


def crear_ensayo(config, motor, nombre, secretos, identidad):
    assert nombre.startswith("synapdesk_auth07_sec01a_")
    with motor.connect() as db:
        assert db.scalar(text("SELECT current_database()")) == nombre
    app = crear_aplicacion(config)

    @app.get("/api/v1/ensayo/eco")
    def eco(request: Request, response: Response, profile: str = "local"):
        cookies = extraer_cookies(request, perfil(profile))
        sin_cache(response)
        return dict(session=cookies.sesion is not None, context=cookies.contexto is not None,
            origin=request.headers.get("origin"), csrf_count=len(request.headers.getlist("x-csrf-token")),
            authorization_present=bool(request.headers.getlist("authorization")),
            forwarded_present=any(k.lower().startswith(b"x-forwarded-") or k.lower() in
                {b"forwarded", b"x-real-ip", b"x-synapdesk-client-ip"} for k, _ in request.scope["headers"]),
            unknown_cookie="desconocida=" in request.headers.get("cookie", ""),
            request_id=str(id_peticion(request)))

    @app.get("/api/v1/ensayo/servicio")
    def servicio(request: Request, response: Response):
        prueba = obtener_intermediario(request)
        with motor.connect() as db:
            assert db.scalar(text("SELECT current_database()")) == nombre
            cabeza = db.scalar(text("SELECT version_num FROM alembic_version"))
        sin_cache(response)
        return dict(service=prueba.servicio, schema=cabeza, user_identity=False, ip_verified=False,
                    request_id=str(id_peticion(request)), harness=identidad)

    @app.get("/api/v1/ensayo/vencida")
    def vencida(request: Request):
        obtener_intermediario(request)  # Primero canal y política real, sin omitirlos.
        politica = config.auth_intermediario.model_copy(update={"credenciales": tuple(
            c.model_copy(update={"vence_en": datetime.now(UTC) - timedelta(seconds=1)})
            for c in config.auth_intermediario.credenciales)})
        caducada = config.model_copy(update={"auth_intermediario": politica})
        ServicioIntermediario(caducada).verificar(request.headers.getlist("authorization"),
            esquema=request.scope["scheme"], cabeceras_reenviadas=False)
        raise AssertionError("La clave vencida no puede autorizar.")

    @app.get("/api/v1/ensayo/otro-entorno")
    def otro_entorno(request: Request):
        obtener_intermediario(request)
        # La misma clave no sirve si política y entorno de aplicación difieren.
        otro = config.model_copy(update={"app_env": "staging"})
        ServicioIntermediario(otro).verificar(request.headers.getlist("authorization"),
            esquema=request.scope["scheme"], cabeceras_reenviadas=False)
        raise AssertionError("No se puede autorizar otro entorno.")

    @app.post("/api/v1/ensayo/controles")
    def controles(request: Request, response: Response):
        exigir_origin(request, config)
        obtener_intermediario(request)
        cookies = extraer_cookies(request, perfil())
        token = obtener_token_csrf(request)
        try:
            with Session(motor) as db, transaccion_seguridad(db):
                ServicioCsrf(db, config).validar_token(token, anonimo=cookies.contexto)
        except ErrorSeguridad as error:
            if error.codigo in {C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO}:
                raise RechazoAntesDeEfectos(error.codigo) from None
            raise
        sin_cache(response)
        return {"validated": True, "business_effects": False}

    @app.get("/api/v1/ensayo/cookies")
    def cookies(response: Response):
        # Marcadores aleatorios del fixture, no credenciales de cuentas/sesiones reales.
        # La transacción de observación termina antes de construir Set-Cookie.
        with motor.begin() as db:
            assert db.scalar(text("SELECT current_database()")) == nombre
        ahora = datetime.now(UTC)
        for p in (perfil(), perfil("production")):
            for tipo in ("sesion", "contexto"):
                emitir_cookie(response, p, tipo, secretos["cookie"], ahora=ahora,
                              vence_en=ahora + timedelta(minutes=5))
        response.set_cookie("desconocida", "marcador", httponly=True)
        return {"fixture_only": True}

    @app.get("/api/v1/ensayo/borrar-cookie")
    def borrar_cookie():
        response = Response(status_code=204)
        for p in (perfil(), perfil("production")):
            for tipo in ("sesion", "contexto"):
                eliminar_cookie(response, p, tipo)
        return response

    @app.get("/api/v1/ensayo/redireccion")
    def redireccion():
        return RedirectResponse("https://no-se-debe-contactar.invalid/", status_code=307)

    @app.get("/api/v1/ensayo/lento")
    async def lento():
        await asyncio.sleep(31)
        return {"late": True}

    @app.get("/api/v1/ensayo/fallo-bd")
    def fallo_bd():
        with motor.connect() as db:
            # Fallo real de PostgreSQL en la base propia, no mock del driver.
            db.execute(text("SELECT * FROM tabla_inexistente_del_arnes"))

    @app.get("/api/v1/ensayo/serializacion")
    def serializacion():
        from fastapi.responses import JSONResponse
        return JSONResponse({"value": object()})

    @app.get("/api/v1/ensayo/bootstrap")
    def bootstrap(request: Request, response: Response):
        exigir_bootstrap_csrf(request, config)
        sin_cache(response)
        return {"gate_only": True, "token_issued": False}

    return app
