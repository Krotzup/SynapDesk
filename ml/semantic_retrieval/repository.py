"""Persistencia experimental en PostgreSQL + pgvector."""

from pathlib import Path
from uuid import UUID, uuid5
import hashlib
import json

from .relevance import validate_min_score


SCHEMA = Path(__file__).with_name("schema.sql")


def init_schema(connection: object) -> None:
    connection.execute(SCHEMA.read_text(encoding="utf-8"))


def replace_document(
    connection: object,
    *,
    document_id: UUID,
    title: str,
    chunks: list[str],
    embeddings: list[object],
    model_id: str,
) -> None:
    if (
        not title.strip() or not model_id.strip() or not chunks
        or any(not content.strip() for content in chunks)
        or len(chunks) != len(embeddings)
    ):
        raise ValueError("Título, fragmentos y vectores deben estar completos.")
    rows = [
        (
            uuid5(document_id, f"{model_id}:{position}"),
            document_id,
            position,
            title.strip(),
            content,
            model_id,
            embedding,
        )
        for position, (content, embedding) in enumerate(zip(chunks, embeddings))
    ]
    with connection.transaction():
        connection.execute(
            "DELETE FROM semantic_prototype_chunks "
            "WHERE document_id = %s AND model_id = %s",
            (document_id, model_id),
        )
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO semantic_prototype_chunks "
                "(id, document_id, position, title, content, model_id, embedding) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                rows,
            )


def search(
    connection: object, *, embedding: object, model_id: str, limit: int,
    min_score: float | None = None,
) -> list[dict[str, object]]:
    if not 1 <= limit <= 20:
        raise ValueError("El límite debe estar entre 1 y 20.")
    score_filter = ""
    parameters = [embedding, model_id]
    if min_score is not None:
        minimum = validate_min_score(min_score)
        score_filter = " AND 1 - (embedding <=> %s) >= %s"
        parameters.extend((embedding, minimum))
    parameters.extend((embedding, limit))
    rows = connection.execute(
        "SELECT document_id, id, title, content, "
        "1 - (embedding <=> %s) AS score "
        "FROM semantic_prototype_chunks WHERE model_id = %s"
        + score_filter + " "
        "ORDER BY embedding <=> %s, document_id, position LIMIT %s",
        tuple(parameters),
    ).fetchall()
    return [
        {
            "documentId": str(document_id),
            "documentChunkId": str(chunk_id),
            "title": title,
            "excerpt": content,
            "score": float(score),
        }
        for document_id, chunk_id, title, content, score in rows
    ]


def corpus_fingerprint(connection: object, *, model_id: str) -> str:
    """Identifica los fragmentos y vectores del modelo dentro del search_path actual."""
    digest = hashlib.sha256()
    digest.update(json.dumps(model_id).encode("utf-8"))
    rows = connection.execute(
        "SELECT id::text, document_id::text, position, title, content, embedding::text "
        "FROM semantic_prototype_chunks WHERE model_id = %s ORDER BY id",
        (model_id,),
    )
    for row in rows:
        digest.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()
