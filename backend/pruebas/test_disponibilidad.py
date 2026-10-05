from unittest.mock import MagicMock
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

from app.configuracion import Configuracion
from app.main import crear_aplicacion
from app.persistencia.conexion import obtener_motor_bd


def crear_app_prueba():
    return crear_aplicacion(
        Configuracion(
            _env_file=None,
            app_env="testing",
            postgres_db=None,
            postgres_user=None,
            postgres_password=None,
        )
    )


def test_disponibilidad_con_consulta_exitosa() -> None:
    motor = MagicMock(spec=Engine)
    conexion = motor.connect.return_value.__enter__.return_value
    conexion.execute.return_value.scalar_one.return_value = 1
    app = crear_app_prueba()
    app.dependency_overrides[obtener_motor_bd] = lambda: motor

    with TestClient(app) as cliente:
        respuesta = cliente.get("/api/v1/ready")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "status": "ready",
        "service": "synapdesk-backend",
        "database": "ok",
    }


def test_error_de_conexion_no_revela_informacion_interna(caplog) -> None:
    motor = MagicMock(spec=Engine)
    secreto = "clave_privada_no_publicar"
    motor.connect.side_effect = OperationalError(
        "consulta_interna", {}, Exception(secreto)
    )
    app = crear_app_prueba()
    app.dependency_overrides[obtener_motor_bd] = lambda: motor

    with TestClient(app) as cliente:
        respuesta = cliente.get("/api/v1/ready")
        respuesta_salud = cliente.get("/api/v1/health")

    assert respuesta.status_code == 503
    error = respuesta.json()["error"]
    assert error["code"] == "DATABASE_UNAVAILABLE"
    assert error["message"] == "La base de datos no está disponible."
    assert error["details"] is None
    UUID(error["requestId"])
    for dato in (secreto, "consulta_interna"):
        assert dato not in respuesta.text
        assert dato not in caplog.text
    assert respuesta_salud.status_code == 200


def test_sin_configuracion_bd_la_api_responde_pero_no_esta_lista() -> None:
    with TestClient(crear_app_prueba()) as cliente:
        assert cliente.get("/api/v1/health").status_code == 200
        assert cliente.get("/api/v1/ready").status_code == 503
