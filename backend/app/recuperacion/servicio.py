"""Modelo compartido por proceso; perfiles V2 y consultas de solo lectura."""

from threading import Lock


class ErrorRecuperacion(Exception):
    def __init__(self, code: str, message: str, status: int = 503):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


class ServicioRecuperacion:
    def __init__(self, configuracion, *, embedder=None):
        from ml.semantic_retrieval.relevance import load_profile
        if (not configuracion.search_relevance_profile or not configuracion.synapdesk_semantic_database_url
                or not configuracion.search_cookie_name):
            raise ValueError("Falta configurar el perfil V2, la conexión semántica y el nombre de cookie de sesión.")
        self.profile = load_profile(configuracion.search_relevance_profile)
        if self.profile["schemaVersion"] != 2:
            raise ValueError("La API requiere recalibrar un perfil V2 con revisión del corpus.")
        self.url = configuracion.synapdesk_semantic_database_url.get_secret_value()
        self.backend_database = configuracion.postgres_db
        if embedder is None:
            from ml.semantic_retrieval.embeddings import LocalEmbedder
            embedder = LocalEmbedder()
        self.embedder = embedder
        self.lock = Lock()

    def buscar(self, query: str, limit: int) -> dict:
        from ml.semantic_retrieval.config import MODEL_ID
        from ml.semantic_retrieval.embeddings import TokenLimitExceeded
        from ml.semantic_retrieval.database import require_semantic_database
        from ml.semantic_retrieval.repository import (corpus_state, require_matching_profile, search, source_metadata,
                                                     require_schema, SemanticSchemaNotPrepared)
        try:
            with self.lock:
                vector = self.embedder.encode([query])[0]
        except TokenLimitExceeded:
            raise ErrorRecuperacion("QUERY_TOKEN_LIMIT_EXCEEDED", "La consulta supera los 128 tokens del modelo. Acórtala sin perder el problema principal.", 422) from None
        except (ValueError, RuntimeError):
            raise ErrorRecuperacion("SEARCH_UNAVAILABLE", "El modelo de búsqueda no está disponible temporalmente.") from None
        import psycopg
        from pgvector.psycopg import register_vector
        try:
            with psycopg.connect(self.url, connect_timeout=5, options="-c statement_timeout=5000") as connection:
                require_semantic_database(connection.info.dbname)
                if connection.info.dbname == self.backend_database:
                    raise ValueError("La recuperación requiere una base distinta del backend.")
                connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                require_schema(connection)
                register_vector(connection)
                state = corpus_state(connection, model_id=MODEL_ID)
                if state is None or not state["hasDocuments"]:
                    return {"status": "no_documents", "items": []}
                try:
                    require_matching_profile(connection, self.profile)
                except ValueError:
                    raise ErrorRecuperacion("SEARCH_PROFILE_STALE", "La base de conocimientos cambió; el servicio debe recalibrarse.") from None
                items = search(connection, embedding=vector, model_id=MODEL_ID, limit=limit,
                               min_score=self.profile["minScore"])
                metadata = source_metadata(connection, document_ids=list({item["documentId"] for item in items}), model_id=MODEL_ID)
                for item in items:
                    item.update({k: v for k, v in metadata.get(item["documentId"], {}).items() if v is not None})
                return {"status": "results" if items else "insufficient_information", "items": items}
        except (psycopg.errors.UndefinedTable, SemanticSchemaNotPrepared):
            raise ErrorRecuperacion("SEARCH_NOT_READY", "La base de conocimientos todavía no está preparada.") from None
        except psycopg.Error:
            raise ErrorRecuperacion("SEARCH_UNAVAILABLE", "La búsqueda no está disponible temporalmente.") from None
        except ValueError:
            raise ErrorRecuperacion("SEARCH_CONFIGURATION_ERROR", "La búsqueda requiere una configuración de base independiente.") from None
