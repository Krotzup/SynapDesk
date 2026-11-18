"""Decisiones del adaptador candidato; sin registrar rutas en la app real."""

from datetime import UTC, datetime, timedelta
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.aplicacion import crear_aplicacion
from app.api.adaptadores_auth import AdaptadorAuth, extraer_cookies, prueba_login
from app.api.cookies_auth import CookieAmbigua, preparar_perfil
from app.api.esquemas_auth import AuthUser, SolicitudLogin, SolicitudLogout
from app.api.respuestas_auth import id_peticion
from app.persistencia.conexion import crear_motor_bd
from app.seguridad.auditoria import MotivoEvento as M
from app.seguridad.login import LoginConfirmado, LoginRechazado, PruebaAnonimaLogin, PruebaSesionLogin
from app.seguridad.secretos import generar_secreto
from app.seguridad.sesiones import Identidad, SesionEmitida
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad
from pruebas.intermediario_auxiliar import ORIGEN, cabeceras, credencial, politica
from pruebas.login_auxiliar import configuracion_login, ip_controlada


def request(config, headers=None, *, method="POST", scheme="https"):
    app = crear_aplicacion(config)
    return Request(dict(type="http", method=method, scheme=scheme, path="/candidato",
        query_string=b"", server=("localhost", 443), client=("127.0.0.1", 1234),
        app=app, headers=[(k.lower().encode(), v.encode()) for k, v in (headers or [])]))


@pytest.fixture
def entorno():
    token = credencial()
    config = configuracion_login(auth_intermediario=politica([token]),
        auth_origenes_permitidos=[ORIGEN], postgres_host="localhost", postgres_port=5433,
        postgres_db="synapdesk_auth07_sec01a_" + uuid4().hex, postgres_user="fixture",
        postgres_password=generar_secreto())
    perfil = preparar_perfil(config, origen_publico=ORIGEN,
        nombre_sesion="synapdesk_session_dev", nombre_contexto="synapdesk_csrf_context_dev")
    motor = crear_motor_bd(config)
    a = AdaptadorAuth(motor, config, perfil, capacidad_argon2=1)
    e = dict(config=config, perfil=perfil, motor=motor, adaptador=a, token=token)
    e["headers"] = list(cabeceras(token).items())
    try:
        yield e
    finally:
        motor.dispose()


def error(respuesta, codigo, estado):
    assert respuesta.status_code == estado
    assert respuesta.headers["cache-control"] == "no-store"
    assert "set-cookie" not in respuesta.headers
    cuerpo = json.loads(respuesta.body)["error"]
    assert set(cuerpo) == {"code", "message", "details", "requestId"}
    assert cuerpo["code"] == codigo
    assert isinstance(UUID(cuerpo["requestId"]), UUID)
    return cuerpo


def test_cookie_valida_ausente_y_pruebas_tipadas(entorno):
    e = entorno
    sesion, contexto, csrf = generar_secreto(), generar_secreto(), generar_secreto()
    ausente = extraer_cookies(request(e["config"]), e["perfil"])
    assert ausente.referencia() is None
    r = request(e["config"], [("Cookie", "synapdesk_session_dev=" + sesion.get_secret_value())])
    c = extraer_cookies(r, e["perfil"])
    assert c.referencia().credencial == sesion
    assert isinstance(prueba_login(c, csrf), PruebaSesionLogin)
    r = request(e["config"], [("Cookie", "synapdesk_csrf_context_dev=" + contexto.get_secret_value())])
    c = extraer_cookies(r, e["perfil"])
    assert isinstance(prueba_login(c, csrf), PruebaAnonimaLogin)
    assert sesion.get_secret_value() not in repr(c) + repr(c.referencia())


@pytest.mark.parametrize("cookie", [
    "synapdesk_session_dev=a; synapdesk_session_dev=a",
    'synapdesk_session_dev="valor"', "synapdesk_session_dev=a b",
    "synapdesk_session_dev", "synapdesk_session_dev=",
    "__Host-synapdesk_session=a", "__Host-synapdesk_csrf_context=a",
])
def test_cookie_duplicada_malformada_y_otro_perfil_rechazados(entorno, cookie):
    with pytest.raises(CookieAmbigua):
        extraer_cookies(request(entorno["config"], [("Cookie", cookie)]), entorno["perfil"])


@pytest.mark.parametrize("caso", ["ausente", "incorrecto", "duplicado", "http", "forwarded"])
def test_intermediario_se_exige_en_me(entorno, caso):
    e = entorno
    headers = e["headers"].copy()
    scheme = "https"
    if caso == "ausente":
        headers = [("Origin", ORIGEN)]
    elif caso == "incorrecto":
        headers = list(cabeceras(credencial()).items())
    elif caso == "duplicado":
        headers.append(headers[0])
    elif caso == "http":
        scheme = "http"
    else:
        headers.append(("X-Forwarded-For", "198.51.100.7"))
    error(e["adaptador"].me(request(e["config"], headers, scheme=scheme)), "SERVICE_UNAVAILABLE", 503)
    assert e["motor"].pool.checkedout() == 0


