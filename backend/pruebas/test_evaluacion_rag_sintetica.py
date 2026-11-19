"""La evaluación humana recibe evidencia; las consultas privadas se rechazan."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herramientas.evaluar_rag_sintetico import cargar_caso, evaluar
from herramientas.resumir_evaluacion_rag import resumir


class EvaluacionRagSinteticaTest(unittest.TestCase):
    def test_rechaza_caso_que_contiene_credencial(self):
        payload = json.dumps({"annotationStatus": "synthetic_pending_human_review",
                              "queries": [{"queryId": "S01", "query": "password=privada",
                                           "answerable": True}]})
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(ValueError):
                cargar_caso(Path("cases.json"), "S01")

    def test_informe_conserva_fuentes_y_campos_para_revision_humana(self):
        document_id, fragment_id = uuid4(), uuid4()
        case = {"queryId": "S01", "query": "Consulta DNS", "answerable": True,
                "expectedDocumentId": str(document_id)}
        source = {"documentId": document_id, "documentChunkId": fragment_id,
                  "title": "DNS", "excerpt": "Consultar DNS configurado.", "score": 0.8}
        config = type("Config", (), {"gemini_api_key": SecretStr("clave-privada"),
                                     "rag_timeout_seconds": 15,
                                     "rag_max_context_chunks": 5})()
        with (patch("herramientas.evaluar_rag_sintetico.ServicioRecuperacion"),
              patch("herramientas.evaluar_rag_sintetico.generar",
                    return_value=(f"Consultar DNS [{fragment_id}]", [source])) as generator):
            report = evaluar(case, config)
        generator.assert_called_once()
        self.assertEqual(report["outcome"], "draft")
        self.assertTrue(report["expectedDocumentCited"])
        self.assertEqual(report["sources"][0]["documentChunkId"], str(fragment_id))
        self.assertIsNone(report["humanReview"]["evidenceSupportsEveryStep"])
        self.assertNotIn("clave-privada", json.dumps(report))

    def test_resumen_distingue_resultado_automatico_de_revision_humana(self):
        def report(case_id, expected, outcome, reviewed=False):
            return {"caseId": case_id, "answerableExpected": expected,
                    "outcome": outcome, "outcomeMatches": expected == (outcome == "draft"),
                    "expectedDocumentCited": outcome == "draft", "durationMs": 100,
                    "humanReview": {"evidenceSupportsEveryStep": True if reviewed else None,
                                    "usefulForSpecialist": True if reviewed else None,
                                    "safeToPresent": True if reviewed else None}}

        summary = resumir([report("P1", True, "draft"),
                           report("P2", True, "insufficient_information"),
                           report("N1", False, "insufficient_information", reviewed=True)])
        self.assertEqual(summary["positiveDrafts"], 1)
        self.assertEqual(summary["negativeAbstentions"], 1)
        self.assertEqual(summary["humanReviewed"], 1)
        self.assertEqual(summary["humanApproved"], 1)
        self.assertEqual(summary["failedCaseIds"], ["P2"])


if __name__ == "__main__":
    unittest.main()
