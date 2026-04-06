"""
Phase 3 RED tests for DIET-347 Stage 3: hedgehog_transceiver_spec CustomField removal.

Groups:
  T1 - CustomField does not exist after migration 0046
  T2 - No hedgehog_transceiver_spec key on any interface after generation (transceiver FK set)
  T3 - No hedgehog_transceiver_spec key on any interface after generation (transceiver FK null)
  T4 - Regression guard: Module-based transceiver placement still works (must stay GREEN)

T1, T2, T3 are RED until Phase 4 GREEN implementation.
T4 is GREEN now (covered by Stage 2 Groups C/D) and must remain GREEN after Phase 4.
"""

from django.core.management import call_command
from django.test import TestCase

from dcim.models import Module

from netbox_hedgehog.models.topology_planning import TopologyPlan

from netbox_hedgehog.tests.test_topology_planning.test_stage2_transceiver import (
    _cleanup,
    _delete_plan,
    _generate,
    _make_plan_with_xcvr,
    _make_s2_fixtures,
)


# ---------------------------------------------------------------------------
# T1: CustomField must not exist after migration 0046
# ---------------------------------------------------------------------------

class TransceiverSpecFieldRemovedTestCase(TestCase):
    """T1: hedgehog_transceiver_spec CustomField must not exist."""

    def test_custom_field_does_not_exist(self):
        """T1: CustomField.objects must return zero rows for hedgehog_transceiver_spec."""
        from extras.models import CustomField
        count = CustomField.objects.filter(name='hedgehog_transceiver_spec').count()
        self.assertEqual(
            count, 0,
            "hedgehog_transceiver_spec CustomField must be removed by migration 0046; "
            f"found {count} row(s)",
        )


# ---------------------------------------------------------------------------
# T2 / T3: No hedgehog_transceiver_spec key on any generated interface
# T4: Module-based transceiver placement regression guard (must stay GREEN)
# ---------------------------------------------------------------------------

class TransceiverSpecAbsenceOnGenerationTestCase(TestCase):
    """
    T2: transceiver FK set → Module placed → no hedgehog_transceiver_spec key.
    T3: transceiver FK null → no Module placed → no hedgehog_transceiver_spec key.
    T4: transceiver FK set → Module objects still created (regression guard).
    """

    @classmethod
    def setUpTestData(cls):
        _make_s2_fixtures(cls)

    def tearDown(self):
        for p in list(TopologyPlan.objects.filter(name__startswith='S2Plan-')):
            _cleanup(p.pk)
            _delete_plan(p)

    def _assert_no_spec_key(self, plan):
        """Assert no generated interface carries hedgehog_transceiver_spec in custom_field_data."""
        from dcim.models import Interface
        count = Interface.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            custom_field_data__has_key='hedgehog_transceiver_spec',
        ).count()
        self.assertEqual(
            count, 0,
            f"hedgehog_transceiver_spec key must not appear on any generated interface; "
            f"found {count} interface(s) with the key set",
        )

    def test_no_spec_key_when_transceiver_module_placed(self):
        """T2: transceiver FK set on connection → Module placed → no hedgehog_transceiver_spec key."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(self, 'T2', with_xcvr=True)
        call_command('populate_transceiver_bays')
        _generate(plan)
        self._assert_no_spec_key(plan)

    def test_no_spec_key_when_transceiver_fk_is_null(self):
        """T3: transceiver FK null → no Module placed → no hedgehog_transceiver_spec key."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(self, 'T3', with_xcvr=False)
        call_command('populate_transceiver_bays')
        _generate(plan)
        self._assert_no_spec_key(plan)

    def test_transceiver_module_still_placed_when_fk_set(self):
        """T4 (regression guard): Module objects for transceivers are still created after Stage 3.

        This must stay GREEN in Phase 4 — confirms the Module-based model is intact
        and hedgehog_transceiver_spec removal does not affect transceiver Module placement.
        """
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(self, 'T4', with_xcvr=True)
        call_command('populate_transceiver_bays')
        _generate(plan)
        xcvr_modules = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            device__device_type=self.server_dt,
            module_type=self.xcvr_mt,
        )
        self.assertGreater(
            xcvr_modules.count(), 0,
            "Module objects for transceivers must still be created when transceiver FK is set; "
            "Stage 3 removal of hedgehog_transceiver_spec must not affect Module placement",
        )
