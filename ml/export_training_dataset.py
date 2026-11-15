"""Exporta un CSV derivado reproducible y su manifiesto sin modificar el original."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path

from dataset_io import apply_priority_corrections, file_sha256, read_dataset
from train_ticket_classifier import validate_columns


def export_training_dataset(source: Path, corrections: Path, correction_manifest: Path, output: Path) -> dict:
    manifest_output = output.with_suffix(".manifest.json")
    if output.suffix.lower() != ".csv":
        raise ValueError("El destino debe ser un archivo .csv.")
    if output.exists() or manifest_output.exists():
        raise ValueError("El CSV o su manifiesto destino ya existen; elige un destino nuevo.")
    raw = source.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    data = read_dataset(source)
    validate_columns(data)
    if data.attrs["source_sha256"] != source_hash:
        raise ValueError("El original cambió durante la lectura.")
    corrected = apply_priority_corrections(data, corrections, correction_manifest)
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True))
    priority_index = rows[0].index("priority")
    changes = []
    for position, row in enumerate(rows[1:]):
        label = str(corrected.iloc[position]["priority"])
        if row[priority_index] != label:
            changes.append({"source_record": position + 2, "original_priority": row[priority_index],
                            "corrected_priority": label})
            row[priority_index] = label
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\r\n").writerows(rows)
    exported = buffer.getvalue().encode("utf-8-sig")
    provenance = corrected.attrs["priority_corrections"]
    if len(changes) != provenance["changed_rows"]:
        raise ValueError("Las etiquetas originales requieren normalización; no se cambia texto al exportar.")
    if file_sha256(source) != source_hash:
        raise ValueError("El original cambió durante la exportación.")
    manifest = {
        "artifact_type": "derived_ticket_dataset", "schema_version": 1,
        "dataset_file": output.name, "created_at": datetime.now(timezone.utc).isoformat(),
        "encoding": "UTF-8 with BOM", "delimiter": ",",
        "source_file": source.name, "source_sha256": source_hash,
        "dataset_sha256": hashlib.sha256(exported).hexdigest(),
        "source_records": len(data), "output_records": len(data),
        "priority_changes": len(changes), "text_changes": 0, "records_removed": 0,
        "reviewed_rows": provenance["reviewed_rows"],
        "doubtful_decisions_preserved": provenance["doubtful_rows"],
        "corrections_already_applied": True,
        "corrections_sha256": provenance["corrections_sha256"],
        "criteria_version": provenance["criteria_version"],
        "validation": provenance["validation"], "validation_note": provenance["validation_note"],
        "changes": changes,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reservar ambos nombres antes de escribir: nunca sustituir datos existentes.
    with output.open("xb") as csv_destination:
        try:
            manifest_destination = manifest_output.open("x", encoding="utf-8")
        except OSError:
            csv_destination.close()
            output.unlink()
            raise
        with manifest_destination:
            csv_destination.write(exported)
            manifest_destination.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--corrections-csv", type=Path, required=True)
    parser.add_argument("--corrections-manifest", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = export_training_dataset(args.input_csv, args.corrections_csv, args.corrections_manifest, args.output_csv)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"CSV y manifiesto creados: {result['output_records']} registros, {result['priority_changes']} prioridades modificadas.")


if __name__ == "__main__":
    main()
