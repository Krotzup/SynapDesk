import base64
import secrets
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event, Lock
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.configuracion import Configuracion
from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import EventoAutenticacion, LimiteAutenticacion, Sesion, Usuario
from app.seguridad.auditoria import MotivoEvento as M, ResultadoEvento as R, ServicioAuditoria, TipoEvento as T
from app.seguridad.identificadores import ServicioIdentificadores
from app.seguridad.limites import ServicioLimites
from app.seguridad.proxies import ServicioIpConfiable
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad, transaccion_seguridad


@pytest.fixture
def entorno_c(configuracion_bd_test):
    motor = crear_motor_bd(configuracion_bd_test)
    configuracion = Configuracion(
        _env_file=None, app_env="testing",
        auth_hmac_clave=base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
        auth_hmac_id_clave="prueba-c", auth_proxies_autorizados=["192.0.2.8/32"],
        auth_limite_cuenta_intentos=2, auth_limite_cuenta_ventana_segundos=60,
        auth_limite_cuenta_bloqueo_segundos=20, auth_limite_ip_intentos=3,
        auth_limite_ip_ventana_segundos=60, auth_limite_ip_bloqueo_segundos=20,
    )
    identificadores = ServicioIdentificadores(configuracion)
    ip = ServicioIpConfiable(configuracion, identificadores).identificar(
        par_transporte="192.0.2.8", valores_ip_cliente=["198.51.100.7"])
    creadas = {clase: set() for clase in (LimiteAutenticacion, EventoAutenticacion, Sesion, Usuario)}
    candado = Lock()

    class SesionPrueba(Session):
        pass

    @event.listens_for(SesionPrueba, "after_flush")
    def recordar(db, contexto):
        with candado:
            for fila in db.new:
                if type(fila) in creadas and fila.id is not None:
                    creadas[type(fila)].add(fila.id)

    e = dict(motor=motor, configuracion=configuracion, identificadores=identificadores,
             ip=ip, cuenta=f"{uuid4()}@example.invalid", Session=SesionPrueba,
             ahora=datetime(2026, 11, 3, tzinfo=UTC))
    e["reloj"] = lambda db: e["ahora"]
    try:
        yield e
    finally:
        # Solo filas creadas por las sesiones de ESTE fixture, incluidos recibos.
        try:
            with Session(motor) as db, db.begin():
                for clase, ids in creadas.items():
                    db.execute(delete(clase).where(clase.id.in_(ids)))
        finally:
            motor.dispose()


@contextmanager
def operacion(e):
    with e["Session"](e["motor"]) as db, transaccion_seguridad(db):
        yield ServicioLimites(db, e["configuracion"], e["identificadores"], e["reloj"]), db


def reservar(e, *, cuenta=None, ip=None):
    with operacion(e) as (servicio, _):
        decision = servicio.reservar(cuenta=cuenta or e["cuenta"], ip=ip or e["ip"])
    return decision


def consolidar(e, reserva):
    with operacion(e) as (servicio, _):
        return servicio.consolidar(reserva)


def filas_cuota(e):
    with Session(e["motor"]) as db:
        return db.scalars(select(LimiteAutenticacion).where(
            LimiteAutenticacion.clave_digest.in_([
                e["identificadores"].cuenta(e["cuenta"]), e["ip"].digest,
            ]), LimiteAutenticacion.tipo_clave.in_(["cuenta", "ip"]),
        ).order_by(LimiteAutenticacion.tipo_clave)).all()


def test_limite_exacto_persiste_y_no_revela_cuenta(entorno_c):
    e = entorno_c
    uno, dos = reservar(e), reservar(e)
    assert uno.permitido and dos.permitido
    denegado = reservar(e)
    assert not denegado.permitido and denegado.reserva is None
    assert denegado.codigo == "RATE_LIMITED" and denegado.retry_after == 60
    assert denegado.reintentar_en == e["ahora"] + timedelta(seconds=60)
    assert e["cuenta"] not in repr(denegado)
    assert [fila.reservas for fila in filas_cuota(e)] == [2, 2]
    assert all(len(fila.clave_digest) == 32 for fila in filas_cuota(e))


