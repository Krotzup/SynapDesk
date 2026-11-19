"""La evaluación de tickets reales exige identidad del dataset y salida local privada."""

import csv
import hashlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herramientas import evaluar_rag_tickets_v2 as modulo


def csv_sintetico(subject: str, body: str) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(modulo.FIELDS)
    writer.writerow(["1", subject, body] + [""] * 10)
    for number in range(2, 2240):
        writer.writerow([str(number)] + [""] * 12)
    return buffer.getvalue().encode("utf-8")


class EvaluacionRagTicketsV2Test(unittest.TestCase):
    def test_rechaza_dataset_distinto_y_tickets_con_correo(self):
        raw = csv_sintetico("Falla de impresora", "La cola de impresión no recibe trabajos nuevos.")
        with patch.object(Path, "read_bytes", return_value=raw):
            with self.assertRaisesRegex(ValueError, "huella"):
                modulo.cargar_ticket(Path("local.csv"), 2)
        raw = csv_sintetico("Falla de impresora", "Escribir a persona@example.com para recuperar la cola.")
        with (patch.object(Path, "read_bytes", return_value=raw),
              patch.object(modulo, "DATASET_SHA256", hashlib.sha256(raw).hexdigest())):
            with self.assertRaisesRegex(ValueError, "revisión privada"):
                modulo.cargar_ticket(Path("local.csv"), 2)

    def test_informe_no_duplica_ticket_y_deja_revision_pendiente(self):
        document_id, chunk_id = uuid4(), uuid4()
        source = {"documentId": document_id, "documentChunkId": chunk_id,
                  "title": "Impresión", "excerpt": "Comprobar el servicio de cola.", "score": 0.8}
        config = type("Config", (), {"rag_external_data_approved": True,
                                     "gemini_api_key": SecretStr("clave-privada"),
                                     "rag_timeout_seconds": 15, "rag_max_context_chunks": 5})()
        with patch.object(modulo, "generar", return_value=("Comprobar el servicio.", [source])):
            report = modulo.evaluar(2, "Texto privado del ticket", config, recuperacion=object())
        self.assertEqual(report["outcome"], "draft")
        self.assertEqual(report["sources"][0]["documentChunkId"], str(chunk_id))
        self.assertIsNone(report["humanReview"]["safeToPresent"])
        self.assertNotIn("Texto privado del ticket", str(report))
        self.assertNotIn("clave-privada", str(report))


if __name__ == "__main__":
    unittest.main()
