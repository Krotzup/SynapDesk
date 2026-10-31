from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from predict_ticket import predict  # noqa: E402


class PredictTicketTest(unittest.TestCase):
    def test_rejects_ticket_without_subject_or_body(self) -> None:
        with self.assertRaisesRegex(ValueError, "asunto o descripcion"):
            predict(Path("nonexistent.joblib"), "  ", "\n\t")


if __name__ == "__main__":
    unittest.main()