def test_ip_compartida_limita_cuentas_distintas_y_no_se_borra_por_exito(entorno_c):
    e = entorno_c
    for numero in range(3):
        decision = reservar(e, cuenta=f"cuenta-{numero}@example.invalid")
        assert decision.permitido
        assert consolidar(e, decision.reserva)
    assert not reservar(e, cuenta="otra@example.invalid").permitido
    with Session(e["motor"]) as db:
        assert db.scalar(select(LimiteAutenticacion.id).where(
            LimiteAutenticacion.tipo_clave == "cuenta",
            LimiteAutenticacion.clave_digest == e["identificadores"].cuenta("otra@example.invalid"),
        )) is None


def test_cuenta_limita_ips_distintas_y_normaliza_identificador(entorno_c):
    e = entorno_c
    assert reservar(e).permitido
    assert reservar(e, cuenta=e["cuenta"].upper()).permitido
    otra_ip = ServicioIpConfiable(e["configuracion"], e["identificadores"]).identificar(
        par_transporte="192.0.2.8", valores_ip_cliente=["198.51.100.9"])
    assert not reservar(e, ip=otra_ip).permitido


def test_consolidacion_exactamente_una_vez_entre_servicios(entorno_c):
    e = entorno_c
    uno, dos = reservar(e), reservar(e)
    assert consolidar(e, uno.reserva)
    assert not consolidar(e, uno.reserva)
    assert [(f.intentos, f.reservas) for f in filas_cuota(e)] == [(1, 1), (1, 1)]
    assert consolidar(e, dos.reserva)
    assert [(f.intentos, f.reservas) for f in filas_cuota(e)] == [(2, 0), (2, 0)]
    assert not reservar(e).permitido


def test_ventana_reservas_abandonadas_y_recibo_antiguo(entorno_c):
    e = entorno_c
    anterior = reservar(e)
    reservar(e)
    e["ahora"] += timedelta(seconds=60)
    nueva = reservar(e)
    assert nueva.permitido
    assert not consolidar(e, anterior.reserva)
    assert [(f.intentos, f.reservas) for f in filas_cuota(e)] == [(0, 1), (0, 1)]
    assert consolidar(e, nueva.reserva)


def test_bloqueo_sobrevive_ventana_y_rechazos_no_lo_extienden(entorno_c):
    e = entorno_c
    e["configuracion"].auth_limite_cuenta_bloqueo_segundos = 90
    reservar(e)
    reservar(e)
    inicio = e["ahora"]
    e["ahora"] = inicio + timedelta(seconds=60)
    assert reservar(e).retry_after == 30
    e["ahora"] = inicio + timedelta(seconds=89, microseconds=999999)
    assert reservar(e).retry_after == 1
    e["ahora"] = inicio + timedelta(seconds=90)
    assert reservar(e).permitido


def test_retry_after_usa_el_maximo_de_ambas_claves(entorno_c):
    e = entorno_c
    e["configuracion"].auth_limite_cuenta_bloqueo_segundos = 90
    e["configuracion"].auth_limite_ip_intentos = 2
    e["configuracion"].auth_limite_ip_bloqueo_segundos = 120
    reservar(e)
    reservar(e)
    assert reservar(e).retry_after == 120


@pytest.mark.parametrize("compartir_cuenta", [True, False])
def test_reservas_concurrentes_no_eluden_cuota(entorno_c, compartir_cuenta):
    e = entorno_c
    barrera = Barrier(8)

    def intentar(numero):
        with operacion(e) as (servicio, db):
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            barrera.wait(timeout=5)
            cuenta = e["cuenta"] if compartir_cuenta else f"{numero}@example.invalid"
            decision = servicio.reservar(cuenta=cuenta, ip=e["ip"])
        return decision, pid

    with ThreadPoolExecutor(max_workers=8) as executor:
        resultados = list(executor.map(intentar, range(8)))
    assert len({pid for _, pid in resultados}) == 8
    assert sum(d.permitido for d, _ in resultados) == (2 if compartir_cuenta else 3)
    assert all(d.retry_after == 60 for d, _ in resultados if not d.permitido)


