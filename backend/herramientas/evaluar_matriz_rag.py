"""Matriz EA3 2.4: evalúa registros locales sin llamar a modelos ni inventar juicios."""
import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from statistics import mean

CASOS = {f"RAG-{i:03}" for i in range(1, 6)}
RAIZ = Path(__file__).resolve().parents[2]


def exigir(condition, message="Registro de evaluación incompleto o inválido."):
    if not condition:
        raise ValueError(message)


def texto(value):
    return isinstance(value, str) and bool(value.strip())


def evaluar_registro(record):
    exigir(isinstance(record, dict) and record.get("caseId") in CASOS)
    fecha = datetime.fromisoformat(record["evaluatedAt"].replace("Z", "+00:00"))
    exigir(fecha.tzinfo is not None and fecha.utcoffset() is not None)
    exigir(isinstance(record["commit"], str) and re.fullmatch(r"[0-9a-f]{40}", record["commit"]))
    docs = record["indexedDocumentIds"]
    exigir(isinstance(docs, list) and all(texto(d) for d in docs) and len(docs) == len(set(docs)))
    exigir(texto(record["query"]) and texto(record["models"]["retrieval"]) and texto(record["models"]["generation"]))
    exigir(record["executionKind"] in {"live", "fixture"})
    exigir(record["dataKind"] in {"synthetic", "anonymized_real"})
    exigir(record["annotationStatus"] in {"pending", "reviewed_independently"})
    k, results = record["topK"], record["results"]
    exigir(type(k) is int and 1 <= k <= 20 and isinstance(results, list) and len(results) <= k)
    seen = set()
    for result in results:
        exigir(texto(result["chunkId"]) and result["chunkId"] not in seen)
        seen.add(result["chunkId"])
        exigir(result["documentId"] in docs)
        score = result["score"]
        exigir(type(score) in {int, float} and math.isfinite(score) and -1 <= score <= 1)
        exigir(result["relevant"] is None or type(result["relevant"]) is bool)
        if result["relevant"] is not None:
            exigir(texto(result["judgedBy"]))
    truth = record["groundTruth"]
    relevant_docs = truth["relevantDocumentIds"]
    exigir(isinstance(relevant_docs, list) and all(d in docs for d in relevant_docs)
           and len(relevant_docs) == len(set(relevant_docs)) and type(truth["complete"]) is bool)
    expected = truth["expectedDocumentId"]
    exigir(expected is None or expected in relevant_docs)
    rag = record["rag"]
    exigir(rag["outcome"] in {"draft", "fallback"} and texto(rag["content"]))
    exigir(isinstance(rag["sourceChunkIds"], list) and all(texto(x) for x in rag["sourceChunkIds"]))
    exigir(len(rag["sourceChunkIds"]) == len(set(rag["sourceChunkIds"])))
    for field in ("sourcesVisible", "fallbackAppropriate"):
        exigir(rag[field] is None or type(rag[field]) is bool)
    exigir(isinstance(rag["citations"], list))
    for citation in rag["citations"]:
        exigir(texto(citation["chunkId"]))
        exigir(citation["supportsClaim"] is None or type(citation["supportsClaim"]) is bool)
        if citation["supportsClaim"] is not None:
            exigir(texto(citation["reviewedBy"]))
    exigir(isinstance(record["humanReviews"], list) and isinstance(record["observations"], str))
    reviewers = set()
    for review in record["humanReviews"]:
        exigir(texto(review["reviewer"]) and review["reviewer"] not in reviewers)
        reviewers.add(review["reviewer"])
        exigir(type(review["rating"]) in {int, float} and math.isfinite(review["rating"]) and review["rating"] >= 0)
    known = lambda n: k >= n and all(r["relevant"] is not None for r in results[:n])
    precision = lambda n: sum(r["relevant"] is True for r in results[:n]) / n if known(n) else None
    first = next((i for i, r in enumerate(results, 1) if r["relevant"] is True), None)
    # Si hay un juicio pendiente antes del primer acierto, no se conoce su rango real.
    rr_known = all(r["relevant"] is not None for r in results[:first])
    rr = (1 / first if first else 0) if rr_known else None
    recall = (len(set(r["documentId"] for r in results[:5]) & set(relevant_docs)) / len(relevant_docs)
              if k >= 5 and truth["complete"] and relevant_docs else None)
    scores = [r["score"] for r in results if r["relevant"] is True]
    citations = rag["citations"]
    traceable = [c["chunkId"] in seen and c["chunkId"] in rag["sourceChunkIds"] for c in citations]
    citation_accuracy = (sum(ok and c["supportsClaim"] is True for ok, c in zip(traceable, citations)) / len(citations)
        if citations and all(c["supportsClaim"] is not None for c in citations) else None)
    rating = mean(r["rating"] for r in record["humanReviews"]) if record["humanReviews"] else None
    fallback = (rag["outcome"] == "fallback" and rag["fallbackAppropriate"] is True and not citations and not rag["sourceChunkIds"]
                if rag["fallbackAppropriate"] is not None else None)
    case = record["caseId"]
    if case == "RAG-001":
        criterion = precision(3) >= 1 / 3 if precision(3) is not None else None
    elif case == "RAG-002":
        criterion = rr >= 1 / 3 if rr is not None and k >= 3 else None
    elif case == "RAG-003":
        criterion = expected in {r["documentId"] for r in results[:5]} if expected and k >= 5 else None
    elif case == "RAG-004":
        criterion = fallback if rag["outcome"] == "fallback" else False
    else:
        criterion = rating >= 4 if rating is not None else None
    pending = []
    if record["executionKind"] != "live": pending.append("ejecucion_con_fixture")
    if record["annotationStatus"] != "reviewed_independently": pending.append("etiquetas_sin_revision_independiente")
    if criterion is None: pending.append("criterio_sin_evidencia")
    if case == "RAG-003" and recall is None: pending.append("recall_sin_ground_truth_completo")
    sources_ok = True if case == "RAG-004" else (
        False if any(source not in seen for source in rag["sourceChunkIds"]) else rag["sourcesVisible"])
    citations_ok = True if case == "RAG-004" else (
        False if any(not ok for ok in traceable) else citation_accuracy == 1 if citation_accuracy is not None else None)
    if sources_ok is None: pending.append("visibilidad_sin_revisar")
    if citations_ok is None: pending.append("citas_sin_revisar")
    passed = criterion is True and sources_ok is True and citations_ok is True and rag["outcome"] == ("fallback" if case == "RAG-004" else "draft")
    failed = criterion is False or sources_ok is False or citations_ok is False or rag["outcome"] != ("fallback" if case == "RAG-004" else "draft")
    return {"caseId": case, "criterionMet": criterion,
        "verdict": "no_apto" if failed else "pendiente" if pending else "apto" if passed else "pendiente",
        "pendingReasons": pending, "metrics": {"precisionAt3": precision(3), "precisionAt5": precision(5),
            "recallAt5": recall, "reciprocalRank": rr,
            "meanRelevantScore": mean(scores) if scores and all(r["relevant"] is not None for r in results) else None,
            "fallbackCorrect": fallback if case == "RAG-004" else None,
            "citationAccuracy": citation_accuracy, "citationTraceability": sum(traceable) / len(traceable) if traceable else None,
            "meanHumanRelevance": rating}, "record": record}


