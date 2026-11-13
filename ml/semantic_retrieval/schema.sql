-- Tabla experimental separada del futuro esquema definitivo de documentos.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS semantic_prototype_chunks (
    id uuid PRIMARY KEY,
    document_id uuid NOT NULL,
    position integer NOT NULL CHECK (position >= 0),
    title text NOT NULL CHECK (length(btrim(title)) > 0),
    content text NOT NULL CHECK (length(btrim(content)) > 0),
    model_id text NOT NULL,
    embedding vector(384) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, model_id, position)
);

CREATE INDEX IF NOT EXISTS semantic_prototype_document_idx
    ON semantic_prototype_chunks (document_id, model_id);

CREATE INDEX IF NOT EXISTS semantic_prototype_model_idx
    ON semantic_prototype_chunks (model_id);

-- Primero se mide búsqueda exacta; un índice vectorial requiere datos y
-- pruebas de recall y latencia representativas.

-- Identidad y revisión del corpus: la consulta HTTP lee esta fila, no todos
-- los embeddings. Los triggers incluyen escrituras SQL ajenas al indexador.
CREATE TABLE IF NOT EXISTS semantic_prototype_corpus_versions (
    model_id text PRIMARY KEY,
    corpus_id uuid NOT NULL DEFAULT gen_random_uuid(),
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0)
);

INSERT INTO semantic_prototype_corpus_versions (model_id)
SELECT DISTINCT model_id FROM semantic_prototype_chunks
ON CONFLICT (model_id) DO NOTHING;

CREATE OR REPLACE FUNCTION semantic_prototype_invalidate_corpus() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE model text;
BEGIN
    FOR model IN
        SELECT DISTINCT value FROM unnest(ARRAY[
            CASE WHEN TG_OP <> 'INSERT' THEN OLD.model_id END,
            CASE WHEN TG_OP <> 'DELETE' THEN NEW.model_id END
        ]) AS models(value) WHERE value IS NOT NULL ORDER BY value
    LOOP
        EXECUTE format(
            'INSERT INTO %I.semantic_prototype_corpus_versions (model_id, revision) VALUES ($1, 1) '
            'ON CONFLICT (model_id) DO UPDATE SET revision = semantic_prototype_corpus_versions.revision + 1',
            TG_TABLE_SCHEMA
        ) USING model;
    END LOOP;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE TRIGGER semantic_prototype_changed
AFTER INSERT OR UPDATE OR DELETE ON semantic_prototype_chunks
FOR EACH ROW EXECUTE FUNCTION semantic_prototype_invalidate_corpus();

CREATE OR REPLACE FUNCTION semantic_prototype_truncated() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE format('UPDATE %I.semantic_prototype_corpus_versions SET revision = revision + 1', TG_TABLE_SCHEMA);
    RETURN NULL;
END;
$$;

CREATE OR REPLACE TRIGGER semantic_prototype_truncated
AFTER TRUNCATE ON semantic_prototype_chunks
FOR EACH STATEMENT EXECUTE FUNCTION semantic_prototype_truncated();

CREATE TABLE IF NOT EXISTS semantic_prototype_document_metadata (
    document_id uuid NOT NULL,
    model_id text NOT NULL,
    source_url text,
    language text,
    PRIMARY KEY (document_id, model_id)
);
