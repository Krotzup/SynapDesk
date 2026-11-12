from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event, local
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import ContextoCsrf, CuotaBootstrapCsrf as Q, LimiteAutenticacion, TokenCsrf
from app.seguridad.bootstrap_csrf import GLOBAL, LOCK_BOOTSTRAP, CuotaBootstrapAgotada, ServicioBootstrapCsrf
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.secretos import generar_secreto
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad
from pruebas.bootstrap_auxiliar import configuracion_ensayo, ip_controlada


@pytest.fixture
def entorno_bootstrap(configuracion_bd_test):
    motor = crear_motor_bd(configuracion_bd_test)
    config = configuracion_ensayo()
    e = dict(motor=motor, config=config, ahora=datetime(2026, 11, 12, tzinfo=UTC))
    e["reloj"] = lambda db: e["ahora"]
    e["ip"] = ip_controlada(config)
    with motor.connect() as db:
        # Este fixture de commits reales exige la base exclusiva del validador.
        nombre = db.scalar(text("SELECT current_database()"))
        assert nombre.startswith("synapdesk_auth07_sec01a_")
        assert configuracion_bd_test.postgres_port == 5433
    try:
        yield e
    finally:
        with motor.begin() as db:
            db.execute(delete(Q))
            db.execute(delete(TokenCsrf).where(TokenCsrf.contexto_id.in_(
                select(ContextoCsrf.id).where(ContextoCsrf.tipo == "anonymous"))))
            db.execute(delete(ContextoCsrf).where(ContextoCsrf.tipo == "anonymous"))
        motor.dispose()


def servicio(e, **politica):
    config = e["config"].model_copy(deep=True)
    if politica:
        from app.seguridad.politica_bootstrap import PoliticaBootstrap
        config.auth_bootstrap = PoliticaBootstrap(**(config.auth_bootstrap.model_dump() | politica))
    return ServicioBootstrapCsrf(e["motor"], config, e["reloj"])


def emitir(e, secreto=None, **politica):
    return servicio(e, **politica).emitir(ip=e["ip"], anonimo=secreto)


def filas(e, ambito=None):
    with Session(e["motor"]) as db:
        q = select(Q)
        if ambito:
            q = q.where(Q.ambito == ambito)
        return db.scalars(q).all()


def cantidad(e, clase):
    with Session(e["motor"]) as db:
        return db.scalar(select(func.count()).select_from(clase))


def test_creacion_reserva_cinco_cuotas_y_reutilizacion_no_crea_contexto(entorno_bootstrap):
    e = entorno_bootstrap
    uno = emitir(e)
    dos = emitir(e, uno.contexto_nuevo.secreto)
    assert dos.contexto_id == uno.contexto_id and dos.contexto_nuevo is None
    assert cantidad(e, ContextoCsrf) == 1
    assert cantidad(e, TokenCsrf) == 2
    assert {f.ambito: f.usados for f in filas(e)} == dict(
        intentos_global=2, intentos_ip=2, contextos_global=1, contextos_ip=1,
        emisiones_contexto=2)
    assert cantidad(e, LimiteAutenticacion) == 0


@pytest.mark.parametrize("ambito", ["contextos_ip", "contextos_global", "intentos_ip", "intentos_global"])
def test_limites_admision_no_crean_reemplazos(entorno_bootstrap, ambito):
    e = entorno_bootstrap
    limites = {ambito: dict(cantidad=1, segundos=60)}
    emitir(e, **limites)
    with pytest.raises(CuotaBootstrapAgotada) as error:
        emitir(e, **limites)
    assert error.value.ambito == ambito and error.value.retry_after == 60
    assert cantidad(e, ContextoCsrf) == 1
    assert filas(e, ambito)[0].usados == 1


