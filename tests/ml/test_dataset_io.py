import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from dataset_io import CORRECTION_FIELDS, apply_priority_corrections, correction_validation, file_sha256, read_dataset
from train_ticket_classifier import load_and_prepare_dataset, safe_train_test_split


class DatasetIOTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "tickets.csv"
        self.corrections = self.root / "correcciones_prioridad.csv"
        self.manifest = self.root / "manifest.json"
        pd.DataFrame([
            {"subject": "Consulta", "body": "Manual", "priority": "low", "type": "request", "queue": "help", "language": "en"},
            {"subject": "Facturación caída", "body": "Área completa sin operar", "priority": "low", "type": "incident", "queue": "it", "language": "es"},
            {"subject": "Consulta", "body": "Manual", "priority": "medium", "type": "request", "queue": "help", "language": "es"},
        ]).to_csv(self.source, index=False)

    def write_corrections(self, rows):
        with self.corrections.open("w", newline="", encoding="utf-8") as destination:
            writer = csv.writer(destination)
            writer.writerow(CORRECTION_FIELDS)
            writer.writerows(rows)
        self.manifest.write_text(json.dumps({
            "source_sha256": file_sha256(self.source),
            "corrections_sha256": file_sha256(self.corrections),
            "criteria_version": "prioridad-impacto-v1",
        }), encoding="utf-8")

    def test_corrections_preserve_source_and_original_record_numbers(self):
        original_hash = file_sha256(self.source)
        self.write_corrections([[3, "low", "high", "Área completa sin operar"],
                                [4, "medium", "medium", "dudoso: falta impacto"]])
        prepared = load_and_prepare_dataset(self.source, "es", 1, self.corrections, self.manifest)
        self.assertEqual(prepared["priority"].tolist(), ["high", "medium"])
        self.assertEqual(file_sha256(self.source), original_hash)
        self.assertEqual(prepared.attrs["priority_corrections"]["changed_rows"], 1)
        self.assertEqual(prepared.attrs["priority_corrections"]["doubtful_rows"], 1)

    def test_invalid_corrections_are_rejected(self):
        for rows in (
            [[99, "low", "high", "Impacto"]], [[3, "medium", "high", "Impacto"]],
            [[3, "low", "high", ""]], [[3, "low", "unknown", "Impacto"]],
            [[3, "low", "high", "dudoso: sin evidencia"]],
            [[3, "low", "critical", "Urgente"]],
            [[3, "low", "high", "Impacto"], [3, "low", "medium", "Alternativa"]],
        ):
            with self.subTest(rows=rows):
                self.write_corrections(rows)
                with self.assertRaises(ValueError):
                    apply_priority_corrections(read_dataset(self.source), self.corrections, self.manifest)

    def test_changed_source_or_corrections_are_rejected(self):
        self.write_corrections([[3, "low", "high", "Impacto"]])
        self.source.write_text(self.source.read_text(encoding="utf-8").replace("Manual", "Guía"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            apply_priority_corrections(read_dataset(self.source), self.corrections, self.manifest)
        self.write_corrections([[3, "low", "high", "Impacto"]])
        with self.corrections.open("a", encoding="utf-8") as destination:
            destination.write("\n")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            apply_priority_corrections(read_dataset(self.source), self.corrections, self.manifest)

    def test_encoding_and_malformed_rows_fail_without_discarding_data(self):
        for raw in (b"subject,priority\nerror,low,extra\n", b"subject,priority\n\xff,low\n",
                    b"subject,subject\na,b\n", b'subject,priority\n"unterminated,low\n'):
            with self.subTest(raw=raw):
                self.source.write_bytes(raw)
                with self.assertRaises(ValueError):
                    read_dataset(self.source)

    def test_unsplittable_groups_fail_instead_of_leaking_text(self):
        data = pd.DataFrame({"text": ["idéntico", "idéntico"], "priority": ["low", "high"]})
        with self.assertRaisesRegex(ValueError, "grupos"):
            safe_train_test_split(data, "priority", 0.2, 42)

    def test_manifest_required_and_multiline_records_supported(self):
        with self.assertRaisesRegex(ValueError, "juntos"):
            load_and_prepare_dataset(self.source, "es", 1, self.corrections)
        self.source.write_text('subject,body\n"Línea uno\nLínea dos",Texto\n', encoding="utf-8")
        self.assertEqual(len(read_dataset(self.source)), 1)

    def test_human_validation_is_pending_unless_explicitly_declared(self):
        self.assertEqual(correction_validation({}, 63), {"status": "pending"})
        validation = {"status": "validated", "reviewer": "Responsable ficticia de prueba",
                      "validated_at": "2026-11-05T12:00:00Z", "reviewed_rows": 63}
        self.assertEqual(correction_validation({"validation": validation}, 63), validation)
        for changed in ({"reviewer": ""}, {"validated_at": "2026-11-05T12:00:00"},
                        {"validated_at": "2026-11-05T12:00:00-03:00"},
                        {"reviewed_rows": 38}, {"reviewed_rows": True}, {"status": "approved"}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                correction_validation({"validation": dict(validation, **changed)}, 63)
        with self.assertRaises(ValueError):
            correction_validation({"validation": {"status": "pending", "reviewer": "Alguien"}}, 63)

    def test_validation_provenance_is_preserved_with_correction_counts(self):
        self.write_corrections([[3, "low", "high", "Impacto"]])
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["validation"] = {"status": "validated", "reviewer": "Responsable ficticia",
                                  "validated_at": "2026-11-05T12:00:00Z", "reviewed_rows": 1}
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        result = apply_priority_corrections(read_dataset(self.source), self.corrections, self.manifest)
        self.assertEqual(result.attrs["priority_corrections"]["validation"], manifest["validation"])
