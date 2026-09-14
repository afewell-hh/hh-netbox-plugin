"""RED import atomicity and success state (#673, rows I15-I16d, I17, I18).

The distinction these rows exist to enforce
-------------------------------------------
I15 fails BEFORE any write is attempted. An implementation with no transaction
whatsoever -- one that merely validates first -- passes it. That is why I15
alone was rejected as proof of atomicity (#672 B1).

I16a-d inject the fault AFTER the first durable write inside the commit
boundary. They are the rows that actually separate an atomic implementation
from a validate-first one, and they must fail for the latter.

Each fault row asserts the same four-part zero-write guarantee: no target
record of EITHER family, no provenance, no success audit or event, and no
retained ingress artifact.
"""

from __future__ import annotations

from django.test import TestCase

from netbox_hedgehog.tests.test_interchange import fixtures
from netbox_hedgehog.tests.test_interchange._support import require_interchange


class _ImportStateMixin:
    """Shared zero-write assertions.

    Counts are taken through the production module's own accessors so the row
    cannot be satisfied by writing to a table the assertion does not know about.
    """

    def durable_state(self, module):
        return {
            "design_revisions": module.count_design_revisions(),
            "catalog_versions": module.count_catalog_versions(),
            "provenance_records": module.count_provenance_records(),
            "success_audit_records": module.count_success_audit_records(),
            "retained_ingress_artifacts": module.count_ingress_artifacts(),
        }

    def assert_zero_durable_writes(self, module, before, label):
        after = self.durable_state(module)
        self.assertEqual(
            after, before,
            f'{label}: import must leave zero durable writes. A surviving '
            f'record of either family, a provenance row, a success audit, or a '
            f'retained upload all break the all-or-nothing guarantee. '
            f'before={before} after={after}')


class PreWriteFailureTestCase(_ImportStateMixin, TestCase):
    """I15 - validation failures before any write. Necessary, not sufficient."""

    def test_i15_invalid_syntax_leaves_no_state(self):
        module = require_interchange()
        before = self.durable_state(module)
        with self.assertRaises(Exception):
            module.import_bundle(module.decode_document("{not: valid: json"), user=None)
        self.assert_zero_durable_writes(module, before, 'invalid syntax')

    def test_i15_schema_failure_leaves_no_state(self):
        module = require_interchange()
        before = self.durable_state(module)
        document = fixtures.valid_bundle()
        document["objects"][1].pop("schemaVersion")
        with self.assertRaises(Exception):
            module.import_bundle(
                module.decode_document(fixtures.to_json(document)), user=None)
        self.assert_zero_durable_writes(module, before, 'schema failure')


class CommitBoundaryFaultTestCase(_ImportStateMixin, TestCase):
    """I16a-d - faults injected after the first durable write.

    These must fail for a validate-first-but-nontransactional implementation.
    """

    def test_i16a_exception_after_first_target_write_rolls_back_both_families(self):
        """Mixed catalog+topology bundle; fail after the first target commits
        but before its counterpart and provenance complete."""
        module = require_interchange()
        before = self.durable_state(module)
        document = fixtures.valid_bundle()
        with self.assertRaises(Exception):
            with module.fault_after_first_target_write():
                module.import_bundle(
                    module.decode_document(fixtures.to_json(document)), user=None)
        self.assert_zero_durable_writes(module, before, 'I16a post-first-write fault')

    def test_i16b_integrity_failure_in_second_target_rolls_back_the_first(self):
        """No partial catalog-only or topology-only success."""
        module = require_interchange()
        before = self.durable_state(module)
        document = fixtures.valid_bundle()
        with self.assertRaises(Exception):
            with module.fault_on_second_target_write():
                module.import_bundle(
                    module.decode_document(fixtures.to_json(document)), user=None)
        self.assert_zero_durable_writes(module, before, 'I16b second-target fault')

    def test_i16c_validation_failure_after_upload_retains_no_artifact(self):
        """The upload is accepted by the request path, then validation fails."""
        module = require_interchange()
        before = self.durable_state(module)
        document = fixtures.valid_bundle()
        document["objects"][1]["invented"] = "value"
        with self.assertRaises(Exception):
            module.import_uploaded_artifact(fixtures.to_json(document), user=None)
        self.assert_zero_durable_writes(module, before, 'I16c post-upload failure')

    def test_i16d_hard_process_loss_after_write_boundary_leaves_no_success(self):
        """Abrupt termination runs no `finally`, so a cleanup design that relies
        on one is insufficient; the approved quarantine/reaper outcome must be
        proven instead."""
        module = require_interchange()
        before = self.durable_state(module)
        document = fixtures.valid_bundle()
        with self.assertRaises(Exception):
            with module.simulate_hard_process_loss_after_write():
                module.import_bundle(
                    module.decode_document(fixtures.to_json(document)), user=None)
        module.run_ingress_reaper()
        self.assert_zero_durable_writes(module, before, 'I16d hard process loss')

    def test_i16_failure_audit_never_claims_success(self):
        module = require_interchange()
        document = fixtures.valid_bundle()
        with self.assertRaises(Exception):
            with module.fault_after_first_target_write():
                module.import_bundle(
                    module.decode_document(fixtures.to_json(document)), user=None)
        for record in module.recent_audit_records():
            with self.subTest(record=record):
                self.assertNotEqual(record.outcome, "success")


