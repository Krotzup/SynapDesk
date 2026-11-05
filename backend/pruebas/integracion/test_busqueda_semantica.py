"""Sesión/CSRF persistentes y recuperación real; bases exclusivas de pruebas."""

import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from unittest.mock import Mock
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.aplicacion import crear_aplicacion
from app.configuracion import Configuracion
from app.persistencia.conexion import crear_motor_bd
from app.persistencia.modelos import Usuario, Sesion as SesionModelo, ContextoCsrf, TokenCsrf
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import transaccion_seguridad


@pytest.fixture(autouse=True)
def monorepository_modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3]))


@pytest.mark.skipif(not os.getenv("SEARCH_TEST_EMPTY_URL") or not os.getenv("SEARCH_TEST_PROFILE"),
                    reason="Requiere bases semánticas vacía y sin preparar exclusivas.")
@pytest.mark.parametrize("database_variable", ["SEARCH_TEST_EMPTY_URL", "SEARCH_TEST_UNPREPARED_URL"])
def test_empty_and_unprepared_databases_are_not_reported_as_low_similarity(database_variable):
    from app.recuperacion.servicio import ServicioRecuperacion, ErrorRecuperacion
    config = Configuracion(_env_file=None, app_env="testing", search_session_cookie_name="test_search_session",
                           search_relevance_profile=Path(os.environ["SEARCH_TEST_PROFILE"]),
                           synapdesk_semantic_database_url=os.environ[database_variable])
    embedder = Mock()
    embedder.encode.return_value = [[1.0] + [0.0] * 383]
    service = ServicioRecuperacion(config, embedder=embedder)
    if database_variable == "SEARCH_TEST_EMPTY_URL":
        assert service.buscar("red", 5) == {"status": "no_documents", "items": []}
    else:
        with pytest.raises(ErrorRecuperacion) as caught:
            service.buscar("red", 5)
        assert caught.value.code == "SEARCH_NOT_READY"


@pytest.mark.skipif(not os.getenv("SEARCH_TEST_PROFILE"), reason="Requiere perfil V2 y base semántica exclusiva preparada.")
def test_search_with_real_session_csrf_model_and_independent_databases(configuracion_bd_test):
    from app.recuperacion.servicio import ServicioRecuperacion
    configuration = Configuracion(_env_file=None, app_env="testing", search_enabled=False,
        search_session_cookie_name="test_search_session", auth_origenes_permitidos=["http://testserver"],
        search_relevance_profile=Path(os.environ["SEARCH_TEST_PROFILE"]),
        synapdesk_semantic_database_url=os.environ["SYNAPDESK_SEMANTIC_TEST_DATABASE_URL"],
        postgres_host=configuracion_bd_test.postgres_host, postgres_port=configuracion_bd_test.postgres_port,
        postgres_db=configuracion_bd_test.postgres_db, postgres_user=configuracion_bd_test.postgres_user,
        postgres_password=configuracion_bd_test.postgres_password)
    engine = crear_motor_bd(configuration)
    identifier = uuid4()
    try:
        with Session(engine) as db, transaccion_seguridad(db):
            db.add(Usuario(id=identifier, nombre="Caso ficticio búsqueda", correo=f"search-{identifier}@example.invalid",
                           hash_contrasena="hash ficticio de prueba", activo=True, rol="agent"))
            db.flush()
            emitted = ServicioSesiones(db).crear(identifier)
            csrf = ServicioCsrf(db, configuration)
            csrf.obtener_autenticado(emitted.credencial)
            token = csrf.emitir_token(sesion=emitted.credencial)
        service = ServicioRecuperacion(configuration)
        with TestClient(crear_aplicacion(configuration)) as client:
            client.app.state.recuperacion = service
            headers = {"Cookie": "test_search_session=" + emitted.credencial.get_secret_value(),
                       "Origin": "http://testserver", "X-CSRF-Token": token.token.get_secret_value()}
            missing = client.post("/api/v1/search", json={"query": "La impresora no imprime"})
            assert missing.status_code == 401
            invalid = client.post("/api/v1/search", json={"query": "red"}, headers=headers | {"X-CSRF-Token": "invalid"})
            assert invalid.status_code == 403 and invalid.json()["error"]["code"] == "CSRF_INVALID"
            result = client.post("/api/v1/search", json={"query": "La impresora no imprime"}, headers=headers)
            assert result.status_code == 200 and result.json()["status"] == "results"
            assert result.json()["items"][0]["documentId"] == "22222222-2222-4222-8222-222222222222"
            assert result.headers["cache-control"] == "no-store"
            distant = client.post("/api/v1/search", json={"query": "¿Cómo hago pan de masa madre?"}, headers=headers)
            assert distant.status_code == 200 and distant.json() == {"status": "insufficient_information", "items": []}
            too_long = client.post("/api/v1/search", json={"query": "red " * 140}, headers=headers)
            assert too_long.status_code == 422 and too_long.json()["error"]["code"] == "QUERY_TOKEN_LIMIT_EXCEEDED"
            original = service.profile
            service.profile = original | {"corpusRevision": original["corpusRevision"] + 1}
            stale = client.post("/api/v1/search", json={"query": "red"}, headers=headers)
            assert stale.status_code == 503 and stale.json()["error"]["code"] == "SEARCH_PROFILE_STALE"
            service.profile = original
            with Session(engine) as db, transaccion_seguridad(db):
                observed = ServicioSesiones(db).consultar(emitted.credencial)
                assert observed.ultima_actividad == db.get(SesionModelo, emitted.id).creado_en
    finally:
        with Session(engine) as db, db.begin():
            sessions = select(SesionModelo.id).where(SesionModelo.usuario_id == identifier)
            contexts = select(ContextoCsrf.id).where(ContextoCsrf.sesion_id.in_(sessions))
            db.execute(delete(TokenCsrf).where(TokenCsrf.contexto_id.in_(contexts)))
            db.execute(delete(ContextoCsrf).where(ContextoCsrf.sesion_id.in_(sessions)))
            db.execute(delete(SesionModelo).where(SesionModelo.usuario_id == identifier))
            db.execute(delete(Usuario).where(Usuario.id == identifier))
        engine.dispose()
