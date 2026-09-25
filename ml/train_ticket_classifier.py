from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from ticket_rules import (
    apply_priority_rule_to_labels,
    apply_priority_rule_to_prediction,
)


REQUIRED_COLUMNS = {
    "subject",
    "body",
    "type",
    "queue",
    "priority",
    "language",
}

TARGETS = {
    "type": "clasificacion_sugerida",
    "priority": "prioridad_estimada",
    "queue": "area_responsable",
}


@dataclass(frozen=True)
class TrainingConfig:
    input_csv: str
    output_dir: str
    language: str
    test_size: float
    random_state: int
    min_target_count: int
    max_features: int
    ngram_min: int
    ngram_max: int
    business_rules_enabled: bool


def normalize_text(value: object) -> str:
    """Clean text without translating or changing its meaning."""
    if pd.isna(value):
        return ""
    text = str(value)
    text = text.replace("\\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_label(value: object) -> str:
    label = normalize_text(value).lower()
    label = re.sub(r"\s+", "_", label)
    return label


def validate_columns(df: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"El CSV no contiene las columnas requeridas: {missing}")


def load_and_prepare_dataset(
    csv_path: Path,
    language: str,
    min_target_count: int,
) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    validate_columns(df)

    df["language"] = df["language"].map(normalize_label)
    prepared = df[df["language"] == normalize_label(language)].copy()

    for column in ("subject", "body"):
        prepared[column] = prepared[column].map(normalize_text)

    prepared["text"] = (
        "Asunto: " + prepared["subject"] + "\nDescripcion: " + prepared["body"]
    ).str.strip()

    for target in TARGETS:
        prepared[target] = prepared[target].map(normalize_label)

    prepared = prepared.dropna(subset=["text", *TARGETS.keys()])
    prepared = prepared[prepared["text"].str.len() > 0]
    for target in TARGETS:
        prepared = prepared[prepared[target].str.len() > 0]
    prepared = prepared.drop_duplicates(subset=["text", *TARGETS.keys()])

    for target in TARGETS:
        counts = prepared[target].value_counts()
        valid_labels = counts[counts >= min_target_count].index
        prepared = prepared[prepared[target].isin(valid_labels)]

    if prepared.empty:
        raise ValueError(
            "No quedaron filas entrenables. Revisa el idioma, columnas o "
            "min_target_count."
        )

    for target in TARGETS:
        if prepared[target].nunique() < 2:
            raise ValueError(
                f"El objetivo '{target}' quedo con menos de 2 clases. "
                "Reduce min_target_count o revisa el dataset."
            )

    return prepared.reset_index(drop=True)


def build_model(max_features: int, ngram_range: tuple[int, int]) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    strip_accents="unicode",
                    lowercase=True,
                    max_features=max_features,
                    ngram_range=ngram_range,
                    min_df=2,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                SGDClassifier(
                    loss="log_loss",
                    alpha=1e-5,
                    class_weight="balanced",
                    max_iter=1000,
                    tol=1e-3,
                    random_state=42,
                ),
            ),
        ]
    )


