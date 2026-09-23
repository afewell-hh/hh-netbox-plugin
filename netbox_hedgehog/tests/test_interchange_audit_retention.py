"""#689: the 30-day half of the approved InterchangeAudit failure policy.

Real-database tests. #672 approved both halves of the policy -- a minimal
non-secret failure audit, and 30-day retention of it. #684/#685 shipped the
first half on the live paste surface; #686 R2 found the second half had never
been implemented on any surface, so failure audits accumulate without bound
today.

Scope is deliberately narrow. This module proves that eligible *failure*
records expire and that everything else survives. It makes no claim about
#678 upload quarantine or reaper behaviour, and it does not touch NetBox
changelog/ObjectChange records, which #658 owns.

The command is exercised through ``call_command`` rather than by calling the
service directly, because an operational purge that works only when driven
from Python is not an operational purge.
"""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import get_resolver
from django.utils import timezone

from netbox_hedgehog.models.interchange import InterchangeAudit
from netbox_hedgehog.services import audit_retention


#: Written by ``views.interchange.audit_failure`` -- the only failure class.
ELIGIBLE_OUTCOME = "ui-import-failed"

#: Every other outcome this plugin writes to InterchangeAudit. Enumerated
#: rather than sampled: a purge that is correct for "success" but wrong for
#: "ingress-accepted" would be caught only by naming them all.
SURVIVING_OUTCOMES = (
    "ui-import",
    "ui-edit",
    "ui-delete",
    "download",
    "approve",
    "success",
    "ingress-accepted",
    "idempotent-no-create",
)


def make_audit(outcome, age_days=None, payload=None, *, seconds=0):
    """Create an audit row and force its ``created`` timestamp.

    ``created`` is ``auto_now_add``, which ignores an assigned value on
    insert, so the age is applied with a follow-up ``update()``.
    """
    record = InterchangeAudit.objects.create(
        outcome=outcome, payload=payload if payload is not None else {})
    if age_days is not None:
        stamp = timezone.now() - timedelta(days=age_days, seconds=seconds)
        InterchangeAudit.objects.filter(pk=record.pk).update(created=stamp)
    return InterchangeAudit.objects.get(pk=record.pk)


class RetentionBoundaryTestCase(TestCase):
    """Exactly-30-days semantics must be explicit, not incidental."""

    def test_older_than_the_boundary_is_purged(self):
        old = make_audit(ELIGIBLE_OUTCOME, age_days=31)
        call_command("purge_interchange_audit")
        self.assertFalse(InterchangeAudit.objects.filter(pk=old.pk).exists())

    # The two exact-boundary cases inject a reference instant instead of
    # driving the command. "Exactly 30 days old" cannot be expressed with two
    # independent timezone.now() calls: the microseconds between creating the
    # row and computing the cutoff make the record fractionally older, and the
    # test would pass or fail on scheduler jitter rather than on the rule. The
    # surrounding cases exercise the real command entrypoint at +/- a day,
    # where that drift cannot change the answer.

    def test_exactly_at_the_boundary_is_preserved(self):
        """'Older than 30 days' excludes a record that is exactly 30 days old.

        The boundary has to fall on one side deliberately. A record aged
        exactly to the cutoff is not *older* than it, so it survives; the
        first instant past that is the first eligible one.
        """
        reference = timezone.now()
        exact = InterchangeAudit.objects.create(outcome=ELIGIBLE_OUTCOME, payload={})
        InterchangeAudit.objects.filter(pk=exact.pk).update(
            created=audit_retention.retention_cutoff(reference))

        audit_retention.purge_expired_failure_audits(now=reference)

        self.assertTrue(InterchangeAudit.objects.filter(pk=exact.pk).exists())

    def test_one_microsecond_past_the_boundary_is_purged(self):
        """The first instant past the cutoff is eligible, with no dead zone."""
        reference = timezone.now()
        past = InterchangeAudit.objects.create(outcome=ELIGIBLE_OUTCOME, payload={})
        InterchangeAudit.objects.filter(pk=past.pk).update(
            created=audit_retention.retention_cutoff(reference) - timedelta(microseconds=1))

        audit_retention.purge_expired_failure_audits(now=reference)

        self.assertFalse(InterchangeAudit.objects.filter(pk=past.pk).exists())

    def test_just_under_the_boundary_is_preserved(self):
        recent = make_audit(ELIGIBLE_OUTCOME, age_days=29)
        call_command("purge_interchange_audit")
        self.assertTrue(InterchangeAudit.objects.filter(pk=recent.pk).exists())

    def test_cutoff_is_timezone_aware_and_derived_from_the_policy(self):
        cutoff = audit_retention.retention_cutoff()
        self.assertIsNotNone(cutoff.tzinfo)
        self.assertEqual(audit_retention.RETENTION_DAYS, 30)
        self.assertAlmostEqual(
            (timezone.now() - cutoff).total_seconds(),
            timedelta(days=30).total_seconds(),
            delta=60,
        )


