"""
Tests for migration 0048: OSFP transceiver ModuleType seeding (DIET-434).

Confirms that after migration runs, both OSFP records exist with the
correct Network Transceiver profile and expected attribute_data.

These tests depend on the seeded data being present (via --keepdb or
a freshly applied migration run) rather than creating test fixtures.
"""

from django.test import TestCase

from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile


class OSFPTransceiverSeedTestCase(TestCase):
    """Verify both OSFP transceiver ModuleTypes are seeded correctly."""

    def _get_generic(self):
        return Manufacturer.objects.filter(name='Generic').first()

    def _get_profile(self):
        return ModuleTypeProfile.objects.filter(name='Network Transceiver').first()

    # ------------------------------------------------------------------
    # T1: Network Transceiver profile exists and includes OSFP in cage_type
    # ------------------------------------------------------------------

    def test_network_transceiver_profile_includes_osfp(self):
        """Network Transceiver profile schema enum includes OSFP."""
        profile = self._get_profile()
        self.assertIsNotNone(profile, "Network Transceiver profile must exist")
        cage_enum = (
            profile.schema
            .get('properties', {})
            .get('cage_type', {})
            .get('enum', [])
        )
        self.assertIn('OSFP', cage_enum,
                      "cage_type enum must include OSFP after migration 0044")

    # ------------------------------------------------------------------
    # T2: OSFP-400G-DR4 exists with correct profile
    # ------------------------------------------------------------------

    def test_osfp_400g_dr4_exists_with_transceiver_profile(self):
        """OSFP-400G-DR4 ModuleType exists and carries the Network Transceiver profile."""
        generic = self._get_generic()
        self.assertIsNotNone(generic, "Generic manufacturer must exist")
        mt = ModuleType.objects.filter(
            manufacturer=generic, model='OSFP-400G-DR4'
        ).first()
        self.assertIsNotNone(mt, "OSFP-400G-DR4 ModuleType must be seeded")
        self.assertIsNotNone(mt.profile, "OSFP-400G-DR4 must have a profile")
        self.assertEqual(mt.profile.name, 'Network Transceiver')

    # ------------------------------------------------------------------
    # T3: OSFP-400G-DR4 attribute_data correctness
    # ------------------------------------------------------------------

    def test_osfp_400g_dr4_attribute_data(self):
        """OSFP-400G-DR4 attribute_data has correct cage_type, medium, standard, reach_class."""
        generic = self._get_generic()
        mt = ModuleType.objects.filter(
            manufacturer=generic, model='OSFP-400G-DR4'
        ).first()
        self.assertIsNotNone(mt)
        data = mt.attribute_data or {}
        self.assertEqual(data.get('cage_type'), 'OSFP')
        self.assertEqual(data.get('medium'), 'SMF')
        self.assertEqual(data.get('standard'), '400GBASE-DR4')
        self.assertEqual(data.get('reach_class'), 'DR')
        self.assertEqual(data.get('connector'), 'MPO-12')
        self.assertEqual(data.get('wavelength_nm'), 1310)
        self.assertEqual(data.get('lane_count'), 4)
        self.assertEqual(data.get('host_serdes_gbps_per_lane'), 100)
        self.assertEqual(data.get('optical_lane_pattern'), 'DR4')
        self.assertFalse(data.get('gearbox_present'))
        self.assertEqual(data.get('cable_assembly_type'), 'none')
        self.assertEqual(data.get('breakout_topology'), '1x')

    # ------------------------------------------------------------------
    # T4: OSFP-400G-DR4 has one InterfaceTemplate of type 400gbase-x-osfp
    # ------------------------------------------------------------------

    def test_osfp_400g_dr4_interface_template(self):
        """OSFP-400G-DR4 has exactly one InterfaceTemplate: port0 (400gbase-x-osfp)."""
        generic = self._get_generic()
        mt = ModuleType.objects.filter(
            manufacturer=generic, model='OSFP-400G-DR4'
        ).first()
        self.assertIsNotNone(mt)
        templates = list(mt.interfacetemplates.all())
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0].name, 'port0')
        self.assertEqual(templates[0].type, '400gbase-x-osfp')

    # ------------------------------------------------------------------
    # T5: OSFP-200G-DR4 exists with correct profile
    # ------------------------------------------------------------------

    def test_osfp_200g_dr4_exists_with_transceiver_profile(self):
        """OSFP-200G-DR4 ModuleType exists and carries the Network Transceiver profile."""
        generic = self._get_generic()
        self.assertIsNotNone(generic, "Generic manufacturer must exist")
        mt = ModuleType.objects.filter(
            manufacturer=generic, model='OSFP-200G-DR4'
        ).first()
        self.assertIsNotNone(mt, "OSFP-200G-DR4 ModuleType must be seeded")
        self.assertIsNotNone(mt.profile, "OSFP-200G-DR4 must have a profile")
        self.assertEqual(mt.profile.name, 'Network Transceiver')

    # ------------------------------------------------------------------
    # T6: OSFP-200G-DR4 attribute_data correctness
    # ------------------------------------------------------------------

    def test_osfp_200g_dr4_attribute_data(self):
        """OSFP-200G-DR4 attribute_data has correct cage_type, medium, standard, reach_class."""
        generic = self._get_generic()
        mt = ModuleType.objects.filter(
            manufacturer=generic, model='OSFP-200G-DR4'
        ).first()
        self.assertIsNotNone(mt)
        data = mt.attribute_data or {}
        self.assertEqual(data.get('cage_type'), 'OSFP')
        self.assertEqual(data.get('medium'), 'SMF')
        self.assertEqual(data.get('standard'), '200GBASE-DR4')
        self.assertEqual(data.get('reach_class'), 'DR')
        self.assertEqual(data.get('connector'), 'MPO-12')
        self.assertEqual(data.get('wavelength_nm'), 1310)
        self.assertEqual(data.get('lane_count'), 4)
        self.assertEqual(data.get('host_serdes_gbps_per_lane'), 50)
        self.assertEqual(data.get('optical_lane_pattern'), 'DR4')
        self.assertFalse(data.get('gearbox_present'))
        self.assertEqual(data.get('cable_assembly_type'), 'none')
        self.assertEqual(data.get('breakout_topology'), '1x')

    # ------------------------------------------------------------------
    # T7: OSFP-200G-DR4 has one InterfaceTemplate
    # ------------------------------------------------------------------

    def test_osfp_200g_dr4_interface_template(self):
        """OSFP-200G-DR4 has exactly one InterfaceTemplate: port0."""
        generic = self._get_generic()
        mt = ModuleType.objects.filter(
            manufacturer=generic, model='OSFP-200G-DR4'
        ).first()
        self.assertIsNotNone(mt)
        templates = list(mt.interfacetemplates.all())
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0].name, 'port0')

    # ------------------------------------------------------------------
    # T8: Both types are distinct (no model-name collision)
    # ------------------------------------------------------------------

    def test_osfp_types_are_distinct(self):
        """OSFP-400G-DR4 and OSFP-200G-DR4 are two separate ModuleType records."""
        generic = self._get_generic()
        self.assertIsNotNone(generic)
        count = ModuleType.objects.filter(
            manufacturer=generic,
            model__in=['OSFP-400G-DR4', 'OSFP-200G-DR4'],
        ).count()
        self.assertEqual(count, 2)
