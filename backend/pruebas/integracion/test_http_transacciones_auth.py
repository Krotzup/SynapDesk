from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import Depends, Response
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.aplicacion import crear_aplicacion
from app.api.cookies_auth import PerfilCookies, emitir_cookie
from app.api.dependencias_auth import SesionHttp, obtener_sesion
from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import Usuario
from app.seguridad.secretos import generar_secreto
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad, transaccion_seguridad


@pytest.fixture
def entorno_http(configuracion_bd_test):
    assert configuracion_bd_test.postgres_port == 5433
    assert configuracion_bd_test.postgres_host in {"localhost","127.0.0.1","::1"}
    motor = crear_motor_bd(configuracion_bd_test)
    creados = set()
    app = crear_aplicacion(configuracion_bd_test)

    def agregar(db):
        identificador = uuid4()
        creados.add(identificador)
        usuario = Usuario(id=identificador, nombre="Ficticio AUTH07A",
                          correo=f"{identificador}@example.invalid", hash_contrasena="hash_ficticio",
                          rol="agent", activo=True)
        db.add(usuario)
        db.flush()
        return identificador

    e = dict(app=app, motor=motor, agregar=agregar)
    try:
        yield e
    finally:
        try:
            with Session(motor) as db, db.begin():
                db.execute(delete(Usuario).where(Usuario.id.in_(creados)))
        finally:
            motor.dispose()


def existe(e, identificador):
    with Session(e["motor"]) as db:
        return db.scalar(select(Usuario.id).where(Usuario.id == identificador)) is not None


def test_http_commit_explicito_precede_cookie_y_resultado_persistente(entorno_http):
    e = entorno_http
    comprobados = []

    @e["app"].post("/prueba")
    def prueba(db: SesionHttp):
        with transaccion_seguridad(db):
            identificador = e["agregar"](db)
            assert not existe(e,identificador)  # Otra conexión aún no ve el efecto.
        assert existe(e,identificador)  # Commit antes de preparar la cookie.
        comprobados.append(identificador)
        respuesta = Response(status_code=204)
        ahora = datetime.now(UTC)
        emitir_cookie(respuesta,PerfilCookies("testing","http://localhost:3000","s","c"),
                      "sesion",generar_secreto(),ahora=ahora,vence_en=ahora+timedelta(seconds=30))
        return respuesta

    with TestClient(e["app"]) as cliente:
        respuesta = cliente.post("/prueba")
    assert respuesta.status_code == 204 and "set-cookie" in respuesta.headers
    assert len(comprobados) == 1 and existe(e,comprobados[0])


def test_http_cierre_no_confirma_escrituras_sin_commit(entorno_http):
    e = entorno_http
    identificadores = []

    @e["app"].post("/prueba")
    def prueba(db: SesionHttp):
        identificadores.append(e["agregar"](db))
        return {}

    with TestClient(e["app"]) as cliente:
        assert cliente.post("/prueba").status_code == 200
    assert not existe(e,identificadores[0])


def test_http_rollback_por_error_no_emite_cookie(entorno_http, caplog):
    e = entorno_http
    identificadores = []

    @e["app"].post("/prueba")
    def prueba(db: SesionHttp):
        with transaccion_seguridad(db):
            identificadores.append(e["agregar"](db))
            raise ErrorSeguridad(C.INFRAESTRUCTURA)

    with TestClient(e["app"]) as cliente:
        r = cliente.post("/prueba")
    assert r.status_code == 503 and r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "set-cookie" not in r.headers and not existe(e,identificadores[0])
    assert "hash_ficticio" not in r.text and "hash_ficticio" not in caplog.text


def test_http_fallo_real_de_commit_revierte_y_no_publica_exito(entorno_http, caplog):
    e = entorno_http
    identificadores = []

    @e["app"].post("/prueba")
    def prueba(db: SesionHttp):
        with transaccion_seguridad(db):
            identificadores.append(e["agregar"](db))
            # El flush anterior pasó. Esta restricción se verifica al COMMIT.
            db.execute(text("CREATE TEMP TABLE auth07a_commit (n int UNIQUE DEFERRABLE INITIALLY DEFERRED) ON COMMIT DROP"))
            db.execute(text("INSERT INTO auth07a_commit VALUES (1),(1)"))
        pytest.fail("No debe construir respuesta de éxito tras fallo de commit")

    with TestClient(e["app"]) as cliente:
        r = cliente.post("/prueba")
    assert r.status_code == 503 and "set-cookie" not in r.headers
    assert not existe(e,identificadores[0])
    for secreto in ("auth07a_commit","INSERT INTO","hash_ficticio"):
        assert secreto not in r.text and secreto not in caplog.text


def test_http_peticiones_concurrentes_usan_sesiones_y_conexiones_distintas(entorno_http):
    e = entorno_http
    barrera = Barrier(2)
    sesiones = []

    @e["app"].get("/prueba")
    def prueba(db: SesionHttp):
        sesiones.append(db)  # Retener referencias para evitar reutilización de id().
        with transaccion_seguridad(db):
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            barrera.wait(timeout=10)
        return {"pid":pid}

    with TestClient(e["app"]) as cliente, ThreadPoolExecutor(max_workers=2) as ejecutor:
        respuestas = list(ejecutor.map(lambda _:cliente.get("/prueba"),range(2)))
    assert all(r.status_code == 200 for r in respuestas)
    assert sesiones[0] is not sesiones[1]
    assert len({r.json()["pid"] for r in respuestas}) == 2
    assert all(not db.in_transaction() for db in sesiones)


def test_http_dependencia_reutilizada_solo_dentro_de_la_peticion(entorno_http):
    e = entorno_http

    @e["app"].get("/prueba")
    def prueba(db: SesionHttp, segunda: Session = Depends(obtener_sesion, scope="function")):
        assert db is segunda
        with transaccion_seguridad(db):
            assert db.scalar(text("SELECT 1")) == 1
        return {}

    with TestClient(e["app"]) as cliente:
        assert cliente.get("/prueba").status_code == 200


def test_http_cierre_sesion_termina_antes_de_enviar_respuesta(entorno_http):
    e = entorno_http
    identificadores = []
    # Observar la base desde el emisor ASGI al comenzar la respuesta acredita
    # scope=function: el rollback de la dependencia ocurrió antes de headers.
    observados = []
    sesiones = []

    @e["app"].post("/prueba")
    def prueba(db: SesionHttp):
        sesiones.append(db)
        identificadores.append(e["agregar"](db))
        return {}

    class ObservarEnvio:
        async def __call__(self, scope, receive, send):
            async def observar(mensaje):
                if mensaje["type"] == "http.response.start":
                    observados.append(not sesiones[0].in_transaction())
                await send(mensaje)
            await e["app"](scope, receive, observar)

    with TestClient(ObservarEnvio()) as cliente:
        r = cliente.post("/prueba")
        assert r.status_code == 200 and not existe(e,identificadores[0])
    assert observados == [True]
