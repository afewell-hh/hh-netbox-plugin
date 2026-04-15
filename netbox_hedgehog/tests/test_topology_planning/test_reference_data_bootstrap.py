"""
Regression tests for DIET-448: canonical switch inventory bootstrap.

Verifies that load_diet_reference_data (without --skip-switch-profile-import)
deterministically produces the correct Hedgehog switch inventory and that
populate_transceiver_bays can subsequently operate on that inventory.

Gate 1 — canonical bootstrap path is explicit and defendable.
Gate 2 — no dual-source DS5000 mapping drift remains.
Gate 3 — seeded-catalog tests are green.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from dcim.models import DeviceType, InterfaceTemplate, ModuleBayTemplate, ModuleType, ModuleTypeProfile


class CanonicalSwitchInventoryTestCase(TestCase):
    """
    Gate 1+2: load_diet_reference_data (no --skip flag) must produce the
    profile-backed celestica-ds5000 DeviceType with correct interface types.
    """

    def _seed(self):
        call_command("load_diet_reference_data", stdout=StringIO())

    def test_canonical_ds5000_slug_exists(self):
        """load_diet_reference_data creates celestica-ds5000 (canonical slug)."""
        self._seed()
        self.assertTrue(
            DeviceType.objects.filter(slug="celestica-ds5000").exists(),
            "Expected profile-backed DeviceType with slug 'celestica-ds5000'",
        )

    def test_canonical_ds5000_has_osfp_interface_templates(self):
        """celestica-ds5000 OSFP ports must be 800gbase-x-osfp, not qsfpdd."""
        self._seed()
        dt = DeviceType.objects.get(slug="celestica-ds5000")
        osfp_templates = InterfaceTemplate.objects.filter(
            device_type=dt, type="800gbase-x-osfp"
        )
        self.assertEqual(
            osfp_templates.count(),
            64,
            "celestica-ds5000 must have exactly 64 OSFP interface templates "
            "(E1/1–E1/64, type=800gbase-x-osfp)",
        )

    def test_canonical_ds5000_has_no_qsfpdd_templates(self):
        """
        Regression guard (Gate 2): no qsfpdd templates on celestica-ds5000.

        The legacy seed_diet_device_types command hardcoded 800gbase-x-qsfpdd.
        The canonical import_fabric_profiles path maps OSFP-800G → 800gbase-x-osfp.
        This test ensures the drift is gone.
        """
        self._seed()
        dt = DeviceType.objects.get(slug="celestica-ds5000")
        wrong = InterfaceTemplate.objects.filter(
            device_type=dt, type="800gbase-x-qsfpdd"
        )
        self.assertEqual(
            wrong.count(),
            0,
            f"celestica-ds5000 must not have 800gbase-x-qsfpdd templates; "
            f"found {wrong.count()} wrong-type template(s): "
            f"{list(wrong.values_list('name', 'type'))}",
        )

    def test_canonical_ds5000_osfp_port_names(self):
        """celestica-ds5000 OSFP templates are named E1/1 through E1/64."""
        self._seed()
        dt = DeviceType.objects.get(slug="celestica-ds5000")
        osfp_names = set(
            InterfaceTemplate.objects.filter(
                device_type=dt, type="800gbase-x-osfp"
            ).values_list("name", flat=True)
        )
        for n in range(1, 65):
            self.assertIn(
                f"E1/{n}",
                osfp_names,
                f"Expected OSFP template E1/{n} on celestica-ds5000",
            )

    def test_canonical_ds5000_is_idempotent(self):
        """Running load_diet_reference_data twice does not duplicate templates."""
        self._seed()
        self._seed()
        dt = DeviceType.objects.get(slug="celestica-ds5000")
        osfp_count = InterfaceTemplate.objects.filter(
            device_type=dt, type="800gbase-x-osfp"
        ).count()
        self.assertEqual(
            osfp_count,
            64,
            f"Double-seed must not duplicate templates; expected 64, got {osfp_count}",
        )

    def test_legacy_ds5000_slug_is_not_created_by_reference_data(self):
        """
        The legacy 'ds5000' slug (from seed_diet_device_types) must NOT be
        created by load_diet_reference_data.  This ensures only one canonical
        DS5000 model exists after a clean bootstrap.
        Purge all DeviceTypes first so the test is independent of pre-existing
        test-DB state (e.g. from previous seed_diet_device_types runs).
        """
        DeviceType.objects.all().delete()
        self._seed()
        self.assertFalse(
            DeviceType.objects.filter(slug="ds5000").exists(),
            "load_diet_reference_data must not create the legacy 'ds5000' slug",
        )


class SwitchBayPopulationTestCase(TestCase):
    """
    Gate 3: populate_transceiver_bays works against the seeded DS5000 path.
    """

    def test_populate_bays_after_seed(self):
        """
        After load_diet_reference_data + populate_transceiver_bays,
        celestica-ds5000 must have 66 ModuleBayTemplates — one per
        InterfaceTemplate (64 OSFP E1/1–E1/64 + 2 SFP28 E1/65–E1/66).
        """
        call_command("load_diet_reference_data", stdout=StringIO())
        call_command("populate_transceiver_bays", verbosity=0)

        dt = DeviceType.objects.get(slug="celestica-ds5000")
        bays = ModuleBayTemplate.objects.filter(device_type=dt)
        self.assertEqual(
            bays.count(),
            66,
            f"celestica-ds5000 must have 66 ModuleBayTemplates after populate "
            f"(64 OSFP + 2 SFP28); got {bays.count()}",
        )
        bay_names = set(bays.values_list("name", flat=True))
        # Verify all 64 OSFP bays are present (these are the ones used for
        # transceiver placement in generation)
        for n in range(1, 65):
            self.assertIn(
                f"E1/{n}",
                bay_names,
                f"Expected ModuleBayTemplate E1/{n} on celestica-ds5000",
            )
        # SFP28 management uplink bays also present
        self.assertIn("E1/65", bay_names)
        self.assertIn("E1/66", bay_names)

    def test_populate_bays_is_idempotent(self):
        """populate_transceiver_bays twice does not create duplicate bays."""
        call_command("load_diet_reference_data", stdout=StringIO())
        call_command("populate_transceiver_bays", verbosity=0)
        call_command("populate_transceiver_bays", verbosity=0)

        dt = DeviceType.objects.get(slug="celestica-ds5000")
        self.assertEqual(
            ModuleBayTemplate.objects.filter(device_type=dt).count(),
            66,
            "Double populate_transceiver_bays must not duplicate ModuleBayTemplates",
        )


class PurgeAndReseedRoundTripTestCase(TestCase):
    """
    Gate 4: purge → reseed recreates the canonical switch inventory.

    Simulates reset_local_dev.sh --purge-inventory followed by
    load_diet_reference_data.
    """

    def test_purge_and_reseed_recreates_canonical_ds5000(self):
        """Purge all inventory, reseed, and verify celestica-ds5000 is correct."""
        # Initial seed
        call_command("load_diet_reference_data", stdout=StringIO())

        # Simulate --purge-inventory: delete ModuleType first (FK protected),
        # then ModuleTypeProfile, then DeviceType / Manufacturer
        ModuleType.objects.all().delete()
        ModuleTypeProfile.objects.all().delete()
        DeviceType.objects.all().delete()

        self.assertFalse(
            DeviceType.objects.filter(slug="celestica-ds5000").exists(),
            "Purge should remove celestica-ds5000",
        )

        # Reseed
        call_command("load_diet_reference_data", stdout=StringIO())

        dt = DeviceType.objects.filter(slug="celestica-ds5000").first()
        self.assertIsNotNone(dt, "celestica-ds5000 must be recreated after purge + reseed")

        osfp_count = InterfaceTemplate.objects.filter(
            device_type=dt, type="800gbase-x-osfp"
        ).count()
        self.assertEqual(
            osfp_count,
            64,
            f"Reseeded celestica-ds5000 must have 64 OSFP templates; got {osfp_count}",
        )

    def test_purge_and_reseed_then_populate_bays(self):
        """Full round trip: purge → reseed → populate_transceiver_bays."""
        call_command("load_diet_reference_data", stdout=StringIO())

        ModuleType.objects.all().delete()
        ModuleTypeProfile.objects.all().delete()
        DeviceType.objects.all().delete()

        call_command("load_diet_reference_data", stdout=StringIO())
        call_command("populate_transceiver_bays", verbosity=0)

        dt = DeviceType.objects.get(slug="celestica-ds5000")
        self.assertEqual(
            ModuleBayTemplate.objects.filter(device_type=dt).count(),
            66,
            "Full purge→reseed→populate round trip must produce 66 bays "
            "(64 OSFP + 2 SFP28) on celestica-ds5000",
        )
