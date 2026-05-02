"""
RED tests for DIET-460: Server-Link Review service and plan detail panel.

Tests reference build_server_link_review() and ServerLinkReviewSummary which
do not exist yet. All tests in this file must fail until Phase 4 GREEN
implements the service and updates the template.

Acceptance cases from #461 spec:
  SLR-1  through SLR-13
  PERM-1 through PERM-4 (server-link angle)
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from dcim.models import DeviceType, Manufacturer
from users.models import ObjectPermission

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
from netbox_hedgehog.tests.test_topology_planning import (
    get_test_server_nic,
    get_test_transceiver_module_type,
    get_test_transceiver_module_type_osfp,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_fixtures():
    mfr, _ = Manufacturer.objects.get_or_create(
        name='SLR-Vendor', defaults={'slug': 'slr-vendor'}
    )
    dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='SLR-Switch', defaults={'slug': 'slr-switch'}
    )
    ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=dt,
        defaults={
            'native_speed': 800,
            'supported_breakouts': ['1x800g', '4x200g'],
            'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    bo_1x, _ = BreakoutOption.objects.get_or_create(
        breakout_id='slr-1x800g',
        defaults={'from_speed': 800, 'logical_ports': 1, 'logical_speed': 800},
    )
    bo_4x, _ = BreakoutOption.objects.get_or_create(
        breakout_id='slr-4x200g',
        defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200},
    )
    srv_mfr, _ = Manufacturer.objects.get_or_create(
        name='SLR-SrvVendor', defaults={'slug': 'slr-srvvendor'}
    )
    srv_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=srv_mfr, model='SLR-Server', defaults={'slug': 'slr-server'}
    )
    return mfr, dt, ext, bo_1x, bo_4x, srv_dt


def _make_plan(name='SLR-Plan'):
    return TopologyPlan.objects.create(
        name=name, status=TopologyPlanStatusChoices.DRAFT
    )


def _make_switch_class(plan, ext):
    return PlanSwitchClass.objects.create(
        plan=plan,
        switch_class_id='slr-fe-leaf',
        fabric=FabricTypeChoices.FRONTEND,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=ext,
        uplink_ports_per_switch=4,
    )


def _make_server_class(plan, srv_dt, qty=2, sc_id='slr-gpu'):
    return PlanServerClass.objects.create(
        plan=plan, server_class_id=sc_id,
        category=ServerClassCategoryChoices.GPU,
        quantity=qty, gpus_per_server=8, server_device_type=srv_dt,
    )


def _make_zone(switch_class, bo, name='slr-zone', xcvr=None,
               zone_type=PortZoneTypeChoices.SERVER):
    return SwitchPortZone.objects.create(
        switch_class=switch_class,
        zone_name=name,
        zone_type=zone_type,
        port_spec='1-48',
        breakout_option=bo,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
        priority=100,
        transceiver_module_type=xcvr,
    )


def _make_connection(sc, zone, nic_id='nic-slr', xcvr=None,
                     speed=200, conn_id='SLR-001', port_index=0):
    nic = get_test_server_nic(sc, nic_id=nic_id)
    return PlanServerConnection.objects.create(
        server_class=sc,
        connection_id=conn_id,
        nic=nic,
        port_index=port_index,
        target_zone=zone,
        ports_per_connection=2,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        speed=speed,
        port_type='data',
        transceiver_module_type=xcvr,
    )


def _get_smf_xcvr():
    """Return (or create) a Network Transceiver ModuleType with SMF medium."""
    from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile
    mfr, _ = Manufacturer.objects.get_or_create(
        name='SLR-SMF-Vendor', defaults={'slug': 'slr-smf-vendor'}
    )
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr,
        model='XCVR-QSFP112-SMF-SLR',
        defaults={
            'profile': profile,
            'description': 'SLR 200G SMF QSFP112 DR4',
            'attribute_data': {
                'cage_type': 'QSFP112',
                'medium': 'SMF',
                'connector': 'MPO-12',
                'standard': '200GBASE-DR4',
                'reach_class': 'DR',
            },
        },
    )
    return mt


def _get_approved_asymmetric_server_xcvr():
    """QSFP112 200G with MPO-12 — server (host) side of the approved asymmetric pair.

    The compat registry defines the pair as (switch=OSFP/Dual MPO-12/2x400g,
    server=QSFP112/MPO-12).  The server plugs into the QSFP112 end of the
    Y-splitter harness.
    """
    from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile
    mfr, _ = Manufacturer.objects.get_or_create(
        name='SLR-Asym-Vendor', defaults={'slug': 'slr-asym-vendor'}
    )
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr,
        model='XCVR-QSFP112-200G-SLR-SRV',
        defaults={
            'profile': profile,
            'description': 'SLR 200G QSFP112 SR2',
            'attribute_data': {
                'cage_type': 'QSFP112',
                'medium': 'MMF',
                'connector': 'MPO-12',
                'standard': '200GBASE-SR2',
            },
        },
    )
    return mt


def _get_approved_asymmetric_zone_xcvr():
    """OSFP 800G with Dual MPO-12 — switch (zone) side of the approved asymmetric pair.

    The compat registry defines the pair as (switch=OSFP/Dual MPO-12/2x400g,
    server=QSFP112/MPO-12).  The switch-side OSFP drives a Y-splitter harness.
    Requires breakout_topology='2x400g' in attribute_data for the rule engine.
    """
    from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile
    mfr, _ = Manufacturer.objects.get_or_create(
        name='SLR-Asym-Vendor', defaults={'slug': 'slr-asym-vendor'}
    )
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr,
        model='XCVR-OSFP-800G-SLR-SW',
        defaults={
            'profile': profile,
            'description': 'SLR 800G OSFP 2xVR4',
            'attribute_data': {
                'cage_type': 'OSFP',
                'medium': 'MMF',
                'connector': 'Dual MPO-12',
                'standard': '800GBASE-2xVR4',
                'breakout_topology': '2x400g',
            },
        },
    )
    return mt


# ---------------------------------------------------------------------------
# Unit tests for build_server_link_review()
# ---------------------------------------------------------------------------

class TestServerLinkReviewService(TestCase):

    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext, cls.bo_1x, cls.bo_4x, cls.srv_dt = _make_fixtures()

    def setUp(self):
        self.plan = _make_plan()
        self.sw = _make_switch_class(self.plan, self.ext)
        self.sc = _make_server_class(self.plan, self.srv_dt)

    def _build(self):
        # RED: build_server_link_review does not exist yet
        from netbox_hedgehog.services.connection_review import build_server_link_review
        return build_server_link_review(self.plan)

    # SLR-1: DIET-466: both null → blocked (transceiver required)
    def test_slr1_both_null_with_breakout_is_match(self):
        zone = _make_zone(self.sw, self.bo_1x)
        _make_connection(self.sc, zone, speed=800)
        summary = self._build()
        self.assertEqual(len(summary.rows), 1)
        self.assertEqual(summary.rows[0].outcome, 'match')

    # SLR-2: both null, NO breakout → blocked
    def test_slr2_no_breakout_is_blocked(self):
        zone = SwitchPortZone.objects.create(
            switch_class=self.sw, zone_name='slr-nob',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-4', breakout_option=None,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )
        _make_connection(self.sc, zone)
        summary = self._build()
        self.assertEqual(summary.rows[0].outcome, 'blocked')
        self.assertIn('breakout', summary.rows[0].reason.lower())

    # SLR-3: both set, matching attrs → match
    def test_slr3_matching_transceivers_is_match(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, xcvr=xcvr)
        _make_connection(self.sc, zone, xcvr=xcvr)
        summary = self._build()
        self.assertEqual(summary.rows[0].outcome, 'match')

    # SLR-4: medium mismatch (MMF server, SMF zone) → blocked
    def test_slr4_medium_mismatch_is_blocked(self):
        mmf_xcvr = get_test_transceiver_module_type()   # MMF
        smf_xcvr = _get_smf_xcvr()                       # SMF
        zone = _make_zone(self.sw, self.bo_4x, xcvr=smf_xcvr)
        _make_connection(self.sc, zone, xcvr=mmf_xcvr)
        summary = self._build()
        self.assertEqual(summary.rows[0].outcome, 'blocked')

    # SLR-5: conn xcvr set, zone null → needs_review (intent asymmetry)
    def test_slr5_conn_xcvr_zone_null_is_needs_review(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, xcvr=None)
        _make_connection(self.sc, zone, xcvr=xcvr)
        summary = self._build()
        self.assertEqual(summary.rows[0].outcome, 'needs_review')

    # SLR-6: approved asymmetric pair → match
    def test_slr6_approved_asymmetric_pair_is_match(self):
        srv_xcvr = _get_approved_asymmetric_server_xcvr()   # OSFP / Dual MPO-12
        zone_xcvr = _get_approved_asymmetric_zone_xcvr()    # QSFP112 / MPO-12
        bo_2x, _ = BreakoutOption.objects.get_or_create(
            breakout_id='slr-2x400g',
            defaults={'from_speed': 800, 'logical_ports': 2, 'logical_speed': 400},
        )
        zone = _make_zone(self.sw, bo_2x, name='slr-asym-zone', xcvr=zone_xcvr)
        _make_connection(self.sc, zone, xcvr=srv_xcvr, speed=400)
        summary = self._build()
        self.assertEqual(summary.rows[0].outcome, 'match')

    # SLR-7: cage mismatch, not approved → needs_review
    def test_slr7_cage_mismatch_not_approved_is_needs_review(self):
        mmf_xcvr = get_test_transceiver_module_type()       # QSFP112 / MMF
        osfp_xcvr = get_test_transceiver_module_type_osfp() # OSFP / MMF (different cage)
        zone = _make_zone(self.sw, self.bo_4x, xcvr=osfp_xcvr)
        _make_connection(self.sc, zone, xcvr=mmf_xcvr)      # QSFP112 ↔ OSFP, not approved
        summary = self._build()
        self.assertEqual(summary.rows[0].outcome, 'needs_review')

    # SLR-8: both null, 4x breakout → needs_review (splitter advisory)
    def test_slr8_breakout_no_xcvr_is_needs_review(self):
        zone = _make_zone(self.sw, self.bo_4x, xcvr=None)   # logical_ports=4
        _make_connection(self.sc, zone, xcvr=None)
        summary = self._build()
        self.assertEqual(summary.rows[0].outcome, 'needs_review')
        self.assertIn('breakout', summary.rows[0].reason.lower())

    # SLR-9: two connections targeting same zone → two rows, same edit_zone_url
    def test_slr9_two_connections_same_zone_give_two_rows(self):
        zone = _make_zone(self.sw, self.bo_4x, name='slr-shared-zone')
        _make_connection(self.sc, zone, nic_id='nic-a', conn_id='SLR-A', port_index=0)
        _make_connection(self.sc, zone, nic_id='nic-b', conn_id='SLR-B', port_index=1)
        summary = self._build()
        self.assertEqual(len(summary.rows), 2)
        urls = [r.edit_zone_url for r in summary.rows]
        self.assertEqual(urls[0], urls[1], 'Both rows must link to the same zone edit URL')
        conn_urls = [r.edit_connection_url for r in summary.rows]
        self.assertNotEqual(conn_urls[0], conn_urls[1], 'Each row must have its own connection edit URL')

    # SLR-10: edit_connection_url resolves to planserverconnection_edit
    def test_slr10_edit_connection_url_is_connection_edit(self):
        zone = _make_zone(self.sw, self.bo_1x)
        conn = _make_connection(self.sc, zone, speed=800)
        summary = self._build()
        expected = reverse('plugins:netbox_hedgehog:planserverconnection_edit', args=[conn.pk])
        self.assertEqual(summary.rows[0].edit_connection_url, expected)

    # SLR-11: edit_zone_url resolves to switchportzone_edit
    def test_slr11_edit_zone_url_is_zone_edit(self):
        zone = _make_zone(self.sw, self.bo_1x)
        _make_connection(self.sc, zone, speed=800)
        summary = self._build()
        expected = reverse('plugins:netbox_hedgehog:switchportzone_edit', args=[zone.pk])
        self.assertEqual(summary.rows[0].edit_zone_url, expected)

    # Row field contracts
    def test_row_physical_count_equals_qty_times_ppc(self):
        sc4 = _make_server_class(self.plan, self.srv_dt, qty=4, sc_id='slr-count')
        zone = _make_zone(self.sw, self.bo_4x, name='slr-cnt-zone')
        _make_connection(sc4, zone, nic_id='nic-cnt', conn_id='SLR-CNT')
        summary = self._build()
        # qty=4, ports_per_connection=2 → physical_count=8
        self.assertEqual(summary.rows[0].physical_count, 8)

    def test_row_xcvr_labels_show_description_and_model(self):
        """server_xcvr_label and zone_xcvr_label use description+model format."""
        from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile
        mfr, _ = Manufacturer.objects.get_or_create(
            name='SLR-Desc-Vendor', defaults={'slug': 'slr-desc-vendor'}
        )
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        xcvr, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='SLR-XCVR-DESC',
            defaults={
                'profile': profile,
                'description': 'SLR 200G Test Optic',
                'attribute_data': {'cage_type': 'QSFP112', 'medium': 'MMF'},
            },
        )
        zone = _make_zone(self.sw, self.bo_4x, xcvr=xcvr)
        _make_connection(self.sc, zone, xcvr=xcvr)
        summary = self._build()
        row = summary.rows[0]
        self.assertIn('SLR 200G Test Optic', row.server_xcvr_label)
        self.assertIn('SLR-XCVR-DESC', row.server_xcvr_label)
        self.assertIn('SLR 200G Test Optic', row.zone_xcvr_label)

    def test_row_xcvr_labels_dash_when_null(self):
        """Null xcvr label is '—' (neutral, not alarming)."""
        zone = _make_zone(self.sw, self.bo_1x, xcvr=None)
        _make_connection(self.sc, zone, xcvr=None, speed=800)
        summary = self._build()
        self.assertEqual(summary.rows[0].server_xcvr_label, '—')
        self.assertEqual(summary.rows[0].zone_xcvr_label, '—')

    def test_summary_totals_are_consistent(self):
        zone = _make_zone(self.sw, self.bo_4x)
        _make_connection(self.sc, zone, nic_id='nic-tot-1', conn_id='SLR-T1')
        _make_connection(self.sc, zone, nic_id='nic-tot-2', conn_id='SLR-T2', port_index=1)
        summary = self._build()
        self.assertEqual(
            summary.match_count + summary.needs_review_count + summary.blocked_count,
            len(summary.rows),
        )

    def test_rows_sorted_by_speed_desc_then_conn_type(self):
        zone_800 = _make_zone(self.sw, self.bo_1x, name='slr-z800')
        zone_200 = _make_zone(self.sw, self.bo_4x, name='slr-z200')
        _make_connection(self.sc, zone_200, nic_id='nic-200', conn_id='SLR-200', speed=200)
        _make_connection(self.sc, zone_800, nic_id='nic-800', conn_id='SLR-800',
                         speed=800, port_index=1)
        summary = self._build()
        speeds = [r.speed for r in summary.rows]
        self.assertEqual(speeds, sorted(speeds, reverse=True))

    def test_empty_plan_returns_empty_summary(self):
        summary = self._build()
        self.assertEqual(summary.rows, [])
        self.assertEqual(summary.total_connections, 0)


# ---------------------------------------------------------------------------
# Integration tests: plan detail renders Server-Link Review panel
# ---------------------------------------------------------------------------

class TestServerLinkReviewIntegration(TestCase):

    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext, cls.bo_1x, cls.bo_4x, cls.srv_dt = _make_fixtures()
        cls.superuser = User.objects.create_user(
            username='slr-su', password='pass', is_staff=True, is_superuser=True
        )
        cls.plain = User.objects.create_user(
            username='slr-plain', password='pass', is_staff=True
        )
        # viewer has plan view ObjectPermission
        cls.viewer = User.objects.create_user(
            username='slr-viewer', password='pass', is_staff=True
        )
        from django.contrib.auth.models import Permission
        perm = Permission.objects.get(
            content_type__app_label='netbox_hedgehog',
            codename='view_topologyplan',
        )
        cls.viewer.user_permissions.add(perm)
        obj_perm = ObjectPermission.objects.create(
            name='slr-viewer-plan', actions=['view']
        )
        obj_perm.object_types.add(ContentType.objects.get_for_model(TopologyPlan))
        obj_perm.users.add(cls.viewer)

    def setUp(self):
        self.client = Client()
        self.client.login(username='slr-su', password='pass')
        self.plan = _make_plan(name='SLR-View-Plan')
        self.sw = _make_switch_class(self.plan, self.ext)
        self.sc = _make_server_class(self.plan, self.srv_dt)

    def _url(self):
        return reverse('plugins:netbox_hedgehog:topologyplan_detail',
                       kwargs={'pk': self.plan.pk})

    # SLR-12: plan detail renders "Server-Link Review" heading
    def test_slr12_server_link_review_panel_present(self):
        zone = _make_zone(self.sw, self.bo_4x)
        _make_connection(self.sc, zone)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Server-Link Review')

    # SLR-12: context key server_link_review is present
    def test_slr12_context_has_server_link_review_key(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('server_link_review', resp.context)

    # SLR-13: empty plan shows empty-state text
    def test_slr13_empty_state_text_shown(self):
        resp = self.client.get(self._url())
        self.assertContains(resp, 'No server connections defined yet')

    # Rendered columns: server_class_id, connection_id, speed, zone xcvr label
    def test_rendered_row_shows_server_class_and_connection_ids(self):
        zone = _make_zone(self.sw, self.bo_1x)
        _make_connection(self.sc, zone, conn_id='SLR-HTML-001', speed=800)
        resp = self.client.get(self._url())
        self.assertContains(resp, 'slr-gpu')        # server_class_id
        self.assertContains(resp, 'SLR-HTML-001')   # connection_id

    def test_rendered_row_shows_zone_xcvr_label_with_description(self):
        from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile
        mfr, _ = Manufacturer.objects.get_or_create(
            name='SLR-HTML-Vendor', defaults={'slug': 'slr-html-vendor'}
        )
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        xcvr, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='SLR-HTML-XCVR',
            defaults={
                'profile': profile,
                'description': 'SLR 200G HTML Label Optic',
                'attribute_data': {'cage_type': 'QSFP112', 'medium': 'MMF'},
            },
        )
        zone = _make_zone(self.sw, self.bo_4x, xcvr=xcvr)
        _make_connection(self.sc, zone, xcvr=xcvr)
        resp = self.client.get(self._url())
        self.assertContains(resp, 'SLR 200G HTML Label Optic')

    def test_rendered_row_shows_edit_connection_link(self):
        zone = _make_zone(self.sw, self.bo_1x)
        conn = _make_connection(self.sc, zone, speed=800)
        expected_url = reverse('plugins:netbox_hedgehog:planserverconnection_edit',
                                args=[conn.pk])
        resp = self.client.get(self._url())
        self.assertContains(resp, expected_url)

    def test_rendered_row_shows_edit_zone_link(self):
        zone = _make_zone(self.sw, self.bo_1x, name='slr-zone-link')
        _make_connection(self.sc, zone, speed=800)
        expected_url = reverse('plugins:netbox_hedgehog:switchportzone_edit',
                                args=[zone.pk])
        resp = self.client.get(self._url())
        self.assertContains(resp, expected_url)

    def test_match_row_has_success_class(self):
        """DIET-466: both xcvr set and matching → 'match' → table-success row class."""
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_1x, name='slr-match-row', xcvr=xcvr)
        _make_connection(self.sc, zone, speed=800, xcvr=xcvr)
        resp = self.client.get(self._url())
        self.assertContains(resp, 'table-success')

    def test_blocked_row_has_danger_class(self):
        zone = SwitchPortZone.objects.create(
            switch_class=self.sw, zone_name='slr-blocked-html',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-4',
            breakout_option=None,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )
        _make_connection(self.sc, zone)
        resp = self.client.get(self._url())
        self.assertContains(resp, 'table-danger')

    # PERM-1: viewer sees the panel
    def test_perm1_viewer_sees_server_link_review(self):
        zone = _make_zone(self.sw, self.bo_4x)
        _make_connection(self.sc, zone)
        self.client.login(username='slr-viewer', password='pass')
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('server_link_review', resp.context)

    # PERM-2: edit connection view returns 403 without change perm
    def test_perm2_edit_connection_without_perm_is_403(self):
        zone = _make_zone(self.sw, self.bo_4x)
        conn = _make_connection(self.sc, zone)
        self.client.login(username='slr-viewer', password='pass')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_edit', args=[conn.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    # PERM-3: edit zone view returns 403 without change perm
    def test_perm3_edit_zone_without_perm_is_403(self):
        zone = _make_zone(self.sw, self.bo_4x)
        self.client.login(username='slr-viewer', password='pass')
        url = reverse('plugins:netbox_hedgehog:switchportzone_edit', args=[zone.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    # PERM-4: unauthenticated redirects
    def test_perm4_unauthenticated_redirects(self):
        anon = Client()
        resp = anon.get(self._url())
        self.assertIn(resp.status_code, [302, 403])

    # existing connection_review summary function must still work (no removal)
    def test_legacy_connection_review_context_still_present(self):
        zone = _make_zone(self.sw, self.bo_4x)
        _make_connection(self.sc, zone)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        # Deprecated function is retained; its context key may or may not still be
        # passed. If it is, it should not cause an error. This is a smoke test.
