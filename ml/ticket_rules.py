from __future__ import annotations

import re
from typing import Iterable


URGENT_PRIORITY_LABEL = "critical"

URGENT_PRIORITY_PATTERN = re.compile(
    r"\b(?:"
    r"urgente|urgencia|emergencia|"
    r"cr[ií]tic[oa]|"
    r"inmediat(?:amente|o)|de inmediato|"
    r"alta prioridad|prioridad urgente|"
    r"ca[ií]da total|interrupci[oó]n total|servicio ca[ií]do"
    r")\b",
    re.IGNORECASE,
)


def find_urgent_trigger(text: str) -> str | None:
    """Return the first strong urgency phrase found in a ticket."""
    match = URGENT_PRIORITY_PATTERN.search(text or "")
    if match is None:
        return None
    return re.sub(r"\s+", " ", match.group(0)).strip().lower()


def apply_priority_rule_to_labels(
    texts: Iterable[str],
    labels: Iterable[str],
) -> tuple[list[str], list[str]]:
    """Force critical priority for tickets with an explicit urgency signal."""
    adjusted: list[str] = []
    triggers: list[str] = []
    for text, label in zip(texts, labels, strict=True):
        trigger = find_urgent_trigger(text)
        adjusted.append(URGENT_PRIORITY_LABEL if trigger else label)
        triggers.append(trigger or "")
    return adjusted, triggers


def apply_priority_rule_to_prediction(
    text: str,
    prediction: dict[str, object],
) -> dict[str, object]:
    """Annotate and apply the urgency override to a prediction payload."""
    trigger = find_urgent_trigger(text)
    model_label = prediction.get("label")
    prediction["model_label"] = model_label
    if "confidence" in prediction:
        prediction["model_confidence"] = prediction["confidence"]
    prediction["confidence_source"] = "model"

    if trigger is None:
        prediction["decision"] = "model"
        prediction["decision_source"] = "model"
        return prediction

    prediction["label"] = URGENT_PRIORITY_LABEL
    prediction["decision"] = (
        "model_and_business_rule"
        if model_label == URGENT_PRIORITY_LABEL
        else "business_rule"
    )
    prediction["decision_source"] = "business_rule"
    prediction["rule"] = "urgent_priority"
    prediction["trigger"] = trigger
    prediction["confidence"] = None
    prediction["confidence_source"] = "not_applicable"

    return prediction
