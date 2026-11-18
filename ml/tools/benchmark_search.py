"""Mide la concurrencia de búsqueda con bases desechables y sesiones ficticias."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from math import ceil
import os
from pathlib import Path
from secrets import token_urlsafe
from statistics import median
from threading import Barrier, Lock
from time import perf_counter
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
from pydantic import SecretStr
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.aplicacion import crear_aplicacion
from app.configuracion import Configuracion
from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import Usuario
from app.recuperacion.servicio import ServicioRecuperacion
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.intermediario import digest_credencial_servicio
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import transaccion_seguridad
from ml.semantic_retrieval.embeddings import LocalEmbedder

ORIGIN = "https://testserver"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        auth_url = os.environ["SYNAPDESK_BENCH_AUTH_URL"]
        semantic_url = os.environ["SYNAPDESK_SEMANTIC_DATABASE_URL"]
        auth = conninfo_to_dict(auth_url)
        semantic = conninfo_to_dict(semantic_url)
        for info, prefix in ((auth, "synapdesk_backend_"), (semantic, "synapdesk_semantic_")):
            if (
                info.get("host") not in {"127.0.0.1", "::1", "localhost"}
                or info.get("hostaddr", info.get("host")) not in {"127.0.0.1", "::1", "localhost"}
                or not info.get("dbname", "").startswith(prefix)
                or not info["dbname"].endswith("_test")
            ):
                raise ValueError
        if not auth.get("user") or not auth.get("password"):
            raise ValueError
        if args.output.exists():
            parser.error("La ruta del informe ya existe.")
    except (KeyError, ValueError, psycopg.Error):
        parser.error("Configura dos bases locales desechables con nombres de ensayo y credenciales válidas.")
    model = LocalEmbedder()
    service_credential = SecretStr(token_urlsafe(32))
    config = Configuracion(
        _env_file=None,
        app_env="testing",
        search_enabled=False,
        auth_cookie_profile="local",
        auth_origenes_permitidos=[ORIGIN],
        auth_intermediario={
            "habilitado": True,
            "entorno": "testing",
            "transporte": "tls_directo",
            "politica_ip": "no_acreditada",
            "credenciales": [{
                "identificador": "benchmark",
                "digest": digest_credencial_servicio(service_credential, "testing"),
                "vence_en": datetime.now(timezone.utc) + timedelta(hours=1),
            }],
        },
        search_relevance_profile=args.profile,
        synapdesk_semantic_database_url=semantic_url,
        postgres_host=auth["host"],
        postgres_port=int(auth.get("port", 5432)),
        postgres_db=auth["dbname"],
        postgres_user=auth["user"],
        postgres_password=auth["password"],
    )
    headers = []
    engine = crear_motor_bd(config)
    with Session(engine) as db, transaccion_seguridad(db):
        for _ in range(8):
            actor = Usuario(id=uuid4(), nombre="Agente de ensayo", correo=f"bench-{uuid4()}@example.invalid",
                            hash_contrasena="ficticio", activo=True, rol="agent")
            db.add(actor)
            db.flush()
            credential = ServicioSesiones(db).crear(actor.id).credencial
            csrf = ServicioCsrf(db, config)
            csrf.obtener_autenticado(credential)
            token = csrf.emitir_token(sesion=credential).token.get_secret_value()
            headers.append({"Origin": ORIGIN, "X-CSRF-Token": token,
                            "Authorization": f"Bearer {service_credential.get_secret_value()}",
                            "Cookie": f"synapdesk_session_dev={credential.get_secret_value()}"})
    engine.dispose()

    report = {"timestamp": datetime.now(timezone.utc).isoformat(),
              "percentileMethod": "nearest rank", "scenarios": measure(config, headers, model)}
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    if any(set(row["statuses"]) != {"200"} for row in report["scenarios"].values()):
        parser.exit(1, "El informe incluye solicitudes fallidas.\n")

def summarize(values):
    if not values:
        return None
    ordered = sorted(values)
    return {
        "medianMs": round(median(ordered) * 1000, 1),
        "p95Ms": round(ordered[ceil(len(ordered) * 0.95) - 1] * 1000, 1),
        "maxMs": round(ordered[-1] * 1000, 1),
    }


class MeasuredLock:
    def __init__(self, lock):
        self.lock = lock
        self.waits = []

    def __enter__(self):
        started = perf_counter()
        self.lock.acquire()
        self.waits.append(perf_counter() - started)

    def __exit__(self, *_):
        self.lock.release()


def measure(config, headers, model):
    service = ServicioRecuperacion(config, embedder=model)
    service.lock = MeasuredLock(service.lock)
    checkout_times = []
    active = 0
    peak = 0
    sample_lock = Lock()
    payload = {"query": "No se resuelve el nombre del servidor DNS.", "limit": 5}
    scenarios = {}
    with TestClient(crear_aplicacion(config), base_url=ORIGIN) as client:
        client.app.state.recuperacion = service
        engine = client.app.state.motor_bd

        @event.listens_for(engine, "checkout")
        def checked_out(_, record, __):
            nonlocal active, peak
            record.info["bench_started"] = perf_counter()
            with sample_lock:
                active += 1
                peak = max(peak, active)

        @event.listens_for(engine, "checkin")
        def checked_in(_, record):
            nonlocal active
            started = record.info.pop("bench_started", None)
            if started is not None:
                with sample_lock:
                    checkout_times.append(perf_counter() - started)
                    active -= 1

        def send(auth, barrier=None):
            if barrier is not None:
                barrier.wait()
            started = perf_counter()
            response = client.post("/api/v1/search", headers=auth, json=payload)
            return response.status_code, perf_counter() - started

        status, _ = send(headers[0])
        if status != 200:
            raise RuntimeError(f"El calentamiento falló con HTTP {status}.")

        for level, label, identities, rounds in (
            (1, "sequential", headers[:1], 12),
            (4, "shared_4", [headers[0]] * 4, 6),
            (4, "independent_4", headers[:4], 6),
            (8, "shared_8", [headers[0]] * 8, 4),
            (8, "independent_8", headers, 4),
        ):
            peak = 0
            checkout_times.clear()
            service.lock.waits.clear()
            responses = []
            with ThreadPoolExecutor(max_workers=level) as pool:
                for _ in range(rounds):
                    barrier = Barrier(level, timeout=15)
                    jobs = [pool.submit(send, auth, barrier) for auth in identities]
                    responses.extend(job.result() for job in jobs)
            statuses = Counter(str(status) for status, _ in responses)
            scenarios[label] = {
                "concurrency": level,
                "requests": len(responses),
                "statuses": dict(statuses),
                "latency": summarize([elapsed for _, elapsed in responses]),
                "authConnectionHeld": summarize(checkout_times),
                "embeddingLockWait": summarize(service.lock.waits),
                "peakAuthConnections": peak,
            }
    return scenarios


if __name__ == "__main__":
    main()
