"""Separa consultas sintéticas por documento para calibrar y evaluar sin reutilizarlas."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from ml.semantic_retrieval.relevance import load_cases, read_json


def split(cases_path: Path, output_dir: Path) -> dict[str, int]:
    document, _ = read_json(cases_path)
    cases, _ = load_cases(cases_path)
    counts: dict[str, int] = defaultdict(int)
    negative_count = 0
    calibration, evaluation = [], []

    for case in cases:
        if case["answerable"]:
            document_id = case.get("expectedDocumentId")
            if document_id is None:
                raise ValueError("Cada consulta con cobertura necesita expectedDocumentId.")
            position = counts[document_id]
            counts[document_id] += 1
            target = calibration if position % 2 == 0 else evaluation
        else:
            target = evaluation if negative_count % 3 == 2 else calibration
            negative_count += 1
        target.append(case)

    if any(count < 2 for count in counts.values()) or negative_count < 3:
        raise ValueError("Se requieren dos consultas por documento y tres sin cobertura.")
    if output_dir.exists():
        raise ValueError("La carpeta de salida ya existe; conserva los casos anteriores.")
    output_dir.mkdir(parents=True)
    for name, rows in (("calibracion.json", calibration), ("evaluacion.json", evaluation)):
        payload = {"annotationStatus": document.get("annotationStatus"), "queries": rows}
        (output_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        load_cases(output_dir / name)
    return {"calibration": len(calibration), "evaluation": len(evaluation)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(split(args.cases, args.output_dir)))
    except (OSError, ValueError) as error:
        parser.error(str(error))
