import json
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, Request, Response
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from starlette.requests import Request as Solicitud

from app.aplicacion import crear_aplicacion
from app.api.cookies_auth import (
    CookieAmbigua, PerfilCookies, eliminar_cookie, emitir_cookie, leer_cookie, preparar_perfil,
)
from app.api.dependencias_auth import exigir_origin, obtener_ip_verificada, obtener_token_csrf, SesionHttp
from app.api.errores_auth import (
    CodigoHttp, RechazoAntesDeEfectos, respuesta_error, respuesta_limite, traducir_error,
)
from app.api.esquemas_auth import AuthUser, RespuestaUsuario, SolicitudLogin, RespuestaCsrf
from app.api.respuestas_auth import id_peticion, respuesta_auth
from app.configuracion import Configuracion
from app.seguridad.contrasenas import ErrorContrasena
from app.seguridad.limites import DecisionLimite
from app.seguridad.origenes import ErrorConfiguracionSeguridad
from app.seguridad.secretos import generar_secreto
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad

AHORA = datetime(2026, 11, 5, 12, tzinfo=UTC)
ORIGEN = "http://localhost:3000"


def aplicacion():
    return crear_aplicacion(Configuracion(_env_file=None, auth_origenes_permitidos=[ORIGEN]))


def solicitud(cabeceras=()):
    return Solicitud({"type": "http", "headers": [(k.encode(), v.encode()) for k, v in cabeceras]})


def perfil(entorno="testing", origen=ORIGEN):
    return PerfilCookies(entorno, origen, "synapdesk_session_dev", "synapdesk_csrf_context_dev")


def test_auth_user_y_envoltura_tienen_campos_exactos():
    usuario = AuthUser(id=uuid4(), email="persona@example.invalid", role="agent")
    datos = RespuestaUsuario(user=usuario).model_dump(mode="json")
    assert set(datos) == {"user"}
    assert set(datos["user"]) == {"id", "email", "role"}
    UUID(datos["user"]["id"])


@pytest.mark.parametrize("cambio", [dict(name="extra"), dict(id="no_uuid"), dict(role="root"), dict(email=3)])
def test_auth_user_rechaza_campos_y_tipos_invalidos(cambio):
    with pytest.raises(ValidationError):
        AuthUser(**(dict(id=uuid4(), email="a@example.invalid", role="admin") | cambio))


def test_login_normaliza_cuenta_sin_transformar_password_ni_exponerla():
    entrada = SolicitudLogin(email="  ÁGENTE@Example.invalid  ", password="  secreto ficticio  ")
    assert entrada.email == "ágente@example.invalid"
    assert entrada.password.get_secret_value() == "  secreto ficticio  "
    assert "secreto ficticio" not in repr(entrada)
    assert "secreto ficticio" not in entrada.model_dump_json()


@pytest.mark.parametrize("datos", [dict(email="sin_arroba", password="a"), dict(email="@dom", password="a"),
    dict(email="a@", password="a"), dict(email="a b@dom", password="a"), dict(email=7, password="a"),
    dict(email="a@b", password=123), dict(email="a@b", password=""), dict(email="a@b"),
    dict(email="a@b", password="a", role="admin"), dict(email="a@b", password="\ud800")])
def test_login_rechaza_entradas_invalidas(datos):
    with pytest.raises(ValidationError):
        SolicitudLogin(**datos)


def test_csrf_serializa_solo_el_token_previsto_y_utc():
    token = generar_secreto()
    dto = RespuestaCsrf(csrfToken=token, expiresAt=AHORA.astimezone(timezone(timedelta(hours=-3))))
    assert token.get_secret_value() not in repr(dto)
    assert dto.expiresAt.utcoffset() == timedelta(0)
    assert json.loads(dto.model_dump_json()) == {"csrfToken": token.get_secret_value(), "expiresAt": "2026-11-05T12:00:00Z"}


@pytest.mark.parametrize("token,vence", [("invalido", AHORA), ("a"*43, AHORA.replace(tzinfo=None))])
def test_csrf_rechaza_representaciones_invalidas(token, vence):
    with pytest.raises(ValidationError):
        RespuestaCsrf(csrfToken=token, expiresAt=vence)


