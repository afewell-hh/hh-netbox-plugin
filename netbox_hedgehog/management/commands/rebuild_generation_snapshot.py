"""Management command: rebuild_generation_snapshot

Rebuilds GenerationState.snapshot for one or all plans.
Used after migration 0032 resets snapshots for plans with connections.
"""

from django.core.management.base import BaseCommand, CommandError

from netbox_hedgehog.models.topology_planning import GenerationState, TopologyPlan
from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot


class Command(BaseCommand):
    help = "Rebuild GenerationState snapshots (mark plans as needing regeneration)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--plan',
            type=int,
            dest='plan_id',
            help='Rebuild snapshot for a single plan ID only',
        )
        parser.add_argument(
            '--only-empty',
            action='store_true',
            default=False,
            help='Only rebuild plans whose snapshot is currently empty ({})',
        )

    def handle(self, *args, **options):
        plan_id = options.get('plan_id')
        only_empty = options.get('only_empty')

        if plan_id:
            try:
                states = GenerationState.objects.filter(plan_id=plan_id)
                if not states.exists():
                    raise CommandError(f"No GenerationState found for plan_id={plan_id}")
            except GenerationState.DoesNotExist:
                raise CommandError(f"No GenerationState found for plan_id={plan_id}")
        else:
            states = GenerationState.objects.all()

        if only_empty:
            states = states.filter(snapshot={})

        count = 0
        for state in states.select_related('plan'):
            state.snapshot = build_plan_snapshot(state.plan)
            state.save(update_fields=['snapshot'])
            count += 1
            self.stdout.write(f"  Rebuilt snapshot for plan: {state.plan.name}")

        self.stdout.write(self.style.SUCCESS(f"Rebuilt {count} snapshot(s)."))
