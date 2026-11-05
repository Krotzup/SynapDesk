import hashlib
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec("bs4"), "Requiere ml/requirements-corpus.txt")
class ProcedureCorpusTests(unittest.TestCase):
    def test_index_catalog_rejects_external_paths_and_modified_content(self):
        from ml.tools.index_procedure_corpus import prepare_documents
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            text = folder / "body.txt"
            text.write_text("Texto de prueba.", encoding="utf-8")
            doc = {"documentId": "11111111-1111-4111-8111-111111111111", "title": "Prueba",
                   "retrievalFile": "body.txt", "retrievalSha256": hashlib.sha256(text.read_bytes()).hexdigest(),
                   "sourceUrl": "https://learn.microsoft.com/es-es/", "contentLanguage": "es",
                   "preprocessingVersion": "official_body_v1"}
            catalog = folder / "catalog.json"
            catalog.write_text(json.dumps({"documents": [doc]}), encoding="utf-8")
            self.assertEqual(len(prepare_documents(folder)), 1)
            for change in ({"retrievalFile": "../outside.txt"}, {"retrievalSha256": "0" * 64}, {"title": " "},
                           {"sourceUrl": "https://secret@site.invalid/"}):
                catalog.write_text(json.dumps({"documents": [doc | change]}), encoding="utf-8")
                with self.subTest(change=change), self.assertRaises(ValueError):
                    prepare_documents(folder)

    def test_source_change_is_rejected_and_untrusted_hosts_are_not_fetched(self):
        from ml.tools.build_procedure_corpus import read_source, validate_url
        for url in ("http://learn.microsoft.com/a", "https://127.0.0.1/a", "https://learn.microsoft.com.evil.invalid/a",
                    "https://secret@learn.microsoft.com/a", "https://learn.microsoft.com:444/a"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "snapshot.html"
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "fuente cambió"):
                read_source("https://learn.microsoft.com/example", "0" * 64, path)

    def test_html_extraction_preserves_code_and_removes_scripts(self):
        from bs4 import BeautifulSoup
        from ml.tools.html_procedures import render
        raw = '<div><h2>Prueba</h2><pre><span>ipconfig</span> /all\n</pre><script>do_not_execute()</script><p>Revisar.</p></div>'
        text = render(BeautifulSoup(raw, "html.parser").div)
        self.assertIn('```\nipconfig /all\n```', text)
        self.assertNotIn('do_not_execute', text)
