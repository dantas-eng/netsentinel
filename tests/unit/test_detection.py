"""Detecção ampla com mitigação restrita ao MAC pré-aprovado."""
import tempfile
import unittest
from unittest.mock import MagicMock
from netsentinel.analysis.models import RiskInputs, RiskResult
from netsentinel.security.demo import SecurityDemo
from tests.security_support import config


class DetectionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.cfg = config(temp.name)
        self.classifier, self.mitigation = MagicMock(), MagicMock()
        self.mitigation.status.return_value = {'mitigated': True}
        self.events = []
        identity = MagicMock()
        identity.attacker_mac = self.cfg.attacker_mac
        identity.gateway_ip = self.cfg.gateway_ip
        identity.trusted_bindings.return_value = self.cfg.trusted_bindings()
        self.demo = SecurityDemo(identity, self.classifier, self.mitigation, self.events.append)

    def result(self, score=70):
        return RiskResult(score, 'suspeito', None, RiskInputs(0, 10, 'new', None), {}, {})

    def consume(self, claims, scores):
        self.classifier.classify.return_value = {
            mac: self.result(score) for mac, score in scores.items()}
        self.demo.consume(dict(timestamp=len(self.events) + 1, arp_claims=claims))

    def spoof(self, source, ip, claimed=None):
        return dict(ip=ip, claimed_mac=claimed or source, source_mac=source)

    def threats(self):
        for event in reversed(self.events):
            if event['event'] == 'risk_evaluated':
                return event['threats']
        return None

    def test_gateway_spoof_is_detected(self):
        self.consume([self.spoof(self.cfg.attacker_mac, self.cfg.gateway_ip)],
                     {self.cfg.attacker_mac: 70})
        self.assertEqual(self.threats(), [dict(mac=self.cfg.attacker_mac, score=70,
                                               spoofed_ips=[self.cfg.gateway_ip], mitigable=True)])

    def test_victim_spoof_is_detected(self):
        self.consume([self.spoof(self.cfg.attacker_mac, self.cfg.victim_ip)],
                     {self.cfg.attacker_mac: 70})
        self.assertEqual(self.threats()[0]['spoofed_ips'], [self.cfg.victim_ip])

    def test_sensor_spoof_is_detected(self):
        self.consume([self.spoof(self.cfg.attacker_mac, self.cfg.sensor_internal_ip)],
                     {self.cfg.attacker_mac: 70})
        self.assertEqual(self.threats()[0]['spoofed_ips'], [self.cfg.sensor_internal_ip])

    def test_legitimate_claim_is_not_a_threat(self):
        self.consume([self.spoof(self.cfg.gateway_mac, self.cfg.gateway_ip,
                                 claimed=self.cfg.gateway_mac)],
                     {self.cfg.gateway_mac: 70})
        self.assertEqual(self.threats(), [])

    def test_ip_outside_trusted_inventory_is_not_a_threat(self):
        self.consume([self.spoof(self.cfg.attacker_mac, '10.77.0.99')],
                     {self.cfg.attacker_mac: 70})
        self.assertEqual(self.threats(), [])

    def test_score_below_threshold_is_not_a_threat(self):
        self.consume([self.spoof(self.cfg.attacker_mac, self.cfg.gateway_ip)],
                     {self.cfg.attacker_mac: 64})
        self.assertEqual(self.threats(), [])

    def test_unapproved_mac_is_detected_and_never_applied(self):
        other = '02:00:00:00:00:50'
        for _ in range(2):
            self.consume([self.spoof(other, self.cfg.victim_ip)], {other: 80})
        self.mitigation.apply.assert_not_called()
        unmitigable = [e for e in self.events if e['event'] == 'threat_unmitigable']
        self.assertEqual(len(unmitigable), 2)
        self.assertEqual(unmitigable[0]['mac'], other)
        self.assertEqual(unmitigable[0]['reason'], 'mac_not_pre_approved')
        self.assertEqual(unmitigable[0]['spoofed_ips'], [self.cfg.victim_ip])
        self.assertEqual(unmitigable[0]['score'], 80)

    def test_two_simultaneous_threats_only_one_mitigable(self):
        other = '02:00:00:00:00:50'
        claims = [self.spoof(self.cfg.attacker_mac, self.cfg.gateway_ip),
                  self.spoof(other, self.cfg.victim_ip)]
        scores = {self.cfg.attacker_mac: 70, other: 80}
        self.consume(claims, scores)
        self.consume(claims, scores)
        self.mitigation.apply.assert_called_once_with(self.cfg.attacker_mac)
        kinds = [e['event'] for e in self.events]
        self.assertIn('threat_unmitigable', kinds)
        self.assertIn('mitigation_applied', kinds)
        found = self.threats()
        mitigable = [t for t in found if t['mitigable']]
        refused = [t for t in found if not t['mitigable']]
        self.assertEqual(len(mitigable), 1)
        self.assertEqual(len(refused), 1)

    def test_sequence_is_independent_per_mac(self):
        other = '02:00:00:00:00:50'
        self.consume([self.spoof(self.cfg.attacker_mac, self.cfg.gateway_ip),
                      self.spoof(other, self.cfg.victim_ip)],
                     {self.cfg.attacker_mac: 70, other: 80})
        self.consume([self.spoof(other, self.cfg.victim_ip)], {other: 80})
        self.mitigation.apply.assert_not_called()
        self.assertEqual(self.demo.qualifying_count, 0)
        self.consume([self.spoof(self.cfg.attacker_mac, self.cfg.gateway_ip),
                      self.spoof(other, self.cfg.victim_ip)],
                     {self.cfg.attacker_mac: 70, other: 80})
        self.consume([self.spoof(self.cfg.attacker_mac, self.cfg.gateway_ip)],
                     {self.cfg.attacker_mac: 70})
        self.mitigation.apply.assert_called_once_with(self.cfg.attacker_mac)

    def test_nonqualifying_evaluation_zeros_only_the_affected_mac(self):
        other = '02:00:00:00:00:50'
        claims = [self.spoof(self.cfg.attacker_mac, self.cfg.gateway_ip),
                  self.spoof(other, self.cfg.victim_ip)]
        self.consume(claims, {self.cfg.attacker_mac: 70, other: 80})
        self.assertEqual(self.demo.qualifying_count, 1)
        self.consume(claims, {self.cfg.attacker_mac: 50, other: 80})
        self.assertEqual(self.demo.qualifying_count, 0)
        self.mitigation.apply.assert_not_called()
        self.assertTrue(any(e['event'] == 'threat_unmitigable' and e['mac'] == other
                            for e in self.events))
