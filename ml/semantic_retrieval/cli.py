"""CLI de demostración sobre textos UTF-8 aprobados y no sensibles."""

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

from .chunking import chunk_text
from .config import MODEL_ID
from .embeddings import LocalEmbedder
from .repository import init_schema, replace_document, search


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

    if args.command == "index":
        if not args.title.strip():
            parser.error("El título no puede estar vacío.")
        if args.file.stat().st_size > 1_000_000:
            parser.error("El archivo supera el límite experimental de 1 MB.")
        text = args.file.read_text(encoding="utf-8")
        embedder = LocalEmbedder()
        chunks = chunk_text(text, embedder.tokenizer)
        vectors = embedder.encode(chunks)
    elif args.command == "search":
        if not args.query.strip() or len(args.query) > 1000 or not 1 <= args.limit <= 20:
            parser.error("La consulta debe tener 1–1000 caracteres y el límite debe estar entre 1 y 20.")
        embedder = LocalEmbedder()
        vector = embedder.encode([args.query])[0]

    import psycopg
    from pgvector.psycopg import register_vector

    with psycopg.connect(database_url) as connection:
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


if __name__ == "__main__":
    main()
