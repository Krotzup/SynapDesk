import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.aplicacion import crear_aplicacion
from app.configuracion import Configuracion

RAIZ_BACKEND = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "contenido",
    ["APP_ENV=local\n", "BACKEND_CORS_ORIGINS=http://localhost:3000\n"],
)
def test_importar_fabrica_y_probar_salud_ignora_env_local_invalido(tmp_path, contenido):
    archivo_env = tmp_path / ".env"
    archivo_env.write_text(contenido, encoding="utf-8")
    codigo = """
import sys
from pathlib import Path
from app.configuracion import Configuracion

Configuracion.model_config["env_file"] = Path(sys.argv[1])
from app.aplicacion import crear_aplicacion
from fastapi.testclient import TestClient

configuracion = Configuracion(_env_file=None, app_env="testing", backend_cors_origins=[])
with TestClient(crear_aplicacion(configuracion)) as cliente:
    respuesta = cliente.get("/api/v1/health")
assert respuesta.status_code == 200
assert respuesta.json() == {"status": "ok", "service": "synapdesk-backend"}
"""
    resultado = subprocess.run(
        [sys.executable, "-c", codigo, str(archivo_env)],
        cwd=RAIZ_BACKEND,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr


def test_fabrica_sin_configuracion_conserva_carga_del_archivo_env(tmp_path, monkeypatch):
    archivo_env = tmp_path / ".env"
    archivo_env.write_text(
        'APP_ENV=testing\nBACKEND_CORS_ORIGINS=["https://frontend.example.invalid"]\n',
        encoding="utf-8",
    )
    monkeypatch.setitem(Configuracion.model_config, "env_file", archivo_env)

    with TestClient(crear_aplicacion()) as cliente:
        respuesta = cliente.options(
            "/api/v1/health",
            headers={
                "Origin": "https://frontend.example.invalid",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == "https://frontend.example.invalid"


def test_fabrica_conserva_validacion_de_app_env(tmp_path, monkeypatch):
    archivo_env = tmp_path / ".env"
    archivo_env.write_text("APP_ENV=local\n", encoding="utf-8")
    monkeypatch.setitem(Configuracion.model_config, "env_file", archivo_env)

    with pytest.raises(ValidationError):
        crear_aplicacion()
