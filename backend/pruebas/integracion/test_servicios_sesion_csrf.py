from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from app.configuracion import Configuracion
from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import ContextoCsrf, Sesion, TokenCsrf, Usuario
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.secretos import digest_secreto, generar_secreto
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad, transaccion_seguridad


class RelojControlado:
    def __init__(self):
        self.ahora = datetime(2026, 11, 3, tzinfo=UTC)

    def __call__(self, db):
        return self.ahora


@pytest.fixture
def entorno_servicios(configuracion_bd_test):
    motor = crear_motor_bd(configuracion_bd_test)
    with Session(motor) as db, db.begin():
        usuario = Usuario(nombre="Prueba servicios", correo=f"servicios-{uuid4()}@example.invalid",
                          hash_contrasena="hash ficticio de persistencia", activo=True, rol="agent")
        db.add(usuario)
        db.flush()
        usuario_id = usuario.id
    entorno = {"motor": motor, "usuario": usuario_id, "reloj": RelojControlado(), "anonimos": [],
               "configuracion": Configuracion(_env_file=None, app_env="testing")}
    try:
        yield entorno
    finally:
        # Solo filas creadas por este fixture, incluso al fallar una prueba.
        with Session(motor) as db, db.begin():
            sesiones = select(Sesion.id).where(Sesion.usuario_id == usuario_id)
            contextos = select(ContextoCsrf.id).where(
                (ContextoCsrf.sesion_id.in_(sesiones)) | (ContextoCsrf.id.in_(entorno["anonimos"]))
            )
            db.execute(delete(TokenCsrf).where(TokenCsrf.contexto_id.in_(contextos)))
            db.execute(delete(ContextoCsrf).where(ContextoCsrf.id.in_(contextos)))
            db.execute(delete(Sesion).where(Sesion.usuario_id == usuario_id))
            db.execute(delete(Usuario).where(Usuario.id == usuario_id))
        motor.dispose()


@contextmanager
def operacion(entorno):
    with Session(entorno["motor"]) as db, transaccion_seguridad(db):
        yield (ServicioSesiones(db, entorno["reloj"]),
               ServicioCsrf(db, entorno["configuracion"], entorno["reloj"]), db)


def crear_sesion(entorno):
    with operacion(entorno) as (sesiones, _, _):
        resultado = sesiones.crear(entorno["usuario"])
    return resultado


def crear_anonimo(entorno):
    with operacion(entorno) as (_, csrf, _):
        resultado = csrf.crear_anonimo()
    entorno["anonimos"].append(resultado.id)
    return resultado


def esperar_lock(entorno, pid):
    limite = monotonic() + 3
    while monotonic() < limite:
        with entorno["motor"].connect() as conexion:
            if conexion.execute(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"),
                                  {"pid": pid}).scalar_one_or_none() == "Lock":
                return
        sleep(0.01)
    pytest.fail("La conexión independiente no llegó al bloqueo PostgreSQL esperado.")


def test_sesion_persiste_solo_digest_y_recupera_identidad_vigente(entorno_servicios, caplog):
    e = entorno_servicios
    uno, dos = crear_sesion(e), crear_sesion(e)
    assert uno.credencial != dos.credencial
    assert uno.credencial.get_secret_value() not in repr(uno)
    with operacion(e) as (sesiones, _, db):
        registro = db.get(Sesion, uno.id)
        assert registro.digest_credencial == digest_secreto(uno.credencial, C.SESION_INEXISTENTE)
        assert len(registro.digest_credencial) == 32
        assert registro.expira_en - registro.creado_en == timedelta(hours=8)
        assert sesiones.consultar(uno.credencial).usuario.role == "agent"
    with Session(e["motor"]) as db, db.begin():
        db.execute(update(Usuario).where(Usuario.id == e["usuario"]).values(rol="admin"))
    with operacion(e) as (sesiones, _, _):
        identidad = sesiones.consultar(uno.credencial).usuario
        assert identidad.id == e["usuario"] and identidad.role == "admin"
    assert not caplog.records


@pytest.mark.parametrize("segundos", [1800, 1801, 8 * 3600])
def test_inactividad_y_limite_exacto(entorno_servicios, segundos):
    e = entorno_servicios
    sesion = crear_sesion(e)
    e["reloj"].ahora += timedelta(seconds=segundos)
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (sesiones, _, _):
            sesiones.consultar(sesion.credencial)
    assert error.value.codigo == C.SESION_VENCIDA


