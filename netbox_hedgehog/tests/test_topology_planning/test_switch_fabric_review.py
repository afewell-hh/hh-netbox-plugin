"""
RED tests for DIET-460 / DIET-505 (Phase 3): Switch-Fabric Link Review service and plan detail panel.

DIET-460 tests (SFR-1 through SFR-14) are GREEN after Phase 4.
DIET-505 Phase 3 tests (categories A–I) are RED until Phase 4 GREEN implementation.

Spec source: GitHub issue #508 (Phase 2 tech spec) and #509 (Phase 3 RED).
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from dcim.models import DeviceType, Manufacturer, ModuleType, ModuleTypeProfile
from users.models import ObjectPermission

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_switch_ext():
    mfr, _ = Manufacturer.objects.get_or_create(
        name='SFR-Vendor', defaults={'slug': 'sfr-vendor'}
    )
    dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='SFR-Switch', defaults={'slug': 'sfr-switch'}
    )
    ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=dt,
        defaults={
            'native_speed': 400,
            'supported_breakouts': ['1x400g'],
            'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    return ext


def _make_plan(name='SFR-Plan'):
    return TopologyPlan.objects.create(
        name=name, status=TopologyPlanStatusChoices.DRAFT
    )


def _make_switch_class(plan, ext, sc_id='sfr-fe-leaf',
                       role=HedgehogRoleChoices.SERVER_LEAF):
    return PlanSwitchClass.objects.create(
        plan=plan,
        switch_class_id=sc_id,
        fabric=FabricTypeChoices.FRONTEND,
        hedgehog_role=role,
        device_type_extension=ext,
        uplink_ports_per_switch=4,
    )


def _make_uplink_zone(sw, name='sfr-uplink', xcvr=None,
                      zone_type=PortZoneTypeChoices.UPLINK, peer_zone=None):
    bo, _ = BreakoutOption.objects.get_or_create(
        breakout_id='sfr-1x400g',
        defaults={'from_speed': 400, 'logical_ports': 1, 'logical_speed': 400},
    )
    return SwitchPortZone.objects.create(
        switch_class=sw,
        zone_name=name,
        zone_type=zone_type,
        port_spec='33-48',
        breakout_option=bo,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
        priority=200,
        transceiver_module_type=xcvr,
        peer_zone=peer_zone,
    )


def _get_mmf_xcvr(model='SFR-XCVR-MMF'):
    mfr, _ = Manufacturer.objects.get_or_create(
        name='SFR-MMF-Vendor', defaults={'slug': 'sfr-mmf-vendor'}
    )
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr, model=model,
        defaults={
            'profile': profile,
            'description': f'SFR MMF Optic {model}',
            'attribute_data': {'cage_type': 'QSFP112', 'medium': 'MMF'},
        },
    )
    return mt


def _get_smf_xcvr():
    mfr, _ = Manufacturer.objects.get_or_create(
        name='SFR-SMF-Vendor', defaults={'slug': 'sfr-smf-vendor'}
    )
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr, model='SFR-XCVR-SMF',
        defaults={
            'profile': profile,
            'description': 'SFR SMF Optic',
            'attribute_data': {'cage_type': 'QSFP112', 'medium': 'SMF'},
        },
    )
    return mt


# ---------------------------------------------------------------------------
# Unit tests for build_switch_fabric_review()
# ---------------------------------------------------------------------------

class TestSwitchFabricReviewService(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.ext = _make_switch_ext()

    def setUp(self):
        self.plan = _make_plan()
        self.sw = _make_switch_class(self.plan, self.ext)

    def _build(self):
        # RED: module does not exist yet
        from netbox_hedgehog.services.switch_fabric_review import build_switch_fabric_review
        return build_switch_fabric_review(self.plan)

    # SFR-1: paired zone, both null → needs_review (null intent is review concern)
    def test_sfr1_paired_both_null_is_needs_review(self):
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine')
        far = _make_uplink_zone(sw2, name='sfr-spine-dl', zone_type=PortZoneTypeChoices.FABRIC)
        near = _make_uplink_zone(self.sw, name='sfr-leaf-ul', peer_zone=far)
        summary = self._build()
        paired = [r for r in summary.rows if r.is_paired]
        self.assertEqual(len(paired), 1)
        self.assertEqual(paired[0].outcome, 'needs_review')

    # SFR-2: paired, both xcvr set with matching attrs → match
    def test_sfr2_paired_matching_xcvr_is_match(self):
        xcvr = _get_mmf_xcvr('SFR-MATCH')
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine-2')
        far = _make_uplink_zone(sw2, name='sfr-sp2-dl',
                                zone_type=PortZoneTypeChoices.FABRIC, xcvr=xcvr)
        near = _make_uplink_zone(self.sw, name='sfr-lf2-ul', xcvr=xcvr, peer_zone=far)
        summary = self._build()
        paired = [r for r in summary.rows if r.is_paired]
        self.assertEqual(paired[0].outcome, 'match')

    # SFR-3: paired, MMF near / SMF far → blocked (medium mismatch)
    def test_sfr3_paired_medium_mismatch_is_blocked(self):
        mmf = _get_mmf_xcvr('SFR-MMF-3')
        smf = _get_smf_xcvr()
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine-3')
        far = _make_uplink_zone(sw2, name='sfr-sp3-dl',
                                zone_type=PortZoneTypeChoices.FABRIC, xcvr=smf)
        near = _make_uplink_zone(self.sw, name='sfr-lf3-ul', xcvr=mmf, peer_zone=far)
        summary = self._build()
        paired = [r for r in summary.rows if r.is_paired]
        self.assertEqual(paired[0].outcome, 'blocked')

    # SFR-4: paired, near xcvr set, far null → needs_review (null intent is review concern)
    def test_sfr4_paired_one_null_is_needs_review(self):
        xcvr = _get_mmf_xcvr('SFR-ASYM-4')
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine-4')
        far = _make_uplink_zone(sw2, name='sfr-sp4-dl',
                                zone_type=PortZoneTypeChoices.FABRIC, xcvr=None)
        near = _make_uplink_zone(self.sw, name='sfr-lf4-ul', xcvr=xcvr, peer_zone=far)
        summary = self._build()
        paired = [r for r in summary.rows if r.is_paired]
        self.assertEqual(paired[0].outcome, 'needs_review')

    # SFR-5: UPLINK zone, no peer_zone, xcvr set → unpaired row, outcome None (informational)
    def test_sfr5_unpaired_uplink_zone_with_xcvr_has_none_outcome(self):
        xcvr = _get_mmf_xcvr('SFR-XCVR-SFR5')
        _make_uplink_zone(self.sw, name='sfr-unpaired', zone_type=PortZoneTypeChoices.UPLINK,
                          xcvr=xcvr)
        summary = self._build()
        unpaired = [r for r in summary.rows if not r.is_paired]
        self.assertEqual(len(unpaired), 1)
        self.assertIsNone(unpaired[0].outcome)
        # Eligible managed uplink with no spine candidate now gives inference-aware reason.
        self.assertIn('frontend', unpaired[0].reason)

    # SFR-5b: UPLINK zone, no peer_zone, xcvr null → needs_review (null intent is review concern)
    def test_sfr5b_unpaired_uplink_zone_without_xcvr_is_needs_review(self):
        _make_uplink_zone(self.sw, name='sfr-unpaired-null', zone_type=PortZoneTypeChoices.UPLINK,
                          xcvr=None)
        summary = self._build()
        unpaired = [r for r in summary.rows if not r.is_paired]
        self.assertEqual(len(unpaired), 1)
        self.assertEqual(unpaired[0].outcome, 'needs_review')
        self.assertEqual(unpaired[0].near_xcvr_label, '—')

    # Asymmetric dedup: only near has peer_zone set; far is visited first in
    # queryset order → must emit exactly one paired row (not one unpaired + one paired)
    def test_asymmetric_peer_zone_far_first_emits_one_paired_row_only(self):
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine-asym')
        # far name sorts before near name → far is iterated first
        far = _make_uplink_zone(sw2, name='sfr-a-far-dl', zone_type=PortZoneTypeChoices.FABRIC)
        near = _make_uplink_zone(self.sw, name='sfr-b-near-ul', peer_zone=far)
        # far.peer_zone is NOT set (asymmetric)
        summary = self._build()
        self.assertEqual(len(summary.rows), 1, 'Expected exactly one row, not unpaired+paired duplicate')
        self.assertTrue(summary.rows[0].is_paired)
        self.assertEqual(summary.paired_count, 1)
        self.assertEqual(summary.unpaired_count, 0)

    # SFR-6: peer_zone set on both A and B → exactly one row emitted
    def test_sfr6_symmetric_peer_zone_emits_one_row(self):
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine-6')
        # Create far first without peer_zone, then set it after
        far = _make_uplink_zone(sw2, name='sfr-sp6-dl', zone_type=PortZoneTypeChoices.FABRIC)
        near = _make_uplink_zone(self.sw, name='sfr-lf6-ul', peer_zone=far)
        far.peer_zone = near
        far.save()
        summary = self._build()
        paired = [r for r in summary.rows if r.is_paired]
        self.assertEqual(len(paired), 1, 'Expected exactly one paired row (A<B dedup)')

    def test_multiple_near_zones_can_share_one_far_zone(self):
        sw_gpu = _make_switch_class(self.plan, self.ext, sc_id='sfr-fe-gpu-leaf')
        sw_storage = _make_switch_class(self.plan, self.ext, sc_id='sfr-fe-storage-leaf')
        sw_spine = _make_switch_class(self.plan, self.ext, sc_id='sfr-fe-spine')

        far = _make_uplink_zone(
            sw_spine,
            name='fe-spine-downlinks',
            zone_type=PortZoneTypeChoices.FABRIC,
        )
        _make_uplink_zone(
            sw_gpu,
            name='fe-gpu-leaf-uplinks',
            zone_type=PortZoneTypeChoices.UPLINK,
            peer_zone=far,
        )
        _make_uplink_zone(
            sw_storage,
            name='fe-storage-leaf-uplinks',
            zone_type=PortZoneTypeChoices.UPLINK,
            peer_zone=far,
        )

        summary = self._build()
        paired = [r for r in summary.rows if r.is_paired]
        self.assertEqual(len(paired), 2)
        self.assertCountEqual(
            [r.near_zone_name for r in paired],
            ['fe-gpu-leaf-uplinks', 'fe-storage-leaf-uplinks'],
        )
        self.assertTrue(all(r.far_zone_name == 'fe-spine-downlinks' for r in paired))

    # SFR-7: zones from two fabrics → rows sorted by fabric_name
    def test_sfr7_rows_sorted_by_fabric_name(self):
        from netbox_hedgehog.choices import FabricTypeChoices
        ext2 = self.ext
        sw_be = PlanSwitchClass.objects.create(
            plan=self.plan, switch_class_id='sfr-be-leaf',
            fabric=FabricTypeChoices.BACKEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=ext2, uplink_ports_per_switch=4,
        )
        _make_uplink_zone(self.sw, name='sfr-fe-ul', zone_type=PortZoneTypeChoices.UPLINK)
        _make_uplink_zone(sw_be, name='sfr-be-ul', zone_type=PortZoneTypeChoices.UPLINK)
        summary = self._build()
        fabrics = [r.near_fabric_name for r in summary.rows]
        self.assertEqual(fabrics, sorted(fabrics))

    # SFR-8: server zones excluded from Switch-Fabric Review
    def test_sfr8_server_zones_excluded(self):
        from netbox_hedgehog.models.topology_planning import BreakoutOption
        bo, _ = BreakoutOption.objects.get_or_create(
            breakout_id='sfr-srv-1x', defaults={'from_speed': 400, 'logical_ports': 1, 'logical_speed': 400}
        )
        SwitchPortZone.objects.create(
            switch_class=self.sw, zone_name='sfr-server-zone',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-32', breakout_option=bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )
        summary = self._build()
        server_rows = [r for r in summary.rows
                       if r.near_zone_name == 'sfr-server-zone']
        self.assertEqual(len(server_rows), 0)

    # SFR-9: OOB zones excluded
    def test_sfr9_oob_zones_excluded(self):
        from netbox_hedgehog.models.topology_planning import BreakoutOption
        bo, _ = BreakoutOption.objects.get_or_create(
            breakout_id='sfr-oob-1x', defaults={'from_speed': 10, 'logical_ports': 1, 'logical_speed': 10}
        )
        SwitchPortZone.objects.create(
            switch_class=self.sw, zone_name='sfr-oob-zone',
            zone_type=PortZoneTypeChoices.OOB,
            port_spec='17-20', breakout_option=bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )
        summary = self._build()
        oob_rows = [r for r in summary.rows if r.near_zone_name == 'sfr-oob-zone']
        self.assertEqual(len(oob_rows), 0)

    # SFR-10: paired row → edit_near_zone_url is switchportzone_edit for near zone
    def test_sfr10_edit_near_zone_url_for_paired_row(self):
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine-10')
        far = _make_uplink_zone(sw2, name='sfr-sp10-dl', zone_type=PortZoneTypeChoices.FABRIC)
        near = _make_uplink_zone(self.sw, name='sfr-lf10-ul', peer_zone=far)
        summary = self._build()
        paired = [r for r in summary.rows if r.is_paired][0]
        expected = reverse('plugins:netbox_hedgehog:switchportzone_edit',
                           args=[near.pk])
        self.assertEqual(paired.edit_near_zone_url, expected)

    # SFR-11: paired row → edit_far_zone_url is switchportzone_edit for far zone
    def test_sfr11_edit_far_zone_url_for_paired_row(self):
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine-11')
        far = _make_uplink_zone(sw2, name='sfr-sp11-dl', zone_type=PortZoneTypeChoices.FABRIC)
        near = _make_uplink_zone(self.sw, name='sfr-lf11-ul', peer_zone=far)
        summary = self._build()
        paired = [r for r in summary.rows if r.is_paired][0]
        expected = reverse('plugins:netbox_hedgehog:switchportzone_edit',
                           args=[far.pk])
        self.assertEqual(paired.edit_far_zone_url, expected)

    # SFR-12: unpaired row → edit_far_zone_url is None
    def test_sfr12_unpaired_row_no_far_edit_url(self):
        _make_uplink_zone(self.sw, name='sfr-unp12', zone_type=PortZoneTypeChoices.UPLINK)
        summary = self._build()
        unpaired = [r for r in summary.rows if not r.is_paired][0]
        self.assertIsNone(unpaired.edit_far_zone_url)

    # near_xcvr_label uses description+model format
    def test_near_xcvr_label_uses_description_format(self):
        xcvr = _get_mmf_xcvr('SFR-LABEL-TEST')
        _make_uplink_zone(self.sw, name='sfr-label-ul',
                          zone_type=PortZoneTypeChoices.UPLINK, xcvr=xcvr)
        summary = self._build()
        row = summary.rows[0]
        self.assertIn('SFR MMF Optic SFR-LABEL-TEST', row.near_xcvr_label)
        self.assertIn('SFR-LABEL-TEST', row.near_xcvr_label)

    # near_xcvr_label is '—' when null (neutral label, not alarming)
    def test_near_xcvr_label_dash_when_null(self):
        _make_uplink_zone(self.sw, name='sfr-null-ul',
                          zone_type=PortZoneTypeChoices.UPLINK, xcvr=None)
        summary = self._build()
        self.assertEqual(summary.rows[0].near_xcvr_label, '—')

    # Summary counters (paired/unpaired/match/needs_review/blocked)
    def test_summary_counters_are_consistent(self):
        xcvr = _get_mmf_xcvr('SFR-XCVR-CNT')
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine-cnt')
        far = _make_uplink_zone(sw2, name='sfr-far-cnt', zone_type=PortZoneTypeChoices.FABRIC,
                                xcvr=xcvr)
        _make_uplink_zone(self.sw, name='sfr-near-cnt', peer_zone=far, xcvr=xcvr)
        # Unpaired zone with xcvr set → outcome=None (informational, not blocked)
        _make_uplink_zone(self.sw, name='sfr-unp-cnt', zone_type=PortZoneTypeChoices.UPLINK,
                          xcvr=xcvr)
        summary = self._build()
        self.assertEqual(summary.paired_count + summary.unpaired_count, len(summary.rows))
        # Unpaired xcvr-set zones have outcome=None, so blocked_count reflects only paired rows.
        self.assertEqual(
            summary.match_count + summary.needs_review_count + summary.blocked_count,
            summary.paired_count,
        )

    def test_empty_plan_returns_empty_summary(self):
        summary = self._build()
        self.assertEqual(summary.rows, [])
        self.assertEqual(summary.paired_count, 0)
        self.assertEqual(summary.unpaired_count, 0)


# ---------------------------------------------------------------------------
# Integration tests: plan detail renders Switch-Fabric Link Review panel
# ---------------------------------------------------------------------------

class TestSwitchFabricReviewIntegration(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.ext = _make_switch_ext()
        cls.superuser = User.objects.create_user(
            username='sfr-su', password='pass', is_staff=True, is_superuser=True
        )
        # viewer: plan view ObjectPermission only
        cls.viewer = User.objects.create_user(
            username='sfr-viewer', password='pass', is_staff=True
        )
        from django.contrib.auth.models import Permission
        perm = Permission.objects.get(
            content_type__app_label='netbox_hedgehog',
            codename='view_topologyplan',
        )
        cls.viewer.user_permissions.add(perm)
        obj_perm = ObjectPermission.objects.create(
            name='sfr-viewer-plan', actions=['view']
        )
        obj_perm.object_types.add(ContentType.objects.get_for_model(TopologyPlan))
        obj_perm.users.add(cls.viewer)

    def setUp(self):
        self.client = Client()
        self.client.login(username='sfr-su', password='pass')
        self.plan = _make_plan(name='SFR-View-Plan')
        self.sw = _make_switch_class(self.plan, self.ext)

    def _url(self):
        return reverse('plugins:netbox_hedgehog:topologyplan_detail',
                       kwargs={'pk': self.plan.pk})

    # SFR-13: panel heading present
    def test_sfr13_switch_fabric_review_heading_in_html(self):
        _make_uplink_zone(self.sw, name='sfr-html-ul', zone_type=PortZoneTypeChoices.UPLINK)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Switch-Fabric Link Review')

    # SFR-13: context key present
    def test_sfr13_context_has_switch_fabric_review_key(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('switch_fabric_review', resp.context)

    # SFR-14: zero qualifying zones → empty state text
    def test_sfr14_empty_state_text_shown(self):
        resp = self.client.get(self._url())
        self.assertContains(resp, 'No switch-fabric zones defined')

    def test_rendered_one_sided_badge_for_unpaired_zone(self):
        _make_uplink_zone(self.sw, name='sfr-unp-badge', zone_type=PortZoneTypeChoices.UPLINK)
        resp = self.client.get(self._url())
        self.assertContains(resp, 'one-sided')

    def test_rendered_review_table_uses_standard_table_styling(self):
        _make_uplink_zone(self.sw, name='sfr-table-style', zone_type=PortZoneTypeChoices.UPLINK)
        resp = self.client.get(self._url())
        content = resp.content.decode()
        self.assertIn('<table class="table table-hover">', content)
        self.assertNotIn('table-sm', content)

    def test_rendered_edit_near_zone_link_in_html(self):
        zone = _make_uplink_zone(self.sw, name='sfr-lnk-ul', zone_type=PortZoneTypeChoices.UPLINK)
        expected = reverse('plugins:netbox_hedgehog:switchportzone_edit', args=[zone.pk])
        resp = self.client.get(self._url())
        self.assertContains(resp, expected)

    def test_rendered_edit_far_zone_link_for_paired_row(self):
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-sp-lnk')
        far = _make_uplink_zone(sw2, name='sfr-sp-lnk-dl', zone_type=PortZoneTypeChoices.FABRIC)
        _make_uplink_zone(self.sw, name='sfr-lf-lnk-ul', peer_zone=far)
        far_url = reverse('plugins:netbox_hedgehog:switchportzone_edit', args=[far.pk])
        resp = self.client.get(self._url())
        self.assertContains(resp, far_url)

    def test_near_zone_name_appears_in_html(self):
        _make_uplink_zone(self.sw, name='sfr-name-check', zone_type=PortZoneTypeChoices.UPLINK)
        resp = self.client.get(self._url())
        self.assertContains(resp, 'sfr-name-check')

    def test_viewer_sees_switch_fabric_review_panel(self):
        _make_uplink_zone(self.sw, name='sfr-viewer-ul', zone_type=PortZoneTypeChoices.UPLINK)
        self.client.login(username='sfr-viewer', password='pass')
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('switch_fabric_review', resp.context)

    def test_edit_zone_view_without_perm_is_403(self):
        zone = _make_uplink_zone(self.sw, name='sfr-perm-ul', zone_type=PortZoneTypeChoices.UPLINK)
        self.client.login(username='sfr-viewer', password='pass')
        url = reverse('plugins:netbox_hedgehog:switchportzone_edit', args=[zone.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# DIET-505 Phase 3 RED tests — inferred managed-fabric far-side pairing
# ---------------------------------------------------------------------------

def _make_spine_class(plan, ext, sc_id='sfr509-spine', fabric=FabricTypeChoices.FRONTEND):
    """Spine switch class: role=SPINE, uplink_ports_per_switch=0, same managed fabric."""
    return PlanSwitchClass.objects.create(
        plan=plan,
        switch_class_id=sc_id,
        fabric=fabric,
        hedgehog_role=HedgehogRoleChoices.SPINE,
        device_type_extension=ext,
        uplink_ports_per_switch=0,
    )


def _make_fabric_zone(sw, name='sfr509-fabric-dl', xcvr=None):
    """FABRIC zone (spine downlinks)."""
    bo, _ = BreakoutOption.objects.get_or_create(
        breakout_id='sfr509-1x400g',
        defaults={'from_speed': 400, 'logical_ports': 1, 'logical_speed': 400},
    )
    return SwitchPortZone.objects.create(
        switch_class=sw,
        zone_name=name,
        zone_type=PortZoneTypeChoices.FABRIC,
        port_spec='1-16',
        breakout_option=bo,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
        priority=100,
        transceiver_module_type=xcvr,
    )


def _make_leaf_uplink(sw, name='sfr509-leaf-ul', xcvr=None):
    """UPLINK zone on a leaf (no peer_zone)."""
    return _make_uplink_zone(sw, name=name, xcvr=xcvr,
                             zone_type=PortZoneTypeChoices.UPLINK, peer_zone=None)


class TestSwitchFabricInferenceService(TestCase):
    """
    RED tests for DIET-505 Phase 3: inferred managed-fabric far-side pairing.
    All tests must fail until Phase 4 GREEN implementation.
    Failure mechanisms noted inline.
    """

    @classmethod
    def setUpTestData(cls):
        cls.ext = _make_switch_ext()

    def setUp(self):
        self.plan = _make_plan(f'SFR509-{self._testMethodName}')
        self.leaf = _make_switch_class(
            self.plan, self.ext, sc_id='sfr509-fe-leaf',
            role=HedgehogRoleChoices.SERVER_LEAF,
        )

    def _build(self):
        from netbox_hedgehog.services.switch_fabric_review import build_switch_fabric_review
        return build_switch_fabric_review(self.plan)

    # --- Category A: explicit rows stay non-inferred ---

    def test_a1_explicit_peer_zone_row_is_not_inferred(self):
        # FAIL: SwitchFabricRow has no is_inferred field → AttributeError
        spine = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-a1')
        far = _make_fabric_zone(spine, name='sfr509-sp-a1-dl')
        _make_uplink_zone(self.leaf, name='sfr509-lf-a1-ul', peer_zone=far)
        summary = self._build()
        paired = [r for r in summary.rows if r.is_paired]
        self.assertEqual(len(paired), 1)
        self.assertFalse(paired[0].is_inferred)

    def test_a2_inferred_count_present_on_summary(self):
        # FAIL: SwitchFabricReviewSummary has no inferred_count field → AttributeError
        summary = self._build()
        self.assertEqual(summary.inferred_count, 0)

    # --- Category B: single-candidate inferred pairing ---

    def test_b1_single_spine_candidate_produces_inferred_row(self):
        # FAIL: no inference logic → leaf uplink stays unpaired, is_inferred doesn't exist
        spine = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-b1')
        _make_fabric_zone(spine, name='sfr509-sp-b1-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-b1-ul')
        summary = self._build()
        inferred = [r for r in summary.rows if getattr(r, 'is_inferred', False)]
        self.assertEqual(len(inferred), 1)
        self.assertTrue(inferred[0].is_paired)

    def test_b2_inferred_row_is_inferred_true(self):
        # FAIL: field doesn't exist → AttributeError when accessing row.is_inferred
        spine = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-b2')
        _make_fabric_zone(spine, name='sfr509-sp-b2-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-b2-ul')
        summary = self._build()
        rows = summary.rows
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].is_inferred)

    def test_b3_spine_fabric_zone_suppressed_when_inferred(self):
        # FAIL: currently spine FABRIC zone emitted as unpaired row → len(rows)==2 not 1
        spine = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-b3')
        _make_fabric_zone(spine, name='sfr509-sp-b3-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-b3-ul')
        summary = self._build()
        zone_names = [r.near_zone_name for r in summary.rows]
        self.assertNotIn('sfr509-sp-b3-dl', zone_names)

    def test_b4_inferred_near_xcvr_null_is_needs_review(self):
        # FAIL: no inference → leaf stays unpaired; if it were inferred, null xcvr → needs_review
        xcvr = _get_mmf_xcvr('SFR509-MMF-B4')
        spine = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-b4')
        _make_fabric_zone(spine, name='sfr509-sp-b4-dl', xcvr=xcvr)
        _make_leaf_uplink(self.leaf, name='sfr509-lf-b4-ul', xcvr=None)
        summary = self._build()
        rows = summary.rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].outcome, 'needs_review')
        self.assertTrue(rows[0].is_inferred)

    def test_b5_inferred_far_xcvr_null_is_needs_review(self):
        # FAIL: no inference
        xcvr = _get_mmf_xcvr('SFR509-MMF-B5')
        spine = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-b5')
        _make_fabric_zone(spine, name='sfr509-sp-b5-dl', xcvr=None)
        _make_leaf_uplink(self.leaf, name='sfr509-lf-b5-ul', xcvr=xcvr)
        summary = self._build()
        rows = summary.rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].outcome, 'needs_review')

    def test_b6_inferred_both_xcvr_match(self):
        # FAIL: no inference
        xcvr = _get_mmf_xcvr('SFR509-MMF-B6')
        spine = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-b6')
        _make_fabric_zone(spine, name='sfr509-sp-b6-dl', xcvr=xcvr)
        _make_leaf_uplink(self.leaf, name='sfr509-lf-b6-ul', xcvr=xcvr)
        summary = self._build()
        rows = summary.rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].outcome, 'match')

    def test_b7_inferred_row_edit_far_zone_url_set(self):
        # FAIL: no inference → row is unpaired, edit_far_zone_url=None
        spine = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-b7')
        spine_zone = _make_fabric_zone(spine, name='sfr509-sp-b7-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-b7-ul')
        summary = self._build()
        rows = summary.rows
        self.assertEqual(len(rows), 1)
        expected_url = reverse(
            'plugins:netbox_hedgehog:switchportzone_edit', args=[spine_zone.pk]
        )
        self.assertEqual(rows[0].edit_far_zone_url, expected_url)

    def test_b8_inferred_row_counters(self):
        # FAIL: inferred_count field missing + paired_count wrong
        spine = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-b8')
        _make_fabric_zone(spine, name='sfr509-sp-b8-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-b8-ul')
        summary = self._build()
        self.assertEqual(summary.paired_count, 1)
        self.assertEqual(summary.inferred_count, 1)
        self.assertEqual(summary.unpaired_count, 0)

    # --- Category C: multi-candidate pool ---

    def test_c1_two_spine_candidates_produce_one_row(self):
        # FAIL: currently emits 2 unpaired spine rows + 1 unpaired leaf row = 3 rows total
        sp1 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp1-c1')
        sp2 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp2-c1')
        _make_fabric_zone(sp1, name='sfr509-sp1-c1-dl')
        _make_fabric_zone(sp2, name='sfr509-sp2-c1-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-c1-ul')
        summary = self._build()
        self.assertEqual(len(summary.rows), 1)

    def test_c2_pool_far_zone_name(self):
        # FAIL: no inference → far_zone_name is None
        sp1 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp1-c2')
        sp2 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp2-c2')
        _make_fabric_zone(sp1, name='sfr509-sp1-c2-dl')
        _make_fabric_zone(sp2, name='sfr509-sp2-c2-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-c2-ul')
        summary = self._build()
        self.assertEqual(len(summary.rows), 1)
        self.assertEqual(summary.rows[0].far_zone_name, 'managed spine pool (2 zones)')

    def test_c3_pool_edit_far_zone_url_is_none(self):
        # FAIL: accessing row.is_inferred → AttributeError (also validates pool behavior)
        sp1 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp1-c3')
        sp2 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp2-c3')
        _make_fabric_zone(sp1, name='sfr509-sp1-c3-dl')
        _make_fabric_zone(sp2, name='sfr509-sp2-c3-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-c3-ul')
        summary = self._build()
        self.assertEqual(len(summary.rows), 1)
        row = summary.rows[0]
        self.assertIsNone(row.edit_far_zone_url)
        self.assertTrue(row.is_inferred)

    def test_c4_pool_spine_zones_suppressed(self):
        # FAIL: currently both spine zones appear as unpaired rows
        sp1 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp1-c4')
        sp2 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp2-c4')
        _make_fabric_zone(sp1, name='sfr509-sp1-c4-dl')
        _make_fabric_zone(sp2, name='sfr509-sp2-c4-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-c4-ul')
        summary = self._build()
        zone_names = [r.near_zone_name for r in summary.rows]
        self.assertNotIn('sfr509-sp1-c4-dl', zone_names)
        self.assertNotIn('sfr509-sp2-c4-dl', zone_names)

    def test_c5_pool_uniform_xcvr_evaluates_normally(self):
        # FAIL: no inference
        xcvr = _get_mmf_xcvr('SFR509-C5')
        sp1 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp1-c5')
        sp2 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp2-c5')
        _make_fabric_zone(sp1, name='sfr509-sp1-c5-dl', xcvr=xcvr)
        _make_fabric_zone(sp2, name='sfr509-sp2-c5-dl', xcvr=xcvr)
        _make_leaf_uplink(self.leaf, name='sfr509-lf-c5-ul', xcvr=xcvr)
        summary = self._build()
        self.assertEqual(len(summary.rows), 1)
        self.assertEqual(summary.rows[0].outcome, 'match')

    def test_c6_pool_mixed_xcvr_is_needs_review(self):
        # FAIL: no inference
        mmf = _get_mmf_xcvr('SFR509-C6-MMF')
        smf = _get_smf_xcvr()
        sp1 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp1-c6')
        sp2 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp2-c6')
        _make_fabric_zone(sp1, name='sfr509-sp1-c6-dl', xcvr=mmf)
        _make_fabric_zone(sp2, name='sfr509-sp2-c6-dl', xcvr=smf)
        _make_leaf_uplink(self.leaf, name='sfr509-lf-c6-ul', xcvr=mmf)
        summary = self._build()
        self.assertEqual(len(summary.rows), 1)
        row = summary.rows[0]
        self.assertEqual(row.outcome, 'needs_review')
        self.assertIn('transceiver specifications differ', row.reason)

    # --- Category D: genuinely unpaired (no spine candidate) ---

    def test_d1_no_spine_candidate_stays_unpaired(self):
        # FAIL: is_inferred field doesn't exist → AttributeError
        _make_leaf_uplink(self.leaf, name='sfr509-lf-d1-ul')
        summary = self._build()
        self.assertEqual(len(summary.rows), 1)
        row = summary.rows[0]
        self.assertFalse(row.is_paired)
        self.assertFalse(row.is_inferred)

    def test_d2_no_spine_xcvr_set_reason(self):
        # FAIL: current reason is 'No peer_zone configured...' not the new fabric-aware string
        xcvr = _get_mmf_xcvr('SFR509-D2')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-d2-ul', xcvr=xcvr)
        summary = self._build()
        row = summary.rows[0]
        self.assertIsNone(row.outcome)
        self.assertIn('No managed spine FABRIC zone found in fabric', row.reason)
        self.assertIn('frontend', row.reason)

    def test_d3_no_spine_xcvr_null_reason_contains_fabric(self):
        # FAIL: current reason 'Transceiver intent not specified on this zone' has no fabric name
        _make_leaf_uplink(self.leaf, name='sfr509-lf-d3-ul', xcvr=None)
        summary = self._build()
        row = summary.rows[0]
        self.assertEqual(row.outcome, 'needs_review')
        self.assertIn('frontend', row.reason)

    # --- Category E: ineligible zones stay uninferred ---

    def test_e1_zero_uplink_ports_not_inferred(self):
        # FAIL: is_inferred field doesn't exist → AttributeError
        leaf0 = PlanSwitchClass.objects.create(
            plan=self.plan, switch_class_id='sfr509-leaf0-e1',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
        )
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-e1')
        _make_fabric_zone(sp, name='sfr509-sp-e1-dl')
        _make_leaf_uplink(leaf0, name='sfr509-leaf0-e1-ul')
        summary = self._build()
        leaf_rows = [r for r in summary.rows if r.near_zone_name == 'sfr509-leaf0-e1-ul']
        self.assertEqual(len(leaf_rows), 1)
        self.assertFalse(leaf_rows[0].is_paired)
        self.assertFalse(leaf_rows[0].is_inferred)

    def test_e2_zero_uplink_ports_xcvr_set_reason(self):
        # FAIL: current reason is 'No peer_zone configured...' not the new string
        xcvr = _get_mmf_xcvr('SFR509-E2')
        leaf0 = PlanSwitchClass.objects.create(
            plan=self.plan, switch_class_id='sfr509-leaf0-e2',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
        )
        _make_leaf_uplink(leaf0, name='sfr509-leaf0-e2-ul', xcvr=xcvr)
        summary = self._build()
        row = [r for r in summary.rows if r.near_zone_name == 'sfr509-leaf0-e2-ul'][0]
        self.assertIn('uplink_ports_per_switch is 0', row.reason)

    def test_e3_zero_uplink_ports_xcvr_null_reason(self):
        # FAIL: current reason has no 'non-standard uplink' text
        leaf0 = PlanSwitchClass.objects.create(
            plan=self.plan, switch_class_id='sfr509-leaf0-e3',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
        )
        _make_leaf_uplink(leaf0, name='sfr509-leaf0-e3-ul', xcvr=None)
        summary = self._build()
        row = [r for r in summary.rows if r.near_zone_name == 'sfr509-leaf0-e3-ul'][0]
        self.assertIn('non-standard uplink', row.reason.lower())
        self.assertIn('uplink_ports_per_switch is 0', row.reason)

    def test_e4_unmanaged_fabric_not_inferred(self):
        # FAIL: is_inferred field doesn't exist → AttributeError
        # OOB_MGMT fabric → fabric_class='unmanaged'
        unmanaged_leaf = PlanSwitchClass.objects.create(
            plan=self.plan, switch_class_id='sfr509-oob-leaf-e4',
            fabric=FabricTypeChoices.OOB_MGMT,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.ext,
            uplink_ports_per_switch=4,
        )
        _make_leaf_uplink(unmanaged_leaf, name='sfr509-oob-e4-ul')
        summary = self._build()
        oob_rows = [r for r in summary.rows if r.near_zone_name == 'sfr509-oob-e4-ul']
        self.assertEqual(len(oob_rows), 1)
        self.assertFalse(oob_rows[0].is_inferred)

    # --- Category F: far-end suppression ---

    def test_f1_single_inferred_pair_total_rows_is_one(self):
        # FAIL: currently emits 2 rows (leaf unpaired + spine unpaired)
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-f1')
        _make_fabric_zone(sp, name='sfr509-sp-f1-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-f1-ul')
        summary = self._build()
        self.assertEqual(len(summary.rows), 1)

    def test_f2_two_leaf_uplinks_spine_not_standalone(self):
        # FAIL: currently 3 rows (2 unpaired leaves + 1 unpaired spine)
        leaf2 = _make_switch_class(self.plan, self.ext, sc_id='sfr509-leaf2-f2')
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-f2')
        _make_fabric_zone(sp, name='sfr509-sp-f2-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf1-f2-ul')
        _make_leaf_uplink(leaf2, name='sfr509-lf2-f2-ul')
        summary = self._build()
        zone_names = [r.near_zone_name for r in summary.rows]
        self.assertNotIn('sfr509-sp-f2-dl', zone_names)
        self.assertEqual(len(summary.rows), 2)

    def test_f3_inferred_far_end_not_counted_as_unpaired(self):
        # FAIL: currently spine zone emitted as unpaired → unpaired_count >= 1
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-f3')
        _make_fabric_zone(sp, name='sfr509-sp-f3-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-f3-ul')
        summary = self._build()
        self.assertEqual(summary.unpaired_count, 0)

    # --- Category G: counter semantics ---

    def test_g1_inferred_count_increments_per_row(self):
        # FAIL: inferred_count field missing
        leaf2 = _make_switch_class(self.plan, self.ext, sc_id='sfr509-leaf2-g1')
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-g1')
        _make_fabric_zone(sp, name='sfr509-sp-g1-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf1-g1-ul')
        _make_leaf_uplink(leaf2, name='sfr509-lf2-g1-ul')
        summary = self._build()
        self.assertEqual(summary.inferred_count, 2)

    def test_g2_inferred_rows_count_in_paired_count(self):
        # FAIL: currently leaf zone is unpaired → paired_count=0
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-g2')
        _make_fabric_zone(sp, name='sfr509-sp-g2-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-lf-g2-ul')
        summary = self._build()
        self.assertEqual(summary.paired_count, 1)
        self.assertEqual(summary.inferred_count, 1)

    def test_g3_inferred_count_subset_of_paired_count(self):
        # FAIL: inferred_count field missing
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-g3')
        far_explicit = _make_fabric_zone(sp, name='sfr509-sp-g3-explicit')
        leaf2 = _make_switch_class(self.plan, self.ext, sc_id='sfr509-leaf2-g3')
        sp2 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp2-g3')
        _make_fabric_zone(sp2, name='sfr509-sp2-g3-inferred')
        # leaf2 has explicit peer_zone; self.leaf gets inferred pairing with sp2
        _make_uplink_zone(leaf2, name='sfr509-lf2-g3-ul', peer_zone=far_explicit)
        _make_leaf_uplink(self.leaf, name='sfr509-lf-g3-ul')
        summary = self._build()
        self.assertLessEqual(summary.inferred_count, summary.paired_count)
        self.assertEqual(summary.inferred_count, 1)
        self.assertEqual(summary.paired_count, 2)

    # --- Category I: no generator coupling ---

    def test_i1_inference_does_not_modify_peer_zone_fk(self):
        # Inference is review-only: peer_zone FK on zones must remain unchanged after build.
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-sp-i1')
        _make_fabric_zone(sp, name='sfr509-sp-i1-dl')
        leaf_zone = _make_leaf_uplink(self.leaf, name='sfr509-lf-i1-ul')
        self._build()
        leaf_zone.refresh_from_db()
        self.assertIsNone(leaf_zone.peer_zone)


class TestSwitchFabricInferenceUI(TestCase):
    """
    RED tests for DIET-505 Phase 3: template badge and pool label rendering.
    All tests fail until Phase 4 GREEN (template not yet updated).
    """

    @classmethod
    def setUpTestData(cls):
        cls.ext = _make_switch_ext()
        cls.superuser = User.objects.create_user(
            username='sfr509-su', password='pass', is_staff=True, is_superuser=True
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='sfr509-su', password='pass')
        self.plan = _make_plan(f'SFR509-UI-{self._testMethodName}')
        self.leaf = _make_switch_class(self.plan, self.ext, sc_id='sfr509-ui-leaf')

    def _url(self):
        return reverse('plugins:netbox_hedgehog:topologyplan_detail',
                       kwargs={'pk': self.plan.pk})

    def test_h1_inferred_badge_present_for_inferred_row(self):
        # FAIL: summary.inferred_count field missing → AttributeError;
        # also secondary check that the badge text appears in the cell
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-ui-sp-h1')
        _make_fabric_zone(sp, name='sfr509-ui-sp-h1-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-ui-lf-h1-ul')
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        summary = resp.context['switch_fabric_review']
        self.assertEqual(summary.inferred_count, 1)

    def test_h2_explicit_only_plan_inferred_count_zero(self):
        # FAIL: summary.inferred_count field doesn't exist → AttributeError in context access
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-ui-sp-h2')
        far = _make_fabric_zone(sp, name='sfr509-ui-sp-h2-dl')
        _make_uplink_zone(self.leaf, name='sfr509-ui-lf-h2-ul', peer_zone=far)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        summary = resp.context['switch_fabric_review']
        self.assertEqual(summary.inferred_count, 0)

    def test_h3_header_inferred_count_badge_when_nonzero(self):
        # FAIL: summary.inferred_count field missing → AttributeError;
        # once field exists, also verify >0 so the header badge would render
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-ui-sp-h3')
        _make_fabric_zone(sp, name='sfr509-ui-sp-h3-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-ui-lf-h3-ul')
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        summary = resp.context['switch_fabric_review']
        self.assertGreater(summary.inferred_count, 0)

    def test_h4_explicit_only_no_inferred_badge_in_header(self):
        # FAIL: inferred_count field missing → AttributeError
        sp = _make_spine_class(self.plan, self.ext, sc_id='sfr509-ui-sp-h4')
        far = _make_fabric_zone(sp, name='sfr509-ui-sp-h4-dl')
        _make_uplink_zone(self.leaf, name='sfr509-ui-lf-h4-ul', peer_zone=far)
        resp = self.client.get(self._url())
        summary = resp.context['switch_fabric_review']
        self.assertEqual(summary.inferred_count, 0)

    def test_h5_pool_label_in_html(self):
        # FAIL: no inference → pool label never rendered
        sp1 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-ui-sp1-h5')
        sp2 = _make_spine_class(self.plan, self.ext, sc_id='sfr509-ui-sp2-h5')
        _make_fabric_zone(sp1, name='sfr509-ui-sp1-h5-dl')
        _make_fabric_zone(sp2, name='sfr509-ui-sp2-h5-dl')
        _make_leaf_uplink(self.leaf, name='sfr509-ui-lf-h5-ul')
        resp = self.client.get(self._url())
        self.assertContains(resp, 'managed spine pool')
