"""Preparación no persistente: SQL/locks y rollback reales, no alta activada."""

from multiprocessing import get_context
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.configuracion import Configuracion
from app.persistencia.modelos import EventoAutenticacion, Sesion, Usuario
from app.seguridad.bootstrap_admin import CodigoBootstrap as C, ErrorBootstrap, ServicioBootstrapAdmin
from app.seguridad.secretos import generar_secreto
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import ErrorSeguridad, transaccion_seguridad


@pytest.fixture
def entorno_bootstrap(configuracion_bd_test):
    assert configuracion_bd_test.postgres_port == 5433
    config = configuracion_bd_test.model_copy(update=dict(auth_argon2_memoria_kib=1024,
        auth_argon2_iteraciones=1, auth_argon2_paralelismo=1))
    servicio = ServicioBootstrapAdmin(config)
    with servicio._motor.connect() as db:
        assert db.scalar(text("SELECT current_database()")) == config.postgres_db
        assert config.postgres_db.startswith("synapdesk_auth07_sec01a_")
        assert db.scalar(select(func.count()).select_from(Usuario)) == 0
    e = dict(config=config, servicio=servicio, clave=generar_secreto(), usuarios=[], sesiones=[])
    try:
        yield e
    finally:
        try:
            with servicio._motor.begin() as db:
                db.execute(delete(Sesion).where(Sesion.id.in_(e["sesiones"])))
                db.execute(delete(Usuario).where(Usuario.id.in_(e["usuarios"])))
        finally:
            servicio.cerrar()


def preparar(e, **cambios):
    return e["servicio"].preparar(**(dict(nombre="Administrador provisional",
        correo=f"  ADMIN-{uuid4()}@EXAMPLE.INVALID  ", contrasena=e["clave"],
        confirmacion=e["clave"]) | cambios))


def cantidad(e, modelo):
    with e["servicio"]._motor.connect() as db:
        return db.scalar(select(func.count()).select_from(modelo))


def test_admin_provisional_argon2_activo_normalizado_y_rollback_obligatorio(entorno_bootstrap, caplog):
    e = entorno_bootstrap
    preparado = preparar(e)
    visto = []
    sin_commit = []

    def inspeccionar(db, contexto):
        if db.get_bind().pool is e["servicio"]._motor.pool:
            usuario = db.scalar(select(Usuario))
            assert usuario.rol == "admin" and usuario.activo
            assert usuario.correo == preparado.correo == preparado.correo.strip().lower()
            assert usuario.hash_contrasena != e["clave"].get_secret_value()
            assert e["servicio"]._contrasenas.verificar(usuario.hash_contrasena,
                                                      e["clave"].get_secret_value())
            visto.append(usuario.id)

    def no_commit(db):
        if db.get_bind().pool is e["servicio"]._motor.pool:
            sin_commit.append(True)

    event.listen(Session, "after_flush", inspeccionar)
    event.listen(Session, "before_commit", no_commit)
    try:
        resultado = e["servicio"].ensayar(preparado, confirmar_destino=e["servicio"].destino)
    finally:
        event.remove(Session, "after_flush", inspeccionar)
        event.remove(Session, "before_commit", no_commit)
    assert visto and not sin_commit and resultado.persistido is False
    assert cantidad(e, Usuario) == 0
    assert e["clave"].get_secret_value() not in repr(resultado) + caplog.text
    assert preparado.hash_contrasena.get_secret_value() not in caplog.text


@pytest.mark.parametrize("rol,activo", [("admin", True), ("agent", True), ("admin", False), ("agent", False)])
def test_cualquier_usuario_cierra_estado_inicial_y_conserva_sesion(entorno_bootstrap, rol, activo):
    e = entorno_bootstrap
    with Session(e["servicio"]._motor) as db, transaccion_seguridad(db):
        usuario = Usuario(nombre="Preexistente", correo=f"{uuid4()}@example.invalid",
            hash_contrasena=e["servicio"]._contrasenas.generar_hash(e["clave"].get_secret_value()),
            rol=rol, activo=True)
        db.add(usuario)
        db.flush()
        e["usuarios"].append(usuario.id)
        sesion = ServicioSesiones(db).crear(usuario.id)
        e["sesiones"].append(sesion.id)
        usuario.activo = activo
    with pytest.raises(ErrorBootstrap) as error:
        e["servicio"].ensayar(preparar(e), confirmar_destino=e["servicio"].destino)
    assert error.value.codigo == C.INSTALACION_NO_VACIA
    assert cantidad(e, Usuario) == 1 and cantidad(e, Sesion) == 1
    with Session(e["servicio"]._motor) as db:
        assert db.get(Usuario, e["usuarios"][0]).activo == activo
        assert db.get(Sesion, sesion.id).revocada_en is None


