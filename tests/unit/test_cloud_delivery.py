"""Contrato de entrega: sem rede, credenciais reais ou provisionamento pago."""
import unittest
from unittest.mock import Mock

from tools.cloud_smoke import check, validate_url
from tools.render_deploy import deploy


SHA = 'a' * 40


class RenderDeliveryTests(unittest.TestCase):
    def test_deploy_pins_sha_and_waits_for_live(self):
        api = Mock(side_effect=[{'id': 'dep-example'}, {'status': 'build_in_progress'},
                                {'status': 'live', 'commit': {'id': SHA}}])
        result = deploy(api, 'srv-example', SHA, sleep=Mock())
        self.assertEqual(result['commit'], SHA)
        self.assertEqual(api.call_args_list[0].args[1]['commitId'], SHA)
        self.assertEqual(api.call_count, 3)

    def test_live_wrong_commit_is_not_success(self):
        api = Mock(side_effect=[{'id': 'dep-example'},
                                {'status': 'live', 'commit': {'id': 'b' * 40}}])
        with self.assertRaisesRegex(RuntimeError, 'difere'):
            deploy(api, 'srv-example', SHA)

    def test_terminal_failure_or_unknown_status_is_not_success(self):
        for status in ('build_failed', 'update_failed', 'canceled', 'deactivated', 'unexpected'):
            with self.subTest(status=status):
                api = Mock(side_effect=[{'id': 'dep-example'}, {'status': status}])
                with self.assertRaises(RuntimeError):
                    deploy(api, 'srv-example', SHA)

    def test_timeout_does_not_trigger_second_deploy(self):
        api = Mock(return_value={'id': 'dep-example'})
        with self.assertRaisesRegex(RuntimeError, 'Tempo limite'):
            deploy(api, 'srv-example', SHA, clock=Mock(side_effect=[0, 1201]))
        self.assertEqual(api.call_count, 1)

    def test_bad_id_or_sha_never_calls_provider(self):
        for service, sha in (('srv-../x', SHA), ('srv-example', 'main')):
            api = Mock()
            with self.assertRaises(ValueError):
                deploy(api, service, sha)
            api.assert_not_called()

    def test_accepted_response_without_deploy_id_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'identificador'):
            deploy(Mock(return_value={}), 'srv-example', SHA)


class FakeCloud:
    """Simula política de sessão, rotação CSRF e fonte; guarda ordem das chamadas."""
    def __init__(self, source='synthetic', moving=True):
        self.logged_in = False
        self.source, self.moving = source, moving
        self.calls = []
        self.timestamp = 100

    def __call__(self, path, data=None, csrf=None):
        self.calls.append((path, data, csrf))
        if path == '/health':
            return 200, {'status': 'ok', 'mode': 'cloud'}
        if path == '/api/auth/csrf':
            return 200, {'csrf_token': 'prelogin'}
        if path == '/api/auth/login':
            if csrf != 'prelogin':
                return 403, {}
            self.logged_in = True
            return 200, {'csrf_token': 'rotated'}
        if path == '/api/auth/logout':
            if csrf != 'rotated':
                return 403, {}
            self.logged_in = False
            return 200, {}
        if not self.logged_in:
            return 401, {}
        if path == '/api/status':
            self.timestamp += int(self.moving)
            return 200, {'mode': 'cloud', 'source_running': True,
                         'last_snapshot_at': self.timestamp, 'source_error': None}
        if path == '/api/events':
            return 200, {'events': [{'source': self.source}]}
        return 200, {}


class CloudSmokeTests(unittest.TestCase):
    def test_https_origin_required_before_credentials(self):
        for url in ('http://example.com', 'https://u:p@example.com',
                    'https://example.com/path', 'https://example.com?x=1',
                    'https://example.com#token'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)
        self.assertEqual(validate_url('https://demo.onrender.com/'), 'https://demo.onrender.com')

    def test_csrf_first_rotates_and_logs_out(self):
        cloud = FakeCloud()
        check(cloud, 'operador', 'test-only', sleep=Mock())
        self.assertFalse(cloud.logged_in)
        calls = [call[0] for call in cloud.calls]
        self.assertLess(calls.index('/api/auth/csrf'), calls.index('/api/auth/login'))
        self.assertEqual(cloud.calls[-2], ('/api/auth/logout', {}, 'rotated'))

    def test_stationary_source_is_failure_and_logs_out(self):
        cloud = FakeCloud(moving=False)
        with self.assertRaisesRegex(RuntimeError, 'avançando'):
            check(cloud, 'operador', 'test-only', sleep=Mock())
        self.assertFalse(cloud.logged_in)

    def test_real_traffic_is_rejected_and_logs_out(self):
        cloud = FakeCloud(source='live')
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            check(cloud, 'operador', 'test-only', sleep=Mock())
        self.assertFalse(cloud.logged_in)

    def test_unauthenticated_api_must_be_protected(self):
        client = Mock(side_effect=[(200, {'status': 'ok', 'mode': 'cloud'}), (200, {})])
        with self.assertRaisesRegex(RuntimeError, 'esperado 401'):
            check(client, 'operador', 'test-only')
