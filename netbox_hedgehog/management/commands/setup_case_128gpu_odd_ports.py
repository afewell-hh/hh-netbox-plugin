"""
Create the 128-GPU odd-port breakout topology test case.

Usage:
    docker compose exec netbox python manage.py setup_case_128gpu_odd_ports
    docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --clean
    docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --generate
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.exceptions import ValidationError

from dcim.models import Manufacturer, DeviceType, Cable, Device, Interface
from extras.models import Tag

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    SwitchPortZone,
    DeviceTypeExtension,
    BreakoutOption,
    GenerationState,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    ServerClassCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    PortTypeChoices,
    AllocationStrategyChoices,
    PortZoneTypeChoices,
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

    def handle(self, *args, **options):
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
                    update_plan_calculations(plan)
                    self.stdout.write(self.style.SUCCESS("✅ Case created successfully."))
                    self.stdout.write(f"  Plan: {plan.name} (ID: {plan.pk})")

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
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Generic",
            defaults={"slug": "generic"},
        )
        gpu_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="GPU-Server",
            defaults={"slug": "gpu-server"},
        )
        storage_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="Storage-Server",
            defaults={"slug": "storage-server"},
        )

        ds5000_ext = self._ensure_ds5000_extension()
        breakout_4x200 = self._ensure_breakout("4x200g", 800, 4, 200)
        breakout_2x400 = self._ensure_breakout("2x400g", 800, 2, 400)

        plan = TopologyPlan.objects.create(
            name=PLAN_NAME,
            status=TopologyPlanStatusChoices.DRAFT,
            description=(
                "128 GPU servers with FE redundancy, BE rails, storage split, "
                "and odd-port 4x200G breakouts"
            ),
        )

        fe_gpu_leaf = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="fe-gpu-leaf",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=ds5000_ext,
            uplink_ports_per_switch=32,
            mclag_pair=True,
        )
        fe_storage_leaf_a = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="fe-storage-leaf-a",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=ds5000_ext,
            uplink_ports_per_switch=32,
            mclag_pair=False,
        )
        fe_storage_leaf_b = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="fe-storage-leaf-b",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=ds5000_ext,
            uplink_ports_per_switch=32,
            mclag_pair=False,
        )
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="fe-spine",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SPINE,
            device_type_extension=ds5000_ext,
            uplink_ports_per_switch=0,
            mclag_pair=False,
        )
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="be-rail-leaf",
            fabric=FabricTypeChoices.BACKEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=ds5000_ext,
            uplink_ports_per_switch=32,
            mclag_pair=False,
            override_quantity=8,
        )
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="be-spine",
            fabric=FabricTypeChoices.BACKEND,
            hedgehog_role=HedgehogRoleChoices.SPINE,
            device_type_extension=ds5000_ext,
            uplink_ports_per_switch=0,
            mclag_pair=False,
        )

        def add_server_zone(switch_class, breakout, name="server-downlinks"):
            SwitchPortZone.objects.create(
                switch_class=switch_class,
                zone_name=name,
                zone_type=PortZoneTypeChoices.SERVER,
                port_spec="1-63:2",
                breakout_option=breakout,
                allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
                priority=100,
            )

        add_server_zone(fe_gpu_leaf, breakout_4x200)
        add_server_zone(fe_storage_leaf_a, breakout_4x200)
        add_server_zone(fe_storage_leaf_b, breakout_4x200)

        be_rail_leaf = PlanSwitchClass.objects.get(
            plan=plan,
            switch_class_id="be-rail-leaf",
        )
        add_server_zone(be_rail_leaf, breakout_2x400)

        gpu_fe_only = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-fe-only",
            description="96 GPU servers with frontend only",
            category=ServerClassCategoryChoices.GPU,
            quantity=96,
            gpus_per_server=8,
            server_device_type=gpu_type,
        )
        gpu_with_be = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-with-backend",
            description="32 GPU servers with backend rails",
            category=ServerClassCategoryChoices.GPU,
            quantity=32,
            gpus_per_server=8,
            server_device_type=gpu_type,
        )
        storage_a = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="storage-a",
            description="Storage appliances 1-9",
            category=ServerClassCategoryChoices.STORAGE,
            quantity=9,
            gpus_per_server=0,
            server_device_type=storage_type,
        )
        storage_b = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="storage-b",
            description="Storage appliances 10-18",
            category=ServerClassCategoryChoices.STORAGE,
            quantity=9,
            gpus_per_server=0,
            server_device_type=storage_type,
        )

        def add_frontend_connection(server_class):
            PlanServerConnection.objects.create(
                server_class=server_class,
                connection_id="fe",
                connection_name="frontend",
                ports_per_connection=2,
                hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
                distribution=ConnectionDistributionChoices.ALTERNATING,
                target_switch_class=fe_gpu_leaf,
                speed=200,
                port_type=PortTypeChoices.DATA,
            )

        add_frontend_connection(gpu_fe_only)
        add_frontend_connection(gpu_with_be)

        for rail in range(8):
            PlanServerConnection.objects.create(
                server_class=gpu_with_be,
                connection_id=f"be-rail-{rail}",
                connection_name=f"backend-rail-{rail}",
                ports_per_connection=1,
                hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
                distribution=ConnectionDistributionChoices.RAIL_OPTIMIZED,
                target_switch_class=be_rail_leaf,
                speed=400,
                rail=rail,
                port_type=PortTypeChoices.DATA,
            )

        PlanServerConnection.objects.create(
            server_class=storage_a,
            connection_id="fe-storage",
            connection_name="storage-frontend",
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.BUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_switch_class=fe_storage_leaf_a,
            speed=200,
            port_type=PortTypeChoices.DATA,
        )
        PlanServerConnection.objects.create(
            server_class=storage_b,
            connection_id="fe-storage",
            connection_name="storage-frontend",
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.BUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_switch_class=fe_storage_leaf_b,
            speed=200,
            port_type=PortTypeChoices.DATA,
        )

        return plan

    def _ensure_breakout(self, breakout_id: str, from_speed: int, logical_ports: int, logical_speed: int):
        breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id=breakout_id,
            defaults={
                "from_speed": from_speed,
                "logical_ports": logical_ports,
                "logical_speed": logical_speed,
                "optic_type": "QSFP-DD",
            },
        )
        return breakout

    def _ensure_ds5000_extension(self) -> DeviceTypeExtension:
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Celestica",
            defaults={"slug": "celestica"},
        )
        device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="DS5000",
            defaults={"slug": "ds5000"},
        )
        ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=device_type,
            defaults={
                "mclag_capable": False,
                "hedgehog_roles": ["spine", "server-leaf"],
                "supported_breakouts": ["1x800g", "2x400g", "4x200g", "8x100g"],
                "native_speed": 800,
                "uplink_ports": 32,
                "notes": "Auto-created for 128-GPU odd-port case",
            },
        )
        return ext