def test_consolidacion_concurrente_del_mismo_recibo_es_idempotente(entorno_c):
    e = entorno_c
    reserva = reservar(e).reserva
    barrera = Barrier(2)

    def finalizar(_):
        barrera.wait(timeout=5)
        return consolidar(e, reserva)

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(finalizar, range(2))) == [False, True]
    assert [(f.intentos, f.reservas) for f in filas_cuota(e)] == [(1, 0), (1, 0)]


def test_cambio_de_ventana_concurrente_no_crea_cuota_extra(entorno_c):
    e = entorno_c
    reservar(e)
    reservar(e)
    e["ahora"] += timedelta(seconds=60)
    barrera = Barrier(4)

    def intentar(_):
        barrera.wait(timeout=5)
        return reservar(e).permitido

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(intentar, range(4))) == 2
    assert [f.reservas for f in filas_cuota(e)] == [2, 2]


def test_conflicto_version_reintenta_solo_el_savepoint(entorno_c, monkeypatch):
    e = entorno_c
    with operacion(e) as (servicio, db):
        original = db.flush
        conflictos = []

        def flush(*args, **kwargs):
            # El primer flush ya escribió ambas cuotas dentro del savepoint.
            # Fallar al insertar el recibo obliga a revertir ese trabajo parcial.
            if any(isinstance(f, LimiteAutenticacion) and f.tipo_clave == "reserva" for f in db.new) and not conflictos:
                conflictos.append(True)
                raise StaleDataError("detalle privado del conflicto")
            return original(*args, **kwargs)

        monkeypatch.setattr(db, "flush", flush)
        assert servicio.reservar(cuenta=e["cuenta"], ip=e["ip"]).permitido
    assert conflictos == [True]
    assert [f.reservas for f in filas_cuota(e)] == [1, 1]


def test_conflictos_version_agotan_reintentos_sin_reservar(entorno_c, monkeypatch, caplog):
    e = entorno_c
    conflictos = []
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (servicio, db):
            original = db.flush

            def flush(*args, **kwargs):
                if db.new or db.dirty:
                    conflictos.append(True)
                    raise StaleDataError("credencial privada")
                return original(*args, **kwargs)

            monkeypatch.setattr(db, "flush", flush)
            servicio.reservar(cuenta=e["cuenta"], ip=e["ip"])
    assert error.value.codigo == C.CONFLICTO_VERSION
    assert len(conflictos) == e["configuracion"].auth_limite_reintentos_version + 1
    assert not filas_cuota(e)
    assert "credencial privada" not in str(error.value)
    assert not caplog.records


def test_objeto_orm_obsoleto_se_refresca_tras_otro_worker(entorno_c):
    e = entorno_c
    reservar(e)
    with operacion(e) as (servicio, db):
        antigua = db.scalar(select(LimiteAutenticacion).where(
            LimiteAutenticacion.tipo_clave == "cuenta",
            LimiteAutenticacion.clave_digest == e["identificadores"].cuenta(e["cuenta"])))
        version = antigua.version
        assert reservar(e).permitido
        assert not servicio.reservar(cuenta=e["cuenta"], ip=e["ip"]).permitido
        assert antigua.version > version and antigua.reservas == 2


def test_reloj_se_toma_despues_de_esperar_lock(entorno_c):
    e = entorno_c
    reservar(e)
    reservar(e)
    listo = Event()
    pids = []

    def esperar():
        with operacion(e) as (servicio, db):
            pids.append(db.scalar(text("SELECT pg_backend_pid()")))
            listo.set()
            return servicio.reservar(cuenta=e["cuenta"], ip=e["ip"])

    with ThreadPoolExecutor(max_workers=1) as executor:
        with operacion(e) as (servicio, _):
            servicio._bloquear([("cuenta", e["identificadores"].cuenta(e["cuenta"]))])
            futuro = executor.submit(esperar)
            assert listo.wait(3)
            fin = monotonic() + 3
            while monotonic() < fin:
                with e["motor"].connect() as conexion:
                    if conexion.execute(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"),
                                          {"pid": pids[0]}).scalar_one() == "Lock":
                        break
                sleep(0.01)
            else:
                pytest.fail("No se observó espera real de lock.")
            e["ahora"] += timedelta(seconds=60)
        assert futuro.result(timeout=5).permitido


