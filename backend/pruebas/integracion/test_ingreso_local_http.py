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

from app.api.cookies_auth import preparar_perfil
from app.configuracion import Configuracion
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
        def obtener(ruta, actor):
            headers = {"Authorization": "Bearer " + servicio.get_secret_value(),
                       "Cookie": "synapdesk_session_dev=" + tickets["referencias"][actor].credencial.get_secret_value()}
            url = urlsplit(ruta)
            request = Request(dict(type="http", method="GET", path=url.path,
                raw_path=url.path.encode(), query_string=url.query.encode(),
                headers=[(k.lower().encode(), v.encode()) for k, v in headers.items()]))
            payload = base64.urlsafe_b64encode(json.dumps(dict(v=1, aud=audiencia, ip="127.0.0.1",
                ts=int(time()), nonce=uuid4().hex, method="GET", path=ruta,
                controls=huella_controles(request)), separators=(",", ":")).encode()).decode().rstrip("=")
            headers["X-SynapDesk-Ingress-Evidence"] = payload + "." + hmac.digest(clave,
                DOMINIO + payload.encode(), "sha256").hex()
            return cliente.get(ruta, headers=headers)
        yield dict(tickets, obtener=obtener)


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
