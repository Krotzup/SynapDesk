from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_mock_engine

from app.configuracion import Configuracion
from app.aplicacion import crear_aplicacion
from app.seguridad.bootstrap_csrf import CuotaBootstrapAgotada, ServicioBootstrapCsrf
from app.seguridad.politica_bootstrap import PoliticaBootstrap
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad
from pruebas.bootstrap_auxiliar import configuracion_ensayo, politica_ensayo


def test_cuotas_ausentes_no_construyen_servicio():
    with pytest.raises(ErrorSeguridad) as error:
        ServicioBootstrapCsrf(create_mock_engine("postgresql://", lambda *a: None),
                             Configuracion(_env_file=None))
    assert error.value.codigo == C.INFRAESTRUCTURA


@pytest.mark.parametrize("ambito", ["contextos_ip", "contextos_global", "intentos_ip",
                                  "intentos_global", "emisiones_contexto"])
@pytest.mark.parametrize("valor", [0, -1, True, 1.5, "12", 1_000_001])
def test_cuotas_exigen_enteros_validos(ambito, valor):
    with pytest.raises(ValidationError):
        PoliticaBootstrap(**politica_ensayo(**{ambito: dict(cantidad=valor, segundos=60)}))


@pytest.mark.parametrize("campo,valor", [
    ("token_segundos", 901), ("max_tokens", 13), ("max_filas_cuota", 4),
    ("lote_limpieza", 0), ("contexto_segundos", 86401), ("max_tokens", True),
    ("lock_timeout_ms", 3000), ("statement_timeout_ms", 500),
    ("max_filas_tokens", 1), ("perfil", "produccion"),
])
def test_configuracion_incoherente_falla(campo, valor):
    with pytest.raises(ValidationError):
        PoliticaBootstrap(**politica_ensayo(**{campo: valor}))


@pytest.mark.parametrize("campo", list(PoliticaBootstrap.model_fields))
def test_todos_los_parametros_son_explicitos(campo):
    datos = politica_ensayo()
    del datos[campo]
    with pytest.raises(ValidationError):
        PoliticaBootstrap(**datos)


@pytest.mark.parametrize("entorno", ["development", "staging", "production"])
def test_ensayo_no_se_activa_fuera_de_testing(entorno):
    config = configuracion_ensayo()
    config.app_env = entorno
    with pytest.raises(ErrorSeguridad):
        ServicioBootstrapCsrf(create_mock_engine("postgresql://", lambda *a: None), config)


def test_retry_after_redondea_espera_verificable_sin_datos_sensibles():
    ahora = datetime(2026, 11, 12, tzinfo=UTC)
    error = CuotaBootstrapAgotada("intentos_ip", ahora, ahora + timedelta(seconds=1.1))
    assert error.retry_after == 2
    assert str(error) == "Cuota de bootstrap agotada."


@pytest.mark.parametrize("cabecera", ["X-Forwarded-For", "X-Real-IP", "Forwarded", "X-SynapDesk-Client-IP"])
def test_politica_completa_no_habilita_confianza_http(cabecera):
    config = configuracion_ensayo()
    config.auth_origenes_permitidos = ["http://localhost:3000"]
    with TestClient(crear_aplicacion(config)) as cliente:
        respuesta = cliente.get("/api/v1/auth/csrf", headers={
            "Origin": "http://localhost:3000", cabecera: "198.51.100.7"})
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "set-cookie" not in respuesta.headers
    assert "retry-after" not in respuesta.headers
    assert respuesta.headers["cache-control"] == "no-store"
