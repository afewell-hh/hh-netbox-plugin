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
        # NetBox uses ObjectPermissionBackend (no ModelBackend) — ObjectPermission alone
        # is sufficient. Model-level user_permissions.add() has no effect and is omitted
        # so that positive tests verify the real RBAC boundary.
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
        # One distinct NIC ModuleType → badge shows "N devices · 1 modules"
        self.assertIn('1 modules', content,
                      "Badge must contain '1 modules' for one distinct ModuleType")

    def test_t5b_bom_panel_shows_module_description_when_present(self):
        """T5b: BOM panel renders module description under the model name when available."""
        self.nic_mt.description = 'Built-in/native RJ45 port placeholder - no transceiver needed'
        self.nic_mt.save(update_fields=['description'])
        plan = self._make_generated_plan('T5b-bom-desc')
        self._add_nic_module(plan)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.nic_mt.model, content)
        self.assertIn('no transceiver needed', content.lower())

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
            'section,module_type_model,module_type_description,hedgehog_class,manufacturer,quantity,'
            'cage_type,medium,connector,standard,'
            'reach_class,wavelength_nm,host_lane_count,host_serdes_gbps_per_lane,'
            'optical_lane_pattern,gearbox_present,cable_assembly_type,breakout_topology,'
            'is_cable_assembly'
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

    def test_t13b_csv_body_contains_module_description_when_present(self):
        """T13b: CSV body includes module_type_description for module rows when present."""
        self.nic_mt.description = 'Built-in/native RJ45 port placeholder - no transceiver needed'
        self.nic_mt.save(update_fields=['description'])
        plan = self._make_generated_plan('T13b-csv-desc')
        self._add_nic_module(plan)
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        data_lines = [
            line for line in response.content.decode('utf-8').splitlines()
            if line.strip() and not line.startswith('#')
        ]
        rows = list(csv.DictReader(iter(data_lines)))
        nic_rows = [r for r in rows if r.get('section') == 'nic']
        self.assertEqual(
            nic_rows[0].get('module_type_description'),
            'Built-in/native RJ45 port placeholder - no transceiver needed',
        )

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


# ---------------------------------------------------------------------------
# BD-T13–BD-T18: Base-device UI tests (DIET-523 RED)
# ---------------------------------------------------------------------------

