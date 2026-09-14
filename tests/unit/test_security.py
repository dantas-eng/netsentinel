import copy
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from netsentinel.security.config import validate_mac, validate_interface
from netsentinel.security.system import preflight, SystemFailure
from netsentinel.security.agent.controller import VictimController
from netsentinel.security.agent.api import create_app
from netsentinel.security.strategy import VictimAgentMitigationStrategy, DirectAgentTransport, AgentFailure
from netsentinel.security.evidence import verify_interval
from netsentinel.security.attack import run_attack
from tests.security_support import config, FakeLinux


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = config(self.temp.name)
        self.system = FakeLinux(self.config)
        self.controller = VictimController(self.config, self.system)

    def test_injection_and_non_unicast_macs_rejected(self):
        for value in ('02:00:00:00:00:30; flush ruleset', '$(id)', 'ff:ff:ff:ff:ff:ff',
                      '00:00:00:00:00:00', '02:00:00:00:00:30\n', None, 123):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_mac(value)
        self.assertEqual(validate_mac('02:AB:00:00:00:30'), '02:ab:00:00:00:30')

    def test_interface_injection_rejected(self):
        for value in ('enp0s3;drop', 'lo', 'a' * 16):
            with self.assertRaises(ValueError):
                validate_interface(value)

    def test_unknown_mac_rejected_before_any_command(self):
        with self.assertRaises(ValueError):
            self.controller.apply(self.config.gateway_mac)
        self.assertEqual(self.system.commands, [])

    def test_prepare_apply_and_reapply_preserve_counters(self):
        self.controller.prepare()
        self.system.counters['seen']['packets'] = 10
        first = self.controller.apply(self.config.attacker_mac)
        second = self.controller.apply(self.config.attacker_mac)
        self.assertTrue(first['mitigated'])
        self.assertEqual(first['run_id'], second['run_id'])
        self.assertEqual(first['counters'], second['counters'])
        batches = [stdin for argv, stdin in self.system.commands if stdin]
        self.assertEqual(sum(s.startswith('create table') for s in batches), 1)
        self.assertFalse(any('flush ruleset' in s for s in batches))

    def test_restore_removes_only_owned_static_and_table(self):
        self.controller.prepare()
        self.controller.apply(self.config.attacker_mac)
        self.assertTrue(self.controller.restore()['restored'])
        self.assertIsNone(self.system.neighbor)
        self.assertIsNone(self.system.table)
        self.assertTrue(self.controller.restore()['already_clean'])

    def test_preexisting_correct_static_is_preserved(self):
        self.system.neighbor = dict(lladdr=self.config.gateway_mac, state=['PERMANENT'])
        self.controller.prepare()
        self.controller.apply(self.config.attacker_mac)
        self.controller.restore()
        self.assertEqual(self.system.neighbor['lladdr'], self.config.gateway_mac)

    def test_preexisting_foreign_table_never_overwritten(self):
        self.system.table = 'foreign'
        with self.assertRaises(SystemFailure):
            self.controller.prepare()
        self.assertEqual(self.system.table, 'foreign')

    def test_external_neighbor_change_is_not_deleted(self):
        self.controller.prepare()
        self.controller.apply(self.config.attacker_mac)
        self.system.neighbor['lladdr'] = self.config.attacker_mac
        with self.assertRaises(SystemFailure):
            self.controller.restore()
        self.assertIsNotNone(self.system.table)

    def test_partial_failure_does_not_report_success(self):
        self.controller.prepare()
        self.system.fail_replace = True
        with self.assertRaises(SystemFailure):
            self.controller.apply(self.config.attacker_mac)
        status = self.controller.status()
        self.assertTrue(status['blocked'])
        self.assertFalse(status['arp_static_correct'])
        self.assertFalse(status['mitigated'])

    def test_restart_resumes_idempotently(self):
        self.controller.prepare()
        self.controller.apply(self.config.attacker_mac)
        resumed = VictimController(self.config, self.system)
        self.assertTrue(resumed.prepare()['mitigated'])
        self.assertTrue(resumed.restore()['restored'])

    def test_recreated_table_changes_run_id(self):
        old = self.controller.prepare()['run_id']
        self.system.table = None
        new = self.controller.prepare()['run_id']
        self.assertNotEqual(old, new)

    def test_sensor_accepts_only_two_declared_interfaces_and_internal_identity(self):
        cfg = config(self.temp.name, hostonly_interface='enp0s8', hostonly_ip='192.168.56.40',
                     hostonly_cidr='192.168.56.0/24')
        system = FakeLinux(cfg, role='sensor')
        preflight(cfg, 'sensor', system)
        system.addresses.append(dict(ifname='extra', addr_info=[]))
        with self.assertRaises(SystemFailure):
            preflight(cfg, 'sensor', system)

    def test_forwarding_default_route_and_bridge_rejected(self):
        self.system.forwarding = '1'
        with self.assertRaises(SystemFailure):
            preflight(self.config, 'victim', self.system)
        self.system.forwarding = '0'
        self.system.routes = [{'dst': 'default'}]
        with self.assertRaises(SystemFailure):
            preflight(self.config, 'victim', self.system)
        self.system.routes = []
        self.system.addresses[0]['master'] = 'br0'
        with self.assertRaises(SystemFailure):
            preflight(self.config, 'victim', self.system)

    def test_api_requires_actual_internal_peer_and_token(self):
        app = create_app(self.config, self.controller, 'a' * 64)
        client = app.test_client()
        self.assertEqual(client.get('/v1/status', headers={
            'X-Forwarded-For': self.config.sensor_internal_ip}).status_code, 403)
        self.assertEqual(client.get('/v1/status', environ_overrides={
            'REMOTE_ADDR': '192.168.56.40'}, headers={'Authorization': 'Bearer ' + 'a' * 64}).status_code, 403)
        self.assertEqual(client.get('/v1/status', environ_overrides={
            'REMOTE_ADDR': self.config.sensor_internal_ip}).status_code, 401)
        self.assertEqual(self.system.commands, [])

    def test_api_rejects_extra_fields_bad_mac_and_non_json(self):
        client = create_app(self.config, self.controller, 'a' * 64).test_client()
        opts = dict(environ_overrides={'REMOTE_ADDR': self.config.sensor_internal_ip},
                    headers={'Authorization': 'Bearer ' + 'a' * 64})
        for payload in ({'command': 'anything'}, {'attacker_mac': 'bad'},
                        {'attacker_mac': self.config.attacker_mac, 'gateway_mac': 'bad'}):
            self.assertEqual(client.post('/v1/mitigations', json=payload, **opts).status_code, 400)
        self.assertEqual(client.post('/v1/mitigations', data='bad', **opts).status_code, 415)
        self.assertEqual(client.post('/v1/mitigations', data='x' * 1024,
                                    content_type='application/json', **opts).status_code, 413)
        self.assertEqual(self.system.commands, [])

    def test_api_partial_failure_is_503_and_queryable(self):
        self.controller.prepare()
        self.system.fail_replace = True
        client = create_app(self.config, self.controller, 'a' * 64).test_client()
        opts = dict(environ_overrides={'REMOTE_ADDR': self.config.sensor_internal_ip},
                    headers={'Authorization': 'Bearer ' + 'a' * 64})
        result = client.post('/v1/mitigations', json={'attacker_mac': self.config.attacker_mac}, **opts)
        self.assertEqual(result.status_code, 503)
        self.assertFalse(client.get('/v1/status', **opts).json['mitigated'])

    @patch('netsentinel.security.strategy.HTTPConnection')
    def test_transport_binds_internal_source_and_has_timeout(self, connection):
        Path(self.config.token_file).write_text('a' * 64)
        connection.return_value.getresponse.return_value.status = 200
        connection.return_value.getresponse.return_value.read.return_value = b'{}'
        DirectAgentTransport(self.config).request('GET', '/v1/status')
        connection.assert_called_once_with(self.config.victim_ip, self.config.agent_port,
                                           timeout=5.0, source_address=(self.config.sensor_internal_ip, 0))
        connection.return_value.close.assert_called_once()

    @patch('netsentinel.security.strategy.HTTPConnection')
    def test_transport_does_not_follow_redirects(self, connection):
        Path(self.config.token_file).write_text('a' * 64)
        connection.return_value.getresponse.return_value.status = 302
        connection.return_value.getresponse.return_value.read.return_value = b''
        with self.assertRaises(AgentFailure):
            DirectAgentTransport(self.config).request('GET', '/v1/status')
        connection.assert_called_once()

    def test_strategy_requires_both_layers_confirmed(self):
        transport = MagicMock()
        transport.request.return_value = {'attacker_mac': self.config.attacker_mac, 'mitigated': True,
                                           'blocked': True, 'arp_static_correct': False}
        with self.assertRaises(AgentFailure):
            VictimAgentMitigationStrategy(self.config, transport).apply(self.config.attacker_mac)

    def test_attack_fails_preflight_before_sending_with_forwarding(self):
        system = FakeLinux(self.config, role='attacker')
        system.forwarding = '1'
        sender = MagicMock()
        with self.assertRaises(SystemFailure):
            run_attack(self.config, 10, 30, MagicMock(), system, sender)
        sender.assert_not_called()

    def test_attack_packet_only_targets_configured_victim(self):
        from netsentinel.security.attack import poison_packet
        from scapy.layers.l2 import Ether, ARP
        packet = poison_packet(self.config)
        self.assertEqual(packet[Ether].dst, self.config.victim_mac)
        self.assertEqual(packet[ARP].psrc, self.config.gateway_ip)
        self.assertEqual(packet[ARP].hwsrc, self.config.attacker_mac)
        self.assertEqual(packet[ARP].pdst, self.config.victim_ip)
        self.assertEqual(packet[ARP].op, 2)

    def test_attack_loop_is_bounded_without_real_transmission(self):
        system = FakeLinux(self.config, role='attacker')
        now = [0.0]
        stop = MagicMock()
        stop.is_set.return_value = False
        stop.wait.side_effect = lambda seconds: now.__setitem__(0, now[0] + seconds)
        sender = MagicMock()
        count = run_attack(self.config, 4, 1, stop, system, sender, clock=lambda: now[0])
        self.assertEqual(count, 4)
        self.assertEqual(sender.call_count, 4)
        self.assertEqual(now[0], 1)
        self.assertTrue(all(call.kwargs['iface'] == self.config.interface for call in sender.call_args_list))

    def test_high_score_alone_never_triggers_mitigation(self):
        from netsentinel.analysis.models import RiskInputs, RiskResult
        from netsentinel.security.demo import SecurityDemo
        classifier, mitigation = MagicMock(), MagicMock()
        classifier.classify.return_value = {self.config.attacker_mac: RiskResult(
            90, 'suspeito', None, RiskInputs(0, 10, 'new', None), {}, {})}
        demo = SecurityDemo(self.config, classifier, mitigation, lambda _: None)
        demo.consume(dict(timestamp=1, arp_claims=[]))
        mitigation.apply.assert_not_called()


