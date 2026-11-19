"""Evalúa un ticket V2 aprobado sin publicar su texto ni su respuesta histórica."""

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path
from time import perf_counter

from pydantic import ValidationError

from app.configuracion import Configuracion
from app.recuperacion.servicio import ErrorRecuperacion, ServicioRecuperacion
from app.recomendaciones.generacion import MODEL, PROMPT_VERSION, generar, sanear_para_proveedor


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "ml/data/raw/tickets_esp_entrenamiento_v2.csv"
DATASET_SHA256 = "a3792862678c009ca66dad41aeb3e1fbc0a55d4213fd3c39e5cd2e6586e6740a"
FIELDS = ("indice_original", "subject", "body", "answer", "type", "queue", "priority",
          "business_type", "tag_1", "tag_2", "tag_3", "language", "origen")
PRIVATE_PATTERN = re.compile(
    r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|https?://\S+|"
    r"\b(?:password|contrase(?:ñ|n)a|token|api[_ -]?key|secret)\s*[:=]\s*\S+|"
    r"(?<!\d)(?:\+?\d[\d\s()\-]{7,}\d)(?!\d)"
)


def cargar_ticket(csv_path: Path, row_number: int) -> str:
    if row_number < 2:
        raise ValueError("El número de registro CSV debe ser al menos 2.")
    raw = csv_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DATASET_SHA256:
        raise ValueError("El CSV V2 no coincide con la huella documentada.")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("El CSV V2 no tiene el esquema documentado.")
        selected = None
        count = 0
        for number, row in enumerate(reader, 2):
            count += 1
            if None in row or any(value is None for value in row.values()):
                raise ValueError("El CSV V2 contiene un registro mal formado.")
            if number == row_number:
                selected = row
    except (UnicodeDecodeError, csv.Error):
        raise ValueError("El CSV V2 debe ser UTF-8 válido.") from None
    if count != 2239 or selected is None:
        raise ValueError("El CSV V2 no tiene los 2.239 registros esperados o falta el seleccionado.")
    ticket = f"Asunto: {selected['subject']}\nDescripción: {selected['body']}".strip()
    if not 40 <= len(ticket) <= 1000 or PRIVATE_PATTERN.search(ticket) or sanear_para_proveedor(ticket) != ticket:
        raise ValueError("El ticket excede el límite o requiere revisión privada antes de enviarse.")
    return ticket


def evaluar(row_number: int, ticket: str, config: Configuracion, recuperacion=None) -> dict:
    if not config.rag_external_data_approved or not config.gemini_api_key:
        raise ValueError("La evaluación externa necesita aprobación operativa y GEMINI_API_KEY.")
    started = perf_counter()
    result = generar(ticket, recuperacion if recuperacion is not None else ServicioRecuperacion(config),
                     api_key=config.gemini_api_key.get_secret_value(), timeout=config.rag_timeout_seconds,
                     max_chunks=config.rag_max_context_chunks)
    content, sources = result if result else (None, [])
    return {
        "datasetSha256": DATASET_SHA256, "csvRecordNumber": row_number,
        "model": MODEL, "promptVersion": PROMPT_VERSION,
        "outcome": "draft" if content else "insufficient_information",
        "durationMs": round((perf_counter() - started) * 1000, 1), "content": content,
        "sources": [{key: str(item[key]) if key in {"documentId", "documentChunkId"} else item[key]
                     for key in ("documentId", "documentChunkId", "title", "excerpt", "score", "sourceUrl")
                     if key in item} for item in sources],
        "humanReview": {"evidenceSupportsEveryStep": None, "usefulForSpecialist": None,
                        "safeToPresent": None, "notes": None},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--row-number", type=int, required=True, help="Registro CSV: cabecera = 1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    local_artifacts = (ROOT / "ml/artifacts").resolve()
    if not args.output.resolve().is_relative_to(local_artifacts):
        parser.error("El informe debe quedar bajo ml/artifacts, excluido de Git.")
    if args.output.exists():
        parser.error("El informe ya existe; no se sobrescribirá.")
    try:
        ticket = cargar_ticket(DATASET, args.row_number)
        report = evaluar(args.row_number, ticket, Configuracion())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as target:
            json.dump(report, target, ensure_ascii=False, indent=2)
            target.write("\n")
    except (OSError, ValueError, ValidationError, ErrorRecuperacion) as error:
        code = error.code if isinstance(error, ErrorRecuperacion) else type(error).__name__
        parser.exit(1, f"No se completó el registro {args.row_number}: {code}.\n")
    print(f"Registro {args.row_number}: {report['outcome']}; informe local creado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
