import tempfile
import unittest
from netsentinel.repositories.database import Database
from netsentinel.repositories.migrate import upgrade_schema
from netsentinel.repositories.store import Repository
from tests.unit.test_packets import arp

NOW = 1_800_000_000.0
TRUSTED = {'10.77.0.1': '02:00:00:00:00:10', '10.77.0.20': '02:00:00:00:00:20'}
LEGIT = arp(2, '02:00:00:00:00:10', '10.77.0.1', '02:00:00:00:00:20', '10.77.0.20')
SPOOF = arp(2, '02:00:00:00:00:30', '10.77.0.1', '02:00:00:00:00:20', '10.77.0.20')


class ArpFrameRepositoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Database('sqlite:///' + temp.name + '/db.sqlite')
        self.addCleanup(self.db.engine.dispose)
        upgrade_schema(self.db.engine)
        self.repo = Repository(self.db)

    def save(self, *items, now=NOW, days=5, rows=20000):
        frames = [dict(timestamp=ts, raw=raw) for ts, raw in items]
        return self.repo.save_arp_frames(frames, 'run-1', 'live', days, rows, now=now)

    def test_identical_frames_are_separate_records(self):
        self.assertEqual(self.save((NOW, SPOOF), (NOW, SPOOF), (NOW, LEGIT)), 3)
        self.assertEqual(len(self.repo.arp_frames(trusted=TRUSTED)), 3)

    def test_prune_by_age(self):
        self.save((NOW - 6 * 86400, LEGIT), (NOW, SPOOF))
        listed = self.repo.arp_frames(trusted=TRUSTED)
        self.assertEqual([f['captured_at'] for f in listed], [NOW])

    def test_prune_by_limit_keeps_newest_ids(self):
        self.save((NOW, LEGIT), (NOW, LEGIT), (NOW, SPOOF), rows=2)
        listed = self.repo.arp_frames(trusted=TRUSTED)
        self.assertEqual(len(listed), 2)
        self.assertTrue(listed[-1]['spoofed'])

    def test_list_is_ascending_after_id_without_raw(self):
        self.save((NOW, LEGIT), (NOW + 1, SPOOF))
        first, second = self.repo.arp_frames(trusted=TRUSTED)
        self.assertLess(first['id'], second['id'])
        self.assertEqual([f['id'] for f in self.repo.arp_frames(after_id=first['id'], trusted=TRUSTED)],
                         [second['id']])
        self.assertNotIn('raw', first)
        self.assertEqual(second['summary'], '10.77.0.1 está em 02:00:00:00:00:30')
        self.assertEqual(second['length'], 60)

    def test_spoofed_only_and_query(self):
        self.save((NOW, LEGIT), (NOW, SPOOF))
        self.assertEqual([f['sender_mac'] for f in self.repo.arp_frames(spoofed_only=True, trusted=TRUSTED)],
                         ['02:00:00:00:00:30'])
        self.assertEqual(len(self.repo.arp_frames(query=':30', trusted=TRUSTED)), 1)
        self.assertEqual(self.repo.arp_frames(query='%', trusted=TRUSTED), [])

    def test_detail_has_hex_layers_and_verdict(self):
        self.save((NOW, SPOOF))
        frame_id = self.repo.arp_frames(trusted=TRUSTED)[0]['id']
        detail = self.repo.arp_frame(frame_id, TRUSTED)
        self.assertEqual(detail['raw_hex'], SPOOF.hex())
        self.assertTrue(detail['verdict']['spoofed'])
        self.assertEqual(detail['layers'][0]['name'], 'Ethernet II')
        self.assertIsNone(self.repo.arp_frame(frame_id + 99, TRUSTED))

    def test_match_returns_latest_before_instant(self):
        self.save((NOW, SPOOF), (NOW + 5, SPOOF), (NOW + 10, SPOOF))
        match = self.repo.match_arp_frame('02:00:00:00:00:30', '10.77.0.1', NOW + 6, TRUSTED)
        self.assertEqual(match['captured_at'], NOW + 5)
        self.assertIsNone(self.repo.match_arp_frame('02:00:00:00:00:30', '10.77.0.1', NOW - 1, TRUSTED))

    def test_manual_prune_returns_removed_count(self):
        self.save((NOW - 10 * 86400, LEGIT), (NOW, SPOOF), days=30)
        self.assertEqual(self.repo.prune_arp_frames(5, 20000, now=NOW), 1)

    def test_cli_prune_confirm_also_prunes_frames_and_dry_run_keeps_them(self):
        import os
        from unittest.mock import patch
        from netsentinel.api.__main__ import main
        self.save((NOW - 6 * 86400, LEGIT), (NOW, SPOOF), days=30)
        env = {'DATABASE_URL': str(self.db.engine.url), 'OPERATOR_USERNAME': 'operator', 'PACKET_RETENTION_DAYS': '5'}
        with patch.dict(os.environ, env), patch('netsentinel.repositories.store.time', return_value=NOW):
            with patch('sys.argv', ['netsentinel.api', 'prune', '--keep-days', '7']):
                main()
            self.assertEqual(len(self.repo.arp_frames()), 2)
            with patch('sys.argv', ['netsentinel.api', 'prune', '--keep-days', '7', '--confirm']):
                main()
        self.assertEqual(len(self.repo.arp_frames()), 1)
