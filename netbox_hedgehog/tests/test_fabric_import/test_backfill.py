"""
Tests for fix_ds5000_interface_types management command (DIET-148).

These tests validate the backfill command that corrects interface types
for DS5000 variants from QSFP-DD to OSFP for 800G ports.
"""

from io import StringIO
from django.core.management import call_command
from django.test import TestCase

from dcim.models import DeviceType, Manufacturer, InterfaceTemplate


class FixDS5000InterfaceTypesTestCase(TestCase):
    """Test backfill command for DS5000 interface type fix."""

    DS5000_MODELS = ["DS5000", "celestica-ds5000", "celestica-ds5000-clsp"]

    def setUp(self):
        """Create DS5000 device types with wrong interface types."""
        self.manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Celestica",
            defaults={"slug": "celestica"}
        )

        # Create 3 DS5000 variants with wrong interface types
        for model_name in self.DS5000_MODELS:
            dt, _ = DeviceType.objects.get_or_create(
                manufacturer=self.manufacturer,
                model=model_name,
                defaults={"slug": model_name.lower()},
            )

            # Ensure a clean slate for interface templates
            dt.interfacetemplates.all().delete()

            # Create 64 interfaces with WRONG type (qsfpdd instead of osfp)
            for i in range(1, 65):
                InterfaceTemplate.objects.create(
                    device_type=dt,
                    name=f"E1/{i}",
                    type="800gbase-x-qsfpdd"  # WRONG
                )

    def test_dry_run_shows_changes_without_applying(self):
        """Dry-run should show what would change without changing data."""
        out = StringIO()

        # Run in dry-run mode
        call_command("fix_ds5000_interface_types", "--dry-run", stdout=out)

        output = out.getvalue()

        # Verify output mentions all 3 device types
        self.assertIn("DS5000", output)
        self.assertIn("celestica-ds5000", output)
        self.assertIn("celestica-ds5000-clsp", output)

        # Verify shows 192 total interfaces
        self.assertIn("192", output)

        # Verify no changes made
        wrong_interfaces = InterfaceTemplate.objects.filter(
            device_type__model__in=self.DS5000_MODELS,
            type="800gbase-x-qsfpdd",
        )
        self.assertEqual(wrong_interfaces.count(), 192, "Dry-run should not change data")

    def test_backfill_fixes_all_ds5000_interfaces(self):
        """Running command should fix all DS5000 interface types."""
        out = StringIO()

        # Verify broken state
        wrong_before = InterfaceTemplate.objects.filter(
            device_type__model__in=self.DS5000_MODELS,
            type="800gbase-x-qsfpdd",
        ).count()
        correct_before = InterfaceTemplate.objects.filter(
            device_type__model__in=self.DS5000_MODELS,
            type="800gbase-x-osfp",
        ).count()
        self.assertEqual(wrong_before, 192)
        self.assertEqual(correct_before, 0)

        # Run fix
        call_command("fix_ds5000_interface_types", stdout=out)

        # Verify fixed state
        wrong_after = InterfaceTemplate.objects.filter(
            device_type__model__in=self.DS5000_MODELS,
            type="800gbase-x-qsfpdd",
        ).count()
        correct_after = InterfaceTemplate.objects.filter(
            device_type__model__in=self.DS5000_MODELS,
            type="800gbase-x-osfp",
        ).count()
        self.assertEqual(wrong_after, 0, "Should have no QSFP-DD 800G interfaces")
        self.assertEqual(correct_after, 192, "Should have 192 OSFP 800G interfaces")

        # Verify output mentions success
        output = out.getvalue()
        self.assertIn("OK", output)
        self.assertIn("192", output)

    def test_backfill_is_idempotent(self):
        """Running command multiple times should be safe."""
        # Run fix twice
        call_command("fix_ds5000_interface_types")
        call_command("fix_ds5000_interface_types")

        # Should still have correct state
        correct = InterfaceTemplate.objects.filter(
            device_type__model__in=self.DS5000_MODELS,
            type="800gbase-x-osfp",
        ).count()
        self.assertEqual(correct, 192)

    def test_backfill_skips_non_celestica_manufacturers(self):
        """Safety check: skip device types with wrong manufacturer."""
        # Create fake DS5000 under wrong manufacturer
        wrong_mfg = Manufacturer.objects.create(
            name="FakeVendor",
            slug="fakevendor"
        )
        fake_dt = DeviceType.objects.create(
            manufacturer=wrong_mfg,
            model="DS5000",
            slug="fake-ds5000"
        )
        InterfaceTemplate.objects.create(
            device_type=fake_dt,
            name="E1/1",
            type="800gbase-x-qsfpdd"
        )

        out = StringIO()
        call_command("fix_ds5000_interface_types", stdout=out)

        # Should skip fake device type
        output = out.getvalue()
        self.assertIn("Skipping", output)
        self.assertIn("FakeVendor", output)

        # Fake device type should remain unchanged
        fake_iface = fake_dt.interfacetemplates.first()
        self.assertEqual(fake_iface.type, "800gbase-x-qsfpdd", "Should not modify non-Celestica device")
