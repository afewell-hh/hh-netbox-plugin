"""Explicit #673 row -> test mapping (#674 non-blocking item 3).

Test count is not coverage. This declares which test carries each dispatched
row and fails if a named test disappears or is renamed, so a row cannot quietly
lose its only coverage. The mapping is declared, not inferred from names,
because inference would silently accept a row with no test at all.
"""

from __future__ import annotations

import unittest

from django.test import SimpleTestCase

#: #673 dispatches I1-I18 (with I8a, I11a-c), I26 core, I30, and the
#: architecture/dependency row. Value is the list of tests that carry the row.
ROW_TESTS = {
    "I1": ["test_core_contract.DecodeContractTestCase."
           "test_i1_yaml_and_json_decode_to_the_same_semantic_model",
           "test_semantics.YamlSafetyTestCase."
           "test_implicit_yaml_typing_cannot_change_a_value"],
    "I1a": ["test_core_contract.DecodeContractTestCase."
            "test_i1a_transport_metadata_does_not_decide_format"],
    "I3": ["test_core_contract.DecodeContractTestCase."
           "test_i3_missing_envelope_fields_are_source_located"],
    "I4": ["test_core_contract.DecodeContractTestCase."
           "test_i4_unknown_core_field_is_rejected_not_preserved"],
    "I5": ["test_core_contract.DecodeContractTestCase."
           "test_i5_unregistered_extension_namespace_is_rejected"],
    "I6": ["test_core_contract.DecodeContractTestCase."
           "test_i6_duplicate_mapping_key_is_rejected",
           "test_core_contract.DecodeContractTestCase."
           "test_i6_same_local_slug_under_distinct_parents_is_valid",
           "test_semantics.YamlSafetyTestCase."
           "test_duplicate_mapping_key_in_yaml_is_rejected",
           "test_semantics.YamlSafetyTestCase.test_yaml_anchor_and_alias_are_rejected",
           "test_semantics.YamlSafetyTestCase.test_unsupported_yaml_tag_is_rejected"],
    "I7": ["test_core_contract.CatalogReferenceTestCase."
           "test_i7_topology_without_an_explicit_catalog_version_cannot_import"],
    "I8": ["test_semantics.ReferenceGraphTestCase."
           "test_i8_cyclic_reference_where_disallowed_fails",
           "test_semantics.ReferenceGraphTestCase."
           "test_i8_cross_bundle_unresolved_reference_fails",
           "test_semantics.ReferenceGraphTestCase."
           "test_i8_valid_in_bundle_reference_resolves"],
    "I8a": ["test_core_contract.CatalogReferenceTestCase."
            "test_i8a_matching_version_with_mismatched_binding_is_rejected",
            "test_core_contract.CatalogReferenceTestCase."
            "test_i8a_same_version_alone_is_never_proof_of_equal_content",
            "test_core_contract.CatalogReferenceTestCase."
            "test_i8a_unknown_binding_algorithm_is_not_silently_equivalent"],
    "I9": ["test_semantics.TopologyFamilyTestCase."
           "test_i9_absent_family_declaration_is_rejected",
           "test_semantics.TopologyFamilyTestCase."
           "test_i9_each_family_complete_declaration_is_accepted",
           "test_semantics.TopologyFamilyTestCase."
           "test_i9_under_specified_family_intent_is_rejected",
           "test_semantics.TopologyFamilyTestCase."
           "test_i9_clos_requires_a_non_vacuous_spine_domain",
           "test_semantics.TopologyFamilyTestCase."
           "test_i9_single_switch_must_declare_its_capacity_bound",
           "test_semantics.TopologyFamilyTestCase."
           "test_i9_mesh_declared_with_a_spine_role_is_rejected",
           "test_semantics.TopologyFamilyTestCase."
           "test_i9_breakout_endpoint_without_parent_or_lane_is_rejected"],
    "I10": ["test_semantics.PhysicalCapabilityTestCase."
            "test_i10_native_fixed_port_is_accepted_without_a_transceiver",
            "test_semantics.PhysicalCapabilityTestCase."
            "test_i10_incompatible_overlay_on_a_native_port_is_rejected",
            "test_semantics.PhysicalCapabilityTestCase."
            "test_i10_media_overlay_is_not_silently_accepted_by_inference",
            "test_semantics.PhysicalCapabilityTestCase."
            "test_i10_integrated_assembly_is_not_inferred_from_a_pluggable_default"],
    "I11a": ["test_core_contract.RoundTripTestCase."
             "test_i11a_topology_subset_survives_the_round_trip",
             "test_core_contract.RoundTripTestCase."
             "test_i11a_topology_perturbation_is_detected_by_the_subset_comparison"],
    "I11b": ["test_core_contract.RoundTripTestCase."
             "test_i11b_full_model_round_trip_preserves_every_claimed_fact_class",
             "test_comparator_controls.ComparatorControlTestCase."
             "test_mutation_control_detects_each_fact_class_by_name_and_path"],
    "I11c": ["test_containment.ProductionDoesNotImportTestCodeTestCase."
             "test_no_production_module_imports_a_test_package",
             "test_containment.ProductionDoesNotImportTestCodeTestCase."
             "test_comparator_does_not_import_t1"],
    "I12": ["test_core_contract.DeterminismAndProvenanceTestCase."
            "test_i12_export_is_deterministic_under_specified_perturbations",
            "test_core_contract.DeterminismAndProvenanceTestCase."
            "test_i12_export_is_deterministic_across_independent_runs"],
    "I13": ["test_core_contract.DeterminismAndProvenanceTestCase."
            "test_i13_export_provenance_names_required_elements",
            "test_core_contract.DeterminismAndProvenanceTestCase."
            "test_i13_volatile_invocation_facts_stay_out_of_the_payload"],
    "I14": ["test_core_contract.DeterminismAndProvenanceTestCase."
            "test_i14_unsupported_fact_cannot_be_silently_dropped"],
    "I15": ["test_atomicity.PreWriteFailureTestCase."
            "test_i15_invalid_syntax_leaves_no_state",
            "test_atomicity.PreWriteFailureTestCase."
            "test_i15_schema_failure_leaves_no_state"],
    "I16a": ["test_atomicity.CommitBoundaryFaultTestCase."
             "test_i16a_fault_after_first_target_write_rolls_back_both_families"],
    "I16b": ["test_atomicity.CommitBoundaryFaultTestCase."
             "test_i16b_integrity_failure_in_second_target_rolls_back_the_first"],
    "I16c": ["test_atomicity.IngressFailureTestCase."
             "test_i16c_accepted_upload_is_not_retained_after_validation_failure"],
    # Both halves. Graceful cancellation does NOT substitute for process loss;
    # it is listed alongside, never instead of, the SIGKILL probe.
    "I16d": ["test_atomicity.HardProcessLossTestCase."
             "test_i16d_hard_process_loss_after_write_boundary_leaves_no_success",
             "test_atomicity.GracefulCancellationTestCase."
             "test_i16d_graceful_cancellation_after_write_boundary_leaves_no_success"],
    "I17": ["test_atomicity.SuccessStateTestCase."
            "test_i17_valid_import_creates_one_draft_and_one_unpublished_version",
            "test_atomicity.SuccessStateTestCase."
            "test_i17_import_does_not_mutate_existing_approved_content"],
    "I18": ["test_atomicity.RetryAndConflictTestCase."
            "test_i18_exact_retry_is_idempotent_and_creates_no_duplicate",
            "test_atomicity.RetryAndConflictTestCase."
            "test_i18_non_identical_reuse_of_an_identity_conflicts_with_zero_write"],
    "I26": ["test_core_contract.SecretBoundaryTestCase."
            "test_i26a_designated_credential_field_is_rejected",
            "test_core_contract.SecretBoundaryTestCase."
            "test_i26b_free_text_sentinel_documents_the_stated_limit"],
    "I30": ["test_core_contract.CorpusBaselineTestCase."
            "test_i30_pilot_round_trip_evidence_is_measured_and_downgraded",
            "test_core_contract.CorpusBaselineTestCase."
            "test_i30_ledger_is_the_source_of_the_expected_unresolved_set"],
}

