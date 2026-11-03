import subprocess
import sys
import base64
from io import StringIO
from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.aplicacion import crear_aplicacion
from app.configuracion import Configuracion

RAIZ_BACKEND = Path(__file__).resolve().parents[1]

# Valores ficticios del fixture AUTH-06C; no cuotas de despliegue aprobadas.
LIMITES_FICTICIOS = {
    "AUTH_LIMITE_CUENTA_INTENTOS": 2,
    "AUTH_LIMITE_CUENTA_VENTANA_SEGUNDOS": 60,
    "AUTH_LIMITE_CUENTA_BLOQUEO_SEGUNDOS": 20,
    "AUTH_LIMITE_IP_INTENTOS": 3,
    "AUTH_LIMITE_IP_VENTANA_SEGUNDOS": 60,
    "AUTH_LIMITE_IP_BLOQUEO_SEGUNDOS": 20,
}


def ejemplo_temporal(tmp_path, *, sin_configurar=None):
    contenido = (RAIZ_BACKEND.parent / ".env.example").read_text(encoding="utf-8")
    valores = dotenv_values(stream=StringIO(contenido))
    reemplazos = {**LIMITES_FICTICIOS,
                  "AUTH_HMAC_CLAVE": base64.b64encode(bytes(range(32))).decode("ascii")}
    for nombre, valor in reemplazos.items():
        if nombre != sin_configurar:
            contenido = contenido.replace(f"{nombre}={valores[nombre]}", f"{nombre}={valor}", 1)
    archivo = tmp_path / ".env.auth06.ficticio"
    archivo.write_text(contenido, encoding="utf-8")
    return archivo


def test_ejemplo_incluye_exactamente_las_variables_auth_reales():
    valores = dotenv_values(RAIZ_BACKEND.parent / ".env.example")
    variables = {nombre for nombre in valores if nombre.startswith("AUTH_")}
    reales = {nombre.upper() for nombre in Configuracion.model_fields if nombre.startswith("auth_")}
    assert variables == reales
    assert valores["AUTH_ORIGENES_PERMITIDOS"] == '["http://localhost:3000"]'
    assert valores["AUTH_PROXIES_AUTORIZADOS"] == '[]'


def test_ejemplo_sin_configurar_rechaza_todos_los_marcadores(tmp_path, caplog):
    archivo = tmp_path / ".env.ejemplo_sin_configurar"
    archivo.write_text((RAIZ_BACKEND.parent / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ValidationError) as error:
        Configuracion(_env_file=archivo)
    campos = {item["loc"][0] for item in error.value.errors(include_input=False, include_context=False)}
    assert campos == {nombre.lower() for nombre in LIMITES_FICTICIOS} | {"auth_hmac_clave"}
    assert not caplog.records


def test_ejemplo_derivado_carga_y_construye_servicios_sin_abrir_bd(tmp_path, caplog):
    from sqlalchemy.orm import Session
    from app.seguridad.contrasenas import ServicioContrasenas
    from app.seguridad.csrf import ServicioCsrf
    from app.seguridad.identificadores import ServicioIdentificadores
    from app.seguridad.limites import ServicioLimites
    from app.seguridad.origenes import ServicioOrigen
    from app.seguridad.proxies import ServicioIpConfiable
    from app.seguridad.transacciones import ErrorSeguridad

    configuracion = Configuracion(_env_file=ejemplo_temporal(tmp_path))
    ServicioContrasenas(configuracion)
    identificadores = ServicioIdentificadores(configuracion)
    assert identificadores.id_clave == "local-v1"
    assert len(identificadores.cuenta("ficticia@example.invalid")) == 32
    ServicioOrigen(configuracion).validar(["http://localhost:3000"])
    with pytest.raises(ErrorSeguridad):
        ServicioIpConfiable(configuracion, identificadores).identificar(
            par_transporte="127.0.0.1", valores_ip_cliente=["198.51.100.7"])
    with Session() as db:
        csrf = ServicioCsrf(db, configuracion)
        limites = ServicioLimites(db, configuracion, identificadores)
        assert csrf.max_tokens == 8 and csrf.token_bytes == 32
        assert (limites.politicas["cuenta"].intentos, limites.politicas["ip"].intentos) == (2, 3)
        assert limites.politicas["cuenta"].ventana.total_seconds() == 60
        assert limites.politicas["ip"].bloqueo.total_seconds() == 20
        assert not db.in_transaction()
    clave_ficticia = configuracion.auth_hmac_clave.get_secret_value()
    assert clave_ficticia not in repr(configuracion)
    assert clave_ficticia not in configuracion.model_dump_json()
    assert not caplog.records


@pytest.mark.parametrize("variable", ["AUTH_HMAC_CLAVE", *LIMITES_FICTICIOS])
def test_marcador_del_ejemplo_no_se_acepta_como_valor_operativo(tmp_path, variable):
    with pytest.raises(ValidationError) as error:
        Configuracion(_env_file=ejemplo_temporal(tmp_path, sin_configurar=variable))
    assert [item["loc"] for item in error.value.errors(include_input=False, include_context=False)] == [(variable.lower(),)]


@pytest.mark.parametrize(
    "contenido",
    [
        "APP_ENV=local\n",
        "BACKEND_CORS_ORIGINS=http://localhost:3000\n",
        "POSTGRES_PORT=puerto_invalido\n",
        "POSTGRES_SSLMODE=modo_invalido\n",
    ],
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


@pytest.mark.parametrize(
    ("variable", "valor"),
    [("POSTGRES_PORT", "puerto_invalido"), ("POSTGRES_SSLMODE", "modo_invalido")],
)
def test_configuracion_conserva_validacion_de_postgresql(monkeypatch, variable, valor):
    monkeypatch.setenv(variable, valor)

    with pytest.raises(ValidationError):
        crear_aplicacion()


def test_punto_de_entrada_no_crea_motor_al_importarse():
    codigo = """
from unittest.mock import patch
from app.configuracion import Configuracion

Configuracion.model_config["env_file"] = None
with patch.dict("os.environ", {
    "APP_ENV": "testing",
    "BACKEND_CORS_ORIGINS": "[]",
    "POSTGRES_DB": "base_ficticia",
    "POSTGRES_USER": "usuario_ficticio",
    "POSTGRES_PASSWORD": "clave_ficticia",
}), patch("sqlalchemy.create_engine") as crear_motor:
    from app.main import app, crear_aplicacion
    from app.aplicacion import crear_aplicacion as fabrica
    assert crear_aplicacion is fabrica
    assert app.state.motor_bd is None
    assert set(app.openapi()["paths"]) == {"/api/v1/health", "/api/v1/ready"}
    crear_motor.assert_not_called()
"""
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=RAIZ_BACKEND,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
