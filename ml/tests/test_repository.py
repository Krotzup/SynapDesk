import unittest
from uuid import UUID

from ml.semantic_retrieval.repository import search


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


if __name__ == "__main__":
    unittest.main()