def test_validacion_http_sanea_valores_loc_y_mensajes(caplog):
    app = aplicacion()

    @app.post("/prueba")
    def prueba(entrada: SolicitudLogin):
        return {}

    with TestClient(app) as cliente:
        respuesta = cliente.post("/prueba", json={"email": "no_correo_secreto", "password": 123,
                                                   "token_secreto_como_campo": "no_publicar"},
                                 headers={"X-Request-ID": str(uuid4())})
    assert respuesta.status_code == 422
    error = respuesta.json()["error"]
    assert set(error) == {"code", "message", "details", "requestId"}
    assert error["code"] == "VALIDATION_ERROR"
    assert {d["field"] for d in error["details"]} == {"email", "password"}
    UUID(error["requestId"])
    assert respuesta.headers["Cache-Control"] == "no-store"
    for secreto in ("no_correo_secreto", "token_secreto_como_campo", "no_publicar", "123"):
        assert secreto not in respuesta.text
        assert secreto not in caplog.text


def test_json_malformado_no_expone_cuerpo():
    app = aplicacion()

    @app.post("/prueba")
    def prueba(entrada: SolicitudLogin):
        return {}

    with TestClient(app) as cliente:
        respuesta = cliente.post("/prueba", content='{"password":"secreto_no_publicar",',
                                 headers={"Content-Type": "application/json"})
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["details"] == []
    assert "secreto_no_publicar" not in respuesta.text


@pytest.mark.parametrize("codigo", [C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO])
def test_csrf_previo_a_efectos_comparte_respuesta_publica(codigo):
    app = aplicacion()

    @app.post("/prueba")
    def prueba():
        raise RechazoAntesDeEfectos(codigo)

    with TestClient(app) as cliente:
        r = cliente.post("/prueba")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_INVALID"
    assert r.json()["error"]["details"] is None
    assert codigo.value not in r.text


@pytest.mark.parametrize("codigo", [C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO])
def test_csrf_sin_garantia_previa_no_publica_error_reintentable(codigo):
    assert traducir_error(ErrorSeguridad(codigo)) == CodigoHttp.INTERNAL_ERROR


@pytest.mark.parametrize("error,estado,codigo", [
    (ErrorSeguridad(C.SESION_VENCIDA),401,"AUTHENTICATION_REQUIRED"),
    (ErrorSeguridad(C.SESION_INEXISTENTE),401,"AUTHENTICATION_REQUIRED"),
    (ErrorSeguridad(C.SESION_REVOCADA),401,"AUTHENTICATION_REQUIRED"),
    (ErrorSeguridad(C.INFRAESTRUCTURA),503,"SERVICE_UNAVAILABLE"),
    (ErrorSeguridad(C.TRANSACCION),503,"SERVICE_UNAVAILABLE"),
    (ErrorSeguridad(C.CONFLICTO_VERSION),503,"SERVICE_UNAVAILABLE"),
    (OperationalError("SQL secreto",{},Exception("clave oculta")),503,"SERVICE_UNAVAILABLE"),
    (ErrorContrasena("hash privado"),500,"INTERNAL_ERROR"),
    (ErrorConfiguracionSeguridad("clave HMAC"),500,"INTERNAL_ERROR"),
    (RuntimeError("token privado"),500,"INTERNAL_ERROR"),
    (ErrorSeguridad(C.LIMITE_TOKENS),500,"INTERNAL_ERROR"),
])
def test_errores_no_confunden_infraestructura_y_credenciales(error, estado, codigo, caplog):
    app = aplicacion()

    @app.get("/prueba")
    def prueba():
        raise error

    with TestClient(app, raise_server_exceptions=False) as cliente:
        r = cliente.get("/prueba")
    assert r.status_code == estado
    assert r.json()["error"]["code"] == codigo
    assert r.json()["error"]["details"] is None
    assert r.headers["Cache-Control"] == "no-store"
    for dato in ("SQL secreto", "clave oculta", "hash privado", "clave HMAC", "token privado", "INVALID_CREDENTIALS"):
        assert dato not in r.text and dato not in caplog.text


@pytest.mark.parametrize("cabeceras,estado", [
    ([("Origin", ORIGEN)],200), ([],403), ([("Origin","null")],403),
    ([("Origin","https://externo.invalid")],403), ([("Origin",ORIGEN),("Origin",ORIGEN)],403),
    ([("Origin",ORIGEN+", "+ORIGEN)],403), ([("Origin","http://localhost:3001")],403),
    ([("Origin","https://localhost:3000")],403),
    ([("X-Forwarded-Host","localhost:3000"),("Referer",ORIGEN)],403),
])
def test_origin_http_conserva_ocurrencias_y_rechaza_ambiguedad(cabeceras, estado):
    app = aplicacion()
    efectos = []

    @app.post("/prueba", dependencies=[Depends(exigir_origin)])
    def prueba():
        efectos.append(True)
        return {}

    with TestClient(app) as cliente:
        r = cliente.post("/prueba", headers=cabeceras)
    assert r.status_code == estado
    assert bool(efectos) == (estado == 200)
    if estado == 403:
        assert r.json()["error"]["code"] == "ORIGIN_INVALID"


