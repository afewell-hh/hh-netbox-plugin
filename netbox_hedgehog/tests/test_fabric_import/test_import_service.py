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
            ("Edge-Core DCS203", "Edge-Core"),  # Must match seed data
            ("Edgecore EPS203", "Edge-Core"),  # Normalized to seed data name
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

    def test_derive_native_speed_handles_decimal_speeds(self):
        """Derive native_speed from decimal speeds like 2.5G (EPS203)."""
        port_profiles = {
            "2.5GBASE-T": {
                "speed": {
                    "default": "2.5G",
                    "supported": ["100M", "1G", "2.5G"]
                }
            }
        }

        native_speed = self.importer.derive_native_speed(port_profiles)
        # Returns 2.5 as float (accurate parsing)
        self.assertEqual(native_speed, 2.5)

    def test_create_extension_stores_none_for_decimal_native_speed(self):
        """DeviceTypeExtension stores None for decimal native_speed (IntegerField limitation)."""
        device_type = DeviceType.objects.create(
            manufacturer=self.celestica,
            model='TEST-EPS203',
            slug='test-eps203'
        )

        parsed_data = {
            "object_meta": {"name": "test-eps203"},
            "spec": {
                "display_name": "Test EPS203",
                "features": {"MCLAG": False},
                "ports": {},
                "port_profiles": {
                    "2.5GBASE-T": {
                        "speed": {
                            "default": "2.5G",
                            "supported": ["2.5G"]
                        }
                    }
                }
            }
        }

        ext = self.importer.create_or_update_extension(device_type, parsed_data)

        # native_speed should be None (not truncated) for decimal speeds
        # Accurate speed info is in supported_breakouts
        self.assertIsNone(ext.native_speed,
            "Decimal speeds should store as None, not truncated integer")

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
        self.assertEqual(e1_1.type, "800gbase-x-osfp")

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


# =============================================================================
# DIET-148: Port Mapping and Nonstandard Profile Tests
# =============================================================================

class ProfileNameMappingTestCase(TestCase):
    """Test profile-name-aware interface type mapping (DIET-148)."""

    def setUp(self):
        """Set up importer for each test."""
        self.importer = FabricProfileImporter()

    def test_osfp_800g_maps_to_osfp_not_qsfpdd(self):
        """OSFP-800G profile should map to 800gbase-x-osfp."""
        # Explicit profile name mapping
        interface_type = self.importer.PROFILE_NAME_TO_INTERFACE_TYPE.get("OSFP-800G")
        self.assertEqual(interface_type, "800gbase-x-osfp")

        # Should NOT use speed-based fallback for OSFP-800G
        speed_fallback = self.importer.SPEED_TO_INTERFACE_TYPE.get(800)
        self.assertEqual(speed_fallback, "800gbase-x-qsfpdd")  # Fallback is qsfpdd
        self.assertNotEqual(interface_type, speed_fallback)  # But OSFP overrides it

    def test_unmapped_profile_falls_back_to_speed(self):
        """Profiles not in PROFILE_NAME_TO_INTERFACE_TYPE should use speed fallback."""
        # Fictional profile not in map
        fictional_profile = "QSFP56-200G-Custom"

        # Should not be in explicit map
        self.assertNotIn(fictional_profile, self.importer.PROFILE_NAME_TO_INTERFACE_TYPE)

        # Should fall back to speed-based mapping (200G → qsfp56)
        # This verifies backward compatibility
        self.assertEqual(self.importer.SPEED_TO_INTERFACE_TYPE[200], "200gbase-x-qsfp56")

    def test_all_fabric_profiles_have_mapping(self):
        """All actual fabric port profiles should have a mapping."""
        # Known profiles from fabric source
        known_profiles = [
            "OSFP-800G",
            "OSFP-2x400G",
            "QSFPDD-400G",
            "QSFP28-100G",
            "SFP28-25G",
            "SFP28-10G",
            "RJ45-10G",
            "RJ45-2.5G",
        ]

        for profile_name in known_profiles:
            # Either in explicit map OR has speed-based fallback
            has_explicit = profile_name in self.importer.PROFILE_NAME_TO_INTERFACE_TYPE

            # If not explicit, verify it would work via speed fallback
            # (This test documents coverage)
            if not has_explicit:
                self.fail(f"Profile {profile_name} not in PROFILE_NAME_TO_INTERFACE_TYPE map")


