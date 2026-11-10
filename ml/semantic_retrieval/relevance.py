"""Calibración experimental orientada a conservar consultas con cobertura."""

import hashlib
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re

from .config import MAX_DOCUMENT_BYTES, MAX_QUERY_CHARACTERS, MODEL_ID


def validate_min_score(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not -1 <= value <= 1 or not math.isfinite(value):
        raise ValueError("El umbral debe ser un número finito entre -1 y 1.")
    return float(value)


def read_json(path: Path) -> tuple[dict, str]:
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_DOCUMENT_BYTES + 1)
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise ValueError("El archivo JSON supera el límite de 1 MB.")
        document = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("No se pudo leer un archivo JSON UTF-8 válido.") from None
    if not isinstance(document, dict):
        raise ValueError("El archivo JSON debe contener un objeto.")
    return document, hashlib.sha256(raw).hexdigest()


def load_cases(path: Path) -> tuple[list[dict], str]:
    document, digest = read_json(path)
    cases = document.get("queries")
    if not isinstance(cases, list) or not cases:
        raise ValueError("La calibración requiere una lista queries no vacía.")
    identifiers, texts = set(), set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Cada consulta debe ser un objeto.")
        identifier, query = case.get("queryId"), case.get("query")
        if (not isinstance(identifier, str) or not identifier.strip() or identifier in identifiers
                or not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARACTERS
                or type(case.get("answerable")) is not bool):
            raise ValueError("Las consultas requieren queryId único, query de 1–1000 caracteres y answerable booleano.")
        normalized = " ".join(query.casefold().split())
        if normalized in texts:
            raise ValueError("La calibración no admite consultas duplicadas.")
        identifiers.add(identifier)
        texts.add(normalized)
    if {case["answerable"] for case in cases} != {True, False}:
        raise ValueError("Se requieren consultas con cobertura y sin cobertura.")
    return cases, digest


def build_profile(observations: list[dict], *, corpus_sha256: str, cases_sha256: str) -> dict:
    positive, negative = [], []
    for row in observations:
        if type(row.get("answerable")) is not bool:
            raise ValueError("answerable debe ser booleano.")
        score = row.get("score")
        if score is None:
            if row["answerable"]:
                raise ValueError("Una consulta con cobertura no obtuvo resultados; no se puede calibrar conservando su recuperación.")
            continue
        (positive if row["answerable"] else negative).append(validate_min_score(score))
    if not positive or not any(not row["answerable"] for row in observations):
        raise ValueError("Se requieren observaciones con cobertura y sin cobertura.")

    # Conservar todos los positivos observados. Entre los cortes que lo permiten,
    # rechazar tantos negativos como sea posible; usar el punto medio del hueco
    # observado para no situar el corte exactamente sobre una muestra.
    lowest_positive = min(positive)
    rejected_scores = [score for score in negative if score < lowest_positive]
    threshold = ((max(rejected_scores) + lowest_positive) / 2
                 if rejected_scores else lowest_positive)
    if rejected_scores and threshold <= max(rejected_scores):
        threshold = lowest_positive
    decisions = [dict(row, accepted=row["score"] is not None and row["score"] >= threshold)
                 for row in observations]
    counts = {
        "coveredAccepted": sum(row["answerable"] and row["accepted"] for row in decisions),
        "coveredRejected": sum(row["answerable"] and not row["accepted"] for row in decisions),
        "uncoveredAccepted": sum(not row["answerable"] and row["accepted"] for row in decisions),
        "uncoveredRejected": sum(not row["answerable"] and not row["accepted"] for row in decisions),
    }
    return {
        "schemaVersion": 1, "status": "experimental", "modelId": MODEL_ID,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "corpusSha256": corpus_sha256, "casesSha256": cases_sha256,
        "minScore": threshold,
        "selectionRule": "preserve_all_covered_calibration_queries_then_maximize_uncovered_rejection",
        "calibration": counts, "observations": decisions,
        "limitations": "Resultados de calibración, no evaluación independiente. No prueba que un fragmento responda correctamente. Requiere revisión humana y recalibración al cambiar modelo o corpus.",
    }


def load_profile(path: Path) -> dict:
    profile, _ = read_json(path)
    if (type(profile.get("schemaVersion")) is not int or profile["schemaVersion"] != 1
            or profile.get("status") != "experimental" or profile.get("modelId") != MODEL_ID
            or not isinstance(profile.get("corpusSha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", profile["corpusSha256"])):
        raise ValueError("El perfil de relevancia no es válido o corresponde a otro modelo.")
    validate_min_score(profile.get("minScore"))
    return profile


def write_profile(path: Path, profile: dict) -> None:
    try:
        with path.open("x", encoding="utf-8") as output:
            output.write(json.dumps(profile, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    except OSError:
        raise ValueError("No se pudo crear el perfil; el destino debe ser nuevo y su carpeta debe existir.") from None
