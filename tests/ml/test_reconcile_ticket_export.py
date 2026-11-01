import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from dataset_io import file_sha256, read_dataset
from reconcile_ticket_export import EXPECTED_HEADER, reconcile


class ReconcileExportTest(unittest.TestCase):
    def write_export(self, path, records):
        with path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.writer(output, delimiter=";")
            for fields in [EXPECTED_HEADER] + records:
                inner = io.StringIO()
                csv.writer(inner).writerow(fields)
                writer.writerow([inner.getvalue().rstrip("\r\n"), "", ""])

    def test_preserves_edits_repairs_only_optional_delimiter_and_quarantines_ambiguity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, edited = root / "original.csv", root / "edited.csv"
            row = ["1", "Consulta", "Texto original", "Respuesta", "incident", "it_support",
                   "medium", "support", "Urgent Issue", "network", "hardware", "es", "original"]
            changed = row.copy()
            changed[2], changed[6] = "Texto editado sin inventar impacto", "high"
            del changed[8]
            ambiguous = row.copy()
            ambiguous[0] = "2"
            del ambiguous[3]  # Falta respuesta: no se adivina la frontera cuerpo/respuesta.
            self.write_export(original, [row, ambiguous])
            self.write_export(edited, [changed, ambiguous])
            hashes = file_sha256(original), file_sha256(edited)
            report = reconcile(original, edited, root / "out", "utf-8")
            data = read_dataset(root / "out/tickets_esp_utf8_normalizado.csv")
            self.assertEqual(data.iloc[0]["body"], changed[2])
            self.assertEqual(data.iloc[0]["priority"], "high")
            self.assertTrue(pd.isna(data.iloc[0]["tag_1"]))  # Vacía, no restaurada.
            self.assertEqual(report["validated_records"], 1)
            self.assertEqual(report["quarantined_record_numbers"], [3])
            self.assertEqual(len(report["structural_repairs"]), 1)
            self.assertEqual(hashes, (file_sha256(original), file_sha256(edited)))

    def test_mismatched_row_count_fails_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_export(root / "original.csv", [])
            self.write_export(root / "edited.csv", [["incomplete"]])
            with self.assertRaisesRegex(ValueError, "cantidad"):
                reconcile(root / "original.csv", root / "edited.csv", root / "out", "utf-8")
            self.assertFalse((root / "out").exists())
