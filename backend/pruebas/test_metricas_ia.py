from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from app.aplicacion import crear_aplicacion
from app.configuracion import Configuracion
from app.recuperacion.servicio import ErrorRecuperacion


def test_hu10_no_registra_ruta_por_defecto():
    app = crear_aplicacion(Configuracion(_env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/v1/metrics/recommendations").status_code == 404


def test_hu10_exige_identidad_antes_de_consultar_bd():
    app = crear_aplicacion(Configuracion(_env_file=None, metrics_ai_enabled=True))
    with TestClient(app) as client, patch("app.api.metricas_ia.identidad_aplicacion",
            side_effect=ErrorRecuperacion("AUTHENTICATION_REQUIRED", "Inicia sesión", 401)) as identity, \
            patch("app.api.metricas_ia.contar_revisiones") as count:
        result = client.get("/api/v1/metrics/recommendations")
    assert result.status_code == 401 and result.headers["cache-control"] == "no-store"
    assert identity.call_args.kwargs == {"escritura": False}
    count.assert_not_called()


def test_hu10_fallo_de_persistencia_no_inventa_conteos():
    app = crear_aplicacion(Configuracion(_env_file=None, metrics_ai_enabled=True))
    with TestClient(app) as client, patch("app.api.metricas_ia.identidad_aplicacion"), \
            patch("app.api.metricas_ia.Session", side_effect=SQLAlchemyError("detalle privado")):
        app.state.motor_bd = object()
        result = client.get("/api/v1/metrics/recommendations")
        app.state.motor_bd = None
    assert result.status_code == 503 and result.headers["cache-control"] == "no-store"
    assert result.json()["error"]["code"] == "METRICS_UNAVAILABLE"
    assert "detalle privado" not in result.text and "recommendationsAccepted" not in result.text
