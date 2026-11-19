"""Ejecuta suites existentes sin bases compartidas ni evidencia histórica mutable."""

import argparse
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4
import xml.etree.ElementTree as ET

BACKEND = Path(__file__).resolve().parents[1]
TLS = "pruebas/integracion/test_intermediario_tls.py"
BUSQUEDA = "pruebas/integracion/test_busqueda_semantica.py"


def comprobar_importaciones():
    for modulo in ("fastapi", "uvicorn", "pydantic", "pydantic_settings", "sqlalchemy",
                   "psycopg", "alembic", "argon2", "pytest", "h11", "httpx2", "yaml"):
        importlib.import_module(modulo)
    from app.configuracion import Configuracion
    config = Configuracion(_env_file=None, app_env="testing", postgres_db=None,
                           postgres_user=None, postgres_password=None,
                           auth_intermediario=None, auth_bootstrap=None)
    if config.tiene_configuracion_bd or config.auth_intermediario is not None:
        raise ValueError("La comprobación aislada no debe habilitar infraestructura.")


def comprobar_destino(config):
    if (config.app_env != "testing" or config.postgres_host not in {"127.0.0.1", "localhost", "::1"}
            or config.postgres_port != 5433):
        raise ValueError("CI requiere testing y exclusivamente loopback:5433.")


def comprobar_resultados(ruta):
    casos = list(ET.parse(ruta).getroot().iter("testcase"))
    if not casos or any(c.find(marca) is not None for c in casos
                        for marca in ("failure", "error", "skipped")):
        raise ValueError("La suite debe ejecutar casos sin fallos ni omisiones.")
    return len(casos)


def ejecutar_pytest(argumentos, temporal, env=None):
    reporte = temporal / "junit.xml"
    resultado = subprocess.run([
        sys.executable, "-B", "-m", "pytest", *argumentos, "-q", "--tb=short",
        "-p", "no:cacheprovider", "--basetemp=" + str(temporal / "pytest"),
        "--junitxml=" + str(reporte),
    ], cwd=BACKEND, env=env, timeout=600, check=False)
    if resultado.returncode:
        raise RuntimeError("La suite no terminó correctamente.")
    return comprobar_resultados(reporte)


def ejecutar(modo):
    if modo not in {"unitarias", "postgresql", "tls", "migraciones"}:
        raise ValueError("Suite desconocida.")
    comprobar_importaciones()
    if modo in {"unitarias", "tls"}:
        with TemporaryDirectory(prefix="synapdesk-ci-") as carpeta:
            argumentos = (["pruebas", "--ignore=pruebas/integracion"] if modo == "unitarias" else [TLS])
            total = ejecutar_pytest(argumentos, Path(carpeta))
        return {"suite": modo, "passed": total, "skipped": 0, "temporary_deleted": True}

    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.persistencia.entornos import seleccionar_configuracion_bd
    from herramientas.arnes_http_seguro.infraestructura import base_propia, borrar_temporal

    config = seleccionar_configuracion_bd("testing")
    comprobar_destino(config)  # Siempre antes de abrir conexiones.
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    if scripts.get_heads() != ["0007_recomendaciones_rag"]:
        raise ValueError("Se exige el head único de migraciones vigente.")
    revisiones = list(reversed(list(scripts.walk_revisions())))
    if (len(revisiones) != 7 or revisiones[0].down_revision is not None
            or len({r.revision for r in revisiones}) != 7
            or any(b.down_revision != a.revision for a, b in zip(revisiones, revisiones[1:]))):
        raise ValueError("Se exige la cadena lineal vigente 0001–0007.")
    carpeta = BACKEND / (".arnes-auth07d2-" + uuid4().hex)
    carpeta.mkdir()
    evidencia = {"suite": modo, "temporary_directory": carpeta.name,
                 "migration_chain": [r.revision for r in revisiones]}
    try:
        # Reutiliza el creador con identidad, prefijo, puerto y limpieza acotados.
        # Verifica vector y ejecuta upgrade/current/heads/check en una base vacía.
        with base_propia(carpeta, evidencia) as (_, nombre):
            if modo == "postgresql":
                env = os.environ.copy()
                env.update(POSTGRES_TEST_DB=nombre, POSTGRES_TEST_PORT="5433",
                           EJECUTAR_PRUEBAS_BD="1", PYTHONDONTWRITEBYTECODE="1")
                # Pytest crea enlaces *current: son propios de su temporal,
                # no de los recursos sujetos a la guarda estricta del arnés.
                with TemporaryDirectory(prefix="synapdesk-ci-postgresql-") as ruta:
                    temporal_pytest = Path(ruta)
                    # La búsqueda prepara sus bases semánticas y su perfil V2 en otro ensayo.
                    evidencia["passed"] = ejecutar_pytest(
                        ["pruebas/integracion", "--ignore=" + TLS, "--ignore=" + BUSQUEDA],
                        temporal_pytest, env)
                evidencia["pytest_temporary_deleted"] = not temporal_pytest.exists()
                if not evidencia["pytest_temporary_deleted"]:
                    raise RuntimeError("No se eliminó el temporal propio de pytest.")
                evidencia["skipped"] = 0
    finally:
        borrar_temporal(carpeta)
        evidencia["temporary_deleted"] = not carpeta.exists()
    return evidencia


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modo", choices=("unitarias", "postgresql", "tls", "migraciones"))
    args = parser.parse_args()
    try:
        print(json.dumps(ejecutar(args.modo), ensure_ascii=False))
    except Exception as error:
        # Sin str(error), DSN, valores de configuración o secretos en este resumen.
        print("CI_BACKEND_FAILED: " + type(error).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