def test_actividad_explicita_no_amplia_maximo_absoluto(entorno_servicios):
    e = entorno_servicios
    sesion = crear_sesion(e)
    inicio = e["reloj"].ahora
    e["reloj"].ahora += timedelta(minutes=20)
    with operacion(e) as (sesiones, _, _):
        assert sesiones.consultar(sesion.credencial).ultima_actividad == inicio
        assert sesiones.registrar_actividad(sesion.credencial).ultima_actividad == e["reloj"].ahora
    # Simula actividad autorizada durante el resto del máximo de ocho horas.
    with Session(e["motor"]) as db, db.begin():
        db.execute(update(Sesion).where(Sesion.id == sesion.id).values(
            ultima_actividad=inicio + timedelta(hours=7, minutes=59)))
    e["reloj"].ahora = inicio + timedelta(hours=8) - timedelta(microseconds=1)
    with operacion(e) as (sesiones, _, _):
        assert sesiones.registrar_actividad(sesion.credencial).expira_en == sesion.expira_en
    e["reloj"].ahora += timedelta(microseconds=1)
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (sesiones, _, _):
            sesiones.registrar_actividad(sesion.credencial)
    assert error.value.codigo == C.SESION_VENCIDA


def test_usuario_inactivo_y_sesion_desconocida_son_distintos(entorno_servicios):
    e = entorno_servicios
    sesion = crear_sesion(e)
    with Session(e["motor"]) as db, db.begin():
        db.execute(update(Usuario).where(Usuario.id == e["usuario"]).values(activo=False))
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (sesiones, _, _):
            sesiones.consultar(sesion.credencial)
    assert error.value.codigo == C.USUARIO_INACTIVO
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (sesiones, _, _):
            sesiones.consultar(generar_secreto())
    assert error.value.codigo == C.SESION_INEXISTENTE


def test_revocacion_individual_invalida_contexto_y_tokens(entorno_servicios):
    e = entorno_servicios
    uno, dos = crear_sesion(e), crear_sesion(e)
    with operacion(e) as (_, csrf, _):
        token = csrf.emitir_token(sesion=uno.credencial)
    with operacion(e) as (sesiones, _, _):
        assert sesiones.revocar(uno.credencial)
        assert not sesiones.revocar(uno.credencial)
        assert sesiones.consultar(dos.credencial).id == dos.id
    with Session(e["motor"]) as db:
        assert db.get(ContextoCsrf, token.contexto_id).revocado_en is not None
        assert db.scalar(select(TokenCsrf.invalidado_en).where(TokenCsrf.contexto_id == token.contexto_id)) is not None
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (sesiones, _, _):
            sesiones.consultar(uno.credencial)
    assert error.value.codigo == C.SESION_REVOCADA


def test_reemplazo_solo_presentada_y_rollback_conserva_anterior(entorno_servicios):
    e = entorno_servicios
    anterior, independiente = crear_sesion(e), crear_sesion(e)
    with operacion(e) as (_, csrf, _):
        token = csrf.emitir_token(sesion=anterior.credencial)
    with pytest.raises(RuntimeError):
        with operacion(e) as (sesiones, _, _):
            descartada = sesiones.crear(e["usuario"], presentada=anterior.credencial)
            raise RuntimeError("Fallo posterior ficticio")
    with operacion(e) as (sesiones, csrf, db):
        assert db.get(Sesion, descartada.id) is None
        assert sesiones.consultar(anterior.credencial).id == anterior.id
        csrf.validar_token(token.token, sesion=anterior.credencial)
        nueva = sesiones.crear(e["usuario"], presentada=anterior.credencial)
    assert nueva.credencial != anterior.credencial
    with operacion(e) as (sesiones, _, _):
        assert sesiones.consultar(independiente.credencial).id == independiente.id
        assert sesiones.consultar(nueva.credencial).id == nueva.id
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (sesiones, _, _):
            sesiones.consultar(anterior.credencial)
    assert error.value.codigo == C.SESION_REVOCADA


