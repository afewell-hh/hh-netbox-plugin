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
    REQUIRED_HARNESS_OBSERVATIONS,
    build_deficient_stub,
    build_permissive_stub,
    build_single_fault_stub,
    shipped_configuration_inventory,
    scan_for_artifact_references,
    check_shipped_artifact_containment,
    ShippedConfigurationUnavailable,
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
    AdapterRow("A12", "test_a12_lane_harness_declares_its_contract", "harness manifest", "harness"),
    AdapterRow("A13", "test_a13_valid_non_default_configuration_is_accepted", "valid non-default accepted", "validation"),
    AdapterRow("A14", "test_a14_mount_and_surface_configuration_is_rejected", "mount/surface negatives", "validation"),
    AdapterRow("A15", "test_a15_harness_emits_artifacts_and_observed_results", "harness artifacts + evidence", "harness"),
    AdapterRow("A16", "test_a16_missing_or_contradictory_harness_evidence_fails", "evidence gaps fail", "harness"),
    AdapterRow("A17", "test_a17_harness_artifacts_are_contained_outside_shipped_configuration", "harness containment", "harness"),
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
        self.artifacts = root / "lane-artifacts"
        self.artifacts.mkdir(mode=0o700)
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
        # A spec that merely echoes its input would present a root reaper as
        # a valid deployment. Building one must fail, not round-trip.
        with self.assertRaises(api.DeploymentRejected):
            api.AdapterSpec(self.replaced(reaper_uid=0))

    @adapter_red("A02")
    def test_a02_reaper_mounts_quarantine_only(self):
        api = require_reaper_adapter()
        spec = api.AdapterSpec(self.fixture)
        self.assertEqual(tuple(spec.reaper_mount_points), (str(self.fixture.quarantine_root),))
        for name in FORBIDDEN_REAPER_MOUNTS:
            with self.subTest(mount=name):
                self.assertNotIn(str(self.forbidden[name]), spec.reaper_mount_points)
        # A constant mount list would satisfy the assertions above whatever it
        # was handed. A deployment carrying a prohibited mount must be refused
        # rather than silently normalised into a clean-looking spec.
        with self.assertRaises(api.DeploymentRejected):
            api.AdapterSpec(self.replaced(
                reaper_mounts=(str(self.fixture.quarantine_root),
                               str(self.forbidden["media"]))))

    # --- 2. startup/preflight validation ----------------------------------

    @adapter_red("A03")
    def test_a03_cap_mismatch_is_rejected(self):
        api = require_reaper_adapter()
        api.validate_deployment(self.fixture)
        mismatched = self.replaced(max_raw_bytes=TEST_UNIT_CAP_BYTES + 1)
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(mismatched)

    @adapter_red("A13")
    def test_a13_valid_non_default_configuration_is_accepted(self):
        """Rejecting every departure from v1 defaults is not validation.

        Without this, a validator that simply refuses anything unfamiliar
        satisfies every negative row while being useless.
        """
        api = require_reaper_adapter()
        doubled = self.replaced(
            unit_route_cap_bytes=TEST_UNIT_CAP_BYTES * 2,
            max_raw_bytes=TEST_UNIT_CAP_BYTES * 2,
            reaper_interval_seconds=V1_DEFAULTS["reaper_interval_seconds"] * 2,
            orphan_bound_seconds=V1_DEFAULTS["orphan_bound_seconds"] * 2,
        )
        self.assertNotEqual(doubled.max_raw_bytes, V1_DEFAULTS["max_raw_bytes"])
        # Pin the verdict: "did not raise" is also true of a validator that
        # does nothing, so the accepted result has to be stated.
        self.assertIs(api.validate_deployment(doubled), True)
        self.assertIs(api.validate_deployment(self.fixture), True)

    @adapter_red("A14")
    def test_a14_mount_and_surface_configuration_is_rejected(self):
        """The cases #705 names that no other row presents."""
        api = require_reaper_adapter()
        cases = {
            "no quarantine mount": self.replaced(reaper_mounts=()),
            "non-dedicated quarantine mount":
                self.replaced(quarantine_mount_is_dedicated=False),
            "public upload surface": self.replaced(exposes_public_upload=True),
            "additional prohibited mount": self.replaced(
                reaper_mounts=(str(self.fixture.quarantine_root),
                               str(self.forbidden["scripts"]))),
        }
        for label, candidate in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(api.DeploymentRejected):
                    api.validate_deployment(candidate)

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
        # Strictly below the boundary as well as at it: a validator keyed to
        # equality alone would accept the worse configuration.
        below = self.replaced(
            orphan_bound_seconds=(self.fixture.reaper_interval_seconds
                                  + self.fixture.clock_skew_seconds))
        self.assertLess(below.derived_eligibility_seconds,
                        below.active_write_grace_seconds)
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(below)

    @adapter_red("A05")
    def test_a05_quarantine_under_prohibited_root_is_rejected(self):
        api = require_reaper_adapter()
        for name, root in self.forbidden.items():
            with self.subTest(root=name):
                nested = root / "secure-quarantine"
                nested.mkdir(mode=0o700)
                # The mount must follow the root. Varying only the root lets a
                # validator reject every candidate for an unmounted Q and never
                # evaluate placement at all, which hides the rule this row names.
                with self.assertRaises(api.DeploymentRejected):
                    api.validate_deployment(self.replaced(
                        quarantine_root=nested, reaper_mounts=(str(nested),)))
        # Reverse overlap: a Q root that contains a prohibited root is equally
        # unsafe, and a prefix test written one way round misses it.
        container = Path(self.temp.name)
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(self.replaced(
                quarantine_root=container, reaper_mounts=(str(container),)))

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

        # The mode case specifically: a validator that chmods to 0700 and then
        # raises still rejects, so rejection alone cannot detect the repair.
        self.fixture.quarantine_root.chmod(0o750)
        before_mode = directory_identity(self.fixture.quarantine_root)
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(self.fixture)
        self.assertEqual(directory_identity(self.fixture.quarantine_root), before_mode,
                         "preflight repaired the mode it was asked to judge")
        self.fixture.quarantine_root.chmod(0o700)

        before = directory_identity(self.fixture.quarantine_root)
        with self.assertRaises(api.DeploymentRejected):
            api.validate_deployment(self.replaced(reaper_uid=0))
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

        # The discriminator. These two reports have an alert_required that
        # disagrees with the fields it is normally derived from, so an adapter
        # that recomputes `failed or bound_exceeded_count` gets the opposite
        # answer. Comparing against equivalent values, as the cases above do,
        # cannot tell the two implementations apart.
        class _OverriddenQuiet(ReaperReport):
            @property
            def alert_required(self):
                return False

        class _OverriddenLoud(ReaperReport):
            @property
            def alert_required(self):
                return True

        lying_quiet = _OverriddenQuiet((), 777, True, 1, 1, 777)
        lying_loud = _OverriddenLoud((), 0, False, 0, 0, 0)
        self.assertIs(lying_quiet.failed, True)
        self.assertIs(lying_loud.failed, False)

        self.assertIs(
            api.run_scheduled_reap(self.fixture, report=lying_quiet).alerting, False,
            "adapter re-derived the verdict instead of reading alert_required")
        self.assertIs(
            api.run_scheduled_reap(self.fixture, report=lying_loud).alerting, True,
            "adapter re-derived the verdict instead of reading alert_required")

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
        interval = self.fixture.reaper_interval_seconds
        now = 1_000_000

        # Elapsed time is derived from observed completion, never supplied.
        # An implementation that echoes a caller-provided age has nothing to
        # echo here and must compute it.
        healthy = api.health_state(self.fixture, now=now,
                                   last_success_at=now - interval // 2, runs=())
        self.assertIs(healthy.alerting, False)
        self.assertEqual(healthy.seconds_since_success, interval // 2)

        missed = api.health_state(self.fixture, now=now,
                                  last_success_at=now - interval * 2, runs=())
        self.assertIs(missed.alerting, True)
        self.assertEqual(missed.seconds_since_success, interval * 2)
        self.assertLess(missed.seconds_since_success, self.fixture.orphan_bound_seconds)

        # A failed execution is a scheduler health event too, and it must be
        # inferred from an observed run outcome rather than a policy flag the
        # caller sets.
        failed = api.health_state(
            self.fixture, now=now, last_success_at=now - interval // 2,
            runs=(api.RunOutcome(started_at=now - 60, succeeded=False),))
        self.assertIs(failed.alerting, True)

    @adapter_red("A11")
    def test_a11_health_record_is_bounded_and_safe(self):
        api = require_reaper_adapter()
        from netbox_hedgehog.secure_ingress import ReaperReport

        report = ReaperReport((SENTINEL,), 777, True, 1, 1, 108000)
        limit = 3
        now = 1_000_000
        state = api.health_state(self.fixture, now=now, last_success_at=now,
                                 runs=(api.RunOutcome(started_at=now, succeeded=True),),
                                 last_report=report, history_limit=limit)

        # A record must actually exist. An empty history satisfies every bound
        # and secrecy assertion while retaining no operational evidence at all.
        self.assertEqual(len(state.history), 1)
        self.assertEqual(state.history_limit, limit)

        stored = repr(list(state.history))
        self.assertNotIn(SENTINEL, stored)
        self.assertNotIn(str(self.fixture.quarantine_root), stored)
        self.assertNotIn(SENTINEL, str(state))

        # Bounded in fact, and bounded to the *most recent* runs: a capacity
        # honoured by discarding the newest records would pass a length check.
        for index in range(limit * 4):
            state = api.health_state(
                self.fixture, now=now + index + 1, last_success_at=now + index + 1,
                runs=(api.RunOutcome(started_at=now + index + 1, succeeded=True),),
                last_report=ReaperReport((), index, False, 0, 0, index),
                history_limit=limit, previous=state)
        self.assertEqual(len(state.history), limit)
        self.assertNotIn(SENTINEL, repr(list(state.history)))
        observed = [record.oldest_orphan_seconds for record in state.history]
        # The exact sequence. Length, ordering and a final value are all
        # satisfied by an aliased history such as [11, 11, 11]; only the
        # expected run identities rule that out.
        expected = list(range(limit * 4 - limit, limit * 4))
        self.assertEqual(observed, expected,
                         "history must retain the most recent runs, distinctly and in order")

    @adapter_red("A12")
    def test_a12_lane_harness_declares_its_contract(self):
        """The declarative half: what a harness run must cover.

        Kept deliberately separate from A15. A manifest is worth pinning, but
        on its own it is a statement the adapter makes about itself, which is
        why it is not the whole row it used to be.
        """
        api = require_reaper_adapter()
        harness = api.lane_harness_spec(self.fixture, artifact_dir=self.artifacts)
        self.assertIs(harness.is_lane_only, True)
        self.assertEqual(harness.unit_route_cap_bytes, TEST_UNIT_CAP_BYTES)
        self.assertEqual(set(harness.required_observations), set(REQUIRED_HARNESS_OBSERVATIONS))
        self.assertIs(harness.exposes_public_upload, False)

    @adapter_red("A15")
    def test_a15_harness_emits_artifacts_and_observed_results(self):
        """The falsifiable half: artifacts on disk, evidence per observation.

        A declaration cannot be the contract. The harness must produce real
        files and return observations that each carry evidence of having been
        made, so a stand-in returning the right-shaped namespace fails.
        """
        api = require_reaper_adapter()
        harness = api.lane_harness_spec(self.fixture, artifact_dir=self.artifacts)

        written = harness.render()
        produced = sorted(path.name for path in self.artifacts.iterdir())
        self.assertTrue(produced, "harness rendered no artifact")
        self.assertEqual(sorted(Path(p).name for p in written), produced)
        for path in written:
            with self.subTest(artifact=Path(path).name):
                self.assertGreater(Path(path).stat().st_size, 0,
                                   "an empty artifact is not a rendered harness")

        result = harness.observe()
        self.assertEqual(set(result.observations), set(REQUIRED_HARNESS_OBSERVATIONS))
        for name, observation in result.observations.items():
            with self.subTest(observation=name):
                self.assertIs(observation.observed, True)
                self.assertTrue(observation.evidence,
                                f"{name} was asserted without evidence")
        self.assertEqual(result.unit_version, harness.pinned_unit_version)
        # The pinned version must be the one the deployment actually runs, not
        # an arbitrary string echoed back from the harness to itself.
        self.assertRegex(str(harness.pinned_unit_version), r"^\d+\.\d+\.\d+$")

    @adapter_red("A16")
    def test_a16_missing_or_contradictory_harness_evidence_fails(self):
        """Verification must judge the real result, and judge its evidence.

        Checking a freshly-built boolean map proves nothing about what
        ``observe()`` returned. Verification has to consume that result, and
        an ``observed=True`` carrying unrelated evidence has to be rejected --
        otherwise evidence collapses back into a truthiness flag whatever its
        format.
        """
        api = require_reaper_adapter()
        harness = api.lane_harness_spec(self.fixture, artifact_dir=self.artifacts)
        harness.render()
        result = harness.observe()

        harness.verify(result)

        for name in sorted(REQUIRED_HARNESS_OBSERVATIONS):
            with self.subTest(missing=name):
                partial = result.without(name)
                with self.assertRaises(api.HarnessEvidenceMissing):
                    harness.verify(partial)
            with self.subTest(contradicted=name):
                contradicted = result.with_observation(name, observed=False)
                with self.assertRaises(api.HarnessEvidenceMissing):
                    harness.verify(contradicted)
            with self.subTest(unrelated_evidence=name):
                swapped = result.with_observation(
                    name, observed=True, evidence="HH705-UNRELATED-PLACEHOLDER")
                with self.assertRaises(api.HarnessEvidenceMissing):
                    harness.verify(swapped)

        # Evidence must stay bound to what produced it: destroying the
        # artifacts behind an otherwise successful result must invalidate it.
        for path in self.artifacts.iterdir():
            path.unlink()
        with self.assertRaises(api.HarnessEvidenceMissing):
            harness.verify(result)

    @adapter_red("A17")
    def test_a17_harness_artifacts_are_contained_outside_shipped_configuration(self):
        """Lane-only has to mean something a reader can check.

        The artifacts must land where the caller asked -- a disposable
        directory -- and must not appear in, or be referenced by, anything the
        repository ships.
        """
        api = require_reaper_adapter()
        harness = api.lane_harness_spec(self.fixture, artifact_dir=self.artifacts)
        written = [Path(path) for path in harness.render()]
        self.assertTrue(written, "harness rendered nothing to contain")

        for path in written:
            with self.subTest(artifact=path.name):
                self.assertTrue(path.resolve().is_relative_to(self.artifacts.resolve()))

        names = {path.name for path in written}

        # Controlled negative first, so the scanner is exercised even where no
        # checkout is reachable. A reference is planted in a disposable decoy;
        # if the scan were disabled this reports nothing and fails. Placed
        # before the inventory gate deliberately: behind it, this proof would
        # be unreachable in exactly the environment CI runs in.
        decoy_dir = Path(self.temp.name) / "decoy-shipped"
        decoy_dir.mkdir()
        decoy = decoy_dir / "workflow.yml"
        planted_name = sorted(names)[0]
        decoy.write_text(f"jobs:\n  run:\n    script: {planted_name}\n", encoding="utf-8")
        self.assertEqual(scan_for_artifact_references(names, [decoy]),
                         [f"workflow.yml: {planted_name}"],
                         "the scanner cannot detect a reference it is given")

        shipped = shipped_configuration_inventory()

        self.assertEqual(check_shipped_artifact_containment(names), len(shipped))
        for config in shipped:
            self.assertFalse(
                any(path.resolve().is_relative_to(config.parent.resolve())
                    for path in written),
                "a harness artifact was written into shipped configuration")

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

    def _rows_passing_against(self, stub):
        """Run every row body directly against a stand-in; return the passers.

        Directly rather than through the suite, so an unexpected success is
        observable here instead of being absorbed by expectedFailure.
        """
        original = sys.modules.get(ADAPTER_MODULE)
        sys.modules[ADAPTER_MODULE] = stub
        try:
            passing = []
            for row in ADAPTER_ROWS:
                case = ReaperAdapterRedContract(row.method)
                case.setUp()
                method = getattr(ReaperAdapterRedContract, row.method)
                method = getattr(method, "__wrapped__", method)
                try:
                    method(case)
                    passing.append(row.identifier)
                except Exception:
                    pass
                finally:
                    case.tearDown()
            return passing
        finally:
            if original is None:
                sys.modules.pop(ADAPTER_MODULE, None)
            else:
                sys.modules[ADAPTER_MODULE] = original

    def test_no_row_passes_against_a_permissive_adapter_stub(self):
        """Rows must assert something: the weakest adversary."""
        vacuous = self._rows_passing_against(build_permissive_stub())
        self.assertEqual(vacuous, [],
                         f"rows green against a do-nothing adapter: {vacuous}")

    #: Each deficiency the #706 review's typed stand-in exhibits, and the row
    #: that must catch it. Named individually rather than asserting the whole
    #: suite rejects the stub: that adapter implements some checks correctly,
    #: and demanding every row fail would assert it is wrong about everything.
    TYPED_DEFICIENCIES = {
        "quarantine placement checked one direction only": "A05",
        "repairs an unsafe mode before rejecting it": "A07",
        "re-derives the alert verdict instead of reading it": "A08",
        "fabricates its health age and always alerts": "A10",
        "retains raw content and grows history without bound": "A11",
        "omits mount and public-surface validation": "A14",
        "ships a harness manifest with no run behind it": "A15",
        "treats missing harness evidence as success": "A16",
        "cannot show its artifacts are contained": "A17",
    }

    def test_each_typed_deficiency_is_caught_by_its_row(self):
        """Rows must constrain behaviour, not merely shape.

        The stronger adversary, from #706 review: a typed adapter returning
        plausible values that nonetheless gets the behaviour wrong. Rejecting
        MagicMock did not catch any of it, so the adversary is kept here and
        runs on every execution rather than depending on a reviewer thinking
        of it again.
        """
        passing = set(self._rows_passing_against(build_deficient_stub()))
        undetected = sorted(
            f"{row}: {deficiency}"
            for deficiency, row in self.TYPED_DEFICIENCIES.items()
            if row in passing)
        self.assertEqual(undetected, [],
                         f"deficiencies no row detects: {undetected}")

    #: One fault at a time, so an early assertion cannot mask a later rule.
    SINGLE_FAULT_ROWS = {
        "health_unbounded": "A11",
        "health_retains_raw": "A11",
        "health_empty_history": "A11",
    }

    def test_sound_health_stub_passes_the_health_rows(self):
        """The positive half, committed.

        Demanding only failures is satisfied by an implementation that always
        raises: the faults would look discriminating while the rows rejected
        everything. Only the health rows are claimed -- the sound stub's other
        entry points stay deliberately deficient.
        """
        passing = set(self._rows_passing_against(build_single_fault_stub("none")))
        for row in ("A10", "A11"):
            with self.subTest(row=row):
                self.assertIn(row, passing,
                              f"{row} rejects a sound health implementation")

    def test_each_single_fault_variant_is_caught(self):
        """A multi-fault stub can be rejected for the wrong reason.

        #706 re-review: A11 tripped the bundled stand-in on capacity before
        reaching secrecy, so secrecy was never actually exercised against it.
        Each fault is injected alone into an otherwise sound adapter.
        """
        for fault, row in sorted(self.SINGLE_FAULT_ROWS.items()):
            with self.subTest(fault=fault):
                passing = self._rows_passing_against(build_single_fault_stub(fault))
                self.assertNotIn(row, passing,
                                 f"{row} did not catch the isolated fault {fault!r}")

    def test_typed_deficiency_map_names_real_rows(self):
        identifiers = {row.identifier for row in ADAPTER_ROWS}
        self.assertEqual(set(self.TYPED_DEFICIENCIES.values()) - identifiers, set())

    def test_lane_evidence_alone_cannot_upgrade_the_t3_inventory(self):
        """#705 adds no path-specific proof, so nothing may move to asserted."""
        statuses = {path.name: path.status for path in INGRESS_RED_INVENTORY.paths}
        self.assertEqual(statuses["InterchangeAudit"], "asserted")
        self.assertEqual(
            {status for name, status in statuses.items() if name != "InterchangeAudit"},
            {"unverified"},
            "a deployment lane proves a deployment, not a per-path emission claim")

    def test_scanner_fails_closed_on_unreadable_or_missing_configuration(self):
        """An unsearched file must not read as a searched one.

        The scanner previously swallowed OSError and continued, so a config
        it could not open reported clean -- including one that contained an
        artifact name. "No violations" then meant "nothing was looked at",
        which is the hollow result this scanner exists to prevent.
        """
        names = {"lane-harness.yml"}
        with tempfile.TemporaryDirectory(prefix="hh705-scan-") as temp:
            root = Path(temp)

            clean = root / "clean.yml"
            clean.write_text("jobs: {}\n", encoding="utf-8")
            self.assertEqual(scan_for_artifact_references(names, [clean]), [])

            missing = root / "vanished.yml"
            with self.assertRaises(ShippedConfigurationUnavailable):
                scan_for_artifact_references(names, [missing])

            unreadable = root / "unreadable.yml"
            unreadable.write_text("jobs:\n  run: lane-harness.yml\n", encoding="utf-8")
            os.chmod(unreadable, 0o000)
            try:
                if os.geteuid() == 0:
                    # Root reads it regardless, so the permission half cannot
                    # be exercised here; the missing-file case above still
                    # covers the fail-closed contract.
                    self.assertEqual(
                        scan_for_artifact_references(names, [unreadable]),
                        [f"unreadable.yml: lane-harness.yml"])
                else:
                    with self.assertRaises(ShippedConfigurationUnavailable):
                        scan_for_artifact_references(names, [unreadable])
            finally:
                os.chmod(unreadable, 0o600)

    def test_shipped_inventory_fails_closed_rather_than_returning_nothing(self):
        """An empty scan must raise, never read as a clean result."""
        inventory = shipped_configuration_inventory()
        self.assertTrue(inventory)
        self.assertTrue(any(path.suffix in {".yml", ".yaml"} or path.parent.name == "scripts"
                            for path in inventory))

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
