"""
Model tests for SwitchPortZone.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from dcim.models import DeviceType, Manufacturer

from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanSwitchClass,
    TopologyPlan,
    SwitchPortZone,
)


class SwitchPortZoneModelTestCase(TestCase):
    """Test suite for SwitchPortZone model"""

    @classmethod
    def setUpTestData(cls):
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
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

    def test_create_port_zone_minimal(self):
        """Test creating port zone with minimal required fields"""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-48',
            allocation_strategy='sequential',
        )

        self.assertEqual(zone.zone_name, 'server-ports')
        self.assertEqual(zone.zone_type, 'server')
        self.assertEqual(zone.port_spec, '1-48')
        self.assertEqual(zone.allocation_strategy, 'sequential')
        self.assertIsNone(zone.breakout_option)
        self.assertIsNone(zone.allocation_order)

    def test_create_port_zone_with_breakout(self):
        """Test creating port zone with a breakout option"""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-32',
            breakout_option=self.breakout_4x200g,
            allocation_strategy='sequential',
        )

        self.assertEqual(zone.breakout_option, self.breakout_4x200g)

    def test_str_representation(self):
        """Test __str__ formatting"""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-48',
            allocation_strategy='sequential',
        )

        self.assertEqual(str(zone), 'fe-gpu-leaf/server-ports')

    def test_zone_name_required(self):
        """Test zone_name is required"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_type='server',
            port_spec='1-48',
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError):
            zone.full_clean()

    def test_clean_rejects_invalid_port_spec(self):
        """Test clean() rejects invalid port_spec format"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='invalid-spec',
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('port_spec', cm.exception.message_dict)

    def test_clean_requires_allocation_order_for_custom(self):
        """Test clean() requires allocation_order when strategy is custom"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='uplinks',
            zone_type='uplink',
            port_spec='49-64',
            allocation_strategy='custom',
            allocation_order=None,
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('allocation_order', cm.exception.message_dict)

    def test_clean_allows_allocation_order_for_non_custom(self):
        """Test clean() allows allocation_order for non-custom strategies"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='uplinks',
            zone_type='uplink',
            port_spec='49-64',
            allocation_strategy='sequential',
            allocation_order=[49, 50, 51, 52],
        )

        zone.full_clean()

    # Field Validation Tests

    def test_zone_name_max_length(self):
        """Test zone_name max length is 100 chars"""
        long_name = 'a' * 101
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name=long_name,
            zone_type='server',
            port_spec='1-48',
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError):
            zone.full_clean()

    def test_zone_type_choices(self):
        """Test zone_type accepts valid choices only"""
        valid_types = ['server', 'uplink', 'mclag', 'peer', 'session', 'oob', 'fabric']

        for zone_type in valid_types:
            zone = SwitchPortZone.objects.create(
                switch_class=self.switch_class,
                zone_name=f'test-{zone_type}',
                zone_type=zone_type,
                port_spec='1-16',
                allocation_strategy='sequential',
            )
            self.assertEqual(zone.zone_type, zone_type)

    def test_zone_type_invalid_choice(self):
        """Test zone_type rejects invalid choices"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='invalid',
            port_spec='1-16',
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError):
            zone.full_clean()

    def test_port_spec_max_length(self):
        """Test port_spec max length is 200 chars"""
        long_spec = '1,' * 100 + 'x'  # 201 chars (exceeds limit)
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec=long_spec,
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError):
            zone.full_clean()

    def test_allocation_strategy_choices(self):
        """Test allocation_strategy accepts valid choices"""
        valid_strategies = ['sequential', 'interleaved', 'spaced', 'custom']

        for strategy in valid_strategies:
            allocation_order = list(range(1, 17)) if strategy == 'custom' else None
            zone = SwitchPortZone.objects.create(
                switch_class=self.switch_class,
                zone_name=f'test-{strategy}',
                zone_type='server',
                port_spec='1-16',
                allocation_strategy=strategy,
                allocation_order=allocation_order,
            )
            self.assertEqual(zone.allocation_strategy, strategy)

    def test_priority_positive_integer(self):
        """Test priority must be positive integer"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1-16',
            allocation_strategy='sequential',
            priority=0,  # Invalid: must be >= 1
        )

        with self.assertRaises(ValidationError):
            zone.full_clean()

    def test_priority_default_value(self):
        """Test priority defaults to 100"""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1-16',
            allocation_strategy='sequential',
        )

        self.assertEqual(zone.priority, 100)

    # Port Spec Edge Case Tests

    def test_port_spec_with_whitespace(self):
        """Test port_spec handles whitespace gracefully"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1-4, 6, 8-10',  # Spaces around commas
            allocation_strategy='sequential',
        )
        zone.full_clean()  # Should succeed (whitespace stripped)

    def test_port_spec_rejects_reversed_range(self):
        """Test port_spec rejects range where start > end"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='4-1',  # Invalid: reversed
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('port_spec', cm.exception.message_dict)
        error_msg = str(cm.exception).lower()
        self.assertTrue('invalid' in error_msg or 'range' in error_msg)

    def test_port_spec_rejects_zero_port(self):
        """Test port_spec rejects port number 0"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='0-5',
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('port_spec', cm.exception.message_dict)
        error_msg = str(cm.exception).lower()
        self.assertTrue('positive' in error_msg or 'must be' in error_msg)

    def test_port_spec_rejects_negative_port(self):
        """Test port_spec rejects negative port numbers"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='-1-3',
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('port_spec', cm.exception.message_dict)

    def test_port_spec_rejects_unrealistic_port_number(self):
        """Test port_spec rejects port numbers > reasonable max (1024)"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1-9999',  # Unrealistic
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('port_spec', cm.exception.message_dict)
        error_msg = str(cm.exception).lower()
        self.assertTrue('maximum' in error_msg or 'max' in error_msg or '1024' in error_msg)

    def test_port_spec_rejects_zero_step_interleaved(self):
        """Test port_spec rejects interleaved with step=0"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1-16:0',  # Invalid: step=0
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('port_spec', cm.exception.message_dict)
        error_msg = str(cm.exception).lower()
        self.assertTrue('step' in error_msg or 'positive' in error_msg)

    def test_port_spec_rejects_negative_step_interleaved(self):
        """Test port_spec rejects interleaved with negative step"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1-16:-2',
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('port_spec', cm.exception.message_dict)

    # allocation_order Validation Tests

    def test_clean_validates_allocation_order_matches_port_set(self):
        """Test clean() validates allocation_order contains same ports as port_spec"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1-4',  # Ports: [1,2,3,4]
            allocation_strategy='custom',
            allocation_order=[1, 2, 5, 6],  # Wrong ports! (5,6 not in spec; missing 3,4)
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('allocation_order', cm.exception.message_dict)
        error_msg = str(cm.exception).lower()
        self.assertTrue('must match' in error_msg or 'port set' in error_msg)

    def test_clean_validates_allocation_order_no_duplicates(self):
        """Test clean() rejects allocation_order with duplicate port numbers"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1-4',
            allocation_strategy='custom',
            allocation_order=[1, 2, 3, 3],  # Duplicate 3
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('allocation_order', cm.exception.message_dict)
        error_msg = str(cm.exception).lower()
        self.assertTrue('duplicate' in error_msg)

    def test_clean_validates_allocation_order_length_matches(self):
        """Test clean() validates allocation_order length matches port count"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1-16',  # 16 ports
            allocation_strategy='custom',
            allocation_order=[1, 2, 3],  # Only 3 entries (mismatch)
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('allocation_order', cm.exception.message_dict)
        error_msg = str(cm.exception).lower()
        self.assertTrue('match' in error_msg or 'count' in error_msg)

    def test_create_port_zone_with_custom_allocation(self):
        """Test creating port zone with custom allocation order"""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='uplinks',
            zone_type='uplink',
            port_spec='49-64',
            allocation_strategy='custom',
            allocation_order=list(range(49, 65)),  # 16 port numbers
        )

        self.assertEqual(zone.allocation_strategy, 'custom')
        self.assertEqual(len(zone.allocation_order), 16)

    # Model Constraint Tests

    def test_unique_together_zone_name_per_switch_class(self):
        """Test zone_name must be unique within switch_class"""
        SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-48',
            allocation_strategy='sequential',
        )

        # Attempt to create duplicate
        with self.assertRaises(IntegrityError):
            SwitchPortZone.objects.create(
                switch_class=self.switch_class,
                zone_name='server-ports',  # Same name
                zone_type='uplink',
                port_spec='49-64',
                allocation_strategy='sequential',
            )

    def test_zone_name_unique_across_different_switch_classes(self):
        """Test same zone_name allowed across different switch classes"""
        # Create second switch class
        switch_class_2 = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='test-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.device_type_extension,
            uplink_ports_per_switch=0,
        )

        # Create zone in first switch class
        SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-48',
            allocation_strategy='sequential',
        )

        # Create zone with same name in second switch class (should succeed)
        zone_2 = SwitchPortZone.objects.create(
            switch_class=switch_class_2,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-32',
            allocation_strategy='sequential',
        )

        self.assertEqual(zone_2.zone_name, 'server-ports')

    def test_cascade_delete_when_switch_class_deleted(self):
        """Test port zones are deleted when switch class is deleted"""
        SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-48',
            allocation_strategy='sequential',
        )

        self.assertEqual(SwitchPortZone.objects.count(), 1)

        self.switch_class.delete()

        self.assertEqual(SwitchPortZone.objects.count(), 0)

    def test_protect_delete_when_breakout_option_used(self):
        """Test cannot delete BreakoutOption if used by port zone"""
        from django.db.models import ProtectedError

        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-32',
            breakout_option=self.breakout_4x200g,
            allocation_strategy='sequential',
        )

        with self.assertRaises(ProtectedError):
            self.breakout_4x200g.delete()

    # Ordering Tests

    def test_default_ordering_by_switch_class_priority_zone_name(self):
        """Test default ordering is switch_class, priority, zone_name"""
        # Create multiple zones with different priorities
        zone_c = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='zone-c',
            zone_type='server',
            port_spec='1-16',
            allocation_strategy='sequential',
            priority=300,
        )
        zone_a = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='zone-a',
            zone_type='server',
            port_spec='17-32',
            allocation_strategy='sequential',
            priority=100,
        )
        zone_b = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='zone-b',
            zone_type='uplink',
            port_spec='33-48',
            allocation_strategy='sequential',
            priority=200,
        )

        zones = list(SwitchPortZone.objects.all())

        # Should be ordered by priority (100, 200, 300)
        self.assertEqual(zones[0], zone_a)
        self.assertEqual(zones[1], zone_b)
        self.assertEqual(zones[2], zone_c)

    def test_ordering_by_zone_name_when_priority_same(self):
        """Test ordering by zone_name when priority is the same"""
        zone_b = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='zone-b',
            zone_type='server',
            port_spec='1-16',
            allocation_strategy='sequential',
            priority=100,
        )
        zone_a = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='zone-a',
            zone_type='uplink',
            port_spec='17-32',
            allocation_strategy='sequential',
            priority=100,
        )

        zones = list(SwitchPortZone.objects.filter(priority=100))

        # Should be ordered alphabetically by zone_name
        self.assertEqual(zones[0], zone_a)
        self.assertEqual(zones[1], zone_b)

    def test_ordering_scoped_by_switch_class(self):
        """Test ordering respects switch_class boundaries"""
        # Create second switch class
        switch_class_2 = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='test-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.device_type_extension,
            uplink_ports_per_switch=0,
        )

        # Create zones across both switch classes
        # switch_class 1: priority 200, 300
        zone_1b = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='zone-b',
            zone_type='server',
            port_spec='1-16',
            allocation_strategy='sequential',
            priority=300,
        )
        zone_1a = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='zone-a',
            zone_type='server',
            port_spec='17-32',
            allocation_strategy='sequential',
            priority=200,
        )

        # switch_class 2: priority 100, 150
        zone_2b = SwitchPortZone.objects.create(
            switch_class=switch_class_2,
            zone_name='zone-d',
            zone_type='uplink',
            port_spec='1-16',
            allocation_strategy='sequential',
            priority=150,
        )
        zone_2a = SwitchPortZone.objects.create(
            switch_class=switch_class_2,
            zone_name='zone-c',
            zone_type='uplink',
            port_spec='17-32',
            allocation_strategy='sequential',
            priority=100,
        )

        # Fetch all zones
        all_zones = list(SwitchPortZone.objects.all())

        # Expected order: switch_class (by ID), then priority within class
        # Assuming switch_class 1 has lower ID than switch_class 2
        self.assertEqual(all_zones[0], zone_1a)  # switch_class 1, priority 200
        self.assertEqual(all_zones[1], zone_1b)  # switch_class 1, priority 300
        self.assertEqual(all_zones[2], zone_2a)  # switch_class 2, priority 100
        self.assertEqual(all_zones[3], zone_2b)  # switch_class 2, priority 150

    # Additional Port Spec Format Validation Tests

    def test_clean_validates_port_spec_format_range(self):
        """Test clean() validates port_spec range format"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1-48',
            allocation_strategy='sequential',
        )

        zone.full_clean()  # Should not raise

    def test_clean_validates_port_spec_format_list(self):
        """Test clean() validates port_spec list format"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1,3,5,7,9',
            allocation_strategy='sequential',
        )

        zone.full_clean()  # Should not raise

    def test_clean_validates_port_spec_format_interleaved(self):
        """Test clean() validates port_spec interleaved format"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='1-64:2',
            allocation_strategy='sequential',
        )

        zone.full_clean()  # Should not raise

    def test_clean_rejects_empty_port_spec(self):
        """Test clean() rejects port_spec that defines no ports"""
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='test',
            zone_type='server',
            port_spec='',
            allocation_strategy='sequential',
        )

        with self.assertRaises(ValidationError) as cm:
            zone.full_clean()

        self.assertIn('port_spec', cm.exception.message_dict)
