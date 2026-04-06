"""
Phase 3 RED tests — BOM UI panel and CSV download (#382).

Tests for:
  - BOM summary panel on the topology plan detail page
  - CSV download endpoint (TopologyPlanBOMCSVView)
  - RBAC enforcement on both surfaces

All tests in this file are expected to FAIL (RED) until Phase 4 implements:
  - render_bom_csv() in bom_export.py
  - plan_bom context injection in TopologyPlanView.get_extra_context()
  - TopologyPlanBOMCSVView view class
  - URL registration for topologyplan_bom_csv
  - BOM panel card in topologyplan.html
  - CSV download button in topologyplan.html

Spec: #385
Parent: #382
Epic: #349
"""
from __future__ import annotations

import csv
import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse, NoReverseMatch

from users.models import ObjectPermission

from dcim.models import (
    Device, DeviceRole, DeviceType, Manufacturer, Module, ModuleBay,
    ModuleType, Site,
)

from netbox_hedgehog.choices import GenerationStatusChoices
from netbox_hedgehog.models.topology_planning import GenerationState, TopologyPlan

User = get_user_model()

_DETAIL_URL_NAME = 'plugins:netbox_hedgehog:topologyplan_detail'
_CSV_URL_NAME = 'plugins:netbox_hedgehog:topologyplan_bom_csv'
_BOM_PANEL_HEADING = 'Bill of Materials (Generated)'
_SUPPRESSED_FOOTNOTE = 'Suppressed switch-side cable assembly modules (DAC/ACC):'
_EMPTY_STATE_MSG = 'No module line items for this plan'
_CSV_BUTTON_TEXT = 'Download BOM (CSV)'


def _detail_url(pk):
    return reverse(_DETAIL_URL_NAME, args=[pk])


# ---------------------------------------------------------------------------
# Shared fixture mixin
# ---------------------------------------------------------------------------

class _BOMUIFixtureMixin:
    """
    Shared setUpTestData for all BOM UI test classes.
    Uses get_or_create for shared infra to be safe with --keepdb.
    """

    @classmethod
    def setUpTestData(cls):
        cls.mfr, _ = Manufacturer.objects.get_or_create(
            name='BOM-UI-Vendor', defaults={'slug': 'bom-ui-vendor'},
        )
        cls.nic_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-UI-NIC-100G',
            defaults={'attribute_data': {
                'cage_type': 'QSFP28', 'medium': 'MMF',
                'connector': 'LC', 'standard': 'TEST-SR4',
            }},
        )
        # slug='server' is required — _classify_module checks role.slug == 'server'
        cls.server_role, _ = DeviceRole.objects.get_or_create(
            slug='server',
            defaults={'name': 'Server', 'color': 'aa1409'},
        )
        cls.site, _ = Site.objects.get_or_create(
            name='BOM-UI-Test-Site', defaults={'slug': 'bom-ui-test-site'},
        )
        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-UI-Server-DT',
            defaults={'slug': 'bom-ui-server-dt'},
        )
        cls.superuser, _ = User.objects.get_or_create(
            username='bom-ui-admin',
            defaults={'is_staff': True, 'is_superuser': True},
        )
        cls.superuser.set_password('testpass123')
        cls.superuser.save()

        cls.noperm_user, _ = User.objects.get_or_create(
            username='bom-ui-noperms',
            defaults={'is_staff': False, 'is_superuser': False},
        )
        cls.noperm_user.set_password('testpass123')
        cls.noperm_user.save()

        cls.view_user, _ = User.objects.get_or_create(
            username='bom-ui-viewer',
            defaults={'is_staff': False, 'is_superuser': False},
        )
        cls.view_user.set_password('testpass123')
        cls.view_user.save()
        # NetBox uses ObjectPermissionBackend (no ModelBackend) — grant ObjectPermission.
        # Also add model-level permission per NetBox's "additive" pattern.
        perm = Permission.objects.get(
            content_type__app_label='netbox_hedgehog',
            codename='view_topologyplan',
        )
        cls.view_user.user_permissions.add(perm)
        ct = ContentType.objects.get_for_model(TopologyPlan)
        obj_perm, _ = ObjectPermission.objects.get_or_create(
            name='bom-ui-viewer-view-topologyplan',
            defaults={'actions': ['view']},
        )
        obj_perm.object_types.set([ct])
        obj_perm.users.add(cls.view_user)

    # -- plan helpers --

    def _make_generated_plan(self, name):
        plan = TopologyPlan.objects.create(name=name)
        GenerationState.objects.create(
            plan=plan,
            status=GenerationStatusChoices.GENERATED,
            device_count=0, interface_count=0, cable_count=0,
            snapshot={},
        )
        return plan

    def _make_plan_with_status(self, name, status):
        plan = TopologyPlan.objects.create(name=name)
        GenerationState.objects.create(
            plan=plan,
            status=status,
            device_count=0, interface_count=0, cable_count=0,
            snapshot={},
        )
        return plan

    def _make_plan_no_state(self, name):
        return TopologyPlan.objects.create(name=name)

    def _add_nic_module(self, plan):
        """Create a Device + ModuleBay + Module tagged to the plan."""
        device = Device.objects.create(
            name=f'bom-ui-dev-{plan.pk}-{id(plan)}',
            device_type=self.server_dt,
            role=self.server_role,
            site=self.site,
            status='planned',
            custom_field_data={'hedgehog_plan_id': str(plan.pk)},
        )
        bay = ModuleBay.objects.create(device=device, name='fe')
        Module.objects.create(
            device=device, module_bay=bay,
            module_type=self.nic_mt, status='active',
        )
        return device


