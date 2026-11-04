"""CLI de demostración sobre textos UTF-8 aprobados y no sensibles."""

import argparse
import json
import os
from pathlib import Path
import sys
from uuid import UUID

from .chunking import chunk_text
from .config import MAX_DOCUMENT_BYTES, MAX_QUERY_CHARACTERS, MODEL_ID
from .embeddings import LocalEmbedder
from .repository import corpus_fingerprint, init_schema, replace_document, search
from .relevance import build_profile, load_cases, load_profile, write_profile


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
    query.add_argument("--relevance-profile", type=Path,
                       help="Perfil experimental calibrado para este modelo y corpus")
    calibration = commands.add_parser("calibrate-relevance", help="Calibrar abstención conservando consultas con cobertura")
    calibration.add_argument("--cases", type=Path, required=True)
    calibration.add_argument("--output", type=Path, required=True)
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
            profile = load_profile(args.relevance_profile) if args.relevance_profile else None
            embedder = LocalEmbedder()
            vector = embedder.encode([args.query])[0]
        elif args.command == "calibrate-relevance":
            cases, cases_sha256 = load_cases(args.cases)
            if args.output.exists():
                raise ValueError("El destino del perfil ya existe; usa un archivo nuevo para preservar la calibración anterior.")
            vectors = LocalEmbedder().encode([case["query"] for case in cases])
    except ValueError as error:
        parser.error(str(error))

    import psycopg
    from pgvector.psycopg import register_vector

    try:
        with psycopg.connect(database_url, connect_timeout=5) as connection:
            if args.command == "calibrate-relevance" or (args.command == "search" and profile):
                connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
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
                elif args.command == "calibrate-relevance":
                    fingerprint = corpus_fingerprint(connection, model_id=MODEL_ID)
                    observations = []
                    for case, vector in zip(cases, vectors, strict=True):
                        items = search(connection, embedding=vector, model_id=MODEL_ID, limit=1)
                        observations.append({"queryId": case["queryId"], "answerable": case["answerable"],
                                             "score": items[0]["score"] if items else None,
                                             "topDocumentId": items[0]["documentId"] if items else None})
                    calibrated = build_profile(observations, corpus_sha256=fingerprint, cases_sha256=cases_sha256)
                    write_profile(args.output, calibrated)
                    print(json.dumps({"status": calibrated["status"], "minScore": calibrated["minScore"],
                                      "calibration": calibrated["calibration"]}, ensure_ascii=False))
                else:
                    if profile and corpus_fingerprint(connection, model_id=MODEL_ID) != profile["corpusSha256"]:
                        raise ValueError("El corpus cambió o no coincide con el perfil de relevancia; se requiere recalibrar.")
                    arguments = {"min_score": profile["minScore"]} if profile else {}
                    items = search(connection, embedding=vector, model_id=MODEL_ID, limit=args.limit, **arguments)
                    print(json.dumps({"items": items}, ensure_ascii=False, indent=2))
                    if profile and not items:
                        print("Información insuficiente: no hay fragmentos que alcancen el umbral para esta consulta.", file=sys.stderr)
    except ValueError as error:
        parser.error(str(error))
    except psycopg.OperationalError:
        parser.error("No se pudo acceder a la base de datos; verifica el servicio y la configuración de conexión.")


if __name__ == "__main__":
    main()