def test_reserva_y_auditoria_se_revierten_con_transaccion(entorno_c):
    e = entorno_c
    with pytest.raises(RuntimeError):
        with operacion(e) as (servicio, db):
            decision = servicio.reservar(cuenta=e["cuenta"], ip=e["ip"])
            evento = ServicioAuditoria(db, e["reloj"]).registrar(tipo=T.BLOQUEO, resultado=R.RECHAZO, motivo=M.LIMITE)
            raise RuntimeError("rollback de prueba")
    assert not filas_cuota(e)
    with Session(e["motor"]) as db:
        assert db.get(LimiteAutenticacion, decision.reserva.id) is None
        assert db.get(EventoAutenticacion, evento.id) is None
    assert reservar(e).permitido


@pytest.mark.parametrize("campo,valor", [("inicio", datetime(2026, 11, 2, tzinfo=UTC)), ("digest", b"x" * 32), ("tipo", "otro")])
def test_recibo_modificado_no_consolida_reservas_ajenas(entorno_c, campo, valor):
    e = entorno_c
    uno, dos = reservar(e).reserva, reservar(e).reserva
    falso = replace(uno, limites=(replace(uno.limites[0], **{campo: valor}), uno.limites[1]))
    with pytest.raises(ErrorSeguridad) as error:
        consolidar(e, falso)
    assert error.value.codigo == C.RESERVA_INVALIDA
    assert [f.reservas for f in filas_cuota(e)] == [2, 2]
    assert consolidar(e, dos)


def test_no_admite_ninguna_ip_sin_procedencia(entorno_c):
    e = entorno_c
    with pytest.raises(ErrorSeguridad) as error:
        reservar(e, ip="198.51.100.7")
    assert error.value.codigo == C.IP_NO_VERIFICABLE
    assert not filas_cuota(e)


def test_caida_real_bd_no_pasa_a_rate_limited_ni_deja_bloqueo(entorno_c, caplog):
    e = entorno_c
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (servicio, db):
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            with e["motor"].connect() as otra:
                assert otra.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}).scalar_one()
            servicio.reservar(cuenta=e["cuenta"], ip=e["ip"])
    assert error.value.codigo == C.INFRAESTRUCTURA
    assert not filas_cuota(e)
    assert reservar(e).permitido
    assert not caplog.records


@pytest.mark.parametrize("tipo,resultado,motivo", [
    (T.LOGIN, R.EXITO, M.CREDENCIALES_VALIDAS), (T.LOGIN, R.RECHAZO, M.CREDENCIALES_INVALIDAS),
    (T.BLOQUEO, R.RECHAZO, M.LIMITE), (T.VALIDACION, R.RECHAZO, M.ORIGIN),
    (T.VALIDACION, R.RECHAZO, M.CSRF), (T.VALIDACION, R.RECHAZO, M.IP),
])
def test_auditoria_persiste_minimos_y_utc(entorno_c, tipo, resultado, motivo, caplog):
    e = entorno_c
    request_id = uuid4()
    with operacion(e) as (_, db):
        evento = ServicioAuditoria(db, e["reloj"]).registrar(
            tipo=tipo, resultado=resultado, motivo=motivo, request_id=request_id, ip=e["ip"])
    with Session(e["motor"]) as db:
        fila = db.get(EventoAutenticacion, evento.id)
        assert (fila.tipo_evento, fila.resultado, fila.motivo) == (tipo.value, resultado.value, motivo.value)
        assert fila.request_id == str(request_id)
        assert fila.usuario_id is None and fila.sesion_id is None
        assert fila.ocurrido_en == e["ahora"] and fila.ocurrido_en.utcoffset() == timedelta(0)
        assert fila.ip_verificada_digest == e["ip"].digest
        assert set(fila.__table__.columns.keys()) == {"id", "tipo_evento", "ocurrido_en", "usuario_id", "sesion_id", "resultado", "request_id", "motivo", "ip_verificada_digest"}
    assert not caplog.records


