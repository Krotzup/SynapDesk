import os
import unittest
from unittest.mock import patch

from ml.semantic_retrieval.database import require_semantic_database
from ml.semantic_retrieval.repository import require_matching_profile


class DatabaseSafetyTests(unittest.TestCase):
    def test_backend_databases_are_rejected(self):
        with patch.dict(os.environ, {"POSTGRES_DB": "private_dev", "POSTGRES_TEST_DB": "private_testing"}):
            for name in (None, "", "synapdesk", "synapdesk_test", "private_dev", "private_testing"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    require_semantic_database(name)
            require_semantic_database("synapdesk_semantic_test")

    def test_v2_validation_does_not_read_the_corpus_fingerprint(self):
        profile = {"schemaVersion": 2, "modelId": "model", "corpusId": "id", "corpusRevision": 7}
        with patch("ml.semantic_retrieval.repository.corpus_fingerprint") as expensive, \
             patch("ml.semantic_retrieval.repository.corpus_state", return_value={"corpusId": "id", "revision": 7}):
            require_matching_profile(None, profile)
            expensive.assert_not_called()
        with patch("ml.semantic_retrieval.repository.corpus_state", return_value={"corpusId": "id", "revision": 8}):
            with self.assertRaises(ValueError):
                require_matching_profile(None, profile)