def test_aislamiento_ip_y_global_no_crea_filas_al_rechazar(entorno_bootstrap):
    e = entorno_bootstrap
    s = servicio(e, contextos_ip=dict(cantidad=1, segundos=60),
                 intentos_global=dict(cantidad=3, segundos=60))
    s.emitir(ip=e["ip"])
    with pytest.raises(CuotaBootstrapAgotada):
        s.emitir(ip=e["ip"])
    s.emitir(ip=ip_controlada(e["config"], "198.51.100.8"))
    antes = len(filas(e))
    for n in range(9, 20):
        with pytest.raises(CuotaBootstrapAgotada) as error:
            s.emitir(ip=ip_controlada(e["config"], f"198.51.100.{n}"))
        assert error.value.ambito == "intentos_global"
    assert len(filas(e)) == antes
    assert cantidad(e, ContextoCsrf) == 2


def test_cuota_contexto_sigue_al_secreto_aunque_cambie_ip(entorno_bootstrap):
    e = entorno_bootstrap
    s = servicio(e, emisiones_contexto=dict(cantidad=8, segundos=60))
    a, b = s.emitir(ip=e["ip"]), s.emitir(ip=e["ip"])
    for _ in range(7):
        s.emitir(ip=e["ip"], anonimo=a.contexto_nuevo.secreto)
    with pytest.raises(CuotaBootstrapAgotada) as error:
        s.emitir(ip=ip_controlada(e["config"], "198.51.100.8"), anonimo=a.contexto_nuevo.secreto)
    assert error.value.ambito == "emisiones_contexto"
    assert s.emitir(ip=e["ip"], anonimo=b.contexto_nuevo.secreto).contexto_id == b.contexto_id
    assert cantidad(e, ContextoCsrf) == 2


def test_ventana_discreta_y_retry_fraccionario(entorno_bootstrap):
    e = entorno_bootstrap
    s = servicio(e, intentos_ip=dict(cantidad=1, segundos=60))
    s.emitir(ip=e["ip"])
    e["ahora"] += timedelta(seconds=59, microseconds=500000)
    with pytest.raises(CuotaBootstrapAgotada) as error:
        s.emitir(ip=e["ip"])
    assert error.value.retry_after == 1
    e["ahora"] += timedelta(microseconds=500000)
    s.emitir(ip=e["ip"])
    assert filas(e, "intentos_ip")[0].usados == 1


@pytest.mark.parametrize("valor", ["uuid", "secreto_inexistente", "vacio"])
def test_identidad_arbitraria_se_cuenta_sin_crear_contexto(entorno_bootstrap, valor):
    e = entorno_bootstrap
    secreto = {"uuid": str(uuid4()), "secreto_inexistente": generar_secreto(), "vacio": ""}[valor]
    with pytest.raises(ErrorSeguridad) as error:
        emitir(e, secreto)
    assert error.value.codigo == C.CONTEXTO_INVALIDO
    assert filas(e, "intentos_global")[0].usados == 1
    assert cantidad(e, ContextoCsrf) == 0


@pytest.mark.parametrize("ip", [None, "198.51.100.7", bytes(32)])
def test_ip_sin_acreditar_no_toca_persistencia(entorno_bootstrap, ip):
    e = entorno_bootstrap
    with pytest.raises(ErrorSeguridad) as error:
        servicio(e).emitir(ip=ip)
    assert error.value.codigo == C.IP_NO_VERIFICABLE and not filas(e)


def test_tokens_vigentes_no_se_expulsan_y_reserva_sobrevive(entorno_bootstrap):
    e = entorno_bootstrap
    uno = emitir(e)
    for _ in range(7):
        emitir(e, uno.contexto_nuevo.secreto)
    with pytest.raises(ErrorSeguridad) as error:
        emitir(e, uno.contexto_nuevo.secreto)
    assert error.value.codigo == C.LIMITE_TOKENS
    assert cantidad(e, TokenCsrf) == 8
    assert filas(e, "emisiones_contexto")[0].usados == 9
    with Session(e["motor"]) as db, db.begin():
        ServicioCsrf(db, e["config"], e["reloj"]).validar_token(
            uno.token.token, anonimo=uno.contexto_nuevo.secreto)


