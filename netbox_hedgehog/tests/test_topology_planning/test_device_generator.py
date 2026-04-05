"""
Tests for the DeviceGenerator service.
"""

from django.test import TestCase

from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
from dcim.models import Cable

from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic

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
            nic=get_test_server_nic(cls.server_class),
            port_index=0,
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
        self.assertEqual(result.interface_count, 2)  # switch-side only
        self.assertEqual(result.cable_count, 2)

        self.assertEqual(Device.objects.filter(tags__slug='hedgehog-generated').count(), 3)
        self.assertEqual(Interface.objects.filter(tags__slug='hedgehog-generated').count(), 2)  # switch-side only
        self.assertEqual(Cable.objects.filter(tags__slug='hedgehog-generated').count(), 2)

        state = GenerationState.objects.get(plan=self.plan)
        self.assertEqual(state.device_count, 3)
        self.assertEqual(state.interface_count, 2)  # switch-side only
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


class RailDomainAllocationTestCase(TestCase):
    """
    Regression tests for DIET-332: rail-domain allocation.

    Two complementary behaviors:
    1. Multiple rails share one switch when num_switches < total_rails (capacity-sharing).
       This was always supported; regression guard only.
    2. One rail spans multiple switches via repeated first-hop rail domains when
       num_switches >= total_rails (domain-based allocation).
       This is the new behavior that fixes XOC-1024 generation.
    """

    @classmethod
    def setUpTestData(cls):
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica-RailDomain',
            defaults={'slug': 'celestica-raildomain'},
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='SRV-RD-01',
            defaults={'slug': 'srv-rd-01', 'u_height': 2},
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='SW-RD-01',
            defaults={'slug': 'sw-rd-01', 'u_height': 1},
        )
        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'supported_breakouts': [],
                'native_speed': 400,
                'uplink_ports': 0,
            },
        )

    def _make_rail_plan(self, num_servers, num_rails, ports_per_switch):
        """
        Create a minimal plan with rail-optimized backend connections.

        num_switches = (num_servers * num_rails) // ports_per_switch
        (assumes even division for simplicity)
        """
        import math
        num_switches = math.ceil(num_servers * num_rails / ports_per_switch)
        plan = TopologyPlan.objects.create(
            name=f'RD-{num_servers}srv-{num_rails}rail-{ports_per_switch}cap',
            customer_name='Test',
        )
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='be-rail-leaf',
            fabric='backend',
            hedgehog_role='server-leaf',
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=0,
            calculated_quantity=num_switches,
        )
        zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='be-server-ports',
            zone_type='server',
            port_spec=f'1-{ports_per_switch}',
            allocation_strategy='sequential',
        )
        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-server',
            server_device_type=self.server_type,
            quantity=num_servers,
        )
        for rail in range(num_rails):
            PlanServerConnection.objects.create(
                server_class=server_class,
                connection_id=f'BE-RAIL-{rail}',
                nic=get_test_server_nic(server_class, nic_id=f'nic-rail-{rail}'),
                port_index=0,
                ports_per_connection=1,
                hedgehog_conn_type='unbundled',
                distribution='rail-optimized',
                target_zone=zone,
                speed=400,
                rail=rail,
            )
        return plan, switch_class, zone, num_switches

    def test_multiple_rails_share_switch_when_capacity_allows(self):
        """
        Regression guard: capacity-sharing (num_switches < total_rails).

        4 servers, 4 rails, 8 ports per switch → 2 switches.
        2 switches < 4 rails → rails 0-1 share switch 0, rails 2-3 share switch 1.
        Each switch must handle 4 servers × 2 rails × 1 port = 8 ports.
        Generation must succeed.
        """
        plan, _, _, num_switches = self._make_rail_plan(
            num_servers=4, num_rails=4, ports_per_switch=8
        )
        self.assertEqual(num_switches, 2)
        generator = DeviceGenerator(plan)
        result = generator.generate_all()
        # 2 switches + 4 servers = 6 devices
        self.assertEqual(result.device_count, 6)
        # Each switch should have 8 interfaces (4 servers × 2 rails)
        switch_devices = list(Device.objects.filter(
            role__slug='leaf',
            tags__slug='hedgehog-generated',
        ).order_by('name'))
        self.assertEqual(len(switch_devices), 2)
        for sw in switch_devices:
            iface_count = Interface.objects.filter(
                device=sw, tags__slug='hedgehog-generated'
            ).count()
            self.assertEqual(iface_count, 8, f"{sw.name} expected 8 interfaces")

    def test_repeated_rail_domains_when_demand_exceeds_switch_capacity(self):
        """
        New behavior (DIET-332): domain-based allocation (num_switches >= total_rails).

        8 servers, 2 rails, 2 ports per switch → 8 switches.
        8 switches >= 2 rails → 4 domains of 2 servers each.
        - domain 0: servers 0-1 → switches 0 (rail-0) and 1 (rail-1)
        - domain 1: servers 2-3 → switches 2 (rail-0) and 3 (rail-1)
        - domain 2: servers 4-5 → switches 4 (rail-0) and 5 (rail-1)
        - domain 3: servers 6-7 → switches 6 (rail-0) and 7 (rail-1)
        Each switch must receive exactly 2 interfaces (one per server in its domain).
        Without the fix, all 8 servers would pile onto switches 0 and 1, exhausting
        capacity and raising "only 0 remain in zone 'be-server-ports'".
        """
        plan, _, _, num_switches = self._make_rail_plan(
            num_servers=8, num_rails=2, ports_per_switch=2
        )
        self.assertEqual(num_switches, 8)
        generator = DeviceGenerator(plan)
        result = generator.generate_all()
        # 8 switches + 8 servers = 16 devices
        self.assertEqual(result.device_count, 16)
        # Each switch should have exactly 2 interfaces (one per server in its domain)
        switch_devices = list(Device.objects.filter(
            role__slug='leaf',
            tags__slug='hedgehog-generated',
        ).order_by('name'))
        self.assertEqual(len(switch_devices), 8)
        for sw in switch_devices:
            iface_count = Interface.objects.filter(
                device=sw, tags__slug='hedgehog-generated'
            ).count()
            self.assertEqual(iface_count, 2, f"{sw.name} expected 2 interfaces (domain model)")

    def test_single_domain_rail_optimized_succeeds(self):
        """
        Boundary: num_switches == total_rails → one domain, all servers in it.

        4 servers, 2 rails, 4 ports per switch → 2 switches (== total_rails).
        servers_per_domain = 4; all servers fit in domain 0.
        Each switch: 4 interfaces (4 servers × 1 rail).
        """
        plan, _, _, num_switches = self._make_rail_plan(
            num_servers=4, num_rails=2, ports_per_switch=4
        )
        self.assertEqual(num_switches, 2)
        generator = DeviceGenerator(plan)
        result = generator.generate_all()
        self.assertEqual(result.device_count, 6)  # 2 switches + 4 servers
        switch_devices = list(Device.objects.filter(
            role__slug='leaf',
            tags__slug='hedgehog-generated',
        ).order_by('name'))
        self.assertEqual(len(switch_devices), 2)
        for sw in switch_devices:
            iface_count = Interface.objects.filter(
                device=sw, tags__slug='hedgehog-generated'
            ).count()
            self.assertEqual(iface_count, 4, f"{sw.name} expected 4 interfaces")
