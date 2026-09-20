"""Forma do harness fuzzy, sem piso de métrica.

Um piso (F1 mínimo, taxa máxima de erro) pressiona a ajustar o cenário
sintético até o teste passar, em vez de investigar o motor. Este módulo
verifica só boa formação: nome, rótulo, unicidade, quatro outcomes,
matriz que soma N e varredura dos floors.
"""
import json
import io
import unittest
from contextlib import redirect_stdout
from tools.fuzzy_metrics import FLOORS, OUTCOMES, SCENARIOS, confusion, main, report, sweep

VALID_LABELS = set(OUTCOMES)


class FuzzyMetricsFormTests(unittest.TestCase):
    def test_scenarios_are_well_formed(self):
        names = [scenario.name for scenario in SCENARIOS]
        self.assertGreaterEqual(len(SCENARIOS), 14)
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(name for name in names))
        labels = {scenario.expected for scenario in SCENARIOS}
        self.assertTrue(labels <= VALID_LABELS)
        self.assertEqual(labels, VALID_LABELS)

    def test_confusion_matrix_sums_to_n(self):
        result = confusion(SCENARIOS)
        total = sum(
            result["matrix"][expected][predicted]
            for expected in OUTCOMES
            for predicted in OUTCOMES
        )
        self.assertEqual(total, len(SCENARIOS))
        self.assertEqual(result["n"], len(SCENARIOS))

    def test_sweep_covers_required_floors(self):
        self.assertEqual(FLOORS, (0.3, 0.4, 0.5, 0.6, 0.7))
        self.assertEqual([row["floor"] for row in sweep(FLOORS)], list(FLOORS))

    def test_report_body_states_synthetic_limitation(self):
        text = report()
        heading_at = text.find("## ")
        limitation_at = text.find("não afirma")
        self.assertNotEqual(heading_at, -1)
        self.assertGreater(limitation_at, heading_at)
        self.assertIn("sintéticos", text)
        self.assertIn("rede real", text)
        self.assertIn("enganoso", text)

    def test_json_flag_emits_object(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            main(["--json"])
        payload = json.loads(buffer.getvalue())
        self.assertIn("confusion", payload)
        self.assertIn("sweep", payload)
