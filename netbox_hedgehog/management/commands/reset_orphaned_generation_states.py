"""
Management command to reset orphaned generation states.

An orphaned generation state occurs when a user deletes a background job from
the NetBox Jobs page while the TopologyPlan's GenerationState is still marked
as QUEUED or IN_PROGRESS. This leaves the plan stuck and unable to start new
generation jobs.

This command finds and resets all orphaned states to FAILED, allowing users to
start new generation jobs.

Usage:
    # Preview what will be reset (dry run)
    docker compose exec netbox python manage.py reset_orphaned_generation_states --dry-run

    # Reset all orphaned states
    docker compose exec netbox python manage.py reset_orphaned_generation_states

    # Reset orphaned state for a specific plan
    docker compose exec netbox python manage.py reset_orphaned_generation_states --plan <plan_id>

    # Skip confirmation prompt (for CI/automation)
    docker compose exec netbox python manage.py reset_orphaned_generation_states --no-input

Reference:
    - Issue #137: Orphaned job bug discovered during deployment
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from netbox_hedgehog.models.topology_planning import TopologyPlan, GenerationState
from netbox_hedgehog.choices import GenerationStatusChoices


class Command(BaseCommand):
    help = 'Reset orphaned generation states (job deleted but state still QUEUED/IN_PROGRESS)'

    def add_arguments(self, parser):
        """Add command-line arguments"""
        parser.add_argument(
            '--plan',
            type=int,
            help='Reset orphaned state for a specific plan ID only'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without making changes'
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Skip confirmation prompt'
        )

    def handle(self, *args, **options):
        """Execute command logic"""
        plan_id = options.get('plan')
        dry_run = options.get('dry_run', False)
        no_input = options.get('no_input', False)

        # Find orphaned generation states
        orphaned_states = GenerationState.objects.filter(
            job__isnull=True,
            status__in=[GenerationStatusChoices.QUEUED, GenerationStatusChoices.IN_PROGRESS]
        )

        # Filter by plan if specified
        if plan_id:
            orphaned_states = orphaned_states.filter(plan_id=plan_id)
            try:
                plan = TopologyPlan.objects.get(pk=plan_id)
                self.stdout.write(f"Filtering to plan: {plan.name} (ID: {plan_id})")
            except TopologyPlan.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Plan with ID {plan_id} does not exist"))
                return

        # Count orphaned states
        count = orphaned_states.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No orphaned generation states found."))
            return

        # Display what will be reset
        self.stdout.write(f"\nFound {count} orphaned generation state(s):")
        self.stdout.write("=" * 80)

        for state in orphaned_states:
            self.stdout.write(
                f"  Plan: {state.plan.name} (ID: {state.plan_id})\n"
                f"  Status: {state.status}\n"
                f"  Job: None (deleted)\n"
                f"  Last generated: {state.generated_at}\n"
                f"  Device count: {state.device_count}\n"
            )

        if dry_run:
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made"))
            self.stdout.write(f"Would reset {count} orphaned state(s) to FAILED status")
            return

        # Confirm with user
        if not no_input:
            self.stdout.write("\n" + "=" * 80)
            confirm = input(f"Reset {count} orphaned state(s) to FAILED? [y/N]: ")
            if confirm.lower() not in ['y', 'yes']:
                self.stdout.write(self.style.WARNING("Aborted - no changes made"))
                return

        # Reset orphaned states
        with transaction.atomic():
            updated_count = orphaned_states.update(status=GenerationStatusChoices.FAILED)

        # Report results
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully reset {updated_count} orphaned generation state(s) to FAILED"
            )
        )
        self.stdout.write("\nAffected plans can now start new generation jobs.")