def test_origin_sin_configuracion_es_error_del_servidor():
    app = crear_aplicacion(Configuracion(_env_file=None))

    @app.post("/prueba", dependencies=[Depends(exigir_origin)])
    def prueba():
        return {}

    with TestClient(app) as cliente:
        r = cliente.post("/prueba", headers={"Origin":ORIGEN})
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "INTERNAL_ERROR"


@pytest.mark.parametrize("caso", ["valido","ausente","duplicado","combinado","invalido"])
def test_csrf_header_exige_una_sola_representacion(caso):
    token = generar_secreto().get_secret_value()
    headers = {"valido":[("X-CSRF-Token",token)], "ausente":[],
               "duplicado":[("X-CSRF-Token",token),("X-CSRF-Token",token)],
               "combinado":[("X-CSRF-Token",token+", "+token)],
               "invalido":[("X-CSRF-Token","secreto_invalido")]}[caso]
    app = aplicacion()

    @app.post("/prueba",dependencies=[Depends(obtener_token_csrf)])
    def prueba():
        return {}

    with TestClient(app) as cliente:
        r = cliente.post("/prueba",headers=headers)
    assert r.status_code == (200 if caso == "valido" else 403)
    assert token not in r.text and "secreto_invalido" not in r.text


@pytest.mark.parametrize("cabecera", [None,"X-Forwarded-For","X-Real-IP","Forwarded","X-SynapDesk-Client-IP"])
def test_ip_sigue_cerrada_incluso_desde_loopback(cabecera):
    app = aplicacion()

    @app.post("/prueba", dependencies=[Depends(obtener_ip_verificada)])
    def prueba():
        pytest.fail("No debe concederse IP sin procedencia verificable")

    with TestClient(app, client=("127.0.0.1",1234)) as cliente:
        r = cliente.post("/prueba", headers={cabecera:"198.51.100.9"} if cabecera else {})
    assert r.status_code == 503 and r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.parametrize("entorno,origen,segura", [("testing",ORIGEN,False),
    ("development","https://localhost:3000",True), ("production","https://publico.invalid",True)])
def test_emision_y_borrado_con_atributos_compatibles(entorno, origen, segura):
    p = perfil(entorno, origen)
    r = Response()
    emitir_cookie(r,p,"sesion",generar_secreto(),ahora=AHORA,vence_en=AHORA+timedelta(seconds=90.9))
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert ("Secure" in cookie) == segura
    assert "Domain=" not in cookie and "Max-Age=90" in cookie
    assert r.headers["Cache-Control"] == "no-store"
    borrar = Response()
    eliminar_cookie(borrar,p,"sesion")
    assert "Max-Age=0" in borrar.headers["set-cookie"]
    for atributo in ("HttpOnly","SameSite=lax","Path=/"):
        assert atributo in borrar.headers["set-cookie"]
    assert ("Secure" in borrar.headers["set-cookie"]) == segura
    assert "Domain=" not in borrar.headers["set-cookie"]


@pytest.mark.parametrize("entorno,origen,nombre", [("production",ORIGEN,"sesion"),
    ("staging",ORIGEN,"sesion"),("development","http://publico.invalid","sesion"),
    ("testing",ORIGEN,"__Host-sesion"),("testing",ORIGEN,"sesion;invalida"),
    ("otro",ORIGEN,"sesion")])
def test_perfiles_rechazan_configuracion_insegura(entorno, origen, nombre):
    with pytest.raises(ErrorConfiguracionSeguridad):
        PerfilCookies(entorno,origen,nombre,"contexto")


def test_perfil_exige_origen_configurado_y_nombres_distintos():
    c = Configuracion(_env_file=None, auth_origenes_permitidos=[ORIGEN])
    assert not preparar_perfil(c, origen_publico=ORIGEN,nombre_sesion="sesion",nombre_contexto="contexto").secure
    with pytest.raises(ErrorConfiguracionSeguridad):
        preparar_perfil(c,origen_publico="http://127.0.0.1:3000",nombre_sesion="s",nombre_contexto="c")
    with pytest.raises(ErrorConfiguracionSeguridad):
        PerfilCookies("testing",ORIGEN,"igual","igual")


