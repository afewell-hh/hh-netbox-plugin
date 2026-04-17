"""
RED tests for #465 — mandatory transceiver enforcement in review and detail UX.

Acceptance cases covered:
  A13 — Plan detail page for null-transceiver plan → alert block visible;
         Server-Link Review shows blocked rows with '⚠ Missing (required)' labels
  A14 — Plan detail page for fully-populated plan → alert block hidden;
         Server-Link Review shows match/needs_review rows only
  A15 — Switch-Fabric Review for paired zones, both null → outcome='blocked',
         xcvr labels '⚠ Missing (required)'
  A16 — Switch-Fabric Review for paired zones, one null → outcome='blocked',
         null side '⚠ Missing (required)'

Service unit tests:
  RV1 — _xcvr_label(None) returns '⚠ Missing (required)'
  RV2 — _xcvr_label(mt) returns the description-first label unchanged
  RV3 — build_server_link_review() row for null-connection transceiver:
         outcome='blocked', server_xcvr_label='⚠ Missing (required)'
  RV4 — build_server_link_review() row for null-zone transceiver:
         outcome='blocked', zone_xcvr_label='⚠ Missing (required)'
  RV5 — build_server_link_review() row for both-null transceiver:
         outcome='blocked', both xcvr labels '⚠ Missing (required)'
  RV6 — build_server_link_review() row for both-set, compatible transceiver:
         outcome='match' (unchanged; no regression)
  RV7 — build_switch_fabric_review() paired row, both null:
         outcome='blocked', both xcvr labels '⚠ Missing (required)'
  RV8 — build_switch_fabric_review() paired row, one null:
         outcome='blocked', null-side label '⚠ Missing (required)'
  RV9 — build_switch_fabric_review() unpaired row: outcome=None regardless
         of null transceiver (unpaired rows are informational only)

All tests are RED until GREEN updates _xcvr_label(), _determine_outcome(),
build_switch_fabric_review() null gate, and template alert condition.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import DeviceType, Manufacturer, ModuleBayTemplate

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

_MISSING_LABEL = '⚠ Missing (required)'


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_review_fixtures():
    """Return (mfr, switch_dt, ext, bo_1x) for review tests."""
    mfr, _ = Manufacturer.objects.get_or_create(
        name='MxtRV-Vendor', defaults={'slug': 'mxtrv-vendor'}
    )
    switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='MxtRV-Switch', defaults={'slug': 'mxtrv-switch'}
    )
    ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=switch_dt,
        defaults={
            'native_speed': 200,
            'supported_breakouts': ['1x200g'],
            'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    bo, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x200g-mxtrv',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    srv_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='MxtRV-SRV', defaults={'slug': 'mxtrv-srv'}
    )
    return mfr, switch_dt, ext, bo, srv_dt


def _make_plan_with_null_conn_and_zone():
    """Build a plan with one null-transceiver connection and one null zone."""
    mfr, switch_dt, ext, bo, srv_dt = _make_review_fixtures()
    plan = TopologyPlan.objects.create(
        name='MxtRV-NullPlan', status=TopologyPlanStatusChoices.DRAFT,
    )
    sc = PlanServerClass.objects.create(
        plan=plan, server_class_id='gpu', server_device_type=srv_dt, quantity=2,
    )
    sw = PlanSwitchClass.objects.create(
        plan=plan, switch_class_id='fe-leaf',
        fabric_name=FabricTypeChoices.FRONTEND,
        fabric_class=FabricClassChoices.MANAGED,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=ext,
        uplink_ports_per_switch=0, mclag_pair=False,
        override_quantity=2, redundancy_type='eslag',
    )
    zone = SwitchPortZone.objects.create(
        switch_class=sw, zone_name='server-dl',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-48',
        breakout_option=bo,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        transceiver_module_type=None,
    )
    nic = get_test_server_nic(sc, nic_id='nic-rv')
    PlanServerConnection.objects.create(
        server_class=sc, connection_id='fe',
        nic=nic, port_index=0, ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        target_zone=zone, speed=200, port_type='data',
        transceiver_module_type=None,
    )
    return plan


def _make_plan_with_full_xcvr():
    """Build a plan with all transceivers set (valid state)."""
    mfr, switch_dt, ext, bo, srv_dt = _make_review_fixtures()
    xcvr = get_test_transceiver_module_type()
    plan = TopologyPlan.objects.create(
        name='MxtRV-FullPlan', status=TopologyPlanStatusChoices.DRAFT,
    )
    sc = PlanServerClass.objects.create(
        plan=plan, server_class_id='gpu', server_device_type=srv_dt, quantity=2,
    )
    sw = PlanSwitchClass.objects.create(
        plan=plan, switch_class_id='fe-leaf',
        fabric_name=FabricTypeChoices.FRONTEND,
        fabric_class=FabricClassChoices.MANAGED,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=ext,
        uplink_ports_per_switch=0, mclag_pair=False,
        override_quantity=2, redundancy_type='eslag',
    )
    zone = SwitchPortZone.objects.create(
        switch_class=sw, zone_name='server-dl',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-48',
        breakout_option=bo,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        transceiver_module_type=xcvr,
    )
    nic = get_test_server_nic(sc, nic_id='nic-rv-full')
    # Ensure the NIC ModuleType has a ModuleBayTemplate so Phase 2 (NIC bay check) passes.
    ModuleBayTemplate.objects.get_or_create(module_type=nic.module_type, name='cage-0')
    PlanServerConnection.objects.create(
        server_class=sc, connection_id='fe',
        nic=nic, port_index=0, ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        target_zone=zone, speed=200, port_type='data',
        transceiver_module_type=xcvr,
    )
    return plan


# ---------------------------------------------------------------------------
# Group RV — service-level unit tests
# ---------------------------------------------------------------------------

class MandatoryTransceiverLabelTestCase(TestCase):
    """RV1–RV2: _xcvr_label() null and non-null behaviour."""

    def _xcvr_label(self, mt):
        from netbox_hedgehog.services.connection_review import _xcvr_label
        return _xcvr_label(mt)

    def test_rv1_null_returns_missing_required(self):
        """RV1: _xcvr_label(None) must return '⚠ Missing (required)'."""
        label = self._xcvr_label(None)
        self.assertEqual(
            label, _MISSING_LABEL,
            f'_xcvr_label(None) must return {_MISSING_LABEL!r}; got {label!r}',
        )

    def test_rv2_set_returns_description_model_format(self):
        """RV2: _xcvr_label(mt) returns description-first label when mt is set."""
        mt = get_test_transceiver_module_type()
        label = self._xcvr_label(mt)
        # Must not be the missing label
        self.assertNotEqual(
            label, _MISSING_LABEL,
            '_xcvr_label(mt) must not return the missing label for a non-null mt',
        )
        # Must contain the model name somewhere
        self.assertIn(
            mt.model, label,
            f'_xcvr_label(mt) must include ModuleType.model in label; got {label!r}',
        )


class MandatoryTransceiverSwitchFabricLabelTestCase(TestCase):
    """RV1 for switch_fabric_review._xcvr_label() — must have same contract."""

    def _xcvr_label(self, mt):
        from netbox_hedgehog.services.switch_fabric_review import _xcvr_label
        return _xcvr_label(mt)

    def test_null_returns_missing_required(self):
        """switch_fabric_review._xcvr_label(None) returns '⚠ Missing (required)'."""
        label = self._xcvr_label(None)
        self.assertEqual(
            label, _MISSING_LABEL,
            f'switch_fabric_review._xcvr_label(None) must return {_MISSING_LABEL!r}; '
            f'got {label!r}',
        )


class MandatoryTransceiverServerLinkReviewServiceTestCase(TestCase):
    """RV3–RV6: build_server_link_review() outcome for null/non-null transceivers."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.switch_dt, cls.ext, cls.bo, cls.srv_dt = _make_review_fixtures()
        cls.xcvr = get_test_transceiver_module_type()

    def _build_review(self, plan):
        from netbox_hedgehog.services.connection_review import build_server_link_review
        return build_server_link_review(plan)

    def _make_plan(self, conn_xcvr=None, zone_xcvr=None, suffix=''):
        plan = TopologyPlan.objects.create(
            name=f'MxtRV-SLR-{suffix}', status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu', server_device_type=self.srv_dt, quantity=1,
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
            switch_class=sw, zone_name='server-dl',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-48',
            breakout_option=self.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=zone_xcvr,
        )
        nic = get_test_server_nic(sc, nic_id=f'nic-rv-{suffix}')
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
            transceiver_module_type=conn_xcvr,
        )
        return plan

    # RV3
    def test_rv3_null_connection_xcvr_row_is_blocked(self):
        """RV3: Row where connection transceiver is null → outcome='blocked'."""
        plan = self._make_plan(conn_xcvr=None, zone_xcvr=self.xcvr, suffix='rv3')
        review = self._build_review(plan)
        self.assertTrue(len(review.rows) > 0, 'Must have at least one row')
        row = review.rows[0]
        self.assertEqual(
            row.outcome, 'blocked',
            f'Row with null connection transceiver must be blocked; got {row.outcome!r}',
        )
        self.assertEqual(
            row.server_xcvr_label, _MISSING_LABEL,
            f'server_xcvr_label must be {_MISSING_LABEL!r}; got {row.server_xcvr_label!r}',
        )

    # RV4
    def test_rv4_null_zone_xcvr_row_is_blocked(self):
        """RV4: Row where zone transceiver is null → outcome='blocked'."""
        plan = self._make_plan(conn_xcvr=self.xcvr, zone_xcvr=None, suffix='rv4')
        review = self._build_review(plan)
        row = review.rows[0]
        self.assertEqual(
            row.outcome, 'blocked',
            f'Row with null zone transceiver must be blocked; got {row.outcome!r}',
        )
        self.assertEqual(
            row.zone_xcvr_label, _MISSING_LABEL,
            f'zone_xcvr_label must be {_MISSING_LABEL!r}; got {row.zone_xcvr_label!r}',
        )

    # RV5
    def test_rv5_both_null_xcvr_row_is_blocked(self):
        """RV5: Row where both connection and zone transceivers are null → outcome='blocked'."""
        plan = self._make_plan(conn_xcvr=None, zone_xcvr=None, suffix='rv5')
        review = self._build_review(plan)
        row = review.rows[0]
        self.assertEqual(
            row.outcome, 'blocked',
            f'Row with both null transceivers must be blocked; got {row.outcome!r}',
        )
        self.assertEqual(row.server_xcvr_label, _MISSING_LABEL)
        self.assertEqual(row.zone_xcvr_label, _MISSING_LABEL)
        self.assertGreater(
            review.blocked_count, 0,
            'blocked_count must be > 0 when rows are blocked',
        )

    # RV6
    def test_rv6_both_set_compatible_row_is_match(self):
        """RV6: Row with both transceivers set and compatible → outcome='match' (no regression)."""
        plan = self._make_plan(conn_xcvr=self.xcvr, zone_xcvr=self.xcvr, suffix='rv6')
        review = self._build_review(plan)
        row = review.rows[0]
        self.assertEqual(
            row.outcome, 'match',
            f'Row with compatible transceivers must remain match; got {row.outcome!r}',
        )
        self.assertNotEqual(row.server_xcvr_label, _MISSING_LABEL)
        self.assertNotEqual(row.zone_xcvr_label, _MISSING_LABEL)