def test_sin_destino_aprobado_no_hay_alta_ni_auditoria_ficticia(entorno_bootstrap):
    e = entorno_bootstrap
    eventos = cantidad(e, EventoAutenticacion)
    with pytest.raises(ErrorBootstrap) as error:
        e["servicio"].crear(preparar(e))
    assert error.value.codigo == C.DESTINO
    assert cantidad(e, Usuario) == 0 and cantidad(e, EventoAutenticacion) == eventos


def test_fallo_insert_real_revierte_candidato(entorno_bootstrap):
    e = entorno_bootstrap

    def invalidar(db, contexto, instancias):
        if db.get_bind().pool is e["servicio"]._motor.pool:
            for fila in db.new:
                if isinstance(fila, Usuario):
                    fila.rol = "fuera_del_catalogo"

    event.listen(Session, "before_flush", invalidar)
    try:
        with pytest.raises(ErrorSeguridad):
            e["servicio"].ensayar(preparar(e), confirmar_destino=e["servicio"].destino)
    finally:
        event.remove(Session, "before_flush", invalidar)
    assert cantidad(e, Usuario) == 0


def test_fallo_despues_insert_revierte_sin_commit(entorno_bootstrap):
    e = entorno_bootstrap

    def fallar(db, contexto):
        if db.get_bind().pool is e["servicio"]._motor.pool:
            db.execute(text("SELECT 1/0"))

    event.listen(Session, "after_flush", fallar)
    try:
        with pytest.raises(ErrorSeguridad):
            e["servicio"].ensayar(preparar(e), confirmar_destino=e["servicio"].destino)
    finally:
        event.remove(Session, "after_flush", fallar)
    assert cantidad(e, Usuario) == 0


@pytest.mark.parametrize("caso", ["principal", "puerto", "host", "base", "confirmacion"])
def test_destino_no_autorizado_rechazado_antes_de_conectar(entorno_bootstrap, caso, monkeypatch):
    e = entorno_bootstrap
    config = e["config"].model_copy(update={
        "principal": dict(app_env="development"), "puerto": dict(postgres_port=5432),
        "host": dict(postgres_host="example.invalid"), "base": dict(postgres_db="desconocida"),
        "confirmacion": {},
    }[caso])
    servicio = ServicioBootstrapAdmin(config)
    try:
        def no_conectar(*args, **kwargs):
            pytest.fail("Se intentó conectar a un destino no autorizado.")
        monkeypatch.setattr(servicio._motor, "connect", no_conectar)
        with pytest.raises(ErrorBootstrap) as error:
            servicio.ensayar(servicio.preparar(nombre="Ensayo", correo="a@example.invalid",
                contrasena=e["clave"], confirmacion=e["clave"]),
                confirmar_destino="incorrecto" if caso == "confirmacion" else servicio.destino)
        assert error.value.codigo == C.DESTINO
    finally:
        servicio.cerrar()


@pytest.mark.parametrize("campo", ["postgres_db", "postgres_user"])
def test_identidad_real_de_conexion_no_coincide_cierra_sin_insertar(entorno_bootstrap, campo):
    e = entorno_bootstrap
    servicio = e["servicio"]
    preparado = preparar(e)
    cambio = "synapdesk_auth07_sec01a_" + uuid4().hex if campo == "postgres_db" else "otro_usuario"
    servicio._config = servicio._config.model_copy(update={campo: cambio})
    with pytest.raises(ErrorBootstrap) as error:
        servicio.ensayar(preparado, confirmar_destino=servicio.destino)
    assert error.value.codigo == C.DESTINO and cantidad(e, Usuario) == 0


def test_base_inaccesible_error_saneado(entorno_bootstrap):
    e = entorno_bootstrap
    config = e["config"].model_copy(update=dict(postgres_db="synapdesk_auth07_sec01a_" + uuid4().hex))
    servicio = ServicioBootstrapAdmin(config)
    try:
        with pytest.raises(ErrorSeguridad) as error:
            servicio.ensayar(servicio.preparar(nombre="Ensayo", correo="a@example.invalid",
                contrasena=e["clave"], confirmacion=e["clave"]), confirmar_destino=servicio.destino)
        assert config.postgres_db not in str(error.value)
        assert config.postgres_password.get_secret_value() not in str(error.value)
    finally:
        servicio.cerrar()


