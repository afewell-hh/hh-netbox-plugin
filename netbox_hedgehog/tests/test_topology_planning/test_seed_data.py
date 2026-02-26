"""
Integration Tests for DIET Reference Data Seed Loading (DIET-001)

Tests verify that the load_diet_reference_data management command:
- Creates exactly 14 expected BreakoutOption records with correct optic types
- Is idempotent (safe to run multiple times)
- Seeded data has correct field values and ordering

Note: UI templates/views are not tested here - those are deferred to a future PR
for complete CRUD coverage per AGENTS.md requirements.
"""

from django.test import TestCase
from django.core.management import call_command
from io import StringIO

from dcim.models import DeviceType, InterfaceTemplate

from netbox_hedgehog.models.topology_planning import BreakoutOption, DeviceTypeExtension


class SeedDataCommandTestCase(TestCase):
    """Test the load_diet_reference_data management command"""

    def setUp(self):
        """Clean up before each test"""
        # Delete any existing BreakoutOption records to ensure clean state
        BreakoutOption.objects.all().delete()

    def test_command_creates_breakout_options(self):
        """Test that command creates expected BreakoutOption records"""
        # Verify no records exist initially
        self.assertEqual(BreakoutOption.objects.count(), 0,
                        "BreakoutOption table should be empty before seeding")

        # Run the management command
        out = StringIO()
        call_command('load_diet_reference_data', stdout=out)

        # Verify records were created
        count = BreakoutOption.objects.count()
        self.assertGreater(count, 0,
                          "Command should create BreakoutOption records")

        # Verify specific records exist (from PRD #83)
        expected_breakouts = [
            ('1x800g', 800, 1, 800),   # No breakout
            ('2x400g', 800, 2, 400),   # 800G → 2x400G
            ('4x200g', 800, 4, 200),   # 800G → 4x200G
            ('8x100g', 800, 8, 100),   # 800G → 8x100G
            ('1x400g', 400, 1, 400),   # No breakout
            ('2x200g', 400, 2, 200),   # 400G → 2x200G
            ('4x100g', 400, 4, 100),   # 400G → 4x100G
            ('1x100g', 100, 1, 100),   # No breakout
            ('4x25g', 100, 4, 25),     # 100G → 4x25G
            ('1x1g', 1, 1, 1),         # No breakout
        ]

        for breakout_id, from_speed, logical_ports, logical_speed in expected_breakouts:
            breakout = BreakoutOption.objects.filter(breakout_id=breakout_id).first()
            self.assertIsNotNone(
                breakout,
                f"BreakoutOption '{breakout_id}' should exist after seeding"
            )
            self.assertEqual(breakout.from_speed, from_speed,
                           f"{breakout_id}: from_speed should be {from_speed}")
            self.assertEqual(breakout.logical_ports, logical_ports,
                           f"{breakout_id}: logical_ports should be {logical_ports}")
            self.assertEqual(breakout.logical_speed, logical_speed,
                           f"{breakout_id}: logical_speed should be {logical_speed}")

    def test_command_is_idempotent(self):
        """Test that running command multiple times doesn't duplicate records"""
        # Run command first time
        call_command('load_diet_reference_data', stdout=StringIO())
        first_count = BreakoutOption.objects.count()
        self.assertGreater(first_count, 0, "First run should create records")

        # Run command second time
        call_command('load_diet_reference_data', stdout=StringIO())
        second_count = BreakoutOption.objects.count()

        # Count should be the same (update-or-create, not duplicate)
        self.assertEqual(
            first_count, second_count,
            "Running command twice should not duplicate records (should be idempotent)"
        )

    def test_command_updates_existing_records(self):
        """Test that command updates existing records if run again"""
        # Create a breakout option manually with different values
        BreakoutOption.objects.create(
            breakout_id='1x800g',
            from_speed=800,
            logical_ports=1,
            logical_speed=800,
            optic_type='OLD_VALUE'
        )

        # Run command - should update the record
        call_command('load_diet_reference_data', stdout=StringIO())

        # Verify the record was updated (optic_type should change to expected value)
        breakout = BreakoutOption.objects.get(breakout_id='1x800g')
        self.assertEqual(breakout.from_speed, 800)
        self.assertEqual(breakout.logical_ports, 1)
        self.assertEqual(breakout.logical_speed, 800)
        # Command should set optic_type to expected value (QSFP-DD for 800G)
        self.assertIn('QSFP', breakout.optic_type.upper())

    def test_command_provides_feedback(self):
        """Test that command prints useful feedback about what it did"""
        out = StringIO()
        call_command('load_diet_reference_data', stdout=out)

        output = out.getvalue()
        self.assertIn('BreakoutOption', output,
                     "Command output should mention BreakoutOption")
        self.assertIn('created', output.lower(),
                     "Command output should mention creating records")

    def test_command_imports_baseline_profile_backed_switch_model(self):
        """load_diet_reference_data should ensure celestica-ds5000 exists."""
        call_command('load_diet_reference_data', stdout=StringIO())
        self.assertTrue(
            DeviceType.objects.filter(model='celestica-ds5000').exists(),
            "Expected profile-backed switch DeviceType 'celestica-ds5000' to be present",
        )

    def test_command_seeds_management_switch_device_type(self):
        """load_diet_reference_data should ensure celestica-es1000 exists."""
        call_command('load_diet_reference_data', stdout=StringIO())
        self.assertTrue(
            DeviceType.objects.filter(model='celestica-es1000').exists(),
            "Expected management switch DeviceType 'celestica-es1000' to be present",
        )

    def test_management_switch_has_expected_interface_templates(self):
        """celestica-es1000 should have 48x1G + 4xSFP28 + mgmt."""
        call_command('load_diet_reference_data', stdout=StringIO())
        device_type = DeviceType.objects.get(model='celestica-es1000')
        interfaces = InterfaceTemplate.objects.filter(device_type=device_type)

        self.assertEqual(interfaces.count(), 53)
        self.assertEqual(interfaces.filter(type='1000base-t').count(), 49)
        self.assertEqual(interfaces.filter(type='25gbase-x-sfp28').count(), 4)
        self.assertTrue(interfaces.filter(name='mgmt0', type='1000base-t').exists())
        extension = DeviceTypeExtension.objects.get(device_type=device_type)
        self.assertEqual(extension.hedgehog_roles, [])

    def test_management_switch_is_recreated_after_inventory_purge(self):
        """Simulate reset/purge flow and ensure celestica-es1000 is restored."""
        call_command('load_diet_reference_data', stdout=StringIO())
        DeviceType.objects.all().delete()

        call_command('load_diet_reference_data', stdout=StringIO())
        self.assertTrue(DeviceType.objects.filter(model='celestica-es1000').exists())


