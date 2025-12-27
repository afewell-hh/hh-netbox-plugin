"""
Unit tests for get_physical_port_count() helper.

These tests define expected behavior for deriving port counts from
InterfaceTemplate data with a safe fallback for legacy device types.
"""

from django.test import TestCase

from dcim.models import DeviceType, Manufacturer, InterfaceTemplate
from netbox_hedgehog.utils.topology_calculations import get_physical_port_count


def create_interface_templates(
    device_type: DeviceType,
    count: int,
    port_type: str = '100gbase-x-qsfp28',
    name_pattern: str = 'Ethernet1/{}'
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


class GetPhysicalPortCountTestCase(TestCase):
    """Tests for get_physical_port_count()."""

    @classmethod
    def setUpTestData(cls):
        cls.manufacturer = Manufacturer.objects.create(name='Test', slug='test')

    def test_returns_64_for_device_type_with_64_templates(self):
        """Returns 64 for DS5000-style device types."""
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

        port_count = get_physical_port_count(device_type)

        self.assertEqual(port_count, 64)

    def test_returns_32_for_device_type_with_32_templates(self):
        """Returns 32 for DS3000-style device types."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='DS3000',
            slug='ds3000'
        )
        create_interface_templates(
            device_type,
            32,
            port_type='100gbase-x-qsfp28'
        )

        port_count = get_physical_port_count(device_type)

        self.assertEqual(port_count, 32)

    def test_returns_52_for_mixed_port_device_type(self):
        """Counts all InterfaceTemplates for mixed-port switches."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='ES1000-48',
            slug='es1000-48'
        )
        create_interface_templates(device_type, 48, port_type='1000base-t')
        create_interface_templates(
            device_type,
            4,
            port_type='25gbase-x-sfp28',
            name_pattern='Ethernet1/5{}'
        )

        port_count = get_physical_port_count(device_type)

        self.assertEqual(port_count, 52)

    def test_returns_64_fallback_when_no_templates_defined(self):
        """Returns fallback value when no templates exist."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='Legacy-Switch',
            slug='legacy-switch'
        )

        port_count = get_physical_port_count(device_type)

        self.assertEqual(port_count, 64)
