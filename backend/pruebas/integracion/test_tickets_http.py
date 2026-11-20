"""Adaptador candidato + PostgreSQL real; invocación interna, sin listener TLS.

La sesión y el token se emiten con los servicios persistentes existentes. Un
scope ASGI controlado no demuestra TLS ni una lectura Next.js de extremo a extremo.
"""

from datetime import timedelta
import json
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session

from app.api.adaptadores_tickets import AdaptadorTickets
from app.api.cookies_auth import preparar_perfil
from app.persistencia.modelos import Sesion, Ticket as TicketORM, Usuario
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.transacciones import transaccion_seguridad
from app.tickets.esquemas import TicketCreate, TicketPagination, TicketStatusUpdate
from pruebas.integracion.test_tickets import consulta_interna, tickets  # noqa: F401
from pruebas.intermediario_auxiliar import ORIGEN, credencial, politica
from pruebas.login_auxiliar import configuracion_login
from pruebas.test_adaptadores_tickets import comprobar_error, solicitud


@pytest.fixture
def candidato_pg(tickets):
    clave = credencial()
    config = configuracion_login(auth_intermediario=politica([clave]), auth_origenes_permitidos=[ORIGEN])
    perfil = preparar_perfil(config, origen_publico=ORIGEN,
        nombre_sesion="synapdesk_session_dev", nombre_contexto="synapdesk_csrf_context_dev")
    return dict(tickets, clave=clave, config=config, perfil=perfil,
                adaptador=AdaptadorTickets(tickets["motor"], config, perfil))


def peticion(e, *, metodo="GET", actor=0, token=None, extras=(), origen=True, sesion=None):
    h = [("Authorization", "Bearer " + e["clave"].get_secret_value()),
         ("Cookie", "synapdesk_session_dev=" + (sesion or e["referencias"][actor].credencial).get_secret_value())]
    if origen:
        h.append(("Origin", ORIGEN))
    if token is not None:
        h.append(("X-CSRF-Token", token.get_secret_value()))
    return solicitud(e, metodo=metodo, headers=h + list(extras))


def emitir(e, actor=0):
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        return ServicioCsrf(db, e["config"]).emitir_token(sesion=e["referencias"][actor].credencial)


def cuerpo(r, estado=200):
    assert r.status_code == estado, r.body
    assert r.headers["cache-control"] == "no-store"
    assert "set-cookie" not in r.headers
    return json.loads(r.body)


@pytest.mark.parametrize("actor", [0, 1], ids=["admin", "agent"])
def test_cinco_adaptadores_con_sesion_y_csrf_persistidos(candidato_pg, actor):
    e = candidato_pg
    token = emitir(e, actor).token
    t = cuerpo(e["adaptador"].crear(peticion(e, metodo="POST", actor=actor, token=token),
        TicketCreate(title="Ticket integrado real", description="Guardado por sesión persistente.")), 201)
    assert t["createdBy"]["id"] == str(e["usuarios"][actor])
    from uuid import UUID
    ticket_id = UUID(t["id"])
    # La otra cuenta puede consultar y modificar, según el alcance global aprobado.
    otro = 1 - actor
    pagina = cuerpo(e["adaptador"].listar(peticion(e, actor=otro, origen=False), TicketPagination(pageSize=1)))
    assert pagina["items"] == [t] and pagina["totalItems"] == 1
    assert cuerpo(e["adaptador"].detalle(peticion(e, actor=otro), ticket_id)) == t
    cambiado = cuerpo(e["adaptador"].actualizar_estado(
        peticion(e, metodo="PATCH", actor=otro, token=emitir(e, otro).token),
        ticket_id, TicketStatusUpdate(status="resolved")))
    assert cambiado["status"] == "resolved" and cambiado["resolvedAt"] is not None
    assert cuerpo(e["adaptador"].resumen(peticion(e, actor=actor))) == {
        "totalTickets": 1, "openTickets": 0, "inProgressTickets": 0,
        "resolvedTickets": 1, "closedTickets": 0}
    leido = consulta_interna(e, lambda repo: repo.detalle(ticket_id)).model_dump(mode="json")
    assert leido == cambiado  # Otra Session/conexión tras commit.


