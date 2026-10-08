from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from ticket_rules import (  # noqa: E402
    apply_priority_rule_to_labels,
    apply_priority_rule_to_prediction,
    find_urgent_trigger,
)


class TicketRulesTest(unittest.TestCase):
    def test_find_urgent_trigger_normalizes_first_match(self) -> None:
        trigger = find_urgent_trigger("Necesito ayuda DE INMEDIATO, por favor.")

        self.assertEqual(trigger, "de inmediato")

    def test_priority_rule_forces_critical_label(self) -> None:
        adjusted, triggers = apply_priority_rule_to_labels(
            ["Caso normal", "URGENTE servicio caido"],
            ["low", "medium"],
        )

        self.assertEqual(adjusted, ["low", "critical"])
        self.assertEqual(triggers, ["", "urgente"])

    def test_prediction_rule_preserves_model_confidence(self) -> None:
        prediction = {
            "label": "medium",
            "confidence": 0.42,
            "top3": [
                {"label": "medium", "confidence": 0.42},
                {"label": "high", "confidence": 0.31},
            ],
        }

        result = apply_priority_rule_to_prediction(
            "Emergencia con internet en toda la oficina",
            prediction,
        )

        self.assertEqual(result["label"], "critical")
        self.assertEqual(result["model_label"], "medium")
        self.assertIsNone(result["confidence"])
        self.assertEqual(result["model_confidence"], 0.42)
        self.assertEqual(result["confidence_source"], "not_applicable")
        self.assertEqual(result["decision"], "business_rule")
        self.assertEqual(result["decision_source"], "business_rule")
        self.assertEqual(result["rule"], "urgent_priority")
        self.assertEqual(result["top3"][0]["label"], "medium")

    def test_prediction_without_rule_marks_model_decision(self) -> None:
        result = apply_priority_rule_to_prediction(
            "Consulta sobre acceso",
            {"label": "low", "confidence": 0.75},
        )

        self.assertEqual(result["label"], "low")
        self.assertEqual(result["model_label"], "low")
        self.assertEqual(result["confidence"], 0.75)
        self.assertEqual(result["model_confidence"], 0.75)
        self.assertEqual(result["confidence_source"], "model")
        self.assertEqual(result["decision"], "model")
        self.assertEqual(result["decision_source"], "model")
        self.assertNotIn("rule", result)


if __name__ == "__main__":
    unittest.main()
