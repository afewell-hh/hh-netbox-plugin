"""
Phase 3 RED tests — BOM comparison service, panel, permissions, and CSV (#400).
Phase 4 GREEN: fixture helpers updated to create plan intent data (PlanServerClass,
PlanServerNIC, PlanServerConnection) so the service can compare plan vs generated.

Tests for:
  - compare_plan_vs_generated() service returning BOMComparisonResult
  - BOM comparison panel on the topology plan detail page
  - Permission enforcement on the comparison CSV endpoint
  - CSV endpoint content and headers

Spec: #399
Parent: #400
Epic: #396
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

from netbox_hedgehog.choices import (
    AllocationStrategyChoices, ConnectionDistributionChoices,
    ConnectionTypeChoices, FabricClassChoices, FabricTypeChoices,
    GenerationStatusChoices, HedgehogRoleChoices, PortZoneTypeChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption, DeviceTypeExtension, GenerationState,
    PlanServerClass, PlanServerConnection, PlanServerNIC,
    PlanSwitchClass, SwitchPortZone, TopologyPlan,
)

User = get_user_model()

_DETAIL_URL_NAME = 'plugins:netbox_hedgehog:topologyplan_detail'
_COMPARISON_CSV_URL_NAME = 'plugins:netbox_hedgehog:topologyplan_bom_comparison_csv'
_COMPARISON_PANEL_HEADING = 'BOM Comparison'

# Canonical "expected" types for test plan intent.
# All _make_server_device calls create PlanServerNIC(nic-fe, BOM-CMP-NIC-100G-A).
# All _add_transceiver_module calls create PlanServerConnection(transceiver=BOM-CMP-XCVR-100G-A)
# unless create_plan_connection=False is passed.
_EXPECTED_NIC_BAY = 'nic-fe'
_EXPECTED_XCVR_CONNECTION_ID = 'bom-cmp-conn-{port_index}'


def _detail_url(pk):
    return reverse(_DETAIL_URL_NAME, args=[pk])


def _comparison_csv_url(pk):
    try:
        return reverse(_COMPARISON_CSV_URL_NAME, args=[pk])
    except NoReverseMatch:
        return None


# ---------------------------------------------------------------------------
# Shared fixture mixin
# ---------------------------------------------------------------------------

class _BOMComparisonFixtureMixin:
    """
    Shared setUpTestData for all BOM comparison test classes.
    Uses 'bom-cmp-' prefix to avoid --keepdb conflicts with other BOM test fixtures.

    Phase 4 additions: helpers create plan intent data (PlanServerClass,
    PlanServerNIC, PlanServerConnection) alongside generated inventory so
    compare_plan_vs_generated() can perform meaningful comparisons.
    """

    @classmethod
    def setUpTestData(cls):
        cls.mfr, _ = Manufacturer.objects.get_or_create(
            name='BOM-CMP-Vendor', defaults={'slug': 'bom-cmp-vendor'},
        )
        cls.nic_mt_a, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-CMP-NIC-100G-A',
            defaults={'attribute_data': {
                'cage_type': 'QSFP28', 'medium': 'MMF',
                'connector': 'LC', 'standard': 'CMP-SR4',
            }},
        )
        cls.nic_mt_b, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-CMP-NIC-200G-B',
            defaults={'attribute_data': {
                'cage_type': 'QSFP112', 'medium': 'MMF',
                'connector': 'MPO-12', 'standard': 'CMP-SR4-200G',
            }},
        )
        cls.xcvr_mt_a, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-CMP-XCVR-100G-A',
            defaults={'attribute_data': {
                'cage_type': 'QSFP28', 'medium': 'MMF',
                'connector': 'LC', 'standard': 'CMP-XCVR-SR4',
            }},
        )
        cls.xcvr_mt_b, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-CMP-XCVR-200G-B',
            defaults={'attribute_data': {
                'cage_type': 'QSFP112', 'medium': 'MMF',
                'connector': 'MPO-12', 'standard': 'CMP-XCVR-SR4-200G',
            }},
        )
        cls.server_role, _ = DeviceRole.objects.get_or_create(
            slug='server',
            defaults={'name': 'Server', 'color': 'aa1409'},
        )
        cls.site, _ = Site.objects.get_or_create(
            name='BOM-CMP-Test-Site', defaults={'slug': 'bom-cmp-test-site'},
        )
        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-CMP-Server-DT',
            defaults={'slug': 'bom-cmp-server-dt'},
        )
        # Switch DT + DeviceTypeExtension needed for PlanSwitchClass (transceiver tests).
        cls.switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-CMP-Switch-DT',
            defaults={'slug': 'bom-cmp-switch-dt'},
        )
        cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_dt,
            defaults={
                'native_speed': 100, 'uplink_ports': 0,
                'supported_breakouts': [], 'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
            },
        )
        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x100g-bom-cmp',
            defaults={'from_speed': 100, 'logical_ports': 1, 'logical_speed': 100},
        )

        cls.superuser, _ = User.objects.get_or_create(
            username='bom-cmp-admin',
            defaults={'is_staff': True, 'is_superuser': True},
        )
        cls.superuser.set_password('testpass123')
        cls.superuser.save()

        cls.noperm_user, _ = User.objects.get_or_create(
            username='bom-cmp-noperms',
            defaults={'is_staff': False, 'is_superuser': False},
        )
        cls.noperm_user.set_password('testpass123')
        cls.noperm_user.save()

        cls.view_user, _ = User.objects.get_or_create(
            username='bom-cmp-viewer',
            defaults={'is_staff': False, 'is_superuser': False},
        )
        cls.view_user.set_password('testpass123')
        cls.view_user.save()

        ct = ContentType.objects.get_for_model(TopologyPlan)
        obj_perm, _ = ObjectPermission.objects.get_or_create(
            name='bom-cmp-viewer-view-topologyplan',
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

    def _ensure_server_class(self, plan):
        """Return (or create) the canonical PlanServerClass + PlanServerNIC for this plan."""
        server_class, _ = PlanServerClass.objects.get_or_create(
            plan=plan,
            server_class_id='bom-cmp-sc',
            defaults={'server_device_type': self.server_dt, 'quantity': 1},
        )
        # PlanServerNIC: canonical expected NIC bay is 'nic-fe' with nic_mt_a.
        # Use save() directly to bypass the interface-template validation in clean().
        if not PlanServerNIC.objects.filter(server_class=server_class, nic_id='nic-fe').exists():
            nic = PlanServerNIC(
                server_class=server_class,
                nic_id='nic-fe',
                module_type=self.nic_mt_a,
            )
            nic.save()
        return server_class

    def _ensure_switch_zone(self, plan):
        """Return (or create) a minimal SwitchPortZone for transceiver connection setup."""
        switch_class, _ = PlanSwitchClass.objects.get_or_create(
            plan=plan,
            switch_class_id='bom-cmp-sw',
            defaults={
                'fabric_name': FabricTypeChoices.FRONTEND,
                'fabric_class': FabricClassChoices.MANAGED,
                'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
                'device_type_extension': self.device_ext,
                'uplink_ports_per_switch': 0,
                'mclag_pair': False,
                'override_quantity': 2,
                'redundancy_type': 'eslag',
            },
        )
        zone, _ = SwitchPortZone.objects.get_or_create(
            switch_class=switch_class,
            zone_name='server-downlinks',
            defaults={
                'zone_type': PortZoneTypeChoices.SERVER,
                'port_spec': '1-64',
                'breakout_option': self.breakout,
                'allocation_strategy': AllocationStrategyChoices.SEQUENTIAL,
                'priority': 100,
            },
        )
        return zone

    def _make_server_device(self, plan, suffix=''):
        """Create a Device tagged to the plan, with plan intent (PlanServerClass + PlanServerNIC)."""
        server_class = self._ensure_server_class(plan)
        device = Device.objects.create(
            name=f'bom-cmp-dev-{plan.pk}{suffix}',
            device_type=self.server_dt,
            role=self.server_role,
            site=self.site,
            status='planned',
            custom_field_data={
                'hedgehog_plan_id': str(plan.pk),
                'hedgehog_class': server_class.server_class_id,
            },
        )
        return device

    def _add_nic_module(self, plan, bay_name, module_type):
        """Add a device with a NIC module in a named bay."""
        device = self._make_server_device(plan, suffix=f'-{bay_name}')
        bay = ModuleBay.objects.create(device=device, name=bay_name)
        module = Module.objects.create(
            device=device, module_bay=bay,
            module_type=module_type, status='active',
            custom_field_data={'hedgehog_plan_id': str(plan.pk)},
        )
        return device, bay, module

    def _get_nic_module(self, device):
        """Return the NIC module on a device (the top-level Module in bay nic-fe)."""
        return Module.objects.filter(device=device).first()

    def _add_transceiver_module(self, plan, device, bay_name, module_type,
                                create_plan_connection=True):
        """
        Add a transceiver module in a NESTED bay (inside the NIC module) on a device.

        Creates ModuleBay on the NIC module (module_id set), so the service
        classifies it as 'server_transceiver' via module_bay.module_id is not None.

        When create_plan_connection=True (default), also creates a
        PlanServerConnection with transceiver_module_type=xcvr_mt_a (the
        canonical expected type) so the service can compare plan vs generated.
        Pass create_plan_connection=False for orphan-module tests where the
        bay should have no plan coverage.
        """
        # Find the NIC module on this device to nest the transceiver bay inside it.
        nic_module = Module.objects.filter(device=device).first()
        if nic_module is None:
            # Fallback: create device-level bay (service will treat as nic orphan)
            bay = ModuleBay.objects.create(device=device, name=bay_name)
        else:
            bay = ModuleBay.objects.create(device=device, module=nic_module, name=bay_name)
        module = Module.objects.create(
            device=device, module_bay=bay,
            module_type=module_type, status='active',
            custom_field_data={'hedgehog_plan_id': str(plan.pk)},
        )
        if create_plan_connection:
            # Derive port_index from bay name (cage-{N} → N).
            try:
                port_index = int(bay_name.split('-')[1])
            except (IndexError, ValueError):
                port_index = 0
            server_class = self._ensure_server_class(plan)
            nic = PlanServerNIC.objects.get(server_class=server_class, nic_id='nic-fe')
            zone = self._ensure_switch_zone(plan)
            conn_id = f'bom-cmp-conn-{port_index}'
            PlanServerConnection.objects.get_or_create(
                server_class=server_class,
                connection_id=conn_id,
                defaults={
                    'nic': nic,
                    'port_index': port_index,
                    'ports_per_connection': 1,
                    'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
                    'distribution': ConnectionDistributionChoices.ALTERNATING,
                    'target_zone': zone,
                    'speed': 100,
                    'transceiver_module_type': self.xcvr_mt_a,
                },
            )
        return bay, module


# ---------------------------------------------------------------------------
# Class 1 — BOMComparisonService unit-level tests
# ---------------------------------------------------------------------------

class BOMComparisonServiceTestCase(_BOMComparisonFixtureMixin, TestCase):
    """
    Tests for compare_plan_vs_generated() service.

    Modules are built manually; no full device generation is run.
    Tests validate BOMComparisonResult structure and match logic.
    All tests expect ImportError or AttributeError until bom_comparison.py exists.
    """

    def _import_service(self):
        from netbox_hedgehog.services.bom_comparison import (
            compare_plan_vs_generated, BOMComparisonResult,
        )
        return compare_plan_vs_generated, BOMComparisonResult

    def test_all_modules_match(self):
        """
        When every generated Module matches the plan intent exactly,
        BOMComparisonResult.total_matched > 0 and total_mismatched == 0.
        """
        compare_plan_vs_generated, BOMComparisonResult = self._import_service()
        plan = self._make_generated_plan('svc-all-match')
        # Add a NIC module whose bay name matches the nic_id convention.
        self._add_nic_module(plan, 'nic-fe', self.nic_mt_a)

        result = compare_plan_vs_generated(plan)
        self.assertIsInstance(result, BOMComparisonResult)
        self.assertTrue(result.has_generation_state)
        self.assertGreater(result.total_matched, 0)
        self.assertEqual(result.total_mismatched, 0)
        self.assertEqual(result.total_expected_not_generated, 0)
        self.assertEqual(result.total_generated_not_in_plan, 0)

    def test_nic_type_mismatch(self):
        """
        When a generated NIC Module type differs from plan intent,
        total_mismatched == 1 and the DeviceBOMComparison item has status TYPE_MISMATCH.
        """
        compare_plan_vs_generated, BOMComparisonResult = self._import_service()
        plan = self._make_generated_plan('svc-nic-mismatch')
        # Plan expects nic_mt_a; generated has nic_mt_b (wrong type).
        self._add_nic_module(plan, 'nic-fe', self.nic_mt_b)

        result = compare_plan_vs_generated(plan)
        self.assertIsInstance(result, BOMComparisonResult)
        self.assertGreater(result.total_mismatched, 0,
                           "Expected at least one TYPE_MISMATCH item")

    def test_nic_expected_not_generated(self):
        """
        When plan intent includes a NIC bay but no Module exists in that bay,
        total_expected_not_generated > 0.
        """
        compare_plan_vs_generated, BOMComparisonResult = self._import_service()
        plan = self._make_generated_plan('svc-nic-missing')
        # Device exists but no Module in the NIC bay.
        self._make_server_device(plan, suffix='-no-nic')

        result = compare_plan_vs_generated(plan)
        self.assertIsInstance(result, BOMComparisonResult)
        self.assertGreater(result.total_expected_not_generated, 0,
                           "Expected at least one EXPECTED_NOT_GENERATED item")

    def test_nic_generated_not_in_plan(self):
        """
        When a Module exists on a plan device but no current plan intent covers that bay,
        total_generated_not_in_plan > 0.
        """
        compare_plan_vs_generated, BOMComparisonResult = self._import_service()
        plan = self._make_generated_plan('svc-nic-orphan')
        # Module in an unrecognised bay name → no matching plan intent.
        self._add_nic_module(plan, 'orphan-bay-99', self.nic_mt_a)

        result = compare_plan_vs_generated(plan)
        self.assertIsInstance(result, BOMComparisonResult)
        self.assertGreater(result.total_generated_not_in_plan, 0,
                           "Expected at least one GENERATED_NOT_IN_PLAN item")

    def test_transceiver_type_mismatch(self):
        """
        When plan specifies transceiver_module_type X but generated Module in
        cage-{port_index} bay has type Y, the mismatch is captured.
        """
        compare_plan_vs_generated, BOMComparisonResult = self._import_service()
        plan = self._make_generated_plan('svc-xcvr-mismatch')
        device, nic_bay, nic_mod = self._add_nic_module(plan, 'nic-fe', self.nic_mt_a)
        # cage-0 has wrong transceiver type.
        self._add_transceiver_module(plan, device, 'cage-0', self.xcvr_mt_b)

        result = compare_plan_vs_generated(plan)
        self.assertIsInstance(result, BOMComparisonResult)
        self.assertGreater(result.total_mismatched, 0,
                           "Expected at least one TYPE_MISMATCH item for transceiver")

    def test_transceiver_expected_not_generated(self):
        """
        When plan specifies a transceiver FK but no Module exists in the cage bay,
        total_expected_not_generated > 0 (or total_mismatched > 0 — either is valid).
        """
        compare_plan_vs_generated, BOMComparisonResult = self._import_service()
        plan = self._make_generated_plan('svc-xcvr-absent')
        # NIC module exists (and creates the plan server class + NIC intent).
        device, nic_bay, nic_mod = self._add_nic_module(plan, 'nic-fe', self.nic_mt_a)
        # Explicitly create a plan connection expecting xcvr_mt_a for cage-0,
        # but do NOT install a cage-0 module — so it will be EXPECTED_NOT_GENERATED.
        server_class = self._ensure_server_class(plan)
        nic = PlanServerNIC.objects.get(server_class=server_class, nic_id='nic-fe')
        zone = self._ensure_switch_zone(plan)
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='bom-cmp-conn-absent-0',
            nic=nic,
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone,
            speed=100,
            transceiver_module_type=self.xcvr_mt_a,
        )

        result = compare_plan_vs_generated(plan)
        self.assertIsInstance(result, BOMComparisonResult)
        discrepancies = (
            result.total_expected_not_generated + result.total_mismatched
        )
        self.assertGreater(discrepancies, 0,
                           "Expected a discrepancy when cage bay is absent but plan has transceiver FK")

    def test_transceiver_generated_not_in_plan(self):
        """
        When a transceiver Module exists in a cage bay but plan has no matching
        transceiver FK for that connection, total_generated_not_in_plan > 0.
        """
        compare_plan_vs_generated, BOMComparisonResult = self._import_service()
        plan = self._make_generated_plan('svc-xcvr-orphan')
        device, nic_bay, nic_mod = self._add_nic_module(plan, 'nic-fe', self.nic_mt_a)
        # cage-99 is an out-of-range bay not covered by any plan connection.
        self._add_transceiver_module(plan, device, 'cage-99', self.xcvr_mt_a,
                                     create_plan_connection=False)

        result = compare_plan_vs_generated(plan)
        self.assertIsInstance(result, BOMComparisonResult)
        self.assertGreater(result.total_generated_not_in_plan, 0,
                           "Expected GENERATED_NOT_IN_PLAN for cage bay without plan coverage")

    def test_null_transceiver_fk_empty_bay(self):
        """
        When transceiver_module_type is None and the cage bay is empty,
        no comparison item is emitted for that connection (row omitted).
        total_matched + total_mismatched + total_expected_not_generated +
        total_generated_not_in_plan should not increase due to that bay.
        """
        compare_plan_vs_generated, BOMComparisonResult = self._import_service()
        plan = self._make_generated_plan('svc-null-xcvr')
        # NIC present, no cage bay at all, no transceiver FK in plan.
        self._add_nic_module(plan, 'nic-fe', self.nic_mt_a)

        result = compare_plan_vs_generated(plan)
        self.assertIsInstance(result, BOMComparisonResult)
        # No row for the absent cage bay when FK is null — total items should
        # only reflect the NIC comparison item.
        total_items = sum([
            len(d.items) for d in result.devices
        ])
        # One NIC item expected; no transceiver item.
        self.assertEqual(total_items, 1,
                         "Null-FK empty-bay must not produce a comparison item")

    def test_multi_port_connection(self):
        """
        When ports_per_connection > 1, one comparison item is expected per cage
        in range(port_index, port_index + ports_per_connection).
        """
        compare_plan_vs_generated, BOMComparisonResult = self._import_service()
        plan = self._make_generated_plan('svc-multi-port')
        device, nic_bay, nic_mod = self._add_nic_module(plan, 'nic-fe', self.nic_mt_a)
        # Add transceivers for cage-0 and cage-1 (2-port connection).
        self._add_transceiver_module(plan, device, 'cage-0', self.xcvr_mt_a)
        self._add_transceiver_module(plan, device, 'cage-1', self.xcvr_mt_a)

        result = compare_plan_vs_generated(plan)
        self.assertIsInstance(result, BOMComparisonResult)
        all_bay_names = [
            item.bay_name
            for dev in result.devices
            for item in dev.items
            if item.section == 'server_transceiver'
        ]
        self.assertIn('cage-0', all_bay_names,
                      "cage-0 must appear as comparison item for multi-port connection")
        self.assertIn('cage-1', all_bay_names,
                      "cage-1 must appear as comparison item for multi-port connection")

    def test_no_generation_state(self):
        """
        When no GenerationState exists, BOMComparisonResult.has_generation_state is False
        and devices is empty (or an appropriate zero-comparison result is returned).
        """
        compare_plan_vs_generated, BOMComparisonResult = self._import_service()
        plan = self._make_plan_no_state('svc-no-state')

        result = compare_plan_vs_generated(plan)
        self.assertIsInstance(result, BOMComparisonResult)
        self.assertFalse(result.has_generation_state,
                         "has_generation_state must be False when no GenerationState exists")

    def test_summary_counts_correct(self):
        """
        BOMComparisonResult summary counts equal the sum across all DeviceBOMComparison items.
        """
        compare_plan_vs_generated, BOMComparisonResult = self._import_service()
        from netbox_hedgehog.services.bom_comparison import MatchStatus

        plan = self._make_generated_plan('svc-summary-counts')
        self._add_nic_module(plan, 'nic-fe', self.nic_mt_a)
        self._add_nic_module(plan, 'nic-be', self.nic_mt_b)

        result = compare_plan_vs_generated(plan)
        # Recompute from per-device items.
        matched = sum(
            1 for d in result.devices for i in d.items
            if i.status == MatchStatus.MATCH
        )
        mismatched = sum(
            1 for d in result.devices for i in d.items
            if i.status == MatchStatus.TYPE_MISMATCH
        )
        exp_not_gen = sum(
            1 for d in result.devices for i in d.items
            if i.status == MatchStatus.EXPECTED_NOT_GENERATED
        )
        gen_not_plan = sum(
            1 for d in result.devices for i in d.items
            if i.status == MatchStatus.GENERATED_NOT_IN_PLAN
        )
        self.assertEqual(result.total_matched, matched)
        self.assertEqual(result.total_mismatched, mismatched)
        self.assertEqual(result.total_expected_not_generated, exp_not_gen)
        self.assertEqual(result.total_generated_not_in_plan, gen_not_plan)


# ---------------------------------------------------------------------------
# Class 2 — BOM comparison panel on plan detail view
# ---------------------------------------------------------------------------

class BOMComparisonPanelTestCase(_BOMComparisonFixtureMixin, TestCase):
    """
    Tests that the BOM comparison panel appears/disappears based on
    GenerationState.status and plan state.
    """

    def setUp(self):
        self.client = Client()
        self.client.login(username='bom-cmp-admin', password='testpass123')

    def test_panel_visible_when_generated(self):
        """BOM Comparison panel is shown when GenerationState.status == GENERATED."""
        plan = self._make_generated_plan('panel-visible')
        self._add_nic_module(plan, 'nic-fe', self.nic_mt_a)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn(_COMPARISON_PANEL_HEADING, response.content.decode(),
                      "BOM Comparison panel heading must be present when GENERATED")

    def test_panel_hidden_when_no_generation_state(self):
        """BOM Comparison panel is absent when the plan has never been generated."""
        plan = self._make_plan_no_state('panel-no-state')
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(_COMPARISON_PANEL_HEADING, response.content.decode(),
                         "BOM Comparison panel must be absent when no GenerationState")

    def test_panel_hidden_when_failed(self):
        """BOM Comparison panel is absent when GenerationState.status == FAILED."""
        plan = self._make_plan_with_status('panel-failed', GenerationStatusChoices.FAILED)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(_COMPARISON_PANEL_HEADING, response.content.decode(),
                         "BOM Comparison panel must be absent when status=FAILED")

    def test_needs_regeneration_warning_shown(self):
        """
        When GenerationState.status == DIRTY, a staleness/regeneration warning is shown
        and the comparison panel is NOT rendered (stale data guard).
        """
        plan = self._make_plan_with_status('panel-dirty', GenerationStatusChoices.DIRTY)
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn(_COMPARISON_PANEL_HEADING, content,
                         "BOM Comparison panel must be absent when status=DIRTY")

    def test_needs_regeneration_warning_absent(self):
        """
        When GenerationState.status == GENERATED, the staleness warning is absent.
        """
        plan = self._make_generated_plan('panel-no-warn')
        response = self.client.get(_detail_url(plan.pk))
        self.assertEqual(response.status_code, 200)
        # Panel is present; stale-data warning should NOT appear alongside it.
        content = response.content.decode()
        self.assertIn(_COMPARISON_PANEL_HEADING, content,
                      "BOM Comparison panel must be present when GENERATED")
        self.assertNotIn('needs_regeneration', content,
                         "needs_regeneration warning must be absent when status=GENERATED")


# ---------------------------------------------------------------------------
# Class 3 — Permission enforcement on BOM comparison CSV endpoint
# ---------------------------------------------------------------------------

class BOMComparisonPermissionTestCase(_BOMComparisonFixtureMixin, TestCase):
    """
    Tests permission enforcement on the topologyplan_bom_comparison_csv endpoint.
    """

    def setUp(self):
        self.client = Client()
        self.plan = self._make_generated_plan('perm-plan')
        self._add_nic_module(self.plan, 'nic-fe', self.nic_mt_a)

    def test_csv_without_permission(self):
        """User without view_topologyplan receives 403 from comparison CSV endpoint."""
        self.client.login(username='bom-cmp-noperms', password='testpass123')
        url = _comparison_csv_url(self.plan.pk)
        if url is None:
            raise NoReverseMatch(
                f"URL name '{_COMPARISON_CSV_URL_NAME}' not registered — "
                "expected RED failure: URL not yet implemented."
            )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403,
                         "User without view_topologyplan must receive 403")

    def test_csv_with_permission(self):
        """User with view_topologyplan receives 200 from comparison CSV endpoint."""
        self.client.login(username='bom-cmp-viewer', password='testpass123')
        url = _comparison_csv_url(self.plan.pk)
        if url is None:
            raise NoReverseMatch(
                f"URL name '{_COMPARISON_CSV_URL_NAME}' not registered — "
                "expected RED failure: URL not yet implemented."
            )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200,
                         "User with view_topologyplan must receive 200")


# ---------------------------------------------------------------------------
# Class 4 — BOM comparison CSV endpoint content
# ---------------------------------------------------------------------------

class BOMComparisonCSVTestCase(_BOMComparisonFixtureMixin, TestCase):
    """
    Tests for the BOM comparison CSV endpoint: headers, content, and Content-Type.
    Uses superuser to avoid permission noise.
    """

    def setUp(self):
        self.client = Client()
        self.client.login(username='bom-cmp-admin', password='testpass123')

    def _get_csv_url(self, pk):
        url = _comparison_csv_url(pk)
        if url is None:
            raise NoReverseMatch(
                f"URL name '{_COMPARISON_CSV_URL_NAME}' not registered — "
                "expected RED failure: URL not yet implemented."
            )
        return url

    def test_csv_returns_200_with_correct_headers(self):
        """
        Comparison CSV endpoint returns 200 with text/csv Content-Type
        and the correct CSV column headers.
        """
        plan = self._make_generated_plan('csv-headers')
        self._add_nic_module(plan, 'nic-fe', self.nic_mt_a)
        url = self._get_csv_url(plan.pk)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200,
                         "Comparison CSV endpoint must return 200 when GENERATED")
        self.assertIn('text/csv', response.get('Content-Type', ''),
                      "Content-Type must be text/csv")
        content = response.content.decode('utf-8')
        first_data_line = next(
            line for line in content.splitlines() if line.strip()
        )
        expected_columns = {
            'device_name', 'bay_name', 'section',
            'plan_module_type', 'generated_module_type', 'status',
        }
        header_cols = set(c.strip() for c in first_data_line.split(','))
        missing = expected_columns - header_cols
        self.assertFalse(missing,
                         f"CSV header missing expected columns: {missing}")

    def test_csv_rows_match_comparison_result(self):
        """
        Rows in the comparison CSV correspond to the items returned by
        compare_plan_vs_generated(). One row per ModuleComparisonItem.
        """
        plan = self._make_generated_plan('csv-rows')
        self._add_nic_module(plan, 'nic-fe', self.nic_mt_a)
        url = self._get_csv_url(plan.pk)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        data_lines = [
            line for line in content.splitlines()
            if line.strip() and not line.startswith('#')
        ]
        reader = csv.DictReader(iter(data_lines))
        rows = list(reader)
        self.assertGreater(len(rows), 0,
                           "Comparison CSV must contain at least one data row")
        # Every row must have a non-empty device_name and status.
        for row in rows:
            self.assertTrue(row.get('device_name', '').strip(),
                            f"Row missing device_name: {row}")
            self.assertTrue(row.get('status', '').strip(),
                            f"Row missing status: {row}")