def test_concurrencia_ocho_conexiones_no_excede_global(entorno_bootstrap):
    e = entorno_bootstrap
    s = servicio(e, intentos_global=dict(cantidad=3, segundos=60))
    barrera = Barrier(8)
    pids = set()
    hilo = local()

    def observar(conexion, cursor, statement, parameters, context, executemany):
        if "pg_advisory_xact_lock" in statement and not getattr(hilo, "observado", False):
            hilo.observado = True
            pids.add(conexion.connection.driver_connection.info.backend_pid)
            barrera.wait(timeout=10)

    def intentar(n):
        try:
            s.emitir(ip=ip_controlada(e["config"], f"198.51.100.{n+10}"))
            return True
        except CuotaBootstrapAgotada:
            return False
    event.listen(e["motor"], "before_cursor_execute", observar)
    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            resultados = list(ex.map(intentar, range(8)))
    finally:
        event.remove(e["motor"], "before_cursor_execute", observar)
    assert len(pids) == 8
    assert sum(resultados) == 3
    assert cantidad(e, ContextoCsrf) == 3
    assert filas(e, "intentos_global")[0].usados == 3


def test_concurrencia_emision_no_excede_tokens(entorno_bootstrap):
    e = entorno_bootstrap
    uno = emitir(e)
    barrera = Barrier(12)

    def intentar(_):
        barrera.wait(timeout=10)
        try:
            emitir(e, uno.contexto_nuevo.secreto)
            return True
        except (CuotaBootstrapAgotada, ErrorSeguridad):
            return False
    with ThreadPoolExecutor(max_workers=12) as ex:
        assert sum(ex.map(intentar, range(12))) == 7
    assert cantidad(e, TokenCsrf) == 8
    assert filas(e, "emisiones_contexto")[0].usados == 12


def test_motores_independientes_comparten_admision(entorno_bootstrap, configuracion_bd_test):
    e = entorno_bootstrap
    otro = crear_motor_bd(configuracion_bd_test)
    config = e["config"].model_copy(deep=True)
    from app.seguridad.politica_bootstrap import PoliticaBootstrap
    config.auth_bootstrap = PoliticaBootstrap(**(config.auth_bootstrap.model_dump() | {
        "intentos_global": dict(cantidad=1, segundos=60)}))
    servicios = [ServicioBootstrapCsrf(m, config, e["reloj"]) for m in (e["motor"], otro)]
    barrera = Barrier(2)

    def intentar(s):
        barrera.wait(timeout=5)
        try:
            s.emitir(ip=e["ip"])
            return True
        except CuotaBootstrapAgotada:
            return False
    try:
        with ThreadPoolExecutor(max_workers=2) as ex:
            assert sum(ex.map(intentar, servicios)) == 1
    finally:
        otro.dispose()
    assert filas(e, "intentos_global")[0].usados == 1


def test_rollback_real_emision_no_revierte_admision(entorno_bootstrap):
    e = entorno_bootstrap
    llamadas = []

    def fallar_commit(conexion):
        llamadas.append(True)
        if len(llamadas) == 2:
            # PostgreSQL falla realmente al confirmar la segunda transacción.
            conexion.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
            conexion.exec_driver_sql("SELECT 1 / 0")
    event.listen(e["motor"], "commit", fallar_commit)
    try:
        with pytest.raises(ErrorSeguridad):
            emitir(e)
    finally:
        event.remove(e["motor"], "commit", fallar_commit)
    assert filas(e, "intentos_global")[0].usados == 1
    assert filas(e, "contextos_global")[0].usados == 1
    assert cantidad(e, ContextoCsrf) == cantidad(e, TokenCsrf) == 0
    assert not filas(e, "emisiones_contexto")


