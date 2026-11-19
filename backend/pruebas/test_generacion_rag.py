"""Pruebas del límite de confianza entre recuperación y borrador."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.recuperacion.servicio import ErrorRecuperacion
from app.recomendaciones.generacion import (MAX_OUTPUT_TOKENS, generar, sanear_para_proveedor,
                                            solicitar_gemini, validar_borrador)


class Recuperador:
    def __init__(self, items):
        self.items = items
        self.query = None

    def buscar(self, query, limit):
        self.query = query
        return {"status": "results" if self.items else "insufficient_information", "items": self.items[:limit]}


class GeneracionRagTest(unittest.TestCase):
    def setUp(self):
        self.id = str(uuid4())
        self.item = {"documentId": uuid4(), "documentChunkId": self.id,
                     "title": "DNS oficial", "excerpt": "Consultar DNS configurado.", "score": 0.8}

    def test_sin_evidencia_no_llama_gemini(self):
        def fallar(*args, **kwargs):
            self.fail("Se llamó al proveedor sin evidencia")

        self.assertIsNone(generar("Falla DNS", Recuperador([]), api_key="ficticia",
                                  timeout=1, max_chunks=5, completar=fallar))

    def test_solo_citas_recuperadas_y_borrador(self):
        retriever = Recuperador([self.item])
        def complete(ticket, fragments, **_):
            self.assertEqual(set(fragments), {self.id})
            return '{"steps":[{"text":"Revisar DNS","fragmentIds":["' + self.id + '"]}]}'
        content, sources = generar("Falla DNS", retriever, api_key="ficticia",
                                   timeout=1, max_chunks=5, completar=complete)
        self.assertEqual(content, f"Revisar DNS [{self.id}]")
        self.assertEqual(sources, [self.item])

    def test_cita_inventada_rechaza_todo(self):
        with self.assertRaises(ErrorRecuperacion) as caught:
            validar_borrador('{"steps":[{"text":"Revisar DNS","fragmentIds":["inventado"]}]}',
                            {self.id: "texto"})
        self.assertEqual(caught.exception.code, "GENERATION_INVALID")

    def test_abstencion_del_modelo(self):
        self.assertIsNone(validar_borrador('{"steps":[]}', {self.id: "texto"}))

    def test_consulta_larga_reintenta_con_resumen_sin_cambiar_ticket(self):
        class RecuperadorLimitado(Recuperador):
            def buscar(self, query, limit):
                if len(query) > 100:
                    raise ErrorRecuperacion("QUERY_TOKEN_LIMIT_EXCEEDED", "consulta larga", 422)
                return super().buscar(query, limit)
        query = "DNS " * 100
        # En este fixture también el segundo intento supera el límite; el tercero cabe.
        def complete(ticket, fragments, **_):
            self.assertEqual(ticket, query)
            return '{"steps":[{"text":"Revisar DNS","fragmentIds":["' + self.id + '"]}]}'
        retriever = RecuperadorLimitado([self.item])
        self.assertIsNotNone(generar(query, retriever, api_key="ficticia", timeout=1,
                                     max_chunks=5, completar=complete))
        self.assertEqual(len(retriever.query), 80)

    def test_redaccion_y_salida_sensible(self):
        self.assertNotIn("ana@example.com", sanear_para_proveedor("ana@example.com password=abc123"))
        self.assertNotIn("abc123", sanear_para_proveedor("password=abc123"))
        with self.assertRaises(ErrorRecuperacion):
            validar_borrador('{"steps":[{"text":"Enviar correo a ana@example.com",'
                            '"fragmentIds":["' + self.id + '"]}]}', {self.id: "texto"})

    def test_respuesta_incompleta_del_proveedor_se_sanea(self):
        class Respuesta:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return None
            def read(self, *_):
                return b'{"candidates":[]}'

        with patch("app.recomendaciones.generacion.urlopen", return_value=Respuesta()):
            with self.assertRaises(ErrorRecuperacion) as caught:
                solicitar_gemini("Falla DNS", {self.id: "texto"}, api_key="clave-privada", timeout=1)
        self.assertEqual(caught.exception.code, "GENERATION_UNAVAILABLE")
        self.assertNotIn("clave-privada", caught.exception.message)

    def test_solicitud_gemini_tiene_presupuesto_y_no_envia_credenciales_evidentes(self):
        requests = []

        class Respuesta:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self, *_):
                return b'{"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":"{\\"steps\\":[]}"}]}}]}'

        def responder(request, *, timeout):
            requests.append(request)
            self.assertEqual(timeout, 15)
            return Respuesta()

        item = dict(self.item, excerpt="Contactar a ana@example.com")
        with patch("app.recomendaciones.generacion.urlopen", side_effect=responder):
            self.assertIsNone(generar("DNS password=secreto", Recuperador([item]),
                                      api_key="clave-privada", timeout=15, max_chunks=5))
        body = json.loads(requests[0].data)
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], MAX_OUTPUT_TOKENS)
        self.assertEqual(MAX_OUTPUT_TOKENS, 4096)
        self.assertNotIn("secreto", requests[0].data.decode("utf-8"))
        self.assertNotIn("ana@example.com", requests[0].data.decode("utf-8"))
        self.assertNotIn("clave-privada", requests[0].full_url)

    def test_respuesta_truncada_no_se_acepta_como_borrador(self):
        class Respuesta:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self, *_):
                return b'{"candidates":[{"finishReason":"MAX_TOKENS","content":{"parts":[{"text":"{\\"steps\\":[]}"}]}}]}'

        with patch("app.recomendaciones.generacion.urlopen", return_value=Respuesta()):
            with self.assertRaises(ErrorRecuperacion) as caught:
                generar("Falla DNS", Recuperador([self.item]), api_key="ficticia",
                        timeout=15, max_chunks=5)
        self.assertEqual(caught.exception.code, "GENERATION_UNAVAILABLE")

    def test_respuesta_omite_bloques_de_razonamiento(self):
        class Respuesta:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self, *_):
                return b'{"candidates":[{"finishReason":"STOP","content":{"parts":[' \
                    b'{"text":"razonamiento interno","thought":true},' \
                    b'{"text":"{\\"steps\\":[]}"},' \
                    b'{"thoughtSignature":"firma"}]}}]}'

        with patch("app.recomendaciones.generacion.urlopen", return_value=Respuesta()):
            raw = solicitar_gemini("Falla DNS", {self.id: "Consultar DNS"},
                                  api_key="ficticia", timeout=15)
        self.assertIsNone(validar_borrador(raw, {self.id: "Consultar DNS"}))

    def test_telemetria_registra_solo_contadores_del_proveedor(self):
        class Respuesta:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self, *_):
                return json.dumps({
                    "candidates": [{"finishReason": "STOP", "content": {"parts": [
                        {"text": '{"steps":[]}'},
                    ]}}],
                    "usageMetadata": {"promptTokenCount": 12, "totalTokenCount": 20,
                                      "privateValue": "dato que no debe registrarse"},
                }).encode("utf-8")

        with (patch("app.recomendaciones.generacion.urlopen", return_value=Respuesta()),
              self.assertLogs("app.recomendaciones.generacion", level="INFO") as logs):
            solicitar_gemini("ticket privado", {self.id: "fragmento privado"},
                            api_key="clave-privada", timeout=1)
        joined = "\n".join(logs.output)
        self.assertIn("promptTokenCount", joined)
        self.assertIn("totalTokenCount", joined)
        for secret in ("ticket privado", "fragmento privado", "clave-privada", "dato que no debe registrarse"):
            self.assertNotIn(secret, joined)


if __name__ == "__main__":
    unittest.main()
