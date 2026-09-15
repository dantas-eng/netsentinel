import io
import tempfile
import unittest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from netsentinel.repositories.database import Database
from netsentinel.repositories.store import Repository, DomainConflict
from netsentinel.repositories.models import Base
from netsentinel.repositories.migrate import upgrade_schema, migration_config
from netsentinel.analysis.contracts import Reputation
from tests.backend_support import MAC, snapshot


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.url = 'sqlite:///' + self.temp.name + '/db.sqlite'
        self.db = Database(self.url)
        self.addCleanup(self.db.engine.dispose)
        upgrade_schema(self.db.engine)
        self.repo = Repository(self.db)

    def known(self):
        self.repo.save_snapshot(snapshot())
        self.repo.change_reputation(MAC, True, 'operator', 'Reconhecido na VM')

    def test_new_stays_new_after_persisting_and_restart(self):
        self.assertEqual(self.repo.get_reputation(MAC), Reputation.NEW)
        self.repo.save_snapshot(snapshot())
        self.db.engine.dispose()
        reopened = Database(self.url)
        try:
            self.assertEqual(Repository(reopened).get_reputation(MAC), Reputation.NEW)
        finally:
            reopened.engine.dispose()

    def test_confirmation_persists_and_revocation_is_not_overwritten_by_bootstrap(self):
        self.known()
        self.db.engine.dispose()
        reopened = Database(self.url)
        try:
            repo = Repository(reopened)
            self.assertEqual(repo.get_reputation(MAC), Reputation.KNOWN)
            repo.change_reputation(MAC, False, 'operator', 'Revogado')
            repo.bootstrap([MAC], 'operator')
            self.assertEqual(repo.get_reputation(MAC), Reputation.NEW)
            self.assertEqual(len(repo.audits()), 2)
        finally:
            reopened.engine.dispose()

    def test_provider_failure_is_unknown_not_new(self):
        with patch.object(self.db, 'transaction', side_effect=SQLAlchemyError('offline')):
            self.assertEqual(self.repo.get_reputation(MAC), Reputation.UNKNOWN)
            self.assertIsNone(self.repo.get_baseline_bps(MAC))

    def test_baseline_converts_each_window_bytes_to_bytes_per_second(self):
        self.known()
        self.repo.start_calibration(MAC, 'operator', 'capture-1', 8)
        for index, count in enumerate([80, 160, 240, 320, 400]):
            self.repo.collect_calibration(snapshot(end=16+index*8, count=count))
        self.assertEqual(self.repo.get_baseline_bps(MAC), 30.0)
        samples = self.repo.calibrations(MAC)[0]['samples']
        self.assertEqual([s['bytes_per_second'] for s in samples], [10, 20, 30, 40, 50])
        self.assertEqual(samples[2]['bytes'], 240)
        reopened = Database(self.url)
        try:
            self.assertEqual(Repository(reopened).get_baseline_bps(MAC), 30)
        finally:
            reopened.engine.dispose()

    def test_baseline_frozen_until_five_new_samples_finish(self):
        self.known()
        self.repo.start_calibration(MAC, 'operator', 'capture-1', 8)
        for end in (16,24,32,40,48):
            self.repo.collect_calibration(snapshot(end=end,count=80))
        self.repo.collect_calibration(snapshot(end=56,count=8000))
        self.assertEqual(self.repo.get_baseline_bps(MAC), 10)
        self.repo.start_calibration(MAC, 'operator', 'capture-1', 56)
        for end in (64,72,80,88):
            self.repo.collect_calibration(snapshot(end=end,count=800))
        self.assertEqual(self.repo.get_baseline_bps(MAC), 10)
        self.repo.collect_calibration(snapshot(end=96,count=800))
        self.assertEqual(self.repo.get_baseline_bps(MAC), 100)

    def test_zero_median_is_unavailable(self):
        self.known()
        self.repo.start_calibration(MAC, 'operator', 'capture-1', 8)
        for end in (16,24,32,40,48):
            self.repo.collect_calibration(snapshot(end=end,count=0))
        self.assertIsNone(self.repo.get_baseline_bps(MAC))
        self.assertEqual(self.repo.calibrations(MAC)[0]['status'], 'completed')

    def test_overlap_warmup_incomplete_and_conflict_do_not_count(self):
        self.known()
        self.repo.start_calibration(MAC, 'operator', 'capture-1', 8)
        self.repo.collect_calibration(snapshot(end=16))
        self.repo.collect_calibration(snapshot(end=17))
        self.repo.collect_calibration(snapshot(end=24,incomplete=True))
        self.repo.collect_calibration(snapshot(end=24,warming_up=True))
        claims = [dict(ip='192.0.2.1',claimed_mac='a'),dict(ip='192.0.2.1',claimed_mac='b')]
        self.repo.collect_calibration(snapshot(end=24,arp_claims=claims))
        self.assertEqual(len(self.repo.calibrations(MAC)[0]['samples']), 1)
        self.repo.collect_calibration(snapshot(end=24))
        self.assertEqual(len(self.repo.calibrations(MAC)[0]['samples']), 2)

    def test_new_device_cannot_calibrate_or_start_twice(self):
        self.repo.save_snapshot(snapshot())
        with self.assertRaises(DomainConflict):
            self.repo.start_calibration(MAC,'operator','capture-1',8)
        self.known()
        self.repo.start_calibration(MAC,'operator','capture-1',8)
        with self.assertRaises(DomainConflict):
            self.repo.start_calibration(MAC,'operator','capture-1',8)

    def test_new_source_run_interrupts_calibration(self):
        self.known()
        self.repo.start_calibration(MAC,'operator','capture-1',8)
        self.repo.collect_calibration(snapshot(end=16,run_id='capture-2'))
        self.assertEqual(self.repo.calibrations(MAC)[0]['status'],'interrupted')

    def test_revocation_cancels_calibration(self):
        self.known()
        self.repo.start_calibration(MAC,'operator','capture-1',8)
        self.repo.change_reputation(MAC,False,'operator','Removido')
        self.assertEqual(self.repo.calibrations(MAC)[0]['status'],'cancelled')

    def test_migrations_match_models_and_repeat_without_changes(self):
        upgrade_schema(self.db.engine)
        with self.db.engine.connect() as connection:
            differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
            self.assertEqual(differences, [])

    def test_initial_migration_compiles_for_postgres_without_a_live_database(self):
        cfg = migration_config()
        cfg.set_main_option('sqlalchemy.url', 'postgresql+psycopg://test:test@localhost/test')
        cfg.output_buffer = io.StringIO()
        command.upgrade(cfg, 'head', sql=True)
        sql = cfg.output_buffer.getvalue()
        self.assertIn('CREATE TABLE baselines',sql)
        self.assertIn('CREATE TABLE calibrations',sql)

    def _risk(self, mac, score, classification='suspeito', timestamp=1.0):
        return self.repo.append_event(dict(
            event='risk_evaluated', timestamp=timestamp,
            devices={mac: dict(score=score, classification=classification)}))

    def test_risk_history_extracts_series_asc_and_skips_unusable_points(self):
        other = '02:00:00:00:00:21'
        first = self._risk(MAC, 10, 'confiável', timestamp=10)
        self.repo.append_event(dict(event='mitigation_applied', timestamp=11,
                                    devices={MAC: dict(score=99, classification='suspeito')}))
        self._risk(MAC, None, None, timestamp=12)
        self.repo.append_event(dict(event='risk_evaluated', timestamp=13, devices={MAC: 'ignored'}))
        self._risk(other, 80, 'suspeito', timestamp=14)
        second = self._risk(MAC, 40, 'desconhecido', timestamp=15)
        third = self._risk(MAC, 90, 'suspeito', timestamp=16)
        history = self.repo.risk_history(MAC, limit=100)
        self.assertEqual([item['event_id'] for item in history],
                         [first['event_id'], second['event_id'], third['event_id']])
        self.assertEqual([item['score'] for item in history], [10, 40, 90])
        self.assertEqual([item['classification'] for item in history],
                         ['confiável', 'desconhecido', 'suspeito'])
        self.assertEqual([item['timestamp'] for item in history], [10, 15, 16])
        newest = self.repo.risk_history(MAC, limit=2)
        self.assertEqual([item['event_id'] for item in newest],
                         [second['event_id'], third['event_id']])
        with self.assertRaises(ValueError):
            self.repo.risk_history('not-a-mac')
