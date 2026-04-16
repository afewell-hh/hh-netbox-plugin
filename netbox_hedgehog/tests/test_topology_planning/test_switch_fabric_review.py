"""
RED tests for DIET-460: Switch-Fabric Link Review service and plan detail panel.

Tests reference build_switch_fabric_review() and SwitchFabricReviewSummary
from services/switch_fabric_review.py which does not exist yet.
All tests must fail until Phase 4 GREEN.

Acceptance cases from #461 spec:
  SFR-1  through SFR-14
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

    # SFR-1: paired zone (peer_zone set), both xcvr null → match R_NULL
    def test_sfr1_paired_both_null_is_match(self):
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine')
        far = _make_uplink_zone(sw2, name='sfr-spine-dl', zone_type=PortZoneTypeChoices.FABRIC)
        near = _make_uplink_zone(self.sw, name='sfr-leaf-ul', peer_zone=far)
        summary = self._build()
        paired = [r for r in summary.rows if r.is_paired]
        self.assertEqual(len(paired), 1)
        self.assertEqual(paired[0].outcome, 'match')

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

    # SFR-4: paired, near xcvr set, far null → needs_review
    def test_sfr4_paired_one_null_is_needs_review(self):
        xcvr = _get_mmf_xcvr('SFR-ASYM-4')
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine-4')
        far = _make_uplink_zone(sw2, name='sfr-sp4-dl',
                                zone_type=PortZoneTypeChoices.FABRIC, xcvr=None)
        near = _make_uplink_zone(self.sw, name='sfr-lf4-ul', xcvr=xcvr, peer_zone=far)
        summary = self._build()
        paired = [r for r in summary.rows if r.is_paired]
        self.assertEqual(paired[0].outcome, 'needs_review')

    # SFR-5: UPLINK zone, no peer_zone → unpaired row, outcome None
    def test_sfr5_unpaired_uplink_zone_has_none_outcome(self):
        _make_uplink_zone(self.sw, name='sfr-unpaired', zone_type=PortZoneTypeChoices.UPLINK)
        summary = self._build()
        unpaired = [r for r in summary.rows if not r.is_paired]
        self.assertEqual(len(unpaired), 1)
        self.assertIsNone(unpaired[0].outcome)
        self.assertIn('peer_zone', unpaired[0].reason.lower())

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

    # near_xcvr_label is '—' when null
    def test_near_xcvr_label_dash_when_null(self):
        _make_uplink_zone(self.sw, name='sfr-null-ul',
                          zone_type=PortZoneTypeChoices.UPLINK, xcvr=None)
        summary = self._build()
        self.assertEqual(summary.rows[0].near_xcvr_label, '—')

    # Summary counters (paired/unpaired/match/needs_review/blocked)
    def test_summary_counters_are_consistent(self):
        sw2 = _make_switch_class(self.plan, self.ext, sc_id='sfr-spine-cnt')
        far = _make_uplink_zone(sw2, name='sfr-far-cnt', zone_type=PortZoneTypeChoices.FABRIC)
        _make_uplink_zone(self.sw, name='sfr-near-cnt', peer_zone=far)
        _make_uplink_zone(self.sw, name='sfr-unp-cnt', zone_type=PortZoneTypeChoices.UPLINK)
        summary = self._build()
        self.assertEqual(summary.paired_count + summary.unpaired_count, len(summary.rows))
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
