import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from evaluate_ticket_classifier import (
    CANDIDATES, EvaluationConfig, candidate_model, evaluate_models, fit_outer_model, grouped_folds,
)
from train_ticket_classifier import build_model


def synthetic_tickets():
    rows = []
    for number in range(36):
        label = ("low", "medium", "high")[number % 3]
        topic = {"low": "consulta manual", "medium": "lentitud correo", "high": "servicio caido"}[label]
        rows.append({"text": f"{topic} soporte equipo caso{number}", "priority": label,
                     "type": "incident" if label == "high" else "request", "queue": "it"})
    return pd.DataFrame(rows)


class GroupedEvaluationTest(unittest.TestCase):
    def test_duplicate_texts_never_cross_groups_and_every_record_is_tested_once(self):
        data = synthetic_tickets()
        data = pd.concat([data, data.iloc[[0]].assign(priority="high")], ignore_index=True)
        folds = grouped_folds(data, "priority", 5, 42)
        tested = []
        for training, test in folds:
            self.assertFalse(set(data.iloc[training]["text"]) & set(data.iloc[test]["text"]))
            tested.extend(test.tolist())
        self.assertEqual(sorted(tested), list(range(len(data))))
        repeated = grouped_folds(data, "priority", 5, 42)
        self.assertEqual([test.tolist() for _, test in folds], [test.tolist() for _, test in repeated])

    def test_invalid_groups_fail_without_falling_back_to_row_splits(self):
        for data, count in (
            (synthetic_tickets().iloc[:3], 5),
            (pd.DataFrame({"text": ["igual", "igual"], "priority": ["low", "high"]}), 2),
            (pd.DataFrame({"text": ["a", "b"], "priority": ["low", "high"]}), 2),
        ):
            with self.subTest(count=count), self.assertRaises(ValueError):
                grouped_folds(data, "priority", count, 42)

    def test_candidates_use_the_requested_seed_and_baseline_defaults_remain(self):
        self.assertEqual(build_model(100, (1, 2)).named_steps["classifier"].random_state, 42)
        for name in CANDIDATES:
            model = candidate_model(name, EvaluationConfig(random_state=17, max_features=100))
            self.assertEqual(model.named_steps["classifier"].random_state, 17)

    def test_models_share_partitions_and_report_full_oof_counts(self):
        data = synthetic_tickets()
        result = evaluate_models(data, EvaluationConfig(folds=3, max_features=100))
        self.assertEqual(set(result["candidates"]), set(CANDIDATES))
        expected = [len(test) for _, test in grouped_folds(data, "priority", 3, 42)]
        for candidate in result["candidates"].values():
            self.assertEqual([fold["test_rows"] for fold in candidate["folds"]], expected)
            self.assertTrue(all(fold["shared_texts"] == 0 for fold in candidate["folds"]))
            matrix = candidate["oof_metrics"]["confusion_matrix"]["rows_actual_columns_predicted"]
            self.assertEqual(sum(map(sum, matrix)), len(data))
            self.assertEqual(candidate["summary"]["macro_f1"]["valid_folds"], 3)
            self.assertGreaterEqual(candidate["summary"]["macro_f1"]["std"], 0)
        json.dumps(result, allow_nan=False)

    def test_corrected_reference_preserves_population_and_partition(self):
        original = synthetic_tickets()
        corrected = original.copy()
        corrected.loc[0, "priority"] = "high"
        config = EvaluationConfig(folds=3, max_features=100, candidates=("sgd_words",))
        before = evaluate_models(original, config, reference=corrected)
        after = evaluate_models(corrected, config, reference=corrected)
        self.assertEqual(before["partition_sha256"], after["partition_sha256"])
        self.assertEqual(before["candidates"]["sgd_words"]["oof_metrics"]["high_detection"]["actual_high"], 13)
        with self.assertRaises(ValueError):
            evaluate_models(original, config, reference=corrected.assign(text="otro"))

    def test_optional_nested_search_never_fit_on_outer_test(self):
        data = synthetic_tickets()
        config = EvaluationConfig(folds=3, inner_folds=2, max_features=100,
                                  candidates=("sgd_words",), tune_hyperparameters=True)
        fitted_groups = []
        from sklearn.pipeline import Pipeline
        actual_fit = Pipeline.fit

        def record_fit(model, texts, labels, **kwargs):
            fitted_groups.append(set(texts))
            return actual_fit(model, texts, labels, **kwargs)

        for train, test in grouped_folds(data, "priority", 3, 42):
            fitted_groups.clear()
            with patch.object(Pipeline, "fit", record_fit), patch(
                "evaluate_ticket_classifier.parameter_grid", return_value={"classifier__alpha": [1e-5, 1e-4]},
            ):
                _, params = fit_outer_model("sgd_words", data.iloc[train], config)
            self.assertIn("classifier__alpha", params)
            self.assertTrue(fitted_groups)
            for group in fitted_groups:
                self.assertTrue(group <= set(data.iloc[train]["text"]))
                self.assertFalse(group & set(data.iloc[test]["text"]))
            self.assertTrue(any(group < set(data.iloc[train]["text"]) for group in fitted_groups))

    def test_invalid_config_is_rejected(self):
        data = synthetic_tickets()
        for config in (EvaluationConfig(candidates=()), EvaluationConfig(candidates=("unknown",)),
                       EvaluationConfig(max_features=0)):
            with self.subTest(config=config), self.assertRaises(ValueError):
                evaluate_models(data, config)

    def test_cli_uses_strict_reader_and_does_not_overwrite_existing_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.csv"
            source.write_bytes(b"subject,priority\ninvalid,low,extra\n")
            report = Path(directory) / "report.json"
            args = [sys.executable, "-X", "utf8", str(ROOT / "ml/evaluate_ticket_classifier.py"),
                    "--input-csv", str(source), "--output", str(report)]
            invalid = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(invalid.returncode, 2)
            self.assertNotIn("Traceback", invalid.stderr)
            self.assertFalse(report.exists())
            report.write_text("preservado", encoding="utf-8")
            existing = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(existing.returncode, 2)
            self.assertEqual(report.read_text(encoding="utf-8"), "preservado")

    def test_cli_exits_successfully_after_writing_report_with_cp932_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            result = subprocess.run(
                [sys.executable, str(ROOT / "ml/evaluate_ticket_classifier.py"),
                 "--input-csv", str(ROOT / "ml/samples/tickets_esp_sintetico.csv"),
                 "--output", str(report), "--folds", "3", "--min-target-count", "1",
                 "--candidates", "sgd_words"],
                cwd=ROOT, env={**os.environ, "PYTHONIOENCODING": "cp932"},
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"], "experimental")


if __name__ == "__main__":
    unittest.main()
