"""#719 G1 RED expectations against the pinned existing safety controls.

No future splitter/evidence validator is implemented here. Failures measure the
reviewed shared setup and metadata-blind loader. Passing harness models in the
companion modules do NOT make this subject green. Main has no #716 integration;
this source-fixture RED scope does not claim #717/CI-equivalent live execution.
"""

from django.test import SimpleTestCase

from . import safety_g1_support as S


class SafetySubjectRed(SimpleTestCase):
    def test_r01_reviewed_subject_has_exact_independent_four_seven_partition(self):
        _, report = S.invoke_probe()
        S.validate_inventory(S.declaration(), report["discovered"])

    def test_r02_missing_evidence_does_not_suppress_source_bodies(self):
        context, report = S.invoke_probe(evidence="missing")
        # Establish the error is the evidence gate, not a broken subprocess.
        S.reconcile(context, report, partitioned=False, missing=True)
        self.assertEqual({r["id"].rsplit(".", 1)[-1] for r in report["entries"]},
                         {method for _, method, kind in S.ROWS if kind == "source"})

    def assert_unusable_refused(self, kind):
        context, report = S.invoke_probe(evidence=kind)
        # It ran the ORIGINAL eleven assertions, not a fake loader's answer.
        # Today they all pass despite the bad metadata, the intended RED cause.
        if report["successful"]:
            S.reconcile(context, report, partitioned=False)
        self.assertFalse(report["successful"], f"{kind} fixture evidence was accepted")
        self.assertEqual({r["id"].rsplit(".", 1)[-1] for r in report["entries"]},
                         {method for _, method, obligation in S.ROWS if obligation == "source"})
        self.assertEqual(len(report["setup_errors"]), 1)
        self.assertEqual(report["setup_errors"][0]["type"], "EvidenceUnusable")
        self.assertEqual(report["setup_errors"][0]["reason"], kind)

    def test_r03_stale_fixture_is_refused(self):
        self.assert_unusable_refused("stale")

    def test_r04_future_fixture_is_refused(self):
        self.assert_unusable_refused("future")

    def test_r05_wrong_run_fixture_is_refused(self):
        self.assert_unusable_refused("wrong-run")

    def test_r06_wrong_head_fixture_is_refused(self):
        self.assert_unusable_refused("wrong-head")

    def test_r07_partial_fixture_is_refused(self):
        self.assert_unusable_refused("partial")
