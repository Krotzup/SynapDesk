"""Altas confirmadas, auditoría y carreras en PostgreSQL temporal exclusivo."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event, Lock
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import ContextoCsrf, EventoAutenticacion, Sesion, TokenCsrf, Usuario
from app.seguridad.auditoria import ServicioAuditoria
from app.seguridad.creacion_usuarios import (
    CodigoCreacionUsuario as C, DatosNuevoUsuario, ErrorCreacionUsuario, ServicioCreacionUsuarios,
)
from app.seguridad.login import LoginConfirmado
from app.seguridad.operaciones_sesion import ReferenciaSesion, ServicioConsultaSesion
from app.seguridad.secretos import generar_secreto
from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad, transaccion_seguridad
from pruebas.integracion.test_login import entorno_login, login
from pruebas.integracion.test_operaciones_sesion import esperar_bloqueado


@pytest.fixture
def altas(entorno_login, configuracion_bd_test):
    e = entorno_login
    base = configuracion_bd_test
    assert base.postgres_port == 5433 and base.postgres_host in {"localhost", "127.0.0.1", "::1"}
    assert base.postgres_db.startswith("synapdesk_auth07_sec01a_")
    with e["motor"].begin() as db:
        assert db.scalar(text("SELECT current_database()")) == base.postgres_db
        db.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(rol="admin"))
    r = login(e)
    e.update(referencia=ReferenciaSesion(r.sesion.credencial), sesion_id=r.sesion.id)
    config = e["config"].model_copy(update={campo: getattr(base, campo)
        for campo in ("postgres_host", "postgres_port", "postgres_db", "postgres_user",
                      "postgres_password", "postgres_sslmode")})
    e["config_alta"] = config
    e["altas"] = ServicioCreacionUsuarios(config, reloj=e["reloj"])
    e["nueva_clave"] = generar_secreto()
    e["correo_nuevo"] = f"alta-{uuid4()}@example.invalid"
    ids = {EventoAutenticacion: set(), Usuario: set()}
    candado = Lock()

    def recordar(db, contexto):
        if db.get_bind().pool is e["altas"]._motor.pool:
            with candado:
                for fila in db.new:
                    if type(fila) in ids and fila.id is not None:
                        ids[type(fila)].add(fila.id)

    event.listen(Session, "after_flush", recordar)
    try:
        yield e
    finally:
        event.remove(Session, "after_flush", recordar)
        try:
            with e["motor"].begin() as db:
                assert db.scalar(text("SELECT current_database()")) == base.postgres_db
                # Solo filas propias. Las sesiones de login las limpia su fixture.
                db.execute(delete(EventoAutenticacion).where(EventoAutenticacion.id.in_(ids[EventoAutenticacion])))
                sesiones = select(Sesion.id).where(Sesion.usuario_id.in_(ids[Usuario]))
                contextos = select(ContextoCsrf.id).where(ContextoCsrf.sesion_id.in_(sesiones))
                db.execute(delete(TokenCsrf).where(TokenCsrf.contexto_id.in_(contextos)))
                db.execute(delete(ContextoCsrf).where(ContextoCsrf.sesion_id.in_(sesiones)))
                db.execute(delete(Sesion).where(Sesion.usuario_id.in_(ids[Usuario])))
                db.execute(delete(Usuario).where(Usuario.id.in_(ids[Usuario])))
        finally:
            e["altas"].cerrar()


def preparar(e, rol="agent", correo=None):
    return e["altas"].preparar(DatosNuevoUsuario(nombre="Persona de prueba",
        correo="  " + (correo or e["correo_nuevo"]).upper() + "  ", rol=rol,
        contrasena=e["nueva_clave"]))


def contar(e, modelo):
    with e["motor"].connect() as db:
        return db.scalar(select(func.count()).select_from(modelo))


def comprobar_ausencia(e):
    with Session(e["motor"]) as db:
        assert db.scalar(select(Usuario.id).where(Usuario.correo == e["correo_nuevo"])) is None
        assert db.scalar(select(func.count()).select_from(EventoAutenticacion).where(
            EventoAutenticacion.tipo_evento == "user_created")) == 0


def otra_admin(e):
    correo = f"otra-admin-{uuid4()}@example.invalid"
    cuenta = e["altas"].crear(e["referencia"], preparar(e, "admin", correo))
    autenticado = login(e, cuenta=correo, contrasena=e["nueva_clave"])
    assert isinstance(autenticado, LoginConfirmado)
    return ReferenciaSesion(autenticado.sesion.credencial), cuenta.id


@pytest.mark.parametrize("rol", ["admin", "agent"])
def test_alta_commit_auditoria_otra_conexion_y_login_con_csrf(altas, rol, caplog):
    e = altas
    preparado = preparar(e, rol)
    sesiones = contar(e, Sesion)
    with Session(e["motor"]) as db:
        s = db.get(Sesion, e["sesion_id"])
        estado = (s.ultima_actividad, s.expira_en, s.revocada_en)
    lector = crear_motor_bd(e["config_alta"])
    vistos = []

    def inspeccionar(db, contexto):
        if db.get_bind().pool is e["altas"]._motor.pool:
            with lector.connect() as otro:
                assert otro.scalar(select(Usuario.id).where(Usuario.correo == e["correo_nuevo"])) is None
            vistos.extend(type(f) for f in db.new)

    event.listen(Session, "after_flush", inspeccionar)
    try:
        resultado = e["altas"].crear(e["referencia"], preparado)
        with Session(lector) as db:
            cuenta = db.get(Usuario, resultado.id)
            evento = db.scalar(select(EventoAutenticacion).where(
                EventoAutenticacion.usuario_id == cuenta.id,
                EventoAutenticacion.tipo_evento == "user_created"))
            assert cuenta.activo and cuenta.rol == rol and cuenta.correo == e["correo_nuevo"]
            assert e["passwords"].verificar(cuenta.hash_contrasena, e["nueva_clave"].get_secret_value())
            assert cuenta.hash_contrasena.startswith("$argon2id$")
            assert evento.actor_tipo == "synapdesk_user" and evento.actor_id == str(e["usuario"].id)
            assert evento.rol_asignado == rol and evento.ocurrido_en == e["ahora"]
            assert evento.resultado == "success" and evento.motivo == "user_created_by_admin"
            assert evento.sesion_id == e["sesion_id"] and evento.request_id is not None
            texto = repr(vars(evento)) + resultado.model_dump_json() + caplog.text
            assert e["nueva_clave"].get_secret_value() not in texto
            assert preparado.hash_contrasena.get_secret_value() not in texto
            assert e["referencia"].credencial.get_secret_value() not in texto
            s = db.get(Sesion, e["sesion_id"])
            assert (s.ultima_actividad, s.expira_en, s.revocada_en) == estado
    finally:
        event.remove(Session, "after_flush", inspeccionar)
        lector.dispose()
    assert vistos == [Usuario, EventoAutenticacion]
    assert resultado.model_dump() == dict(id=resultado.id, email=e["correo_nuevo"], role=rol)
    assert contar(e, Sesion) == sesiones  # No hay sesión automática.
    autenticado = login(e, cuenta=e["correo_nuevo"], contrasena=e["nueva_clave"])
    assert isinstance(autenticado, LoginConfirmado) and autenticado.usuario.id == resultado.id
    assert autenticado.usuario.role == rol
    referencia = ReferenciaSesion(autenticado.sesion.credencial)
    assert ServicioConsultaSesion(e["motor"], reloj=e["reloj"]).consultar(referencia).id == resultado.id


def test_ensayo_comparte_flujo_y_revierte_cuenta_y_evento(altas):
    e = altas
    vistos, commits = [], []
    def inspeccionar(db, contexto):
        if db.get_bind().pool is e["altas"]._motor.pool:
            vistos.extend(type(f) for f in db.new)
    def commit(db):
        if db.get_bind().pool is e["altas"]._motor.pool:
            commits.append(True)
    event.listen(Session, "after_flush", inspeccionar)
    event.listen(Session, "before_commit", commit)
    try:
        resultado = e["altas"].ensayar(e["referencia"], preparar(e))
    finally:
        event.remove(Session, "after_flush", inspeccionar)
        event.remove(Session, "before_commit", commit)
    assert vistos == [Usuario, EventoAutenticacion] and not commits
    assert not resultado.persistido and not resultado.auditoria_registrada
    comprobar_ausencia(e)


@pytest.mark.parametrize("rol", ["admin", "agent"])
def test_agent_no_puede_crear_ningun_rol(altas, rol):
    e = altas
    with e["motor"].begin() as db:
        db.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(rol="agent"))
    with pytest.raises(ErrorCreacionUsuario) as error:
        e["altas"].crear(e["referencia"], preparar(e, rol))
    assert error.value.codigo == C.NO_AUTORIZADO
    comprobar_ausencia(e)


@pytest.mark.parametrize("caso,codigo", [("inactivo", CodigoSeguridad.USUARIO_INACTIVO),
    ("revocada", CodigoSeguridad.SESION_REVOCADA), ("inactividad", CodigoSeguridad.SESION_VENCIDA),
    ("absoluta", CodigoSeguridad.SESION_VENCIDA), ("inexistente", CodigoSeguridad.SESION_INEXISTENTE),
    ("anonimo", CodigoSeguridad.SESION_INEXISTENTE)])
def test_revalidacion_de_estado_actual(altas, caso, codigo):
    e = altas
    referencia = e["referencia"]
    with e["motor"].begin() as db:
        if caso == "inactivo":
            db.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(activo=False))
        elif caso == "revocada":
            db.execute(update(Sesion).where(Sesion.id == e["sesion_id"]).values(revocada_en=e["ahora"]))
        elif caso in {"inactividad", "absoluta"}:
            e["ahora"] += timedelta(minutes=30) if caso == "inactividad" else timedelta(hours=8)
            if caso == "absoluta":
                db.execute(update(Sesion).where(Sesion.id == e["sesion_id"]).values(ultima_actividad=e["ahora"]))
        elif caso == "anonimo":
            referencia = None
        else:
            referencia = ReferenciaSesion(generar_secreto())
    with pytest.raises(ErrorSeguridad) as error:
        e["altas"].crear(referencia, preparar(e))
    assert error.value.codigo == codigo
    comprobar_ausencia(e)


def test_correo_existente_normalizado_sin_sobrescritura(altas):
    e = altas
    with pytest.raises(ErrorCreacionUsuario) as error:
        e["altas"].crear(e["referencia"], preparar(e, correo=e["usuario"].correo.upper()))
    assert error.value.codigo == C.CORREO_EXISTENTE
    assert contar(e, Usuario) == 1


@pytest.mark.parametrize("cambio", ["rol", "estado", "revocacion", "vencimiento"])
def test_cambio_confirmado_mientras_espera_impide_insercion(altas, cambio):
    e = altas
    preparado = preparar(e)
    listo, pids = Event(), []
    def iniciado(db, transaccion, conexion):
        if db.get_bind().pool is e["altas"]._motor.pool:
            pids.append(conexion.scalar(text("SELECT pg_backend_pid()")))
            listo.set()
    event.listen(Session, "after_begin", iniciado)
    try:
        with ThreadPoolExecutor(1) as pool:
            with Session(e["motor"]) as externo, transaccion_seguridad(externo):
                if cambio in {"rol", "estado"}:
                    valores = dict(rol="agent") if cambio == "rol" else dict(activo=False)
                    externo.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(**valores))
                else:
                    externo.execute(select(Sesion).where(Sesion.id == e["sesion_id"]).with_for_update())
                    if cambio == "revocacion":
                        externo.execute(update(Sesion).where(Sesion.id == e["sesion_id"]).values(revocada_en=e["ahora"]))
                futuro = pool.submit(e["altas"].crear, e["referencia"], preparado)
                assert listo.wait(5)
                esperar_bloqueado(e["motor"], pids[0])
                if cambio == "vencimiento":
                    e["ahora"] += timedelta(minutes=30)
            with pytest.raises((ErrorSeguridad, ErrorCreacionUsuario)) as error:
                futuro.result(timeout=5)
            esperado = {"rol": C.NO_AUTORIZADO, "estado": CodigoSeguridad.USUARIO_INACTIVO,
                "revocacion": CodigoSeguridad.SESION_REVOCADA, "vencimiento": CodigoSeguridad.SESION_VENCIDA}[cambio]
            assert error.value.codigo == esperado
    finally:
        event.remove(Session, "after_begin", iniciado)
    comprobar_ausencia(e)


@pytest.mark.parametrize("cambio", ["rol", "estado", "revocacion"])
def test_cambio_posterior_espera_hasta_commit_del_alta(altas, cambio):
    e = altas
    preparado = preparar(e)
    insertado, liberar, listo = Event(), Event(), Event()
    pids = []
    def retener(db, contexto):
        if db.get_bind().pool is e["altas"]._motor.pool and any(isinstance(f, Usuario) for f in db.new):
            insertado.set()
            assert liberar.wait(5)
    def modificar():
        with Session(e["motor"]) as db, transaccion_seguridad(db):
            pids.append(db.scalar(text("SELECT pg_backend_pid()")))
            listo.set()
            if cambio == "revocacion":
                db.execute(update(Sesion).where(Sesion.id == e["sesion_id"]).values(revocada_en=e["ahora"]))
            else:
                valores = dict(rol="agent") if cambio == "rol" else dict(activo=False)
                db.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(**valores))
    event.listen(Session, "after_flush", retener)
    try:
        with ThreadPoolExecutor(2) as pool:
            alta = pool.submit(e["altas"].crear, e["referencia"], preparado)
            try:
                assert insertado.wait(5)
                cambio_futuro = pool.submit(modificar)
                assert listo.wait(5)
                esperar_bloqueado(e["motor"], pids[0])
                assert not cambio_futuro.done()
            finally:
                liberar.set()
            resultado = alta.result(timeout=5)
            cambio_futuro.result(timeout=5)
    finally:
        liberar.set()
        event.remove(Session, "after_flush", retener)
    with Session(e["motor"]) as db:
        assert db.get(Usuario, resultado.id) is not None
    with pytest.raises((ErrorSeguridad, ErrorCreacionUsuario)):
        e["altas"].crear(e["referencia"], preparar(e, correo=f"{uuid4()}@example.invalid"))


@pytest.mark.parametrize("fallo", ["auditoria", "insercion", "commit_diferido", "commit_desconexion"])
def test_fallos_reales_revierten_cuenta_y_auditoria(altas, fallo, monkeypatch, caplog):
    e = altas
    if fallo == "auditoria":
        def fallar(self, **datos):
            self.db.execute(text("SELECT 1/0"))
        monkeypatch.setattr(ServicioAuditoria, "registrar", fallar)
    def antes_flush(db, contexto, instancias):
        if db.get_bind().pool is e["altas"]._motor.pool and fallo == "insercion":
            for fila in db.new:
                if isinstance(fila, Usuario):
                    fila.rol = "invalido"
    def antes_commit(db):
        if db.get_bind().pool is not e["altas"]._motor.pool:
            return
        if fallo == "commit_diferido":
            db.execute(text("CREATE TEMP TABLE fallo_alta (n int UNIQUE DEFERRABLE INITIALLY DEFERRED) ON COMMIT DROP"))
            db.execute(text("INSERT INTO fallo_alta VALUES (1),(1)"))
        elif fallo == "commit_desconexion":
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            with e["motor"].connect() as control:
                assert control.scalar(text("SELECT pg_terminate_backend(:pid)"), dict(pid=pid))
    event.listen(Session, "before_flush", antes_flush)
    event.listen(Session, "before_commit", antes_commit)
    try:
        with pytest.raises(ErrorSeguridad) as error:
            e["altas"].crear(e["referencia"], preparar(e))
        assert error.value.codigo in {CodigoSeguridad.TRANSACCION, CodigoSeguridad.INFRAESTRUCTURA}
        assert e["nueva_clave"].get_secret_value() not in str(error.value) + caplog.text
        assert e["config_alta"].postgres_password.get_secret_value() not in str(error.value) + caplog.text
    finally:
        event.remove(Session, "before_flush", antes_flush)
        event.remove(Session, "before_commit", antes_commit)
    comprobar_ausencia(e)


@pytest.mark.parametrize("confirmar", [True, False])
def test_unicidad_real_tras_esperar_insert_externo(altas, confirmar):
    e = altas
    preparado = preparar(e)
    listo, pids = Event(), []
    def iniciado(db, transaccion, conexion):
        if db.get_bind().pool is e["altas"]._motor.pool:
            pids.append(conexion.scalar(text("SELECT pg_backend_pid()")))
            listo.set()
    event.listen(Session, "after_begin", iniciado)
    try:
        with ThreadPoolExecutor(1) as pool:
            with Session(e["motor"]) as externo:
                externo.begin()
                externo.add(Usuario(nombre="Externo", correo=e["correo_nuevo"], rol="agent", activo=True,
                    hash_contrasena=preparado.hash_contrasena.get_secret_value()))
                externo.flush()
                futuro = pool.submit(e["altas"].crear, e["referencia"], preparado)
                assert listo.wait(5)
                esperar_bloqueado(e["motor"], pids[0])
                if confirmar:
                    externo.commit()
                else:
                    externo.rollback()
            if confirmar:
                with pytest.raises(ErrorCreacionUsuario) as error:
                    futuro.result(timeout=5)
                assert error.value.codigo == C.CORREO_EXISTENTE
            else:
                assert futuro.result(timeout=5).email == e["correo_nuevo"]
    finally:
        event.remove(Session, "after_begin", iniciado)
    assert contar(e, Usuario) == 2


@pytest.mark.parametrize("espera", ["correo", "auditoria"])
def test_expiracion_tras_espera_de_escritura_revierte_todo(altas, espera):
    e = altas
    preparado = preparar(e)
    listo, pids = Event(), []
    def iniciado(db, transaccion, conexion):
        if db.get_bind().pool is e["altas"]._motor.pool:
            pids.append(conexion.scalar(text("SELECT pg_backend_pid()")))
            listo.set()
    event.listen(Session, "after_begin", iniciado)
    try:
        with ThreadPoolExecutor(1) as pool:
            with Session(e["motor"]) as externo:
                externo.begin()
                if espera == "correo":
                    externo.add(Usuario(nombre="Externo", correo=e["correo_nuevo"], rol="agent", activo=True,
                        hash_contrasena=preparado.hash_contrasena.get_secret_value()))
                    externo.flush()
                else:
                    externo.execute(text("LOCK TABLE public.eventos_autenticacion IN ACCESS EXCLUSIVE MODE"))
                futuro = pool.submit(e["altas"].crear, e["referencia"], preparado)
                assert listo.wait(5)
                esperar_bloqueado(e["motor"], pids[0])
                e["ahora"] += timedelta(minutes=30)
                externo.rollback()
            with pytest.raises(ErrorSeguridad) as error:
                futuro.result(timeout=5)
            assert error.value.codigo == CodigoSeguridad.SESION_VENCIDA
    finally:
        event.remove(Session, "after_begin", iniciado)
    comprobar_ausencia(e)


def test_dos_admins_correos_distintos_confirman_simultaneamente(altas):
    e = altas
    otra, _ = otra_admin(e)
    candidatos = [preparar(e, correo=f"{uuid4()}@example.invalid") for _ in range(2)]
    barrera = Barrier(2)
    def insertado(db, contexto):
        if db.get_bind().pool is e["altas"]._motor.pool and any(isinstance(f, Usuario) for f in db.new):
            barrera.wait(timeout=5)
    event.listen(Session, "after_flush", insertado)
    try:
        with ThreadPoolExecutor(2) as pool:
            futuros = [pool.submit(e["altas"].crear, ref, p)
                for ref, p in zip((e["referencia"], otra), candidatos)]
            resultados = [f.result(timeout=10) for f in futuros]
    finally:
        event.remove(Session, "after_flush", insertado)
    with Session(e["motor"]) as db:
        assert len(db.scalars(select(Usuario).where(Usuario.id.in_([r.id for r in resultados]))).all()) == 2
        assert db.scalar(select(func.count()).select_from(EventoAutenticacion).where(
            EventoAutenticacion.usuario_id.in_([r.id for r in resultados]),
            EventoAutenticacion.tipo_evento == "user_created")) == 2


def test_dos_admins_mismo_correo_un_ganador_y_un_evento(altas):
    e = altas
    otra, _ = otra_admin(e)
    candidatos = [preparar(e) for _ in range(2)]
    insertado, liberar, segundo_listo = Event(), Event(), Event()
    pids = []
    def iniciado(db, transaccion, conexion):
        if db.get_bind().pool is e["altas"]._motor.pool:
            pids.append(conexion.scalar(text("SELECT pg_backend_pid()")))
            if len(pids) == 2:
                segundo_listo.set()
    def retener(db, contexto):
        if (db.get_bind().pool is e["altas"]._motor.pool
                and any(isinstance(f, Usuario) for f in db.new)):
            insertado.set()
            assert liberar.wait(5)
    event.listen(Session, "after_begin", iniciado)
    event.listen(Session, "after_flush", retener)
    try:
        with ThreadPoolExecutor(2) as pool:
            primero = pool.submit(e["altas"].crear, e["referencia"], candidatos[0])
            try:
                assert insertado.wait(5)
                segundo = pool.submit(e["altas"].crear, otra, candidatos[1])
                assert segundo_listo.wait(5)
                esperar_bloqueado(e["motor"], pids[1])
            finally:
                liberar.set()
            resultado = primero.result(timeout=5)
            with pytest.raises(ErrorCreacionUsuario) as error:
                segundo.result(timeout=5)
            assert error.value.codigo == C.CORREO_EXISTENTE
    finally:
        liberar.set()
        event.remove(Session, "after_flush", retener)
        event.remove(Session, "after_begin", iniciado)
    with Session(e["motor"]) as db:
        assert db.scalar(select(func.count()).select_from(Usuario).where(Usuario.correo == e["correo_nuevo"])) == 1
        assert db.scalar(select(func.count()).select_from(EventoAutenticacion).where(
            EventoAutenticacion.usuario_id == resultado.id)) == 1


def test_lock_timeout_real_sin_reintento_o_alta_parcial(altas):
    e = altas
    preparado = preparar(e)
    with ThreadPoolExecutor(1) as pool:
        with Session(e["motor"]) as externo, transaccion_seguridad(externo):
            externo.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(nombre="Retenido"))
            futuro = pool.submit(e["altas"].crear, e["referencia"], preparado)
            with pytest.raises(ErrorSeguridad) as error:
                futuro.result(timeout=7)
            assert error.value.codigo == CodigoSeguridad.TRANSACCION
    comprobar_ausencia(e)


def test_deadlock_real_revierte_alta(altas):
    e = altas
    preparado = preparar(e)
    insertado, continuar, pids = Event(), Event(), []
    def iniciado(db, transaccion, conexion):
        if db.get_bind().pool is e["altas"]._motor.pool:
            pids.append(conexion.scalar(text("SELECT pg_backend_pid()")))
            conexion.execute(text("SET LOCAL deadlock_timeout='100ms'"))
    def retener(db, contexto):
        if db.get_bind().pool is e["altas"]._motor.pool and any(isinstance(f, Usuario) for f in db.new):
            insertado.set()
            assert continuar.wait(5)
    event.listen(Session, "after_begin", iniciado)
    event.listen(Session, "after_flush", retener)
    try:
        with ThreadPoolExecutor(1) as pool:
            with Session(e["motor"]) as externo:
                externo.begin()
                externo.execute(text("SET LOCAL deadlock_timeout='2s'"))
                externo.execute(text("LOCK TABLE public.eventos_autenticacion IN ACCESS EXCLUSIVE MODE"))
                futuro = pool.submit(e["altas"].crear, e["referencia"], preparado)
                try:
                    assert insertado.wait(5)
                    continuar.set()
                    esperar_bloqueado(e["motor"], pids[0])
                    # Ciclo: alta bloquea admin y espera auditoría; escritor
                    # bloquea auditoría y espera admin. Víctima: alta (100 ms).
                    externo.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(rol="agent"))
                finally:
                    continuar.set()
                    externo.rollback()
            with pytest.raises(ErrorSeguridad) as error:
                futuro.result(timeout=5)
            assert error.value.codigo == CodigoSeguridad.TRANSACCION
    finally:
        continuar.set()
        event.remove(Session, "after_begin", iniciado)
        event.remove(Session, "after_flush", retener)
    comprobar_ausencia(e)


def test_desconexion_real_durante_escritura_saneada_sin_reintento(altas):
    e = altas
    preparado = preparar(e)
    def terminar(db, contexto):
        if db.get_bind().pool is e["altas"]._motor.pool and any(isinstance(f, Usuario) for f in db.new):
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            with e["motor"].connect() as control:
                assert control.scalar(text("SELECT pg_terminate_backend(:pid)"), dict(pid=pid))
    event.listen(Session, "after_flush", terminar)
    try:
        with pytest.raises(ErrorSeguridad) as error:
            e["altas"].crear(e["referencia"], preparado)
        assert error.value.codigo == CodigoSeguridad.INFRAESTRUCTURA
    finally:
        event.remove(Session, "after_flush", terminar)
    comprobar_ausencia(e)


def test_acuse_commit_perdido_exige_conciliacion_y_no_reintenta(altas):
    e = altas
    preparado = preparar(e)
    commits = []
    def perder_acuse(db):
        if db.get_bind().pool is e["altas"]._motor.pool:
            commits.append(True)
            # El servidor YA confirmó. Inyección del límite de transporte:
            # no se simula rollback ni se afirma que PostgreSQL no escribió.
            raise DBAPIError(None, None, Exception("acuse no disponible"), connection_invalidated=True)
    event.listen(Session, "after_commit", perder_acuse)
    try:
        with pytest.raises(ErrorSeguridad) as error:
            e["altas"].crear(e["referencia"], preparado)
        assert error.value.codigo == CodigoSeguridad.INFRAESTRUCTURA
    finally:
        event.remove(Session, "after_commit", perder_acuse)
    assert commits == [True]
    with Session(e["motor"]) as db:
        conciliado = db.scalar(select(Usuario).where(Usuario.correo == e["correo_nuevo"]))
        assert conciliado is not None
        assert db.scalar(select(func.count()).select_from(EventoAutenticacion).where(
            EventoAutenticacion.usuario_id == conciliado.id)) == 1
    # Reintento explícito de prueba: no crea otra cuenta ni otro evento.
    with pytest.raises(ErrorCreacionUsuario) as error:
        e["altas"].crear(e["referencia"], preparado)
    assert error.value.codigo == C.CORREO_EXISTENTE
    assert contar(e, Usuario) == 2


def test_conexion_fallida_no_filtra_dsn(altas):
    e = altas
    servicio = ServicioCreacionUsuarios(e["config_alta"].model_copy(update=dict(
        postgres_db="synapdesk_auth07_sec01a_" + uuid4().hex)))
    try:
        entrada = DatosNuevoUsuario("Prueba", e["correo_nuevo"], "agent", e["nueva_clave"])
        with pytest.raises(ErrorSeguridad) as error:
            servicio.crear(e["referencia"], servicio.preparar(entrada))
        assert error.value.codigo == CodigoSeguridad.INFRAESTRUCTURA
        assert e["config_alta"].postgres_password.get_secret_value() not in str(error.value)
    finally:
        servicio.cerrar()


@pytest.mark.parametrize("campo", ["postgres_user", "postgres_db"])
def test_identidad_ensayo_inconsistente_rechaza_sin_insercion(altas, campo):
    e = altas
    valor = "otro_principal" if campo == "postgres_user" else "synapdesk_auth07_sec01a_" + uuid4().hex
    e["altas"]._config = e["altas"]._config.model_copy(update={campo: valor})
    with pytest.raises(ErrorCreacionUsuario) as error:
        e["altas"].ensayar(e["referencia"], preparar(e))
    assert error.value.codigo == C.DESTINO_ENSAYO
    comprobar_ausencia(e)


@pytest.mark.parametrize("cambio", [dict(actor_tipo=None), dict(actor_id=None),
    dict(actor_id="externo"), dict(rol_asignado=None), dict(rol_asignado="root"),
    dict(resultado="failure"), dict(motivo=None)])
def test_restricciones_auditoria_reales(altas, cambio):
    e = altas
    campos = dict(tipo_evento="user_created", resultado="success", motivo="user_created_by_admin",
        actor_tipo="synapdesk_user", actor_id=str(e["usuario"].id), rol_asignado="agent",
        usuario_id=e["usuario"].id)
    with pytest.raises(IntegrityError):
        with Session(e["motor"]) as db, db.begin():
            db.add(EventoAutenticacion(**(campos | cambio)))
    comprobar_ausencia(e)


def test_migracion_preserva_historicos_y_downgrade_no_descarta_altas(altas):
    from alembic import command
    from alembic.config import Config
    e = altas
    config = Config("alembic.ini")
    # Todo en una transacción externa revertida: sin alterar el esquema compartido.
    with e["motor"].connect() as conexion:
        tx = conexion.begin()
        config.attributes["connection"] = conexion
        try:
            historico = conexion.execute(text("INSERT INTO eventos_autenticacion "
                "(tipo_evento,resultado,motivo,actor_tipo,actor_id) VALUES "
                "('admin_bootstrap','success','initial_admin_created','postgresql_role','123') RETURNING id")).scalar_one()
            command.downgrade(config, "0005_actor_bootstrap")
            assert conexion.scalar(text("SELECT actor_id FROM eventos_autenticacion WHERE id=:id"), dict(id=historico)) == "123"
            command.upgrade(config, "head")
            assert conexion.scalar(text("SELECT actor_id FROM eventos_autenticacion WHERE id=:id"), dict(id=historico)) == "123"
            assert conexion.scalar(text("SELECT rol_asignado IS NULL FROM eventos_autenticacion WHERE id=:id"), dict(id=historico))
            command.check(config)
        finally:
            tx.rollback()
    resultado = e["altas"].crear(e["referencia"], preparar(e))
    with e["motor"].connect() as conexion:
        config.attributes["connection"] = conexion
        with pytest.raises(DBAPIError) as error:
            command.downgrade(config, "0005_actor_bootstrap")
        assert error.value.orig.sqlstate == "P0001"
        conexion.rollback()
    with Session(e["motor"]) as db:
        assert db.get(Usuario, resultado.id) is not None
        assert db.scalar(select(EventoAutenticacion.actor_id).where(
            EventoAutenticacion.usuario_id == resultado.id)) == str(e["usuario"].id)
