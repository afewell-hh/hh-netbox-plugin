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


# =============================================================================
# DIET-322: same-switch grouped-per-leaf allocation
# =============================================================================

class SameSwitchGroupingUnitTestCase(TestCase):
    """Unit tests for _select_switch_instance() same-switch grouped placement.

    Uses plain Python objects as stand-ins for Device instances — the method
    only indexes into the list, so no ORM is involved.

    Before DIET-460 the method used server_index % num_switches (round-robin).
    It must now use contiguous grouped allocation so that single-homed
    scale-out variants cable correctly (issue #322).

    Current algorithm (base_group_size / extra_servers loop):
    - extra servers are distributed one at a time to the *first* switches only
    - 7/2 → sw0 gets 4 (0-3), sw1 gets 3 (4-6)
    - 3/2 → sw0 gets 2 (0-1), sw1 gets 1 (2)
    """

    def setUp(self):
        self.gen = DeviceGenerator.__new__(DeviceGenerator)
        self.gen.plan = TopologyPlan(name='unit-test-322')

    def _sel(self, switches, server_index, distribution='same-switch',
             port_index=0, total_servers=None):
        return self.gen._select_switch_instance(
            switch_instances=switches,
            distribution=distribution,
            server_index=server_index,
            port_index=port_index,
            total_servers=total_servers,
        )

    # --- even split: 8 servers / 2 leaves → 4/4 ---

    def test_8_servers_2_leaves_first_four_on_leaf_a(self):
        """Servers 0-3 must all land on leaf-a with 8 servers / 2 leaves."""
        leaves = ['leaf-a', 'leaf-b']
        for idx in range(4):
            self.assertEqual(
                self._sel(leaves, idx, total_servers=8), 'leaf-a',
                f'server_index={idx} expected leaf-a',
            )

    def test_8_servers_2_leaves_last_four_on_leaf_b(self):
        """Servers 4-7 must all land on leaf-b with 8 servers / 2 leaves."""
        leaves = ['leaf-a', 'leaf-b']
        for idx in range(4, 8):
            self.assertEqual(
                self._sel(leaves, idx, total_servers=8), 'leaf-b',
                f'server_index={idx} expected leaf-b',
            )

    # --- odd split: 7 servers / 2 leaves → 4/3 ---

    def test_7_servers_2_leaves_first_switch_gets_extra(self):
        """7/2: base=3, extra=1 → sw0 gets 4 (0-3), sw1 gets 3 (4-6)."""
        leaves = ['leaf-a', 'leaf-b']
        expected = ['leaf-a'] * 4 + ['leaf-b'] * 3
        for idx, exp in enumerate(expected):
            self.assertEqual(
                self._sel(leaves, idx, total_servers=7), exp,
                f'server_index={idx} expected {exp}',
            )

    # --- odd split: 3 servers / 2 leaves → 2/1 ---

    def test_3_servers_2_leaves_split_2_1(self):
        """3/2: base=1, extra=1 → sw0 gets 2 (0-1), sw1 gets 1 (2)."""
        leaves = ['leaf-a', 'leaf-b']
        self.assertEqual(self._sel(leaves, 0, total_servers=3), 'leaf-a')
        self.assertEqual(self._sel(leaves, 1, total_servers=3), 'leaf-a')
        self.assertEqual(self._sel(leaves, 2, total_servers=3), 'leaf-b')

    # --- single switch always returned ---

    def test_single_switch_always_returned(self):
        """With one leaf, every server lands there regardless of total_servers."""
        leaves = ['only-leaf']
        for idx in range(8):
            self.assertEqual(self._sel(leaves, idx, total_servers=8), 'only-leaf')

    # --- multi-port same server stays on same leaf ---

    def test_multi_port_same_server_stays_on_same_leaf(self):
        """port_index does not affect same-switch selection; all ports of server 0 → leaf-a."""
        leaves = ['leaf-a', 'leaf-b']
        for port_idx in range(4):
            self.assertEqual(
                self._sel(leaves, 0, port_index=port_idx, total_servers=8), 'leaf-a',
            )

    # --- fallback when total_servers not provided ---

    def test_total_servers_none_falls_back_to_modulo(self):
        """When total_servers is None the fallback uses server_index % num_switches."""
        leaves = ['leaf-a', 'leaf-b']
        # modulo: 0 → a, 1 → b, 2 → a, 3 → b
        self.assertEqual(self._sel(leaves, 0, total_servers=None), 'leaf-a')
        self.assertEqual(self._sel(leaves, 1, total_servers=None), 'leaf-b')
        self.assertEqual(self._sel(leaves, 2, total_servers=None), 'leaf-a')
        self.assertEqual(self._sel(leaves, 3, total_servers=None), 'leaf-b')

    # --- alternating unchanged (regression guard) ---

    def test_alternating_still_rotates_by_port_index(self):
        """alternating must rotate by port_index regardless of server_index (regression guard)."""
        leaves = ['leaf-a', 'leaf-b']
        self.assertEqual(self._sel(leaves, 0, 'alternating', port_index=0), 'leaf-a')
        self.assertEqual(self._sel(leaves, 0, 'alternating', port_index=1), 'leaf-b')
        self.assertEqual(self._sel(leaves, 0, 'alternating', port_index=2), 'leaf-a')
        # server_index must not affect alternating
        self.assertEqual(self._sel(leaves, 5, 'alternating', port_index=0), 'leaf-a')
        self.assertEqual(self._sel(leaves, 5, 'alternating', port_index=1), 'leaf-b')


