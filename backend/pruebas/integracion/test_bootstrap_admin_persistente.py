"""Alta y auditoría confirmadas en PostgreSQL aislado; nunca ejecuta CLI real."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from multiprocessing import get_context
from threading import Event, Lock
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.configuracion import Configuracion
from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import (
    ContextoCsrf, EventoAutenticacion, LimiteAutenticacion, Sesion, TokenCsrf, Usuario,
)
from app.seguridad.auditoria import ServicioAuditoria, TipoEvento as T
from app.seguridad.bootstrap_admin import (
    CodigoBootstrap as C, DestinoAutorizado, ErrorBootstrap, ServicioBootstrapAdmin,
)
from app.seguridad.login import CredencialesLogin, LoginConfirmado, PruebaAnonimaLogin, ServicioLogin
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.operaciones_sesion import ReferenciaSesion, ServicioConsultaSesion, ServicioLogout
from app.seguridad.secretos import generar_secreto
from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad, transaccion_seguridad
from pruebas.login_auxiliar import configuracion_login, ip_controlada
from pruebas.integracion.test_operaciones_sesion import esperar_bloqueado


def acreditar_fixture(servicio):
    # Frontera confiable exclusiva del fixture: SQL real, sin afirmar TLS de BD.
    # No se ofrece como argumento, flag o modo de la CLI operativa.
    with Session(servicio._motor) as db, transaccion_seguridad(db):
        identidad = servicio._identificar(db)
    return DestinoAutorizado(identidad, "fixture:" + servicio.destino, servicio._emisor)


@pytest.fixture
def persistente(configuracion_bd_test):
    base = configuracion_bd_test
    assert base.postgres_port == 5433 and base.postgres_host in {"localhost", "127.0.0.1", "::1"}
    assert base.postgres_db.startswith("synapdesk_auth07_sec01a_")
    config = configuracion_login().model_copy(update={campo: getattr(base, campo) for campo in (
        "postgres_host", "postgres_port", "postgres_db", "postgres_user", "postgres_password", "postgres_sslmode")})
    config = config.model_copy(update=dict(app_env="testing"))
    servicio = ServicioBootstrapAdmin(config)
    with servicio._motor.connect() as db:
        assert db.scalar(text("SELECT current_database()")) == base.postgres_db
        assert db.scalar(select(func.count()).select_from(Usuario)) == 0
        pin = db.scalar(text("SELECT system_identifier::text FROM pg_catalog.pg_control_system()"))
    servicio._config = servicio._config.model_copy(update=dict(auth_bootstrap_cluster_id=pin))
    clases = (EventoAutenticacion, TokenCsrf, ContextoCsrf, Sesion, LimiteAutenticacion, Usuario)
    ids = {clase: set() for clase in clases}
    candado = Lock()

    def recordar(db, contexto):
        if db.get_bind().pool is servicio._motor.pool:
            with candado:
                for fila in db.new:
                    if type(fila) in ids and fila.id is not None:
                        ids[type(fila)].add(fila.id)

    event.listen(Session, "after_flush", recordar)
    e = dict(servicio=servicio, config=config, ids=ids, clave=generar_secreto(),
             correo=f"bootstrap-{uuid4()}@example.invalid")
    e["destino"] = acreditar_fixture(servicio)
    try:
        yield e
    finally:
        event.remove(Session, "after_flush", recordar)
        try:
            with servicio._motor.begin() as db:
                for clase in clases:
                    db.execute(delete(clase).where(clase.id.in_(ids[clase])))
        finally:
            servicio.cerrar()


def preparar(e):
    return e["servicio"].preparar(nombre="Administrador de ensayo",
        correo="  " + e["correo"].upper() + "  ", contrasena=e["clave"], confirmacion=e["clave"])


def crear(e):
    return e["servicio"].crear(preparar(e), destino=e["destino"],
                               confirmar_destino=e["destino"].confirmacion)


def contar(e, clase):
    with e["servicio"]._motor.connect() as db:
        return db.scalar(select(func.count()).select_from(clase))


def test_admin_y_actor_persistidos_login_me_logout_reales(persistente, caplog):
    e = persistente
    resultado = crear(e)
    with ExitStack() as recursos:
        lector = crear_motor_bd(e["config"])
        recursos.callback(lector.dispose)
        db = recursos.enter_context(Session(lector))  # Pool/conexión distintos del creador.
        usuario = db.get(Usuario, resultado.usuario_id)
        evento = db.get(EventoAutenticacion, resultado.evento_id)
        assert usuario.correo == e["correo"] and usuario.rol == "admin" and usuario.activo
        assert e["servicio"]._contrasenas.verificar(usuario.hash_contrasena, e["clave"].get_secret_value())
        assert usuario.hash_contrasena != e["clave"].get_secret_value()
        assert evento.tipo_evento == "admin_bootstrap" and evento.resultado == "success"
        assert evento.motivo == "initial_admin_created" and evento.usuario_id == usuario.id
        assert evento.actor_tipo == "postgresql_role"
        assert evento.actor_id == str(e["destino"].identidad.operador_oid)
        assert evento.sesion_id is None and evento.ip_verificada_digest is None
        texto = repr(vars(evento)) + repr(resultado) + caplog.text
        assert e["clave"].get_secret_value() not in texto and usuario.hash_contrasena not in texto
    login = ServicioLogin(e["servicio"]._motor, e["config"], capacidad_argon2=1)
    with Session(e["servicio"]._motor) as db, transaccion_seguridad(db):
        csrf = ServicioCsrf(db, e["config"])
        anonimo = csrf.crear_anonimo()
        token = csrf.emitir_token(anonimo=anonimo.secreto)
    contexto = login.validar_contexto(PruebaAnonimaLogin(anonimo.secreto, token.token),
                                      ip=ip_controlada(e["config"]))
    autenticado = login.autenticar(CredencialesLogin(e["correo"], e["clave"]), contexto)
    assert isinstance(autenticado, LoginConfirmado) and autenticado.usuario.role == "admin"
    referencia = ReferenciaSesion(autenticado.sesion.credencial)
    assert ServicioConsultaSesion(e["servicio"]._motor).consultar(referencia).id == resultado.usuario_id
    with Session(e["servicio"]._motor) as db, transaccion_seguridad(db):
        token = ServicioCsrf(db, e["config"]).emitir_token(sesion=referencia.credencial)
    assert ServicioLogout(e["servicio"]._motor, e["config"]).cerrar(referencia, token=token.token).revocada


def test_repeticion_y_borrado_posterior_no_habilitan_recuperacion(persistente):
    e = persistente
    resultado = crear(e)
    for borrar in (False, True):
        if borrar:
            with e["servicio"]._motor.begin() as db:
                db.execute(delete(Usuario).where(Usuario.id == resultado.usuario_id))
        with pytest.raises(ErrorBootstrap) as error:
            crear(e)
        assert error.value.codigo == C.INSTALACION_NO_VACIA
    with Session(e["servicio"]._motor) as db:
        evento = db.get(EventoAutenticacion, resultado.evento_id)
        assert evento.usuario_id is None and evento.actor_id is not None


@pytest.mark.parametrize("rol,activo", [("admin", True), ("agent", True), ("admin", False), ("agent", False)])
def test_usuario_preexistente_impide_alta_sin_afectar_sesiones(persistente, rol, activo):
    e = persistente
    resultado = crear(e)
    with Session(e["servicio"]._motor) as db, transaccion_seguridad(db):
        from app.seguridad.sesiones import ServicioSesiones
        sesion = ServicioSesiones(db).crear(resultado.usuario_id)
        usuario = db.get(Usuario, resultado.usuario_id)
        usuario.rol, usuario.activo = rol, activo
    with pytest.raises(ErrorBootstrap):
        crear(e)
    with Session(e["servicio"]._motor) as db:
        assert db.get(Sesion, sesion.id).revocada_en is None
        usuario = db.get(Usuario, resultado.usuario_id)
        assert usuario.rol == rol and usuario.activo == activo


@pytest.mark.parametrize("fallo", ["auditoria", "insercion", "commit"])
def test_fallos_reales_revierten_usuario_y_evento(persistente, fallo, monkeypatch):
    e = persistente
    if fallo == "auditoria":
        def fallar(self, **datos):
            self.db.execute(text("SELECT 1/0"))
        monkeypatch.setattr(ServicioAuditoria, "registrar", fallar)

    def antes_flush(db, contexto, instancias):
        if db.get_bind().pool is e["servicio"]._motor.pool and fallo == "insercion":
            for fila in db.new:
                if isinstance(fila, Usuario):
                    fila.rol = "invalido"

    def antes_commit(db):
        if db.get_bind().pool is e["servicio"]._motor.pool and fallo == "commit":
            db.execute(text("CREATE TEMP TABLE fallo_bootstrap (n int UNIQUE DEFERRABLE "
                            "INITIALLY DEFERRED) ON COMMIT DROP"))
            db.execute(text("INSERT INTO fallo_bootstrap VALUES (1),(1)"))

    event.listen(Session, "before_flush", antes_flush)
    event.listen(Session, "before_commit", antes_commit)
    try:
        with pytest.raises(ErrorSeguridad) as error:
            crear(e)
        assert error.value.codigo in {CodigoSeguridad.TRANSACCION, CodigoSeguridad.INFRAESTRUCTURA}
    finally:
        event.remove(Session, "before_flush", antes_flush)
        event.remove(Session, "before_commit", antes_commit)
    assert contar(e, Usuario) == 0
    with Session(e["servicio"]._motor) as db:
        assert db.scalar(select(func.count()).select_from(EventoAutenticacion).where(
            EventoAutenticacion.tipo_evento == "admin_bootstrap")) == 0


@pytest.mark.parametrize("caso", ["cluster", "revision", "restriccion", "operador"])
def test_precondiciones_sql_reales_fallan_cerradas(persistente, caso):
    e = persistente
    servicio = e["servicio"]
    with Session(servicio._motor) as db:
        db.begin()
        config = servicio._config
        try:
            if caso == "cluster":
                servicio._config = config.model_copy(update=dict(auth_bootstrap_cluster_id="1"))
            elif caso == "revision":
                db.execute(text("UPDATE public.alembic_version SET version_num='0004_bootstrap_csrf'"))
            elif caso == "restriccion":
                db.execute(text("ALTER TABLE public.eventos_autenticacion DROP CONSTRAINT "
                                "ck_eventos_autenticacion_actor_externo_valido"))
            else:
                db.execute(text("SET LOCAL SESSION AUTHORIZATION pg_read_all_data"))
                servicio._config = config.model_copy(update=dict(postgres_user="pg_read_all_data"))
            with pytest.raises(ErrorBootstrap) as error:
                servicio._identificar(db)
            assert error.value.codigo == ({"cluster": C.DESTINO, "revision": C.ESQUEMA,
                "restriccion": C.ESQUEMA, "operador": C.AUTORIZACION}[caso])
        finally:
            db.rollback()
            servicio._config = config
    assert contar(e, Usuario) == 0


def test_restriccion_actor_real_y_downgrade_protege_auditoria(persistente):
    e = persistente
    with pytest.raises(IntegrityError):
        with Session(e["servicio"]._motor) as db, db.begin():
            db.add(EventoAutenticacion(tipo_evento="admin_bootstrap", resultado="success"))
    resultado = crear(e)
    from alembic import command
    from alembic.config import Config
    config = Config("alembic.ini")
    with e["servicio"]._motor.connect() as conexion:
        config.attributes["connection"] = conexion
        with pytest.raises(DBAPIError) as error:
            command.downgrade(config, "0004_bootstrap_csrf")
        assert error.value.orig.sqlstate == "P0001"
        conexion.rollback()
    with Session(e["servicio"]._motor) as db:
        assert db.get(EventoAutenticacion, resultado.evento_id).actor_id is not None


def test_timeout_lock_real_sin_alta_parcial(persistente):
    e = persistente
    preparado = preparar(e)
    with ThreadPoolExecutor(1) as pool:
        with Session(e["servicio"]._motor) as db, transaccion_seguridad(db):
            db.execute(text("LOCK TABLE public.usuarios IN SHARE ROW EXCLUSIVE MODE"))
            futuro = pool.submit(e["servicio"].crear, preparado, destino=e["destino"],
                                 confirmar_destino=e["destino"].confirmacion)
            with pytest.raises(ErrorSeguridad) as error:
                futuro.result(timeout=10)
            assert error.value.codigo == CodigoSeguridad.TRANSACCION
    assert contar(e, Usuario) == 0


def test_insert_externo_impide_bootstrap_despues_de_esperar(persistente):
    e = persistente
    preparado = preparar(e)
    listo, pid = Event(), []

    def iniciado(db, transaccion, conexion):
        if db.get_bind().pool is e["servicio"]._motor.pool and not pid:
            pid.append(conexion.scalar(text("SELECT pg_backend_pid()")))
            listo.set()

    with ThreadPoolExecutor(1) as pool:
        with Session(e["servicio"]._motor) as db, transaccion_seguridad(db):
            db.add(Usuario(nombre="Escritor externo", correo=f"{uuid4()}@example.invalid",
                hash_contrasena=preparado.hash_contrasena.get_secret_value(), rol="agent", activo=True))
            db.flush()
            event.listen(Session, "after_begin", iniciado)
            try:
                futuro = pool.submit(e["servicio"].crear, preparado, destino=e["destino"],
                                     confirmar_destino=e["destino"].confirmacion)
                assert listo.wait(5)
                esperar_bloqueado(e["servicio"]._motor, pid[0])
            finally:
                event.remove(Session, "after_begin", iniciado)
        with pytest.raises(ErrorBootstrap) as error:
            futuro.result(timeout=5)
        assert error.value.codigo == C.INSTALACION_NO_VACIA
    assert contar(e, Usuario) == 1


def test_deadlock_real_rechaza_sin_usuario_o_evento_residual(persistente):
    e = persistente
    preparado = preparar(e)
    adquirido, continuar, pid = Event(), Event(), []

    def iniciado(db, transaccion, conexion):
        if db.get_bind().pool is e["servicio"]._motor.pool and db is not externo:
            pid.append(conexion.scalar(text("SELECT pg_backend_pid()")))
            conexion.execute(text("SET LOCAL deadlock_timeout='100ms'"))

    def tras_lock(conexion, cursor, sentencia, parametros, contexto, muchos):
        if sentencia == "LOCK TABLE public.usuarios IN SHARE ROW EXCLUSIVE MODE":
            adquirido.set()
            assert continuar.wait(5)

    with ThreadPoolExecutor(1) as pool:
        with Session(e["servicio"]._motor) as externo:
            externo.begin()
            event.listen(Session, "after_begin", iniciado)
            event.listen(e["servicio"]._motor, "after_cursor_execute", tras_lock)
            try:
                # Adquirir su conexión antes de arrancar el coordinador.
                externo.connection()
                pid.clear()
                futuro = pool.submit(e["servicio"].crear, preparado, destino=e["destino"],
                                     confirmar_destino=e["destino"].confirmacion)
                assert adquirido.wait(5)
                externo.execute(text("LOCK TABLE public.eventos_autenticacion IN ACCESS EXCLUSIVE MODE"))
                continuar.set()
                esperar_bloqueado(e["servicio"]._motor, pid[0])
                # Ciclo: bootstrap tiene usuarios y espera auditoría; externo
                # tiene auditoría y espera usuarios. Solo recursos de esta base.
                externo.add(Usuario(nombre="Externo", correo=f"{uuid4()}@example.invalid",
                    hash_contrasena=preparado.hash_contrasena.get_secret_value(), rol="agent", activo=True))
                externo.flush()
            finally:
                continuar.set()
                externo.rollback()
                event.remove(e["servicio"]._motor, "after_cursor_execute", tras_lock)
                event.remove(Session, "after_begin", iniciado)
        with pytest.raises(ErrorSeguridad) as error:
            futuro.result(timeout=5)
        assert error.value.codigo == CodigoSeguridad.TRANSACCION
    assert contar(e, Usuario) == 0


def test_servidor_sin_tls_no_se_acredita_por_configuracion(persistente):
    servicio = persistente["servicio"]
    servicio._config = servicio._config.model_copy(update=dict(postgres_sslmode="verify-full"))
    with pytest.raises(ErrorBootstrap) as error:
        servicio.verificar_destino()
    assert error.value.codigo == C.CANAL


def test_fallo_real_conexion_persistente_saneado(persistente):
    e = persistente
    config = e["servicio"]._config.model_copy(update=dict(postgres_db="synapdesk_auth07_sec01a_" + uuid4().hex))
    servicio = ServicioBootstrapAdmin(config)
    try:
        destino = DestinoAutorizado(e["destino"].identidad, "fixture", servicio._emisor)
        preparado = servicio.preparar(nombre="Ensayo", correo="a@example.invalid",
                                     contrasena=e["clave"], confirmacion=e["clave"])
        with pytest.raises(ErrorSeguridad) as error:
            servicio.crear(preparado, destino=destino, confirmar_destino="fixture")
        assert error.value.codigo == CodigoSeguridad.INFRAESTRUCTURA
        assert config.postgres_password.get_secret_value() not in str(error.value)
        assert config.postgres_db not in str(error.value)
    finally:
        servicio.cerrar()


def proceso_alta(datos, barrera, salida):
    servicio = ServicioBootstrapAdmin(Configuracion(_env_file=None, **datos))
    clave = generar_secreto()
    try:
        destino = acreditar_fixture(servicio)
        preparado = servicio.preparar(nombre="Inicial", correo=f"{uuid4()}@example.invalid",
                                     contrasena=clave, confirmacion=clave)
        barrera.wait(timeout=10)
        try:
            r = servicio.crear(preparado, destino=destino, confirmar_destino=destino.confirmacion)
            salida.put(("creado", r.usuario_id, r.evento_id))
        except ErrorBootstrap as error:
            salida.put((error.codigo.value, None, None))
    finally:
        servicio.cerrar()


def test_dos_procesos_un_admin_y_un_evento_confirmados(persistente):
    e = persistente
    ctx = get_context("spawn")
    salida, barrera = ctx.Queue(), ctx.Barrier(2)
    procesos = [ctx.Process(target=proceso_alta,
        args=(e["servicio"]._config.model_dump(), barrera, salida)) for _ in range(2)]
    resultados = []
    try:
        for p in procesos:
            p.start()
        for _ in procesos:
            r = salida.get(timeout=15)
            resultados.append(r)
            if r[0] == "creado":
                e["ids"][Usuario].add(r[1])
                e["ids"][EventoAutenticacion].add(r[2])
    finally:
        for p in procesos:
            p.join(10)
            if p.is_alive():
                p.terminate()
                p.join(5)
        salida.close()
    assert all(p.exitcode == 0 for p in procesos)
    assert sorted(r[0] for r in resultados) == [C.INSTALACION_NO_VACIA.value, "creado"]
    assert contar(e, Usuario) == 1
    with Session(e["servicio"]._motor) as db:
        assert db.scalar(select(func.count()).select_from(EventoAutenticacion).where(
            EventoAutenticacion.tipo_evento == "admin_bootstrap")) == 1