def crear_usuario(db):
    usuario = Usuario(nombre="Prueba C", correo=f"{uuid4()}@example.invalid", hash_contrasena="hash ficticio")
    db.add(usuario)
    db.flush()
    return usuario


def test_auditoria_sesion_y_revocacion_en_misma_transaccion(entorno_c):
    e = entorno_c
    with operacion(e) as (_, db):
        usuario = crear_usuario(db)
        sesion = ServicioSesiones(db, e["reloj"]).crear(usuario.id)
        creado = ServicioAuditoria(db, e["reloj"]).registrar(
            tipo=T.SESION_CREADA, resultado=R.EXITO, motivo=M.CREACION,
            usuario_id=usuario.id, sesion_id=sesion.id)
        usuario_id = usuario.id
    with operacion(e) as (_, db):
        assert ServicioSesiones(db, e["reloj"]).revocar(sesion.credencial)
        revocado = ServicioAuditoria(db, e["reloj"]).registrar(
            tipo=T.SESION_REVOCADA, resultado=R.EXITO, motivo=M.LOGOUT,
            usuario_id=usuario_id, sesion_id=sesion.id)
    with Session(e["motor"]) as db:
        assert db.get(Sesion, sesion.id).revocada_en is not None
        assert db.get(EventoAutenticacion, creado.id).sesion_id == sesion.id
        assert db.get(EventoAutenticacion, revocado.id).usuario_id == usuario_id


def test_fallo_commit_real_revierte_cuota_sesion_y_auditoria_sin_secretos(entorno_c, caplog):
    e = entorno_c
    with operacion(e) as (_, db):
        usuario = crear_usuario(db)
        usuario_id, correo = usuario.id, usuario.correo
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (servicio, db):
            reserva = servicio.reservar(cuenta=e["cuenta"], ip=e["ip"]).reserva
            sesion = ServicioSesiones(db, e["reloj"]).crear(usuario_id)
            evento = ServicioAuditoria(db, e["reloj"]).registrar(
                tipo=T.SESION_CREADA, resultado=R.EXITO, usuario_id=usuario_id, sesion_id=sesion.id)
            # Flush del commit, después de que ambos servicios devolvieron resultados.
            db.add(Usuario(nombre="Duplicado", correo=correo, hash_contrasena="secreto-no-log"))
    assert error.value.codigo == C.TRANSACCION
    assert correo not in str(error.value)
    assert sesion.credencial.get_secret_value() not in str(error.value)
    with Session(e["motor"]) as db:
        assert db.get(Sesion, sesion.id) is None
        assert db.get(EventoAutenticacion, evento.id) is None
        assert db.get(LimiteAutenticacion, reserva.id) is None
    assert not filas_cuota(e)
    assert not caplog.records


def test_auditoria_fk_invalida_revierte_efectos_y_sanea_error(entorno_c, caplog):
    e = entorno_c
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (servicio, db):
            servicio.reservar(cuenta=e["cuenta"], ip=e["ip"])
            ServicioAuditoria(db).registrar(tipo=T.LOGIN, resultado=R.EXITO, sesion_id=uuid4())
    assert error.value.codigo == C.TRANSACCION
    assert not filas_cuota(e)
    assert not caplog.records


def test_fallo_auditoria_revierte_revocacion(entorno_c):
    e = entorno_c
    with operacion(e) as (_, db):
        usuario = crear_usuario(db)
        sesion = ServicioSesiones(db, e["reloj"]).crear(usuario.id)
    with pytest.raises(ErrorSeguridad):
        with operacion(e) as (_, db):
            assert ServicioSesiones(db, e["reloj"]).revocar(sesion.credencial)
            ServicioAuditoria(db).registrar(tipo=T.SESION_REVOCADA, resultado=R.EXITO, usuario_id=uuid4())
    with Session(e["motor"]) as db:
        assert db.get(Sesion, sesion.id).revocada_en is None


