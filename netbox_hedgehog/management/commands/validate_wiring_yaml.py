"""
Validate generated wiring YAML via hhfab (Issue #159).

This management command generates Hedgehog wiring YAML from a topology plan
and validates it using the `hhfab validate` command.

Usage:
    docker compose exec netbox python manage.py validate_wiring_yaml <plan_id>
    docker compose exec netbox python manage.py validate_wiring_yaml 1 --verbosity=2
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from netbox_hedgehog.models.topology_planning import TopologyPlan
from netbox_hedgehog.services import hhfab


class Command(BaseCommand):
    help = "Generate and validate wiring YAML for a topology plan using hhfab"

    def add_arguments(self, parser):
        parser.add_argument(
            'plan_id',
            type=int,
            help='ID of the TopologyPlan to validate'
        )
        parser.add_argument(
            '--show-yaml',
            action='store_true',
            help='Display the generated YAML content'
        )

    def handle(self, *args, **options):
        plan_id = options['plan_id']
        verbosity = options['verbosity']
        show_yaml = options.get('show_yaml', False)

        # Retrieve the plan
        try:
            plan = TopologyPlan.objects.get(pk=plan_id)
        except TopologyPlan.DoesNotExist:
            raise CommandError(f"TopologyPlan with ID {plan_id} does not exist")

        if verbosity >= 1:
            self.stdout.write(f"📋 Validating wiring YAML for plan: {plan.name} (ID: {plan.pk})")

        # Check if hhfab is available
        if not hhfab.is_hhfab_available():
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  hhfab CLI not found in PATH. Skipping validation.\n"
                    "   Install hhfab to enable wiring diagram validation."
                )
            )
            if verbosity >= 2:
                self.stdout.write("   Generating YAML for inspection only...")

            # Still generate YAML for inspection
            from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan
            try:
                yaml_content = generate_yaml_for_plan(plan)
                if show_yaml:
                    self.stdout.write("\n" + "="*80)
                    self.stdout.write("Generated YAML:")
                    self.stdout.write("="*80)
                    self.stdout.write(yaml_content)
                    self.stdout.write("="*80 + "\n")
                else:
                    self.stdout.write(f"✓ YAML generated successfully ({len(yaml_content)} bytes)")
                    self.stdout.write("  Use --show-yaml to display content")
            except ValidationError as e:
                raise CommandError(f"YAML generation failed: {str(e)}")

            return

        # Generate and validate
        if verbosity >= 2:
            self.stdout.write("🔧 Generating wiring YAML from NetBox inventory...")

        try:
            success, yaml_content, stdout, stderr = hhfab.validate_plan_yaml(plan)
        except ValidationError as e:
            raise CommandError(f"YAML generation failed: {str(e)}")
        except Exception as e:
            raise CommandError(f"Validation error: {str(e)}")

        # Display results
        if show_yaml:
            self.stdout.write("\n" + "="*80)
            self.stdout.write("Generated YAML:")
            self.stdout.write("="*80)
            self.stdout.write(yaml_content)
            self.stdout.write("="*80 + "\n")

        if verbosity >= 2:
            self.stdout.write(f"📊 YAML size: {len(yaml_content)} bytes")
            if stdout:
                self.stdout.write(f"\nhhfab stdout:\n{stdout}")

        if success:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Validation PASSED for plan {plan.pk} ({plan.name})"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Validation FAILED for plan {plan.pk} ({plan.name})"
                )
            )
            if stderr:
                self.stdout.write(self.style.ERROR(f"\nValidation errors:\n{stderr}"))

            # Exit with non-zero status for CI/CD integration
            raise CommandError("hhfab validation failed")

        if verbosity >= 1:
            self.stdout.write("✓ Validation complete")
