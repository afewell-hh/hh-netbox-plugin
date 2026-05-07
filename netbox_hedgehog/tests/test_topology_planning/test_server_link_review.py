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
                     speed=200, conn_id='SLR-001', port_index=0,
                     ports_per_connection=2):
    nic = get_test_server_nic(sc, nic_id=nic_id)
    return PlanServerConnection.objects.create(
        server_class=sc,
        connection_id=conn_id,
        nic=nic,
        port_index=port_index,
        target_zone=zone,
        ports_per_connection=ports_per_connection,
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
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-cnt-zone', xcvr=xcvr)
        _make_connection(sc4, zone, nic_id='nic-cnt', conn_id='SLR-CNT', xcvr=xcvr)
        summary = self._build()
        # qty=4, ports_per_connection=2 → physical_count=8
        self.assertEqual(summary.rows[0].physical_count, 8)

    def test_row_server_transceiver_count_equals_qty_times_ppc_when_set(self):
        sc4 = _make_server_class(self.plan, self.srv_dt, qty=4, sc_id='slr-srv-qty')
        zone = _make_zone(self.sw, self.bo_4x, name='slr-srv-zone')
        xcvr = get_test_transceiver_module_type()
        _make_connection(sc4, zone, nic_id='nic-srv-qty', conn_id='SLR-SRV-QTY', xcvr=xcvr)
        summary = self._build()
        self.assertEqual(summary.rows[0].server_transceiver_count, 8)

    def test_row_server_transceiver_count_zero_when_unset(self):
        zone = _make_zone(self.sw, self.bo_1x, name='slr-srv-zero', xcvr=None)
        _make_connection(self.sc, zone, conn_id='SLR-SRV-ZERO', xcvr=None, speed=800)
        summary = self._build()
        self.assertEqual(summary.rows[0].server_transceiver_count, 0)

    # SLR-R1: zone_transceiver_count removed from ServerLinkRow (RED: field still exists)
    def test_row_has_no_zone_transceiver_count_attr(self):
        self.sw.override_quantity = 1
        self.sw.save(update_fields=['override_quantity'])
        sc4 = _make_server_class(self.plan, self.srv_dt, qty=4, sc_id='slr-zone-qty')
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-zone-qty-zone', xcvr=xcvr)
        _make_connection(sc4, zone, nic_id='nic-zone-qty', conn_id='SLR-ZONE-QTY', xcvr=xcvr)
        summary = self._build()
        self.assertEqual(summary.rows[0].physical_count, 8)
        # RED: field is removed in DIET-493 GREEN; still present now → assertFalse fails
        self.assertFalse(
            hasattr(summary.rows[0], 'zone_transceiver_count'),
            'zone_transceiver_count must be removed from ServerLinkRow per DIET-492 spec',
        )

    # zone_aggregates must carry the alternating-distribution counts instead (SLR-D2 scope)
    def test_row_physical_count_unaffected_by_alternating_distribution(self):
        self.sw.override_quantity = 4
        self.sw.save(update_fields=['override_quantity'])
        sc2 = _make_server_class(self.plan, self.srv_dt, qty=2, sc_id='slr-alt-zone')
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-alt-zone-qty', xcvr=xcvr)
        _make_connection(sc2, zone, nic_id='nic-alt-zone', conn_id='SLR-ALT-ZONE', xcvr=xcvr)
        summary = self._build()
        # physical_count is still qty*ppc = 2*2 = 4; that field is unchanged
        self.assertEqual(summary.rows[0].physical_count, 4)
        # zone_transceiver_count must be gone; switch-side optics live in zone_aggregates
        self.assertFalse(hasattr(summary.rows[0], 'zone_transceiver_count'))

    # zone with no xcvr → aggregate shows required_switch_optics=0 (not row field)
    def test_row_has_no_zone_transceiver_count_when_zone_xcvr_unset(self):
        zone = _make_zone(self.sw, self.bo_4x, name='slr-zone-zero', xcvr=None)
        _make_connection(self.sc, zone, conn_id='SLR-ZONE-ZERO', xcvr=get_test_transceiver_module_type())
        summary = self._build()
        self.assertFalse(hasattr(summary.rows[0], 'zone_transceiver_count'))

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

    # SLR-R2: Zone Qty column removed from row table; helper text added (RED: both still present)
    def test_rendered_table_has_no_zone_qty_header(self):
        zone = _make_zone(self.sw, self.bo_1x)
        _make_connection(self.sc, zone, speed=800)
        resp = self.client.get(self._url())
        self.assertContains(resp, '<th>Links</th>', html=True)
        self.assertContains(resp, '<th>Server Qty</th>', html=True)
        # RED: Zone Qty must be absent after GREEN removes it
        self.assertNotContains(resp, 'Zone Qty')
        # RED: helper text must appear below Server-Link Review heading
        self.assertContains(resp, 'Links and Server Qty are per-row totals')

    def test_rendered_review_table_uses_standard_table_styling(self):
        zone = _make_zone(self.sw, self.bo_1x)
        _make_connection(self.sc, zone, speed=800)
        resp = self.client.get(self._url())
        content = resp.content.decode()
        self.assertIn('<table class="table table-hover">', content)
        self.assertNotIn('table-sm', content)

    # SLR-R3: Zone Qty column absent; companion-card heading present after GREEN
    def test_rendered_row_shows_links_and_server_qty_without_zone_qty(self):
        self.sw.override_quantity = 1
        self.sw.save(update_fields=['override_quantity'])
        sc4 = _make_server_class(self.plan, self.srv_dt, qty=4, sc_id='slr-html-qty')
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-html-zone-qty', xcvr=xcvr)
        _make_connection(sc4, zone, nic_id='nic-html-qty', conn_id='SLR-HTML-QTY', xcvr=xcvr)
        resp = self.client.get(self._url())
        self.assertContains(resp, 'SLR-HTML-QTY')
        # RED: Zone Qty must be absent from row table after GREEN removes the column
        self.assertNotContains(resp, 'Zone Qty')
        # RED: companion card heading must be present after GREEN adds the card
        self.assertContains(resp, 'Switch Zone Optic Summary')

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
        """Matching rows use a success badge."""
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_1x, name='slr-match-row', xcvr=xcvr)
        _make_connection(self.sc, zone, speed=800, xcvr=xcvr)
        resp = self.client.get(self._url())
        self.assertContains(resp, '<span class="badge bg-success">match</span>', html=True)

    def test_blocked_row_has_danger_class(self):
        """Blocked rows use a danger badge."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.sw, zone_name='slr-blocked-html',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-4',
            breakout_option=None,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )
        _make_connection(self.sc, zone)
        resp = self.client.get(self._url())
        self.assertContains(resp, '<span class="badge bg-danger">blocked</span>', html=True)

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


# ---------------------------------------------------------------------------
# DIET-493 RED: ZoneOpticAggregate presence and fields (SLR-A1 through A8)
# ---------------------------------------------------------------------------

class TestZoneOpticAggregates(TestCase):

    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext, cls.bo_1x, cls.bo_4x, cls.srv_dt = _make_fixtures()

    def setUp(self):
        self.plan = _make_plan(name='SLR-AGG-Plan')
        self.sw = _make_switch_class(self.plan, self.ext)
        self.sw.override_quantity = 1
        self.sw.save(update_fields=['override_quantity'])
        self.sc = _make_server_class(self.plan, self.srv_dt, qty=1, sc_id='slr-agg-gpu')

    def _build(self):
        from netbox_hedgehog.services.connection_review import build_server_link_review
        return build_server_link_review(self.plan)

    # SLR-A1: empty plan → zone_aggregates == []
    def test_a1_empty_plan_zone_aggregates_empty(self):
        summary = self._build()
        self.assertTrue(
            hasattr(summary, 'zone_aggregates'),
            'ServerLinkReviewSummary must have zone_aggregates field',
        )
        self.assertEqual(summary.zone_aggregates, [])

    # SLR-A2: single connection → exactly 1 aggregate
    def test_a2_single_connection_yields_one_aggregate(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-a2-zone', xcvr=xcvr)
        _make_connection(self.sc, zone, nic_id='nic-a2', conn_id='SLR-A2')
        summary = self._build()
        self.assertEqual(len(summary.zone_aggregates), 1)

    # SLR-A3: aggregate zone_name matches zone
    def test_a3_aggregate_zone_name_matches(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-a3-zone', xcvr=xcvr)
        _make_connection(self.sc, zone, nic_id='nic-a3', conn_id='SLR-A3')
        summary = self._build()
        self.assertEqual(summary.zone_aggregates[0].zone_name, 'slr-a3-zone')

    # SLR-A4: aggregate breakout_id matches zone's breakout option
    def test_a4_aggregate_breakout_id_matches(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-a4-zone', xcvr=xcvr)
        _make_connection(self.sc, zone, nic_id='nic-a4', conn_id='SLR-A4')
        summary = self._build()
        self.assertEqual(summary.zone_aggregates[0].breakout_id, self.bo_4x.breakout_id)

    # SLR-A5: zone with no xcvr → xcvr_label='—', required_switch_optics=0
    def test_a5_zone_no_xcvr_shows_zero_optics_and_dash_label(self):
        zone = _make_zone(self.sw, self.bo_4x, name='slr-a5-zone', xcvr=None)
        _make_connection(self.sc, zone, nic_id='nic-a5', conn_id='SLR-A5')
        summary = self._build()
        agg = summary.zone_aggregates[0]
        self.assertEqual(agg.xcvr_label, '—')
        self.assertEqual(agg.required_switch_optics, 0)

    # SLR-A6: zone with xcvr → xcvr_label contains description and model
    def test_a6_aggregate_xcvr_label_contains_description_and_model(self):
        from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile
        mfr, _ = Manufacturer.objects.get_or_create(
            name='SLR-A6-Vendor', defaults={'slug': 'slr-a6-vendor'}
        )
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        xcvr, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='SLR-A6-XCVR',
            defaults={
                'profile': profile,
                'description': 'SLR A6 Test Optic',
                'attribute_data': {'cage_type': 'QSFP112', 'medium': 'MMF'},
            },
        )
        zone = _make_zone(self.sw, self.bo_4x, name='slr-a6-zone', xcvr=xcvr)
        _make_connection(self.sc, zone, nic_id='nic-a6', conn_id='SLR-A6')
        summary = self._build()
        label = summary.zone_aggregates[0].xcvr_label
        self.assertIn('SLR A6 Test Optic', label)
        self.assertIn('SLR-A6-XCVR', label)

    # SLR-A7: two zones → 2 aggregates sorted by zone_name ascending
    def test_a7_two_zones_two_aggregates_sorted_by_name(self):
        xcvr = get_test_transceiver_module_type()
        zone_b = _make_zone(self.sw, self.bo_4x, name='slr-a7-zone-b', xcvr=xcvr)
        zone_a = _make_zone(self.sw, self.bo_1x, name='slr-a7-zone-a', xcvr=xcvr)
        sc_b = _make_server_class(self.plan, self.srv_dt, qty=1, sc_id='slr-a7-b')
        sc_a = _make_server_class(self.plan, self.srv_dt, qty=1, sc_id='slr-a7-a')
        _make_connection(sc_b, zone_b, nic_id='nic-a7b', conn_id='SLR-A7B', speed=200)
        _make_connection(sc_a, zone_a, nic_id='nic-a7a', conn_id='SLR-A7A', speed=800, port_index=1)
        summary = self._build()
        self.assertEqual(len(summary.zone_aggregates), 2)
        names = [agg.zone_name for agg in summary.zone_aggregates]
        self.assertEqual(names, sorted(names))

    # SLR-A8: edit_zone_url resolves to switchportzone_edit
    def test_a8_aggregate_edit_zone_url_resolves(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-a8-zone', xcvr=xcvr)
        _make_connection(self.sc, zone, nic_id='nic-a8', conn_id='SLR-A8')
        summary = self._build()
        expected = reverse('plugins:netbox_hedgehog:switchportzone_edit', args=[zone.pk])
        self.assertEqual(summary.zone_aggregates[0].edit_zone_url, expected)


# ---------------------------------------------------------------------------
# DIET-493 RED: Core shared-zone correctness (SLR-S1 through S5)
# ---------------------------------------------------------------------------

class TestSharedZoneCorrectness(TestCase):
    """Canonical shared-zone optic aggregation scenarios."""

    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext, cls.bo_1x, cls.bo_4x, cls.srv_dt = _make_fixtures()

    def setUp(self):
        self.plan = _make_plan(name='SLR-SHZ-Plan')
        self.sw = _make_switch_class(self.plan, self.ext)
        self.sw.override_quantity = 1
        self.sw.save(update_fields=['override_quantity'])

    def _build(self):
        from netbox_hedgehog.services.connection_review import build_server_link_review
        return build_server_link_review(self.plan)

    # SLR-S1: 4 classes × qty=1 × ppc=1, same 4×200G zone, 1 switch → 1 switch optic
    def test_s1_four_classes_same_zone_one_switch_optic(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-s1-zone', xcvr=xcvr)
        for i in range(4):
            sc = _make_server_class(self.plan, self.srv_dt, qty=1, sc_id=f'slr-s1-cls{i}')
            _make_connection(sc, zone, nic_id=f'nic-s1-{i}', conn_id=f'SLR-S1-{i}', ports_per_connection=1)
        summary = self._build()
        agg = summary.zone_aggregates[0]
        self.assertEqual(agg.total_logical_links, 4)
        self.assertEqual(agg.required_switch_optics, 1)

    # SLR-S2: 3 classes × qty=1 × ppc=1 → 3 links < 4 logical_ports → still 1 optic
    def test_s2_three_classes_same_zone_one_switch_optic(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-s2-zone', xcvr=xcvr)
        for i in range(3):
            sc = _make_server_class(self.plan, self.srv_dt, qty=1, sc_id=f'slr-s2-cls{i}')
            _make_connection(sc, zone, nic_id=f'nic-s2-{i}', conn_id=f'SLR-S2-{i}', ports_per_connection=1)
        summary = self._build()
        agg = summary.zone_aggregates[0]
        self.assertEqual(agg.total_logical_links, 3)
        self.assertEqual(agg.required_switch_optics, 1)

    # SLR-S3: 1 class × qty=4 × ppc=2 → 8 links → ceil(8/4)=2 optics
    def test_s3_one_class_qty4_ppc2_two_optics(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-s3-zone', xcvr=xcvr)
        sc = _make_server_class(self.plan, self.srv_dt, qty=4, sc_id='slr-s3-cls')
        _make_connection(sc, zone, nic_id='nic-s3', conn_id='SLR-S3')
        summary = self._build()
        agg = summary.zone_aggregates[0]
        self.assertEqual(agg.total_logical_links, 8)
        self.assertEqual(agg.required_switch_optics, 2)

    # SLR-S4: 1 class × qty=1 × ppc=1 → 1 link → ceil(1/4)=1 optic (partial cage)
    def test_s4_one_link_partial_cage_still_one_optic(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-s4-zone', xcvr=xcvr)
        sc = _make_server_class(self.plan, self.srv_dt, qty=1, sc_id='slr-s4-cls')
        _make_connection(sc, zone, nic_id='nic-s4', conn_id='SLR-S4', ports_per_connection=1)
        summary = self._build()
        agg = summary.zone_aggregates[0]
        self.assertEqual(agg.total_logical_links, 1)
        self.assertEqual(agg.required_switch_optics, 1)

    # SLR-S5: two distinct zones → 2 aggregates, each computed independently
    def test_s5_two_zones_computed_independently(self):
        xcvr = get_test_transceiver_module_type()
        zone_a = _make_zone(self.sw, self.bo_4x, name='slr-s5-zone-a', xcvr=xcvr)
        zone_b = _make_zone(self.sw, self.bo_1x, name='slr-s5-zone-b', xcvr=xcvr)
        sc_a = _make_server_class(self.plan, self.srv_dt, qty=1, sc_id='slr-s5-a')
        sc_b = _make_server_class(self.plan, self.srv_dt, qty=1, sc_id='slr-s5-b')
        _make_connection(sc_a, zone_a, nic_id='nic-s5a', conn_id='SLR-S5A', speed=200, ports_per_connection=1)
        _make_connection(sc_b, zone_b, nic_id='nic-s5b', conn_id='SLR-S5B', speed=800, port_index=1, ports_per_connection=1)
        summary = self._build()
        self.assertEqual(len(summary.zone_aggregates), 2)
        aggs = {a.zone_name: a for a in summary.zone_aggregates}
        # zone_a: 1 link, 4x200G → ceil(1/4)=1
        self.assertEqual(aggs['slr-s5-zone-a'].required_switch_optics, 1)
        # zone_b: 1 link, 1x800G → ceil(1/1)=1
        self.assertEqual(aggs['slr-s5-zone-b'].required_switch_optics, 1)


# ---------------------------------------------------------------------------
# DIET-493 RED: Distribution-specific aggregation (SLR-D1 through D4)
# ---------------------------------------------------------------------------

class TestDistributionSpecificAggregation(TestCase):

    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext, cls.bo_1x, cls.bo_4x, cls.srv_dt = _make_fixtures()

    def setUp(self):
        self.plan = _make_plan(name='SLR-DIST-Plan')
        self.sw = _make_switch_class(self.plan, self.ext)

    def _build(self):
        from netbox_hedgehog.services.connection_review import build_server_link_review
        return build_server_link_review(self.plan)

    # SLR-D1: alternating, 4 switches, ppc=1
    # port_index=0 % 4 = 0 for all → all links on sw0 → ceil(4/4)=1 optic
    def test_d1_alternating_ppc1_four_switches_all_land_on_switch_zero(self):
        self.sw.override_quantity = 4
        self.sw.save(update_fields=['override_quantity'])
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-d1-zone', xcvr=xcvr)
        for i in range(4):
            sc = _make_server_class(self.plan, self.srv_dt, qty=1, sc_id=f'slr-d1-cls{i}')
            _make_connection(
                sc, zone, nic_id=f'nic-d1-{i}', conn_id=f'SLR-D1-{i}',
                xcvr=xcvr, ports_per_connection=1,
            )
        summary = self._build()
        agg = summary.zone_aggregates[0]
        self.assertEqual(agg.total_logical_links, 4)
        # All ppc=1 links have port_index=0 → 0%4=0; all on sw0 → 1 cage
        self.assertEqual(agg.required_switch_optics, 1)

    # SLR-D2: alternating, 2 switches, ppc=2
    # Each server: port0→sw0, port1→sw1 → each switch gets qty*1=2 links → ceil(2/4)*2=2 optics
    def test_d2_alternating_ppc2_two_switches_splits_links(self):
        self.sw.override_quantity = 2
        self.sw.save(update_fields=['override_quantity'])
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-d2-zone', xcvr=xcvr)
        sc = _make_server_class(self.plan, self.srv_dt, qty=2, sc_id='slr-d2-cls')
        _make_connection(sc, zone, nic_id='nic-d2', conn_id='SLR-D2', xcvr=xcvr)
        summary = self._build()
        agg = summary.zone_aggregates[0]
        self.assertEqual(agg.total_logical_links, 4)   # 2 servers × ppc=2
        # sw0 gets 2 links (port0 for each server), sw1 gets 2 links (port1 for each)
        # ceil(2/4) + ceil(2/4) = 1 + 1 = 2
        self.assertEqual(agg.required_switch_optics, 2)

    # SLR-D3: same-switch, 2 switches, qty=4
    # Servers evenly split: sw0 gets servers 0+1, sw1 gets servers 2+3 → 2 links each
    # ceil(2/4) + ceil(2/4) = 2 optics
    def test_d3_same_switch_two_switches_splits_servers(self):
        self.sw.override_quantity = 2
        self.sw.save(update_fields=['override_quantity'])
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-d3-zone', xcvr=xcvr)
        sc = _make_server_class(self.plan, self.srv_dt, qty=4, sc_id='slr-d3-cls')
        _make_connection(
            sc, zone, nic_id='nic-d3', conn_id='SLR-D3', xcvr=xcvr, ports_per_connection=1,
        )
        # Override distribution on the connection after creation
        from netbox_hedgehog.choices import ConnectionDistributionChoices
        from netbox_hedgehog.models.topology_planning import PlanServerConnection
        PlanServerConnection.objects.filter(connection_id='SLR-D3').update(
            distribution=ConnectionDistributionChoices.SAME_SWITCH
        )
        summary = self._build()
        agg = summary.zone_aggregates[0]
        self.assertEqual(agg.total_logical_links, 4)
        self.assertEqual(agg.required_switch_optics, 2)

    # SLR-D4: rail-optimized → no exception; required_switch_optics is non-negative
    def test_d4_rail_optimized_no_exception(self):
        self.sw.override_quantity = 2
        self.sw.save(update_fields=['override_quantity'])
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-d4-zone', xcvr=xcvr)
        sc = _make_server_class(self.plan, self.srv_dt, qty=2, sc_id='slr-d4-cls')
        from netbox_hedgehog.choices import ConnectionDistributionChoices
        from netbox_hedgehog.models.topology_planning import PlanServerNIC
        from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type
        nic_mt = get_test_nic_module_type()
        nic, _ = PlanServerNIC.objects.get_or_create(
            server_class=sc, nic_id='nic-d4',
            defaults={'module_type': nic_mt},
        )
        from netbox_hedgehog.models.topology_planning import PlanServerConnection
        PlanServerConnection.objects.create(
            server_class=sc,
            connection_id='SLR-D4',
            nic=nic,
            port_index=0,
            target_zone=zone,
            ports_per_connection=2,
            hedgehog_conn_type='unbundled',
            distribution=ConnectionDistributionChoices.RAIL_OPTIMIZED,
            speed=200,
            port_type='data',
            transceiver_module_type=xcvr,
            rail=0,
        )
        summary = self._build()
        self.assertEqual(len(summary.zone_aggregates), 1)
        self.assertGreaterEqual(summary.zone_aggregates[0].required_switch_optics, 0)


# ---------------------------------------------------------------------------
# DIET-493 RED: Canonical multi-class regression (SLR-C1, C2)
# Lightweight proxy for 128-GPU: 4 classes, shared 4×200G zone, 1 switch.
# ---------------------------------------------------------------------------

class TestCanonical128GPURegressionSLR(TestCase):
    """
    Regression guard using a minimal 4-class / shared-zone plan.

    Mirrors the structural invariant of the 128-GPU case (multiple server
    classes sharing one physical breakout cage per switch) without running the
    full generation pipeline.
    """

    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext, cls.bo_1x, cls.bo_4x, cls.srv_dt = _make_fixtures()
        cls.superuser = User.objects.create_user(
            username='slr-c-su', password='pass', is_staff=True, is_superuser=True
        )

    def _make_multiclass_plan(self, name='SLR-C-Plan'):
        plan = _make_plan(name=name)
        sw = _make_switch_class(plan, self.ext)
        sw.override_quantity = 1
        sw.save(update_fields=['override_quantity'])
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(sw, self.bo_4x, name='slr-c-shared-zone', xcvr=xcvr)
        for i in range(4):
            sc = _make_server_class(plan, self.srv_dt, qty=1, sc_id=f'slr-c-cls{i}')
            _make_connection(sc, zone, nic_id=f'nic-c-{i}', conn_id=f'SLR-C-{i}', xcvr=xcvr)
        return plan

    def _build(self, plan):
        from netbox_hedgehog.services.connection_review import build_server_link_review
        return build_server_link_review(plan)

    # SLR-C1: summary builds without error; zone_aggregates populated; no AttributeError
    def test_c1_multiclass_plan_zone_aggregates_nonempty(self):
        plan = self._make_multiclass_plan()
        summary = self._build(plan)
        # zone_aggregates must exist (RED: AttributeError if field absent)
        self.assertTrue(hasattr(summary, 'zone_aggregates'))
        self.assertGreater(len(summary.zone_aggregates), 0)
        for agg in summary.zone_aggregates:
            self.assertGreaterEqual(agg.required_switch_optics, 0)
        # row table must have NO zone_transceiver_count (field removal regression)
        for row in summary.rows:
            self.assertFalse(hasattr(row, 'zone_transceiver_count'))

    # SLR-C2: plan detail renders correct columns and companion card
    def test_c2_plan_detail_no_zone_qty_has_companion_card(self):
        plan = self._make_multiclass_plan(name='SLR-C2-Plan')
        client = Client()
        client.login(username='slr-c-su', password='pass')
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail',
                      kwargs={'pk': plan.pk})
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Zone Qty column must be absent
        self.assertNotContains(resp, 'Zone Qty')
        # Companion card must be present
        self.assertContains(resp, 'Switch Zone Optic Summary')
        # Pre-generation disclaimer must be present
        self.assertContains(resp, 'Pre-generation estimate')


# ---------------------------------------------------------------------------
# DIET-493 RED: Companion table rendering (SLR-I1 through I5)
# ---------------------------------------------------------------------------

class TestCompanionTableRendering(TestCase):

    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext, cls.bo_1x, cls.bo_4x, cls.srv_dt = _make_fixtures()
        cls.superuser = User.objects.create_user(
            username='slr-i-su', password='pass', is_staff=True, is_superuser=True
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='slr-i-su', password='pass')
        self.plan = _make_plan(name='SLR-I-Plan')
        self.sw = _make_switch_class(self.plan, self.ext)
        self.sw.override_quantity = 1
        self.sw.save(update_fields=['override_quantity'])
        self.sc = _make_server_class(self.plan, self.srv_dt, qty=1, sc_id='slr-i-gpu')

    def _url(self):
        return reverse('plugins:netbox_hedgehog:topologyplan_detail',
                       kwargs={'pk': self.plan.pk})

    # SLR-I1: connection with zone xcvr → companion card present
    def test_i1_companion_card_present_when_connections_exist(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-i1-zone', xcvr=xcvr)
        _make_connection(self.sc, zone, nic_id='nic-i1', conn_id='SLR-I1', xcvr=xcvr)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Switch Zone Optic Summary')

    # SLR-I2: any connection → Pre-generation disclaimer present
    def test_i2_pre_generation_disclaimer_present(self):
        zone = _make_zone(self.sw, self.bo_1x, name='slr-i2-zone')
        _make_connection(self.sc, zone, nic_id='nic-i2', conn_id='SLR-I2', speed=800)
        resp = self.client.get(self._url())
        self.assertContains(resp, 'Pre-generation estimate')

    # SLR-I3: empty plan → companion card absent
    def test_i3_companion_card_absent_when_no_connections(self):
        resp = self.client.get(self._url())
        self.assertNotContains(resp, 'Switch Zone Optic Summary')

    # SLR-I4: zone with no xcvr → zone name present, required_switch_optics=0 shown
    def test_i4_zone_no_xcvr_shows_zero_in_companion_table(self):
        zone = _make_zone(self.sw, self.bo_4x, name='slr-i4-zone', xcvr=None)
        _make_connection(self.sc, zone, nic_id='nic-i4', conn_id='SLR-I4')
        resp = self.client.get(self._url())
        self.assertContains(resp, 'slr-i4-zone')
        # required_switch_optics=0 for xcvr-less zone; '0' must appear in the cell
        self.assertContains(resp, '0')

    # SLR-I5: 2 classes → same zone → 1 row in companion table; total_logical_links = sum
    def test_i5_two_classes_same_zone_one_aggregate_row(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.sw, self.bo_4x, name='slr-i5-shared', xcvr=xcvr)
        sc2 = _make_server_class(self.plan, self.srv_dt, qty=1, sc_id='slr-i5-b')
        _make_connection(self.sc, zone, nic_id='nic-i5a', conn_id='SLR-I5A', xcvr=xcvr)
        _make_connection(sc2, zone, nic_id='nic-i5b', conn_id='SLR-I5B', xcvr=xcvr, port_index=1)
        # Build service directly to verify aggregate count (template check is indirect)
        from netbox_hedgehog.services.connection_review import build_server_link_review
        summary = build_server_link_review(self.plan)
        # Only 1 zone → 1 aggregate entry
        self.assertEqual(len(summary.zone_aggregates), 1)
        agg = summary.zone_aggregates[0]
        # total_logical_links = 2 classes × qty=1 × ppc=2 = 4
        self.assertEqual(agg.total_logical_links, 4)
        # required_switch_optics < total_logical_links (shared cage semantics)
        self.assertLess(agg.required_switch_optics, agg.total_logical_links)


# ---------------------------------------------------------------------------
# DIET-493 RED: BOM parity guard (SLR-N1)
# ---------------------------------------------------------------------------

class TestBOMParityGuard(TestCase):
    """
    SLR-N1: Regression guard that BOM service behavior is unchanged and that
    the review aggregate estimate agrees with BOM in the ungenerated case.

    Full generation parity (comparing live Module counts to zone_aggregates)
    is a GREEN integration concern; RED scope is:
    1. BOM service API unchanged (no zone_aggregates contamination).
    2. zone_aggregates is accessible from build_server_link_review().
    3. In the ungenerated plan, BOM switch_transceiver items = 0, while
       zone_aggregates[0].required_switch_optics reflects the estimate.
    """

    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext, cls.bo_1x, cls.bo_4x, cls.srv_dt = _make_fixtures()

    def test_n1_bom_service_structure_unchanged(self):
        """get_plan_bom() returns PlanBOM; no zone_aggregates field on it."""
        from netbox_hedgehog.services.bom_export import get_plan_bom, PlanBOM
        plan = _make_plan(name='SLR-N1-BOM')
        bom = get_plan_bom(plan)
        self.assertIsInstance(bom, PlanBOM)
        self.assertFalse(
            hasattr(bom, 'zone_aggregates'),
            'zone_aggregates must NOT appear on PlanBOM; it belongs on ServerLinkReviewSummary',
        )
        self.assertEqual(bom.plan_id, plan.pk)

    def test_n1_review_aggregate_estimate_accessible_on_ungenerated_plan(self):
        """
        zone_aggregates[0].required_switch_optics = 1 for 1 link / 4-port breakout.
        BOM switch_transceiver count = 0 (no devices generated yet).
        This confirms the review is a pre-generation *estimate* and that the field exists.
        """
        from netbox_hedgehog.services.bom_export import get_plan_bom
        from netbox_hedgehog.services.connection_review import build_server_link_review

        plan = _make_plan(name='SLR-N1-Review')
        sw = _make_switch_class(plan, self.ext)
        sw.override_quantity = 1
        sw.save(update_fields=['override_quantity'])
        sc = _make_server_class(plan, self.srv_dt, qty=1, sc_id='slr-n1-cls')
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(sw, self.bo_4x, name='slr-n1-zone', xcvr=xcvr)
        _make_connection(sc, zone, nic_id='nic-n1', conn_id='SLR-N1', xcvr=xcvr)

        bom = get_plan_bom(plan)
        review = build_server_link_review(plan)

        # BOM: no generated devices → 0 switch_transceiver line items
        sw_xcvr_items = [i for i in bom.line_items if i.section == 'switch_transceiver']
        self.assertEqual(len(sw_xcvr_items), 0)

        # Review: zone_aggregates must exist (RED: AttributeError if field absent)
        self.assertTrue(
            hasattr(review, 'zone_aggregates'),
            'zone_aggregates field must exist on ServerLinkReviewSummary',
        )
        self.assertEqual(len(review.zone_aggregates), 1)
        # 1 link / 4 logical_ports → ceil(1/4) = 1 switch optic estimate
        self.assertEqual(review.zone_aggregates[0].required_switch_optics, 1)
