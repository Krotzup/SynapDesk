"""Señales léxicas para auditar datos; no asignan ni alteran prioridades."""

from __future__ import annotations

import re

# Solo auditoría del dataset: una señal léxica no modifica la prioridad.

URGENT_PRIORITY_PATTERN = re.compile(
    r"\b(?:"
    r"urgente|urgencia|emergencia|"
    r"(?:es|est[aá]|servicio|sistema|situaci[oó]n|falla|error|problema|incidente|servidor)\s+cr[ií]tic[oa]|"
    r"inmediat(?:amente|o)|de inmediato|"
    r"alta prioridad|prioridad urgente|"
    r"ca[ií]da total|interrupci[oó]n total|servicio ca[ií]do"
    r")\b",
    re.IGNORECASE,
)

NEGATED_URGENCY_CONTEXT = re.compile(
    r"\b(?:no(?:\s+(?:es|est[aá]|se\s+considera|parece|creo\s+que\s+sea))?|sin|nada)\s+"
    r"(?:(?:un|una|el|la|de|caso|situaci[oó]n|ticket|ningun[ao]?|nada|tan|muy|para\s+nada)\s+){0,3}$",
    re.IGNORECASE,
)


def find_urgent_trigger(text: str) -> str | None:
    """Return the first non-negated strong urgency phrase in a ticket."""
    text = text or ""
    for match in URGENT_PRIORITY_PATTERN.finditer(text):
        context = text[max(0, match.start() - 80) : match.start()]
        if NEGATED_URGENCY_CONTEXT.search(context):
            continue
        return re.sub(r"\s+", " ", match.group(0)).strip().lower()
    return None