# ---------------------------------------------------------------------------
# Class 1 — BOM panel on plan detail view
# ---------------------------------------------------------------------------

class BOMPanelDetailViewTestCase(_BOMUIFixtureMixin, TestCase):
    """
    Tests that the BOM summary panel appears/disappears based on
    GenerationState.status and contains correct content.
    Uses superuser to avoid permission noise.
    """

    def setUp(self):
        self.client = Client()
        self.client.login(username='bom-ui-admin', password='testpass123')

    # T1 — Panel present when GENERATED with modules
    def test_t1_bom_panel_present_when_generated_with_modules(self):
        """T1: BOM panel heading is rendered when status=GENERATED and modules exist."""
        plan = self._make_generated_plan('T1-bom-panel')
        self._add_nic_module(plan)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn(_BOM_PANEL_HEADING, response.content.decode(),
                      "BOM panel heading must be present when GENERATED with modules")

    # T2 — Panel absent when FAILED
    def test_t2_bom_panel_absent_when_failed(self):
        """T2: BOM panel is absent when generation status is FAILED."""
        plan = self._make_plan_with_status('T2-bom-failed', GenerationStatusChoices.FAILED)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(_BOM_PANEL_HEADING, response.content.decode(),
                         "BOM panel must be absent when status=FAILED")

    # T3 — Panel absent when no GenerationState
    def test_t3_bom_panel_absent_when_no_generation_state(self):
        """T3: BOM panel is absent when the plan has no GenerationState."""
        plan = self._make_plan_no_state('T3-bom-no-state')
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(_BOM_PANEL_HEADING, response.content.decode(),
                         "BOM panel must be absent when no GenerationState")

    # T4 — Panel absent when DIRTY
    def test_t4_bom_panel_absent_when_dirty(self):
        """T4: BOM panel is absent when status=DIRTY (plan changed since generation)."""
        plan = self._make_plan_with_status('T4-bom-dirty', GenerationStatusChoices.DIRTY)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(_BOM_PANEL_HEADING, response.content.decode(),
                         "BOM panel must be absent when status=DIRTY")

    # T5 — Panel shows correct line-item count badge
    def test_t5_bom_panel_shows_line_item_count(self):
        """T5: BOM panel badge shows correct line-item count (1 for one NIC module type)."""
        plan = self._make_generated_plan('T5-bom-count')
        self._add_nic_module(plan)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(_BOM_PANEL_HEADING, content)
        # One distinct NIC ModuleType → one line item; badge should show "1"
        self.assertIn('badge-secondary">1<', content,
                      "Line-item count badge must show 1 for one distinct ModuleType")

    # T6 — Empty BOM panel shows empty-state message
    def test_t6_empty_bom_panel_shows_empty_state_message(self):
        """T6: When GENERATED but no modules, panel shows empty-state message."""
        plan = self._make_generated_plan('T6-bom-empty')
        # No modules added
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(_BOM_PANEL_HEADING, content,
                      "Panel heading must still be present for empty BOM")
        self.assertIn(_EMPTY_STATE_MSG, content,
                      "Empty-state message must be shown when no modules exist")

    # T7 — Suppressed count footnote always present when panel is shown
    def test_t7_suppressed_count_footnote_present(self):
        """T7: Suppressed cable-assembly count footnote appears when panel is shown."""
        plan = self._make_generated_plan('T7-bom-suppress')
        self._add_nic_module(plan)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn(_SUPPRESSED_FOOTNOTE, response.content.decode(),
                      "Suppressed count footnote must appear when panel is shown")

    # T8 — CSV download button present and active when GENERATED
    def test_t8_csv_button_present_and_active_when_generated(self):
        """T8: 'Download BOM (CSV)' button is an active <a> link when GENERATED."""
        plan = self._make_generated_plan('T8-csv-button')
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(_CSV_BUTTON_TEXT, content,
                      "Download BOM (CSV) button text must be present when GENERATED")
        # Active button: the resolved URL path must appear (not the URL name)
        self.assertIn('bom.csv', content,
                      "CSV download URL path (bom.csv) must appear in active button href")

    # T9 — CSV download button disabled when not GENERATED
    def test_t9_csv_button_disabled_when_not_generated(self):
        """T9: 'Download BOM (CSV)' button is disabled when status is not GENERATED."""
        plan = self._make_plan_with_status('T9-csv-disabled', GenerationStatusChoices.FAILED)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(_CSV_BUTTON_TEXT, content,
                      "Download BOM (CSV) button text must be present (disabled) when not GENERATED")
        self.assertIn('disabled', content,
                      "Button must have disabled attribute when status is not GENERATED")


