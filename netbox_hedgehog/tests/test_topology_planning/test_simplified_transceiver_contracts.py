"""
RED tests for #475 — simplified transceiver contracts.

Covers acceptance matrix items from #474 §9:
  M1–M7: model/save validation boundary
  G1–G7: generation behavior
  B1:    BOM with all-null transceiver plan

Model tests (M1, M2, M6, M7) are RED because model clean() currently
enforces mandatory transceiver and cross-end compatibility at save time.

Generation tests (G3, G6, G7) are RED because _run_compatibility_sweep()
currently fails on OUTCOME_NEEDS_REVIEW (cage/connector mismatch).
G1 via view is RED because preflight Phase 0 blocks null-transceiver plans.
G2 via view is RED for the same reason.
G4, G5 are regression guards (already correctly fail at sweep/bay level).

B1 is a regression guard — zero BOM rows for null-transceiver plan.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from dcim.models import (
    DeviceType,
    InterfaceTemplate,
    Manufacturer,
    ModuleBayTemplate,
    ModuleType,
    ModuleTypeProfile,
)

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricClassChoices,
    FabricTypeChoices,
    GenerationStatusChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    GenerationState,
    PlanServerClass,
    PlanServerConnection,
    PlanServerNIC,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import (
    get_test_nic_module_type,
    get_test_non_transceiver_module_type,
    get_test_transceiver_module_type,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_sc_fixtures(cls):
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name='MxtSC-Vendor', defaults={'slug': 'mxtsc-vendor'}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MxtSC-SRV', defaults={'slug': 'mxtsc-srv'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MxtSC-SW', defaults={'slug': 'mxtsc-sw'}
    )
    for n in range(1, 9):
        InterfaceTemplate.objects.get_or_create(
            device_type=cls.switch_dt, name=f'E1/{n}',
            defaults={'type': '200gbase-x-qsfp112'},
        )
    cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=cls.switch_dt,
        defaults={
            'native_speed': 200, 'uplink_ports': 0,
            'supported_breakouts': ['1x200g'], 'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    cls.breakout, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x200g-mxtsc',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    cls.xcvr_mt = get_test_transceiver_module_type()
    cls.nic_mt = get_test_nic_module_type()
    cls.non_xcvr_mt = get_test_non_transceiver_module_type()


def _make_plan_with_zone(cls, suffix, server_xcvr=None, zone_xcvr=None):
    """Build minimal plan + zone + connection using Model.objects.create() to bypass clean()."""
    plan = TopologyPlan.objects.create(
        name=f'MxtSC-Plan-{suffix}',
        status=TopologyPlanStatusChoices.DRAFT,
    )
    sc = PlanServerClass.objects.create(
        plan=plan, server_class_id='gpu',
        server_device_type=cls.server_dt, quantity=1,
    )
    sw = PlanSwitchClass.objects.create(
        plan=plan, switch_class_id='fe-leaf',
        fabric_name=FabricTypeChoices.FRONTEND,
        fabric_class=FabricClassChoices.MANAGED,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=cls.device_ext,
        uplink_ports_per_switch=0, mclag_pair=False,
        override_quantity=2, redundancy_type='eslag',
    )
    zone = SwitchPortZone.objects.create(
        switch_class=sw, zone_name='server-downlinks',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-8',
        breakout_option=cls.breakout,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        transceiver_module_type=zone_xcvr,
    )
    nic = PlanServerNIC.objects.create(
        server_class=sc, nic_id='nic-fe', module_type=cls.nic_mt,
    )
    PlanServerConnection.objects.create(
        server_class=sc, connection_id='fe',
        nic=nic, port_index=0, ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        target_zone=zone, speed=200, port_type='data',
        transceiver_module_type=server_xcvr,
    )
    return plan, sc, sw, zone


def _generate(plan):
    from netbox_hedgehog.services.device_generator import DeviceGenerator
    return DeviceGenerator(plan).generate_all()


# ---------------------------------------------------------------------------
# M1–M7: Model save-time validation
# ---------------------------------------------------------------------------

class ModelSaveValidationTestCase(TestCase):
    """
    M1–M7: PlanServerConnection.clean() and SwitchPortZone.clean() validation boundary.
    """

    @classmethod
    def setUpTestData(cls):
        _make_sc_fixtures(cls)
        cls.plan_m = TopologyPlan.objects.create(
            name='MxtSC-ModelPlan', status=TopologyPlanStatusChoices.DRAFT,
        )
        cls.sc_m = PlanServerClass.objects.create(
            plan=cls.plan_m, server_class_id='gpu',
            server_device_type=cls.server_dt, quantity=1,
        )
        cls.sw_m = PlanSwitchClass.objects.create(
            plan=cls.plan_m, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        cls.zone_m = SwitchPortZone.objects.create(
            switch_class=cls.sw_m, zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-8',
            breakout_option=cls.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=cls.xcvr_mt,
        )
        cls.nic_m = PlanServerNIC.objects.create(
            server_class=cls.sc_m, nic_id='nic-fe', module_type=cls.nic_mt,
        )

    def _psc_clean(self, **kwargs):
        """Build a PSC instance and call clean() on it."""
        defaults = dict(
            server_class=self.sc_m,
            connection_id='fe-clean-test',
            nic=self.nic_m,
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=self.zone_m,
            speed=200,
            port_type='data',
        )
        defaults.update(kwargs)
        conn = PlanServerConnection(**defaults)
        conn.clean()

    def test_m1_psc_null_transceiver_no_error(self):
        """M1: PlanServerConnection.clean() with null transceiver_module_type → no ValidationError."""
        try:
            self._psc_clean(transceiver_module_type=None)
        except ValidationError as exc:
            transceiver_errors = exc.message_dict.get('transceiver_module_type', [])
            self.fail(
                f'M1: null transceiver must not raise ValidationError; '
                f'got transceiver_module_type errors: {transceiver_errors}',
            )

    def test_m2_zone_null_transceiver_no_error(self):
        """M2: SwitchPortZone.clean() with null transceiver_module_type → no ValidationError."""
        zone = SwitchPortZone(
            switch_class=self.sw_m,
            zone_name='m2-zone',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='9-12',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=200,
            transceiver_module_type=None,
        )
        try:
            zone.clean()
        except ValidationError as exc:
            transceiver_errors = exc.message_dict.get('transceiver_module_type', [])
            self.fail(
                f'M2: null zone transceiver must not raise ValidationError; '
                f'got transceiver_module_type errors: {transceiver_errors}',
            )

    def test_m3_psc_non_transceiver_profile_raises(self):
        """M3 (regression): non-Network-Transceiver profile FK → ValidationError (V1 preserved)."""
        with self.assertRaises(ValidationError) as ctx:
            self._psc_clean(transceiver_module_type=self.non_xcvr_mt)
        errors = ctx.exception.message_dict
        self.assertIn(
            'transceiver_module_type', errors,
            'M3: V1 profile check must raise on transceiver_module_type field',
        )

    def test_m4_zone_non_transceiver_profile_raises(self):
        """M4 (regression): zone with non-Network-Transceiver profile FK → ValidationError (V1)."""
        zone = SwitchPortZone(
            switch_class=self.sw_m,
            zone_name='m4-zone',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='13-16',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=300,
            transceiver_module_type=self.non_xcvr_mt,
        )
        with self.assertRaises(ValidationError) as ctx:
            zone.clean()
        self.assertIn(
            'transceiver_module_type', ctx.exception.message_dict,
            'M4: V1 profile check must raise on zone transceiver_module_type',
        )

    def test_m5_dac_reach_class_mmf_medium_raises(self):
        """M5 (regression): DAC reach_class + MMF medium → ValidationError (V7 preserved)."""
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        dac_mmf_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=self.mfr, model='SC-DAC-MMF-InvalidTest',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112', 'medium': 'MMF', 'reach_class': 'DAC',
                },
            },
        )
        with self.assertRaises(ValidationError):
            self._psc_clean(transceiver_module_type=dac_mmf_mt)

    def test_m6_cage_mismatch_no_save_time_error(self):
        """M6: mismatched cage_type between server and zone FKs → no ValidationError at save time.

        Cross-end cage checks (V4) are removed from clean() and moved to
        review-only via the rule engine. Save must succeed.
        """
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        osfp_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=self.mfr, model='SC-OSFP-SRV-Test',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'OSFP', 'medium': 'MMF', 'reach_class': 'SR',
                },
            },
        )
        # xcvr_mt has cage_type=QSFP112; zone has xcvr_mt (QSFP112)
        # Server has OSFP → cage mismatch, but must not raise at save time
        try:
            self._psc_clean(transceiver_module_type=osfp_mt)
        except ValidationError as exc:
            cage_errors = exc.message_dict.get('transceiver_module_type', [])
            cage_errors += exc.message_dict.get('cage_type', [])
            self.fail(
                f'M6: cage mismatch must not raise ValidationError at save time '
                f'(V4 removed — review-only via rule engine); '
                f'got errors: {cage_errors}',
            )

    def test_m7_medium_mismatch_no_save_time_error(self):
        """M7: mismatched medium between server and zone FKs → no ValidationError at save time.

        V5/V8 cross-end medium checks are removed from clean(). Medium mismatch
        is still enforced at generation sweep (G4), but not at save time.
        """
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        dac_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=self.mfr, model='SC-DAC-SRV-Test',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112', 'medium': 'DAC', 'reach_class': 'DAC',
                },
            },
        )
        # xcvr_mt on zone has medium=MMF; server has DAC → medium mismatch.
        # Must not raise at save time; will fail at generation sweep (G4).
        try:
            self._psc_clean(transceiver_module_type=dac_mt)
        except ValidationError as exc:
            medium_errors = exc.message_dict.get('transceiver_module_type', [])
            medium_errors += exc.message_dict.get('medium', [])
            self.fail(
                f'M7: medium mismatch must not raise ValidationError at save time '
                f'(V5/V8 removed — enforced only at generation sweep via R_MEDIUM_MISMATCH); '
                f'got errors: {medium_errors}',
            )


# ---------------------------------------------------------------------------
# G1–G7: Generation behavior
# ---------------------------------------------------------------------------

class GenerationBehaviorTestCase(TestCase):
    """
    G1–G7: Generation outcomes for various transceiver states.
    Tests call DeviceGenerator.generate_all() directly (no view preflight).
    """

    @classmethod
    def setUpTestData(cls):
        _make_sc_fixtures(cls)
        # NIC and switch must have bays for module placement
        ModuleBayTemplate.objects.get_or_create(
            module_type=cls.nic_mt, name='cage-0',
        )
        for n in range(1, 9):
            ModuleBayTemplate.objects.get_or_create(
                device_type=cls.switch_dt, name=f'E1/{n}',
            )
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        cls.osfp_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='SC-G-OSFP',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'OSFP', 'medium': 'MMF', 'reach_class': 'SR',
                },
            },
        )
        cls.dac_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='SC-G-DAC',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112', 'medium': 'DAC', 'reach_class': 'DAC',
                },
            },
        )

    def test_g1_all_null_generates_successfully(self):
        """G1: all-null transceiver plan → status=GENERATED when generator is called directly.

        The direct generator call bypasses the view preflight (which is RED via
        PF1/view test). The sweep already skips null pairs (line 1104), so this
        test confirms zero mismatches and GENERATED status.
        Note: this test may be GREEN pre-implementation via direct generator call;
        the view-level RED test is in test_mandatory_transceiver_preflight.py.
        """
        plan, sc, sw, zone = _make_plan_with_zone(
            self, 'g1', server_xcvr=None, zone_xcvr=None
        )
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs, 'G1: GenerationState must be created')
        self.assertEqual(
            gs.status, GenerationStatusChoices.GENERATED,
            f'G1: all-null plan → GENERATED; got {gs.status}',
        )

    def test_g1_all_null_no_transceiver_modules_created(self):
        """G1b: all-null plan → xcvr_mt Modules not placed for any server device.

        The generator may place NIC modules (non-transceiver) and switch modules.
        Here we check specifically that the test transceiver ModuleType (xcvr_mt)
        appears in zero Modules, since it was the only candidate transceiver for
        this plan and the connection FK was null.

        Contract: null server FK → generator skips transceiver module placement.
        """
        from dcim.models import Module
        plan, sc, sw, zone = _make_plan_with_zone(
            self, 'g1b', server_xcvr=None, zone_xcvr=None
        )
        _generate(plan)
        # Count any module using xcvr_mt on devices belonging to this plan
        xcvr_count = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            module_type=self.xcvr_mt,
        ).count()
        self.assertEqual(
            xcvr_count, 0,
            f'G1b: null-transceiver plan must create zero xcvr_mt Modules on plan devices; '
            f'got {xcvr_count}',
        )

    def test_g3_cage_mismatch_generates_successfully(self):
        """G3: cage mismatch (non-approved) between server and zone FK → status=GENERATED.

        Currently RED: sweep adds cage mismatch to mismatches[] because
        OUTCOME_NEEDS_REVIEW != OUTCOME_MATCH → status=FAILED.
        After GREEN: sweep passes on OUTCOME_NEEDS_REVIEW → GENERATED.
        """
        # xcvr_mt has cage_type=QSFP112 (zone); osfp_mt has cage_type=OSFP (server)
        plan, sc, sw, zone = _make_plan_with_zone(
            self, 'g3', server_xcvr=self.osfp_mt, zone_xcvr=self.xcvr_mt
        )
        call_command('populate_transceiver_bays', verbosity=0)
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(
            gs.status, GenerationStatusChoices.GENERATED,
            f'G3: cage mismatch must produce GENERATED (not FAILED) after sweep fix; '
            f'got {gs.status}. mismatch_report: {gs.mismatch_report}',
        )

    def test_g4_medium_mismatch_fails_generation(self):
        """G4 (regression): medium mismatch → status=FAILED. R_MEDIUM_MISMATCH stays blocked."""
        # dac_mt: medium=DAC; xcvr_mt: medium=MMF → medium mismatch
        plan, sc, sw, zone = _make_plan_with_zone(
            self, 'g4', server_xcvr=self.dac_mt, zone_xcvr=self.xcvr_mt
        )
        call_command('populate_transceiver_bays', verbosity=0)
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(
            gs.status, GenerationStatusChoices.FAILED,
            f'G4: medium mismatch must still produce FAILED; got {gs.status}',
        )

    def test_g5_bay_missing_fails_generation(self):
        """G5 (regression): FK set but NIC bay absent → status=FAILED."""
        from dcim.models import InterfaceTemplate as IT
        mfr, _ = Manufacturer.objects.get_or_create(
            name='MxtSC-NoBay-Vendor', defaults={'slug': 'mxtsc-nobay-vendor'}
        )
        nobay_server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr, model='MxtSC-NoBay-SRV', defaults={'slug': 'mxtsc-nobay-srv'}
        )
        nobay_nic_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='MxtSC-NoBay-NIC',
        )
        # NIC needs interface templates so generator can wire connections, but
        # deliberately has NO ModuleBayTemplates — that absence is what G5 tests.
        IT.objects.get_or_create(
            module_type=nobay_nic_mt, name='p0',
            defaults={'type': '200gbase-x-qsfp112'},
        )
        plan = TopologyPlan.objects.create(
            name='MxtSC-NoBayPlan', status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu',
            server_device_type=nobay_server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        zone = SwitchPortZone.objects.create(
            switch_class=sw, zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-8',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=self.xcvr_mt,
        )
        nic = PlanServerNIC.objects.create(
            server_class=sc, nic_id='nic-nobay', module_type=nobay_nic_mt,
        )
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
            transceiver_module_type=self.xcvr_mt,
        )
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(
            gs.status, GenerationStatusChoices.FAILED,
            f'G5: bay-missing must still produce FAILED; got {gs.status}',
        )

    def test_g6_needs_review_connections_generate_successfully(self):
        """G6: plan with needs_review connections (cage mismatch) → GENERATED.

        Same scenario as G3: cage mismatch produces OUTCOME_NEEDS_REVIEW.
        After GREEN sweep fix, these connections are not added to mismatches.
        RED: currently the sweep adds needs_review connections to mismatches → FAILED.
        """
        plan, sc, sw, zone = _make_plan_with_zone(
            self, 'g6', server_xcvr=self.osfp_mt, zone_xcvr=self.xcvr_mt
        )
        call_command('populate_transceiver_bays', verbosity=0)
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(
            gs.status, GenerationStatusChoices.GENERATED,
            f'G6: needs_review connections must not block generation; '
            f'got {gs.status}. mismatch_report: {gs.mismatch_report}',
        )

    def test_g7_regenerate_cage_mismatch_plan_succeeds(self):
        """G7: regenerate a plan that previously had cage-mismatch FAILED status → GENERATED.

        Verifies that removing the sweep block is durable across re-generation.
        RED: currently a cage-mismatch plan stays FAILED on re-generation.
        """
        plan, sc, sw, zone = _make_plan_with_zone(
            self, 'g7', server_xcvr=self.osfp_mt, zone_xcvr=self.xcvr_mt
        )
        call_command('populate_transceiver_bays', verbosity=0)
        # First generation
        _generate(plan)
        # Second generation (regenerate)
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(
            gs.status, GenerationStatusChoices.GENERATED,
            f'G7: cage-mismatch plan must reach GENERATED on re-generation; '
            f'got {gs.status}',
        )


# ---------------------------------------------------------------------------
# B1: BOM with all-null transceiver plan → zero BOM rows
# ---------------------------------------------------------------------------

class BOMNullTransceiverTestCase(TestCase):
    """
    B1: get_plan_bom() on plan with all null transceivers (after generation)
    → PlanBOM with zero server_transceiver/switch_transceiver line items.
    No error raised. suppressed_switch_cable_assembly_count = 0.
    """

    @classmethod
    def setUpTestData(cls):
        _make_sc_fixtures(cls)

    def test_b1_all_null_bom_zero_transceiver_rows(self):
        """B1: all-null transceiver plan → zero BOM transceiver line items."""
        from netbox_hedgehog.services.bom_export import get_plan_bom
        plan, sc, sw, zone = _make_plan_with_zone(
            self, 'b1', server_xcvr=None, zone_xcvr=None
        )
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        if gs is None or gs.status != GenerationStatusChoices.GENERATED:
            self.skipTest(
                'B1 requires G1 to be GREEN (null-transceiver plan must generate). '
                'Skipping BOM test until G1 passes.'
            )
        bom = get_plan_bom(plan)
        xcvr_rows = [
            item for item in bom.line_items
            if item.section in ('server_transceiver', 'switch_transceiver')
        ]
        self.assertEqual(
            len(xcvr_rows), 0,
            f'B1: all-null plan must produce zero transceiver BOM rows; '
            f'got {len(xcvr_rows)} rows: {[r.module_type_model for r in xcvr_rows]}',
        )
        self.assertEqual(
            bom.suppressed_switch_cable_assembly_count, 0,
            f'B1: suppressed count must be 0 for all-null plan; '
            f'got {bom.suppressed_switch_cable_assembly_count}',
        )
