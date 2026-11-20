"""PostgreSQL real y vectores deterministas; sin acreditar calidad del modelo o Gemini."""
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from app.api.predicciones import generar_prediccion
from app.documentos import conexion_documentos, ingresar
from app.persistencia.conexion import construir_url_bd
from app.recuperacion.servicio import ErrorRecuperacion
from app.tickets.esquemas import TicketPagination, TicketStatusUpdate
from app.tickets.repositorio import CodigoTickets, ErrorTickets
from pruebas.integracion.test_tickets import tickets, crear, consulta_interna
from pruebas.integracion.test_tickets_http import candidato_pg, emitir


def test_filtros_reales_combinan_y_escapan_comodines(tickets):
    primero = crear(tickets, "VPN 100% disponible")
    crear(tickets, "VPN 1000 disponible")
    consulta_interna(tickets, lambda repo: repo.actualizar_estado(primero.id, TicketStatusUpdate(status="resolved")))
    result = tickets["servicio"].listar(tickets["referencias"][0], TicketPagination(search="100%", status="resolved"))
    assert result.totalItems == 1 and result.items[0].id == primero.id
    assert result.items[0].resolvedAt is not None
    empty = tickets["servicio"].listar(tickets["referencias"][0], TicketPagination(search="100%", page=100))
    assert empty.items == () and empty.totalItems == 1
    with pytest.raises(ErrorTickets) as error:
        consulta_interna(tickets, lambda repo: repo.actualizar_estado(primero.id,
            TicketStatusUpdate(status="closed", expectedStatus="open")))
    assert error.value.codigo == CodigoTickets.CONFLICTO_ESTADO


def test_prediccion_es_persistente_idempotente_y_no_altera_ticket(tickets):
    ticket = crear(tickets)
    class Clasificador:
        llamadas = 0
        def huella(self, *_): return "a" * 64
        def predecir(self, *_):
            self.llamadas += 1
            return {"predictedCategory": None, "predictedPriority": "high", "predictedArea": None,
                    "confidence": None, "modelName": "simulado", "modelVersion": "1"}
    servicio = Clasificador()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(motor_bd=tickets["motor"], clasificacion=servicio)))
    first = generar_prediccion(request, ticket.id)
    assert generar_prediccion(request, ticket.id) == first
    assert servicio.llamadas == 1
    assert consulta_interna(tickets, lambda repo: repo.detalle(ticket.id)) == ticket


def test_router_optativo_usa_sesion_csrf_y_precondicion_reales(candidato_pg):
    from fastapi.testclient import TestClient
    from app.aplicacion import crear_aplicacion
    from pruebas.intermediario_auxiliar import ORIGEN
    e = candidato_pg
    config = e["config"].model_copy(update={"tickets_http_enabled": True,
        "application_public_origin": ORIGEN, "auth_cookie_profile": "local"})
    app = crear_aplicacion(config)
    headers = {"Authorization": "Bearer " + e["clave"].get_secret_value(), "Origin": ORIGEN,
        "Cookie": "synapdesk_session_dev=" + e["referencias"][0].credencial.get_secret_value(),
        "X-CSRF-Token": emitir(e).token.get_secret_value()}
    # Scope HTTPS de pruebas: verifica HTTP/SQL, no certifica listener TLS real.
    with TestClient(app, base_url="https://localhost", client=("127.0.0.1", 12345)) as client:
        app.state.motor_bd = e["motor"]
        created = client.post("/api/v1/tickets", headers=headers,
            json={"title": "Router con sesion real", "description": "Descripcion del router optativo."})
        assert created.status_code == 201, created.text
        identifier = created.json()["id"]
        resolved = client.patch(f"/api/v1/tickets/{identifier}", headers=headers,
            json={"status": "resolved", "expectedStatus": "open"})
        assert resolved.status_code == 200 and resolved.json()["resolvedAt"] is not None
        conflict = client.patch(f"/api/v1/tickets/{identifier}", headers=headers,
            json={"status": "closed", "expectedStatus": "open"})
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "TICKET_STATE_CONFLICT"
        result = client.get("/api/v1/tickets?status=resolved&search=Router", headers=headers)
        assert result.status_code == 200 and result.json()["totalItems"] == 1


