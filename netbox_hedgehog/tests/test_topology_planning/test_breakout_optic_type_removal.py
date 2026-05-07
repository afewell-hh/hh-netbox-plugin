"""
RED tests for DIET-500: BreakoutOption.optic_type field removal.

These tests define the post-removal contract and FAIL on the current codebase
(where `optic_type` still exists). They will PASS after the GREEN implementation
in DIET-501 (migration + code cleanup).

Test categories:
  Category A - Behavioral assertion tests (model, UI, serializer, seed)
  Compat     - Ingest compatibility: legacy YAML with optic_type silently accepted
  Math       - Breakout math regression guards (logical_ports/speed/from_speed unchanged)
"""

from django.test import TestCase
from django.core.management import call_command
from io import StringIO

from netbox_hedgehog.models.topology_planning import BreakoutOption
from netbox_hedgehog.api.serializers_simple import BreakoutOptionSerializer


class BreakoutOptionFieldRemovalTest(TestCase):
    """Category A: model-level and serializer-level RED assertions."""

    def test_breakout_option_model_has_no_optic_type_field(self):
        """BreakoutOption must not have an optic_type attribute after removal."""
        bo = BreakoutOption(
            breakout_id='red-test-4x200g',
            from_speed=800,
            logical_ports=4,
            logical_speed=200,
        )
        # RED: fails while model still has the optic_type CharField
        self.assertFalse(
            hasattr(bo, 'optic_type'),
            "BreakoutOption.optic_type field must be removed (DIET-501 migration pending)"
        )

    def test_breakout_option_serializer_excludes_optic_type(self):
        """BreakoutOptionSerializer must not expose optic_type in its output."""
        bo = BreakoutOption.objects.create(
            breakout_id='red-serial-4x200g',
            from_speed=800,
            logical_ports=4,
            logical_speed=200,
        )
        data = BreakoutOptionSerializer(bo).data
        # RED: fails while serializer.Meta.fields still lists 'optic_type'
        self.assertNotIn(
            'optic_type',
            data,
            "BreakoutOptionSerializer must not expose optic_type (remove from Meta.fields)"
        )

    def test_seed_command_produces_breakouts_without_optic_type(self):
        """load_diet_reference_data must not write optic_type on any seeded BreakoutOption."""
        call_command('load_diet_reference_data', stdout=StringIO())
        bo = BreakoutOption.objects.get(breakout_id='4x200g')
        # RED: fails while model still carries the field
        self.assertFalse(
            hasattr(bo, 'optic_type'),
            "Seeded BreakoutOption must not have optic_type after removal"
        )

    def test_seed_command_all_breakouts_lack_optic_type(self):
        """Every seeded BreakoutOption must be free of optic_type."""
        call_command('load_diet_reference_data', stdout=StringIO())
        for bo in BreakoutOption.objects.all():
            # RED: fails while model still carries the field
            self.assertFalse(
                hasattr(bo, 'optic_type'),
                f"BreakoutOption '{bo.breakout_id}' must not have optic_type"
            )


