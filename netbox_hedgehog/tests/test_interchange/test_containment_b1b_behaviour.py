"""#716 B1b behavioural controls: mutation-sensitive, driving the real code.

Every earlier B1b control was a source-position check, a copied predicate,
or an independent snippet, and all eighteen passed when nonce validation
was removed, start-identity comparison disabled, and fixture registration
commented out. These drive the real `main()` through a mocked harness, so a
mutation to the implementation changes the result here.

No Docker, no containers, no signals.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from netbox_hedgehog.tests.test_interchange import containment_b1b_harness as H


class B1bBehaviourControls(SimpleTestCase):

    @staticmethod
    def _baseline_signals(recorded):
        """Signals against the BASELINE child only.

        Preflight's readiness subject signals first, so an unfiltered
        `recorded["signalled"]` is never empty and a 'no signal was sent'
        assertion would be unsatisfiable.
        """
        return [entry for entries in recorded["signalled"] for entry in entries
                if entry.get("pid") == H.CHILD_PID]

    def _run(self, **options):
        """Fresh module instance per control, so patches never leak."""
        b1b = H.load_b1b()
        recorded = H.install(b1b, **options)
        with tempfile.TemporaryDirectory(prefix="hh716-beh-") as workspace:
            output = Path(workspace) / "evidence.json"
            code = H.run_main(b1b, output)
            evidence = json.loads(output.read_text(encoding="utf-8"))
        return b1b, code, evidence, recorded

    # --- the sound positive ----------------------------------------------

    def test_sound_run_completes(self):
        """Without a positive, every negative below could pass vacuously."""
        _, code, evidence, recorded = self._run()
        self.assertEqual(code, 0, evidence.get("dirty_reasons"))
        self.assertTrue(evidence["baseline_complete"])
        self.assertFalse(evidence["lane_dirty"], evidence["dirty_reasons"])
        self.assertTrue(evidence["published_nonce_validated"])
        self.assertTrue(self._baseline_signals(recorded),
                        "the baseline child was never signalled")

    # --- nonce validation is load-bearing --------------------------------

    def test_a_wrong_published_child_nonce_is_refused(self):
        """Removing nonce validation must make this fail.

        Dev B's probe reached the kill with a wrong published nonce and
        reported baseline_complete. The control now drives the real main().
        """
        _, code, evidence, recorded = self._run(
            published_child_nonce="not-the-registered-nonce")
        self.assertNotEqual(code, 0, "a wrong published nonce was accepted")
        self.assertTrue(evidence["lane_dirty"])
        self.assertFalse(evidence.get("baseline_complete", False))
        self.assertTrue(
            any("published nonce" in reason
                for reason in evidence["dirty_reasons"]),
            evidence["dirty_reasons"])
        self.assertEqual(
            self._baseline_signals(recorded), [],
            "a signal was sent against the baseline child despite an "
            "unvalidated nonce")

    def test_a_wrong_published_parent_nonce_is_refused(self):
        _, code, evidence, _ = self._run(
            published_parent_nonce="parent-nonce-mismatch")
        self.assertNotEqual(code, 0)
        self.assertTrue(any("nonce" in reason
                            for reason in evidence["dirty_reasons"]),
                        evidence["dirty_reasons"])

    # --- start-identity comparison is load-bearing -----------------------

    def test_a_different_instance_at_the_same_pid_is_unresolved(self):
        """Disabling the start-ticks comparison must make this fail."""
        _, code, evidence, recorded = self._run(
            observed_start_ticks="a-different-instance")
        self.assertNotEqual(code, 0,
                            "a recycled pid was accepted as the same process")
        self.assertTrue(evidence["lane_dirty"])
        self.assertTrue(
            any("different instance" in reason or "unknown" in reason.lower()
                for reason in evidence["dirty_reasons"]),
            evidence["dirty_reasons"])
        self.assertEqual(
            self._baseline_signals(recorded), [],
            "a signal was sent against an unbound instance")

    def test_a_survivor_after_rescue_is_unresolved(self):
        _, code, evidence, _ = self._run(after_rescue_found=True)
        self.assertNotEqual(code, 0, "an owned survivor was accepted")
        self.assertTrue(any("survived" in reason or "unknown" in reason.lower()
                            for reason in evidence["dirty_reasons"]),
                        evidence["dirty_reasons"])

    # --- fixture registration is load-bearing ----------------------------

    def test_the_decoy_is_disposed_through_the_fixture_registry(self):
        """Commenting out the registration must make this fail.

        Asserted from what the real code DID -- the ids it removed -- not
        from source text, which a comment would still satisfy.
        """
        _, code, evidence, recorded = self._run()
        self.assertEqual(code, 0, evidence.get("dirty_reasons"))
        self.assertIn(H.DECOY_ID, evidence.get("fixture_registry", []),
                      "the decoy never entered the fixture registry")
        self.assertIn(H.DECOY_ID, recorded["removed"],
                      "the decoy was never disposed")
        disposed = {entry["id"] for entry in evidence["fixture_cleanup"]}
        self.assertIn(H.DECOY_ID, disposed,
                      "fixture cleanup did not report the decoy")

    def test_every_rescue_call_targets_the_scenario_container(self):
        """Container-aware: redirecting the rescue to the decoy must fail.

        The previous control compared a pid against a container id, which
        could never match, so redirecting the rescue to the decoy container
        was invisible to it.
        """
        _, code, evidence, recorded = self._run()
        self.assertEqual(code, 0, evidence.get("dirty_reasons"))
        self.assertTrue(recorded["rescue_calls"], "the rescue never ran")
        preflight = evidence["preflight"]
        scenario = preflight["container_id"]
        decoy = preflight["decoy_container_id"]
        self.assertNotEqual(scenario, decoy, "fixture collapsed the two ids")
        # Both the pre-termination verification and the signalling call must
        # be aimed at the scenario container.
        self.assertGreaterEqual(
            len(recorded["rescue_calls"]), 2,
            "expected a verification call and a signalling call")
        self.assertTrue(any(c["send_signal"] for c in recorded["rescue_calls"]),
                        "no rescue call ever sent a signal")
        for index, call in enumerate(recorded["rescue_calls"]):
            with self.subTest(call=index, send_signal=call["send_signal"]):
                self.assertEqual(
                    call["container_id"], scenario,
                    f"rescue call {index} targeted "
                    f"{call['container_id'][:12]}, not the scenario "
                    f"container {scenario[:12]}")
                self.assertNotEqual(
                    call["container_id"], decoy,
                    f"rescue call {index} was pointed at the unregistered "
                    f"decoy {decoy[:12]}")

    def test_the_decoy_is_registered_before_it_is_started(self):
        """Registering after start must fail.

        Asserting only that the id ends up registered is satisfied by
        registering after start. This reads the registry's real contents at
        the start boundary.
        """
        _, code, evidence, _ = self._run()
        self.assertEqual(code, 0, evidence.get("dirty_reasons"))
        snapshot = evidence.get("fixture_registry_at_decoy_start")
        self.assertIsNotNone(
            snapshot, "no registry snapshot was taken at the start boundary")
        self.assertIn(
            H.DECOY_ID, snapshot,
            "the decoy was not in the fixture registry when it was started; "
            "a container that starts before it is registered is unowned")

    # --- the hex check must be the implementation's, not a copy ----------

    def test_a_non_hex_container_id_fails_preflight(self):
        """Driven through the real preflight, not a re-declared predicate.

        The previous control defined its own `is_hex_id` and tested that,
        which said nothing about the implementation.
        """
        _, code, evidence, _ = self._run(scenario_id="z" * 64)
        self.assertNotEqual(code, 0, "a non-hex container id passed preflight")
        shortfall = evidence["preflight_shortfall"]
        self.assertIn("immutable_id_is_64_hex",
                      shortfall["any_false"] + shortfall["not_literally_true"],
                      shortfall)

    # ------------------------------------------------------------------
    # Conclusion-bearing evidence.
    #
    # A static audit of this module against containment_b1b showed that 17
    # of 28 top-level evidence keys were recorded but read by no control,
    # including every key the baseline exists to report. The module's own
    # guards covered them, so a mutation removing a guard AND recording the
    # wrong conclusion passed all 36 controls. These read those keys.
    # ------------------------------------------------------------------

    def test_a_child_that_did_not_survive_cannot_report_success(self):
        """The baseline's entire claim is that the child outlived the client.

        If it did not, this run demonstrates nothing and must not report a
        completed baseline -- the distinction between observing survival and
        attributing it to the termination.
        """
        _, code, evidence, _ = self._run(child_found_after_kill=False)
        self.assertNotEqual(code, 0, "a non-surviving child reported success")
        self.assertTrue(evidence["lane_dirty"])
        self.assertNotIn("baseline_complete", evidence)
        observed = evidence["inner_subject_after_host_kill"]
        self.assertEqual(observed["alive"], "false")
        self.assertTrue(any("did not survive" in r
                            for r in evidence["dirty_reasons"]),
                        evidence["dirty_reasons"])

    def test_an_unknown_probe_after_the_kill_is_not_a_clean_result(self):
        """UNKNOWN must stay UNKNOWN, never collapse to survived-or-not."""
        b1b, code, evidence, _ = self._run(probe_unknown_after_kill=True)
        self.assertNotEqual(code, 0, "an UNKNOWN probe reported success")
        self.assertTrue(evidence["lane_dirty"])
        self.assertNotIn("baseline_complete", evidence)
        self.assertEqual(
            evidence["inner_subject_after_host_kill"]["alive"],
            b1b.UNKNOWN,
            "a probe that could not run was recorded as a definite state")

    def test_a_destroyed_same_label_decoy_fails_the_baseline(self):
        """Disposal goes by registered id; a same-label bystander survives.

        If the decoy is gone, disposal reached an unregistered resource and
        the run must not report success.
        """
        _, code, evidence, _ = self._run(decoy_state_after_rescue="absent")
        self.assertNotEqual(code, 0,
                            "destroying an unregistered resource passed")
        self.assertTrue(evidence["lane_dirty"])
        self.assertNotIn("baseline_complete", evidence)
        self.assertEqual(
            evidence["same_label_decoy_after_rescue"]["state"], "absent")

    def test_a_rescue_outcome_that_is_not_a_cleanup_fails(self):
        """Only `reaped` or `terminated_zombie` are cleanups."""
        _, code, evidence, _ = self._run(rescue_outcome="skipped")
        self.assertNotEqual(code, 0, "a non-cleanup outcome passed")
        self.assertTrue(evidence["lane_dirty"])
        self.assertNotIn("baseline_complete", evidence)
        # It must reach the baseline rescue and fail THERE. Injected into
        # preflight readiness as well, this run aborted before the rescue
        # and the assertions above passed for the wrong reason.
        self.assertTrue(evidence["preflight_passed"],
                        "the run never reached the baseline rescue")
        self.assertEqual(evidence["rescue"]["reports"][0]["outcome"],
                         "skipped")
        self.assertTrue(any("not a cleanup" in r
                            for r in evidence["dirty_reasons"]),
                        evidence["dirty_reasons"])

    def test_the_sound_run_records_every_conclusion_it_claims(self):
        """The positive, read through the reported conclusions.

        Previously the positive asserted only exit 0, so a run that
        completed while recording nothing would have passed.
        """
        _, code, evidence, _ = self._run()
        self.assertEqual(code, 0, evidence.get("dirty_reasons"))
        self.assertFalse(evidence["lane_dirty"])
        self.assertTrue(evidence["baseline_complete"])
        self.assertTrue(evidence["preflight_passed"])
        self.assertTrue(evidence["published_nonce_validated"])
        self.assertTrue(evidence["inner_parent_child_verified"])
        # The child outlived the host client...
        self.assertEqual(
            evidence["inner_subject_after_host_kill"]["alive"], "true")
        # ...the rescue cleaned it up...
        self.assertIn(evidence["rescue"]["reports"][0]["outcome"],
                      ("reaped", "terminated_zombie"))
        self.assertEqual(
            evidence["owned_membership_after_rescue"]["alive"], "false")
        # ...and the same-label bystander was untouched.
        self.assertEqual(
            evidence["same_label_decoy_after_rescue"]["state"], "present")
        self.assertTrue(evidence["teardown_registered"]["proved"])
        # The claim is scoped to non-propagation, not causation.
        claim = evidence["inner_subject_after_host_kill"]["claim"]
        self.assertIn("did not propagate", claim)
        self.assertIn("not caused by the termination", claim)
