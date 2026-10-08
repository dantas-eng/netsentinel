import tempfile
import time
import unittest
from unittest.mock import MagicMock
from netsentinel.api.app import create_app
from netsentinel.packets.dissect import dissect, verdict
from netsentinel.repositories.database import Database
from netsentinel.repositories.migrate import upgrade_schema
from tests.backend_support import settings, login
from tests.security_support import config
from tests.unit.test_packets import arp


class PacketsApiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Database('sqlite://')
        self.addCleanup(self.db.engine.dispose)
        upgrade_schema(self.db.engine)
        self.cfg = config(temp.name, hostonly_interface='enp0s8', hostonly_ip='192.168.56.40',
                          hostonly_cidr='192.168.56.0/24')
        self.app = create_app(settings('sqlite://'), self.cfg, self.db, MagicMock())
        self.client = self.app.test_client()
        trusted = self.cfg.trusted_bindings()
        self.gateway_ip = next(ip for ip, mac in trusted.items() if mac == self.cfg.gateway_mac)
        victim_ip = next(ip for ip, mac in trusted.items() if mac == self.cfg.victim_mac)
        self.spoof = arp(2, self.cfg.attacker_mac, self.gateway_ip, self.cfg.victim_mac, victim_ip,
                         dst=self.cfg.victim_mac)
        self.legit = arp(2, self.cfg.gateway_mac, self.gateway_ip, self.cfg.victim_mac, victim_ip,
                         dst=self.cfg.victim_mac)
        self.now = time.time()
        self.app.extensions['repository'].save_arp_frames(
            [dict(timestamp=self.now, raw=self.legit), dict(timestamp=self.now + 1, raw=self.spoof)],
            'run-1', 'live', 5, 20000)

    def get(self, path):
        return self.client.get(path)

    def test_routes_require_session(self):
        for path in ('/api/packets', '/api/packets/1', '/api/packets/match?mac=02:00:00:00:00:30&ip=10.0.0.1&before=1'):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, 401)

    def test_list_filters_and_headers(self):
        login(self.client)
        response = self.get('/api/packets')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(len(response.json['packets']), 2)
        spoofed = self.get('/api/packets?spoofed=1').json['packets']
        self.assertEqual([p['sender_mac'] for p in spoofed], [self.cfg.attacker_mac])
        self.assertEqual(self.get('/api/packets?q=%25').json['packets'], [])

    def test_list_rejects_invalid_parameters(self):
        login(self.client)
        for query in ('limit=0', 'limit=501', 'q=' + 'a' * 65, 'after_id=-1', 'spoofed=2'):
            with self.subTest(query=query):
                self.assertEqual(self.get('/api/packets?' + query).status_code, 400)

    def test_detail_matches_detector_verdict(self):
        login(self.client)
        spoofed_id = self.get('/api/packets?spoofed=1').json['packets'][0]['id']
        detail = self.get(f'/api/packets/{spoofed_id}').json
        self.assertEqual(detail['verdict'], verdict(dissect(self.spoof), self.cfg.trusted_bindings()))
        self.assertEqual(detail['raw_hex'], self.spoof.hex())
        self.assertEqual(self.get('/api/packets/9999').status_code, 404)

    def test_match_validates_and_reports_not_retained(self):
        login(self.client)
        base = f'/api/packets/match?mac={self.cfg.attacker_mac}&ip={self.gateway_ip}'
        found = self.get(f'{base}&before={self.now + 5}')
        self.assertEqual(found.status_code, 200)
        self.assertTrue(found.json['verdict']['spoofed'])
        missing = self.get(f'{base}&before={self.now - 100}')
        self.assertEqual((missing.status_code, missing.json), (404, {'error': 'packet_not_retained'}))
        for query in (f'mac=xx&ip={self.gateway_ip}&before=1', f'mac={self.cfg.attacker_mac}&ip=999.1.1.1&before=1',
                      f'mac={self.cfg.attacker_mac}&ip={self.gateway_ip}&before=nan'):
            with self.subTest(query=query):
                self.assertEqual(self.get('/api/packets/match?' + query).status_code, 400)
