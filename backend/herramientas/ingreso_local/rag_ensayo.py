"""Dependencias sintéticas y telemetría acotada, exclusivas del ensayo local."""

from contextlib import contextmanager
from functools import partial
import json
import logging
from unittest.mock import patch

from app.recomendaciones.generacion import MODEL, generar
from herramientas.ingreso_local.evidencia import exigir_testing_propio


FUENTE = {
    "documentId": "10000000-0000-4000-8000-000000000001",
    "documentChunkId": "10000000-0000-4000-8000-000000000002",
    "title": "Procedimiento DNS sintético del ensayo",
    "excerpt": "Comprobar el servidor DNS configurado y revisar el archivo hosts.",
    "score": 0.9,
}


class RecuperacionSintetica:
    def buscar(self, query, limit):
        return {"status": "results", "items": [dict(FUENTE)][:limit]}


class EventosRag(logging.Handler):
    """Nunca copia mensajes arbitrarios, entradas, fragmentos ni salida del modelo."""
    def __init__(self, eventos):
        super().__init__(logging.INFO)
        self.eventos = eventos

    def emit(self, record):
        args = record.args
        if record.msg == "rag outcome=insufficient stage=retrieval duration_ms=%.1f":
            evento = dict(outcome="insufficient_information", stage="retrieval", duration_ms=round(args[0], 1))
        elif record.msg == "rag outcome=insufficient stage=generation duration_ms=%.1f":
            evento = dict(outcome="insufficient_information", stage="generation", duration_ms=round(args[0], 1))
        elif record.msg == "rag outcome=draft sources=%d duration_ms=%.1f":
            evento = dict(outcome="draft", sources=args[0], duration_ms=round(args[1], 1))
        elif record.msg == "rag provider outcome=http_error status=%d duration_ms=%.1f":
            evento = dict(stage="provider", outcome="http_error", status=args[0], duration_ms=round(args[1], 1))
        elif record.msg == "rag provider outcome=invalid_or_unreachable duration_ms=%.1f":
            evento = dict(stage="provider", outcome="invalid_or_unreachable", duration_ms=round(args[0], 1))
        elif record.msg == "rag provider outcome=success model=%s duration_ms=%.1f usage=%s":
            counts = {key: value for key in ("promptTokenCount", "candidatesTokenCount",
                       "thoughtsTokenCount", "totalTokenCount")
                      if type(value := args[2].get(key)) is int and value >= 0}
            evento = dict(stage="provider", outcome="success", model=MODEL,
                          duration_ms=round(args[1], 1), usage=counts)
        else:
            return
        self.eventos.append(evento)


@contextmanager
def preparar_rag(config, fixture, evidencia):
    exigir_testing_propio(config)
    evidencia["rag_mode"] = "fixture" if fixture else "live"
    evidencia["rag_fixture"] = fixture
    evidencia["rag_events"] = []
    logger = logging.getLogger("app.recomendaciones.generacion")
    nivel = logger.level
    handler = EventosRag(evidencia["rag_events"])
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        if fixture:
            if fixture not in {"draft", "abstention"}:
                raise ValueError("Fixture RAG desconocido.")

            def completar(ticket, fragments, **kwargs):
                steps = [] if fixture == "abstention" else [{
                    "text": FUENTE["excerpt"], "fragmentIds": [FUENTE["documentChunkId"]],
                }]
                return json.dumps({"steps": steps})

            # Solo se sustituye recuperación/proveedor; siguen reales la orquestación,
            # validación de citas, API, ingreso, sesión, CSRF y persistencia.
            with patch("app.api.recomendaciones.generar", partial(generar, completar=completar)):
                yield RecuperacionSintetica()
        else:
            from app.recuperacion.servicio import ServicioRecuperacion
            recuperacion = ServicioRecuperacion(config)
            evidencia["rag_retrieval_profile"] = {key: recuperacion.profile[key] for key in (
                "schemaVersion", "modelId", "corpusSha256", "casesSha256", "minScore")}
            yield recuperacion
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel)