@pytest.fixture
def semantica(configuracion_bd_test, monkeypatch):
    # Una segunda base desechable; nunca se apunta la ingestión a tickets.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3]))
    from ml.semantic_retrieval.repository import init_schema
    import psycopg
    config = configuracion_bd_test
    name = "synapdesk_semantic_webtest_" + uuid4().hex
    assert config.app_env == "testing" and config.postgres_port == 5433
    assert name != config.postgres_db and name.startswith("synapdesk_semantic_webtest_")
    url = construir_url_bd(config)
    admin = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    created = False
    try:
        with admin.connect() as db:
            db.exec_driver_sql(f'CREATE DATABASE "{name}"')
            created = True
        semantic_url = url.set(drivername="postgresql", database=name).render_as_string(hide_password=False)
        with psycopg.connect(semantic_url) as db:
            init_schema(db)
        yield config.model_copy(update={"documents_enabled": True,
            "synapdesk_semantic_database_url": SecretStr(semantic_url)})
    finally:
        if created:
            with admin.connect() as db:
                db.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:n AND pid<>pg_backend_pid()"), {"n": name})
                db.exec_driver_sql(f'DROP DATABASE "{name}"')
        admin.dispose()


def test_indexacion_retiro_y_rollback_atomicos(semantica):
    from ml.semantic_retrieval.config import MODEL_ID
    from ml.semantic_retrieval.repository import corpus_state, require_matching_profile
    from app.api.documentos import listar, retirar
    from fastapi import Response
    import numpy as np
    class Tokenizer:
        def encode(self, text, **_): return list(text.encode())
        def decode(self, values, **_): return bytes(values).decode()
    class Embedder:
        tokenizer = Tokenizer()
        def encode(self, chunks):
            vector = np.zeros(384, dtype=np.float32)
            vector[0] = 1
            return [vector.copy() for _ in chunks]
    indexador = SimpleNamespace(lock=Lock(), embedder=Embedder())
    author = {"id": str(uuid4()), "name": "Admin de prueba"}
    document = ingresar(semantica, indexador, title="Procedimiento", description=None,
                       filename="pasos.md", data=b"Consultar DNS de forma segura.", author=author)
    identifier = UUID(document["id"])
    with conexion_documentos(semantica) as db:
        state = corpus_state(db, model_id=MODEL_ID)
        assert state["hasDocuments"]
        before = db.execute("SELECT count(*) FROM semantic_prototype_chunks").fetchone()[0]
    with pytest.raises(ErrorRecuperacion):
        ingresar(semantica, indexador, title="x" * 151, description=None, filename="fallo.txt", data=b"Texto valido", author=author)
    with conexion_documentos(semantica) as db:
        assert db.execute("SELECT count(*) FROM semantic_prototype_chunks").fetchone()[0] == before
        assert corpus_state(db, model_id=MODEL_ID) == state
    from starlette.datastructures import QueryParams
    request = SimpleNamespace(query_params=QueryParams(), app=SimpleNamespace(state=SimpleNamespace(configuracion=semantica)))
    with patch("app.api.documentos.identidad_aplicacion", return_value=SimpleNamespace(role="admin", id=UUID(author["id"]))):
        assert listar(request, Response())["totalItems"] == 1
        assert retirar(identifier, request).status_code == 204
        assert retirar(identifier, request).status_code == 204
        assert listar(request, Response())["totalItems"] == 0
    with conexion_documentos(semantica) as db:
        assert db.execute("SELECT count(*) FROM semantic_prototype_chunks").fetchone()[0] == 0
        with pytest.raises(ValueError):
            require_matching_profile(db, {"schemaVersion": 2, "modelId": MODEL_ID,
                "corpusId": state["corpusId"], "corpusRevision": state["revision"]})
