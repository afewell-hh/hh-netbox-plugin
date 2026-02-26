"""
Tests for the DeviceGenerator service.
"""

from django.test import TestCase

from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
from dcim.models import Cable

from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    GenerationState,
    NamingTemplate,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator


class DeviceGeneratorTestCase(TestCase):
    """Test suite for DeviceGenerator service"""

    @classmethod
    def setUpTestData(cls):
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'},
        )

        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='SRV-01',
            defaults={
                'slug': 'srv-01',
                'u_height': 2,
                'is_full_depth': True,
            },
        )

        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={
                'slug': 'ds5000',
                'u_height': 1,
                'is_full_depth': True,
            },
        )

        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf'],
                'supported_breakouts': ['4x200g'],
                'native_speed': 800,
                'uplink_ports': 4,
            },
        )

        cls.breakout_4x200g, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200},
        )

        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer',
        )

        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-gpu-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=4,
            calculated_quantity=1,
        )

        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='gpu-b200',
            server_device_type=cls.server_type,
            quantity=2,
        )

        cls.zone = SwitchPortZone.objects.create(
            switch_class=cls.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-2',
            allocation_strategy='sequential',
        )

        cls.connection = PlanServerConnection.objects.create(
            server_class=cls.server_class,
            connection_id='FE-01',
            ports_per_connection=1,
            hedgehog_conn_type='unbundled',
            distribution='same-switch',
            target_zone=cls.zone,
            speed=200,
        )

    def test_generate_creates_devices_interfaces_cables_and_state(self):
        """Generator should create devices, interfaces, cables, and GenerationState."""
        generator = DeviceGenerator(self.plan)
        result = generator.generate_all()

        self.assertEqual(result.device_count, 3)
        self.assertEqual(result.interface_count, 4)
        self.assertEqual(result.cable_count, 2)

        self.assertEqual(Device.objects.filter(tags__slug='hedgehog-generated').count(), 3)
        self.assertEqual(Interface.objects.filter(tags__slug='hedgehog-generated').count(), 4)
        self.assertEqual(Cable.objects.filter(tags__slug='hedgehog-generated').count(), 2)

        state = GenerationState.objects.get(plan=self.plan)
        self.assertEqual(state.device_count, 3)
        self.assertEqual(state.interface_count, 4)
        self.assertEqual(state.cable_count, 2)

    def test_generate_applies_naming_template(self):
        """Generator should honor plan-specific naming templates."""
        NamingTemplate.objects.create(
            plan=self.plan,
            device_category='server',
            pattern='srv-{class}-{index:02d}',
        )

        generator = DeviceGenerator(self.plan)
        generator.generate_all()

        server_names = sorted(Device.objects.filter(role__slug='server').values_list('name', flat=True))
        self.assertEqual(server_names, ['srv-gpu-b200-01', 'srv-gpu-b200-02'])

    def test_generate_applies_breakout_metadata(self):
        """Generator should set breakout metadata on switch interfaces."""
        self.zone.breakout_option = self.breakout_4x200g
        self.zone.port_spec = '1-1'
        self.zone.save()

        self.connection.ports_per_connection = 2
        self.connection.save()

        generator = DeviceGenerator(self.plan)
        generator.generate_all()

        switch_interfaces = Interface.objects.filter(
            device__role__slug='leaf',
            tags__slug='hedgehog-generated',
        ).order_by('name')
        self.assertEqual(
            list(switch_interfaces.values_list('name', flat=True)),
            ['E1/1/1', 'E1/1/2', 'E1/1/3', 'E1/1/4'],
        )

        for iface in switch_interfaces:
            self.assertEqual(iface.custom_field_data.get('hedgehog_zone'), 'server-ports')
            self.assertEqual(iface.custom_field_data.get('hedgehog_physical_port'), 1)
            self.assertIsNotNone(iface.custom_field_data.get('hedgehog_breakout_index'))

    def test_generate_creates_default_site_and_roles(self):
        """Generator should create default site and device roles if missing."""
        generator = DeviceGenerator(self.plan)
        generator.generate_all()

        self.assertTrue(Site.objects.filter(slug='hedgehog').exists())
        self.assertTrue(DeviceRole.objects.filter(slug='server').exists())
        self.assertTrue(DeviceRole.objects.filter(slug='leaf').exists())
