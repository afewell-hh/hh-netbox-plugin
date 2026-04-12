"""
Tests for migration 0048: OSFP transceiver ModuleType seeding (DIET-434).

Confirms that after migration runs, both OSFP records exist with the
correct Network Transceiver profile and expected attribute_data.

XOC-64 server-side intent (resolved in training-ra#20 Phase 0):
- OSFP-400G-DR4: server-side optic for CX-7 scale-out NIC ports
- OSFP-200G-DR4: server-side optic for the Generic OSFP SoC/Storage NIC
  ('Generic xPU SoC/Storage 2x200G NIC' in the DIET case file)
  NOT the BF3220/QSFP112 optic — the XOC-64 switch zone declares
  OSFP-800G-4x200G-DR4 (SMF), which is physically incompatible with
  QSFP112/MMF (different cage type and medium).

These tests depend on the seeded data being present (via --keepdb or
a freshly applied migration run) rather than creating test fixtures.
"""

from django.test import TestCase

from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile


class OSFPTransceiverSeedTestCase(TestCase):
    """
    Verify both OSFP transceiver ModuleTypes are seeded correctly.

    These records serve the XOC-64 server-side transceiver paths:
    - OSFP-400G-DR4: CX-7 scale-out NIC ports
    - OSFP-200G-DR4: generic OSFP SoC/Storage NIC ports
      (NOT BF3220/QSFP112 — see module docstring for physical rationale)
    """

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
    # T4: OSFP-400G-DR4 has no InterfaceTemplates (transceivers are optics,
    #     not NICs — they do not add logical interfaces to the parent device)
    # ------------------------------------------------------------------

    def test_osfp_400g_dr4_no_interface_templates(self):
        """
        OSFP-400G-DR4 has zero InterfaceTemplates after migration 0049.

        Transceivers are physical optics installed in NIC cage bays. The
        parent device's interfaces come from the NIC module type, not from
        the transceiver. Adding interface templates to transceiver ModuleTypes
        causes duplicate-interface errors when multiple transceivers are
        installed on the same server (e.g., 8 rails × port0 = 8 collisions).
        """
        generic = self._get_generic()
        mt = ModuleType.objects.filter(
            manufacturer=generic, model='OSFP-400G-DR4'
        ).first()
        self.assertIsNotNone(mt)
        templates = list(mt.interfacetemplates.all())
        self.assertEqual(len(templates), 0,
                         "OSFP-400G-DR4 must have no InterfaceTemplates (migration 0049)")

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
    # T7: OSFP-200G-DR4 has no InterfaceTemplates (same rationale as T4)
    # ------------------------------------------------------------------

    def test_osfp_200g_dr4_no_interface_templates(self):
        """
        OSFP-200G-DR4 has zero InterfaceTemplates after migration 0049.

        See T4 for the full rationale. Transceivers do not add logical
        interfaces to the parent device; the NIC module provides those.
        """
        generic = self._get_generic()
        mt = ModuleType.objects.filter(
            manufacturer=generic, model='OSFP-200G-DR4'
        ).first()
        self.assertIsNotNone(mt)
        templates = list(mt.interfacetemplates.all())
        self.assertEqual(len(templates), 0,
                         "OSFP-200G-DR4 must have no InterfaceTemplates (migration 0049)")

    # ------------------------------------------------------------------
    # T8: OSFP-200G-DR4 is NOT QSFP112 (documents resolved intent)
    # ------------------------------------------------------------------

    def test_osfp_200g_dr4_is_not_qsfp112(self):
        """
        OSFP-200G-DR4 cage_type is OSFP, not QSFP112.

        Regression guard: confirms the XOC-64 soc-storage server-side optic is
        genuinely OSFP/SMF (compatible with the switch's OSFP-800G-4x200G-DR4
        zone), not QSFP112/MMF (which would fail the cross-end V4 cage_type check).
        """
        generic = self._get_generic()
        mt = ModuleType.objects.filter(
            manufacturer=generic, model='OSFP-200G-DR4'
        ).first()
        self.assertIsNotNone(mt)
        data = mt.attribute_data or {}
        self.assertNotEqual(data.get('cage_type'), 'QSFP112',
                            "OSFP-200G-DR4 must not use QSFP112 cage_type")
        self.assertNotEqual(data.get('medium'), 'MMF',
                            "OSFP-200G-DR4 must not use MMF medium")
        self.assertEqual(data.get('cage_type'), 'OSFP')
        self.assertEqual(data.get('medium'), 'SMF')

    # ------------------------------------------------------------------
    # T9: Both types are distinct (no model-name collision)
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
