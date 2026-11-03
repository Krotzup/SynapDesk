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
        self.max_tokens = self.model.max_seq_length
        if not isinstance(self.max_tokens, int) or self.max_tokens < 1:
            raise ValueError("El modelo no declara un límite de tokens válido.")

    def encode(self, texts: list[str]) -> list[object]:
        if not isinstance(texts, list) or not texts or any(
            not isinstance(text, str) or not text.strip() for text in texts
        ):
            raise ValueError("Se requiere al menos un texto no vacío.")
        for position, text in enumerate(texts, 1):
            tokens = self.tokenizer.encode(text, add_special_tokens=True, truncation=False)
            if len(tokens) > self.max_tokens:
                raise ValueError(
                    f"El texto {position} supera el límite de {self.max_tokens} tokens "
                    "del modelo, incluidos los tokens especiales; acórtalo antes de continuar."
                )
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        if getattr(vectors, "shape", None) != (len(texts), self.dimensions):
            raise ValueError("El modelo entregó vectores con dimensiones incorrectas.")
        for vector in vectors:
            if not all(math.isfinite(float(value)) for value in vector):
                raise ValueError("El modelo entregó un vector no finito.")
            if not any(float(value) != 0 for value in vector):
                raise ValueError("El modelo entregó un vector nulo.")
        return list(vectors)