def evaluar(records):
    exigir(isinstance(records, list) and records)
    cases = [evaluar_registro(r) for r in records]
    exigir(len({r["caseId"] for r in cases}) == len(cases), "No repetir casos en una misma evaluación.")
    missing = sorted(CASOS - {r["caseId"] for r in cases})
    fallback_cases = [r["metrics"]["fallbackCorrect"] for r in cases if r["caseId"] == "RAG-004"]
    retrieval = [r for r in cases if r["caseId"] != "RAG-004"]
    ranks = [r["metrics"]["reciprocalRank"] for r in retrieval]
    return {"matrixReference": "Gestión de Datos e Inteligencia Artificial, corte EA3, sección 2.4 (extracto aportado)",
        "verdict": "no_apto" if any(r["verdict"] == "no_apto" for r in cases) else "pendiente" if missing or any(r["verdict"] != "apto" for r in cases) else "apto",
        "missingCases": missing, "productionApproved": False,
        "mrr": mean(ranks) if ranks and all(x is not None for x in ranks) else None,
        "fallbackCorrectRate": mean(fallback_cases) if fallback_cases and all(x is not None for x in fallback_cases) else None,
        "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        exigir(output.is_relative_to((RAIZ / "artifacts").resolve()), "Guardar informes privados bajo artifacts/.")
        report = evaluar(json.loads(args.records.read_text(encoding="utf-8"))["records"])
        serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as target:
            target.write(serialized)
        print(f"Matriz: {report['verdict']}; casos: {len(report['cases'])}.")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        parser.exit(1, "No se evaluaron los registros. Revisa formato, evidencia y destino nuevo bajo artifacts/.\n")


if __name__ == "__main__":
    main()
