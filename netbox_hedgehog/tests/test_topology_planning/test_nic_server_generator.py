"""
Generator tests for PlanServerNIC-driven Module creation (DIET-294).

Tests fail RED until GREEN implementation replaces _create_module_for_connection
with _create_module_for_nic and adds the two-pass generation loop.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError

from dcim.models import (
    DeviceType, Manufacturer, ModuleType, InterfaceTemplate,
    Device, Module, ModuleBay, Interface, Site,
)

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan, PlanServerClass, PlanSwitchClass, PlanServerConnection,
    PlanServerNIC, DeviceTypeExtension, BreakoutOption, SwitchPortZone,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices, FabricTypeChoices, HedgehogRoleChoices,
    ConnectionTypeChoices, ConnectionDistributionChoices,
    ServerClassCategoryChoices, PortZoneTypeChoices, AllocationStrategyChoices,
    FabricClassChoices,
)


class NICServerGeneratorTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.mfr, _ = Manufacturer.objects.get_or_create(name='GenTest294', defaults={'slug': 'gentest294'})
        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='SRV-GEN', defaults={'slug': 'srv-gen'},
        )
        cls.switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='SW-GEN', defaults={'slug': 'sw-gen'},
        )
        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_dt,
            defaults={
                'native_speed': 200, 'uplink_ports': 0,
                'supported_breakouts': ['1x200g'], 'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
            },
        )
        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x200g-gen',
            defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
        )
        # BF3 with 2 ports
        cls.bf3_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='BF3-GEN',
        )
        InterfaceTemplate.objects.get_or_create(
            module_type=cls.bf3_mt, name='p0', defaults={'type': '200gbase-x-qsfp112'},
        )
        InterfaceTemplate.objects.get_or_create(
            module_type=cls.bf3_mt, name='p1', defaults={'type': '200gbase-x-qsfp112'},
        )
        # Single-port CX7
        cls.cx7_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='CX7-GEN',
        )
        InterfaceTemplate.objects.get_or_create(
            module_type=cls.cx7_mt, name='port0', defaults={'type': '400gbase-x-osfp'},
        )
        cls.site, _ = Site.objects.get_or_create(name='GenSite294', defaults={'slug': 'gensite294'})

    def setUp(self):
        Device.objects.filter(
            custom_field_data__has_key='hedgehog_plan_id'
        ).filter(role__slug='server').delete()
        from dcim.models import Cable
        Cable.objects.all().delete()

    def tearDown(self):
        from dcim.models import Cable
        Device.objects.filter(
            custom_field_data__has_key='hedgehog_plan_id'
        ).delete()
        Cable.objects.all().delete()

    def _make_plan(self, server_quantity=1):
        plan = TopologyPlan.objects.create(
            name=f'GenPlan294-{id(self)}', status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu', server_device_type=self.server_dt,
            quantity=server_quantity,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        zone = SwitchPortZone.objects.create(
            switch_class=sw, zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-64',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )
        return plan, sc, sw, zone

    def test_one_module_per_nic_not_per_connection(self):
        """One NIC with ports_per_connection=2 → exactly one Module, not two."""
        plan, sc, sw, zone = self._make_plan()
        nic = PlanServerNIC.objects.create(server_class=sc, nic_id='nic-fe', module_type=self.bf3_mt)
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe',
            nic=nic, port_index=0, ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
        )
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        DeviceGenerator(plan).generate_all()
        module_count = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
        ).count()
        self.assertEqual(module_count, 1, f"Expected 1 Module, got {module_count}")

    def test_bay_name_equals_nic_id(self):
        """Generated ModuleBay.name must equal PlanServerNIC.nic_id."""
        plan, sc, sw, zone = self._make_plan()
        nic = PlanServerNIC.objects.create(server_class=sc, nic_id='nic-fe', module_type=self.bf3_mt)
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
        )
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        DeviceGenerator(plan).generate_all()
        bay = ModuleBay.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
        ).first()
        self.assertIsNotNone(bay)
        self.assertEqual(bay.name, 'nic-fe')

    def test_interface_prefix_equals_nic_id(self):
        """Auto-created interfaces are prefixed with nic_id: 'nic-fe-p0', 'nic-fe-p1'."""
        plan, sc, sw, zone = self._make_plan()
        nic = PlanServerNIC.objects.create(server_class=sc, nic_id='nic-fe', module_type=self.bf3_mt)
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe',
            nic=nic, port_index=0, ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
        )
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        DeviceGenerator(plan).generate_all()
        iface_names = list(Interface.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            module__isnull=False,
        ).values_list('name', flat=True))
        self.assertIn('nic-fe-p0', iface_names)
        self.assertIn('nic-fe-p1', iface_names)

    def test_generate_raises_if_nic_module_type_has_no_templates(self):
        """Generator raises ValidationError when NIC module_type has no InterfaceTemplates."""
        plan, sc, sw, zone = self._make_plan()
        empty_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=self.mfr, model='Empty-GEN',
        )
        nic = PlanServerNIC.objects.create(
            server_class=sc, nic_id='nic-empty', module_type=empty_mt,
        )
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
        )
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        with self.assertRaises((ValidationError, Exception)):
            DeviceGenerator(plan).generate_all()
