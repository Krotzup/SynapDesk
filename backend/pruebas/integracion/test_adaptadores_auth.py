"""Candidatos directos con PostgreSQL real; no certifica HTTP de Render."""

import json
from uuid import uuid4

import pytest
from fastapi import Request
from sqlalchemy import delete, event, func, select, text, tuple_
from sqlalchemy.orm import Session as DbSession

from app.aplicacion import crear_aplicacion
from app.api.adaptadores_auth import AdaptadorAuth
from app.api.cookies_auth import preparar_perfil
from app.api.esquemas_auth import SolicitudLogin, SolicitudLogout
from app.api.respuestas_auth import id_peticion
from app.persistencia.modelos import ContextoCsrf, CuotaBootstrapCsrf, EventoAutenticacion, Sesion, TokenCsrf
from app.seguridad.secretos import digest_secreto
from app.seguridad.transacciones import CodigoSeguridad
from pruebas.integracion.test_login import entorno_login
from pruebas.intermediario_auxiliar import ORIGEN, cabeceras, credencial, politica


@pytest.fixture
def http(entorno_login, monkeypatch):
    e = entorno_login
    token = credencial()
    from app.configuracion import Configuracion
    datos = e["config"].model_dump()
    datos.update(auth_intermediario=politica([token]), auth_origenes_permitidos=[ORIGEN])
    config = Configuracion(_env_file=None, **datos)
    perfil = preparar_perfil(config, origen_publico=ORIGEN,
        nombre_sesion="synapdesk_session_dev", nombre_contexto="synapdesk_csrf_context_dev")
    e["adaptador"] = AdaptadorAuth(e["motor"], config, perfil, capacidad_argon2=1, reloj=e["reloj"])
    e["config_http"], e["headers"] = config, list(cabeceras(token).items())
    propias = set()
    def recordar(db, contexto):
        if db.get_bind().pool is e["motor"].pool:
            propias.update((f.ambito, f.identidad) for f in db.new if isinstance(f, CuotaBootstrapCsrf))
    event.listen(DbSession, "after_flush", recordar)
    # Evidencia de IP del fixture interno, nunca extraída de cabeceras.
    monkeypatch.setattr("app.api.adaptadores_auth.obtener_ip_verificada", lambda request: e["ip"])
    try:
        yield e
    finally:
        event.remove(DbSession, "after_flush", recordar)
        with e["motor"].begin() as db:
            assert db.scalar(text("SELECT current_database()")).startswith("synapdesk_auth07_sec01a_")
            db.execute(delete(CuotaBootstrapCsrf).where(
                tuple_(CuotaBootstrapCsrf.ambito, CuotaBootstrapCsrf.identidad).in_(propias)))


def solicitud(e, headers=(), *, method="POST"):
    return Request(dict(type="http", method=method, scheme="https", path="/candidato",
        query_string=b"", server=("localhost", 443), client=("127.0.0.1", 1234),
        app=crear_aplicacion(e["config_http"]),
        headers=[(k.lower().encode(), v.encode()) for k, v in e["headers"] + list(headers)]))


def bootstrap(e):
    r = e["adaptador"].csrf(solicitud(e, method="GET"))
    assert r.status_code == 200
    return r.headers["set-cookie"].split(";", 1)[0], json.loads(r.body)["csrfToken"]


def login(e):
    cookie, token = bootstrap(e)
    request = solicitud(e, [("Cookie", cookie), ("X-CSRF-Token", token)])
    respuesta = e["adaptador"].login(request, SolicitudLogin(
        email=e["usuario"].correo.upper(), password=e["clave"].get_secret_value()))
    assert respuesta.status_code == 200
    return request, respuesta, respuesta.headers.getlist("set-cookie")[0].split(";", 1)[0]


def test_bootstrap_login_me_csrf_logout_postcommit_y_auditoria(http, monkeypatch, caplog):
    e = http
    from app.api import adaptadores_auth as modulo
    original = modulo.emitir_cookie
    vistos = []
    def verificar_commit(response, perfil, tipo, secreto, **kwargs):
        with DbSession(e["motor"]) as db:  # Otra conexión antes de Set-Cookie.
            modelo = Sesion if tipo == "sesion" else ContextoCsrf
            columna = Sesion.digest_credencial if tipo == "sesion" else ContextoCsrf.digest_secreto
            assert db.scalar(select(modelo.id).where(
                columna == digest_secreto(secreto, CodigoSeguridad.SESION_INEXISTENTE))) is not None
        vistos.append(tipo)
        return original(response, perfil, tipo, secreto, **kwargs)
    monkeypatch.setattr(modulo, "emitir_cookie", verificar_commit)
    request_login, respuesta, cookie = login(e)
    assert vistos == ["contexto", "sesion"]
    assert set(json.loads(respuesta.body)["user"]) == {"id", "email", "role"}
    with DbSession(e["motor"]) as db:
        eventos = db.scalars(select(EventoAutenticacion).where(
            EventoAutenticacion.request_id == str(id_peticion(request_login)))).all()
        assert sorted(f.tipo_evento for f in eventos) == ["login", "session_created"]
        s = db.scalar(select(Sesion).where(Sesion.usuario_id == e["usuario"].id))
        estado = (s.ultima_actividad, s.expira_en)
        sesion_id = s.id
    r = e["adaptador"].me(solicitud(e, [("Cookie", cookie)], method="GET"))
    assert r.status_code == 200 and "set-cookie" not in r.headers
    r = e["adaptador"].csrf(solicitud(e, [("Cookie", cookie)], method="GET"))
    assert r.status_code == 200 and "set-cookie" not in r.headers
    token = json.loads(r.body)["csrfToken"]
    request_logout = solicitud(e, [("Cookie", cookie), ("X-CSRF-Token", token)])
    r = e["adaptador"].logout(request_logout, SolicitudLogout())
    assert r.status_code == 204 and not r.body and "Max-Age=0" in r.headers["set-cookie"]
    with DbSession(e["motor"]) as db:
        s = db.get(Sesion, sesion_id)
        assert s.revocada_en is not None and (s.ultima_actividad, s.expira_en) == estado
        assert db.scalar(select(EventoAutenticacion.request_id).where(
            EventoAutenticacion.motivo == "logout")) == str(id_peticion(request_logout))
    # Idempotencia confirmada: el token anterior ya no importa.
    r = e["adaptador"].logout(solicitud(e, [("Cookie", cookie)]), SolicitudLogout())
    assert r.status_code == 204
    assert e["clave"].get_secret_value() not in respuesta.body.decode() + caplog.text


