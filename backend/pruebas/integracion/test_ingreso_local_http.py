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
from sqlalchemy import delete, event, select, update
from sqlalchemy.orm import Session

from app.api.cookies_auth import preparar_perfil
from app.configuracion import Configuracion
from app.persistencia.modelos import (
    ContextoCsrf, EventoAutenticacion, Sesion, Ticket as TicketORM, TokenCsrf, Usuario,
)
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
                 auth_proxies_autorizados=["127.0.0.1/32"], search_enabled=True, auth_cookie_profile="local",
                 application_public_origin=ORIGEN)
    config = Configuracion(_env_file=None, **datos)
    perfil = preparar_perfil(config, origen_publico=ORIGEN,
        nombre_sesion="synapdesk_session_dev", nombre_contexto="synapdesk_csrf_context_dev")
    verificador = VerificadorIngresoLocal(config, SecretBytes(clave), audiencia,
        ventana_segundos=30, capacidad_nonces=64)
    app = crear_aplicacion_local(config, tickets["motor"], perfil, verificador,
        capacidad_argon2=1, max_cuerpo_bytes=65536)
    with TestClient(app, base_url="https://localhost", client=("127.0.0.1", 12345)) as cliente:
        def solicitar(ruta, actor, metodo="GET", cuerpo=None, token=None, origen=ORIGEN, evidencia=True,
                      canal=True, sesion=True):
            headers = {"Authorization": "Bearer " + servicio.get_secret_value(),
                       "Origin": origen,
                       "Cookie": "synapdesk_session_dev=" + tickets["referencias"][actor].credencial.get_secret_value()}
            if not canal:
                headers["Authorization"] = "Bearer credencial-invalida-de-prueba"
            if not sesion:
                # Evitar que TestClient añada su cookie jar después de firmar el sello.
                headers["Cookie"] = ""
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
        yield dict(tickets, obtener=solicitar, solicitar=solicitar, app=app, config=config)


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


@pytest.mark.parametrize("query", ["page=1&page=2", "page=1e3", "pageSize=101", "status=invalid"])
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


@pytest.mark.parametrize("actor", [0, 1], ids=["admin", "agent"])
def test_logout_inactivo_solo_revoca_sesion_verificable_sin_mutaciones_ajenas(logout_local, actor):
    e = logout_local
    pedir = e["solicitar"]
    otro = 1 - actor
    tokens = [pedir("/api/v1/auth/csrf", n).json()["csrfToken"] for n in (0, 1)]
    existente = e["servicio"].crear(e["referencias"][actor], TicketCreate(
        title="Ticket protegido de cuenta inactiva", description="Debe persistir sin modificación."))

    def filas_sql(modelo):
        with e["motor"].connect() as db:
            return db.execute(select(modelo.__table__).order_by(modelo.id)).all()

    tablas = (TicketORM, Sesion, ContextoCsrf, TokenCsrf)
    antes = {m: filas_sql(m) for m in tablas}
    sesion_ajena_id = next(s.id for s in antes[Sesion] if s.usuario_id == e["usuarios"][otro])
    with e["motor"].begin() as db:
        db.execute(update(Usuario).where(Usuario.id == e["usuarios"][actor]).values(activo=False))
    for ruta, metodo, cuerpo in (
        ("/api/v1/auth/me", "GET", None),
        ("/api/v1/auth/csrf", "GET", None),
        ("/api/v1/tickets", "GET", None),
        (f"/api/v1/tickets/{existente.id}", "GET", None),
        ("/api/v1/metrics/summary", "GET", None),
        ("/api/v1/tickets", "POST", dict(title="Ticket prohibido", description="No debe insertarse.")),
        (f"/api/v1/tickets/{existente.id}", "PATCH", dict(status="closed")),
        ("/api/v1/auth/login", "POST", dict(email="inactivo@example.invalid", password="no-es-credencial-real")),
    ):
        respuesta = pedir(ruta, actor, metodo, cuerpo=cuerpo, token=tokens[actor])
        assert respuesta.status_code == 401
        assert "set-cookie" not in respuesta.headers
    assert {m: filas_sql(m) for m in tablas} == antes

    for cambios, esperado in (
        (dict(token=None), 403),
        (dict(token="invalido"), 403),
        (dict(token=tokens[otro]), 403),
        (dict(origen="https://ajeno.invalid"), 403),
        (dict(evidencia=False), 503),
        (dict(cuerpo={"sesion_id": str(sesion_ajena_id)}), 422),
    ):
        argumentos = dict(cuerpo={}, token=tokens[actor]) | cambios
        respuesta = pedir("/api/v1/auth/logout", actor, "POST", **argumentos)
        assert respuesta.status_code == esperado
        assert "set-cookie" not in respuesta.headers
        assert {m: filas_sql(m) for m in tablas} == antes

    respuesta = pedir("/api/v1/auth/logout", actor, "POST", cuerpo={}, token=tokens[actor])
    assert respuesta.status_code == 204 and not respuesta.content
    assert respuesta.headers["cache-control"] == "no-store"
    assert "Max-Age=0" in respuesta.headers["set-cookie"]
    with Session(e["motor"]) as db:
        usuario = db.get(Usuario, e["usuarios"][actor])
        assert usuario.activo is False and usuario.rol == ("admin" if actor == 0 else "agent")
        propia = db.scalar(select(Sesion).where(Sesion.usuario_id == usuario.id))
        assert propia.revocada_en is not None
        contexto = db.scalar(select(ContextoCsrf).where(ContextoCsrf.sesion_id == propia.id))
        assert contexto.revocado_en is not None
        assert all(t.invalidado_en is not None for t in db.scalars(
            select(TokenCsrf).where(TokenCsrf.contexto_id == contexto.id)))
        ajena = db.scalar(select(Sesion).where(Sesion.usuario_id == e["usuarios"][otro]))
        assert ajena.revocada_en is None
        contexto_ajeno = db.scalar(select(ContextoCsrf).where(ContextoCsrf.sesion_id == ajena.id))
        assert contexto_ajeno.revocado_en is None
        assert all(t.invalidado_en is None for t in db.scalars(
            select(TokenCsrf).where(TokenCsrf.contexto_id == contexto_ajeno.id)))
        assert propia.ultima_actividad == next(f.ultima_actividad for f in antes[Sesion] if f.id == propia.id)
    assert filas_sql(TicketORM) == antes[TicketORM]
    assert all(len(filas_sql(m)) == len(antes[m]) for m in tablas)
    assert pedir("/api/v1/auth/me", actor).status_code == 401
    assert pedir("/api/v1/tickets", actor).status_code == 401
    assert pedir("/api/v1/auth/logout", actor, "POST", cuerpo={}).status_code == 204
    assert pedir("/api/v1/auth/me", otro).status_code == 200


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


