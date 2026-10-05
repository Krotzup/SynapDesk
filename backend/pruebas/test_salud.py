from fastapi.testclient import TestClient

from app.configuracion import Configuracion
from app.main import crear_aplicacion


def test_salud_responde_con_el_contrato_esperado() -> None:
    app = crear_aplicacion(
        Configuracion(_env_file=None, app_env="testing", backend_cors_origins=[])
    )
    with TestClient(app) as cliente:
        respuesta = cliente.get("/api/v1/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "status": "ok",
        "service": "synapdesk-backend",
    }