class SameSwitchGroupingIntegrationTestCase(TestCase):
    """Integration test: generator groups servers per leaf for same-switch (issue #322).

    2 leaf instances, 8 servers, same-switch distribution.
    Expected: servers 001-004 (sorted) → leaf 01, servers 005-008 → leaf 02.
    If the algorithm were still round-robin each leaf would get 4 servers
    interleaved (001,003,005,007 vs 002,004,006,008) — the test would fail.
    """

    @classmethod
    def setUpTestData(cls):
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica-322',
            defaults={'slug': 'celestica-322'},
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='SRV-322',
            defaults={'slug': 'srv-322', 'u_height': 2, 'is_full_depth': True},
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000-322',
            defaults={'slug': 'ds5000-322', 'u_height': 1, 'is_full_depth': True},
        )
        cls.ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'supported_breakouts': [],
                'native_speed': 400,
                'uplink_ports': 0,
            },
        )
        cls.plan = TopologyPlan.objects.create(name='SH-Grouping-322')
        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='sh-leaf-322',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=cls.ext,
            uplink_ports_per_switch=0,
            calculated_quantity=2,
        )
        cls.zone = SwitchPortZone.objects.create(
            switch_class=cls.switch_class,
            zone_name='sh-server',
            zone_type='server',
            port_spec='1-8',
            allocation_strategy='sequential',
        )
        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='sh-compute-322',
            server_device_type=cls.server_type,
            quantity=8,
        )
        PlanServerConnection.objects.create(
            server_class=cls.server_class,
            connection_id='SH-01',
            nic=get_test_server_nic(cls.server_class),
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type='unbundled',
            distribution='same-switch',
            target_zone=cls.zone,
            speed=400,
        )

    def test_same_switch_groups_servers_per_leaf(self):
        """8 servers × same-switch × 2 leaves must produce 4/4 grouped cabling, not interleaved."""
        DeviceGenerator(self.plan).generate_all()

        # Switch interfaces have hedgehog_plan_id set; use that to scope to this plan.
        # Server interfaces are created via Module instantiation and are not tagged,
        # so we traverse: plan-scoped switch interface → cable → server interface.
        plan_id = str(self.plan.pk)
        server_to_switch: dict[str, str] = {}
        for sw_iface in Interface.objects.filter(
            custom_field_data__hedgehog_plan_id=plan_id,
            device__role__slug='leaf',
            cable__isnull=False,
        ).select_related('device'):
            server_iface = Interface.objects.filter(
                cable=sw_iface.cable,
                device__role__slug='server',
            ).select_related('device').first()
            if server_iface:
                server_to_switch[server_iface.device.name] = sw_iface.device.name

        self.assertEqual(len(server_to_switch), 8, 'Expected 8 server→leaf cable mappings')

        servers_sorted = sorted(server_to_switch)
        group_a = {server_to_switch[s] for s in servers_sorted[:4]}
        group_b = {server_to_switch[s] for s in servers_sorted[4:]}

        self.assertEqual(len(group_a), 1,
                         f'Servers 001-004 must all be on one leaf, got {group_a}')
        self.assertEqual(len(group_b), 1,
                         f'Servers 005-008 must all be on one leaf, got {group_b}')
        self.assertNotEqual(group_a, group_b,
                            'The two server groups must be on different leaves')
