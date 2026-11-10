"""Lectura estricta y correcciones explícitas sin reescribir el CSV fuente."""

import csv
import hashlib
import io
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from text_preprocessing import normalize_label

CORRECTION_FIELDS = (
    "numero_fila", "prioridad_original", "prioridad_corregida", "motivo",
)
PRIORITIES = {"low", "medium", "high"}


def correction_validation(manifest: dict, reviewed_rows: int) -> dict:
    """Conserva la declaración humana; su ausencia nunca equivale a aprobación."""
    validation = manifest.get("validation", {"status": "pending"})
    if not isinstance(validation, dict):
        raise ValueError("La validación de correcciones debe ser un objeto.")
    if validation == {"status": "pending"}:
        return dict(validation)
    if (set(validation) != {"status", "reviewer", "validated_at", "reviewed_rows"}
            or validation.get("status") != "validated"
            or not isinstance(validation.get("reviewer"), str)
            or not validation["reviewer"].strip()
            or type(validation.get("reviewed_rows")) is not int
            or validation["reviewed_rows"] != reviewed_rows):
        raise ValueError("La validación requiere responsable, fecha UTC y el total de decisiones revisadas.")
    try:
        timestamp = datetime.fromisoformat(validation["validated_at"])
        if timestamp.utcoffset() != timedelta(0):
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("La fecha de validación debe ser ISO 8601 con zona UTC.") from None
    return dict(validation)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_dataset(csv_path: Path) -> pd.DataFrame:
    raw = csv_path.read_bytes()
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("El CSV debe estar codificado en UTF-8; exporta una copia válida.") from None
    try:
        rows = list(csv.reader(io.StringIO(decoded, newline=""), strict=True))
    except csv.Error:
        raise ValueError("CSV inválido: revisa delimitadores y comillas.") from None
    if not rows or not rows[0] or len(set(rows[0])) != len(rows[0]):
        raise ValueError("El CSV requiere una cabecera no vacía sin columnas duplicadas.")
    for number, row in enumerate(rows[1:], 2):
        if len(row) != len(rows[0]):
            raise ValueError(f"El registro CSV {number} tiene una cantidad incorrecta de campos.")
    data = pd.read_csv(io.StringIO(decoded))
    data.attrs["source_sha256"] = hashlib.sha256(raw).hexdigest()
    manifest_path = csv_path.with_suffix(".manifest.json")
    if manifest_path.exists():
        attach_derived_manifest(data, csv_path, manifest_path)
    return data