def test_lock_timeout_real_distingue_indisponibilidad(entorno_bootstrap, caplog):
    e = entorno_bootstrap
    s = servicio(e, lock_timeout_ms=50)
    with e["motor"].begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": LOCK_BOOTSTRAP})
        with pytest.raises(ErrorSeguridad) as error:
            s.emitir(ip=e["ip"])
    assert error.value.codigo == C.TRANSACCION
    assert not filas(e) and not caplog.records
    assert emitir(e).contexto_nuevo is not None


def test_statement_timeout_real_no_es_cuota(entorno_bootstrap):
    e = entorno_bootstrap
    s = servicio(e, lock_timeout_ms=10, statement_timeout_ms=40)
    with pytest.raises(ErrorSeguridad) as error:
        with s._transaccion() as db:
            db.execute(text("SELECT pg_sleep(1)"))
    assert error.value.codigo == C.INFRAESTRUCTURA
    assert not filas(e)


def test_reloj_se_lee_despues_del_lock(entorno_bootstrap):
    e = entorno_bootstrap
    s = servicio(e, intentos_ip=dict(cantidad=1, segundos=60))
    s.emitir(ip=e["ip"])
    listo = Event()
    pid = []

    def observar(conexion, cursor, statement, parameters, context, executemany):
        if "pg_advisory_xact_lock" in statement:
            pid.append(conexion.connection.driver_connection.info.backend_pid)
            listo.set()

    with ThreadPoolExecutor(max_workers=1) as ex:
        with e["motor"].begin() as bloqueo:
            bloqueo.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": LOCK_BOOTSTRAP})
            event.listen(e["motor"], "before_cursor_execute", observar)
            try:
                futuro = ex.submit(s.emitir, ip=e["ip"])
                assert listo.wait(3)
                fin = monotonic() + 0.8
                while monotonic() < fin:
                    with e["motor"].connect() as db:
                        if db.scalar(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:p"),
                                     {"p": pid[0]}) == "Lock":
                            break
                    sleep(0.005)
                else:
                    pytest.fail("No se observó la espera real en PostgreSQL.")
                e["ahora"] += timedelta(seconds=60)
            finally:
                event.remove(e["motor"], "before_cursor_execute", observar)
        assert futuro.result(timeout=5).contexto_nuevo is not None


def test_admision_no_confirmada_revierte_sus_contadores(entorno_bootstrap):
    e = entorno_bootstrap
    s = servicio(e)
    with pytest.raises(RuntimeError):
        with s._transaccion() as db:
            s._consumir(db, "intentos_global", GLOBAL, e["ahora"])
            raise RuntimeError("rollback controlado")
    assert not filas(e)


def test_reserva_contexto_sobrevive_fallo_de_commit_emision(entorno_bootstrap):
    e = entorno_bootstrap
    uno = emitir(e)
    commits = []

    def fallar(conexion):
        commits.append(True)
        if len(commits) == 3:
            conexion.exec_driver_sql("SELECT 1 / 0")
    event.listen(e["motor"], "commit", fallar)
    try:
        with pytest.raises(ErrorSeguridad):
            emitir(e, uno.contexto_nuevo.secreto)
    finally:
        event.remove(e["motor"], "commit", fallar)
    assert cantidad(e, TokenCsrf) == 1
    assert filas(e, "emisiones_contexto")[0].usados == 2
    assert filas(e, "intentos_global")[0].usados == 2


def test_contexto_revocado_no_se_reemplaza(entorno_bootstrap):
    e = entorno_bootstrap
    uno = emitir(e)
    with Session(e["motor"]) as db, db.begin():
        ServicioCsrf(db, e["config"], e["reloj"]).invalidar_contexto(anonimo=uno.contexto_nuevo.secreto)
    with pytest.raises(ErrorSeguridad) as error:
        emitir(e, uno.contexto_nuevo.secreto)
    assert error.value.codigo == C.CONTEXTO_INVALIDO
    assert cantidad(e, ContextoCsrf) == 1


