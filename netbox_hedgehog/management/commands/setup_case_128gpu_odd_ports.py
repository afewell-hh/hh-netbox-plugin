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

from dcim.models import Manufacturer, DeviceType, InterfaceTemplate, Cable, Device, Interface
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
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Generic",
            defaults={"slug": "generic"},
        )
        gpu_fe_type = self._ensure_server_device_type(
            manufacturer=manufacturer,
            model="GPU-Server-FE",
            slug="gpu-server-fe",
            interface_specs=[
                ("eth1", "200gbase-x-qsfp56"),
                ("eth2", "200gbase-x-qsfp56"),
            ],
        )
        gpu_be_type = self._ensure_server_device_type(
            manufacturer=manufacturer,
            model="GPU-Server-FE-BE",
            slug="gpu-server-fe-be",
            interface_specs=[
                ("eth1", "200gbase-x-qsfp56"),
                ("eth2", "200gbase-x-qsfp56"),
                ("cx7-1", "400gbase-x-qsfpdd"),
                ("cx7-2", "400gbase-x-qsfpdd"),
                ("cx7-3", "400gbase-x-qsfpdd"),
                ("cx7-4", "400gbase-x-qsfpdd"),
                ("cx7-5", "400gbase-x-qsfpdd"),
                ("cx7-6", "400gbase-x-qsfpdd"),
                ("cx7-7", "400gbase-x-qsfpdd"),
                ("cx7-8", "400gbase-x-qsfpdd"),
            ],
        )
        storage_type = self._ensure_server_device_type(
            manufacturer=manufacturer,
            model="Storage-Server-200G",
            slug="storage-server-200g",
            interface_specs=[
                ("eth1", "200gbase-x-qsfp56"),
                ("eth2", "200gbase-x-qsfp56"),
            ],
        )

        ds5000_ext = self._ensure_ds5000_extension()
        breakout_4x200 = self._ensure_breakout("4x200g", 800, 4, 200)
        breakout_2x400 = self._ensure_breakout("2x400g", 800, 2, 400)
        breakout_1x800 = self._ensure_breakout("1x800g", 800, 1, 800)

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
            uplink_ports_per_switch=None,
            mclag_pair=False,
        )
        fe_storage_leaf_a = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="fe-storage-leaf-a",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=ds5000_ext,
            uplink_ports_per_switch=None,
            mclag_pair=False,
        )
        fe_storage_leaf_b = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="fe-storage-leaf-b",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=ds5000_ext,
            uplink_ports_per_switch=None,
            mclag_pair=False,
        )
        fe_spine = PlanSwitchClass.objects.create(
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
            uplink_ports_per_switch=None,
            mclag_pair=False,
        )
        be_spine = PlanSwitchClass.objects.create(
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

        def add_uplink_zone(switch_class, breakout, name="uplinks"):
            SwitchPortZone.objects.create(
                switch_class=switch_class,
                zone_name=name,
                zone_type=PortZoneTypeChoices.UPLINK,
                port_spec="2-64:2",
                breakout_option=breakout,
                allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
                priority=100,
            )

        def add_fabric_zone(switch_class, breakout, name="leaf-downlinks"):
            SwitchPortZone.objects.create(
                switch_class=switch_class,
                zone_name=name,
                zone_type=PortZoneTypeChoices.FABRIC,
                port_spec="1-64",
                breakout_option=breakout,
                allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
                priority=100,
            )

        add_server_zone(fe_gpu_leaf, breakout_4x200)
        add_server_zone(fe_storage_leaf_a, breakout_4x200)
        add_server_zone(fe_storage_leaf_b, breakout_4x200)
        add_uplink_zone(fe_gpu_leaf, breakout_1x800)
        add_uplink_zone(fe_storage_leaf_a, breakout_1x800)
        add_uplink_zone(fe_storage_leaf_b, breakout_1x800)
        add_fabric_zone(fe_spine, breakout_1x800)

        be_rail_leaf = PlanSwitchClass.objects.get(
            plan=plan,
            switch_class_id="be-rail-leaf",
        )
        add_server_zone(be_rail_leaf, breakout_2x400)
        add_uplink_zone(be_rail_leaf, breakout_1x800, name="backend-uplinks")
        add_fabric_zone(be_spine, breakout_1x800)

        gpu_fe_only = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-fe-only",
            description="96 GPU servers with frontend only",
            category=ServerClassCategoryChoices.GPU,
            quantity=96,
            gpus_per_server=8,
            server_device_type=gpu_fe_type,
        )
        gpu_with_be = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-with-backend",
            description="32 GPU servers with backend rails",
            category=ServerClassCategoryChoices.GPU,
            quantity=32,
            gpus_per_server=8,
            server_device_type=gpu_be_type,
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
            # Get eth1 interface template for frontend connections
            eth1_template = InterfaceTemplate.objects.filter(
                device_type=server_class.server_device_type,
                name='eth1'
            ).first()

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
                server_interface_template=eth1_template,
            )

        add_frontend_connection(gpu_fe_only)
        add_frontend_connection(gpu_with_be)

        # Backend rail connections (cx7-1 through cx7-8)
        for rail in range(8):
            # Get the corresponding cx7 interface template (cx7-1 for rail 0, cx7-2 for rail 1, etc.)
            cx7_template = InterfaceTemplate.objects.filter(
                device_type=gpu_with_be.server_device_type,
                name=f'cx7-{rail + 1}'
            ).first()

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
                server_interface_template=cx7_template,
            )

        # Storage frontend connections (eth1 for both storage classes)
        storage_a_eth1 = InterfaceTemplate.objects.filter(
            device_type=storage_a.server_device_type,
            name='eth1'
        ).first()
        storage_b_eth1 = InterfaceTemplate.objects.filter(
            device_type=storage_b.server_device_type,
            name='eth1'
        ).first()

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
            server_interface_template=storage_a_eth1,
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
            server_interface_template=storage_b_eth1,
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
        if InterfaceTemplate.objects.filter(device_type=device_type).count() == 0:
            for index in range(1, 65):
                InterfaceTemplate.objects.get_or_create(
                    device_type=device_type,
                    name=f"E1/{index}",
                    defaults={"type": "800gbase-x-qsfpdd"},
                )
        ext, created = DeviceTypeExtension.objects.get_or_create(
            device_type=device_type,
            defaults={
                "mclag_capable": False,
                "hedgehog_roles": ["spine", "server-leaf"],
                "supported_breakouts": ["1x800g", "2x400g", "4x200g", "8x100g"],
                "native_speed": 800,
                "uplink_ports": 32,
                "hedgehog_profile_name": "celestica-ds5000",
                "notes": "Auto-created for 128-GPU odd-port case",
            },
        )
        if not created:
            updated_fields = []
            if not ext.hedgehog_profile_name:
                ext.hedgehog_profile_name = "celestica-ds5000"
                updated_fields.append("hedgehog_profile_name")
            if ext.native_speed is None:
                ext.native_speed = 800
                updated_fields.append("native_speed")
            if not ext.supported_breakouts:
                ext.supported_breakouts = ["1x800g", "2x400g", "4x200g", "8x100g"]
                updated_fields.append("supported_breakouts")
            if ext.uplink_ports is None:
                ext.uplink_ports = 32
                updated_fields.append("uplink_ports")
            if not ext.hedgehog_roles:
                ext.hedgehog_roles = ["spine", "server-leaf"]
                updated_fields.append("hedgehog_roles")
            if updated_fields:
                ext.save(update_fields=updated_fields)
        return ext

    def _ensure_server_device_type(
        self,
        manufacturer: Manufacturer,
        model: str,
        slug: str,
        interface_specs: list[tuple[str, str]],
    ) -> DeviceType:
        device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model=model,
            defaults={
                "slug": slug,
                "u_height": 2,
                "is_full_depth": True,
            },
        )
        for name, interface_type in interface_specs:
            InterfaceTemplate.objects.get_or_create(
                device_type=device_type,
                name=name,
                defaults={"type": interface_type},
            )
        return device_type

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
                        f"({conn.hedgehog_conn_type}, {conn.distribution}) to {conn.target_switch_class.switch_class_id}"
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
