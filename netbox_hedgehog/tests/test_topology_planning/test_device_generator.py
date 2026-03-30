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


# =============================================================================
# DIET-322: same-switch grouped-per-leaf allocation unit tests
# =============================================================================

class SameSwitchGroupingUnitTestCase(TestCase):
    """Unit tests for _select_switch_instance() same-switch grouped placement.

    Uses plain Python objects as stand-ins for Device instances since the
    method only indexes into the list — no ORM calls are made.

    Regression guard for issue #322: previously the method used
    `server_index % num_switches` (round-robin); it must now use
    contiguous grouped allocation so single-homed scale-out variants
    cable correctly.
    """

    def setUp(self):
        # Minimal plan needed to instantiate the generator
        self.plan = TopologyPlan(name="unit-test-plan")
        self.gen = DeviceGenerator.__new__(DeviceGenerator)
        self.gen.plan = self.plan

    def _select(self, switches, distribution, server_index, port_index,
                total_servers=None, rail=None, total_rails=None):
        return self.gen._select_switch_instance(
            switch_instances=switches,
            distribution=distribution,
            server_index=server_index,
            port_index=port_index,
            total_servers=total_servers,
            rail=rail,
            total_rails=total_rails,
        )

    # --- same-switch: even split (8 servers, 2 leaves → 4/4) ---

    def test_same_switch_8_servers_2_leaves_servers_0_3_go_to_leaf_a(self):
        """First 4 of 8 servers must all map to leaf A (issue #322)."""
        leaves = ["leaf-a", "leaf-b"]
        for idx in range(4):
            result = self._select(leaves, "same-switch", idx, 0, total_servers=8)
            self.assertEqual(result, "leaf-a",
                             f"server_index={idx} should be on leaf-a, got {result}")

    def test_same_switch_8_servers_2_leaves_servers_4_7_go_to_leaf_b(self):
        """Last 4 of 8 servers must all map to leaf B (issue #322)."""
        leaves = ["leaf-a", "leaf-b"]
        for idx in range(4, 8):
            result = self._select(leaves, "same-switch", idx, 0, total_servers=8)
            self.assertEqual(result, "leaf-b",
                             f"server_index={idx} should be on leaf-b, got {result}")

    # --- same-switch: odd count (7 servers → 4 on A, 3 on B) ---

    def test_same_switch_7_servers_2_leaves_first_switch_gets_extra(self):
        """Odd count: ceil(7/2)=4, so leaf-A gets servers 0-3, leaf-B gets 4-6."""
        leaves = ["leaf-a", "leaf-b"]
        expected = ["leaf-a"] * 4 + ["leaf-b"] * 3
        for idx, exp in enumerate(expected):
            result = self._select(leaves, "same-switch", idx, 0, total_servers=7)
            self.assertEqual(result, exp,
                             f"server_index={idx}: expected {exp}, got {result}")

    # --- same-switch: 3 servers, 2 leaves → 2/1 ---

    def test_same_switch_3_servers_2_leaves(self):
        """3 servers, 2 leaves: ceil(3/2)=2, so servers 0-1 → leaf-A, server 2 → leaf-B."""
        leaves = ["leaf-a", "leaf-b"]
        self.assertEqual(self._select(leaves, "same-switch", 0, 0, total_servers=3), "leaf-a")
        self.assertEqual(self._select(leaves, "same-switch", 1, 0, total_servers=3), "leaf-a")
        self.assertEqual(self._select(leaves, "same-switch", 2, 0, total_servers=3), "leaf-b")

    # --- same-switch: single switch always returns it ---

    def test_same_switch_single_leaf_always_returns_it(self):
        """With one leaf, all servers land there regardless of total_servers."""
        leaves = ["only-leaf"]
        for idx in range(8):
            result = self._select(leaves, "same-switch", idx, 0, total_servers=8)
            self.assertEqual(result, "only-leaf")

    # --- same-switch: ports_per_connection >1 (all ports for one server stay on same leaf) ---

    def test_same_switch_multi_port_stays_on_same_leaf(self):
        """All 8 ports of server_index=0 must hit leaf-A (port_index is irrelevant)."""
        leaves = ["leaf-a", "leaf-b"]
        for port_idx in range(8):
            result = self._select(leaves, "same-switch", 0, port_idx, total_servers=8)
            self.assertEqual(result, "leaf-a")

    # --- alternating unchanged ---

    def test_alternating_still_round_robins_by_port_index(self):
        """alternating must still rotate by port_index (regression guard)."""
        leaves = ["leaf-a", "leaf-b"]
        self.assertEqual(self._select(leaves, "alternating", 0, 0), "leaf-a")
        self.assertEqual(self._select(leaves, "alternating", 0, 1), "leaf-b")
        self.assertEqual(self._select(leaves, "alternating", 0, 2), "leaf-a")
        self.assertEqual(self._select(leaves, "alternating", 1, 0), "leaf-a")
        self.assertEqual(self._select(leaves, "alternating", 1, 1), "leaf-b")


