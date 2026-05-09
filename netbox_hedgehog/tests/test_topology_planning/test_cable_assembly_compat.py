"""
RED tests for DIET-512 Phase 3: attached cable assembly semantics.

Encodes the approved spec (#515) before implementation.  All groups should
fail in RED state; each seam is isolated so GREEN can be verified group by group.

Groups
------
A  — schema shape: far_end_medium / far_end_cage_type fields in profile schema
B  — seed coverage: R4113-75C41-03 carries far_end_medium=MMF, far_end_cage_type=SFP28
C  — pure rule-engine: Rule 2.5 branch, new reason codes, fallthrough guards
D  — narrow integration: connection review outcome self-heals once Rule 2.5 lands

Implementation seams expected to close in GREEN (#517)
-------------------------------------------------------
1. seed_catalog.py  — add far_end_medium / far_end_cage_type to schema + seed R4113-75C41-03
2. transceiver_rules.py — add R_CABLE_ASSEMBLY_MATCH, R_CABLE_ASSEMBLY_FAR_END_CAGE_MISMATCH,
                          _ATTACHED_ASSEMBLY_TYPES, _is_attached_assembly(), Rule 2.5 branch
3. Inherited: connection_review._determine_outcome() calls evaluate_xcvr_pair() unchanged;
   no code changes needed there — it self-heals once the rule engine is updated.
"""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from netbox_hedgehog.seed_catalog import NETWORK_TRANSCEIVER_PROFILE_SCHEMA
from netbox_hedgehog.services.transceiver_rules import (
    OUTCOME_BLOCKED,
    OUTCOME_MATCH,
    OUTCOME_NEEDS_REVIEW,
    R_MEDIUM_MISMATCH,
    evaluate_xcvr_pair,
)

# New constants — will cause AttributeError on access until GREEN.
# Imported defensively so Groups A/B/D can still collect and fail independently.
try:
    from netbox_hedgehog.services.transceiver_rules import (
        R_CABLE_ASSEMBLY_MATCH,
        R_CABLE_ASSEMBLY_FAR_END_CAGE_MISMATCH,
    )
    _NEW_CONSTANTS_IMPORTABLE = True
except ImportError:
    R_CABLE_ASSEMBLY_MATCH = None            # type: ignore[assignment]
    R_CABLE_ASSEMBLY_FAR_END_CAGE_MISMATCH = None  # type: ignore[assignment]
    _NEW_CONSTANTS_IMPORTABLE = False


# ---------------------------------------------------------------------------
# Shared attribute dicts
# ---------------------------------------------------------------------------

# Zone side: DAC breakout assembly with (future) far-end metadata
_DAC_ZONE_WITH_FAR_END = {
    'cage_type': 'QSFP28',
    'medium': 'DAC',
    'connector': 'Direct',
    'standard': '100GBASE-CR4',
    'cable_assembly_type': 'DAC',
    'breakout_topology': '4x25g',
    'far_end_medium': 'MMF',
    'far_end_cage_type': 'SFP28',
}

# Zone side: AOC variant (same far-end fields, different assembly type)
_AOC_ZONE_WITH_FAR_END = {
    'cage_type': 'QSFP28',
    'medium': 'AOC',
    'connector': 'Direct',
    'cable_assembly_type': 'AOC',
    'far_end_medium': 'MMF',
    'far_end_cage_type': 'SFP28',
}

# Zone side: ACC variant
_ACC_ZONE_WITH_FAR_END = {
    'cage_type': 'QSFP28',
    'medium': 'ACC',
    'connector': 'Direct',
    'cable_assembly_type': 'ACC',
    'far_end_medium': 'MMF',
    'far_end_cage_type': 'SFP28',
}

# Zone side: DAC breakout WITHOUT far-end metadata (incomplete seed; fallthrough case)
_DAC_ZONE_NO_FAR_END = {
    'cage_type': 'QSFP28',
    'medium': 'DAC',
    'connector': 'Direct',
    'standard': '100GBASE-CR4',
    'cable_assembly_type': 'DAC',
    'breakout_topology': '4x25g',
    # deliberately no far_end_medium / far_end_cage_type
}

