from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from train_ticket_classifier import (  # noqa: E402
    REQUIRED_COLUMNS,
    load_and_prepare_dataset,
    safe_train_test_split,
    validate_columns,
)


def valid_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "subject": "No puedo acceder",
        "body": "El correo no permite iniciar sesion",
        "type": "Incident",
        "queue": "IT Support",
        "priority": "Medium",
        "language": "es",
    }
    row.update(overrides)
    return row


class TrainTicketClassifierTest(unittest.TestCase):
    def test_validate_columns_reports_missing_columns(self) -> None:
        columns = sorted(REQUIRED_COLUMNS - {"body"})
        df = pd.DataFrame(columns=columns)

        with self.assertRaisesRegex(ValueError, "body"):
            validate_columns(df)

    def test_load_and_prepare_dataset_filters_and_normalizes_rows(self) -> None:
        rows = [
            valid_row(subject="No puedo acceder", type="Incident"),
            valid_row(subject="No puedo acceder", type="Incident"),
            valid_row(subject="Cambio permisos", type="Request", priority="Low"),
            valid_row(subject="VPN falla", type="Incident", queue="Network"),
            valid_row(subject="Not english", language="en"),
            valid_row(subject="", body=""),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "tickets.csv"
            pd.DataFrame(rows).to_csv(csv_path, index=False)

            prepared = load_and_prepare_dataset(
                csv_path=csv_path,
                language="es",
                min_target_count=1,
            )

        self.assertEqual(len(prepared), 3)
        self.assertEqual(set(prepared["language"]), {"es"})
        self.assertEqual(set(prepared["type"]), {"incident", "request"})
        self.assertIn("it_support", set(prepared["queue"]))

    def test_safe_train_test_split_keeps_duplicate_texts_together(self) -> None:
        df = pd.DataFrame(
            [
                {"text": "texto repetido", "priority": "low"},
                {"text": "texto repetido", "priority": "medium"},
                {"text": "texto unico a", "priority": "high"},
                {"text": "texto unico b", "priority": "critical"},
                {"text": "texto unico c", "priority": "low"},
                {"text": "texto unico d", "priority": "medium"},
            ]
        )

        x_train, x_test, _, _ = safe_train_test_split(
            df=df,
            target="priority",
            test_size=0.4,
            random_state=7,
        )

        self.assertFalse(set(x_train).intersection(set(x_test)))


if __name__ == "__main__":
    unittest.main()
