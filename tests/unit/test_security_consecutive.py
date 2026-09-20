"""ADR 0007: sequência por MAC, reset e preservação das retentativas."""
from dataclasses import replace
import tempfile
import unittest
from unittest.mock import MagicMock
from netsentinel.analysis.models import RiskInputs, RiskResult
from netsentinel.security.demo import SecurityDemo
from netsentinel.security.strategy import AgentFailure
from tests.security_support import config


class ConsecutiveEvaluationsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.cfg = config(temp.name)
        self.classifier, self.mitigation = MagicMock(), MagicMock()
        self.mitigation.status.return_value = {'mitigated': True}
        self.events = []
        self.demo = SecurityDemo(self.cfg, self.classifier, self.mitigation, self.events.append)

    def consume(self, score=65, claim=True, missing=False, result_mac=None):
        mac = self.demo.config.attacker_mac
        result = RiskResult(score, 'suspeito', None, RiskInputs(0, 10, 'new', None), {}, {})
        self.classifier.classify.return_value = {} if missing else {result_mac or mac: result}
        claims = [dict(source_mac=mac, ip=self.cfg.gateway_ip, claimed_mac=mac)] if claim else []
        self.demo.consume(dict(timestamp=len(self.events) + 1, arp_claims=claims))

    def test_two_consecutive_qualifications_apply_once_at_threshold(self):
        self.consume()
        self.mitigation.apply.assert_not_called()
        self.consume()
        self.mitigation.apply.assert_called_once_with(self.cfg.attacker_mac)
        self.consume()
        self.mitigation.apply.assert_called_once()
        self.assertEqual(self.events[-1]['event'], 'mitigation_status')

    def test_nonqualifying_evaluation_resets_then_requires_two_fresh_ones(self):
        self.consume()
        self.consume(claim=False)
        self.mitigation.apply.assert_not_called()
        self.assertEqual(self.demo.qualifying_count, 0)
        self.consume()
        self.mitigation.apply.assert_not_called()
        self.consume()
        self.mitigation.apply.assert_called_once()

    def test_no_false_claim_or_score_below_threshold_never_applies(self):
        for kwargs in ({'claim': False}, {'score': 64.99}, {'score': None}, {'missing': True},
                       {'result_mac': self.cfg.victim_mac}):
            with self.subTest(kwargs=kwargs):
                self.consume(**kwargs)
                self.consume(**kwargs)
                self.mitigation.apply.assert_not_called()
                self.assertEqual(self.demo.qualifying_count, 0)

    def test_low_or_missing_score_breaks_a_started_streak(self):
        for kwargs in ({'score': 64}, {'score': None}, {'missing': True}):
            with self.subTest(kwargs=kwargs):
                self.consume()
                self.consume(**kwargs)
                self.assertEqual(self.demo.qualifying_count, 0)
                self.mitigation.apply.assert_not_called()

    def test_target_change_cannot_combine_two_different_macs(self):
        self.consume()
        other = '02:00:00:00:00:99'
        self.demo.config = replace(self.cfg, attacker_mac=other)
        self.consume()
        self.mitigation.apply.assert_not_called()
        self.consume()
        self.mitigation.apply.assert_called_once_with(other)

    def test_failure_retries_on_next_qualifying_evaluation(self):
        self.mitigation.apply.side_effect = [AgentFailure('offline'), {'mitigated': True}]
        self.consume()
        self.consume()
        self.assertEqual(self.events[-1]['event'], 'mitigation_error')
        self.assertFalse(self.demo.applied)
        self.consume()
        self.assertEqual(self.mitigation.apply.call_count, 2)
        self.assertTrue(self.demo.applied)

    def test_nonqualification_after_failed_apply_clears_retry_streak(self):
        self.mitigation.apply.side_effect = AgentFailure('offline')
        self.consume()
        self.consume()
        self.consume(claim=False)
        self.consume()
        self.assertEqual(self.mitigation.apply.call_count, 1)

    def test_lost_mitigation_needs_new_two_sample_streak(self):
        self.consume()
        self.consume()
        self.mitigation.status.return_value = {'mitigated': False}
        self.consume()
        self.assertEqual(self.mitigation.apply.call_count, 1)
        self.consume()
        self.assertEqual(self.mitigation.apply.call_count, 2)
