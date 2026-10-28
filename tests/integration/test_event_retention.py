import unittest
from unittest.mock import MagicMock, patch
from netsentinel.api.app import create_app
from netsentinel.repositories.database import Database
from netsentinel.repositories.migrate import upgrade_schema
from netsentinel.repositories.store import Repository
from tests.backend_support import settings, snapshot
from tests.security_support import config


class EventRetentionTests(unittest.TestCase):
    def setUp(self):
        self.db = Database('sqlite://')
        self.addCleanup(self.db.engine.dispose)
        upgrade_schema(self.db.engine)
        self.repo = Repository(self.db)
        self.now = [100.0]

    def cloud(self, env=None):
        with patch.dict('os.environ', env or {}):
            app = create_app(settings('sqlite://', mode='cloud'), database=self.db, clock=lambda: self.now[0])
        return app.extensions['pipeline']

    def event_ids(self):
        return [e['event_id'] for e in self.repo.events(0, 500)]

    def test_prune_event_rows_keeps_only_the_newest(self):
        for n in range(5):
            self.repo.append_event(dict(event='snapshot_updated', timestamp=float(n)))
        newest = self.event_ids()[-2:]
        self.assertEqual(self.repo.prune_event_rows(2), 3)
        self.assertEqual(self.event_ids(), newest)
        self.assertEqual(self.repo.prune_event_rows(2), 0)
        with self.assertRaises(ValueError):
            self.repo.prune_event_rows(0)

    def test_cloud_prunes_events_to_the_configured_limit(self):
        pipeline = self.cloud({'EVENT_MAX_ROWS': '3'})
        for _ in range(4):
            self.repo.append_event(dict(event='snapshot_updated'))
        pipeline.consume(snapshot(source='synthetic'))
        self.assertEqual(len(self.event_ids()), 3)

    def test_cloud_prunes_at_most_once_per_minute(self):
        pipeline = self.cloud({'EVENT_MAX_ROWS': '1'})
        pipeline.consume(snapshot(source='synthetic'))
        pipeline.consume(snapshot(source='synthetic', end=16))
        self.assertGreater(len(self.event_ids()), 1)
        self.now[0] += 60
        pipeline.consume(snapshot(source='synthetic', end=24))
        self.assertEqual(len(self.event_ids()), 1)

    def test_cloud_default_limit_is_twenty_thousand(self):
        self.assertEqual(self.cloud().event_max_rows, 20000)

    def test_lab_keeps_events_unless_a_limit_is_set(self):
        import tempfile
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        cfg = config(temp.name, hostonly_interface='enp0s8', hostonly_ip='192.168.56.40',
                     hostonly_cidr='192.168.56.0/24')
        lab = create_app(settings('sqlite://'), cfg, self.db, MagicMock()).extensions['pipeline']
        self.assertIsNone(lab.event_max_rows)
        with patch.dict('os.environ', {'EVENT_MAX_ROWS': '500'}):
            lab = create_app(settings('sqlite://'), cfg, self.db, MagicMock()).extensions['pipeline']
        self.assertEqual(lab.event_max_rows, 500)

    def test_invalid_limit_is_rejected(self):
        for value in ('0', 'abc', '-5'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.cloud({'EVENT_MAX_ROWS': value})
