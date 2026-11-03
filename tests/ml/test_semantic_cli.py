import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ml.semantic_retrieval import cli


class SemanticCLITests(unittest.TestCase):
    def invoke_invalid(self, arguments, expected):
        stderr = io.StringIO()
        with patch.dict(os.environ, {"SYNAPDESK_SEMANTIC_DATABASE_URL": "postgresql://unused.invalid/test"}), \
             patch("sys.argv", ["semantic", *arguments]), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as result:
                cli.main()
        self.assertEqual(result.exception.code, 2)
        self.assertIn(expected, stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_missing_file_is_controlled_before_loading_model(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(cli, "LocalEmbedder") as model:
            self.invoke_invalid([
                "index", "--document-id", "11111111-1111-4111-8111-111111111111",
                "--title", "Red", "--file", str(Path(temporary) / "missing.txt"),
            ], "No se pudo leer el archivo")
            model.assert_not_called()

    def test_document_encoding_size_and_empty_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "document.txt"
            for content, error in ((b"\xff", "UTF-8"), (b" \n ", "contener texto")):
                path.write_bytes(content)
                with self.subTest(content=content), self.assertRaisesRegex(ValueError, error):
                    cli.read_document(path)
            path.write_bytes(b"123456")
            with patch.object(cli, "MAX_DOCUMENT_BYTES", 5), self.assertRaisesRegex(ValueError, "1 MB"):
                cli.read_document(path)
            path.write_bytes(b"\xef\xbb\xbfRed")
            self.assertEqual(cli.read_document(path), "Red")

    def test_permission_error_is_controlled(self):
        with patch.object(Path, "open", side_effect=PermissionError), self.assertRaisesRegex(ValueError, "permisos"):
            cli.read_document(Path("private.txt"))

    def test_invalid_query_and_limit_do_not_load_model(self):
        with patch.object(cli, "LocalEmbedder") as model:
            for arguments in (["--query", " "], ["--query", "x" * 1001],
                              ["--query", "red", "--limit", "0"], ["--query", "red", "--limit", "21"]):
                self.invoke_invalid(["search", *arguments], "1–1000")
            model.assert_not_called()

    def test_token_overflow_is_a_controlled_cli_error(self):
        with patch.object(cli, "LocalEmbedder") as model:
            model.return_value.encode.side_effect = ValueError("El texto supera el límite de 128 tokens")
            self.invoke_invalid(["search", "--query", "red"], "128 tokens")
