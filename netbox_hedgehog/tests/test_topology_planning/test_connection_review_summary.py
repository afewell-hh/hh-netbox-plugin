"""
Tests for DIET-449: connection review summary service and plan detail panel.

Service tests (TestConnectionReviewService):
  Verify build_connection_review_summary() groups correctly, assigns outcomes,
  and produces accurate totals.

View integration tests (TestConnectionReviewPanelView):
  Verify the plan detail page renders the review panel with correct content
  and correct permission behavior.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from dcim.models import DeviceType, Manufacturer, ModuleType, ModuleTypeProfile
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
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_switch_fixtures():
    """Return (manufacturer, switch_dt, ext, breakout_1x800g, breakout_4x200g)."""
    mfr, _ = Manufacturer.objects.get_or_create(
        name='CRv-Vendor', defaults={'slug': 'crv-vendor'}
    )
    dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='CRv-Switch', defaults={'slug': 'crv-switch'}
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
    bo_1x800g, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x800g-crv',
        defaults={'from_speed': 800, 'logical_ports': 1, 'logical_speed': 800},
    )
    bo_4x200g, _ = BreakoutOption.objects.get_or_create(
        breakout_id='4x200g-crv',
        defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200},
    )
    return mfr, dt, ext, bo_1x800g, bo_4x200g


def _make_server_dt():
    generic, _ = Manufacturer.objects.get_or_create(
        name='CRv-Server-Vendor', defaults={'slug': 'crv-server-vendor'}
    )
    dt, _ = DeviceType.objects.get_or_create(
        manufacturer=generic, model='CRv-Server', defaults={'slug': 'crv-server'}
    )
    return dt


def _make_plan(name='CRv-Plan'):
    return TopologyPlan.objects.create(
        name=name,
        customer_name='DIET-449 Test',
        status=TopologyPlanStatusChoices.DRAFT,
    )


def _make_switch_class(plan, ext):
    return PlanSwitchClass.objects.create(
        plan=plan,
        switch_class_id='crv-fe-leaf',
        fabric=FabricTypeChoices.FRONTEND,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=ext,
        uplink_ports_per_switch=4,
        mclag_pair=False,
    )


def _make_server_class(plan, server_dt, qty=2, server_class_id='crv-gpu'):
    return PlanServerClass.objects.create(
        plan=plan,
        server_class_id=server_class_id,
        category=ServerClassCategoryChoices.GPU,
        quantity=qty,
        gpus_per_server=8,
        server_device_type=server_dt,
    )


def _make_zone(switch_class, breakout_option, zone_name='crv-zone', xcvr_mt=None):
    return SwitchPortZone.objects.create(
        switch_class=switch_class,
        zone_name=zone_name,
        zone_type=PortZoneTypeChoices.SERVER,
        port_spec='1-48',
        breakout_option=breakout_option,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
        priority=100,
        transceiver_module_type=xcvr_mt,
    )


def _make_connection(server_class, zone, nic_id='nic-crv', xcvr_mt=None, speed=200,
                     conn_id='FE-001', port_index=0):
    nic = get_test_server_nic(server_class, nic_id=nic_id)
    return PlanServerConnection.objects.create(
        server_class=server_class,
        connection_id=conn_id,
        nic=nic,
        port_index=port_index,
        target_zone=zone,
        ports_per_connection=2,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        speed=speed,
        port_type='data',
        transceiver_module_type=xcvr_mt,
    )


# ---------------------------------------------------------------------------
# S1: Service unit tests
# ---------------------------------------------------------------------------

class TestConnectionReviewService(TestCase):
    """Unit tests for build_connection_review_summary()."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext, cls.bo_1x800g, cls.bo_4x200g = _make_switch_fixtures()
        cls.server_dt = _make_server_dt()

    def setUp(self):
        self.plan = _make_plan()
        self.switch_class = _make_switch_class(self.plan, self.ext)
        self.server_class = _make_server_class(self.plan, self.server_dt)

    def _build(self):
        from netbox_hedgehog.services.connection_review import build_connection_review_summary
        return build_connection_review_summary(self.plan)

    # ------------------------------------------------------------------
    # S1.1 — Empty plan
    # ------------------------------------------------------------------

    def test_empty_plan_returns_empty_summary(self):
        """Plan with no connections returns an empty summary."""
        summary = self._build()
        self.assertEqual(summary.groups, [])
        self.assertEqual(summary.total_connections, 0)
        self.assertEqual(summary.match_count, 0)
        self.assertEqual(summary.needs_review_count, 0)
        self.assertEqual(summary.blocked_count, 0)

    # ------------------------------------------------------------------
    # S1.2 — Outcome: match
    # ------------------------------------------------------------------

    def test_single_connection_no_transceiver_is_match(self):
        """DIET-466: both null → blocked (transceiver required on both sides)."""
        zone = _make_zone(self.switch_class, self.bo_1x800g)
        _make_connection(self.server_class, zone, speed=800)
        summary = self._build()
        self.assertEqual(len(summary.groups), 1)
        self.assertEqual(summary.groups[0].outcome, 'blocked')
        self.assertEqual(summary.blocked_count, 1)

    def test_connection_with_matching_transceiver_fks_is_match(self):
        """Connection and zone both have the same transceiver FK → match."""
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.switch_class, self.bo_4x200g, xcvr_mt=xcvr)
        _make_connection(self.server_class, zone, xcvr_mt=xcvr)
        summary = self._build()
        self.assertEqual(summary.groups[0].outcome, 'match')

    def test_no_breakout_and_no_transceiver_1x_is_match(self):
        """DIET-466: both null, 1x800g → blocked (transceiver required regardless of breakout)."""
        zone = _make_zone(self.switch_class, self.bo_1x800g)
        _make_connection(self.server_class, zone, speed=800)
        summary = self._build()
        self.assertEqual(summary.groups[0].outcome, 'blocked')

    # ------------------------------------------------------------------
    # S1.3 — Outcome: needs_review
    # ------------------------------------------------------------------

    def test_conn_xcvr_without_zone_xcvr_is_needs_review(self):
        """DIET-466: zone null → blocked (null gate fires; both ends required)."""
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.switch_class, self.bo_4x200g, xcvr_mt=None)
        _make_connection(self.server_class, zone, xcvr_mt=xcvr)
        summary = self._build()
        self.assertEqual(summary.groups[0].outcome, 'blocked')
        self.assertIn('transceiver', summary.groups[0].reason.lower())

    def test_zone_xcvr_without_conn_xcvr_is_needs_review(self):
        """DIET-466: conn null → blocked (null gate fires; both ends required)."""
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.switch_class, self.bo_4x200g, xcvr_mt=xcvr)
        _make_connection(self.server_class, zone, xcvr_mt=None)
        summary = self._build()
        self.assertEqual(summary.groups[0].outcome, 'blocked')
        self.assertIn('transceiver', summary.groups[0].reason.lower())

    def test_breakout_without_transceiver_is_needs_review(self):
        """DIET-466: both null, 4x200g breakout → blocked (null gate fires before breakout advisory)."""
        zone = _make_zone(self.switch_class, self.bo_4x200g, xcvr_mt=None)
        _make_connection(self.server_class, zone, xcvr_mt=None, speed=200)
        summary = self._build()
        self.assertEqual(summary.groups[0].outcome, 'blocked')
        self.assertIn('transceiver', summary.groups[0].reason.lower())

    def test_mismatched_transceiver_fks_is_needs_review(self):
        """Connection and zone have different (non-null) transceiver FKs → needs_review."""
        from netbox_hedgehog.tests.test_topology_planning import get_test_transceiver_module_type_osfp
        xcvr_a = get_test_transceiver_module_type()
        xcvr_b = get_test_transceiver_module_type_osfp()
        zone = _make_zone(self.switch_class, self.bo_4x200g, xcvr_mt=xcvr_a)
        _make_connection(self.server_class, zone, xcvr_mt=xcvr_b)
        summary = self._build()
        self.assertEqual(summary.groups[0].outcome, 'needs_review')

    # ------------------------------------------------------------------
    # S1.4 — Outcome: blocked
    # ------------------------------------------------------------------

    def test_zone_without_breakout_option_is_blocked(self):
        """Zone with no breakout_option → blocked (can't calculate switch quantity)."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='crv-zone-nob',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-4',
            breakout_option=None,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )
        _make_connection(self.server_class, zone)
        summary = self._build()
        self.assertEqual(summary.groups[0].outcome, 'blocked')
        self.assertIn('breakout', summary.groups[0].reason.lower())

    # ------------------------------------------------------------------
    # S1.5 — Grouping
    # ------------------------------------------------------------------

    def test_two_connections_same_type_form_one_group(self):
        """Two connections with identical type key → one group, count = 2 rows × qty=2 × ppc=2 = 8."""
        zone = _make_zone(self.switch_class, self.bo_4x200g)
        _make_connection(self.server_class, zone, nic_id='nic-1', conn_id='FE-001', port_index=0)
        _make_connection(self.server_class, zone, nic_id='nic-2', conn_id='FE-002', port_index=1)
        summary = self._build()
        self.assertEqual(len(summary.groups), 1)
        # 2 rows × server_class.quantity(2) × ports_per_connection(2) = 8
        self.assertEqual(summary.groups[0].count, 8)
        self.assertEqual(summary.total_connections, 8)

    def test_different_speeds_form_separate_groups(self):
        """Connections with different speeds → separate groups."""
        zone_800 = _make_zone(self.switch_class, self.bo_1x800g, zone_name='zone-800')
        zone_200 = _make_zone(self.switch_class, self.bo_4x200g, zone_name='zone-200')
        _make_connection(self.server_class, zone_800, nic_id='nic-800', conn_id='FE-800',
                         port_index=0, speed=800)
        _make_connection(self.server_class, zone_200, nic_id='nic-200', conn_id='FE-200',
                         port_index=1, speed=200)
        summary = self._build()
        self.assertEqual(len(summary.groups), 2)
        # Each group: qty=2 × ppc=2 = 4; total across both = 8
        self.assertEqual(summary.total_connections, 8)

    def test_different_breakouts_form_separate_groups(self):
        """Connections with different breakout options → separate groups."""
        zone_1 = _make_zone(self.switch_class, self.bo_1x800g, zone_name='z-1x800g', )
        zone_4 = _make_zone(self.switch_class, self.bo_4x200g, zone_name='z-4x200g')
        _make_connection(self.server_class, zone_1, nic_id='nic-a', conn_id='FE-A',
                         port_index=0, speed=800)
        _make_connection(self.server_class, zone_4, nic_id='nic-b', conn_id='FE-B',
                         port_index=1, speed=200)
        summary = self._build()
        self.assertEqual(len(summary.groups), 2)

    def test_summary_totals_are_correct(self):
        """match_count + needs_review_count + blocked_count = len(groups)."""
        xcvr = get_test_transceiver_module_type()
        zone_match = _make_zone(self.switch_class, self.bo_4x200g, zone_name='z-match',
                                xcvr_mt=xcvr)
        zone_nr = _make_zone(self.switch_class, self.bo_4x200g, zone_name='z-nr', xcvr_mt=None)
        _make_connection(self.server_class, zone_match, nic_id='nic-m', conn_id='FE-M',
                         port_index=0, xcvr_mt=xcvr, speed=200)
        _make_connection(self.server_class, zone_nr, nic_id='nic-nr', conn_id='FE-NR',
                         port_index=1, xcvr_mt=xcvr, speed=200)
        summary = self._build()
        self.assertEqual(
            summary.match_count + summary.needs_review_count + summary.blocked_count,
            len(summary.groups),
        )

    # ------------------------------------------------------------------
    # S1.6 — Group field values
    # ------------------------------------------------------------------

    def test_group_speed_matches_connection_speed(self):
        zone = _make_zone(self.switch_class, self.bo_4x200g)
        _make_connection(self.server_class, zone, speed=200)
        summary = self._build()
        self.assertEqual(summary.groups[0].speed, 200)

    def test_group_breakout_id_matches_zone_breakout(self):
        zone = _make_zone(self.switch_class, self.bo_4x200g)
        _make_connection(self.server_class, zone)
        summary = self._build()
        self.assertEqual(summary.groups[0].breakout_id, '4x200g-crv')

    def test_group_xcvr_fields_populated(self):
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.switch_class, self.bo_4x200g, xcvr_mt=xcvr)
        _make_connection(self.server_class, zone, xcvr_mt=xcvr)
        summary = self._build()
        self.assertEqual(summary.groups[0].connection_xcvr, xcvr.model)
        self.assertEqual(summary.groups[0].zone_xcvr, xcvr.model)

    def test_group_xcvr_fields_none_when_no_fk(self):
        zone = _make_zone(self.switch_class, self.bo_4x200g, xcvr_mt=None)
        _make_connection(self.server_class, zone, xcvr_mt=None)
        summary = self._build()
        self.assertIsNone(summary.groups[0].connection_xcvr)
        self.assertIsNone(summary.groups[0].zone_xcvr)

    def test_groups_sorted_by_speed_descending(self):
        """Faster connections appear first in the sorted group list."""
        zone_800 = _make_zone(self.switch_class, self.bo_1x800g, zone_name='z800')
        zone_200 = _make_zone(self.switch_class, self.bo_4x200g, zone_name='z200')
        _make_connection(self.server_class, zone_200, nic_id='n200', conn_id='F200',
                         port_index=0, speed=200)
        _make_connection(self.server_class, zone_800, nic_id='n800', conn_id='F800',
                         port_index=1, speed=800)
        summary = self._build()
        speeds = [g.speed for g in summary.groups]
        self.assertEqual(speeds, sorted(speeds, reverse=True))

    # ------------------------------------------------------------------
    # S1.7 — Count expansion: server_class.quantity × ports_per_connection
    # ------------------------------------------------------------------

    def test_count_expands_by_server_quantity(self):
        """
        count = server_class.quantity × ports_per_connection.

        A single PlanServerConnection row applied to 4 servers with
        ports_per_connection=2 must yield count=8, not count=1.
        """
        server_class_4 = _make_server_class(
            self.plan, self.server_dt, qty=4, server_class_id='crv-gpu-exp-qty')
        zone = _make_zone(self.switch_class, self.bo_4x200g, zone_name='z-exp-qty')
        _make_connection(server_class_4, zone, nic_id='nic-exp-qty',
                         conn_id='EXP-QTY', port_index=0)
        # _make_connection sets ports_per_connection=2 (see fixture helper)
        summary = self._build()

        # The group for server_class_4's connection: 4 servers × 2 ports = 8
        self.assertEqual(len(summary.groups), 1)
        self.assertEqual(
            summary.groups[0].count, 8,
            f'Expected 4 servers × 2 ports = 8; got {summary.groups[0].count}',
        )

    def test_count_expands_by_ports_per_connection(self):
        """
        Higher ports_per_connection multiplies the count correctly.
        4 servers × 4 ports_per_connection = 16.
        """
        from netbox_hedgehog.models.topology_planning import PlanServerNIC

        server_class_4 = _make_server_class(
            self.plan, self.server_dt, qty=4, server_class_id='crv-gpu-exp-ppc')
        zone = _make_zone(self.switch_class, self.bo_4x200g, zone_name='z-exp-ppc')
        nic = get_test_server_nic(server_class_4, nic_id='nic-exp-ppc')
        PlanServerConnection.objects.create(
            server_class=server_class_4,
            connection_id='EXP-PPC',
            nic=nic,
            port_index=0,
            target_zone=zone,
            ports_per_connection=4,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200,
            port_type='data',
        )
        summary = self._build()

        self.assertEqual(len(summary.groups), 1)
        self.assertEqual(
            summary.groups[0].count, 16,
            f'Expected 4 servers × 4 ports = 16; got {summary.groups[0].count}',
        )

    def test_total_connections_is_sum_of_expanded_counts(self):
        """
        total_connections sums the expanded counts across all groups.
        2 groups: (2 servers × 2 ports) + (3 servers × 1 port) = 4 + 3 = 7.
        """
        from netbox_hedgehog.models.topology_planning import PlanServerNIC

        # Group 1: 2 servers × 2 ports = 4
        server_class_2 = _make_server_class(
            self.plan, self.server_dt, qty=2, server_class_id='crv-gpu-tot-a')
        zone_a = _make_zone(self.switch_class, self.bo_4x200g, zone_name='z-tot-a')
        nic_a = get_test_server_nic(server_class_2, nic_id='nic-tot-a')
        PlanServerConnection.objects.create(
            server_class=server_class_2, connection_id='TOT-A', nic=nic_a,
            port_index=0, target_zone=zone_a, ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200, port_type='data',
        )

        # Group 2: 3 servers × 1 port = 3  (different zone breakout → separate group)
        server_class_3 = PlanServerClass.objects.create(
            plan=self.plan, server_class_id='crv-gpu-3', quantity=3,
            category=ServerClassCategoryChoices.GPU,
            gpus_per_server=8, server_device_type=self.server_dt,
        )
        zone_b = _make_zone(self.switch_class, self.bo_1x800g, zone_name='z-tot-b')
        nic_b = get_test_server_nic(server_class_3, nic_id='nic-tot-b')
        PlanServerConnection.objects.create(
            server_class=server_class_3, connection_id='TOT-B', nic=nic_b,
            port_index=0, target_zone=zone_b, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=800, port_type='data',
        )

        summary = self._build()
        self.assertEqual(
            summary.total_connections, 7,
            f'Expected (2×2) + (3×1) = 7; got {summary.total_connections}',
        )

    def test_same_type_multiple_server_classes_counts_are_summed(self):
        """
        Two PlanServerConnection rows with the same type key (different server classes)
        must land in the same group and their expanded counts are summed.
        (2 servers × 2 ports) + (3 servers × 2 ports) = 4 + 6 = 10 in one group.
        """
        from netbox_hedgehog.models.topology_planning import PlanServerNIC

        zone = _make_zone(self.switch_class, self.bo_4x200g, zone_name='z-merge')

        sc_2 = _make_server_class(
            self.plan, self.server_dt, qty=2, server_class_id='crv-gpu-merge-a')
        nic_2 = get_test_server_nic(sc_2, nic_id='nic-merge-a')
        PlanServerConnection.objects.create(
            server_class=sc_2, connection_id='MERGE-A', nic=nic_2,
            port_index=0, target_zone=zone, ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200, port_type='data',
        )

        sc_3 = PlanServerClass.objects.create(
            plan=self.plan, server_class_id='crv-gpu-merge3', quantity=3,
            category=ServerClassCategoryChoices.GPU,
            gpus_per_server=8, server_device_type=self.server_dt,
        )
        nic_3 = get_test_server_nic(sc_3, nic_id='nic-merge-b')
        PlanServerConnection.objects.create(
            server_class=sc_3, connection_id='MERGE-B', nic=nic_3,
            port_index=0, target_zone=zone, ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200, port_type='data',
        )

        summary = self._build()
        # Both rows have identical type key → one group
        self.assertEqual(len(summary.groups), 1)
        self.assertEqual(
            summary.groups[0].count, 10,
            f'Expected (2×2) + (3×2) = 10; got {summary.groups[0].count}',
        )


# ---------------------------------------------------------------------------
# S2: View integration tests — plan detail renders connection review panel
# ---------------------------------------------------------------------------

class TestConnectionReviewPanelView(TestCase):
    """
    Integration tests: plan detail page must render the connection review panel
    with correct content, badges, and permission enforcement.
    """

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext, cls.bo_1x800g, cls.bo_4x200g = _make_switch_fixtures()
        cls.server_dt = _make_server_dt()

        # Superuser for main functionality tests
        cls.superuser = User.objects.create_user(
            username='crv-superuser', password='pass', is_staff=True, is_superuser=True
        )
        # Regular user without plan permission
        cls.plain_user = User.objects.create_user(
            username='crv-plain', password='pass', is_staff=True
        )
        # User with ObjectPermission on TopologyPlan (view only)
        cls.plan_viewer = User.objects.create_user(
            username='crv-viewer', password='pass', is_staff=True
        )
        from django.contrib.auth.models import Permission
        perm = Permission.objects.get(
            content_type__app_label='netbox_hedgehog',
            codename='view_topologyplan',
        )
        cls.plan_viewer.user_permissions.add(perm)
        obj_perm = ObjectPermission.objects.create(
            name='crv-viewer-topologyplan', actions=['view']
        )
        obj_perm.object_types.add(
            ContentType.objects.get_for_model(TopologyPlan)
        )
        obj_perm.users.add(cls.plan_viewer)

    def setUp(self):
        self.client = Client()
        self.client.login(username='crv-superuser', password='pass')
        self.plan = _make_plan(name='CRv-View-Plan')
        self.switch_class = _make_switch_class(self.plan, self.ext)
        self.server_class = _make_server_class(self.plan, self.server_dt)

    def _detail_url(self):
        return reverse('plugins:netbox_hedgehog:topologyplan_detail', kwargs={'pk': self.plan.pk})

    def _get_detail(self):
        return self.client.get(self._detail_url())

    # ------------------------------------------------------------------
    # V1: Panel visibility
    # ------------------------------------------------------------------

    def test_review_panel_present_on_draft_plan_with_connections(self):
        """Connection review panel renders on a draft plan (no GenerationState needed)."""
        zone = _make_zone(self.switch_class, self.bo_4x200g)
        _make_connection(self.server_class, zone)
        response = self._get_detail()
        self.assertEqual(response.status_code, 200)
        self.assertIn('server_link_review', response.context)

    def test_review_panel_present_even_without_connections(self):
        """Review panel context key is always present, even with zero connections."""
        response = self._get_detail()
        self.assertEqual(response.status_code, 200)
        self.assertIn('server_link_review', response.context)

    def test_review_section_heading_in_html(self):
        """HTML response must contain the 'Server-Link Review' heading (DIET-460 replaced legacy panel)."""
        response = self._get_detail()
        self.assertContains(response, 'Server-Link Review')

    # ------------------------------------------------------------------
    # V2: Match/needs_review/blocked badge counts in context
    # ------------------------------------------------------------------

    def test_review_context_shows_match_for_clean_connection(self):
        """Both zone and connection have matching transceiver → match."""
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.switch_class, self.bo_1x800g, zone_name='crv-1x-match', xcvr_mt=xcvr)
        _make_connection(self.server_class, zone, speed=800, xcvr_mt=xcvr)
        response = self._get_detail()
        summary = response.context['server_link_review']
        self.assertEqual(summary.match_count, 1)
        self.assertEqual(summary.needs_review_count, 0)
        self.assertEqual(summary.blocked_count, 0)

    def test_review_context_shows_needs_review_for_transceiver_mismatch(self):
        """DIET-466: zone null → blocked. Mismatched (both set, different) → needs_review."""
        from netbox_hedgehog.tests.test_topology_planning import get_test_transceiver_module_type_osfp
        xcvr_conn = get_test_transceiver_module_type()
        xcvr_zone = get_test_transceiver_module_type_osfp()
        zone = _make_zone(self.switch_class, self.bo_4x200g, xcvr_mt=xcvr_zone)
        _make_connection(self.server_class, zone, xcvr_mt=xcvr_conn)
        response = self._get_detail()
        summary = response.context['server_link_review']
        self.assertGreaterEqual(summary.needs_review_count + summary.blocked_count, 1)

    def test_review_context_shows_blocked_for_missing_breakout(self):
        """Zone with no breakout_option → blocked in context."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='crv-blocked-zone',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-4',
            breakout_option=None,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )
        _make_connection(self.server_class, zone)
        response = self._get_detail()
        summary = response.context['server_link_review']
        self.assertEqual(summary.blocked_count, 1)

    # ------------------------------------------------------------------
    # V3: HTML content — group table
    # ------------------------------------------------------------------

    def test_group_speed_appears_in_html(self):
        """Connection speed (e.g. '200G') appears in the review panel HTML."""
        zone = _make_zone(self.switch_class, self.bo_4x200g)
        _make_connection(self.server_class, zone, speed=200)
        response = self._get_detail()
        self.assertContains(response, '200G')

    def test_group_breakout_appears_in_html(self):
        """Breakout option ID appears in the review panel HTML."""
        zone = _make_zone(self.switch_class, self.bo_4x200g)
        _make_connection(self.server_class, zone)
        response = self._get_detail()
        self.assertContains(response, '4x200g-crv')

    def test_match_outcome_badge_appears_in_html(self):
        """'match' badge appears in HTML when both zone and connection have matching xcvr."""
        xcvr = get_test_transceiver_module_type()
        zone = _make_zone(self.switch_class, self.bo_1x800g, zone_name='crv-1x-html', xcvr_mt=xcvr)
        _make_connection(self.server_class, zone, speed=800, xcvr_mt=xcvr)
        response = self._get_detail()
        content = response.content.decode()
        self.assertIn('match', content.lower())

    def test_needs_review_outcome_badge_appears_in_html(self):
        """'needs review' badge/text appears in HTML for a mismatched-xcvr connection."""
        from netbox_hedgehog.tests.test_topology_planning import get_test_transceiver_module_type_osfp
        xcvr_conn = get_test_transceiver_module_type()
        xcvr_zone = get_test_transceiver_module_type_osfp()
        zone = _make_zone(self.switch_class, self.bo_4x200g, xcvr_mt=xcvr_zone)
        _make_connection(self.server_class, zone, xcvr_mt=xcvr_conn)
        response = self._get_detail()
        content = response.content.decode()
        # Mismatched xcvrs → 'needs_review' or 'blocked'; either contains relevant text
        self.assertTrue('needs' in content.lower() or 'blocked' in content.lower())

    # ------------------------------------------------------------------
    # V4: Permission enforcement
    # ------------------------------------------------------------------

    def test_anonymous_user_cannot_access_detail(self):
        """Unauthenticated request redirects to login."""
        anon_client = Client()
        response = anon_client.get(self._detail_url())
        self.assertIn(response.status_code, [302, 403])

    def test_user_without_plan_permission_gets_403(self):
        """User with no plan ObjectPermission is denied."""
        self.client.login(username='crv-plain', password='pass')
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 403)

    def test_plan_viewer_sees_review_panel(self):
        """User with view ObjectPermission can see the server-link review panel."""
        zone = _make_zone(self.switch_class, self.bo_4x200g)
        _make_connection(self.server_class, zone)
        self.client.login(username='crv-viewer', password='pass')
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn('server_link_review', response.context)
