"""Recursos propios efímeros. Sin configuración de confianza global o IP HTTP."""

from contextlib import contextmanager
from pathlib import Path
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
from threading import Thread
from time import monotonic, sleep
from uuid import uuid4

import uvicorn
from sqlalchemy import create_engine, text

from app.persistencia.conexion import construir_url_bd
from app.persistencia.entornos import seleccionar_configuracion_bd


BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
PR30 = "0f0105e5a14ec095f538bf1079a6439b3ccf9d40"
PR32 = "ac9f02516becb8f1c4a02c149131835b8e8a6b2e"


def comprobar_base(config, nombre):
    if (config.postgres_host not in {"localhost", "127.0.0.1", "::1"}
            or config.postgres_port != 5433
            or not re.fullmatch(r"synapdesk_auth07_sec01a_[a-f0-9]{32}", nombre)
            or nombre == config.postgres_db):
        raise ValueError("Se exige base propia de ensayo en localhost:5433.")


@contextmanager
def base_propia(carpeta, evidencia):
    config = seleccionar_configuracion_bd("testing")
    nombre = "synapdesk_auth07_sec01a_" + uuid4().hex
    comprobar_base(config, nombre)
    url = construir_url_bd(config)
    admin = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True,
                          connect_args={"connect_timeout": 5})
    creada, motor = False, None
    try:
        with admin.connect() as db:
            assert db.scalar(text("SELECT current_database()")) == config.postgres_db
            db.exec_driver_sql(f'CREATE DATABASE "{nombre}" TEMPLATE template0')
            creada = True
        motor = create_engine(url.set(database=nombre), hide_parameters=True,
                              connect_args={"connect_timeout": 5})
        with motor.begin() as db:
            assert db.scalar(text("SELECT current_database()")) == nombre
            evidencia["database"] = dict(db.execute(text(
                "SELECT current_database() AS name, inet_server_port() AS internal_port, "
                "current_setting('server_version_num') AS version")).mappings().one())
            evidencia["database"]["client_port"] = 5433
            db.execute(text("CREATE EXTENSION vector"))
        env = os.environ.copy()
        env.update(POSTGRES_TEST_DB=nombre, POSTGRES_TEST_PORT="5433")
        evidencia["alembic"] = []
        for paso in ("upgrade", "current", "heads", "check"):
            result = subprocess.run([sys.executable, "-m", "alembic", "-x", "base=testing", paso,
                *(["head"] if paso == "upgrade" else [])], cwd=BACKEND, env=env,
                capture_output=True, timeout=60)
            assert result.returncode == 0, "Alembic no completó el ensayo."
            evidencia["alembic"].append(dict(step=paso, exit_code=0))
        with motor.connect() as db:
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0007_recomendaciones_rag"
            catalogo = db.scalars(text("SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='eventos_autenticacion'::regclass AND contype='c'")).all()
            assert any("user_created" in c for c in catalogo)
        evidencia["schema_head"] = "0007_recomendaciones_rag"
        evidencia["user_created_catalog_present"] = True
        yield motor, nombre
    finally:
        if motor is not None:
            motor.dispose()
        if creada:
            with admin.connect() as db:
                assert db.scalar(text("SELECT current_database()")) == config.postgres_db
                comprobar_base(config, nombre)
                db.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=:n AND pid<>pg_backend_pid()"), {"n": nombre})
                db.exec_driver_sql(f'DROP DATABASE "{nombre}"')
                evidencia["database_deleted"] = bool(db.scalar(text(
                    "SELECT count(*)=0 FROM pg_database WHERE datname=:n"), {"n": nombre}))
                assert evidencia["database_deleted"]
        admin.dispose()


def certificados(carpeta):
    openssl = shutil.which("openssl")
    if openssl is None:
        git = shutil.which("git")
        candidato = Path(git).resolve().parents[1] / "usr/bin/openssl.exe" if git else Path("ausente")
        openssl = str(candidato) if candidato.is_file() else None
    assert openssl, "Se necesita OpenSSL, incluido con Git for Windows."
    extensiones = carpeta / "san.txt"
    extensiones.write_text("subjectAltName=DNS:localhost\nextendedKeyUsage=serverAuth\n", encoding="ascii")
    comandos = [
        ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=CA-ensayo",
         "-addext", "basicConstraints=critical,CA:TRUE", "-keyout", "ca.key", "-out", "ca.pem"],
        ["req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=localhost", "-keyout", "server.key", "-out", "server.csr"],
        ["x509", "-req", "-in", "server.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
         "-days", "1", "-extfile", "san.txt", "-out", "server.pem"],
    ]
    for args in comandos:
        r = subprocess.run([openssl, *args], cwd=carpeta, capture_output=True, timeout=30)
        assert r.returncode == 0, "No se generó PKI efímera."
    for name in ("ca.key", "server.key"):
        (carpeta / name).chmod(0o600)
    return ssl.create_default_context(cafile=str(carpeta / "ca.pem"))


@contextmanager
def listener(app, carpeta, evidencia):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False,
        proxy_headers=False, ssl_keyfile=str(carpeta / "server.key"),
        ssl_certfile=str(carpeta / "server.pem")))
    thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    try:
        thread.start()
        limite = monotonic() + 15
        while not server.started and thread.is_alive() and monotonic() < limite:
            sleep(0.02)
        assert server.started, "El listener TLS de ensayo no arrancó."
        evidencia["fastapi_port"] = port
        yield port
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        sock.close()
        evidencia["fastapi_stopped"] = not thread.is_alive()
        assert evidencia["fastapi_stopped"]


def puerto_libre():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def detener(proceso):
    # Solo el PID/subárbol que creó este arnés; nunca un puerto o nombre global.
    if proceso.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proceso.pid), "/T", "/F"],
                           capture_output=True, timeout=20)
        else:
            proceso.terminate()
        proceso.wait(timeout=20)
    assert proceso.poll() is not None


def borrar_temporal(carpeta):
    carpeta = carpeta.absolute()
    assert carpeta.parent == BACKEND and carpeta.name.startswith(".arnes-auth07d2-")
    assert not carpeta.is_symlink()
    # No hay enlaces/junctions a node_modules. Solo recursos creados dentro del temporal.
    assert not any(p.is_symlink() or p.is_junction() for p in carpeta.rglob("*"))
    shutil.rmtree(carpeta)
    assert not carpeta.exists()
