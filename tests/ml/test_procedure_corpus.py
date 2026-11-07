import hashlib
import json
import importlib.util
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


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

    def test_public_snapshot_accepts_html_changes_only_with_verified_text(self):
        from ml.tools.build_procedure_corpus import build

        original = b'<main><h1>Guia</h1><div class="content"><p>Revisar.</p></div></main>'
        archived = ("Prueba\nAplicabilidad editorial: Windows\n\nGuia\n\nRevisar.\n\n"
                    "Procedencia: Ejemplo\nFuente publicada: https://learn.microsoft.com/example"
                    "\nLicencia del repositorio fuente: CC-BY-4.0; véanse catálogo y avisos adjuntos.\n")
        original_digest = hashlib.sha256(original).hexdigest()
        spec = {"id": "P01", "title": "Prueba", "applies": "Windows", "publisher": "Ejemplo",
                "licenseId": "CC-BY-4.0", "url": "https://learn.microsoft.com/example",
                "sourceSnapshot": "sources/source_01.html", "sourceSha256": original_digest,
                "expectedTextSha256": hashlib.sha256(archived.encode("utf-8")).hexdigest(),
                "documentId": "11111111-1111-4111-8111-111111111111", "queries": [],
                "contentLanguage": "es", "section": None}
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            registry = folder / "registry.json"
            registry.write_text(json.dumps({"sources": [spec], "licenses": [], "corpusId": "test",
                                            "distributionStatus": "test"}), encoding="utf-8")
            updated = b'<!-- publicacion nueva -->' + original
            output = folder / "verified"
            with patch("ml.tools.build_procedure_corpus.build_opener") as opener:
                opener.return_value.open.return_value = BytesIO(updated)
                self.assertEqual(build(registry, output)["changedHtmlSnapshots"], 1)
                self.assertEqual((output / "documents/p01.txt").read_bytes(), archived.encode("utf-8"))
                manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["sourceSnapshots"]["source_01.html"], {
                    "expectedSha256": original_digest,
                    "receivedSha256": hashlib.sha256(updated).hexdigest(),
                })
                opener.return_value.open.return_value = BytesIO(updated.replace(b"Revisar.", b"Ejecutar."))
                rejected = folder / "rejected"
                with self.assertRaisesRegex(ValueError, "texto extraído no coincide"):
                    build(registry, rejected)
                self.assertFalse(rejected.exists())
