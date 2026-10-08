"""Fragmentación con el tokenizador del mismo modelo que genera los vectores."""

from .config import CHUNK_OVERLAP, CHUNK_TOKENS


def chunk_text(
    text: str,
    tokenizer: object,
    *,
    max_tokens: int = CHUNK_TOKENS,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    if not text or not text.strip():
        raise ValueError("El documento debe contener texto.")
    if max_tokens < 1 or not 0 <= overlap < max_tokens:
        raise ValueError("El solapamiento debe ser menor que el tamaño del fragmento.")

    token_ids = tokenizer.encode(text.strip(), add_special_tokens=False)
    if not token_ids:
        raise ValueError("El documento no produjo tokens.")

    chunks: list[str] = []
    step = max_tokens - overlap
    for start in range(0, len(token_ids), step):
        window = token_ids[start : start + max_tokens]
        chunk = tokenizer.decode(window, skip_special_tokens=True).strip()
        if chunk:
            chunks.append(chunk)
        if start + max_tokens >= len(token_ids):
            break

    if not chunks:
        raise ValueError("El documento no produjo fragmentos de texto.")
    return chunks
