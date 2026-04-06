"""
Management command to generate NetBox devices/interfaces/cables from a TopologyPlan.

This command uses the DeviceGenerator service to create NetBox objects
based on the topology plan's server and switch class definitions.

Usage:
    # Preview what would be generated (dry run)
    docker compose exec netbox python manage.py generate_devices <plan_id> --preview

    # Actually generate devices
    docker compose exec netbox python manage.py generate_devices <plan_id>

    # Generate with specific site
    docker compose exec netbox python manage.py generate_devices <plan_id> --site tus1

    # Preview with specific site
    docker compose exec netbox python manage.py generate_devices <plan_id> --site tus1 --preview

Reference:
    - Issue #107 (DIET-011): Scale Generation Engine
    - Week 2: Generation Engine - Management command for CLI testing
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dcim.choices import SiteStatusChoices
from dcim.models import Site

from netbox_hedgehog.models.topology_planning import TopologyPlan
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.utils.topology_calculations import update_plan_calculations


class Command(BaseCommand):
    help = 'Generate NetBox devices, interfaces, and cables from a TopologyPlan'

    def add_arguments(self, parser):
        """Add command-line arguments"""
        parser.add_argument(
            'plan_id',
            type=int,
            help='ID of the TopologyPlan to generate from'
        )

        parser.add_argument(
            '--preview',
            action='store_true',
            help='Preview generation without creating objects (dry run)'
        )

        parser.add_argument(
            '--site',
            type=str,
            help='Site slug for generated devices (default: creates "hedgehog" site)'
        )

    def handle(self, *args, **options):
        """Execute the command"""
        plan_id = options['plan_id']
        preview = options['preview']
        site_slug = options.get('site')

        # Fetch the plan
        try:
            plan = TopologyPlan.objects.get(pk=plan_id)
        except TopologyPlan.DoesNotExist:
            raise CommandError(f'TopologyPlan with ID {plan_id} does not exist')

        # Get or create site if specified
        site = None
        if site_slug:
            site, created = Site.objects.get_or_create(
                slug=site_slug,
                defaults={
                    'name': site_slug.replace('-', ' ').title(),
                    'status': SiteStatusChoices.STATUS_ACTIVE,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Created site: {site.name} ({site_slug})'))

        # Display plan info
        self.stdout.write(self.style.WARNING(f'\nTopology Plan: {plan.name}'))
        self.stdout.write(f'  ID: {plan.pk}')
        self.stdout.write(f'  Status: {plan.status}')
        self.stdout.write(f'  Server Classes: {plan.server_classes.count()}')
        self.stdout.write(f'  Switch Classes: {plan.switch_classes.count()}')

        # Mirror the web generate/update flow: calculate switch quantities first.
        calc_result = update_plan_calculations(plan)
        if calc_result['errors']:
            first_error = calc_result['errors'][0]
            switch_class_id = (
                first_error.get('switch_class_id')
                or first_error.get('switch_class')
                or 'unknown'
            )
            message = first_error.get('message') or first_error.get('error') or 'Unknown error'
            raise CommandError(
                f"Calculation failed for switch class '{switch_class_id}': {message}"
            )

        self.stdout.write(self.style.SUCCESS('\n✓ Recalculated switch quantities'))
        for switch_class_id, summary in calc_result['summary'].items():
            self.stdout.write(
                f"  - {switch_class_id}: calculated={summary['calculated']} "
                f"override={summary['override']} effective={summary['effective']}"
            )

        # Check if plan has already been generated
        if hasattr(plan, 'generation_state') and not preview:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  Plan was previously generated at {plan.last_generated_at}'
            ))
            if plan.needs_regeneration:
                self.stdout.write(self.style.WARNING(
                    '⚠️  Plan has been modified since last generation'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    '⚠️  Plan has NOT been modified since last generation'
                ))
            self.stdout.write(self.style.WARNING(
                '⚠️  Generation will DELETE existing generated objects and recreate them\n'
            ))

        # Initialize generator
        generator = DeviceGenerator(
            plan=plan,
            site=site
        )

        if preview:
            # Preview mode - show what would be generated
            self.preview_generation(generator, plan, site)
        else:
            # Actually generate
            self.perform_generation(generator, plan, site)

    def preview_generation(self, generator, plan, site):
        """Show what would be generated without creating objects"""
        self.stdout.write(self.style.WARNING('\n=== PREVIEW MODE (Dry Run) ===\n'))

        # Calculate counts
        server_count = sum(sc.quantity for sc in plan.server_classes.all())
        switch_count = sum(sc.effective_quantity for sc in plan.switch_classes.all())
        total_devices = server_count + switch_count

        self.stdout.write(self.style.SUCCESS('Would generate:'))
        self.stdout.write(f'  Devices: {total_devices}')
        self.stdout.write(f'    - Servers: {server_count}')
        self.stdout.write(f'    - Switches: {switch_count}')

        # Show server classes
        if plan.server_classes.exists():
            self.stdout.write('\n  Server Classes:')
            for sc in plan.server_classes.all():
                self.stdout.write(f'    - {sc.server_class_id}: {sc.quantity}x')

        # Show switch classes
        if plan.switch_classes.exists():
            self.stdout.write('\n  Switch Classes:')
            for sc in plan.switch_classes.all():
                self.stdout.write(
                    f'    - {sc.switch_class_id}: {sc.effective_quantity}x'
                )

        # Show site
        site_name = site.name if site else DeviceGenerator.DEFAULT_SITE_NAME
        self.stdout.write(f'\n  Site: {site_name}')
        self.stdout.write(f'  Status: planned')

        self.stdout.write(self.style.WARNING(
            '\n💡 Run without --preview to actually generate these objects\n'
        ))

    @transaction.atomic
    def perform_generation(self, generator, plan, site):
        """Actually perform the generation"""
        self.stdout.write(self.style.WARNING('\n=== GENERATING OBJECTS ===\n'))

        from netbox_hedgehog.services.preflight import (
            check_transceiver_bay_readiness,
            cli_message,
        )
        readiness = check_transceiver_bay_readiness(plan)
        if not readiness.is_ready:
            self.stdout.write(self.style.ERROR(cli_message(readiness)))
            raise CommandError(
                "Generation blocked: transceiver bays missing. "
                "Run populate_transceiver_bays and retry."
            )

        try:
            # Generate all objects
            result = generator.generate_all()

            # Re-read generation state to get the status the generator set (#345).
            plan.refresh_from_db()
            gs = plan.generation_state
            if gs.status == 'failed':
                report = gs.mismatch_report or {}
                if report.get('bay_errors'):
                    detail = "Transceiver bay placement failed during generation. Check the mismatch report."
                else:
                    detail = "Transceiver compatibility mismatches found. Check mismatch_report."
                self.stdout.write(self.style.ERROR(f'\n✗ Generation failed: {detail}'))
                raise CommandError(f'Generation failed: {detail}')

            # Display results
            self.stdout.write(self.style.SUCCESS('\n✓ Generation complete!'))
            self.stdout.write(self.style.SUCCESS(f'\nCreated:'))
            self.stdout.write(f'  Devices: {result.device_count}')
            self.stdout.write(f'  Interfaces: {result.interface_count}')
            self.stdout.write(f'  Cables: {result.cable_count}')

            # Show site
            site_name = site.name if site else DeviceGenerator.DEFAULT_SITE_NAME
            self.stdout.write(f'\n  Site: {site_name}')
            self.stdout.write(f'  Status: planned')

            # Show tags and filtering info
            self.stdout.write(f'\n  Tagged with: hedgehog-generated')
            self.stdout.write(f'  Custom field: hedgehog_plan_id={plan.pk}')

            # Show next steps
            self.stdout.write(self.style.SUCCESS('\n💡 Next steps:'))
            self.stdout.write('  - View devices in NetBox UI')
            self.stdout.write('  - Filter by tag: hedgehog-generated')
            self.stdout.write(f'  - Or custom field: hedgehog_plan_id={plan.pk}')
            self.stdout.write('  - Check cable connections')

        except CommandError:
            raise
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Generation failed: {str(e)}'))
            raise CommandError(f'Generation failed: {str(e)}')
