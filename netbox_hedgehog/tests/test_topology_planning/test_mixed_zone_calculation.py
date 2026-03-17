"""
DIET-319 RED: Mixed-zone switch quantity calculation

Tests that expose the current bug where calculate_switch_quantity() aggregates
demand across all server zones and uses only the first zone's capacity, producing
wrong results when a switch class has multiple server zones with different breakouts.

Correct algorithm: per-zone demand / per-zone capacity → max() across zones.

Tests
-----
T1 test_conv_leaf_mixed_zones_two_switches_needed
    OPG-64 conv_leaf reproducer. Two zones: 400G and 200G. Both need 2 switches.
    Current code sums demand and divides by first zone → returns 4. Correct: 2.
    STATUS: RED — fails with current implementation.

T2 test_single_zone_baseline_unchanged
    Single server zone. Verifies the refactor does not break the common case.
    STATUS: GREEN baseline — passes with current implementation.

T3 test_multi_zone_dominant_zone_wins
    Two zones; zone A needs 3 switches, zone B needs 1. max() must select 3.
    Current code sums demand → returns 4. Correct: 3.
    STATUS: RED — fails with current implementation.

T4 test_alternating_min_two_preserved_after_max
    Both zones each need 1 switch (max()=1), but one connection uses
    distribution='alternating'. The post-max min-2 guard must bump to 2.
    STATUS: GREEN baseline — passes with current implementation.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model

from dcim.models import DeviceType, Manufacturer

from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.utils.topology_calculations import calculate_switch_quantity
from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic

User = get_user_model()


class MixedZoneCalculationTestCase(TestCase):
    """
    Switch quantity calculation with multiple server zones per switch class.

    All tests use zone-based capacity (is_fallback=False), meaning uplink port
    subtraction is skipped and capacity comes directly from zone port_spec × breakout.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='test-mixed-zone')

        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica-MZ', defaults={'slug': 'celestica-mz'}
        )

        # DS5000-like switch: 800G native ports
        cls.switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000-MZ',
            defaults={'slug': 'ds5000-mz', 'u_height': 1}
        )
        cls.switch_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_dt,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'supported_breakouts': ['1x800g', '2x400g', '4x200g'],
                'native_speed': 800,
            }
        )

        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='GPU-Server-MZ',
            defaults={'slug': 'gpu-server-mz', 'u_height': 2}
        )

        # Breakout options needed by the tests
        cls.b_2x400, _ = BreakoutOption.objects.get_or_create(
            breakout_id='2x400g',
            defaults={'from_speed': 800, 'logical_ports': 2, 'logical_speed': 400}
        )
        cls.b_4x200, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200}
        )
        cls.b_2x400_400native, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x400g',
            defaults={'from_speed': 400, 'logical_ports': 1, 'logical_speed': 400}
        )

    def setUp(self):
        self.plan = TopologyPlan.objects.create(
            name='Mixed-Zone Test Plan',
            customer_name='Test Customer',
            created_by=self.user,
        )

    # ------------------------------------------------------------------
    # T1 — OPG-64 conv_leaf reproducer (RED: currently returns 4, want 2)
    # ------------------------------------------------------------------

    def test_conv_leaf_mixed_zones_two_switches_needed(self):
        """
        OPG-64 conv_leaf: two server zones with different breakouts.

        Zone layout (per switch instance):
          zone-400g: ports 1-16 (16 physical), b_2x400 → 16 × 2 = 32 logical 400G
          zone-200g: ports 17-22 (6 physical), b_4x200 → 6 × 4 = 24 logical 200G

        Demand:
          connection-A → zone-400g: 8 servers × 8 ports = 64 × 400G
            zone requirement: ceil(64 / 32) = 2 switches
          connection-B → zone-200g: 9 servers × 4 ports = 36 × 200G
            zone requirement: ceil(36 / 24) = 2 switches

        Correct answer: max(2, 2) = 2

        Current (buggy) answer:
          total_ports_needed = 64 + 36 = 100 (mixed units!)
          capacity = zone-400g first by priority → 32
          result = ceil(100 / 32) = 4   ← wrong
        """
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='conv-leaf',
            fabric_name='backend',
            fabric_class='managed',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_ext,
        )

        zone_400g = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='zone-400g',
            zone_type='server',
            port_spec='1-16',
            breakout_option=self.b_2x400,
            priority=10,
        )
        zone_200g = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='zone-200g',
            zone_type='server',
            port_spec='17-22',
            breakout_option=self.b_4x200,
            priority=20,
        )

        server_a = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='be-gpu',
            server_device_type=self.server_dt,
            quantity=8,
        )
        PlanServerConnection.objects.create(
            server_class=server_a,
            connection_id='conn-be-400g',
            nic=get_test_server_nic(server_a, nic_id='nic-be'),
            port_index=0,
            ports_per_connection=8,
            hedgehog_conn_type='unbundled',
            distribution='same-switch',
            target_zone=zone_400g,
            speed=400,
        )

        server_b = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='conv-server',
            server_device_type=self.server_dt,
            quantity=9,
        )
        PlanServerConnection.objects.create(
            server_class=server_b,
            connection_id='conn-conv-200g',
            nic=get_test_server_nic(server_b, nic_id='nic-conv'),
            port_index=0,
            ports_per_connection=4,
            hedgehog_conn_type='unbundled',
            distribution='same-switch',
            target_zone=zone_200g,
            speed=200,
        )

        result = calculate_switch_quantity(switch_class)

        # RED: current code returns 4 (demand mixed, single-zone denominator)
        self.assertEqual(result, 2)

    # ------------------------------------------------------------------
    # T2 — single-zone baseline (GREEN baseline: must stay passing)
    # ------------------------------------------------------------------

    def test_single_zone_baseline_unchanged(self):
        """
        Single server zone: per-zone algorithm degenerates to current behaviour.

        Zone layout (per switch):
          zone-400g: ports 1-32 (32 physical), b_2x400 → 64 logical 400G

        Demand: 8 servers × 8 ports = 64 × 400G
          zone requirement: ceil(64 / 64) = 1 switch

        Correct: 1. Current code also returns 1 (no mixing bug).
        This test verifies the refactor does not regress the single-zone path.
        """
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='single-zone-leaf',
            fabric_name='backend',
            fabric_class='managed',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_ext,
        )

        zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='zone-400g',
            zone_type='server',
            port_spec='1-32',
            breakout_option=self.b_2x400,
            priority=10,
        )

        server = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='be-gpu-single',
            server_device_type=self.server_dt,
            quantity=8,
        )
        PlanServerConnection.objects.create(
            server_class=server,
            connection_id='conn-single',
            nic=get_test_server_nic(server, nic_id='nic-single'),
            port_index=0,
            ports_per_connection=8,
            hedgehog_conn_type='unbundled',
            distribution='same-switch',
            target_zone=zone,
            speed=400,
        )

        result = calculate_switch_quantity(switch_class)
        self.assertEqual(result, 1)

    # ------------------------------------------------------------------
    # T3 — dominant zone wins via max() (RED: currently returns 4, want 3)
    # ------------------------------------------------------------------

    def test_multi_zone_dominant_zone_wins(self):
        """
        Two zones; zone A dominates and max() must select its requirement.

        Zone layout (per switch):
          zone-400g: ports 1-16 (16 physical), b_2x400 → 32 logical 400G
          zone-200g: ports 17-22 (6 physical), b_4x200 → 24 logical 200G

        Demand:
          connection-A → zone-400g: 12 servers × 8 ports = 96 × 400G
            zone requirement: ceil(96 / 32) = 3 switches
          connection-B → zone-200g: 1 server × 10 ports = 10 × 200G
            zone requirement: ceil(10 / 24) = 1 switch

        Correct answer: max(3, 1) = 3

        Current (buggy) answer:
          total_ports_needed = 96 + 10 = 106 (mixed!)
          capacity = zone-400g → 32 logical 400G
          result = ceil(106 / 32) = 4   ← wrong
        """
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='dominant-zone-leaf',
            fabric_name='backend',
            fabric_class='managed',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_ext,
        )

        zone_400g = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='zone-400g',
            zone_type='server',
            port_spec='1-16',
            breakout_option=self.b_2x400,
            priority=10,
        )
        zone_200g = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='zone-200g',
            zone_type='server',
            port_spec='17-22',
            breakout_option=self.b_4x200,
            priority=20,
        )

        server_a = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='be-gpu-dom',
            server_device_type=self.server_dt,
            quantity=12,
        )
        PlanServerConnection.objects.create(
            server_class=server_a,
            connection_id='conn-dom-400g',
            nic=get_test_server_nic(server_a, nic_id='nic-dom-a'),
            port_index=0,
            ports_per_connection=8,
            hedgehog_conn_type='unbundled',
            distribution='same-switch',
            target_zone=zone_400g,
            speed=400,
        )

        server_b = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='conv-server-dom',
            server_device_type=self.server_dt,
            quantity=1,
        )
        PlanServerConnection.objects.create(
            server_class=server_b,
            connection_id='conn-dom-200g',
            nic=get_test_server_nic(server_b, nic_id='nic-dom-b'),
            port_index=0,
            ports_per_connection=10,
            hedgehog_conn_type='unbundled',
            distribution='same-switch',
            target_zone=zone_200g,
            speed=200,
        )

        result = calculate_switch_quantity(switch_class)

        # RED: current code returns 4 (summed demand / first zone)
        self.assertEqual(result, 3)

    # ------------------------------------------------------------------
    # T4 — alternating min-2 guard still applies after max() (GREEN baseline)
    # ------------------------------------------------------------------

    def test_alternating_min_two_preserved_after_max(self):
        """
        Both zones need 1 switch (max()=1). A connection with distribution='alternating'
        must trigger the existing min-2 guard, yielding 2.

        Zone layout (per switch):
          zone-400g: ports 1-16 (16 physical), b_2x400 → 32 logical 400G
          zone-200g: ports 17-22 (6 physical), b_4x200 → 24 logical 200G

        Demand:
          connection-A (alternating) → zone-400g: 2 servers × 4 ports = 8 × 400G
            zone requirement: ceil(8 / 32) = 1
          connection-B → zone-200g: 2 servers × 4 ports = 8 × 200G
            zone requirement: ceil(8 / 24) = 1

        max(1, 1) = 1; alternating guard → bumps to 2.

        Correct: 2. Current code also returns 2 (happens to agree via coincidence).
        This test verifies the alternating guard survives the refactor.
        """
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='alternating-leaf',
            fabric_name='backend',
            fabric_class='managed',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_ext,
        )

        zone_400g = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='zone-400g',
            zone_type='server',
            port_spec='1-16',
            breakout_option=self.b_2x400,
            priority=10,
        )
        zone_200g = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='zone-200g',
            zone_type='server',
            port_spec='17-22',
            breakout_option=self.b_4x200,
            priority=20,
        )

        server_a = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='be-gpu-alt',
            server_device_type=self.server_dt,
            quantity=2,
        )
        # alternating connection → triggers min-2 guard
        PlanServerConnection.objects.create(
            server_class=server_a,
            connection_id='conn-alt-400g',
            nic=get_test_server_nic(server_a, nic_id='nic-alt-a'),
            port_index=0,
            ports_per_connection=4,
            hedgehog_conn_type='unbundled',
            distribution='alternating',
            target_zone=zone_400g,
            speed=400,
        )

        server_b = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='conv-server-alt',
            server_device_type=self.server_dt,
            quantity=2,
        )
        PlanServerConnection.objects.create(
            server_class=server_b,
            connection_id='conn-alt-200g',
            nic=get_test_server_nic(server_b, nic_id='nic-alt-b'),
            port_index=0,
            ports_per_connection=4,
            hedgehog_conn_type='unbundled',
            distribution='same-switch',
            target_zone=zone_200g,
            speed=200,
        )

        result = calculate_switch_quantity(switch_class)

        # Both zones need 1 switch; alternating guard bumps to 2
        self.assertEqual(result, 2)
