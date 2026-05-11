"""
Phase 3 RED tests — per-device BOM CSV endpoint and template button (#389).

Tests for:
  - TopologyPlanBOMPerDeviceCSVView (endpoint success/failure/RBAC)
  - Per-device download button visibility on the plan detail page
  - Regression guard: aggregate BOM panel and CSV endpoint remain unchanged

All tests in this file are expected to FAIL (RED) until Phase 4 implements:
  - get_plan_bom_by_device() and render_bom_per_device_csv() in bom_export.py
  - TopologyPlanBOMPerDeviceCSVView in views/topology_planning.py
  - URL topologyplan_bom_per_device_csv in urls.py
  - Per-device download button in topologyplan.html

Spec: #392
Parent: #389
Epic: #349
"""
from __future__ import annotations

import csv

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
_AGGREGATE_CSV_URL_NAME = 'plugins:netbox_hedgehog:topologyplan_bom_csv'
_PER_DEVICE_CSV_URL_NAME = 'plugins:netbox_hedgehog:topologyplan_bom_per_device_csv'

_PER_DEVICE_BUTTON_TEXT = 'Download Per-Device BOM (CSV)'
_PER_DEVICE_CSV_FILENAME_FRAGMENT = 'bom-per-device.csv'
_PER_DEVICE_CSV_HEADER = (
    'device_name,hedgehog_class,device_role,section,'
    'module_type_model,manufacturer,quantity,'
    'cage_type,medium,connector,standard,'
    'reach_class,wavelength_nm,host_lane_count,host_serdes_gbps_per_lane,'
    'optical_lane_pattern,gearbox_present,cable_assembly_type,breakout_topology,'
    'is_cable_assembly'
)

_AGGREGATE_BOM_PANEL_HEADING = 'Bill of Materials (Generated)'


def _detail_url(pk):
    return reverse(_DETAIL_URL_NAME, args=[pk])


# ---------------------------------------------------------------------------
# Shared fixture mixin (distinct names from test_bom_ui.py to avoid --keepdb conflicts)
# ---------------------------------------------------------------------------

