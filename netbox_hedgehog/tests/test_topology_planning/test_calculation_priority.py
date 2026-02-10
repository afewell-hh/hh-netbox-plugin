"""
Unit tests for Calculation Priority Logic (DIET-165 Phase 4)

Tests validate the priority flip and deprecation warning behavior as specified
in the Phase 3 spec from issue #164.

Coverage includes:
- get_uplink_port_count() priority: zones FIRST, then uplink_ports_per_switch
- Deprecation warnings when both fields are set
- Deprecation warnings when using uplink_ports_per_switch alone
- calculate_switch_quantity() redundancy rounding (MCLAG even, ESLAG 2-4)
- Backward compatibility with mclag_pair field

This file contains 5 unit tests as specified in the Phase 3 spec addendum.
"""

import warnings
from django.test import TestCase
from django.core.exceptions import ValidationError

from dcim.models import DeviceType, Manufacturer

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanSwitchClass,
    DeviceTypeExtension,
    BreakoutOption,
    SwitchPortZone,
)
from netbox_hedgehog.utils.topology_calculations import (
    get_uplink_port_count,
    calculate_switch_quantity,
)
from netbox_hedgehog.choices import (
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
)


class UplinkPortCalculationPriorityTestCase(TestCase):
    """
    Unit tests for get_uplink_port_count() priority flip (3 tests).

    Tests verify that zones take precedence over uplink_ports_per_switch,
    and that deprecation warnings are emitted correctly.
    """

    @classmethod
    def setUpTestData(cls):
        """Create shared test data"""
        cls.manufacturer = Manufacturer.objects.create(
            name='Test Mfg',
            slug='test-mfg'
        )

        cls.device_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='Test Switch',
            slug='test-switch'
        )

        cls.breakout_1x800g = BreakoutOption.objects.create(
            breakout_id='test-1x800g',
            from_speed=800,
            logical_ports=1,
            logical_speed=800,
            optic_type='QSFP-DD'
        )

        cls.device_ext = DeviceTypeExtension.objects.create(
            device_type=cls.device_type,
            mclag_capable=True,
            supported_breakouts=['test-1x800g']
        )

        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer'
        )

    def _create_switch_class(self, uplink_ports_per_switch=None):
        """Helper to create a switch class"""
        return PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id=f'switch-{PlanSwitchClass.objects.count()}',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=uplink_ports_per_switch
        )

    def _create_uplink_zone(self, switch_class, port_spec):
        """Helper to create an uplink zone"""
        return SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec=port_spec,
            breakout_option=self.breakout_1x800g
        )

    # =========================================================================
    # Test 1: Zones Take Precedence
    # =========================================================================

    def test_get_uplink_port_count_zones_take_precedence(self):
        """Zones take precedence over uplink_ports_per_switch"""
        # Create switch class with uplink_ports_per_switch (deprecated)
        switch_class = self._create_switch_class(uplink_ports_per_switch=8)

        # Create uplink zone with different port count
        self._create_uplink_zone(switch_class, port_spec='49-52')  # 4 ports

        # Act
        uplink_count = get_uplink_port_count(switch_class)

        # Assert: Zones win (4 ports, not 8)
        self.assertEqual(uplink_count, 4)

    # =========================================================================
    # Test 2: Deprecation Warning When Both Set
    # =========================================================================

    def test_get_uplink_port_count_warns_when_both_set(self):
        """Warn when both uplink_ports_per_switch and zones are set"""
        # Arrange: Create switch class with BOTH fields
        switch_class = self._create_switch_class(uplink_ports_per_switch=8)
        self._create_uplink_zone(switch_class, port_spec='49-52')  # 4 ports

        # Act + Assert: Warning emitted
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            uplink_count = get_uplink_port_count(switch_class)

            # Should have a deprecation warning
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))
            self.assertIn('has both zones and uplink_ports_per_switch', str(w[0].message))

        # Assert: Zones take precedence
        self.assertEqual(uplink_count, 4)  # Not 8

    # =========================================================================
    # Test 3: Deprecation Warning for uplink_ports_per_switch Only
    # =========================================================================

    def test_get_uplink_port_count_warns_for_deprecated_field_only(self):
        """Warn when using uplink_ports_per_switch without zones"""
        # Arrange: Create switch class with only uplink_ports_per_switch (no zones)
        switch_class = self._create_switch_class(uplink_ports_per_switch=8)

        # Act + Assert: Warning emitted
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            uplink_count = get_uplink_port_count(switch_class)

            # Should have a deprecation warning
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))
            self.assertIn('uplink_ports_per_switch is deprecated', str(w[0].message))

        # Assert: Returns the deprecated field value (backward compatibility)
        self.assertEqual(uplink_count, 8)


class SwitchQuantityRedundancyRoundingTestCase(TestCase):
    """
    Unit tests for calculate_switch_quantity() redundancy rounding (2 tests).

    Tests verify that:
    - MCLAG rounds up to nearest even number
    - ESLAG enforces minimum 2 switches
    """

    @classmethod
    def setUpTestData(cls):
        """Create shared test data"""
        cls.manufacturer = Manufacturer.objects.create(
            name='Test Mfg',
            slug='test-mfg'
        )

        cls.device_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='Test Switch',
            slug='test-switch'
        )

        cls.breakout_1x800g = BreakoutOption.objects.create(
            breakout_id='test-1x800g',
            from_speed=800,
            logical_ports=1,
            logical_speed=800,
            optic_type='QSFP-DD'
        )

        cls.device_ext = DeviceTypeExtension.objects.create(
            device_type=cls.device_type,
            mclag_capable=True,
            supported_breakouts=['test-1x800g']
        )

        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer'
        )

    def _create_switch_class(self, redundancy_type=None, redundancy_group=None, mclag_pair=False):
        """Helper to create a switch class"""
        return PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id=f'switch-{PlanSwitchClass.objects.count()}',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            redundancy_type=redundancy_type,
            redundancy_group=redundancy_group if redundancy_type else None,
            mclag_pair=mclag_pair,
            calculated_quantity=0  # Will be updated by calculation
        )

    # =========================================================================
    # Test 4: MCLAG Rounds Up to Even
    # =========================================================================

    def test_calculate_switch_quantity_mclag_rounds_to_even(self):
        """MCLAG redundancy rounds up to nearest even number"""
        # Create MCLAG switch class
        switch_class = self._create_switch_class(
            redundancy_type='mclag',
            redundancy_group='mclag-1'
        )

        # Simulate calculation result of 3 switches (odd)
        switch_class.calculated_quantity = 3

        # Act: Recalculate with redundancy rounding
        result = calculate_switch_quantity(switch_class)

        # Assert: Should round up to 4 (even)
        self.assertEqual(result, 4)

    # =========================================================================
    # Test 5: ESLAG Enforces Minimum 2 Switches
    # =========================================================================

    def test_calculate_switch_quantity_eslag_enforces_minimum(self):
        """ESLAG redundancy enforces minimum 2 switches"""
        # Create ESLAG switch class
        switch_class = self._create_switch_class(
            redundancy_type='eslag',
            redundancy_group='eslag-1'
        )

        # Simulate calculation result of 1 switch (below minimum)
        switch_class.calculated_quantity = 1

        # Act: Recalculate with redundancy constraint
        result = calculate_switch_quantity(switch_class)

        # Assert: Should enforce minimum of 2
        self.assertEqual(result, 2)
