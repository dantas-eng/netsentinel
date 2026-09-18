"""Aceitação: PCAP -> Scapy -> CaptureService -> providers -> Mamdani."""
from pathlib import Path
import tempfile
import unittest
from scapy.all import sniff
from netsentinel.capture.config import CaptureConfig
from netsentinel.capture.service import CaptureService
from netsentinel.analysis.contracts import Reputation
from netsentinel.analysis.fuzzy import FuzzyRiskStrategy
from tests.support import FixedReputation, FixedBaseline
from tests.fixtures.demo import ATTACKER, EPOCH, write_fixtures

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'


class DemoAcceptance(unittest.TestCase):
    def classify_fixture(self, filename):
        clock = [0.0]
        snapshots = []
        capture = CaptureService(CaptureConfig('offline', 10, 1000, True),
                                 snapshots.append, clock=lambda: clock[0])

        def ingest(packet):
            clock[0] = float(packet.time) - EPOCH
            capture.ingest(packet)

        sniff(offline=str(FIXTURES / filename), store=False, prn=ingest)
        clock[0] = 12.0
        capture.emit()
        strategy = FuzzyRiskStrategy(FixedReputation({ATTACKER: Reputation.NEW}),
                                     FixedBaseline({}))
        return snapshots[-1], strategy.classify(snapshots[-1])[ATTACKER]

    def test_new_attacker_without_baseline_with_conflict(self):
        snapshot, result = self.classify_fixture('demo_gateway_claim.pcap')
        self.assertFalse(snapshot['warming_up'])
        self.assertFalse(snapshot['incomplete'])
        self.assertEqual(result.inputs.conflict, 0.5)
        self.assertIsNone(result.inputs.volume_deviation)
        self.assertEqual(result.memberships['deviation'], {'low': 0, 'high': 0})
        self.assertGreaterEqual(result.score, 65)
        self.assertEqual(result.classification, 'suspeito')
        self.assertEqual(result.rule_strengths['R1'], 0.5)
        self.assertEqual(result.rule_strengths['R2'], 0.5)

    def test_new_attacker_without_baseline_without_conflict(self):
        _, result = self.classify_fixture('demo_no_gateway_claim.pcap')
        self.assertEqual(result.inputs.conflict, 0)
        self.assertGreaterEqual(result.inputs.arp_frequency, 5)
        self.assertIsNone(result.inputs.volume_deviation)
        self.assertEqual(result.rule_strengths['R1'], 0)
        self.assertEqual(result.rule_strengths['R2'], 1)
        self.assertGreaterEqual(result.score, 65)
        self.assertEqual(result.classification, 'suspeito')

    def test_fixtures_are_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            write_fixtures(Path(directory))
            for name in ('demo_gateway_claim.pcap', 'demo_no_gateway_claim.pcap'):
                self.assertEqual((FIXTURES / name).read_bytes(),
                                 (Path(directory) / name).read_bytes())
