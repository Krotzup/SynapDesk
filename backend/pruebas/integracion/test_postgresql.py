import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.aplicacion import crear_aplicacion
from app.configuracion import Configuracion
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


def test_ejemplo_directo_inicia_salud_y_disponibilidad_sin_servicios_auth(
    configuracion_bd_test, tmp_path, monkeypatch,
) -> None:
    from app.seguridad.identificadores import ServicioIdentificadores
    from app.seguridad.limites import ServicioLimites

    assert configuracion_bd_test.postgres_host in {"localhost", "127.0.0.1", "::1"}
    assert configuracion_bd_test.postgres_port == 5433
    archivo = tmp_path / ".env"
    archivo.write_text(
        (Path(__file__).resolve().parents[3] / ".env.example").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # Solo sustituir los requisitos PostgreSQL preexistentes por la base aislada.
    for campo in ("host", "port", "db", "user", "password"):
        valor = getattr(configuracion_bd_test, f"postgres_{campo}")
        if campo == "password":
            valor = valor.get_secret_value()
        monkeypatch.setenv(f"POSTGRES_{campo.upper()}", str(valor))
    for campo in Configuracion.model_fields:
        if campo.startswith("auth_"):
            monkeypatch.delenv(campo.upper(), raising=False)
    monkeypatch.setitem(Configuracion.model_config, "env_file", archivo)

    def construccion_no_permitida(*args, **kwargs):
        pytest.fail("El backend básico no debe construir servicios de autenticación.")

    monkeypatch.setattr(ServicioIdentificadores, "__init__", construccion_no_permitida)
    monkeypatch.setattr(ServicioLimites, "__init__", construccion_no_permitida)
    configuracion = Configuracion()
    assert configuracion.auth_hmac_clave is None
    assert configuracion.auth_limite_cuenta_intentos is None
    with TestClient(crear_aplicacion()) as cliente:
        assert cliente.get("/api/v1/health").status_code == 200
        respuesta = cliente.get("/api/v1/ready")
        assert respuesta.status_code == 200
        assert respuesta.json()["database"] == "ok"
