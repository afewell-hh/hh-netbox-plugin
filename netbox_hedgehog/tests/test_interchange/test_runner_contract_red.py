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

import os
import tempfile
import unittest
from pathlib import Path

from django.test import SimpleTestCase

from netbox_hedgehog.tests.test_interchange.runner_contract_support import (
    CONTRACT_MODULE,
    ORDINARY_MARKER,
    PROTECTED_MARKER,
    build_fixture_tree,
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
)

AREAS = ("selector", "compatibility", "boundary", "remediation", "declaration")


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

    def assert_refused(self, outcome, label, marker_bearing=True):
        """A refusal, observed by markers rather than by a missing summary.

        B3: `Ran 0 tests` is a summary and an executed body can leave none, so
        absence of a summary proves nothing in either direction. Fixture
        bodies announce themselves, and a genuine pre-execution refusal means
        neither marker appears.
        """
        contract = require_runner_contract()
        self.assertFalse(
            outcome.timed_out,
            f"{label}: no refusal within the bound; the selection ran instead")
        self.assertEqual(
            outcome.survivors, 0,
            f"{label}: {outcome.survivors} descendant(s) survived the bound")
        self.assertEqual(
            outcome.returncode, contract.PREREQUISITE_EXIT_CODE,
            f"{label}: expected the prerequisite exit code, got {outcome.returncode}")
        self.assertIn(contract.PREREQUISITE_DIAGNOSTIC, outcome.combined,
                      f"{label}: refusal must carry the stable diagnostic token")
        if marker_bearing:
            self.assertFalse(outcome.body_ran(ORDINARY_MARKER),
                             f"{label}: an ordinary body ran before the refusal")
            self.assertFalse(outcome.body_ran(PROTECTED_MARKER),
                             f"{label}: the protected body ran")
        self.assertEqual(outcome.tests_executed, 0,
                         f"{label}: {outcome.tests_executed} test(s) executed before refusal")

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
        self.assert_refused(self.fixture_run(self.tree.protected), "module")

    def test_r02_class_selection_is_refused(self):
        self.assert_refused(self.fixture_run(self.tree.protected_class), "class")

    def test_r03_method_selection_is_refused(self):
        self.assert_refused(self.fixture_run(self.tree.protected_method), "method")

    def test_r04_parent_package_selection_is_refused(self):
        self.assert_refused(self.fixture_run(self.tree.parent), "parent")

    def test_r05_options_only_invocation_is_refused(self):
        """No labels means Django's broad discovery, which reaches protected modules.

        Rejected early with the supported command rather than guessed at.
        """
        # Bounded deliberately: with the contract absent this invocation
        # discovers and runs the entire tree. A timeout is reported as
        # "did not refuse" rather than hanging the suite.
        self.assert_refused(
            self.fixture_run(cwd=self.tree.root, timeout=90), "options-only")

    def test_r13_selection_matching_is_dot_component_aware(self):
        """`test_interchange_audit_retention` is not inside `test_interchange`.

        Today's wrapper matches it by string prefix and prepares needlessly;
        the contract must compare dot components.
        """
        contract = require_runner_contract()
        self.assertFalse(contract.selection_requires_evidence(
            ("netbox_hedgehog.tests.test_interchange_audit_retention",)))
        self.assertTrue(contract.selection_requires_evidence((PROTECTED,)))
        self.assertTrue(contract.selection_requires_evidence(
            ("netbox_hedgehog.tests",)))
        self.assertTrue(contract.selection_requires_evidence(
            (f"{PROTECTED}.ReaperAdapterRedContract.test_a01_distinct_execution_identities",)))

    def test_r15_grandparent_selection_is_refused(self):
        """Two levels up still reaches protected modules.

        Listed separately from the parent row in Dev B's acceptance, and not
        inferable from it: a mechanism could match the immediate package and
        miss `netbox_hedgehog.tests`.
        """
        self.assert_refused(self.fixture_run(self.tree.grandparent), "grandparent")

    # --- compatibility: the contract must not become a blanket refusal ----

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
        contract = require_runner_contract()
        for selection in (GRANDPARENT_SELECTION, "netbox_hedgehog.tests.test_interchange"):
            with self.subTest(selection=selection):
                prepared = contract.wrapper_prepares_selection((selection,))
                self.assertTrue(prepared.prepared,
                                f"the wrapper must prepare {selection}, not refuse it")
                self.assertFalse(getattr(prepared, "refused", False))

    # --- the boundary ----------------------------------------------------

    def test_r08_refusal_precedes_every_test_body(self):
        """An ordinary body listed first must never run.

        This is the row that distinguishes a real pre-execution boundary from
        a per-module error: unittest turns a load-time raise into a placeholder
        and keeps going, so earlier bodies still execute.
        """
        outcome = self.fixture_run(self.tree.ordinary, self.tree.protected)
        self.assert_refused(outcome, "mixed selection")

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
        contract = require_runner_contract()
        prepared = contract.wrapper_prepares_selection((PROTECTED,))
        corrupted = dict(prepared.evidence)
        corrupted["HNP_TEST_CHECKOUT_ROOT"] = "/nonexistent-hh711-integrity-probe"
        outcome = raw_django(PROTECTED, env=corrupted)
        self.assertNotEqual(outcome.returncode, 0,
                            "corrupt evidence passed preflight and was never revalidated")
        self.assertNotIn(contract.PREREQUISITE_DIAGNOSTIC, outcome.combined,
                         "this must fail integrity validation, not the preflight gate")

    def test_r10_remediation_names_a_runnable_command(self):
        """The printed command must be the supported one, and host-side.

        A message printed from inside the container has to say so, or a
        contributor pastes it where it cannot work.
        """
        contract = require_runner_contract()
        outcome = raw_django(PROTECTED)
        remediation = contract.remediation_command((PROTECTED,))
        self.assertIn("run_diet_tests.sh", remediation)
        self.assertIn(PROTECTED, remediation)
        self.assertIn(remediation, outcome.combined,
                      "the refusal must print the command the contract recommends")

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
        """An omitted declaration must stay visible in a bare lane.

        Dev B's acceptance is specific: the omission has to be demonstrated
        with neither inherited CI evidence variables nor usable residual
        evidence, because either can conceal missing preparation and turn a
        silent fast-path pass into something that looks correct.

        So this row does three things rather than one. It observes, from the
        child's own side, that no evidence variable survived into the fresh
        process -- scrubbing in the parent is not evidence that the child saw
        nothing. It then requires the protected module to refuse anyway, which
        is the independent refusal that makes an omission loud while
        preserving #699. Only then does it check that the declaration API
        itself rejects an empty declaration instead of reading it as
        "needs none".
        """
        seen = evidence_visible_to_child()
        self.assertEqual(seen, {},
                         f"a bare lane still exposed evidence: {seen}; an omitted "
                         "declaration could be concealed by it")

        contract = require_runner_contract()
        outcome = raw_django(PROTECTED)
        self.assert_refused(outcome, "undeclared module in a bare lane")

        with self.assertRaises(contract.ContractDeclarationInvalid):
            contract.selection_requires_evidence((PROTECTED,), declared=())

    def test_r18_declared_case_consumes_fresh_evidence(self):
        """The paired positive: correctly declared, and actually prepared.

        Required alongside R12. Without it, "omission refuses" is satisfiable
        by a contract that refuses unconditionally, and the declaration would
        prove nothing. The declared module must pass *and* show it consumed
        freshly prepared evidence rather than a residue.
        """
        contract = require_runner_contract()
        self.assertIn(PROTECTED, contract.EVIDENCE_REQUIREMENTS)
        prepared = contract.wrapper_prepares_selection((PROTECTED,))
        self.assertTrue(prepared.prepared,
                        "the supported wrapper must prepare a declared module")
        self.assertTrue(set(prepared.evidence) & set(EVIDENCE_VARIABLES),
                        "preparation must supply the evidence the module consumes")
        outcome = raw_django(PROTECTED, env=prepared.evidence)
        self.assertEqual(outcome.returncode, 0, outcome.combined[-400:])
        self.assertGreater(outcome.tests_executed, 0,
                           "a prepared run must execute real bodies, not refuse; "
                           "`Ran 0 tests / OK` is not preparation working")


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