class EligibilityScopeTestCase(TestCase):
    """Only the failure class expires. Everything else is out of policy."""

    def test_every_other_outcome_survives_even_when_ancient(self):
        kept = {outcome: make_audit(outcome, age_days=400)
                for outcome in SURVIVING_OUTCOMES}
        call_command("purge_interchange_audit")
        for outcome, record in kept.items():
            with self.subTest(outcome=outcome):
                self.assertTrue(
                    InterchangeAudit.objects.filter(pk=record.pk).exists(),
                    f"{outcome!r} is not a failure record and is outside the "
                    f"approved 30-day policy; purging it would delete history "
                    f"no decision authorized removing",
                )

    def test_declared_eligible_set_is_exactly_the_failure_outcome(self):
        self.assertEqual(audit_retention.ELIGIBLE_OUTCOMES, frozenset({ELIGIBLE_OUTCOME}))

    def test_mixed_population_loses_only_expired_failures(self):
        expired = make_audit(ELIGIBLE_OUTCOME, age_days=45)
        recent_failure = make_audit(ELIGIBLE_OUTCOME, age_days=2)
        old_success = make_audit("success", age_days=45)
        call_command("purge_interchange_audit")
        self.assertFalse(InterchangeAudit.objects.filter(pk=expired.pk).exists())
        self.assertTrue(InterchangeAudit.objects.filter(pk=recent_failure.pk).exists())
        self.assertTrue(InterchangeAudit.objects.filter(pk=old_success.pk).exists())

    def test_survivor_payloads_are_untouched(self):
        """A purge deletes rows; it must not rewrite the ones it keeps."""
        payload = {"actor": 7, "stage": "validation", "request_id": "a" * 32}
        survivor = make_audit(ELIGIBLE_OUTCOME, age_days=1, payload=payload)
        make_audit(ELIGIBLE_OUTCOME, age_days=90)
        call_command("purge_interchange_audit")
        survivor.refresh_from_db()
        self.assertEqual(survivor.payload, payload)
        self.assertEqual(survivor.outcome, ELIGIBLE_OUTCOME)

    def test_queryset_is_filtered_not_broad(self):
        """Guard the shape of the delete, not only its outcome.

        A correct-looking result can still come from a dangerous query. The
        eligible queryset must constrain both outcome and age, so that a
        future edit dropping either filter fails here rather than in
        production.
        """
        query = str(audit_retention.eligible_queryset().query)
        self.assertIn("outcome", query)
        self.assertIn("created", query)


class IdempotenceAndEmptyStateTestCase(TestCase):
    """Scheduled invocation means running against nothing is the normal case."""

    def test_second_run_deletes_nothing_and_does_not_fail(self):
        make_audit(ELIGIBLE_OUTCOME, age_days=60)
        survivor = make_audit(ELIGIBLE_OUTCOME, age_days=1)

        first = audit_retention.purge_expired_failure_audits()
        second = audit_retention.purge_expired_failure_audits()

        self.assertEqual(first["deleted"], 1)
        self.assertEqual(second["deleted"], 0)
        self.assertTrue(InterchangeAudit.objects.filter(pk=survivor.pk).exists())

    def test_runs_cleanly_against_an_empty_table(self):
        out = StringIO()
        call_command("purge_interchange_audit", stdout=out)
        self.assertEqual(InterchangeAudit.objects.count(), 0)
        self.assertIn("0", out.getvalue())


class DryRunTestCase(TestCase):
    """An operator must be able to see the scope before taking it."""

    def test_dry_run_reports_without_deleting(self):
        expired = make_audit(ELIGIBLE_OUTCOME, age_days=60)
        out = StringIO()
        call_command("purge_interchange_audit", "--dry-run", stdout=out)
        self.assertTrue(InterchangeAudit.objects.filter(pk=expired.pk).exists())
        self.assertIn("1", out.getvalue())

    def test_dry_run_then_real_run_deletes_the_same_records(self):
        expired = make_audit(ELIGIBLE_OUTCOME, age_days=60)
        call_command("purge_interchange_audit", "--dry-run")
        call_command("purge_interchange_audit")
        self.assertFalse(InterchangeAudit.objects.filter(pk=expired.pk).exists())


