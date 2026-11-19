"""El modo reproducible conserva el validador real y nunca usa el proveedor."""

import json
import logging
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.api import recomendaciones
from app.seguridad.transacciones import ErrorSeguridad
from herramientas.ingreso_local.rag_ensayo import EventosRag, FUENTE, preparar_rag
from pruebas.login_auxiliar import configuracion_login


def configuracion():
    return configuracion_login(app_env="testing", postgres_host="127.0.0.1", postgres_port=5433,
                              postgres_db="synapdesk_auth07_sec01a_" + uuid4().hex)


@pytest.mark.parametrize("fixture", ["draft", "abstention"])
def test_fixture_pasa_por_orquestacion_y_registra_etapa_sin_egress(fixture):
    evidencia = {}
    original = recomendaciones.generar
    logger = logging.getLogger("app.recomendaciones.generacion")
    nivel, handlers = logger.level, list(logger.handlers)
    with patch("app.recomendaciones.generacion.urlopen", side_effect=AssertionError("egress")):
        with preparar_rag(configuracion(), fixture, evidencia) as recuperacion:
            result = recomendaciones.generar("Ticket sintético", recuperacion,
                api_key="clave-que-no-debe-aparecer", timeout=1, max_chunks=5)
    assert recomendaciones.generar is original
    assert logger.level == nivel and logger.handlers == handlers
    assert evidencia["rag_mode"] == "fixture"
    assert "clave-que-no-debe-aparecer" not in str(evidencia)
    if fixture == "draft":
        content, sources = result
        assert content == FUENTE["excerpt"] + " [" + FUENTE["documentChunkId"] + "]"
        assert sources == [FUENTE]
        assert evidencia["rag_events"][0]["outcome"] == "draft"
    else:
        assert result is None
        assert evidencia["rag_events"][0]["outcome"] == "insufficient_information"
        assert evidencia["rag_events"][0]["stage"] == "generation"


def test_fixture_rechaza_entorno_ajeno_y_restaura_despues_de_error():
    original = recomendaciones.generar
    with pytest.raises(ErrorSeguridad):
        with preparar_rag(configuracion_login(), "draft", {}):
            pytest.fail("Aceptó un entorno ajeno al ensayo")
    with pytest.raises(RuntimeError):
        with preparar_rag(configuracion(), "draft", {}):
            raise RuntimeError("fallo del ensayo")
    assert recomendaciones.generar is original


def test_telemetria_ignora_mensajes_arbitrarios():
    evidencia = {}
    with preparar_rag(configuracion(), "draft", evidencia):
        logging.getLogger("app.recomendaciones.generacion").info("dato privado %s", "no registrar")
    assert evidencia["rag_events"] == []


def test_checkpoint_no_expone_json_parcial_a_lectores(tmp_path, monkeypatch):
    from herramientas.ingreso_local import demo
    path = tmp_path / "reply.json"
    siguiente = {"sequence": 2, "passed": True}

    def escritura_interrumpida(destino, value):
        with destino.open("w", encoding="utf-8") as archivo:
            archivo.write('{"sequence":')
            archivo.flush()
            # Simula el sondeo del navegador mientras el escritor aún no termina.
            assert not path.exists()
            archivo.write('2,"passed":true}')

    monkeypatch.setattr(demo, "escribir", escritura_interrumpida)
    demo.responder_checkpoint(path, siguiente)
    assert json.loads(path.read_text(encoding="utf-8")) == siguiente


def test_checkpoint_tolera_bloqueo_transitorio_de_windows(tmp_path, monkeypatch):
    from pathlib import Path
    from herramientas.ingreso_local import demo
    path = tmp_path / "reply.json.1"
    reemplazar = Path.replace
    intentos = []

    def ocupado(temporal, destino):
        intentos.append(1)
        if len(intentos) == 1:
            raise PermissionError("archivo ocupado")
        return reemplazar(temporal, destino)

    monkeypatch.setattr(Path, "replace", ocupado)
    demo.responder_checkpoint(path, {"sequence": 1, "passed": True})
    assert json.loads(path.read_text(encoding="utf-8")) == {"sequence": 1, "passed": True}
    assert len(intentos) == 2


def test_eventos_del_proveedor_solo_conservan_metadatos_permitidos():
    eventos = []
    handler = EventosRag(eventos)
    messages = [
        ("rag provider outcome=http_error status=%d duration_ms=%.1f", (429, 123.4)),
        ("rag provider outcome=invalid_or_unreachable duration_ms=%.1f", (20000.1,)),
        ("rag provider outcome=success model=%s duration_ms=%.1f usage=%s",
         ("dato-privado", 100.0, {"promptTokenCount": 4, "totalTokenCount": 9,
          "candidatesTokenCount": True, "thoughtsTokenCount": -1, "privateValue": "dato-privado"})),
    ]
    for message, args in messages:
        handler.emit(logging.LogRecord("test", logging.INFO, __file__, 1, message, args, None))
    assert eventos[0] == {"stage": "provider", "outcome": "http_error", "status": 429, "duration_ms": 123.4}
    assert eventos[1]["outcome"] == "invalid_or_unreachable"
    assert eventos[2]["usage"] == {"promptTokenCount": 4, "totalTokenCount": 9}
    assert "dato-privado" not in str(eventos)


def test_driver_ausente_se_rechaza_antes_de_crear_recursos(tmp_path, monkeypatch):
    from herramientas.ingreso_local import demo
    monkeypatch.setattr(demo, "BACKEND", tmp_path)
    with pytest.raises(ValueError, match="driver de navegador"):
        demo.ejecutar(tmp_path, tmp_path / "report.json", tmp_path / "ausente.mjs")
    assert list(tmp_path.iterdir()) == []
