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

-- Primero se mide búsqueda exacta; un índice vectorial requiere datos y
-- pruebas de recall y latencia representativas.