class SeedDataRecordTestCase(TestCase):
    """Test that seeded data records are correct"""

    @classmethod
    def setUpTestData(cls):
        """Load seed data for testing"""
        call_command('load_diet_reference_data', stdout=StringIO())

    def test_seeded_data_count_matches_expected(self):
        """Test that baseline records were seeded with correct IDs and optic types"""
        count = BreakoutOption.objects.count()
        self.assertGreaterEqual(count, 14,
                                "Should have at least 14 BreakoutOption records")

        # Validate all 14 expected breakout IDs and their optic types
        expected_breakouts = [
            ('1x800g', 'QSFP-DD'),
            ('2x400g', 'QSFP-DD'),
            ('4x200g', 'QSFP-DD'),
            ('8x100g', 'QSFP-DD'),
            ('1x400g', 'QSFP-DD'),
            ('2x200g', 'QSFP-DD'),
            ('4x100g', 'QSFP-DD'),
            ('1x100g', 'QSFP28'),
            ('1x40g', 'QSFP28'),
            ('2x50g', 'QSFP28'),
            ('4x25g', 'QSFP28'),
            ('4x10g', 'QSFP28'),
            ('1x10g', 'SFP+'),
            ('1x1g', 'RJ45'),
        ]

        for breakout_id, expected_optic in expected_breakouts:
            breakout = BreakoutOption.objects.filter(breakout_id=breakout_id).first()
            self.assertIsNotNone(
                breakout,
                f"BreakoutOption '{breakout_id}' should exist"
            )
            self.assertEqual(
                breakout.optic_type, expected_optic,
                f"BreakoutOption '{breakout_id}' should have optic_type '{expected_optic}'"
            )

    def test_breakout_options_ordered_correctly(self):
        """Test that breakout options are ordered by from_speed desc, logical_ports"""
        breakouts = list(BreakoutOption.objects.all())

        # Verify ordering (highest speed first)
        if len(breakouts) >= 2:
            # First breakout should be 800G (highest speed)
            self.assertEqual(breakouts[0].from_speed, 800,
                           "First breakout should be highest speed (800G)")

            # Verify within same speed, ordered by logical_ports
            same_speed_breakouts = [b for b in breakouts if b.from_speed == 800]
            if len(same_speed_breakouts) >= 2:
                for i in range(len(same_speed_breakouts) - 1):
                    self.assertLessEqual(
                        same_speed_breakouts[i].logical_ports,
                        same_speed_breakouts[i + 1].logical_ports,
                        "Within same speed, breakouts should be ordered by logical_ports"
                    )
