"""Compara dos entrenamientos del mismo CSV, cambiando únicamente prioridad."""

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score

from dataset_io import file_sha256
from train_ticket_classifier import (
    TrainingConfig, load_and_prepare_dataset, safe_train_test_split, train, write_json,
)


def validate_population(original: pd.DataFrame, corrected: pd.DataFrame) -> str:
    if not original.drop(columns=["priority"]).equals(corrected.drop(columns=["priority"])):
        raise ValueError("La comparación requiere idénticos registros, orden y textos; solo puede cambiar prioridad.")
    records = original.drop(columns=["priority"]).to_json(orient="records", force_ascii=False)
    return hashlib.sha256(records.encode("utf-8")).hexdigest()


def evaluate_priority(
    expected: list[str], predicted: list[str], *, labels: list[str] | None = None,
) -> dict:
    if not expected or len(expected) != len(predicted):
        raise ValueError("La evaluación requiere predicciones para todos los registros de prueba.")
    labels = labels if labels is not None else sorted(set(expected) | set(predicted))
    tp = sum(truth == "high" and guess == "high" for truth, guess in zip(expected, predicted, strict=True))
    fn = sum(truth == "high" and guess != "high" for truth, guess in zip(expected, predicted, strict=True))
    fp = sum(truth != "high" and guess == "high" for truth, guess in zip(expected, predicted, strict=True))
    return {
        "macro_f1": float(f1_score(expected, predicted, labels=labels, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(expected, predicted, labels=labels, average="weighted", zero_division=0)),
        "per_class": classification_report(expected, predicted, labels=labels, output_dict=True, zero_division=0),
        "confusion_matrix": {"labels": labels, "rows_actual_columns_predicted":
                             confusion_matrix(expected, predicted, labels=labels).tolist()},
        "high_detection": {
            "actual_high": tp + fn, "detected_high": tp, "missed_high": fn,
            "false_high": fp, "recall": tp / (tp + fn) if tp + fn else None,
        },
    }


def compare(source: Path, corrections: Path, manifest: Path, output: Path,
            random_state: int = 42, test_size: float = 0.2,
            min_target_count: int = 2, max_features: int = 120000) -> dict:
    source_hash = file_sha256(source)
    original = load_and_prepare_dataset(source, "es", min_target_count)
    corrected = load_and_prepare_dataset(source, "es", min_target_count, corrections, manifest)
    population_hash = validate_population(original, corrected)
    train_x, test_x, _, original_test = safe_train_test_split(original, "priority", test_size, random_state)
    corrected_train, corrected_test_x, _, corrected_test = safe_train_test_split(
        corrected, "priority", test_size, random_state,
    )
    if not train_x.equals(corrected_train) or not test_x.equals(corrected_test_x):
        raise ValueError("Las particiones de ambos experimentos no coinciden.")
    for name, use_corrections in (("baseline", False), ("corrected", True)):
        train(TrainingConfig(
            input_csv=str(source), output_dir=str(output / name), language="es",
            test_size=test_size, random_state=random_state, min_target_count=min_target_count,
            max_features=max_features, ngram_min=1, ngram_max=2, business_rules_enabled=False,
            corrections_csv=str(corrections) if use_corrections else None,
            corrections_manifest=str(manifest) if use_corrections else None,
        ))
    artifacts = {name: joblib.load(output / name / "ticket_classifier.joblib")
                 for name in ("baseline", "corrected")}
    for artifact in artifacts.values():
        if artifact["dataset"]["source_sha256"] != source_hash:
            raise ValueError("El artefacto no corresponde al CSV original de esta comparación.")
    guesses = {name: artifact["models"]["prioridad_estimada"].predict(test_x).tolist()
               for name, artifact in artifacts.items()}
    if file_sha256(source) != source_hash:
        raise ValueError("El CSV original cambió durante el experimento.")
    partition = {"train": train_x.index.tolist(), "test": test_x.index.tolist()}
    report = {
        "source_sha256": source_hash, "population_sha256": population_hash,
        "partition_sha256": hashlib.sha256(json.dumps(partition).encode("utf-8")).hexdigest(),
        "random_state": random_state, "test_size": test_size, "business_rules_enabled": False,
        "rows_after_filter": len(original), "train_rows": len(train_x), "test_rows": len(test_x),
        "shared_texts": len(set(train_x) & set(test_x)),
        "corrections": corrected.attrs["priority_corrections"],
        "changed_test_labels": int((original_test != corrected_test).sum()),
        "native_reference": {
            "baseline": evaluate_priority(original_test.tolist(), guesses["baseline"]),
            "corrected": evaluate_priority(corrected_test.tolist(), guesses["corrected"]),
        },
        "common_corrected_reference": {
            name: evaluate_priority(corrected_test.tolist(), prediction)
            for name, prediction in guesses.items()
        },
        "note": "La referencia común son las etiquetas revisadas de los mismos tickets de prueba; no se optimizan motivos usando predicciones.",
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "comparison.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--corrections-csv", type=Path, required=True)
    parser.add_argument("--corrections-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("ml/artifacts/priority_comparison"))
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    report = compare(args.input_csv, args.corrections_csv, args.corrections_manifest,
                     args.output_dir, args.random_state)
    print(json.dumps({"rows": report["rows_after_filter"],
                      "high_detection": {name: item["high_detection"] for name, item in
                                         report["common_corrected_reference"].items()}}))