# Server side: SFP28 MMF optic (the 25G far-end that mates with the DAC tails)
_SFP28_MMF_SERVER = {
    'cage_type': 'SFP28',
    'medium': 'MMF',
    'connector': 'LC',
    'standard': '25GBASE-SR',
}

# Server side: QSFP28 MMF optic (cage mismatch vs SFP28 far-end)
_QSFP28_MMF_SERVER = {
    'cage_type': 'QSFP28',
    'medium': 'MMF',
    'connector': 'MPO-12',
    'standard': '100GBASE-SR4',
}

# Server side: SFP28 SMF optic (medium mismatch vs far_end_medium=MMF)
_SFP28_SMF_SERVER = {
    'cage_type': 'SFP28',
    'medium': 'SMF',
    'connector': 'LC',
    'standard': '25GBASE-LR',
}

# Ordinary (non-cable-assembly) optic that must not trigger Rule 2.5
_ORDINARY_QSFP28 = {
    'cage_type': 'QSFP28',
    'medium': 'MMF',
    'connector': 'MPO-12',
    'standard': '100GBASE-SR4',
    'cable_assembly_type': 'none',
}


# ===========================================================================
# Group A — Schema / metadata shape
# ===========================================================================

class TestGroupASchemaShape(SimpleTestCase):
    """
    A.1-A.5: far_end_medium and far_end_cage_type must appear in the profile schema.

    RED seam: seed_catalog.NETWORK_TRANSCEIVER_PROFILE_SCHEMA does not yet
    contain these fields.
    """

    def _props(self):
        return NETWORK_TRANSCEIVER_PROFILE_SCHEMA.get('properties', {})

    def test_a1_far_end_medium_field_exists_in_schema(self):
        """far_end_medium must be a recognized property in the schema."""
        self.assertIn(
            'far_end_medium',
            self._props(),
            "NETWORK_TRANSCEIVER_PROFILE_SCHEMA missing 'far_end_medium' property",
        )

    def test_a2_far_end_cage_type_field_exists_in_schema(self):
        """far_end_cage_type must be a recognized property in the schema."""
        self.assertIn(
            'far_end_cage_type',
            self._props(),
            "NETWORK_TRANSCEIVER_PROFILE_SCHEMA missing 'far_end_cage_type' property",
        )

    def test_a3_far_end_medium_enum_includes_mmf(self):
        """far_end_medium enum must include 'MMF' (the R4113-75C41-03 value)."""
        enum = self._props().get('far_end_medium', {}).get('enum', [])
        self.assertIn('MMF', enum)

    def test_a4_far_end_cage_type_enum_includes_sfp28(self):
        """far_end_cage_type enum must include 'SFP28' (the DAC tail cage type)."""
        enum = self._props().get('far_end_cage_type', {}).get('enum', [])
        self.assertIn('SFP28', enum)

    def test_a5_far_end_fields_are_not_required(self):
        """Both far_end_* fields must be optional (absent from 'required' list)."""
        required = NETWORK_TRANSCEIVER_PROFILE_SCHEMA.get('required', [])
        self.assertNotIn('far_end_medium', required)
        self.assertNotIn('far_end_cage_type', required)


# ===========================================================================
# Group B — Seed coverage
# ===========================================================================

