"""#705 RED contract for the deployable isolated reaper adapter.

Test-only. No deployment adapter, Compose file, CI change, public route, UI,
multipart surface, or `secure_ingress` behaviour change is added here.

#703 merged the internal quarantine service and proved its deployment shape in
a lane that was deleted afterwards. Everything that lane demonstrated -- a
non-root reaper identity matching the Q owner, a Q-only mount, a pinned Unit
cap that does not spool, a health signal when a run is missed -- is currently
an assumption. This module turns each into a row that fails until an adapter
satisfies it.

Structure mirrors #701, which worked: twelve expected-failure rows against one
named seam, plus controls that pass today and prove the observers are real.
Two things are added from reviewing #701/#703, because both were found there
the hard way:

* a vacuity control that installs a permissive stub and requires every row to
  keep failing, so no row can go green against a do-nothing adapter;
* a guard that lane evidence alone cannot upgrade the T3 inventory.
"""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from netbox_hedgehog.tests.test_interchange.reaper_adapter_red_support import (
    ADAPTER_MODULE,
    DEPLOYMENT_EVIDENCE_ROWS,
    FORBIDDEN_REAPER_MOUNTS,
    REQUIRED_ENTRY_POINTS,
    V1_DEFAULTS,
    AdapterAbsent,
    AdapterRow,
    DeploymentFixture,
    directory_identity,
    read_self_mounts,
    require_reaper_adapter,
    run_as_child,
)
from netbox_hedgehog.tests.test_interchange.secure_ingress_red_support import (
    INGRESS_RED_INVENTORY,
)


TEST_WEB_UID = 999
TEST_REAPER_UID = 999
TEST_UNIT_CAP_BYTES = 10 * 1024 * 1024


ADAPTER_ROWS = (
    AdapterRow("A01", "test_a01_distinct_execution_identities", "web/reaper identities", "spec"),
    AdapterRow("A02", "test_a02_reaper_mounts_quarantine_only", "Q-only mount", "spec"),
    AdapterRow("A03", "test_a03_cap_mismatch_is_rejected", "raw cap vs Unit cap", "validation"),
    AdapterRow("A04", "test_a04_unsafe_derived_eligibility_is_rejected", "eligibility safety", "validation"),
    AdapterRow("A05", "test_a05_quarantine_under_prohibited_root_is_rejected", "Q placement", "validation"),
    AdapterRow("A06", "test_a06_identity_mismatch_is_rejected", "Q mode/owner, reaper uid", "validation"),
    AdapterRow("A07", "test_a07_validation_never_mutates_the_deployment", "non-mutating preflight", "validation"),
    AdapterRow("A08", "test_a08_scheduled_run_consumes_alert_required", "alert_required is the interface", "schedule"),
    AdapterRow("A09", "test_a09_missed_run_is_distinct_from_a_clean_report", "missed != clean", "schedule"),
    AdapterRow("A10", "test_a10_first_missed_run_signals_before_the_bound", "signal before 24h", "health"),
    AdapterRow("A11", "test_a11_health_record_is_bounded_and_safe", "safe bounded history", "health"),
    AdapterRow("A12", "test_a12_lane_harness_is_not_shipped_configuration", "lane harness is lane-only", "harness"),
)

#: Requirement areas from #705, so a dropped area fails accounting rather than
#: going unnoticed.
REQUIREMENT_AREAS = ("spec", "validation", "schedule", "health", "harness")

SENTINEL = "HH705_RAW_MUST_NOT_REACH_HEALTH"


def adapter_red(row: str):
    """Mark a claim expected-failure, retaining a machine-readable row id."""
    def decorate(method):
        method._adapter_red_row = row
        wrapped = unittest.expectedFailure(method)
        wrapped._adapter_red_row = row
        return wrapped
    return decorate


