"""
Phase 3 RED tests for BOM export service and management command.

All tests in this file are expected to FAIL (RED) until Phase 4 implements:
  netbox_hedgehog/services/bom_export.py
  netbox_hedgehog/management/commands/export_plan_bom.py
"""
from __future__ import annotations

import csv
import json
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from dcim.models import (
    Device, DeviceRole, DeviceType, Manufacturer, Module, ModuleBay,
    ModuleType, Site,
)

from netbox_hedgehog.choices import GenerationStatusChoices
from netbox_hedgehog.models.topology_planning import GenerationState, TopologyPlan

# This import will fail (RED) until bom_export.py is created.
from netbox_hedgehog.services.bom_export import get_plan_bom


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

class _BOMFixtureMixin:
    """Shared setUpTestData and helper methods for both test classes."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, _ = Manufacturer.objects.get_or_create(
            name='BOM-NIC-Vendor', defaults={'slug': 'bom-nic-vendor'},
        )
        cls.mfr_xcvr, _ = Manufacturer.objects.get_or_create(
            name='BOM-XCVR-Vendor', defaults={'slug': 'bom-xcvr-vendor'},
        )
        cls.nic_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-NIC-200G',
            defaults={'attribute_data': {
                'cage_type': 'QSFP112', 'medium': 'MMF',
                'connector': 'MPO-12', 'standard': 'TEST-200G',
            }},
        )
        cls.nic_mt2, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-NIC-400G',
            defaults={'attribute_data': {
                'cage_type': 'OSFP', 'medium': 'MMF',
                'connector': 'MPO-16', 'standard': 'TEST-400G',
            }},
        )
        cls.xcvr_mt_mmf, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr_xcvr, model='BOM-XCVR-MMF',
            defaults={'attribute_data': {
                'cage_type': 'QSFP112', 'medium': 'MMF',
                'connector': 'LC', 'standard': 'TEST-SR4',
            }},
        )
        cls.xcvr_mt_dac, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr_xcvr, model='BOM-XCVR-DAC',
            defaults={'attribute_data': {
                'cage_type': 'QSFP28', 'medium': 'DAC',
                'connector': 'Direct', 'standard': None,
            }},
        )
        cls.xcvr_mt_acc, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr_xcvr, model='BOM-XCVR-ACC',
            defaults={'attribute_data': {
                'cage_type': 'QSFP28', 'medium': 'ACC',
                'connector': 'Direct', 'standard': None,
            }},
        )
        cls.xcvr_mt_sparse, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr_xcvr, model='BOM-XCVR-SPARSE',
            defaults={'attribute_data': {}},
        )
        # slug='server' is required — _classify_module checks role.slug == 'server'
        cls.server_role, _ = DeviceRole.objects.get_or_create(
            name='Server', defaults={'slug': 'server', 'color': 'aa1409'},
        )
        cls.leaf_role, _ = DeviceRole.objects.get_or_create(
            name='Leaf', defaults={'slug': 'leaf', 'color': '2196f3'},
        )
        cls.site, _ = Site.objects.get_or_create(
            name='BOM-Test-Site', defaults={'slug': 'bom-test-site'},
        )
        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-Server-DT',
            defaults={'slug': 'bom-server-dt'},
        )
        cls.switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='BOM-Switch-DT',
            defaults={'slug': 'bom-switch-dt'},
        )

    # -- plan helpers --

    def _make_plan(self, name):
        return TopologyPlan.objects.create(name=name)

    def _make_plan_generated(self, name):
        plan = self._make_plan(name)
        GenerationState.objects.create(
            plan=plan, device_count=0, interface_count=0, cable_count=0,
            snapshot={}, status=GenerationStatusChoices.GENERATED,
        )
        return plan

    def _make_plan_with_status(self, name, status):
        plan = self._make_plan(name)
        GenerationState.objects.create(
            plan=plan, device_count=0, interface_count=0, cable_count=0,
            snapshot={}, status=status,
        )
        return plan

    # -- device helpers --

    def _server(self, plan, name):
        return Device.objects.create(
            name=name, device_type=self.server_dt, role=self.server_role,
            site=self.site, status='planned',
            custom_field_data={'hedgehog_plan_id': str(plan.pk)},
        )

    def _switch(self, plan, name):
        return Device.objects.create(
            name=name, device_type=self.switch_dt, role=self.leaf_role,
            site=self.site, status='planned',
            custom_field_data={'hedgehog_plan_id': str(plan.pk)},
        )

    # -- module helpers --

    def _install_nic(self, device, bay_name, mt):
        bay = ModuleBay.objects.create(device=device, name=bay_name)
        return Module.objects.create(
            device=device, module_bay=bay, module_type=mt, status='active',
        )

    def _install_nested_xcvr(self, device, nic_module, cage_name, mt):
        bay = ModuleBay.objects.create(
            device=device, module=nic_module, name=cage_name,
        )
        return Module.objects.create(
            device=device, module_bay=bay, module_type=mt, status='planned',
        )

    def _install_switch_xcvr(self, device, port_name, mt):
        bay = ModuleBay.objects.create(device=device, name=port_name)
        return Module.objects.create(
            device=device, module_bay=bay, module_type=mt, status='planned',
        )


# ---------------------------------------------------------------------------
# T1–T20: Service tests
# ---------------------------------------------------------------------------

class BOMServiceTestCase(_BOMFixtureMixin, TestCase):

    # T1
    def test_empty_plan_no_devices(self):
        plan = self._make_plan_generated('T1-empty')
        bom = get_plan_bom(plan)
        self.assertEqual(bom.line_items, ())
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 0)

    # T2
    def test_nic_module_classified_as_nic(self):
        plan = self._make_plan_generated('T2-nic')
        srv = self._server(plan, 'T2-srv')
        self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom(plan)
        self.assertEqual(len(bom.line_items), 1)
        item = bom.line_items[0]
        self.assertEqual(item.section, 'nic')
        self.assertEqual(item.quantity, 1)
        self.assertEqual(item.module_type_model, self.nic_mt.model)

    # T3
    def test_nested_transceiver_classified_as_server_transceiver(self):
        plan = self._make_plan_generated('T3-srv-xcvr')
        srv = self._server(plan, 'T3-srv')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_mmf)
        bom = get_plan_bom(plan)
        sections = [i.section for i in bom.line_items]
        self.assertIn('server_transceiver', sections)
        st = next(i for i in bom.line_items if i.section == 'server_transceiver')
        self.assertFalse(st.is_cable_assembly)

    # T4
    def test_switch_transceiver_classified_as_switch_transceiver(self):
        plan = self._make_plan_generated('T4-sw-xcvr')
        sw = self._switch(plan, 'T4-sw')
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_mmf)
        bom = get_plan_bom(plan)
        self.assertEqual(len(bom.line_items), 1)
        self.assertEqual(bom.line_items[0].section, 'switch_transceiver')
        self.assertFalse(bom.line_items[0].is_cable_assembly)

    # T5
    def test_dac_server_side_included(self):
        plan = self._make_plan_generated('T5-dac-srv')
        srv = self._server(plan, 'T5-srv')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_dac)
        bom = get_plan_bom(plan)
        st = next((i for i in bom.line_items if i.section == 'server_transceiver'), None)
        self.assertIsNotNone(st)
        self.assertTrue(st.is_cable_assembly)
        self.assertEqual(st.medium, 'DAC')

    # T6
    def test_dac_switch_side_suppressed(self):
        plan = self._make_plan_generated('T6-dac-sw')
        sw = self._switch(plan, 'T6-sw')
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_dac)
        bom = get_plan_bom(plan)
        sw_items = [i for i in bom.line_items if i.section == 'switch_transceiver']
        self.assertEqual(sw_items, [])
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 1)

    # T7
    def test_acc_switch_side_suppressed(self):
        plan = self._make_plan_generated('T7-acc-sw')
        sw = self._switch(plan, 'T7-sw')
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_acc)
        bom = get_plan_bom(plan)
        sw_items = [i for i in bom.line_items if i.section == 'switch_transceiver']
        self.assertEqual(sw_items, [])
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 1)

    # T8
    def test_multiple_servers_same_nic_aggregated(self):
        plan = self._make_plan_generated('T8-agg')
        for i in range(3):
            srv = self._server(plan, f'T8-srv-{i}')
            self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom(plan)
        nic_items = [i for i in bom.line_items if i.section == 'nic']
        self.assertEqual(len(nic_items), 1)
        self.assertEqual(nic_items[0].quantity, 3)

    # T9
    def test_two_nic_types_separate_line_items(self):
        plan = self._make_plan_generated('T9-two-nic')
        srv1 = self._server(plan, 'T9-srv1')
        srv2 = self._server(plan, 'T9-srv2')
        self._install_nic(srv1, 'fe', self.nic_mt)
        self._install_nic(srv2, 'fe', self.nic_mt2)
        bom = get_plan_bom(plan)
        nic_items = [i for i in bom.line_items if i.section == 'nic']
        self.assertEqual(len(nic_items), 2)

    # T10
    def test_sort_order_sections(self):
        plan = self._make_plan_generated('T10-sort-sec')
        srv = self._server(plan, 'T10-srv')
        sw = self._switch(plan, 'T10-sw')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_mmf)
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_mmf)
        bom = get_plan_bom(plan)
        sections = [i.section for i in bom.line_items]
        self.assertEqual(sections.index('nic'), 0)
        self.assertLess(sections.index('nic'), sections.index('server_transceiver'))
        self.assertLess(sections.index('server_transceiver'), sections.index('switch_transceiver'))

    # T11
    def test_sort_order_within_section_alpha_by_model(self):
        plan = self._make_plan_generated('T11-sort-alpha')
        # nic_mt model='BOM-NIC-200G', nic_mt2 model='BOM-NIC-400G' — 200G < 400G alpha
        srv1 = self._server(plan, 'T11-srv1')
        srv2 = self._server(plan, 'T11-srv2')
        # install in reverse order to verify sort
        self._install_nic(srv1, 'fe', self.nic_mt2)
        self._install_nic(srv2, 'fe', self.nic_mt)
        bom = get_plan_bom(plan)
        nic_items = [i for i in bom.line_items if i.section == 'nic']
        self.assertEqual(nic_items[0].module_type_model, 'BOM-NIC-200G')
        self.assertEqual(nic_items[1].module_type_model, 'BOM-NIC-400G')

    # T12
    def test_attribute_data_populated(self):
        plan = self._make_plan_generated('T12-attrs')
        srv = self._server(plan, 'T12-srv')
        self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom(plan)
        item = bom.line_items[0]
        self.assertEqual(item.cage_type, 'QSFP112')
        self.assertEqual(item.medium, 'MMF')
        self.assertEqual(item.connector, 'MPO-12')
        self.assertEqual(item.standard, 'TEST-200G')

    # T13
    def test_sparse_attribute_data_no_crash(self):
        plan = self._make_plan_generated('T13-sparse')
        srv = self._server(plan, 'T13-srv')
        self._install_switch_xcvr(srv, 'fe', self.xcvr_mt_sparse)
        # srv has role='server', top-level bay → nic section
        bom = get_plan_bom(plan)
        item = bom.line_items[0]
        self.assertIsNone(item.cage_type)
        self.assertIsNone(item.medium)

    # T14
    def test_no_attribute_data_no_crash(self):
        mt_none, _ = ModuleType.objects.get_or_create(
            manufacturer=self.mfr, model='BOM-NIC-NO-ATTRS',
            defaults={'attribute_data': None},
        )
        plan = self._make_plan_generated('T14-no-attrs')
        srv = self._server(plan, 'T14-srv')
        self._install_nic(srv, 'fe', mt_none)
        bom = get_plan_bom(plan)
        item = bom.line_items[0]
        self.assertIsNone(item.cage_type)

    # T15
    def test_plan_scoping_excludes_other_plan(self):
        plan_a = self._make_plan_generated('T15-plan-a')
        plan_b = self._make_plan_generated('T15-plan-b')
        srv_a = self._server(plan_a, 'T15-srv-a')
        srv_b = self._server(plan_b, 'T15-srv-b')
        self._install_nic(srv_a, 'fe', self.nic_mt)
        self._install_nic(srv_b, 'fe', self.nic_mt)
        bom = get_plan_bom(plan_a)
        nic_items = [i for i in bom.line_items if i.section == 'nic']
        self.assertEqual(nic_items[0].quantity, 1)

    # T16
    def test_is_cable_assembly_false_for_mmf(self):
        plan = self._make_plan_generated('T16-mmf')
        srv = self._server(plan, 'T16-srv')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_mmf)
        bom = get_plan_bom(plan)
        st = next(i for i in bom.line_items if i.section == 'server_transceiver')
        self.assertFalse(st.is_cable_assembly)

    # T17
    def test_generated_at_from_state(self):
        plan = self._make_plan_generated('T17-gen-at')
        gs = plan.generation_state
        bom = get_plan_bom(plan)
        self.assertEqual(bom.generated_at, gs.generated_at.isoformat())

    # T18
    def test_generated_at_empty_without_state(self):
        plan = self._make_plan('T18-no-state')
        bom = get_plan_bom(plan)
        self.assertEqual(bom.generated_at, '')

    # T19
    def test_multiple_dac_switch_suppressed_count(self):
        plan = self._make_plan_generated('T19-multi-dac')
        sw = self._switch(plan, 'T19-sw')
        for port in ('E1/1', 'E1/2', 'E1/3', 'E1/4'):
            self._install_switch_xcvr(sw, port, self.xcvr_mt_dac)
        bom = get_plan_bom(plan)
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 4)
        self.assertEqual(bom.line_items, ())

    # T20
    def test_dac_server_and_switch_only_switch_suppressed(self):
        plan = self._make_plan_generated('T20-dac-both')
        srv = self._server(plan, 'T20-srv')
        sw = self._switch(plan, 'T20-sw')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_dac)
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_dac)
        bom = get_plan_bom(plan)
        sw_items = [i for i in bom.line_items if i.section == 'switch_transceiver']
        self.assertEqual(sw_items, [])
        st_items = [i for i in bom.line_items if i.section == 'server_transceiver']
        self.assertEqual(len(st_items), 1)
        self.assertTrue(st_items[0].is_cable_assembly)
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 1)


# ---------------------------------------------------------------------------
# T21–T36: Command tests
# ---------------------------------------------------------------------------

class BOMExportCommandTestCase(_BOMFixtureMixin, TestCase):

    def setUp(self):
        self.plan = self._make_plan_generated('CMD-plan')
        srv = self._server(self.plan, 'CMD-srv')
        self._install_nic(srv, 'fe', self.nic_mt)
        self.tmpdir = tempfile.mkdtemp()

    def _out_path(self, filename):
        return os.path.join(self.tmpdir, filename)

    # T21
    def test_json_format_writes_valid_json(self):
        path = self._out_path('bom.json')
        call_command('export_plan_bom', str(self.plan.pk), '--output', path)
        with open(path) as f:
            doc = json.load(f)
        self.assertIn('metadata', doc)
        self.assertIn('bom', doc)

    # T22
    def test_json_metadata_fields(self):
        path = self._out_path('bom-meta.json')
        call_command('export_plan_bom', str(self.plan.pk), '--output', path)
        with open(path) as f:
            doc = json.load(f)
        for key in ('plan_id', 'plan_name', 'generated_at', 'bom_exported_at',
                    'suppressed_switch_cable_assembly_count'):
            self.assertIn(key, doc['metadata'], f"missing metadata key: {key}")

    # T23
    def test_json_bom_fields_per_line_item(self):
        path = self._out_path('bom-fields.json')
        call_command('export_plan_bom', str(self.plan.pk), '--output', path)
        with open(path) as f:
            doc = json.load(f)
        self.assertGreater(len(doc['bom']), 0)
        item = doc['bom'][0]
        for key in ('section', 'module_type_model', 'manufacturer', 'quantity',
                    'cage_type', 'medium', 'connector', 'standard', 'is_cable_assembly'):
            self.assertIn(key, item, f"missing bom item key: {key}")

    # T24
    def test_json_bom_quantity_correct(self):
        plan = self._make_plan_generated('CMD-qty')
        for i in range(2):
            srv = self._server(plan, f'CMD-qty-srv-{i}')
            self._install_nic(srv, 'fe', self.nic_mt)
        path = self._out_path('bom-qty.json')
        call_command('export_plan_bom', str(plan.pk), '--output', path)
        with open(path) as f:
            doc = json.load(f)
        nic_items = [r for r in doc['bom'] if r['section'] == 'nic']
        self.assertEqual(nic_items[0]['quantity'], 2)

    # T25
    def test_json_null_attribute_serialized_as_null(self):
        mt_sparse, _ = ModuleType.objects.get_or_create(
            manufacturer=self.mfr, model='CMD-SPARSE-NIC',
            defaults={'attribute_data': {}},
        )
        plan = self._make_plan_generated('CMD-null-attr')
        srv = self._server(plan, 'CMD-null-srv')
        self._install_nic(srv, 'fe', mt_sparse)
        path = self._out_path('bom-null.json')
        call_command('export_plan_bom', str(plan.pk), '--output', path)
        with open(path) as f:
            doc = json.load(f)
        self.assertIsNone(doc['bom'][0]['cage_type'])

    # T26
    def test_csv_format_header_columns(self):
        path = self._out_path('bom.csv')
        call_command('export_plan_bom', str(self.plan.pk), '--output', path, '--format', 'csv')
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
        expected = ['section', 'module_type_model', 'manufacturer', 'quantity',
                    'cage_type', 'medium', 'connector', 'standard', 'is_cable_assembly']
        self.assertEqual(fieldnames, expected)

    # T27
    def test_csv_format_data_row(self):
        path = self._out_path('bom-data.csv')
        call_command('export_plan_bom', str(self.plan.pk), '--output', path, '--format', 'csv')
        with open(path, newline='') as f:
            rows = [r for r in csv.DictReader(f) if not r['section'].startswith('#')]
        self.assertGreater(len(rows), 0)
        self.assertEqual(rows[0]['section'], 'nic')
        self.assertEqual(rows[0]['module_type_model'], self.nic_mt.model)

    # T28
    def test_csv_suppressed_count_footer(self):
        plan = self._make_plan_generated('CMD-csv-dac')
        sw = self._switch(plan, 'CMD-csv-sw')
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_dac)
        path = self._out_path('bom-dac.csv')
        call_command('export_plan_bom', str(plan.pk), '--output', path, '--format', 'csv')
        with open(path) as f:
            lines = f.read().splitlines()
        footer = next((l for l in lines if l.startswith('# suppressed_switch_cable_assembly_count,')), None)
        self.assertIsNotNone(footer, "suppressed count footer row not found in CSV")
        count_str = footer.split(',', 1)[1]
        self.assertEqual(int(count_str), 1)

    # T29
    def test_table_format_stdout(self):
        out = StringIO()
        call_command('export_plan_bom', str(self.plan.pk), '--format', 'table', stdout=out)
        output = out.getvalue()
        self.assertIn(self.nic_mt.model, output)
        self.assertIn('Suppressed', output)

    # T30
    def test_plan_not_found_raises(self):
        with self.assertRaises(CommandError):
            call_command('export_plan_bom', '999999', '--output', self._out_path('x.json'))

    # T31
    def test_no_generation_state_raises(self):
        plan = self._make_plan('CMD-no-state')
        with self.assertRaises(CommandError) as ctx:
            call_command('export_plan_bom', str(plan.pk), '--output', self._out_path('x.json'))
        self.assertIn('generation state', str(ctx.exception).lower())

    # T32
    def test_status_queued_raises(self):
        plan = self._make_plan_with_status('CMD-queued', GenerationStatusChoices.QUEUED)
        with self.assertRaises(CommandError) as ctx:
            call_command('export_plan_bom', str(plan.pk), '--output', self._out_path('x.json'))
        self.assertIn('generated', str(ctx.exception).lower())

    # T33
    def test_status_failed_raises(self):
        plan = self._make_plan_with_status('CMD-failed', GenerationStatusChoices.FAILED)
        with self.assertRaises(CommandError):
            call_command('export_plan_bom', str(plan.pk), '--output', self._out_path('x.json'))

    # T34
    def test_status_dirty_raises(self):
        plan = self._make_plan_with_status('CMD-dirty', GenerationStatusChoices.DIRTY)
        with self.assertRaises(CommandError):
            call_command('export_plan_bom', str(plan.pk), '--output', self._out_path('x.json'))

    # T35
    def test_status_generated_succeeds(self):
        path = self._out_path('bom-ok.json')
        # Should not raise
        call_command('export_plan_bom', str(self.plan.pk), '--output', path)
        self.assertTrue(os.path.exists(path))

    # T36
    def test_output_dir_not_exist_raises(self):
        with self.assertRaises(CommandError):
            call_command('export_plan_bom', str(self.plan.pk),
                         '--output', '/nonexistent/dir/bom.json')
