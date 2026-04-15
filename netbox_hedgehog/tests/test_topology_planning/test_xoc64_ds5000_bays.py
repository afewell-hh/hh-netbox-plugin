"""
Tests for DIET-cleanup: celestica-ds5000 canonical DeviceType bay population,
and regression guards that the legacy celestica-ds5000-leaf / -spine types
are NOT present in any case file or created by the canonical seed path.
"""

from io import StringIO
from pathlib import Path

import yaml

from django.core.management import call_command
from django.test import TestCase

from dcim.models import DeviceType, InterfaceTemplate, ModuleBayTemplate

# Locate the test_cases directory relative to this file so tests are
# independent of the current working directory.
_CASES_DIR = Path(__file__).resolve().parents[2] / "test_cases"


class CanonicalDS5000BayPopulationTestCase(TestCase):
    """
    Verify that the canonical celestica-ds5000 DeviceType has the expected
    interface templates and receives ModuleBayTemplates after
    populate_transceiver_bays.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('load_diet_reference_data', stdout=StringIO())

    def test_canonical_ds5000_exists_after_seed(self):
        """load_diet_reference_data must produce celestica-ds5000."""
        self.assertTrue(
            DeviceType.objects.filter(slug='celestica-ds5000').exists(),
            "celestica-ds5000 must exist after load_diet_reference_data",
        )

    def test_canonical_ds5000_has_66_interface_templates(self):
        """
        The canonical profile import creates 64 OSFP (E1/1–E1/64) +
        2 SFP28 (E1/65–E1/66) = 66 interface templates.
        """
        dt = DeviceType.objects.get(slug='celestica-ds5000')
        count = InterfaceTemplate.objects.filter(device_type=dt).count()
        self.assertEqual(
            count, 66,
            f"Expected 66 interface templates on celestica-ds5000, got {count}",
        )

    def test_canonical_ds5000_osfp_template_type(self):
        """OSFP ports (E1/1–E1/64) must use type 800gbase-x-osfp."""
        dt = DeviceType.objects.get(slug='celestica-ds5000')
        osfp = InterfaceTemplate.objects.filter(
            device_type=dt, type='800gbase-x-osfp'
        )
        self.assertEqual(
            osfp.count(), 64,
            "Expected 64 OSFP (800gbase-x-osfp) interface templates",
        )

    def test_populate_transceiver_bays_creates_66_bays(self):
        """
        populate_transceiver_bays must create one ModuleBayTemplate per
        InterfaceTemplate for HNP DeviceTypes — 66 for celestica-ds5000.
        """
        call_command('populate_transceiver_bays', stdout=StringIO())
        dt = DeviceType.objects.get(slug='celestica-ds5000')
        count = ModuleBayTemplate.objects.filter(device_type=dt).count()
        self.assertEqual(
            count, 66,
            f"Expected 66 ModuleBayTemplates on celestica-ds5000 after populate, got {count}",
        )

    def test_populate_transceiver_bays_is_idempotent(self):
        """Running populate_transceiver_bays twice must not add duplicate bays."""
        call_command('populate_transceiver_bays', stdout=StringIO())
        call_command('populate_transceiver_bays', stdout=StringIO())
        dt = DeviceType.objects.get(slug='celestica-ds5000')
        count = ModuleBayTemplate.objects.filter(device_type=dt).count()
        self.assertEqual(count, 66, "Second populate_transceiver_bays run must not add duplicates")


class LegacyDS5000AbsenceRegressionTestCase(TestCase):
    """
    Regression guards: canonical seed/reset paths must NOT create the
    deprecated celestica-ds5000-leaf and celestica-ds5000-spine DeviceTypes.
    Those types were previously created only by case-file ingest and have
    been retired in favour of the canonical celestica-ds5000.
    """

    def test_canonical_seed_does_not_create_leaf_slug(self):
        """load_diet_reference_data must not create celestica-ds5000-leaf."""
        call_command('load_diet_reference_data', stdout=StringIO())
        self.assertFalse(
            DeviceType.objects.filter(slug='celestica-ds5000-leaf').exists(),
            "celestica-ds5000-leaf must not be created by canonical seed",
        )

    def test_canonical_seed_does_not_create_spine_slug(self):
        """load_diet_reference_data must not create celestica-ds5000-spine."""
        call_command('load_diet_reference_data', stdout=StringIO())
        self.assertFalse(
            DeviceType.objects.filter(slug='celestica-ds5000-spine').exists(),
            "celestica-ds5000-spine must not be created by canonical seed",
        )

    def _device_type_slugs(self, case_filename: str) -> list[str]:
        """Return all device_type slugs declared in a case YAML file."""
        path = _CASES_DIR / case_filename
        with open(path) as fh:
            data = yaml.safe_load(fh)
        return [
            dt.get('slug', '')
            for dt in data.get('reference_data', {}).get('device_types', [])
        ]

    def test_opg64_case_yaml_uses_canonical_ds5000(self):
        """opg64_hyperconverged_ds5000.yaml must reference celestica-ds5000, not leaf/spine."""
        slugs = self._device_type_slugs('opg64_hyperconverged_ds5000.yaml')
        self.assertIn('celestica-ds5000', slugs,
                      "opg64 case must reference the canonical celestica-ds5000 slug")
        self.assertNotIn('celestica-ds5000-leaf', slugs,
                         "opg64 case must not reference the retired celestica-ds5000-leaf slug")
        self.assertNotIn('celestica-ds5000-spine', slugs,
                         "opg64 case must not reference the retired celestica-ds5000-spine slug")

    def test_xoc64_ro_case_yaml_uses_canonical_ds5000(self):
        """training_xoc64_1xopg64_mesh_conv_ro.yaml must reference celestica-ds5000."""
        slugs = self._device_type_slugs('training_xoc64_1xopg64_mesh_conv_ro.yaml')
        self.assertIn('celestica-ds5000', slugs,
                      "xoc64-ro case must reference canonical celestica-ds5000")
        self.assertNotIn('celestica-ds5000-leaf', slugs,
                         "xoc64-ro case must not reference retired celestica-ds5000-leaf")

    def test_xoc64_sh_case_yaml_uses_canonical_ds5000(self):
        """training_xoc64_1xopg64_mesh_conv_sh.yaml must reference celestica-ds5000."""
        slugs = self._device_type_slugs('training_xoc64_1xopg64_mesh_conv_sh.yaml')
        self.assertIn('celestica-ds5000', slugs,
                      "xoc64-sh case must reference canonical celestica-ds5000")
        self.assertNotIn('celestica-ds5000-leaf', slugs,
                         "xoc64-sh case must not reference retired celestica-ds5000-leaf")


class RetireLegacyDeviceTypesTestCase(TestCase):
    """
    Verify that load_diet_reference_data removes stale celestica-ds5000-leaf
    and -spine DeviceTypes from dirty environments during reset.
    """

    def _create_legacy_dt(self, slug: str):
        """Helper: directly insert a legacy DeviceType as if from old ingest."""
        from dcim.models import Manufacturer
        celestica, _ = Manufacturer.objects.get_or_create(
            name='Celestica', defaults={'slug': 'celestica'}
        )
        return DeviceType.objects.create(
            manufacturer=celestica,
            model=slug,
            slug=slug,
        )

    def test_load_diet_reference_data_removes_legacy_leaf_slug(self):
        """load_diet_reference_data must delete celestica-ds5000-leaf if present."""
        self._create_legacy_dt('celestica-ds5000-leaf')
        self.assertTrue(
            DeviceType.objects.filter(slug='celestica-ds5000-leaf').exists(),
            "Pre-condition: celestica-ds5000-leaf must exist before the command runs",
        )
        call_command('load_diet_reference_data', stdout=StringIO())
        self.assertFalse(
            DeviceType.objects.filter(slug='celestica-ds5000-leaf').exists(),
            "load_diet_reference_data must remove the retired celestica-ds5000-leaf",
        )

    def test_load_diet_reference_data_removes_legacy_spine_slug(self):
        """load_diet_reference_data must delete celestica-ds5000-spine if present."""
        self._create_legacy_dt('celestica-ds5000-spine')
        call_command('load_diet_reference_data', stdout=StringIO())
        self.assertFalse(
            DeviceType.objects.filter(slug='celestica-ds5000-spine').exists(),
            "load_diet_reference_data must remove the retired celestica-ds5000-spine",
        )

    def test_retire_is_noop_on_clean_db(self):
        """retire_legacy_device_types must be a no-op when legacy types are absent."""
        self.assertFalse(DeviceType.objects.filter(slug='celestica-ds5000-leaf').exists())
        self.assertFalse(DeviceType.objects.filter(slug='celestica-ds5000-spine').exists())
        # Must not raise; canonical DS5000 must still be present after seed
        call_command('load_diet_reference_data', stdout=StringIO())
        self.assertTrue(DeviceType.objects.filter(slug='celestica-ds5000').exists())
