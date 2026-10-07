"""#711 Phase C RED contract for the supported test-runner boundary.

Test-only. No runner script, workflow, documentation, production module, or
test-selection policy is changed here; Phase D implements the contract.

Background measured in Phase A/B and recorded on #711: raw `manage.py test`
reaches the two evidence-requiring Interchange modules and fails with
`HarnessEvidenceMissing` and a read-only-mount assertion, which read as
product defects. The accepted design is selective preparation by the
supported wrapper plus an early, actionable refusal on the raw path.

Three things this suite does deliberately, each from review:

* **Fresh processes only.** Python caches imports, so an in-process check
  proves nothing about the next run, and once the hook exists an in-process
  import would terminate the test process. Every refusal claim spawns.
* **Every selector shape.** `load_tests` was proposed and rejected because
  `module.Class` and `module.Class.method` bypass it; the shapes are
  enumerated so a mechanism cannot pass by guarding only the one probed.
* **Both directions.** Rows that must refuse sit beside rows that must still
  run, so the contract cannot be satisfied by refusing everything.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from django.test import SimpleTestCase

from netbox_hedgehog.tests.test_interchange.runner_contract_support import (
    CONTRACT_MODULE,
    ORDINARY_MARKER,
    PROTECTED_MARKER,
    build_fixture_tree,
    decisions_from_output,
    load_driver_evidence,
    validate_decision_binding,
    EVIDENCE_VARIABLES,
    GRANDPARENT_SELECTION,
    PROTECTED_MODULES,
    REQUIRED_ENTRY_POINTS,
    UNPROTECTED_MODULES,
    UNRELATED_MODULE,
    ContractRow,
    RunnerContractAbsent,
    evidence_visible_to_child,
    import_in_fresh_process,
    raw_django,
    require_runner_contract,
)


PROTECTED = PROTECTED_MODULES[0]

CONTRACT_ROWS = (
    ContractRow("R01", "test_r01_module_selection_is_refused", "module label", "selector"),
    ContractRow("R02", "test_r02_class_selection_is_refused", "class label", "selector"),
    ContractRow("R03", "test_r03_method_selection_is_refused", "method label", "selector"),
    ContractRow("R04", "test_r04_parent_package_selection_is_refused", "parent label", "selector"),
    ContractRow("R05", "test_r05_options_only_invocation_is_refused", "options-only", "selector"),
    ContractRow("R06", "test_r06_unprotected_interchange_modules_still_run_raw", "fast path kept", "compatibility"),
    ContractRow("R07", "test_r07_unrelated_suite_still_runs_raw", "no leakage", "compatibility"),
    ContractRow("R08", "test_r08_refusal_precedes_every_test_body", "early boundary", "boundary"),
    ContractRow("R09", "test_r09_refusal_is_distinct_from_a_crash", "not a crash", "boundary"),
    ContractRow("R10", "test_r10_remediation_names_a_runnable_command", "actionable", "remediation"),
    ContractRow("R11", "test_r11_declaration_matches_discovered_modules", "declaration bound", "declaration"),
    ContractRow("R12", "test_r12_deleting_a_declaration_fails_closed", "deletion fails closed", "declaration"),
    ContractRow("R13", "test_r13_selection_matching_is_dot_component_aware", "no substring match", "selector"),
    ContractRow("R14", "test_r14_import_hook_scope_is_fresh_process_only", "fresh-process scope", "boundary"),
    ContractRow("R15", "test_r15_grandparent_selection_is_refused", "grandparent label", "selector"),
    ContractRow("R16", "test_r16_wrapper_broad_selection_prepares", "wrapper prepares", "compatibility"),
    ContractRow("R17", "test_r17_preflight_is_not_an_integrity_exemption", "no exemption", "boundary"),
    ContractRow("R18", "test_r18_declared_case_consumes_fresh_evidence", "paired positive", "declaration"),
    ContractRow("R19", "test_r19_fast_path_creates_no_preparation_containers", "no needless prep", "compatibility"),
    ContractRow("R20", "test_r20_lifecycle_observer_detects_real_preparation", "observer positive", "compatibility"),
    ContractRow("R21", "test_r21_no_argument_invocation_keeps_topology_default", "default kept", "remediation"),
    ContractRow("R22", "test_r22_option_value_resembling_a_label_does_not_prepare", "option value", "selector"),
    ContractRow("R23", "test_r23_ci_membership_is_independent_of_evidence_metadata", "ci membership", "declaration"),
    ContractRow("R24", "test_r24_hold_persists_while_host_is_not_observing", "hold persists", "boundary"),
    ContractRow("R25", "test_r25_every_selector_shape_reaches_the_prerequisite_seam", "seam plumbing", "selector"),
    ContractRow("R26", "test_r26_the_boundary_and_its_binding_are_load_bearing", "seam mutations", "selector"),
)

AREAS = ("selector", "compatibility", "boundary", "remediation", "declaration")

#: Accepted Phase B amendments mapped to the tests that carry them, or named
#: as still-open gates. Dev B's point: area and entry-point coverage cannot
#: prove these obligations exist, because both are satisfied by a suite that
#: never expresses them. A row here is either a method that must exist -- the
#: control below fails if one is renamed away -- or an explicit gate with a
#: reason, which is a visible debt rather than a silent omission.
#:
#: Rows marked OPEN are not claimed as covered. Several are genuinely not yet
#: expressible, and two (T03, T07, T10-T12) I could not resolve from the issue
#: thread; I would rather name that than map them to something approximate.
#: Rows whose evidence cannot be produced until #715 lands. They are left
#: failing and annotated -- never skipped, xfailed, or rewritten to pass
#: against a weaker observation. Each needs the supported wrapper to run the
#: declared protected module, which is SimpleTestCase-only and therefore
#: cannot run today: DietTestRunner asks the DIET-643 guard about an alias
#: Django never prepared, and the guard correctly refuses.
#:
#: Measured in #715 Phase A: SimpleTestCase-only gives get_databases()==[]
#: and setup_databases()==[], leaving connections['default'] on 'netbox'.
BLOCKED_BY_715 = {
    "test_r10_remediation_names_a_runnable_command":
        "the remediation round-trip drives the declared protected module, "
        "which the supported wrapper cannot run until #715 lands",
    "test_r12_deleting_a_declaration_fails_closed":
        "declaration removal is exercised against the declared protected "
        "module, which cannot run through the wrapper until #715 lands",
    "test_r20_lifecycle_observer_detects_real_preparation":
        "its positive must be a genuinely preparation-required selection; "
        "the only one available is the declared protected module, blocked "
        "by #715. Re-pointing it at a non-preparing selection would lock in "
        "the defect R13 exists to remove",
    "test_r16_wrapper_broad_selection_prepares":
        "a broad interchange selection includes the SimpleTestCase-only "
        "protected module, so the run cannot complete through the wrapper",
    "test_r17_preflight_is_not_an_integrity_exemption":
        "its sound-evidence pair is declared_ok, which cannot run; the "
        "post-preflight integrity rejection was independently observed and "
        "stands as regression evidence, but does not substitute for the pair",
    "test_r18_declared_case_consumes_fresh_evidence":
        "declared_ok is the declared protected module itself",
}

AMENDMENT_MAP = {
    "T01": ("test_r18_declared_case_consumes_fresh_evidence",
            "test_r12_deleting_a_declaration_fails_closed"),
    "T02": ("test_r19_fast_path_creates_no_preparation_containers",
            "test_r20_lifecycle_observer_detects_real_preparation"),
    "T03": ("test_r23_ci_membership_is_independent_of_evidence_metadata",),
    "T04a": ("test_r11_declaration_matches_discovered_modules",),
    "T04b": ("test_r13_selection_matching_is_dot_component_aware",),
    "T04c": ("test_r12_deleting_a_declaration_fails_closed",),
    "T04d": ("test_r12_deleting_a_declaration_fails_closed",),
    "T05a": ("test_r01_module_selection_is_refused",),
    "T05b": ("test_r02_class_selection_is_refused",),
    "T05c": ("test_r03_method_selection_is_refused",),
    "T05d": ("test_r04_parent_package_selection_is_refused",),
    "T05e": ("test_r15_grandparent_selection_is_refused",),
    "T05f": ("test_r05_options_only_invocation_is_refused",),
    "T05g": ("test_r06_unprotected_interchange_modules_still_run_raw",),
    "T05h": ("test_r07_unrelated_suite_still_runs_raw",),
    "T05i": ("test_r09_refusal_is_distinct_from_a_crash",),
    "T05j": ("test_r16_wrapper_broad_selection_prepares",),
    "T06": ("test_r10_remediation_names_a_runnable_command",),
    "T07": ("test_r06_unprotected_interchange_modules_still_run_raw",
            "test_r07_unrelated_suite_still_runs_raw"),
    "T08": ("test_every_row_is_declared_and_exists",
            "test_observers_reject_single_fault_outcomes"),
    "T09": ("test_r17_preflight_is_not_an_integrity_exemption",),
    "T10": ("test_r19_fast_path_creates_no_preparation_containers",),
    "T13": ("test_r24_hold_persists_while_host_is_not_observing",),
    "T11": ("test_r05_options_only_invocation_is_refused",
            "test_r21_no_argument_invocation_keeps_topology_default"),
    "T12": ("test_r22_option_value_resembling_a_label_does_not_prepare",),
}


class RunnerContractRedTests(SimpleTestCase):
    """Rows that fail until #711 Phase D implements the contract."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tree_dir = tempfile.TemporaryDirectory(prefix="hh711-tree-")
        cls.tree = build_fixture_tree(Path(cls._tree_dir.name))

    @classmethod
    def tearDownClass(cls):
        cls._tree_dir.cleanup()
        super().tearDownClass()

    def fixture_env(self):
        """PYTHONPATH for the disposable tree; no evidence for its protected module."""
        return {"PYTHONPATH": str(self.tree.root)}

    def assert_refused(self, outcome, label, marker_bearing=True,
                       invocation=None, selection=None):
        """A refusal, observed by markers and backed by a bound decision.

        Order matters. Binding is checked FIRST, against what the child
        itself published, because that is the evidence that changes when the
        contract is implemented. Checking `require_runner_contract()` first
        made the binding check unreachable for every core row: the contract
        is absent today, so the row raised before binding was ever examined,
        and the validator guarded nothing.
        """
        self.assertFalse(
            outcome.timed_out,
            f"{label}: no refusal within the bound; the selection ran instead")
        self.assertEqual(
            outcome.survivors, 0,
            f"{label}: {outcome.survivors} descendant(s) survived the bound")

        self.assertIsNotNone(
            invocation,
            f"{label}: no invocation was supplied, so this refusal cannot be "
            "bound to the run that produced it")
        published = [{"request": {"module": d.get("module")}, "decision": d}
                     for d in decisions_from_output(outcome.combined)]
        bound, reasons = validate_decision_binding(
            published, invocation, selection or (), self.tree.protected)
        self.assertTrue(
            bound, f"{label}: the refusal is not backed by a bound decision: "
                   f"{reasons}")

        if marker_bearing:
            self.assertFalse(outcome.body_ran(ORDINARY_MARKER),
                             f"{label}: an ordinary body ran before the refusal")
            self.assertFalse(outcome.body_ran(PROTECTED_MARKER),
                             f"{label}: the protected body ran")
        self.assertEqual(outcome.tests_executed, 0,
                         f"{label}: {outcome.tests_executed} test(s) executed before refusal")

        contract = require_runner_contract()
        self.assertEqual(
            outcome.returncode, contract.PREREQUISITE_EXIT_CODE,
            f"{label}: expected the prerequisite exit code, got {outcome.returncode}")
        self.assertIn(contract.PREREQUISITE_DIAGNOSTIC, outcome.combined,
                      f"{label}: refusal must carry the stable diagnostic token")

    def refusal_invocation(self, shape):
        """A per-row invocation id, so each refusal binds to its own run."""
        return f"inv-{shape}-{os.getpid()}"

    def fixture_run(self, *labels, **kwargs):
        
        """Drive the real loader against the disposable tree.

        B2: parent, grandparent and options-only selections discover every
        sibling of their target. Against the real tree that rediscovers this
        driver and respawns it -- measured four levels deep. This tree names
        nothing in the suite, so it cannot.
        """
        kwargs.setdefault("env", self.fixture_env())
        kwargs.setdefault("keepdb", False)
        kwargs.setdefault("timeout", 120)
        return raw_django(*labels, **kwargs)

    # --- selector shapes -------------------------------------------------

    def test_r01_module_selection_is_refused(self):
        invocation = self.refusal_invocation("module")
        self.assert_refused(
            self.fixture_run(self.tree.protected, env={**self.fixture_env(),
                                   "HH711_INVOCATION": invocation}),
            "module", invocation=invocation, selection=(self.tree.protected,))

    def test_r02_class_selection_is_refused(self):
        invocation = self.refusal_invocation("class")
        self.assert_refused(
            self.fixture_run(self.tree.protected_class, env={**self.fixture_env(),
                                   "HH711_INVOCATION": invocation}),
            "class", invocation=invocation, selection=(self.tree.protected_class,))

    def test_r03_method_selection_is_refused(self):
        invocation = self.refusal_invocation("method")
        self.assert_refused(
            self.fixture_run(self.tree.protected_method, env={**self.fixture_env(),
                                   "HH711_INVOCATION": invocation}),
            "method", invocation=invocation, selection=(self.tree.protected_method,))

    def test_r04_parent_package_selection_is_refused(self):
        invocation = self.refusal_invocation("parent")
        self.assert_refused(
            self.fixture_run(self.tree.parent, env={**self.fixture_env(),
                                   "HH711_INVOCATION": invocation}),
            "parent", invocation=invocation, selection=(self.tree.parent,))

    def test_r05_options_only_invocation_is_refused(self):
        """No labels means Django's broad discovery, which reaches protected modules.

        Rejected early with the supported command rather than guessed at.
        """
        # Bounded deliberately: with the contract absent this invocation
        # discovers and runs the entire tree. A timeout is reported as
        # "did not refuse" rather than hanging the suite.
        invocation = self.refusal_invocation("options-only")
        self.assert_refused(
            self.fixture_run(cwd=self.tree.root, timeout=90,
                             env={**self.fixture_env(),
                                  "HH711_INVOCATION": invocation}),
            "options-only", invocation=invocation, selection=())

    def test_r13_selection_matching_is_dot_component_aware(self):
        """`test_interchange_audit_retention` is not inside `test_interchange`.

        Today's wrapper matches it by string prefix and prepares needlessly;
        the contract must compare dot components.
        """
        sibling = ("netbox_hedgehog.tests.test_interchange_audit_retention",)
        record = load_driver_evidence("sibling_not_inside", sibling)
        self.assertEqual(record["verdict"], "held",
                         f"the decision was not observable: {record['verdict_reasons']}")
        self.assertEqual(record["group_survivors_after_cleanup"], 0,
                         "the observation left processes behind")
        self.assertFalse(
            record["prepared"],
            "the wrapper prepared a module that only shares a name prefix; "
            "`run_diet_tests.sh` matches with == netbox_hedgehog.tests.test_interchange* "
            "so test_interchange_audit_retention is treated as inside the package")
        self.assertEqual(record["returncode"], 0, record["stderr_tail"][-300:])
        self.assertGreater(record["tests_executed"], 0)

    def test_r15_grandparent_selection_is_refused(self):
        """Two levels up still reaches protected modules.

        Listed separately from the parent row in Dev B's acceptance, and not
        inferable from it: a mechanism could match the immediate package and
        miss `netbox_hedgehog.tests`.
        """
        invocation = self.refusal_invocation("grandparent")
        self.assert_refused(
            self.fixture_run(self.tree.grandparent,
                             env={**self.fixture_env(),
                                  "HH711_INVOCATION": invocation}),
            "grandparent", invocation=invocation,
            selection=(self.tree.grandparent,))

    def test_r25_every_selector_shape_reaches_the_prerequisite_seam(self):
        """Each selector shape reaches the boundary, bound, and completes.

        A sound boundary ALLOWS, so the child must run to completion: exit 0
        and real bodies. The earlier version checked only that a ledger entry
        existed, which an assertion-level probe passed with exit 3, zero
        tests and a refusal after the write -- a boundary could be reached,
        refuse, and still satisfy it.

        Binding is per shape: the recorded decision must echo this run's
        invocation and the selection as the boundary normalized it, so five
        shapes cannot write five indistinguishable entries.
        """
        from netbox_hedgehog.tests.test_interchange.runner_contract_seam_adapter import (
            LEDGER_VARIABLE)
        from netbox_hedgehog.tests.test_interchange.runner_contract_support import (
            INVOCATION_VARIABLE, SEAM_VARIABLE)

        sound = ("netbox_hedgehog.tests.test_interchange."
                 "runner_contract_seam_adapter.sound_decision")
        # Expected normalized selections are written out per shape rather
        # than computed with the adapter's own helper. Validating the
        # adapter's output with the adapter's normalizer is circular: a bug
        # in the helper would satisfy both sides.
        shapes = {
            "module": ((self.tree.protected,), (self.tree.protected,), None),
            "class": ((self.tree.protected_class,), (self.tree.protected_class,), None),
            "method": ((self.tree.protected_method,), (self.tree.protected_method,), None),
            "parent": ((self.tree.parent,), (self.tree.parent,), None),
            "grandparent": ((self.tree.grandparent,), (self.tree.grandparent,), None),
            # Genuinely no labels: discovery from the tree root. The previous
            # "options-only-ish" shape passed an explicit parent label, which
            # is a parent-plus-option invocation, not the shape R05 exercises.
            "options-only": ((), (), self.tree.root),
            "parent-plus-option": (
                (self.tree.parent, "--exclude-tag", "slow"), (self.tree.parent,), None),
            "mixed": ((self.tree.ordinary, self.tree.protected),
                      (self.tree.ordinary, self.tree.protected), None),
        }
        with tempfile.TemporaryDirectory(prefix="hh711-seam-") as workspace:
            for shape, (labels, expected_selection, cwd) in shapes.items():
                with self.subTest(shape=shape):
                    invocation = f"inv-{shape}-{os.getpid()}"
                    ledger = Path(workspace) / f"{shape}.json"
                    extra = {"cwd": cwd} if cwd else {}
                    outcome = self.fixture_run(*labels, **extra, env={
                        "PYTHONPATH": f"{self.tree.root}:{Path(__file__).resolve().parents[3]}",
                        SEAM_VARIABLE: sound,
                        INVOCATION_VARIABLE: invocation,
                        LEDGER_VARIABLE: str(ledger),
                    })
                    self.assertFalse(outcome.timed_out, f"{shape}: timed out")
                    self.assertTrue(ledger.exists(),
                                    f"{shape}: the selection never reached the boundary")
                    entries = json.loads(ledger.read_text(encoding="utf-8"))

                    bound = [e for e in entries
                             if e["decision"]["invocation"] == invocation]
                    self.assertTrue(
                        bound,
                        f"{shape}: no decision carried this run's invocation "
                        f"{invocation!r}; entries={entries}")
                    decision, request = bound[0]["decision"], bound[0]["request"]

                    self.assertEqual(
                        tuple(decision["normalized_selection"]),
                        tuple(expected_selection),
                        f"{shape}: the boundary normalized the selection to "
                        f"{decision['normalized_selection']!r}, expected "
                        f"{list(expected_selection)!r}")
                    # Restored: the regression R25 originally caught was the
                    # fixture naming a literal '{module}' placeholder, which a
                    # completing child would otherwise hide.
                    self.assertEqual(
                        request["module"], self.tree.protected,
                        f"{shape}: the boundary was consulted for "
                        f"{request['module']!r}, not the protected module")
                    self.assertEqual(
                        tuple(request["selection"]), tuple(labels),
                        f"{shape}: the request carried a different selection")
                    self.assertIn("evidence_context", request,
                                  f"{shape}: the request carried no evidence context")
                    self.assertTrue(decision["allow"],
                                    f"{shape}: the sound boundary did not allow")

                    # A sound boundary allows, so the child must complete.
                    self.assertEqual(
                        outcome.returncode, 0,
                        f"{shape}: a sound ALLOW decision did not complete: "
                        f"{outcome.combined[-300:]}")
                    self.assertGreater(
                        outcome.tests_executed, 0,
                        f"{shape}: no bodies executed under a sound ALLOW; a "
                        "boundary that is reached and then refuses must not "
                        "satisfy this row")

    def test_r26_the_boundary_and_its_binding_are_load_bearing(self):
        """Mutations that the core refusal path must reject.

        Each previously had a weaker form: the first observed normal RED
        absence instead of removing anything, and the second merely recorded
        that the emitter's fields were empty, which certifies the fault was
        constructed rather than that anything rejects it.
        """
        from netbox_hedgehog.tests.test_interchange.runner_contract_seam_adapter import (
            LEDGER_VARIABLE)
        from netbox_hedgehog.tests.test_interchange.runner_contract_support import (
            INVOCATION_VARIABLE, SEAM_VARIABLE)

        plugin_root = str(Path(__file__).resolve().parents[3])
        protected_source = (self.tree.root / "hh711_root" / "pkg" /
                            "test_protected.py")
        sound = ("netbox_hedgehog.tests.test_interchange."
                 "runner_contract_seam_adapter.sound_decision")
        emitter = ("netbox_hedgehog.tests.test_interchange."
                   "runner_contract_seam_adapter.unbound_emitter")

        with self.subTest(mutation="boundary removed, child runs freely"):
            original = protected_source.read_text(encoding="utf-8")
            # Remove the ENTIRE boundary block, not just the _decide() call.
            # Stripping only the call left the contract import in place, so
            # the child still died on the missing module: the mutation never
            # produced a boundary-free run, and `Ran 1 test` was counting
            # unittest's failed-loader placeholder rather than a body.
            class_at = original.index("class ProtectedFixture")
            boundary_free = ("from django.test import SimpleTestCase\n\n\n"
                             + original[class_at:])
            self.assertNotIn("_decide(", boundary_free,
                             "the mutation left the boundary call in place")
            self.assertNotIn("import_module", boundary_free,
                             "the mutation left the contract import in place, so "
                             "the child would fail on that rather than run freely")
            protected_source.write_text(boundary_free, encoding="utf-8")
            try:
                invocation = self.refusal_invocation("boundary-removed")
                outcome = self.fixture_run(self.tree.protected, env={
                    "PYTHONPATH": f"{self.tree.root}:{plugin_root}",
                    "HH711_INVOCATION": invocation})

                # The mutation must produce a SUCCESSFUL boundary-free run.
                # Anything less and this is not exercising what it claims.
                self.assertEqual(
                    outcome.returncode, 0,
                    f"the boundary-free child did not complete cleanly: "
                    f"{outcome.combined[-400:]}")
                self.assertTrue(
                    outcome.body_ran(PROTECTED_MARKER),
                    "the protected body did not run, so no real execution "
                    "occurred; a loader placeholder counts in tests_executed "
                    "but is not a body")
                self.assertGreater(outcome.tests_executed, 0)
                self.assertEqual(
                    decisions_from_output(outcome.combined), [],
                    "a boundary-free child published a decision")

                # Now the shared core checker must reject that completion,
                # and for the right reason.
                with self.assertRaises(AssertionError) as caught:
                    self.assert_refused(
                        outcome, "boundary removed", invocation=invocation,
                        selection=(self.tree.protected,))
                message = str(caught.exception)
                self.assertNotIn(
                    "runner contract absent", message,
                    "the checker rejected on contract absence, not on the "
                    f"mutation: {message}")
                self.assertIn(
                    "not backed by a bound decision", message,
                    f"the rejection must name the missing binding: {message}")
            finally:
                protected_source.write_text(original, encoding="utf-8")

        with self.subTest(mutation="unbound emitter must be REJECTED"):
            with tempfile.TemporaryDirectory(prefix="hh711-mut-") as workspace:
                ledger = Path(workspace) / "ledger.json"
                invocation = f"inv-emitter-{os.getpid()}"
                outcome = self.fixture_run(self.tree.protected, env={
                    "PYTHONPATH": f"{self.tree.root}:{plugin_root}",
                    SEAM_VARIABLE: emitter,
                    INVOCATION_VARIABLE: invocation,
                    LEDGER_VARIABLE: str(ledger),
                })
                entries = json.loads(ledger.read_text(encoding="utf-8"))
                ok, reasons = validate_decision_binding(
                    entries, invocation, (self.tree.protected,),
                    self.tree.protected)
                self.assertFalse(
                    ok,
                    "a fabricated refusal with no binding was accepted; exit "
                    "code, diagnostic and absence of bodies are all forgeable "
                    f"together, so only binding separates them: {reasons}")
                self.assertEqual(outcome.tests_executed, 0,
                                 "the emitter did stop the child, which is why "
                                 "body-count alone cannot discriminate")

        with self.subTest(positive="a bound decision is accepted"):
            with tempfile.TemporaryDirectory(prefix="hh711-pos-") as workspace:
                ledger = Path(workspace) / "ledger.json"
                invocation = f"inv-sound-{os.getpid()}"
                self.fixture_run(self.tree.protected, env={
                    "PYTHONPATH": f"{self.tree.root}:{plugin_root}",
                    SEAM_VARIABLE: sound,
                    INVOCATION_VARIABLE: invocation,
                    LEDGER_VARIABLE: str(ledger),
                })
                entries = json.loads(ledger.read_text(encoding="utf-8"))
                ok, reasons = validate_decision_binding(
                    entries, invocation, (self.tree.protected,),
                    self.tree.protected)
                self.assertTrue(ok, f"a genuinely bound decision was rejected: "
                                    f"{reasons}")

    # --- compatibility: the contract must not become a blanket refusal ----    # --- compatibility: the contract must not become a blanket refusal ----    # --- compatibility: the contract must not become a blanket refusal ----

    def test_r06_unprotected_interchange_modules_still_run_raw(self):
        for module in UNPROTECTED_MODULES:
            with self.subTest(module=module):
                outcome = raw_django(module)
                self.assertEqual(outcome.returncode, 0, outcome.combined[-400:])
                self.assertGreater(outcome.tests_executed, 0,
                                   "a compatibility row must show real execution")

    def test_r07_unrelated_suite_still_runs_raw(self):
        outcome = raw_django(UNRELATED_MODULE)
        self.assertEqual(outcome.returncode, 0, outcome.combined[-400:])
        self.assertGreater(outcome.tests_executed, 0,
                           "a compatibility row must show real execution")

    def test_r16_wrapper_broad_selection_prepares(self):
        """Raw broad discovery refuses; the supported wrapper must prepare.

        This is the distinction Dev B asked to be falsifiable. R04/R05/R15
        pin the raw side, and without this row a contract that refused broad
        selection everywhere -- wrapper included -- would satisfy all of
        them while making the supported command unusable.
        """
        # Broad, but slow-tagged cases excluded: the claim is that a broad
        # supported selection *prepares*, not that the heaviest suite fits
        # in the lane. The full package SIGKILLed it at rc=137.
        selection = ("netbox_hedgehog.tests.test_interchange", "--exclude-tag", "slow")
        record = load_driver_evidence("broad_supported", selection)
        self.assertTrue(record["prepared"],
                        "the supported wrapper must prepare a broad selection")
        self.assertGreater(record["tests_executed"], 0,
                           "preparation that executes nothing is not preparation")
        # Deliberately NOT asserting returncode == 0. A broad interchange
        # selection includes this RED suite, whose rows are expected to fail,
        # so requiring a clean exit would make the row unpassable by
        # construction rather than by the contract's absence. The claim here
        # is that the wrapper *prepares and executes*, not that every test in
        # the package passes; refusal is what must not happen.
        self.assertFalse(record.get("timed_out"), "the broad selection timed out")
        self.assertIn(
            record["returncode"], (0, 1),
            f"exit {record['returncode']} is not a test result: 2 is a usage error, "
            "137 a kill, -1 a timeout. Only a clean run or ordinary test failures "
            "count as the wrapper having executed the selection.")
        if record["returncode"] == 1:
            self.assertIn(
                "test_runner_contract_red", record["stdout_tail"] + record["stderr_tail"],
                "the broad selection failed, but not with this suite's expected RED "
                "rows; an unidentified failure is not an accepted outcome")

    def test_r19_fast_path_creates_no_preparation_containers(self):
        """T10/T02-negative: the topology fast path prepares nothing.

        Observed at the barrier, so no body executes to establish it. Timing
        is reported, never gated on a ratio -- a ratio fails on machine load
        rather than on behaviour.
        """
        selection = ("netbox_hedgehog.tests.test_topology_planning.test_port_allocator",)
        record = load_driver_evidence("topology_fast_path", selection)
        self.assertEqual(record["verdict"], "held",
                         f"the decision was not observable: {record['verdict_reasons']}")
        self.assertFalse(record["prepared"],
                         "the fast path triggered preparation it does not need")
        self.assertEqual(record["group_survivors_after_cleanup"], 0)
        print(f"\n      [R19] reached barrier in {record['elapsed_to_barrier']}s "
              "(reported, not gated)")

    def test_r24_hold_persists_while_host_is_not_observing(self):
        """The only row that pays the persistence gap.

        A hold that survives only while the host watches is not a hold. This
        control alone requires the 125s unobserved gap; every other held row
        asserts marker, binding, no bodies and a live child without waiting,
        because re-proving persistence per row would add a minute of sleeping
        each for a property established once.
        """
        selection = ("netbox_hedgehog.tests.test_topology_planning.test_port_allocator",)
        record = load_driver_evidence("held_while_unobserved", selection)
        self.assertEqual(record["verdict"], "held",
                         f"not certified as held: {record['verdict_reasons']}")
        self.assertIsNotNone(record["persistence_gap"],
                             "this control must record an observation gap")
        self.assertGreaterEqual(
            record["persistence_gap"], 125,
            "the gap is too short to show the hold persists unobserved")
        self.assertEqual(record["group_survivors_after_cleanup"], 0)

    def test_r20_lifecycle_observer_detects_real_preparation(self):
        """T02-positive: the observer must detect preparation that really happens.

        Previously this used `sibling_not_inside` as its positive, asserting
        `prepared=True` — while R13 requires that same scenario to be False
        once the wrapper is fixed. The two could not both hold, so a correct
        GREEN implementation would have broken one of them. Asserting that a
        current defect must persist is not a regression guard; it is a lock
        on the bug.

        The positive is now a selection that genuinely requires preparation:
        the declared protected module. That selection cannot run until #715
        lands, so this row is blocked rather than quietly re-pointed at
        something convenient.
        """
        record = load_driver_evidence("declared_ok", (PROTECTED,))
        self.assertTrue(
            record["attributed_containers"],
            "no preparation container was attributed to a selection that "
            "genuinely prepares; R19's negative is worthless unless this "
            "positive fires, because an observer that detects nothing reports "
            "'no containers' either way")

    def test_r21_no_argument_invocation_keeps_topology_default(self):
        """T11: bare invocation keeps its explicit topology default."""
        record = load_driver_evidence("no_argument_default", ())
        notes = json.loads(record["notes"])
        self.assertEqual(
            notes["common_args_applied"], [],
            "options were injected into the bare invocation, so this no longer "
            "tests bare invocation: the wrapper substitutes its default only "
            "when $# -eq 0, and one extra argument made it discover the whole tree")
        self.assertEqual(
            len(notes["argv"]), 1,
            f"the recorded argv is not a bare invocation: {notes['argv']}")
        self.assertEqual(record["returncode"], 0, record["stderr_tail"][-300:])
        self.assertGreater(record["tests_executed"], 0,
                           "the no-argument default executed nothing")
        self.assertFalse(record["prepared"],
                         "the topology default must not trigger preparation")

    def test_r22_option_value_resembling_a_label_does_not_prepare(self):
        """T12: an option *value* that looks like a protected label is not one.

        The wrapper matches arguments positionally today, so a supported
        option whose value happens to spell a protected package can be read
        as a selection and prepare needlessly.
        """
        selection = ("netbox_hedgehog.tests.test_topology_planning.test_port_allocator",
                     "--exclude-tag", "netbox_hedgehog.tests.test_interchange")
        record = load_driver_evidence("option_value_lookalike", selection)
        self.assertEqual(record["verdict"], "held",
                         f"the decision was not observable: {record['verdict_reasons']}")
        self.assertFalse(record["prepared"],
                         "an option value was mistaken for a protected selection")
        self.assertEqual(record["group_survivors_after_cleanup"], 0)

    def test_r23_ci_membership_is_independent_of_evidence_metadata(self):
        """T03: discovery governs CI membership; metadata governs preparation.

        Security modules must stay CI-enforced whether or not they require
        evidence, so membership is derived from source discovery and never
        from the evidence declaration. A declared requirement additionally
        triggers preparation -- the two must not collapse into one list.
        """
        contract = require_runner_contract()
        here = Path(__file__).resolve().parent
        discovered = {f"netbox_hedgehog.tests.test_interchange.{path.stem}"
                      for path in here.glob("test_*.py")}
        self.assertTrue(discovered, "discovery found no interchange test modules")

        declared = set(contract.EVIDENCE_REQUIREMENTS)
        self.assertTrue(declared.issubset(discovered),
                        f"declared modules not discoverable from source: {declared - discovered}")
        self.assertTrue(discovered - declared,
                        "every discovered module requires evidence, so this control "
                        "cannot show membership is independent of the declaration")

        record = load_driver_evidence("declared_ok", (PROTECTED,))
        self.assertTrue(record["prepared"],
                        "a declared requirement must additionally trigger preparation")

    # --- the boundary ----------------------------------------------------

    def test_r08_refusal_precedes_every_test_body(self):
        """An ordinary body listed first must never run.

        This is the row that distinguishes a real pre-execution boundary from
        a per-module error: unittest turns a load-time raise into a placeholder
        and keeps going, so earlier bodies still execute.
        """
        invocation = self.refusal_invocation("mixed")
        outcome = self.fixture_run(
            self.tree.ordinary, self.tree.protected,
            env={**self.fixture_env(), "HH711_INVOCATION": invocation})
        self.assert_refused(outcome, "mixed selection", invocation=invocation,
                            selection=(self.tree.ordinary, self.tree.protected))

    def test_r09_refusal_is_distinct_from_a_crash(self):
        """An unrelated failure must not be mistaken for the contract firing."""
        contract = require_runner_contract()
        outcome = self.fixture_run("hh711_root.pkg.does_not_exist")
        self.assertNotEqual(outcome.returncode, contract.PREREQUISITE_EXIT_CODE)
        self.assertNotIn(contract.PREREQUISITE_DIAGNOSTIC, outcome.combined)

    def test_r14_import_hook_scope_is_fresh_process_only(self):
        """The hook fires per interpreter, and the suite must rely on that.

        Importing a protected module in this process would terminate the test
        run once Phase D lands. The contract therefore has to be observable
        from a spawned interpreter, and this row pins that: a fresh import
        refuses, while this process -- which never imported it -- is unharmed
        and still running to make the assertion.
        """
        outcome = import_in_fresh_process(PROTECTED)
        contract = require_runner_contract()
        self.assertEqual(outcome.returncode, contract.PREREQUISITE_EXIT_CODE)
        self.assertNotIn("IMPORT_COMPLETED", outcome.combined)

        # B4: no assertion here about the *parent* interpreter's sys.modules.
        # A supported package run legitimately imports the protected sibling
        # during Django discovery, so requiring its absence would fail a
        # correctly prepared run for the selection's own imports rather than
        # for any runner defect. Import-graph ownership belongs to the
        # isolated-module control, which checks only what this module does.

    # --- remediation -----------------------------------------------------

    def test_r17_preflight_is_not_an_integrity_exemption(self):
        """Passing preflight must not switch off the real evidence checks.

        Dev B's wording: a successful early preflight is not a permanent
        exemption from freshness, read-only-mount or integrity validation.
        The failure this guards against is a contract that satisfies itself
        by making the protected module's own assertions conditional, so a
        prepared run with deliberately corrupt evidence must still fail.
        """
        sound = load_driver_evidence("declared_ok", (PROTECTED,))
        self.assertEqual(sound["returncode"], 0,
                         "the paired sound-evidence case must pass, or a later "
                         "rejection proves nothing about exemption")
        self.assertGreater(sound["tests_executed"], 0)

        record = load_driver_evidence("preflight_then_invalidated", (PROTECTED,))
        self.assertTrue(record["preflight_ok"],
                        "preflight did not succeed, so this run cannot show that a "
                        "successful preflight fails to exempt later checks")
        self.assertTrue(record["invalidated"],
                        "the evidence was never actually invalidated")
        self.assertFalse(record["timed_out"],
                         "a timeout is not an integrity rejection")
        self.assertNotEqual(record["returncode"], 0,
                            "the consumer accepted evidence invalidated after preflight")
        self.assertTrue(record["integrity_token_seen"],
                        "the consumer must fail with an identifiable integrity error "
                        "from the real checker, not an unrelated crash")

    def test_r10_remediation_names_a_runnable_command(self):
        """The printed command must work when run, not merely read correctly.

        Substring checks pass on a command that cannot execute. The driver
        takes the exact string the refusal emits and runs it verbatim in the
        same isolated lane; this row judges that execution.
        """
        record = load_driver_evidence("remediation_round_trip", (PROTECTED,))
        self.assertTrue(record["emitted"],
                        "the refusal printed no remediation command to run")
        self.assertIn("run_diet_tests.sh", record["emitted"])
        self.assertIn(PROTECTED, record["emitted"],
                      "remediation must name the selection the user asked for")
        self.assertEqual(
            record["executed_returncode"], 0,
            f"the emitted command failed when executed: {record['stderr_tail'][-300:]}")
        self.assertGreater(
            record["executed_tests"], 0,
            "remediation that executes no tests has not remediated anything")

    # --- declaration -----------------------------------------------------

    def test_r11_declaration_matches_discovered_modules(self):
        """Each declared entry must name a module that actually exists.

        An unchecked hand-maintained list is what Phase B rejected; the
        declaration has to be bound to reality.
        """
        contract = require_runner_contract()
        self.assertTrue(contract.EVIDENCE_REQUIREMENTS)
        for module in contract.EVIDENCE_REQUIREMENTS:
            with self.subTest(module=module):
                path = Path(*module.split(".")).with_suffix(".py")
                self.assertTrue((Path(__file__).resolve().parents[3] / path).is_file(),
                                f"{module} is declared but no such module exists")
        self.assertEqual(set(contract.EVIDENCE_REQUIREMENTS), set(PROTECTED_MODULES))

    def test_r12_deleting_a_declaration_fails_closed(self):
        """Remove one real declaration, drive the real wrapper, see it refuse.

        The earlier version asked the contract in-process with an empty
        declaration, which a wrapper ignoring its metadata entirely would
        have survived. The driver now removes one genuine declaration from a
        disposable worktree -- never the shared checkout -- runs the actual
        supported command there with no inherited or residual evidence, and
        requires the protected child to refuse rather than quietly take the
        fast path.

        Restoring the declaration must produce real preparation and nonzero
        execution; without that pair, "omission refuses" is satisfied by a
        wrapper that refuses unconditionally.
        """
        seen = evidence_visible_to_child()
        self.assertEqual(seen, {},
                         f"a bare lane still exposed evidence: {seen}; an omitted "
                         "declaration could be concealed by it")

        declared = "netbox_hedgehog.tests.test_interchange.test_checkout_containment"
        record = load_driver_evidence("declaration_removed", (declared,))
        self.assertTrue(record["declaration_actually_removed"],
                        "no declaration was removed, so this proves nothing")
        self.assertTrue(
            record["mutated_script_still_parses"],
            "the mutated wrapper does not parse, so any refusal below is bash "
            f"failing to read it, not the contract: {record['mutated_script_syntax_error']}")
        self.assertFalse(record["removed_prepared"],
                         "the wrapper prepared a module whose declaration was removed")
        self.assertNotEqual(record["removed_returncode"], 0,
                            "an undeclared protected module ran instead of refusing")
        self.assertEqual(record["removed_tests"], 0,
                         "bodies executed despite the declaration being removed")

        self.assertTrue(record["restored_prepared"],
                        "restoring the declaration did not restore preparation")
        self.assertEqual(record["restored_returncode"], 0,
                         f"the restored case failed: {record['stderr_tail'][-300:]}")
        self.assertGreater(record["restored_tests"], 0,
                           "the restored case executed nothing")

    def test_r18_declared_case_consumes_fresh_evidence(self):
        """The paired positive: correctly declared, and actually prepared.

        Required alongside R12. Without it, "omission refuses" is satisfiable
        by a contract that refuses unconditionally, and the declaration would
        prove nothing. The declared module must pass *and* show it consumed
        freshly prepared evidence rather than a residue.
        """
        record = load_driver_evidence("declared_ok", (PROTECTED,))
        self.assertTrue(record["prepared"],
                        "the wrapper must prepare a correctly declared module")
        self.assertTrue(
            record["prepared_artifact"],
            "a preparation banner is not proof of preparation: no fresh evidence "
            "artifact identity was observed for this run")
        self.assertEqual(record["returncode"], 0,
                         f"the declared case failed: {record['stderr_tail'][-300:]}")
        self.assertGreater(record["tests_executed"], 0,
                           "`Ran 0 tests / OK` is not a consumed-evidence positive")


