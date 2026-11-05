from __future__ import annotations

import sys
import unittest
import tempfile
import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import joblib
import pandas as pd
from sklearn.pipeline import FeatureUnion


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from predict_ticket import build_text, predict  # noqa: E402
from prediction_output import PREDICTION_FIELDS  # noqa: E402
from train_ticket_classifier import TrainingConfig, build_model, load_and_prepare_dataset, top_prediction, train  # noqa: E402


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
                        "config": {"business_rules_enabled": False},
                        "models": {name: model for name in
                                   ("clasificacion_sugerida", "prioridad_estimada", "area_responsable")}}
            joblib.dump(artifact, path)
            for rules in (False, None):
                result = predict(path, "URGENTE correo falla", "Revisar acceso", business_rules=rules)
                self.assertFalse(result["businessRulesEnabled"])
                for prediction in result["predictions"].values():
                    self.assertEqual(set(prediction), set(PREDICTION_FIELDS))
                    self.assertEqual(prediction["top3"], sorted(prediction["top3"], key=lambda item: item["confidence"], reverse=True))
                    self.assertEqual(prediction["decision_source"], "model")
                    self.assertEqual(prediction["confidence"], prediction["model_confidence"])
                    self.assertIsNone(prediction["trigger"])
                    self.assertIsNone(prediction["rule"])
            with self.assertRaisesRegex(ValueError, "regla de urgencia fue retirada"):
                predict(path, "URGENTE", "Ayuda", business_rules=True)
            artifact["config"]["business_rules_enabled"] = True
            joblib.dump(artifact, path)
            with self.assertRaisesRegex(ValueError, "artefacto habilita una regla retirada"):
                predict(path, "URGENTE", "Ayuda")
            self.assertFalse(predict(path, "URGENTE", "Ayuda", business_rules=False)["businessRulesEnabled"])
            sample = top_prediction(model, build_text("Consulta", "Revisar acceso"))
            self.assertEqual(set(sample), set(PREDICTION_FIELDS))

    def test_legacy_artifact_with_removed_priority_is_rejected(self):
        model = build_model(200, (1, 2))
        model.fit(["falla correo red", "falla correo acceso", "manual consulta", "manual ayuda"],
                  ["critical", "critical", "low", "low"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.joblib"
            joblib.dump({"models": {"prioridad_estimada": model}}, path)
            with self.assertRaisesRegex(ValueError, "prioridades no admitidas"):
                predict(path, "Consulta", "Manual", business_rules=False)

    def test_training_rejects_removed_rule_before_reading_dataset(self):
        config = TrainingConfig(
            input_csv="nonexistent.csv", output_dir="unused", language="es", test_size=0.2,
            random_state=42, min_target_count=1, max_features=200, ngram_min=1, ngram_max=2,
            business_rules_enabled=True,
        )
        with self.assertRaisesRegex(ValueError, "regla de urgencia fue retirada"):
            train(config)

    def test_missing_artifact_is_not_reported_as_prediction(self) -> None:
        with self.assertRaises(FileNotFoundError):
            predict(Path("nonexistent.joblib"), "Consulta", "Revisar acceso")

    def test_character_variant_trains_and_preserves_inference_contract_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            config = TrainingConfig(
                input_csv=str(ROOT / "ml/samples/tickets_esp_sintetico.csv"),
                output_dir=str(output), language="es", test_size=0.2, random_state=17,
                min_target_count=1, max_features=200, ngram_min=1, ngram_max=2,
                business_rules_enabled=False, character_ngram_targets=("priority",),
            )
            with redirect_stdout(StringIO()):
                train(config)
            artifact = joblib.load(output / "ticket_classifier.joblib")
            self.assertIn("words_chars", artifact["model_name"])
            self.assertEqual(artifact["config"]["character_ngram_targets"], ("priority",))
            for target, model in artifact["models"].items():
                self.assertEqual(model.named_steps["classifier"].random_state, 17)
                self.assertEqual(isinstance(model.named_steps["tfidf"], FeatureUnion),
                                 target == "prioridad_estimada")
            metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
            self.assertTrue(all(result["shared_texts"] == 0 for result in metrics["models"].values()))
            prediction = predict(output / "ticket_classifier.joblib", "Correo caido", "No puedo trabajar")
            self.assertFalse(prediction["businessRulesEnabled"])
            for result in prediction["predictions"].values():
                self.assertEqual(set(result), set(PREDICTION_FIELDS))


if __name__ == "__main__":
    unittest.main()