@pytest.mark.parametrize("actor", [0, 1], ids=["admin", "agent"])
@pytest.mark.parametrize("metodo,cuerpo,campo", [
    ("POST", {"title": "x", "description": "Descripción válida de prueba."}, "title"),
    ("POST", {"title": "Ticket válido", "description": "x"}, "description"),
    ("PATCH", {"status": "estado_invalido"}, "status"),
    ("POST", {"title": "Ticket válido", "description": "Descripción válida de prueba.",
              "campo_no_previsto": True}, None),
    ("PATCH", {"status": "closed", "campo_no_previsto": True}, None),
], ids=["titulo", "descripcion", "estado", "extra_creacion", "extra_actualizacion"])
def test_escritura_invalida_detalla_campos_conocidos_sin_mutar_sql(
        logout_local, actor, metodo, cuerpo, campo):
    e = logout_local
    existente = e["servicio"].crear(e["referencias"][actor], TicketCreate(
        title="Ticket que debe conservarse", description="Estado y contenido persistentes de prueba."))
    csrf = e["solicitar"]("/api/v1/auth/csrf", actor)
    assert csrf.status_code == 200
    ruta = "/api/v1/tickets" + (f"/{existente.id}" if metodo == "PATCH" else "")

    def filas_sql():
        with e["motor"].connect() as db:
            return db.execute(select(TicketORM.__table__).order_by(TicketORM.id)).all()

    antes = filas_sql()
    respuesta = e["solicitar"](ruta, actor, metodo, cuerpo=cuerpo, token=csrf.json()["csrfToken"])
    assert respuesta.status_code == 422
    error = respuesta.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Revisa los campos de la solicitud."
    assert error["requestId"]
    assert respuesta.headers["cache-control"] == "no-store"
    assert "set-cookie" not in respuesta.headers
    assert filas_sql() == antes
    if campo is None:
        # PR #51 sigue abierto: no publicar nombres adicionales no contratados.
        assert error["details"] in (None, [])
    else:
        assert error["details"] == [dict(
            field=campo, message="El campo no tiene un valor válido.")]


