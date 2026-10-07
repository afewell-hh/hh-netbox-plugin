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
        # The B1a artifact. These controls previously read the superseded
        # B1 evidence, so the new adversaries and observation-error cases
        # were recorded in the artifact and enforced by nothing.
        cls.b1a = _evidence("HH716_B1A_EVIDENCE")

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
        # B1a removes host-kill induction entirely, so the permitted set is
        # empty here; B1b will reintroduce exactly one kill, of the prover's
        # own exec handle. A subset assertion covers both without loosening
        # the prohibition -- anything other than `host_child` still fails.
        self.assertLessEqual(
            set(killers), {"host_child"},
            f"unexpected kill target(s) {killers}; the only host-side "
            "termination permitted is of the prover's own exec handle")
        self.assertEqual(
            killers, [],
            "B1a must contain no host-side termination at all; induction is "
            "held until B1a is accepted")

    # --- source-level controls on the real functions ---------------------

    def test_not_found_association_is_enforced_by_the_real_function(self):
        """Call the committed function, not a reimplementation of it.

        My previous report of this fix was wrong twice over: the edit had not
        applied, and the probe I ran rebuilt the intended logic inline rather
        than calling `classify_not_found`, so an unchanged function appeared
        to pass. This control calls the real thing.
        """
        import importlib.util
        import sys

        # Register before exec: dataclass processing resolves the module
        # through sys.modules, and a module built from a spec without being
        # registered raises AttributeError on the first @dataclass.
        spec = importlib.util.spec_from_file_location("hh716_prover", PROVER)
        prover = importlib.util.module_from_spec(spec)
        sys.modules["hh716_prover"] = prover
        try:
            spec.loader.exec_module(prover)
        finally:
            sys.modules.pop("hh716_prover", None)

        ours = "a" * 64
        other = "b" * 64
        cases = {
            f"No such container: {ours}": True,
            f"No such object: {ours}": True,
            f"No such container: {other}\nwhile reconciling {ours}": False,
            "Error response from daemon: No such container": False,
            f"daemon busy; could not reach {ours}": False,
            "": False,
        }
        for stderr, expected in cases.items():
            with self.subTest(stderr=stderr[:44]):
                self.assertEqual(
                    prover.classify_not_found(stderr, ours), expected,
                    f"classify_not_found({stderr[:40]!r}) should be {expected}")

    # --- behavioural controls, enforcing the B1a artifact ---------------

    def test_b1a_induces_no_host_kill_baseline(self):
        """B1a must not terminate a host exec at all."""
        self.assertFalse(
            self.b1a["host_kill_baseline_attempted"],
            "B1a attempted a host-kill baseline; induction is held until "
            "B1a is accepted")

    def test_registration_precedes_start_in_recorded_state(self):
        """Read the registry state captured at each step, not the labels.

        A label-only control compares the positions of hand-written event
        names, so moving the real `registry.containers.append` after start
        while leaving `note("register")` in place would still pass. Each
        lifecycle entry now carries a snapshot of the actual registry, which
        makes the claim falsifiable: if registration has not happened, the
        id is simply absent from that snapshot.
        """
        container_id = self.b1a["container_id"]
        entries = {e["event"]: e for e in self.b1a["lifecycle_order"]
                   if "registered_containers" in e}
        for step in ("create", "register", "verify", "start"):
            self.assertIn(step, entries, f"no snapshot recorded at {step}")

        # Falsifiability: the snapshot must vary. If the id were present at
        # every step the check below would be vacuous.
        self.assertNotIn(
            container_id, entries["create"]["registered_containers"],
            "the id was already registered at create, so these snapshots "
            "cannot distinguish registration order")

        for step in ("register", "verify", "start"):
            with self.subTest(step=step):
                self.assertIn(
                    container_id, entries[step]["registered_containers"],
                    f"the container was NOT registered by {step}; an "
                    "unregistered resource cannot be torn down")

        # Each child must be registered BEFORE its exec. The launch_start
        # snapshot is taken after the exec, so an append moved to sit between
        # the exec and that note would still satisfy it. The pre-exec
        # snapshot is the one that cannot be.
        pre_exec = [e for e in self.b1a["lifecycle_order"]
                    if e["event"].startswith("launch_pre_exec:")]
        self.assertTrue(pre_exec, "no pre-exec snapshots were recorded")
        for entry in pre_exec:
            nonce = entry["event"].split(":", 1)[1]
            with self.subTest(nonce=nonce[:20]):
                self.assertIn(
                    nonce, entry["registered_nonces"],
                    "the child was not in the launch registry immediately "
                    "before its exec; a late append would be invisible to "
                    "the post-exec snapshot")

        starts = [e for e in self.b1a["lifecycle_order"]
                  if e["event"].startswith("launch_start:")]
        self.assertEqual(
            len(starts), len(pre_exec),
            "every launch must have both a pre-exec and a start snapshot")

        self.assertIn(container_id, self.b1a["registry"]["containers"])

    def test_every_adversary_mutates_exactly_one_field(self):
        """A rejection must be attributable to the field it violates.

        Without this, six rejections could all come from one unrelated
        fault -- which is exactly what happened when a failed `bind()` edit
        left every entry with no expected argv: all six were rejected, for
        the wrong reason, and it looked like success.
        """
        adversaries = self.b1a["adversaries_rejected"]
        self.assertGreaterEqual(len(adversaries), 6)
        for name, record in sorted(adversaries.items()):
            with self.subTest(adversary=name):
                self.assertIsNotNone(record, f"{name} produced no report")
                self.assertFalse(record["verified"])
                self.assertFalse(record["signalled"],
                                 f"{name} authorized a signal")
                self.assertTrue(
                    record["unrelated_fields_valid"],
                    f"{name} failed checks {record['failing_checks']}, not only "
                    f"{record['mutated_field']}; the rejection is not "
                    "attributable to the mutated field")
                self.assertEqual(record["failing_checks"],
                                 [record["mutated_field"]])

    def test_a_sound_positive_is_paired_with_the_negatives(self):
        """All-negatives-pass is indistinguishable from a broken comparison."""
        verified = self.b1a["verifies_without_signalling"]["reports"][0]
        self.assertTrue(verified["verified"],
                        "no sound positive: the negatives prove nothing alone")
        self.assertFalse(verified["signalled"])
        self.assertTrue(self.b1a["rescue_owner_proven"])

    def test_observation_errors_are_unknown_never_a_result(self):
        errors = self.b1a["observation_errors"]
        for case in ("already_exited", "unpinnable_pid", "malformed_pid"):
            with self.subTest(case=case):
                record = errors.get(case)
                self.assertIsNotNone(record, f"{case} was not exercised")
                self.assertEqual(
                    record["outcome"], "unknown",
                    f"{case} produced {record['outcome']!r}; a failed "
                    "observation must never read as reaped or clean")
                self.assertFalse(record["signalled"])

    def test_teardown_failure_and_empty_registry_do_not_prove(self):
        """Successful disposal alone does not show the failure path works."""
        self.assertTrue(self.b1a["teardown"]["proved"],
                        "the real teardown must prove, or the positive is absent")
        self.assertFalse(
            self.b1a["teardown_failure_control"]["proved"],
            "a registered ID that never existed was reported as destroyed")
        self.assertEqual(self.b1a["teardown_failure_control"]["outcome"], "unknown")
        self.assertFalse(
            self.b1a["teardown_empty_registry_control"]["proved"],
            "an empty registry reported a successful teardown")

    def test_the_rm_f_observation_is_scoped_to_this_environment(self):
        """A local daemon behaviour must not be recorded as universal."""
        environment = self.b1a["environment"]
        self.assertTrue(environment["docker_server_version"])
        self.assertIn("not asserted as universal",
                      environment["rm_f_note"].lower())
