"""Indexación local de texto oficial, separado de las atribuciones editoriales."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import UUID

from ml.semantic_retrieval.chunking import chunk_text
from ml.semantic_retrieval.cli import read_document
from ml.semantic_retrieval.config import MODEL_ID
from ml.semantic_retrieval.database import require_semantic_database
from ml.semantic_retrieval.embeddings import LocalEmbedder
from ml.semantic_retrieval.repository import init_schema, replace_document, set_document_metadata, validate_source_metadata


def prepare_documents(folder):
    catalog = json.loads((folder / "catalog.json").read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or not isinstance(catalog.get("documents"), list):
        raise ValueError("El catálogo debe contener una lista documents.")
    prepared, identifiers = [], set()
    for doc in catalog["documents"]:
        fields = ("documentId", "title", "retrievalFile", "retrievalSha256", "sourceUrl", "contentLanguage")
        if (not isinstance(doc, dict) or any(not isinstance(doc.get(field), str) for field in fields)
                or not re.fullmatch(r"[a-f0-9]{64}", doc["retrievalSha256"])
                or doc.get("preprocessingVersion") != "official_body_v1"):
            raise ValueError("Los metadatos y la versión del texto preparado deben estar completos.")
        identifier = UUID(doc["documentId"])
        path = (folder / doc["retrievalFile"]).resolve()
        if not path.is_relative_to(folder.resolve()) or identifier in identifiers:
            raise ValueError("El catálogo contiene una ruta externa o un UUID duplicado.")
        text = read_document(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != doc["retrievalSha256"]:
            raise ValueError("No coincide la huella del texto preparado para recuperación.")
        validate_source_metadata(doc["sourceUrl"], doc["contentLanguage"])
        if not doc["title"].strip():
            raise ValueError("El documento requiere un título.")
        identifiers.add(identifier)
        prepared.append((identifier, doc, text))
    if not prepared:
        raise ValueError("El catálogo no contiene documentos.")
    return prepared


def index(folder, database_url):
    import psycopg
    from pgvector.psycopg import register_vector
    prepared = prepare_documents(folder)
    # Comprobar el destino antes de cargar el modelo o generar embeddings.
    with psycopg.connect(database_url, connect_timeout=5) as connection:
        require_semantic_database(connection.info.dbname)
    model = LocalEmbedder()
    batches = [(identifier, doc, chunk_text(text, model.tokenizer)) for identifier, doc, text in prepared]
    vectors = model.encode([text for _, _, chunks in batches for text in chunks])
    offset = 0
    with psycopg.connect(database_url, connect_timeout=5) as connection:
        require_semantic_database(connection.info.dbname)
        init_schema(connection)
        register_vector(connection)
        for identifier, doc, chunks in batches:
            replace_document(connection, document_id=identifier, title=doc["title"], chunks=chunks,
                             embeddings=vectors[offset:offset + len(chunks)], model_id=MODEL_ID)
            set_document_metadata(connection, document_id=identifier, model_id=MODEL_ID,
                                  source_url=doc["sourceUrl"], language=doc["contentLanguage"])
            offset += len(chunks)
    return {"documents": len(prepared), "fragments": offset, "preprocessingVersion": "official_body_v1"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    args = parser.parse_args()
    url = os.getenv("SYNAPDESK_SEMANTIC_DATABASE_URL")
    if not url:
        parser.error("Falta SYNAPDESK_SEMANTIC_DATABASE_URL.")
    try:
        print(json.dumps(index(args.corpus, url), ensure_ascii=False))
    except (OSError, ValueError):
        parser.error("No se pudo validar o indexar el corpus; revisa rutas, huellas y configuración de base propia.")
    except Exception as error:
        import psycopg
        if isinstance(error, psycopg.Error):
            parser.error("No se pudo preparar PostgreSQL; revisa el servicio y la base semántica propia.")
        raise
