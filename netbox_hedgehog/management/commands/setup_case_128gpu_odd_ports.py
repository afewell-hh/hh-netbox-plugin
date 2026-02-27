"""
Create the 128-GPU odd-port breakout topology test case.

Usage:
    docker compose exec netbox python manage.py setup_case_128gpu_odd_ports
    docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --clean
    docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --generate
    docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --generate --report
    docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --generate --report --cleanup-after
"""

from django.core.management.base import BaseCommand
from django.db import transaction, models
from django.core.exceptions import ValidationError

from dcim.models import Cable, Device, Interface
from extras.models import Tag

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    SwitchPortZone,
    GenerationState,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.utils.topology_calculations import update_plan_calculations


PLAN_NAME = "UX Case 128GPU Odd Ports"


class Command(BaseCommand):
    help = "Create the 128-GPU odd-port breakout topology test case"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Remove existing case data before creating new data",
        )
        parser.add_argument(
            "--generate",
            action="store_true",
            help="Generate devices/interfaces/cables after creating the plan",
        )
        parser.add_argument(
            "--report",
            action="store_true",
            help="Display detailed report of plan and generated objects (implies no cleanup)",
        )
        parser.add_argument(
            "--cleanup-after",
            action="store_true",
            help="Remove all data after reporting (only with --report)",
        )

    def handle(self, *args, **options):
        if options["cleanup_after"] and not options["report"]:
            raise ValidationError("--cleanup-after requires --report")

        # Check if plan already exists
        existing_plan = TopologyPlan.objects.filter(name=PLAN_NAME).first()

        if options["clean"] and existing_plan:
            self.stdout.write("🧹 Cleaning up existing case data...")
            self._cleanup_case_data()
            existing_plan = None
        elif existing_plan:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  Plan '{PLAN_NAME}' already exists (ID: {existing_plan.pk}). "
                    "Use --clean to recreate."
                )
            )
            if not options["generate"]:
                return
            # If --generate is specified, continue to generation step below

        if not existing_plan:
            self.stdout.write("📦 Creating 128-GPU odd-port breakout case...")

        try:
            with transaction.atomic():
                if existing_plan:
                    plan = existing_plan
                else:
                    plan = self._create_case_data()
                    result = update_plan_calculations(plan)

                    # Check for calculation errors - test cases must be perfect
                    if result['errors']:
                        self.stdout.write(self.style.ERROR("❌ Calculation errors detected:"))
                        for error_info in result['errors']:
                            self.stdout.write(
                                f"  - {error_info['switch_class']}: {error_info['error']}"
                            )
                        raise ValidationError(
                            "Test case has calculation errors. Fix the plan configuration."
                        )

                    self.stdout.write(self.style.SUCCESS("✅ Case created successfully."))
                    self.stdout.write(f"  Plan: {plan.name} (ID: {plan.pk})")
                    self.stdout.write(f"  Calculated {len(result['summary'])} switch classes")

                if options["generate"]:
                    self.stdout.write("⚙️  Generating devices for case...")
                    result = DeviceGenerator(plan).generate_all()
                    self.stdout.write(
                        self.style.SUCCESS(
                            "✅ Generation complete: "
                            f"{result.device_count} devices, "
                            f"{result.interface_count} interfaces, "
                            f"{result.cable_count} cables."
                        )
                    )

                # Generate detailed report if requested
                if options["report"]:
                    self._display_report(plan)

                    # Optionally cleanup after reporting
                    if options["cleanup_after"]:
                        self.stdout.write("\n🧹 Cleaning up after report...")
                        self._cleanup_case_data()
                        self.stdout.write(self.style.SUCCESS("✅ Cleanup complete."))
                    else:
                        self.stdout.write(
                            f"\n💡 Tip: Data remains in database. Clean up with:"
                        )
                        self.stdout.write(
                            f"  docker compose exec netbox python manage.py reset_diet_data --plan {plan.pk}"
                        )

        except ValidationError as exc:
            self.stdout.write(self.style.ERROR(f"❌ Validation error: {exc}"))
            raise
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"❌ Error creating case: {exc}"))
            raise

    def _cleanup_case_data(self) -> None:
        plan = TopologyPlan.objects.filter(name=PLAN_NAME).first()
        if not plan:
            return

        tag = Tag.objects.filter(slug=DeviceGenerator.DEFAULT_TAG_SLUG).first()
        if tag:
            # Delete generated objects (can be slow if many objects exist)
            cable_filter = Cable.objects.filter(
                tags=tag,
                custom_field_data__hedgehog_plan_id=str(plan.pk),
            )
            cable_count = cable_filter.count()
            if cable_count > 0:
                self.stdout.write(f"  Deleting {cable_count} cables...")
                cable_filter.delete()

            device_filter = Device.objects.filter(
                tags=tag,
                custom_field_data__hedgehog_plan_id=str(plan.pk),
            )
            device_count = device_filter.count()
            if device_count > 0:
                self.stdout.write(f"  Deleting {device_count} devices...")
                device_filter.delete()

            interface_filter = Interface.objects.filter(
                tags=tag,
                custom_field_data__hedgehog_plan_id=str(plan.pk),
            )
            interface_count = interface_filter.count()
            if interface_count > 0:
                self.stdout.write(f"  Deleting {interface_count} interfaces...")
                interface_filter.delete()

        # Delete plan metadata
        self.stdout.write("  Deleting plan metadata...")
        PlanServerConnection.objects.filter(server_class__plan=plan).delete()
        SwitchPortZone.objects.filter(switch_class__plan=plan).delete()
        PlanSwitchClass.objects.filter(plan=plan).delete()
        PlanServerClass.objects.filter(plan=plan).delete()
        GenerationState.objects.filter(plan=plan).delete()
        plan.delete()
        self.stdout.write("  ✓ Cleanup complete")

    def _create_case_data(self) -> TopologyPlan:
        # Phase 5: delegate case definition to YAML ingestion engine.
        from netbox_hedgehog.test_cases.runner import apply_case_id

        return apply_case_id(
            "ux_case_128gpu_odd_ports",
            clean=False,
            prune=True,
            reference_mode="ensure",
        )

    def _display_report(self, plan: TopologyPlan) -> None:
        """Display detailed report of plan and generated objects."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 DETAILED REPORT"))
        self.stdout.write("=" * 80)

        # Plan summary
        self.stdout.write(f"\n📋 Plan: {plan.name} (ID: {plan.pk})")
        self.stdout.write(f"   Status: {plan.status}")
        self.stdout.write(f"   Description: {plan.description}")

        # Server classes
        self.stdout.write("\n👥 Server Classes:")
        server_classes = PlanServerClass.objects.filter(plan=plan)
        for sc in server_classes:
            self.stdout.write(f"   • {sc.server_class_id}: {sc.quantity} servers")
            self.stdout.write(f"     - Category: {sc.category}")
            self.stdout.write(f"     - GPUs per server: {sc.gpus_per_server}")
            self.stdout.write(f"     - Device type: {sc.server_device_type}")

            # Connections for this server class
            connections = PlanServerConnection.objects.filter(server_class=sc)
            if connections:
                self.stdout.write(f"     - Connections:")
                for conn in connections:
                    self.stdout.write(
                        f"       → {conn.connection_id}: {conn.ports_per_connection}x{conn.speed}G "
                        f"({conn.hedgehog_conn_type}, {conn.distribution}) to {conn.target_zone}"
                    )

        # Switch classes
        self.stdout.write("\n🔀 Switch Classes:")
        switch_classes = PlanSwitchClass.objects.filter(plan=plan).order_by("fabric", "hedgehog_role")
        for swc in switch_classes:
            calc_qty = swc.calculated_quantity if swc.calculated_quantity is not None else "N/A"
            override_qty = swc.override_quantity if swc.override_quantity is not None else "-"
            self.stdout.write(
                f"   • {swc.switch_class_id} ({swc.fabric}, {swc.hedgehog_role})"
            )
            self.stdout.write(
                f"     - Quantity: {swc.effective_quantity} (calculated: {calc_qty}, override: {override_qty})"
            )
            self.stdout.write(f"     - Device type: {swc.device_type_extension.device_type}")
            self.stdout.write(f"     - MCLAG pair: {swc.mclag_pair}")

            # Port zones for this switch class
            zones = SwitchPortZone.objects.filter(switch_class=swc)
            if zones:
                self.stdout.write(f"     - Port zones:")
                for zone in zones:
                    self.stdout.write(
                        f"       → {zone.zone_name} ({zone.zone_type}): ports {zone.port_spec}, "
                        f"breakout {zone.breakout_option.breakout_id}"
                    )

        # Generated objects (if any)
        tag = Tag.objects.filter(slug=DeviceGenerator.DEFAULT_TAG_SLUG).first()
        if tag:
            devices = Device.objects.filter(
                tags=tag,
                custom_field_data__hedgehog_plan_id=str(plan.pk),
            )
            interfaces = Interface.objects.filter(
                tags=tag,
                custom_field_data__hedgehog_plan_id=str(plan.pk),
            )
            cables = Cable.objects.filter(
                tags=tag,
                custom_field_data__hedgehog_plan_id=str(plan.pk),
            )

            if devices.exists():
                self.stdout.write("\n📦 Generated Objects:")
                self.stdout.write(f"   • Devices: {devices.count()}")

                # Breakdown by device type
                device_breakdown = devices.values('device_type__model').annotate(
                    count=models.Count('id')
                ).order_by('-count')
                for item in device_breakdown:
                    self.stdout.write(f"     - {item['device_type__model']}: {item['count']}")

                self.stdout.write(f"   • Interfaces: {interfaces.count()}")
                self.stdout.write(f"   • Cables: {cables.count()}")

                # Sample devices
                self.stdout.write("\n   Sample devices:")
                for device in devices[:5]:
                    self.stdout.write(f"     - {device.name} ({device.device_type})")
                if devices.count() > 5:
                    self.stdout.write(f"     ... and {devices.count() - 5} more")

        # NetBox URLs
        self.stdout.write(f"\n🔗 View in NetBox:")
        self.stdout.write(f"   • Plan detail: http://localhost:8000/plugins/hedgehog/topology-plans/{plan.pk}/")
        self.stdout.write(f"   • All plans: http://localhost:8000/plugins/hedgehog/topology-plans/")
        if tag and devices.exists():
            self.stdout.write(f"   • Generated devices: http://localhost:8000/dcim/devices/?tag=hedgehog-generated")

        self.stdout.write("\n" + "=" * 80)