@pytest.mark.parametrize("cabeceras", [
    [("cookie","synapdesk_session_dev=a; synapdesk_session_dev=b")],
    [("cookie","synapdesk_session_dev=a"),("cookie","synapdesk_session_dev=a")],
    [("cookie",'synapdesk_session_dev="a"')],[("cookie","synapdesk_session_dev=")],
    [("cookie","synapdesk_session_dev")],
    [("cookie","synapdesk_session_dev =a; synapdesk_session_dev=b")],
])
def test_rechaza_cookie_duplicada_o_ambigua(cabeceras):
    with pytest.raises(CookieAmbigua):
        leer_cookie(solicitud(cabeceras),perfil(),"sesion")


def test_lee_solo_cookie_del_perfil_y_no_duplica_set_cookie():
    assert leer_cookie(solicitud(),perfil(),"sesion") is None
    assert leer_cookie(solicitud([("cookie","otra=a; synapdesk_session_dev=abc")]),perfil(),"sesion").get_secret_value() == "abc"
    r = Response()
    emitir_cookie(r,perfil(),"sesion",generar_secreto(),ahora=AHORA,vence_en=AHORA+timedelta(seconds=30))
    emitir_cookie(r,perfil(),"contexto",generar_secreto(),ahora=AHORA,vence_en=AHORA+timedelta(seconds=20))
    assert len(r.headers.getlist("set-cookie")) == 2
    with pytest.raises(ErrorConfiguracionSeguridad):
        eliminar_cookie(r,perfil(),"sesion")


@pytest.mark.parametrize("vence", [AHORA, AHORA-timedelta(seconds=1), AHORA.replace(tzinfo=None)])
def test_no_emite_cookie_sin_vigencia_valida(vence):
    r = Response()
    with pytest.raises(ErrorConfiguracionSeguridad):
        emitir_cookie(r,perfil(),"sesion",generar_secreto(),ahora=AHORA,vence_en=vence)
    assert "set-cookie" not in r.headers


def test_no_emite_credencial_corta_o_no_canonica():
    from pydantic import SecretStr
    with pytest.raises(ErrorConfiguracionSeguridad):
        emitir_cookie(Response(),perfil(),"sesion",SecretStr("corta"),
                      ahora=AHORA,vence_en=AHORA+timedelta(seconds=30))


def test_retry_after_se_deriva_de_la_decision_y_no_se_inventa():
    r = respuesta_limite(solicitud(),DecisionLimite(False,AHORA,AHORA+timedelta(seconds=2.1)))
    assert r.status_code == 429 and r.headers["Retry-After"] == "3"
    assert r.headers["Cache-Control"] == "no-store"
    assert json.loads(r.body)["error"]["code"] == "RATE_LIMITED"
    for d in [DecisionLimite(True,AHORA),DecisionLimite(False,AHORA),DecisionLimite(False,AHORA,AHORA)]:
        with pytest.raises(ErrorConfiguracionSeguridad):
            respuesta_limite(solicitud(),d)


def test_request_id_es_del_servidor_y_se_reutiliza_solo_en_la_peticion():
    falso = uuid4()
    r = solicitud([("x-request-id",str(falso))])
    primero = id_peticion(r)
    assert primero != falso and primero == id_peticion(r)
    assert primero != id_peticion(solicitud())


def test_uvicorn_sin_proxy_headers_no_reescribe_el_peer():
    from uvicorn import Config
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    configuracion = Config(aplicacion(),proxy_headers=False,log_config=None)
    configuracion.load()
    assert not isinstance(configuracion.loaded_app,ProxyHeadersMiddleware)


def test_respuesta_usuario_es_no_store_y_no_expone_campos_internos():
    r = respuesta_auth(RespuestaUsuario(user=AuthUser(id=uuid4(),email="a@b",role="admin")))
    assert r.headers["Cache-Control"] == "no-store"
    assert set(json.loads(r.body)["user"]) == {"id","email","role"}
    assert "set-cookie" not in r.headers


def test_sesion_sin_motor_falla_cerrada_y_rutas_reales_siguen_intactas():
    app = aplicacion()
    assert set(app.openapi()["paths"]) == {
        "/api/v1/health", "/api/v1/ready", "/api/v1/auth/csrf",
    }

    @app.get("/prueba")
    def prueba(db: SesionHttp):
        return {}

    with TestClient(app) as cliente:
        assert cliente.get("/prueba").status_code == 503
        assert cliente.get("/api/v1/health").status_code == 200
        r = cliente.get("/api/v1/ready")
        assert r.status_code == 503 and r.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
