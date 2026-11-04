"""CLI de demostración sobre textos UTF-8 aprobados y no sensibles."""

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

from .chunking import chunk_text
from .config import MAX_DOCUMENT_BYTES, MAX_QUERY_CHARACTERS, MODEL_ID
from .embeddings import LocalEmbedder
from .repository import init_schema, replace_document, search


def read_document(path: Path) -> str:
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_DOCUMENT_BYTES + 1)
    except OSError:
        raise ValueError("No se pudo leer el archivo; verifica que exista y tengas permisos.") from None
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError("El archivo supera el límite experimental de 1 MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("El archivo debe estar codificado en UTF-8.") from None
    if not text.strip():
        raise ValueError("El documento debe contener texto.")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="Prototipo de búsqueda semántica")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Crear tabla experimental")
    index = commands.add_parser("index", help="Indexar un documento de texto")
    index.add_argument("--document-id", type=UUID, required=True)
    index.add_argument("--title", required=True)
    index.add_argument("--file", type=Path, required=True)
    query = commands.add_parser("search", help="Buscar fragmentos similares")
    query.add_argument("--query", required=True)
    query.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    database_url = os.getenv("SYNAPDESK_SEMANTIC_DATABASE_URL")
    if not database_url:
        parser.error("Falta SYNAPDESK_SEMANTIC_DATABASE_URL.")

    try:
        if args.command == "index":
            if not args.title.strip():
                raise ValueError("El título no puede estar vacío.")
            text = read_document(args.file)
            embedder = LocalEmbedder()
            chunks = chunk_text(text, embedder.tokenizer)
            vectors = embedder.encode(chunks)
        elif args.command == "search":
            if not args.query.strip() or len(args.query) > MAX_QUERY_CHARACTERS or not 1 <= args.limit <= 20:
                raise ValueError("La consulta debe tener 1–1000 caracteres y el límite debe estar entre 1 y 20.")
            embedder = LocalEmbedder()
            vector = embedder.encode([args.query])[0]
    except ValueError as error:
        parser.error(str(error))

    import psycopg
    from pgvector.psycopg import register_vector

    try:
        with psycopg.connect(database_url, connect_timeout=5) as connection:
            if args.command == "init-db":
                init_schema(connection)
                print("Tabla experimental preparada.")
            else:
                register_vector(connection)
                if args.command == "index":
                    replace_document(
                        connection,
                        document_id=args.document_id,
                        title=args.title,
                        chunks=chunks,
                        embeddings=vectors,
                        model_id=MODEL_ID,
                    )
                    print(f"Documento indexado: {len(chunks)} fragmentos.")
                else:
                    print(json.dumps({"items": search(
                        connection, embedding=vector, model_id=MODEL_ID, limit=args.limit
                    )}, ensure_ascii=False, indent=2))
    except psycopg.OperationalError:
        parser.error("No se pudo acceder a la base de datos; verifica el servicio y la configuración de conexión.")


if __name__ == "__main__":
    main()