# =============================================================================
# DIET-322: integration test — grouped-per-leaf cabling
# =============================================================================

class SameSwitchGroupingIntegrationTestCase(TestCase):
    """Integration test: generate_all() groups servers per leaf for same-switch.

    Sets up a plan with 2 leaf instances and 8 servers, then verifies that the
    generated cables are grouped (servers 1-4 → leaf-1, servers 5-8 → leaf-2),
    not alternated.
    """

    @classmethod
    def setUpTestData(cls):
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'},
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
                'native_speed': 800,
                'uplink_ports': 0,
            },
        )
        cls.plan = TopologyPlan.objects.create(name='SH Grouping Test Plan')

        # 2 leaf instances
        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='scale-out-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=cls.ext,
            uplink_ports_per_switch=0,
            calculated_quantity=2,
        )
        cls.zone = SwitchPortZone.objects.create(
            switch_class=cls.switch_class,
            zone_name='scale-out-server',
            zone_type='server',
            port_spec='1-32',
            allocation_strategy='sequential',
        )
        # 8 servers
        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='compute-xpu',
            server_device_type=cls.server_type,
            quantity=8,
        )
        cls.connection = PlanServerConnection.objects.create(
            server_class=cls.server_class,
            connection_id='scale-out',
            nic=get_test_server_nic(cls.server_class),
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type='unbundled',
            distribution='same-switch',
            target_zone=cls.zone,
            speed=400,
        )

    def test_same_switch_groups_servers_per_leaf(self):
        """8 servers × same-switch × 2 leaves must produce 4/4 grouped cabling."""
        generator = DeviceGenerator(self.plan)
        generator.generate_all()

        # Collect which switch each server is cabled to
        server_to_switch = {}
        for cable in Cable.objects.filter(tags__slug='hedgehog-generated'):
            # Each cable has two terminations; find server side and switch side
            a_dev = cable.a_terminations[0].device if cable.a_terminations else None
            b_dev = cable.b_terminations[0].device if cable.b_terminations else None
            if a_dev and b_dev:
                if a_dev.role.slug == 'server':
                    server_to_switch[a_dev.name] = b_dev.name
                elif b_dev.role.slug == 'server':
                    server_to_switch[b_dev.name] = a_dev.name

        self.assertEqual(len(server_to_switch), 8,
                         "Expected 8 server→switch cable mappings")

        # Servers sorted by index to get stable assignment
        servers_sorted = sorted(server_to_switch.keys())
        group_a = {server_to_switch[s] for s in servers_sorted[:4]}
        group_b = {server_to_switch[s] for s in servers_sorted[4:]}

        # Each group must be on a single switch
        self.assertEqual(len(group_a), 1,
                         f"Servers 1-4 must all be on one leaf, got {group_a}")
        self.assertEqual(len(group_b), 1,
                         f"Servers 5-8 must all be on one leaf, got {group_b}")

        # The two groups must be on different switches
        self.assertNotEqual(group_a, group_b,
                            "The two server groups must be on different leaves")
