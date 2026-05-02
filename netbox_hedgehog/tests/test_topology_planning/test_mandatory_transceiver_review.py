"""
RED tests for #475 — simplified transceiver UX: review-pane behavior.

Replaces DIET-466 mandatory-transceiver review tests with tests that pin the
approved target behavior from #474 §9.3 (R1–R10).

Target behavior (not yet implemented):
  R1  — both server and zone FK null → outcome='match', reason_code=R_NULL
  R2  — server FK set, zone FK null → outcome='needs_review', R_INTENT_ASYMMETRY
  R3  — server FK null, zone FK set → outcome='needs_review', R_INTENT_ASYMMETRY
  R4  — medium mismatch → outcome='blocked', R_MEDIUM_MISMATCH  (preserved)
  R5  — cage mismatch (non-approved) → outcome='needs_review', R_CAGE_MISMATCH
  R6  — paired switch-fabric, one FK null → outcome='needs_review' (not 'blocked')
  R7  — unpaired switch-fabric zone, FK null → outcome='needs_review' (not 'blocked')
  R8  — unpaired switch-fabric zone, FK set → outcome=None (no peer to compare)
  R9  — plan detail GET, all null transceivers → HTTP 200, no error banner
  R10 — _xcvr_label(None) → '—' or 'Not specified', not '⚠ Missing (required)'

RED tests: R1, R2, R3, R6, R7, R10
Regression guards (already correct or should stay correct): R4, R5, R8

All RED tests fail until GREEN removes the DIET-466 null gate from
_determine_outcome() (connection_review.py:161-163), build_switch_fabric_review()
paired/unpaired null handling (switch_fabric_review.py:138-140, 172-174), and
changes _xcvr_label(None) from '⚠ Missing (required)' to '—'.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import DeviceType, Manufacturer, ModuleType, ModuleTypeProfile

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricClassChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanServerClass,
    PlanServerConnection,
    PlanServerNIC,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import (
    get_test_server_nic,
    get_test_transceiver_module_type,
)

User = get_user_model()

_APPROVED_NULL_LABEL_OPTIONS = ('—', 'Not specified')
_OLD_MISSING_LABEL = '⚠ Missing (required)'


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_rv_fixtures(cls):
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name='MxtRV2-Vendor', defaults={'slug': 'mxtrv2-vendor'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MxtRV2-Switch', defaults={'slug': 'mxtrv2-switch'}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MxtRV2-SRV', defaults={'slug': 'mxtrv2-srv'}
    )
    cls.ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=cls.switch_dt,
        defaults={
            'native_speed': 200, 'supported_breakouts': ['1x200g'],
            'mclag_capable': False, 'hedgehog_roles': ['server-leaf'],
        },
    )
    cls.bo, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x200g-mxtrv2',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    cls.xcvr_mt = get_test_transceiver_module_type()
    cls.superuser, _ = User.objects.get_or_create(
        username='mxtrv2-admin',
        defaults={'is_staff': True, 'is_superuser': True},
    )
    cls.superuser.set_password('pass')
    cls.superuser.save()


def _make_server_plan(cls, suffix, server_xcvr=None, zone_xcvr=None):
    plan = TopologyPlan.objects.create(
        name=f'MxtRV2-Plan-{suffix}',
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
        device_type_extension=cls.ext,
        uplink_ports_per_switch=0, mclag_pair=False,
        override_quantity=2, redundancy_type='eslag',
    )
    zone = SwitchPortZone.objects.create(
        switch_class=sw, zone_name='server-downlinks',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-4',
        breakout_option=cls.bo,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        transceiver_module_type=zone_xcvr,
    )
    nic = get_test_server_nic(sc, nic_id=f'nic-{suffix}')
    PlanServerConnection.objects.create(
        server_class=sc, connection_id='fe',
        nic=nic, port_index=0, ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        target_zone=zone, speed=200, port_type='data',
        transceiver_module_type=server_xcvr,
    )
    return plan, sc, sw, zone


# ---------------------------------------------------------------------------
# R10 — _xcvr_label(None) returns neutral label
# ---------------------------------------------------------------------------

class XcvrLabelNullTestCase(TestCase):
    """R10: _xcvr_label(None) must not return '⚠ Missing (required)'."""

    def test_r10_connection_review_xcvr_label_none(self):
        """R10a: connection_review._xcvr_label(None) → neutral label."""
        from netbox_hedgehog.services.connection_review import _xcvr_label
        label = _xcvr_label(None)
        self.assertNotEqual(
            label, _OLD_MISSING_LABEL,
            f'R10a: must not return the alarming required label; got: {label!r}',
        )
        self.assertIn(
            label, _APPROVED_NULL_LABEL_OPTIONS,
            f'R10a: must return one of {_APPROVED_NULL_LABEL_OPTIONS}; got: {label!r}',
        )

    def test_r10_switch_fabric_review_xcvr_label_none(self):
        """R10b: switch_fabric_review._xcvr_label(None) → neutral label."""
        from netbox_hedgehog.services.switch_fabric_review import _xcvr_label
        label = _xcvr_label(None)
        self.assertNotEqual(
            label, _OLD_MISSING_LABEL,
            f'R10b: must not return the alarming required label; got: {label!r}',
        )
        self.assertIn(
            label, _APPROVED_NULL_LABEL_OPTIONS,
            f'R10b: must return one of {_APPROVED_NULL_LABEL_OPTIONS}; got: {label!r}',
        )


# ---------------------------------------------------------------------------
# R1–R5 — Server-Link Review: outcome per transceiver combination
# ---------------------------------------------------------------------------

class ServerLinkReviewOutcomeTestCase(TestCase):
    """R1–R5: build_server_link_review() row outcomes."""

    @classmethod
    def setUpTestData(cls):
        _make_rv_fixtures(cls)
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        cls.dac_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='RV2-DAC-Test',
            defaults={
                'profile': profile,
                'attribute_data': {'cage_type': 'QSFP112', 'medium': 'DAC', 'reach_class': 'DAC'},
            },
        )
        cls.osfp_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='RV2-OSFP-Test',
            defaults={
                'profile': profile,
                'attribute_data': {'cage_type': 'OSFP', 'medium': 'MMF', 'reach_class': 'SR'},
            },
        )

    def test_r1_both_null_outcome_is_match(self):
        """R1: both server and zone FK null → outcome='match'."""
        from netbox_hedgehog.services.connection_review import build_server_link_review
        plan, sc, sw, zone = _make_server_plan(self, 'r1', server_xcvr=None, zone_xcvr=None)
        summary = build_server_link_review(plan)
        self.assertEqual(len(summary.rows), 1)
        self.assertEqual(
            summary.rows[0].outcome, 'match',
            f'R1: both-null → must be "match"; got {summary.rows[0].outcome!r}',
        )

    def test_r1_determine_outcome_both_null_returns_match(self):
        """R1b: _determine_outcome directly: both None attrs → match."""
        from netbox_hedgehog.services.connection_review import _determine_outcome
        outcome, reason = _determine_outcome('1x200g', 1, None, None)
        self.assertEqual(outcome, 'match',
            f'R1b: _determine_outcome both-null → "match"; got {outcome!r}')

    def test_r2_server_set_zone_null_needs_review(self):
        """R2: server FK set, zone FK null → outcome='needs_review'."""
        from netbox_hedgehog.services.connection_review import build_server_link_review
        plan, sc, sw, zone = _make_server_plan(
            self, 'r2', server_xcvr=self.xcvr_mt, zone_xcvr=None
        )
        summary = build_server_link_review(plan)
        self.assertEqual(len(summary.rows), 1)
        self.assertEqual(
            summary.rows[0].outcome, 'needs_review',
            f'R2: server set + zone null → "needs_review"; got {summary.rows[0].outcome!r}',
        )

    def test_r3_server_null_zone_set_needs_review(self):
        """R3: server FK null, zone FK set → outcome='needs_review'."""
        from netbox_hedgehog.services.connection_review import build_server_link_review
        plan, sc, sw, zone = _make_server_plan(
            self, 'r3', server_xcvr=None, zone_xcvr=self.xcvr_mt
        )
        summary = build_server_link_review(plan)
        self.assertEqual(len(summary.rows), 1)
        self.assertEqual(
            summary.rows[0].outcome, 'needs_review',
            f'R3: server null + zone set → "needs_review"; got {summary.rows[0].outcome!r}',
        )

    def test_r4_medium_mismatch_is_blocked(self):
        """R4 (regression): medium mismatch → 'blocked'. Must stay blocked."""
        from netbox_hedgehog.services.connection_review import build_server_link_review
        mmf_mt = self.xcvr_mt  # has medium='MMF'
        plan, sc, sw, zone = _make_server_plan(
            self, 'r4', server_xcvr=self.dac_mt, zone_xcvr=mmf_mt
        )
        summary = build_server_link_review(plan)
        self.assertEqual(len(summary.rows), 1)
        self.assertEqual(
            summary.rows[0].outcome, 'blocked',
            f'R4: medium mismatch must remain "blocked"; got {summary.rows[0].outcome!r}',
        )

    def test_r5_cage_mismatch_is_needs_review(self):
        """R5: cage mismatch → outcome='needs_review' (not blocked, not match)."""
        from netbox_hedgehog.services.connection_review import build_server_link_review
        # xcvr_mt has cage_type=QSFP112; osfp_mt has cage_type=OSFP → cage mismatch
        plan, sc, sw, zone = _make_server_plan(
            self, 'r5', server_xcvr=self.xcvr_mt, zone_xcvr=self.osfp_mt
        )
        summary = build_server_link_review(plan)
        self.assertEqual(len(summary.rows), 1)
        self.assertEqual(
            summary.rows[0].outcome, 'needs_review',
            f'R5: cage mismatch → "needs_review"; got {summary.rows[0].outcome!r}',
        )


# ---------------------------------------------------------------------------
# R6 / R7 / R8 — Switch-Fabric Review null outcomes
# ---------------------------------------------------------------------------

class SwitchFabricReviewNullTestCase(TestCase):
    """
    R6: paired zones, one null → needs_review (not blocked).
    R7: unpaired zone, null → needs_review (not blocked).
    R8: unpaired zone, FK set → outcome=None (regression guard).
    """

    @classmethod
    def setUpTestData(cls):
        _make_rv_fixtures(cls)

    def _paired_plan(self, suffix, near_xcvr, far_xcvr):
        plan = TopologyPlan.objects.create(
            name=f'MxtRV2-PairedPlan-{suffix}',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        near_sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        far_sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-spine',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SPINE,
            device_type_extension=self.ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        far_zone = SwitchPortZone.objects.create(
            switch_class=far_sw, zone_name='leaf-downlinks',
            zone_type=PortZoneTypeChoices.UPLINK, port_spec='1-4',
            breakout_option=self.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=far_xcvr,
        )
        SwitchPortZone.objects.create(
            switch_class=near_sw, zone_name='uplinks',
            zone_type=PortZoneTypeChoices.UPLINK, port_spec='1-4',
            breakout_option=self.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=near_xcvr,
            peer_zone=far_zone,
        )
        return plan

    def _unpaired_plan(self, suffix, zone_xcvr):
        plan = TopologyPlan.objects.create(
            name=f'MxtRV2-UnpairedPlan-{suffix}',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf-up',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=1, redundancy_type='eslag',
        )
        SwitchPortZone.objects.create(
            switch_class=sw, zone_name='uplinks',
            zone_type=PortZoneTypeChoices.UPLINK, port_spec='1-4',
            breakout_option=self.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=zone_xcvr,
        )
        return plan

    def test_r6_paired_one_null_needs_review(self):
        """R6: paired zones, near null → needs_review."""
        from netbox_hedgehog.services.switch_fabric_review import build_switch_fabric_review
        plan = self._paired_plan('r6', near_xcvr=None, far_xcvr=self.xcvr_mt)
        summary = build_switch_fabric_review(plan)
        paired = [r for r in summary.rows if r.is_paired]
        self.assertEqual(len(paired), 1)
        self.assertEqual(
            paired[0].outcome, 'needs_review',
            f'R6: paired near-null → "needs_review"; got {paired[0].outcome!r}',
        )

    def test_r6b_paired_both_null_needs_review(self):
        """R6b: paired zones, both null → needs_review."""
        from netbox_hedgehog.services.switch_fabric_review import build_switch_fabric_review
        plan = self._paired_plan('r6b', near_xcvr=None, far_xcvr=None)
        summary = build_switch_fabric_review(plan)
        paired = [r for r in summary.rows if r.is_paired]
        self.assertEqual(len(paired), 1)
        self.assertEqual(
            paired[0].outcome, 'needs_review',
            f'R6b: paired both-null → "needs_review"; got {paired[0].outcome!r}',
        )

    def test_r7_unpaired_null_needs_review(self):
        """R7: unpaired zone, null FK → needs_review."""
        from netbox_hedgehog.services.switch_fabric_review import build_switch_fabric_review
        plan = self._unpaired_plan('r7', zone_xcvr=None)
        summary = build_switch_fabric_review(plan)
        unpaired = [r for r in summary.rows if not r.is_paired]
        self.assertEqual(len(unpaired), 1)
        self.assertEqual(
            unpaired[0].outcome, 'needs_review',
            f'R7: unpaired null → "needs_review"; got {unpaired[0].outcome!r}',
        )

    def test_r8_unpaired_xcvr_set_outcome_none(self):
        """R8 (regression): unpaired zone, FK set → outcome=None."""
        from netbox_hedgehog.services.switch_fabric_review import build_switch_fabric_review
        plan = self._unpaired_plan('r8', zone_xcvr=self.xcvr_mt)
        summary = build_switch_fabric_review(plan)
        unpaired = [r for r in summary.rows if not r.is_paired]
        self.assertEqual(len(unpaired), 1)
        self.assertIsNone(
            unpaired[0].outcome,
            f'R8: unpaired set → outcome must be None; got {unpaired[0].outcome!r}',
        )


# ---------------------------------------------------------------------------
# R9 — plan detail page for null-transceiver plan
# ---------------------------------------------------------------------------

class PlanDetailNullTransceiverTestCase(TestCase):
    """
    R9: GET plan detail page for null-transceiver plan → 200, no error banner.
    """

    @classmethod
    def setUpTestData(cls):
        _make_rv_fixtures(cls)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def _null_plan(self, suffix):
        from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type
        plan = TopologyPlan.objects.create(
            name=f'MxtRV2-NullPlan-{suffix}',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu',
            server_device_type=self.server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        zone = SwitchPortZone.objects.create(
            switch_class=sw, zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-4',
            breakout_option=self.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=None,
        )
        nic_mt = get_test_nic_module_type()
        nic = PlanServerNIC.objects.create(
            server_class=sc, nic_id=f'nic-{suffix}', module_type=nic_mt,
        )
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
            transceiver_module_type=None,
        )
        return plan

    def test_r9_plan_detail_200_for_null_transceiver_plan(self):
        """R9: GET plan detail → 200 for null-transceiver plan."""
        plan = self._null_plan('r9a')
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', kwargs={'pk': plan.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_r9_no_prerequisite_missing_banner(self):
        """R9b: plan detail must not show 'Transceiver Bay Prerequisite Missing' banner."""
        plan = self._null_plan('r9b')
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', kwargs={'pk': plan.pk})
        response = self.client.get(url)
        self.assertNotIn(
            'Transceiver Bay Prerequisite Missing',
            response.content.decode(),
            'R9b: null-transceiver plan must not show required-transceiver banner '
            '(has_transceiver_fks=False after Phase 0 removal)',
        )


# ---------------------------------------------------------------------------
# Gap 3: edit affordances in rendered review panels
# ---------------------------------------------------------------------------

class ReviewEditAffordancesTestCase(TestCase):
    """
    Gap 3 fill: plan detail page must render edit URLs for connections and zones
    in the Server-Link Review and Switch-Fabric Review panels.

    GREEN could preserve outcome logic but drop navigation affordances (edit links).
    These tests guard that the rendered HTML contains the actual edit URLs so users
    can navigate to fix transceiver intent directly from the review card.

    These tests use a plan with null transceivers on both the connection and zone
    to match the simplified-transceiver post-GREEN steady state.
    """

    @classmethod
    def setUpTestData(cls):
        _make_rv_fixtures(cls)

        from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type

        plan = TopologyPlan.objects.create(
            name='MxtRV2-EditUrls',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu-eu',
            server_device_type=cls.server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf-eu',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        cls.zone = SwitchPortZone.objects.create(
            switch_class=sw, zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-4',
            breakout_option=cls.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=None,
        )
        nic_mt = get_test_nic_module_type()
        nic = PlanServerNIC.objects.create(
            server_class=sc, nic_id='nic-eu', module_type=nic_mt,
        )
        cls.conn = PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=cls.zone, speed=200, port_type='data',
            transceiver_module_type=None,
        )
        cls.plan = plan

        # Paired uplink zones for Switch-Fabric Review edit-URL assertions
        far_sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-spine-eu',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        cls.far_zone = SwitchPortZone.objects.create(
            switch_class=far_sw, zone_name='downlinks',
            zone_type=PortZoneTypeChoices.UPLINK, port_spec='1-4',
            breakout_option=cls.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=None,
        )
        cls.near_zone = SwitchPortZone.objects.create(
            switch_class=sw, zone_name='uplinks',
            zone_type=PortZoneTypeChoices.UPLINK, port_spec='5-8',
            breakout_option=cls.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=90,
            transceiver_module_type=None,
            peer_zone=cls.far_zone,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def _get_plan_html(self):
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': self.plan.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_r10_server_link_review_shows_connection_edit_url(self):
        """Gap 3a: plan detail HTML must contain the PSC edit URL in Server-Link Review."""
        html = self._get_plan_html()
        edit_conn_url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_edit',
            kwargs={'pk': self.conn.pk},
        )
        self.assertIn(
            edit_conn_url, html,
            'Gap 3a: edit_connection_url must appear in rendered plan detail — '
            'GREEN must not drop Server-Link Review navigation affordances',
        )

    def test_r10_server_link_review_shows_zone_edit_url(self):
        """Gap 3b: plan detail HTML must contain the zone edit URL in Server-Link Review."""
        html = self._get_plan_html()
        edit_zone_url = reverse(
            'plugins:netbox_hedgehog:switchportzone_edit',
            kwargs={'pk': self.zone.pk},
        )
        self.assertIn(
            edit_zone_url, html,
            'Gap 3b: edit_zone_url must appear in rendered plan detail — '
            'GREEN must not drop Server-Link Review navigation affordances',
        )

    def test_r10_switch_fabric_review_shows_near_zone_edit_url(self):
        """Gap 3c: plan detail HTML must contain the near-zone edit URL in Switch-Fabric Review."""
        html = self._get_plan_html()
        edit_near_url = reverse(
            'plugins:netbox_hedgehog:switchportzone_edit',
            kwargs={'pk': self.near_zone.pk},
        )
        self.assertIn(
            edit_near_url, html,
            'Gap 3c: edit_near_zone_url must appear in rendered plan detail — '
            'GREEN must not drop Switch-Fabric Review navigation affordances',
        )

    def test_r10_switch_fabric_review_shows_far_zone_edit_url(self):
        """Gap 3d: plan detail HTML must contain the far-zone edit URL in Switch-Fabric Review."""
        html = self._get_plan_html()
        edit_far_url = reverse(
            'plugins:netbox_hedgehog:switchportzone_edit',
            kwargs={'pk': self.far_zone.pk},
        )
        self.assertIn(
            edit_far_url, html,
            'Gap 3d: edit_far_zone_url must appear in rendered plan detail — '
            'GREEN must not drop Switch-Fabric Review navigation affordances',
        )
