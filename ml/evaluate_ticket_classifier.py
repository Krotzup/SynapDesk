"""Experimentos locales con validación cruzada por texto; no publica un modelo."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
from statistics import mean, pstdev

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, fbeta_score, make_scorer
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from compare_priority_corrections import evaluate_priority, validate_population
from dataset_io import file_sha256
from train_ticket_classifier import TARGETS, build_model, load_and_prepare_dataset

CANDIDATES = ("sgd_words", "sgd_words_chars", "logistic_words", "linear_svc_words")


@dataclass(frozen=True)
class EvaluationConfig:
    target: str = "priority"
    folds: int = 5
    inner_folds: int = 3
    random_state: int = 42
    max_features: int = 120000
    candidates: tuple[str, ...] = CANDIDATES
    tune_hyperparameters: bool = False
    tune_high_threshold: bool = False
    high_beta: float = 2.0
    high_thresholds: tuple[float, ...] = (0.2, 0.35, 0.5, 0.65, 0.8, 1.0)


def grouped_folds(data: pd.DataFrame, target: str, count: int, seed: int) -> list:
    if type(count) is not int or count < 2 or data["text"].nunique() < count:
        raise ValueError("Se requieren al menos dos particiones y tantos grupos de texto como particiones.")
    splitter = GroupKFold(n_splits=count, shuffle=True, random_state=seed)
    folds = list(splitter.split(data["text"], data[target], groups=data["text"]))
    for train, test in folds:
        if data.iloc[train][target].nunique() < 2:
            raise ValueError("Una partición de entrenamiento tiene menos de dos clases; revisa grupos y datos.")
        if set(data.iloc[train]["text"]) & set(data.iloc[test]["text"]):
            raise ValueError("Una partición comparte textos de entrenamiento y prueba.")
    return folds


def candidate_model(name: str, config: EvaluationConfig) -> Pipeline:
    if name not in CANDIDATES:
        raise ValueError("Candidato de clasificación desconocido.")
    model = build_model(config.max_features, (1, 2), random_state=config.random_state,
                        include_character_ngrams=name == "sgd_words_chars")
    if name == "logistic_words":
        model.steps[1] = ("classifier", LogisticRegression(
            C=1.0, class_weight="balanced", max_iter=1000, random_state=config.random_state,
        ))
    elif name == "linear_svc_words":
        model.steps[1] = ("classifier", LinearSVC(
            C=1.0, class_weight="balanced", max_iter=1000, random_state=config.random_state,
        ))
    return model


def parameter_grid(name: str) -> dict:
    ngrams = "tfidf__words__ngram_range" if name == "sgd_words_chars" else "tfidf__ngram_range"
    regularization = "classifier__alpha" if name.startswith("sgd_") else "classifier__C"
    return {
        regularization: [1e-5, 1e-4] if name.startswith("sgd_") else [0.5, 1.0, 2.0],
        "classifier__class_weight": ["balanced", None],
        ngrams: [(1, 2), (1, 3)],
    }


def apply_high_threshold(predicted, probabilities, threshold: float) -> list[str]:
    probabilities = np.asarray(probabilities, dtype=float)
    if (probabilities.shape != (len(predicted),) or not np.isfinite(probabilities).all()
            or np.any((probabilities < 0) | (probabilities > 1))
            or isinstance(threshold, bool) or not np.isfinite(threshold) or not 0 <= threshold <= 1):
        raise ValueError("El umbral y las probabilidades deben ser finitos y estar entre cero y uno.")
    # Experimento de promoción: nunca rebajar una predicción high.
    return ["high" if label in {"low", "medium"} and probability >= threshold else str(label)
            for label, probability in zip(predicted, probabilities, strict=True)]


def choose_high_threshold(expected, predicted, probabilities, thresholds, beta: float) -> dict:
    if (not len(expected) or len(expected) != len(predicted)
            or set(np.asarray(expected) == "high") != {False, True}
            or isinstance(beta, bool) or not np.isfinite(beta) or beta <= 0 or not thresholds):
        raise ValueError("La selección requiere clases high/no-high, candidatos y beta positivo.")
    trials = []
    for threshold in thresholds:
        adjusted = apply_high_threshold(predicted, probabilities, threshold)
        score = fbeta_score(np.asarray(expected) == "high", np.asarray(adjusted) == "high",
                            beta=beta, zero_division=0)
        false_high = sum(truth != "high" and guess == "high"
                         for truth, guess in zip(expected, adjusted, strict=True))
        trials.append({"threshold": float(threshold), "high_fbeta": float(score), "false_high": false_high})
    selected = max(trials, key=lambda row: (row["high_fbeta"], -row["false_high"], row["threshold"]))
    return {"value": selected["threshold"], "selection_metric": "high_fbeta",
            "beta": beta, "source": "grouped_oof_outer_training_only", "trials": trials}


def high_probabilities(model: Pipeline, texts) -> np.ndarray:
    classes = list(model.classes_)
    if "high" not in classes:
        raise ValueError("No se puede ajustar un umbral: una partición de entrenamiento no contiene high.")
    return model.predict_proba(texts)[:, classes.index("high")]


def fit_outer_model(name: str, training: pd.DataFrame, config: EvaluationConfig) -> tuple:
    model = candidate_model(name, config)
    threshold_supported = config.tune_high_threshold and hasattr(model, "predict_proba")
    inner = (grouped_folds(training, config.target, config.inner_folds, config.random_state)
             if config.tune_hyperparameters or threshold_supported else [])
    selected_params = {}
    if config.tune_hyperparameters:
        scorer = make_scorer(f1_score, average="macro", zero_division=0,
                            labels=sorted(training[config.target].unique()))
        search = GridSearchCV(model, parameter_grid(name), scoring=scorer,
                              cv=inner, n_jobs=1, error_score="raise", refit=True)
        search.fit(training["text"], training[config.target])
        model, selected_params = search.best_estimator_, search.best_params_
    else:
        model.fit(training["text"], training[config.target])
    threshold = None
    if threshold_supported:
        oof_predictions = np.empty(len(training), dtype=object)
        oof_probabilities = np.empty(len(training), dtype=float)
        for train, validation in inner:
            inner_model = clone(model).fit(training.iloc[train]["text"], training.iloc[train][config.target])
            oof_predictions[validation] = inner_model.predict(training.iloc[validation]["text"])
            oof_probabilities[validation] = high_probabilities(inner_model, training.iloc[validation]["text"])
        threshold = choose_high_threshold(training[config.target].to_numpy(), oof_predictions,
                                          oof_probabilities, config.high_thresholds, config.high_beta)
    return model, selected_params, threshold


def classification_metrics(expected, predicted, labels: list[str], target: str) -> dict:
    result = evaluate_priority(list(expected), list(predicted), labels=labels)
    if target != "priority":
        result.pop("high_detection")
    return result


def summarize(folds: list[dict], target: str) -> dict:
    result = {}
    names = ["macro_f1", "weighted_f1"] + (["high_recall", "false_high"] if target == "priority" else [])
    for name in names:
        values = []
        for fold in folds:
            metrics = fold["metrics"]
            value = (metrics["high_detection"]["recall" if name == "high_recall" else "false_high"]
                     if name in {"high_recall", "false_high"} else metrics[name])
            if value is not None:
                values.append(value)
        result[name] = {"mean": mean(values) if values else None,
                        "std": pstdev(values) if values else None, "valid_folds": len(values)}
    return result


def evaluate_models(data: pd.DataFrame, config: EvaluationConfig, *, reference=None) -> dict:
    if (config.target not in TARGETS or not config.candidates or len(set(config.candidates)) != len(config.candidates)
            or any(name not in CANDIDATES for name in config.candidates)
            or type(config.max_features) is not int or config.max_features < 1
            or (config.tune_high_threshold and config.target != "priority")):
        raise ValueError("Revisa objetivo, candidatos, max_features y el uso del umbral solo para prioridad.")
    if config.tune_high_threshold and (
        isinstance(config.high_beta, bool) or not np.isfinite(config.high_beta) or config.high_beta <= 0
        or not config.high_thresholds or any(
            isinstance(value, bool) or not np.isfinite(value) or not 0 <= value <= 1
            for value in config.high_thresholds
        )
    ):
        raise ValueError("El experimento de umbral requiere beta positivo y cortes finitos entre cero y uno.")
    reference = data if reference is None else reference
    validate_population(data, reference)
    folds = grouped_folds(data, config.target, config.folds, config.random_state)
    labels = sorted(set(data[config.target]) | set(reference[config.target]))
    partitions = [{"train": train.tolist(), "test": test.tolist()} for train, test in folds]
    report = {
        "config": asdict(config), "classes": labels, "rows_after_filter": len(data),
        "groups": data["text"].nunique(), "dataset": dict(data.attrs),
        "partition_sha256": hashlib.sha256(json.dumps(partitions).encode("utf-8")).hexdigest(),
        "candidates": {},
    }
    for name in config.candidates:
        candidate_folds, threshold_folds = [], []
        oof = np.empty(len(data), dtype=object)
        adjusted_oof = np.empty(len(data), dtype=object)
        for number, (train, test) in enumerate(folds, 1):
            training, testing = data.iloc[train], data.iloc[test]
            model, params, threshold = fit_outer_model(name, training, config)
            predicted = model.predict(testing["text"])
            oof[test] = predicted
            expected = reference.iloc[test][config.target]
            fold = {
                "fold": number, "train_rows": len(train), "test_rows": len(test),
                "shared_texts": 0, "train_classes": list(model.classes_),
                "selected_params": params,
                "metrics": classification_metrics(expected, predicted, labels, config.target),
                "native_metrics": classification_metrics(testing[config.target], predicted, labels, config.target),
            }
            candidate_folds.append(fold)
            if threshold is not None:
                adjusted = apply_high_threshold(predicted, high_probabilities(model, testing["text"]), threshold["value"])
                adjusted_oof[test] = adjusted
                threshold_folds.append({"fold": number, "selection": threshold,
                                        "metrics": classification_metrics(expected, adjusted, labels, config.target)})
        result = {
            "folds": candidate_folds, "summary": summarize(candidate_folds, config.target),
            "oof_metrics": classification_metrics(reference[config.target], oof, labels, config.target),
        }
        if threshold_folds:
            result["high_threshold_experiment"] = {
                "folds": threshold_folds, "summary": summarize(threshold_folds, config.target),
                "oof_metrics": classification_metrics(reference[config.target], adjusted_oof, labels, config.target),
            }
        elif config.tune_high_threshold:
            result["high_threshold_experiment"] = {"status": "not_applicable", "reason": "El candidato no ofrece predict_proba."}
        report["candidates"][name] = result
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="JSON nuevo; no sobrescribe reportes.")
    parser.add_argument("--target", choices=tuple(TARGETS), default="priority")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--inner-folds", type=int, default=3)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--min-target-count", type=int, default=2)
    parser.add_argument("--max-features", type=int, default=120000)
    parser.add_argument("--candidates", choices=CANDIDATES, nargs="+", default=CANDIDATES)
    parser.add_argument("--tune-hyperparameters", action="store_true")
    parser.add_argument("--tune-high-threshold", action="store_true")
    parser.add_argument("--high-beta", type=float, default=2.0)
    parser.add_argument("--corrections-csv", type=Path)
    parser.add_argument("--corrections-manifest", type=Path)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("El reporte ya existe; elige una ruta nueva.")
        if bool(args.corrections_csv) != bool(args.corrections_manifest):
            raise ValueError("Las correcciones requieren CSV y manifiesto juntos.")
        if args.corrections_csv and args.target != "priority":
            raise ValueError("La comparación de correcciones evalúa únicamente prioridad.")
        source_hash = file_sha256(args.input_csv)
        original = load_and_prepare_dataset(args.input_csv, "es", args.min_target_count)
        corrected = (load_and_prepare_dataset(args.input_csv, "es", args.min_target_count,
                                              args.corrections_csv, args.corrections_manifest)
                     if args.corrections_csv else None)
        config = EvaluationConfig(
            target=args.target, folds=args.folds, inner_folds=args.inner_folds,
            random_state=args.random_state, max_features=args.max_features,
            candidates=tuple(args.candidates), tune_hyperparameters=args.tune_hyperparameters,
            tune_high_threshold=args.tune_high_threshold, high_beta=args.high_beta,
        )
        input_variant = "derived" if "derived_dataset" in original.attrs else "original"
        variants = {input_variant: evaluate_models(original, config, reference=corrected)}
        if corrected is not None:
            variants["corrected"] = evaluate_models(corrected, config, reference=corrected)
        if file_sha256(args.input_csv) != source_hash:
            raise ValueError("El CSV fuente cambió durante la evaluación; no se publica el reporte.")
        report = {
            "status": "experimental", "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reference": ("common_corrected" if corrected is not None else
                          "derived_input_labels" if input_variant == "derived" else "input_labels"),
            "business_rules_enabled": False,
            "runtime": {"python": platform.python_version(), **{name: version(name) for name in (
                "pandas", "scikit-learn", "joblib", "numpy", "scipy", "threadpoolctl")}},
            "variants": variants,
            "limitations": "Etiquetas pendientes de validación humana cuando corresponda; media/desviación no prueban significancia. No exporta ni selecciona un modelo de producción. Umbral opcional no calibrado ni aprobado.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as destination:
            destination.write(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print("Evaluación experimental terminada; reporte local creado.")


if __name__ == "__main__":
    main()