def safe_train_test_split(
    df: pd.DataFrame,
    target: str,
    test_size: float,
    random_state: int,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    class_counts = df[target].value_counts()
    stratify = df[target] if class_counts.min() >= 2 else None
    try:
        return train_test_split(
            df["text"],
            df[target],
            test_size=test_size,
            random_state=random_state,
            stratify=stratify,
        )
    except ValueError:
        return train_test_split(
            df["text"],
            df[target],
            test_size=test_size,
            random_state=random_state,
            stratify=None,
        )


def top_prediction(model: Pipeline, text: str) -> dict[str, object]:
    label = model.predict([text])[0]
    result: dict[str, object] = {"label": label}

    classifier = model.named_steps["classifier"]
    if hasattr(classifier, "predict_proba"):
        probabilities = model.predict_proba([text])[0]
        classes = classifier.classes_
        ranked = sorted(
            zip(classes, probabilities, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )
        result["confidence"] = float(ranked[0][1])
        result["top_3"] = [
            {"label": item_label, "confidence": float(score)}
            for item_label, score in ranked[:3]
        ]

    return result


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def target_distribution(df: pd.DataFrame, targets: Iterable[str]) -> dict[str, dict[str, int]]:
    return {
        target: {
            str(label): int(count)
            for label, count in df[target].value_counts().sort_index().items()
        }
        for target in targets
    }


def train(config: TrainingConfig) -> None:
    csv_path = Path(config.input_csv)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_and_prepare_dataset(
        csv_path=csv_path,
        language=config.language,
        min_target_count=config.min_target_count,
    )

    prepared_path = output_dir / "prepared_tickets.csv"
    df.to_csv(prepared_path, index=False, encoding="utf-8")

    metrics: dict[str, object] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": asdict(config),
        "rows_after_filter": int(len(df)),
        "target_distribution": target_distribution(df, TARGETS.keys()),
        "targets": TARGETS,
        "business_rules": {
            "enabled": config.business_rules_enabled,
            "urgent_priority_rule": (
                "strong Spanish urgency phrases force priority high"
            ),
        },
        "models": {},
    }

    models: dict[str, Pipeline] = {}
    for target, business_name in TARGETS.items():
        x_train, x_test, y_train, y_test = safe_train_test_split(
            df=df,
            target=target,
            test_size=config.test_size,
            random_state=config.random_state,
        )

        model = build_model(
            max_features=config.max_features,
            ngram_range=(config.ngram_min, config.ngram_max),
        )
        model.fit(x_train, y_train)

        raw_predictions = model.predict(x_test).tolist()
        predictions = raw_predictions
        rule_triggers: list[str] = []
        if target == "priority" and config.business_rules_enabled:
            predictions, rule_triggers = apply_priority_rule_to_labels(
                x_test.tolist(), raw_predictions
            )

        raw_report = classification_report(
            y_test,
            raw_predictions,
            output_dict=True,
            zero_division=0,
        )
        report = classification_report(
            y_test,
            predictions,
            output_dict=True,
            zero_division=0,
        )

        metrics["models"][business_name] = {
            "source_column": target,
            "train_rows": int(len(x_train)),
            "test_rows": int(len(x_test)),
            "macro_f1": float(f1_score(y_test, predictions, average="macro")),
            "weighted_f1": float(f1_score(y_test, predictions, average="weighted")),
            "classification_report": report,
            "model_only": {
                "macro_f1": float(
                    f1_score(y_test, raw_predictions, average="macro")
                ),
                "weighted_f1": float(
                    f1_score(y_test, raw_predictions, average="weighted")
                ),
                "classification_report": raw_report,
            },
            "business_rule_overrides": int(
                sum(bool(trigger) for trigger in rule_triggers)
            ),
            "business_rule_triggers": dict(
                Counter(trigger for trigger in rule_triggers if trigger)
            ),
        }
        models[business_name] = model

    artifact = {
        "model_name": "synapdesk_tfidf_sgd_ticket_classifier",
        "model_version": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "targets": TARGETS,
        "models": models,
        "config": asdict(config),
    }

    joblib.dump(artifact, output_dir / "ticket_classifier.joblib")
    write_json(output_dir / "metrics.json", metrics)

    sample_text = df.iloc[0]["text"]
    sample_prediction = {
        business_name: top_prediction(model, sample_text)
        for business_name, model in models.items()
    }
    if config.business_rules_enabled:
        sample_prediction["prioridad_estimada"] = apply_priority_rule_to_prediction(
            sample_text,
            sample_prediction["prioridad_estimada"],
        )
    write_json(output_dir / "sample_prediction.json", sample_prediction)

    print(f"Dataset preparado: {prepared_path}")
    print(f"Modelo guardado: {output_dir / 'ticket_classifier.joblib'}")
    print(f"Metricas guardadas: {output_dir / 'metrics.json'}")


def parse_args() -> TrainingConfig:
    parser = argparse.ArgumentParser(
        description="Prepara el CSV de tickets y entrena los modelos ML de SynapDesk."
    )
    parser.add_argument(
        "--input-csv",
        default="ml/data/raw/tickets_esp.csv",
        help="Ruta del CSV de tickets.",
    )
    parser.add_argument(
        "--output-dir",
        default="ml/artifacts/ticket_classifier_es",
        help="Carpeta local para dataset preparado, modelo y metricas.",
    )
    parser.add_argument(
        "--language",
        default="es",
        help="Valor de la columna language que se usara para entrenar.",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument(
        "--min-target-count",
        type=int,
        default=2,
        help="Minimo de filas por clase para conservar una etiqueta.",
    )
    parser.add_argument("--max-features", type=int, default=120000)
    parser.add_argument("--ngram-min", type=int, default=1)
    parser.add_argument("--ngram-max", type=int, default=2)
    parser.add_argument(
        "--disable-business-rules",
        action="store_true",
        help="No aplicar reglas deterministas de prioridad durante la evaluacion.",
    )
    args = parser.parse_args()

    return TrainingConfig(
        input_csv=args.input_csv,
        output_dir=args.output_dir,
        language=args.language,
        test_size=args.test_size,
        random_state=args.random_state,
        min_target_count=args.min_target_count,
        max_features=args.max_features,
        ngram_min=args.ngram_min,
        ngram_max=args.ngram_max,
        business_rules_enabled=not args.disable_business_rules,
    )


if __name__ == "__main__":
    train(parse_args())
