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

from dcim.models import DeviceType, InterfaceTemplate, ModuleType, ModuleTypeProfile

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
        )

        # Run command - should update the record
        call_command('load_diet_reference_data', stdout=StringIO())

        # Verify the record was updated
        breakout = BreakoutOption.objects.get(breakout_id='1x800g')
        self.assertEqual(breakout.from_speed, 800)
        self.assertEqual(breakout.logical_ports, 1)
        self.assertEqual(breakout.logical_speed, 800)
        # RED: optic_type field must be removed from BreakoutOption
        self.assertFalse(hasattr(breakout, 'optic_type'), "BreakoutOption.optic_type field must be removed")

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

    def test_command_seeds_generic_server_device_types(self):
        """load_diet_reference_data should ensure all three generic server DeviceTypes exist."""
        call_command('load_diet_reference_data', stdout=StringIO())
        for model in ('GPU-Server-FE', 'GPU-Server-FE-BE', 'Storage-Server-200G'):
            self.assertTrue(
                DeviceType.objects.filter(model=model).exists(),
                f"Expected generic server DeviceType '{model}' to be present",
            )

    def test_generic_server_device_types_have_correct_interfaces(self):
        """Generic server DeviceTypes should have the expected interface templates."""
        call_command('load_diet_reference_data', stdout=StringIO())

        fe = DeviceType.objects.get(model='GPU-Server-FE')
        self.assertEqual(
            InterfaceTemplate.objects.filter(device_type=fe).count(), 2
        )
        self.assertTrue(
            InterfaceTemplate.objects.filter(
                device_type=fe, name='eth1', type='200gbase-x-qsfp56'
            ).exists()
        )

        fe_be = DeviceType.objects.get(model='GPU-Server-FE-BE')
        self.assertEqual(
            InterfaceTemplate.objects.filter(device_type=fe_be).count(), 10
        )
        self.assertEqual(
            InterfaceTemplate.objects.filter(
                device_type=fe_be, type='400gbase-x-qsfpdd'
            ).count(), 8
        )

    def test_generic_server_device_types_recreated_after_purge(self):
        """Generic server DeviceTypes should be restored after a DeviceType purge."""
        call_command('load_diet_reference_data', stdout=StringIO())
        DeviceType.objects.all().delete()

        call_command('load_diet_reference_data', stdout=StringIO())

        for model in ('GPU-Server-FE', 'GPU-Server-FE-BE', 'Storage-Server-200G'):
            self.assertTrue(
                DeviceType.objects.filter(model=model).exists(),
                f"'{model}' must be recreated after purge+reseed",
            )

    def test_command_recreates_network_transceiver_profile_after_inventory_purge(self):
        """load_diet_reference_data should restore Network Transceiver profile after purge."""
        # Must delete ModuleTypes before ModuleTypeProfile to avoid ProtectedError
        # (mirrors what reset_local_dev.sh --purge-inventory does in the container)
        ModuleType.objects.all().delete()
        ModuleTypeProfile.objects.all().delete()

        call_command('load_diet_reference_data', stdout=StringIO())

        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        self.assertIsNotNone(profile, "Network Transceiver profile must be recreated")
        cage_enum = (
            profile.schema.get('properties', {})
            .get('cage_type', {})
            .get('enum', [])
        )
        self.assertIn('OSFP', cage_enum)
        self.assertIn('QSFP56', cage_enum)

    def test_command_seeds_celestica_transceiver_module_inventory(self):
        """load_diet_reference_data should ensure static Celestica optics exist."""
        call_command('load_diet_reference_data', stdout=StringIO())

        optic = ModuleType.objects.filter(model='R4113-A9311-DR').first()
        self.assertIsNotNone(optic, "Expected Celestica DR8 optic ModuleType")
        self.assertEqual(optic.part_number, 'R4113-A9311-DR')
        self.assertEqual(optic.profile.name, 'Network Transceiver')
        self.assertEqual(optic.description, '800G OSFP112 DR8 (MPO-16)')
        self.assertEqual(optic.attribute_data.get('cage_type'), 'OSFP')
        self.assertEqual(optic.attribute_data.get('reach_class'), 'DR')
        self.assertEqual(optic.interfacetemplates.count(), 0)

    def test_command_seeds_management_transceiver_module_inventory(self):
        """load_diet_reference_data should ensure 25G/10G/1G management optics exist."""
        call_command('load_diet_reference_data', stdout=StringIO())

        eps_200g = ModuleType.objects.filter(model='T1-QSFP112-200G-SR2').first()
        self.assertIsNotNone(eps_200g, "Expected EPS Global 200G QSFP112 SR2 ModuleType")
        self.assertEqual(eps_200g.profile.name, 'Network Transceiver')
        self.assertEqual(eps_200g.attribute_data.get('cage_type'), 'QSFP112')
        self.assertEqual(eps_200g.attribute_data.get('standard'), '200GBASE-SR2')

        eps_400g = ModuleType.objects.filter(model='T1-OSFP112-400G-SR4').first()
        self.assertIsNotNone(eps_400g, "Expected EPS Global 400G OSFP SR4 ModuleType")
        self.assertEqual(eps_400g.attribute_data.get('cage_type'), 'OSFP')
        self.assertEqual(eps_400g.attribute_data.get('standard'), '400GBASE-SR4')

        eps_100g = ModuleType.objects.filter(model='T1-QSFP28-100G-SR4').first()
        self.assertIsNotNone(eps_100g, "Expected EPS Global 100G QSFP28 SR4 ModuleType")
        self.assertEqual(eps_100g.attribute_data.get('cage_type'), 'QSFP28')
        self.assertEqual(eps_100g.attribute_data.get('standard'), '100GBASE-SR4')

        celestica_100g_dr = ModuleType.objects.filter(model='R4113-75111-DR').first()
        self.assertIsNotNone(celestica_100g_dr, "Expected Celestica 100G QSFP28 DR1 ModuleType")
        self.assertEqual(celestica_100g_dr.attribute_data.get('cage_type'), 'QSFP28')
        self.assertEqual(celestica_100g_dr.attribute_data.get('standard'), '100GBASE-DR')

        celestica_100g_sr = ModuleType.objects.filter(model='R4113-75210-SR').first()
        self.assertIsNotNone(celestica_100g_sr, "Expected Celestica 100G QSFP28 SR4 ModuleType")
        self.assertEqual(celestica_100g_sr.attribute_data.get('cage_type'), 'QSFP28')
        self.assertEqual(celestica_100g_sr.attribute_data.get('standard'), '100GBASE-SR4')

        celestica_100g_4x25_dac = ModuleType.objects.filter(model='R4113-75C41-03').first()
        self.assertIsNotNone(celestica_100g_4x25_dac, "Expected Celestica 100G -> 4x25G breakout DAC ModuleType")
        self.assertEqual(celestica_100g_4x25_dac.attribute_data.get('cage_type'), 'QSFP28')
        self.assertEqual(celestica_100g_4x25_dac.attribute_data.get('standard'), '100GBASE-CR4')
        self.assertEqual(celestica_100g_4x25_dac.attribute_data.get('breakout_topology'), '4x25g')

        sfp28 = ModuleType.objects.filter(model='SFP28-25GBASE-SR').first()
        self.assertIsNotNone(sfp28, "Expected generic 25G SFP28 SR ModuleType")
        self.assertEqual(sfp28.profile.name, 'Network Transceiver')
        self.assertEqual(sfp28.attribute_data.get('cage_type'), 'SFP28')
        self.assertEqual(sfp28.attribute_data.get('medium'), 'MMF')

        sfp_plus = ModuleType.objects.filter(model='SFP+-10GBASE-SR').first()
        self.assertIsNotNone(sfp_plus, "Expected generic 10G SFP+ SR ModuleType")
        self.assertEqual(sfp_plus.attribute_data.get('cage_type'), 'SFP+')

        rj45 = ModuleType.objects.filter(model='RJ45-1000BASE-T').first()
        self.assertIsNotNone(rj45, "Expected generic 1G copper RJ45 ModuleType")
        self.assertEqual(rj45.attribute_data.get('cage_type'), 'RJ45')
        self.assertEqual(rj45.attribute_data.get('medium'), 'Copper')
        self.assertEqual(rj45.attribute_data.get('connector'), 'RJ45')
        self.assertEqual(rj45.attribute_data.get('standard'), '1000BASE-T')
        self.assertEqual(rj45.attribute_data.get('reach_class'), 'Copper')
        self.assertEqual(rj45.attribute_data.get('cable_assembly_type'), 'none')

    def test_command_seeds_static_nic_module_inventory(self):
        """load_diet_reference_data should ensure static NIC ModuleTypes exist."""
        call_command('load_diet_reference_data', stdout=StringIO())

        nic = ModuleType.objects.filter(model='AOC-CX766003N-SQ0').first()
        self.assertIsNotNone(nic, "Expected ConnectX-7 400G OSFP NIC ModuleType")
        self.assertEqual(nic.part_number, 'AOC-CX766003N-SQ0')
        self.assertEqual(nic.description, '1x NDR400G IB/EN OSFP Gen5 x16 CX7')
        self.assertEqual(
            list(nic.interfacetemplates.order_by('name').values_list('name', flat=True)),
            ['port0'],
        )

    def test_command_restores_module_inventory_after_purge(self):
        """Simulate reset/purge flow and ensure static ModuleTypes are restored."""
        call_command('load_diet_reference_data', stdout=StringIO())
        ModuleType.objects.all().delete()
        ModuleTypeProfile.objects.all().delete()

        call_command('load_diet_reference_data', stdout=StringIO())

        self.assertTrue(ModuleType.objects.filter(model='R4113-A9311-DR').exists())
        self.assertTrue(ModuleType.objects.filter(model='AOC-CX766003N-SQ0').exists())