class MandatoryTransceiverSwitchFabricReviewServiceTestCase(TestCase):
    """RV7–RV9: build_switch_fabric_review() outcome for null paired zones."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.switch_dt, cls.ext, cls.bo, cls.srv_dt = _make_review_fixtures()
        cls.xcvr = get_test_transceiver_module_type()

    def _build_review(self, plan):
        from netbox_hedgehog.services.switch_fabric_review import build_switch_fabric_review
        return build_switch_fabric_review(plan)

    def _make_plan_with_paired_zones(self, near_xcvr=None, far_xcvr=None, suffix=''):
        """Build a plan with two zones connected via peer_zone FK."""
        plan = TopologyPlan.objects.create(
            name=f'MxtRV-SFR-{suffix}', status=TopologyPlanStatusChoices.DRAFT,
        )
        sw_near = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        sw_far = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-spine',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SPINE,
            device_type_extension=self.ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        zone_far = SwitchPortZone.objects.create(
            switch_class=sw_far, zone_name='fe-spine-downlinks',
            zone_type=PortZoneTypeChoices.FABRIC, port_spec='1-32',
            breakout_option=self.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=far_xcvr,
        )
        zone_near = SwitchPortZone.objects.create(
            switch_class=sw_near, zone_name='fe-leaf-uplinks',
            zone_type=PortZoneTypeChoices.UPLINK, port_spec='1-8',
            breakout_option=self.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=near_xcvr,
            peer_zone=zone_far,
        )
        return plan, zone_near, zone_far

    # RV7
    def test_rv7_paired_both_null_is_blocked(self):
        """RV7: Paired zones with both null transceiver → outcome='blocked'."""
        plan, zone_near, _ = self._make_plan_with_paired_zones(
            near_xcvr=None, far_xcvr=None, suffix='rv7'
        )
        review = self._build_review(plan)
        paired_rows = [r for r in review.rows if r.far_zone_name is not None]
        self.assertTrue(len(paired_rows) > 0, 'Must have at least one paired row')
        row = paired_rows[0]
        self.assertEqual(
            row.outcome, 'blocked',
            f'Paired row with both null xcvr must be blocked; got {row.outcome!r}',
        )
        self.assertEqual(row.near_xcvr_label, _MISSING_LABEL)
        self.assertEqual(row.far_xcvr_label, _MISSING_LABEL)

    # RV8
    def test_rv8_paired_one_null_is_blocked(self):
        """RV8: Paired zones with one null transceiver → outcome='blocked'."""
        plan, _, _ = self._make_plan_with_paired_zones(
            near_xcvr=None, far_xcvr=self.xcvr, suffix='rv8'
        )
        review = self._build_review(plan)
        paired_rows = [r for r in review.rows if r.far_zone_name is not None]
        row = paired_rows[0]
        self.assertEqual(
            row.outcome, 'blocked',
            f'Paired row with one null xcvr must be blocked; got {row.outcome!r}',
        )
        # Near is null; far is set
        self.assertEqual(row.near_xcvr_label, _MISSING_LABEL)
        self.assertNotEqual(row.far_xcvr_label, _MISSING_LABEL)

    # RV9
    def test_rv9_unpaired_zone_outcome_is_none_regardless_of_null_xcvr(self):
        """
        RV9: Unpaired zone (no peer_zone) with null transceiver → outcome=None.
        Unpaired rows are informational; they do not get a blocked outcome.
        The xcvr label still reflects null as '⚠ Missing (required)'.
        """
        plan = TopologyPlan.objects.create(
            name='MxtRV-SFR-rv9', status=TopologyPlanStatusChoices.DRAFT,
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
        # Uplink zone with no peer_zone — intentionally no transceiver
        SwitchPortZone.objects.create(
            switch_class=sw, zone_name='fe-leaf-uplinks-unpaired',
            zone_type=PortZoneTypeChoices.UPLINK, port_spec='1-8',
            breakout_option=self.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=None,
            peer_zone=None,
        )
        review = self._build_review(plan)
        unpaired = [r for r in review.rows if r.far_zone_name is None]
        self.assertTrue(len(unpaired) > 0, 'Must have unpaired rows')
        row = unpaired[0]
        self.assertIsNone(
            row.outcome,
            f'Unpaired row must have outcome=None; got {row.outcome!r}',
        )
        # Label still shows missing
        self.assertEqual(
            row.near_xcvr_label, _MISSING_LABEL,
            f'Unpaired null-xcvr zone label must be {_MISSING_LABEL!r}',
        )


# ---------------------------------------------------------------------------
# Group A13/A14 — plan detail page view integration
# ---------------------------------------------------------------------------

class MandatoryTransceiverPlanDetailViewTestCase(TestCase):
    """
    A13: Plan detail page for null-transceiver plan → alert visible, blocked rows.
    A14: Plan detail page for fully-populated plan → alert hidden, clean rows.
    """

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='mxt-detail-admin', password='pass',
            is_staff=True, is_superuser=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    # A13
    def test_a13_plan_detail_shows_alert_and_blocked_for_null_xcvr_plan(self):
        """
        A13: GET plan detail for a null-transceiver plan → 200;
        alert block is visible; Server-Link Review shows blocked rows
        with '⚠ Missing (required)' labels.
        """
        plan = _make_plan_with_null_conn_and_zone()
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', kwargs={'pk': plan.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()

        # The transceiver prerequisite alert must be visible.
        self.assertIn(
            'Transceiver Bay Prerequisite Missing', content,
            'Prerequisite alert block must be visible for null-transceiver plan',
        )

        # The '⚠ Missing (required)' label must appear in the Server-Link Review.
        self.assertIn(
            _MISSING_LABEL, content,
            f'{_MISSING_LABEL!r} must appear in the rendered plan detail page',
        )

        # The blocked row indicator must appear (table-danger class or 'blocked' outcome).
        self.assertIn(
            'table-danger', content,
            'Server-Link Review must render blocked rows with table-danger style',
        )

    # A14
    def test_a14_plan_detail_hides_alert_for_fully_populated_plan(self):
        """
        A14: GET plan detail for a fully-populated plan → 200;
        alert block not rendered; Server-Link Review shows no missing labels.
        """
        plan = _make_plan_with_full_xcvr()
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', kwargs={'pk': plan.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()

        # The prerequisite alert must NOT appear.
        self.assertNotIn(
            'Transceiver Bay Prerequisite Missing', content,
            'Alert must not appear for a fully-populated plan',
        )

        # The missing label must not appear in any review row.
        self.assertNotIn(
            _MISSING_LABEL, content,
            f'{_MISSING_LABEL!r} must not appear for a fully-populated plan',
        )
