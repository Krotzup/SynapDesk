import unittest
import os

from ml.semantic_retrieval.chunking import chunk_text
from ml.semantic_retrieval.config import MODEL_NAME, MODEL_REVISION


class WordTokenizer:
    def encode(self, text: str, *, add_special_tokens: bool) -> list[str]:
        assert not add_special_tokens
        return text.split()

    def decode(self, tokens: list[str], *, skip_special_tokens: bool) -> str:
        assert skip_special_tokens
        return " ".join(tokens)


class ChunkingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tokenizer = WordTokenizer()

    def test_long_text_preserves_tail_and_overlap(self) -> None:
        text = " ".join(f"palabra{i}" for i in range(12))
        chunks = chunk_text(text, self.tokenizer, max_tokens=5, overlap=2)
        self.assertEqual(len(chunks), 4)
        self.assertEqual(chunks[0].split()[-2:], chunks[1].split()[:2])
        self.assertEqual(chunks[-1].split()[-1], "palabra11")

    def test_empty_text_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            chunk_text(" \n ", self.tokenizer)

    def test_invalid_window_parameters_are_rejected(self):
        for maximum, overlap in ((0, 0), (5, -1), (5, 5), (5, 6)):
            with self.subTest(maximum=maximum, overlap=overlap), self.assertRaises(ValueError):
                chunk_text("red", self.tokenizer, max_tokens=maximum, overlap=overlap)

    @unittest.skipUnless(os.getenv("SYNAPDESK_RUN_SEMANTIC_MODEL_TESTS") == "1", "Requiere tokenizador real en caché; activación explícita.")
    def test_real_subwords_fit_model_and_preserve_tail(self):
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, revision=MODEL_REVISION, local_files_only=True)
        text = " ".join(["electroencefalografistas"] * 45)
        original = tokenizer.encode(text, add_special_tokens=False)
        self.assertGreater(len(original), len(text.split()))
        chunks = chunk_text(text, tokenizer)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(tokenizer.encode(chunk, add_special_tokens=True, truncation=False)), 128)
        self.assertEqual(tokenizer.encode(chunks[-1], add_special_tokens=False)[-16:], original[-16:])


if __name__ == "__main__":
    unittest.main()
