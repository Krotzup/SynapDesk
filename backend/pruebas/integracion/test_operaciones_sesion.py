"""Operaciones sobre sesiones nacidas de login real; commits y locks PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from time import monotonic, sleep

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, event, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.esquemas_auth import AuthUser
from app.persistencia.conexion import construir_url_bd
from app.persistencia.modelos import ContextoCsrf, EventoAutenticacion, Sesion, TokenCsrf, Usuario
from app.seguridad.auditoria import ServicioAuditoria, TipoEvento as T
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.operaciones_sesion import ReferenciaSesion, ServicioConsultaSesion, ServicioLogout
from app.seguridad.secretos import generar_secreto
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad, transaccion_seguridad
from pruebas.integracion.test_login import entorno_login, filas, login


@pytest.fixture
def operaciones(entorno_login):
    e = entorno_login
    resultado = login(e)
    e["referencia"] = ReferenciaSesion(resultado.sesion.credencial)
    e["sesion_id"] = resultado.sesion.id
    e["consulta"] = ServicioConsultaSesion(e["motor"], reloj=e["reloj"])
    e["logout"] = ServicioLogout(e["motor"], e["config"], reloj=e["reloj"])
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        e["token"] = ServicioCsrf(db, e["config"], e["reloj"]).emitir_token(
            sesion=e["referencia"].credencial).token
    return e


def estado(e):
    with Session(e["motor"]) as db:
        sesion = db.get(Sesion, e["sesion_id"])
        return sesion.revocada_en, sesion.ultima_actividad, sesion.expira_en


def cerrar(e, token=None):
    return e["logout"].cerrar(e["referencia"], token=e["token"] if token is None else token)


def eventos_logout(e):
    return [f for f in filas(e, EventoAutenticacion) if f.motivo == "logout"]


@pytest.mark.parametrize("rol", ["admin", "agent"])
def test_consulta_proyecta_solo_authuser_vigente(operaciones, rol, caplog):
    e = operaciones
    correo = "CAMBIO@EXAMPLE.INVALID"
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        usuario = db.get(Usuario, e["usuario"].id)
        usuario.correo = "  " + correo + "  "
        usuario.rol = rol
    usuario = e["consulta"].consultar(e["referencia"])
    assert type(usuario) is AuthUser
    assert usuario.model_dump() == dict(id=e["usuario"].id, email=correo.lower(), role=rol)
    texto = usuario.model_dump_json() + repr(e["referencia"]) + caplog.text
    for secreto in (e["clave"], e["referencia"].credencial, e["token"]):
        assert secreto.get_secret_value() not in texto
    assert "hash_contrasena" not in texto and "nombre" not in texto


def test_consulta_no_renueva_actividad_ni_expiracion(operaciones):
    e = operaciones
    inicial = estado(e)
    for minutos in (10, 20, 29):
        e["ahora"] = inicial[1] + timedelta(minutes=minutos)
        e["consulta"].consultar(e["referencia"])
        assert estado(e) == inicial
    e["ahora"] = inicial[1] + timedelta(minutes=30)
    with pytest.raises(ErrorSeguridad) as error:
        e["consulta"].consultar(e["referencia"])
    assert error.value.codigo == C.SESION_VENCIDA


@pytest.mark.parametrize("caso,codigo", [("inactiva", C.USUARIO_INACTIVO),
    ("revocada", C.SESION_REVOCADA), ("absoluta", C.SESION_VENCIDA),
    ("inactividad", C.SESION_VENCIDA), ("ausente", C.SESION_INEXISTENTE)])
def test_consulta_rechaza_estado_actual(operaciones, caso, codigo):
    e = operaciones
    referencia = e["referencia"]
    if caso == "inactiva":
        with e["motor"].begin() as db:
            db.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(activo=False))
    elif caso == "revocada":
        cerrar(e)
    elif caso == "absoluta":
        e["ahora"] += timedelta(hours=8)
        with e["motor"].begin() as db:
            db.execute(update(Sesion).where(Sesion.id == e["sesion_id"]).values(
                ultima_actividad=e["ahora"] - timedelta(minutes=1)))
    elif caso == "inactividad":
        e["ahora"] += timedelta(minutes=30)
    else:
        referencia = ReferenciaSesion(generar_secreto())
    with pytest.raises(ErrorSeguridad) as error:
        e["consulta"].consultar(referencia)
    assert error.value.codigo == codigo


def test_fk_impide_usuario_eliminado_con_sesion_persistida(operaciones):
    e = operaciones
    with pytest.raises(IntegrityError):
        with e["motor"].begin() as db:
            db.execute(delete(Usuario).where(Usuario.id == e["usuario"].id))
    assert e["consulta"].consultar(e["referencia"]).id == e["usuario"].id


def test_logout_revoca_contexto_tokens_y_conserva_otro_dispositivo(operaciones, caplog):
    e = operaciones
    otro = login(e).sesion
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        otro_token = ServicioCsrf(db, e["config"], e["reloj"]).emitir_token(sesion=otro.credencial)
    resultado = cerrar(e)
    assert resultado.revocada is True and estado(e)[0] is not None
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        contexto = db.scalar(select(ContextoCsrf).where(ContextoCsrf.sesion_id == e["sesion_id"]))
        assert contexto.revocado_en is not None
        tokens = db.scalars(select(TokenCsrf).where(TokenCsrf.contexto_id == contexto.id)).all()
        assert tokens and all(t.invalidado_en is not None for t in tokens)
        ServicioCsrf(db, e["config"], e["reloj"]).validar_token(otro_token.token, sesion=otro.credencial)
    assert e["consulta"].consultar(ReferenciaSesion(otro.credencial)).id == e["usuario"].id
    eventos = eventos_logout(e)
    assert len(eventos) == 1
    assert eventos[0].sesion_id == e["sesion_id"] and eventos[0].resultado == "success"
    texto = repr(resultado) + repr([vars(evento) for evento in eventos]) + caplog.text
    for secreto in (e["referencia"].credencial, e["token"], e["clave"]):
        assert secreto.get_secret_value() not in texto


@pytest.mark.parametrize("caso,codigo", [("ausente", C.TOKEN_INVALIDO),
    ("malformado", C.TOKEN_INVALIDO), ("otro", C.TOKEN_INVALIDO),
    ("ajeno", C.TOKEN_INVALIDO), ("anonimo", C.TOKEN_INVALIDO),
    ("vencido", C.TOKEN_VENCIDO), ("invalidado", C.TOKEN_INVALIDO),
    ("contexto_revocado", C.CONTEXTO_INVALIDO), ("contexto_vencido", C.CONTEXTO_INVALIDO)])
def test_csrf_rechazado_sin_revocar_y_con_auditoria(operaciones, caso, codigo):
    e = operaciones
    token = e["token"]
    if caso == "ausente":
        token = None
    elif caso == "malformado":
        token = SecretStr("malformado")
    elif caso == "otro":
        token = generar_secreto()
    elif caso in {"ajeno", "anonimo"}:
        otro = login(e).sesion if caso == "ajeno" else None
        with Session(e["motor"]) as db, transaccion_seguridad(db):
            csrf = ServicioCsrf(db, e["config"], e["reloj"])
            if otro is not None:
                token = csrf.emitir_token(sesion=otro.credencial).token
            else:
                token = csrf.emitir_token(anonimo=csrf.crear_anonimo().secreto).token
    elif caso == "vencido":
        e["ahora"] += timedelta(seconds=e["config"].auth_csrf_token_segundos)
    else:
        with Session(e["motor"]) as db, transaccion_seguridad(db):
            csrf = ServicioCsrf(db, e["config"], e["reloj"])
            if caso == "invalidado":
                csrf.invalidar_token(token, sesion=e["referencia"].credencial)
            elif caso == "contexto_revocado":
                csrf.invalidar_contexto(sesion=e["referencia"].credencial)
            else:
                contexto = db.scalar(select(ContextoCsrf).where(ContextoCsrf.sesion_id == e["sesion_id"]))
                e["ahora"] += timedelta(seconds=1)
                contexto.expira_en = e["ahora"]
    with pytest.raises(ErrorSeguridad) as error:
        e["logout"].cerrar(e["referencia"], token=token)
    assert error.value.codigo == codigo
    assert estado(e)[0] is None and not eventos_logout(e)
    assert filas(e, EventoAutenticacion)[-1].motivo == "csrf_invalid"


def test_token_reutilizable_hasta_revocacion_y_logout_repetido_idempotente(operaciones):
    e = operaciones
    for _ in range(2):
        with Session(e["motor"]) as db, transaccion_seguridad(db):
            ServicioCsrf(db, e["config"], e["reloj"]).validar_token(
                e["token"], sesion=e["referencia"].credencial)
    assert cerrar(e).revocada
    assert e["logout"].cerrar(e["referencia"]).revocada is False
    assert cerrar(e, generar_secreto()).revocada is False
    assert len(eventos_logout(e)) == 1


@pytest.mark.parametrize("caso", ["desconocida", "vencida", "revocada"])
def test_logout_idempotente_solo_ausencia_confirmada_en_bd(operaciones, caso):
    e = operaciones
    referencia = e["referencia"]
    if caso == "desconocida":
        referencia = ReferenciaSesion(generar_secreto())
    elif caso == "vencida":
        e["ahora"] += timedelta(minutes=30)
    else:
        cerrar(e)
    antes = len(eventos_logout(e))
    assert e["logout"].cerrar(referencia).revocada is False
    assert len(eventos_logout(e)) == antes


def test_cuenta_inactiva_cierra_rama_no_definida_sin_fingir_revocacion(operaciones):
    e = operaciones
    with e["motor"].begin() as db:
        db.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(activo=False))
    with pytest.raises(ErrorSeguridad) as error:
        cerrar(e)
    assert error.value.codigo == C.USUARIO_INACTIVO
    assert estado(e)[0] is None and not eventos_logout(e)


@pytest.mark.parametrize("operacion", ["consulta", "logout"])
def test_fallo_real_conexion_no_equivale_a_sesion_ausente(operaciones, configuracion_bd_test, operacion):
    e = operaciones
    url = construir_url_bd(configuracion_bd_test).set(database="synapdesk_auth07_sec01a_no_existe")
    motor = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 2})
    try:
        with pytest.raises(ErrorSeguridad) as error:
            if operacion == "consulta":
                ServicioConsultaSesion(motor).consultar(e["referencia"])
            else:
                ServicioLogout(motor, e["config"]).cerrar(e["referencia"], token=e["token"])
        assert error.value.codigo == C.INFRAESTRUCTURA
        assert "no_existe" not in str(error.value)
        assert error.value.__cause__ is None
    finally:
        motor.dispose()
    assert estado(e)[0] is None


def test_fallo_auditoria_revierte_revocacion_y_csrf(operaciones, monkeypatch):
    e = operaciones
    original = ServicioAuditoria.registrar

    def fallar(self, **datos):
        if datos["tipo"] == T.SESION_REVOCADA:
            # Error real de PostgreSQL dentro de la transacción obligatoria.
            self.db.execute(text("SELECT 1/0"))
        return original(self, **datos)

    monkeypatch.setattr(ServicioAuditoria, "registrar", fallar)
    with pytest.raises(ErrorSeguridad) as error:
        cerrar(e)
    assert error.value.codigo == C.INFRAESTRUCTURA
    assert estado(e)[0] is None and not eventos_logout(e)
    assert filas(e, EventoAutenticacion)[-1].motivo == "security_unavailable"
    monkeypatch.setattr(ServicioAuditoria, "registrar", original)
    assert cerrar(e).revocada


def test_fallo_commit_real_revierte_sesion_contexto_y_evento(operaciones):
    e = operaciones

    def antes_commit(db):
        if db.get_bind().pool is e["motor"].pool:
            db.flush()
            eventos = db.scalars(select(EventoAutenticacion).where(
                EventoAutenticacion.sesion_id == e["sesion_id"],
                EventoAutenticacion.motivo == "logout")).all()
            if eventos:
                db.execute(text("CREATE TEMP TABLE fallo_logout (n int UNIQUE DEFERRABLE "
                                "INITIALLY DEFERRED) ON COMMIT DROP"))
                db.execute(text("INSERT INTO fallo_logout VALUES (1), (1)"))

    event.listen(Session, "before_commit", antes_commit)
    try:
        with pytest.raises(ErrorSeguridad) as error:
            cerrar(e)
        assert error.value.codigo == C.TRANSACCION
    finally:
        event.remove(Session, "before_commit", antes_commit)
    assert estado(e)[0] is None and not eventos_logout(e)
    assert e["consulta"].consultar(e["referencia"]).id == e["usuario"].id
    assert cerrar(e).revocada


def esperar_bloqueado(motor, pid):
    fin = monotonic() + 5
    while monotonic() < fin:
        with motor.connect() as db:
            if db.scalar(text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid=:pid"),
                         {"pid": pid}):
                return
        sleep(0.01)
    raise AssertionError("La operación no esperó el lock PostgreSQL previsto.")


def observar_pid(e, monkeypatch):
    original = ServicioSesiones.consultar
    listo = Event()
    pid = []

    def consultar(self, credencial):
        pid.append(self.db.scalar(text("SELECT pg_backend_pid()")))
        listo.set()
        return original(self, credencial)

    monkeypatch.setattr(ServicioSesiones, "consultar", consultar)
    return listo, pid


def test_dos_logouts_concurrentes_una_revocacion_un_evento(operaciones):
    e = operaciones
    barrera = Barrier(2)

    def ejecutar():
        barrera.wait(timeout=5)
        return cerrar(e).revocada

    with ThreadPoolExecutor(2) as pool:
        resultados = list(pool.map(lambda _: ejecutar(), range(2)))
    assert sorted(resultados) == [False, True]
    assert len(eventos_logout(e)) == 1
    with pytest.raises(ErrorSeguridad) as error:
        e["consulta"].consultar(e["referencia"])
    assert error.value.codigo == C.SESION_REVOCADA


@pytest.mark.parametrize("cambio", ["rol", "activo", "revocacion"])
def test_consulta_relee_cambio_confirmado_tras_espera_real(operaciones, monkeypatch, cambio):
    e = operaciones
    listo, pid = observar_pid(e, monkeypatch)
    with ThreadPoolExecutor(1) as pool:
        with Session(e["motor"]) as db, transaccion_seguridad(db):
            if cambio == "revocacion":
                ServicioSesiones(db, e["reloj"]).revocar(e["referencia"].credencial)
            else:
                db.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(
                    **({"rol": "admin"} if cambio == "rol" else {"activo": False})))
            futuro = pool.submit(e["consulta"].consultar, e["referencia"])
            assert listo.wait(5)
            esperar_bloqueado(e["motor"], pid[0])
        if cambio == "rol":
            assert futuro.result(timeout=5).role == "admin"
        else:
            with pytest.raises(ErrorSeguridad) as error:
                futuro.result(timeout=5)
            assert error.value.codigo == (C.SESION_REVOCADA if cambio == "revocacion" else C.USUARIO_INACTIVO)


def test_me_autorizado_antes_logout_no_se_deshace_retroactivamente(operaciones, monkeypatch):
    e = operaciones
    original = ServicioSesiones.consultar
    autorizado, liberar = Event(), Event()
    logout_iniciado = Event()
    pid = []

    def consultar(self, credencial):
        if autorizado.is_set():
            pid.append(self.db.scalar(text("SELECT pg_backend_pid()")))
            logout_iniciado.set()
            return original(self, credencial)
        resultado = original(self, credencial)
        autorizado.set()
        assert liberar.wait(5)
        return resultado

    monkeypatch.setattr(ServicioSesiones, "consultar", consultar)
    with ThreadPoolExecutor(2) as pool:
        consulta = pool.submit(e["consulta"].consultar, e["referencia"])
        assert autorizado.wait(5)
        logout = pool.submit(cerrar, e)
        try:
            assert logout_iniciado.wait(5)
            esperar_bloqueado(e["motor"], pid[0])
        finally:
            liberar.set()
        assert consulta.result(timeout=5).id == e["usuario"].id
        assert logout.result(timeout=5).revocada
    monkeypatch.setattr(ServicioSesiones, "consultar", original)
    with pytest.raises(ErrorSeguridad):
        e["consulta"].consultar(e["referencia"])


@pytest.mark.parametrize("minutos", [10, 30])
def test_expiracion_mientras_logout_espera_contexto_no_revoca(operaciones, minutos):
    e = operaciones
    original = e["reloj"]
    pid, listo = [], Event()

    def reloj(db):
        if not pid:
            pid.append(db.scalar(text("SELECT pg_backend_pid()")))
            listo.set()
        return original(db)

    e["logout"] = ServicioLogout(e["motor"], e["config"], reloj=reloj)
    with ThreadPoolExecutor(1) as pool:
        with Session(e["motor"]) as db, transaccion_seguridad(db):
            db.scalar(select(ContextoCsrf).where(ContextoCsrf.sesion_id == e["sesion_id"]).with_for_update())
            futuro = pool.submit(cerrar, e)
            assert listo.wait(5)
            esperar_bloqueado(e["motor"], pid[0])
            e["ahora"] += timedelta(minutes=minutos)
        if minutos == 30:
            assert futuro.result(timeout=5).revocada is False
        else:
            with pytest.raises(ErrorSeguridad) as error:
                futuro.result(timeout=5)
            assert error.value.codigo == C.TOKEN_VENCIDO
    assert estado(e)[0] is None and not eventos_logout(e)


def test_fallo_auditoria_de_rechazo_tambien_falla_cerrado(operaciones, monkeypatch):
    e = operaciones

    def fallar(self, **datos):
        self.db.execute(text("SELECT 1/0"))

    monkeypatch.setattr(ServicioAuditoria, "registrar", fallar)
    with pytest.raises(ErrorSeguridad) as error:
        e["logout"].cerrar(e["referencia"], token=generar_secreto())
    assert error.value.codigo == C.INFRAESTRUCTURA
    assert estado(e)[0] is None and not eventos_logout(e)
