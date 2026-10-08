import unittest

from ml.semantic_retrieval.chunking import chunk_text


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


if __name__ == "__main__":
    unittest.main()
