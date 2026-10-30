"""Configuración reproducible del modelo candidato para el prototipo."""

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
MODEL_ID = f"{MODEL_NAME}@{MODEL_REVISION}"
EMBEDDING_DIMENSIONS = 384
CHUNK_TOKENS = 96
CHUNK_OVERLAP = 16
