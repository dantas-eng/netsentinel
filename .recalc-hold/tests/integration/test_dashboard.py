"""Shell e assets reais via Flask; não substitui ensaio no navegador das VMs."""
from html.parser import HTMLParser
import tempfile
import unittest
from unittest.mock import MagicMock
from netsentinel.api.app import create_app
from netsentinel.repositories.database import Database
from netsentinel.repositories.migrate import upgrade_schema
from tests.backend_support import settings, login, snapshot
from tests.security_support import config


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == 'script' and 'src' in data:
            self.urls.append(data['src'])
        if tag == 'link' and data.get('rel') == 'stylesheet':
            self.urls.append(data['href'])


class DashboardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = Database('sqlite://')
        self.addCleanup(db.engine.dispose)
        upgrade_schema(db.engine)
        cfg = config(temp.name, hostonly_interface='enp0s8', hostonly_ip='192.168.56.40',
                     hostonly_cidr='192.168.56.0/24')
        self.app = create_app(settings('sqlite://'), cfg, db, MagicMock())
        self.client = self.app.test_client()

    def test_public_shell_uses_only_served_local_assets_and_keeps_data_private(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.content_type)
        self.assertIn('id="workspace" hidden', response.text)
        parser = Assets()
        parser.feed(response.text)
        self.assertEqual(len(parser.urls), 4)
        for url in parser.urls + ['/static/core.mjs']:
            with self.subTest(url=url):
                self.assertTrue(url.startswith('/static/'))
                asset = self.client.get(url)
                self.assertEqual(asset.status_code, 200)
                self.assertGreater(len(asset.data), 100)
                if url.endswith('.mjs'):
                    self.assertIn('javascript', asset.content_type)
        self.assertEqual(self.client.get('/api/devices').status_code, 401)

    def test_shell_and_authenticated_snapshots_are_not_cached(self):
        login(self.client)
        self.app.extensions['pipeline'].consume(snapshot())
        for url in ['/', '/api/topology', '/api/devices', '/api/events', '/api/audit', '/api/status']:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        home = self.client.get('/')
        self.assertEqual(home.headers['X-Frame-Options'], 'DENY')
        csp = home.headers['Content-Security-Policy']
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp)
        csrf = self.client.get('/api/auth/csrf')
        self.assertIn("default-src 'self'", csrf.headers['Content-Security-Policy'])

    def test_offline_bundles_keep_versions_and_license_notices(self):
        manifest = self.client.get('/static/vendor/versions.json').json
        self.assertEqual(manifest['vis-network'], '10.1.2')
        self.assertEqual(manifest['socket.io-client'], '4.8.3')
        for file in ['vis-network/LICENSE-MIT', 'socket.io-client/LICENSE', 'tailwindcss/LICENSE']:
            self.assertEqual(self.client.get('/static/vendor/licenses/' + file).status_code, 200)
