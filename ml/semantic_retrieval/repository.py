"""Persistencia experimental en PostgreSQL + pgvector."""

from pathlib import Path
from uuid import UUID, uuid5
import hashlib
import json
import re
from urllib.parse import urlsplit

from .relevance import validate_min_score


SCHEMA = Path(__file__).with_name("schema.sql")


class SemanticSchemaNotPrepared(ValueError):
    pass


def require_schema(connection: object) -> None:
    row = connection.execute("SELECT to_regclass('semantic_prototype_chunks'), to_regtype('vector')").fetchone()
    if row is None or row[0] is None or row[1] is None:
        raise SemanticSchemaNotPrepared("El esquema semántico no está preparado; ejecuta init-db en la base semántica propia.")


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


def corpus_state(connection: object, *, model_id: str) -> dict | None:
    row = connection.execute(
        "SELECT corpus_id::text, revision, EXISTS (SELECT 1 FROM semantic_prototype_chunks WHERE model_id = %s) "
        "FROM semantic_prototype_corpus_versions WHERE model_id = %s", (model_id, model_id),
    ).fetchone()
    return {"corpusId": row[0], "revision": row[1], "hasDocuments": row[2]} if row else None


def require_matching_profile(connection: object, profile: dict) -> None:
    if profile["schemaVersion"] == 1:
        matches = corpus_fingerprint(connection, model_id=profile["modelId"]) == profile["corpusSha256"]
    else:
        current = corpus_state(connection, model_id=profile["modelId"])
        matches = (current is not None and current["corpusId"] == profile["corpusId"]
                   and current["revision"] == profile["corpusRevision"])
    if not matches:
        raise ValueError("El corpus cambió o no coincide con el perfil de relevancia; se requiere recalibrar.")


def validate_source_metadata(source_url: str | None, language: str | None) -> None:
    if source_url is not None:
        try:
            url = urlsplit(source_url)
            if (len(source_url) > 2000 or url.scheme != "https" or not url.hostname
                    or url.username is not None or url.password is not None
                    or any(char.isspace() or ord(char) < 32 for char in source_url)):
                raise ValueError
        except ValueError:
            raise ValueError("La fuente debe ser una URL HTTPS pública sin credenciales ni espacios.") from None
    if language is not None and not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", language):
        raise ValueError("El idioma debe usar un código como es, en o es-CL.")


def set_document_metadata(connection: object, *, document_id: UUID, model_id: str,
                          source_url: str | None, language: str | None) -> None:
    validate_source_metadata(source_url, language)
    connection.execute(
        "INSERT INTO semantic_prototype_document_metadata (document_id, model_id, source_url, language) "
        "VALUES (%s,%s,%s,%s) ON CONFLICT (document_id,model_id) DO UPDATE "
        "SET source_url=excluded.source_url, language=excluded.language",
        (document_id, model_id, source_url, language),
    )


def source_metadata(connection: object, *, document_ids: list[str], model_id: str) -> dict:
    if not document_ids:
        return {}
    rows = connection.execute(
        "SELECT document_id::text, source_url, language FROM semantic_prototype_document_metadata "
        "WHERE model_id=%s AND document_id=ANY(%s)", (model_id, [UUID(value) for value in document_ids]),
    ).fetchall()
    result = {}
    for document_id, url, language in rows:
        try:
            validate_source_metadata(url, language)
        except ValueError:
            continue
        result[document_id] = {"sourceUrl": url, "language": language}
    return result