class DS5000ImportTestCase(TestCase):
    """Test DS5000 import produces OSFP interface types (DIET-148)."""

    @classmethod
    def setUpTestData(cls):
        """Create manufacturer."""
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Celestica",
            defaults={'slug': 'celestica'}
        )

    def setUp(self):
        """Set up importer and parser for each test."""
        from netbox_hedgehog.utils.fabric_import import FabricProfileGoParser
        self.parser = FabricProfileGoParser()
        self.importer = FabricProfileImporter()

    def test_ds5000_imports_with_osfp_interface_type(self):
        """DS5000 should create InterfaceTemplates with 800gbase-x-osfp type."""
        # Load DS5000 fixture
        from pathlib import Path
        fixture_path = Path(__file__).parent / "fixtures" / "p_bcm_celestica_ds5000.go"

        with open(fixture_path) as f:
            parsed_data = self.parser._parse_go_source(f.read())

        # Verify profile name is OSFP-800G (not QSFPDD-800G)
        ports = parsed_data["spec"]["ports"]
        sample_port = ports["E1/1"]
        self.assertEqual(sample_port["profile"], "OSFP-800G")

        # Create device type
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="test-celestica-ds5000-osfp",
            slug="test-celestica-ds5000-osfp"
        )

        # Import interface templates
        self.importer.create_interface_templates(
            device_type,
            parsed_data["spec"]["ports"],
            parsed_data["spec"]["port_profiles"]
        )

        # CRITICAL: Verify OSFP interface type (not QSFP-DD)
        osfp_interfaces = device_type.interfacetemplates.filter(type="800gbase-x-osfp")
        qsfpdd_interfaces = device_type.interfacetemplates.filter(type="800gbase-x-qsfpdd")

        self.assertEqual(osfp_interfaces.count(), 64, "Should have 64 OSFP 800G ports")
        self.assertEqual(qsfpdd_interfaces.count(), 0, "Should have ZERO QSFP-DD 800G ports")

        # Verify SFP28 ports also created correctly
        sfp28_interfaces = device_type.interfacetemplates.filter(type="25gbase-x-sfp28")
        self.assertEqual(sfp28_interfaces.count(), 2, "Should have 2 SFP28 25G ports (E1/65-66)")


class AliasProfileTestCase(TestCase):
    """Test alias profile import (Supermicro SSE-C4632) (DIET-148)."""

    @classmethod
    def setUpTestData(cls):
        """Create manufacturers."""
        cls.celestica, _ = Manufacturer.objects.get_or_create(
            name="Celestica",
            defaults={'slug': 'celestica'}
        )
        cls.supermicro, _ = Manufacturer.objects.get_or_create(
            name="Supermicro",
            defaults={'slug': 'supermicro'}
        )

    def setUp(self):
        """Set up importer and parser for each test."""
        from netbox_hedgehog.utils.fabric_import import FabricProfileGoParser
        self.parser = FabricProfileGoParser()
        self.importer = FabricProfileImporter()

    def test_supermicro_sse_c4632_imports_as_alias(self):
        """Supermicro SSE-C4632 should import with DS3000 specs."""
        # Verify alias config exists
        alias_config = self.importer.ALIAS_PROFILES.get("supermicro-sse-c4632sb")
        self.assertIsNotNone(alias_config)
        self.assertEqual(alias_config["reference"], "celestica-ds3000")
        self.assertEqual(alias_config["manufacturer"], "Supermicro")

        # Import reference profile first (DS3000)
        ds3000_dt = self._import_ds3000()

        # Simulate alias import
        sse_dt = DeviceType.objects.create(
            manufacturer=self.supermicro,
            model="test-supermicro-sse-c4632sb",
            slug="test-supermicro-sse-c4632sb"
        )

        # Should have same interface count as DS3000
        ds3000_interface_count = ds3000_dt.interfacetemplates.count()

        # Import SSE-C4632 interfaces (using DS3000 parsed data)
        from pathlib import Path
        ds3000_fixture = Path(__file__).parent / "fixtures" / "p_bcm_celestica_ds3000.go"
        with open(ds3000_fixture) as f:
            parsed_data = self.parser._parse_go_source(f.read())

        self.importer.create_interface_templates(
            sse_dt,
            parsed_data["spec"]["ports"],
            parsed_data["spec"]["port_profiles"]
        )

        sse_interface_count = sse_dt.interfacetemplates.count()

        # Verify same specs as DS3000
        self.assertEqual(sse_interface_count, ds3000_interface_count)
        self.assertEqual(sse_dt.interfacetemplates.filter(type="100gbase-x-qsfp28").count(), 32)
        self.assertEqual(sse_dt.interfacetemplates.filter(type="10gbase-x-sfpp").count(), 1)

    def _import_ds3000(self):
        """Helper: import DS3000 for comparison."""
        dt = DeviceType.objects.create(
            manufacturer=self.celestica,
            model="test-celestica-ds3000-ref",
            slug="test-celestica-ds3000-ref"
        )

        from pathlib import Path
        fixture = Path(__file__).parent / "fixtures" / "p_bcm_celestica_ds3000.go"
        with open(fixture) as f:
            parsed_data = self.parser._parse_go_source(f.read())

        self.importer.create_interface_templates(
            dt,
            parsed_data["spec"]["ports"],
            parsed_data["spec"]["port_profiles"]
        )

        return dt


