from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from ticket_rules import find_urgent_trigger
from train_ticket_classifier import normalize_label, normalize_text, validate_columns


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_priority_labels(
    csv_path: Path, language: str
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Flag priority labels for human review without changing source data."""
    data = pd.read_csv(csv_path)
    validate_columns(data)
    requested_language = normalize_label(language)
    signal_by_priority: Counter[str] = Counter()
    priority_distribution: Counter[str] = Counter()
    candidates: list[dict[str, object]] = []
    language_rows = 0
    empty_text_rows = 0
    duplicate_exact_rows = 0
    seen_rows: set[tuple[str, str, str, str]] = set()
    priorities_by_text: dict[str, set[str]] = {}

    for index, row in data.iterrows():
        if normalize_label(row["language"]) != requested_language:
            continue
        language_rows += 1
        subject = normalize_text(row["subject"])
        body = normalize_text(row["body"])
        if not subject and not body:
            empty_text_rows += 1
            continue

        priority = normalize_label(row["priority"])
        text = f"Asunto: {subject}\nDescripcion: {body}"
        row_key = (
            text,
            normalize_label(row["type"]),
            priority,
            normalize_label(row["queue"]),
        )
        if row_key in seen_rows:
            duplicate_exact_rows += 1
        seen_rows.add(row_key)
        priorities_by_text.setdefault(text, set()).add(priority)
        priority_distribution[priority] += 1
        trigger = find_urgent_trigger(text)
        if trigger is None:
            continue
        signal_by_priority[priority] += 1
        if priority in {"low", "medium"}:
            candidates.append(
                {
                    "csv_row_number": int(index) + 2,
                    "current_priority": priority,
                    "trigger": trigger,
                }
            )

    report: dict[str, object] = {
        "input_csv_sha256": file_sha256(csv_path),
        "input_rows": int(len(data)),
        "language": requested_language,
        "language_rows": language_rows,
        "empty_text_rows": empty_text_rows,
        "duplicate_exact_rows": duplicate_exact_rows,
        "texts_with_conflicting_priority_labels": sum(
            len(priorities) > 1 for priorities in priorities_by_text.values()
        ),
        "priority_distribution": dict(sorted(priority_distribution.items())),
        "urgency_signal_rows": sum(signal_by_priority.values()),
        "urgency_signal_by_priority": dict(sorted(signal_by_priority.items())),
        "priority_review_candidates": len(candidates),
        "labels_changed": 0,
    }
    return report, candidates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audita señales de urgencia y prioridades sin modificar el CSV."
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--language", default="es")
    parser.add_argument("--output-dir", default="ml/artifacts/data_quality")
    args = parser.parse_args()

    report, candidates = audit_priority_labels(Path(args.input_csv), args.language)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data_quality.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with (output_dir / "priority_review_candidates.csv").open(
        "w", newline="", encoding="utf-8"
    ) as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=["csv_row_number", "current_priority", "trigger"],
        )
        writer.writeheader()
        writer.writerows(candidates)

    print(f"Filas candidatas a revision: {len(candidates)}")
    print(f"Informe local: {output_dir / 'data_quality.json'}")
    print(f"Lista local: {output_dir / 'priority_review_candidates.csv'}")


if __name__ == "__main__":
    main()