def test_insert_externo_serializa_y_estado_se_relee_tras_lock(entorno_bootstrap):
    e = entorno_bootstrap
    preparado = preparar(e)
    listo, pid = Event(), []

    def iniciado(db, transaccion, conexion):
        if db.get_bind().pool is e["servicio"]._motor.pool and not pid:
            pid.append(conexion.scalar(text("SELECT pg_backend_pid()")))
            listo.set()

    with ThreadPoolExecutor(1) as pool:
        with Session(e["servicio"]._motor) as db, transaccion_seguridad(db):
            # INSERT ordinario: no adquiere el lock del coordinador.
            usuario = Usuario(nombre="Otro escritor", correo=f"{uuid4()}@example.invalid",
                hash_contrasena=preparado.hash_contrasena.get_secret_value(), rol="agent", activo=True)
            db.add(usuario)
            db.flush()
            e["usuarios"].append(usuario.id)
            event.listen(Session, "after_begin", iniciado)
            try:
                futuro = pool.submit(e["servicio"].ensayar, preparado,
                                     confirmar_destino=e["servicio"].destino)
                assert listo.wait(5)
                fin = monotonic() + 5
                bloqueado = False
                while monotonic() < fin:
                    with e["servicio"]._motor.connect() as consulta:
                        bloqueado = consulta.scalar(text(
                            "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:p"), {"p": pid[0]})
                    if bloqueado:
                        break
                    sleep(0.01)
                assert bloqueado
            finally:
                event.remove(Session, "after_begin", iniciado)
        with pytest.raises(ErrorBootstrap) as error:
            futuro.result(timeout=5)
        assert error.value.codigo == C.INSTALACION_NO_VACIA
    assert cantidad(e, Usuario) == 1


def proceso_ensayo(configuracion, retener, liberar, cola):
    # Proceso spawn independiente; configuración de pruebas por IPC, nunca argv.
    servicio = ServicioBootstrapAdmin(Configuracion(_env_file=None, **configuracion))
    clave = generar_secreto()
    preparado = servicio.preparar(nombre="Provisional", correo=f"{uuid4()}@example.invalid",
                                 contrasena=clave, confirmacion=clave)
    pid = []

    def iniciado(db, transaccion, conexion):
        if db.get_bind().pool is servicio._motor.pool and not pid:
            pid.append(conexion.scalar(text("SELECT pg_backend_pid()")))
            cola.put(("pid", pid[0]))

    def insertado(db, contexto):
        if db.get_bind().pool is servicio._motor.pool and retener:
            cola.put(("retiene", pid[0]))
            assert liberar.wait(10)

    event.listen(Session, "after_begin", iniciado)
    event.listen(Session, "after_flush", insertado)
    try:
        resultado = servicio.ensayar(preparado, confirmar_destino=servicio.destino)
        cola.put(("revertido", resultado.persistido))
    finally:
        event.remove(Session, "after_begin", iniciado)
        event.remove(Session, "after_flush", insertado)
        servicio.cerrar()


def test_dos_procesos_exclusion_postgresql_y_ningun_admin_confirmado(entorno_bootstrap):
    e = entorno_bootstrap
    ctx = get_context("spawn")
    liberar = ctx.Event()
    primera, segunda = ctx.Queue(), ctx.Queue()
    p1 = ctx.Process(target=proceso_ensayo, args=(e["config"].model_dump(), True, liberar, primera))
    p2 = ctx.Process(target=proceso_ensayo, args=(e["config"].model_dump(), False, liberar, segunda))
    p1.start()
    try:
        assert primera.get(timeout=10)[0] == "pid"
        assert primera.get(timeout=10)[0] == "retiene"
        p2.start()
        tipo, pid = segunda.get(timeout=10)
        assert tipo == "pid"
        fin = monotonic() + 5
        bloqueado = False
        while monotonic() < fin:
            with e["servicio"]._motor.connect() as db:
                bloqueado = db.scalar(text("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:p"),
                                      {"p": pid})
            if bloqueado:
                break
            sleep(0.01)
        assert bloqueado
        assert cantidad(e, Usuario) == 0  # Primer candidato aún no confirmado.
    finally:
        liberar.set()
        p1.join(10)
        if p2.pid is not None:
            p2.join(10)
        for proceso in (p1, p2):
            if proceso.is_alive():
                proceso.terminate()
                proceso.join(5)
        primera.close()
        segunda.close()
    assert p1.exitcode == p2.exitcode == 0
    assert cantidad(e, Usuario) == 0
