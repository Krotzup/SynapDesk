"""Frontera del adaptador candidato, sin certificar transporte ASGI como TLS."""

import json
from uuid import UUID, uuid4

from fastapi import Request
import pytest
from sqlalchemy import create_engine

from app.api.adaptadores_tickets import AdaptadorTickets
from app.api.cookies_auth import preparar_perfil
from app.aplicacion import crear_aplicacion
from app.tickets.esquemas import TicketCreate, TicketStatusUpdate
from pruebas.intermediario_auxiliar import ORIGEN, cabeceras, configuracion, credencial


@pytest.fixture
def candidato():
    clave = credencial()
    config = configuracion([clave])
    perfil = preparar_perfil(config, origen_publico=ORIGEN,
        nombre_sesion="synapdesk_session_dev", nombre_contexto="synapdesk_csrf_context_dev")
    motor = create_engine("postgresql+psycopg://", hide_parameters=True)
    try:
        yield dict(config=config, clave=clave, adaptador=AdaptadorTickets(motor, config, perfil))
    finally:
        motor.dispose()


def solicitud(e, *, metodo="GET", esquema="https", headers=None):
    valores = list(cabeceras(e["clave"]).items()) if headers is None else headers
    return Request(dict(type="http", method=metodo, scheme=esquema, path="/candidato-tickets",
        query_string=b"", server=("localhost", 443), client=("127.0.0.1", 1234),
        app=crear_aplicacion(e["config"]),
        headers=[(k.lower().encode("ascii"), v.encode("latin-1")) for k, v in valores]))


def comprobar_error(respuesta, estado, codigo):
    assert respuesta.status_code == estado
    assert respuesta.headers["cache-control"] == "no-store"
    assert "set-cookie" not in respuesta.headers
    error = json.loads(respuesta.body)["error"]
    assert set(error) == {"code", "message", "details", "requestId"}
    assert error["code"] == codigo
    UUID(error["requestId"])


@pytest.mark.parametrize("operacion", ["crear", "listar", "detalle", "actualizar_estado", "resumen"])
def test_intermediario_sin_sesion_no_es_usuario(candidato, operacion):
    e = candidato
    parametros = {"crear": (TicketCreate(title="Ticket válido", description="Descripción válida."),),
        "listar": (), "detalle": (uuid4(),), "resumen": (),
        "actualizar_estado": (uuid4(), TicketStatusUpdate(status="closed"))}
    metodo = "POST" if operacion == "crear" else "PATCH" if operacion == "actualizar_estado" else "GET"
    r = getattr(e["adaptador"], operacion)(solicitud(e, metodo=metodo), *parametros[operacion])
    comprobar_error(r, 401, "AUTHENTICATION_REQUIRED")


@pytest.mark.parametrize("caso", ["ausente", "incorrecta", "duplicada", "http", "forwarded"])
def test_lectura_exige_canal_sec01b(candidato, caso):
    e = candidato
    headers = list(cabeceras(e["clave"]).items())
    if caso == "ausente":
        headers = []
    elif caso == "incorrecta":
        headers = list(cabeceras(credencial()).items())
    elif caso == "duplicada":
        headers.append(headers[0])
    elif caso == "forwarded":
        headers.append(("X-Forwarded-Proto", "https"))
    r = e["adaptador"].listar(solicitud(e, headers=headers, esquema="http" if caso == "http" else "https"))
    comprobar_error(r, 503, "SERVICE_UNAVAILABLE")


@pytest.mark.parametrize("headers", [[], [("Origin", "null")], [("Origin", "https://otro.invalid")],
    [("Origin", ORIGEN), ("Origin", ORIGEN)]])
def test_origin_mutacion_antes_de_efectos(candidato, headers):
    e = candidato
    h = [("Authorization", "Bearer " + e["clave"].get_secret_value())] + headers
    r = e["adaptador"].crear(solicitud(e, metodo="POST", headers=h),
        TicketCreate(title="Ticket válido", description="Descripción válida."))
    comprobar_error(r, 403, "ORIGIN_INVALID")


@pytest.mark.parametrize("cookie", ["synapdesk_session_dev=a; synapdesk_session_dev=a",
    "synapdesk_session_dev=abc\u00a0", "__Host-synapdesk_session=abc"])
def test_cookies_no_se_reparan(candidato, cookie):
    e = candidato
    h = list(cabeceras(e["clave"]).items()) + [("Cookie", cookie)]
    # CookieAmbigua conserva la clasificación saneada vigente, pendiente C03.
    comprobar_error(e["adaptador"].listar(solicitud(e, headers=h)), 500, "INTERNAL_ERROR")


def test_no_registra_rutas_ni_acepta_rol_o_uuid_como_usuario(candidato):
    e = candidato
    h = list(cabeceras(e["clave"]).items()) + [("X-Role", "admin"), ("X-User-ID", str(uuid4()))]
    comprobar_error(e["adaptador"].resumen(solicitud(e, headers=h)), 401, "AUTHENTICATION_REQUIRED")
    # La búsqueda de #32 ya está integrada; los adaptadores no publican rutas de tickets.
    assert set(crear_aplicacion(e["config"]).openapi()["paths"]) == {
        "/api/v1/health", "/api/v1/ready", "/api/v1/auth/csrf", "/api/v1/search",
        "/api/v1/tickets/{ticket_id}/recommendations",
        "/api/v1/tickets/{ticket_id}/prediction", "/api/v1/documents", "/api/v1/documents/{document_id}",
        "/api/v1/recommendations/{recommendation_id}",
        "/api/v1/recommendations/{recommendation_id}/reviews"}