@pytest.mark.parametrize("origin", [None, "null", "https://otro.invalid", ORIGEN + ", " + ORIGEN])
def test_origin_logout_obligatorio_antes_de_efectos(entorno, origin):
    e = entorno
    headers = [(k, v) for k, v in e["headers"] if k != "Origin"]
    if origin is not None:
        headers.append(("Origin", origin))
    error(e["adaptador"].logout(request(e["config"], headers), SolicitudLogout()), "ORIGIN_INVALID", 403)


def test_me_sin_origin_ssr_no_store_y_request_id_local(entorno, monkeypatch):
    e = entorno
    identidad = AuthUser(id=uuid4(), email="a@b", role="agent")
    monkeypatch.setattr(e["adaptador"]._consulta, "consultar", lambda ref: identidad)
    falso = uuid4()
    r = request(e["config"], [e["headers"][0], ("X-Request-ID", str(falso))], method="GET")
    respuesta = e["adaptador"].me(r)
    assert respuesta.status_code == 200 and respuesta.headers["cache-control"] == "no-store"
    assert set(json.loads(respuesta.body)["user"]) == {"id", "email", "role"}
    assert id_peticion(r) != falso
    assert "set-cookie" not in respuesta.headers


@pytest.mark.parametrize("operacion", ["csrf", "login"])
def test_ip_no_acreditada_impide_efectos_aunque_bearer_valido(entorno, operacion):
    e = entorno
    r = request(e["config"], e["headers"], method="GET" if operacion == "csrf" else "POST")
    a = e["adaptador"]
    resultado = a.csrf(r) if operacion == "csrf" else a.login(r, SolicitudLogin(email="a@b", password=generar_secreto().get_secret_value()))
    error(resultado, "SERVICE_UNAVAILABLE", 503)
    assert e["motor"].pool.checkedout() == 0


def habilitar_ip_solo_test(e, monkeypatch):
    # No existe como opción de la aplicación: únicamente monkeypatch de pruebas.
    monkeypatch.setattr("app.api.adaptadores_auth.obtener_ip_verificada", lambda request: ip_controlada(e["config"]))


def entrada_login():
    return SolicitudLogin(email="  PERSONA@EXAMPLE.INVALID  ", password=generar_secreto().get_secret_value())


@pytest.mark.parametrize("caso", ["ausente", "duplicado", "malformado", "persistido"])
def test_csrf_invalido_antes_de_login_sin_cookie_de_exito(entorno, monkeypatch, caso):
    e = entorno
    habilitar_ip_solo_test(e, monkeypatch)
    h = e["headers"] + [("Cookie", "synapdesk_csrf_context_dev=" + generar_secreto().get_secret_value())]
    if caso == "duplicado":
        h += [("X-CSRF-Token", generar_secreto().get_secret_value())] * 2
    elif caso == "malformado":
        h += [("X-CSRF-Token", "corto")]
    elif caso == "persistido":
        h += [("X-CSRF-Token", generar_secreto().get_secret_value())]
        def fallar(*args, **kwargs):
            raise ErrorSeguridad(C.TOKEN_VENCIDO)
        monkeypatch.setattr(e["adaptador"]._login, "validar_contexto", fallar)
    error(e["adaptador"].login(request(e["config"], h), entrada_login()), "CSRF_INVALID", 403)


def test_login_cookie_solo_tras_resultado_confirmado_y_correlacion(entorno, monkeypatch, caplog):
    e = entorno
    habilitar_ip_solo_test(e, monkeypatch)
    ahora = datetime.now(UTC)
    secreto = generar_secreto()
    resultado = LoginConfirmado(Identidad(uuid4(), "persona@example.invalid", "admin"),
        SesionEmitida(uuid4(), ahora + timedelta(hours=8), secreto))
    ids = []
    monkeypatch.setattr(e["adaptador"], "_ahora_cookie", lambda: ahora)
    monkeypatch.setattr(e["adaptador"]._login, "validar_contexto",
        lambda prueba, **kwargs: ids.append(kwargs["request_id"]) or object())
    def autenticar(credenciales, contexto, **kwargs):
        ids.append(kwargs["request_id"])
        assert credenciales.cuenta == "persona@example.invalid"
        return resultado
    monkeypatch.setattr(e["adaptador"]._login, "autenticar", autenticar)
    r = request(e["config"], e["headers"] + [
        ("Cookie", "synapdesk_csrf_context_dev=" + generar_secreto().get_secret_value()),
        ("X-CSRF-Token", generar_secreto().get_secret_value())])
    respuesta = e["adaptador"].login(r, entrada_login())
    assert respuesta.status_code == 200 and ids == [id_peticion(r)] * 2
    cookies = respuesta.headers.getlist("set-cookie")
    assert len(cookies) == 2 and "HttpOnly" in cookies[0] and "SameSite=lax" in cookies[0]
    assert "Path=/" in cookies[0] and "Domain=" not in cookies[0]
    assert "Max-Age=0" in cookies[1]
    assert secreto.get_secret_value() not in respuesta.body.decode() + caplog.text


