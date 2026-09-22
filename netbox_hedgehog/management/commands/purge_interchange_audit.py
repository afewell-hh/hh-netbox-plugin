"""Enforce the approved 30-day InterchangeAudit failure retention (#689).

Usage:
    # Preview the scope without deleting anything
    docker compose exec netbox python manage.py purge_interchange_audit --dry-run

    # Apply the policy
    docker compose exec netbox python manage.py purge_interchange_audit

Scheduling is deliberately not wired up here. NetBox offers a system-job
registration that would run this on an interval, but choosing a cadence and
an execution identity is an operator/lead decision, and #689 is explicit that
an unreviewed scheduler must not be assumed. The command is idempotent and
safe to invoke from whatever scheduler the deployment already trusts.

Reference: #672 (policy), #686 R2 (the gap), #689 (this work).
"""

from django.core.management.base import BaseCommand

from netbox_hedgehog.services import audit_retention


class Command(BaseCommand):
    help = (
        "Delete interchange failure audit records older than the approved "
        f"{audit_retention.RETENTION_DAYS}-day retention window. Success and "
        "lifecycle audit records, other models, and the NetBox changelog are "
        "never touched. The window is fixed by policy and has no override."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report how many records are eligible without deleting them.",
        )

    def handle(self, *args, **options):
        result = audit_retention.purge_expired_failure_audits(
            dry_run=options["dry_run"])

        if result["dry_run"]:
            self.stdout.write(
                f"{result['eligible']} interchange failure audit record(s) are "
                f"eligible for deletion (older than {result['retention_days']} "
                f"days, cutoff {result['cutoff']}). No records were deleted."
            )
            return

        self.stdout.write(self.style.SUCCESS(
            f"Deleted {result['deleted']} interchange failure audit record(s) "
            f"older than {result['retention_days']} days "
            f"(cutoff {result['cutoff']})."
        ))
