from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from audit_ticket_dataset import audit_priority_labels, file_sha256  # noqa: E402


class AuditTicketDatasetTest(unittest.TestCase):
    def test_flags_candidates_without_changing_labels_or_source(self) -> None:
        rows = [
            {
                "subject": "URGENTE: falla de correo",
                "body": "No responde",
                "type": "Incident",
                "queue": "IT Support",
                "priority": "Low",
                "language": "es",
            },
            {
                "subject": "No es urgente",
                "body": "Puede esperar",
                "type": "Incident",
                "queue": "IT Support",
                "priority": "Medium",
                "language": "es",
            },
            {
                "subject": "Emergencia",
                "body": "Servicio caido",
                "type": "Incident",
                "queue": "IT Support",
                "priority": "High",
                "language": "es",
            },
            {
                "subject": "Urgente",
                "body": "Other language",
                "type": "Incident",
                "queue": "IT Support",
                "priority": "Low",
                "language": "en",
            },
            {
                "subject": "No es urgente",
                "body": "Puede esperar",
                "type": "Incident",
                "queue": "IT Support",
                "priority": "Medium",
                "language": "es",
            },
        ]
        with tempfile.TemporaryDirectory() as temporary_dir:
            csv_path = Path(temporary_dir) / "tickets.csv"
            pd.DataFrame(rows).to_csv(csv_path, index=False)
            original_hash = file_sha256(csv_path)

            report, candidates = audit_priority_labels(csv_path, "es")

            self.assertEqual(file_sha256(csv_path), original_hash)

        self.assertEqual(report["input_rows"], 5)
        self.assertEqual(report["language_rows"], 4)
        self.assertEqual(report["duplicate_exact_rows"], 1)
        self.assertEqual(report["texts_with_conflicting_priority_labels"], 0)
        self.assertEqual(report["urgency_signal_rows"], 2)
        self.assertEqual(report["priority_review_candidates"], 1)
        self.assertEqual(report["labels_changed"], 0)
        self.assertEqual(
            candidates,
            [{"csv_row_number": 2, "current_priority": "low", "trigger": "urgente"}],
        )


if __name__ == "__main__":
    unittest.main()