class SuccessStateTestCase(_ImportStateMixin, TestCase):
    """I17 - exactly one new unapproved draft and one unpublished version."""

    def test_i17_valid_import_creates_one_draft_and_one_unpublished_version(self):
        module = require_interchange()
        before = self.durable_state(module)
        result = module.import_bundle(
            module.decode_document(fixtures.to_json(fixtures.valid_bundle())), user=None)
        after = self.durable_state(module)
        self.assertEqual(after["design_revisions"], before["design_revisions"] + 1)
        self.assertEqual(after["catalog_versions"], before["catalog_versions"] + 1)
        self.assertFalse(result.design_revision.approved)
        self.assertFalse(result.catalog_version.published)

    def test_i17_import_does_not_mutate_existing_approved_content(self):
        module = require_interchange()
        baseline = module.approved_content_fingerprint()
        module.import_bundle(
            module.decode_document(fixtures.to_json(fixtures.valid_bundle())), user=None)
        self.assertEqual(module.approved_content_fingerprint(), baseline)


class RetryAndConflictTestCase(_ImportStateMixin, TestCase):
    """I18 - the accepted duplicate/retry policy."""

    def test_i18_exact_retry_is_idempotent_and_creates_no_duplicate(self):
        module = require_interchange()
        text = fixtures.to_json(fixtures.valid_bundle())
        first = module.import_bundle(module.decode_document(text), user=None)
        before = self.durable_state(module)
        second = module.import_bundle(module.decode_document(text), user=None)
        self.assertEqual(self.durable_state(module), before,
                         'an exact retry must create nothing')
        self.assertTrue(second.idempotent)
        self.assertEqual(second.design_revision.pk, first.design_revision.pk)

    def test_i18_non_identical_reuse_of_an_identity_conflicts_with_zero_write(self):
        module = require_interchange()
        text = fixtures.to_json(fixtures.valid_bundle())
        module.import_bundle(module.decode_document(text), user=None)
        changed = fixtures.valid_bundle()
        changed["objects"][1]["assumptions"][0]["statement"] = "different"
        before = self.durable_state(module)
        with self.assertRaises(Exception):
            module.import_bundle(
                module.decode_document(fixtures.to_json(changed)), user=None)
        self.assert_zero_durable_writes(module, before, 'I18 identity conflict')

    def test_i18_retry_is_audited_as_an_idempotent_no_create(self):
        module = require_interchange()
        text = fixtures.to_json(fixtures.valid_bundle())
        module.import_bundle(module.decode_document(text), user=None)
        module.import_bundle(module.decode_document(text), user=None)
        self.assertEqual(module.recent_audit_records()[-1].outcome, "idempotent-no-create")