class _BOMPerDeviceUIFixtureMixin:
    """
    Shared setUpTestData for per-device BOM UI test classes.
    Uses 'bom-pd-' prefix throughout to avoid conflicts with bom_ui fixtures
    when running with --keepdb.
    """

    @classmethod
    def setUpTestData(cls):
        cls.mfr, _ = Manufacturer.objects.get_or_create(
            name='BOM-PD-Vendor', defaults={'slug': 'bom-pd-vendor'},
        )
        cls.nic_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-PD-NIC-100G',
            defaults={'attribute_data': {
                'cage_type': 'QSFP28', 'medium': 'MMF',
                'connector': 'LC', 'standard': 'PD-SR4',
            }},
        )
        cls.server_role, _ = DeviceRole.objects.get_or_create(
            slug='server',
            defaults={'name': 'Server', 'color': 'aa1409'},
        )
        cls.site, _ = Site.objects.get_or_create(
            name='BOM-PD-Test-Site', defaults={'slug': 'bom-pd-test-site'},
        )
        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-PD-Server-DT',
            defaults={'slug': 'bom-pd-server-dt'},
        )
        cls.superuser, _ = User.objects.get_or_create(
            username='bom-pd-admin',
            defaults={'is_staff': True, 'is_superuser': True},
        )
        cls.superuser.set_password('testpass123')
        cls.superuser.save()

        cls.noperm_user, _ = User.objects.get_or_create(
            username='bom-pd-noperms',
            defaults={'is_staff': False, 'is_superuser': False},
        )
        cls.noperm_user.set_password('testpass123')
        cls.noperm_user.save()

        cls.view_user, _ = User.objects.get_or_create(
            username='bom-pd-viewer',
            defaults={'is_staff': False, 'is_superuser': False},
        )
        cls.view_user.set_password('testpass123')
        cls.view_user.save()

        ct = ContentType.objects.get_for_model(TopologyPlan)
        obj_perm, _ = ObjectPermission.objects.get_or_create(
            name='bom-pd-viewer-view-topologyplan',
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

    def _add_nic_module(self, plan, hedgehog_class='pd-test-class', suffix=''):
        """Create a Device + ModuleBay + Module tagged to the plan."""
        device = Device.objects.create(
            name=f'bom-pd-dev-{plan.pk}-{suffix or id(plan)}',
            device_type=self.server_dt,
            role=self.server_role,
            site=self.site,
            status='planned',
            custom_field_data={
                'hedgehog_plan_id': str(plan.pk),
                'hedgehog_class': hedgehog_class,
            },
        )
        bay = ModuleBay.objects.create(device=device, name='fe')
        Module.objects.create(
            device=device, module_bay=bay,
            module_type=self.nic_mt, status='active',
        )
        return device

    # -- URL helpers --

    def _per_device_csv_url(self, pk):
        return reverse(_PER_DEVICE_CSV_URL_NAME, args=[pk])

    def _aggregate_csv_url(self, pk):
        return reverse(_AGGREGATE_CSV_URL_NAME, args=[pk])


# ---------------------------------------------------------------------------
# Class 1 — Per-device CSV endpoint
# ---------------------------------------------------------------------------

class BOMPerDeviceCSVEndpointTestCase(_BOMPerDeviceUIFixtureMixin, TestCase):
    """
    Tests for TopologyPlanBOMPerDeviceCSVView:
    status gate, response headers, CSV content, and precondition failures.
    Uses superuser to avoid permission noise.
    """

    def setUp(self):
        self.client = Client()
        self.client.login(username='bom-pd-admin', password='testpass123')
        self.plan = self._make_generated_plan('U-endpoint-plan')
        self._add_nic_module(self.plan, hedgehog_class='class-a', suffix='1')
        self._add_nic_module(self.plan, hedgehog_class='class-b', suffix='2')

    # U1
    def test_u1_returns_200_when_generated(self):
        """U1: Per-device CSV endpoint returns 200 when plan is GENERATED."""
        response = self.client.get(self._per_device_csv_url(self.plan.pk))
        self.assertEqual(response.status_code, 200,
                         "Per-device CSV endpoint must return 200 when GENERATED")

    # U2
    def test_u2_content_type_is_text_csv(self):
        """U2: Content-Type contains text/csv."""
        response = self.client.get(self._per_device_csv_url(self.plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response.get('Content-Type', ''),
                      "Content-Type must be text/csv")

    # U3
    def test_u3_content_disposition_attachment_filename(self):
        """U3: Content-Disposition contains 'attachment' and 'bom-per-device.csv'."""
        response = self.client.get(self._per_device_csv_url(self.plan.pk))
        self.assertEqual(response.status_code, 200)
        disposition = response.get('Content-Disposition', '')
        self.assertIn('attachment', disposition,
                      "Content-Disposition must contain 'attachment'")
        self.assertIn(_PER_DEVICE_CSV_FILENAME_FRAGMENT, disposition,
                      f"Content-Disposition must contain '{_PER_DEVICE_CSV_FILENAME_FRAGMENT}'")

    # U4
    def test_u4_csv_header_row_matches_spec(self):
        """U4: First non-empty line of CSV body matches the 12-column header spec."""
        response = self.client.get(self._per_device_csv_url(self.plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        first_line = next(line for line in content.splitlines() if line.strip())
        self.assertEqual(first_line, _PER_DEVICE_CSV_HEADER,
                         f"CSV header mismatch. Got: {first_line!r}")

    # U5
    def test_u5_csv_rows_contain_device_name_and_hedgehog_class(self):
        """U5: At least one data row has non-empty device_name and hedgehog_class."""
        response = self.client.get(self._per_device_csv_url(self.plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        data_lines = [
            l for l in content.splitlines()
            if l.strip() and not l.startswith('#')
        ]
        reader = csv.DictReader(iter(data_lines))
        rows = list(reader)
        self.assertGreater(len(rows), 0)
        self.assertNotEqual(rows[0]['device_name'], '',
                            "device_name column must be non-empty")
        self.assertNotEqual(rows[0]['hedgehog_class'], '',
                            "hedgehog_class column must be non-empty")

    # U6
    def test_u6_two_devices_produce_two_rows(self):
        """U6: Two-device plan with same NIC type → exactly 2 data rows (one per device)."""
        response = self.client.get(self._per_device_csv_url(self.plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        data_lines = [
            l for l in content.splitlines()
            if l.strip() and not l.startswith('#')
        ]
        reader = csv.DictReader(iter(data_lines))
        rows = list(reader)
        self.assertEqual(len(rows), 2,
                         f"Two-device plan must produce 2 per-device rows, got {len(rows)}")

    # U7
    def test_u7_returns_400_when_no_generation_state(self):
        """U7: Returns 400 when plan has no GenerationState."""
        plan = self._make_plan_no_state('U7-no-state')
        response = self.client.get(self._per_device_csv_url(plan.pk))
        self.assertEqual(response.status_code, 400,
                         "Must return 400 when no GenerationState")

    # U8
    def test_u8_returns_400_when_status_failed(self):
        """U8: Returns 400 when GenerationState.status=FAILED."""
        plan = self._make_plan_with_status('U8-failed', GenerationStatusChoices.FAILED)
        response = self.client.get(self._per_device_csv_url(plan.pk))
        self.assertEqual(response.status_code, 400,
                         "Must return 400 when status=FAILED")

    # U9
    def test_u9_returns_400_when_status_dirty(self):
        """U9: Returns 400 when GenerationState.status=DIRTY."""
        plan = self._make_plan_with_status('U9-dirty', GenerationStatusChoices.DIRTY)
        response = self.client.get(self._per_device_csv_url(plan.pk))
        self.assertEqual(response.status_code, 400,
                         "Must return 400 when status=DIRTY")


# ---------------------------------------------------------------------------
# Class 2 — RBAC
# ---------------------------------------------------------------------------

class BOMPerDeviceRBACTestCase(_BOMPerDeviceUIFixtureMixin, TestCase):
    """Tests permission enforcement on the per-device CSV endpoint."""

    def setUp(self):
        self.client = Client()
        self.plan = self._make_generated_plan('U-rbac-plan')
        self._add_nic_module(self.plan)

    # U10
    def test_u10_no_permission_returns_403(self):
        """U10: User without view_topologyplan receives 403."""
        self.client.login(username='bom-pd-noperms', password='testpass123')
        response = self.client.get(self._per_device_csv_url(self.plan.pk))
        self.assertEqual(response.status_code, 403,
                         "User without view_topologyplan must receive 403")

    # U11
    def test_u11_view_permission_returns_200(self):
        """U11: User with view_topologyplan receives 200."""
        self.client.login(username='bom-pd-viewer', password='testpass123')
        response = self.client.get(self._per_device_csv_url(self.plan.pk))
        self.assertEqual(response.status_code, 200,
                         "User with view_topologyplan must receive 200")


# ---------------------------------------------------------------------------
# Class 3 — Template button visibility
# ---------------------------------------------------------------------------

class BOMPerDeviceButtonTestCase(_BOMPerDeviceUIFixtureMixin, TestCase):
    """Top action bar should not expose the per-device download button."""

    def setUp(self):
        self.client = Client()
        self.client.login(username='bom-pd-admin', password='testpass123')

    # U12
    def test_u12_per_device_button_absent_when_generated(self):
        """U12: 'Download Per-Device BOM (CSV)' is absent from the top action bar when GENERATED."""
        plan = self._make_generated_plan('U12-pd-btn')
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn(_PER_DEVICE_BUTTON_TEXT, content,
                         f"'{_PER_DEVICE_BUTTON_TEXT}' must not be shown in the top action bar")
        self.assertNotIn(_PER_DEVICE_CSV_FILENAME_FRAGMENT, content,
                         f"'{_PER_DEVICE_CSV_FILENAME_FRAGMENT}' must not appear in the detail page action links")

    # U13
    def test_u13_per_device_button_absent_when_not_generated(self):
        """U13: 'Download Per-Device BOM (CSV)' is absent from the top action bar when not GENERATED."""
        plan = self._make_plan_with_status('U13-pd-disabled', GenerationStatusChoices.FAILED)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn(_PER_DEVICE_BUTTON_TEXT, content,
                         f"'{_PER_DEVICE_BUTTON_TEXT}' must not be shown when not GENERATED")
        self.assertNotIn(_PER_DEVICE_CSV_FILENAME_FRAGMENT, content,
                         f"'{_PER_DEVICE_CSV_FILENAME_FRAGMENT}' must not appear when not GENERATED")


# ---------------------------------------------------------------------------
# Class 4 — Regression guards
# ---------------------------------------------------------------------------

class BOMRegressionGuardTestCase(_BOMPerDeviceUIFixtureMixin, TestCase):
    """
    Regression guards: aggregate BOM panel and aggregate CSV endpoint must
    continue to work after the per-device endpoint is added.
    """

    def setUp(self):
        self.client = Client()
        self.client.login(username='bom-pd-admin', password='testpass123')
        self.plan = self._make_generated_plan('U-regression-plan')
        self._add_nic_module(self.plan)

    # U14
    def test_u14_aggregate_bom_panel_still_renders(self):
        """U14: Aggregate BOM panel heading still appears on plan detail page."""
        response = self.client.get(_detail_url(self.plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn(_AGGREGATE_BOM_PANEL_HEADING, response.content.decode(),
                      "Aggregate BOM panel must still render after per-device work")

    # U15
    def test_u15_aggregate_csv_endpoint_still_returns_200(self):
        """U15: Aggregate CSV endpoint (topologyplan_bom_csv) still returns 200."""
        response = self.client.get(self._aggregate_csv_url(self.plan.pk))
        self.assertEqual(response.status_code, 200,
                         "Aggregate CSV endpoint must still return 200 after per-device work")
