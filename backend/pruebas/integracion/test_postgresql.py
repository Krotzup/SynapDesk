import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import crear_aplicacion
from app.persistencia.conexion import crear_motor_bd

pytestmark = pytest.mark.skipif(
    os.getenv("EJECUTAR_PRUEBAS_BD") != "1",
    reason="Requiere db_test y EJECUTAR_PRUEBAS_BD=1.",
)


def test_postgresql_y_pgvector_en_base_de_pruebas(configuracion_bd_test) -> None:
    motor = crear_motor_bd(configuracion_bd_test)
    try:
        with motor.connect() as conexion:
            nombre = conexion.execute(text("SELECT current_database()")).scalar_one()
            version = conexion.execute(text("SHOW server_version_num")).scalar_one()
            vector = conexion.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one()
        assert nombre == configuracion_bd_test.postgres_db
        assert int(version) // 10000 == 17
        assert vector == "0.8.6"
    finally:
        motor.dispose()


def test_disponibilidad_con_postgresql_real(configuracion_bd_test) -> None:
    with TestClient(crear_aplicacion(configuracion_bd_test)) as cliente:
        respuesta = cliente.get("/api/v1/ready")
    assert respuesta.status_code == 200
    assert respuesta.json()["database"] == "ok"
