from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from dcim.models import Device, DeviceType, Manufacturer, ModuleType

from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanServerClass,
    PlanServerConnection,
    PlanServerNIC,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)


class GenerateDevicesCommandIntegrationTestCase(TestCase):
    """Integration coverage for CLI generation preflight behavior."""

    @classmethod
    def setUpTestData(cls):
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Celestica-CLI",
            defaults={"slug": "celestica-cli"},
        )
        nvidia, _ = Manufacturer.objects.get_or_create(
            name="NVIDIA-CLI",
            defaults={"slug": "nvidia-cli"},
        )

        switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="DS5000-CLI",
            defaults={"slug": "ds5000-cli"},
        )
        server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="GPU-Server-CLI",
            defaults={"slug": "gpu-server-cli"},
        )
        nic_type, created = ModuleType.objects.get_or_create(
            manufacturer=nvidia,
            model="BF3-CLI",
        )
        if created:
            nic_type.interfacetemplates.create(name="p0", type="other")
            nic_type.interfacetemplates.create(name="p1", type="other")

        cls.switch_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=switch_type,
            defaults={
                "native_speed": 800,
                "supported_breakouts": ["1x800g", "4x200g"],
                "mclag_capable": False,
                "hedgehog_roles": ["spine", "server-leaf"],
                "hedgehog_profile_name": "celestica-ds5000",
            },
        )
        cls.breakout_4x200, _ = BreakoutOption.objects.get_or_create(
            breakout_id="4x200g",
            defaults={"from_speed": 800, "logical_ports": 4, "logical_speed": 200},
        )
        cls.breakout_1x800, _ = BreakoutOption.objects.get_or_create(
            breakout_id="1x800g",
            defaults={"from_speed": 800, "logical_ports": 1, "logical_speed": 800},
        )
        cls.server_type = server_type
        cls.nic_type = nic_type

    def _build_uncalculated_plan(self):
        plan = TopologyPlan.objects.create(name="CLI Generate Recalc Test")

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu",
            category="gpu",
            quantity=2,
            gpus_per_server=8,
            server_device_type=self.server_type,
        )
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="fe-leaf",
            fabric_name="frontend",
            fabric_class="managed",
            hedgehog_role="server-leaf",
            device_type_extension=self.switch_ext,
            calculated_quantity=None,
            override_quantity=None,
            mclag_pair=False,
        )
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name="server",
            zone_type="server",
            port_spec="1-48",
            breakout_option=self.breakout_4x200,
            allocation_strategy="sequential",
            priority=100,
        )
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name="uplink",
            zone_type="uplink",
            port_spec="49-50",
            breakout_option=self.breakout_1x800,
            allocation_strategy="sequential",
            priority=200,
        )
        nic = PlanServerNIC.objects.create(
            server_class=server_class,
            nic_id="fe",
            module_type=self.nic_type,
        )
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id="frontend",
            nic=nic,
            port_index=0,
            ports_per_connection=2,
            hedgehog_conn_type="unbundled",
            distribution="alternating",
            target_zone=switch_class.port_zones.get(zone_name="server"),
            speed=200,
            port_type="data",
        )
        return plan, switch_class

    def test_generate_devices_command_auto_recalculates_before_generation(self):
        plan, switch_class = self._build_uncalculated_plan()
        out = StringIO()

        call_command("generate_devices", str(plan.pk), stdout=out)

        switch_class.refresh_from_db()
        self.assertEqual(switch_class.calculated_quantity, 2)
        self.assertIn("Recalculated switch quantities", out.getvalue())
        self.assertTrue(
            Device.objects.filter(custom_field_data__hedgehog_plan_id=str(plan.pk)).exists()
        )