def test_conexion_terminada_no_se_confunde_con_cuota(entorno_bootstrap, caplog):
    e = entorno_bootstrap
    una_vez = []

    def terminar(conexion, cursor, statement, parameters, context, executemany):
        if "pg_advisory_xact_lock" in statement and not una_vez:
            una_vez.append(True)
            with e["motor"].connect() as otra:
                otra.execute(text("SELECT pg_terminate_backend(:pid)"),
                             {"pid": conexion.connection.driver_connection.info.backend_pid})
    event.listen(e["motor"], "before_cursor_execute", terminar)
    try:
        with pytest.raises(ErrorSeguridad) as error:
            emitir(e)
    finally:
        event.remove(e["motor"], "before_cursor_execute", terminar)
    assert error.value.codigo == C.INFRAESTRUCTURA
    assert not filas(e) and not caplog.records


@pytest.mark.parametrize("campo,valor", [("ambito", "login"), ("identidad", b"x"),
                                         ("usados", -1), ("usados", 1000001), ("fin", None)])
def test_restricciones_postgresql_reales(entorno_bootstrap, campo, valor):
    e = entorno_bootstrap
    datos = dict(ambito="intentos_ip", identidad=bytes(32), inicio=e["ahora"],
                 fin=e["ahora"]+timedelta(seconds=60), usados=1)
    datos[campo] = valor
    with pytest.raises(IntegrityError):
        with Session(e["motor"]) as db, db.begin():
            db.add(Q(**datos))


def test_pk_impide_duplicar_identidad(entorno_bootstrap):
    e = entorno_bootstrap
    emitir(e)
    with pytest.raises(IntegrityError):
        with Session(e["motor"]) as db, db.begin():
            db.add(Q(ambito="intentos_global", identidad=GLOBAL, inicio=e["ahora"],
                     fin=e["ahora"]+timedelta(seconds=60), usados=1))


def test_limpieza_acotada_no_elimina_tokens_validos(entorno_bootstrap):
    e = entorno_bootstrap
    uno = emitir(e)
    emitir(e)
    s = servicio(e, lote_limpieza=1)
    assert s.limpiar() == dict(cuotas=0, tokens=0, contextos=0)
    e["ahora"] += timedelta(seconds=601)
    resultado = s.limpiar()
    assert max(resultado.values()) <= 1
    assert cantidad(e, TokenCsrf) == 1 and cantidad(e, ContextoCsrf) == 2
    e["ahora"] += timedelta(seconds=300)
    for _ in range(12):
        s.limpiar()
    assert not filas(e)
    assert cantidad(e, TokenCsrf) == cantidad(e, ContextoCsrf) == 0
    with pytest.raises(ErrorSeguridad):
        emitir(e, uno.contexto_nuevo.secreto)
    assert cantidad(e, ContextoCsrf) == 0


@pytest.mark.parametrize("capacidad", ["max_contextos", "max_filas_tokens", "max_filas_cuota"])
def test_capacidad_cerrada_sin_expulsion(entorno_bootstrap, capacidad):
    e = entorno_bootstrap
    parametros = {capacidad: 5 if capacidad == "max_filas_cuota" else 1}
    if capacidad == "max_filas_tokens":
        parametros["max_contextos"] = 1
    s = servicio(e, **parametros)
    uno = s.emitir(ip=e["ip"])
    with pytest.raises(ErrorSeguridad) as error:
        s.emitir(ip=e["ip"], anonimo=uno.contexto_nuevo.secreto if capacidad == "max_filas_tokens" else None)
    assert error.value.codigo == C.INFRAESTRUCTURA
    assert cantidad(e, ContextoCsrf) == cantidad(e, TokenCsrf) == 1


def test_digests_y_resultados_no_exponen_secretos(entorno_bootstrap, caplog):
    e = entorno_bootstrap
    resultado = emitir(e)
    representacion = repr(resultado)
    assert resultado.token.token.get_secret_value() not in representacion
    assert resultado.contexto_nuevo.secreto.get_secret_value() not in representacion
    assert "198.51.100.7" not in representacion
    assert all(isinstance(f.identidad, bytes) and len(f.identidad) == 32 for f in filas(e))
    assert not caplog.records
