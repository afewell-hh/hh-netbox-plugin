"""#716 Step B1: controls proving the prover itself is safe.

These are not the containment rows (#717, held). They prove the *fixture*
obeys the constraints the rows specify -- the gap that made the previous
prover unacceptable: it performed unverified broad `pkill` cleanup while
belonging to a suite that forbids exactly that.

Consumes two host-produced artifacts: a healthy run and a run whose rescue
proof was deliberately forced unproven.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

from django.test import SimpleTestCase


SUPPORT_DIR = Path(__file__).resolve().parent
PROVER = SUPPORT_DIR / "containment_prover.py"
RESCUE = SUPPORT_DIR / "containment_rescue.py"

PROHIBITED_COMMANDS = ("pkill", "killall")


def _evidence(variable):
    location = os.environ.get(variable)
    if not location:
        raise AssertionError(f"{variable} is unset; run containment_prover.py")
    return json.loads(Path(location).read_text(encoding="utf-8"))


class ProverSafetyControls(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.healthy = _evidence("HH716_CONTAINMENT_EVIDENCE")
        cls.unproven = _evidence("HH716_CONTAINMENT_UNPROVEN")

    # --- source controls ---------------------------------------------------

    def test_no_prohibited_cleanup_command_is_executed(self):
        """No pkill/killall anywhere in executable code.

        Covers the shape Dev B showed slipping past my earlier AST check:
        an ordinary list argv such as `subprocess.run(["docker", ...])`.
        Every string constant in every call, at any nesting depth, is
        examined -- not only direct positional arguments.
        """
        for source in (PROVER, RESCUE):
            with self.subTest(module=source.name):
                tree = ast.parse(source.read_text(encoding="utf-8"))
                offenders = []
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    for literal in [n for n in ast.walk(node)
                                    if isinstance(n, ast.Constant)
                                    and isinstance(n.value, str)]:
                        for banned in PROHIBITED_COMMANDS:
                            if banned in literal.value:
                                offenders.append((node.lineno, literal.value[:60]))
                self.assertEqual(
                    offenders, [],
                    f"{source.name} executes a prohibited cleanup command: "
                    f"{offenders}")

    def test_the_prohibited_detector_actually_detects(self):
        """The control above must fail on a planted call; else it proves nothing."""
        planted = ast.parse('subprocess.run(["sh", "-c", "pkill -9 -f tag"])')
        found = []
        for node in ast.walk(planted):
            if isinstance(node, ast.Call):
                for literal in [n for n in ast.walk(node)
                                if isinstance(n, ast.Constant)
                                and isinstance(n.value, str)]:
                    if any(b in literal.value for b in PROHIBITED_COMMANDS):
                        found.append(literal.value)
        self.assertTrue(found, "the detector misses a list-argv pkill call")

    def test_the_host_prover_signals_only_its_own_host_side_exec(self):
        """The host may kill its own exec; it may not signal into the container.

        The first version of this control forbade every `.kill()` and failed
        on `host_child.kill()` -- the deliberate baseline induction, which
        terminates the prover's own host-side `docker compose exec` and is
        the whole point of the controlled defect. The rule was right to
        flag it; the exception is therefore narrow and named rather than
        the rule being loosened.
        """
        tree = ast.parse(PROVER.read_text(encoding="utf-8"))

        # No process-signalling syscalls at all from the host side.
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in (
                    "killpg", "pidfd_send_signal", "kill") and isinstance(
                    node.value, ast.Name) and node.value.id in ("os", "signal"):
                self.fail(f"the host prover calls {node.value.id}.{node.attr}; "
                          "only the verified in-container rescue owner may signal")

        # The single permitted `.kill()` is on the host-side exec handle.
        killers = [n.value.id for n in ast.walk(tree)
                   if isinstance(n, ast.Attribute) and n.attr == "kill"
                   and isinstance(n.value, ast.Name)]
        self.assertEqual(
            killers, ["host_child"],
            f"unexpected kill target(s) {killers}; the only host-side "
            "termination permitted is of the prover's own exec handle")

    # --- behavioural controls ---------------------------------------------

    def test_orphan_induction_never_starts_when_rescue_is_unproven(self):
        """Regression control for the first real run of this prover.

        That run's rescue proof failed on an invalid subject command, and
        the prover correctly skipped orphan induction. The ordering is now
        asserted so it cannot regress into induce-first-rescue-later.
        """
        self.assertTrue(self.unproven["lane_dirty"])
        self.assertFalse(
            self.unproven["orphan_induction_started"],
            "an orphan was induced while the rescue owner was unproven")
        for stage in ("orphan_survives_host_kill", "orphan_rescued"):
            self.assertNotIn(stage, self.unproven,
                             f"{stage} ran despite an unproven rescue owner")

        # Paired positive: a proven rescue does proceed.
        self.assertFalse(self.healthy["lane_dirty"])
        self.assertTrue(self.healthy["orphan_induction_started"],
                        "a proven rescue owner must not block induction; the "
                        "gate is not a blanket refusal")

    def test_verification_happens_without_signalling(self):
        """Verification must be separable from signalling."""
        report = self.healthy["orphan_survives_host_kill"]["reports"][0]
        self.assertTrue(report["verified"])
        self.assertFalse(report["signalled"],
                         "verification signalled; it must be observable alone")
        self.assertEqual(report["outcome"], "verified_not_signalled")

    def test_an_unregistered_nonce_authorizes_no_signal(self):
        """Two-sided ownership: a forged claim is not ownership."""
        report = self.healthy["forged_nonce_rejected"]["reports"][0]
        self.assertFalse(report["verified"])
        self.assertFalse(report["signalled"],
                         "a record with no registry agreement authorized a signal")

    def test_terminated_is_distinguished_from_fully_reaped(self):
        """"Nothing is running" is not "nothing is there".

        A zombie holds a PID slot with no live execution. Collapsing it into
        the same outcome as a reaped process loses a fact the lane's
        operator needs, and it is the distinction that produced the opposite
        error in #711, where counting zombies reported survivors for a tree
        already killed.
        """
        from netbox_hedgehog.tests.test_interchange import containment_rescue
        source = Path(containment_rescue.__file__).read_text(encoding="utf-8")
        self.assertIn('"terminated_zombie"', source)
        self.assertIn('"reaped"', source)
        outcome = self.healthy["orphan_rescued"]["reports"][0]["outcome"]
        self.assertIn(outcome, ("reaped", "terminated_zombie"),
                      f"cleanup outcome {outcome!r} is neither reaped nor "
                      "terminated; a cleanup claim must say which")

    def test_the_bystander_is_never_touched(self):
        report = self.healthy["bystander_intact"]["reports"][0]
        self.assertTrue(report["verified"], "the bystander was not observable")
        self.assertFalse(report["signalled"], "an unrelated subject was signalled")

    def test_teardown_destroys_only_registered_identities(self):
        """Teardown is bounded by the registry, not by a label query."""
        registry = self.healthy["registry"]
        teardown = self.healthy["teardown"]
        self.assertTrue(teardown["proved"])
        self.assertEqual(
            set(teardown["destroyed"]) - set(registry["containers"]), set(),
            "teardown destroyed something the registry never recorded creating")

    def test_cleanup_failure_would_leave_the_lane_dirty(self):
        """An unproved teardown must not read as clean."""
        self.assertIn("lane_dirty", self.healthy)
        self.assertTrue(self.unproven["dirty_reasons"],
                        "a dirty lane recorded no reason")
