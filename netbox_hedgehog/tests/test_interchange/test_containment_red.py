"""#716 Phase B: RED contract for fail-closed in-container containment.

Test-only. No production wrapper, driver cleanup, NetBox deployment or CI
change. Every row below fails for one reason -- `ContainmentAbsent` -- so a
row-to-cause table can show the failures come from the missing containment
behaviour rather than from fixture, import or lane trouble.

The controlled baseline (C01) is deliberately NOT the #711 driver's unsafe
pre-acknowledgement path. It builds its own disposable child in this lane,
which is what the issue asks for and what keeps the known-unsafe path
unexercised.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import unittest
from dataclasses import dataclass
from pathlib import Path

from django.test import SimpleTestCase

from netbox_hedgehog.tests.test_interchange.containment_support import (
    CONTAINMENT_MODULE,
    OWNERSHIP_PATH,
    REQUIRED_CONTAINMENT_ENTRY_POINTS,
    ContainmentAbsent,
    OwnershipRecord,
    Probe,
    ProbeResult,
    compose_exec,
    load_prover_evidence,
    require_containment,
)


LANE = os.environ.get("HH716_LANE", "diet716")
NETBOX_DOCKER = Path(os.environ.get(
    "HH716_NETBOX_DOCKER", "/home/ubuntu/afewell-hh/netbox-docker"))

#: Marks every process this suite creates, so nothing it does can be
#: confused with the lane's own work or with another scenario.
SUBJECT_TAG = "HH716_OWNED_SUBJECT"
BYSTANDER_TAG = "HH716_UNRELATED_BYSTANDER"


@dataclass(frozen=True)
class ContainmentRow:
    identifier: str
    method: str
    gate_point: int
    claim: str


CONTAINMENT_ROWS = (
    ContainmentRow("C01", "test_c01_host_termination_leaves_an_in_container_child", 1,
                   "host kill does not cross P2; a verified owner must"),
    ContainmentRow("C02", "test_c02_ownership_is_two_stage_and_precedes_launch", 2,
                   "container identity before launch, process identity before setup"),
    ContainmentRow("C03", "test_c03_every_population_is_registered_or_unresolved", 3,
                   "P2 child, P4/P6 probes, P5 preparation containers"),
    ContainmentRow("C04", "test_c04_deficient_ownership_records_authorize_no_signal", 4,
                   "missing/stale/wrong-run/wrong-container/wrong-pgid/malformed"),
    ContainmentRow("C05", "test_c05_identity_is_verified_before_signalling", 5,
                   "PID reuse race; structured argv only"),
    ContainmentRow("C06", "test_c06_probe_failure_is_unknown_not_clean", 6,
                   "membership, survivor and pg_database probes"),
    ContainmentRow("C07", "test_c07_observer_failure_enters_finally_scoped_recovery", 7,
                   "original error preserved, cleanup failure recorded"),
    ContainmentRow("C08", "test_c08_failed_verification_is_never_reported_as_clean", 8,
                   "no zero-survivors or absent-DB from a failed probe"),
    ContainmentRow("C09", "test_c09_dirty_lane_refuses_the_next_scenario", 9,
                   "refusal proven, with clean-lane and reset positives"),
    ContainmentRow("C10", "test_c10_successful_release_performs_no_forced_cleanup", 10,
                   "positive completion path"),
    ContainmentRow("C11", "test_c11_scenario_verifies_its_own_compose_identity", 11,
                   "dedicated project verified before action"),
    ContainmentRow("C12", "test_c12_heuristic_ownership_is_rejected", 3,
                   "prefix/time-window selection must fail; exact run-bound "
                   "identity only"),
)


class ContainmentFixture(SimpleTestCase):
    """Shared setup. Touches no Docker: evidence is observed host-side.

    A first version ran `docker inspect` from inside the test container with
    the socket mounted. That is the privilege Dev B ruled out on #711, and
    it failed only because the image has no docker CLI -- an image that had
    one would have worked and violated the constraint silently.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.evidence = load_prover_evidence(LANE)
        cls.container_id = cls.evidence["container_id"]


