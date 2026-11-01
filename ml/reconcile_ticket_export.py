"""Recupera una copia del export de Excel conocido, sin modificar sus fuentes.

Solo restituye separadores de etiquetas opcionales con correspondencia única.
Los registros ambiguos se preservan completos y se excluyen del entrenamiento.
"""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from dataset_io import PRIORITIES, file_sha256

EXPECTED_HEADER = [
    "indice_original", "subject", "body", "answer", "type", "queue", "priority",
    "business_type", "tag_1", "tag_2", "tag_3", "language", "origen",
]


def parse_record(row: list[str]) -> list[str]:
    parts = list(row)
    while len(parts) > 1 and parts[-1] == "":
        parts.pop()
    records = list(csv.reader(io.StringIO(";".join(parts)), strict=True))
    if len(records) != 1:
        raise ValueError("multiple_records")
    return records[0]


def reconcile(original_path: Path, edited_path: Path, output_dir: Path,
              original_encoding: str = "cp932") -> dict:
    # Lectura explícita: no se adivina la codificación ni se reemplazan caracteres.
    original_raw, edited_raw = original_path.read_bytes(), edited_path.read_bytes()
    original_text = original_raw.decode(original_encoding).replace("\r\n", "\n").replace("\r", "\n")
    edited_text = edited_raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    before = list(csv.reader(io.StringIO(original_text), delimiter=";", strict=True))
    after = list(csv.reader(io.StringIO(edited_text), delimiter=";", strict=True))
    if not before or len(before) != len(after):
        raise ValueError("Los archivos deben tener la misma cantidad de registros.")
    if parse_record(before[0]) != EXPECTED_HEADER or parse_record(after[0]) != EXPECTED_HEADER:
        raise ValueError("El export no tiene la estructura de tickets documentada.")
    if any(len(row) != 3 for row in before + after):
        raise ValueError("Esta recuperación requiere el export externo de tres columnas.")
    output_dir = output_dir.resolve()
    destinations = [output_dir / name for name in (
        "tickets_esp_utf8_normalizado.csv", "registros_estructura_dudosa.json",
        "normalization_report.json", "cambios_usuario.json",
    )]
    if any(path in (original_path.resolve(), edited_path.resolve()) for path in destinations):
        raise ValueError("La salida no puede reemplazar un archivo fuente.")
    hashes = {"source_original_sha256": hashlib.sha256(original_raw).hexdigest(),
              "source_edited_sha256": hashlib.sha256(edited_raw).hexdigest()}
    valid, quarantine, repairs, changes = [], [], [], []
    for number, (old, new) in enumerate(zip(before[1:], after[1:], strict=True), 2):
        if old != new:
            changes.append({"numero_fila": number, "original": old, "editado": new})
        try:
            reference, edited = parse_record(old), parse_record(new)
            if len(reference) != 13:
                raise ValueError("estructura_original_ambigua")
            if not edited or reference[0] != edited[0] or not reference[0].isdigit():
                raise ValueError("identificador_no_coincide")
            repair = None
            if len(edited) == 12:
                tags, remaining = reference[8:11], edited[8:-2]
                candidates = [i for i in range(3) if tags[:i] + tags[i + 1:] == remaining]
                if len(candidates) != 1 or [v.strip() for v in edited[-2:]] != [v.strip() for v in reference[-2:]]:
                    raise ValueError("columna_eliminada_ambigua")
                index = candidates[0]
                remaining.insert(index, "")
                edited = edited[:8] + remaining + edited[-2:]
                repair = {"numero_fila": number, "columna": EXPECTED_HEADER[8 + index],
                          "accion": "Conservar eliminación del valor; restituir separador como celda vacía."}
            if len(edited) != 13:
                raise ValueError("cantidad_campos_incorrecta")
            if edited[6].strip().lower() not in PRIORITIES or edited[11].strip().lower() != "es":
                raise ValueError("prioridad_o_idioma_ambiguos")
            if edited[4:6] != reference[4:6]:
                raise ValueError("tipo_o_cola_no_comprobados")
            valid.append(edited + [number])
            if repair:
                repairs.append(repair)
        except (csv.Error, ValueError, IndexError) as error:
            quarantine.append({"numero_fila": number, "motivo": str(error),
                               "original": old, "editado": new})
    # No escribir resultados si otra aplicación cambió las fuentes durante la lectura.
    if hashes != {"source_original_sha256": file_sha256(original_path),
                  "source_edited_sha256": file_sha256(edited_path)}:
        raise ValueError("Los archivos fuente cambiaron durante la reconciliación.")
    output_dir.mkdir(parents=True, exist_ok=True)
    with destinations[0].open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(EXPECTED_HEADER + ["registro_csv_fuente"])
        writer.writerows(valid)
    report = {**hashes, "original_encoding": original_encoding,
              "input_records": len(after) - 1, "validated_records": len(valid),
              "quarantined_records": len(quarantine), "changed_records": len(changes),
              "structural_repairs": repairs,
              "quarantined_record_numbers": [item["numero_fila"] for item in quarantine],
              "training_copy_sha256": file_sha256(destinations[0])}
    for path, payload in ((destinations[1], quarantine), (destinations[2], report),
                          (destinations[3], changes)):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--edited", type=Path, required=True)
    parser.add_argument("--original-encoding", default="cp932")
    parser.add_argument("--output-dir", type=Path, default=Path("ml/artifacts/data_reconciliation"))
    args = parser.parse_args()
    report = reconcile(args.original, args.edited, args.output_dir, args.original_encoding)
    print(json.dumps({key: report[key] for key in
                      ("input_records", "validated_records", "quarantined_records", "changed_records")}))
