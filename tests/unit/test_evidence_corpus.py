"""Paridade de verify_interval contra o corpus compartilhado.

Divergência real que o corpus trava: Python indexava
after['counters'][name]['packets'] e levantava KeyError; JS (core.mjs)
usava Number.isFinite e degradava. A ADR 0006 previu isso e já tinha
acontecido. verify_interval agora degrada com reason_code e compara
simulated → environment_changed.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from netsentinel.security.evidence import verify_interval

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures' / 'evidence_cases.json'


class EvidenceCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def test_corpus_has_at_least_ten_cases_with_reason_code(self):
        cases = self.payload['cases']
        self.assertGreaterEqual(len(cases), 10)
        for case in cases:
            self.assertIn('reason_code', case['expected'], case['name'])

    def test_verify_interval_matches_shared_corpus(self):
        for case in self.payload['cases']:
            with self.subTest(case['name']):
                result = verify_interval(case['before'], case['after'])
                expected = case['expected']
                self.assertEqual(result['verified'], expected['verified'])
                self.assertEqual(result['reason_code'], expected['reason_code'])
                self.assertEqual(result['reason'], result['reason_code'])
                self.assertIn('reason_code', result)
