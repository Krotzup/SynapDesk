from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib

from prediction_output import model_prediction
from text_preprocessing import build_text
from ticket_rules import apply_priority_rule_to_prediction


def predict(
    model_path: Path,
    subject: str,
    body: str,
    business_rules: bool | None = None,
) -> dict[str, object]:
    text = build_text(subject, body)
    artifact = joblib.load(model_path)
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
        prediction = model_prediction(model, text)

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
    rules_group = parser.add_mutually_exclusive_group()
    rules_group.add_argument(
        "--enable-business-rules",
        action="store_true",
        help="Activa reglas deterministas de prioridad aprobadas funcionalmente.",
    )
    rules_group.add_argument(
        "--disable-business-rules",
        action="store_true",
        help="Desactiva reglas deterministas aunque el artefacto las tenga habilitadas.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    business_rules = None
    if args.enable_business_rules:
        business_rules = True
    if args.disable_business_rules:
        business_rules = False

    if not args.subject.strip() and not args.body.strip():
        raise SystemExit("Error de entrada: el ticket debe incluir asunto o descripcion.")

    result = predict(
        Path(args.model),
        args.subject,
        args.body,
        business_rules=business_rules,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
