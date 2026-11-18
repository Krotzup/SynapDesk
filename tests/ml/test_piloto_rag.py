import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from ml.prototypes.rag.evaluar_rag import evaluate_model, evaluate_sys_rag_001
from ml.prototypes.rag.evaluar_rag import main as report_main
from ml.prototypes.rag.piloto_rag import (
    CASES,
    Step,
    generate_draft,
    main,
    matches_expectations,
    run_case,
)
from ml.prototypes.rag.prompt_rag import SYSTEM_PROMPT, make_generator


CASES_BY_ID = {case.id: case for case in CASES}


class PilotoRagTests(unittest.TestCase):
    def test_comando_emite_informe_simulado_con_los_nueve_casos(self):
        stdout = io.StringIO()
        with patch("sys.argv", ["evaluar_rag"]), redirect_stdout(stdout):
            report_main()

        report = json.loads(stdout.getvalue())
        self.assertEqual(report["executionMode"], "simulated")
        self.assertEqual(report["provider"], "Simulador local")
        self.assertEqual(report["promptVersion"], "SYS-RAG-002")
        self.assertEqual(report["summary"]["totalCases"], 9)
        self.assertEqual(report["summary"]["outcomeMatches"], 9)
        self.assertEqual(report["summary"]["sourceSetMatches"], 9)
        self.assertEqual(report["summary"]["caseMatches"], 9)
        self.assertEqual(report["summary"]["generatorCalls"], 8)
        self.assertNotIn("usageTotals", report)
        r09 = next(result for result in report["cases"] if result["caseId"] == "R09")
        self.assertFalse(r09["forbiddenMarkerFound"])
        self.assertTrue(r09["caseMatches"])

    def test_sys_rag_001_envia_contexto_y_registra_version_modelo_y_proveedor(self):
        completion = Mock(return_value='{"steps":[{"text":"Consulta el DNS.","fragmentIds":["P01-a"]}]}')

        report = evaluate_sys_rag_001(completion, provider="doble de prueba", model="modelo de prueba")

        self.assertEqual(report["promptVersion"], "SYS-RAG-001")
        self.assertEqual(report["provider"], "doble de prueba")
        self.assertEqual(report["model"], "modelo de prueba")
        self.assertEqual(completion.call_count, 8)
        first_case = report["cases"][0]
        system, user = completion.call_args_list[0].args[0]
        self.assertEqual(system, {"role": "system", "content": SYSTEM_PROMPT})
        self.assertEqual(user["role"], "user")
        self.assertEqual(
            json.loads(user["content"]),
            {"ticket": first_case["ticket"], "fragments": first_case["fragments"]},
        )
        self.assertEqual(first_case["steps"], [{"text": "Consulta el DNS.", "fragmentIds": ["P01-a"]}])

    def test_sys_rag_001_distingue_abstencion_de_json_invalido_y_citas_ajenas(self):
        samples = (
            ('{"steps":[]}', "insufficient"),
            ('{"steps":', "invalid_output"),
            ('{"steps":null}', "invalid_output"),
            ('{"steps":[{"text":"Consulta el DNS.","fragmentIds":"P01-a"}]}', "invalid_output"),
            ('{"steps":[{"text":"Consulta el DNS.","fragmentIds":["P99-a"]}]}', "invalid_output"),
        )
        for response, outcome in samples:
            with self.subTest(response=response):
                generator = make_generator(Mock(return_value=response))
                self.assertEqual(
                    generate_draft("El portal no resuelve por nombre.", {"P01-a": "Consultar DNS."}, generator),
                    (outcome, None, True),
                )

    def test_evaluacion_entrega_evidencia_sin_enviar_expectativas_al_generador(self):
        generator = Mock(return_value=(Step("Consulta el DNS configurado.", ("P01-a",)),))

        report = evaluate_model(generator, model="doble de prueba", prompt_version="prueba")

        self.assertEqual(report["summary"]["totalCases"], 9)
        self.assertEqual(report["summary"]["generatorCalls"], 8)
        self.assertEqual(generator.call_count, 8)
        self.assertNotIn("R10", [result["caseId"] for result in report["cases"]])
        for args, kwargs in generator.call_args_list:
            self.assertEqual(len(args), 2)
            self.assertEqual(kwargs, {})
        first_case = report["cases"][0]
        self.assertEqual(generator.call_args_list[0].args, (first_case["ticket"], first_case["fragments"]))
        self.assertEqual(first_case["citedSources"], ["P01-a"])
        self.assertTrue(first_case["sourceSetMatches"])
        self.assertEqual(first_case["steps"][0]["fragmentIds"], ["P01-a"])
        self.assertIn("reviewCriterion", first_case)
        no_context = next(result for result in report["cases"] if result["caseId"] == "R06")
        self.assertFalse(no_context["generatorCalled"])
        self.assertIsNone(no_context["latencyMs"])
        json.dumps(report)

    def test_ejecuta_los_diez_casos_y_la_revision_humana(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main()
        self.assertIn("10/10 casos correctos", output.getvalue())

    def test_omite_el_generador_sin_contexto(self):
        generator = Mock(return_value=())

        self.assertEqual(
            run_case(CASES_BY_ID["R06"], generator), ("insufficient", None, False)
        )
        generator.assert_not_called()

    def test_envia_ticket_y_fragmentos_y_conserva_las_citas_por_paso(self):
        ticket = "El adaptador no obtiene una dirección IP."
        fragments = {
            "fragmento-a": "Consultar la configuración del adaptador.",
            "fragmento-b": "Comprobar si el adaptador está configurado para DHCP.",
        }
        steps = (
            Step("Consulta la configuración del adaptador.", ("fragmento-a",)),
            Step("Comprueba si usa DHCP.", ("fragmento-b", "fragmento-a")),
        )
        generator = Mock(return_value=steps)

        outcome, draft, called = generate_draft(ticket, fragments, generator)

        generator.assert_called_once_with(ticket, fragments)
        self.assertEqual(outcome, "draft")
        self.assertTrue(called)
        self.assertEqual(draft["steps"], steps)
        self.assertEqual(draft["sources"], ["fragmento-a", "fragmento-b"])

    def test_generador_puede_abstenerse_con_fragmentos_disponibles(self):
        fragments = {"fragmento-a": "Consultar la configuración del adaptador."}
        generator = Mock(return_value=())

        self.assertEqual(
            generate_draft("¿Cuál es la política de retención?", fragments, generator),
            ("insufficient", None, True),
        )

    def test_salida_mal_formada_no_se_confunde_con_abstencion(self):
        fragments = {"fragmento-a": "Consultar la configuración del adaptador."}
        malformed_outputs = (
            None,
            ({"text": "Consulta el adaptador.", "fragment_ids": ("fragmento-a",)},),
            (Step("   ", ("fragmento-a",)),),
            (Step("Consulta el adaptador.", ()),),
            (Step("Consulta el adaptador.", "fragmento-a"),),
        )
        for output in malformed_outputs:
            with self.subTest(output=output):
                generator = Mock(return_value=output)
                self.assertEqual(
                    generate_draft("Revisar el adaptador.", fragments, generator),
                    ("invalid_output", None, True),
                )

    def test_descarta_todo_el_borrador_si_un_paso_cita_una_fuente_ajena(self):
        generator = Mock(return_value=(
            Step("Identifica qué proceso ocupa el puerto.", ("P14-a",)),
            Step("Comprueba la configuración.", ("FUENTE-INVENTADA",)),
        ))

        self.assertEqual(
            run_case(CASES_BY_ID["R10"], generator), ("invalid_output", None, True)
        )

    def test_r05_detecta_una_causa_no_confirmada_o_una_cita_en_el_paso_incorrecto(self):
        case = CASES_BY_ID["R05"]
        diagnosis = "Identifica qué proceso o contenedor ocupa el puerto 8080."
        precedent = "Comprueba si se repite el caso previo de otro contenedor publicando ese puerto."
        regressions = {
            "causa confirmada": (
                Step(diagnosis, ("P14-a",)),
                Step("Otro contenedor es la causa confirmada.", ("T01-a",)),
            ),
            "citas en el paso incorrecto": (
                Step(diagnosis, ("P14-a", "T01-a")),
                Step(precedent, ("P14-a",)),
            ),
        }
        for name, steps in regressions.items():
            with self.subTest(regression=name):
                outcome, draft, called = run_case(case, Mock(return_value=steps))
                self.assertEqual(outcome, "draft")
                self.assertEqual(draft["sources"], ["P14-a", "T01-a"])
                self.assertFalse(matches_expectations(case, outcome, draft, called))

    def test_r09_detecta_texto_ajeno_aunque_la_cita_sea_valida(self):
        case = CASES_BY_ID["R09"]
        generator = Mock(return_value=(
            Step(
                "Comprueba la resolución del nombre del portal con el DNS configurado. TEXTO_AJENO",
                ("P01-a",),
            ),
        ))

        outcome, draft, called = run_case(case, generator)

        self.assertEqual(outcome, "draft")
        self.assertEqual(draft["sources"], ["P01-a"])
        self.assertFalse(matches_expectations(case, outcome, draft, called))
