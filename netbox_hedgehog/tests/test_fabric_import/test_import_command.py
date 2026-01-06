"""
Tests for import_fabric_profiles management command (DIET-144).
"""

from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.test import TestCase

from dcim.models import DeviceType, Manufacturer
from netbox_hedgehog.models.topology_planning import DeviceTypeExtension


class ImportFabricProfilesCommandTestCase(TestCase):
    """Tests for import_fabric_profiles management command."""

    def setUp(self):
        """Set up test fixtures directory."""
        self.fixtures_dir = Path(__file__).parent / "fixtures"

    def test_command_dry_run_mode(self):
        """Dry run mode should not create any records."""
        out = StringIO()

        # Record counts before import
        initial_device_types = DeviceType.objects.count()
        initial_extensions = DeviceTypeExtension.objects.count()

        call_command(
            "import_fabric_profiles",
            source_dir=str(self.fixtures_dir),
            dry_run=True,
            stdout=out
        )

        output = out.getvalue()

        # Should indicate dry run
        self.assertIn("DRY RUN", output)
        self.assertIn("No changes made", output)

        # Should show profiles found
        self.assertIn("celestica-ds5000", output)
        self.assertIn("celestica-ds3000", output)
        self.assertIn("edgecore-dcs203", output)

        # Should not create any new records
        self.assertEqual(DeviceType.objects.count(), initial_device_types)
        self.assertEqual(DeviceTypeExtension.objects.count(), initial_extensions)

    def test_command_imports_all_profiles_from_local_directory(self):
        """Import all profiles from local directory."""
        out = StringIO()

        call_command(
            "import_fabric_profiles",
            source_dir=str(self.fixtures_dir),
            stdout=out
        )

        output = out.getvalue()

        # Should show success
        self.assertIn("Import Complete", output)
        self.assertIn("Profiles processed: 3", output)

        # Should create device types (check specific models, not total count)
        self.assertTrue(DeviceType.objects.filter(model="celestica-ds5000").exists())
        self.assertTrue(DeviceType.objects.filter(model="celestica-ds3000").exists())
        self.assertTrue(DeviceType.objects.filter(model="edgecore-dcs203").exists())

        # Verify DS5000 details
        ds5000 = DeviceType.objects.get(model="celestica-ds5000")
        self.assertEqual(ds5000.manufacturer.name, "Celestica")
        self.assertEqual(ds5000.interfacetemplates.count(), 66)

        ext = DeviceTypeExtension.objects.get(device_type=ds5000)
        self.assertEqual(ext.native_speed, 800)
        self.assertIn("1x800g", ext.supported_breakouts)

    def test_command_filters_by_profile_names(self):
        """--profiles flag should filter which profiles are imported."""
        out = StringIO()

        call_command(
            "import_fabric_profiles",
            source_dir=str(self.fixtures_dir),
            profiles="celestica-ds5000",
            stdout=out
        )

        output = out.getvalue()

        # Should only import 1 profile
        self.assertIn("Profiles processed: 1", output)

        # Should create only the filtered device type
        self.assertTrue(DeviceType.objects.filter(model="celestica-ds5000").exists())
        self.assertFalse(DeviceType.objects.filter(model="celestica-ds3000").exists())

    def test_command_handles_multiple_profile_filter(self):
        """--profiles flag should handle comma-separated list."""
        out = StringIO()

        call_command(
            "import_fabric_profiles",
            source_dir=str(self.fixtures_dir),
            profiles="celestica-ds5000,celestica-ds3000",
            stdout=out
        )

        output = out.getvalue()

        # Should import 2 profiles
        self.assertIn("Profiles processed: 2", output)

        # Should create the filtered device types
        self.assertTrue(DeviceType.objects.filter(model="celestica-ds5000").exists())
        self.assertTrue(DeviceType.objects.filter(model="celestica-ds3000").exists())
        self.assertFalse(DeviceType.objects.filter(model="edgecore-dcs203").exists())

    def test_command_does_not_overwrite_existing_data(self):
        """Re-importing should not overwrite existing extension data."""
        # Create a device type with custom extension data
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Celestica",
            defaults={"slug": "celestica"}
        )
        device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model="celestica-ds5000",
            defaults={"slug": "celestica-ds5000"}
        )

        # Create extension with user-modified values
        ext = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=999,  # User-modified value
            supported_breakouts=["custom-breakout"],  # User-modified value
            mclag_capable=True
        )

        out = StringIO()

        # Import the same profile
        call_command(
            "import_fabric_profiles",
            source_dir=str(self.fixtures_dir),
            profiles="celestica-ds5000",
            stdout=out
        )

        # Refresh extension from DB
        ext.refresh_from_db()

        # User-modified values should NOT be overwritten
        self.assertEqual(ext.native_speed, 999, "Should preserve user-modified native_speed")
        self.assertEqual(
            ext.supported_breakouts,
            ["custom-breakout"],
            "Should preserve user-modified supported_breakouts"
        )
        self.assertTrue(ext.mclag_capable, "Should preserve user-modified mclag_capable")

    def test_command_reports_correct_stats_on_reimport(self):
        """Re-importing should report correct created vs updated stats."""
        out1 = StringIO()

        # First import
        call_command(
            "import_fabric_profiles",
            source_dir=str(self.fixtures_dir),
            profiles="celestica-ds5000",
            stdout=out1
        )

        output1 = out1.getvalue()
        self.assertIn("Device types created: 1", output1)
        self.assertIn("Device types updated: 0", output1)

        out2 = StringIO()

        # Re-import same profile
        call_command(
            "import_fabric_profiles",
            source_dir=str(self.fixtures_dir),
            profiles="celestica-ds5000",
            stdout=out2
        )

        output2 = out2.getvalue()
        self.assertIn("Device types created: 0", output2)
        self.assertIn("Device types updated: 1", output2)

    def test_command_invalid_source_directory(self):
        """Command should raise error for non-existent directory."""
        with self.assertRaises(Exception):
            call_command(
                "import_fabric_profiles",
                source_dir="/nonexistent/directory"
            )

    @patch('netbox_hedgehog.utils.fabric_import.FabricProfileGoParser.parse_profile_from_url')
    def test_command_github_mode_default_ref(self, mock_parse):
        """GitHub mode should use default ref (master)."""
        # Mock parser to avoid actual network calls
        mock_parse.return_value = {
            "object_meta": {"name": "test-profile"},
            "spec": {
                "display_name": "Test Profile",
                "ports": {},
                "port_profiles": {
                    "TEST": {
                        "breakout": {
                            "default": "1x100G",
                            "supported": {"1x100g": {}}
                        }
                    }
                },
                "features": {"MCLAG": False}
            }
        }

        out = StringIO()

        # Test dry-run to avoid actual import
        call_command(
            "import_fabric_profiles",
            dry_run=True,
            stdout=out
        )

        output = out.getvalue()

        # Should use master branch
        self.assertIn("fabric@master", output)

    def test_command_creates_manufacturers(self):
        """Command should create manufacturers as needed."""
        # Ensure manufacturers don't exist before test
        Manufacturer.objects.filter(name__in=["Celestica-Test", "Edgecore"]).delete()

        # Modify one fixture to use a test manufacturer name
        # Since we can't modify the fixtures easily, just check that manufacturers exist after import
        out = StringIO()

        call_command(
            "import_fabric_profiles",
            source_dir=str(self.fixtures_dir),
            stdout=out
        )

        # Should have created/retrieved manufacturers (using seed data names)
        self.assertTrue(Manufacturer.objects.filter(name="Celestica").exists())
        self.assertTrue(Manufacturer.objects.filter(name="Edge-Core").exists())

    def test_command_shows_summary_stats(self):
        """Command output should include summary statistics."""
        out = StringIO()

        call_command(
            "import_fabric_profiles",
            source_dir=str(self.fixtures_dir),
            stdout=out
        )

        output = out.getvalue()

        # Should show summary
        self.assertIn("Profiles processed:", output)
        self.assertIn("Device types created:", output)
        self.assertIn("Extensions created:", output)
        self.assertIn("Interface templates created:", output)
        self.assertIn("Import Complete", output)
