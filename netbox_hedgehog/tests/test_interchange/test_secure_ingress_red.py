"""#701 RED-only secure raw-ingress, quarantine, and isolated-reaper contract.

The tests deliberately name no upload URL, multipart parser, Django FileField,
model, storage backend, migration, or deployment unit.  They describe the
accepted #686 seam only: bounded raw bytes -> private filesystem quarantine ->
decode/validate/atomic commit -> terminal delete, with an isolated reaper for
hard-loss orphans.  Every feature claim is an expected failure until a distinct
#678 GREEN change supplies the production seam.  Passing controls below use a
real private temporary filesystem and a killed child process now, so audits or
mocks can never stand in for storage/process evidence.
"""

from __future__ import annotations

import importlib.util
import os
import signal
import stat
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from netbox_hedgehog.models.interchange import (
    InterchangeAudit,
    InterchangeCatalogVersion,
    InterchangeDesignRevision,
    InterchangeProvenance,
)

from netbox_hedgehog.tests.test_interchange.secure_ingress_red_support import (
    IngressTestConfig,
    INGRESS_RED_INVENTORY,
    PRODUCTION_MODULE,
    REQUIRED_ENTRY_POINTS,
    SecureIngressAbsent,
    T3_INGRESS_ROWS,
    direct_entries,
    entry_kind,
    launch_writer,
    require_secure_ingress,
)


# These values are intentionally awkward fixture inputs, not product defaults.
# #701 requires the lead to approve shipped ingress cap/grace/skew/health
# values separately; a future implementation must accept controlled values.
TEST_CAP_BYTES = 97
TEST_ACTIVE_WRITE_GRACE_SECONDS = 13
TEST_CLOCK_SKEW_SECONDS = 5
TEST_REAPER_INTERVAL_SECONDS = 60 * 60
TEST_ORPHAN_BOUND_SECONDS = 24 * 60 * 60
TEST_HEALTH_FAILURE_THRESHOLD = 2
SENTINEL = b"HH701_RAW_BYTES_MUST_NOT_SURVIVE"


@dataclass(frozen=True)
class RedRow:
    identifier: str
    method: str
    claim: str


RED_ROWS = (
    RedRow("R01", "test_r01_private_quarantine_configuration", "private Q config"),
    RedRow("R02", "test_r02_identifiers_are_server_opaque", "opaque identifiers"),
    RedRow("R03", "test_r03_raw_bounded_stream", "raw bounded stream"),
    RedRow("R04", "test_r04_q_is_first_artifact_and_success_deletes", "Q custody"),
    RedRow("R05", "test_r05_every_handled_failure_deletes_q", "terminal cleanup"),
    RedRow("R06", "test_r06_filesystem_no_follow_contract", "filesystem safety"),
    RedRow("R07", "test_r07_atomic_commit_and_failure_audit", "atomic core/audit"),
    RedRow("R08", "test_r08_abrupt_loss_orphan_contract", "hard-loss orphan"),
    RedRow("R09", "test_r09_clock_and_schedule_are_configurable", "time contract"),
    RedRow("R10", "test_r10_reaper_idempotence_race_health", "reaper behavior"),
    RedRow("R11", "test_r11_unit_listener_shapes", "Unit regression"),
    RedRow("R12", "test_r12_t3_secret_absence_and_audit_presence", "T3 evidence"),
)


def ingress_red(row: str):
    """Mark a claim as expected failure and retain a machine-readable row id."""
    def decorate(method):
        method._ingress_red_row = row
        wrapped = unittest.expectedFailure(method)
        wrapped._ingress_red_row = row
        return wrapped
    return decorate


class RawRequest:
    """A stream-only request fixture: full-body access is deliberately poison."""

    def __init__(self, payload: bytes, metadata: dict[str, str]):
        self._payload = payload
        self.metadata = metadata
        self.read_sizes: list[int] = []

    @property
    def body(self):
        raise AssertionError("raw ingress must not access request.body")

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if size < 0:
            raise AssertionError("raw ingress must not request an unbounded read")
        result, self._payload = self._payload[:size], self._payload[size:]
        return result


