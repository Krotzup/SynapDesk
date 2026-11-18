"""Repite PostgreSQL o Edge desde esta copia, sin depender de otro worktree."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4
import xml.etree.ElementTree as ET

from dotenv import dotenv_values
from sqlalchemy import text

from herramientas.arnes_http_seguro.infraestructura import BACKEND, REPO, base_propia, borrar_temporal


class ArgumentosSeguros(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("Argumentos inválidos; consultar --help. No pasar secretos por argumentos.")


def postgresql(salida):
    recurso = BACKEND / (".arnes-auth07d2-" + uuid4().hex)
    recurso.mkdir()
    evidencia = {}
    try:
        with base_propia(recurso, evidencia) as (motor, nombre):
            with motor.connect() as db:
                evidencia["pgvector"] = db.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
                assert evidencia["pgvector"] == "0.8.6"
                assert 170000 <= int(evidencia["database"]["version"]) < 180000
            env = dict(os.environ, POSTGRES_TEST_DB=nombre, EJECUTAR_PRUEBAS_BD="1")
            with TemporaryDirectory(prefix="synapdesk-mvp09-pytest-") as temporal:
                resultado = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "--tb=short",
                    "-p", "no:cacheprovider", "pruebas/integracion/test_tickets.py",
                    "pruebas/integracion/test_tickets_http.py", "pruebas/integracion/test_ingreso_local_http.py",
                    "--junitxml=" + str(salida / "postgresql.xml"),
                    "--basetemp=" + str(Path(temporal) / "pytest")],
                    cwd=BACKEND, env=env, capture_output=True, timeout=240)
                (salida / "postgresql.log").write_bytes(resultado.stdout + resultado.stderr)
                casos = list(ET.parse(salida / "postgresql.xml").getroot().iter("testcase"))
                evidencia.update(
                    passed=sum(not any(c.find(t) is not None for t in ("failure", "error", "skipped")) for c in casos),
                    failed=sum(any(c.find(t) is not None for t in ("failure", "error")) for c in casos),
                    skipped=sum(c.find("skipped") is not None for c in casos), exit_code=resultado.returncode)
                assert resultado.returncode == 0 and evidencia["passed"] >= 91 and evidencia["skipped"] == 0
    finally:
        borrar_temporal(recurso)
        evidencia["temporary_deleted"] = not recurso.exists()
        (salida / "postgresql.json").write_text(json.dumps(evidencia, indent=2), encoding="utf-8")
    return evidencia


def navegador(salida):
    from herramientas.ingreso_local.demo import ejecutar
    return ejecutar(REPO / "frontend", salida / "browser.json", REPO / "frontend/tests/proxy/browser-crud.mjs")


def main():
    try:
        parser = ArgumentosSeguros(description=__doc__, allow_abbrev=False)
        parser.add_argument("--modo", required=True, choices=("postgresql", "navegador", "todo"))
        parser.add_argument("--env-file", type=Path, help="Archivo privado explícito, no se copia ni imprime.")
        parser.add_argument("--salida", type=Path, help="Directorio nuevo dentro de artifacts/ de esta copia.")
        parser.add_argument("--playwright-module", type=Path, help="playwright-core ya instalado; no instala software.")
        args = parser.parse_args()
        if args.env_file is not None:
            if not args.env_file.is_file():
                raise ValueError("Archivo privado ausente.")
            for nombre, valor in dotenv_values(args.env_file).items():
                if valor is not None:
                    os.environ[nombre] = valor
        if args.playwright_module is not None:
            if not (args.playwright_module / "package.json").is_file():
                raise ValueError("Módulo de navegador ausente.")
            os.environ["PLAYWRIGHT_MODULE"] = str(args.playwright_module.resolve())
        salida = (args.salida or REPO / "artifacts" / ("mvp09-" + uuid4().hex)).resolve()
        salida.relative_to((REPO / "artifacts").resolve())
        salida.mkdir(parents=True, exist_ok=False)
        resumen = {}
        if args.modo in {"postgresql", "todo"}:
            resultado = postgresql(salida)
            resumen["postgresql"] = {k: resultado[k] for k in ("passed", "failed", "skipped", "database_deleted")}
        if args.modo in {"navegador", "todo"}:
            resultado = navegador(salida)
            resumen["browser"] = dict(passed=resultado["browser_verified"],
                checks=len(resultado["browser"]["cases"]), database_deleted=resultado["database_deleted"])
        print(json.dumps(resumen))
        return 0
    except Exception as error:
        # Nunca mostrar Settings/SQL/DSN/entradas ni un traceback de configuración.
        print(json.dumps(dict(passed=False, error_type=type(error).__name__)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
