from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.aplicacion import crear_aplicacion
from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import ContextoCsrf, TokenCsrf, Sesion, LimiteAutenticacion, EventoAutenticacion


def cantidades(motor):
    with motor.connect() as conexion:
        return tuple(conexion.scalar(select(func.count()).select_from(modelo)) for modelo in (
            ContextoCsrf, TokenCsrf, Sesion, LimiteAutenticacion, EventoAutenticacion,
        ))


@pytest.mark.parametrize("cabeceras,estado", [
    ({"Origin": "http://localhost:3000"}, 503),
    ({"Sec-Fetch-Site": "same-origin"}, 503),
    ({"Origin": "null"}, 403),
    ({"Origin": "http://localhost:3000", "Cookie": "synapdesk_csrf_context_dev=antigua_ficticia"}, 503),
])
def test_rechazo_bootstrap_no_persiste_contextos_ni_tokens(configuracion_bd_test, cabeceras, estado):
    assert configuracion_bd_test.postgres_port == 5433
    assert configuracion_bd_test.postgres_host in {"localhost", "127.0.0.1", "::1"}
    configuracion = configuracion_bd_test.model_copy(update={
        "auth_origenes_permitidos": ["http://localhost:3000"],
    })
    motor = crear_motor_bd(configuracion)
    try:
        antes = cantidades(motor)
        with TestClient(crear_aplicacion(configuracion)) as cliente:
            respuesta = cliente.get("/api/v1/auth/csrf", headers=cabeceras)
        assert respuesta.status_code == estado
        assert "set-cookie" not in respuesta.headers
        assert cantidades(motor) == antes
    finally:
        motor.dispose()


def test_emision_concurrente_sigue_cerrada_sin_consumir_persistencia(configuracion_bd_test):
    assert configuracion_bd_test.postgres_port == 5433
    assert configuracion_bd_test.postgres_host in {"localhost", "127.0.0.1", "::1"}
    configuracion = configuracion_bd_test.model_copy(update={
        "auth_origenes_permitidos": ["http://localhost:3000"],
    })
    motor = crear_motor_bd(configuracion)
    try:
        antes = cantidades(motor)
        with TestClient(crear_aplicacion(configuracion)) as cliente, ThreadPoolExecutor(max_workers=4) as ejecutor:
            respuestas = list(ejecutor.map(lambda _: cliente.get("/api/v1/auth/csrf", headers={
                "Origin": "http://localhost:3000", "X-Forwarded-For": "198.51.100.79",
            }), range(20)))
        assert all(r.status_code == 503 and "set-cookie" not in r.headers for r in respuestas)
        assert cantidades(motor) == antes
    finally:
        motor.dispose()
