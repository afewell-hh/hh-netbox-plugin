import csv
import json
import os
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from dcim.models import Cable, Device, DeviceRole, DeviceType, Interface, InterfaceTemplate, Manufacturer, Site

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricTypeChoices,
    GenerationStatusChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    ServerClassCategoryChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    GenerationState,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic


class PlanInventoryExportCommandsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name="ExportCmd Celestica",
            defaults={"slug": "exportcmd-celestica"},
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="ExportCmd DS5000",
            defaults={"slug": "exportcmd-ds5000"},
        )
        InterfaceTemplate.objects.get_or_create(
            device_type=cls.switch_type,
            name="E1/1",
            defaults={"type": "800gbase-x-osfp"},
        )

        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="ExportCmd Server",
            defaults={"slug": "exportcmd-server"},
        )
        for name in ("eth1", "eth2"):
            InterfaceTemplate.objects.get_or_create(
                device_type=cls.server_type,
                name=name,
                defaults={"type": "200gbase-x-qsfp56"},
            )

        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_type,
            defaults={
                "native_speed": 800,
                "supported_breakouts": ["4x200g"],
                "mclag_capable": False,
                "hedgehog_roles": ["server-leaf"],
            },
        )
        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id="4x200g",
            defaults={"from_speed": 800, "logical_ports": 4, "logical_speed": 200},
        )
        cls.site, _ = Site.objects.get_or_create(
            name="ExportCmd Site",
            defaults={"slug": "exportcmd-site"},
        )
        DeviceRole.objects.get_or_create(
            name="Server",
            defaults={"slug": "server", "color": "aa1409"},
        )

    def setUp(self):
        self.plan = TopologyPlan.objects.create(name="Export Commands Plan")
        self.server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id="server-class",
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            gpus_per_server=8,
            server_device_type=self.server_type,
        )
        self.switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id="fe-leaf",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=0,
            mclag_pair=False,
            calculated_quantity=1,
            override_quantity=1,
        )
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name="server-downlinks",
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec="1-1",
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )
        PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id="fe-conn",
            nic=get_test_server_nic(self.server_class),
            port_index=0,
            connection_name="frontend",
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_zone=zone,
            speed=200,
        )
        DeviceGenerator(plan=self.plan, site=self.site).generate_all()
        self.other_plan = TopologyPlan.objects.create(name="Other Plan")
        self._create_other_plan_noise()

    def _create_other_plan_noise(self):
        device_a = Device.objects.create(
            name="other-device-a",
            device_type=self.server_type,
            role=DeviceRole.objects.get(slug="server"),
            site=self.site,
            status="planned",
            custom_field_data={"hedgehog_plan_id": str(self.other_plan.pk)},
        )
        device_b = Device.objects.create(
            name="other-device-b",
            device_type=self.server_type,
            role=DeviceRole.objects.get(slug="server"),
            site=self.site,
            status="planned",
            custom_field_data={"hedgehog_plan_id": str(self.other_plan.pk)},
        )
        interface_a = Interface.objects.get(device=device_a, name="eth1")
        interface_b = Interface.objects.get(device=device_b, name="eth1")
        interface_a.custom_field_data = {"hedgehog_plan_id": str(self.other_plan.pk)}
        interface_a.save()
        interface_b.custom_field_data = {"hedgehog_plan_id": str(self.other_plan.pk)}
        interface_b.save()

        cable = Cable(a_terminations=[interface_a], b_terminations=[interface_b])
        cable.custom_field_data = {"hedgehog_plan_id": str(self.other_plan.pk)}
        cable.save()

    def test_export_plan_inventory_json_filters_to_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "inventory.json")
            call_command(
                "export_plan_inventory_json",
                str(self.plan.pk),
                "--output",
                output_path,
            )

            with open(output_path, "r", encoding="utf-8") as handle:
                document = json.load(handle)

        self.assertEqual(document["metadata"]["plan_id"], self.plan.pk)
        device_names = {d["name"] for d in document["devices"]}
        self.assertNotIn("other-device-a", device_names)
        self.assertNotIn("other-device-b", device_names)
        self.assertGreaterEqual(document["metadata"]["counts"]["devices"], 2)
        self.assertGreaterEqual(document["metadata"]["counts"]["cables"], 1)

    def test_export_interface_connections_csv_filters_to_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "connections.csv")
            call_command(
                "export_interface_connections_csv",
                str(self.plan.pk),
                "--output",
                output_path,
            )

            with open(output_path, "r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(all(row["plan_id"] == str(self.plan.pk) for row in rows))
        devices = {row["a_device"] for row in rows} | {row["b_device"] for row in rows}
        self.assertNotIn("other-device-a", devices)
        self.assertNotIn("other-device-b", devices)

    def test_inventory_export_requires_generated_status(self):
        failed_plan = TopologyPlan.objects.create(name="Failed Export Plan")
        GenerationState.objects.create(
            plan=failed_plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status=GenerationStatusChoices.FAILED,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(CommandError):
                call_command(
                    "export_plan_inventory_json",
                    str(failed_plan.pk),
                    "--output",
                    os.path.join(tmpdir, "inventory.json"),
                )

    def test_csv_export_requires_existing_output_directory(self):
        with self.assertRaises(CommandError):
            call_command(
                "export_interface_connections_csv",
                str(self.plan.pk),
                "--output",
                "/nonexistent/export/connections.csv",
            )
