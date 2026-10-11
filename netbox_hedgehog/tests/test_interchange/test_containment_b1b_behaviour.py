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

    def test_the_rescue_path_never_targets_the_decoy(self):
        """Only the registered scenario child may be signalled."""
        _, _, _, recorded = self._run()
        for entries in recorded["signalled"]:
            for entry in entries:
                self.assertNotEqual(
                    entry.get("pid"), H.DECOY_ID,
                    "the rescue path targeted the unregistered decoy")

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
