"""
RED Tests — Compatibility Report UI (#375)

Tests for the compatibility-report panel on the topology plan detail page.
These tests are written in Phase 3 (RED) and must FAIL until Phase 4 implements:
  - show_failure_report / mismatch_rows / bay_error_rows in TopologyPlanView.get_extra_context()
  - The conditional "Generation Failure Report" card in topologyplan.html

Test coverage per the Phase 2 spec (#378):
  T1  — FAILED + sweep mismatches → panel visible, rows rendered
  T2  — GENERATED → panel absent
  T3  — FAILED + mismatch_report=None → panel absent
  T4  — FAILED + mismatch_report={} → panel absent
  T5  — No GenerationState → panel absent
  T6a — cage_type dimension renders
  T6b — medium dimension renders
  T6c — connector dimension renders
  T6d — standard dimension renders
  T7  — Multiple mismatch rows all rendered
  T8a — FAILED + bay_errors (missing_nested_bay) → bay section visible
  T8b — FAILED + bay_errors (missing_switch_bay) → bay section visible
  T9  — Deleted connection renders fallback label (#pk)
  T10 — RBAC: no permission → 302/403
  T11 — RBAC: with ObjectPermission → 200 + panel visible

Parent: #375
Spec: #378
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from dcim.models import DeviceType, Manufacturer
from users.models import ObjectPermission

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    BreakoutOption,
    DeviceTypeExtension,
    SwitchPortZone,
    GenerationState,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    ServerClassCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    GenerationStatusChoices,
    ConnectionTypeChoices,
    ConnectionDistributionChoices,
    PortZoneTypeChoices,
    FabricClassChoices,
)
from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic

User = get_user_model()

_DETAIL_URL_NAME = 'plugins:netbox_hedgehog:topologyplan_detail'
_PANEL_HEADING = 'Generation Failure Report'
_MISMATCH_SECTION = 'Transceiver Compatibility Mismatches'
_BAY_SECTION = 'Bay Configuration Errors'


def _detail_url(pk):
    return reverse(_DETAIL_URL_NAME, args=[pk])


class CompatibilityReportUITestCase(TestCase):
    """
    Integration tests for the compatibility report panel on the topology plan detail page.

    All tests load the detail page via GET and assert on rendered HTML content.
    GenerationState objects are created directly with crafted mismatch_report JSON —
    no actual device generation is performed.
    """

    @classmethod
    def setUpTestData(cls):
        """Shared test data: users, device types, breakout option, switch extension."""
        cls.superuser = User.objects.create_user(
            username='report-admin',
            password='testpass123',
            is_staff=True,
            is_superuser=True,
        )
        cls.regular_user = User.objects.create_user(
            username='report-noperms',
            password='testpass123',
            is_staff=False,
            is_superuser=False,
        )

        cls.manufacturer = Manufacturer.objects.create(
            name='CompatMfg',
            slug='compatmfg',
        )
        cls.switch_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='CompatSwitch',
            slug='compatswitch',
            u_height=1,
        )
        cls.server_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='CompatServer',
            slug='compatserver',
            u_height=2,
        )
        cls.breakout = BreakoutOption.objects.create(
            breakout_id='compat-4x200g',
            from_speed=800,
            logical_ports=4,
            logical_speed=200,
        )
        cls.switch_ext = DeviceTypeExtension.objects.create(
            device_type=cls.switch_type,
            native_speed=800,
            supported_breakouts=['4x200g'],
            mclag_capable=False,
            hedgehog_roles=['spine', 'server-leaf'],
        )

    def setUp(self):
        """Per-test: fresh client (superuser), fresh plan, switch class, zone, server class."""
        self.client = Client()
        self.client.login(username='report-admin', password='testpass123')

        self.plan = TopologyPlan.objects.create(
            name='Compat Report Plan',
            customer_name='Test Customer',
            status=TopologyPlanStatusChoices.DRAFT,
            created_by=self.superuser,
        )
        self.switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='COMPAT-SW',
            device_type_extension=self.switch_ext,
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SPINE,
            override_quantity=2,
        )
        self.zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='fe-leaf-downlinks',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-32',
            breakout_option=self.breakout,
            priority=10,
        )
        self.server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='COMPAT-SRV',
            server_device_type=self.server_type,
            quantity=4,
            gpus_per_server=8,
            category=ServerClassCategoryChoices.GPU,
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _make_connection(self, connection_id='fe-conn-0'):
        """Create a minimal PlanServerConnection for mismatch-row label tests."""
        return PlanServerConnection.objects.create(
            connection_id=connection_id,
            server_class=self.server_class,
            nic=get_test_server_nic(self.server_class),
            port_index=0,
            target_zone=self.zone,
            ports_per_connection=1,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
        )

    def _make_generation_state(self, status, mismatch_report=None):
        """Create a GenerationState with the given status and mismatch_report."""
        return GenerationState.objects.create(
            plan=self.plan,
            status=status,
            mismatch_report=mismatch_report,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
        )

    def _get_detail(self):
        response = self.client.get(_detail_url(self.plan.pk))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    # =========================================================================
    # T1 — FAILED + sweep mismatches → panel and rows visible
    # =========================================================================

    def test_t1_failed_with_sweep_mismatches_shows_report(self):
        """
        T1: Detail page shows the Generation Failure Report panel when
        GenerationState.status=FAILED and mismatch_report contains 'mismatches'.
        The connection label, dimension, server_end, and switch_end are rendered.
        """
        conn = self._make_connection('fe-conn-0')
        self._make_generation_state(
            status=GenerationStatusChoices.FAILED,
            mismatch_report={'mismatches': [{
                'connection_id': conn.pk,
                'server_device': 'COMPAT-SRV',
                'switch_port': 'fe-leaf-downlinks',
                'mismatch_type': 'cage_type',
                'server_end': 'SFP28',
                'switch_end': 'QSFP28',
            }]},
        )
        # Verify context variables are present (RED: these keys don't exist yet)
        response = self.client.get(_detail_url(self.plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn('show_failure_report', response.context,
                      "show_failure_report must be in view context")
        self.assertTrue(response.context['show_failure_report'],
                        "show_failure_report must be True for FAILED+mismatches")
        self.assertIn('mismatch_rows', response.context,
                      "mismatch_rows must be in view context")
        self.assertEqual(len(response.context['mismatch_rows']), 1,
                         "mismatch_rows must contain one row")

        content = response.content.decode()
        # Panel heading
        self.assertIn(_PANEL_HEADING, content,
                      "Generation Failure Report panel must be visible")
        # Section heading
        self.assertIn(_MISMATCH_SECTION, content,
                      "Transceiver Compatibility Mismatches section must be visible")
        # Row data
        self.assertIn('fe-conn-0', content,
                      "connection_id label must be rendered")
        self.assertIn('cage_type', content,
                      "dimension must be rendered")
        self.assertIn('SFP28', content,
                      "server_end value must be rendered")
        self.assertIn('QSFP28', content,
                      "switch_end value must be rendered")
        self.assertIn('COMPAT-SRV', content,
                      "server_device must be rendered")
        self.assertIn('fe-leaf-downlinks', content,
                      "switch_port must be rendered")
        # Bay section must NOT appear
        self.assertNotIn(_BAY_SECTION, content,
                         "Bay Configuration Errors section must be absent")

    # =========================================================================
    # T2 — GENERATED → panel absent
    # =========================================================================

    def test_t2_generated_status_hides_report(self):
        """T2: Detail page hides the failure report when status=GENERATED."""
        self._make_generation_state(
            status=GenerationStatusChoices.GENERATED,
            mismatch_report=None,
        )
        content = self._get_detail()
        self.assertNotIn(_PANEL_HEADING, content,
                         "Panel must be absent when generation succeeded")

    # =========================================================================
    # T3 — FAILED + mismatch_report=None → panel absent
    # =========================================================================

    def test_t3_failed_null_mismatch_report_hides_panel(self):
        """T3: Panel is absent when status=FAILED but mismatch_report is None."""
        self._make_generation_state(
            status=GenerationStatusChoices.FAILED,
            mismatch_report=None,
        )
        content = self._get_detail()
        self.assertNotIn(_PANEL_HEADING, content,
                         "Panel must be absent when mismatch_report is None")

    # =========================================================================
    # T4 — FAILED + mismatch_report={} → panel absent
    # =========================================================================

    def test_t4_failed_empty_mismatch_report_hides_panel(self):
        """T4: Panel is absent when status=FAILED but mismatch_report is empty dict."""
        self._make_generation_state(
            status=GenerationStatusChoices.FAILED,
            mismatch_report={},
        )
        content = self._get_detail()
        self.assertNotIn(_PANEL_HEADING, content,
                         "Panel must be absent when mismatch_report is {}")

    # =========================================================================
    # T5 — No GenerationState → panel absent
    # =========================================================================

    def test_t5_no_generation_state_hides_panel(self):
        """T5: Panel is absent when the plan has no GenerationState at all."""
        # No GenerationState created for this plan
        content = self._get_detail()
        self.assertNotIn(_PANEL_HEADING, content,
                         "Panel must be absent when no GenerationState exists")

    # =========================================================================
    # T6a–T6d — Each sweep dimension renders
    # =========================================================================

    def _make_mismatch_gs(self, dim, server_val, switch_val):
        """Helper: create FAILED GenerationState with a single sweep mismatch."""
        conn = self._make_connection(f'conn-{dim}')
        self._make_generation_state(
            status=GenerationStatusChoices.FAILED,
            mismatch_report={'mismatches': [{
                'connection_id': conn.pk,
                'server_device': 'COMPAT-SRV',
                'switch_port': 'fe-leaf-downlinks',
                'mismatch_type': dim,
                'server_end': server_val,
                'switch_end': switch_val,
            }]},
        )

    def test_t6a_cage_type_dimension_rendered(self):
        """T6a: cage_type dimension appears in the rendered mismatch table."""
        self._make_mismatch_gs('cage_type', 'SFP28', 'QSFP28')
        content = self._get_detail()
        self.assertIn(_PANEL_HEADING, content)
        self.assertIn('cage_type', content,
                      "cage_type dimension must appear in table")

    def test_t6b_medium_dimension_rendered(self):
        """T6b: medium dimension appears in the rendered mismatch table."""
        self._make_mismatch_gs('medium', 'copper', 'optical')
        content = self._get_detail()
        self.assertIn(_PANEL_HEADING, content)
        self.assertIn('medium', content,
                      "medium dimension must appear in table")

    def test_t6c_connector_dimension_rendered(self):
        """T6c: connector dimension appears in the rendered mismatch table."""
        self._make_mismatch_gs('connector', 'LC-UPC', 'MPO-12')
        content = self._get_detail()
        self.assertIn(_PANEL_HEADING, content)
        self.assertIn('connector', content,
                      "connector dimension must appear in table")

    def test_t6d_standard_dimension_rendered(self):
        """T6d: standard dimension appears in the rendered mismatch table."""
        self._make_mismatch_gs('standard', '10GBASE-SR', '100GBASE-SR4')
        content = self._get_detail()
        self.assertIn(_PANEL_HEADING, content)
        self.assertIn('standard', content,
                      "standard dimension must appear in table")

    # =========================================================================
    # T7 — Multiple mismatch rows all rendered
    # =========================================================================

    def test_t7_multiple_mismatch_rows_all_rendered(self):
        """T7: All mismatch rows across multiple dimensions are rendered."""
        conn = self._make_connection('fe-conn-multi')
        self._make_generation_state(
            status=GenerationStatusChoices.FAILED,
            mismatch_report={'mismatches': [
                {
                    'connection_id': conn.pk,
                    'server_device': 'COMPAT-SRV',
                    'switch_port': 'fe-leaf-downlinks',
                    'mismatch_type': 'cage_type',
                    'server_end': 'SFP28',
                    'switch_end': 'QSFP28',
                },
                {
                    'connection_id': conn.pk,
                    'server_device': 'COMPAT-SRV',
                    'switch_port': 'fe-leaf-downlinks',
                    'mismatch_type': 'medium',
                    'server_end': 'copper',
                    'switch_end': 'optical',
                },
            ]},
        )
        response = self.client.get(_detail_url(self.plan.pk))
        self.assertEqual(response.status_code, 200)
        # Both rows must be in context
        self.assertIn('mismatch_rows', response.context)
        self.assertEqual(len(response.context['mismatch_rows']), 2,
                         "Both mismatch rows must appear in context")
        content = response.content.decode()
        self.assertIn('SFP28', content)
        self.assertIn('copper', content)
        # Both dimensions present
        self.assertIn('cage_type', content)
        self.assertIn('medium', content)

    # =========================================================================
    # T8a — FAILED + bay_errors (missing_nested_bay)
    # =========================================================================

    def test_t8a_bay_errors_missing_nested_bay_shows_bay_section(self):
        """
        T8a: Bay Configuration Errors section is visible when mismatch_report
        contains bay_errors with error_type=missing_nested_bay.
        The Compatibility Mismatches section must be absent.
        """
        self._make_generation_state(
            status=GenerationStatusChoices.FAILED,
            mismatch_report={'bay_errors': [{
                'error_type': 'missing_nested_bay',
                'device': 'server-001',
                'cage': 'cage-0',
                'connection_id': 99,
                'hint': 'Run populate_transceiver_bays to add ModuleBayTemplates to NIC ModuleTypes.',
            }]},
        )
        response = self.client.get(_detail_url(self.plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn('bay_error_rows', response.context,
                      "bay_error_rows must be in view context")
        self.assertEqual(len(response.context['bay_error_rows']), 1,
                         "bay_error_rows must contain one row")

        content = response.content.decode()
        self.assertIn(_PANEL_HEADING, content,
                      "Generation Failure Report panel must be visible")
        self.assertIn(_BAY_SECTION, content,
                      "Bay Configuration Errors section must be visible")
        self.assertIn('Missing NIC Port Bay', content,
                      "error_type_display must be rendered for missing_nested_bay")
        self.assertIn('server-001', content,
                      "device name must be rendered")
        self.assertIn('cage-0', content,
                      "cage name must be rendered")
        # Compatibility Mismatches section must be absent
        self.assertNotIn(_MISMATCH_SECTION, content,
                         "Compatibility Mismatches section must be absent for bay-only failure")

    # =========================================================================
    # T8b — FAILED + bay_errors (missing_switch_bay)
    # =========================================================================

    def test_t8b_bay_errors_missing_switch_bay_shows_bay_section(self):
        """
        T8b: Bay Configuration Errors section is visible when mismatch_report
        contains bay_errors with error_type=missing_switch_bay.
        """
        self._make_generation_state(
            status=GenerationStatusChoices.FAILED,
            mismatch_report={'bay_errors': [{
                'error_type': 'missing_switch_bay',
                'device': 'leaf-01',
                'port': 'Ethernet1/1',
                'zone': 'fe-leaf-downlinks',
                'connection_id': 42,
                'hint': 'Run populate_transceiver_bays to add ModuleBayTemplates to switch DeviceTypes.',
            }]},
        )
        content = self._get_detail()
        self.assertIn(_PANEL_HEADING, content)
        self.assertIn(_BAY_SECTION, content)
        self.assertIn('Missing Switch Port Bay', content,
                      "error_type_display must be rendered for missing_switch_bay")
        self.assertIn('leaf-01', content,
                      "device name must be rendered")
        self.assertIn('Ethernet1/1', content,
                      "port name must be rendered in bay_or_port column")

    # =========================================================================
    # T9 — Deleted connection renders fallback label
    # =========================================================================

    def test_t9_deleted_connection_renders_fallback_label(self):
        """
        T9: When connection_id in mismatch_report refers to a nonexistent PK,
        the view must render a fallback label '#<pk>' rather than crashing.
        """
        nonexistent_pk = 999999
        self._make_generation_state(
            status=GenerationStatusChoices.FAILED,
            mismatch_report={'mismatches': [{
                'connection_id': nonexistent_pk,
                'server_device': 'COMPAT-SRV',
                'switch_port': 'fe-leaf-downlinks',
                'mismatch_type': 'cage_type',
                'server_end': 'SFP28',
                'switch_end': 'QSFP28',
            }]},
        )
        response = self.client.get(_detail_url(self.plan.pk))
        self.assertEqual(response.status_code, 200,
                         "Page must not crash for deleted connection reference")
        content = response.content.decode()
        self.assertIn(_PANEL_HEADING, content)
        self.assertIn(f'#{nonexistent_pk}', content,
                      "Fallback label #<pk> must be rendered for deleted connection")

    # =========================================================================
    # T10 — RBAC: user without view permission → 302/403
    # =========================================================================

    def test_t10_no_permission_denied(self):
        """
        T10: Unauthenticated user or user without view_topologyplan permission
        cannot access the plan detail page (redirected to login or 403).
        """
        self.client.logout()
        response = self.client.get(_detail_url(self.plan.pk))
        # NetBox redirects unauthenticated users to login (302) or returns 403
        self.assertIn(response.status_code, [302, 403],
                      "Unauthenticated user must not access plan detail page")

    def test_t10b_authenticated_no_permission_denied(self):
        """
        T10b: Authenticated user with no permissions receives 403.
        """
        self.client.login(username='report-noperms', password='testpass123')
        response = self.client.get(_detail_url(self.plan.pk))
        self.assertEqual(response.status_code, 403,
                         "User without view permission must receive 403")

    # =========================================================================
    # T11 — RBAC: user with ObjectPermission → 200 and panel visible
    # =========================================================================

    def test_t11_object_permission_sees_report(self):
        """
        T11: User with ObjectPermission for view_topologyplan can access the
        detail page and sees the failure report panel.
        """
        conn = self._make_connection('fe-conn-rbac')
        self._make_generation_state(
            status=GenerationStatusChoices.FAILED,
            mismatch_report={'mismatches': [{
                'connection_id': conn.pk,
                'server_device': 'COMPAT-SRV',
                'switch_port': 'fe-leaf-downlinks',
                'mismatch_type': 'cage_type',
                'server_end': 'SFP28',
                'switch_end': 'QSFP28',
            }]},
        )

        content_type = ContentType.objects.get_for_model(TopologyPlan)
        perm = ObjectPermission.objects.create(
            name='compat-report-view-perm',
            actions=['view'],
        )
        perm.object_types.add(content_type)
        perm.users.add(self.regular_user)

        self.client.login(username='report-noperms', password='testpass123')
        response = self.client.get(_detail_url(self.plan.pk))
        self.assertEqual(response.status_code, 200,
                         "User with ObjectPermission must access plan detail page")
        content = response.content.decode()
        self.assertIn(_PANEL_HEADING, content,
                      "User with ObjectPermission must see the failure report panel")