class ContainmentRedTests(ContainmentFixture):
    """Rows that fail until #716 implements fail-closed containment."""

    def test_c01_host_termination_leaves_an_in_container_child(self):
        """Gate 1: the defect, then a verified rescue owner that cleans it.

        The baseline is the prover's own disposable child in this dedicated
        lane -- not #711's unsafe pre-acknowledgement path, which the issue
        forbids re-exercising.
        """
        baseline = self.evidence["baseline"]
        self.assertTrue(baseline["hostkilled_child_alive_known"],
                        "the baseline probe could not run, so it establishes nothing")
        self.assertGreater(
            baseline["hostkilled_child_alive"], 0,
            "the in-container child did not survive host termination, so this "
            "baseline is not demonstrating the defect it claims")
        self.assertGreater(baseline["bystander"], 0,
                           "the unrelated bystander was not alive to begin with")

        contract = require_containment()
        report = contract.cleanup_owned(lane=LANE, container_id=self.container_id,
                                        run_id=self.evidence["run_id"])
        self.assertTrue(report.cleaned)
        self.assertEqual(report.survivors, 0)
        self.assertTrue(report.bystander_intact,
                        "the rescue owner killed an unrelated bystander")

    def test_c02_ownership_is_two_stage_and_precedes_launch(self):
        """Gate 2: container identity before launch, process identity before setup."""
        contract = require_containment()
        first = contract.publish_container_identity(lane=LANE, run_id="c02")
        self.assertEqual(first.container_id, self.container_id)
        self.assertEqual(first.stage, "container")
        second = contract.publish_process_identity(lane=LANE, run_id="c02")
        self.assertEqual(second.stage, "process")
        for field in ("pid", "pgid", "sid", "command"):
            self.assertTrue(getattr(second, field),
                            f"process-stage record lacks {field}")

    def test_c03_every_population_is_registered_or_unresolved(self):
        """Gate 3: P2 child, P4/P6 probes, P5 preparation containers."""
        contract = require_containment()
        state = contract.lane_state(lane=LANE)
        for population in ("test_child", "probe_processes", "preparation_containers"):
            with self.subTest(population=population):
                self.assertIn(population, state.registered,
                              f"{population} is neither registered nor unresolved; "
                              "prefix or time-window guessing is not ownership")

    def test_c12_heuristic_ownership_is_rejected(self):
        """Gate 3, strengthened: a heuristic implementation must FAIL here.

        The lane holds two preparation-shaped processes created in the same
        window. One carries this run's binding; the decoy wears the same
        recognizable `hh709-` prefix and carries none. A contract selecting
        by prefix, or by "started recently", takes both. Only exact
        run-bound identity takes one.

        Identity here is immutable -- container id plus pid plus start-time
        ticks -- because a display name is not an identity and a pid alone
        is reusable.
        """
        trap = self.evidence["heuristic_trap"]

        # The decoy must actually be a trap, or this row proves nothing.
        self.assertGreater(
            trap["prefix_would_match"], 1,
            "a prefix matcher does not select more than the bound resource "
            "here, so this row cannot discriminate a heuristic contract")
        self.assertEqual(len(trap["legitimate"]), 1,
                         "exactly one run-bound resource must exist")
        self.assertEqual(len(trap["decoy"]), 1,
                         "the unrelated prefix-sharing decoy must exist")
        self.assertNotEqual(trap["legitimate_tag"], trap["decoy_tag"])
        for entry in trap["legitimate"] + trap["decoy"]:
            self.assertTrue(entry["start_ticks"],
                            "no start-time recorded, so pid reuse is undetectable")

        contract = require_containment()
        reconciled = contract.lane_state(lane=LANE).reconcile_preparation(
            run_id=trap["run_id"], container_id=self.container_id)

        # A prefix or time-window implementation returns both.
        self.assertEqual(
            len(reconciled), 1,
            f"the contract reconciled {len(reconciled)} resources where exactly "
            "one carries this run's binding; prefix or time-window selection "
            "is not ownership")
        owned = reconciled[0]
        self.assertEqual(owned.run_id, trap["run_id"])
        self.assertEqual(owned.container_id, self.container_id,
                         "ownership must bind immutable container identity, "
                         "not a display name")
        self.assertEqual(owned.pid, trap["legitimate"][0]["pid"])
        self.assertEqual(
            str(owned.start_ticks), trap["legitimate"][0]["start_ticks"],
            "ownership must bind process start time; a pid alone is reusable")
        self.assertNotEqual(
            owned.pid, trap["decoy"][0]["pid"],
            "the contract selected the unrelated prefix-sharing decoy")

    def test_c04_deficient_ownership_records_authorize_no_signal(self):
        """Gate 4: seven deficiency shapes, none may authorize a signal."""
        contract = require_containment()
        good = OwnershipRecord(run_id="c04", container_id=self.container_id,
                               pid=1, pgid=1, sid=1, command="python", stage="process")
        deficient = {
            "missing": OwnershipRecord(),
            "stale": OwnershipRecord(**{**good.__dict__, "run_id": "older-run"}),
            "wrong_run": OwnershipRecord(**{**good.__dict__, "run_id": "other"}),
            "wrong_container": OwnershipRecord(**{**good.__dict__,
                                                  "container_id": "0" * 64}),
            "wrong_pgid": OwnershipRecord(**{**good.__dict__, "pgid": 999999}),
            "mismatched_command": OwnershipRecord(**{**good.__dict__,
                                                     "command": "not-the-command"}),
            "malformed_but_parseable": OwnershipRecord.from_text('{"run_id": 5}'),
        }
        for shape, record in deficient.items():
            with self.subTest(shape=shape):
                with self.assertRaises(contract.OwnershipInvalid):
                    contract.verify_ownership(record, lane=LANE, run_id="c04",
                                              container_id=self.container_id)

    def test_c05_identity_is_verified_before_signalling(self):
        """Gate 5: PID reuse race, and structured arguments only."""
        contract = require_containment()
        with self.assertRaises(contract.OwnershipInvalid):
            # A PGID that exists but belongs to something else must not be
            # signalled on the strength of the number alone.
            contract.cleanup_owned(lane=LANE, container_id=self.container_id,
                                   run_id="c05", pgid=1)
        self.assertFalse(
            contract.cleanup_owned.__doc__ and "shell=True" in
            contract.cleanup_owned.__doc__)

    def test_c06_probe_failure_is_unknown_not_clean(self):
        """Gate 6: a probe that could not run is UNKNOWN, never a clean result."""
        observed = self.evidence["unreachable_probe"]
        self.assertFalse(
            observed["known"],
            "a probe against a nonexistent lane produced a definite answer; "
            "today's driver turns exactly this into 'no survivors'")
        with self.assertRaises(TypeError):
            bool(ProbeResult(Probe.UNKNOWN))

        contract = require_containment()
        self.assertEqual(
            contract.lane_state(lane="hh716-no-such-lane").reusable,
            False,
            "unknown state must block reuse")

    def test_c07_observer_failure_enters_finally_scoped_recovery(self):
        """Gate 7: recovery runs, the original error survives, failures recorded."""
        contract = require_containment()

        class ObserverFailure(RuntimeError):
            pass

        with self.assertRaises(ObserverFailure):
            with contract.owned_scenario(lane=LANE, run_id="c07") as scenario:
                raise ObserverFailure("observer died after publication")
        self.assertTrue(scenario.recovery_attempted,
                        "no finally-scoped recovery ran after observer failure")

    def test_c08_failed_verification_is_never_reported_as_clean(self):
        """Gate 8: a failed signal or probe cannot become zero survivors."""
        contract = require_containment()
        report = contract.cleanup_owned(lane="hh716-no-such-lane",
                                        container_id=self.container_id,
                                        run_id="c08")
        self.assertNotEqual(report.survivors, 0,
                            "a cleanup that could not verify reported zero survivors")
        self.assertEqual(report.survivors_known, False)

    def test_c09_dirty_lane_refuses_the_next_scenario(self):
        """Gate 9: refusal proven, with clean-lane and reset positives."""
        contract = require_containment()
        contract.lane_state(lane=LANE).mark_dirty("c09 forced")
        with self.assertRaises(contract.OwnershipInvalid):
            contract.lane_state(lane=LANE).begin_scenario("c09-next")
        self.assertTrue(contract.lane_state(lane=LANE).reset(verified=True))
        self.assertTrue(contract.lane_state(lane=LANE).begin_scenario("c09-after"),
                        "a reset lane must proceed; the gate is not a blanket refusal")

    def test_c10_successful_release_performs_no_forced_cleanup(self):
        """Gate 10: the completion path runs bodies and forces nothing."""
        contract = require_containment()
        with contract.owned_scenario(lane=LANE, run_id="c10") as scenario:
            pass
        self.assertFalse(scenario.forced_cleanup,
                         "a clean completion performed forced cleanup")

    def test_c11_scenario_verifies_its_own_compose_identity(self):
        """Gate 11: the dedicated project is verified before any action."""
        contract = require_containment()
        with self.assertRaises(contract.OwnershipInvalid):
            contract.publish_container_identity(lane="netbox-docker", run_id="c11")


