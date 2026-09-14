"""PCAP -> captura 8 s -> fuzzy -> Strategy -> Flask -> comandos simulados.

Scapy, inferência, autenticação e API são reais; kernel e socket HTTP são substitutos.
"""
from pathlib import Path
import tempfile
import unittest
from scapy.all import sniff, wrpcap
from netsentinel.capture.config import CaptureConfig
from netsentinel.capture.service import CaptureService
from netsentinel.analysis.fuzzy import FuzzyRiskStrategy
from netsentinel.security.agent.controller import VictimController
from netsentinel.security.agent.api import create_app
from netsentinel.security.strategy import VictimAgentMitigationStrategy, AgentFailure
from netsentinel.security.demo import SecurityDemo, LabReputation, NoHistoricalBaseline
from tests.security_support import config, FakeLinux
from tests.fixtures.demo import EPOCH, packets


class FlaskTransport:
    def __init__(self, app, config):
        self.client, self.config = app.test_client(), config
        self.calls = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path))
        response = self.client.open(path, method=method, json=payload,
            environ_overrides={'REMOTE_ADDR': self.config.sensor_internal_ip},
            headers={'Authorization': 'Bearer ' + 'a' * 64})
        if response.status_code != 200:
            raise AgentFailure('HTTP failure')
        return response.json


class SecurityPipelineAcceptance(unittest.TestCase):
    def test_new_attacker_without_baseline_causes_verified_agent_action(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = config(directory)
            system = FakeLinux(cfg)
            controller = VictimController(cfg, system)
            controller.prepare()
            transport = FlaskTransport(create_app(cfg, controller, 'a' * 64), cfg)
            strategy = VictimAgentMitigationStrategy(cfg, transport)
            classifier = FuzzyRiskStrategy(LabReputation(cfg), NoHistoricalBaseline())
            events = []
            demo = SecurityDemo(cfg, classifier, strategy, events.append)
            now = [0.0]
            snapshots = []
            capture = CaptureService(CaptureConfig('offline', 8, 1000, True),
                                     snapshots.append, clock=lambda: now[0])
            fixture = Path(directory) / 'lab.pcap'
            wrpcap(str(fixture), packets(False, gateway_ip=cfg.gateway_ip, victim_ip=cfg.victim_ip))

            def ingest(packet):
                now[0] = float(packet.time) - EPOCH
                capture.ingest(packet)

            sniff(offline=str(fixture), store=False, prn=ingest)
            now[0] = 12
            capture.emit()
            snapshot = snapshots[-1]
            demo.consume(snapshot)
            self.assertEqual(snapshot['window_seconds'], 8)
            self.assertFalse(snapshot['warming_up'])
            self.assertGreaterEqual(events[0]['attacker']['score'], 65)
            self.assertEqual(events[0]['attacker']['inputs']['conflict'], 0)
            self.assertIsNone(events[0]['attacker']['inputs']['volume_deviation'])
            self.assertFalse(any(method == 'POST' for method, _ in transport.calls))
            now[0] = 13
            capture.emit()
            demo.consume(snapshots[-1])
            self.assertEqual(events[-1]['event'], 'mitigation_applied')
            self.assertTrue(events[-1]['evidence']['arp_static_correct'])
            self.assertTrue(events[-1]['evidence']['blocked'])
            demo.consume(snapshots[-1])
            self.assertEqual(sum(method == 'POST' for method, _ in transport.calls), 1)