class VirtualSwitchTestCase(TestCase):
    """Test virtual switch import (vs, vs-clsp) (DIET-148)."""

    @classmethod
    def setUpTestData(cls):
        """Create manufacturer."""
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Hedgehog",
            defaults={'slug': 'hedgehog'}
        )

    def setUp(self):
        """Set up importer for each test."""
        self.importer = FabricProfileImporter()

    def test_vs_has_48_ports_no_breakouts(self):
        """Virtual switch should have E1/1-48 only, no breakout support."""
        # Get VS config
        vs_config = self.importer.VIRTUAL_SWITCH_PROFILES.get("vs")
        self.assertIsNotNone(vs_config)

        # Verify port count
        self.assertEqual(len(vs_config["ports"]), 48)

        # Verify port range (E1/1 - E1/48)
        port_names = list(vs_config["ports"].keys())
        self.assertEqual(port_names[0], "E1/1")
        self.assertEqual(port_names[-1], "E1/48")

        # Verify NO E1/49-56 (uplink ports removed)
        self.assertNotIn("E1/49", vs_config["ports"])
        self.assertNotIn("E1/56", vs_config["ports"])

        # Verify all ports use SFP28-25G
        for port_name, port_config in vs_config["ports"].items():
            self.assertEqual(port_config["profile"], "SFP28-25G")

        # Verify NO breakout profiles
        port_profiles = vs_config["port_profiles"]
        for profile_name, profile_config in port_profiles.items():
            self.assertNotIn("breakout", profile_config,
                           f"VS should not have breakout profiles, found in {profile_name}")
            self.assertIn("speed", profile_config,
                         f"VS should use speed profiles, missing in {profile_name}")

    def test_vs_import_creates_correct_device_type(self):
        """Importing VS should create DeviceType with 48 SFP28 interfaces."""
        vs_config = self.importer.VIRTUAL_SWITCH_PROFILES["vs"]

        # Create device type
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="test-vs",
            slug="test-vs"
        )

        # Construct parsed data format
        parsed_data = {
            "spec": {
                "ports": vs_config["ports"],
                "port_profiles": vs_config["port_profiles"],
                "features": vs_config["features"],
            }
        }

        # Import interfaces
        self.importer.create_interface_templates(
            device_type,
            parsed_data["spec"]["ports"],
            parsed_data["spec"]["port_profiles"]
        )

        # Verify interface count and types
        interfaces = device_type.interfacetemplates.all()
        self.assertEqual(interfaces.count(), 48)

        # All should be SFP28 25G
        sfp28_interfaces = device_type.interfacetemplates.filter(type="25gbase-x-sfp28")
        self.assertEqual(sfp28_interfaces.count(), 48)

        # Verify DeviceTypeExtension has no breakout support
        from netbox_hedgehog.models.topology_planning import DeviceTypeExtension
        ext = DeviceTypeExtension.objects.create(device_type=device_type)
        self.importer.create_or_update_extension(device_type, parsed_data)
        ext.refresh_from_db()

        self.assertEqual(ext.supported_breakouts, [], "VS should have no breakouts")
        self.assertEqual(ext.native_speed, 25, "VS native speed should be 25G")