def test_reserva_confirmada_conserva_cuota_finita_tras_fallo_posterior(entorno_c):
    e = entorno_c
    reserva = reservar(e).reserva
    with pytest.raises(ErrorSeguridad):
        with operacion(e) as (servicio, db):
            assert servicio.consolidar(reserva)
            ServicioAuditoria(db).registrar(tipo=T.LOGIN, resultado=R.EXITO, usuario_id=uuid4())
    assert [(f.intentos, f.reservas) for f in filas_cuota(e)] == [(0, 1), (0, 1)]
    e["ahora"] += timedelta(seconds=60)
    assert reservar(e).permitido


@pytest.mark.parametrize("relaciones", ["ninguna", "usuario", "sesion", "ambas"])
def test_auditoria_relaciones_opcionales(entorno_c, relaciones):
    e = entorno_c
    with operacion(e) as (_, db):
        usuario = crear_usuario(db)
        sesion = ServicioSesiones(db, e["reloj"]).crear(usuario.id)
        usuario_id = usuario.id if relaciones in {"usuario", "ambas"} else None
        sesion_id = sesion.id if relaciones in {"sesion", "ambas"} else None
        evento = ServicioAuditoria(db).registrar(
            tipo=T.VALIDACION, resultado=R.RECHAZO, usuario_id=usuario_id, sesion_id=sesion_id)
    with Session(e["motor"]) as db:
        fila = db.get(EventoAutenticacion, evento.id)
        assert fila.usuario_id == usuario_id and fila.sesion_id == sesion_id
        assert fila.motivo is None and fila.request_id is None and fila.ip_verificada_digest is None


def test_rechazo_auditado_despues_del_rollback_conserva_evento(entorno_c):
    e = entorno_c
    with pytest.raises(RuntimeError):
        with operacion(e) as (servicio, _):
            servicio.reservar(cuenta=e["cuenta"], ip=e["ip"])
            raise RuntimeError("rechazo")
    # Transacción independiente: el rechazo no se pierde con la operación fallida.
    with operacion(e) as (_, db):
        evento = ServicioAuditoria(db).registrar(tipo=T.LOGIN, resultado=R.RECHAZO, motivo=M.CREDENCIALES_INVALIDAS)
    with Session(e["motor"]) as db:
        assert db.get(EventoAutenticacion, evento.id) is not None
    assert not filas_cuota(e)


def test_auditoria_indisponible_no_devuelve_evento_persistido(entorno_c, caplog):
    e = entorno_c
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (_, db):
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            with e["motor"].connect() as otra:
                assert otra.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}).scalar_one()
            ServicioAuditoria(db).registrar(tipo=T.VALIDACION, resultado=R.RECHAZO, motivo=M.INFRAESTRUCTURA)
    assert error.value.codigo == C.INFRAESTRUCTURA
    assert not caplog.records


def test_limites_exigen_transaccion_limpia_y_auditoria_transaccion_activa(entorno_c):
    e = entorno_c
    with e["Session"](e["motor"]) as db:
        servicio = ServicioLimites(db, e["configuracion"], e["identificadores"])
        with pytest.raises(ErrorSeguridad) as error:
            servicio.reservar(cuenta=e["cuenta"], ip=e["ip"])
        assert error.value.codigo == C.TRANSACCION
        with pytest.raises(ErrorSeguridad):
            ServicioAuditoria(db).registrar(tipo=T.LOGIN, resultado=R.RECHAZO)
    with pytest.raises(ErrorSeguridad) as error:
        with operacion(e) as (servicio, db):
            db.add(Usuario(nombre="Pendiente", correo=f"{uuid4()}@example.invalid", hash_contrasena="hash ficticio"))
            servicio.reservar(cuenta=e["cuenta"], ip=e["ip"])
    assert error.value.codigo == C.TRANSACCION