@pytest.mark.parametrize("actor", [0, 1], ids=["admin", "agent"])
@pytest.mark.parametrize("cantidad", [0, 3], ids=["vacio", "con_datos"])
@pytest.mark.parametrize("page_size", [1, 100])
@pytest.mark.parametrize("posicion", ["bigint_anterior", "bigint_maximo", "bigint_excedido", "enorme"])
def test_pagina_extrema_conserva_contrato_y_snapshot(candidato_pg, actor, cantidad, page_size, posicion):
    e = candidato_pg
    for n in range(cantidad):
        e["servicio"].crear(e["referencias"][0], TicketCreate(
            title=f"Ticket extremo {n}", description="Datos para paginación extrema."))
    maximo = 2**63 - 1
    paginas = {"bigint_anterior": maximo // page_size,
               "bigint_maximo": maximo // page_size + 1,
               "bigint_excedido": maximo // page_size + 2,
               "enorme": 10**100}
    page = paginas[posicion]
    consultas = []

    def registrar(_, __, statement, parameters, *___):
        if "total_tickets" in statement:
            consultas.append((statement, parameters))

    event.listen(e["motor"], "before_cursor_execute", registrar)
    try:
        respuesta = cuerpo(e["adaptador"].listar(peticion(e, actor=actor),
            TicketPagination(page=page, pageSize=page_size)))
    finally:
        event.remove(e["motor"], "before_cursor_execute", registrar)
    assert respuesta == {"items": [], "page": page, "pageSize": page_size,
        "totalItems": cantidad, "totalPages": (cantidad + page_size - 1) // page_size}
    assert len(consultas) == 1  # Página y total comparten una sentencia/snapshot.
    sql, parametros = consultas[0]
    assert all(type(v) is not int or v <= maximo for v in parametros.values())
    if (page - 1) * page_size > maximo:
        assert "OFFSET" not in sql.upper()


@pytest.mark.parametrize("actor", [0, 1], ids=["admin", "agent"])
def test_pagina_en_rango_e_inmediatamente_fuera_con_totales(candidato_pg, actor):
    e = candidato_pg
    creados = [e["servicio"].crear(e["referencias"][0], TicketCreate(
        title=f"Ticket de página {n}", description="Listado contractual de prueba.")) for n in range(3)]
    for page, esperado in ((2, [creados[0].model_dump(mode="json")]), (3, [])):
        respuesta = cuerpo(e["adaptador"].listar(peticion(e, actor=actor),
            TicketPagination(page=page, pageSize=2)))
        assert respuesta == {"items": esperado, "page": page, "pageSize": 2,
            "totalItems": 3, "totalPages": 2}


@pytest.mark.parametrize("caso", ["ausente", "duplicado", "otra_sesion", "desconocido", "vencido"])
def test_csrf_invalido_no_escribe(candidato_pg, caso):
    e = candidato_pg
    emitido = emitir(e, 1 if caso == "otra_sesion" else 0)
    token = None if caso == "ausente" else credencial() if caso == "desconocido" else emitido.token
    extras = [("X-CSRF-Token", token.get_secret_value())] if caso == "duplicado" else ()
    adaptador = e["adaptador"]
    if caso == "vencido":
        adaptador = AdaptadorTickets(e["motor"], e["config"], e["perfil"],
            reloj=lambda _: emitido.expira_en + timedelta(seconds=1))
    r = adaptador.crear(peticion(e, metodo="POST", token=token, extras=extras),
        TicketCreate(title="No debe guardarse", description="Token ausente o no válido."))
    comprobar_error(r, 403, "CSRF_INVALID")
    assert consulta_interna(e, lambda repo: repo.resumen()).totalTickets == 0


def test_csrf_vence_durante_escritura_revierte_sin_reintento(candidato_pg):
    e = candidato_pg
    emitido = emitir(e)
    with e["motor"].connect() as db:
        ahora = [db.scalar(select(func.clock_timestamp()))]

    def avanzar(db, _):
        if db.get_bind().pool is e["motor"].pool and any(type(f) is TicketORM for f in db.new):
            ahora[0] = emitido.expira_en + timedelta(seconds=1)

    adaptador = AdaptadorTickets(e["motor"], e["config"], e["perfil"], reloj=lambda _: ahora[0])
    event.listen(Session, "after_flush", avanzar)
    try:
        r = adaptador.crear(peticion(e, metodo="POST", token=emitido.token),
            TicketCreate(title="Rollback por CSRF", description="Vence después del INSERT, antes del commit."))
    finally:
        event.remove(Session, "after_flush", avanzar)
    comprobar_error(r, 503, "SERVICE_UNAVAILABLE")
    assert consulta_interna(e, lambda repo: repo.resumen()).totalTickets == 0


@pytest.mark.parametrize("caso", ["inactivo", "revocada", "credencial_servicio"])
@pytest.mark.parametrize("page", [1, 10**100])
def test_lectura_exige_usuario_activo_y_sesion_real(candidato_pg, caso, page):
    e = candidato_pg
    with e["motor"].begin() as db:
        if caso == "inactivo":
            db.execute(update(Usuario).where(Usuario.id == e["usuarios"][0]).values(activo=False))
        elif caso == "revocada":
            db.execute(update(Sesion).where(Sesion.usuario_id == e["usuarios"][0]).values(
                revocada_en=func.clock_timestamp(), motivo_revocacion="individual"))
    r = e["adaptador"].listar(peticion(e, sesion=e["clave"] if caso == "credencial_servicio" else None),
        TicketPagination(page=page, pageSize=100))
    comprobar_error(r, 401, "AUTHENTICATION_REQUIRED")


def test_errores_tipados_saneados_y_requestid_del_servidor(candidato_pg):
    e = candidato_pg
    r = e["adaptador"].detalle(peticion(e, extras=[("X-Request-ID", "dato-del-cliente")]), uuid4())
    comprobar_error(r, 404, "TICKET_NOT_FOUND")
    assert json.loads(r.body)["error"]["requestId"] != "dato-del-cliente"
    r = e["adaptador"].crear(peticion(e, metodo="POST", token=emitir(e).token),
        TicketCreate.model_construct(title="x", description="contenido privado"))
    comprobar_error(r, 422, "VALIDATION_ERROR")
    assert "contenido privado" not in r.body.decode()
    assert consulta_interna(e, lambda repo: repo.resumen()).totalTickets == 0
