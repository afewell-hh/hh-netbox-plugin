"""Measured fixture execution and adversarial observer controls for #719.

The parent process supervises a child in the SAME isolated test lane. Child
profile hooks and unittest share interpreter/import/dispatch failure modes.
The parent cannot attest to execution independently from those events. These
tests establish mutation sensitivity, never kernel/daemon facts.
"""

import copy

from django.test import SimpleTestCase

from . import safety_g1_support as S


class SafetyExecutionControls(SimpleTestCase):
    def test_missing_fixture_executes_four_bodies_but_is_not_success(self):
        context, report = S.invoke_probe(partition_model=True, evidence="missing")
        S.reconcile(context, report, partitioned=True, missing=True)
        self.assertEqual(report["ran"], 4)
        self.assertEqual(len(report["entries"]), 4)
        self.assertFalse(report["successful"])

    def test_fresh_synthetic_fixture_executes_all_eleven_original_bodies(self):
        context, report = S.invoke_probe()
        # The unsplit subject can run all eleven with synthetic data. This
        # positive is NOT evidence it validates freshness or daemon provenance.
        S.reconcile(context, report, partitioned=False)
        self.assertEqual(report["ran"], 11)
        self.assertEqual(len(report["entries"]), 11)

    def test_runner_bypass_fabricates_success_but_not_body_entry(self):
        context, report = S.invoke_probe(partition_model=True, mutation="bypass-bodies")
        self.assertEqual(len(report["receipts"]), 11)
        self.assertTrue(report["successful"])
        self.assertEqual(report["entries"], [])
        with self.assertRaisesRegex(AssertionError, "receipt without body"):
            S.reconcile(context, report, partitioned=True)

    def test_noop_under_original_id_has_wrong_callable_identity(self):
        context, report = S.invoke_probe(partition_model=True, mutation="noop-original-id")
        self.assertTrue(report["successful"])
        self.assertEqual(len(report["entries"]), 11)
        with self.assertRaisesRegex(AssertionError, "unreviewed callable"):
            S.reconcile(context, report, partitioned=True)

    def test_success_receipt_cannot_override_real_runner_failure(self):
        context, report = S.invoke_probe(partition_model=True, mutation="runner-failure")
        self.assertFalse(report["successful"])
        self.assertTrue(any(r["outcome"] == "failure" for r in report["outcomes"]))
        self.assertTrue(all(r["outcome"] == "success" for r in report["receipts"]))
        with self.assertRaisesRegex(AssertionError, "disagrees with runner"):
            S.reconcile(context, report, partitioned=True)

    def test_disabled_and_corrupt_observer_fail_closed(self):
        context, report = S.invoke_probe(partition_model=True, mutation="disable-observer")
        self.assertTrue(report["successful"])
        self.assertEqual(report["entries"], [])
        with self.assertRaisesRegex(AssertionError, "disabled or replaced"):
            S.reconcile(context, report, partitioned=True)
        with self.assertRaisesRegex(AssertionError, "missing/corrupt"):
            S.invoke_probe(partition_model=True, mutation="corrupt-stream")
        with self.assertRaisesRegex(AssertionError, "observer child failed"):
            S.invoke_probe(partition_model=True, mutation="crash-observer")

    def test_restoring_observer_after_execution_does_not_restore_missing_events(self):
        context, report = S.invoke_probe(partition_model=True, mutation="restore-after-bypass")
        self.assertTrue(report["observer_intact"])
        self.assertTrue(report["successful"])
        self.assertEqual(report["entries"], [])
        with self.assertRaisesRegex(AssertionError, "receipt without body"):
            S.reconcile(context, report, partitioned=True)

    def test_unknown_duplicate_missing_receipts_and_replay_are_rejected(self):
        context, original = S.invoke_probe(partition_model=True)
        mutations = {}
        item = copy.deepcopy(original)
        item["receipts"].append({"id": "never.discovered.test_ghost", "outcome": "success"})
        mutations["undiscovered receipt"] = item
        item = copy.deepcopy(original)
        item["receipts"].append(dict(item["receipts"][0]))
        mutations["duplicate receipt"] = item
        item = copy.deepcopy(original)
        item["receipts"].pop()
        mutations["missing receipt"] = item
        item = copy.deepcopy(original)
        item["entries"].pop()
        mutations["missing body entry"] = item
        item = copy.deepcopy(original)
        item["complete"] = False
        mutations["partial stream"] = item
        for name, report in mutations.items():
            with self.subTest(mutation=name):
                with self.assertRaises(AssertionError):
                    S.reconcile(context, report, partitioned=True)
        for field in ("run_id", "head"):
            with self.subTest(replay=field):
                expected = dict(context, **{field: "different"})
                with self.assertRaisesRegex(AssertionError, "unbound"):
                    S.reconcile(expected, original, partitioned=True)

    def test_skip_or_expected_failure_is_never_execution_success(self):
        context, original = S.invoke_probe(partition_model=True)
        for outcome in ("skip", "expectedFailure", "unexpectedSuccess", "error"):
            report = copy.deepcopy(original)
            report["outcomes"][0]["outcome"] = outcome
            report["receipts"][0]["outcome"] = outcome
            with self.subTest(outcome=outcome):
                with self.assertRaisesRegex(AssertionError, "did not report success"):
                    S.reconcile(context, report, partitioned=True)

    def test_shared_interpreter_limitation_cannot_be_relabeled_independent(self):
        context, report = S.invoke_probe(partition_model=True)
        self.assertEqual(report["observer"], "in-process-profile/1;shared-interpreter")
        report["observer"] = "independent-execution-attestation"
        with self.assertRaisesRegex(AssertionError, "misrepresented"):
            S.reconcile(context, report, partitioned=True)
