"""Resume informes sintéticos RAG sin copiar consultas, borradores ni fragmentos."""

import argparse
import json
from math import ceil
from pathlib import Path
from statistics import median


def resumir(reports: list[dict]) -> dict:
    ids = [report["caseId"] for report in reports]
    if len(ids) != len(set(ids)):
        raise ValueError("Hay identificadores de caso duplicados.")
    positives = [report for report in reports if report["answerableExpected"]]
    negatives = [report for report in reports if not report["answerableExpected"]]
    reviewed = [report for report in reports if all(isinstance(report["humanReview"].get(field), bool)
                for field in ("evidenceSupportsEveryStep", "usefulForSpecialist", "safeToPresent"))]
    durations = sorted(report["durationMs"] for report in reports)
    return {
        "totalCases": len(reports), "positiveCases": len(positives), "negativeCases": len(negatives),
        "positiveDrafts": sum(report["outcome"] == "draft" for report in positives),
        "negativeAbstentions": sum(report["outcome"] == "insufficient_information" for report in negatives),
        "expectedDocumentCited": sum(report["expectedDocumentCited"] is True for report in positives),
        "humanReviewed": len(reviewed),
        "humanApproved": sum(all(report["humanReview"][field] for field in
                                ("evidenceSupportsEveryStep", "usefulForSpecialist", "safeToPresent"))
                             for report in reviewed),
        "observedDurationMs": ({"median": round(median(durations), 1),
                                "p95NearestRank": durations[ceil(len(durations) * 0.95) - 1]}
                               if durations else None),
        "failedCaseIds": [report["caseId"] for report in reports if not report["outcomeMatches"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("El archivo de salida ya existe; no se sobrescribirá.")
    try:
        paths = sorted(args.reports_dir.glob("*.json"))
        paths = [path for path in paths if path.name != args.output.name]
        if not paths:
            raise ValueError("No hay informes de casos.")
        summary = resumir([json.loads(path.read_text(encoding="utf-8")) for path in paths])
        with args.output.open("x", encoding="utf-8") as target:
            json.dump(summary, target, indent=2)
            target.write("\n")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        parser.exit(1, "No se pudo resumir los informes locales.\n")
    print(f"Casos: {summary['totalCases']}; revisión humana: {summary['humanReviewed']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
