"""Separación explícita entre recuperación experimental y datos del backend."""

import os


def require_semantic_database(name: object) -> None:
    forbidden = {"synapdesk", "synapdesk_test"}
    forbidden.update(os.environ[key] for key in ("POSTGRES_DB", "POSTGRES_TEST_DB") if os.environ.get(key))
    if not isinstance(name, str) or not name.strip() or name in forbidden:
        raise ValueError("La recuperación requiere una base propia; no se permite la base del backend ni synapdesk_test.")
