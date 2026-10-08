"""Generación local de embeddings; sin dependencia del backend o de un LLM."""

import math

from .config import EMBEDDING_DIMENSIONS, MODEL_ID, MODEL_NAME, MODEL_REVISION


class LocalEmbedder:
    model_id = MODEL_ID
    dimensions = EMBEDDING_DIMENSIONS

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION)
        self.tokenizer = self.model.tokenizer
        actual_dimensions = self.model.get_sentence_embedding_dimension()
        if actual_dimensions != self.dimensions:
            raise ValueError(
                f"Dimensión inesperada del modelo: {actual_dimensions}; "
                f"se esperaban {self.dimensions}."
            )

    def encode(self, texts: list[str]) -> list[object]:
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("Se requiere al menos un texto no vacío.")
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        if vectors.shape != (len(texts), self.dimensions):
            raise ValueError("El modelo entregó vectores con dimensiones incorrectas.")
        for vector in vectors:
            if not all(math.isfinite(float(value)) for value in vector):
                raise ValueError("El modelo entregó un vector no finito.")
            if not any(float(value) != 0 for value in vector):
                raise ValueError("El modelo entregó un vector nulo.")
        return list(vectors)
