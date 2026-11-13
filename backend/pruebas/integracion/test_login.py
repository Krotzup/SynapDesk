"""Login con Argon2 y commits/locks reales; sin rutas HTTP de ensayo."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event, Lock
from time import monotonic, sleep
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, event, func, select, text, update
from sqlalchemy.orm import Session

from app.persistencia.conexion import construir_url_bd, crear_motor_bd
from app.persistencia.modelos import (
    ContextoCsrf, EventoAutenticacion, LimiteAutenticacion, Sesion, TokenCsrf, Usuario,
)
from app.seguridad.auditoria import MotivoEvento as M
from app.seguridad.contrasenas import ErrorContrasena, ServicioContrasenas
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.login import (
    CredencialesLogin, LoginConfirmado, LoginRechazado, PruebaAnonimaLogin,
    PruebaSesionLogin, ServicioLogin,
)
from app.seguridad.secretos import digest_secreto, generar_secreto
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad, transaccion_seguridad
from pruebas.login_auxiliar import configuracion_login, ip_controlada


@pytest.fixture
def entorno_login(configuracion_bd_test):
    config = configuracion_login()
    motor = crear_motor_bd(configuracion_bd_test)
    with motor.connect() as db:
        assert configuracion_bd_test.postgres_port == 5433
        assert db.scalar(text("SELECT current_database()" )).startswith("synapdesk_auth07_sec01a_")
    e = dict(config=config, motor=motor, ahora=datetime(2026, 11, 12, tzinfo=UTC),
             clave=generar_secreto(), ip=ip_controlada(config))
    e["reloj"] = lambda db: e["ahora"]
    e["passwords"] = ServicioContrasenas(config)
    e["servicio"] = ServicioLogin(motor, config, capacidad_argon2=8, reloj=e["reloj"])
    clases = (EventoAutenticacion, TokenCsrf, ContextoCsrf, Sesion, LimiteAutenticacion, Usuario)
    ids = {clase: set() for clase in clases}
    candado = Lock()

    def recordar(db, contexto):
        if db.get_bind().pool is motor.pool:
            with candado:
                for fila in db.new:
                    if type(fila) in ids and fila.id is not None:
                        ids[type(fila)].add(fila.id)

    event.listen(Session, "after_flush", recordar)
    try:
        e["usuario"] = crear_usuario(e)
        yield e
    finally:
        event.remove(Session, "after_flush", recordar)
        try:
            with motor.begin() as db:
                for clase in clases:
                    db.execute(delete(clase).where(clase.id.in_(ids[clase])))
        finally:
            motor.dispose()


def crear_usuario(e, **cambios):
    datos = dict(nombre="Ensayo interno", correo=f"login-{uuid4()}@example.invalid",
                 hash_contrasena=e["passwords"].generar_hash(e["clave"].get_secret_value()),
                 activo=True, rol="agent") | cambios
    with Session(e["motor"], expire_on_commit=False) as db, transaccion_seguridad(db):
        usuario = Usuario(**datos)
        db.add(usuario)
        db.flush()
    return usuario


def anonimo(e):
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        csrf = ServicioCsrf(db, e["config"], e["reloj"])
        contexto = csrf.crear_anonimo()
        token = csrf.emitir_token(anonimo=contexto.secreto)
    return contexto, token


def preparar(e, *, par=None, servicio=None, ip=None):
    par = par or anonimo(e)
    servicio = servicio or e["servicio"]
    prueba = PruebaAnonimaLogin(par[0].secreto, par[1].token)
    return servicio.validar_contexto(prueba, ip=ip or e["ip"])


def entrada(e, **cambios):
    return CredencialesLogin(**(dict(cuenta=e["usuario"].correo, contrasena=e["clave"]) | cambios))


def login(e, **cambios):
    return e["servicio"].autenticar(entrada(e, **cambios), preparar(e))


def filas(e, modelo):
    with Session(e["motor"]) as db:
        return db.scalars(select(modelo)).all()


def cuotas(e):
    return sorted((f.tipo_clave, f.intentos, f.reservas) for f in filas(e, LimiteAutenticacion)
                  if f.tipo_clave in {"cuenta", "ip"})


def motivos(e):
    return [f.motivo for f in filas(e, EventoAutenticacion)]


@pytest.mark.parametrize("rol", ["admin", "agent"])
def test_login_correcto_persistido_con_identidad_minima_y_secretos_ocultos(entorno_login, rol, caplog):
    e = entorno_login
    with e["motor"].begin() as db:
        db.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(rol=rol))
    par = anonimo(e)
    resultado = e["servicio"].autenticar(entrada(e, cuenta="  " + e["usuario"].correo.upper() + "  "),
                                       preparar(e, par=par))
    assert isinstance(resultado, LoginConfirmado)
    assert resultado.usuario.id == e["usuario"].id and resultado.usuario.role == rol
    assert resultado.usuario.email == e["usuario"].correo
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        sesion = db.get(Sesion, resultado.sesion.id)
        assert sesion.digest_credencial == digest_secreto(resultado.sesion.credencial, C.SESION_INEXISTENTE)
        assert sesion.expira_en == sesion.creado_en + timedelta(hours=8)
        assert ServicioSesiones(db, e["reloj"]).consultar(resultado.sesion.credencial).usuario == resultado.usuario
        anterior = db.get(ContextoCsrf, par[0].id)
        assert anterior.revocado_en is not None
        assert all(f.invalidado_en is not None for f in db.scalars(select(TokenCsrf).where(
            TokenCsrf.contexto_id == anterior.id)))
        nuevo = db.scalar(select(ContextoCsrf).where(ContextoCsrf.sesion_id == sesion.id))
        assert nuevo.tipo == "authenticated" and nuevo.id != anterior.id
    assert cuotas(e) == [("cuenta", 1, 0), ("ip", 1, 0)]
    assert sorted(motivos(e)) == sorted([M.CREDENCIALES_VALIDAS, M.CREACION])
    texto = repr(resultado) + caplog.text + repr(filas(e, EventoAutenticacion))
    for secreto in (e["clave"], resultado.sesion.credencial, par[0].secreto, par[1].token):
        assert secreto.get_secret_value() not in texto


@pytest.mark.parametrize("caso", ["ausente", "inactiva", "incorrecta"])
def test_credenciales_rechazadas_uniformes_con_cuota_y_auditoria(entorno_login, caso, monkeypatch):
    e = entorno_login
    cambios = {}
    if caso == "ausente":
        cambios["cuenta"] = f"ausente-{uuid4()}@example.invalid"
    elif caso == "inactiva":
        with e["motor"].begin() as db:
            db.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(activo=False))
    else:
        cambios["contrasena"] = generar_secreto()
    original = e["servicio"]._contrasenas.verificar
    calculos = []

    def verificar(hash, clave):
        # No hay conexión abierta ni locks del coordinador durante Argon2.
        assert e["motor"].pool.checkedout() == 0
        calculos.append(True)
        return original(hash, clave)

    monkeypatch.setattr(e["servicio"]._contrasenas, "verificar", verificar)
    assert login(e, **cambios) == LoginRechazado(M.CREDENCIALES_INVALIDAS)
    assert calculos == [True]
    assert filas(e, Sesion) == []
    assert motivos(e) == [M.CREDENCIALES_INVALIDAS]
    evento = filas(e, EventoAutenticacion)[0]
    assert evento.usuario_id is None and evento.sesion_id is None
    assert cuotas(e) == [("cuenta", 1, 0), ("ip", 1, 0)]


@pytest.mark.parametrize("caso", ["hash_invalido", "argon2"])
def test_fallo_interno_de_hash_no_es_credencial_incorrecta(entorno_login, caso, monkeypatch):
    e = entorno_login
    if caso == "hash_invalido":
        with e["motor"].begin() as db:
            db.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(hash_contrasena="incompatible"))
    else:
        from argon2.exceptions import VerificationError
        def fallar(*args, **kwargs):
            raise VerificationError("entrada privada del driver Argon2")
        monkeypatch.setattr(type(e["servicio"]._contrasenas._hasher), "verify", fallar)
    with pytest.raises(ErrorContrasena) as error:
        login(e)
    assert "privada" not in str(error.value)
    assert filas(e, Sesion) == [] and motivos(e) == [M.INFRAESTRUCTURA]
    assert cuotas(e) == [("cuenta", 1, 0), ("ip", 1, 0)]


@pytest.mark.parametrize("caso", ["ausente", "incorrecto", "vencido", "contexto_vencido",
                                  "otro_contexto", "otro_navegador"])
def test_csrf_rechazado_antes_de_argon_y_de_reservas(entorno_login, caso, monkeypatch):
    e = entorno_login
    contexto, token = anonimo(e)
    secreto_contexto, secreto_token = contexto.secreto, token.token
    if caso == "ausente":
        secreto_token = SecretStr("")
    elif caso == "incorrecto":
        secreto_token = generar_secreto()
    elif caso == "vencido":
        e["ahora"] = token.expira_en
    elif caso == "contexto_vencido":
        e["ahora"] = contexto.expira_en
    elif caso == "otro_contexto":
        secreto_token = anonimo(e)[1].token
    else:
        secreto_contexto = anonimo(e)[0].secreto
    def prohibido(*args):
        pytest.fail("No debe calcular Argon2 ante CSRF inválido")
    monkeypatch.setattr(e["servicio"]._contrasenas, "verificar", prohibido)
    with pytest.raises(ErrorSeguridad) as error:
        e["servicio"].validar_contexto(PruebaAnonimaLogin(secreto_contexto, secreto_token), ip=e["ip"])
    assert error.value.codigo in {C.TOKEN_INVALIDO, C.TOKEN_VENCIDO, C.CONTEXTO_INVALIDO}
    assert filas(e, Sesion) == [] and filas(e, LimiteAutenticacion) == []
    assert motivos(e) == [M.CSRF]


def test_contexto_validado_no_congela_vigencia(entorno_login):
    e = entorno_login
    par = anonimo(e)
    prueba = preparar(e, par=par)
    e["ahora"] = par[1].expira_en
    with pytest.raises(ErrorSeguridad) as error:
        e["servicio"].autenticar(entrada(e), prueba)
    assert error.value.codigo == C.TOKEN_VENCIDO
    assert filas(e, Sesion) == [] and cuotas(e) == []


@pytest.mark.parametrize("ip", [None, True, "127.0.0.1", "198.51.100.1", uuid4()])
def test_ip_no_acreditada_rechazada(entorno_login, ip):
    e = entorno_login
    contexto, token = anonimo(e)
    with pytest.raises(ErrorSeguridad) as error:
        e["servicio"].validar_contexto(PruebaAnonimaLogin(contexto.secreto, token.token), ip=ip)
    assert error.value.codigo == C.IP_NO_VERIFICABLE
    assert filas(e, Sesion) == [] and cuotas(e) == []
    assert motivos(e) == [M.IP]


@pytest.mark.parametrize("ambito", ["cuenta", "ip"])
def test_limites_persistentes_no_reinician_por_exitos(entorno_login, ambito):
    e = entorno_login
    config = e["config"].model_copy(update={f"auth_limite_{ambito}_intentos": 1})
    servicio = ServicioLogin(e["motor"], config, capacidad_argon2=2, reloj=e["reloj"])
    resultado = servicio.autenticar(entrada(e), preparar(e, servicio=servicio))
    assert isinstance(resultado, LoginConfirmado)
    ip = ip_controlada(config, "198.51.100.9") if ambito == "cuenta" else e["ip"]
    cuenta = e["usuario"].correo if ambito == "cuenta" else "otra@example.invalid"
    rechazo = servicio.autenticar(entrada(e, cuenta=cuenta), preparar(e, servicio=servicio, ip=ip))
    assert rechazo.motivo == M.LIMITE and rechazo.limite.retry_after > 0
    assert len(filas(e, Sesion)) == 1 and M.LIMITE in motivos(e)


def test_concurrencia_limites_cuenta_e_ip_en_coordinador(entorno_login):
    e = entorno_login
    config = e["config"].model_copy(update={"auth_limite_cuenta_intentos": 2,
                                           "auth_limite_ip_intentos": 3})
    servicio = ServicioLogin(e["motor"], config, capacidad_argon2=8, reloj=e["reloj"])
    pruebas = [preparar(e, servicio=servicio) for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as grupo:
        resultados = list(grupo.map(lambda p: servicio.autenticar(entrada(e), p), pruebas))
    assert sum(isinstance(r, LoginConfirmado) for r in resultados) == 2
    assert sum(isinstance(r, LoginRechazado) and r.motivo == M.LIMITE for r in resultados) == 6
    assert cuotas(e) == [("cuenta", 2, 0), ("ip", 2, 0)]


def test_mismo_contexto_solo_puede_confirmar_un_login(entorno_login, monkeypatch):
    e = entorno_login
    contexto = preparar(e)
    barrera = Barrier(2)
    original = e["servicio"]._contrasenas.verificar
    def verificar(*args):
        resultado = original(*args)
        barrera.wait(timeout=5)
        return resultado
    monkeypatch.setattr(e["servicio"]._contrasenas, "verificar", verificar)
    def intentar(_):
        try:
            return e["servicio"].autenticar(entrada(e), contexto)
        except ErrorSeguridad as error:
            return error.codigo
    with ThreadPoolExecutor(max_workers=2) as grupo:
        resultados = list(grupo.map(intentar, range(2)))
    assert sum(isinstance(r, LoginConfirmado) for r in resultados) == 1
    assert resultados.count(C.CONTEXTO_INVALIDO) == 1
    assert len(filas(e, Sesion)) == 1 and cuotas(e) == [("cuenta", 2, 0), ("ip", 2, 0)]


def test_token_reutilizable_en_rechazos_pero_no_tras_login(entorno_login):
    e = entorno_login
    contexto = preparar(e)
    assert e["servicio"].autenticar(entrada(e, contrasena=generar_secreto()), contexto).motivo == M.CREDENCIALES_INVALIDAS
    assert isinstance(e["servicio"].autenticar(entrada(e), contexto), LoginConfirmado)
    with pytest.raises(ErrorSeguridad):
        e["servicio"].autenticar(entrada(e), contexto)
    assert len(filas(e, Sesion)) == 1


def test_reemplazo_usa_csrf_de_sesion_y_conserva_otro_dispositivo(entorno_login):
    e = entorno_login
    anterior, otro = login(e), login(e)
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        token = ServicioCsrf(db, e["config"], e["reloj"]).emitir_token(sesion=anterior.sesion.credencial)
    prueba = e["servicio"].validar_contexto(
        PruebaSesionLogin(anterior.sesion.credencial, token.token), ip=e["ip"])
    nueva = e["servicio"].autenticar(entrada(e), prueba)
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        assert db.get(Sesion, anterior.sesion.id).revocada_en is not None
        assert db.get(Sesion, anterior.sesion.id).motivo_revocacion == "reemplazo"
        assert ServicioSesiones(db, e["reloj"]).consultar(otro.sesion.credencial)
        assert ServicioSesiones(db, e["reloj"]).consultar(nueva.sesion.credencial)
        viejo = db.scalar(select(ContextoCsrf).where(ContextoCsrf.sesion_id == anterior.sesion.id))
        assert viejo.revocado_en is not None
    assert M.REEMPLAZO in motivos(e)


@pytest.mark.parametrize("caso", ["desconocida", "vencida", "revocada", "token_anonimo"])
def test_recuperacion_de_sesion_previa_no_se_inventa(entorno_login, caso):
    e = entorno_login
    anterior = login(e)
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        token = ServicioCsrf(db, e["config"], e["reloj"]).emitir_token(sesion=anterior.sesion.credencial)
        if caso == "revocada":
            ServicioSesiones(db, e["reloj"]).revocar(anterior.sesion.credencial)
    sesion = anterior.sesion.credencial
    if caso == "desconocida":
        sesion = generar_secreto()
    elif caso == "vencida":
        e["ahora"] += timedelta(minutes=30)
    secreto = anonimo(e)[1].token if caso == "token_anonimo" else token.token
    with pytest.raises(ErrorSeguridad):
        e["servicio"].validar_contexto(PruebaSesionLogin(sesion, secreto), ip=e["ip"])
    assert len(filas(e, Sesion)) == 1


@pytest.mark.parametrize("segundos", [1800, 28800])
def test_expiracion_de_sesion_creada_por_login(entorno_login, segundos):
    e = entorno_login
    resultado = login(e)
    if segundos == 28800:
        with e["motor"].begin() as db:
            db.execute(update(Sesion).where(Sesion.id == resultado.sesion.id).values(
                ultima_actividad=e["ahora"] + timedelta(hours=7, minutes=59)))
    e["ahora"] += timedelta(seconds=segundos)
    with pytest.raises(ErrorSeguridad) as error:
        with Session(e["motor"]) as db, transaccion_seguridad(db):
            ServicioSesiones(db, e["reloj"]).consultar(resultado.sesion.credencial)
    assert error.value.codigo == C.SESION_VENCIDA


@pytest.mark.parametrize("cambio", ["hash", "estado", "rol", "correo"])
def test_cambio_durante_argon_revalida_usuario_sin_bloquearlo(entorno_login, cambio, monkeypatch):
    e = entorno_login
    original = e["servicio"]._contrasenas.verificar
    def verificar(*args):
        resultado = original(*args)
        assert e["motor"].pool.checkedout() == 0
        valores = {"hash": dict(hash_contrasena=e["passwords"].generar_hash(generar_secreto().get_secret_value())),
                   "estado": dict(activo=False), "rol": dict(rol="admin"),
                   "correo": dict(correo=f"nuevo-{uuid4()}@example.invalid")}[cambio]
        with e["motor"].begin() as db:
            db.execute(update(Usuario).where(Usuario.id == e["usuario"].id).values(**valores))
        return resultado
    monkeypatch.setattr(e["servicio"]._contrasenas, "verificar", verificar)
    resultado = login(e)
    if cambio == "rol":
        assert isinstance(resultado, LoginConfirmado) and resultado.usuario.role == "admin"
    else:
        assert resultado == LoginRechazado(M.CREDENCIALES_INVALIDAS) and filas(e, Sesion) == []


def test_reserva_expirada_durante_argon_no_autoriza_sesion(entorno_login, monkeypatch):
    e = entorno_login
    original = e["servicio"]._contrasenas.verificar
    def verificar(*args):
        resultado = original(*args)
        e["ahora"] += timedelta(seconds=120)
        return resultado
    monkeypatch.setattr(e["servicio"]._contrasenas, "verificar", verificar)
    with pytest.raises(ErrorSeguridad) as error:
        login(e)
    assert error.value.codigo == C.RESERVA_INVALIDA
    assert filas(e, Sesion) == [] and M.INFRAESTRUCTURA in motivos(e)
    assert cuotas(e) == [("cuenta", 0, 1), ("ip", 0, 1)]
    monkeypatch.setattr(e["servicio"]._contrasenas, "verificar", original)
    # Solo el cambio de ventana normal del servicio permite otro intento.
    assert isinstance(login(e), LoginConfirmado)
    assert cuotas(e) == [("cuenta", 1, 0), ("ip", 1, 0)]


@pytest.mark.parametrize("reemplazo", [False, True])
def test_commit_real_fallido_revierte_sesion_contextos_y_eventos(entorno_login, reemplazo):
    e = entorno_login
    anterior = login(e) if reemplazo else None
    if anterior is not None:
        with Session(e["motor"]) as db, transaccion_seguridad(db):
            token = ServicioCsrf(db, e["config"], e["reloj"]).emitir_token(sesion=anterior.sesion.credencial)
        contexto = e["servicio"].validar_contexto(
            PruebaSesionLogin(anterior.sesion.credencial, token.token), ip=e["ip"])
    else:
        contexto = preparar(e)
    contextos_iniciales = {c.id: c.revocado_en for c in filas(e, ContextoCsrf)}
    motivos_iniciales = motivos(e)
    def marcar(db, flush):
        if db.get_bind().pool is e["motor"].pool and any(isinstance(f, Sesion) for f in db.new):
            db.info["fallar_login"] = True
    def impedir_commit(db):
        if db.info.pop("fallar_login", False):
            # La violación se comprueba realmente en COMMIT, tras todos los flush.
            db.execute(text("CREATE TEMP TABLE fallo_login (n int UNIQUE DEFERRABLE INITIALLY DEFERRED) ON COMMIT DROP"))
            db.execute(text("INSERT INTO fallo_login VALUES (1), (1)"))
    event.listen(Session, "after_flush", marcar)
    event.listen(Session, "before_commit", impedir_commit)
    try:
        with pytest.raises(ErrorSeguridad) as error:
            e["servicio"].autenticar(entrada(e), contexto)
        assert error.value.codigo == C.TRANSACCION
    finally:
        event.remove(Session, "after_flush", marcar)
        event.remove(Session, "before_commit", impedir_commit)
    assert len(filas(e, Sesion)) == int(reemplazo)
    assert {c.id: c.revocado_en for c in filas(e, ContextoCsrf)} == contextos_iniciales
    assert sorted(motivos(e)) == sorted(motivos_iniciales + [M.INFRAESTRUCTURA])
    consumidos = 2 if reemplazo else 1
    assert cuotas(e) == [("cuenta", consumidos, 0), ("ip", consumidos, 0)]
    if anterior is not None:
        with Session(e["motor"]) as db, transaccion_seguridad(db):
            assert ServicioSesiones(db, e["reloj"]).consultar(anterior.sesion.credencial)
            ServicioCsrf(db, e["config"], e["reloj"]).validar_token(
                token.token, sesion=anterior.sesion.credencial)


def test_fallo_auditoria_impide_confirmar_login_y_revierte_contexto(entorno_login, monkeypatch):
    e = entorno_login
    from app.seguridad.auditoria import ServicioAuditoria, ResultadoEvento
    original = ServicioAuditoria.registrar
    def registrar(self, **datos):
        if datos["resultado"] == ResultadoEvento.EXITO:
            self.db.execute(text("SELECT 1 / 0"))
        return original(self, **datos)
    monkeypatch.setattr(ServicioAuditoria, "registrar", registrar)
    with pytest.raises(ErrorSeguridad):
        login(e)
    assert filas(e, Sesion) == [] and motivos(e) == [M.INFRAESTRUCTURA]
    assert all(c.revocado_en is None for c in filas(e, ContextoCsrf))


def test_caida_real_postgresql_no_simula_evento_o_sesion(entorno_login, configuracion_bd_test):
    e = entorno_login
    contexto = preparar(e)
    url = construir_url_bd(configuracion_bd_test).set(database=configuracion_bd_test.postgres_db + "_inexistente")
    motor = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 2})
    original = e["servicio"]._motor
    e["servicio"]._motor = motor
    try:
        with pytest.raises(ErrorSeguridad) as error:
            e["servicio"].autenticar(entrada(e), contexto)
        assert error.value.codigo == C.INFRAESTRUCTURA
        assert "inexistente" not in str(error.value)
        assert filas(e, Sesion) == [] and filas(e, EventoAutenticacion) == []
    finally:
        e["servicio"]._motor = original
        motor.dispose()


def test_capacidad_argon_acotada_sin_abrir_transaccion(entorno_login, monkeypatch):
    e = entorno_login
    servicio = ServicioLogin(e["motor"], e["config"], capacidad_argon2=1, reloj=e["reloj"])
    pruebas = [preparar(e, servicio=servicio) for _ in range(2)]
    ocupado, continuar = Event(), Event()
    original = servicio._contrasenas.verificar
    def verificar(*args):
        ocupado.set()
        assert continuar.wait(timeout=5)
        return original(*args)
    monkeypatch.setattr(servicio._contrasenas, "verificar", verificar)
    with ThreadPoolExecutor(max_workers=1) as grupo:
        futuro = grupo.submit(servicio.autenticar, entrada(e), pruebas[0])
        try:
            assert ocupado.wait(timeout=5)
            assert e["motor"].pool.checkedout() == 0
            with pytest.raises(ErrorSeguridad) as error:
                servicio.autenticar(entrada(e), pruebas[1])
            assert error.value.codigo == C.INFRAESTRUCTURA
        finally:
            continuar.set()
        assert isinstance(futuro.result(timeout=5), LoginConfirmado)
    assert cuotas(e) == [("cuenta", 1, 0), ("ip", 1, 0)]


@pytest.mark.parametrize("vence", ["token", "reserva"])
def test_autorizacion_expira_mientras_espera_lock_postgresql(entorno_login, monkeypatch, vence):
    e = entorno_login
    par = anonimo(e)
    contexto = preparar(e, par=par)
    calculado, continuar = Event(), Event()
    original = e["servicio"]._contrasenas.verificar
    def verificar(*args):
        resultado = original(*args)
        calculado.set()
        assert continuar.wait(timeout=5)
        return resultado
    monkeypatch.setattr(e["servicio"]._contrasenas, "verificar", verificar)
    with ThreadPoolExecutor(max_workers=1) as grupo:
        futuro = grupo.submit(e["servicio"].autenticar, entrada(e), contexto)
        try:
            assert calculado.wait(timeout=5)
            with Session(e["motor"]) as db, transaccion_seguridad(db):
                db.scalar(select(ContextoCsrf).where(ContextoCsrf.id == par[0].id).with_for_update())
                continuar.set()
                limite = monotonic() + 5
                esperando = False
                while monotonic() < limite:
                    with e["motor"].connect() as observador:
                        esperando = observador.scalar(text("SELECT count(*) > 0 FROM pg_stat_activity "
                            "WHERE datname = current_database() AND wait_event_type = 'Lock'"))
                    if esperando:
                        break
                    sleep(0.01)
                assert esperando, "No se observó una espera real de lock PostgreSQL"
                e["ahora"] = par[1].expira_en if vence == "token" else e["ahora"] + timedelta(seconds=120)
        finally:
            continuar.set()
        with pytest.raises(ErrorSeguridad) as error:
            futuro.result(timeout=5)
        assert error.value.codigo == (C.TOKEN_VENCIDO if vence == "token" else C.RESERVA_INVALIDA)
    assert filas(e, Sesion) == []
    assert (M.CSRF if vence == "token" else M.INFRAESTRUCTURA) in motivos(e)


def test_reemplazo_rechazado_no_revoca_sesion_previa(entorno_login):
    e = entorno_login
    anterior = login(e)
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        token = ServicioCsrf(db, e["config"], e["reloj"]).emitir_token(sesion=anterior.sesion.credencial)
    contexto = e["servicio"].validar_contexto(
        PruebaSesionLogin(anterior.sesion.credencial, token.token), ip=e["ip"])
    resultado = e["servicio"].autenticar(entrada(e, contrasena=generar_secreto()), contexto)
    assert resultado == LoginRechazado(M.CREDENCIALES_INVALIDAS)
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        assert ServicioSesiones(db, e["reloj"]).consultar(anterior.sesion.credencial)
        ServicioCsrf(db, e["config"], e["reloj"]).validar_token(token.token, sesion=anterior.sesion.credencial)
    assert len(filas(e, Sesion)) == 1 and M.REEMPLAZO not in motivos(e)


def test_reemplazo_no_acepta_token_de_otra_sesion(entorno_login):
    e = entorno_login
    anterior, otro = login(e), login(e)
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        token = ServicioCsrf(db, e["config"], e["reloj"]).emitir_token(sesion=otro.sesion.credencial)
    with pytest.raises(ErrorSeguridad) as error:
        e["servicio"].validar_contexto(PruebaSesionLogin(anterior.sesion.credencial, token.token), ip=e["ip"])
    assert error.value.codigo == C.TOKEN_INVALIDO
    assert all(s.revocada_en is None for s in filas(e, Sesion))


def test_reemplazo_entre_usuarios_preserva_otras_sesiones(entorno_login):
    e = entorno_login
    anterior, otro = login(e), login(e)
    destino = crear_usuario(e, rol="admin")
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        token = ServicioCsrf(db, e["config"], e["reloj"]).emitir_token(sesion=anterior.sesion.credencial)
    contexto = e["servicio"].validar_contexto(
        PruebaSesionLogin(anterior.sesion.credencial, token.token), ip=e["ip"])
    nuevo = e["servicio"].autenticar(entrada(e, cuenta=destino.correo), contexto)
    assert nuevo.usuario.id == destino.id and nuevo.usuario.role == "admin"
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        assert ServicioSesiones(db, e["reloj"]).consultar(otro.sesion.credencial)
        assert db.get(Sesion, anterior.sesion.id).revocada_en is not None


def test_dos_reemplazos_concurrentes_no_reutilizan_sesion_revocada(entorno_login, monkeypatch):
    e = entorno_login
    anterior = login(e)
    with Session(e["motor"]) as db, transaccion_seguridad(db):
        token = ServicioCsrf(db, e["config"], e["reloj"]).emitir_token(sesion=anterior.sesion.credencial)
    contexto = e["servicio"].validar_contexto(
        PruebaSesionLogin(anterior.sesion.credencial, token.token), ip=e["ip"])
    original = e["servicio"]._contrasenas.verificar
    barrera = Barrier(2)
    def verificar(*args):
        resultado = original(*args)
        barrera.wait(timeout=5)
        return resultado
    monkeypatch.setattr(e["servicio"]._contrasenas, "verificar", verificar)
    def intentar(_):
        try:
            return e["servicio"].autenticar(entrada(e), contexto)
        except ErrorSeguridad as error:
            return error.codigo
    with ThreadPoolExecutor(max_workers=2) as grupo:
        resultados = list(grupo.map(intentar, range(2)))
    assert sum(isinstance(r, LoginConfirmado) for r in resultados) == 1
    assert resultados.count(C.SESION_REVOCADA) == 1
    assert len(filas(e, Sesion)) == 2