class ReaperAdapterRedContract(SimpleTestCase):
    """Expected failures that become ordinary tests only in #705 GREEN.

    SimpleTestCase deliberately: every claim here is about deployment shape,
    configuration, and process state. A row needing the database would be a
    sign the adapter had grown responsibilities that belong to the service.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hh705-")
        root = Path(self.temp.name)
        self.forbidden = {}
        for name in FORBIDDEN_REAPER_MOUNTS:
            path = root / name
            path.mkdir(mode=0o700)
            self.forbidden[name] = path
        quarantine = root / "secure-quarantine"
        quarantine.mkdir(mode=0o700)
        self.fixture = DeploymentFixture(
            quarantine_root=quarantine,
            web_uid=TEST_WEB_UID,
            reaper_uid=TEST_REAPER_UID,
            reaper_mounts=(str(quarantine),),
            forbidden_roots=self.forbidden,
            unit_route_cap_bytes=TEST_UNIT_CAP_BYTES,
            max_raw_bytes=V1_DEFAULTS["max_raw_bytes"],
            active_write_grace_seconds=V1_DEFAULTS["active_write_grace_seconds"],
            clock_skew_seconds=V1_DEFAULTS["clock_skew_seconds"],
            reaper_interval_seconds=V1_DEFAULTS["reaper_interval_seconds"],
            orphan_bound_seconds=V1_DEFAULTS["orphan_bound_seconds"],
        )

    def tearDown(self):
        self.temp.cleanup()

    def replaced(self, **changes):
        from dataclasses import replace
        return replace(self.fixture, **changes)

    # --- 1. declarative reference adapter specification -------------------

    @adapter_red("A01")
    def test_a01_distinct_execution_identities(self):
        api = require_reaper_adapter()
        spec = api.AdapterSpec(self.fixture)
        self.assertEqual(spec.reaper_uid, TEST_REAPER_UID)
        self.assertNotEqual(spec.reaper_uid, 0)
        self.assertEqual(spec.reaper_uid, spec.quarantine_owner_uid)
        self.assertNotEqual(spec.web_service_name, spec.reaper_service_name)

    @adapter_red("A02")
    def test_a02_reaper_mounts_quarantine_only(self):
        api = require_reaper_adapter()
        spec = api.AdapterSpec(self.fixture)
        self.assertEqual(tuple(spec.reaper_mount_points), (str(self.fixture.quarantine_root),))
        for name in FORBIDDEN_REAPER_MOUNTS:
            with self.subTest(mount=name):
                self.assertNotIn(str(self.forbidden[name]), spec.reaper_mount_points)

    # --- 2. startup/preflight validation ----------------------------------

    @adapter_red("A03")
    def test_a03_cap_mismatch_is_rejected(self):
        api = require_reaper_adapter()
        api.validate_deployment(self.fixture)
        mismatched = self.replaced(max_raw_bytes=TEST_UNIT_CAP_BYTES + 1)
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(mismatched)

    @adapter_red("A04")
    def test_a04_unsafe_derived_eligibility_is_rejected(self):
        """bound <= cadence + skew + grace leaves no safe window."""
        api = require_reaper_adapter()
        unsafe = self.replaced(
            orphan_bound_seconds=(self.fixture.reaper_interval_seconds
                                  + self.fixture.clock_skew_seconds
                                  + self.fixture.active_write_grace_seconds))
        self.assertLessEqual(unsafe.derived_eligibility_seconds,
                             unsafe.active_write_grace_seconds)
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(unsafe)

    @adapter_red("A05")
    def test_a05_quarantine_under_prohibited_root_is_rejected(self):
        api = require_reaper_adapter()
        for name, root in self.forbidden.items():
            with self.subTest(root=name):
                nested = root / "secure-quarantine"
                nested.mkdir(mode=0o700)
                with self.assertRaises(api.DeploymentRejected):
                    api.validate_deployment(self.replaced(quarantine_root=nested))

    @adapter_red("A06")
    def test_a06_identity_mismatch_is_rejected(self):
        api = require_reaper_adapter()
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(self.replaced(reaper_uid=0))
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(self.replaced(reaper_uid=TEST_WEB_UID + 1))
        self.fixture.quarantine_root.chmod(0o750)
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(self.fixture)

    @adapter_red("A07")
    def test_a07_validation_never_mutates_the_deployment(self):
        """Preflight reports; it does not repair.

        A validator that chmods or creates its way to a passing state would
        hide the misconfiguration it exists to surface, and would do so with
        more privilege than the adapter should hold.
        """
        api = require_reaper_adapter()
        before = directory_identity(self.fixture.quarantine_root)
        bad = self.replaced(reaper_uid=0)
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(bad)
        self.assertEqual(directory_identity(self.fixture.quarantine_root), before)
        missing = self.fixture.quarantine_root.parent / "absent-root"
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(self.replaced(quarantine_root=missing))
        self.assertFalse(missing.exists(), "validation must not create the root it checks")

    # --- 3. scheduled invocation ------------------------------------------

    @adapter_red("A08")
    def test_a08_scheduled_run_consumes_alert_required(self):
        """The adapter reads the report's own verdict rather than re-deriving it."""
        api = require_reaper_adapter()
        from netbox_hedgehog.secure_ingress import ReaperReport

        quiet = ReaperReport((), 0, False, 0, 0, 0)
        breached = ReaperReport(("a" * 32,), 0, False, 0, 1, 108000)
        incident = ReaperReport((), 777, True, 1, 0, 777)

        self.assertIs(api.run_scheduled_reap(self.fixture, report=quiet).alerting, False)
        self.assertIs(api.run_scheduled_reap(self.fixture, report=breached).alerting, True)
        self.assertIs(api.run_scheduled_reap(self.fixture, report=incident).alerting, True)
        for report in (quiet, breached, incident):
            with self.subTest(report=report):
                self.assertIs(
                    api.run_scheduled_reap(self.fixture, report=report).alerting,
                    report.alert_required,
                    "adapter must consume ReaperReport.alert_required, not reimplement it")

    @adapter_red("A09")
    def test_a09_missed_run_is_distinct_from_a_clean_report(self):
        """A reaper that never ran is not a reaper that found nothing."""
        api = require_reaper_adapter()
        from netbox_hedgehog.secure_ingress import ReaperReport

        clean = api.run_scheduled_reap(self.fixture, report=ReaperReport((), 0, False, 0, 0, 0))
        missed = api.run_scheduled_reap(self.fixture, report=None, missed=True)
        self.assertIs(clean.alerting, False)
        self.assertIs(missed.alerting, True)
        self.assertNotEqual(clean.state, missed.state)

    # --- 4. health signal and record --------------------------------------

    @adapter_red("A10")
    def test_a10_first_missed_run_signals_before_the_bound(self):
        """One missed cadence must alert, not the twenty-fourth.

        Waiting for the bound itself to be breached would make the signal
        useless: by then an artifact has already outlived the policy.
        """
        api = require_reaper_adapter()
        state = api.health_state(self.fixture, missed_runs=1,
                                 seconds_since_success=self.fixture.reaper_interval_seconds * 2)
        self.assertIs(state.alerting, True)
        self.assertLess(state.seconds_since_success, self.fixture.orphan_bound_seconds)

    @adapter_red("A11")
    def test_a11_health_record_is_bounded_and_safe(self):
        api = require_reaper_adapter()
        from netbox_hedgehog.secure_ingress import ReaperReport

        report = ReaperReport((SENTINEL,), 777, True, 1, 1, 108000)
        state = api.health_state(self.fixture, last_report=report)
        rendered = str(state)
        self.assertNotIn(SENTINEL, rendered)
        self.assertNotIn(str(self.fixture.quarantine_root), rendered)
        self.assertLessEqual(len(state.history), state.history_limit)
        self.assertGreater(state.history_limit, 0)

    # --- 5. lane-only harness ---------------------------------------------

    @adapter_red("A12")
    def test_a12_lane_harness_is_not_shipped_configuration(self):
        api = require_reaper_adapter()
        harness = api.lane_harness_spec(self.fixture)
        self.assertIs(harness.is_lane_only, True)
        self.assertEqual(harness.unit_route_cap_bytes, TEST_UNIT_CAP_BYTES)
        self.assertEqual(set(harness.required_observations),
                         {"accepted_raw", "oversize_413", "chunked_411",
                          "no_listener_spool", "uid_isolation", "no_public_upload_route"})
        self.assertIs(harness.exposes_public_upload, False)