class TestGroupBSeedCoverage(TestCase):
    """
    B.1-B.4: R4113-75C41-03 must carry far_end_medium and far_end_cage_type
    after load_diet_reference_data runs.

    RED seam: seed_catalog.STATIC_TRANSCEIVER_MODULE_TYPES entry for
    R4113-75C41-03 lacks far_end_medium and far_end_cage_type.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('load_diet_reference_data', stdout=StringIO())

    def _get_dac(self):
        from dcim.models import ModuleType
        mt = ModuleType.objects.filter(model='R4113-75C41-03').first()
        self.assertIsNotNone(mt, "R4113-75C41-03 ModuleType must be seeded")
        return mt

    def test_b1_r4113_75c41_03_has_far_end_medium(self):
        """Seeded R4113-75C41-03 must have far_end_medium='MMF'."""
        mt = self._get_dac()
        self.assertEqual(
            mt.attribute_data.get('far_end_medium'),
            'MMF',
            f"Expected far_end_medium='MMF', got {mt.attribute_data.get('far_end_medium')!r}",
        )

    def test_b2_r4113_75c41_03_has_far_end_cage_type(self):
        """Seeded R4113-75C41-03 must have far_end_cage_type='SFP28'."""
        mt = self._get_dac()
        self.assertEqual(
            mt.attribute_data.get('far_end_cage_type'),
            'SFP28',
            f"Expected far_end_cage_type='SFP28', got {mt.attribute_data.get('far_end_cage_type')!r}",
        )

    def test_b3_r4113_75c41_03_cable_assembly_type_unchanged(self):
        """cable_assembly_type must still be 'DAC' (no regression)."""
        mt = self._get_dac()
        self.assertEqual(mt.attribute_data.get('cable_assembly_type'), 'DAC')

    def test_b4_ordinary_optic_has_no_far_end_fields(self):
        """An ordinary optic (R4113-A9220-VR) must not gain far_end_* fields."""
        from dcim.models import ModuleType
        mt = ModuleType.objects.filter(model='R4113-A9220-VR').first()
        self.assertIsNotNone(mt)
        self.assertIsNone(
            mt.attribute_data.get('far_end_medium'),
            "Ordinary optic must not have far_end_medium",
        )
        self.assertIsNone(
            mt.attribute_data.get('far_end_cage_type'),
            "Ordinary optic must not have far_end_cage_type",
        )


# ===========================================================================
# Group C — Pure rule-engine behavior
# ===========================================================================

class TestGroupCRuleEngineConstants(SimpleTestCase):
    """
    C.1-C.3: New reason-code constants must exist and follow naming conventions.

    RED seam: transceiver_rules.py does not yet export these constants.
    """

    def test_c1_r_cable_assembly_match_constant_exists(self):
        """R_CABLE_ASSEMBLY_MATCH must be importable from transceiver_rules."""
        self.assertTrue(
            _NEW_CONSTANTS_IMPORTABLE,
            "R_CABLE_ASSEMBLY_MATCH and R_CABLE_ASSEMBLY_FAR_END_CAGE_MISMATCH "
            "could not be imported from netbox_hedgehog.services.transceiver_rules",
        )
        self.assertIsNotNone(R_CABLE_ASSEMBLY_MATCH)

    def test_c2_r_cable_assembly_far_end_cage_mismatch_constant_exists(self):
        """R_CABLE_ASSEMBLY_FAR_END_CAGE_MISMATCH must be importable."""
        self.assertTrue(
            _NEW_CONSTANTS_IMPORTABLE,
            "R_CABLE_ASSEMBLY_FAR_END_CAGE_MISMATCH could not be imported",
        )
        self.assertIsNotNone(R_CABLE_ASSEMBLY_FAR_END_CAGE_MISMATCH)

    def test_c3_new_constants_are_strings_with_r_prefix(self):
        """New reason codes must be plain strings prefixed with R_."""
        self.assertTrue(_NEW_CONSTANTS_IMPORTABLE, "Constants not importable")
        for val in (R_CABLE_ASSEMBLY_MATCH, R_CABLE_ASSEMBLY_FAR_END_CAGE_MISMATCH):
            self.assertIsInstance(val, str)
            self.assertTrue(val.startswith('R_'), f"{val!r} does not start with 'R_'")


class TestGroupCRuleEngineBranch(SimpleTestCase):
    """
    C.4-C.11: Rule 2.5 branch behavior.

    RED seam: evaluate_xcvr_pair() lacks the _is_attached_assembly() check and
    Rule 2.5 branch, so all assembly-specific assertions will fail.
    """

    def test_c4_dac_with_far_end_matching_server_is_cable_assembly_match(self):
        """
        Motivating case: SFP28-MMF server vs QSFP28-DAC zone with
        far_end_medium=MMF and far_end_cage_type=SFP28 must yield MATCH /
        R_CABLE_ASSEMBLY_MATCH, not BLOCKED.
        """
        result = evaluate_xcvr_pair(_SFP28_MMF_SERVER, _DAC_ZONE_WITH_FAR_END)
        self.assertEqual(result.outcome, OUTCOME_MATCH, f"Got: {result}")
        self.assertEqual(result.reason_code, R_CABLE_ASSEMBLY_MATCH, f"Got: {result}")

    def test_c5_dac_far_end_cage_mismatch_is_needs_review(self):
        """
        Server cage=QSFP28 vs far_end_cage_type=SFP28 → NEEDS_REVIEW /
        R_CABLE_ASSEMBLY_FAR_END_CAGE_MISMATCH (cage differs, but medium matches).
        """
        result = evaluate_xcvr_pair(_QSFP28_MMF_SERVER, _DAC_ZONE_WITH_FAR_END)
        self.assertEqual(result.outcome, OUTCOME_NEEDS_REVIEW, f"Got: {result}")
        self.assertEqual(
            result.reason_code, R_CABLE_ASSEMBLY_FAR_END_CAGE_MISMATCH, f"Got: {result}"
        )

    def test_c6_dac_far_end_medium_mismatch_is_blocked(self):
        """
        Server medium=SMF vs far_end_medium=MMF → BLOCKED / R_MEDIUM_MISMATCH
        (Rule 2.5 still enforces medium compatibility via R_MEDIUM_MISMATCH).
        """
        result = evaluate_xcvr_pair(_SFP28_SMF_SERVER, _DAC_ZONE_WITH_FAR_END)
        self.assertEqual(result.outcome, OUTCOME_BLOCKED, f"Got: {result}")
        self.assertEqual(result.reason_code, R_MEDIUM_MISMATCH, f"Got: {result}")

    def test_c7_dac_without_far_end_fields_falls_through_to_rule3(self):
        """
        DAC zone without far_end_medium / far_end_cage_type must NOT activate
        Rule 2.5.  Rule 3 fires: DAC vs MMF medium → BLOCKED / R_MEDIUM_MISMATCH.
        This guards the conservative fallback: incomplete metadata preserves
        the existing blocked signal.
        """
        result = evaluate_xcvr_pair(_SFP28_MMF_SERVER, _DAC_ZONE_NO_FAR_END)
        self.assertEqual(result.outcome, OUTCOME_BLOCKED, f"Got: {result}")
        self.assertEqual(result.reason_code, R_MEDIUM_MISMATCH, f"Got: {result}")

    def test_c8_aoc_with_far_end_fields_activates_branch(self):
        """AOC cable_assembly_type with far-end metadata triggers Rule 2.5."""
        result = evaluate_xcvr_pair(_SFP28_MMF_SERVER, _AOC_ZONE_WITH_FAR_END)
        self.assertEqual(result.outcome, OUTCOME_MATCH, f"Got: {result}")
        self.assertEqual(result.reason_code, R_CABLE_ASSEMBLY_MATCH, f"Got: {result}")

    def test_c9_acc_with_far_end_fields_activates_branch(self):
        """ACC cable_assembly_type with far-end metadata triggers Rule 2.5."""
        result = evaluate_xcvr_pair(_SFP28_MMF_SERVER, _ACC_ZONE_WITH_FAR_END)
        self.assertEqual(result.outcome, OUTCOME_MATCH, f"Got: {result}")
        self.assertEqual(result.reason_code, R_CABLE_ASSEMBLY_MATCH, f"Got: {result}")

    def test_c10_ordinary_none_assembly_type_does_not_activate_branch(self):
        """
        cable_assembly_type='none' must never trigger Rule 2.5 even if
        far_end_* keys happen to be present (should not occur in practice).
        """
        zone_ordinary_with_spurious_far_end = dict(
            _ORDINARY_QSFP28,
            far_end_medium='MMF',
            far_end_cage_type='SFP28',
        )
        result = evaluate_xcvr_pair(_SFP28_MMF_SERVER, zone_ordinary_with_spurious_far_end)
        # Rule 5 (cage mismatch QSFP28 vs QSFP28 → same cage, falls through to R_MATCH)
        # or Rule 6/7 depending on connector; the key invariant is it must NOT be
        # R_CABLE_ASSEMBLY_MATCH since cable_assembly_type is 'none'.
        self.assertNotEqual(
            result.reason_code, R_CABLE_ASSEMBLY_MATCH,
            "Rule 2.5 must not fire for cable_assembly_type='none'",
        )

    def test_c11_rule2_intent_asymmetry_checked_before_rule25(self):
        """
        Rule 2 (intent asymmetry) must still fire before Rule 2.5.
        If server_attrs is None, outcome is NEEDS_REVIEW / R_INTENT_ASYMMETRY
        even when zone is a cable assembly.
        """
        from netbox_hedgehog.services.transceiver_rules import R_INTENT_ASYMMETRY
        result = evaluate_xcvr_pair(None, _DAC_ZONE_WITH_FAR_END)
        self.assertEqual(result.outcome, OUTCOME_NEEDS_REVIEW, f"Got: {result}")
        self.assertEqual(result.reason_code, R_INTENT_ASYMMETRY, f"Got: {result}")


# ===========================================================================
# Group D — Narrow integration: connection review inherits corrected behavior
# ===========================================================================

def _make_transceiver_module_type(model, attribute_data):
    """Get-or-create a Network Transceiver ModuleType with given attribute_data."""
    from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile

    mfr, _ = Manufacturer.objects.get_or_create(
        name='CA-Test-Vendor', defaults={'slug': 'ca-test-vendor'}
    )
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr,
        model=model,
        defaults={'profile': profile, 'attribute_data': attribute_data},
    )
    return mt


def _make_review_fixtures():
    """
    Build minimal plan → switch_class → server_class → zone → connection
    for the motivating DAC-assembly review case.

    Returns (plan, zone, server_class, dac_zone_mt, sfp28_server_mt).
    """
    from dcim.models import DeviceType, Manufacturer

    from netbox_hedgehog.choices import (
        AllocationStrategyChoices,
        ConnectionDistributionChoices,
        ConnectionTypeChoices,
        FabricTypeChoices,
        HedgehogRoleChoices,
        PortZoneTypeChoices,
        ServerClassCategoryChoices,
        TopologyPlanStatusChoices,
    )
    from netbox_hedgehog.models.topology_planning import (
        BreakoutOption,
        DeviceTypeExtension,
        PlanServerClass,
        PlanServerConnection,
        PlanSwitchClass,
        SwitchPortZone,
        TopologyPlan,
    )
    from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic

    # Transceiver ModuleTypes
    dac_zone_mt = _make_transceiver_module_type(
        'CA-DAC-100G-4x25G-TEST',
        {
            'cage_type': 'QSFP28',
            'medium': 'DAC',
            'connector': 'Direct',
            'standard': '100GBASE-CR4',
            'cable_assembly_type': 'DAC',
            'breakout_topology': '4x25g',
            'far_end_medium': 'MMF',
            'far_end_cage_type': 'SFP28',
        },
    )
    sfp28_server_mt = _make_transceiver_module_type(
        'CA-SFP28-25G-SR-TEST',
        {
            'cage_type': 'SFP28',
            'medium': 'MMF',
            'connector': 'LC',
            'standard': '25GBASE-SR',
            'cable_assembly_type': 'none',
        },
    )

    # Switch fixtures
    mfr, _ = Manufacturer.objects.get_or_create(
        name='CA-Switch-Vendor', defaults={'slug': 'ca-switch-vendor'}
    )
    switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='CA-Switch', defaults={'slug': 'ca-switch'}
    )
    ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=switch_dt,
        defaults={
            'native_speed': 100,
            'supported_breakouts': ['4x25g'],
            'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    bo_4x25g, _ = BreakoutOption.objects.get_or_create(
        breakout_id='4x25g-ca',
        defaults={'from_speed': 100, 'logical_ports': 4, 'logical_speed': 25},
    )

    # Server DeviceType
    srv_mfr, _ = Manufacturer.objects.get_or_create(
        name='CA-Server-Vendor', defaults={'slug': 'ca-server-vendor'}
    )
    srv_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=srv_mfr, model='CA-Server', defaults={'slug': 'ca-server'}
    )

    plan = TopologyPlan.objects.create(
        name='CA-DAC-Plan',
        customer_name='DIET-516 Test',
        status=TopologyPlanStatusChoices.DRAFT,
    )
    switch_class = PlanSwitchClass.objects.create(
        plan=plan,
        switch_class_id='ca-fe-leaf',
        fabric=FabricTypeChoices.FRONTEND,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=ext,
        uplink_ports_per_switch=4,
        mclag_pair=False,
    )
    server_class = PlanServerClass.objects.create(
        plan=plan,
        server_class_id='ca-gpu',
        category=ServerClassCategoryChoices.GPU,
        quantity=2,
        gpus_per_server=8,
        server_device_type=srv_dt,
    )
    zone = SwitchPortZone.objects.create(
        switch_class=switch_class,
        zone_name='ca-fe-zone',
        zone_type=PortZoneTypeChoices.SERVER,
        port_spec='1-48',
        breakout_option=bo_4x25g,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
        priority=100,
        transceiver_module_type=dac_zone_mt,
    )
    nic = get_test_server_nic(server_class, nic_id='nic-ca')
    PlanServerConnection.objects.create(
        server_class=server_class,
        connection_id='CA-FE-001',
        nic=nic,
        port_index=0,
        target_zone=zone,
        ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        speed=25,
        port_type='data',
        transceiver_module_type=sfp28_server_mt,
    )
    return plan, zone, server_class, dac_zone_mt, sfp28_server_mt


class TestGroupDIntegration(TestCase):
    """
    D.1-D.4: Connection review shows correct outcomes once Rule 2.5 lands.

    RED seam: Rule 2.5 absent → DAC zone medium 'DAC' vs server medium 'MMF'
    triggers Rule 3 (R_MEDIUM_MISMATCH) → outcome='blocked'.
    Tests assert 'match', so they fail RED.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('load_diet_reference_data', stdout=StringIO())
        (
            cls.plan,
            cls.zone,
            cls.server_class,
            cls.dac_zone_mt,
            cls.sfp28_server_mt,
        ) = _make_review_fixtures()

    def _build(self):
        from netbox_hedgehog.services.connection_review import build_connection_review_summary
        return build_connection_review_summary(self.plan)

    def test_d1_dac_assembly_with_matching_far_end_is_match(self):
        """
        Motivating case: DAC zone (far_end_medium=MMF, far_end_cage_type=SFP28)
        paired with SFP28-MMF server must yield outcome='match'.

        RED: currently BLOCKED (R_MEDIUM_MISMATCH) because Rule 2.5 is absent.
        """
        summary = self._build()
        self.assertEqual(len(summary.groups), 1)
        group = summary.groups[0]
        self.assertEqual(
            group.outcome, 'match',
            f"Expected 'match' but got '{group.outcome}': {group.reason}",
        )
        self.assertEqual(summary.blocked_count, 0)

    def test_d2_dac_assembly_match_not_blocked(self):
        """Connection review must report zero blocked groups for the motivating case."""
        summary = self._build()
        self.assertEqual(
            summary.blocked_count, 0,
            f"Expected 0 blocked groups, got {summary.blocked_count}",
        )

    def test_d3_ordinary_medium_mismatch_still_blocks(self):
        """
        Regression guard: an ordinary MMF vs SMF pair (no cable_assembly_type)
        must still yield BLOCKED / R_MEDIUM_MISMATCH through the rule engine.
        """
        from netbox_hedgehog.services.transceiver_rules import R_MEDIUM_MISMATCH as _R_MM
        smf_attrs = {
            'cage_type': 'QSFP28',
            'medium': 'SMF',
            'connector': 'MPO-12',
            'standard': '100GBASE-DR',
            'cable_assembly_type': 'none',
        }
        mmf_attrs = {
            'cage_type': 'QSFP28',
            'medium': 'MMF',
            'connector': 'MPO-12',
            'standard': '100GBASE-SR4',
            'cable_assembly_type': 'none',
        }
        result = evaluate_xcvr_pair(mmf_attrs, smf_attrs)
        self.assertEqual(result.outcome, OUTCOME_BLOCKED)
        self.assertEqual(result.reason_code, _R_MM)

    def test_d4_dac_without_far_end_metadata_still_blocks(self):
        """
        Conservative fallback: a DAC zone without far_end_* metadata must still
        block (Rule 3 fires).  Tests that the fallback survives GREEN intact.
        """
        result = evaluate_xcvr_pair(_SFP28_MMF_SERVER, _DAC_ZONE_NO_FAR_END)
        self.assertEqual(result.outcome, OUTCOME_BLOCKED)
        self.assertEqual(result.reason_code, R_MEDIUM_MISMATCH)
