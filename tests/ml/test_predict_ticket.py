from __future__ import annotations

import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import joblib
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from predict_ticket import build_text, predict  # noqa: E402
from prediction_output import PREDICTION_FIELDS  # noqa: E402
from train_ticket_classifier import build_model, load_and_prepare_dataset, top_prediction  # noqa: E402


class PredictTicketTest(unittest.TestCase):
    def test_rejects_ticket_without_subject_or_body(self) -> None:
        with self.assertRaisesRegex(ValueError, "asunto o descripcion"):
            predict(Path("nonexistent.joblib"), "  ", "\n\t")

    def test_rejects_non_text_and_normalized_empty_input_before_loading(self) -> None:
        for subject, body in [(None, "texto"), (123, "texto"), ("\\n", "\t")]:
            with self.subTest(subject=subject), patch("predict_ticket.joblib.load") as load:
                with self.assertRaises(ValueError):
                    predict(Path("nonexistent.joblib"), subject, body)
                load.assert_not_called()

    def test_preprocessing_matches_training(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.csv"
            rows = [
                {"subject": "  VPN\\n  falla  ", "body": "  Sin\n acceso\t a red ",
                 "type": "incident", "priority": "high", "queue": "it", "language": "es"},
                {"subject": "Consulta", "body": "Ayuda", "type": "request",
                 "priority": "low", "queue": "sales", "language": "es"},
            ]
            pd.DataFrame(rows).to_csv(path, index=False)
            prepared = load_and_prepare_dataset(path, "es", 1)
            self.assertEqual(prepared.iloc[0]["text"], build_text(rows[0]["subject"], rows[0]["body"]))

    def test_real_artifact_roundtrip_and_uniform_schema(self) -> None:
        model = build_model(200, (1, 2))
        model.fit(
            ["correo falla red", "correo falla acceso", "solicitud manual ayuda", "solicitud manual consulta"],
            ["high", "high", "low", "low"],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "classifier.joblib"
            artifact = {"model_name": "test", "model_version": "1",
                        "config": {"business_rules_enabled": True},
                        "models": {name: model for name in
                                   ("clasificacion_sugerida", "prioridad_estimada", "area_responsable")}}
            joblib.dump(artifact, path)
            for rules, subject in [(False, "URGENTE correo falla"), (True, "Consulta"), (True, "URGENTE correo falla")]:
                result = predict(path, subject, "Revisar acceso", business_rules=rules)
                for prediction in result["predictions"].values():
                    self.assertEqual(set(prediction), set(PREDICTION_FIELDS))
                    self.assertEqual(prediction["top3"], sorted(prediction["top3"], key=lambda item: item["confidence"], reverse=True))
                    self.assertNotIn("top_3", prediction)
                priority = result["predictions"]["prioridad_estimada"]
                if rules and "URGENTE" in subject:
                    self.assertEqual(priority["label"], "critical")
                    self.assertIsNone(priority["confidence"])
                    self.assertIsNotNone(priority["model_confidence"])
                else:
                    self.assertEqual(priority["decision_source"], "model")
                    self.assertEqual(priority["confidence"], priority["model_confidence"])
                    self.assertIsNone(priority["trigger"])
            inherited = predict(path, "URGENTE correo falla", "Revisar acceso")
            self.assertTrue(inherited["businessRulesEnabled"])
            self.assertEqual(inherited["predictions"]["prioridad_estimada"]["label"], "critical")
            sample = top_prediction(model, build_text("Consulta", "Revisar acceso"))
            self.assertEqual(set(sample), set(PREDICTION_FIELDS))

    def test_missing_artifact_is_not_reported_as_prediction(self) -> None:
        with self.assertRaises(FileNotFoundError):
            predict(Path("nonexistent.joblib"), "Consulta", "Revisar acceso")


if __name__ == "__main__":
    unittest.main()