class ReaperAdapterRedControls(SimpleTestCase):
    """Controls that pass today, proving the RED rows are honest."""

    def test_red_phase_has_no_adapter_module(self):
        with self.assertRaises(AdapterAbsent) as caught:
            require_reaper_adapter()
        self.assertIn(ADAPTER_MODULE, str(caught.exception))

    def test_every_row_is_accounted_and_expected_to_fail(self):
        methods = {name: getattr(ReaperAdapterRedContract, name)
                   for name in dir(ReaperAdapterRedContract) if name.startswith("test_")}
        declared = {row.method for row in ADAPTER_ROWS}
        tagged = {name for name, method in methods.items()
                  if hasattr(method, "_adapter_red_row")}
        self.assertEqual(declared, tagged, "every row must be declared and tagged exactly once")
        self.assertEqual(len({row.identifier for row in ADAPTER_ROWS}), len(ADAPTER_ROWS))
        for row in ADAPTER_ROWS:
            with self.subTest(row=row.identifier):
                self.assertTrue(getattr(methods[row.method],
                                        "__unittest_expecting_failure__", False))

    def test_every_requirement_area_has_at_least_one_row(self):
        covered = {row.requirement for row in ADAPTER_ROWS}
        self.assertEqual(covered, set(REQUIREMENT_AREAS))

    def test_declared_entry_points_cover_every_api_reference(self):
        """A short declaration turns 'seam absent' into AttributeError at GREEN."""
        import re
        source = Path(__file__).read_text(encoding="utf-8")
        used = set(re.findall(r"api\.([A-Za-z_]\w*)", source))
        self.assertEqual(used - set(REQUIRED_ENTRY_POINTS), set())
        self.assertEqual(set(REQUIRED_ENTRY_POINTS) - used, set())

    def test_no_row_passes_against_a_permissive_adapter_stub(self):
        """The control #701 lacked until review: rows must demand behaviour.

        A row that goes green against a MagicMock would go green against an
        adapter that does nothing, which is precisely the evidence #678 must
        not accept. Rows are run directly rather than through the suite so an
        unexpected success is observable here instead of being absorbed.
        """
        stub = types.ModuleType(ADAPTER_MODULE)
        for name in REQUIRED_ENTRY_POINTS:
            setattr(stub, name, MagicMock(name=name))
        stub.DeploymentRejected = type("DeploymentRejected", (Exception,), {})
        original = sys.modules.get(ADAPTER_MODULE)
        sys.modules[ADAPTER_MODULE] = stub
        try:
            vacuous = []
            for row in ADAPTER_ROWS:
                case = ReaperAdapterRedContract(row.method)
                case.setUp()
                method = getattr(ReaperAdapterRedContract, row.method)
                method = getattr(method, "__wrapped__", method)
                try:
                    method(case)
                    vacuous.append(row.identifier)
                except Exception:
                    pass
                finally:
                    case.tearDown()
        finally:
            if original is None:
                sys.modules.pop(ADAPTER_MODULE, None)
            else:
                sys.modules[ADAPTER_MODULE] = original
        self.assertEqual(vacuous, [],
                         f"rows green against a do-nothing adapter: {vacuous}")

    def test_lane_evidence_alone_cannot_upgrade_the_t3_inventory(self):
        """#705 adds no path-specific proof, so nothing may move to asserted."""
        statuses = {path.name: path.status for path in INGRESS_RED_INVENTORY.paths}
        self.assertEqual(statuses["InterchangeAudit"], "asserted")
        self.assertEqual(
            {status for name, status in statuses.items() if name != "InterchangeAudit"},
            {"unverified"},
            "a deployment lane proves a deployment, not a per-path emission claim")

    def test_deployment_evidence_rows_are_named(self):
        """Rows whose real proof must come from a container, not this suite."""
        identifiers = {row.identifier for row in ADAPTER_ROWS}
        self.assertTrue(DEPLOYMENT_EVIDENCE_ROWS <= identifiers)

    def test_no_public_upload_surface_is_added_by_this_phase(self):
        from django.urls import get_resolver
        patterns = str(get_resolver().url_patterns)
        for token in ("upload", "quarantine", "reaper"):
            with self.subTest(token=token):
                self.assertNotIn(f"interchange_{token}", patterns)

    # --- real observers ---------------------------------------------------

    def test_real_mount_observation_reads_the_kernel(self):
        mounts = read_self_mounts()
        self.assertIn("/", mounts)
        self.assertTrue(all(entry.startswith("/") for entry in mounts))

    def test_real_identity_observation_distinguishes_owner_and_mode(self):
        with tempfile.TemporaryDirectory(prefix="hh705-id-") as temp:
            path = Path(temp) / "q"
            path.mkdir(mode=0o700)
            uid, _gid, mode = directory_identity(path)
            self.assertEqual(uid, os.geteuid())
            self.assertEqual(mode, 0o700)
            path.chmod(0o750)
            self.assertEqual(directory_identity(path)[2], 0o750)

    def test_real_child_process_reports_its_own_identity(self):
        """Process identity claims need a process, not an in-test assertion."""
        done = run_as_child("import os,sys; sys.stdout.write(str(os.geteuid()))")
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout.strip(), str(os.geteuid()))
