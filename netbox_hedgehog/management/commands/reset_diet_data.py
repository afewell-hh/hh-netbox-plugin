"""
Management command to reset all DIET planning data.

This command provides a comprehensive cleanup of DIET topology planning data:
1. Delete DIET planning data (TopologyPlan, PlanSwitchClass, etc.)
2. Delete generated Devices/Interfaces/Cables (tagged with 'hedgehog-generated')
3. Optionally delete seed DeviceTypes (DS5000 + 3 server types)

Use this command to:
- Start fresh with a clean NetBox install
- Verify no hidden dependencies on stale data
- Reset to baseline state for testing

IMPORTANT: This is a destructive operation. Review what will be deleted before confirming.

Usage:
    # Preview what will be deleted (dry run)
    docker compose exec netbox python manage.py reset_diet_data --dry-run

    # Reset planning data only (preserve DeviceTypes)
    docker compose exec netbox python manage.py reset_diet_data

    # Reset everything including DeviceTypes
    docker compose exec netbox python manage.py reset_diet_data --include-device-types

    # Reset a specific plan only
    docker compose exec netbox python manage.py reset_diet_data --plan <plan_id>

    # Skip confirmation prompt (for CI)
    docker compose exec netbox python manage.py reset_diet_data --no-input

Reference:
    - Issue #124: Define CI testing strategy
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from dcim.models import Manufacturer, DeviceType, InterfaceTemplate, Cable, Device, Interface
from extras.models import Tag

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    SwitchPortZone,
    GenerationState,
    DeviceTypeExtension,
)


class Command(BaseCommand):
    help = "Reset all DIET planning data (destructive operation)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--include-device-types",
            action="store_true",
            help="Also delete DIET seed DeviceTypes (DS5000 + 3 server types)",
        )
        parser.add_argument(
            "--plan",
            type=int,
            help="Reset only a specific plan by ID (scoped deletion)",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Skip confirmation prompt (use with caution!)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        include_device_types = options["include_device_types"]
        plan_id = options.get("plan")
        no_input = options["no_input"]

        # Validate plan if specified
        target_plan = None
        if plan_id:
            try:
                target_plan = TopologyPlan.objects.get(pk=plan_id)
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  DIET Data Reset - Plan '{target_plan.name}' (ID: {plan_id})\n"
                    )
                )
            except TopologyPlan.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"❌ Plan with ID {plan_id} does not exist")
                )
                return
        else:
            self.stdout.write(
                self.style.WARNING("⚠️  DIET Data Reset - Comprehensive Cleanup\n")
            )

        # Collect counts
        stats = self._collect_statistics(include_device_types, target_plan)

        # Display what will be deleted
        self._display_summary(stats, include_device_types, dry_run, target_plan)

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("\n✓ Dry run complete. No data was deleted.")
            )
            return

        # Confirm deletion
        if not no_input:
            confirm = input("\nType 'DELETE' to confirm deletion: ")
            if confirm != "DELETE":
                self.stdout.write(self.style.WARNING("Aborted. No data was deleted."))
                return

        # Perform deletion
        self.stdout.write("\n🗑️  Deleting DIET data...")

        try:
            with transaction.atomic():
                deleted_stats = self._delete_diet_data(include_device_types, target_plan)
                self._display_results(deleted_stats)

                self.stdout.write(
                    self.style.SUCCESS("\n✅ DIET data reset complete!")
                )

        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"\n❌ Error during reset: {exc}"))
            raise

    def _collect_statistics(self, include_device_types: bool, target_plan=None) -> dict:
        """Collect counts of objects that will be deleted."""
        stats = {}

        # Planning data (scoped to plan if specified)
        if target_plan:
            stats["topology_plans"] = 1  # Just the target plan
            stats["server_classes"] = PlanServerClass.objects.filter(plan=target_plan).count()
            stats["switch_classes"] = PlanSwitchClass.objects.filter(plan=target_plan).count()
            stats["server_connections"] = PlanServerConnection.objects.filter(
                server_class__plan=target_plan
            ).count()
            stats["port_zones"] = SwitchPortZone.objects.filter(
                switch_class__plan=target_plan
            ).count()
            stats["generation_states"] = GenerationState.objects.filter(plan=target_plan).count()
        else:
            stats["topology_plans"] = TopologyPlan.objects.count()
            stats["server_classes"] = PlanServerClass.objects.count()
            stats["switch_classes"] = PlanSwitchClass.objects.count()
            stats["server_connections"] = PlanServerConnection.objects.count()
            stats["port_zones"] = SwitchPortZone.objects.count()
            stats["generation_states"] = GenerationState.objects.count()

        # Generated objects (scoped by tag AND hedgehog_plan_id)
        tag = Tag.objects.filter(slug="hedgehog-generated").first()
        if tag:
            if target_plan:
                # Scope to specific plan
                stats["generated_cables"] = Cable.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id=str(target_plan.pk)
                ).count()
                stats["generated_devices"] = Device.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id=str(target_plan.pk)
                ).count()
                stats["generated_interfaces"] = Interface.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id=str(target_plan.pk)
                ).count()
            else:
                # All DIET-generated objects (those with hedgehog_plan_id set)
                stats["generated_cables"] = Cable.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id__isnull=False
                ).count()
                stats["generated_devices"] = Device.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id__isnull=False
                ).count()
                stats["generated_interfaces"] = Interface.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id__isnull=False
                ).count()
        else:
            stats["generated_cables"] = 0
            stats["generated_devices"] = 0
            stats["generated_interfaces"] = 0

        # DeviceTypes (if requested)
        if include_device_types:
            device_type_count = 0
            interface_template_count = 0
            device_type_extension_count = 0

            device_type_models = [
                ("Celestica", "DS5000"),
                ("Generic", "GPU-Server-FE"),
                ("Generic", "GPU-Server-FE-BE"),
                ("Generic", "Storage-Server-200G"),
            ]

            for manufacturer_name, model in device_type_models:
                try:
                    manufacturer = Manufacturer.objects.get(name=manufacturer_name)
                    device_type = DeviceType.objects.filter(
                        manufacturer=manufacturer, model=model
                    ).first()

                    if device_type:
                        device_type_count += 1
                        interface_template_count += InterfaceTemplate.objects.filter(
                            device_type=device_type
                        ).count()
                        device_type_extension_count += DeviceTypeExtension.objects.filter(
                            device_type=device_type
                        ).count()
                except Manufacturer.DoesNotExist:
                    continue

            stats["device_types"] = device_type_count
            stats["interface_templates"] = interface_template_count
            stats["device_type_extensions"] = device_type_extension_count

        return stats

    def _display_summary(self, stats: dict, include_device_types: bool, dry_run: bool, target_plan=None) -> None:
        """Display summary of what will be deleted."""
        if dry_run:
            self.stdout.write("📋 DRY RUN - No data will be deleted\n")

        if target_plan:
            self.stdout.write(f"The following objects will be deleted for plan '{target_plan.name}':\n")
        else:
            self.stdout.write("The following objects will be deleted:\n")

        # Planning data
        self.stdout.write("  DIET Planning Data:")
        self.stdout.write(f"    - TopologyPlans: {stats['topology_plans']}")
        self.stdout.write(f"    - PlanServerClasses: {stats['server_classes']}")
        self.stdout.write(f"    - PlanSwitchClasses: {stats['switch_classes']}")
        self.stdout.write(f"    - PlanServerConnections: {stats['server_connections']}")
        self.stdout.write(f"    - SwitchPortZones: {stats['port_zones']}")
        self.stdout.write(f"    - GenerationStates: {stats['generation_states']}")

        # Generated objects
        self.stdout.write("\n  Generated NetBox Objects:")
        self.stdout.write(f"    - Cables: {stats['generated_cables']}")
        self.stdout.write(f"    - Devices: {stats['generated_devices']}")
        self.stdout.write(f"    - Interfaces: {stats['generated_interfaces']}")

        # DeviceTypes
        if include_device_types:
            self.stdout.write("\n  DIET Seed DeviceTypes:")
            self.stdout.write(f"    - DeviceTypes: {stats.get('device_types', 0)}")
            self.stdout.write(f"    - InterfaceTemplates: {stats.get('interface_templates', 0)}")
            self.stdout.write(f"    - DeviceTypeExtensions: {stats.get('device_type_extensions', 0)}")
        else:
            self.stdout.write("\n  DIET Seed DeviceTypes:")
            self.stdout.write("    - (preserved - use --include-device-types to delete)")

        # Calculate total
        total = (
            stats["topology_plans"]
            + stats["server_classes"]
            + stats["switch_classes"]
            + stats["server_connections"]
            + stats["port_zones"]
            + stats["generation_states"]
            + stats["generated_cables"]
            + stats["generated_devices"]
            + stats["generated_interfaces"]
        )

        if include_device_types:
            total += (
                stats.get("device_types", 0)
                + stats.get("interface_templates", 0)
                + stats.get("device_type_extensions", 0)
            )

        self.stdout.write(f"\n  Total objects: {total}")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("\n✓ No DIET data found. Database is clean."))

    def _delete_diet_data(self, include_device_types: bool, target_plan=None) -> dict:
        """Delete DIET data and return statistics."""
        deleted = {}

        # Delete generated objects first (foreign key dependencies)
        # IMPORTANT: Scope by both tag AND hedgehog_plan_id to avoid deleting unrelated objects
        tag = Tag.objects.filter(slug="hedgehog-generated").first()
        if tag:
            if target_plan:
                # Scope to specific plan
                deleted["cables"] = Cable.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id=str(target_plan.pk)
                ).delete()[0]
                deleted["interfaces"] = Interface.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id=str(target_plan.pk)
                ).delete()[0]
                deleted["devices"] = Device.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id=str(target_plan.pk)
                ).delete()[0]
            else:
                # All DIET-generated objects (those with hedgehog_plan_id set)
                deleted["cables"] = Cable.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id__isnull=False
                ).delete()[0]
                deleted["interfaces"] = Interface.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id__isnull=False
                ).delete()[0]
                deleted["devices"] = Device.objects.filter(
                    tags=tag,
                    custom_field_data__hedgehog_plan_id__isnull=False
                ).delete()[0]

            self.stdout.write(f"  ✓ Deleted {deleted['cables']} cables")
            self.stdout.write(f"  ✓ Deleted {deleted['interfaces']} interfaces")
            self.stdout.write(f"  ✓ Deleted {deleted['devices']} devices")

        # Delete planning data (in dependency order, scoped to plan if specified)
        if target_plan:
            deleted["server_connections"] = PlanServerConnection.objects.filter(
                server_class__plan=target_plan
            ).delete()[0]
            deleted["port_zones"] = SwitchPortZone.objects.filter(
                switch_class__plan=target_plan
            ).delete()[0]
            deleted["switch_classes"] = PlanSwitchClass.objects.filter(
                plan=target_plan
            ).delete()[0]
            deleted["server_classes"] = PlanServerClass.objects.filter(
                plan=target_plan
            ).delete()[0]
            deleted["generation_states"] = GenerationState.objects.filter(
                plan=target_plan
            ).delete()[0]
            deleted["topology_plans"] = 1
            target_plan.delete()
        else:
            deleted["server_connections"] = PlanServerConnection.objects.all().delete()[0]
            deleted["port_zones"] = SwitchPortZone.objects.all().delete()[0]
            deleted["switch_classes"] = PlanSwitchClass.objects.all().delete()[0]
            deleted["server_classes"] = PlanServerClass.objects.all().delete()[0]
            deleted["generation_states"] = GenerationState.objects.all().delete()[0]
            deleted["topology_plans"] = TopologyPlan.objects.all().delete()[0]

        self.stdout.write(f"  ✓ Deleted {deleted['server_connections']} server connections")
        self.stdout.write(f"  ✓ Deleted {deleted['port_zones']} port zones")
        self.stdout.write(f"  ✓ Deleted {deleted['switch_classes']} switch classes")
        self.stdout.write(f"  ✓ Deleted {deleted['server_classes']} server classes")
        self.stdout.write(f"  ✓ Deleted {deleted['generation_states']} generation states")
        self.stdout.write(f"  ✓ Deleted {deleted['topology_plans']} topology plans")

        # Delete DeviceTypes if requested
        if include_device_types:
            deleted["device_types"] = 0
            deleted["interface_templates"] = 0
            deleted["device_type_extensions"] = 0

            device_type_models = [
                ("Celestica", "DS5000"),
                ("Generic", "GPU-Server-FE"),
                ("Generic", "GPU-Server-FE-BE"),
                ("Generic", "Storage-Server-200G"),
            ]

            for manufacturer_name, model in device_type_models:
                try:
                    manufacturer = Manufacturer.objects.get(name=manufacturer_name)
                    device_type = DeviceType.objects.filter(
                        manufacturer=manufacturer, model=model
                    ).first()

                    if device_type:
                        # Count before deletion
                        ext_count = DeviceTypeExtension.objects.filter(device_type=device_type).count()
                        template_count = InterfaceTemplate.objects.filter(device_type=device_type).count()

                        # Delete in order
                        DeviceTypeExtension.objects.filter(device_type=device_type).delete()
                        InterfaceTemplate.objects.filter(device_type=device_type).delete()
                        device_type.delete()

                        deleted["device_types"] += 1
                        deleted["interface_templates"] += template_count
                        deleted["device_type_extensions"] += ext_count

                        self.stdout.write(f"  ✓ Deleted {manufacturer_name} {model}")
                except Manufacturer.DoesNotExist:
                    continue

        return deleted

    def _display_results(self, deleted: dict) -> None:
        """Display deletion results."""
        total = sum(deleted.values())
        self.stdout.write(f"\n  Total objects deleted: {total}")
