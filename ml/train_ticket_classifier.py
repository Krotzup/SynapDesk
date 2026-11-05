from __future__ import annotations

import argparse
import json
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Iterable

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import FeatureUnion, Pipeline

from dataset_io import PRIORITIES, apply_priority_corrections, file_sha256, read_dataset
from prediction_output import model_prediction
from text_preprocessing import build_text, normalize_label, normalize_text


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
    corrections_csv: str | None = None
    corrections_manifest: str | None = None
    character_ngram_targets: tuple[str, ...] = ()


def validate_columns(df: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"El CSV no contiene las columnas requeridas: {missing}")


def load_and_prepare_dataset(
    csv_path: Path,
    language: str,
    min_target_count: int,
    corrections_csv: Path | None = None,
    corrections_manifest: Path | None = None,
) -> pd.DataFrame:
    df = read_dataset(csv_path)
    validate_columns(df)
    if (corrections_csv is None) != (corrections_manifest is None):
        raise ValueError("Las correcciones requieren CSV y manifiesto juntos.")
    if corrections_csv is not None:
        df = apply_priority_corrections(df, corrections_csv, corrections_manifest)
    provenance = dict(df.attrs)

    df["language"] = df["language"].map(normalize_label)
    prepared = df[df["language"] == normalize_label(language)].copy()

    for column in ("subject", "body"):
        prepared[column] = prepared[column].map(normalize_text)
    prepared = prepared[
        (prepared["subject"].str.len() > 0) | (prepared["body"].str.len() > 0)
    ]

    prepared["text"] = [
        build_text(subject, body)
        for subject, body in zip(prepared["subject"], prepared["body"], strict=True)
    ]

    for target in TARGETS:
        prepared[target] = prepared[target].map(normalize_label)

    invalid_priorities = set(prepared["priority"]) - PRIORITIES - {""}
    if invalid_priorities:
        raise ValueError("Prioridad no admitida: el catálogo vigente es low, medium, high. Revisa el dataset.")

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

    prepared = prepared.reset_index(drop=True)
    prepared.attrs.update(provenance)
    return prepared


def build_model(
    max_features: int, ngram_range: tuple[int, int], *, random_state: int = 42,
    include_character_ngrams: bool = False,
) -> Pipeline:
    model = Pipeline(
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
                    random_state=random_state,
                ),
            ),
        ]
    )
    if include_character_ngrams:
        model.steps[0] = ("tfidf", FeatureUnion([
            ("words", model.named_steps["tfidf"]),
            ("characters", TfidfVectorizer(
                analyzer="char_wb", ngram_range=(3, 5), min_df=2,
                sublinear_tf=True, strip_accents="unicode", max_features=max_features,
            )),
        ]))
    return model