class SeedDataRecordTestCase(TestCase):
    """Test that seeded data records are correct"""

    @classmethod
    def setUpTestData(cls):
        """Load seed data for testing"""
        call_command('load_diet_reference_data', stdout=StringIO())

    def test_seeded_data_count_matches_expected(self):
        """Test that baseline records were seeded with correct IDs"""
        count = BreakoutOption.objects.count()
        self.assertGreaterEqual(count, 14,
                                "Should have at least 14 BreakoutOption records")

        # Validate all 14 expected breakout IDs exist
        expected_breakout_ids = [
            '1x800g', '2x400g', '4x200g', '8x100g',
            '1x400g', '2x200g', '4x100g',
            '1x100g', '1x40g', '2x50g', '4x25g', '4x10g',
            '1x10g', '1x1g',
        ]

        for breakout_id in expected_breakout_ids:
            breakout = BreakoutOption.objects.filter(breakout_id=breakout_id).first()
            self.assertIsNotNone(
                breakout,
                f"BreakoutOption '{breakout_id}' should exist"
            )
            # RED: optic_type field must be removed from BreakoutOption
            self.assertFalse(
                hasattr(breakout, 'optic_type'),
                f"BreakoutOption.optic_type field must be removed (found on '{breakout_id}')"
            )

    def test_breakout_options_ordered_correctly(self):
        """Test that breakout options are ordered by from_speed desc, logical_ports"""
        breakouts = list(BreakoutOption.objects.order_by('-from_speed', 'logical_ports'))

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

    def test_static_module_inventory_counts_are_seeded(self):
        """Reference data seed should include the expected static optics and NICs."""
        self.assertGreaterEqual(
            ModuleType.objects.filter(model__startswith='R4113-').count(),
            10,
            "Expected at least the 10 Celestica transceiver SKUs from the repo catalog",
        )
        self.assertTrue(
            ModuleType.objects.filter(model='AOC-A100G-B2CM-O').exists(),
            "Expected Supermicro AOC-A100G-B2CM-O NIC ModuleType",
        )
