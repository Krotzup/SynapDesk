import pytest

from app.configuracion import Configuracion
from app.persistencia.entornos import EntornoPruebasBD


@pytest.fixture(autouse=True)
def aislar_variables_de_configuracion(monkeypatch, request):
    """Aísla pruebas locales; la integración conserva su selección explícita."""
    if "configuracion_bd_test" in request.fixturenames:
        return

    for clase in (Configuracion, EntornoPruebasBD):
        monkeypatch.setitem(clase.model_config, "env_file", None)
        for campo in clase.model_fields:
            monkeypatch.delenv(campo.upper(), raising=False)
