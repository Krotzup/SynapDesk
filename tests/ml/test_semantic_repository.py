import unittest
from contextlib import contextmanager
from copy import deepcopy
from uuid import UUID

from ml.semantic_retrieval.repository import replace_document, search


class QueryConnection:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.statement = ""
        self.parameters: tuple[object, ...] = ()

    def execute(self, statement: str, parameters: tuple[object, ...]) -> "QueryConnection":
        self.statement = statement
        self.parameters = parameters
        return self

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


class SearchTests(unittest.TestCase):
    def test_search_keeps_source_and_model_filter(self) -> None:
        document_id = UUID("11111111-1111-4111-8111-111111111111")
        chunk_id = UUID("22222222-2222-4222-8222-222222222222")
        connection = QueryConnection([(document_id, chunk_id, "Red", "Revise IP", 0.75)])
        vector = [0.1, 0.2]

        items = search(connection, embedding=vector, model_id="model@revision", limit=5)

        self.assertEqual(connection.parameters, (vector, "model@revision", vector, 5))
        self.assertIn("WHERE model_id = %s", connection.statement)
        self.assertEqual(items, [{
            "documentId": str(document_id),
            "documentChunkId": str(chunk_id),
            "title": "Red",
            "excerpt": "Revise IP",
            "score": 0.75,
        }])

    def test_invalid_limit_is_rejected_before_query(self) -> None:
        connection = QueryConnection([])
        with self.assertRaises(ValueError):
            search(connection, embedding=[1], model_id="model@revision", limit=21)
        self.assertEqual(connection.statement, "")


class TransactionConnection:
    def __init__(self):
        self.rows = []
        self.events = []
        self.fail_insert = False

    @contextmanager
    def transaction(self):
        previous = deepcopy(self.rows)
        self.events.append("begin")
        try:
            yield
        except Exception:
            self.rows = previous
            self.events.append("rollback")
            raise
        else:
            self.events.append("commit")

    def execute(self, statement, parameters):
        self.events.append("delete")
        assert "WHERE document_id = %s AND model_id = %s" in statement
        self.rows = [row for row in self.rows if (row[1], row[5]) != parameters]

    @contextmanager
    def cursor(self):
        yield self

    def executemany(self, statement, rows):
        self.events.append("insert")
        assert "INSERT INTO semantic_prototype_chunks" in statement
        for row in rows:
            self.rows.append(row)
            if self.fail_insert:
                raise RuntimeError("Inserción interrumpida")


class ReplaceDocumentTests(unittest.TestCase):
    def setUp(self):
        self.connection = TransactionConnection()
        self.arguments = {
            "document_id": UUID("11111111-1111-4111-8111-111111111111"),
            "title": " Red ", "chunks": ["Uno", "Dos"],
            "embeddings": [[1.0], [2.0]], "model_id": "model@revision",
        }

    def test_invalid_documents_do_not_start_a_transaction(self):
        for change in ({"title": " "}, {"model_id": " "}, {"chunks": []},
                       {"chunks": [" "]}, {"embeddings": []}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace_document(self.connection, **(self.arguments | change))
        self.assertEqual(self.connection.events, [])

    def test_reindex_is_atomic_deterministic_and_scoped_to_model(self):
        replace_document(self.connection, **self.arguments)
        first_ids = [row[0] for row in self.connection.rows]
        self.assertEqual(self.connection.events, ["begin", "delete", "insert", "commit"])
        self.assertEqual([row[2] for row in self.connection.rows], [0, 1])
        self.assertTrue(all(row[3] == "Red" for row in self.connection.rows))
        replace_document(self.connection, **(self.arguments | {"chunks": ["Nuevo", "Contenido"]}))
        self.assertEqual([row[0] for row in self.connection.rows], first_ids)
        replace_document(self.connection, **(self.arguments | {"model_id": "otro@revision"}))
        self.assertEqual(len(self.connection.rows), 4)
        self.assertEqual(len({row[0] for row in self.connection.rows}), 4)
        self.assertEqual([row[0] for row in self.connection.rows[:2]], first_ids)

    def test_failed_insertion_restores_previous_chunks(self):
        replace_document(self.connection, **self.arguments)
        before = deepcopy(self.connection.rows)
        self.connection.fail_insert = True
        with self.assertRaises(RuntimeError):
            replace_document(self.connection, **(self.arguments | {"chunks": ["Nuevo", "Contenido"]}))
        self.assertEqual(self.connection.rows, before)
        self.assertEqual(self.connection.events[-1], "rollback")


if __name__ == "__main__":
    unittest.main()
