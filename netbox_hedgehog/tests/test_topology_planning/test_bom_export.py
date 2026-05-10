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
        cls.xcvr_mt_rj45, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr_xcvr, model='BOM-XCVR-RJ45',
            defaults={'attribute_data': {
                'cage_type': 'RJ45', 'medium': 'Copper',
                'connector': 'RJ45', 'standard': '1000BASE-T',
                'reach_class': 'Copper', 'cable_assembly_type': 'none',
            }},
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
        self.assertEqual(item.module_type_description, '')

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

    # T7b
    def test_rj45_switch_side_not_suppressed(self):
        plan = self._make_plan_generated('T7b-rj45-sw')
        sw = self._switch(plan, 'T7b-sw')
        self._install_switch_xcvr(sw, 'mgmt0', self.xcvr_mt_rj45)
        bom = get_plan_bom(plan)
        sw_items = [i for i in bom.line_items if i.section == 'switch_transceiver']
        self.assertEqual(len(sw_items), 1)
        self.assertEqual(sw_items[0].module_type_model, self.xcvr_mt_rj45.model)
        self.assertEqual(sw_items[0].quantity, 1)
        self.assertFalse(sw_items[0].is_cable_assembly)
        self.assertEqual(sw_items[0].module_type_description, '')
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 0)

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
        expected = [
            'section', 'module_type_model', 'hedgehog_class', 'manufacturer', 'quantity',
            'cage_type', 'medium', 'connector', 'standard',
            'reach_class', 'wavelength_nm', 'host_lane_count', 'host_serdes_gbps_per_lane',
            'optical_lane_pattern', 'gearbox_present', 'cable_assembly_type', 'breakout_topology',
            'is_cable_assembly',
        ]
        self.assertEqual(fieldnames, expected)

    # T27
    def test_csv_format_data_row(self):
        path = self._out_path('bom-data.csv')
        call_command('export_plan_bom', str(self.plan.pk), '--output', path, '--format', 'csv')
        with open(path, newline='') as f:
            rows = [r for r in csv.DictReader(f) if not r['section'].startswith('#')]
        self.assertGreater(len(rows), 0)
        # base-device rows come first; find the NIC module row
        nic_rows = [r for r in rows if r['section'] == 'nic']
        self.assertGreater(len(nic_rows), 0)
        self.assertEqual(nic_rows[0]['module_type_model'], self.nic_mt.model)

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


# ---------------------------------------------------------------------------
# D1–D12: Per-device service tests
# ---------------------------------------------------------------------------

