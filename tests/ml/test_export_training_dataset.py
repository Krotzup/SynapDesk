import csv
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest

import joblib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from dataset_io import CORRECTION_FIELDS, apply_priority_corrections, file_sha256, read_dataset
from export_training_dataset import export_training_dataset
from train_ticket_classifier import TrainingConfig, load_and_prepare_dataset, train


class ExportTrainingDatasetTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.source = self.directory / "source.csv"
        self.corrections = self.directory / "corrections.csv"
        self.correction_manifest = self.directory / "corrections.json"
        self.output = self.directory / "tickets_esp_entrenamiento_v1.csv"
        self.manifest_path = self.output.with_suffix(".manifest.json")
        with self.source.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerows([
                ["indice_original", "subject", "body", "answer", "type", "queue", "priority", "language"],
                ["0007", 'Consulta "VPN"', "Línea uno\nLínea dos, acceso", "NA", "incident", "it", "medium", "es"],
                ["0008", "Manual", "Documentación, no urgente", "", "request", "help", "low", "es"],
                ["0009", "Red caída", "Sin servicio", "", "incident", "it", "high", "es"],
                ["0010", "Instalación", "Cambio de puesto", "", "request", "help", "medium", "es"],
            ])
        with self.corrections.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerows([
                CORRECTION_FIELDS, [2, "medium", "high", "Bloqueo operativo confirmado"],
                [3, "low", "low", "dudoso: falta impacto"],
            ])
        self.validation = {"status": "validated", "reviewer": "Responsable ficticia",
                           "validated_at": "2026-11-05T17:57:02Z", "reviewed_rows": 2}
        self.correction_manifest.write_text(json.dumps({
            "source_sha256": file_sha256(self.source), "corrections_sha256": file_sha256(self.corrections),
            "criteria_version": "prioridad-impacto-v1", "validation": self.validation,
            "validation_note": "Fecha de confirmación; fecha histórica no conocida.",
        }), encoding="utf-8")

    def export(self):
        return export_training_dataset(self.source, self.corrections, self.correction_manifest, self.output)

    def test_roundtrip_preserves_all_text_identifiers_and_records(self):
        before_hash = file_sha256(self.source)
        report = self.export()
        with self.source.open(encoding="utf-8-sig", newline="") as stream:
            original = list(csv.reader(stream, strict=True))
        with self.output.open(encoding="utf-8-sig", newline="") as stream:
            derived = list(csv.reader(stream, strict=True))
        differences = [(row, column) for row in range(len(original))
                       for column in range(len(original[0])) if original[row][column] != derived[row][column]]
        self.assertEqual(differences, [(1, 6)])
        self.assertEqual(derived[1][0], "0007")
        self.assertEqual(derived[1][3], "NA")
        self.assertEqual(file_sha256(self.source), before_hash)
        self.assertEqual(report["source_records"], 4)
        self.assertEqual(report["output_records"], 4)
        self.assertEqual(report["priority_changes"], 1)
        self.assertEqual(report["doubtful_decisions_preserved"], 1)
        self.assertEqual(report["dataset_sha256"], file_sha256(self.output))
        self.assertEqual(report["validation"], self.validation)

    def test_export_is_deterministic_and_rejects_overwrite(self):
        self.export()
        original_output = self.output.read_bytes()
        original_manifest = self.manifest_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "existen"):
            self.export()
        self.assertEqual(self.output.read_bytes(), original_output)
        self.assertEqual(self.manifest_path.read_bytes(), original_manifest)
        other = self.directory / "otra.csv"
        export_training_dataset(self.source, self.corrections, self.correction_manifest, other)
        self.assertEqual(other.read_bytes(), original_output)

    def test_existing_sidecar_or_invalid_corrections_do_not_create_csv(self):
        self.manifest_path.write_text("preservado", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.manifest_path.read_text(encoding="utf-8"), "preservado")
        self.manifest_path.unlink()
        with self.corrections.open("a", encoding="utf-8") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.export()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.manifest_path.exists())

    def test_reader_retains_provenance_and_prevents_double_corrections(self):
        self.export()
        data = read_dataset(self.output)
        self.assertEqual(data.attrs["source_sha256"], file_sha256(self.output))
        self.assertEqual(data.attrs["derived_dataset"]["original_source_sha256"], file_sha256(self.source))
        self.assertEqual(data.attrs["priority_corrections"]["validation"], self.validation)
        self.assertIn("histórica", data.attrs["priority_corrections"]["validation_note"])
        with self.assertRaisesRegex(ValueError, "reaplicarse"):
            apply_priority_corrections(data, self.corrections, self.correction_manifest)
        with self.assertRaisesRegex(ValueError, "reaplicarse"):
            export_training_dataset(self.output, self.corrections, self.correction_manifest,
                                    self.directory / "twice.csv")

    def test_corrupt_renamed_or_incoherent_sidecars_are_rejected(self):
        valid = self.export()
        for change in ({"dataset_file": "anterior.csv"}, {"dataset_sha256": "0" * 64},
                       {"schema_version": True}, {"output_records": 3}, {"text_changes": 1},
                       {"source_records": True}, {"source_sha256": "missing"},
                       {"reviewed_rows": 5}, {"doubtful_decisions_preserved": 2},
                       {"corrections_already_applied": False},
                       {"validation": dict(self.validation, reviewed_rows=1)}):
            with self.subTest(change=change):
                self.manifest_path.write_text(json.dumps(dict(valid, **change)), encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_dataset(self.output)
        self.manifest_path.write_text(json.dumps(valid), encoding="utf-8")
        with self.output.open("a", encoding="utf-8") as stream:
            stream.write("\n")
        with self.assertRaises(ValueError):
            read_dataset(self.output)

    def test_training_preserves_derived_validation_in_artifact_and_metrics(self):
        self.export()
        prepared = load_and_prepare_dataset(self.output, "es", 1)
        self.assertEqual(prepared.attrs["priority_corrections"]["changed_rows"], 1)
        output = self.directory / "model"
        with redirect_stdout(StringIO()):
            train(TrainingConfig(
                input_csv=str(self.output), output_dir=str(output), language="es", test_size=0.25,
                random_state=42, min_target_count=1, max_features=100, ngram_min=1, ngram_max=2,
                business_rules_enabled=False, character_ngram_targets=("priority",),
            ))
        artifact = joblib.load(output / "ticket_classifier.joblib")
        metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
        artifact_manifest = json.loads((output / "artifact_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(artifact_manifest["artifact_sha256"], file_sha256(output / "ticket_classifier.joblib"))
        self.assertEqual(artifact_manifest["runtime"], artifact["runtime"])
        for metadata in (artifact["dataset"], metrics["dataset"], artifact_manifest["dataset"]):
            self.assertEqual(metadata["source_sha256"], file_sha256(self.output))
            self.assertEqual(metadata["priority_corrections"]["validation"], self.validation)
            self.assertEqual(metadata["derived_dataset"]["original_source_sha256"], file_sha256(self.source))


if __name__ == "__main__":
    unittest.main()