def test_login_fallo_commit_no_usa_resultado_provisional(entorno, monkeypatch):
    e = entorno
    habilitar_ip_solo_test(e, monkeypatch)
    monkeypatch.setattr(e["adaptador"]._login, "validar_contexto", lambda *a, **k: object())
    def fallar(*args, **kwargs):
        raise ErrorSeguridad(C.TRANSACCION)
    monkeypatch.setattr(e["adaptador"]._login, "autenticar", fallar)
    h = e["headers"] + [("Cookie", "synapdesk_csrf_context_dev=" + generar_secreto().get_secret_value()),
        ("X-CSRF-Token", generar_secreto().get_secret_value())]
    error(e["adaptador"].login(request(e["config"], h), entrada_login()), "SERVICE_UNAVAILABLE", 503)


def test_rechazo_credenciales_uniforme_candidato_ya_documentado(entorno, monkeypatch):
    e = entorno
    habilitar_ip_solo_test(e, monkeypatch)
    monkeypatch.setattr(e["adaptador"]._login, "validar_contexto", lambda *a, **k: object())
    monkeypatch.setattr(e["adaptador"]._login, "autenticar", lambda *a, **k: LoginRechazado(M.CREDENCIALES_INVALIDAS))
    h = e["headers"] + [("Cookie", "synapdesk_csrf_context_dev=" + generar_secreto().get_secret_value()),
        ("X-CSRF-Token", generar_secreto().get_secret_value())]
    error(e["adaptador"].login(request(e["config"], h), entrada_login()), "INVALID_CREDENTIALS", 401)


def test_logout_ausente_con_origin_valido_sin_csrf_ni_bd(entorno):
    e = entorno
    r = e["adaptador"].logout(request(e["config"], e["headers"]), SolicitudLogout())
    assert r.status_code == 204 and not r.body and "set-cookie" not in r.headers
    assert r.headers["cache-control"] == "no-store" and e["motor"].pool.checkedout() == 0


@pytest.mark.parametrize("dto", [SolicitudLogin, SolicitudLogout])
def test_rol_y_name_no_se_aceptan_en_json(dto):
    valores = dict(email="a@b", password=generar_secreto().get_secret_value()) if dto is SolicitudLogin else {}
    with pytest.raises(ValidationError):
        dto(**valores, role="admin", name="No permitido")


def test_rutas_reales_siguen_cerradas(entorno):
    with TestClient(crear_aplicacion(entorno["config"])) as client:
        for metodo, ruta in [("post", "login"), ("get", "me"), ("post", "logout")]:
            assert getattr(client, metodo)("/api/v1/auth/" + ruta).status_code == 404
        r = client.get("/api/v1/auth/csrf", headers={"Origin": ORIGEN})
        assert r.status_code == 503 and "set-cookie" not in r.headers


def test_me_sin_cookie_rechaza_sin_consulta_y_sin_borrado(entorno):
    e = entorno
    error(e["adaptador"].me(request(e["config"], e["headers"], method="GET")),
          "AUTHENTICATION_REQUIRED", 401)
    assert e["motor"].pool.checkedout() == 0


@pytest.mark.parametrize("nombre", ["X-Forwarded-For", "X-Real-IP", "Forwarded", "X-SynapDesk-Client-IP"])
def test_ip_en_cabecera_no_se_convierte_en_ip_verificada(entorno, nombre):
    e = entorno
    error(e["adaptador"].csrf(request(e["config"], e["headers"] + [(nombre, "198.51.100.7")],
        method="GET")), "SERVICE_UNAVAILABLE", 503)
    assert e["motor"].pool.checkedout() == 0


@pytest.mark.parametrize("site,estado", [(None, 403), ("same-origin", 503), ("cross-site", 403)])
def test_bootstrap_sin_origin_conserva_condicion_especifica_y_cierre_ip(entorno, site, estado):
    e = entorno
    h = [e["headers"][0]] + ([("Sec-Fetch-Site", site)] if site else [])
    error(e["adaptador"].csrf(request(e["config"], h, method="GET")),
        "SERVICE_UNAVAILABLE" if estado == 503 else "ORIGIN_INVALID", estado)


def test_422_general_no_filtra_datos_ni_se_confunde_con_401(entorno):
    e = entorno
    app = crear_aplicacion(e["config"])
    @app.post("/ensayo-dto-login")
    def candidato(entrada: SolicitudLogin, request: Request):
        return e["adaptador"].login(request, entrada)
    secreto = generar_secreto().get_secret_value()
    with TestClient(app, base_url="https://localhost") as client:
        r = client.post("/ensayo-dto-login", json=dict(email="a@b", password=secreto,
            role="admin", campo_privado=secreto), headers=dict(e["headers"]))
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert set(r.json()["error"]) == {"code", "message", "details", "requestId"}
    assert secreto not in r.text and "campo_privado" not in r.text
    assert r.headers["cache-control"] == "no-store" and "set-cookie" not in r.headers