class BOMPerDeviceServiceTestCase(_BOMFixtureMixin, TestCase):
    """
    Phase 3 RED tests for get_plan_bom_by_device().
    All tests import get_plan_bom_by_device lazily so that only the new
    tests fail (ImportError); existing T1–T36 tests remain green.
    """

    # D1
    def test_d1_empty_plan_returns_empty(self):
        """D1: Empty generated plan → empty line_items and suppressed==0."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan = self._make_plan_generated('D1-empty')
        bom = get_plan_bom_by_device(plan)
        self.assertEqual(bom.line_items, ())
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 0)

    # D2
    def test_d2_single_server_nic_row_fields(self):
        """D2: Single server with NIC → one row with device_name, hedgehog_class,
        device_role, and section='nic' all populated correctly."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan = self._make_plan_generated('D2-srv-nic')
        srv = self._server(plan, 'D2-srv')
        srv.custom_field_data['hedgehog_class'] = 'test-srv-class'
        srv.save()
        self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom_by_device(plan)
        self.assertEqual(len(bom.line_items), 1)
        item = bom.line_items[0]
        self.assertEqual(item.device_name, 'D2-srv')
        self.assertEqual(item.hedgehog_class, 'test-srv-class')
        self.assertEqual(item.device_role, self.server_role.slug)
        self.assertEqual(item.section, 'nic')
        self.assertEqual(item.module_type_model, self.nic_mt.model)

    # D3
    def test_d3_two_servers_same_nic_type_produce_two_rows(self):
        """D3: Two servers with same NIC type → two per-device rows (not aggregated)."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan = self._make_plan_generated('D3-two-srv')
        for name in ('D3-srv1', 'D3-srv2'):
            srv = self._server(plan, name)
            self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom_by_device(plan)
        nic_rows = [i for i in bom.line_items if i.section == 'nic']
        self.assertEqual(len(nic_rows), 2,
                         "Two servers must produce two per-device NIC rows, not one aggregated row")

    # D4
    def test_d4_per_device_quantity_is_one_per_type_per_device(self):
        """D4: Each per-device row has quantity==1 when one module of that type per device."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan = self._make_plan_generated('D4-qty')
        for name in ('D4-srv1', 'D4-srv2'):
            srv = self._server(plan, name)
            self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom_by_device(plan)
        for item in bom.line_items:
            self.assertEqual(item.quantity, 1,
                             f"Per-device quantity must be 1, got {item.quantity} for {item.device_name}")

    # D5
    def test_d5_switch_dac_suppressed_not_in_rows(self):
        """D5: Switch-side DAC module is suppressed from line_items; suppressed count == 1."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan = self._make_plan_generated('D5-sw-dac')
        sw = self._switch(plan, 'D5-sw')
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_dac)
        bom = get_plan_bom_by_device(plan)
        sw_rows = [i for i in bom.line_items if i.section == 'switch_transceiver']
        self.assertEqual(sw_rows, [],
                         "Switch-side DAC must not appear in per-device line_items")
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 1)

    # D6
    def test_d6_server_dac_included_as_server_transceiver(self):
        """D6: Server-side nested DAC appears as server_transceiver row with is_cable_assembly==True."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan = self._make_plan_generated('D6-srv-dac')
        srv = self._server(plan, 'D6-srv')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_dac)
        bom = get_plan_bom_by_device(plan)
        st_rows = [i for i in bom.line_items if i.section == 'server_transceiver']
        self.assertEqual(len(st_rows), 1,
                         "Server-side DAC must appear as a server_transceiver row")
        self.assertTrue(st_rows[0].is_cable_assembly)

    # D7
    def test_d7_sort_by_hedgehog_class_then_device_name(self):
        """D7: Rows sorted by hedgehog_class first, then device_name."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan = self._make_plan_generated('D7-sort')
        # 'b-class' before 'a-class' insertion order; expect 'a-class' first in output
        for class_id, name in (('b-class', 'D7-srv-b'), ('a-class', 'D7-srv-a')):
            srv = self._server(plan, name)
            srv.custom_field_data['hedgehog_class'] = class_id
            srv.save()
            self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom_by_device(plan)
        classes = [i.hedgehog_class for i in bom.line_items]
        self.assertEqual(classes, sorted(classes),
                         "line_items must be sorted by hedgehog_class")

    # D8
    def test_d8_plan_scoping_excludes_other_plan(self):
        """D8: Per-device BOM of plan A contains only plan A devices."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan_a = self._make_plan_generated('D8-plan-a')
        plan_b = self._make_plan_generated('D8-plan-b')
        for plan, name in ((plan_a, 'D8-srv-a'), (plan_b, 'D8-srv-b')):
            srv = self._server(plan, name)
            self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom_by_device(plan_a)
        device_names = {i.device_name for i in bom.line_items}
        self.assertIn('D8-srv-a', device_names)
        self.assertNotIn('D8-srv-b', device_names)

    # D9
    def test_d9_device_role_is_slug_not_name(self):
        """D9: item.device_role equals device.role.slug (not device.role.name)."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan = self._make_plan_generated('D9-role')
        srv = self._server(plan, 'D9-srv')
        self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom_by_device(plan)
        self.assertEqual(len(bom.line_items), 1)
        self.assertEqual(bom.line_items[0].device_role, self.server_role.slug)
        self.assertNotEqual(bom.line_items[0].device_role, self.server_role.name)

    # D10
    def test_d10_hedgehog_class_from_custom_field(self):
        """D10: item.hedgehog_class equals the value set in custom_field_data['hedgehog_class']."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan = self._make_plan_generated('D10-hh-class')
        srv = self._server(plan, 'D10-srv')
        srv.custom_field_data['hedgehog_class'] = 'be-rail-leaf'
        srv.save()
        self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom_by_device(plan)
        self.assertEqual(bom.line_items[0].hedgehog_class, 'be-rail-leaf')

    # D11
    def test_d11_aggregate_consistency_invariant(self):
        """D11: Sum of per-device quantities for each (section, module_type_id) equals
        the aggregate BOM quantity for the same key (after same DAC/ACC suppression)."""
        from netbox_hedgehog.services.bom_export import get_plan_bom, get_plan_bom_by_device
        plan = self._make_plan_generated('D11-inv')
        srv1 = self._server(plan, 'D11-srv1')
        srv1.custom_field_data['hedgehog_class'] = 'srv-cls'
        srv1.save()
        srv2 = self._server(plan, 'D11-srv2')
        srv2.custom_field_data['hedgehog_class'] = 'srv-cls'
        srv2.save()
        sw = self._switch(plan, 'D11-sw')
        self._install_nic(srv1, 'fe', self.nic_mt)
        self._install_nic(srv2, 'fe', self.nic_mt)
        nic1 = self._install_nic(srv1, 'be', self.nic_mt)
        nic2 = self._install_nic(srv2, 'be', self.nic_mt)
        self._install_nested_xcvr(srv1, nic1, 'cage-0', self.xcvr_mt_mmf)
        self._install_nested_xcvr(srv2, nic2, 'cage-0', self.xcvr_mt_mmf)
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_mmf)
        # One switch DAC — suppressed from both
        self._install_switch_xcvr(sw, 'E1/2', self.xcvr_mt_dac)

        agg_bom = get_plan_bom(plan)
        per_dev_bom = get_plan_bom_by_device(plan)

        per_dev_totals: dict[tuple, int] = {}
        for item in per_dev_bom.line_items:
            key = (item.section, item.module_type_id)
            per_dev_totals[key] = per_dev_totals.get(key, 0) + item.quantity
        agg_totals = {
            (item.section, item.module_type_id): item.quantity
            for item in agg_bom.line_items
        }
        self.assertEqual(per_dev_totals, agg_totals,
                         "Per-device quantity totals must match aggregate BOM quantities")

    # D12
    def test_d12_missing_hedgehog_class_defaults_to_empty_string(self):
        """D12: Device with no hedgehog_class in custom_field_data → item.hedgehog_class==''."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan = self._make_plan_generated('D12-no-class')
        srv = self._server(plan, 'D12-srv')  # _server does not set hedgehog_class
        self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom_by_device(plan)
        self.assertEqual(len(bom.line_items), 1)
        self.assertEqual(bom.line_items[0].hedgehog_class, '',
                         "Missing hedgehog_class must default to empty string, not raise")


# ---------------------------------------------------------------------------
# D13–D16: Per-device CSV renderer tests
# ---------------------------------------------------------------------------

class BOMPerDeviceCSVRenderTestCase(_BOMFixtureMixin, TestCase):
    """Phase 3 RED tests for render_bom_per_device_csv()."""

    def _make_minimal_bom(self):
        """Helper: create a GENERATED plan with one server NIC and return the BOM."""
        from netbox_hedgehog.services.bom_export import get_plan_bom_by_device
        plan = self._make_plan_generated('CSV-render-plan')
        srv = self._server(plan, 'CSV-render-srv')
        srv.custom_field_data['hedgehog_class'] = 'csv-class'
        srv.save()
        self._install_nic(srv, 'fe', self.nic_mt)
        return get_plan_bom_by_device(plan)

    # D13
    def test_d13_csv_header_row(self):
        """D13: First line of CSV matches the exact 12-column fieldnames."""
        from netbox_hedgehog.services.bom_export import render_bom_per_device_csv
        bom = self._make_minimal_bom()
        content = render_bom_per_device_csv(bom)
        first_line = content.splitlines()[0]
        expected = (
            'device_name,hedgehog_class,device_role,section,'
            'module_type_model,manufacturer,quantity,'
            'cage_type,medium,connector,standard,'
            'reach_class,wavelength_nm,host_lane_count,host_serdes_gbps_per_lane,'
            'optical_lane_pattern,gearbox_present,cable_assembly_type,breakout_topology,'
            'is_cable_assembly'
        )
        self.assertEqual(first_line, expected,
                         f"CSV header mismatch. Got: {first_line!r}")

    # D14
    def test_d14_csv_data_row_has_device_fields(self):
        """D14: A data row has non-empty device_name and hedgehog_class columns."""
        from netbox_hedgehog.services.bom_export import render_bom_per_device_csv
        bom = self._make_minimal_bom()
        content = render_bom_per_device_csv(bom)
        data_lines = [
            l for l in content.splitlines()
            if l.strip() and not l.startswith('#')
        ]
        reader = csv.DictReader(iter(data_lines))
        rows = list(reader)
        self.assertGreater(len(rows), 0)
        self.assertNotEqual(rows[0]['device_name'], '')
        self.assertNotEqual(rows[0]['hedgehog_class'], '')

    # D15
    def test_d15_csv_suppressed_footer(self):
        """D15: Last line is a suppressed_switch_cable_assembly_count footer comment."""
        from netbox_hedgehog.services.bom_export import render_bom_per_device_csv
        bom = self._make_minimal_bom()
        content = render_bom_per_device_csv(bom)
        lines = content.splitlines()
        footer = next(
            (l for l in lines if l.startswith('# suppressed_switch_cable_assembly_count,')),
            None,
        )
        self.assertIsNotNone(footer, "Footer comment line missing from per-device CSV")
        count_str = footer.split(',', 1)[1]
        self.assertEqual(int(count_str), 0)

    # D16
    def test_d16_none_attributes_rendered_as_empty_string(self):
        """D16: None cage_type/medium/connector/standard → empty string in CSV (not 'None')."""
        from netbox_hedgehog.services.bom_export import (
            get_plan_bom_by_device, render_bom_per_device_csv,
        )
        plan = self._make_plan_generated('D16-null-attr')
        srv = self._server(plan, 'D16-srv')
        self._install_nic(srv, 'fe', self.xcvr_mt_sparse)  # sparse attrs → all None
        bom = get_plan_bom_by_device(plan)
        content = render_bom_per_device_csv(bom)
        data_lines = [
            l for l in content.splitlines()
            if l.strip() and not l.startswith('#')
        ]
        reader = csv.DictReader(iter(data_lines))
        rows = list(reader)
        self.assertGreater(len(rows), 0)
        self.assertNotIn('None', rows[0]['cage_type'],
                         "None must render as '' not 'None'")


# ---------------------------------------------------------------------------
# D17–D21: Per-device-csv command tests
# ---------------------------------------------------------------------------

class BOMPerDeviceCommandTestCase(_BOMFixtureMixin, TestCase):
    """Phase 3 RED tests for export_plan_bom --format per-device-csv."""

    def setUp(self):
        self.plan = self._make_plan_generated('PD-CMD-plan')
        srv1 = self._server(self.plan, 'PD-CMD-srv1')
        srv1.custom_field_data['hedgehog_class'] = 'class-b'
        srv1.save()
        srv2 = self._server(self.plan, 'PD-CMD-srv2')
        srv2.custom_field_data['hedgehog_class'] = 'class-a'
        srv2.save()
        sw = self._switch(self.plan, 'PD-CMD-sw')
        sw.custom_field_data['hedgehog_class'] = 'sw-class'
        sw.save()
        self._install_nic(srv1, 'fe', self.nic_mt)
        self._install_nic(srv2, 'fe', self.nic_mt)
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_mmf)
        self.tmpdir = tempfile.mkdtemp()

    def _out_path(self, filename):
        return os.path.join(self.tmpdir, filename)

    # D17
    def test_d17_per_device_csv_format_writes_file(self):
        """D17: --format per-device-csv writes a file that contains valid CSV."""
        path = self._out_path('bom-pd.csv')
        call_command('export_plan_bom', str(self.plan.pk),
                     '--output', path, '--format', 'per-device-csv')
        self.assertTrue(os.path.exists(path))
        with open(path, newline='') as f:
            rows = list(csv.DictReader(
                l for l in f if not l.startswith('#')
            ))
        self.assertGreater(len(rows), 0, "per-device-csv must produce at least one data row")

    # D18
    def test_d18_per_device_csv_requires_output(self):
        """D18: --format per-device-csv without --output raises CommandError."""
        with self.assertRaises(CommandError):
            call_command('export_plan_bom', str(self.plan.pk),
                         '--format', 'per-device-csv')

    # D19
    def test_d19_per_device_csv_header_columns(self):
        """D19: per-device-csv file header matches the 12-column spec."""
        path = self._out_path('bom-pd-header.csv')
        call_command('export_plan_bom', str(self.plan.pk),
                     '--output', path, '--format', 'per-device-csv')
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
        expected = [
            'device_name', 'hedgehog_class', 'device_role',
            'section', 'module_type_model', 'manufacturer', 'quantity',
            'cage_type', 'medium', 'connector', 'standard',
            'reach_class', 'wavelength_nm', 'host_lane_count', 'host_serdes_gbps_per_lane',
            'optical_lane_pattern', 'gearbox_present', 'cable_assembly_type', 'breakout_topology',
            'is_cable_assembly',
        ]
        self.assertEqual(fieldnames, expected)

    # D20
    def test_d20_per_device_csv_rows_sorted_by_hedgehog_class(self):
        """D20: Data rows in per-device-csv are sorted by hedgehog_class."""
        path = self._out_path('bom-pd-sort.csv')
        call_command('export_plan_bom', str(self.plan.pk),
                     '--output', path, '--format', 'per-device-csv')
        with open(path, newline='') as f:
            rows = [r for r in csv.DictReader(f) if not r.get('device_name', '').startswith('#')]
        classes = [r['hedgehog_class'] for r in rows]
        self.assertEqual(classes, sorted(classes),
                         "per-device-csv rows must be sorted by hedgehog_class")

    # D21
    def test_d21_per_device_csv_stdout_summary(self):
        """D21: Command stdout contains 'per_device_rows:' when format=per-device-csv."""
        path = self._out_path('bom-pd-stdout.csv')
        out = StringIO()
        call_command('export_plan_bom', str(self.plan.pk),
                     '--output', path, '--format', 'per-device-csv',
                     stdout=out)
        self.assertIn('per_device_rows:', out.getvalue())


# ---------------------------------------------------------------------------
# BD-T1–BD-T12: Base-device service tests (DIET-523 RED)
# ---------------------------------------------------------------------------

class BOMBaseDeviceServiceTestCase(_BOMFixtureMixin, TestCase):
    """
    DIET-523 Phase 3 RED tests for base-device aggregation in get_plan_bom().

    All tests in this class MUST FAIL until PlanBOM gains base_device_items
    and get_plan_bom() populates it.
    """

    # BD-T1: PlanBOM has base_device_items attribute
    def test_bd_t1_plan_bom_has_base_device_items_attribute(self):
        """BD-T1: get_plan_bom() returns object with base_device_items attribute."""
        plan = self._make_plan_generated('BD-T1-attr')
        bom = get_plan_bom(plan)
        self.assertTrue(
            hasattr(bom, 'base_device_items'),
            "PlanBOM must have a base_device_items attribute (DIET-523 not implemented yet)",
        )

    # BD-T2: Empty plan → empty tuple
    def test_bd_t2_empty_plan_returns_empty_base_device_items(self):
        """BD-T2: Plan with no devices → base_device_items == ()."""
        plan = self._make_plan_generated('BD-T2-empty')
        bom = get_plan_bom(plan)
        self.assertEqual(
            bom.base_device_items, (),
            "Empty plan must yield base_device_items == ()",
        )

    # BD-T3: Server device → section='server'
    def test_bd_t3_server_device_section_is_server(self):
        """BD-T3: Device with role.slug='server' → BaseDeviceBOMLineItem.section='server'."""
        plan = self._make_plan_generated('BD-T3-srv')
        self._server(plan, 'BD-T3-srv-dev')
        bom = get_plan_bom(plan)
        self.assertEqual(len(bom.base_device_items), 1)
        self.assertEqual(bom.base_device_items[0].section, 'server')

    # BD-T4: Non-server device → section='switch'
    def test_bd_t4_non_server_device_section_is_switch(self):
        """BD-T4: Device with non-server role → BaseDeviceBOMLineItem.section='switch'."""
        plan = self._make_plan_generated('BD-T4-sw')
        self._switch(plan, 'BD-T4-sw-dev')
        bom = get_plan_bom(plan)
        self.assertEqual(len(bom.base_device_items), 1)
        self.assertEqual(bom.base_device_items[0].section, 'switch')

    # BD-T5: Two servers, same DeviceType and hedgehog_class → one row, quantity=2
    def test_bd_t5_two_servers_same_dt_and_class_aggregate(self):
        """BD-T5: Two servers with same DeviceType and hedgehog_class → one row with quantity=2."""
        plan = self._make_plan_generated('BD-T5-agg')
        for name in ('BD-T5-srv-1', 'BD-T5-srv-2'):
            dev = self._server(plan, name)
            dev.custom_field_data['hedgehog_class'] = 'be-rail-leaf'
            dev.save()
        bom = get_plan_bom(plan)
        self.assertEqual(len(bom.base_device_items), 1)
        self.assertEqual(bom.base_device_items[0].quantity, 2)

    # BD-T6: Two servers, different DeviceTypes → two rows
    def test_bd_t6_two_servers_different_dt_two_rows(self):
        """BD-T6: Two servers with different DeviceTypes → two distinct base_device rows."""
        mfr2, _ = Manufacturer.objects.get_or_create(
            name='BD-T6-Vendor', defaults={'slug': 'bd-t6-vendor'},
        )
        dt2, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr2, model='BD-T6-Server-DT',
            defaults={'slug': 'bd-t6-server-dt'},
        )
        plan = self._make_plan_generated('BD-T6-two-dt')
        dev1 = Device.objects.create(
            name='BD-T6-srv-1', device_type=self.server_dt, role=self.server_role,
            site=self.site, status='planned',
            custom_field_data={'hedgehog_plan_id': str(plan.pk)},
        )
        dev1.custom_field_data['hedgehog_class'] = 'same-class'
        dev1.save()
        dev2 = Device.objects.create(
            name='BD-T6-srv-2', device_type=dt2, role=self.server_role,
            site=self.site, status='planned',
            custom_field_data={'hedgehog_plan_id': str(plan.pk)},
        )
        dev2.custom_field_data['hedgehog_class'] = 'same-class'
        dev2.save()
        bom = get_plan_bom(plan)
        self.assertEqual(
            len(bom.base_device_items), 2,
            "Two different DeviceTypes must produce two separate base_device rows",
        )

    # BD-T7: Two servers, same DeviceType but different hedgehog_class → two rows
    def test_bd_t7_same_dt_different_class_two_rows(self):
        """BD-T7: Two servers with same DeviceType but different hedgehog_class → two rows."""
        plan = self._make_plan_generated('BD-T7-diff-class')
        for class_name, dev_name in (('class-a', 'BD-T7-srv-a'), ('class-b', 'BD-T7-srv-b')):
            dev = self._server(plan, dev_name)
            dev.custom_field_data['hedgehog_class'] = class_name
            dev.save()
        bom = get_plan_bom(plan)
        self.assertEqual(
            len(bom.base_device_items), 2,
            "Same DeviceType but different hedgehog_class must produce two separate rows",
        )

    # BD-T8: Mixed plan → server row before switch row
    def test_bd_t8_server_row_before_switch_row(self):
        """BD-T8: In a mixed plan, server rows (section='server') appear before switch rows."""
        plan = self._make_plan_generated('BD-T8-order')
        # Insert switch first to verify sort, not insertion order
        self._switch(plan, 'BD-T8-sw')
        self._server(plan, 'BD-T8-srv')
        bom = get_plan_bom(plan)
        sections = [item.section for item in bom.base_device_items]
        server_idx = sections.index('server')
        switch_idx = sections.index('switch')
        self.assertLess(
            server_idx, switch_idx,
            "Server rows must appear before switch rows in base_device_items",
        )

    # BD-T9: Sort within section: hedgehog_class, then manufacturer, then device_type_model
    def test_bd_t9_sort_within_section(self):
        """BD-T9: Within each section, rows sorted by hedgehog_class, manufacturer, device_type_model."""
        mfr_a, _ = Manufacturer.objects.get_or_create(
            name='BD-T9-Aardvark', defaults={'slug': 'bd-t9-aardvark'},
        )
        mfr_z, _ = Manufacturer.objects.get_or_create(
            name='BD-T9-Zebra', defaults={'slug': 'bd-t9-zebra'},
        )
        dt_a, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr_a, model='BD-T9-Model-A', defaults={'slug': 'bd-t9-model-a'},
        )
        dt_z, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr_z, model='BD-T9-Model-Z', defaults={'slug': 'bd-t9-model-z'},
        )
        plan = self._make_plan_generated('BD-T9-sort')
        # Create in reverse expected order
        for dt, mfr, hh_class in [
            (dt_z, mfr_z, 'z-class'),
            (dt_a, mfr_a, 'a-class'),
        ]:
            dev = Device.objects.create(
                name=f'BD-T9-{hh_class}', device_type=dt, role=self.server_role,
                site=self.site, status='planned',
                custom_field_data={'hedgehog_plan_id': str(plan.pk)},
            )
            dev.custom_field_data['hedgehog_class'] = hh_class
            dev.save()
        bom = get_plan_bom(plan)
        classes = [item.hedgehog_class for item in bom.base_device_items]
        self.assertEqual(
            classes, sorted(classes),
            "base_device_items must be sorted by hedgehog_class within each section",
        )

    # BD-T10: Plan scoping — devices from another plan excluded
    def test_bd_t10_plan_scoping_excludes_other_plan(self):
        """BD-T10: base_device_items only includes devices tagged to the queried plan."""
        plan_a = self._make_plan_generated('BD-T10-plan-a')
        plan_b = self._make_plan_generated('BD-T10-plan-b')
        self._server(plan_a, 'BD-T10-srv-a')
        self._server(plan_b, 'BD-T10-srv-b')
        bom = get_plan_bom(plan_a)
        self.assertEqual(
            len(bom.base_device_items), 1,
            "base_device_items must be scoped to the queried plan only",
        )

    # BD-T11: role field equals device.role.slug
    def test_bd_t11_role_field_equals_device_role_slug(self):
        """BD-T11: BaseDeviceBOMLineItem.role equals device.role.slug."""
        plan = self._make_plan_generated('BD-T11-role')
        self._server(plan, 'BD-T11-srv')
        bom = get_plan_bom(plan)
        self.assertEqual(len(bom.base_device_items), 1)
        self.assertEqual(
            bom.base_device_items[0].role,
            self.server_role.slug,
            "role field must equal device.role.slug",
        )

    # BD-T12: Existing line_items unchanged when base_device_items is populated
    def test_bd_t12_line_items_unchanged_alongside_base_devices(self):
        """BD-T12: Existing module line_items are unaffected when base_device_items also runs."""
        plan = self._make_plan_generated('BD-T12-regression')
        srv = self._server(plan, 'BD-T12-srv')
        self._install_nic(srv, 'fe', self.nic_mt)
        bom = get_plan_bom(plan)
        nic_items = [i for i in bom.line_items if i.section == 'nic']
        self.assertEqual(
            len(nic_items), 1,
            "line_items must still contain the NIC row after base_device_items is computed",
        )
        self.assertEqual(nic_items[0].quantity, 1)


# ---------------------------------------------------------------------------
# BD-T25–BD-T27: Base-device JSON tests (DIET-523 RED)
# ---------------------------------------------------------------------------

class BOMBaseDeviceJSONTestCase(_BOMFixtureMixin, TestCase):
    """
    DIET-523 Phase 3 RED tests for base_devices key in JSON export.

    All tests MUST FAIL until export_plan_bom command emits a base_devices
    top-level key in JSON output.
    """

    def setUp(self):
        self.plan = self._make_plan_generated('BD-JSON-plan')
        dev = self._server(self.plan, 'BD-JSON-srv')
        dev.custom_field_data['hedgehog_class'] = 'be-rail-leaf'
        dev.save()
        # Also install a module so bom key has content
        self._install_nic(dev, 'fe', self.nic_mt)
        import tempfile
        self.tmpdir = tempfile.mkdtemp()

    def _out_path(self, filename):
        import os
        return os.path.join(self.tmpdir, filename)

    # BD-T25: JSON output contains base_devices top-level key
    def test_bd_t25_json_contains_base_devices_key(self):
        """BD-T25: JSON output file contains a 'base_devices' top-level key."""
        from django.core.management import call_command
        path = self._out_path('bd-t25.json')
        call_command('export_plan_bom', str(self.plan.pk), '--output', path)
        with open(path) as f:
            doc = json.load(f)
        self.assertIn(
            'base_devices', doc,
            "JSON output must have a top-level 'base_devices' key (DIET-523 not implemented)",
        )

    # BD-T26: base_devices items have all six required fields
    def test_bd_t26_base_devices_items_have_all_fields(self):
        """BD-T26: Each item in base_devices has: section, role, hedgehog_class,
        manufacturer, device_type_model, quantity."""
        from django.core.management import call_command
        path = self._out_path('bd-t26.json')
        call_command('export_plan_bom', str(self.plan.pk), '--output', path)
        with open(path) as f:
            doc = json.load(f)
        self.assertIn('base_devices', doc)
        self.assertGreater(
            len(doc['base_devices']), 0,
            "base_devices must be non-empty when a device is in the plan",
        )
        item = doc['base_devices'][0]
        for field in ('section', 'role', 'hedgehog_class', 'manufacturer',
                      'device_type_model', 'quantity'):
            self.assertIn(
                field, item,
                f"base_devices item missing field: {field!r}",
            )

    # BD-T27: Existing bom key still present and contains only module rows
    def test_bd_t27_bom_key_unchanged_contains_only_module_rows(self):
        """BD-T27: 'bom' key still present and does not contain device_type_model rows.

        Regression guard: adding base_devices must not pollute the existing bom key.
        """
        from django.core.management import call_command
        path = self._out_path('bd-t27.json')
        call_command('export_plan_bom', str(self.plan.pk), '--output', path)
        with open(path) as f:
            doc = json.load(f)
        self.assertIn('bom', doc, "'bom' key must still be present in JSON output")
        # bom key must contain the NIC module row, not device rows
        bom_rows = doc['bom']
        self.assertGreater(len(bom_rows), 0, "'bom' must be non-empty (has a NIC module)")
        # Verify bom rows have the module section (nic), not device sections
        bom_sections = {r.get('section') for r in bom_rows}
        self.assertIn(
            'nic', bom_sections,
            "'bom' key must still contain the NIC module row",
        )
