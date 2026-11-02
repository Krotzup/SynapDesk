"""Preparación textual compartida por entrenamiento, auditoría e inferencia."""

import re

import pandas as pd


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\\n", " ")).strip()


def normalize_label(value: object) -> str:
    return re.sub(r"\s+", "_", normalize_text(value).lower())


def build_text(subject: str, body: str) -> str:
    if not isinstance(subject, str) or not isinstance(body, str):
        raise ValueError("El asunto y la descripción deben ser textos.")
    subject, body = normalize_text(subject), normalize_text(body)
    if not subject and not body:
        raise ValueError("El ticket debe incluir asunto o descripcion.")
    return f"Asunto: {subject}\nDescripcion: {body}"
