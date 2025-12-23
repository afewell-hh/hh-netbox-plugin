"""
Tests for the PortAllocatorV2 service.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from dcim.models import DeviceType, Manufacturer

from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services.port_allocator import PortAllocatorV2


class PortAllocatorV2TestCase(TestCase):
    """Test suite for PortAllocatorV2"""

    @classmethod
    def setUpTestData(cls):
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'},
        )

        cls.switch_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={
                'slug': 'ds5000',
                'u_height': 1,
                'is_full_depth': True,
            },
        )

        cls.device_type_extension, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_device_type,
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
            device_type_extension=cls.device_type_extension,
            uplink_ports_per_switch=4,
        )

    def test_allocate_sequential_without_breakout(self):
        """Sequential allocation should walk ports in order."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-4',
            allocation_strategy='sequential',
        )

        allocator = PortAllocatorV2()
        first = allocator.allocate('fe-leaf-01', zone, 2)
        second = allocator.allocate('fe-leaf-01', zone, 2)

        self.assertEqual([slot.name for slot in first], ['E1/1', 'E1/2'])
        self.assertEqual([slot.name for slot in second], ['E1/3', 'E1/4'])

    def test_allocate_with_breakout_expands_logical_ports(self):
        """Breakout options should expand logical ports before allocation."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-2',
            breakout_option=self.breakout_4x200g,
            allocation_strategy='sequential',
        )

        allocator = PortAllocatorV2()
        allocated = allocator.allocate('fe-leaf-01', zone, 5)

        self.assertEqual(
            [slot.name for slot in allocated],
            ['E1/1/1', 'E1/1/2', 'E1/1/3', 'E1/1/4', 'E1/2/1'],
        )

    def test_interleaved_allocation_orders_by_index(self):
        """Interleaved allocation should take odd-indexed ports before even."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='uplinks',
            zone_type='uplink',
            port_spec='1-8',
            allocation_strategy='interleaved',
        )

        allocator = PortAllocatorV2()
        allocated = allocator.allocate('fe-leaf-01', zone, 8)

        self.assertEqual(
            [slot.name for slot in allocated],
            ['E1/1', 'E1/3', 'E1/5', 'E1/7', 'E1/2', 'E1/4', 'E1/6', 'E1/8'],
        )

    def test_spaced_allocation_interleaves_halves(self):
        """Spaced allocation should alternate across port halves."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='spaced-ports',
            zone_type='uplink',
            port_spec='1-8',
            allocation_strategy='spaced',
        )

        allocator = PortAllocatorV2()
        allocated = allocator.allocate('fe-leaf-01', zone, 8)

        self.assertEqual(
            [slot.name for slot in allocated],
            ['E1/1', 'E1/5', 'E1/2', 'E1/6', 'E1/3', 'E1/7', 'E1/4', 'E1/8'],
        )

    def test_custom_allocation_uses_explicit_order(self):
        """Custom allocation should honor allocation_order."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='custom-ports',
            zone_type='server',
            port_spec='1-4',
            allocation_strategy='custom',
            allocation_order=[4, 2, 1, 3],
        )

        allocator = PortAllocatorV2()
        allocated = allocator.allocate('fe-leaf-01', zone, 4)

        self.assertEqual(
            [slot.name for slot in allocated],
            ['E1/4', 'E1/2', 'E1/1', 'E1/3'],
        )

    def test_allocation_isolated_per_switch(self):
        """Allocation state should be isolated per switch instance."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-2',
            allocation_strategy='sequential',
        )

        allocator = PortAllocatorV2()
        first = allocator.allocate('fe-leaf-01', zone, 1)
        second = allocator.allocate('fe-leaf-02', zone, 1)

        self.assertEqual([slot.name for slot in first], ['E1/1'])
        self.assertEqual([slot.name for slot in second], ['E1/1'])

    def test_allocation_rejects_non_positive_counts(self):
        """Allocation should reject zero or negative requests."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-2',
            allocation_strategy='sequential',
        )

        allocator = PortAllocatorV2()

        with self.assertRaises(ValidationError):
            allocator.allocate('fe-leaf-01', zone, 0)

        with self.assertRaises(ValidationError):
            allocator.allocate('fe-leaf-01', zone, -1)

    def test_allocation_rejects_overflow(self):
        """Allocation should fail when requests exceed remaining ports."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-2',
            allocation_strategy='sequential',
        )

        allocator = PortAllocatorV2()
        allocator.allocate('fe-leaf-01', zone, 2)

        with self.assertRaises(ValidationError):
            allocator.allocate('fe-leaf-01', zone, 1)