@pytest.mark.parametrize("caso", ["ausente", "duplicado", "otro_contexto"])
def test_logout_valido_exige_csrf_y_no_borra_cookie_al_rechazar(http, caso):
    e = http
    _, _, cookie = login(e)
    h = [("Cookie", cookie)]
    if caso == "duplicado":
        _, t = bootstrap(e)
        h += [("X-CSRF-Token", t)] * 2
    elif caso == "otro_contexto":
        _, t = bootstrap(e)
        h += [("X-CSRF-Token", t)]
    r = e["adaptador"].logout(solicitud(e, h), SolicitudLogout())
    assert r.status_code == 403 and json.loads(r.body)["error"]["code"] == "CSRF_INVALID"
    assert "set-cookie" not in r.headers
    with DbSession(e["motor"]) as db:
        assert db.scalar(select(Sesion.revocada_en)) is None


@pytest.mark.parametrize("operacion", ["csrf", "login", "logout"])
def test_fallo_real_commit_sin_cookie_de_exito(http, operacion):
    e = http
    a = e["adaptador"]
    if operacion == "login":
        cookie, token = bootstrap(e)
        req = solicitud(e, [("Cookie", cookie), ("X-CSRF-Token", token)])
    elif operacion == "logout":
        _, _, cookie = login(e)
        r = a.csrf(solicitud(e, [("Cookie", cookie)], method="GET"))
        token = json.loads(r.body)["csrfToken"]
        req = solicitud(e, [("Cookie", cookie), ("X-CSRF-Token", token)])
    else:
        req = solicitud(e, method="GET")

    def marcar(db, contexto):
        if db.get_bind().pool is not e["motor"].pool:
            return
        for f in db.new:
            if ((operacion == "csrf" and isinstance(f, TokenCsrf))
                    or (operacion == "login" and isinstance(f, Sesion))
                    or (operacion == "logout" and isinstance(f, EventoAutenticacion)
                        and f.tipo_evento == "session_revoked")):
                db.info["fallo_commit_http"] = True

    def fallar(db):
        if db.info.get("fallo_commit_http"):
            db.execute(text("CREATE TEMP TABLE fallo_http(n int UNIQUE DEFERRABLE "
                            "INITIALLY DEFERRED) ON COMMIT DROP"))
            db.execute(text("INSERT INTO fallo_http VALUES (1),(1)"))
    event.listen(DbSession, "after_flush", marcar)
    event.listen(DbSession, "before_commit", fallar)
    try:
        if operacion == "csrf":
            r = a.csrf(req)
        elif operacion == "login":
            r = a.login(req, SolicitudLogin(email=e["usuario"].correo, password=e["clave"].get_secret_value()))
        else:
            r = a.logout(req, SolicitudLogout())
    finally:
        event.remove(DbSession, "after_flush", marcar)
        event.remove(DbSession, "before_commit", fallar)
    assert r.status_code == 503 and "set-cookie" not in r.headers
    assert r.headers["cache-control"] == "no-store"
    with DbSession(e["motor"]) as db:
        if operacion == "csrf":
            assert db.scalar(select(func.count()).select_from(ContextoCsrf)) == 0
        elif operacion == "login":
            assert db.scalar(select(func.count()).select_from(Sesion)) == 0
        else:
            assert db.scalar(select(Sesion.revocada_en)) is None


def test_sesion_presentada_invalida_no_se_recupera_como_anonima(http):
    e = http
    cookie, token = bootstrap(e)
    h = [("Cookie", cookie + "; synapdesk_session_dev=" + credencial().get_secret_value()),
         ("X-CSRF-Token", token)]
    r = e["adaptador"].login(solicitud(e, h), SolicitudLogin(
        email=e["usuario"].correo, password=e["clave"].get_secret_value()))
    assert r.status_code == 401 and "set-cookie" not in r.headers
    with DbSession(e["motor"]) as db:
        assert db.scalar(select(func.count()).select_from(Sesion)) == 0
