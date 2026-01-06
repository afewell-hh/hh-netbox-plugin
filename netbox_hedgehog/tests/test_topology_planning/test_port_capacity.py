"""
Unit tests for zone-based port capacity derivation (SPEC-002).
"""

from django.test import TestCase
from django.core.exceptions import ValidationError

from dcim.models import DeviceType, Manufacturer, InterfaceTemplate
from netbox_hedgehog.choices import PortZoneTypeChoices
from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension,
    PlanSwitchClass,
    SwitchPortZone,
    BreakoutOption,
    TopologyPlan,
)
from netbox_hedgehog.utils.topology_calculations import (
    get_port_capacity_for_connection,
)


def create_interface_templates(
    device_type: DeviceType,
    count: int,
    port_type: str = '100gbase-x-qsfp28',
    name_pattern: str = 'E1/{}'
) -> list[InterfaceTemplate]:
    """Create InterfaceTemplate rows for test device types."""
    return [
        InterfaceTemplate.objects.create(
            device_type=device_type,
            name=name_pattern.format(index),
            type=port_type
        )
        for index in range(1, count + 1)
    ]


class GetPortCapacityForConnectionTestCase(TestCase):
    """Tests for get_port_capacity_for_connection()."""

    @classmethod
    def setUpTestData(cls):
        cls.manufacturer = Manufacturer.objects.create(name='Test', slug='test')

    def _create_plan_and_switch_class(self, extension, uplink_ports_per_switch=0):
        plan = TopologyPlan.objects.create(name='test-plan')
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            device_type_extension=extension,
            switch_class_id='leaf',
            uplink_ports_per_switch=uplink_ports_per_switch
        )
        return plan, switch_class

    def test_zone_based_capacity_returns_zone_speed_and_count(self):
        """When zones exist, returns zone speed and port count."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='ES1000',
            slug='es1000'
        )
        extension = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=1
        )
        _, switch_class = self._create_plan_and_switch_class(extension)

        breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x1g',
            defaults={
                'from_speed': 1,
                'logical_ports': 1,
                'logical_speed': 1
            }
        )
        zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-ports',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=breakout,
            priority=100
        )

        capacity = get_port_capacity_for_connection(
            extension,
            switch_class,
            PortZoneTypeChoices.SERVER
        )

        self.assertEqual(capacity.native_speed, 1)
        self.assertEqual(capacity.port_count, 48)
        self.assertEqual(capacity.source_zone, zone)
        self.assertFalse(capacity.is_fallback)

    def test_fallback_when_no_zones_defined(self):
        """When no zones exist, use native_speed and InterfaceTemplate count."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='DS5000',
            slug='ds5000'
        )
        create_interface_templates(
            device_type,
            64,
            port_type='800gbase-x-qsfp-dd'
        )
        extension = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=800
        )
        _, switch_class = self._create_plan_and_switch_class(extension)

        capacity = get_port_capacity_for_connection(
            extension,
            switch_class,
            PortZoneTypeChoices.SERVER
        )

        self.assertEqual(capacity.native_speed, 800)
        self.assertEqual(capacity.port_count, 64)
        self.assertIsNone(capacity.source_zone)
        self.assertTrue(capacity.is_fallback)

    def test_raises_validation_error_for_invalid_connection_type(self):
        """Invalid connection_type raises ValidationError."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='Test',
            slug='test'
        )
        extension = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=800
        )
        _, switch_class = self._create_plan_and_switch_class(extension)

        with self.assertRaises(ValidationError) as cm:
            get_port_capacity_for_connection(extension, switch_class, 'invalid_type')

        message = str(cm.exception)
        self.assertIn("Invalid connection_type", message)
        self.assertIn("server, uplink, fabric", message)

    def test_raises_validation_error_when_zone_missing_breakout_option(self):
        """Zone without breakout_option raises ValidationError."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='Test',
            slug='test'
        )
        extension = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=800
        )
        _, switch_class = self._create_plan_and_switch_class(extension)

        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='incomplete-zone',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=None,
            priority=100
        )

        with self.assertRaises(ValidationError) as cm:
            get_port_capacity_for_connection(
                extension,
                switch_class,
                PortZoneTypeChoices.SERVER
            )

        self.assertIn("no breakout_option defined", str(cm.exception))

    def test_raises_validation_error_when_no_zones_and_no_native_speed(self):
        """No zones + no native_speed raises ValidationError."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='Incomplete',
            slug='incomplete'
        )
        extension = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=None
        )
        _, switch_class = self._create_plan_and_switch_class(extension)

        with self.assertRaises(ValidationError) as cm:
            get_port_capacity_for_connection(
                extension,
                switch_class,
                PortZoneTypeChoices.SERVER
            )

        self.assertIn("no zones and no native_speed", str(cm.exception))

    def test_mixed_port_switch_es1000_returns_correct_zone_speeds(self):
        """ES1000 returns different speeds per server/uplink zones."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='ES1000-48',
            slug='es1000-48'
        )
        extension = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=1
        )
        _, switch_class = self._create_plan_and_switch_class(
            extension,
            uplink_ports_per_switch=4
        )

        breakout_1g, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x1g',
            defaults={
                'from_speed': 1,
                'logical_ports': 1,
                'logical_speed': 1
            }
        )
        breakout_25g, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x25g',
            defaults={
                'from_speed': 25,
                'logical_ports': 1,
                'logical_speed': 25
            }
        )

        server_zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-ports',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=breakout_1g,
            priority=100
        )
        uplink_zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='spine-uplinks',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='49-52',
            breakout_option=breakout_25g,
            priority=100
        )

        server_capacity = get_port_capacity_for_connection(
            extension,
            switch_class,
            PortZoneTypeChoices.SERVER
        )
        self.assertEqual(server_capacity.native_speed, 1)
        self.assertEqual(server_capacity.port_count, 48)
        self.assertEqual(server_capacity.source_zone, server_zone)

        uplink_capacity = get_port_capacity_for_connection(
            extension,
            switch_class,
            PortZoneTypeChoices.UPLINK
        )
        self.assertEqual(uplink_capacity.native_speed, 25)
        self.assertEqual(uplink_capacity.port_count, 4)
        self.assertEqual(uplink_capacity.source_zone, uplink_zone)

    def test_zone_priority_ordering(self):
        """Uses highest priority (lowest number) zone when multiple exist."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='Test',
            slug='test'
        )
        extension = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=800
        )
        _, switch_class = self._create_plan_and_switch_class(extension)

        breakout_100g, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x100g',
            defaults={
                'from_speed': 100,
                'logical_ports': 1,
                'logical_speed': 100
            }
        )
        breakout_200g, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x200g',
            defaults={
                'from_speed': 200,
                'logical_ports': 1,
                'logical_speed': 200
            }
        )

        high_priority_zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='zone-high-priority',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-32',
            breakout_option=breakout_200g,
            priority=50
        )
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='zone-low-priority',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='33-48',
            breakout_option=breakout_100g,
            priority=200
        )

        capacity = get_port_capacity_for_connection(
            extension,
            switch_class,
            PortZoneTypeChoices.SERVER
        )

        self.assertEqual(capacity.source_zone, high_priority_zone)
        self.assertEqual(capacity.native_speed, 200)
        self.assertEqual(capacity.port_count, 32)
