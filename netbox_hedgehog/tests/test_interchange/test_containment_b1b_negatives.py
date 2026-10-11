"""#716 B1b discriminating negative controls. Test-only, no induction.

Each control constructs the deficient input and requires B1b to refuse it.
They exist because a successful baseline exercises one happy path and none
of the failure paths -- and every B1b blocker so far has been on a failure
path that the clean run never touched.

Nothing here launches a subject, terminates a host exec, or signals a
process. The probe and observation helpers are exercised directly with
injected values.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


MODULE_DIR = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(f"hh716neg_{name}",
                                                  MODULE_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"hh716neg_{name}"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(f"hh716neg_{name}", None)
    return module


class B1bNegativeControls(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.b1b = _load("containment_b1b")

    # --- (2) malformed probe output must be UNKNOWN -----------------------

    def test_malformed_probe_output_is_unknown(self):
        """Valid JSON is not a valid observation.

        `{}` made `found` falsy and reported absence; `{"found": true}` with
        no state reported liveness. Both are definite answers derived from
        output that said nothing.
        """
        deficient = {
            "{}": "empty object",
            '{"found": "maybe"}': "found is not a boolean",
            '{"found": 1}': "found is an int, not a boolean",
            '{"found": true}': "found without a state",
            '{"found": true, "state": ""}': "empty state",
            '{"found": true, "state": 7}': "state is not a string",
            '["found"]': "a list, not an object",
            "not json at all": "unparseable",
            "": "empty output",
        }
        for payload, why in deficient.items():
            with self.subTest(case=why):
                outcome, detail = self._probe_with(stdout=payload, returncode=0)
                self.assertEqual(
                    outcome, self.b1b.UNKNOWN,
                    f"{why}: reported {outcome!r} ({detail}); a malformed "
                    "observation must be unknown, never absence or liveness")

    def test_sound_probe_output_still_discriminates(self):
        """The strict schema must not reject every real answer."""
        for payload, expected in (
            ('{"found": false}', "false"),
            ('{"found": true, "state": "S"}', "true"),
            ('{"found": true, "state": "Z"}', "false"),
        ):
            with self.subTest(payload=payload):
                outcome, _ = self._probe_with(stdout=payload, returncode=0)
                self.assertEqual(outcome, expected)

    def test_failed_probe_exit_is_unknown(self):
        outcome, detail = self._probe_with(stdout="", returncode=1)
        self.assertEqual(outcome, self.b1b.UNKNOWN, detail)

    def _probe_with(self, stdout, returncode):
        """Drive alive_in with an injected in-container result."""
        class _Result:
            def __init__(self):
                self.stdout = stdout
                self.stderr = "injected"
                self.returncode = returncode

        original = self.b1b.PROVER.in_scenario
        self.b1b.PROVER.in_scenario = lambda *a, **k: _Result()
        try:
            return self.b1b.alive_in("c" * 64, 1234)
        finally:
            self.b1b.PROVER.in_scenario = original

    # --- (3) a failed observation must not pass a preflight check ---------

    def test_failed_observation_is_not_an_empty_result(self):
        """`_observe` must distinguish 'nothing found' from 'could not look'."""
        ok = self.b1b._observe(["true"])
        self.assertTrue(ok["ok"], ok)

        failed = self.b1b._observe(["false"])
        self.assertFalse(failed["ok"],
                         "a non-zero exit was reported as a successful "
                         "observation with an empty result")
        self.assertTrue(failed["why"])

        missing = self.b1b._observe(["hh716-no-such-binary-xyz"])
        self.assertFalse(missing["ok"],
                         "an OSError was reported as a successful observation")

    def test_observe_timeout_is_not_success(self):
        slow = self.b1b._observe(["sleep", "5"], timeout=1)
        self.assertFalse(slow["ok"], "a timeout was reported as success")
        self.assertIn("Timeout", slow["why"])

    # --- (1) the decoy's cleanup identity precedes its creation ----------

    def test_unrecognized_process_state_is_unknown(self):
        """A state token outside proc(5) must not report liveness.

        Requiring only a non-empty string let any token -- "Q", "hello" --
        pass as alive.
        """
        for token in ("Q", "hello", "ZZ", "s", "1", " "):
            with self.subTest(state=token):
                outcome, detail = self._probe_with(
                    stdout=json.dumps({"found": True, "state": token}),
                    returncode=0)
                self.assertEqual(
                    outcome, self.b1b.UNKNOWN,
                    f"state {token!r} reported {outcome!r} ({detail})")

    def test_recognized_states_still_discriminate(self):
        for token, expected in (("R", "true"), ("S", "true"), ("D", "true"),
                                ("Z", "false"), ("T", "true"), ("I", "true")):
            with self.subTest(state=token):
                outcome, _ = self._probe_with(
                    stdout=json.dumps({"found": True, "state": token}),
                    returncode=0)
                self.assertEqual(outcome, expected)

    def test_fixture_disposal_targets_registered_ids_only(self):
        """Host-observed: a same-named stranger survives a disposal pass.

        These two negatives need Docker, and this suite must never have it.
        I mounted the socket twice while building B1b and both times only
        the missing CLI stopped it, so the Docker-dependent work is
        host-side in `containment_b1b_negative_prover.py` and asserted here
        from its evidence.
        """
        record = self._negatives()["foreign_name_not_adopted"]
        self.assertTrue(record["ok"], record)
        self.assertTrue(record["registry_was_empty"],
                        "the registry was not empty, so nothing was at risk")
        self.assertEqual(
            record["state_after_disposal_pass"], "present",
            "a foreign container sharing the decoy name was destroyed; "
            "disposal must go by registered immutable id")

    def test_a_post_creation_failure_still_leaves_a_registered_id(self):
        """Host-observed: registering before start survives a later failure."""
        record = self._negatives()["post_creation_failure_keeps_id"]
        self.assertTrue(record["ok"], record)
        self.assertTrue(record["retained"],
                        "a post-creation failure lost the id, so the "
                        "container could not have been disposed")
        self.assertEqual(record["state_after"], "absent",
                         "the retained id could not be disposed")

    def _negatives(self):
        import os

        location = os.environ.get("HH716_B1B_NEGATIVES")
        if not location:
            raise AssertionError(
                "HH716_B1B_NEGATIVES is unset; run "
                "containment_b1b_negative_prover.py host-side first")
        return json.loads(Path(location).read_text(encoding="utf-8"))

    # --- (4) no unbounded wait on the main path --------------------------

    def test_no_unbounded_communicate_remains(self):
        """An unbounded wait after the kill can stall the baseline."""
        import ast

        tree = ast.parse((MODULE_DIR / "containment_b1b.py").read_text(
            encoding="utf-8"))
        unbounded = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "communicate"):
                if not any(kw.arg == "timeout" for kw in node.keywords):
                    unbounded.append(node.lineno)
        self.assertEqual(unbounded, [],
                         f"unbounded communicate() at lines {unbounded}")

    def test_the_unbounded_detector_detects(self):
        """The control above must fail on a planted call."""
        import ast

        planted = ast.parse("client.communicate()")
        found = [n.lineno for n in ast.walk(planted)
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "communicate"
                 and not any(kw.arg == "timeout" for kw in n.keywords)]
        self.assertTrue(found, "the detector misses an unbounded communicate")

    # --- induction must not have happened in this suite ------------------

    def test_these_controls_perform_no_induction(self):
        """No control here launches, terminates or signals anything.

        Checked by AST, not by grepping this file for the forbidden names --
        a source grep matches the very list it searches for, so it can never
        pass. That self-matching shape has now bitten this programme three
        times, so the check examines call sites instead of text.
        """
        import ast

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        forbidden = {"launch_inner_subject_non_detached", "run_rescue",
                     "kill", "pidfd_send_signal", "terminate"}
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            name = (target.attr if isinstance(target, ast.Attribute)
                    else getattr(target, "id", None))
            if name in forbidden:
                offenders.append((node.lineno, name))
        self.assertEqual(
            offenders, [],
            f"a negative control invokes an induction primitive: {offenders}")

    def test_the_induction_detector_detects(self):
        """The control above must fail on a planted induction call."""
        import ast

        planted = ast.parse("client.kill()\nPROVER.run_rescue(c, [e], True)")
        forbidden = {"kill", "run_rescue"}
        found = []
        for node in ast.walk(planted):
            if isinstance(node, ast.Call):
                target = node.func
                name = (target.attr if isinstance(target, ast.Attribute)
                        else getattr(target, "id", None))
                if name in forbidden:
                    found.append(name)
        self.assertEqual(sorted(found), ["kill", "run_rescue"],
                         "the detector misses a planted induction call")
