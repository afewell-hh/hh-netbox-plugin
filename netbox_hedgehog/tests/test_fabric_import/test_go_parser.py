"""
Unit tests for FabricProfileGoParser (DIET-144).

These tests validate parsing of Hedgehog Fabric switch profiles from Go source files.
Tests use local fixtures (committed) to ensure deterministic, offline testing.
"""

import unittest
from pathlib import Path
from typing import Dict, Any

from netbox_hedgehog.utils.fabric_import import FabricProfileGoParser


class FabricProfileGoParserTestCase(unittest.TestCase):
    """Tests for FabricProfileGoParser."""

    def setUp(self):
        """Set up parser instance and fixture paths for each test."""
        self.parser = FabricProfileGoParser()
        # Local fixtures directory (relative to this test file)
        self.fixtures_dir = Path(__file__).parent / "fixtures"

    def test_parse_celestica_ds5000(self):
        """Parse Celestica DS5000 profile and validate all fields."""
        fixture_path = self.fixtures_dir / "p_bcm_celestica_ds5000.go"

        result = self.parser.parse_profile_from_file(str(fixture_path))

        # Validate ObjectMeta
        self.assertEqual(result["object_meta"]["name"], "celestica-ds5000")

        # Validate Spec.DisplayName for manufacturer extraction
        self.assertEqual(result["spec"]["display_name"], "Celestica DS5000")

        # Validate Ports (DS5000 has 64 OSFP-800G + 2 SFP28-25G + 1 M1 management = 67 total)
        ports = result["spec"]["ports"]
        self.assertEqual(len(ports), 67, "DS5000 should have 67 ports (66 E1/ + M1 management)")

        # Management port must be present
        self.assertIn("M1", ports, "DS5000 must include M1 management port")
        self.assertTrue(ports["M1"].get("management"), "M1 must have management=True")

        # Validate data port naming pattern (uses E1/N format)
        port_keys = list(ports.keys())
        self.assertIn("E1/1", port_keys)
        self.assertIn("E1/64", port_keys)
        self.assertIn("E1/65", port_keys)  # SFP28 port
        self.assertIn("E1/66", port_keys)  # SFP28 port

        # Validate PortProfiles exist
        port_profiles = result["spec"]["port_profiles"]
        self.assertIn("OSFP-800G", port_profiles)
        self.assertIn("SFP28-25G", port_profiles)

        # Validate OSFP-800G breakout modes
        osfp_profile = port_profiles["OSFP-800G"]
        self.assertIn("breakout", osfp_profile)
        breakout = osfp_profile["breakout"]
        self.assertEqual(breakout["default"], "1x800G")

        # Check some expected breakout modes
        supported_modes = breakout["supported"]
        self.assertIn("1x800g", supported_modes)
        self.assertIn("2x400g", supported_modes)
        self.assertIn("4x200g", supported_modes)

        # Validate Features
        features = result["spec"]["features"]
        self.assertIn("MCLAG", features)
        self.assertIsInstance(features["MCLAG"], bool)
        self.assertFalse(features["MCLAG"], "DS5000 does not support MCLAG")

    def test_parse_celestica_ds3000(self):
        """Parse Celestica DS3000 profile and validate all fields."""
        fixture_path = self.fixtures_dir / "p_bcm_celestica_ds3000.go"

        result = self.parser.parse_profile_from_file(str(fixture_path))

        # Validate ObjectMeta
        self.assertEqual(result["object_meta"]["name"], "celestica-ds3000")

        # Validate manufacturer from DisplayName
        self.assertTrue(result["spec"]["display_name"].startswith("Celestica"))

        # Validate Ports: 32 QSFP28-100G + 1 RJ45-10G console + 1 M1 management = 34 total
        ports = result["spec"]["ports"]
        self.assertEqual(len(ports), 34, "DS3000 should have 34 ports (33 E1/ + M1 management)")

        # Management port must be present
        self.assertIn("M1", ports, "DS3000 must include M1 management port")
        self.assertTrue(ports["M1"].get("management"), "M1 must have management=True")

    def test_parse_edgecore_dcs203(self):
        """Parse Edgecore DCS203 profile (mixed-port device)."""
        fixture_path = self.fixtures_dir / "p_bcm_edgecore_dcs203.go"

        result = self.parser.parse_profile_from_file(str(fixture_path))

        # Validate ObjectMeta
        self.assertEqual(result["object_meta"]["name"], "edgecore-dcs203")

        # Validate manufacturer (Edgecore or Edge-Core)
        display_name = result["spec"]["display_name"]
        self.assertTrue(
            display_name.startswith("Edge-Core") or display_name.startswith("Edgecore")
        )

        # DCS203 is a mixed-port device with multiple port profiles
        port_profiles = result["spec"]["port_profiles"]
        self.assertGreater(len(port_profiles), 1, "DCS203 should have multiple port profiles")

    def test_parse_virtual_vs(self):
        """Virtual VS profile would use dynamic references - not provided as fixture."""
        # VS profile dynamically references other profiles with lo.OmitBy() filtering
        # This cannot be parsed by our regex-based parser, which is expected
        # We only need to parse static hardware profiles, not virtual test fixtures
        # Since we don't include VS in fixtures (it's not a real hardware profile),
        # we just document that this is intentionally unsupported
        self.skipTest("VS profile is virtual/dynamic and not included in fixtures")

    def test_parser_extracts_port_profiles_correctly(self):
        """Validate PortProfiles extraction for DS5000."""
        fixture_path = self.fixtures_dir / "p_bcm_celestica_ds5000.go"

        result = self.parser.parse_profile_from_file(str(fixture_path))
        port_profiles = result["spec"]["port_profiles"]

        # Should have at least OSFP-800G and SFP28-25G
        self.assertGreaterEqual(len(port_profiles), 2)

        # Validate OSFP-800G structure
        osfp = port_profiles["OSFP-800G"]
        self.assertIn("breakout", osfp)
        self.assertIn("default", osfp["breakout"])
        self.assertIn("supported", osfp["breakout"])

        # Validate SFP28-25G structure (has Speed instead of Breakout)
        sfp = port_profiles["SFP28-25G"]
        # SFP profile might have Speed field or just be simpler
        # Structure varies by port type

    def test_parser_extracts_breakout_modes_from_mode_names(self):
        """Validate breakout mode parsing from mode names like '2x400g'."""
        fixture_path = self.fixtures_dir / "p_bcm_celestica_ds5000.go"

        result = self.parser.parse_profile_from_file(str(fixture_path))
        port_profiles = result["spec"]["port_profiles"]

        osfp_breakout = port_profiles["OSFP-800G"]["breakout"]["supported"]

        # Check that mode names are normalized to lowercase
        for mode_name in osfp_breakout.keys():
            self.assertEqual(mode_name, mode_name.lower())

        # Validate specific modes exist
        self.assertIn("1x800g", osfp_breakout)
        self.assertIn("2x400g", osfp_breakout)

    def test_parser_includes_management_port(self):
        """Parser must include M1 management ports in the parsed Ports dict.

        Regression guard for issues #323 and #324: earlier code only matched E1/N
        patterns and silently dropped M1.
        """
        fixture_path = self.fixtures_dir / "p_bcm_celestica_ds5000.go"

        result = self.parser.parse_profile_from_file(str(fixture_path))
        ports = result["spec"]["ports"]

        # M1 management port must be present
        self.assertIn("M1", ports, "Parser must include M1 management port (regression: #323)")
        m1 = ports["M1"]
        self.assertTrue(m1.get("management"), "M1 port_data must carry management=True")
        self.assertIn("nos_name", m1, "M1 must have nos_name extracted")

    def test_parse_celestica_ds2000(self):
        """Parse Celestica DS2000 profile — validates management port + data port counts."""
        fixture_path = self.fixtures_dir / "p_bcm_celestica_ds2000.go"

        result = self.parser.parse_profile_from_file(str(fixture_path))

        self.assertEqual(result["object_meta"]["name"], "celestica-ds2000")
        self.assertTrue(result["spec"]["display_name"].startswith("Celestica"))

        ports = result["spec"]["ports"]

        # DS2000: 48 SFP28-25G + 8 QSFP28-100G (some via string concat, skipped) + M1 = 57 total
        # E1/50-55 use Go constant concatenation → Profile field not matched → 6 ports have no
        # usable profile, but they are still parsed as port entries.
        self.assertIn("M1", ports, "DS2000 must include M1 management port")
        self.assertTrue(ports["M1"].get("management"), "M1 must have management=True")

        # E1/1-48 data ports present
        for i in range(1, 49):
            self.assertIn(f"E1/{i}", ports, f"DS2000 must have E1/{i}")
            self.assertEqual(ports[f"E1/{i}"]["profile"], "SFP28-25G")

        # MCLAG capability
        self.assertTrue(result["spec"]["features"]["MCLAG"], "DS2000 supports MCLAG")

    def test_parser_handles_mclag_feature_flag(self):
        """Validate MCLAG feature extraction."""
        fixture_path = self.fixtures_dir / "p_bcm_celestica_ds5000.go"

        result = self.parser.parse_profile_from_file(str(fixture_path))
        features = result["spec"]["features"]

        self.assertIn("MCLAG", features)
        self.assertIsInstance(features["MCLAG"], bool)

    def test_parser_raises_error_for_invalid_file(self):
        """Parser should raise error for non-existent profile file."""
        nonexistent_path = self.fixtures_dir / "p_bcm_nonexistent_device.go"

        with self.assertRaises(FileNotFoundError):
            self.parser.parse_profile_from_file(str(nonexistent_path))

    def test_parser_validates_required_fields(self):
        """Parser should validate presence of required fields."""
        fixture_path = self.fixtures_dir / "p_bcm_celestica_ds5000.go"

        result = self.parser.parse_profile_from_file(str(fixture_path))

        # Required top-level keys
        self.assertIn("object_meta", result)
        self.assertIn("spec", result)

        # Required ObjectMeta fields
        self.assertIn("name", result["object_meta"])

        # Required Spec fields
        self.assertIn("display_name", result["spec"])
        self.assertIn("ports", result["spec"])
        self.assertIn("port_profiles", result["spec"])
        self.assertIn("features", result["spec"])
