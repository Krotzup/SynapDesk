import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from compare_priority_corrections import evaluate_priority, validate_population
from train_ticket_classifier import safe_train_test_split


class ComparePriorityCorrectionsTest(unittest.TestCase):
    def test_high_counts_include_misses_and_false_alarms(self):
        result = evaluate_priority(["high", "high", "medium", "low"],
                                   ["high", "medium", "high", "low"])
        self.assertEqual(result["high_detection"], {
            "actual_high": 2, "detected_high": 1, "missed_high": 1,
            "false_high": 1, "recall": 0.5,
        })
        self.assertEqual(result["confusion_matrix"]["rows_actual_columns_predicted"],
                         [[1, 0, 1], [0, 1, 0], [1, 0, 0]])

    def test_population_allows_only_priority_changes(self):
        original = pd.DataFrame({"text": ["red", "correo"], "priority": ["low", "high"]})
        corrected = original.copy()
        corrected.loc[0, "priority"] = "medium"
        self.assertEqual(validate_population(original, original), validate_population(original, corrected))
        for altered in (corrected.iloc[:1], corrected.iloc[::-1], corrected.assign(text=["otro", "correo"])):
            with self.subTest(altered=altered.to_dict()), self.assertRaises(ValueError):
                validate_population(original, altered)

    def test_relabelling_does_not_change_grouped_partition(self):
        original = pd.DataFrame({"text": ["a", "a", "b", "c", "d", "e", "f", "g"],
                                 "priority": ["low", "low", "medium", "high", "low", "high", "medium", "high"]})
        corrected = original.copy()
        corrected.loc[2, "priority"] = "high"
        before = safe_train_test_split(original, "priority", 0.3, 42)
        after = safe_train_test_split(corrected, "priority", 0.3, 42)
        self.assertTrue(before[0].equals(after[0]))
        self.assertTrue(before[1].equals(after[1]))
        self.assertFalse(set(before[0]) & set(before[1]))

    def test_absent_high_is_not_reported_as_perfect_recall(self):
        self.assertIsNone(evaluate_priority(["low", "medium"], ["low", "medium"])["high_detection"]["recall"])
        with self.assertRaises(ValueError):
            evaluate_priority(["high"], [])
