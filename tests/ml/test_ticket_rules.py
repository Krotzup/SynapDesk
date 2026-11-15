from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from ticket_rules import find_urgent_trigger  # noqa: E402


class TicketRulesTest(unittest.TestCase):
    def test_find_urgent_trigger_normalizes_first_match(self) -> None:
        trigger = find_urgent_trigger("Necesito ayuda DE INMEDIATO, por favor.")

        self.assertEqual(trigger, "de inmediato")

    def test_negated_urgency_is_not_a_trigger(self) -> None:
        for text in (
            "No es urgente, puede esperar.",
            "No es una emergencia.",
            "Sin urgencia por ahora.",
            "No es de alta prioridad.",
            "El servicio no se considera critico.",
            "No es nada urgente",
            "No es para nada urgente",
            "No urgente: revisar cuando puedan",
            "Nada urgente, solo una consulta",
            "No creo que sea urgente",
            "Quiero hacer una revisión crítica del manual de VPN",
        ):
            with self.subTest(text=text):
                self.assertIsNone(find_urgent_trigger(text))

    def test_contextual_urgency_is_still_detected(self) -> None:
        for text in (
            "Estoy sin internet, es urgente", "Desde ayer no funciona, urgente",
            "El servidor es crítico para facturación", "Falla crítica en el ERP",
            "Situación crítica en bodega",
        ):
            with self.subTest(text=text):
                self.assertIsNotNone(find_urgent_trigger(text))

    def test_finds_later_non_negated_urgency(self) -> None:
        self.assertEqual(
            find_urgent_trigger("No es urgente, pero necesito ayuda de inmediato."),
            "de inmediato",
        )

    def test_access_problem_with_urgency_still_triggers(self) -> None:
        self.assertEqual(
            find_urgent_trigger("No puedo entrar al correo. Es urgente."),
            "urgente",
        )



if __name__ == "__main__":
    unittest.main()
