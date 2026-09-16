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
import time

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase, tag

from netbox_hedgehog.tests.corpus.interchange_model import (
    BINDING_ALGORITHM,
    content_integrity_digest,
)
from netbox_hedgehog.tests.test_interchange import fixtures, persistence
from netbox_hedgehog.tests.test_interchange._support import (
    InjectedFault,
    require_interchange,
    require_interchange_models,
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

    def write_boundary_probe(self, before, label, expect_tables=None):
        """Return a probe that PROVES a durable write occurred, then faults.

        This is the half that stops an implementation self-attesting: if nothing
        was written when the probe runs, the probe fails the test rather than
        letting the row pass.
        """
        def probe(*_args, **_kwargs):
            at_fault = persistence.snapshot()
            changed = before.diff(at_fault).get("tables", {})
            self.assertNotEqual(
                changed, {},
                f'{label}: the fault hook fired before any durable write, so this '
                f'row would prove nothing about commit-boundary atomicity. The '
                f'hook must run AFTER the first target write is visible.')
            if expect_tables is not None:
                # Stronger binding: the change must be in a NAMED target table,
                # not merely any plugin or changelog row. Left optional until the
                # target models exist; see GREEN_PHASE_BINDINGS in
                # test_row_coverage.
                self.assertTrue(
                    [t for t in changed if any(e in t for e in expect_tables)],
                    f'{label}: expected the first write in one of {expect_tables}, '
                    f'observed changes in {sorted(changed)}')
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

    def test_deadline_after_first_target_write_rolls_back_import_half(self):
        """The synchronous UI deadline applies after writes begin, not just decode."""
        module = require_interchange()
        before = persistence.snapshot()

        def cross_deadline():
            time.sleep(0.02)

        with self.assertRaises(module.OperationDeadlineExceeded):
            module.import_bundle(
                module.decode_document(fixtures.to_json(fixtures.valid_bundle())),
                user=None,
                deadline=time.monotonic() + 0.01,
                after_first_target_write=cross_deadline,
            )
        self.assert_zero_durable_writes(before, 'deadline after first target write')

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

    SIGKILL, because abrupt termination runs no cleanup: a design whose only
    cleanup is a `finally` or a context-manager exit cannot pass this row, and
    graceful cancellation therefore does not substitute for it.

    `TransactionTestCase` because the child must observe COMMITTED state.

    Two things make that workable in this repo:

    * `_fixture_teardown` is overridden to pass ``allow_cascade=True``. Django
      otherwise derives it from ``available_apps`` and a plain TRUNCATE fails
      here with "cannot truncate a table referenced in a foreign key
      constraint" (netbox_hedgehog_vpc_tags -> netbox_hedgehog_vpc). Restricting
      ``available_apps`` would also inhibit post-migrate and leave the kept
      database unseeded for later runs, so the flag is set directly instead.
    * The child is told which database to use. `django.setup()` alone would
      connect to the real lane database rather than the test one.

    Tagged slow: the flush re-runs post-migrate reference-data seeding.
    """

    #: The child must PROVE it reached the post-write boundary before killing
    #: itself. A bare `os.kill` hook would let a future implementation call
    #: after_first_target_write before any write: the child still dies by
    #: SIGKILL, the parent still sees no residue, and the row passes having
    #: tested nothing -- the exact pre-write false assurance fixed for I16a/b.
    #:
    #: If no durable write is visible, the child raises instead of killing, so
    #: it exits non-zero and the parent's required -SIGKILL status fails the row.
    CHILD = (
        "import os, signal, django;\n"
        "django.setup();\n"
        "from django.db import connection;\n"
        "connection.settings_dict['NAME'] = os.environ['HH_TEST_DB'];\n"
        "from netbox_hedgehog.tests.test_interchange import fixtures, persistence;\n"
        "from netbox_hedgehog import interchange;\n"
        "before = persistence.snapshot();\n"
        "expect = [t for t in os.environ.get('HH_EXPECT_TABLES', '').split(',') if t];\n"
        "def probe(*a, **k):\n"
        "    changed = before.diff(persistence.snapshot()).get('tables', {});\n"
        "    assert changed, (\n"
        "        'after_first_target_write fired before any durable write was '\n"
        "        'visible on the child connection; this row would prove nothing');\n"
        "    assert not expect or [t for t in changed if any(e in t for e in expect)], (\n"
        "        'expected the first write in %s, saw %s' % (expect, sorted(changed)));\n"
        "    os.kill(os.getpid(), signal.SIGKILL)\n"
        "\n"
        "interchange.import_bundle(\n"
        "    interchange.decode_document(fixtures.to_json(fixtures.valid_bundle())),\n"
        "    user=None, after_first_target_write=probe)\n"
    )

    #: Bind to the real catalog/design target tables when those models exist
    #: (see GREEN_PHASE_BINDINGS in test_row_coverage). Empty means "any durable
    #: write", which is the weaker but still pre-write-proof assertion.
    EXPECT_TABLES: tuple = ()

    def _fixture_teardown(self):
        for db_name in self._databases_names(include_mirrors=False):
            call_command(
                "flush", verbosity=0, interactive=False, database=db_name,
                reset_sequences=False, allow_cascade=True,
                inhibit_post_migrate=False,
            )

    def test_i16d_hard_process_loss_after_write_boundary_leaves_no_success(self):
        module = require_interchange()
        before = persistence.snapshot()

        completed = subprocess.run(
            [sys.executable, "-c", self.CHILD], capture_output=True,
            env={**os.environ, "HH_TEST_DB": connection.settings_dict["NAME"],
                 "HH_EXPECT_TABLES": ",".join(self.EXPECT_TABLES)},
        )
        self.assertEqual(
            completed.returncode, -signal.SIGKILL,
            f'the child must die by SIGKILL for this to be a process-loss test. '
            f'A non-SIGKILL exit means either the feature is absent or the child '
            f'reached the hook before any durable write was visible -- in which '
            f'case this row would prove nothing. '
            f'got {completed.returncode}: {completed.stderr[-500:]!r}')

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

    def _seed_approved_catalog(self, slug="approved-unrelated", version="1",
                               content=None):
        """Seed a PUBLISHED catalog unrelated to the imported bundle."""
        models = require_interchange_models()
        payload = content if content is not None else {"portCount": 64}
        return models.InterchangeCatalogVersion.objects.create(
            namespace="com.example.catalog", slug=slug, version=version,
            content=payload, content_algorithm=BINDING_ALGORITHM,
            content_digest=content_integrity_digest(payload),
            published=True, artifact_digest=content_integrity_digest(payload))

    def test_i17_approved_fingerprint_responds_to_approved_content(self):
        """Mutation control for the invariance assertion below.

        Without it, a fingerprint that ignores its inputs -- the constant
        `content_integrity_digest([])` found in review -- satisfies the
        invariance test unconditionally. Three distinct mutations are required
        to change it, so the fingerprint must cover identity, version AND the
        content binding rather than merely counting rows.
        """
        module = require_interchange()
        empty = module.approved_content_fingerprint()

        self._seed_approved_catalog()
        seeded = module.approved_content_fingerprint()
        self.assertNotEqual(
            seeded, empty,
            'the fingerprint must change when approved content is added; a '
            'constant cannot detect mutation of approved content')

        self._seed_approved_catalog(slug="approved-second")
        self.assertNotEqual(
            module.approved_content_fingerprint(), seeded,
            'the fingerprint must cover approved catalog IDENTITY')

        record = self._seed_approved_catalog(slug="approved-third")
        before_binding = module.approved_content_fingerprint()
        record.content = {"portCount": 32}
        record.content_digest = content_integrity_digest(record.content)
        record.save(update_fields=["content", "content_digest"])
        self.assertNotEqual(
            module.approved_content_fingerprint(), before_binding,
            'the fingerprint must cover the approved CONTENT BINDING')

    def test_i17_import_does_not_mutate_existing_approved_content(self):
        module = require_interchange()
        self._seed_approved_catalog()
        baseline = module.approved_content_fingerprint()
        module.import_bundle(
            module.decode_document(fixtures.to_json(fixtures.valid_bundle())), user=None)
        self.assertEqual(
            module.approved_content_fingerprint(), baseline,
            'import creates only new draft/unpublished state and must leave '
            'approved content untouched')


class RetryAndConflictTestCase(_ZeroWriteMixin, TestCase):
    """I18 - the accepted duplicate/retry policy."""

    TARGET_TABLES = (
        "netbox_hedgehog_interchangedesignrevision",
        "netbox_hedgehog_interchangecatalogversion",
        "netbox_hedgehog_interchangeprovenance",
    )
    AUDIT_TABLE = "netbox_hedgehog_interchangeaudit"

    def test_i18_exact_retry_creates_no_new_target_objects(self):
        module = require_interchange()
        text = fixtures.to_json(fixtures.valid_bundle())
        first = module.import_bundle(module.decode_document(text), user=None)
        before = persistence.snapshot()
        second = module.import_bundle(module.decode_document(text), user=None)
        changed = before.diff(persistence.snapshot()).get("tables", {})
        for table in self.TARGET_TABLES:
            with self.subTest(table=table):
                self.assertNotIn(
                    table, changed,
                    f'an exact retry must create no new {table} rows; got {changed}')
        self.assertTrue(second.idempotent)
        self.assertEqual(second.design_revision.pk, first.design_revision.pk)

    def test_i18_exact_retry_appends_one_audit_record(self):
        """Asserting only "no new rows anywhere" let a retry REWRITE the
        original audit row and still pass, which review found. The retry must
        APPEND, so the audit table must grow by exactly one."""
        module = require_interchange()
        text = fixtures.to_json(fixtures.valid_bundle())
        module.import_bundle(module.decode_document(text), user=None)
        before = persistence.snapshot()
        module.import_bundle(module.decode_document(text), user=None)
        after = persistence.snapshot()
        self.assertEqual(
            after.row_counts.get(self.AUDIT_TABLE, 0)
            - before.row_counts.get(self.AUDIT_TABLE, 0), 1,
            'an exact retry must append exactly one audit record')

    def test_i18_retry_preserves_the_original_success_record(self):
        """An audit trail that mutates prior entries is not an audit trail."""
        module = require_interchange()
        text = fixtures.to_json(fixtures.valid_bundle())
        module.import_bundle(module.decode_document(text), user=None)
        original = [record.outcome for record in module.recent_audit_records()]
        module.import_bundle(module.decode_document(text), user=None)
        after = [record.outcome for record in module.recent_audit_records()]

        self.assertEqual(
            after[:len(original)], original,
            'earlier audit records must be preserved verbatim; relabelling the '
            'original success event destroys the record that it happened')
        self.assertEqual(after[-1], "idempotent-no-create")
        self.assertNotEqual(
            original[-1], "idempotent-no-create",
            'the first import must not already be recorded as a no-create')

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

