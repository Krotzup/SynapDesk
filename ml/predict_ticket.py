from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib

if __package__:
    from .prediction_output import model_prediction
    from .text_preprocessing import build_text
else:
    from prediction_output import model_prediction
    from text_preprocessing import build_text

PRIORITIES = {"low", "medium", "high"}


class TicketClassifier:
    """Artefacto de confianza cargado una vez; nunca entrena durante inferencia."""

    def __init__(self, artifact: dict, business_rules: bool | None = None):
        if business_rules:
            raise ValueError("La regla de urgencia fue retirada; no se pueden habilitar reglas de prioridad.")
        priority_classes = set(artifact["models"]["prioridad_estimada"].classes_)
        if not priority_classes or not priority_classes <= PRIORITIES:
            raise ValueError("El artefacto contiene prioridades no admitidas; reentrena con low, medium, high.")
        if business_rules is None and artifact.get("config", {}).get("business_rules_enabled", False):
            raise ValueError("El artefacto habilita una regla retirada; reentrena o usa --disable-business-rules.")
        self.artifact = artifact

    def predict(self, subject: str, body: str) -> dict[str, object]:
        text = build_text(subject, body)
        return {
            "modelName": self.artifact["model_name"],
            "modelVersion": self.artifact["model_version"],
            "businessRulesEnabled": False,
            "predictions": {name: model_prediction(model, text)
                            for name, model in self.artifact["models"].items()},
        }


def predict(
    model_path: Path,
    subject: str,
    body: str,
    business_rules: bool | None = None,
) -> dict[str, object]:
    build_text(subject, body)
    if business_rules:
        raise ValueError("La regla de urgencia fue retirada; no se pueden habilitar reglas de prioridad.")
    return TicketClassifier(joblib.load(model_path), business_rules).predict(subject, body)


def build_parser() -> argparse.ArgumentParser:
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
        help="Opción retirada: su uso produce error; la prioridad procede del modelo.",
    )
    rules_group.add_argument(
        "--disable-business-rules",
        action="store_true",
        help="Usa solo el modelo aunque el artefacto antiguo configure reglas retiradas.",
    )
    return parser


def parse_args(parser: argparse.ArgumentParser | None = None) -> argparse.Namespace:
    parser = parser or build_parser()
    args = parser.parse_args()
    if args.enable_business_rules:
        parser.error("La regla de urgencia fue retirada; --enable-business-rules ya no está disponible.")
    return args


def main() -> None:
    parser = build_parser()
    args = parse_args(parser)
    business_rules = None
    if args.disable_business_rules:
        business_rules = False

    try:
        if not args.subject.strip() and not args.body.strip():
            raise ValueError("El ticket debe incluir asunto o descripcion.")
        result = predict(
            Path(args.model),
            args.subject,
            args.body,
            business_rules=business_rules,
        )
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
