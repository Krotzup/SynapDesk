"""Verificaciones optativas con modelo y PostgreSQL reales; sin datos del producto."""

import json
import math
import os
import unittest
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np

from ml.semantic_retrieval.chunking import chunk_text
from ml.semantic_retrieval.cli import read_document
from ml.semantic_retrieval.config import MODEL_ID
from ml.semantic_retrieval.embeddings import LocalEmbedder
from ml.semantic_retrieval.repository import init_schema, replace_document, search


@unittest.skipUnless(os.getenv("SYNAPDESK_RUN_SEMANTIC_MODEL_TESTS") == "1", "Requiere modelo real; activación explícita.")
class RealSemanticModelTests(unittest.TestCase):
    def test_real_vectors_and_long_query_validation(self):
        embedder = LocalEmbedder()
        vectors = embedder.encode(["No tengo conexión a la red", "La impresora no responde"])
        self.assertEqual(np.asarray(vectors).shape, (2, 384))
        self.assertTrue(np.isfinite(vectors).all())
        np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), [1, 1], atol=1e-5)
        with self.assertRaisesRegex(ValueError, "tokens"):
            embedder.encode(["red " * 130])


@unittest.skipUnless(os.getenv("SYNAPDESK_SEMANTIC_TEST_DATABASE_URL"), "Requiere PostgreSQL + pgvector de pruebas; activación explícita.")
class RealSemanticDatabaseTests(unittest.TestCase):
    def test_init_index_reindex_search_and_rollback(self):
        import psycopg
        from psycopg import sql
        from pgvector.psycopg import register_vector

        embedder = LocalEmbedder()
        examples = Path(__file__).resolve().parents[2] / "ml" / "examples"
        documents = [
            (UUID("11111111-1111-4111-8111-111111111111"), "Conectividad", "conectividad.txt"),
            (UUID("22222222-2222-4222-8222-222222222222"), "Impresora", "impresora.txt"),
        ]
        prepared = [(identifier, title, chunk_text(read_document(examples / file), embedder.tokenizer))
                    for identifier, title, file in documents]
        vectors = [embedder.encode(chunks) for _, _, chunks in prepared]
        schema = "semantic_test_" + uuid4().hex
        outputs = []
        with psycopg.connect(os.environ["SYNAPDESK_SEMANTIC_TEST_DATABASE_URL"]) as connection:
            try:
                # Todo el esquema, extensión si es nueva y datos se revierten al salir.
                connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
                connection.execute(sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema)))
                init_schema(connection)
                init_schema(connection)
                register_vector(connection)
                self.assertEqual(search(connection, embedding=vectors[0][0], model_id=MODEL_ID, limit=5), [])
                for (identifier, title, chunks), embeddings in zip(prepared, vectors, strict=True):
                    replace_document(connection, document_id=identifier, title=title, chunks=chunks,
                                     embeddings=embeddings, model_id=MODEL_ID)

                def stored():
                    return connection.execute(
                        "SELECT id, content FROM semantic_prototype_chunks WHERE model_id = %s ORDER BY id",
                        (MODEL_ID,),
                    ).fetchall()

                before = stored()
                identifier, title, chunks = prepared[0]
                replace_document(connection, document_id=identifier, title=title, chunks=chunks,
                                 embeddings=vectors[0], model_id=MODEL_ID)
                self.assertEqual(stored(), before)
                with self.assertRaises(psycopg.Error):
                    replace_document(connection, document_id=identifier, title=title,
                                     chunks=["Válido", "Dimensión incorrecta"],
                                     embeddings=[vectors[0][0], np.array([1.0])], model_id=MODEL_ID)
                self.assertEqual(stored(), before)
                replace_document(connection, document_id=identifier, title=title, chunks=chunks,
                                 embeddings=vectors[0], model_id="otro@revision")
                for query, expected in (("No puedo acceder a la red de la oficina", documents[0][0]),
                                        ("La impresora no imprime", documents[1][0])):
                    items = search(connection, embedding=embedder.encode([query])[0], model_id=MODEL_ID, limit=5)
                    self.assertEqual(len(items), len(before))
                    self.assertEqual(items[0]["documentId"], str(expected))
                    self.assertEqual([item["score"] for item in items], sorted((item["score"] for item in items), reverse=True))
                    for item in items:
                        self.assertEqual(set(item), {"documentId", "documentChunkId", "title", "excerpt", "score"})
                        UUID(item["documentChunkId"])
                        self.assertTrue(math.isfinite(item["score"]))
                        self.assertTrue(-1.00001 <= item["score"] <= 1.00001)
                    outputs.append({"query": query, "items": items})
                evidence = {
                    "executed_at": datetime.now(timezone.utc).isoformat(), "modelId": MODEL_ID,
                    "dimensions": len(vectors[0][0]), "postgresql_version": connection.info.server_version,
                    "pgvector_version": connection.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()[0],
                    "runtime": {name: version(name) for name in ("sentence-transformers", "transformers", "torch", "psycopg", "pgvector")},
                    "reindex_stable": True, "failed_insert_rolled_back": True, "model_filter_verified": True,
                    "outputs": outputs,
                }
            finally:
                connection.rollback()
        print(json.dumps({"semantic_evidence": evidence}, ensure_ascii=False))
