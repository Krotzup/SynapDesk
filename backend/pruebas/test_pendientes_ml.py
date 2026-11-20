"""Validación de entradas y límites nuevos, sin proveedor ni datos privados."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import QueryParams
from app.aplicacion import crear_aplicacion
from app.api.tickets import pagina_tickets
from app.clasificacion import ServicioClasificacion
from app.configuracion import Configuracion
from app.documentos import validar_archivo
from app.recuperacion.servicio import ErrorRecuperacion
from app.tickets.transiciones import transicion_permitida


def test_filtros_combinados_y_paginacion_estricta():
    value = pagina_tickets(QueryParams("status=open&priority=high&category=Red&area=TI&search=100%25&page=2"))
    assert (value.status, value.priority, value.category, value.area, value.search, value.page) == (
        "open", "high", "Red", "TI", "100%", 2)
    for query in ("status=open&status=closed", "priority=critical", "sort=sql", "page=1e2", "pageSize=101"):
        with pytest.raises(ErrorRecuperacion) as error:
            pagina_tickets(QueryParams(query))
        assert error.value.status == 422


def test_transiciones_resolver_cerrar_reabrir():
    for actual, destino in (("open", "resolved"), ("resolved", "closed"), ("closed", "in_progress"), ("open", "open")):
        assert transicion_permitida(actual, destino)
    for actual, destino in (("open", "closed"), ("closed", "open"), ("resolved", "open")):
        assert not transicion_permitida(actual, destino)


@pytest.mark.parametrize("filename,data,code", [
    ("../texto.txt", b"texto", "VALIDATION_ERROR"), ("archivo.pdf", b"%PDF", "DOCUMENT_FORMAT_UNSUPPORTED"),
    ("archivo.txt", b"\xff", "VALIDATION_ERROR"), ("archivo.md", b"  ", "VALIDATION_ERROR"),
    ("archivo.txt", b"a\x00b", "VALIDATION_ERROR"), ("archivo.txt", b"a" * 65537, "DOCUMENT_TOO_LARGE"),
], ids=["ruta", "formato", "codificacion", "vacio", "binario", "tamano"])
def test_documentos_invalidos_no_llegan_al_indexador(filename, data, code):
    with pytest.raises(ErrorRecuperacion) as error:
        validar_archivo(filename, data)
    assert error.value.code == code


def test_texto_bom_y_markdown_se_conservan():
    assert validar_archivo("procedimiento.MD", b"\xef\xbb\xbf# Paso\ntexto") == ("# Paso\ntexto", "text/markdown")


def test_clasificador_no_inventa_mapeo_ni_confianza_global():
    from threading import Lock
    service = ServicioClasificacion.__new__(ServicioClasificacion)
    service.lock, service.categories, service.areas = Lock(), {}, {}
    service.model = Mock()
    service.model.predict.return_value = {"modelName": "prueba", "modelVersion": "1", "predictions": {
        name: {"label": label, "confidence": 0.75} for name, label in
        (("clasificacion_sugerida", "incident"), ("prioridad_estimada", "high"), ("area_responsable", "it"))}}
    result = service.predecir("Problema", "Descripción")
    assert result["predictedCategory"] is result["predictedArea"] is result["confidence"] is None
    assert result["predictedType"] == "incident" and result["predictedPriority"] == "high"
    service.model.predict.return_value["predictions"]["prioridad_estimada"]["confidence"] = float("nan")
    with pytest.raises(ErrorRecuperacion):
        service.predecir("Problema", "Descripción")


def test_hash_incorrecto_se_rechaza_antes_de_deserializar(tmp_path):
    path = tmp_path / "model.joblib"
    path.write_bytes(b"no deserializar")
    config = Configuracion(_env_file=None, classifier_model_path=path, classifier_model_sha256="0" * 64)
    import sys
    joblib = Mock()
    with patch.dict(sys.modules, {"joblib": joblib}), pytest.raises(ValueError):
        ServicioClasificacion(config)
    joblib.load.assert_not_called()


def test_documentos_exigen_admin_antes_de_leer_archivo():
    app = crear_aplicacion(Configuracion(_env_file=None))
    with TestClient(app) as client, patch("app.api.documentos.identidad_aplicacion",
            return_value=SimpleNamespace(role="agent", id=uuid4())):
        response = client.post("/api/v1/documents", content=b"archivo no analizado")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert response.headers["cache-control"] == "no-store"


def test_carga_multipart_pasa_bytes_y_metadatos_al_indexador():
    # Prueba del parser real, reemplazando solo persistencia/identidad.
    app = crear_aplicacion(Configuracion(_env_file=None))
    app.state.configuracion = Configuracion(_env_file=None, documents_enabled=True)
    with TestClient(app) as client, patch("app.api.documentos.administrador", return_value=SimpleNamespace(id=uuid4())), \
            patch("app.api.documentos.Session") as session, patch("app.api.documentos.ingresar", return_value={"id": "nuevo"}) as ingest:
        user = session.return_value.__enter__.return_value.get.return_value
        user.id, user.nombre, user.correo, user.rol, user.activo = uuid4(), "Admin", "admin@example.invalid", "admin", True
        from datetime import UTC, datetime
        user.creado_en = user.actualizado_en = datetime.now(UTC)
        response = client.post("/api/v1/documents", data={"title": "Procedimiento", "description": ""},
                               files={"file": ("procedimiento.txt", b"Consultar DNS", "text/plain")})
        assert response.status_code == 201, response.text
        assert ingest.call_args.kwargs["data"] == b"Consultar DNS"
        assert ingest.call_args.kwargs["filename"] == "procedimiento.txt"
