"""#709 operational state/scheduler tests, using actual private files."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_hedgehog import reaper_adapter as adapter
from netbox_hedgehog.secure_ingress import ReaperReport


class ReaperRuntimeTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh709-runtime-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.q = root / 'q'
        self.q.mkdir(mode=0o700)
        self.state_dir = root / 'state'
        self.state_dir.mkdir(mode=0o700)
        forbidden = {}
        for name in adapter._FORBIDDEN:
            path = root / name
            path.mkdir()
            forbidden[name] = path
        self.config = SimpleNamespace(
            quarantine_root=self.q, forbidden_roots=forbidden,
            reaper_uid=os.geteuid(), web_uid=os.geteuid(),
            reaper_mounts=(str(self.q),), quarantine_mount_is_dedicated=True,
            exposes_public_upload=False, unit_route_cap_bytes=10485760,
            **adapter._DEFAULTS)

    def test_real_reap_and_safe_persistent_history(self):
        name = 'b' * 32
        orphan = self.q / name
        orphan.write_text('HH709-SECRET-PAYLOAD')
        orphan.chmod(0o600)
        os.utime(orphan, (100, 100))
        store = adapter._StateStore(self.state_dir)
        scheduler = adapter._Scheduler(self.config, store, history_limit=3)
        state = scheduler.tick(now=108100)
        self.assertFalse(orphan.exists())
        self.assertTrue(state.alerting)
        self.assertEqual(state.history[-1].bound_exceeded_count, 1)
        self.assertTrue(state.history[-1].succeeded)
        text = (self.state_dir / 'health.json').read_text()
        for secret in ('HH709-SECRET-PAYLOAD', name, str(self.q)):
            self.assertNotIn(secret, text)
        before = text
        self.assertIsNone(scheduler.tick(now=108101))
        self.assertEqual((self.state_dir / 'health.json').read_text(), before)
        self.assertFalse(scheduler.tick(now=111700).alerting)
        for index in range(10):
            scheduler.tick(now=115300 + index * 3600)
        self.assertEqual(len(store.load()['history']), 3)
        self.assertEqual(store.load()['history'][-1]['started_at'], 147700)

    def test_preflight_enforces_listener_capacity_without_repair(self):
        for values in ({'body_buffer_size': 10485759},
                       {'max_concurrent_bodies': 0},
                       {'capacity_budget_bytes': 83886079}):
            candidate = SimpleNamespace(**{**vars(self.config), **values})
            with self.subTest(values=values), self.assertRaises(adapter.DeploymentRejected):
                adapter.validate_deployment(candidate)
            self.assertEqual(list(self.q.iterdir()), [])
            self.assertEqual(self.q.stat().st_mode & 0o777, 0o700)

    def test_restart_missed_health_failure_and_recovery(self):
        store = adapter._StateStore(self.state_dir)
        scheduler = adapter._Scheduler(self.config, store)
        self.assertTrue(scheduler.health(now=100).alerting)
        self.assertFalse(scheduler.tick(now=100).alerting)
        restarted = adapter._Scheduler(self.config, adapter._StateStore(self.state_dir))
        self.assertFalse(restarted.health(now=3700).alerting)
        self.assertTrue(restarted.health(now=3761).alerting)
        self.assertFalse(restarted.tick(now=3761).alerting)
        with patch('netbox_hedgehog.secure_ingress.reap_orphans',
                   side_effect=RuntimeError('HH709-DO-NOT-LOG')):
            failed = restarted.tick(now=7361)
        self.assertTrue(failed.alerting)
        self.assertFalse(failed.history[-1].succeeded)
        self.assertNotIn('HH709-DO-NOT-LOG', (self.state_dir / 'health.json').read_text())
        self.assertFalse(restarted.tick(now=10961).alerting)

    def test_started_but_unfinished_run_is_not_clean(self):
        store = adapter._StateStore(self.state_dir)
        scheduler = adapter._Scheduler(self.config, store)
        scheduler.tick(now=100)
        with patch('netbox_hedgehog.secure_ingress.reap_orphans', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                scheduler.tick(now=3700)
        self.assertTrue(adapter._Scheduler(self.config, store).health(now=3701).alerting)

    def test_state_symlink_corruption_and_mode_fail_closed_without_repair(self):
        store = adapter._StateStore(self.state_dir)
        outside = Path(self.temp.name) / 'outside'
        outside.write_text('HH709-SECRET')
        target = self.state_dir / 'health.json'
        target.symlink_to(outside)
        with self.assertRaises(adapter.DeploymentRejected):
            store.load()
        self.assertEqual(outside.read_text(), 'HH709-SECRET')
        target.unlink()
        target.write_text('{invalid HH709-SECRET')
        target.chmod(0o600)
        with self.assertRaises(adapter.DeploymentRejected) as caught:
            store.load()
        self.assertNotIn('HH709-SECRET', str(caught.exception))
        self.state_dir.chmod(0o750)
        with self.assertRaises(adapter.DeploymentRejected):
            adapter._StateStore(self.state_dir)
        self.assertEqual(self.state_dir.stat().st_mode & 0o777, 0o750)

    def test_state_reader_rejects_unknown_fields_and_unbounded_input(self):
        store = adapter._StateStore(self.state_dir)
        adapter._Scheduler(self.config, store).tick(now=100)
        target = self.state_dir / 'health.json'
        state = json.loads(target.read_text())
        state['raw'] = 'HH709-SECRET'
        target.write_text(json.dumps(state))
        with self.assertRaises(adapter.DeploymentRejected):
            store.load()
        target.write_bytes(b' ' * 65537)
        with self.assertRaises(adapter.DeploymentRejected):
            store.load()

    def test_tick_reads_overridden_report_alert_property(self):
        class Loud(ReaperReport):
            @property
            def alert_required(self):
                return True
        store = adapter._StateStore(self.state_dir)
        with patch('netbox_hedgehog.secure_ingress.reap_orphans',
                   return_value=Loud((), 0, False, 0, 0, 0)):
            self.assertTrue(adapter._Scheduler(self.config, store).tick(now=100).alerting)

    def test_interrupted_state_write_is_bounded_and_loud(self):
        store = adapter._StateStore(self.state_dir)
        adapter._Scheduler(self.config, store).tick(now=100)
        pending = self.state_dir / 'health.pending'
        pending.write_text('partial aggregate state')
        pending.chmod(0o600)
        for _ in range(3):
            with self.assertRaises(adapter.DeploymentRejected):
                adapter._Scheduler(self.config, store).tick(now=3700)
        self.assertEqual(pending.read_text(), 'partial aggregate state')
        self.assertEqual({p.name for p in self.state_dir.iterdir()},
                         {'health.pending', 'health.json'})
