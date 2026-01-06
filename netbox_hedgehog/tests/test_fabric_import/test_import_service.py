"""
Unit tests for Fabric Profile Import Service (DIET-144).

These tests validate the import service logic that maps parsed fabric profile
data to NetBox models (DeviceType, DeviceTypeExtension, BreakoutOption, InterfaceTemplate).
"""

from django.test import TestCase
from django.core.exceptions import ValidationError

from dcim.models import DeviceType, Manufacturer, InterfaceTemplate
from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension,
    BreakoutOption,
)
from netbox_hedgehog.utils.fabric_import import FabricProfileImporter


class FabricProfileImporterTestCase(TestCase):
    """Tests for FabricProfileImporter service."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        # Get or create manufacturers (use get_or_create for test db reuse)
        cls.celestica, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )
        cls.edgecore, _ = Manufacturer.objects.get_or_create(
            name='Edgecore',
            defaults={'slug': 'edgecore'}
        )

    def setUp(self):
        """Set up importer for each test."""
        self.importer = FabricProfileImporter()

    def test_extract_manufacturer_from_display_name(self):
        """Test manufacturer extraction from DisplayName."""
        testcases = [
            ("Celestica DS5000", "Celestica"),
            ("Dell S5248F-ON", "Dell"),
            ("NVIDIA SN5600", "NVIDIA"),
            ("Edge-Core DCS203", "Edgecore"),
            ("Edgecore EPS203", "Edgecore"),
            ("Virtual Switch", "Hedgehog"),
        ]

        for display_name, expected_manufacturer in testcases:
            with self.subTest(display_name=display_name):
                manufacturer = self.importer.extract_manufacturer(display_name)
                self.assertEqual(manufacturer, expected_manufacturer)

    def test_extract_manufacturer_raises_error_for_unknown(self):
        """Unknown manufacturer should raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.importer.extract_manufacturer("UnknownVendor Switch")

    def test_derive_native_speed_from_port_profiles(self):
        """Derive native_speed from highest port profile speed."""
        # OSFP-800G + SFP28-25G should yield 800G
        port_profiles = {
            "OSFP-800G": {
                "breakout": {
                    "default": "1x800G",
                    "supported": {
                        "1x800g": {"offsets": ["0"]},
                    }
                }
            },
            "SFP28-25G": {
                "speed": {
                    "default": "25G",
                    "supported": ["1G", "10G", "25G"]
                }
            }
        }

        native_speed = self.importer.derive_native_speed(port_profiles)
        self.assertEqual(native_speed, 800)

    def test_derive_native_speed_from_speed_profiles_only(self):
        """Derive native_speed from Speed profiles when no Breakout profiles."""
        # Only SFP28-25G should yield 25G
        port_profiles = {
            "SFP28-25G": {
                "speed": {
                    "default": "25G",
                    "supported": ["1G", "10G", "25G"]
                }
            }
        }

        native_speed = self.importer.derive_native_speed(port_profiles)
        self.assertEqual(native_speed, 25)

    def test_derive_supported_breakouts_from_port_profiles(self):
        """Extract and normalize supported breakout mode strings."""
        port_profiles = {
            "OSFP-800G": {
                "breakout": {
                    "default": "1x800G",
                    "supported": {
                        "1x800g": {"offsets": ["0"]},
                        "2x400g": {"offsets": ["0", "4"]},
                        "4x200g": {"offsets": ["0", "2", "4", "6"]},
                    }
                }
            }
        }

        supported_breakouts = self.importer.derive_supported_breakouts(port_profiles)

        # Should be a list of normalized lowercase strings
        self.assertIsInstance(supported_breakouts, list)
        self.assertIn("1x800g", supported_breakouts)
        self.assertIn("2x400g", supported_breakouts)
        self.assertIn("4x200g", supported_breakouts)

    def test_derive_supported_breakouts_empty_when_no_breakout_profiles(self):
        """No breakout profiles should return empty list."""
        port_profiles = {
            "SFP28-25G": {
                "speed": {
                    "default": "25G",
                    "supported": ["1G", "10G", "25G"]
                }
            }
        }

        supported_breakouts = self.importer.derive_supported_breakouts(port_profiles)
        self.assertEqual(supported_breakouts, [])

    def test_create_or_update_device_type_extension(self):
        """Create DeviceTypeExtension with derived fields."""
        device_type = DeviceType.objects.create(
            manufacturer=self.celestica,
            model='TEST-DS5000-CREATE',
            slug='test-ds5000-create'
        )

        parsed_data = {
            "object_meta": {"name": "celestica-ds5000"},
            "spec": {
                "display_name": "Celestica DS5000",
                "features": {"MCLAG": False},
                "ports": {},  # Not used for extension creation
                "port_profiles": {
                    "OSFP-800G": {
                        "breakout": {
                            "default": "1x800G",
                            "supported": {
                                "1x800g": {"offsets": ["0"]},
                                "2x400g": {"offsets": ["0", "4"]},
                            }
                        }
                    }
                }
            }
        }

        ext = self.importer.create_or_update_extension(device_type, parsed_data)

        self.assertEqual(ext.device_type, device_type)
        self.assertEqual(ext.native_speed, 800)
        # supported_breakouts is a JSONField list
        self.assertIsInstance(ext.supported_breakouts, list)
        self.assertIn("1x800g", ext.supported_breakouts)
        self.assertIn("2x400g", ext.supported_breakouts)
        self.assertFalse(ext.mclag_capable)

    def test_update_extension_only_fills_empty_fields(self):
        """Existing non-empty extension fields should not be overwritten."""
        device_type = DeviceType.objects.create(
            manufacturer=self.celestica,
            model='TEST-DS5000-UPDATE',
            slug='test-ds5000-update'
        )

        # Create existing extension with user-modified values
        existing_ext = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=400,  # User modified this
            supported_breakouts=["1x400g", "2x200g"],  # User modified this (list)
            mclag_capable=True  # User modified this
        )

        parsed_data = {
            "object_meta": {"name": "celestica-ds5000"},
            "spec": {
                "display_name": "Celestica DS5000",
                "features": {"MCLAG": False},
                "ports": {},
                "port_profiles": {
                    "OSFP-800G": {
                        "breakout": {
                            "default": "1x800G",
                            "supported": {
                                "1x800g": {"offsets": ["0"]},
                            }
                        }
                    }
                }
            }
        }

        ext = self.importer.create_or_update_extension(device_type, parsed_data)

        # Should NOT overwrite existing values
        self.assertEqual(ext.native_speed, 400)  # User value preserved
        self.assertEqual(ext.supported_breakouts, ["1x400g", "2x200g"])  # User value preserved (list)
        self.assertTrue(ext.mclag_capable)  # User value preserved

    def test_create_interface_templates_from_ports(self):
        """Create InterfaceTemplates from parsed ports."""
        device_type = DeviceType.objects.create(
            manufacturer=self.celestica,
            model='TEST-DS5000-INTFTPL',
            slug='test-ds5000-intftpl'
        )

        parsed_ports = {
            "E1/1": {"nos_name": "1/1", "label": "1", "profile": "OSFP-800G"},
            "E1/2": {"nos_name": "1/2", "label": "2", "profile": "OSFP-800G"},
            "E1/65": {"nos_name": "Ethernet512", "label": "65", "profile": "SFP28-25G"},
        }

        port_profiles = {
            "OSFP-800G": {
                "breakout": {"default": "1x800G", "supported": {"1x800g": {}}}
            },
            "SFP28-25G": {
                "speed": {"default": "25G", "supported": ["25G"]}
            }
        }

        self.importer.create_interface_templates(device_type, parsed_ports, port_profiles)

        # Verify templates were created
        templates = InterfaceTemplate.objects.filter(device_type=device_type)
        self.assertEqual(templates.count(), 3)

        # Check E1/1
        e1_1 = templates.get(name="E1/1")
        self.assertEqual(e1_1.type, "800gbase-x-qsfpdd")

        # Check E1/65
        e1_65 = templates.get(name="E1/65")
        self.assertEqual(e1_65.type, "25gbase-x-sfp28")

    def test_create_breakout_options_from_port_profiles(self):
        """Create BreakoutOption records from breakout modes."""
        port_profiles = {
            "OSFP-800G": {
                "breakout": {
                    "default": "1x800G",
                    "supported": {
                        "1x800g": {"offsets": ["0"]},
                        "2x400g": {"offsets": ["0", "4"]},
                        "4x200g": {"offsets": ["0", "2", "4", "6"]},
                    }
                }
            }
        }

        self.importer.create_breakout_options(port_profiles)

        # Verify breakout options were created
        self.assertTrue(BreakoutOption.objects.filter(breakout_id="1x800g").exists())
        self.assertTrue(BreakoutOption.objects.filter(breakout_id="2x400g").exists())
        self.assertTrue(BreakoutOption.objects.filter(breakout_id="4x200g").exists())

        # Check fields for 2x400g
        bo_2x400g = BreakoutOption.objects.get(breakout_id="2x400g")
        self.assertEqual(bo_2x400g.from_speed, 800)
        self.assertEqual(bo_2x400g.logical_ports, 2)
        self.assertEqual(bo_2x400g.logical_speed, 400)

    def test_parse_breakout_mode_name(self):
        """Parse breakout mode name to extract fields."""
        testcases = [
            ("1x800g", {"from_speed": 800, "logical_ports": 1, "logical_speed": 800}),
            ("2x400g", {"from_speed": 800, "logical_ports": 2, "logical_speed": 400}),
            ("4x200g", {"from_speed": 800, "logical_ports": 4, "logical_speed": 200}),
            ("8x100g", {"from_speed": 800, "logical_ports": 8, "logical_speed": 100}),
            ("1x100g", {"from_speed": 100, "logical_ports": 1, "logical_speed": 100}),
            ("4x25g", {"from_speed": 100, "logical_ports": 4, "logical_speed": 25}),
        ]

        for mode_name, expected in testcases:
            with self.subTest(mode_name=mode_name):
                result = self.importer.parse_breakout_mode_name(mode_name)
                self.assertEqual(result["from_speed"], expected["from_speed"])
                self.assertEqual(result["logical_ports"], expected["logical_ports"])
                self.assertEqual(result["logical_speed"], expected["logical_speed"])
