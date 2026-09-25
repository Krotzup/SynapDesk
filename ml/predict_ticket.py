from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib

from ticket_rules import apply_priority_rule_to_prediction


def build_text(subject: str, body: str) -> str:
    return f"Asunto: {subject.strip()}\nDescripcion: {body.strip()}".strip()


def predict(
    model_path: Path,
    subject: str,
    body: str,
    business_rules: bool | None = None,
) -> dict[str, object]:
    artifact = joblib.load(model_path)
    text = build_text(subject, body)
    if business_rules is None:
        business_rules = bool(
            artifact.get("config", {}).get("business_rules_enabled", False)
        )
    response: dict[str, object] = {
        "modelName": artifact["model_name"],
        "modelVersion": artifact["model_version"],
        "businessRulesEnabled": business_rules,
        "predictions": {},
    }

    for business_name, model in artifact["models"].items():
        label = model.predict([text])[0]
        prediction: dict[str, object] = {"label": label}

        classifier = model.named_steps["classifier"]
        if hasattr(classifier, "predict_proba"):
            probabilities = model.predict_proba([text])[0]
            ranked = sorted(
                zip(classifier.classes_, probabilities, strict=True),
                key=lambda item: item[1],
                reverse=True,
            )
            prediction["confidence"] = float(ranked[0][1])
            prediction["top3"] = [
                {"label": item_label, "confidence": float(score)}
                for item_label, score in ranked[:3]
            ]

        if business_name == "prioridad_estimada" and business_rules:
            prediction = apply_priority_rule_to_prediction(text, prediction)
        else:
            prediction["decision"] = "model"
        response["predictions"][business_name] = prediction

    return response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predice atributos de un ticket.")
    parser.add_argument(
        "--model",
        default="ml/artifacts/ticket_classifier_es/ticket_classifier.joblib",
        help="Ruta del artefacto .joblib entrenado.",
    )
    parser.add_argument("--subject", required=True, help="Asunto del ticket.")
    parser.add_argument("--body", required=True, help="Descripcion del ticket.")
    parser.add_argument(
        "--disable-business-rules",
        action="store_true",
        help="Desactiva la regla que eleva urgencias explicitas a prioridad high.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = predict(
        Path(args.model),
        args.subject,
        args.body,
        business_rules=not args.disable_business_rules,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
