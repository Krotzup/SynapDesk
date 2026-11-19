"""Ejecuta un caso sintético del RAG real y prepara su revisión humana local."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from pydantic import ValidationError

from app.configuracion import Configuracion
from app.recuperacion.servicio import ErrorRecuperacion, ServicioRecuperacion
from app.recomendaciones.generacion import MODEL, PROMPT_VERSION, generar, sanear_para_proveedor


def cargar_caso(path: Path, case_id: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("annotationStatus") != "synthetic_pending_human_review":
        raise ValueError("Solo se admiten consultas sintéticas pendientes de revisión humana.")
    matches = [case for case in payload.get("queries", []) if case.get("queryId") == case_id]
    if len(matches) != 1:
        raise ValueError("El identificador debe seleccionar exactamente un caso.")
    case = matches[0]
    query = case.get("query")
    if (not isinstance(query, str) or not query.strip() or len(query) > 1000
            or sanear_para_proveedor(query) != query
            or not isinstance(case.get("answerable"), bool)):
        raise ValueError("El caso sintético no tiene una consulta segura y válida.")
    return case


def evaluar(case: dict, config: Configuracion, recuperacion=None) -> dict:
    if not config.gemini_api_key or not config.gemini_api_key.get_secret_value():
        raise ValueError("Falta GEMINI_API_KEY en la configuración local.")
    started = perf_counter()
    result = generar(case["query"], recuperacion if recuperacion is not None else ServicioRecuperacion(config),
                     api_key=config.gemini_api_key.get_secret_value(),
                     timeout=config.rag_timeout_seconds,
                     max_chunks=config.rag_max_context_chunks)
    content, sources = result if result is not None else (None, [])
    expected = case.get("expectedDocumentId")
    return {
        "caseId": case["queryId"], "query": case["query"],
        "answerableExpected": case["answerable"], "expectedDocumentId": expected,
        "outcome": "draft" if content else "insufficient_information",
        "outcomeMatches": bool(content) == case["answerable"],
        "expectedDocumentCited": expected in {str(item["documentId"]) for item in sources} if expected else None,
        "content": content,
        "sources": [{key: str(item[key]) if key in {"documentId", "documentChunkId"} else item[key]
                     for key in ("documentId", "documentChunkId", "title", "excerpt", "score", "sourceUrl")
                     if key in item} for item in sources],
        "model": MODEL, "promptVersion": PROMPT_VERSION,
        "durationMs": round((perf_counter() - started) * 1000, 1),
        "humanReview": {"evidenceSupportsEveryStep": None, "usefulForSpecialist": None,
                        "safeToPresent": None, "notes": None},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("El archivo de salida ya existe; no se sobrescribirá.")
    try:
        case = cargar_caso(args.cases, args.case_id)
        report = evaluar(case, Configuracion())
    except (OSError, json.JSONDecodeError, ValueError, ValidationError, ErrorRecuperacion) as error:
        # No imprimir consultas, URLs, credenciales ni respuestas del proveedor.
        code = error.code if isinstance(error, ErrorRecuperacion) else type(error).__name__
        parser.exit(1, f"No se completó el caso {args.case_id}: {code}.\n")
    report["evaluatedAt"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
    except OSError:
        parser.exit(1, "No se pudo crear el informe local.\n")
    print(f"Caso {args.case_id}: {report['outcome']}; informe local creado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
