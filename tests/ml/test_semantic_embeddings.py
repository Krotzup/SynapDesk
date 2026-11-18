import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from ml.semantic_retrieval.config import MODEL_NAME, MODEL_REVISION
from ml.semantic_retrieval.embeddings import LocalEmbedder


class SpecialTokenTokenizer:
    def encode(self, text, *, add_special_tokens, truncation):
        assert add_special_tokens and truncation is False
        return [0, *text.split(), 1]


class LocalEmbedderTests(unittest.TestCase):
    def make_embedder(self, *, dimensions=384, max_tokens=128, vectors=None):
        if vectors is None:
            vectors = np.zeros((1, 384))
            vectors[0, 0] = 1
        model = Mock(tokenizer=SpecialTokenTokenizer(), max_seq_length=max_tokens)
        model.get_sentence_embedding_dimension.return_value = dimensions
        model.encode.return_value = vectors
        constructor = Mock(return_value=model)
        with patch.dict(sys.modules, {"sentence_transformers": SimpleNamespace(SentenceTransformer=constructor)}):
            embedder = LocalEmbedder()
        constructor.assert_called_once_with(MODEL_NAME, revision=MODEL_REVISION)
        return embedder, model

    def test_model_revision_and_normalization_are_explicit(self):
        embedder, model = self.make_embedder()
        vectors = embedder.encode(["red"])
        self.assertEqual(len(vectors), 1)
        model.encode.assert_called_once_with(
            ["red"], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False,
        )

    def test_invalid_text_is_rejected_before_encoding(self):
        embedder, model = self.make_embedder()
        for texts in (None, "red", [], [None], [" "], ["red", 1]):
            with self.subTest(texts=texts), self.assertRaises(ValueError):
                embedder.encode(texts)
        model.encode.assert_not_called()

    def test_token_limit_includes_special_tokens_and_never_truncates(self):
        embedder, model = self.make_embedder()
        embedder.encode([" ".join(["red"] * 126)])
        model.encode.reset_mock()
        with self.assertRaisesRegex(ValueError, "128 tokens"):
            embedder.encode([" ".join(["red"] * 127)])
        model.encode.assert_not_called()

    def test_invalid_model_metadata_is_rejected(self):
        for arguments in ({"dimensions": 12}, {"max_tokens": 0}, {"max_tokens": None}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.make_embedder(**arguments)

    def test_invalid_vectors_are_rejected(self):
        for vectors in (np.ones((1, 12)), np.ones((2, 384)), np.zeros((1, 384)),
                        np.full((1, 384), np.nan), np.full((1, 384), np.inf), [[1.0]]):
            with self.subTest(shape=getattr(vectors, "shape", None)):
                embedder, _ = self.make_embedder(vectors=vectors)
                with self.assertRaises(ValueError):
                    embedder.encode(["red"])
