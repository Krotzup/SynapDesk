"""Validación reproducible, exclusivamente en una base temporal de localhost:5433.

No imprime credenciales. Solo elimina la base aleatoria creada en esta ejecución.
Ejecutar desde backend con el intérprete del proyecto.
"""

import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import xml.etree.ElementTree as ET

from sqlalchemy import create_engine, text

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.persistencia.conexion import construir_url_bd
from app.persistencia.entornos import seleccionar_configuracion_bd


def validar(*, nombre_reporte: str = "auth07-sec01a-validacion.json") -> int:
    if not re.fullmatch(r"(?:auth07-sec01[ab]|auth07b2-login|auth07b3-sesiones|auth07c1b?-bootstrap)-validacion\.json", nombre_reporte):
        raise ValueError("Nombre de reporte de validación inválido.")
    config = seleccionar_configuracion_bd("testing")
    if config.postgres_host not in {"localhost", "127.0.0.1", "::1"} or config.postgres_port != 5433:
        raise ValueError("Se exige PostgreSQL de pruebas local en 5433.")
    nombre = "synapdesk_auth07_sec01a_" + uuid4().hex
    if not re.fullmatch(r"synapdesk_auth07_sec01a_[a-f0-9]{32}", nombre) or nombre == config.postgres_db:
        raise ValueError("Identidad temporal inválida.")
    url = construir_url_bd(config)
    admin = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True,
                          connect_args={"connect_timeout": 5})
    creada = False
    reporte = {"base_temporal": nombre, "puerto_cliente": 5433, "pasos": [], "eliminada": False}
    salida = RAIZ.parent / "docs" / "auditorias" / nombre_reporte
    salida.parent.mkdir(parents=True, exist_ok=True)
    # Todos los artefactos temporales permanecen en el workspace autorizado.
    temporal = RAIZ / (".validacion-bootstrap-" + uuid4().hex)
    temporal.mkdir(exist_ok=True)
    entorno = os.environ.copy()
    entorno["POSTGRES_TEST_DB"] = nombre
    entorno["POSTGRES_TEST_PORT"] = "5433"
    entorno["EJECUTAR_PRUEBAS_BD"] = "1"
    try:
        with admin.connect() as db:
            if db.scalar(text("SELECT current_database()")) != config.postgres_db:
                raise ValueError("La conexión administrativa no es la base de pruebas.")
            # Identificador generado internamente, exclusivamente [a-z0-9_].
            db.exec_driver_sql(f'CREATE DATABASE "{nombre}" TEMPLATE template0')
            creada = True
        prueba = create_engine(url.set(database=nombre), hide_parameters=True,
                              connect_args={"connect_timeout": 5})
        try:
            with prueba.begin() as db:
                if db.scalar(text("SELECT current_database()")) != nombre:
                    raise ValueError("La base temporal no coincide con la creada.")
                reporte["servidor"] = dict(db.execute(text(
                    "SELECT current_database() AS base, inet_server_port() AS puerto_interno, "
                    "current_setting('server_version_num') AS version")).mappings().one())
                db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        finally:
            prueba.dispose()
        pasos = [
            ("pip_check", ["-m", "pip", "check"]),
            *[("alembic_" + paso, ["-m", "alembic", "-x", "base=testing", paso,
                                  *(["head"] if paso == "upgrade" else [])])
              for paso in ("upgrade", "current", "heads", "check")],
            ("unitarias", ["-m", "pytest", "pruebas", "--ignore=pruebas/integracion", "-q", "--tb=short",
                           "-p", "no:cacheprovider", "--basetemp=" + str(temporal / "tmp-unit"),
                           "--junitxml=" + str(temporal / "unitarias.xml")]),
            ("postgresql", ["-m", "pytest", "pruebas/integracion", "-q", "--tb=short",
                            "-p", "no:cacheprovider", "--basetemp=" + str(temporal / "tmp-pg"),
                            "--junitxml=" + str(temporal / "postgresql.xml")]),
        ]
        for etiqueta, argumentos in pasos:
            print("EJECUTANDO " + etiqueta, flush=True)
            resultado = subprocess.run([sys.executable, *argumentos], cwd=RAIZ, env=entorno,
                                       text=True, capture_output=True)
            # Herramientas configuradas para no mostrar entradas/credenciales.
            print(resultado.stdout, flush=True)
            print(resultado.stderr, flush=True)
            reporte["pasos"].append(dict(paso=etiqueta, exit_code=resultado.returncode))
            xml = temporal / (etiqueta + ".xml")
            if xml.exists():
                suites = ET.parse(xml).getroot().findall("testsuite")
                reporte[etiqueta] = {campo: sum(int(s.attrib.get(campo, 0)) for s in suites)
                                    for campo in ("tests", "failures", "errors", "skipped")}
            if resultado.returncode and etiqueta not in {"unitarias", "postgresql"}:
                break
    except Exception as error:
        # Evitar interpolar la excepción del driver y su contexto privado.
        reporte["error_tipo"] = type(error).__name__
        print("Validación interrumpida: " + type(error).__name__, flush=True)
    finally:
        if creada:
            with admin.connect() as db:
                if db.scalar(text("SELECT current_database()")) != config.postgres_db:
                    raise ValueError("La conexión de limpieza no es la base de pruebas.")
                db.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                                "WHERE datname = :nombre AND pid <> pg_backend_pid()"), {"nombre": nombre})
                db.exec_driver_sql(f'DROP DATABASE "{nombre}"')
                reporte["eliminada"] = db.scalar(text(
                    "SELECT count(*) = 0 FROM pg_database WHERE datname = :nombre"), {"nombre": nombre})
        admin.dispose()
        salida.write_text(json.dumps(reporte, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        assert temporal.resolve().is_relative_to(RAIZ.resolve())
        assert temporal.name.startswith(".validacion-bootstrap-")
        shutil.rmtree(temporal)
    return 0 if (len(reporte["pasos"]) == 7 and reporte["eliminada"]
                 and not reporte.get("error_tipo")
                 and all(p["exit_code"] == 0 for p in reporte["pasos"])) else 1


if __name__ == "__main__":
    sys.exit(validar())
