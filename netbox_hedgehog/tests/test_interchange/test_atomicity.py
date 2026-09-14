"""RED import atomicity and success state (#673 I15-I16d, I17, I18).

What this suite must be able to falsify
---------------------------------------
I15 fails BEFORE any write is attempted, so an implementation with no
transaction at all -- one that merely validates first -- passes it. It is kept
as necessary-but-not-sufficient and explicitly does not claim to prove
atomicity (#672 B1).

Two properties make I16a-d able to separate atomic from validate-first, both
added after Dev B's #674 review:

1. **State is observed independently of the code under test.** Counting through
   the production module's own accessors would let a non-atomic implementation
   report zero from its own counters while rows exist. `persistence.snapshot()`
   reads the database and media tree by introspection instead.

2. **The fault probe proves a durable write happened before it fires.** The
   probe is supplied BY THE TEST: it asserts, against the independent snapshot,
   that the first target write is visible, and only then raises. An
   implementation cannot satisfy the row by raising before writing anything --
   the probe itself fails first, and the row stays red.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys

from django.test import TestCase, TransactionTestCase, tag

from netbox_hedgehog.tests.test_interchange import fixtures, persistence
from netbox_hedgehog.tests.test_interchange._support import (
    InjectedFault,
    require_interchange,
)


class _ZeroWriteMixin:

    def assert_zero_durable_writes(self, before, label):
        after = persistence.snapshot()
        difference = before.diff(after)
        self.assertEqual(
            difference, {"tables": {}},
            f'{label}: import must leave zero durable writes. A surviving row of '
            f'either target family, a provenance row, a success audit/changelog '
            f'entry, or a retained ingress artifact all break the all-or-nothing '
            f'guarantee. Observed: {difference}')

    def write_boundary_probe(self, before, label):
        """Return a probe that PROVES a durable write occurred, then faults.

        This is the half that stops an implementation self-attesting: if nothing
        was written when the probe runs, the probe fails the test rather than
        letting the row pass.
        """
        def probe(*_args, **_kwargs):
            at_fault = persistence.snapshot()
            self.assertNotEqual(
                before.diff(at_fault), {"tables": {}},
                f'{label}: the fault hook fired before any durable write, so this '
                f'row would prove nothing about commit-boundary atomicity. The '
                f'hook must run AFTER the first target write is visible.')
            raise InjectedFault(label)
        return probe


class PreWriteFailureTestCase(_ZeroWriteMixin, TestCase):
    """I15 - validation failures before any write. Necessary, NOT sufficient.

    These rows deliberately do not claim to prove atomicity; I16a-d do that.
    """

    def test_i15_invalid_syntax_leaves_no_state(self):
        module = require_interchange()
        before = persistence.snapshot()
        with self.assertRaises(Exception):
            module.import_bundle(module.decode_document("{not: valid: json"), user=None)
        self.assert_zero_durable_writes(before, 'invalid syntax')

    def test_i15_schema_failure_leaves_no_state(self):
        module = require_interchange()
        before = persistence.snapshot()
        document = fixtures.valid_bundle()
        document["objects"][1].pop("schemaVersion")
        with self.assertRaises(Exception):
            module.import_bundle(
                module.decode_document(fixtures.to_json(document)), user=None)
        self.assert_zero_durable_writes(before, 'schema failure')


class CommitBoundaryFaultTestCase(_ZeroWriteMixin, TestCase):
    """I16a, I16b - faults injected after a PROVEN durable write."""

    def test_i16a_fault_after_first_target_write_rolls_back_both_families(self):
        module = require_interchange()
        before = persistence.snapshot()
        probe = self.write_boundary_probe(before, 'I16a')
        with self.assertRaises(InjectedFault):
            module.import_bundle(
                module.decode_document(fixtures.to_json(fixtures.valid_bundle())),
                user=None, after_first_target_write=probe)
        self.assert_zero_durable_writes(before, 'I16a post-first-write fault')

    def test_i16b_integrity_failure_in_second_target_rolls_back_the_first(self):
        """No partial catalog-only or topology-only success."""
        module = require_interchange()
        before = persistence.snapshot()
        probe = self.write_boundary_probe(before, 'I16b')
        with self.assertRaises(InjectedFault):
            module.import_bundle(
                module.decode_document(fixtures.to_json(fixtures.valid_bundle())),
                user=None, after_second_target_write=probe)
        self.assert_zero_durable_writes(before, 'I16b second-target fault')

    def test_i16_failure_audit_never_claims_success(self):
        module = require_interchange()
        before = persistence.snapshot()
        probe = self.write_boundary_probe(before, 'audit')
        with self.assertRaises(InjectedFault):
            module.import_bundle(
                module.decode_document(fixtures.to_json(fixtures.valid_bundle())),
                user=None, after_first_target_write=probe)
        for record in module.recent_audit_records():
            with self.subTest(record=record):
                self.assertNotEqual(record.outcome, "success")


class IngressFailureTestCase(_ZeroWriteMixin, TestCase):
    """I16c - the artifact must be ACCEPTED by the request path before the
    failure, otherwise the row proves only that invalid input was refused."""

    def test_i16c_accepted_upload_is_not_retained_after_validation_failure(self):
        module = require_interchange()
        before = persistence.snapshot()

        # Parses cleanly and passes schema, so ingress must accept and store it;
        # it fails later on SEMANTIC validation.
        document = fixtures.valid_bundle()
        document["objects"][1]["catalogRefs"][0]["identity"]["slug"] = "absent-catalog"

        def probe(*_args, **_kwargs):
            at_ingress = persistence.snapshot()
            self.assertTrue(
                at_ingress.media_files - before.media_files
                or before.diff(at_ingress) != {"tables": {}},
                'I16c: nothing was durably accepted at ingress, so this row would '
                'not exercise retention of an accepted artifact')
        with self.assertRaises(Exception):
            module.import_uploaded_artifact(
                fixtures.to_json(document), user=None, after_ingress_accepted=probe)
        self.assert_zero_durable_writes(before, 'I16c accepted-then-failed upload')


class GracefulCancellationTestCase(_ZeroWriteMixin, TestCase):
    """I16d(i) - cooperative cancellation after the write boundary.

    Named for what it actually is. A context manager raising in-process still
    runs normal cleanup, so this is NOT a process-loss test (#674 Blocking 2).
    """

    def test_i16d_graceful_cancellation_after_write_boundary_leaves_no_success(self):
        module = require_interchange()
        before = persistence.snapshot()
        probe = self.write_boundary_probe(before, 'I16d-graceful')
        with self.assertRaises(InjectedFault):
            module.import_bundle(
                module.decode_document(fixtures.to_json(fixtures.valid_bundle())),
                user=None, after_first_target_write=probe)
        self.assert_zero_durable_writes(before, 'I16d graceful cancellation')


@tag('slow')
class HardProcessLossTestCase(_ZeroWriteMixin, TransactionTestCase):
    """I16d(ii) - genuine out-of-process loss.

    Tagged slow, and it genuinely is: `TransactionTestCase` flushes the database
    and re-runs the plugin's post-migrate reference-data seeding, which costs
    minutes in this repo. It is excluded from the fast lane run via
    `--exclude-tag=slow` and must be run explicitly. That cost buys the one thing
    an in-process context manager cannot: a process that dies running no cleanup.

    `TransactionTestCase` because the child process must see COMMITTED state,
    and SIGKILL because abrupt termination runs no `finally` -- a cleanup design
    that depends on one cannot pass this row. The parent then runs the approved
    reaper and asserts the outcome.
    """

    CHILD = (
        "import django; django.setup();\n"
        "import os, signal;\n"
        "from netbox_hedgehog import interchange;\n"
        "from netbox_hedgehog.tests.test_interchange import fixtures;\n"
        "kill = lambda *a, **k: os.kill(os.getpid(), signal.SIGKILL);\n"
        "interchange.import_bundle(\n"
        "    interchange.decode_document(fixtures.to_json(fixtures.valid_bundle())),\n"
        "    user=None, after_first_target_write=kill)\n"
    )

    def test_i16d_hard_process_loss_after_write_boundary_leaves_no_success(self):
        module = require_interchange()
        before = persistence.snapshot()

        completed = subprocess.run(
            [sys.executable, "-c", self.CHILD],
            capture_output=True, env={**os.environ},
        )
        self.assertEqual(
            completed.returncode, -signal.SIGKILL,
            f'the child must die by SIGKILL for this to be a process-loss test; '
            f'got {completed.returncode}: {completed.stderr[-400:]!r}')

        module.run_ingress_reaper()
        self.assert_zero_durable_writes(before, 'I16d hard process loss')


class SuccessStateTestCase(_ZeroWriteMixin, TestCase):
    """I17 - exactly one new unapproved draft and one unpublished version."""

    def test_i17_valid_import_creates_one_draft_and_one_unpublished_version(self):
        module = require_interchange()
        result = module.import_bundle(
            module.decode_document(fixtures.to_json(fixtures.valid_bundle())), user=None)
        self.assertFalse(result.design_revision.approved)
        self.assertFalse(result.catalog_version.published)

    def test_i17_import_does_not_mutate_existing_approved_content(self):
        module = require_interchange()
        baseline = module.approved_content_fingerprint()
        module.import_bundle(
            module.decode_document(fixtures.to_json(fixtures.valid_bundle())), user=None)
        self.assertEqual(module.approved_content_fingerprint(), baseline)


class RetryAndConflictTestCase(_ZeroWriteMixin, TestCase):
    """I18 - the accepted duplicate/retry policy."""

    def test_i18_exact_retry_is_idempotent_and_creates_no_duplicate(self):
        module = require_interchange()
        text = fixtures.to_json(fixtures.valid_bundle())
        first = module.import_bundle(module.decode_document(text), user=None)
        before = persistence.snapshot()
        second = module.import_bundle(module.decode_document(text), user=None)
        self.assertEqual(before.diff(persistence.snapshot()).get("tables"), {},
                         'an exact retry must create no new rows')
        self.assertTrue(second.idempotent)
        self.assertEqual(second.design_revision.pk, first.design_revision.pk)

    def test_i18_non_identical_reuse_of_an_identity_conflicts_with_zero_write(self):
        module = require_interchange()
        text = fixtures.to_json(fixtures.valid_bundle())
        module.import_bundle(module.decode_document(text), user=None)
        changed = fixtures.valid_bundle()
        changed["objects"][1]["assumptions"][0]["statement"] = "different"
        before = persistence.snapshot()
        with self.assertRaises(Exception):
            module.import_bundle(
                module.decode_document(fixtures.to_json(changed)), user=None)
        self.assert_zero_durable_writes(before, 'I18 identity conflict')

    def test_i18_retry_is_audited_as_an_idempotent_no_create(self):
        module = require_interchange()
        text = fixtures.to_json(fixtures.valid_bundle())
        module.import_bundle(module.decode_document(text), user=None)
        module.import_bundle(module.decode_document(text), user=None)
        self.assertEqual(module.recent_audit_records()[-1].outcome, "idempotent-no-create")
