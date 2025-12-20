"""
Tests for Topology Planning Reference Data Models

Following TDD approach - these tests verify the refactored models that
use NetBox core models (DeviceType, ModuleType) with custom extensions.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from dcim.models import DeviceType, Manufacturer
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
)


class BreakoutOptionTestCase(TestCase):
    """Test cases for BreakoutOption model"""

    def test_create_breakout_option(self):
        """Test basic BreakoutOption creation"""
        breakout = BreakoutOption.objects.create(
            breakout_id='2x400g',
            from_speed=800,
            logical_ports=2,
            logical_speed=400,
            optic_type='QSFP-DD'
        )
        self.assertEqual(breakout.breakout_id, '2x400g')
        self.assertEqual(breakout.from_speed, 800)
        self.assertEqual(breakout.logical_ports, 2)
        self.assertEqual(breakout.logical_speed, 400)
        self.assertEqual(breakout.optic_type, 'QSFP-DD')

    def test_breakout_option_str(self):
        """Test __str__ returns readable format"""
        breakout = BreakoutOption.objects.create(
            breakout_id='4x200g',
            from_speed=800,
            logical_ports=4,
            logical_speed=200
        )
        self.assertEqual(str(breakout), '4x200G (from 800G)')

    def test_breakout_option_unique_id(self):
        """Test breakout_id must be unique"""
        BreakoutOption.objects.create(
            breakout_id='2x400g',
            from_speed=800,
            logical_ports=2,
            logical_speed=400
        )
        with self.assertRaises(IntegrityError):
            BreakoutOption.objects.create(
                breakout_id='2x400g',  # Duplicate
                from_speed=400,
                logical_ports=2,
                logical_speed=200
            )

    def test_breakout_option_ordering(self):
        """Test BreakoutOptions are ordered by from_speed desc, logical_ports asc"""
        # Create breakouts in random order
        BreakoutOption.objects.create(
            breakout_id='4x200g', from_speed=800, logical_ports=4, logical_speed=200
        )
        BreakoutOption.objects.create(
            breakout_id='2x400g', from_speed=800, logical_ports=2, logical_speed=400
        )
        BreakoutOption.objects.create(
            breakout_id='4x25g', from_speed=100, logical_ports=4, logical_speed=25
        )

        # Get all in default order
        breakouts = list(BreakoutOption.objects.all())

        # Should be ordered by from_speed DESC, then logical_ports ASC
        self.assertEqual(breakouts[0].breakout_id, '2x400g')  # 800G, 2 ports
        self.assertEqual(breakouts[1].breakout_id, '4x200g')  # 800G, 4 ports
        self.assertEqual(breakouts[2].breakout_id, '4x25g')   # 100G, 4 ports


class DeviceTypeExtensionTestCase(TestCase):
    """Test cases for DeviceTypeExtension model"""

    def setUp(self):
        """Create test data"""
        self.manufacturer = Manufacturer.objects.create(
            name='Test Manufacturer',
            slug='test-manufacturer'
        )
        self.device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='TestSwitch-5000',
            slug='testswitch-5000',
            u_height=1
        )

    def test_create_device_type_extension(self):
        """Test basic DeviceTypeExtension creation"""
        extension = DeviceTypeExtension.objects.create(
            device_type=self.device_type,
            mclag_capable=True,
            hedgehog_roles=['spine', 'server-leaf'],
            notes='Test extension'
        )
        self.assertEqual(extension.device_type, self.device_type)
        self.assertTrue(extension.mclag_capable)
        self.assertEqual(extension.hedgehog_roles, ['spine', 'server-leaf'])
        self.assertEqual(extension.notes, 'Test extension')

    def test_device_type_extension_one_to_one(self):
        """Test DeviceTypeExtension has one-to-one relationship with DeviceType"""
        DeviceTypeExtension.objects.create(
            device_type=self.device_type,
            mclag_capable=True
        )

        # Try to create another extension for the same DeviceType
        with self.assertRaises(IntegrityError):
            DeviceTypeExtension.objects.create(
                device_type=self.device_type,
                mclag_capable=False
            )

    def test_device_type_extension_str(self):
        """Test __str__ returns descriptive text"""
        extension = DeviceTypeExtension.objects.create(
            device_type=self.device_type,
            mclag_capable=True
        )
        expected = f"Hedgehog metadata for {self.device_type}"
        self.assertEqual(str(extension), expected)

    def test_device_type_extension_related_name(self):
        """Test can access extension via DeviceType.hedgehog_metadata"""
        extension = DeviceTypeExtension.objects.create(
            device_type=self.device_type,
            mclag_capable=True,
            hedgehog_roles=['spine']
        )

        # Access via related name
        self.assertEqual(self.device_type.hedgehog_metadata, extension)
        self.assertTrue(self.device_type.hedgehog_metadata.mclag_capable)

    def test_device_type_extension_cascade_delete(self):
        """Test extension is deleted when DeviceType is deleted"""
        extension = DeviceTypeExtension.objects.create(
            device_type=self.device_type,
            mclag_capable=True
        )

        extension_id = extension.id
        self.device_type.delete()

        # Extension should be deleted via cascade
        with self.assertRaises(DeviceTypeExtension.DoesNotExist):
            DeviceTypeExtension.objects.get(id=extension_id)

    def test_device_type_extension_defaults(self):
        """Test DeviceTypeExtension default values"""
        extension = DeviceTypeExtension.objects.create(
            device_type=self.device_type
        )

        self.assertFalse(extension.mclag_capable)  # Default False
        self.assertEqual(extension.hedgehog_roles, [])  # Default empty list
        self.assertEqual(extension.notes, '')  # Default empty string


class SeedDataTestCase(TestCase):
    """Test cases to verify seed data migration worked correctly"""

    def test_seed_manufacturers_exist(self):
        """Test that seed manufacturers were created"""
        celestica = Manufacturer.objects.filter(name='Celestica').first()
        nvidia = Manufacturer.objects.filter(name='NVIDIA').first()
        edgecore = Manufacturer.objects.filter(name='Edge-Core').first()

        self.assertIsNotNone(celestica)
        self.assertIsNotNone(nvidia)
        self.assertIsNotNone(edgecore)

    def test_seed_device_types_exist(self):
        """Test that seed DeviceTypes were created"""
        ds5000 = DeviceType.objects.filter(model='DS5000').first()
        ds3000 = DeviceType.objects.filter(model='DS3000').first()
        sn5600 = DeviceType.objects.filter(model='SN5600').first()
        es1000 = DeviceType.objects.filter(model='ES1000-48').first()

        self.assertIsNotNone(ds5000)
        self.assertIsNotNone(ds3000)
        self.assertIsNotNone(sn5600)
        self.assertIsNotNone(es1000)

    def test_seed_device_type_extensions_exist(self):
        """Test that DeviceTypeExtensions were created for seed devices"""
        ds5000 = DeviceType.objects.filter(model='DS5000').first()
        sn5600 = DeviceType.objects.filter(model='SN5600').first()

        if ds5000:
            self.assertTrue(hasattr(ds5000, 'hedgehog_metadata'))
            self.assertIn('spine', ds5000.hedgehog_metadata.hedgehog_roles)

        if sn5600:
            self.assertTrue(hasattr(sn5600, 'hedgehog_metadata'))
            self.assertTrue(sn5600.hedgehog_metadata.mclag_capable)

    def test_seed_interface_templates_exist(self):
        """Test that InterfaceTemplates were created for seed devices"""
        ds5000 = DeviceType.objects.filter(model='DS5000').first()
        ds3000 = DeviceType.objects.filter(model='DS3000').first()

        if ds5000:
            # DS5000 should have 64 interfaces
            self.assertEqual(ds5000.interfacetemplates.count(), 64)

        if ds3000:
            # DS3000 should have 32 interfaces
            self.assertEqual(ds3000.interfacetemplates.count(), 32)

    def test_seed_breakout_options_exist(self):
        """Test that BreakoutOptions were created"""
        breakout_ids = [
            '1x800g', '2x400g', '4x200g', '8x100g',
            '1x100g', '4x25g', '4x10g', '1x1g'
        ]

        for breakout_id in breakout_ids:
            breakout = BreakoutOption.objects.filter(breakout_id=breakout_id).first()
            self.assertIsNotNone(
                breakout,
                f"BreakoutOption {breakout_id} should exist from seed data"
            )
