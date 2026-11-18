import io
import json
import os
import socket
import ssl
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from ml.prototypes.rag.evaluar_gemini import ENDPOINT, MODEL, GeminiError, evaluate_gemini, main
from ml.prototypes.rag.prompt_rag import FOLLOWUP_PROMPT_VERSION, FOLLOWUP_SYSTEM_PROMPT, SYSTEM_PROMPT


MODULE = "ml.prototypes.rag.evaluar_gemini"


def gemini_response(text, *, usage=None):
    payload = {
        "candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"text": "Razonamiento simulado", "thought": True}, {"text": text}]},
        }],
    }
    if usage is not None:
        payload["usageMetadata"] = usage
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


class GeminiEvaluationTests(unittest.TestCase):
    def test_comparacion_sys_rag_002_envia_el_prompt_nuevo_solo_al_caso_elegido(self):
        responses = {
            "R03": [{"text": "Comprueba el puerto TCP 443.", "fragmentIds": ["P05-a"]}],
            "R05": [
                {"text": "Identifica qué ocupa el puerto 8080.", "fragmentIds": ["P14-a"]},
                {"text": "El otro contenedor es un antecedente por verificar.", "fragmentIds": ["T01-a"]},
            ],
        }
        for case_id, steps in responses.items():
            with self.subTest(case_id=case_id):
                stdout = io.StringIO()
                args = ["evaluar_gemini", "--case", case_id, "--prompt-version", FOLLOWUP_PROMPT_VERSION]
                response = gemini_response(json.dumps({"steps": steps}))
                with (
                    patch.dict(os.environ, {"GEMINI_API_KEY": "clave-ficticia"}),
                    patch("sys.argv", args),
                    patch(f"{MODULE}.urlopen", return_value=response) as transport,
                    redirect_stdout(stdout),
                ):
                    main()

                report = json.loads(stdout.getvalue())
                self.assertEqual(report["promptVersion"], FOLLOWUP_PROMPT_VERSION)
                self.assertEqual(report["summary"]["totalCases"], 1)
                self.assertEqual(report["cases"][0]["caseId"], case_id)
                self.assertEqual(report["cases"][0]["steps"], steps)
                transport.assert_called_once()
                body = json.loads(transport.call_args.args[0].data)
                self.assertEqual(
                    body["systemInstruction"], {"parts": [{"text": FOLLOWUP_SYSTEM_PROMPT}]}
                )

    def test_comando_puede_comprobar_un_caso_con_una_sola_solicitud(self):
        response = gemini_response('{"steps":[{"text":"Consulta el DNS.","fragmentIds":["P01-a"]}]}')
        stdout = io.StringIO()
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "clave-ficticia"}),
            patch("sys.argv", ["evaluar_gemini", "--case", "R01", "--timeout", "60"]),
            patch(f"{MODULE}.urlopen", return_value=response) as transport,
            redirect_stdout(stdout),
        ):
            main()

        report = json.loads(stdout.getvalue())
        transport.assert_called_once()
        self.assertEqual(transport.call_args.kwargs["timeout"], 60)
        self.assertEqual(report["requestTimeoutSeconds"], 60)
        self.assertEqual(report["promptVersion"], "SYS-RAG-002")
        self.assertEqual(report["summary"]["totalCases"], 1)
        self.assertEqual(report["summary"]["generatorCalls"], 1)
        self.assertEqual([case["caseId"] for case in report["cases"]], ["R01"])

    def test_r09_informa_el_marcador_y_falla_el_caso_aunque_las_citas_coincidan(self):
        for suffix, marker_found in (("", False), (" TEXTO_AJENO", True), (" texto_ajeno", True)):
            with self.subTest(suffix=suffix):
                steps = [
                    {"text": "Compara el acceso por IP y por nombre.", "fragmentIds": ["P01-a"]},
                    {"text": f"Consulta el DNS configurado.{suffix}", "fragmentIds": ["P01-a"]},
                ]
                stdout = io.StringIO()
                response = gemini_response(json.dumps({"steps": steps}))
                with (
                    patch.dict(os.environ, {"GEMINI_API_KEY": "clave-ficticia"}),
                    patch("sys.argv", ["evaluar_gemini", "--case", "R09"]),
                    patch(f"{MODULE}.urlopen", return_value=response) as transport,
                    redirect_stdout(stdout),
                ):
                    main()

                report = json.loads(stdout.getvalue())
                transport.assert_called_once()
                result = report["cases"][0]
                self.assertEqual(result["caseId"], "R09")
                self.assertTrue(result["outcomeMatches"])
                self.assertTrue(result["sourceSetMatches"])
                self.assertIs(result["forbiddenMarkerFound"], marker_found)
                self.assertIs(result["caseMatches"], not marker_found)
                self.assertEqual(report["summary"]["caseMatches"], int(not marker_found))

    def test_envia_prompt_con_esquema_y_registra_consumo_por_caso(self):
        usage = {"promptTokenCount": 95, "candidatesTokenCount": 20, "thoughtsTokenCount": 3,
                 "totalTokenCount": 118}
        responses = [
            gemini_response('{"steps":[{"text":"Consulta el DNS.","fragmentIds":["P01-a"]}]}', usage=usage),
            *(gemini_response('{"steps":[]}', usage=usage) for _ in range(7)),
        ]
        with patch(f"{MODULE}.urlopen", side_effect=responses) as transport:
            report = evaluate_gemini("clave-ficticia")

        self.assertEqual(transport.call_count, 8)
        self.assertEqual(report["executionMode"], "api")
        self.assertEqual(report["model"], MODEL)
        self.assertEqual(report["promptVersion"], "SYS-RAG-002")
        self.assertEqual(report["summary"]["totalCases"], 9)
        self.assertEqual(report["summary"]["callsWithUsageMetadata"], 8)
        self.assertEqual(report["usageTotals"], {key: count * 8 for key, count in usage.items()})
        by_id = {case["caseId"]: case for case in report["cases"]}
        self.assertEqual(by_id["R01"]["outcome"], "draft")
        self.assertEqual(by_id["R01"]["citedSources"], ["P01-a"])
        self.assertEqual(by_id["R01"]["usageMetadata"], usage)
        self.assertFalse(by_id["R06"]["generatorCalled"])
        self.assertIsNone(by_id["R06"]["usageMetadata"])
        self.assertEqual(by_id["R07"]["outcome"], "insufficient")
        self.assertEqual(by_id["R07"]["usageMetadata"], usage)

        request, = transport.call_args_list[0].args
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("X-goog-api-key"), "clave-ficticia")
        self.assertNotIn("clave-ficticia", request.full_url)
        self.assertNotIn(b"clave-ficticia", request.data)
        body = json.loads(request.data)
        self.assertEqual(body["systemInstruction"], {"parts": [{"text": FOLLOWUP_SYSTEM_PROMPT}]})
        user_input = json.loads(body["contents"][0]["parts"][0]["text"])
        self.assertEqual(user_input, {"ticket": by_id["R01"]["ticket"], "fragments": by_id["R01"]["fragments"]})
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        required_step_fields = body["generationConfig"]["responseJsonSchema"]["properties"]["steps"]["items"]["required"]
        self.assertEqual(required_step_fields, ["text", "fragmentIds"])

    def test_comando_conserva_sys_rag_001_como_opcion_explicita(self):
        stdout = io.StringIO()
        args = ["evaluar_gemini", "--case", "R01", "--prompt-version", "SYS-RAG-001"]
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "clave-ficticia"}),
            patch("sys.argv", args),
            patch(f"{MODULE}.urlopen", return_value=gemini_response('{"steps":[]}')) as transport,
            redirect_stdout(stdout),
        ):
            main()

        self.assertEqual(json.loads(stdout.getvalue())["promptVersion"], "SYS-RAG-001")
        body = json.loads(transport.call_args.args[0].data)
        self.assertEqual(body["systemInstruction"], {"parts": [{"text": SYSTEM_PROMPT}]})

    def test_totales_omiten_campos_ausentes_de_alguna_llamada(self):
        complete = {"promptTokenCount": 95, "totalTokenCount": 118}
        responses = [gemini_response('{"steps":[]}', usage={"totalTokenCount": 118})]
        responses.extend(gemini_response('{"steps":[]}', usage=complete) for _ in range(7))

        with patch(f"{MODULE}.urlopen", side_effect=responses):
            report = evaluate_gemini("clave-ficticia")

        self.assertEqual(report["summary"]["callsWithUsageMetadata"], 8)
        self.assertEqual(report["usageTotals"], {"totalTokenCount": 944})
        self.assertEqual(report["cases"][0]["usageMetadata"], {"totalTokenCount": 118})

    def test_detiene_el_ensayo_ante_429_o_503_sin_reintentos(self):
        for status in (429, 503):
            with self.subTest(status=status):
                error = HTTPError(ENDPOINT, status, "Error simulado", None, io.BytesIO(b"detalle privado"))
                with patch(f"{MODULE}.urlopen", side_effect=error) as transport:
                    with self.assertRaises(GeminiError) as caught:
                        evaluate_gemini("clave-ficticia")
                self.assertEqual(str(caught.exception), f"R01 · Gemini devolvió HTTP {status}.")
                transport.assert_called_once()

    def test_informa_el_caso_que_fallo_despues_de_una_solicitud_exitosa(self):
        responses = [gemini_response('{"steps":[]}'), URLError(TimeoutError("detalle privado"))]

        with patch(f"{MODULE}.urlopen", side_effect=responses) as transport:
            with self.assertRaises(GeminiError) as caught:
                evaluate_gemini("clave-ficticia", timeout_seconds=60)

        self.assertEqual(
            str(caught.exception), "R02 · Se agotó la espera de conexión o lectura (60 s)."
        )
        self.assertEqual(transport.call_count, 2)

    def test_distingue_fallos_de_dns_tls_y_conexion(self):
        failures = (
            (URLError(socket.gaierror("detalle privado")), "DNS"),
            (URLError(ssl.SSLError("detalle privado")), "TLS"),
            (ConnectionResetError("detalle privado"), "se interrumpió"),
        )
        for error, expected in failures:
            with self.subTest(expected=expected):
                with patch(f"{MODULE}.urlopen", side_effect=error):
                    with self.assertRaises(GeminiError) as caught:
                        evaluate_gemini("clave-ficticia")
                message = str(caught.exception)
                self.assertIn("R01", message)
                self.assertIn(expected, message)
                self.assertNotIn("detalle privado", message)

    def test_comando_real_sin_clave_falla_antes_de_enviar_solicitudes(self):
        stderr = io.StringIO()
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": ""}),
            patch("sys.argv", ["evaluar_gemini"]),
            patch(f"{MODULE}.urlopen") as transport,
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as caught:
                main()

        self.assertEqual(caught.exception.code, 2)
        self.assertIn("Configura GEMINI_API_KEY", stderr.getvalue())
        transport.assert_not_called()

    def test_ayuda_funciona_en_terminal_windows_con_cp932(self):
        with io.TextIOWrapper(io.BytesIO(), encoding="cp932") as stdout:
            with patch("sys.argv", ["evaluar_gemini", "--help"]), redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as caught:
                    main()

            self.assertEqual(caught.exception.code, 0)
            stdout.flush()
            self.assertIn(b"SYS-RAG-001", stdout.buffer.getvalue())