#: Rows whose coverage is KNOWN INCOMPLETE, with the reason. Recorded here so a
#: gap is visible in the coverage map rather than discovered later by its
#: absence. A row may appear in both maps: partially covered is not covered.
#: Currently EMPTY. I16d's process-loss half was blocked here by the
#: TransactionTestCase teardown failure ("cannot truncate a table referenced in
#: a foreign key constraint"); that was repaired by overriding _fixture_teardown
#: to pass allow_cascade=True, so the row is genuinely covered rather than
#: deferred. The mechanism stays for the next real gap.
BLOCKED_ROWS: dict = {}

#: Known-weak bindings that a GREEN implementation must strengthen. These are
#: not coverage gaps -- the rows exist and fail correctly -- but their assertion
#: is looser than it will need to be once the target models exist.
GREEN_PHASE_BINDINGS = {
    "I16a/I16b": (
        "The write-boundary probe proves SOME durable change before faulting, "
        "not that the named catalog/design target was the first write. Bind it "
        "to the actual target tables via write_boundary_probe(expect_tables=...) "
        "once those models exist."
    ),
    "I30": (
        "Evidence is asserted from the value corpus_round_trip_evidence() "
        "returns, so an implementation could still manufacture the disposition "
        "and finding names. GREEN must derive them from actual pilot/invariant "
        "execution and its provenance envelope."
    ),
}

PACKAGE = "netbox_hedgehog.tests.test_interchange"


class RowCoverageTestCase(SimpleTestCase):

    def test_green_phase_bindings_are_declared_with_a_reason(self):
        """A known-weak assertion must be written down, not left to be noticed."""
        for label, reason in sorted(GREEN_PHASE_BINDINGS.items()):
            with self.subTest(binding=label):
                self.assertGreater(len(reason), 80,
                                   f'{label} needs a substantive reason')

    def test_blocked_rows_are_declared_with_a_reason(self):
        """A known gap must be stated, not implied by absence."""
        for row, reason in sorted(BLOCKED_ROWS.items()):
            with self.subTest(row=row):
                self.assertIn(row, ROW_TESTS, f'{row} is blocked but not dispatched')
                self.assertGreater(len(reason), 80,
                                   f'{row} needs a substantive reason, not a label')

    def test_every_dispatched_row_names_at_least_one_test(self):
        empty = sorted(row for row, tests in ROW_TESTS.items() if not tests)
        self.assertEqual(empty, [], f'rows with no test: {empty}')

    def test_every_named_test_exists(self):
        """Fails if a test is renamed or deleted, so a row cannot lose its only
        coverage silently."""
        loader = unittest.TestLoader()
        missing = []
        for row, tests in sorted(ROW_TESTS.items()):
            for dotted in tests:
                module_name, class_name, method = dotted.split(".")
                try:
                    module = __import__(f"{PACKAGE}.{module_name}", fromlist=[class_name])
                    case = getattr(module, class_name)
                    if not callable(getattr(case, method, None)):
                        missing.append(f"{row}: {dotted}")
                except (ImportError, AttributeError) as exc:
                    missing.append(f"{row}: {dotted} ({exc})")
        del loader
        self.assertEqual(missing, [], f'rows pointing at missing tests: {missing}')