@pytest.mark.parametrize("estado", ["inexistente", "vencida", "revocada"])
def test_reemplazo_invalido_no_elige_recuperacion_ni_crea_sesion(entorno_servicios, estado):
    e = entorno_servicios
    anterior = crear_sesion(e)
    credencial = anterior.credencial
    if estado == "inexistente":
        credencial = generar_secreto()
    elif estado == "vencida":
        e["reloj"].ahora += timedelta(minutes=30)
    else:
        with operacion(e) as (sesiones, _, _):
            sesiones.revocar(credencial)
    with pytest.raises(ErrorSeguridad):
        with operacion(e) as (sesiones, _, _):
            sesiones.crear(e["usuario"], presentada=credencial)
    with Session(e["motor"]) as db:
        assert db.scalar(select(func.count(Sesion.id)).where(Sesion.usuario_id == e["usuario"])) == 1


def test_contextos_separados_tokens_reutilizables_y_sin_renovar_actividad(entorno_servicios):
    e = entorno_servicios
    anonimo = crear_anonimo(e)
    uno, dos = crear_sesion(e), crear_sesion(e)
    inicio = e["reloj"].ahora
    e["reloj"].ahora += timedelta(minutes=5)
    with operacion(e) as (sesiones, csrf, _):
        assert csrf.recuperar_anonimo(anonimo.secreto).id == anonimo.id
        autenticado = csrf.obtener_autenticado(uno.credencial)
        csrf.obtener_autenticado(dos.credencial)
        assert csrf.obtener_autenticado(uno.credencial).id == autenticado.id
        token_anonimo = csrf.emitir_token(anonimo=anonimo.secreto)
        token = csrf.emitir_token(sesion=uno.credencial)
        for _ in range(2):
            assert csrf.validar_token(token.token, sesion=uno.credencial).id == autenticado.id
        assert sesiones.consultar(uno.credencial).ultima_actividad == inicio
    for token_erroneo, credencial in [(token_anonimo.token, uno.credencial), (token.token, dos.credencial)]:
        with pytest.raises(ErrorSeguridad) as error:
            with operacion(e) as (_, csrf, _):
                csrf.validar_token(token_erroneo, sesion=credencial)
        assert error.value.codigo == C.TOKEN_INVALIDO


def test_vencimiento_token_y_contexto_en_limite_exacto(entorno_servicios):
    e = entorno_servicios
    contexto = crear_anonimo(e)
    with operacion(e) as (_, csrf, _):
        token = csrf.emitir_token(anonimo=contexto.secreto)
    assert token.expira_en == e["reloj"].ahora + timedelta(minutes=10)
    e["reloj"].ahora += timedelta(minutes=10)
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (_, csrf, _):
            csrf.validar_token(token.token, anonimo=contexto.secreto)
    assert error.value.codigo == C.TOKEN_VENCIDO
    e["reloj"].ahora += timedelta(minutes=5)
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (_, csrf, _):
            csrf.recuperar_anonimo(contexto.secreto)
    assert error.value.codigo == C.CONTEXTO_INVALIDO


def test_tokens_recortados_y_cuota_no_expulsa_otros(entorno_servicios):
    e = entorno_servicios
    e["configuracion"] = Configuracion(_env_file=None, auth_csrf_max_tokens=2,
        auth_csrf_contexto_segundos=30, auth_csrf_token_bytes=64)
    contexto = crear_anonimo(e)
    with operacion(e) as (_, csrf, db):
        uno = csrf.emitir_token(anonimo=contexto.secreto)
        dos = csrf.emitir_token(anonimo=contexto.secreto)
        assert uno.expira_en == contexto.expira_en
        assert db.scalar(select(TokenCsrf.digest_token).where(TokenCsrf.contexto_id == contexto.id).limit(1)) is not None
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (_, csrf, _):
            csrf.emitir_token(anonimo=contexto.secreto)
    assert error.value.codigo == C.LIMITE_TOKENS
    with operacion(e) as (_, csrf, _):
        csrf.validar_token(uno.token, anonimo=contexto.secreto)
        csrf.validar_token(dos.token, anonimo=contexto.secreto)
        assert csrf.invalidar_token(uno.token, anonimo=contexto.secreto)
        assert not csrf.invalidar_token(uno.token, anonimo=contexto.secreto)
        csrf.emitir_token(anonimo=contexto.secreto)


