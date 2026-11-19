"""Rutas locales con SQL real; scope TLS controlado, separado del ensayo Edge/TLS."""

import base64
import hmac
import json
import secrets
from time import time
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import SecretBytes
import pytest
from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from app.api.cookies_auth import preparar_perfil
from app.configuracion import Configuracion
from app.persistencia.modelos import EventoAutenticacion, Sesion
from app.tickets.esquemas import TicketCreate
from herramientas.ingreso_local.aplicacion import crear_aplicacion_local
from herramientas.ingreso_local.evidencia import DOMINIO, VerificadorIngresoLocal, huella_controles
from pruebas.integracion.test_tickets import tickets  # noqa: F401
from pruebas.intermediario_auxiliar import ORIGEN, credencial, politica
from pruebas.login_auxiliar import configuracion_login


@pytest.fixture
def http_local(tickets, configuracion_bd_test):
    datos = configuracion_bd_test.model_dump()
    datos.update({k: v for k, v in configuracion_login().model_dump().items() if k.startswith("auth_")})
    servicio, clave, audiencia = credencial(), secrets.token_bytes(32), uuid4().hex
    datos.update(auth_intermediario=politica([servicio]), auth_origenes_permitidos=[ORIGEN],
                 auth_proxies_autorizados=["127.0.0.1/32"])
    config = Configuracion(_env_file=None, **datos)
    perfil = preparar_perfil(config, origen_publico=ORIGEN,
        nombre_sesion="synapdesk_session_dev", nombre_contexto="synapdesk_csrf_context_dev")
    verificador = VerificadorIngresoLocal(config, SecretBytes(clave), audiencia,
        ventana_segundos=30, capacidad_nonces=64)
    app = crear_aplicacion_local(config, tickets["motor"], perfil, verificador,
        capacidad_argon2=1, max_cuerpo_bytes=65536)
    with TestClient(app, base_url="https://localhost", client=("127.0.0.1", 12345)) as cliente:
        def solicitar(ruta, actor, metodo="GET", cuerpo=None, token=None, origen=ORIGEN, evidencia=True):
            headers = {"Authorization": "Bearer " + servicio.get_secret_value(),
                       "Origin": origen,
                       "Cookie": "synapdesk_session_dev=" + tickets["referencias"][actor].credencial.get_secret_value()}
            if token is not None:
                headers["X-CSRF-Token"] = token
            url = urlsplit(ruta)
            request = Request(dict(type="http", method=metodo, path=url.path,
                raw_path=url.path.encode(), query_string=url.query.encode(),
                headers=[(k.lower().encode(), v.encode()) for k, v in headers.items()]))
            payload = base64.urlsafe_b64encode(json.dumps(dict(v=1, aud=audiencia, ip="127.0.0.1",
                ts=int(time()), nonce=uuid4().hex, method=metodo, path=ruta,
                controls=huella_controles(request)), separators=(",", ":")).encode()).decode().rstrip("=")
            headers["X-SynapDesk-Ingress-Evidence"] = payload + "." + hmac.digest(clave,
                DOMINIO + payload.encode(), "sha256").hex()
            if not evidencia:
                headers.pop("X-SynapDesk-Ingress-Evidence")
            return cliente.request(metodo, ruta, headers=headers, json=cuerpo)
        yield dict(tickets, obtener=solicitar, solicitar=solicitar)


@pytest.mark.parametrize("actor", [0, 1], ids=["admin", "agent"])
@pytest.mark.parametrize("cantidad", [0, 3], ids=["vacio", "con_datos"])
def test_ruta_acepta_pagina_enorme_sin_truncar_ni_desbordar(http_local, actor, cantidad):
    e = http_local
    for n in range(cantidad):
        e["servicio"].crear(e["referencias"][actor], TicketCreate(
            title=f"Ticket HTTP {n}", description="Persistencia real para la ruta de listado."))
    page = 10**100
    respuesta = e["obtener"](f"/api/v1/tickets?page={page}&pageSize=100", actor)
    assert respuesta.status_code == 200
    assert respuesta.headers["cache-control"] == "no-store"
    assert respuesta.json() == dict(items=[], page=page, pageSize=100,
        totalItems=cantidad, totalPages=int(cantidad > 0))
    resumen = e["obtener"]("/api/v1/metrics/summary", actor)
    assert resumen.status_code == 200 and resumen.json()["totalTickets"] == cantidad


@pytest.mark.parametrize("query", ["page=1&page=2", "page=1e3", "pageSize=101", "status=open"])
def test_ruta_no_oculta_parametros_duplicados_invalidos_o_no_soportados(http_local, query):
    respuesta = http_local["obtener"]("/api/v1/tickets?" + query, 0)
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("actor", [0, 1], ids=["admin", "agent"])
def test_logout_local_reutiliza_csrf_origin_procedencia_y_revocacion_sql(logout_local, actor):
    e = logout_local
    pedir = e["solicitar"]
    csrf = pedir("/api/v1/auth/csrf", actor)
    assert csrf.status_code == 200
    token = csrf.json()["csrfToken"]
    for cambios, esperado in ((dict(token="invalido"), 403),
                              (dict(origen="https://ajeno.invalid", token=token), 403),
                              (dict(evidencia=False, token=token), 503),
                              (dict(cuerpo={"otro": True}, token=token), 422)):
        argumentos = dict(cuerpo={}) | cambios
        respuesta = pedir("/api/v1/auth/logout", actor, "POST", **argumentos)
        assert respuesta.status_code == esperado
        assert "set-cookie" not in respuesta.headers
        assert pedir("/api/v1/auth/me", actor).status_code == 200
    respuesta = pedir("/api/v1/auth/logout", actor, "POST", cuerpo={}, token=token)
    assert respuesta.status_code == 204 and not respuesta.content
    assert respuesta.headers["cache-control"] == "no-store"
    assert "Max-Age=0" in respuesta.headers["set-cookie"]
    with Session(e["motor"]) as db:
        sesion = db.scalar(select(Sesion).where(Sesion.usuario_id == e["usuarios"][actor]))
        assert sesion.revocada_en is not None
    assert pedir("/api/v1/auth/me", actor).status_code == 401
    assert pedir("/api/v1/tickets", actor).status_code == 401
    assert pedir("/api/v1/auth/logout", actor, "POST", cuerpo={}).status_code == 204


@pytest.fixture
def logout_local(http_local):
    """Retira sólo las auditorías creadas por este caso en su motor testing propio."""
    e = http_local
    propios = set()

    def recordar(db, _):
        if db.get_bind().pool is e["motor"].pool:
            propios.update(fila.id for fila in db.new
                if type(fila) is EventoAutenticacion and fila.id is not None)

    event.listen(Session, "after_flush", recordar)
    try:
        yield e
    finally:
        event.remove(Session, "after_flush", recordar)
        with e["motor"].begin() as db:
            db.execute(delete(EventoAutenticacion).where(EventoAutenticacion.id.in_(propios)))
