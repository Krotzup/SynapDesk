from __future__ import annotations

import re
from typing import Iterable


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
    """Force high priority for tickets with an explicit urgency signal."""
    adjusted: list[str] = []
    triggers: list[str] = []
    for text, label in zip(texts, labels, strict=True):
        trigger = find_urgent_trigger(text)
        adjusted.append("high" if trigger else label)
        triggers.append(trigger or "")
    return adjusted, triggers


def apply_priority_rule_to_prediction(
    text: str,
    prediction: dict[str, object],
) -> dict[str, object]:
    """Annotate and apply the urgency override to a prediction payload."""
    trigger = find_urgent_trigger(text)
    if trigger is None:
        prediction["decision"] = "model"
        return prediction

    original_label = prediction.get("label")
    prediction["label"] = "high"
    prediction["decision"] = (
        "model_and_business_rule" if original_label == "high" else "business_rule"
    )
    prediction["rule"] = "urgent_priority"
    prediction["trigger"] = trigger

    if "confidence" in prediction:
        prediction["model_confidence"] = prediction["confidence"]
        prediction["confidence"] = 1.0

    for key in ("top3", "top_3"):
        if key not in prediction:
            continue
        ranked = [{"label": "high", "confidence": 1.0}]
        ranked.extend(
            item for item in prediction[key] if item.get("label") != "high"
        )
        prediction[key] = ranked[:3]

    return prediction
