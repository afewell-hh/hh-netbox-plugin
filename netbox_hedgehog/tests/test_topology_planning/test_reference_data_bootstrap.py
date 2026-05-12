"""
Regression tests for DIET-448 and DIET-556: canonical switch inventory bootstrap.

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

from dcim.models import DeviceType, InterfaceTemplate, Manufacturer, ModuleBayTemplate, ModuleType, ModuleTypeProfile

from netbox_hedgehog.models.topology_planning import DeviceTypeExtension


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
        created by load_diet_reference_data.

        Django TestCase already provides a clean DB per test — the previous
        pre-purge (DeviceType.objects.all().delete()) was masking the real
        coexistence scenario.  See LegacyMigrationCoexistenceTestCase for
        tests that exercise the real path where stale rows exist beforehand.
        """
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


class LegacyMigrationCoexistenceTestCase(TestCase):
    """
    DIET-556: Regression contract for the coexistence bug from migration 0009.

    Migration 0009 created 4 invalid DeviceTypes (ds5000, ds3000, sn5600,
    es1000-48) that must not exist after a correct bootstrap. These tests
    simulate the real pre-0053 path where those stale rows are present
    before load_diet_reference_data is called.

    No pre-purge is performed. Each test creates the 4 stale rows directly,
    then asserts the post-bootstrap contract.

    Expected RED failures and their implementation seams:
    - test_stale_slugs_absent_after_load_without_prepurge
      → migration 0053 not yet written; stale rows survive load
    - test_retire_legacy_removes_all_six_forbidden_slugs
      → RETIRED_SLUGS in retire_legacy_device_types() missing the 4 new slugs
    - test_coexistence_is_idempotent
      → same root as first; double load still does not purge stale rows
    """

    # sn5600 is intentionally absent: neutral slug, not forbidden — must not
    # be purged so future NVIDIA support can add it without a migration.
    FORBIDDEN_SLUGS = ['ds5000', 'ds3000', 'es1000-48']
    REQUIRED_SLUGS = ['celestica-ds5000', 'celestica-es1000']

    def _create_stale_0009_rows(self):
        """
        Reproduce the 4 DeviceTypes + DeviceTypeExtensions that migration 0009
        creates, without any prior delete. Matches as-migrated state for
        environments that ran 0009 before migration 0053 is applied.
        """
        celestica, _ = Manufacturer.objects.get_or_create(
            name='Celestica', defaults={'slug': 'celestica'}
        )
        edgecore, _ = Manufacturer.objects.get_or_create(
            name='Edge-Core', defaults={'slug': 'edge-core'}
        )

        stale_specs = [
            (celestica, 'DS5000',    'ds5000',    False, ['spine', 'server-leaf']),
            (celestica, 'DS3000',    'ds3000',    False, ['server-leaf', 'border-leaf']),
            (edgecore,  'ES1000-48', 'es1000-48', False, ['virtual']),
        ]
        for mfr, model, slug, mclag, roles in stale_specs:
            dt, _ = DeviceType.objects.get_or_create(
                manufacturer=mfr,
                model=model,
                defaults={'slug': slug, 'u_height': 1, 'is_full_depth': False},
            )
            DeviceTypeExtension.objects.get_or_create(
                device_type=dt,
                defaults={'mclag_capable': mclag, 'hedgehog_roles': roles},
            )

    def test_stale_slugs_absent_after_load_without_prepurge(self):
        """
        After creating the 4 stale rows then running load_diet_reference_data
        (no --retire-legacy), all 4 forbidden slugs must be absent.

        RED: fails because load_diet_reference_data does not remove stale rows.
        GREEN: migration 0053 purges them during migrate before this command runs.
        """
        self._create_stale_0009_rows()
        call_command("load_diet_reference_data", stdout=StringIO())
        for slug in self.FORBIDDEN_SLUGS:
            self.assertFalse(
                DeviceType.objects.filter(slug=slug).exists(),
                f"Forbidden legacy slug '{slug}' must be absent after load_diet_reference_data "
                f"(seam: migration 0053 missing)",
            )

    def test_required_slugs_present_after_load_without_prepurge(self):
        """
        After creating stale rows then running load_diet_reference_data,
        the required canonical slugs must be present.

        Expected GREEN in RED state — canonical seeds are slug-keyed and
        independent of the stale rows. Guards against regressions where
        coexistence breaks seed logic.
        """
        self._create_stale_0009_rows()
        call_command("load_diet_reference_data", stdout=StringIO())
        for slug in self.REQUIRED_SLUGS:
            self.assertTrue(
                DeviceType.objects.filter(slug=slug).exists(),
                f"Required canonical slug '{slug}' must exist after load_diet_reference_data",
            )

    def test_canonical_ds5000_correct_after_coexistence(self):
        """
        celestica-ds5000 must have exactly 64 OSFP templates and 0 qsfpdd
        templates even when the stale ds5000 DeviceType was present before load.

        Proves template-type drift does not propagate from the legacy row.
        Expected GREEN in RED state — profile import is slug-keyed.
        """
        self._create_stale_0009_rows()
        call_command("load_diet_reference_data", stdout=StringIO())
        dt = DeviceType.objects.get(slug="celestica-ds5000")
        osfp_count = InterfaceTemplate.objects.filter(
            device_type=dt, type="800gbase-x-osfp"
        ).count()
        qsfpdd_count = InterfaceTemplate.objects.filter(
            device_type=dt, type="800gbase-x-qsfpdd"
        ).count()
        self.assertEqual(
            osfp_count,
            64,
            f"celestica-ds5000 must have 64 OSFP templates after coexistence load; got {osfp_count}",
        )
        self.assertEqual(
            qsfpdd_count,
            0,
            f"celestica-ds5000 must have 0 qsfpdd templates; got {qsfpdd_count}",
        )

    def test_retire_legacy_removes_all_five_forbidden_slugs(self):
        """
        load_diet_reference_data --retire-legacy must remove all 5 forbidden slugs:
        the 3 migration-0009 stale rows (ds5000, ds3000, es1000-48) plus
        celestica-ds5000-leaf/-spine.

        sn5600 is intentionally absent from RETIRED_SLUGS — it is a neutral slug
        that must not be actively purged so future NVIDIA support can add it.

        Note: celestica-ds5000-leaf/-spine are absent by default in a clean test DB;
        the command must not error when they are missing.
        """
        self._create_stale_0009_rows()
        all_five_slugs = self.FORBIDDEN_SLUGS + ['celestica-ds5000-leaf', 'celestica-ds5000-spine']
        call_command("load_diet_reference_data", "--retire-legacy", stdout=StringIO())
        for slug in all_five_slugs:
            self.assertFalse(
                DeviceType.objects.filter(slug=slug).exists(),
                f"Forbidden slug '{slug}' must be absent after --retire-legacy "
                f"(seam: RETIRED_SLUGS missing this slug)",
            )

    def test_coexistence_is_idempotent(self):
        """
        Running load_diet_reference_data twice with stale rows on the first run
        must produce the same final state: forbidden slugs absent, required slugs present.

        RED: fails on the forbidden-absent assertion (same root as
        test_stale_slugs_absent_after_load_without_prepurge — two loads still
        do not purge what migration 0053 should have removed).
        GREEN: idempotency is inherent once migration 0053 removes rows on migrate.
        """
        self._create_stale_0009_rows()
        call_command("load_diet_reference_data", stdout=StringIO())
        call_command("load_diet_reference_data", stdout=StringIO())
        for slug in self.FORBIDDEN_SLUGS:
            self.assertFalse(
                DeviceType.objects.filter(slug=slug).exists(),
                f"Forbidden slug '{slug}' must be absent after double load_diet_reference_data "
                f"(seam: migration 0053 missing)",
            )
        for slug in self.REQUIRED_SLUGS:
            self.assertTrue(
                DeviceType.objects.filter(slug=slug).exists(),
                f"Required canonical slug '{slug}' must exist after double load_diet_reference_data",
            )
