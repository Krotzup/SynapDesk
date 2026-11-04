"""Lectura estricta y correcciones explícitas sin reescribir el CSV fuente."""

import csv
import hashlib
import io
import json
from pathlib import Path

import pandas as pd

from text_preprocessing import normalize_label

CORRECTION_FIELDS = (
    "numero_fila", "prioridad_original", "prioridad_corregida", "motivo",
)
PRIORITIES = {"low", "medium", "high", "critical"}


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
    return data


def apply_priority_corrections(
    data: pd.DataFrame, corrections_path: Path, manifest_path: Path,
) -> pd.DataFrame:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
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
        if corrected == "critical" and original != "critical":
            raise ValueError("Los criterios actuales no autorizan introducir critical mediante correcciones.")
        doubtful += int(is_doubtful)
        changed += int(corrected != original)
        result.loc[result.index[number - 2], "priority"] = corrected
    result.attrs.update(data.attrs)
    result.attrs["priority_corrections"] = {
        "corrections_sha256": corrections_hash,
        "criteria_version": manifest["criteria_version"],
        "reviewed_rows": len(corrections), "changed_rows": changed,
        "doubtful_rows": doubtful,
    }
    return result