class SecureIngressRedContract(TestCase):
    """Expected failures that become ordinary tests only in #678 GREEN."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hh701-")
        root = Path(self.temp.name)
        self.config = IngressTestConfig(
            quarantine_root=root / "quarantine",
            media_root=root / "media",
            static_root=root / "static",
            scripts_root=root / "scripts",
            reports_root=root / "reports",
            default_storage_root=root / "default-storage",
            ordinary_temp_root=root / "tmp",
            application_root=root / "application",
            max_raw_bytes=TEST_CAP_BYTES,
            active_write_grace_seconds=TEST_ACTIVE_WRITE_GRACE_SECONDS,
            clock_skew_seconds=TEST_CLOCK_SKEW_SECONDS,
            reaper_interval_seconds=TEST_REAPER_INTERVAL_SECONDS,
            orphan_bound_seconds=TEST_ORPHAN_BOUND_SECONDS,
            health_failure_threshold=TEST_HEALTH_FAILURE_THRESHOLD,
        )
        for path in self.config.__dict__.values():
            if isinstance(path, Path):
                path.mkdir(mode=0o700)

    def tearDown(self):
        self.temp.cleanup()

    @ingress_red("R01")
    def test_r01_private_quarantine_configuration(self):
        api = require_secure_ingress()
        store = api.QuarantineStore(self.config)
        self.assertTrue(store.validate_private_root())
        self.assertEqual(stat.S_IMODE(os.stat(self.config.quarantine_root).st_mode), 0o700)
        self.assertFalse(store.is_web_accessible())

    @ingress_red("R02")
    def test_r02_identifiers_are_server_opaque(self):
        api = require_secure_ingress()
        request = RawRequest(SENTINEL, {
            "filename": "../../client-name.yaml",
            "media_type": "text/plain; HH701_CLIENT_TYPE",
            "request_id": "HH701_CLIENT_REQUEST_ID",
        })
        receipt = api.ingest_raw(request, content_length=len(SENTINEL), config=self.config)
        self.assertNotIn("client-name", receipt.quarantine_id)
        self.assertNotIn("HH701_CLIENT", str(receipt))
        self.assertRegex(receipt.quarantine_id, r"^[a-f0-9-]+$")

    @ingress_red("R03")
    def test_r03_raw_bounded_stream(self):
        api = require_secure_ingress()
        request = RawRequest(SENTINEL, {"filename": "HH701_CLIENT_NAME"})
        api.ingest_raw(request, content_length=len(SENTINEL), config=self.config)
        self.assertTrue(request.read_sizes)
        self.assertTrue(all(0 <= size <= TEST_CAP_BYTES for size in request.read_sizes))
        self.assertNotIn(-1, request.read_sizes)
        with self.assertRaises(api.LengthRejected) as missing:
            api.ingest_raw(RawRequest(SENTINEL, {}), content_length=None, config=self.config)
        self.assertIsNone(getattr(missing.exception, "source_location", None))
        with self.assertRaises(api.LengthRejected) as mismatched:
            api.ingest_raw(RawRequest(SENTINEL, {}), content_length=len(SENTINEL) + 1, config=self.config)
        self.assertIsNone(getattr(mismatched.exception, "source_location", None))

    @ingress_red("R04")
    def test_r04_q_is_first_artifact_and_success_deletes(self):
        api = require_secure_ingress()
        result = api.ingest_raw(RawRequest(SENTINEL, {}), content_length=len(SENTINEL), config=self.config)
        self.assertEqual(result.first_durable_artifact, "quarantine")
        self.assertEqual(direct_entries(self.config.quarantine_root), {})
        self.assertIsNone(result.fetch_url)

    @ingress_red("R05")
    def test_r05_every_handled_failure_deletes_q(self):
        api = require_secure_ingress()
        for phase in ("decode", "validation", "commit"):
            with self.subTest(phase=phase):
                result = api.ingest_raw(
                    RawRequest(SENTINEL, {}), content_length=len(SENTINEL),
                    config=self.config, force_failure=phase)
                self.assertEqual(
                    result.first_durable_artifact,
                    "quarantine",
                    f"{phase}: cleanup is only meaningful after a real Q write",
                )
                self.assertEqual(direct_entries(self.config.quarantine_root), {})
                self.assertTrue(result.cleanup_idempotent)

    @ingress_red("R06")
    def test_r06_filesystem_no_follow_contract(self):
        api = require_secure_ingress()
        store = api.QuarantineStore(self.config)
        created = store.write_raw(SENTINEL)
        self.assertEqual(stat.S_IMODE(os.stat(self.config.quarantine_root).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.lstat(created.path).st_mode), 0o600)
        outside = Path(self.temp.name) / "outside"
        outside.write_bytes(SENTINEL)
        (self.config.quarantine_root / "link").symlink_to(outside)
        os.link(outside, self.config.quarantine_root / "hard")
        with self.assertRaises(api.UnsafeQuarantineEntry):
            store.open_existing("link")
        with self.assertRaises(api.UnsafeQuarantineEntry):
            store.open_existing("hard")
        self.assertEqual(set(direct_entries(self.config.quarantine_root)), {"hard", "link"})

    @ingress_red("R07")
    def test_r07_atomic_commit_and_failure_audit(self):
        api = require_secure_ingress()
        result = api.ingest_raw(
            RawRequest(SENTINEL, {}), content_length=len(SENTINEL), config=self.config,
            force_failure="commit")
        self.assertFalse(InterchangeDesignRevision.objects.exists())
        self.assertFalse(InterchangeCatalogVersion.objects.exists())
        self.assertFalse(InterchangeProvenance.objects.exists())
        self.assertFalse(InterchangeAudit.objects.filter(outcome="success").exists())
        failure = InterchangeAudit.objects.get(outcome="ui-import-failed")
        self.assertNotIn(SENTINEL.decode(), str(failure.payload))
        self.assertEqual(direct_entries(self.config.quarantine_root), {})

    @ingress_red("R08")
    def test_r08_abrupt_loss_orphan_contract(self):
        api = require_secure_ingress()
        child = launch_writer(self.config.quarantine_root / "orphan", SENTINEL)
        self.assertEqual(child.stdout.readline().strip(), "Q-WRITTEN")
        child.kill()
        self.assertEqual(child.wait(timeout=5), -signal.SIGKILL)
        now = 1_000_000
        os.utime(
            self.config.quarantine_root / "orphan",
            (now - TEST_ORPHAN_BOUND_SECONDS - TEST_CLOCK_SKEW_SECONDS - 1,) * 2,
        )
        api.reap_orphans(config=self.config, now=now)
        self.assertFalse((self.config.quarantine_root / "orphan").exists())

    @ingress_red("R09")
    def test_r09_clock_and_schedule_are_configurable(self):
        api = require_secure_ingress()
        schedule = api.reaper_schedule(self.config)
        self.assertEqual(schedule.interval_seconds, TEST_REAPER_INTERVAL_SECONDS)
        self.assertEqual(schedule.orphan_bound_seconds, TEST_ORPHAN_BOUND_SECONDS)
        self.assertEqual(schedule.active_write_grace_seconds, TEST_ACTIVE_WRITE_GRACE_SECONDS)
        self.assertEqual(schedule.clock_skew_seconds, TEST_CLOCK_SKEW_SECONDS)

    @ingress_red("R10")
    def test_r10_reaper_idempotence_race_health(self):
        api = require_secure_ingress()
        now = 1_000_000
        orphan = self.config.quarantine_root / "old"
        orphan.write_bytes(SENTINEL)
        os.utime(
            orphan,
            (now - TEST_ORPHAN_BOUND_SECONDS - TEST_CLOCK_SKEW_SECONDS - 1,) * 2,
        )
        active = launch_writer(self.config.quarantine_root / "active", SENTINEL)
        self.assertEqual(active.stdout.readline().strip(), "Q-WRITTEN")
        try:
            report1 = api.reap_orphans(config=self.config, now=now)
            report2 = api.reap_orphans(config=self.config, now=now)
        finally:
            active.kill()
            active.wait(timeout=5)
        self.assertFalse(orphan.exists())
        self.assertTrue((self.config.quarantine_root / "active").exists())
        self.assertEqual(report2.removed, ())
        self.assertNotIn(SENTINEL.decode(), str(report1))
        self.assertLessEqual(report1.oldest_orphan_seconds, TEST_ORPHAN_BOUND_SECONDS)

    @ingress_red("R11")
    def test_r11_unit_listener_shapes(self):
        api = require_secure_ingress()
        probe = api.listener_regression_probe(config=self.config, unit_version="1.34.2")
        self.assertEqual(probe.accepted.status, 200)
        self.assertEqual(probe.oversize.status, 413)
        self.assertEqual(probe.chunked.status, 411)
        self.assertFalse(probe.listener_regular_body_artifact)
        self.assertFalse(probe.listener_rejections_created_application_audit)

    @ingress_red("R12")
    def test_r12_t3_secret_absence_and_audit_presence(self):
        api = require_secure_ingress()
        evidence = api.t3_evidence(config=self.config, sentinel=SENTINEL.decode())
        self.assertEqual(set(evidence.rows), set(T3_INGRESS_ROWS))
        self.assertFalse(evidence.secret_or_raw_content_found)
        self.assertTrue(evidence.required_failure_audit_present)


class SecureIngressRedControls(SimpleTestCase):
    """Green controls proving the RED observer fixtures are real, not mocked."""

    def test_red_phase_has_no_secure_ingress_production_module(self):
        self.assertIsNone(importlib.util.find_spec(PRODUCTION_MODULE))

    def test_matrix_accounts_for_every_expected_feature_claim(self):
        methods = {
            name: getattr(SecureIngressRedContract, name)
            for name in dir(SecureIngressRedContract)
            if name.startswith("test_")
        }
        self.assertEqual({row.identifier for row in RED_ROWS}, {
            method._ingress_red_row for method in methods.values()
            if hasattr(method, "_ingress_red_row")
        })
        for row in RED_ROWS:
            self.assertTrue(getattr(methods[row.method], "__unittest_expecting_failure__", False))

    def test_t3_inventory_is_machine_accounted_by_red_rows(self):
        row_ids = {row.identifier for row in RED_ROWS}
        expected = {
            "web_raw_ingress", "quarantine_filesystem", "cleanup", "isolated_reaper",
            "unit_access_error_logs", "container_logs", "interchange_audit",
            "exception_logging", "media_default_storage",
        }
        self.assertEqual(set(T3_INGRESS_ROWS), expected)
        self.assertEqual({path.name for path in INGRESS_RED_INVENTORY.paths}, {
            "web raw ingress", "quarantine filesystem", "terminal cleanup", "isolated reaper",
            "Unit access/error logs", "container logs", "InterchangeAudit", "exception/logging",
            "media/default storage",
        })
        self.assertEqual({path.status for path in INGRESS_RED_INVENTORY.paths}, {"unverified"})
        self.assertTrue({row for row, _detail in T3_INGRESS_ROWS.values()} <= row_ids)

    def test_real_private_directory_and_no_follow_observer(self):
        with tempfile.TemporaryDirectory(prefix="hh701-control-") as temp:
            root = Path(temp) / "q"
            root.mkdir(mode=0o700)
            payload = Path(temp) / "outside"
            payload.write_bytes(SENTINEL)
            regular = root / "regular"
            regular.write_bytes(SENTINEL)
            link = root / "link"
            link.symlink_to(payload)
            hard = root / "hard"
            os.link(payload, hard)
            fifo = root / "fifo"
            os.mkfifo(fifo)
            observed = direct_entries(root)
            self.assertEqual(stat.S_IMODE(os.stat(root).st_mode), 0o700)
            self.assertEqual(entry_kind(observed["regular"].st_mode), "regular")
            self.assertEqual(entry_kind(observed["link"].st_mode), "symlink")
            self.assertGreaterEqual(observed["hard"].st_nlink, 2)
            self.assertEqual(entry_kind(observed["fifo"].st_mode), "other")

    def test_real_abrupt_process_control_leaves_observable_orphan(self):
        with tempfile.TemporaryDirectory(prefix="hh701-child-") as temp:
            entry = Path(temp) / "q-entry"
            child = launch_writer(entry, SENTINEL)
            try:
                self.assertEqual(child.stdout.readline().strip(), "Q-WRITTEN")
                self.assertTrue(entry.is_file())
                self.assertEqual(entry.read_bytes(), SENTINEL)
                child.kill()
                self.assertEqual(child.wait(timeout=5), -signal.SIGKILL)
                self.assertTrue(entry.exists(), "a killed writer cannot clean up its own Q entry")
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
