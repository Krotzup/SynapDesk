import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock

from ml.prototypes.rag.piloto_rag import (
    CASES,
    main,
    matches_expectations,
    run_case,
)


CASES_BY_ID = {case.id: case for case in CASES}


class PilotoRagTests(unittest.TestCase):
    def test_ejecuta_los_diez_casos_y_la_revision_humana(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main()
        self.assertIn("10/10 casos correctos", output.getvalue())

    def test_omite_el_generador_sin_contexto(self):
        generator = Mock(return_value=[])

        self.assertEqual(
            run_case(CASES_BY_ID["R06"], generator), ("insufficient", None, False)
        )
        generator.assert_not_called()

    def test_descarta_todo_el_borrador_si_un_paso_cita_una_fuente_ajena(self):
        generator = Mock(return_value=[
            ("Identifica qué proceso ocupa el puerto.", ["P14-a"]),
            ("Comprueba la configuración.", ["FUENTE-INVENTADA"]),
        ])

        self.assertEqual(
            run_case(CASES_BY_ID["R10"], generator), ("invalid_output", None, True)
        )

    def test_r05_detecta_una_causa_no_confirmada_o_una_cita_en_el_paso_incorrecto(self):
        case = CASES_BY_ID["R05"]
        diagnosis = "Identifica qué proceso o contenedor ocupa el puerto 8080."
        precedent = "Comprueba si se repite el caso previo de otro contenedor publicando ese puerto."
        regressions = {
            "causa confirmada": [
                (diagnosis, ["P14-a"]),
                ("Otro contenedor es la causa confirmada.", ["T01-a"]),
            ],
            "citas en el paso incorrecto": [
                (diagnosis, ["P14-a", "T01-a"]),
                (precedent, ["P14-a"]),
            ],
        }
        for name, steps in regressions.items():
            with self.subTest(regression=name):
                outcome, draft, called = run_case(case, Mock(return_value=steps))
                self.assertEqual(outcome, "draft")
                self.assertEqual(draft["sources"], ["P14-a", "T01-a"])
                self.assertFalse(matches_expectations(case, outcome, draft, called))

    def test_r09_detecta_texto_ajeno_aunque_la_cita_sea_valida(self):
        case = CASES_BY_ID["R09"]
        generator = Mock(return_value=[
            ("Comprueba la resolución del nombre del portal con el DNS configurado. TEXTO_AJENO",
             ["P01-a"]),
        ])

        outcome, draft, called = run_case(case, generator)

        self.assertEqual(outcome, "draft")
        self.assertEqual(draft["sources"], ["P01-a"])
        self.assertFalse(matches_expectations(case, outcome, draft, called))
