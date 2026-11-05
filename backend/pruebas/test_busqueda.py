from contextlib import contextmanager
from unittest.mock import Mock, patch
from uuid import UUID
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.aplicacion import crear_aplicacion
from app.configuracion import Configuracion
from app.recuperacion.servicio import ErrorRecuperacion, ServicioRecuperacion


@pytest.fixture(autouse=True)
def monorepository_modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))


@contextmanager
def authorized(request):
    yield None


@pytest.fixture
def client():
    config = Configuracion(_env_file=None, app_env="testing", search_session_cookie_name="test_session",
                           auth_origenes_permitidos=["http://testserver"])
    with TestClient(crear_aplicacion(config)) as value:
        yield value


@pytest.mark.parametrize("status", ["no_documents", "insufficient_information"])
def test_empty_states_are_distinguishable_private_and_read_only(client, status):
    service = Mock()
    service.buscar.return_value = {"status": status, "items": []}
    client.app.state.recuperacion = service
    with patch("app.api.busqueda.autorizar_busqueda", authorized):
        response = client.post("/api/v1/search", json={"query": "red", "limit": 5})
    assert response.status_code == 200
    assert response.json() == {"status": status, "items": []}
    assert response.headers["cache-control"] == "no-store"


def test_valid_results_keep_traceability_and_source_metadata(client):
    item = {"documentId": "11111111-1111-4111-8111-111111111111",
            "documentChunkId": "22222222-2222-4222-8222-222222222222", "title": "DNS",
            "excerpt": "Revise el servidor.", "score": 0.7, "sourceUrl": "https://learn.microsoft.com/es-es/", "language": "es"}
    client.app.state.recuperacion = Mock(buscar=Mock(return_value={"status": "results", "items": [item]}))
    with patch("app.api.busqueda.autorizar_busqueda", authorized):
        response = client.post("/api/v1/search", json={"query": "DNS"})
    assert response.status_code == 200
    assert response.json()["items"] == [item]


@pytest.mark.parametrize("payload", [{"query": " "}, {"query": "private-text" * 200},
                                     {"query": "red", "limit": True}, {"query": "red", "limit": 21},
                                     {"query": 123}, {"query": "red", "unexpected": "private-secret"}])
def test_invalid_input_uses_public_error_contract_without_echoing_input(client, payload):
    response = client.post("/api/v1/search", json=payload)
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    UUID(body["requestId"])
    assert "private-text" not in response.text and "private-secret" not in response.text


def test_missing_or_duplicated_session_never_runs_model(client):
    service = Mock()
    client.app.state.recuperacion = service
    for headers in ({}, {"Cookie": "test_session=a; test_session=b"}):
        response = client.post("/api/v1/search", json={"query": "red"}, headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    service.buscar.assert_not_called()


def test_origin_and_csrf_are_required_before_retrieval(client):
    service = Mock()
    client.app.state.recuperacion = service
    response = client.post("/api/v1/search", json={"query": "red"}, headers={"Cookie": "test_session=unknown"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_INVALID"
    response = client.post("/api/v1/search", json={"query": "red"},
                           headers={"Cookie": "test_session=unknown", "Origin": "http://testserver"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_INVALID"
    service.buscar.assert_not_called()


def test_unavailable_search_uses_sanitized_error_contract(client):
    client.app.state.recuperacion = Mock(buscar=Mock(side_effect=ErrorRecuperacion("SEARCH_PROFILE_STALE", "Recalibración necesaria.")))
    with patch("app.api.busqueda.autorizar_busqueda", authorized):
        response = client.post("/api/v1/search", json={"query": "red"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SEARCH_PROFILE_STALE"
    assert response.headers["cache-control"] == "no-store"


def test_model_failure_is_not_confused_with_query_length():
    service = object.__new__(ServicioRecuperacion)
    from threading import Lock
    from ml.semantic_retrieval.embeddings import TokenLimitExceeded
    service.lock = Lock()
    service.embedder = Mock()
    for failure, expected in [(ValueError("private dimension details"), "SEARCH_UNAVAILABLE"),
                              (TokenLimitExceeded("long"), "QUERY_TOKEN_LIMIT_EXCEEDED")]:
        service.embedder.encode.side_effect = failure
        with pytest.raises(ErrorRecuperacion) as caught:
            service.buscar("red", 5)
        assert caught.value.code == expected
        assert "private" not in str(caught.value)


def test_relative_profile_path_is_resolved_from_repository_root():
    from app.configuracion import RAIZ_PROYECTO
    configuration = Configuracion(_env_file=None, search_relevance_profile="ml/artifacts/profile.json")
    assert configuration.search_relevance_profile == RAIZ_PROYECTO / "ml/artifacts/profile.json"