class BreakoutOptionIngestCompatTest(TestCase):
    """
    Compatibility guard: YAML ingest must silently accept legacy optic_type keys.

    After GREEN, `optic_type` in YAML is read into the item dict and then
    never stored (the defaults dict no longer includes it). No error is raised.
    The resulting BreakoutOption must exist with correct authoritative fields.
    """

    def test_ingest_with_legacy_optic_type_creates_breakout(self):
        """
        Calling _ensure_reference_data with optic_type in YAML must not error
        and must produce a BreakoutOption with correct breakout_id and math fields.
        """
        from netbox_hedgehog.test_cases.ingest import _ensure_reference_data

        case = {
            'reference_data': {
                'breakout_options': [
                    {
                        'id': 'bo-compat',
                        'breakout_id': 'compat-4x200g',
                        'from_speed': 800,
                        'logical_ports': 4,
                        'logical_speed': 200,
                        'optic_type': 'QSFP-DD',  # legacy key — must be silently ignored
                    }
                ]
            }
        }

        # Must not raise any exception
        refs = _ensure_reference_data(case, reference_mode='ensure')

        # Breakout must exist
        bo = BreakoutOption.objects.filter(breakout_id='compat-4x200g').first()
        self.assertIsNotNone(bo, "BreakoutOption must be created by ingest even with legacy optic_type key")

        # Authoritative math fields must be set correctly
        self.assertEqual(bo.from_speed, 800)
        self.assertEqual(bo.logical_ports, 4)
        self.assertEqual(bo.logical_speed, 200)

        # RED: optic_type must NOT be stored on the model after removal
        self.assertFalse(
            hasattr(bo, 'optic_type'),
            "optic_type from YAML must be silently discarded — field must not exist on model"
        )

    def test_ingest_with_multiple_legacy_optic_type_entries_succeeds(self):
        """
        Multiple BreakoutOptions in YAML with legacy optic_type keys all ingest cleanly.
        """
        from netbox_hedgehog.test_cases.ingest import _ensure_reference_data

        case = {
            'reference_data': {
                'breakout_options': [
                    {
                        'id': 'bo1',
                        'breakout_id': 'compat-1x800g',
                        'from_speed': 800,
                        'logical_ports': 1,
                        'logical_speed': 800,
                        'optic_type': 'QSFP-DD',
                    },
                    {
                        'id': 'bo2',
                        'breakout_id': 'compat-1x1g',
                        'from_speed': 1,
                        'logical_ports': 1,
                        'logical_speed': 1,
                        'optic_type': 'RJ45',
                    },
                ]
            }
        }

        refs = _ensure_reference_data(case, reference_mode='ensure')

        self.assertEqual(BreakoutOption.objects.filter(breakout_id__startswith='compat-').count(), 2)

        for bo in BreakoutOption.objects.filter(breakout_id__startswith='compat-'):
            self.assertFalse(
                hasattr(bo, 'optic_type'),
                f"optic_type must not be stored on '{bo.breakout_id}'"
            )


class BreakoutMathRegressionTest(TestCase):
    """
    Regression guards: breakout allocation math fields must be unaffected by
    optic_type removal. logical_ports, logical_speed, from_speed, and breakout_id
    must continue to drive behavior as before.
    """

    def setUp(self):
        BreakoutOption.objects.all().delete()
        call_command('load_diet_reference_data', stdout=StringIO())

    def test_seeded_breakout_math_fields_are_correct(self):
        """Seeded BreakoutOptions must have correct authoritative math fields."""
        expected = [
            ('1x800g', 800, 1, 800),
            ('2x400g', 800, 2, 400),
            ('4x200g', 800, 4, 200),
            ('8x100g', 800, 8, 100),
            ('1x400g', 400, 1, 400),
            ('2x200g', 400, 2, 200),
            ('4x100g', 400, 4, 100),
            ('1x100g', 100, 1, 100),
            ('1x40g',  100, 1,  40),
            ('2x50g',  100, 2,  50),
            ('4x25g',  100, 4,  25),
            ('4x10g',  100, 4,  10),
            ('1x10g',   10, 1,  10),
            ('1x1g',     1, 1,   1),
        ]
        for breakout_id, from_speed, logical_ports, logical_speed in expected:
            with self.subTest(breakout_id=breakout_id):
                bo = BreakoutOption.objects.filter(breakout_id=breakout_id).first()
                self.assertIsNotNone(bo, f"BreakoutOption '{breakout_id}' must be seeded")
                self.assertEqual(bo.from_speed, from_speed,
                    f"'{breakout_id}' from_speed mismatch")
                self.assertEqual(bo.logical_ports, logical_ports,
                    f"'{breakout_id}' logical_ports mismatch")
                self.assertEqual(bo.logical_speed, logical_speed,
                    f"'{breakout_id}' logical_speed mismatch")

    def test_breakout_id_is_primary_lookup_key(self):
        """breakout_id must uniquely identify a BreakoutOption (unique constraint still holds)."""
        bo = BreakoutOption.objects.get(breakout_id='4x200g')
        self.assertEqual(bo.breakout_id, '4x200g')
        # Unique: a second object with same breakout_id must not be creatable
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            BreakoutOption.objects.create(
                breakout_id='4x200g',
                from_speed=800,
                logical_ports=4,
                logical_speed=200,
            )

    def test_seeded_breakout_count(self):
        """At least 14 BreakoutOptions must exist after load_diet_reference_data."""
        # Import may create additional BreakoutOptions from bundled profiles.
        self.assertGreaterEqual(BreakoutOption.objects.count(), 14)
