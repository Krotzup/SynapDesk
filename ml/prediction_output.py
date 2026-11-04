"""Formato interno estable; no define ni modifica el DTO público del backend."""

PREDICTION_FIELDS = (
    "label", "confidence", "top3", "decision", "decision_source",
    "confidence_source", "model_label", "model_confidence", "rule", "trigger",
)


def model_prediction(model, text: str) -> dict[str, object]:
    label = str(model.predict([text])[0])
    result = dict.fromkeys(PREDICTION_FIELDS)
    result.update(
        label=label, top3=[], decision="model", decision_source="model",
        model_label=label,
    )
    classifier = model.named_steps["classifier"]
    if hasattr(classifier, "predict_proba"):
        ranked = sorted(
            zip(classifier.classes_, model.predict_proba([text])[0], strict=True),
            key=lambda item: item[1], reverse=True,
        )
        probabilities = {str(name): float(score) for name, score in ranked}
        result.update(
            confidence=probabilities[label], model_confidence=probabilities[label],
            confidence_source="model",
            top3=[{"label": str(name), "confidence": float(score)}
                  for name, score in ranked[:3]],
        )
    return result
