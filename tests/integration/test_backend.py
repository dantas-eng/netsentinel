import tempfile
import unittest
from http.cookies import SimpleCookie
from unittest.mock import MagicMock, patch
from netsentinel.api.app import create_app
from netsentinel.repositories.database import Database
from netsentinel.repositories.migrate import upgrade_schema
from tests.backend_support import settings, snapshot, login, MAC
from tests.security_support import config


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Database('sqlite://')
        self.addCleanup(self.db.engine.dispose)
        upgrade_schema(self.db.engine)
        cfg = config(self.temp.name, hostonly_interface='enp0s8', hostonly_ip='192.168.56.40',
                     hostonly_cidr='192.168.56.0/24')
        self.now = [8.0]
        self.app = create_app(settings('sqlite://'), cfg, self.db, MagicMock(), clock=lambda: self.now[0])
        self.client = self.app.test_client()
        self.repo = self.app.extensions['repository']
        self.pipeline = self.app.extensions['pipeline']

    def test_http_login_cookie_explicitly_not_secure_and_session_persists(self):
        response, token = login(self.client)
        cookie = SimpleCookie()
        cookie.load(response.headers['Set-Cookie'])
        value = cookie['netsentinel_session']
        self.assertFalse(value['secure'])
        self.assertTrue(value['httponly'])
        self.assertEqual(value['samesite'], 'Lax')
        self.assertIs(self.app.config['SESSION_COOKIE_SECURE'],False)
        self.assertEqual(self.client.get('/api/auth/session', base_url='http://localhost').status_code,200)
        self.assertTrue(token)

    def test_csrf_required_for_login_and_operator_mutations(self):
        self.assertEqual(self.client.post('/api/auth/login',json={}).status_code,403)
        _, token = login(self.client)
        self.repo.save_snapshot(snapshot())
        url = f'/api/devices/{MAC}/reputation'
        payload = dict(known=True,reason='Reconhecido')
        self.assertEqual(self.client.post(url,json=payload).status_code,403)
        self.assertEqual(self.client.post(url,json=payload,headers={'X-CSRF-Token':token}).status_code,200)
        self.assertEqual(self.repo.get_reputation(MAC).value,'known')

    def test_unauthenticated_client_cannot_read_or_change(self):
        self.assertEqual(self.client.get('/api/devices').status_code,401)
        token = self.client.get('/api/auth/csrf').json['csrf_token']
        self.assertEqual(self.client.post(f'/api/devices/{MAC}/reputation',json={},
                        headers={'X-CSRF-Token':token}).status_code,401)

    def test_login_rotates_csrf_token(self):
        old = self.client.get('/api/auth/csrf').json['csrf_token']
        _, new = login(self.client)
        self.assertNotEqual(old,new)
        self.assertEqual(self.client.post('/api/auth/logout',headers={'X-CSRF-Token':old}).status_code,403)

    def test_websocket_requires_session_and_csrf_then_receives_persisted_events(self):
        socketio = self.app.extensions['socketio']
        anonymous = socketio.test_client(self.app)
        self.assertFalse(anonymous.is_connected())
        _, token = login(self.client)
        invalid = socketio.test_client(self.app, flask_test_client=self.client, auth={})
        self.assertFalse(invalid.is_connected())
        client = socketio.test_client(self.app, flask_test_client=self.client, auth={'csrf_token':token})
        self.assertTrue(client.is_connected())
        self.pipeline.consume(snapshot())
        messages = client.get_received()
        event = next(item['args'][0] for item in messages if item['name']=='risk_evaluated')
        self.assertIn('attacker',event)
        self.assertIn('devices',event)
        self.assertEqual(event['source'],'live')
        stored = self.client.get('/api/events').json['events']
        self.assertEqual(stored[0]['event_id'],event['event_id'])
        self.assertIn(MAC,stored[0]['devices'])
        client.disconnect()

    def test_logout_disconnects_websocket(self):
        _, token = login(self.client)
        socket = self.app.extensions['socketio'].test_client(self.app,flask_test_client=self.client,
                                                            auth={'csrf_token':token})
        self.client.post('/api/auth/logout',headers={'X-CSRF-Token':token})
        self.assertFalse(socket.is_connected())
        self.assertEqual(self.client.get('/api/devices').status_code,401)

    def test_api_calibration_then_pipeline_converts_units_and_emits_result(self):
        _, token = login(self.client)
        self.pipeline.consume(snapshot())
        self.repo.change_reputation(MAC,True,'operator','Reconhecido')
        response = self.client.post(f'/api/devices/{MAC}/calibrations',headers={'X-CSRF-Token':token})
        self.assertEqual(response.status_code,202)
        for index,count in enumerate([80,160,240,320,400]):
            self.now[0] = 16+8*index
            self.pipeline.consume(snapshot(end=self.now[0],count=count))
        self.assertEqual(self.repo.get_baseline_bps(MAC),30)
        self.now[0] = 56
        self.pipeline.consume(snapshot(end=56,count=480))
        last_risk = [e for e in self.repo.events() if e['event']=='risk_evaluated'][-1]
        self.assertEqual(last_risk['devices'][MAC]['inputs']['volume_deviation'],1)
        self.assertTrue(any(e['event']=='baseline_calibrated' for e in self.repo.events()))

    def test_cloud_uses_secure_cookie_and_never_constructs_real_agent(self):
        with patch('netsentinel.api.app.VictimAgentMitigationStrategy') as agent:
            app = create_app(settings('sqlite://',mode='cloud'),database=self.db)
            self.assertIs(app.config['SESSION_COOKIE_SECURE'],True)
            agent.assert_not_called()
            from netsentinel.services.synthetic import SyntheticSource
            source = SyntheticSource(clock=lambda:0)
            snap = source.snapshot()
            app.extensions['pipeline'].consume(snap)
            self.assertTrue(all(e['source']=='synthetic' for e in self.repo.events()))
        with self.assertRaises(ValueError):
            create_app(settings('sqlite://',mode='cloud'),database=self.db,mitigation=MagicMock())

    def test_source_mode_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            self.pipeline.consume(snapshot(source='synthetic'))

    def test_pcap_to_repository_strategy_agent_and_websocket(self):
        from scapy.all import sniff, wrpcap
        from pathlib import Path
        from netsentinel.capture.config import CaptureConfig
        from netsentinel.capture.service import CaptureService
        from netsentinel.security.agent.controller import VictimController
        from netsentinel.security.agent.api import create_app as agent_app
        from netsentinel.security.strategy import VictimAgentMitigationStrategy
        from tests.security_support import FakeLinux
        from tests.integration.test_security_pipeline import FlaskTransport
        from tests.fixtures.demo import EPOCH, packets
        cfg = config(self.temp.name)
        controller = VictimController(cfg,FakeLinux(cfg))
        controller.prepare()
        transport = FlaskTransport(agent_app(cfg,controller,'a'*64),cfg)
        self.pipeline.security.mitigation = VictimAgentMitigationStrategy(cfg,transport)
        _, token = login(self.client)
        socket = self.app.extensions['socketio'].test_client(self.app,flask_test_client=self.client,
                                                            auth={'csrf_token':token})
        capture = CaptureService(CaptureConfig('offline',8,1000,True),self.pipeline.consume,
                                 clock=lambda:self.now[0])
        fixture = Path(self.temp.name)/'backend.pcap'
        wrpcap(str(fixture),packets(False,gateway_ip=cfg.gateway_ip,victim_ip=cfg.victim_ip))
        def ingest(packet):
            self.now[0] = float(packet.time)-EPOCH
            capture.ingest(packet)
        sniff(offline=str(fixture),store=False,prn=ingest)
        self.now[0] = 12
        capture.emit()
        first = socket.get_received()
        self.assertNotIn('mitigation_applied', [m['name'] for m in first])
        self.assertFalse(controller.status()['mitigated'])
        self.now[0] = 13
        capture.emit()
        messages = first + socket.get_received()
        names = [m['name'] for m in messages]
        self.assertIn('risk_evaluated',names)
        self.assertIn('mitigation_applied',names)
        self.assertTrue(controller.status()['mitigated'])
        event = next(e for e in self.repo.events() if e['event']=='mitigation_applied')
        self.assertEqual(event['evidence']['attacker_mac'],cfg.attacker_mac)
        self.assertEqual(event['source'],'live')
        self.now[0] = 14
        capture.emit()
        self.assertIn('mitigation_status',[m['name'] for m in socket.get_received()])
        socket.disconnect()
