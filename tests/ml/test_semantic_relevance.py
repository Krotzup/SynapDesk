import json
import math
from pathlib import Path
import tempfile
import unittest

from ml.semantic_retrieval.config import MODEL_ID
from ml.semantic_retrieval.relevance import (build_profile, evaluate_observations, load_cases, load_profile,
                                           query_fingerprint, validate_min_score, write_profile)


class RelevanceTests(unittest.TestCase):
    def test_ranking_distinguishes_coverage_from_correct_document(self):
        profile = self.profile([
            {"queryId": "p", "answerable": True, "score": 0.8, "topDocumentId": "wrong",
             "expectedDocumentId": "expected", "expectedDocumentRank": 3},
            {"queryId": "n", "answerable": False, "score": 0.2},
        ])
        self.assertEqual(profile["calibration"]["coveredAccepted"], 1)
        self.assertEqual(profile["ranking"]["top1Correct"], 0)
        self.assertEqual(profile["ranking"]["expectedDocumentWithinFive"], 1)
        self.assertAlmostEqual(profile["ranking"]["mrrAtFiveFragments"], 1 / 3)

    def test_evaluation_rejects_reused_queries_even_with_different_identifiers(self):
        fingerprint = query_fingerprint("  La IMPRESORA no imprime ")
        profile = self.profile([{"queryId": "old", "querySha256": fingerprint, "answerable": True, "score": 0.8},
                                {"queryId": "old-n", "answerable": False, "score": 0.2}])
        rows = [{"queryId": "new", "querySha256": query_fingerprint("La impresora no imprime"),
                 "answerable": True, "score": 0.7}]
        with self.assertRaisesRegex(ValueError, "distintas"):
            evaluate_observations(rows, profile)
        rows[0]["querySha256"] = query_fingerprint("Otra consulta")
        report = evaluate_observations(rows, profile)
        self.assertEqual(report["counts"]["coveredAccepted"], 1)
        self.assertEqual(profile["minScore"], report["minScore"])

    def profile(self, rows):
        return build_profile(rows, corpus_sha256="a" * 64, cases_sha256="b" * 64)

    def test_preserves_covered_queries_and_rejects_separated_negatives(self):
        profile = self.profile([
            {"queryId": "p1", "answerable": True, "score": 0.6},
            {"queryId": "p2", "answerable": True, "score": 0.8},
            {"queryId": "n1", "answerable": False, "score": 0.4},
            {"queryId": "n2", "answerable": False, "score": None},
        ])
        self.assertEqual(profile["minScore"], 0.5)
        self.assertEqual(profile["calibration"], {"coveredAccepted": 2, "coveredRejected": 0,
                                               "uncoveredAccepted": 0, "uncoveredRejected": 2})
        self.assertEqual(profile["modelId"], MODEL_ID)
        self.assertEqual(profile["status"], "experimental")

    def test_overlap_is_reported_without_sacrificing_covered_queries(self):
        profile = self.profile([
            {"answerable": True, "score": 0.4},
            {"answerable": False, "score": 0.2},
            {"answerable": False, "score": 0.8},
        ])
        self.assertEqual(profile["calibration"]["coveredRejected"], 0)
        self.assertEqual(profile["calibration"]["uncoveredAccepted"], 1)
        self.assertEqual(profile["calibration"]["uncoveredRejected"], 1)

    def test_tied_and_adjacent_scores_do_not_hide_false_positives(self):
        for positive, negative in ((0.5, 0.5), (math.nextafter(0.5, 1), 0.5)):
            with self.subTest(positive=positive):
                profile = self.profile([{"answerable": True, "score": positive},
                                        {"answerable": False, "score": negative}])
                self.assertEqual(profile["calibration"]["coveredAccepted"], 1)
                self.assertEqual(profile["calibration"]["uncoveredAccepted"], int(positive == negative))

    def test_invalid_scores_labels_and_missing_positive_results_are_rejected(self):
        for value in (True, "0.5", None, float("nan"), float("inf"), -1.1, 1.1, 10 ** 400):
            with self.subTest(value=str(value)), self.assertRaises(ValueError):
                validate_min_score(value)
        for rows in ([], [{"answerable": True, "score": 0.7}],
                     [{"answerable": 1, "score": 0.7}],
                     [{"answerable": True, "score": None}, {"answerable": False, "score": 0.2}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.profile(rows)

    def test_profile_roundtrip_is_bound_to_model_and_corpus_and_never_overwrites(self):
        profile = self.profile([{"answerable": True, "score": 0.7}, {"answerable": False, "score": 0.3}])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            write_profile(path, profile)
            original = path.read_bytes()
            self.assertEqual(load_profile(path), profile)
            with self.assertRaises(ValueError):
                write_profile(path, profile | {"minScore": 0.9})
            self.assertEqual(path.read_bytes(), original)
            for change in ({"modelId": "another@revision"}, {"corpusSha256": "invalid"},
                           {"minScore": float("nan")}, {"schemaVersion": True}):
                path.write_text(json.dumps(profile | change), encoding="utf-8")
                with self.subTest(change=change), self.assertRaises(ValueError):
                    load_profile(path)

    def test_cases_require_distinct_queries_and_both_coverage_labels(self):
        good = [{"queryId": "p", "query": "Tengo un problema de red", "answerable": True},
                {"queryId": "n", "query": "Información ajena al corpus", "answerable": False}]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.json"
            path.write_text(json.dumps({"queries": good}), encoding="utf-8")
            self.assertEqual(load_cases(path)[0], good)
            for rows in (good[:1], good + [good[0]], good[:1] + [good[1] | {"query": "  TENGO un problema de red "}],
                         [good[0] | {"answerable": "true"}, good[1]], [good[0] | {"query": " "}, good[1]]):
                path.write_text(json.dumps({"queries": rows}), encoding="utf-8")
                with self.subTest(rows=rows), self.assertRaises(ValueError):
                    load_cases(path)
            path.write_bytes(b"\xff")
            with self.assertRaises(ValueError):
                load_cases(path)
