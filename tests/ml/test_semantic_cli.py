import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

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

    def test_connection_failure_is_controlled_without_leaking_details(self):
        private_details = "postgresql://private_user:private_password@private_host/private_database"
        operational_error = type("OperationalError", (Exception,), {})
        connect = Mock(side_effect=operational_error(private_details))
        modules = {"psycopg": SimpleNamespace(connect=connect, OperationalError=operational_error),
                   "pgvector": SimpleNamespace(), "pgvector.psycopg": SimpleNamespace(register_vector=Mock())}
        stderr = io.StringIO()
        with patch.dict(os.environ, {"SYNAPDESK_SEMANTIC_DATABASE_URL": private_details}), \
             patch("sys.argv", ["semantic", "init-db"]), \
             patch.dict("sys.modules", modules), \
             contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as result:
                cli.main()
        self.assertEqual(result.exception.code, 2)
        self.assertIn("No se pudo acceder a la base de datos", stderr.getvalue())
        for value in ("Traceback", private_details, "private_password", "private_host"):
            self.assertNotIn(value, stderr.getvalue())
        connect.assert_called_once_with(private_details, connect_timeout=5)

    def test_statement_failure_is_not_reported_as_connection_failure(self):
        operational_error = type("OperationalError", (Exception,), {})
        statement_error = type("ProgrammingError", (Exception,), {})
        modules = {"psycopg": SimpleNamespace(connect=MagicMock(), OperationalError=operational_error),
                   "pgvector": SimpleNamespace(), "pgvector.psycopg": SimpleNamespace(register_vector=Mock())}
        with patch.dict(os.environ, {"SYNAPDESK_SEMANTIC_DATABASE_URL": "postgresql://unused.invalid/test"}), \
             patch("sys.argv", ["semantic", "init-db"]), patch.dict("sys.modules", modules), \
             patch.object(cli, "init_schema", side_effect=statement_error("invalid SQL")):
            with self.assertRaises(statement_error):
                cli.main()

    def test_missing_profile_is_rejected_before_loading_model(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(cli, "LocalEmbedder") as model:
            self.invoke_invalid(["search", "--query", "red", "--relevance-profile",
                                 str(Path(temporary) / "missing.json")], "JSON UTF-8 válido")
            model.assert_not_called()

    def test_profile_can_abstain_without_changing_stdout_contract(self):
        connection = MagicMock()
        connect = MagicMock()
        connect.return_value.__enter__.return_value = connection
        modules = {"psycopg": SimpleNamespace(connect=connect, OperationalError=type("OperationalError", (Exception,), {})),
                   "pgvector": SimpleNamespace(), "pgvector.psycopg": SimpleNamespace(register_vector=Mock())}
        profile = {"minScore": 0.5, "corpusSha256": "a" * 64}
        output, errors = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"SYNAPDESK_SEMANTIC_DATABASE_URL": "postgresql://unused.invalid/test"}), \
             patch("sys.argv", ["semantic", "search", "--query", "red", "--relevance-profile", "profile.json"]), \
             patch.dict("sys.modules", modules), patch.object(cli, "load_profile", return_value=profile), \
             patch.object(cli, "corpus_fingerprint", return_value="a" * 64), \
             patch.object(cli, "LocalEmbedder") as model, patch.object(cli, "search", return_value=[]) as search, \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            model.return_value.encode.return_value = [[1.0]]
            cli.main()
        self.assertEqual(json.loads(output.getvalue()), {"items": []})
        self.assertIn("Información insuficiente", errors.getvalue())
        self.assertEqual(search.call_args.kwargs["min_score"], 0.5)

    def test_changed_corpus_rejects_profile_without_unfiltered_fallback(self):
        connect = MagicMock()
        modules = {"psycopg": SimpleNamespace(connect=connect, OperationalError=type("OperationalError", (Exception,), {})),
                   "pgvector": SimpleNamespace(), "pgvector.psycopg": SimpleNamespace(register_vector=Mock())}
        with patch.dict("sys.modules", modules), patch.object(cli, "LocalEmbedder") as model, \
             patch.object(cli, "load_profile", return_value={"minScore": 0.5, "corpusSha256": "a" * 64}), \
             patch.object(cli, "corpus_fingerprint", return_value="b" * 64), patch.object(cli, "search") as search:
            model.return_value.encode.return_value = [[1.0]]
            self.invoke_invalid(["search", "--query", "red", "--relevance-profile", "profile.json"], "corpus cambió")
            search.assert_not_called()
