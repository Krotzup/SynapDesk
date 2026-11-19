"""Política MVP: resolver antes de cerrar; reabrir hacia trabajo en curso."""

TRANSICIONES = {
    "open": {"in_progress", "resolved"},
    "in_progress": {"open", "resolved"},
    "resolved": {"in_progress", "closed"},
    "closed": {"in_progress"},
}


def transicion_permitida(actual: str, destino: str) -> bool:
    return actual == destino or destino in TRANSICIONES.get(actual, set())