def safe_train_test_split(
    df: pd.DataFrame,
    target: str,
    test_size: float,
    random_state: int,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    if df["text"].nunique() < 2:
        raise ValueError("Se requieren al menos dos grupos de texto distintos.")
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_index, test_index = next(splitter.split(df["text"], df[target], groups=df["text"]))
    train_df, test_df = df.iloc[train_index], df.iloc[test_index]
    if train_df[target].nunique() < 2:
        raise ValueError(f"La partición de entrenamiento de {target} requiere al menos dos clases.")
    if set(train_df["text"]).intersection(test_df["text"]):
        raise ValueError("La partición comparte textos entre entrenamiento y prueba.")
    return train_df["text"], test_df["text"], train_df[target], test_df[target]


def top_prediction(model: Pipeline, text: str) -> dict[str, object]:
    return model_prediction(model, text)


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
    if config.business_rules_enabled:
        raise ValueError("La regla de urgencia fue retirada; no se pueden habilitar reglas de prioridad.")
    if (len(set(config.character_ngram_targets)) != len(config.character_ngram_targets)
            or any(target not in TARGETS for target in config.character_ngram_targets)):
        raise ValueError("Los objetivos con caracteres deben ser únicos y pertenecer a type, priority o queue.")
    csv_path = Path(config.input_csv)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_and_prepare_dataset(
        csv_path=csv_path,
        language=config.language,
        min_target_count=config.min_target_count,
        corrections_csv=Path(config.corrections_csv) if config.corrections_csv else None,
        corrections_manifest=Path(config.corrections_manifest) if config.corrections_manifest else None,
    )

    prepared_path = output_dir / "prepared_tickets.csv"
    df.to_csv(prepared_path, index=False, encoding="utf-8")

    metrics: dict[str, object] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": asdict(config),
        "rows_after_filter": int(len(df)),
        "target_distribution": target_distribution(df, TARGETS.keys()),
        "targets": TARGETS,
        "dataset": dict(df.attrs),
        "runtime": {
            "python": platform.python_version(),
            **{name: version(name) for name in (
                "pandas", "scikit-learn", "joblib", "numpy", "scipy", "threadpoolctl",
            )},
        },
        "business_rules": {
            "enabled": False,
            "urgent_priority_rule": None,
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
            random_state=config.random_state,
            include_character_ngrams=target in config.character_ngram_targets,
        )
        model.fit(x_train, y_train)

        raw_predictions = model.predict(x_test).tolist()
        predictions = raw_predictions

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
            "shared_texts": len(set(x_train).intersection(x_test)),
            "classes": [str(label) for label in model.named_steps["classifier"].classes_],
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
            "business_rule_overrides": 0,
            "business_rule_triggers": {},
        }
        models[business_name] = model

    artifact = {
        "model_name": ("synapdesk_tfidf_sgd_words_chars_ticket_classifier"
                       if config.character_ngram_targets else "synapdesk_tfidf_sgd_ticket_classifier"),
        "model_version": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "targets": TARGETS,
        "models": models,
        "config": asdict(config),
        "runtime": metrics["runtime"],
        "dataset": metrics["dataset"],
    }

    artifact_path = output_dir / "ticket_classifier.joblib"
    joblib.dump(artifact, artifact_path)
    write_json(output_dir / "artifact_manifest.json", {
        "schema_version": 1, "artifact_file": artifact_path.name,
        "artifact_sha256": file_sha256(artifact_path),
        "model_name": artifact["model_name"], "model_version": artifact["model_version"],
        "runtime": artifact["runtime"], "dataset": artifact["dataset"],
        "business_rules_enabled": config.business_rules_enabled,
        "character_ngram_targets": config.character_ngram_targets,
        "classes": {name: [str(label) for label in model.classes_] for name, model in models.items()},
    })
    write_json(output_dir / "metrics.json", metrics)

    sample_text = df.iloc[0]["text"]
    sample_prediction = {
        business_name: top_prediction(model, sample_text)
        for business_name, model in models.items()
    }
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
    parser.add_argument("--corrections-csv", help="Correcciones de prioridad revisadas, sin modificar el CSV fuente.")
    parser.add_argument("--corrections-manifest", help="Manifiesto con hashes y versión de criterios.")
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
        "--character-ngram-targets", choices=tuple(TARGETS), nargs="+", default=(),
        help="Objetivos que añaden char_wb 3–5 a las palabras; variante experimental optativa.",
    )
    rules_group = parser.add_mutually_exclusive_group()
    rules_group.add_argument(
        "--enable-business-rules",
        action="store_true",
        help=(
            "Opción retirada: su uso produce error. No hay reglas automáticas de prioridad."
        ),
    )
    rules_group.add_argument(
        "--disable-business-rules",
        action="store_true",
        help=(
            "Mantiene desactivadas las reglas deterministas de prioridad. "
            "Es el comportamiento por defecto."
        ),
    )
    args = parser.parse_args()
    if args.enable_business_rules:
        parser.error("La regla de urgencia fue retirada; --enable-business-rules ya no está disponible.")

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
        business_rules_enabled=False,
        corrections_csv=args.corrections_csv,
        corrections_manifest=args.corrections_manifest,
        character_ngram_targets=tuple(args.character_ngram_targets),
    )


if __name__ == "__main__":
    train(parse_args())