class ObservabilityTestCase(TestCase):
    """Operational evidence, with nothing sensitive in it.

    Two sentinels, deliberately. A purge can leak the content it *deletes*
    (logging what it removed) or the content it *keeps* (logging the table
    afterwards). A fixture carrying only the first would pass against an
    implementation that dumps every surviving payload on each run, so both
    populations are present in every case below.
    """

    SENTINEL = "RETENTION_SENTINEL_MUST_NOT_BE_LOGGED"
    SURVIVOR_SENTINEL = "SURVIVOR_SENTINEL_MUST_NOT_BE_LOGGED"

    def seed(self):
        """One expiring record and one retained record, each sentinel-bearing."""
        make_audit(ELIGIBLE_OUTCOME, age_days=60,
                   payload={"stage": "validation", "leak": self.SENTINEL})
        make_audit(ELIGIBLE_OUTCOME, age_days=1,
                   payload={"stage": "validation", "leak": self.SURVIVOR_SENTINEL})

    def assert_no_sentinels(self, blob):
        self.assertNotIn(self.SENTINEL, blob)
        self.assertNotIn(self.SURVIVOR_SENTINEL, blob)

    def test_result_is_aggregate_and_carries_no_record_content(self):
        self.seed()
        result = audit_retention.purge_expired_failure_audits()
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["retention_days"], 30)
        self.assert_no_sentinels(str(result))

    def test_log_record_is_aggregate_and_leaks_no_payload(self):
        self.seed()
        with self.assertLogs("netbox_hedgehog.audit_retention", level="INFO") as captured:
            audit_retention.purge_expired_failure_audits()
        blob = "\n".join(captured.output)
        self.assert_no_sentinels(blob)
        self.assertIn("1", blob)

    def test_dry_run_log_leaks_no_payload_either(self):
        """The dry run reads the eligible rows; it must not report them."""
        self.seed()
        with self.assertLogs("netbox_hedgehog.audit_retention", level="INFO") as captured:
            audit_retention.purge_expired_failure_audits(dry_run=True)
        self.assert_no_sentinels("\n".join(captured.output))

    def test_command_output_leaks_no_payload(self):
        self.seed()
        out, err = StringIO(), StringIO()
        call_command("purge_interchange_audit", stdout=out, stderr=err)
        self.assert_no_sentinels(out.getvalue() + err.getvalue())

    def test_purge_does_not_write_a_new_unbounded_audit_class(self):
        """The purge must not log its own run into the table it purges.

        A per-run row would be a non-eligible outcome, so nothing would ever
        remove it -- the retention fix would create a second unbounded class.
        Evidence belongs in the log and the command's output.
        """
        make_audit(ELIGIBLE_OUTCOME, age_days=60)
        call_command("purge_interchange_audit")
        self.assertEqual(InterchangeAudit.objects.count(), 0)


class OperationalSurfaceTestCase(TestCase):
    """Purge is an operator action, reachable only through the command."""

    def test_no_url_route_can_trigger_a_purge(self):
        patterns = str(get_resolver().url_patterns)
        for token in ("purge", "retention"):
            with self.subTest(token=token):
                self.assertNotIn(f"interchange_{token}", patterns)

    def test_command_is_registered_and_self_describing(self):
        """Assert the declared surface, not --help output.

        argparse's --help raises SystemExit and writes to the process stdout,
        not the stream call_command is given, so scraping it proves little.
        The command class and its parser are the real contract.
        """
        from django.core.management import get_commands, load_command_class

        self.assertEqual(get_commands()["purge_interchange_audit"], "netbox_hedgehog")
        command = load_command_class("netbox_hedgehog", "purge_interchange_audit")
        self.assertIn(str(audit_retention.RETENTION_DAYS), command.help)

        options = {action.dest for action in command.create_parser("", "x")._actions}
        self.assertIn("dry_run", options)
        self.assertNotIn("days", options)

    def test_retention_window_is_not_operator_tunable(self):
        """The policy value is fixed at the approved 30 days.

        A ``--days`` switch would let an operator widen the delete past what
        #672 authorized, which the issue explicitly forbids without a new
        decision. Absence of that option is part of the contract.
        """
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as caught:
            call_command("purge_interchange_audit", "--days", "1", stderr=StringIO())
        self.assertIn("unrecognized arguments", str(caught.exception))