def test_token_autenticado_acotado_por_inactividad_y_maximo_absoluto(entorno_servicios):
    e = entorno_servicios
    sesion = crear_sesion(e)
    inicio = e["reloj"].ahora
    e["reloj"].ahora = inicio + timedelta(minutes=29)
    with operacion(e) as (_, csrf, _):
        token = csrf.emitir_token(sesion=sesion.credencial)
        assert token.expira_en == inicio + timedelta(minutes=30)
    with Session(e["motor"]) as db, db.begin():
        db.execute(update(Sesion).where(Sesion.id == sesion.id).values(ultima_actividad=inicio + timedelta(hours=7, minutes=59)))
    e["reloj"].ahora = inicio + timedelta(hours=7, minutes=59)
    with operacion(e) as (_, csrf, _):
        assert csrf.emitir_token(sesion=sesion.credencial).expira_en == inicio + timedelta(hours=8)


def test_invalidacion_contexto_y_token_sin_resurreccion(entorno_servicios):
    e = entorno_servicios
    contexto = crear_anonimo(e)
    with operacion(e) as (_, csrf, _):
        token = csrf.emitir_token(anonimo=contexto.secreto)
        csrf.invalidar_token(token.token, anonimo=contexto.secreto)
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (_, csrf, _):
            csrf.validar_token(token.token, anonimo=contexto.secreto)
    assert error.value.codigo == C.TOKEN_INVALIDO
    with operacion(e) as (_, csrf, _):
        csrf.invalidar_contexto(anonimo=contexto.secreto)
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (_, csrf, _):
            csrf.emitir_token(anonimo=contexto.secreto)
    assert error.value.codigo == C.CONTEXTO_INVALIDO


def test_fallo_transaccional_revierte_toda_la_emision(entorno_servicios):
    e = entorno_servicios
    with pytest.raises(RuntimeError):
        with operacion(e) as (sesiones, csrf, _):
            sesion = sesiones.crear(e["usuario"])
            token = csrf.emitir_token(sesion=sesion.credencial)
            raise RuntimeError("Fallo simulado antes del commit")
    with Session(e["motor"]) as db:
        assert db.get(Sesion, sesion.id) is None
        assert db.get(ContextoCsrf, token.contexto_id) is None
        assert db.scalar(select(TokenCsrf.id).where(TokenCsrf.contexto_id == token.contexto_id)) is None


def test_fallo_real_durante_commit_revierte_emision_y_sanea_error(entorno_servicios, caplog):
    e = entorno_servicios
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (sesiones, csrf, db):
            sesion = sesiones.crear(e["usuario"])
            token = csrf.emitir_token(sesion=sesion.credencial)
            correo = db.get(Usuario, e["usuario"]).correo
            # El conflicto UNIQUE se produce en el flush automático del commit.
            db.add(Usuario(nombre="Duplicado", correo=correo, hash_contrasena="hash ficticio"))
    assert error.value.codigo == C.TRANSACCION
    assert correo not in str(error.value)
    assert sesion.credencial.get_secret_value() not in str(error.value)
    with Session(e["motor"]) as db:
        assert db.get(Sesion, sesion.id) is None
        assert db.get(ContextoCsrf, token.contexto_id) is None
    assert not caplog.records


def test_actividad_es_monotona_incluso_con_reloj_inyectado_atrasado(entorno_servicios):
    e = entorno_servicios
    sesion = crear_sesion(e)
    e["reloj"].ahora += timedelta(minutes=20)
    with operacion(e) as (sesiones, _, _):
        ultima = sesiones.registrar_actividad(sesion.credencial).ultima_actividad
    e["reloj"].ahora -= timedelta(minutes=1)
    with operacion(e) as (sesiones, _, _):
        assert sesiones.registrar_actividad(sesion.credencial).ultima_actividad == ultima


