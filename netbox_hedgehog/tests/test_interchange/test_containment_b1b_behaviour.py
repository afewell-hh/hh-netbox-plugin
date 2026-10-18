"""#716 B1b behavioural controls: mutation-sensitive, driving the real code.

Every earlier B1b control was a source-position check, a copied predicate,
or an independent snippet, and all eighteen passed when nonce validation
was removed, start-identity comparison disabled, and fixture registration
commented out. These drive the real `main()` through a mocked harness, so a
mutation to the implementation changes the result here.

No Docker, no containers, no signals.
"""

from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from netbox_hedgehog.tests.test_interchange import containment_b1b_harness as H


# Keys recorded for a human reading the artifact, not claims a control can
# falsify: traces, timings, diagnostic strings and failure-path records
# whose own guards are asserted elsewhere. Anything NOT listed here must be
# read by a control -- enforced by
# test_every_recorded_fact_is_read_or_declared_diagnostic.
DIAGNOSTIC_ONLY = (
    # Run identity and traces, written for a human reading the artifact.
    "step", "lane", "run_id", "observed_at",
    "stages",                   # ordered human-readable trace
    "lifecycle_order",          # docker event ordering
    "timing",                   # durations
    "timing.publication_seconds",
    "timing.host_client_terminated_after_seconds",
    "timing.total_seconds",
    "preflight.lane",
    "preflight.observation_deadline_seconds",
    # Identity inputs, not conclusions.
    "host_client_pid",
    "host_client_returncode",
    "expected_argv",            # asserted through binding.expected_argv
    # Diagnostic strings beside a conclusion that IS asserted.
    "inner_subject_after_host_kill.detail",
    "owned_membership_after_rescue.detail",
    "same_label_decoy_after_rescue.detail",
    "same_label_decoy_after_rescue.note",
    "preflight_failure",
    "registry",                 # serialised; teardown proof is asserted
    # The checks dict: its shortfall is asserted by name in the negatives
    # suite, and preflight refuses unless every required check is True.
    "preflight.checks",
    "preflight.label_discovery_candidates",
    # Crash record. Its recovery path is a #717 row, not a claim this
    # baseline reports.
    "unhandled_exception",
    "unhandled_exception.type",
    "unhandled_exception.message",
)


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
        decoy = evidence["same_label_decoy_after_rescue"]
        self.assertEqual(decoy["state"], "present")
        # The discrimination only means anything if the bystander really
        # carried the registered container's own label.
        self.assertEqual(decoy["label"],
                         f"hh716.run={evidence['preflight']['run_id']}",
                         "the decoy did not carry this run's actual label")
        self.assertTrue(evidence["teardown_registered"]["proved"])
        # The claim is scoped to non-propagation, not causation.
        claim = evidence["inner_subject_after_host_kill"]["claim"]
        self.assertIn("did not propagate", claim)
        self.assertIn("not caused by the termination", claim)

    # ------------------------------------------------------------------
    # Ownership ordering: the rescue owner must be proven by execution
    # BEFORE any orphan is induced. This is a precondition, so asserting
    # only that readiness happened is not enough -- it has to happen first.
    # ------------------------------------------------------------------

    def test_rescue_readiness_is_proven_before_the_orphan_is_induced(self):
        """A rescue owner proven only afterwards leaves a window with a
        live orphan and no demonstrated means of removing it."""
        _, code, evidence, recorded = self._run()
        self.assertEqual(code, 0, evidence.get("dirty_reasons"))
        events = recorded["events"]
        self.assertIn(("launch", "readiness"), events,
                      "no readiness subject was ever launched")
        self.assertIn(("rescue_signal", "readiness"), events,
                      "readiness was never proven by an actual signal")
        self.assertIn(("launch", "baseline"), events,
                      "no baseline subject was launched")
        proof = events.index(("rescue_signal", "readiness"))
        induced = events.index(("launch", "baseline"))
        self.assertLess(
            proof, induced,
            f"the rescue owner was proven at event {proof} but the orphan "
            f"was induced at event {induced}; readiness must precede it")
        self.assertTrue(evidence["rescue_readiness"]["clean"]["signalled"],
                        "readiness recorded without a signal having been sent")

    def test_a_readiness_failure_prevents_the_orphan_from_being_induced(self):
        """If readiness cannot be proven, nothing may be orphaned at all."""
        _, code, evidence, recorded = self._run(readiness_outcome="skipped")
        self.assertNotEqual(code, 0, "an unproven owner still induced")
        self.assertTrue(evidence["lane_dirty"])
        self.assertNotIn("baseline_complete", evidence)
        self.assertNotIn("baseline", recorded["launches"],
                         "an orphan was induced without a proven owner")

    def test_ownership_is_verified_before_termination(self):
        """The pre-termination verification is the ownership gate."""
        _, code, evidence, _ = self._run()
        self.assertEqual(code, 0, evidence.get("dirty_reasons"))
        report = evidence["pre_termination_verification"]["reports"][0]
        self.assertTrue(report["verified"])
        self.assertFalse(report["signalled"],
                         "the verification pass sent a signal")
        self.assertEqual(report["pid"], H.CHILD_PID)
        # Both sides of the binding are recorded, and agree.
        self.assertEqual(evidence["publication"]["child"]["pid"], H.CHILD_PID)
        self.assertEqual(evidence["publication"]["parent"]["nonce"],
                         evidence["publication"]["child"]["nonce"])
        self.assertEqual(evidence["binding"]["nonce"],
                         evidence["publication"]["child"]["nonce"])
        self.assertTrue(evidence["binding"]["expected_argv"],
                        "bound without an expected argv to compare against")

    def test_unverified_ownership_blocks_the_termination(self):
        """The gate must stop the run, not merely be recorded.

        Asserting only that the recorded report says `verified` left the
        gate untested: the fixture always reported success, so removing the
        gate changed nothing observable.
        """
        _, code, evidence, recorded = self._run(verification_verified=False)
        self.assertNotEqual(code, 0, "termination proceeded unverified")
        self.assertTrue(evidence["lane_dirty"])
        self.assertNotIn("baseline_complete", evidence)
        self.assertTrue(any("ownership not verified" in r
                            for r in evidence["dirty_reasons"]),
                        evidence["dirty_reasons"])
        self.assertFalse(
            [c for c in recorded["rescue_calls"] if c["send_signal"]
             and any(e.get("pid") == H.CHILD_PID for e in c["entries"])],
            "the baseline child was signalled without verified ownership")

    def test_every_recorded_fact_is_read_or_declared_diagnostic(self):
        """Standing guard against unfalsified claims.

        A static audit found 17 of 28 evidence keys recorded but read by
        no control, so conclusions went unverified while the path was
        checked. This fails when a key is added that no control reads.

        Enumerating write forms and patching the gaps failed four times
        running, because the scanner looked for shapes it knew and an
        unrecognised construct was simply absent rather than rejected.

        `evidence_grammar_scan` now classifies at the NODE level: every
        maximal `evidence`-rooted expression in the module is located and
        classified, and the last branch is `else: violation`. Stores are
        keyed on `ctx`, not on statement type, so every store position --
        assignment, augmented, annotated, chained, `for` target, `with
        ... as`, comprehension target, and tuple/list targets nested to
        any depth -- is recorded by construction rather than by having
        been anticipated. Loads that merely inspect are allowed; loads
        that RETAIN the object (a container, a return, a yield, a
        closure, a foreign callable) are rejected, since a write through
        a retained reference is as invisible as an alias write.

        Only the control modules count as readers -- not the harness,
        which reads keys to drive injections, not to falsify them.

        The scan also fails if the module performs any reflective or
        indirect-reachability operation outside the three declared
        reflection productions, so the coverage claim rests on a module
        that cannot reach a binding namespace in the first place.
        """
        here = Path(__file__).parent
        subject = str(here / "containment_b1b.py")

        written, violations = H.evidence_grammar_scan(subject)
        # Anything the grammar does not recognise is a violation, not a
        # silent omission. Three rounds of patching individual bypasses
        # each left another form uncounted; this inverts the burden.
        self.assertEqual(
            violations, [],
            "these constructs fall outside the supported evidence-write "
            f"grammar, so this control cannot speak for them: {violations}")

        read = H.evidence_read_paths([
            str(here / "test_containment_b1b_behaviour.py"),
            str(here / "test_containment_b1b_negatives.py")])

        # Canary against an over-broad collector, which would make this
        # control pass vacuously. `stages` is written by the subject and
        # appears in prose and in the declaration, but is never accessed
        # on `evidence`, so a collector crediting bare strings picks it up.
        self.assertNotIn("stages", read,
                         "the collector credited a string that is never "
                         "accessed on `evidence`; coverage is inflated")
        self.assertGreaterEqual(
            len(read), 30,
            f"the collector found only {len(read)} reads; it is probably "
            "not matching accesses")
        self.assertGreaterEqual(
            len(written), 50,
            f"the collector found only {len(written)} writes; it is "
            "probably not matching assignments")

        unfalsified = sorted(written - read - set(DIAGNOSTIC_ONLY))
        self.assertEqual(
            unfalsified, [],
            "these evidence paths are recorded but no control reads them, "
            "so their value is unfalsified. Either assert them or add them "
            f"to DIAGNOSTIC_ONLY with a reason: {unfalsified}")

        stale = sorted(set(DIAGNOSTIC_ONLY) - written)
        self.assertEqual(
            stale, [],
            f"DIAGNOSTIC_ONLY names paths nothing records: {stale}")

    # ------------------------------------------------------------------
    # The manifest boundary itself. The coverage control above can only
    # be trusted if the scan is fail-closed, if permission tracks the
    # module's actual operations, and if recognition alone cannot grant
    # acceptance.
    # ------------------------------------------------------------------

    def _scan_snippet(self, body):
        """Scan a throwaway module containing `body` inside a function."""
        source = (
            "import json\n\n\n"
            "def main():\n"
            '    evidence = {"step": "x"}\n'
            f"    {body}\n"
            "    return json.dumps(evidence)\n")
        with tempfile.TemporaryDirectory(prefix="hh716-grammar-") as work:
            path = Path(work) / "subject.py"
            path.write_text(source, encoding="utf-8")
            # A snippet exercises a handful of productions by
            # construction, so the manifest-vs-subject check -- which is
            # about the designated collector module -- is not applied.
            return H.evidence_grammar_scan(str(path),
                                           check_manifest_usage=False)

    def test_the_fail_closed_default_rejects_an_undeclared_operation(self):
        """An operation matching no production must be REJECTED, not
        silently uncounted.

        This is the branch that makes the boundary fail-closed, so it is
        exercised directly rather than inferred: broadening or deleting
        it makes this control fail even though the real subject would
        still scan clean.
        """
        for body in ('box = [evidence]',
                     'ev = evidence or {}',
                     'evidence.update({"k": 1})',
                     'for evidence["k"] in range(2): pass',
                     'held = evidence.setdefault("k", {})["j"]'):
            with self.subTest(body=body):
                _, violations = self._scan_snippet(body)
                self.assertTrue(
                    violations,
                    f"{body!r} matched no production yet produced no "
                    f"violation; the default-allow branch is back")
                self.assertTrue(
                    any(H.GRAMMAR_VERSION in v or "no declared production" in v
                        or "invisible" in v or "undeclared" in v
                        for v in violations),
                    f"violations do not name the boundary: {violations}")

    def test_permission_tracks_the_modules_actual_operations(self):
        """Manifest vs subject, in both directions.

        A production nobody performs is standing permission for an
        operation the module does not make, and a production the module
        does perform must be declared rather than merely recognised.
        """
        here = Path(__file__).parent
        subject = str(here / "containment_b1b.py")
        _, violations = H.evidence_grammar_scan(subject)
        self.assertEqual(violations, [], violations)

        declared = {p.id for p in H.MANIFEST}
        self.assertEqual(
            declared, set(H.RECOGNIZERS),
            "every declared production needs a recognizer and every "
            "recognizer needs a declaration")
        for production in H.MANIFEST:
            with self.subTest(production=production.id):
                self.assertIn(production.effect,
                              ("records", "reads", "observes"))
                self.assertTrue(production.shape and production.consumer)

    def test_a_production_the_module_never_performs_is_rejected(self):
        """Stale permission must fail rather than sit unused."""
        extra = H.Production("NEVER_USED", "unused shape", "nothing", 1,
                             "str-literal", "records")
        original = H.MANIFEST
        H.MANIFEST = original + (extra,)
        H.RECOGNIZERS["NEVER_USED"] = lambda ctxt: None
        try:
            here = Path(__file__).parent
            _, violations = H.evidence_grammar_scan(
                str(here / "containment_b1b.py"))
            self.assertTrue(
                any("NEVER_USED" in v for v in violations),
                f"a production nothing performs was accepted: {violations}")
        finally:
            H.MANIFEST = original
            H.RECOGNIZERS.pop("NEVER_USED", None)

    def test_recognition_alone_cannot_accept_an_operation(self):
        """A recognizer without a manifest entry must not grant acceptance.

        Otherwise a newly introduced collector operation becomes allowed
        the moment scanner logic happens to match it, with no deliberate
        declaration of its path semantics.
        """
        H.RECOGNIZERS["UNDECLARED"] = lambda ctxt: (True, set(), [])
        try:
            here = Path(__file__).parent
            _, violations = H.evidence_grammar_scan(
                str(here / "containment_b1b.py"))
            self.assertTrue(
                any("UNDECLARED" in v for v in violations),
                f"an undeclared recognizer passed unnoticed: {violations}")
        finally:
            H.RECOGNIZERS.pop("UNDECLARED", None)

    def test_a_safe_recipient_needs_a_stable_identity_not_a_spelling(self):
        """The serializer allowlist matches names, and names can be
        rebound."""
        _, clean = self._scan_snippet('pass')
        self.assertEqual(clean, [], clean)
        _, violations = self._scan_snippet('json = len')
        self.assertTrue(
            any("untouched import" in v or "stable identity" in v
                for v in violations),
            f"a rebound serializer name was still trusted: {violations}")

    def test_a_local_callable_needs_a_stable_identity_not_a_spelling(self):
        """Dev B's blocking finding on the manifest boundary.

        ARG_LOCAL_FN resolved a call by matching the `def` name, so a
        module that rebound that name leaked the evidence dict through
        whatever it was rebound to, with a zero-violation scan. The same
        identity rule already applied to serializer names had simply not
        been applied here.
        """
        sound = (
            "import json\n\n\n"
            # The callee's parameter is named `evidence`, so its own
            # body is scanned too; it must only record, never retain.
            "def sink(evidence):\n"
            '    evidence["seen"] = True\n\n\n'
            "def main():\n"
            '    evidence = {"step": "x"}\n'
            "    sink(evidence)\n"
            "    return json.dumps(evidence)\n")
        leaks = {
            "module-level rebind": "sink = print\n",
            "shadowed by a second def": "def sink():\n    pass\n",
            "shadowed by a class": "class sink:\n    pass\n",
            # A `global` declaration announces that another scope may
            # rebind the name, so its identity is not resolvable here
            # even though this module contains no assignment to it.
            "declared global elsewhere":
                "def rebind():\n    global sink\n    sink = print\n",
        }
        # Binding forms that are NOT assignment statements. The identity
        # helper first enumerated statement types and so missed every
        # one of these -- the same mistake the scanner was rewritten to
        # avoid, repeated in its own helper.
        inline_leaks = {
            "walrus": "    (sink := print)\n",
            "comprehension target": "    [0 for sink in range(1)]\n",
            "match capture": "    match 1:\n        case sink:\n"
                             "            pass\n",
            "match star": "    match [1]:\n        case [*sink]:\n"
                          "            pass\n",
            "match mapping rest": "    match {}:\n        case {**sink}:\n"
                                  "            pass\n",
            "for target": "    for sink in []:\n        pass\n",
            "tuple unpacking": "    sink, _z = print, 1\n",
        }

        def scan(source):
            with tempfile.TemporaryDirectory(prefix="hh716-ident-") as work:
                path = Path(work) / "subject.py"
                path.write_text(source, encoding="utf-8")
                return H.evidence_grammar_scan(str(path),
                                               check_manifest_usage=False)

        _, clean = scan(sound)
        self.assertEqual(clean, [],
                         f"the sound positive must scan clean: {clean}")

        for label, preamble in leaks.items():
            with self.subTest(rebinding=label):
                _, violations = scan(preamble + "\n\n" + sound)
                self.assertTrue(
                    violations,
                    f"{label}: evidence leaked through a rebound callable "
                    f"with a zero-violation scan")
                self.assertTrue(
                    any("stable identity" in v for v in violations),
                    f"{label}: rejected, but not for the identity reason: "
                    f"{violations}")

        for label, statement in inline_leaks.items():
            with self.subTest(inline_rebinding=label):
                _, violations = scan(
                    sound.replace("    sink(evidence)\n",
                                  statement + "    sink(evidence)\n"))
                self.assertTrue(
                    any("stable identity" in v for v in violations),
                    f"{label}: a non-assignment binding left the callable "
                    f"trusted: {violations}")

        # Namespace access of ANY kind can rebind any name, so nothing
        # in the module is identity-stable. A first version looked only
        # for a subscript store through `globals()`, so every
        # mapping-method mutation walked past it -- Dev B's follow-up
        # finding -- and the mapping could also be bound to a name or
        # handed to a foreign callable first.
        namespace_leaks = {
            "subscript store": '    globals()["sink"] = print\n',
            "update by keyword": "    globals().update(sink=print)\n",
            "update by mapping": '    globals().update({"sink": print})\n',
            "setdefault": '    globals().setdefault("sink", print)\n',
            "pop": '    globals().pop("sink", None)\n',
            "locals()": "    locals().update(sink=print)\n",
            "vars()": "    vars().update(sink=print)\n",
            "mapping bound to a name first":
                "    g = globals()\n    g.update(sink=print)\n",
            "mapping handed to a foreign callable":
                "    import copy\n    copy.copy(globals())\n",
            "exec": '    exec("sink = print")\n',
            "setattr on this module":
                "    import sys\n"
                '    setattr(sys.modules[__name__], "sink", print)\n',
            "module __dict__":
                "    import sys\n"
                '    sys.modules[__name__].__dict__["sink"] = print\n',
            # Reaching the same builtins under another spelling. Three
            # versions of the risk check were escaped this way, so these
            # are matched on resolved identity, not on a bare name.
            "builtins.globals()":
                "    import builtins\n"
                "    builtins.globals().update(sink=print)\n",
            "builtins imported under an alias":
                "    import builtins as b\n"
                "    b.globals().update(sink=print)\n",
            "globals imported from builtins":
                "    from builtins import globals as g\n"
                "    g().update(sink=print)\n",
            "exec imported from builtins":
                "    from builtins import exec as e\n"
                '    e("sink = print")\n',
            "globals bound to a local name":
                "    g = globals\n    g().update(sink=print)\n",
            "builtins.setattr":
                "    import builtins, sys\n"
                '    builtins.setattr(sys.modules[__name__], "sink", print)\n',
            "__builtins__ mapping":
                '    __builtins__["globals"]().update(sink=print)\n',
            "importlib.reload":
                "    import importlib, sys\n"
                "    importlib.reload(sys.modules[__name__])\n",
            # Reached without ever naming the attribute, so only the
            # import itself can catch it. Without these two the
            # import-flagging branch is redundant with the attribute
            # branch and could be deleted with no control failing.
            "getattr on the builtins module":
                "    import builtins\n"
                '    f = getattr(builtins, "globals")\n'
                "    f().update(sink=print)\n",
            "builtins imported and never named again":
                "    import builtins\n    _ = builtins\n",
        }
        for label, statement in namespace_leaks.items():
            with self.subTest(namespace_rebinding=label):
                _, violations = scan(
                    sound.replace("    sink(evidence)\n",
                                  statement + "    sink(evidence)\n"))
                self.assertTrue(
                    any("stable identity" in v for v in violations),
                    f"{label}: a namespace mutation left local callables "
                    f"trusted: {violations}")

        # The breadth is deliberate, and it must stay reported rather
        # than inferred: the risk helper names its reasons.
        here = Path(__file__).parent
        subject = ast.parse(
            (here / "containment_b1b.py").read_text(encoding="utf-8"))
        self.assertEqual(
            H._namespace_rebinding_risk(subject), [],
            "the collector module itself uses a namespace or dynamic "
            "binding form; it needs a declared production, not a looser "
            "default")

    # ------------------------------------------------------------------
    # Bounded reflection prohibition (#716 lead decision).
    #
    # Five successive namespace-risk predicates were each escaped by a
    # spelling they did not match, the last using an attribute name
    # built at runtime -- which no name-matching rule can ever catch. So
    # reflection is prohibited rather than analysed, with an allowlist
    # of the three productions the collector already performs.
    # ------------------------------------------------------------------

    #: Exercises all three permitted productions and nothing else.
    PERMITTED_REFLECTION = (
        "import importlib.util\n"
        "import sys\n\n\n"
        "def _load(name):\n"
        '    spec = importlib.util.spec_from_file_location(f"p_{name}",\n'
        '                                                  "/tmp/x.py")\n'
        "    module = importlib.util.module_from_spec(spec)\n"
        '    sys.modules[f"p_{name}"] = module\n'
        "    spec.loader.exec_module(module)\n"
        "    return module\n\n\n"
        "def main():\n"
        "    try:\n"
        "        pass\n"
        "    except Exception as exc:\n"
        '        return f"{type(exc).__name__}"\n')

    def test_the_three_permitted_reflection_productions_are_accepted(self):
        """The positives. Without these the prohibition could be
        satisfied by rejecting everything, including the collector's own
        module loading and its exception-name diagnostics."""
        violations = H.reflection_scan(ast.parse(self.PERMITTED_REFLECTION))
        self.assertEqual(violations, [], violations)

        declared = {p.id for p in H.REFLECTION_MANIFEST}
        self.assertEqual(declared, set(H._REFLECTION_MATCHERS),
                         "every declared reflection production needs a "
                         "matcher and every matcher a declaration")
        for production in H.REFLECTION_MANIFEST:
            with self.subTest(production=production.id):
                self.assertTrue(production.shape and production.rationale)

    def test_the_collector_performs_only_permitted_reflection(self):
        here = Path(__file__).parent
        subject = ast.parse(
            (here / "containment_b1b.py").read_text(encoding="utf-8"))
        self.assertEqual(H.reflection_scan(subject), [])

    def test_indirect_reachability_forms_are_prohibited(self):
        """The five escapes, preserved as regressions.

        S5 is the decisive one: the attribute name is assembled at
        runtime, so it appears nowhere in the source. It is caught
        because `getattr` is prohibited outright, not because anything
        inspected what it reaches.
        """
        leaks = {
            "S1 sys.modules subscript": (
                "    import sys\n"
                '    getattr(sys.modules["builtins"], "globals")()\n',
                "`getattr`"),
            "S2 sys.modules via a variable": (
                "    import sys\n    mods = sys.modules\n"
                '    getattr(mods["builtins"], "globals")()\n',
                "`modules`"),
            "S3 importlib.import_module": (
                "    import importlib\n"
                '    getattr(importlib.import_module("builtins"), "g")()\n',
                "`import_module`"),
            "S4 __subclasses__ graph walk": (
                '    getattr([].__class__.__base__.__subclasses__()[0], "x")\n',
                "`__subclasses__`"),
            "S5 attribute name built at runtime": (
                "    import sys\n"
                '    n = "glo" + "bals"\n'
                '    getattr(sys.modules["builtins"], n)()\n',
                "`getattr`"),
            # Reached through no reflective CONSTRUCT at all, so only
            # the import rejection can catch these. Without them that
            # branch is redundant with the others and could be deleted
            # with no control failing.
        }
        for label, (body, reason) in leaks.items():
            with self.subTest(leak=label):
                source = "def main():\n" + body
                # `check_manifest_usage=False`: a snippet performs none
                # of the three permitted productions, so the usage check
                # would make every one of these pass for the wrong
                # reason -- as it did, until mutations that permit the
                # construct outright were found still passing.
                violations = H.reflection_scan(ast.parse(source),
                                               check_manifest_usage=False)
                self.assertTrue(
                    violations,
                    f"{label}: reached a namespace with no violation")
                self.assertTrue(
                    any(reason in v for v in violations),
                    f"{label}: rejected, but not for the stated reason "
                    f"({reason!r}): {violations}")

    def test_near_misses_of_the_permitted_forms_are_prohibited(self):
        """The allowlist matches shape AND context, not a module name."""
        base = self.PERMITTED_REFLECTION
        near_misses = {
            "sys.modules read instead of store":
                (base, 'sys.modules[f"p_{name}"] = module',
                 'module = sys.modules["builtins"]', "`modules`"),
            "type() without .__name__":
                (base, 'f"{type(exc).__name__}"', "type(exc)", "`type`"),
            "__name__ off another object":
                (base, 'f"{type(exc).__name__}"',
                 'f"{exc.__class__.__name__}"', "__name__"),
            "importlib.import_module":
                (base, "importlib.util.module_from_spec(spec)",
                 'importlib.import_module("x")', "`import_module`"),
            "getattr anywhere":
                (base, "    return module", '    return getattr(module, "x")',
                 "`getattr`"),
        }
        for label, (source, old, new, reason) in near_misses.items():
            with self.subTest(near_miss=label):
                self.assertIn(old, source, f"{label}: fixture drifted")
                # `check_manifest_usage=False`: replacing a permitted
                # form removes it, so the usage check would fire and the
                # assertion would pass for the wrong reason -- it did,
                # until two mutations that disable the real rules were
                # found still passing.
                violations = H.reflection_scan(
                    ast.parse(source.replace(old, new, 1)),
                    check_manifest_usage=False)
                self.assertTrue(
                    violations,
                    f"{label}: a near miss of a permitted production was "
                    f"accepted")
                self.assertTrue(
                    any(reason in v for v in violations),
                    f"{label}: rejected, but not for the stated reason "
                    f"({reason!r}): {violations}")

    def test_reflection_permission_tracks_the_module(self):
        """Stale permission, and permission by recognition alone."""
        here = Path(__file__).parent
        subject = ast.parse(
            (here / "containment_b1b.py").read_text(encoding="utf-8"))

        extra = H.ReflectionProduction("RFL_NEVER", "unused", "none")
        original = H.REFLECTION_MANIFEST
        H.REFLECTION_MANIFEST = original + (extra,)
        H._REFLECTION_IDS.add("RFL_NEVER")
        H._REFLECTION_MATCHERS["RFL_NEVER"] = lambda n, p, t=(): False
        try:
            self.assertTrue(
                any("RFL_NEVER" in v for v in H.reflection_scan(subject)),
                "a reflection production nothing performs was accepted")
        finally:
            H.REFLECTION_MANIFEST = original
            H._REFLECTION_IDS.discard("RFL_NEVER")
            H._REFLECTION_MATCHERS.pop("RFL_NEVER", None)

        H._REFLECTION_MATCHERS["RFL_UNDECLARED"] = lambda n, p, t=(): True
        try:
            self.assertTrue(
                any("RFL_UNDECLARED" in v
                    for v in H.reflection_scan(subject)),
                "an undeclared reflection matcher granted permission")
        finally:
            H._REFLECTION_MATCHERS.pop("RFL_UNDECLARED", None)

    def test_reflection_violations_are_part_of_the_scan_verdict(self):
        """The prohibition must reach `evidence_grammar_scan`.

        The other reflection controls call `reflection_scan` directly,
        so detaching it from the scan's verdict left them all passing
        while the boundary no longer enforced anything.
        """
        source = (
            "import json\n\n\n"
            "def main():\n"
            '    evidence = {"step": "x"}\n'
            '    getattr(evidence, "keys")\n'
            "    return json.dumps(evidence)\n")
        with tempfile.TemporaryDirectory(prefix="hh716-rfl-") as work:
            path = Path(work) / "subject.py"
            path.write_text(source, encoding="utf-8")
            _, violations = H.evidence_grammar_scan(
                str(path), check_manifest_usage=False)
        self.assertTrue(
            any("getattr" in v for v in violations),
            f"a reflective construct did not fail the scan: {violations}")

    # ------------------------------------------------------------------
    # Approved import manifest.
    #
    # The import rule was a denylist of reflective module names.
    # `from pkgutil import resolve_name` defeated it: resolve_name turns
    # the string "builtins:globals" into the callable, naming nothing
    # the denylist knew. pkgutil, ctypes, gc, inspect and pickle all
    # reach a namespace and that list has no end, so imports became an
    # allowlist of the exact forms this collector uses.
    # ------------------------------------------------------------------

    def _import_scan(self, source):
        return H.import_scan(ast.parse(source), check_manifest_usage=False)

    def test_any_unapproved_import_form_fails(self):
        """Dev B's requested regression: a NEW import form fails unless
        declared, whether or not anyone judged it reflective."""
        unapproved = {
            "pkgutil.resolve_name": "from pkgutil import resolve_name\n",
            "ctypes": "import ctypes\n",
            "gc": "import gc\n",
            "inspect": "import inspect\n",
            "pickle": "import pickle\n",
            "operator.attrgetter": "from operator import attrgetter\n",
            "builtins": "import builtins\n",
            "a builtin by name": "from builtins import globals as g\n",
            # Not reflective at all, and still rejected: the rule is the
            # allowlist, not a judgement about what a module can reach.
            "an unknown third party": "import requests\n",
            "a star import": "from os import *\n",
            "a relative import": "from . import siblings\n",
            # A relative import whose (module, name) COLLIDES with an
            # approved key: `.pathlib` is a sibling module, not the
            # stdlib one, so without the relative-import branch this
            # resolves to an approved form and shadows it.
            "a relative import shadowing an approved form":
                "from .pathlib import Path\n",
            "a parent-relative import shadowing an approved form":
                "from ..pathlib import Path\n",
            # Approved module, unapproved SPELLING.
            "an approved module under an alias": "import json as j\n",
            "an approved name under an alias":
                "from pathlib import Path as P\n",
            "a different member of an approved module":
                "from pathlib import PurePath\n",
            "importlib without .util": "import importlib\n",
        }
        for label, source in unapproved.items():
            with self.subTest(import_form=label):
                violations = self._import_scan(source)
                self.assertTrue(
                    violations,
                    f"{label}: an unapproved import form was accepted")
                self.assertTrue(
                    any("not an approved import form" in v
                        for v in violations),
                    f"{label}: rejected, but not as an unapproved import: "
                    f"{violations}")

    def test_the_approved_import_forms_are_accepted(self):
        """The positives. Without them the allowlist could be satisfied
        by rejecting every import, including the collector's own."""
        for form in H.IMPORT_MANIFEST:
            with self.subTest(form=form.spelling()):
                self.assertEqual(
                    self._import_scan(form.spelling() + "\n"), [],
                    f"{form.spelling()} is declared but rejected")
                self.assertTrue(form.rationale,
                                "every approved import needs a rationale")

    def test_the_collector_imports_exactly_the_approved_forms(self):
        here = Path(__file__).parent
        subject = ast.parse(
            (here / "containment_b1b.py").read_text(encoding="utf-8"))
        self.assertEqual(H.import_scan(subject), [])

    def test_import_permission_tracks_the_module(self):
        """A declared import the module does not perform is stale."""
        extra = H.ImportForm("import", None, "never_imported", None, "none")
        original = H.IMPORT_MANIFEST
        H.IMPORT_MANIFEST = original + (extra,)
        try:
            here = Path(__file__).parent
            subject = ast.parse(
                (here / "containment_b1b.py").read_text(encoding="utf-8"))
            self.assertTrue(
                any("never_imported" in v for v in H.import_scan(subject)),
                "a declared import nothing performs was accepted")
        finally:
            H.IMPORT_MANIFEST = original

    def test_import_violations_are_part_of_the_scan_verdict(self):
        """The allowlist must reach `evidence_grammar_scan`."""
        source = (
            "import json\n"
            "from pkgutil import resolve_name\n\n\n"
            "def main():\n"
            '    evidence = {"step": "x"}\n'
            "    return json.dumps(evidence)\n")
        with tempfile.TemporaryDirectory(prefix="hh716-imp-") as work:
            path = Path(work) / "subject.py"
            path.write_text(source, encoding="utf-8")
            _, violations = H.evidence_grammar_scan(
                str(path), check_manifest_usage=False)
        self.assertTrue(
            any("resolve_name" in v for v in violations),
            f"an unapproved import did not fail the scan: {violations}")

    # ------------------------------------------------------------------
    # RFL_IMPORTLIB_LOAD, bound structurally.
    #
    # The matcher ended with `dotted.endswith(".loader.exec_module")`,
    # so ANY receiver could execute ANY argument -- the declared
    # production named `spec` and `module` and the matcher checked
    # neither. The receiver must now be a name bound in the same
    # function by spec_from_file_location, and the argument a name
    # bound there by module_from_spec(<that same spec>).
    # ------------------------------------------------------------------

    LOADER_PRELUDE = (
        "import importlib.util\n"
        "import sys\n\n\n"
        "def _load(name):\n"
        '    spec = importlib.util.spec_from_file_location(f"p_{name}",\n'
        '                                                  "/tmp/x.py")\n'
        "    module = importlib.util.module_from_spec(spec)\n"
        '    sys.modules[f"p_{name}"] = module\n')

    def _loader_scan(self, body):
        return H.reflection_scan(ast.parse(self.LOADER_PRELUDE + body),
                                 check_manifest_usage=False)

    def test_the_declared_loader_call_is_accepted(self):
        """The positive. Without it the binding could be satisfied by
        rejecting the collector's own module loading."""
        self.assertEqual(
            self._loader_scan("    spec.loader.exec_module(module)\n"
                              "    return module\n"),
            [])

    def test_only_the_bound_spec_and_module_may_execute(self):
        """Anything but the exact declared pairing must fail."""
        declared = "    spec.loader.exec_module(module)\n"
        negatives = {
            "a foreign receiver":
                declared + "    untrusted.loader.exec_module(module)\n",
            "an untrusted argument":
                "    spec.loader.exec_module(evil)\n",
            "a deep foreign chain":
                declared + "    a.b.c.loader.exec_module(payload)\n",
            "a loader off an imported module":
                "    import json\n    json.loader.exec_module(module)\n",
            "a receiver not from spec_from_file_location":
                "    spec2 = object()\n"
                "    spec2.loader.exec_module(module)\n",
            "a module built from a DIFFERENT spec":
                '    other = importlib.util.spec_from_file_location("o",\n'
                '                                                   "/o.py")\n'
                "    m2 = importlib.util.module_from_spec(other)\n"
                "    spec.loader.exec_module(m2)\n",
            "the spec rebound after binding":
                "    spec = object()\n"
                "    spec.loader.exec_module(module)\n",
            "the module rebound after binding":
                "    module = object()\n"
                "    spec.loader.exec_module(module)\n",
            "a keyword argument":
                "    spec.loader.exec_module(mod=module)\n",
            "an extra argument":
                "    spec.loader.exec_module(module, 1)\n",
            "a call expression as receiver":
                "    get_spec().loader.exec_module(module)\n",
            "the loader taken without calling it":
                declared + "    f = spec.loader\n",
            # Reaching exec_module without ever naming `loader`, so
            # only the `exec_module` prohibition catches these. Without
            # them it is redundant with `loader` and could be dropped
            # with no control failing.
            "exec_module on a bare name":
                declared + "    ldr.exec_module(payload)\n",
            "exec_module on a call result":
                declared + "    get().exec_module(payload)\n",
            "exec_module straight off the constructor":
                declared +
                '    importlib.util.spec_from_file_location("a",\n'
                '                                           "/b"'
                ").exec_module(payload)\n",
        }
        for label, body in negatives.items():
            with self.subTest(negative=label):
                violations = self._loader_scan(body + "    return module\n")
                self.assertTrue(
                    violations,
                    f"{label}: an undeclared loader call was accepted")
                self.assertTrue(
                    any("exec_module" in v or "loader" in v
                        for v in violations),
                    f"{label}: rejected, but not as a loader violation: "
                    f"{violations}")

    # ------------------------------------------------------------------
    # Stable identity for the importlib and sys paths.
    #
    # The matchers trusted the SPELLING `importlib.util.*`, so rebinding
    # `importlib` after its approved import left every dotted path
    # through it looking trustworthy while reaching something else. Same
    # rule already applied to serializers and local callables.
    # ------------------------------------------------------------------

    IDENTITY_PRELUDE = (
        "import importlib.util\n"
        "import sys\n\n\n"
        "def _load(name):\n"
        "{EXTRA}"
        '    spec = importlib.util.spec_from_file_location(f"p_{{name}}",\n'
        '                                                  "/tmp/x.py")\n'
        "    module = importlib.util.module_from_spec(spec)\n"
        '    sys.modules[f"p_{{name}}"] = module\n'
        "    spec.loader.exec_module(module)\n"
        "    return module\n")

    def _identity_scan(self, extra="", prefix=""):
        source = prefix + self.IDENTITY_PRELUDE.replace("{EXTRA}", extra)
        return H.reflection_scan(ast.parse(source),
                                 check_manifest_usage=False)

    def test_untouched_importlib_and_sys_are_accepted(self):
        """The positive: the collector's own loading must still pass.

        It briefly did not -- `_untouched_imports` counted the module's
        own `sys.modules[key] = module` as rebinding `sys`.
        """
        self.assertEqual(self._identity_scan(), [])

    def test_rebinding_importlib_or_sys_withdraws_the_production(self):
        negatives = {
            "importlib reassigned": ("    importlib = evil\n", ""),
            "importlib.util reassigned":
                ("    importlib.util = evil\n", ""),
            "importlib.util deleted": ("    del importlib.util\n", ""),
            "spec_from_file_location replaced":
                ("    importlib.util.spec_from_file_location = evil\n", ""),
            "importlib as a for target":
                ("    for importlib in []:\n        pass\n", ""),
            "importlib by walrus": ("    (importlib := evil)\n", ""),
            "importlib tuple-unpacked":
                ("    importlib, _z = evil, 1\n", ""),
            "importlib via with-as":
                ("    import contextlib\n"
                 "    with contextlib.nullcontext(1) as importlib:\n"
                 "        pass\n", ""),
            "importlib declared global": ("    global importlib\n", ""),
            "sys reassigned": ("    sys = evil\n", ""),
            "sys.modules reassigned": ("    sys.modules = evil\n", ""),
            "importlib shadowed by a def":
                ("", "def importlib():\n    pass\n\n\n"),
            "sys shadowed by a class": ("", "class sys:\n    pass\n\n\n"),
        }
        for label, (extra, prefix) in negatives.items():
            with self.subTest(rebinding=label):
                violations = self._identity_scan(extra, prefix)
                self.assertTrue(
                    violations,
                    f"{label}: a rebound module path was still trusted")

        # Each constructor alone, so neither spelling's prohibition is
        # redundant with the other's.
        alone = {
            "spec_from_file_location":
                "import importlib.util\n\n\ndef f():\n"
                "    importlib = evil\n"
                '    return importlib.util.spec_from_file_location("a",\n'
                '                                                  "/b")\n',
            "module_from_spec":
                "import importlib.util\n\n\ndef f():\n"
                "    importlib = evil\n"
                "    return importlib.util.module_from_spec(spec)\n",
        }
        for label, source in alone.items():
            with self.subTest(constructor_alone=label):
                violations = H.reflection_scan(
                    ast.parse(source), check_manifest_usage=False)
                self.assertTrue(
                    any(label in v for v in violations),
                    f"{label} alone was not prohibited: {violations}")
