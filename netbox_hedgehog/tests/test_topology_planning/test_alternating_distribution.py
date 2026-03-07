"""
Unit and regression tests for alternating distribution minimum-2 switch enforcement.

Issue: #244 — Fix: alternating distribution enforces minimum 2 switches in
calculate_switch_quantity().

Root cause: calculate_switch_quantity() ignored distribution='alternating', so
when port demand fit on 1 switch and no redundancy_type was set, only 1 switch
was allocated. DeviceGenerator fast-exits on a single switch, collapsing the
HA intent silently.

Fix: After capacity math, if any connection uses distribution='alternating' and
switches_needed < 2, force switches_needed = 2.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from dcim.models import DeviceType, Manufacturer

from netbox_hedgehog.choices import (
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
)
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
from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type


PLAN_NAME_128GPU = "UX Case 128GPU Odd Ports"


class AlternatingDistributionMinTwoTestCase(TestCase):
    """
    Tests that distribution=alternating enforces a minimum of 2 switches
    when capacity math alone would yield 1.

    Uses a small switch (12-port server zone) with low server counts so that
    raw capacity math always resolves to 1 switch, isolating the alternating
    enforcement as the only reason to go to 2.
    """

    @classmethod
    def setUpTestData(cls):
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Test-Alt-Mfg', defaults={'slug': 'test-alt-mfg'}
        )

        # Small switch device type (DS3000-like: 32x100G ports)
        cls.device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='Test-Alt-Switch',
            defaults={'slug': 'test-alt-switch'},
        )

        # Breakout for 100G server zone — 1x100G (no breakout, native 100G)
        cls.breakout_1x100g, _ = BreakoutOption.objects.get_or_create(
            breakout_id='test-alt-1x100g',
            defaults={'from_speed': 100, 'logical_ports': 1, 'logical_speed': 100},
        )

        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.device_type,
            defaults={
                'mclag_capable': False,
                'supported_breakouts': ['test-alt-1x100g'],
                'native_speed': 100,
            },
        )

        # Server device type (arbitrary, just needed for FK)
        cls.server_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='Test-Alt-Server',
            defaults={'slug': 'test-alt-server'},
        )

    def setUp(self):
        self.plan = TopologyPlan.objects.create(
            name=f'Alt-Test-Plan-{self._testMethodName}',
            customer_name='Test Customer',
        )

    def _make_switch_class(self, switch_class_id='border-leaf', redundancy_type=None,
                           redundancy_group=None, mclag_pair=False):
        return PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id=switch_class_id,
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=0,
            mclag_pair=mclag_pair,
            redundancy_type=redundancy_type,
            redundancy_group=redundancy_group if redundancy_type else None,
        )

    def _make_server_zone(self, switch_class, zone_name='downlinks', port_spec='1-12'):
        """Server zone with 12 x 100G ports — large enough that 1-2 servers fit on 1 switch."""
        return SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name=zone_name,
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec=port_spec,
            breakout_option=self.breakout_1x100g,
        )

    def _make_server_class(self, server_class_id='ctrl', quantity=1):
        return PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id=server_class_id,
            server_device_type=self.server_device_type,
            quantity=quantity,
        )

    def _make_connection(self, server_class, zone, distribution, ports_per_connection=2,
                         speed=100, connection_id='conn'):
        return PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id=connection_id,
            nic_module_type=get_test_nic_module_type(),
            port_index=0,
            ports_per_connection=ports_per_connection,
            hedgehog_conn_type='unbundled',
            distribution=distribution,
            target_zone=zone,
            speed=speed,
        )

    # =========================================================================
    # Test 1: alternating enforces minimum 2 even when capacity fits on 1
    # =========================================================================

    def test_alternating_enforces_minimum_two_switches(self):
        """
        When distribution=alternating and capacity math yields 1 switch,
        calculate_switch_quantity() must return 2.

        Setup: 12-port zone, 1 server × 2 ports = 2 demand → ceil(2/12) = 1.
        Expectation: 2 (alternating minimum-2 enforcement).
        """
        switch_class = self._make_switch_class()
        zone = self._make_server_zone(switch_class)
        server_class = self._make_server_class(quantity=1)
        self._make_connection(server_class, zone, distribution='alternating', ports_per_connection=2)

        result = calculate_switch_quantity(switch_class)

        self.assertEqual(result, 2, (
            "distribution=alternating with demand fitting on 1 switch should "
            "enforce a minimum of 2 switches for HA redundancy"
        ))

    # =========================================================================
    # Test 2: alternating does NOT reduce capacity-driven count above 2
    # =========================================================================

    def test_alternating_does_not_reduce_capacity_driven_count(self):
        """
        When alternating demand naturally requires 3 switches, the result
        should be 3 — not forced back down to 2.

        Setup: 12-port zone, 7 servers × 2 ports = 14 demand → ceil(14/12) = 2.
        But adding a second server class with 7 more → 28 total → ceil(28/12) = 3.
        Expectation: 3 (capacity drives the count, alternating floor does not reduce it).
        """
        switch_class = self._make_switch_class()
        zone = self._make_server_zone(switch_class)

        server_a = self._make_server_class(server_class_id='ctrl-a', quantity=7)
        server_b = self._make_server_class(server_class_id='ctrl-b', quantity=7)
        self._make_connection(server_a, zone, distribution='alternating',
                              ports_per_connection=2, connection_id='conn-a')
        self._make_connection(server_b, zone, distribution='alternating',
                              ports_per_connection=2, connection_id='conn-b')

        result = calculate_switch_quantity(switch_class)

        # 14 + 14 = 28 demand, 12 available → ceil(28/12) = 3
        self.assertEqual(result, 3, (
            "Alternating floor should not reduce a capacity-driven count above 2"
        ))

    # =========================================================================
    # Test 3: non-alternating small demand stays at 1 (Dev C guardrail)
    # =========================================================================

    def test_non_alternating_unbundled_unaffected(self):
        """
        Switch classes with no alternating connections are not affected.
        Small demand with same-switch distribution should still return 1.

        Dev C guardrail: alternating enforcement must not apply globally.
        """
        switch_class = self._make_switch_class()
        zone = self._make_server_zone(switch_class)
        server_class = self._make_server_class(quantity=1)
        self._make_connection(server_class, zone, distribution='same-switch',
                              ports_per_connection=2)

        result = calculate_switch_quantity(switch_class)

        self.assertEqual(result, 1, (
            "same-switch distribution with small demand should return 1; "
            "alternating minimum-2 rule must not apply to non-alternating classes"
        ))

    # =========================================================================
    # Test 4: mixed alternating + unbundled — alternating wins
    # =========================================================================

    def test_mixed_alternating_and_unbundled_returns_two(self):
        """
        When a switch class has both alternating and same-switch connections,
        and total demand fits on 1 switch, the alternating connection triggers
        the minimum-2 enforcement.
        """
        switch_class = self._make_switch_class()
        zone = self._make_server_zone(switch_class)

        server_a = self._make_server_class(server_class_id='alt-server', quantity=1)
        server_b = self._make_server_class(server_class_id='same-server', quantity=1)
        # 1×2 + 1×2 = 4 total demand, 12 available → capacity math = 1
        self._make_connection(server_a, zone, distribution='alternating',
                              ports_per_connection=2, connection_id='conn-alt')
        self._make_connection(server_b, zone, distribution='same-switch',
                              ports_per_connection=2, connection_id='conn-same')

        result = calculate_switch_quantity(switch_class)

        self.assertEqual(result, 2, (
            "Presence of any alternating connection should enforce minimum 2 "
            "even when mixed with same-switch connections"
        ))

    # =========================================================================
    # Test 5: alternating + MCLAG redundancy_type — compatible, both enforce 2
    # =========================================================================

    def test_alternating_with_mclag_redundancy_type(self):
        """
        When distribution=alternating and redundancy_type=mclag are both set,
        both enforce a minimum of 2. The result must be at least 2 and even.
        """
        switch_class = self._make_switch_class(
            redundancy_type='mclag',
            redundancy_group='mclag-border',
        )
        zone = self._make_server_zone(switch_class)
        server_class = self._make_server_class(quantity=1)
        self._make_connection(server_class, zone, distribution='alternating',
                              ports_per_connection=2)

        result = calculate_switch_quantity(switch_class)

        self.assertEqual(result, 2, (
            "alternating + MCLAG should both enforce minimum 2; "
            "MCLAG even-rounding still applies after alternating floor"
        ))
        self.assertEqual(result % 2, 0, "MCLAG result must always be even")


class AlternatingDistribution128GpuRegressionTestCase(TestCase):
    """
    Regression guard: the canonical 128GPU case must allocate 2 fe-border-leaf
    switches after the alternating minimum-2 fix.

    Before fix: capacity math yields 1 (small demand fits on 1 DS3000).
    After fix:  alternating connections force calculate_switch_quantity() to 2.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_case_128gpu_odd_ports", stdout=StringIO())
        from netbox_hedgehog.models.topology_planning import TopologyPlan
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME_128GPU)

    def test_128gpu_border_leaf_allocates_two_switches(self):
        """
        fe-border-leaf has 5 server connection types all with distribution=alternating.
        Demand is small (1-3 servers each), so capacity math alone yields 1.
        After fix, calculate_switch_quantity() must return 2.
        """
        border_leaf = PlanSwitchClass.objects.get(
            plan=self.plan,
            switch_class_id='fe-border-leaf',
        )

        result = calculate_switch_quantity(border_leaf)

        self.assertEqual(result, 2, (
            "fe-border-leaf has alternating connections with small demand; "
            "calculate_switch_quantity() must return 2 after the alternating "
            "minimum-2 enforcement fix (issue #244)"
        ))