class EvidenceTests(unittest.TestCase):
    def samples(self):
        before = dict(timestamp=1, run_id='r', attacker_mac='a', mitigated=True,
                      blocked=True, arp_static_correct=True,
                      counters={name: dict(packets=10) for name in ('seen', 'dropped', 'passed')})
        after = copy.deepcopy(before)
        after['timestamp'] = 2
        after['counters']['seen']['packets'] += 5
        after['counters']['dropped']['packets'] += 5
        return before, after

    def test_active_drops_and_zero_post_filter_delta(self):
        result = verify_interval(*self.samples())
        self.assertTrue(result['verified'])
        self.assertFalse(result['ping_verified'])
        self.assertEqual(result['deltas']['passed'], 0)

    def test_no_traffic_is_not_success(self):
        before, after = self.samples()
        after['counters'] = copy.deepcopy(before['counters'])
        self.assertFalse(verify_interval(before, after)['verified'])

    def test_ping_or_static_alone_cannot_prove_firewall(self):
        before, after = self.samples()
        after['counters']['passed']['packets'] += 1
        self.assertFalse(verify_interval(before, after)['verified'])

    def test_counter_reset_and_new_run_rejected(self):
        before, after = self.samples()
        after['counters']['seen']['packets'] = 0
        self.assertEqual(verify_interval(before, after)['reason'], 'counter_reset')
        after['run_id'] = 'new'
        self.assertEqual(verify_interval(before, after)['reason'], 'agent_run_changed')