@pytest.mark.parametrize("limite", [1, 8])
def test_emision_concurrente_respeta_cuota_y_reutiliza_contexto(entorno_servicios, limite):
    e = entorno_servicios
    e["configuracion"] = Configuracion(_env_file=None, auth_csrf_max_tokens=limite)
    sesion = crear_sesion(e)
    barrera = Barrier(limite + 2)
    def emitir():
        barrera.wait(timeout=3)
        try:
            with operacion(e) as (_, csrf, _):
                token = csrf.emitir_token(sesion=sesion.credencial)
            return token
        except ErrorSeguridad as error:
            return error.codigo
    with ThreadPoolExecutor(max_workers=limite + 2) as ejecutor:
        futuros = [ejecutor.submit(emitir) for _ in range(limite + 2)]
        resultados = [f.result(timeout=8) for f in futuros]
    assert resultados.count(C.LIMITE_TOKENS) == 2
    token = next(r for r in resultados if not isinstance(r, C))
    with operacion(e) as (_, csrf, db):
        assert csrf.obtener_autenticado(sesion.credencial).id == token.contexto_id
        csrf.validar_token(token.token, sesion=sesion.credencial)
        assert db.scalar(select(func.count(ContextoCsrf.id)).where(ContextoCsrf.sesion_id == sesion.id)) == 1
        assert db.scalar(select(func.count(TokenCsrf.id)).where(TokenCsrf.contexto_id == token.contexto_id)) == limite


@pytest.mark.parametrize("revocar", [True, False])
def test_espera_lock_relee_estado_y_tiempo_sin_resucitar(entorno_servicios, revocar):
    e = entorno_servicios
    sesion = crear_sesion(e)
    listo, continuar = Event(), Event()
    datos = {}
    def actualizar():
        try:
            with operacion(e) as (sesiones, _, db):
                # Mantiene a propósito un snapshot ORM antiguo en esta conexión.
                anterior = db.get(Sesion, sesion.id)
                assert anterior.revocada_en is None
                datos["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
                listo.set()
                assert continuar.wait(timeout=3)
                sesiones.registrar_actividad(sesion.credencial)
            return None
        except ErrorSeguridad as error:
            return error.codigo
    with ThreadPoolExecutor(max_workers=1) as ejecutor:
        futuro = ejecutor.submit(actualizar)
        try:
            assert listo.wait(timeout=3)
            with operacion(e) as (sesiones, _, db):
                if revocar:
                    sesiones.revocar(sesion.credencial)
                else:
                    db.execute(select(Sesion).where(Sesion.id == sesion.id).with_for_update())
                continuar.set()
                esperar_lock(e, datos["pid"])
                if not revocar:
                    e["reloj"].ahora += timedelta(minutes=30)
            assert futuro.result(timeout=8) == (C.SESION_REVOCADA if revocar else C.SESION_VENCIDA)
        finally:
            continuar.set()
    with Session(e["motor"]) as db:
        assert db.get(Sesion, sesion.id).ultima_actividad == sesion.expira_en - timedelta(hours=8)


def test_contexto_revocado_mientras_emision_espera_lock(entorno_servicios):
    e = entorno_servicios
    contexto = crear_anonimo(e)
    datos, listo = {}, Event()
    def emitir():
        try:
            with operacion(e) as (_, csrf, db):
                datos["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
                listo.set()
                csrf.emitir_token(anonimo=contexto.secreto)
        except ErrorSeguridad as error:
            return error.codigo
    with ThreadPoolExecutor(max_workers=1) as ejecutor:
        with operacion(e) as (_, csrf, _):
            csrf.invalidar_contexto(anonimo=contexto.secreto)
            futuro = ejecutor.submit(emitir)
            assert listo.wait(timeout=3)
            esperar_lock(e, datos["pid"])
        assert futuro.result(timeout=8) == C.CONTEXTO_INVALIDO
    with Session(e["motor"]) as db:
        assert db.scalar(select(func.count(TokenCsrf.id)).where(TokenCsrf.contexto_id == contexto.id)) == 0


def test_reloj_postgresql_no_se_congela_en_inicio_transaccion(entorno_servicios):
    e = entorno_servicios
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        servicio = ServicioSesiones(db)
        primero = servicio.crear(e["usuario"])
        db.execute(text("SELECT pg_sleep(0.02)"))
        segundo = servicio.crear(e["usuario"])
        assert segundo.expira_en > primero.expira_en


def test_fallo_de_conexion_no_se_confunde_con_sesion_ausente(entorno_servicios):
    e = entorno_servicios
    sesion = crear_sesion(e)
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (sesiones, _, db):
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            # Termina exclusivamente la conexión propia de esta prueba temporal.
            with e["motor"].connect() as otra:
                assert otra.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}).scalar_one()
            sesiones.consultar(sesion.credencial)
    assert error.value.codigo == C.INFRAESTRUCTURA
