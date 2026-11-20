"""Ingestión acotada: texto UTF-8, fragmentación y vectores en una sola transacción."""
from contextlib import contextmanager
from datetime import UTC
from uuid import uuid4

from app.recuperacion.servicio import ErrorRecuperacion

MAX_UPLOAD_BYTES = 64 * 1024
MAX_CHUNKS = 128


class IndexadorDocumentos:
    def __init__(self):
        from threading import Lock
        from ml.semantic_retrieval.embeddings import LocalEmbedder
        self.embedder, self.lock = LocalEmbedder(), Lock()


def validar_archivo(filename: str, data: bytes) -> tuple[str, str]:
    if (not filename or len(filename) > 200 or any(c in filename for c in "/\\\x00")
            or any(ord(c) < 32 for c in filename)):
        raise ErrorRecuperacion("VALIDATION_ERROR", "El nombre del archivo no es válido.", 422)
    extension = filename.lower().rsplit(".", 1)[-1]
    if "." not in filename or extension not in {"txt", "md"}:
        raise ErrorRecuperacion("DOCUMENT_FORMAT_UNSUPPORTED", "Usa un archivo .txt o .md en UTF-8.", 422)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ErrorRecuperacion("DOCUMENT_TOO_LARGE", "El archivo supera los 64 KiB.", 413)
    try:
        text = data.decode("utf-8-sig")
        if not text.strip() or any(ord(c) < 32 and c not in "\n\r\t" for c in text):
            raise ValueError
    except (UnicodeError, ValueError):
        raise ErrorRecuperacion("VALIDATION_ERROR", "El archivo debe contener texto UTF-8 válido.", 422) from None
    return text, "text/plain" if extension == "txt" else "text/markdown"


@contextmanager
def conexion_documentos(config):
    import psycopg
    from ml.semantic_retrieval.database import require_semantic_database
    if not config.documents_enabled or not config.synapdesk_semantic_database_url:
        raise ErrorRecuperacion("DOCUMENTS_UNAVAILABLE", "Los documentos todavía no están preparados.")
    try:
        with psycopg.connect(config.synapdesk_semantic_database_url.get_secret_value(),
                              connect_timeout=5, options="-c statement_timeout=10000 -c lock_timeout=3000") as db:
            require_semantic_database(db.info.dbname)
            if db.info.dbname == config.postgres_db:
                raise ValueError
            yield db
    except psycopg.errors.UndefinedTable:
        raise ErrorRecuperacion("DOCUMENTS_NOT_READY", "Prepara el esquema de documentos en la base semántica.") from None
    except (psycopg.Error, ValueError):
        raise ErrorRecuperacion("DOCUMENTS_UNAVAILABLE", "No se pudo completar la operación de documentos.") from None


def representar(row):
    identifier, title, description, filename, content_type, author, created, updated = row
    return {"id": str(identifier), "title": title, "description": description,
            "originalFilename": filename, "contentType": content_type, "uploadedBy": author,
            "processingStatus": "processed", "createdAt": created.astimezone(UTC).isoformat(),
            "updatedAt": updated.astimezone(UTC).isoformat()}


COLUMNAS = "id, title, description, original_filename, content_type, uploaded_by, created_at, updated_at"


def ingresar(config, recuperacion, *, title, description, filename, data, author):
    text, content_type = validar_archivo(filename, data)
    if recuperacion is None:
        raise ErrorRecuperacion("DOCUMENTS_UNAVAILABLE", "El indexador no está preparado.")
    from ml.semantic_retrieval.chunking import chunk_text
    from ml.semantic_retrieval.config import MODEL_ID
    from ml.semantic_retrieval.repository import replace_document, require_schema
    from pgvector.psycopg import register_vector
    from psycopg.types.json import Jsonb
    try:
        # Compartido con búsquedas: evita usar concurrentemente el mismo modelo.
        with recuperacion.lock:
            chunks = chunk_text(text, recuperacion.embedder.tokenizer)
            if len(chunks) > MAX_CHUNKS:
                raise ErrorRecuperacion("DOCUMENT_TOO_LARGE", "El texto supera los 128 fragmentos permitidos.", 413)
            embeddings = recuperacion.embedder.encode(chunks)
    except (ValueError, RuntimeError):
        raise ErrorRecuperacion("DOCUMENT_INDEXING_FAILED", "No se pudo indexar el texto; no se guardó el documento.") from None
    identifier = uuid4()
    with conexion_documentos(config) as db:
        require_schema(db)
        register_vector(db)
        # La conexión ya inicia la transacción al comprobar el esquema. El savepoint
        # de replace_document y la ficha confirman o revierten juntos al salir.
        replace_document(db, document_id=identifier, title=title, chunks=chunks,
                         embeddings=embeddings, model_id=MODEL_ID)
        row = db.execute(f"INSERT INTO semantic_uploaded_documents "
            "(id,title,description,original_filename,content_type,uploaded_by,content) "
            f"VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING {COLUMNAS}",
            (identifier, title, description, filename, content_type, Jsonb(author), text)).fetchone()
        return representar(row)
