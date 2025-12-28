"""
Unit tests for uplink port count derivation (SPEC-003).
"""

from django.test import TestCase
from django.core.exceptions import ValidationError

from dcim.models import DeviceType, Manufacturer
from netbox_hedgehog.choices import PortZoneTypeChoices
from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension,
    TopologyPlan,
    PlanSwitchClass,
    SwitchPortZone,
    BreakoutOption,
)
from netbox_hedgehog.utils.topology_calculations import get_uplink_port_count


class GetUplinkPortCountTestCase(TestCase):
    """Tests for get_uplink_port_count()."""

    @classmethod
    def setUpTestData(cls):
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            slug='test',
            defaults={'name': 'Test'}
        )
        cls.device_type, _ = DeviceType.objects.get_or_create(
            slug='test',
            defaults={
                'manufacturer': cls.manufacturer,
                'model': 'Test'
            }
        )
        cls.extension, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.device_type,
            defaults={
                'native_speed': 800,
                'uplink_ports': 4
            }
        )
        cls.plan = TopologyPlan.objects.create(name='test-plan')
        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x800g',
            defaults={
                'from_speed': 800,
                'logical_ports': 1,
                'logical_speed': 800
            }
        )

    def test_override_takes_precedence(self):
        """Explicit override wins (Priority 1)."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.extension,
            switch_class_id='leaf',
            uplink_ports_per_switch=8
        )

        uplink_count = get_uplink_port_count(switch_class)

        self.assertEqual(uplink_count, 8)

    def test_zone_derived_when_no_override(self):
        """Derived from zones when no override is set."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.extension,
            switch_class_id='leaf',
            uplink_ports_per_switch=None
        )

        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='spine-uplinks',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='61-64',
            breakout_option=self.breakout,
            priority=100
        )

        uplink_count = get_uplink_port_count(switch_class)

        self.assertEqual(uplink_count, 4)

    def test_override_takes_precedence_over_zones(self):
        """Override wins even when uplink zones exist."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.extension,
            switch_class_id='leaf',
            uplink_ports_per_switch=6
        )

        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='spine-uplinks',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='61-64',
            breakout_option=self.breakout,
            priority=100
        )

        uplink_count = get_uplink_port_count(switch_class)

        self.assertEqual(uplink_count, 6)

    def test_multiple_uplink_zones_are_summed(self):
        """Multiple uplink zones are aggregated."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.extension,
            switch_class_id='leaf',
            uplink_ports_per_switch=None
        )

        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='spine-uplinks-1',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='61-62',
            breakout_option=self.breakout,
            priority=100
        )
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='spine-uplinks-2',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='63-64',
            breakout_option=self.breakout,
            priority=100
        )

        uplink_count = get_uplink_port_count(switch_class)

        self.assertEqual(uplink_count, 4)

    def test_raises_validation_error_when_no_configuration(self):
        """Raises ValidationError when neither override nor zones exist."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.extension,
            switch_class_id='leaf',
            uplink_ports_per_switch=None
        )

        with self.assertRaises(ValidationError) as cm:
            get_uplink_port_count(switch_class)

        message = str(cm.exception)
        self.assertIn("no uplink capacity defined", message)
        self.assertIn("uplink_ports_per_switch", message)
        self.assertIn("zone_type='uplink'", message)

    def test_override_zero_is_valid(self):
        """Override of 0 is valid for spine-only switches."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.extension,
            switch_class_id='spine',
            uplink_ports_per_switch=0
        )

        uplink_count = get_uplink_port_count(switch_class)

        self.assertEqual(uplink_count, 0)

    def test_deprecated_field_is_ignored(self):
        """DeviceTypeExtension.uplink_ports is ignored for uplink count."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.extension,
            switch_class_id='leaf',
            uplink_ports_per_switch=None
        )

        with self.assertRaises(ValidationError):
            get_uplink_port_count(switch_class)
