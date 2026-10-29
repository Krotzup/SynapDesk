import pytest


@pytest.fixture(autouse=True)
def aislar_variables_de_configuracion(monkeypatch):
    """Evita que la configuración del proceso anfitrión condicione las pruebas."""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("BACKEND_CORS_ORIGINS", raising=False)