class ContainmentRedControls(ContainmentFixture):
    """Controls that pass today and keep the rows honest."""

    def test_red_phase_has_no_containment_contract(self):
        with self.assertRaises(ContainmentAbsent) as caught:
            require_containment()
        self.assertIn(CONTAINMENT_MODULE, str(caught.exception))

    def test_every_gate_point_is_covered(self):
        self.assertEqual({row.gate_point for row in CONTAINMENT_ROWS},
                         set(range(1, 12)))

    def test_the_heuristic_decoy_is_a_real_trap(self):
        """The decoy must be indistinguishable from the real thing by prefix.

        Without this, C12 could pass against a decoy a prefix matcher would
        never have selected -- certifying discrimination that was never
        tested.
        """
        trap = self.evidence["heuristic_trap"]
        prefix = "hh709-"
        self.assertTrue(trap["legitimate_tag"].startswith(prefix))
        self.assertTrue(trap["decoy_tag"].startswith(prefix),
                        "the decoy does not share the prefix, so a prefix "
                        "matcher would not have been fooled by it")
        self.assertGreaterEqual(
            trap["prefix_would_match"], 2,
            "a prefix matcher selected fewer than both, so the trap is inert")

    def test_every_row_is_declared_and_exists(self):
        declared = {row.method for row in CONTAINMENT_ROWS}
        actual = {n for n in dir(ContainmentRedTests) if n.startswith("test_c")}
        self.assertEqual(declared, actual)

    def test_probe_result_cannot_be_used_as_a_boolean(self):
        """The guard that stops UNKNOWN reading as False."""
        for outcome in Probe:
            with self.subTest(outcome=outcome):
                with self.assertRaises(TypeError):
                    bool(ProbeResult(outcome))

    def test_the_lane_is_dedicated_and_not_shared(self):
        self.assertNotEqual(LANE, "netbox-docker")
        self.assertNotEqual(self.evidence["lane"], "netbox-docker")
        self.assertTrue(self.container_id, "the dedicated lane container was not found")

    def test_this_suite_never_reaches_docker_from_the_container(self):
        """No Docker access from inside the test container, by inspection."""
        import ast
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        literals = [c for c in calls for a in c.args
                    if isinstance(a, ast.Constant) and a.value == "docker"]
        self.assertEqual(literals, [],
                         "a row invokes docker from inside the container")

    def test_compose_exec_refuses_string_commands(self):
        """Structured argv only: a PGID in `sh -c` is unreviewable."""
        with self.assertRaises(TypeError):
            compose_exec(NETBOX_DOCKER, LANE, "netbox", "ps -eo pgid")