# ---------------------------------------------------------------------------
# Class 2 — CSV endpoint
# ---------------------------------------------------------------------------

class BOMCSVEndpointTestCase(_BOMUIFixtureMixin, TestCase):
    """
    Tests for the TopologyPlanBOMCSVView endpoint:
    status gate, response headers, CSV content, and precondition failures.
    Uses superuser for functionality tests.
    """

    def setUp(self):
        self.client = Client()
        self.client.login(username='bom-ui-admin', password='testpass123')

    def _csv_url(self, pk):
        return reverse(_CSV_URL_NAME, args=[pk])

    # T10 — 200 with correct Content-Type when GENERATED
    def test_t10_csv_returns_200_with_text_csv_content_type(self):
        """T10: CSV endpoint returns 200 with Content-Type text/csv when GENERATED."""
        plan = self._make_generated_plan('T10-csv-200')
        self._add_nic_module(plan)
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 200,
                         "CSV endpoint must return 200 when GENERATED")
        self.assertIn('text/csv', response.get('Content-Type', ''),
                      "Content-Type must be text/csv")

    # T11 — Content-Disposition includes attachment and bom.csv
    def test_t11_csv_content_disposition_header(self):
        """T11: Content-Disposition header includes 'attachment' and 'bom.csv'."""
        plan = self._make_generated_plan('T11-csv-disposition')
        self._add_nic_module(plan)
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        disposition = response.get('Content-Disposition', '')
        self.assertIn('attachment', disposition,
                      "Content-Disposition must contain 'attachment'")
        self.assertIn('bom.csv', disposition,
                      "Content-Disposition must contain 'bom.csv' in filename")

    # T12 — CSV body first line is the header row
    def test_t12_csv_body_contains_header_row(self):
        """T12: First non-empty line of CSV body matches expected field names."""
        plan = self._make_generated_plan('T12-csv-header')
        self._add_nic_module(plan)
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        first_line = next(
            line for line in content.splitlines() if line.strip()
        )
        expected_header = (
            'section,module_type_model,manufacturer,quantity,'
            'cage_type,medium,connector,standard,is_cable_assembly'
        )
        self.assertEqual(first_line, expected_header,
                         f"CSV header row mismatch. Got: {first_line!r}")

    # T13 — CSV body contains at least one NIC data row
    def test_t13_csv_body_contains_nic_data_row(self):
        """T13: CSV body contains at least one data row with section='nic'."""
        plan = self._make_generated_plan('T13-csv-data')
        self._add_nic_module(plan)
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        # Strip footer comment lines before parsing
        data_lines = [
            line for line in content.splitlines()
            if line.strip() and not line.startswith('#')
        ]
        reader = csv.DictReader(iter(data_lines))
        rows = list(reader)
        nic_rows = [r for r in rows if r.get('section') == 'nic']
        self.assertGreater(len(nic_rows), 0,
                           "CSV must contain at least one row with section='nic'")

    # T14 — 400 when no GenerationState
    def test_t14_csv_returns_400_when_no_generation_state(self):
        """T14: CSV endpoint returns 400 when plan has no GenerationState."""
        plan = self._make_plan_no_state('T14-csv-no-state')
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 400,
                         "CSV endpoint must return 400 when no GenerationState")

    # T15 — 400 when status is FAILED
    def test_t15_csv_returns_400_when_status_failed(self):
        """T15: CSV endpoint returns 400 when GenerationState.status=FAILED."""
        plan = self._make_plan_with_status('T15-csv-failed', GenerationStatusChoices.FAILED)
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 400,
                         "CSV endpoint must return 400 when status=FAILED")

    # T16 — 400 when status is DIRTY
    def test_t16_csv_returns_400_when_status_dirty(self):
        """T16: CSV endpoint returns 400 when GenerationState.status=DIRTY."""
        plan = self._make_plan_with_status('T16-csv-dirty', GenerationStatusChoices.DIRTY)
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 400,
                         "CSV endpoint must return 400 when status=DIRTY")