class RunnerContractRedControls(SimpleTestCase):
    """Controls that pass today and keep the rows honest."""

    def test_red_phase_has_no_runner_contract(self):
        with self.assertRaises(RunnerContractAbsent) as caught:
            require_runner_contract()
        self.assertIn(CONTRACT_MODULE, str(caught.exception))

    def test_every_row_is_declared_and_exists(self):
        methods = {name for name in dir(RunnerContractRedTests) if name.startswith("test_")}
        declared = {row.method for row in CONTRACT_ROWS}
        self.assertEqual(declared, methods)
        self.assertEqual(len({row.identifier for row in CONTRACT_ROWS}), len(CONTRACT_ROWS))

    def test_amendment_map_names_tests_that_exist(self):
        """Every accepted amendment maps to a real test or a named open gate.

        The failure this prevents is a mapping that drifts: a method renamed
        or deleted while the map still claims the obligation is met. Open
        gates are allowed through deliberately -- an acknowledged debt is
        honest, a stale claim of coverage is not.
        """
        known = {name for name in dir(RunnerContractRedTests) if name.startswith("test_")}
        known |= {name for name in dir(RunnerContractRedControls) if name.startswith("test_")}
        open_gates = []
        for amendment, entries in sorted(AMENDMENT_MAP.items()):
            for entry in entries:
                with self.subTest(amendment=amendment, entry=entry[:40]):
                    if entry.startswith("OPEN:"):
                        open_gates.append(amendment)
                        self.assertGreater(len(entry), len("OPEN: "),
                                           "an open gate must state why")
                    else:
                        self.assertIn(entry, known,
                                      f"{amendment} maps to {entry}, which does not exist")
        # Every amendment now maps to a real test. The control's value is no
        # longer "an open gate exists" but that nothing claims coverage by
        # naming a method that does not.
        self.assertEqual(open_gates, [],
                         f"amendments still unmapped: {sorted(set(open_gates))}")

    #: Declared independently of BLOCKED_BY_715 so the registry is checked
    #: against something, not against itself. Removing an entry from the
    #: registry, or adding a `blocked_by` marker to an unrelated evidence
    #: record, must both be visible rather than silently accepted.
    EXPECTED_BLOCKED_ROWS = frozenset({
        "test_r10_remediation_names_a_runnable_command",
        "test_r12_deleting_a_declaration_fails_closed",
        "test_r16_wrapper_broad_selection_prepares",
        "test_r17_preflight_is_not_an_integrity_exemption",
        "test_r18_declared_case_consumes_fresh_evidence",
        "test_r20_lifecycle_observer_detects_real_preparation",
    })

    def test_loader_rejects_an_unauthorized_block_marker(self):
        """An injected `blocked_by` must not excuse an arbitrary scenario.

        The registry set protects the Python side only. The loader reads
        evidence, and previously honoured a `blocked_by` key on any record,
        so marking an unrelated scenario blocked would have silently excused
        whichever row consumed it.
        """
        from netbox_hedgehog.tests.test_interchange.runner_contract_support import (
            AUTHORIZED_BLOCKED_SCENARIOS,
            DRIVER_EVIDENCE_VARIABLE as _EVIDENCE_VAR,
            DriverEvidenceUnusable,
            load_driver_evidence)

        self.assertIn("declared_ok", AUTHORIZED_BLOCKED_SCENARIOS)
        self.assertNotIn("topology_fast_path", AUTHORIZED_BLOCKED_SCENARIOS,
                         "a decision scenario must never be an authorized block")

        with tempfile.TemporaryDirectory(prefix="hh711-block-") as workspace:
            forged = Path(workspace) / "evidence.json"
            forged.write_text(json.dumps({
                "version": 1, "head": os.environ.get("HH711_EXPECTED_HEAD", ""),
                "lane": "diet711drv", "run_id": "forged",
                "observed_at": int(time.time()),
                "scenarios": {"topology_fast_path": {
                    "name": "topology_fast_path", "selection": ["x"],
                    "blocked_by": 715, "reason": "injected"}},
            }), encoding="utf-8")
            previous = os.environ.get(_EVIDENCE_VAR)
            os.environ[_EVIDENCE_VAR] = str(forged)
            try:
                with self.assertRaises(DriverEvidenceUnusable) as caught:
                    load_driver_evidence("topology_fast_path", ("x",))
                self.assertIn("not an authorized", str(caught.exception))
            finally:
                if previous is None:
                    os.environ.pop(_EVIDENCE_VAR, None)
                else:
                    os.environ[_EVIDENCE_VAR] = previous

    def test_blocked_registry_agrees_with_the_expected_set(self):
        """The registry must match an independently declared expectation.

        The previous control validated only the entries that happened to be
        present, so deleting one was invisible and adding a `blocked_by`
        marker elsewhere was accepted as a new block. Unknown, missing and
        mismatched are now distinct failures.
        """
        declared = set(BLOCKED_BY_715)
        expected = set(self.EXPECTED_BLOCKED_ROWS)
        self.assertEqual(
            declared - expected, set(),
            "rows claim a #715 block that the expected set does not list")
        self.assertEqual(
            expected - declared, set(),
            "rows are expected to be blocked by #715 but are not registered; "
            "a removed entry must fail, not silently become unblocked")

    def test_blocked_rows_are_annotated_not_suppressed(self):
        """Blocked rows stay failing and say why; nothing is suppressed.

        The control exists so "blocked by #715" cannot drift into a silent
        exemption. Each named row must still exist, must still be a declared
        contract row, and must carry no skip/xfail decoration -- the issue
        and the standing constraints forbid conditional suppression, so a
        blocked row fails loudly with a recorded reason instead.
        """
        declared = {row.method for row in CONTRACT_ROWS}
        for method, reason in sorted(BLOCKED_BY_715.items()):
            with self.subTest(row=method):
                self.assertIn(method, declared,
                              f"{method} is marked blocked but is not a contract row")
                self.assertTrue(hasattr(RunnerContractRedTests, method))
                function = getattr(RunnerContractRedTests, method)
                self.assertFalse(getattr(function, "__unittest_skip__", False),
                                 f"{method} is skipped; blocked rows must fail, not skip")
                self.assertFalse(getattr(function, "__unittest_expecting_failure__", False),
                                 f"{method} is xfailed; blocked rows must fail, not xfail")
                self.assertGreater(len(reason), 40, "a blocked row needs a real reason")

    def test_every_area_is_covered(self):
        self.assertEqual({row.area for row in CONTRACT_ROWS}, set(AREAS))

    def test_declared_entry_points_cover_every_contract_reference(self):
        import re
        source = Path(__file__).read_text(encoding="utf-8")
        used = set(re.findall(r"contract\.([A-Za-z_]\w*)", source))
        self.assertEqual(used - set(REQUIRED_ENTRY_POINTS), set())
        self.assertEqual(set(REQUIRED_ENTRY_POINTS) - used, set())

    def test_this_suite_never_imports_a_protected_module(self):
        """The suite's own safety property, asserted rather than assumed.

        If this module imported a protected one, Phase D's hook would kill the
        test process rather than report a failure.
        """
        import ast

        # Deliberately NOT asserted: that no protected module is in
        # sys.modules. That is a property of the *selection*, not of this
        # module -- selecting the whole test_interchange package makes Django
        # discovery import every sibling, protected ones included, before any
        # test runs. Measured: the package run reports
        # loaded='…test_reaper_adapter_red' with this module innocent.
        # Asserting it here would fail for something this suite does not
        # control, and would hide the property that it does.
        #
        # What this suite controls is its own import graph, checked two ways:
        # statically below, and dynamically in a fresh process that imports
        # only this module.
        outcome = import_in_fresh_process(
            "netbox_hedgehog.tests.test_interchange.test_runner_contract_red")
        self.assertIn("IMPORT_COMPLETED", outcome.combined)
        for module in PROTECTED_MODULES:
            with self.subTest(pulled_in=module):
                self.assertNotIn(f"LOADED:{module}", outcome.combined)

        # Parsed, not grepped. A substring search for an import statement
        # matches the search string itself where it appears as a literal in
        # this very assertion, so it can never fail -- the same tautology
        # shape found in #708's containment decoy. The AST sees statements.
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
                imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        for module in PROTECTED_MODULES:
            with self.subTest(statement=module):
                self.assertNotIn(module, imported)

    def test_timeout_reaps_the_whole_descendant_tree(self):
        """Harness control for B2: a bound that cannot reap is not a bound.

        The measured failure was a parent killing only its immediate child
        and orphaning three levels beneath it. This drives a child that
        deliberately spawns a tree, lets the bound expire, and requires both
        the reported survivor count and the live process table to agree that
        nothing is left.
        """
        import subprocess as sp
        import time
        from netbox_hedgehog.tests.test_interchange.runner_contract_support import (
            _process_state, _reap_group, _running_in_group)

        child = sp.Popen(["bash", "-c", "sleep 120 & sleep 120 & sleep 120"],
                         stdout=sp.PIPE, stderr=sp.PIPE, start_new_session=True)
        time.sleep(1)
        group = os.getpgid(child.pid)
        before = _running_in_group(group)
        self.assertGreater(before, 1, "the control must actually build a tree to reap")

        survivors = _reap_group(child)
        time.sleep(0.5)
        self.assertEqual(survivors, 0, "the reaper reported running survivors")
        self.assertEqual(_running_in_group(group), 0,
                         "a descendant outlived the reap")

        # The count must mean "still executing", not "no /proc entry". Inside
        # this container PID 1 does not reap orphans, so the killed tree
        # remains visible as zombies; if the counter regressed to counting
        # entries, it would report survivors for a tree it had just killed.
        entries = [d for d in Path("/proc").glob("[0-9]*")
                   if (_process_state(d) or (None, None))[0] == group]
        self.assertTrue(
            all((_process_state(d) or (None, "Z"))[1] == "Z" for d in entries),
            "every remaining entry for the reaped group must be a zombie")

    def test_observers_reject_single_fault_outcomes(self):
        """B3: typed adversaries, committed so they cannot silently rot.

        Each row below is one deficiency Dev B supplied that the previous
        assertions accepted. They target the discriminators directly rather
        than whole rows, because a row first requires the absent contract and
        would pass for that reason instead of for the fault under test.
        """
        from netbox_hedgehog.tests.test_interchange.runner_contract_support import RunOutcome

        def outcome(**kwargs):
            base = dict(argv=("x",), returncode=0, stdout="", stderr="")
            base.update(kwargs)
            return RunOutcome(**base)

        with self.subTest("zero-test success is not execution"):
            vacuous = outcome(stdout="Ran 0 tests in 0.001s\n\nOK\n")
            self.assertEqual(vacuous.tests_executed, 0,
                             "`Ran 0 tests` must not satisfy a positive row")

        with self.subTest("a real run reports a nonzero count"):
            self.assertEqual(outcome(stdout="Ran 7 tests in 1s\n\nOK\n").tests_executed, 7)

        with self.subTest("a body that ran is visible without any summary"):
            # SystemExit can suppress the summary entirely; the marker cannot.
            self.assertTrue(outcome(stdout=f"{ORDINARY_MARKER}\n").body_ran(ORDINARY_MARKER))
            self.assertEqual(outcome(stdout=f"{ORDINARY_MARKER}\n").tests_executed, 0)

        with self.subTest("a summary with no body is not a body"):
            self.assertFalse(outcome(stdout="Ran 3 tests\nOK\n").body_ran(ORDINARY_MARKER))

        with self.subTest("a timeout is not a refusal and not a failure signal"):
            expired = outcome(returncode=-1, timed_out=True, survivors=2)
            self.assertTrue(expired.timed_out)
            self.assertNotEqual(expired.survivors, 0,
                                "survivors must be observable, not assumed zero")

    def test_subprocess_observer_detects_a_known_outcome(self):
        """The harness must be able to see a result it is given.

        A spawn helper that silently returned empty output would make every
        refusal row pass for the wrong reason.
        """
        outcome = raw_django(UNRELATED_MODULE)
        self.assertGreater(outcome.tests_executed, 0)
        self.assertEqual(outcome.returncode, 0)
        missing = raw_django("netbox_hedgehog.tests.does_not_exist_hh711")
        self.assertNotEqual(missing.returncode, 0)