class BOMBaseDeviceUITestCase(_BOMUIFixtureMixin, TestCase):
    """
    DIET-523 Phase 3 RED tests for base-device UI in the BOM panel.

    All tests MUST FAIL until the template renders "Base Devices" and
    "Modules / Pluggables" sub-tables and the badge switches to
    "N devices · M modules" format.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Extra objects needed for base-device UI tests
        cls.leaf_role, _ = DeviceRole.objects.get_or_create(
            slug='leaf',
            defaults={'name': 'Leaf', 'color': '2196f3'},
        )
        cls.switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-UI-Switch-DT',
            defaults={'slug': 'bom-ui-switch-dt'},
        )

    _device_counter = 0

    def _add_server_device(self, plan, hedgehog_class=''):
        """Create a Device with role=server_role tagged to the plan (no modules)."""
        BOMBaseDeviceUITestCase._device_counter += 1
        dev = Device.objects.create(
            name=f'bd-ui-srv-{plan.pk}-{BOMBaseDeviceUITestCase._device_counter}',
            device_type=self.server_dt,
            role=self.server_role,
            site=self.site,
            status='planned',
            custom_field_data={'hedgehog_plan_id': str(plan.pk)},
        )
        if hedgehog_class:
            dev.custom_field_data['hedgehog_class'] = hedgehog_class
            dev.save()
        return dev

    def _add_switch_device(self, plan):
        """Create a Device with role=leaf_role tagged to the plan (no modules)."""
        BOMBaseDeviceUITestCase._device_counter += 1
        return Device.objects.create(
            name=f'bd-ui-sw-{plan.pk}-{BOMBaseDeviceUITestCase._device_counter}',
            device_type=self.switch_dt,
            role=self.leaf_role,
            site=self.site,
            status='planned',
            custom_field_data={'hedgehog_plan_id': str(plan.pk)},
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='bom-ui-admin', password='testpass123')

    # BD-T13: "Base Devices" sub-table heading rendered
    def test_bd_t13_base_devices_sub_table_heading_present(self):
        """BD-T13: Plan detail page renders 'Base Devices' sub-table heading in BOM panel."""
        plan = self._make_generated_plan('BD-T13-heading')
        self._add_server_device(plan, hedgehog_class='be-rail-leaf')
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Base Devices',
            response.content.decode(),
            "BOM panel must contain 'Base Devices' sub-table heading (DIET-523 not implemented)",
        )

    # BD-T14: "Modules / Pluggables" sub-table heading rendered
    def test_bd_t14_modules_pluggables_sub_table_heading_present(self):
        """BD-T14: Plan detail page renders 'Modules / Pluggables' sub-table heading."""
        plan = self._make_generated_plan('BD-T14-mod-heading')
        self._add_nic_module(plan)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Modules / Pluggables',
            response.content.decode(),
            "BOM panel must contain 'Modules / Pluggables' sub-table heading (DIET-523 not implemented)",
        )

    # BD-T15: Badge shows "N devices · M modules" format
    def test_bd_t15_badge_shows_devices_and_modules_format(self):
        """BD-T15: After adding 2 explicit server devices and 1 NIC module (which also
        creates a device), badge contains device quantity sum and module quantity sum.
        _add_nic_module creates 1 device + 1 module, _add_server_device adds 2 more
        devices → 3 devices total, 1 module total."""
        plan = self._make_generated_plan('BD-T15-badge')
        self._add_server_device(plan, hedgehog_class='cls-a')
        self._add_server_device(plan, hedgehog_class='cls-b')
        self._add_nic_module(plan)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Badge must contain both device qty sum and module qty sum
        self.assertIn(
            '3 devices',
            content,
            "Badge must contain device quantity sum (3 = 2 explicit + 1 from _add_nic_module)",
        )
        self.assertIn(
            '1 modules',
            content,
            "Badge must contain '1 modules' count (DIET-523 not implemented)",
        )

    # BD-T16: Empty devices → Base Devices empty-state message
    def test_bd_t16_base_devices_empty_state_message(self):
        """BD-T16: GENERATED plan with no devices shows Base Devices empty-state message."""
        plan = self._make_generated_plan('BD-T16-empty-devs')
        # No devices, no modules
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'No base devices generated for this plan.',
            response.content.decode(),
            "Empty base_device_items must display the empty-state message (DIET-523 not implemented)",
        )

    # BD-T17: Existing module rows still visible (regression)
    def test_bd_t17_module_rows_still_present(self):
        """BD-T17: Regression guard — existing NIC module rows still appear after DIET-523 changes."""
        plan = self._make_generated_plan('BD-T17-module-reg')
        self._add_nic_module(plan)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'BOM-UI-NIC-100G',
            response.content.decode(),
            "Module rows must still be rendered in the BOM panel (regression guard)",
        )

    # BD-T18: Suppressed footnote still present (regression)
    def test_bd_t18_suppressed_footnote_still_present(self):
        """BD-T18: Regression guard — suppressed cable-assembly footnote still appears."""
        plan = self._make_generated_plan('BD-T18-suppress-reg')
        self._add_nic_module(plan)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            _SUPPRESSED_FOOTNOTE,
            response.content.decode(),
            "Suppressed cable-assembly footnote must still be rendered (regression guard)",
        )


# ---------------------------------------------------------------------------
# BD-T19–BD-T24: Base-device CSV tests (DIET-523 RED)
# ---------------------------------------------------------------------------

class BOMBaseDeviceCSVTestCase(_BOMUIFixtureMixin, TestCase):
    """
    DIET-523 Phase 3 RED tests for base-device rows and new hedgehog_class column
    in the CSV download endpoint.

    All tests MUST FAIL until the CSV renderer gains hedgehog_class column and
    base-device rows are prepended before module rows.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.leaf_role, _ = DeviceRole.objects.get_or_create(
            slug='leaf',
            defaults={'name': 'Leaf', 'color': '2196f3'},
        )
        cls.switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-UI-Switch-DT',
            defaults={'slug': 'bom-ui-switch-dt'},
        )

    _csv_device_counter = 0

    def _add_server_device(self, plan, hedgehog_class=''):
        """Create a Device with role=server_role tagged to the plan (no modules)."""
        BOMBaseDeviceCSVTestCase._csv_device_counter += 1
        dev = Device.objects.create(
            name=f'bd-csv-srv-{plan.pk}-{BOMBaseDeviceCSVTestCase._csv_device_counter}',
            device_type=self.server_dt,
            role=self.server_role,
            site=self.site,
            status='planned',
            custom_field_data={'hedgehog_plan_id': str(plan.pk)},
        )
        if hedgehog_class:
            dev.custom_field_data['hedgehog_class'] = hedgehog_class
            dev.save()
        return dev

    def _csv_url(self, pk):
        return reverse(_CSV_URL_NAME, args=[pk])

    def setUp(self):
        self.client = Client()
        self.client.login(username='bom-ui-admin', password='testpass123')

    # BD-T19: CSV header includes hedgehog_class between module_type_model and manufacturer
    def test_bd_t19_csv_header_includes_hedgehog_class_column(self):
        """BD-T19: CSV header includes 'hedgehog_class' column between
        'module_type_model' and 'manufacturer'."""
        plan = self._make_generated_plan('BD-T19-csv-header')
        self._add_nic_module(plan)
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        first_line = next(line for line in content.splitlines() if line.strip())
        expected_header = (
            'section,module_type_model,module_type_description,hedgehog_class,manufacturer,quantity,'
            'cage_type,medium,connector,standard,'
            'reach_class,wavelength_nm,host_lane_count,host_serdes_gbps_per_lane,'
            'optical_lane_pattern,gearbox_present,cable_assembly_type,breakout_topology,'
            'is_cable_assembly'
        )
        self.assertEqual(
            first_line, expected_header,
            f"CSV header must include hedgehog_class column. Got: {first_line!r}",
        )

    # BD-T20: Base-device rows appear before module rows
    def test_bd_t20_base_device_rows_before_module_rows(self):
        """BD-T20: First non-header data row has a device section ('server' or 'switch'),
        not 'nic' — i.e., base-device rows are prepended before module rows."""
        plan = self._make_generated_plan('BD-T20-order')
        self._add_server_device(plan, hedgehog_class='cls-a')
        self._add_nic_module(plan)
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        data_lines = [
            line for line in content.splitlines()
            if line.strip() and not line.startswith('#')
        ]
        reader = csv.DictReader(iter(data_lines))
        rows = list(reader)
        self.assertGreater(len(rows), 0)
        first_section = rows[0].get('section', '')
        self.assertIn(
            first_section, ('server', 'switch'),
            f"First data row must be a base-device row (server/switch), got: {first_section!r}",
        )

    # BD-T21: Base-device row uses device_type_model in module_type_model column
    def test_bd_t21_base_device_row_device_type_model_in_module_type_model_column(self):
        """BD-T21: Base-device CSV row has device_type_model value in module_type_model column."""
        plan = self._make_generated_plan('BD-T21-dt-model')
        self._add_server_device(plan, hedgehog_class='cls-a')
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        data_lines = [
            line for line in content.splitlines()
            if line.strip() and not line.startswith('#')
        ]
        reader = csv.DictReader(iter(data_lines))
        rows = list(reader)
        device_rows = [r for r in rows if r.get('section') in ('server', 'switch')]
        self.assertGreater(len(device_rows), 0)
        self.assertEqual(
            device_rows[0]['module_type_model'],
            self.server_dt.model,
            "module_type_model column must hold device_type_model for base-device rows",
        )

    # BD-T22: Base-device row has empty string for transceiver-specific columns
    def test_bd_t22_base_device_row_transceiver_columns_empty(self):
        """BD-T22: Base-device CSV row has empty string for all transceiver-specific columns
        (cage_type, medium, connector, standard, etc.)."""
        plan = self._make_generated_plan('BD-T22-empty-xcvr')
        self._add_server_device(plan, hedgehog_class='cls-a')
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        data_lines = [
            line for line in content.splitlines()
            if line.strip() and not line.startswith('#')
        ]
        reader = csv.DictReader(iter(data_lines))
        rows = list(reader)
        device_rows = [r for r in rows if r.get('section') in ('server', 'switch')]
        self.assertGreater(len(device_rows), 0)
        row = device_rows[0]
        for col in ('cage_type', 'medium', 'connector', 'standard',
                    'reach_class', 'wavelength_nm'):
            self.assertEqual(
                row.get(col, None), '',
                f"Base-device row must have empty string for {col!r}, got {row.get(col)!r}",
            )

    # BD-T23: Module rows have empty string in hedgehog_class column
    def test_bd_t23_module_rows_have_empty_hedgehog_class(self):
        """BD-T23: Module rows in CSV have empty string in the hedgehog_class column."""
        plan = self._make_generated_plan('BD-T23-mod-no-class')
        self._add_nic_module(plan)
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        data_lines = [
            line for line in content.splitlines()
            if line.strip() and not line.startswith('#')
        ]
        reader = csv.DictReader(iter(data_lines))
        rows = list(reader)
        module_rows = [r for r in rows if r.get('section') == 'nic']
        self.assertGreater(len(module_rows), 0)
        self.assertEqual(
            module_rows[0].get('hedgehog_class', None), '',
            "Module rows must have empty string in hedgehog_class column",
        )

    # BD-T24: Footer suppressed count unchanged (regression)
    def test_bd_t24_suppressed_footer_unchanged(self):
        """BD-T24: Regression guard — '# suppressed_switch_cable_assembly_count,N' footer
        still appears in CSV after DIET-523 changes."""
        plan = self._make_generated_plan('BD-T24-footer')
        self._add_nic_module(plan)
        response = self.client.get(self._csv_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        footer_line = next(
            (l for l in content.splitlines()
             if l.startswith('# suppressed_switch_cable_assembly_count,')),
            None,
        )
        self.assertIsNotNone(
            footer_line,
            "Footer line '# suppressed_switch_cable_assembly_count,N' must still be present",
        )