# ---------------------------------------------------------------------------
# Class 3 — RBAC
# ---------------------------------------------------------------------------

class BOMRBACTestCase(_BOMUIFixtureMixin, TestCase):
    """
    Tests permission enforcement on the plan detail view and CSV endpoint.
    """

    def setUp(self):
        self.client = Client()
        self.plan = self._make_generated_plan('RBAC-bom-plan')
        self._add_nic_module(self.plan)

    def _csv_url(self, pk):
        return reverse(_CSV_URL_NAME, args=[pk])

    # T17 — Detail view: unauthenticated → redirect to login
    def test_t17_detail_view_unauthenticated_redirects(self):
        """T17: Unauthenticated user is redirected from plan detail page."""
        # No login
        response = self.client.get(_detail_url(self.plan.pk))
        self.assertIn(response.status_code, [302, 403],
                      "Unauthenticated user must be redirected or denied")

    # T18 — Detail view: view_topologyplan → 200 + BOM panel
    def test_t18_detail_view_with_view_permission_shows_bom_panel(self):
        """T18: User with view_topologyplan sees detail page and BOM panel."""
        self.client.login(username='bom-ui-viewer', password='testpass123')
        response = self.client.get(_detail_url(self.plan.pk))
        self.assertEqual(response.status_code, 200,
                         "User with view_topologyplan must access plan detail")
        self.assertIn(_BOM_PANEL_HEADING, response.content.decode(),
                      "BOM panel must be visible to user with view_topologyplan")

    # T19 — CSV endpoint: no permission → 403
    def test_t19_csv_endpoint_without_permission_returns_403(self):
        """T19: User without view_topologyplan receives 403 from CSV endpoint."""
        self.client.login(username='bom-ui-noperms', password='testpass123')
        response = self.client.get(self._csv_url(self.plan.pk))
        self.assertEqual(response.status_code, 403,
                         "User without view_topologyplan must receive 403 from CSV endpoint")

    # T20 — CSV endpoint: view_topologyplan → 200
    def test_t20_csv_endpoint_with_view_permission_returns_200(self):
        """T20: User with view_topologyplan receives 200 from CSV endpoint."""
        self.client.login(username='bom-ui-viewer', password='testpass123')
        response = self.client.get(self._csv_url(self.plan.pk))
        self.assertEqual(response.status_code, 200,
                         "User with view_topologyplan must receive 200 from CSV endpoint")