@pytest.mark.parametrize("ruta", ["/api/v1/documents", "/api/v1/documents/11111111-1111-4111-8111-111111111111",
    "/api/v1/tickets/11111111-1111-4111-8111-111111111111/prediction"])
@pytest.mark.parametrize("metodo", ["GET", "POST", "DELETE"])
def test_asistencia_exige_sello_antes_de_ruta_o_ml(http_local, ruta, metodo):
    response = http_local["solicitar"](ruta, 0, metodo=metodo, evidencia=False)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.parametrize("ruta,modulo", [
    ("/api/v1/documents", "app.api.documentos"),
    ("/api/v1/tickets/11111111-1111-4111-8111-111111111111/prediction", "app.api.predicciones")])
def test_sello_valido_llega_a_autorizacion_de_asistencia(http_local, ruta, modulo):
    from unittest.mock import patch
    from app.recuperacion.servicio import ErrorRecuperacion
    with patch(modulo + ".identidad_aplicacion", side_effect=ErrorRecuperacion("FORBIDDEN", "Prueba de frontera", 403)) as identidad:
        response = http_local["solicitar"](ruta, 0)
    assert response.status_code == 403
    identidad.assert_called_once()


@pytest.mark.parametrize("actor", [0, 1])
def test_busqueda_sesion_csrf_e_ingreso_reales(http_local, actor):
    from app.seguridad.csrf import ServicioCsrf
    from app.seguridad.transacciones import transaccion_seguridad
    from herramientas.ingreso_local.rag_ensayo import RecuperacionSintetica
    e = http_local
    e["app"].state.recuperacion = RecuperacionSintetica()
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        token = ServicioCsrf(db, e["config"]).emitir_token(sesion=e["referencias"][actor].credencial).token.get_secret_value()
    def search(**kwargs):
        return e["solicitar"]("/api/v1/search", actor, metodo="POST", cuerpo={"query": "Consultar DNS", "limit": 3}, **kwargs)
    assert search(token=token, evidencia=False).status_code == 503
    assert search(token=token, origen="https://ajeno.invalid").status_code == 403
    assert search(token="invalido").status_code == 403
    result = search(token=token)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "results" and result.json()["items"]
    assert result.headers["cache-control"] == "no-store"
    e["app"].state.recuperacion = None
    assert search(token=token).json()["error"]["code"] == "SEARCH_UNAVAILABLE"
    with e["motor"].begin() as db:
        from sqlalchemy import func
        db.execute(update(Sesion).where(Sesion.usuario_id == e["usuarios"][actor]).values(revocada_en=func.clock_timestamp()))
    assert search(token=token).status_code == 401


@pytest.mark.parametrize("actor", [0, 1], ids=["admin", "agent"])
@pytest.mark.parametrize("metodo,ruta", [
    ("GET", "/api/v1/documents"),
    ("GET", "/api/v1/tickets/11111111-1111-4111-8111-111111111111/prediction"),
    ("POST", "/api/v1/tickets/11111111-1111-4111-8111-111111111111/prediction"),
    ("POST", "/api/v1/documents"),
    ("DELETE", "/api/v1/documents/11111111-1111-4111-8111-111111111111"),
])
def test_asistencia_conciliada_conserva_fronteras_reales(http_local, actor, metodo, ruta):
    from app.seguridad.csrf import ServicioCsrf
    from app.seguridad.transacciones import transaccion_seguridad
    e = http_local
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        token = ServicioCsrf(db, e["config"]).emitir_token(sesion=e["referencias"][actor].credencial).token.get_secret_value()
    def pedir(**kwargs):
        return e["solicitar"](ruta, actor, metodo=metodo, cuerpo={} if metodo == "POST" else None,
                              **(dict(token=token) | kwargs))
    assert pedir(evidencia=False).status_code == 503
    assert pedir(canal=False).status_code == 503
    assert pedir(origen="https://ajeno.invalid").status_code == 403
    assert pedir(sesion=False).status_code == 401
    if metodo != "GET":
        assert pedir(token="invalido").status_code == 403
    if actor == 1 and ruta.startswith("/api/v1/documents") and metodo != "GET":
        assert pedir().status_code == 403  # agente no administra documentos
    with e["motor"].begin() as db:
        from sqlalchemy import func
        db.execute(update(Sesion).where(Sesion.usuario_id == e["usuarios"][actor]).values(revocada_en=func.clock_timestamp()))
    assert pedir().status_code == 401
