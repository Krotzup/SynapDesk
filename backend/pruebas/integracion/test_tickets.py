"""Persistencia y concurrencia reales, solo en base temporal propia de CI.

No se activa con una base de desarrollo: exige las guardas del arnés vigente.
Las sesiones de fixture usan las primitivas internas existentes, no identidades
proporcionadas al servicio ni autenticación de producción simulada.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import re
from threading import Barrier, Event, Lock
from time import monotonic, sleep
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, event, func, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import ContextoCsrf, Sesion, Ticket as TicketORM, TokenCsrf, Usuario
from app.seguridad.operaciones_sesion import ReferenciaSesion
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad, transaccion_seguridad
from app.tickets.esquemas import TicketCreate, TicketPagination, TicketStatusUpdate
from app.tickets.repositorio import CodigoTickets, ErrorTickets, RepositorioTickets
from app.tickets.servicio import OperacionTicket, ServicioTickets


@pytest.fixture
def tickets(configuracion_bd_test):
    config = configuracion_bd_test
    assert config.postgres_host in {"localhost", "127.0.0.1", "::1"}
    assert config.postgres_port == 5433
    assert re.fullmatch(r"synapdesk_auth07_sec01a_[a-f0-9]{32}", config.postgres_db)
    motor = crear_motor_bd(config)
    ids = {TicketORM: set(), TokenCsrf: set(), ContextoCsrf: set(), Sesion: set(), Usuario: set()}
    candado = Lock()

    def recordar(db, _):
        if db.get_bind().pool is motor.pool:
            with candado:
                for fila in db.new:
                    if type(fila) in ids and fila.id is not None:
                        ids[type(fila)].add(fila.id)

    event.listen(Session, "after_flush", recordar)
    try:
        with motor.connect() as db:
            assert db.execute(text("SELECT current_database(), session_user, current_user")).one() == (
                config.postgres_db, config.postgres_user, config.postgres_user)
            assert 170000 <= int(db.scalar(text("SHOW server_version_num"))) < 180000
            assert db.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0006_user_created"
        referencias = []
        usuarios = []
        for rol in ("admin", "agent"):
            with Session(motor) as db, transaccion_seguridad(db):
                usuario = Usuario(nombre="Prueba MVP01", correo=f"mvp01-{uuid4()}@example.invalid",
                    hash_contrasena="fixture-sin-credencial-de-login", rol=rol, activo=True)
                db.add(usuario)
                db.flush()
                usuarios.append(usuario.id)
                emitida = ServicioSesiones(db).crear(usuario.id)
                referencias.append(ReferenciaSesion(emitida.credencial))
        yield dict(motor=motor, usuarios=usuarios, referencias=referencias,
                   servicio=ServicioTickets(motor), ids=ids)
    finally:
        event.remove(Session, "after_flush", recordar)
        try:
            with motor.begin() as db:
                assert db.scalar(text("SELECT current_database()")) == config.postgres_db
                for modelo in (TicketORM, TokenCsrf, ContextoCsrf, Sesion, Usuario):
                    db.execute(delete(modelo).where(modelo.id.in_(ids[modelo])))
        finally:
            motor.dispose()


def crear(e, titulo="Ticket persistente", actor=0):
    return e["servicio"].crear(e["referencias"][actor],
        TicketCreate(title=titulo, description="Descripción persistente de prueba."))


def consulta_interna(e, operacion):
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        resultado = operacion(RepositorioTickets(db))
    return resultado


def test_crear_confirmado_y_detalle_desde_otra_conexion(tickets):
    e = tickets
    ticket = crear(e)
    leido = consulta_interna(e, lambda repo: repo.detalle(ticket.id))
    assert leido == ticket
    assert (leido.status, leido.priority, leido.category, leido.area,
            leido.assignedTo, leido.resolvedAt) == ("open", "medium", None, None, None, None)
    assert leido.createdBy.id == e["usuarios"][0]
    assert leido.createdBy.role == "admin"
    json = leido.model_dump(mode="json")
    assert set(json) == {"id", "title", "description", "status", "priority", "category", "area",
        "createdBy", "assignedTo", "createdAt", "updatedAt", "resolvedAt"}
    assert set(json["createdBy"]) == {"id", "name", "email", "role", "isActive", "createdAt", "updatedAt"}
    assert "hash_contrasena" not in str(json) and "credencial" not in str(json)


def test_agente_puede_crear_sin_id_de_creador_en_solicitud(tickets):
    ticket = crear(tickets, actor=1)
    assert ticket.createdBy.id == tickets["usuarios"][1]


def test_entrada_invalida_y_model_construct_no_insertan(tickets):
    for datos in ({"title": "a", "description": "Inválida"},
                  {"title": "Ticket válido", "description": "Descripción válida.", "status": "closed"}):
        with pytest.raises(ValidationError):
            TicketCreate(**datos)
    construido = TicketCreate.model_construct(title="x", description="x")
    with pytest.raises(ValidationError):
        tickets["servicio"].crear(tickets["referencias"][0], construido)
    assert consulta_interna(tickets, lambda repo: repo.resumen()).totalTickets == 0


def test_detalle_ausente_es_distinto_de_error_bd(tickets):
    with pytest.raises(ErrorTickets) as error:
        consulta_interna(tickets, lambda repo: repo.detalle(uuid4()))
    assert error.value.codigo == CodigoTickets.NO_ENCONTRADO


def test_listado_vacio_y_fuera_de_rango(tickets):
    vacio = consulta_interna(tickets, lambda repo: repo.listar(TicketPagination()))
    assert vacio.items == () and vacio.totalItems == vacio.totalPages == 0
    crear(tickets)
    fuera = consulta_interna(tickets, lambda repo: repo.listar(TicketPagination(page=4, pageSize=1)))
    assert fuera.items == () and fuera.totalItems == fuera.totalPages == 1


def test_paginacion_orden_estable_empates_y_sin_n_mas_uno(tickets):
    creados = [crear(tickets, f"Ticket estable {n}") for n in range(5)]
    with tickets["motor"].begin() as db:
        db.execute(update(TicketORM).where(TicketORM.id.in_([t.id for t in creados]))
            .values(creado_en=creados[0].createdAt))
    consultas = []

    def registrar(_, __, statement, *___):
        consultas.append(statement)

    event.listen(tickets["motor"], "before_cursor_execute", registrar)
    try:
        paginas = [consulta_interna(tickets, lambda repo, p=p: repo.listar(
            TicketPagination(page=p, pageSize=2))) for p in (1, 2, 3)]
    finally:
        event.remove(tickets["motor"], "before_cursor_execute", registrar)
    assert len(consultas) == 3  # Un SELECT por página, incluyendo total/usuarios.
    assert all("hash_contrasena" not in sql for sql in consultas)
    assert [t.id for pagina in paginas for t in pagina.items] == sorted((t.id for t in creados), reverse=True)
    assert all(p.totalItems == 5 and p.totalPages == 3 for p in paginas)


def test_actualizar_estado_conserva_campos_ajenos_y_es_idempotente(tickets):
    t = crear(tickets)
    with tickets["motor"].begin() as db:
        db.execute(update(TicketORM).where(TicketORM.id == t.id).values(
            categoria="Categoría existente", area="Área existente", prioridad="high",
            asignado_a_id=tickets["usuarios"][1], resuelto_en=t.createdAt))
    antes = consulta_interna(tickets, lambda repo: repo.detalle(t.id))
    despues = consulta_interna(tickets, lambda repo: repo.actualizar_estado(
        t.id, TicketStatusUpdate(status="closed"), estado_esperado="open"))
    assert despues.status == "closed" and despues.updatedAt >= antes.updatedAt
    assert antes.model_dump(exclude={"status", "updatedAt"}) == despues.model_dump(exclude={"status", "updatedAt"})
    repetido = consulta_interna(tickets, lambda repo: repo.actualizar_estado(t.id, TicketStatusUpdate(status="closed")))
    assert repetido == despues


def test_estado_invalido_no_escribe(tickets):
    t = crear(tickets)
    datos = TicketStatusUpdate.model_construct(status="critical")
    with pytest.raises(ValidationError):
        consulta_interna(tickets, lambda repo: repo.actualizar_estado(t.id, datos))
    assert consulta_interna(tickets, lambda repo: repo.detalle(t.id)) == t


def test_actualizacion_de_ausente(tickets):
    with pytest.raises(ErrorTickets) as error:
        consulta_interna(tickets, lambda repo: repo.actualizar_estado(uuid4(), TicketStatusUpdate(status="closed")))
    assert error.value.codigo == CodigoTickets.NO_ENCONTRADO


def test_dos_actualizaciones_con_precondicion_no_pierden_conflicto(tickets):
    t = crear(tickets)
    barrera = Barrier(2)

    def cambiar(estado):
        barrera.wait(timeout=5)
        try:
            consulta_interna(tickets, lambda repo: repo.actualizar_estado(
                t.id, TicketStatusUpdate(status=estado), estado_esperado="open"))
            return estado
        except ErrorTickets as error:
            return error.codigo

    with ThreadPoolExecutor(max_workers=2) as pool:
        futuros = [pool.submit(cambiar, s) for s in ("in_progress", "closed")]
        resultados = [f.result(timeout=10) for f in futuros]
    assert resultados.count(CodigoTickets.CONFLICTO_ESTADO) == 1
    final = consulta_interna(tickets, lambda repo: repo.detalle(t.id))
    assert final.status in resultados


def test_identidad_orm_vieja_y_transaccion_antigua_no_pisan_campos_ni_fecha(tickets):
    t = crear(tickets)
    with Session(tickets["motor"]) as db, transaccion_seguridad(db):
        # Iniciar antes de una escritura ajena y conservar un objeto antiguo.
        vieja = db.get(TicketORM, t.id)
        assert vieja.categoria is None
        with tickets["motor"].begin() as otra:
            otra.execute(update(TicketORM).where(TicketORM.id == t.id).values(
                categoria="Cambio concurrente", actualizado_en=func.clock_timestamp()))
            fecha = otra.scalar(select(TicketORM.actualizado_en).where(TicketORM.id == t.id))
        cambiado = RepositorioTickets(db).actualizar_estado(t.id, TicketStatusUpdate(status="in_progress"))
    assert cambiado.category == "Cambio concurrente"
    assert cambiado.updatedAt >= fecha


def test_vencimiento_despues_de_insertar_revierte_antes_de_commit(tickets):
    with tickets["motor"].connect() as db:
        ahora = [db.scalar(select(func.clock_timestamp()))]

    def avanzar(db, _):
        if db.get_bind().pool is tickets["motor"].pool and any(type(f) is TicketORM for f in db.new):
            ahora[0] += timedelta(hours=1)

    servicio = ServicioTickets(tickets["motor"], reloj=lambda _: ahora[0])
    event.listen(Session, "after_flush", avanzar)
    try:
        with pytest.raises(ErrorSeguridad) as error:
            servicio.crear(tickets["referencias"][0], TicketCreate(
                title="No debe confirmarse", description="Descripción para probar revalidación."))
    finally:
        event.remove(Session, "after_flush", avanzar)
    assert error.value.codigo == CodigoSeguridad.SESION_VENCIDA
    assert consulta_interna(tickets, lambda repo: repo.resumen()).totalTickets == 0


def test_rollback_real_revierte_creacion_y_actualizacion(tickets):
    t = crear(tickets)
    with Session(tickets["motor"]) as db:
        with pytest.raises(RuntimeError), transaccion_seguridad(db):
            repo = RepositorioTickets(db)
            repo.crear(TicketCreate(title="No se confirma", description="Descripción para rollback."),
                       creador_id=tickets["usuarios"][0])
            repo.actualizar_estado(t.id, TicketStatusUpdate(status="resolved"))
            raise RuntimeError("Fallo de la operación compuesta.")
    assert consulta_interna(tickets, lambda repo: repo.detalle(t.id)) == t
    assert consulta_interna(tickets, lambda repo: repo.resumen()).totalTickets == 1


def test_conteos_reales_incluyen_todos_los_estados(tickets):
    for estado in ("open", "in_progress", "resolved", "closed"):
        t = crear(tickets)
        consulta_interna(tickets, lambda repo: repo.actualizar_estado(t.id, TicketStatusUpdate(status=estado)))
    assert consulta_interna(tickets, lambda repo: repo.resumen()).model_dump() == {
        "totalTickets": 4, "openTickets": 1, "inProgressTickets": 1, "resolvedTickets": 1, "closedTickets": 1,
    }


def test_fk_creador_y_errores_saneados(tickets):
    with pytest.raises(ErrorSeguridad) as error:
        consulta_interna(tickets, lambda repo: repo.crear(
            TicketCreate(title="Ticket rechazado", description="Descripción de prueba."), creador_id=uuid4()))
    assert error.value.codigo == CodigoSeguridad.TRANSACCION
    assert "INSERT" not in str(error.value) and "tickets" not in str(error.value)
    assert consulta_interna(tickets, lambda repo: repo.resumen()).totalTickets == 0


def test_fallo_commit_no_devuelve_ticket_ni_lo_persiste(tickets):
    def fallar(_):
        raise OperationalError("SQL interno privado", {}, Exception("secreto del controlador"))

    event.listen(tickets["motor"], "commit", fallar)
    try:
        with pytest.raises(ErrorSeguridad) as error:
            crear(tickets)
    finally:
        event.remove(tickets["motor"], "commit", fallar)
    assert "privado" not in str(error.value) and "secreto" not in str(error.value)
    assert consulta_interna(tickets, lambda repo: repo.resumen()).totalTickets == 0


@pytest.mark.parametrize("operacion", ["listar", "detalle", "actualizar_estado", "resumen"])
def test_coordinador_politica_adicional_puede_restringir(tickets, operacion):
    t = crear(tickets)
    argumentos = {"listar": (), "detalle": (t.id,), "resumen": (),
                  "actualizar_estado": (t.id, TicketStatusUpdate(status="closed"))}
    servicio = ServicioTickets(tickets["motor"], autorizador=lambda *_: False)
    with pytest.raises(ErrorTickets) as error:
        getattr(servicio, operacion)(tickets["referencias"][0], *argumentos[operacion])
    assert error.value.codigo == CodigoTickets.NO_AUTORIZADO
    assert consulta_interna(tickets, lambda repo: repo.detalle(t.id)) == t


@pytest.mark.parametrize("cambio,codigo", [
    ("inactivo", CodigoSeguridad.USUARIO_INACTIVO),
    ("revocada", CodigoSeguridad.SESION_REVOCADA),
    ("vencida", CodigoSeguridad.SESION_VENCIDA),
])
def test_sesion_real_revalidada_en_cada_operacion(tickets, cambio, codigo):
    with tickets["motor"].begin() as db:
        if cambio == "inactivo":
            db.execute(update(Usuario).where(Usuario.id == tickets["usuarios"][0]).values(activo=False))
        else:
            valores = {"revocada_en": func.now(), "motivo_revocacion": "individual"} if cambio == "revocada" else {
                "creado_en": func.now() - timedelta(hours=2),
                "ultima_actividad": func.now() - timedelta(hours=1)}
            db.execute(update(Sesion).where(Sesion.usuario_id == tickets["usuarios"][0]).values(**valores))
    with pytest.raises(ErrorSeguridad) as error:
        crear(tickets)
    assert error.value.codigo == codigo
    assert consulta_interna(tickets, lambda repo: repo.resumen()).totalTickets == 0


def test_politica_inyectada_usa_identidad_vigente_y_no_renueva_actividad(tickets):
    # Restricción adicional exclusiva de este fixture, sobre la matriz aprobada.
    observados = []

    def politica(sesion, operacion, ticket_id):
        observados.append((sesion.usuario.role, operacion, ticket_id))
        return sesion.usuario.role == "agent"

    with tickets["motor"].begin() as db:
        db.execute(update(Usuario).where(Usuario.id == tickets["usuarios"][0]).values(rol="agent"))
        anterior = db.scalar(select(Sesion.ultima_actividad).where(Sesion.usuario_id == tickets["usuarios"][0]))
    servicio = ServicioTickets(tickets["motor"], autorizador=politica)
    assert servicio.resumen(tickets["referencias"][0]).totalTickets == 0
    assert observados == [("agent", OperacionTicket.RESUMEN, None)] * 2
    with tickets["motor"].connect() as db:
        assert db.scalar(select(Sesion.ultima_actividad).where(Sesion.usuario_id == tickets["usuarios"][0])) == anterior


@pytest.mark.parametrize("actor", [0, 1], ids=["admin", "agent"])
def test_matriz_aprobada_cinco_operaciones_con_alcance_global(tickets, actor):
    e = tickets
    ajeno = crear(e, actor=1 - actor)
    propio = crear(e, actor=actor)
    servicio, referencia = e["servicio"], e["referencias"][actor]
    pagina = servicio.listar(referencia, TicketPagination(pageSize=1))
    assert pagina.totalItems == 2 and pagina.totalPages == 2
    assert servicio.detalle(referencia, ajeno.id) == ajeno
    cambiado = servicio.actualizar_estado(referencia, ajeno.id, TicketStatusUpdate(status="in_progress"))
    assert cambiado.createdBy.id == e["usuarios"][1 - actor]
    assert cambiado.status == "in_progress"
    assert propio.createdBy.id == e["usuarios"][actor]
    assert servicio.resumen(referencia).model_dump() == {
        "totalTickets": 2, "openTickets": 1, "inProgressTickets": 1,
        "resolvedTickets": 0, "closedTickets": 0}
    assert consulta_interna(e, lambda repo: repo.detalle(ajeno.id)) == cambiado


def operaciones(e, referencia, ticket_id):
    servicio = e["servicio"]
    return [
        lambda: servicio.crear(referencia, TicketCreate(title="Creación denegada", description="No debe persistirse.")),
        lambda: servicio.listar(referencia),
        lambda: servicio.detalle(referencia, ticket_id),
        lambda: servicio.actualizar_estado(referencia, ticket_id, TicketStatusUpdate(status="closed")),
        lambda: servicio.resumen(referencia),
    ]


@pytest.mark.parametrize("caso,codigo", [
    ("inactivo", CodigoSeguridad.USUARIO_INACTIVO),
    ("revocada", CodigoSeguridad.SESION_REVOCADA),
    ("absoluta", CodigoSeguridad.SESION_VENCIDA),
    ("inactividad", CodigoSeguridad.SESION_VENCIDA),
])
def test_matriz_rechaza_cinco_operaciones_sin_vigencia(tickets, caso, codigo):
    t = crear(tickets)
    with tickets["motor"].begin() as db:
        if caso == "inactivo":
            db.execute(update(Usuario).where(Usuario.id == tickets["usuarios"][0]).values(activo=False))
        else:
            valores = {
                "revocada": {"revocada_en": func.clock_timestamp(), "motivo_revocacion": "individual"},
                "absoluta": {"creado_en": func.now() - timedelta(hours=9),
                             "ultima_actividad": func.now() - timedelta(hours=2),
                             "expira_en": func.now() - timedelta(hours=1)},
                "inactividad": {"creado_en": func.now() - timedelta(hours=2),
                                "ultima_actividad": func.now() - timedelta(hours=1)},
            }[caso]
            db.execute(update(Sesion).where(Sesion.usuario_id == tickets["usuarios"][0]).values(**valores))
    for ejecutar in operaciones(tickets, tickets["referencias"][0], t.id):
        with pytest.raises(ErrorSeguridad) as error:
            ejecutar()
        assert error.value.codigo == codigo
    assert consulta_interna(tickets, lambda repo: repo.detalle(t.id)).status == "open"
    assert consulta_interna(tickets, lambda repo: repo.resumen()).totalTickets == 1


@pytest.mark.parametrize("referencia", [None, uuid4()])
def test_anonimo_o_uuid_no_autorizan_ninguna_operacion(tickets, referencia):
    t = crear(tickets)
    for ejecutar in operaciones(tickets, referencia, t.id):
        with pytest.raises(ErrorSeguridad) as error:
            ejecutar()
        assert error.value.codigo == CodigoSeguridad.SESION_INEXISTENTE
    assert consulta_interna(tickets, lambda repo: repo.detalle(t.id)) == t


@pytest.mark.parametrize("cambio", ["inactivar", "revocar"])
def test_escritura_bloquea_cambio_concurrente_de_autorizacion(tickets, cambio):
    e = tickets
    autorizada, liberar, preparado = Event(), Event(), Event()
    pid = []

    def control(db, actual, antes):
        if antes:
            autorizada.set()
            assert liberar.wait(timeout=8)

    def escribir():
        return e["servicio"].crear(e["referencias"][0], TicketCreate(
            title="Escritura concurrente", description="Autorización bloqueada hasta commit."),
            control_escritura=control)

    def invalidar():
        with e["motor"].begin() as db:
            pid.append(db.scalar(text("SELECT pg_backend_pid()")))
            preparado.set()
            if cambio == "inactivar":
                db.execute(update(Usuario).where(Usuario.id == e["usuarios"][0]).values(activo=False))
            else:
                db.execute(update(Sesion).where(Sesion.usuario_id == e["usuarios"][0]).values(
                    revocada_en=func.clock_timestamp(), motivo_revocacion="individual"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        escritura = pool.submit(escribir)
        invalidacion = None
        try:
            assert autorizada.wait(timeout=5)
            invalidacion = pool.submit(invalidar)
            assert preparado.wait(timeout=5)
            limite = monotonic() + 5
            while monotonic() < limite:
                with e["motor"].connect() as db:
                    bloqueado = db.scalar(text(
                        "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid[0]})
                if bloqueado:
                    break
                sleep(.01)
            assert bloqueado and not invalidacion.done()
        finally:
            liberar.set()
        t = escritura.result(timeout=10)
        invalidacion.result(timeout=10)
    assert consulta_interna(e, lambda repo: repo.detalle(t.id)).id == t.id
    with pytest.raises(ErrorSeguridad) as error:
        e["servicio"].resumen(e["referencias"][0])
    assert error.value.codigo == (CodigoSeguridad.USUARIO_INACTIVO if cambio == "inactivar"
                                else CodigoSeguridad.SESION_REVOCADA)