def attach_derived_manifest(data: pd.DataFrame, csv_path: Path, manifest_path: Path) -> None:
    """Verifica el sidecar local y conserva procedencia sin reaplicar correcciones."""
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw.decode("utf-8-sig"))
    if (not isinstance(manifest, dict) or manifest.get("artifact_type") != "derived_ticket_dataset"
            or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1
            or manifest.get("dataset_file") != csv_path.name
            or manifest.get("dataset_sha256") != data.attrs["source_sha256"]
            or manifest.get("corrections_already_applied") is not True):
        raise ValueError("El manifiesto del dataset derivado no corresponde al CSV o no es compatible.")
    for key in ("source_sha256", "corrections_sha256"):
        if not isinstance(manifest.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", manifest[key]):
            raise ValueError("El manifiesto derivado requiere hashes SHA-256 de origen y correcciones.")
    counts = ("source_records", "output_records", "priority_changes", "reviewed_rows",
              "doubtful_decisions_preserved", "text_changes", "records_removed")
    if (any(type(manifest.get(key)) is not int or manifest[key] < 0 for key in counts)
            or manifest["source_records"] != len(data) or manifest["output_records"] != len(data)
            or manifest.get("text_changes") != 0 or manifest.get("records_removed") != 0
            or manifest["priority_changes"] > manifest["reviewed_rows"]
            or manifest["doubtful_decisions_preserved"] > manifest["reviewed_rows"]
            or manifest["priority_changes"] + manifest["doubtful_decisions_preserved"] > manifest["reviewed_rows"]
            or manifest["reviewed_rows"] > len(data)):
        raise ValueError("Los conteos del manifiesto derivado no son coherentes con el CSV.")
    if not isinstance(manifest.get("criteria_version"), str) or not manifest["criteria_version"].strip():
        raise ValueError("El manifiesto derivado requiere versión de criterios.")
    validation = correction_validation(manifest, manifest["reviewed_rows"])
    data.attrs["derived_dataset"] = {
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "original_source_sha256": manifest["source_sha256"],
        "corrections_already_applied": True,
    }
    data.attrs["priority_corrections"] = {
        "corrections_sha256": manifest["corrections_sha256"],
        "criteria_version": manifest["criteria_version"],
        "reviewed_rows": manifest["reviewed_rows"],
        "changed_rows": manifest["priority_changes"],
        "doubtful_rows": manifest["doubtful_decisions_preserved"],
        "validation": validation,
        "validation_note": manifest.get("validation_note"),
    }


def apply_priority_corrections(
    data: pd.DataFrame, corrections_path: Path, manifest_path: Path,
) -> pd.DataFrame:
    if "priority_corrections" in data.attrs:
        raise ValueError("El dataset ya contiene correcciones aplicadas; no deben reaplicarse.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict):
        raise ValueError("El manifiesto de correcciones debe ser un objeto JSON.")
    if manifest.get("source_sha256") != data.attrs.get("source_sha256"):
        raise ValueError("Las correcciones no corresponden al SHA-256 del CSV fuente.")
    corrections_hash = file_sha256(corrections_path)
    if manifest.get("corrections_sha256") != corrections_hash:
        raise ValueError("El SHA-256 del archivo de correcciones no coincide.")
    if not isinstance(manifest.get("criteria_version"), str) or not manifest["criteria_version"].strip():
        raise ValueError("Falta la versión de los criterios de prioridad.")
    with corrections_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != CORRECTION_FIELDS:
            raise ValueError("La cabecera de correcciones no coincide con el formato documentado.")
        corrections = list(reader)
    validation = correction_validation(manifest, len(corrections))
    result = data.copy(deep=True)
    seen = set()
    changed = doubtful = 0
    for correction in corrections:
        if None in correction or any(value is None for value in correction.values()):
            raise ValueError("Una corrección tiene una cantidad incorrecta de campos.")
        try:
            number = int(correction["numero_fila"])
        except ValueError:
            raise ValueError("El número de registro de una corrección no es entero.") from None
        if number < 2 or number > len(data) + 1 or number in seen:
            raise ValueError(f"Registro de corrección inexistente o repetido: {number}.")
        seen.add(number)
        original = normalize_label(correction["prioridad_original"])
        corrected = normalize_label(correction["prioridad_corregida"])
        reason = correction["motivo"].strip()
        if original not in PRIORITIES or corrected not in PRIORITIES or not reason:
            raise ValueError(f"Prioridad o motivo inválidos en la corrección {number}.")
        if normalize_label(data.iloc[number - 2]["priority"]) != original:
            raise ValueError(f"La prioridad original no coincide en el registro {number}.")
        is_doubtful = reason.lower().startswith("dudoso")
        if is_doubtful and corrected != original:
            raise ValueError(f"Un caso dudoso no puede cambiar prioridad: {number}.")
        doubtful += int(is_doubtful)
        changed += int(corrected != original)
        result.loc[result.index[number - 2], "priority"] = corrected
    result.attrs.update(data.attrs)
    result.attrs["priority_corrections"] = {
        "corrections_sha256": corrections_hash,
        "criteria_version": manifest["criteria_version"],
        "reviewed_rows": len(corrections), "changed_rows": changed,
        "doubtful_rows": doubtful,
        "validation": validation,
        "validation_note": manifest.get("validation_note"),
    }
    return result
