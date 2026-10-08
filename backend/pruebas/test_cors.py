from fastapi.testclient import TestClient

from app.configuracion import Configuracion
from app.main import crear_aplicacion


def crear_cliente() -> TestClient:
    configuracion = Configuracion(
        _env_file=None,
        app_env="testing",
        backend_cors_origins=["http://localhost:3000"],
    )
    return TestClient(crear_aplicacion(configuracion))


def test_cors_permite_el_frontend_configurado() -> None:
    with crear_cliente() as cliente:
        respuesta = cliente.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rechaza_un_origen_no_configurado() -> None:
    with crear_cliente() as cliente:
        respuesta = cliente.options(
            "/api/v1/health",
            headers={
                "Origin": "https://otro.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert respuesta.status_code == 400
    assert "access-control-allow-origin" not in respuesta.headers
