"""
Phase 3 RED tests — transceiver metadata schema completeness (#415/#418).

All T1-T8 test classes are expected to FAIL until Phase 4 implements:
  - migration 0047 (profile schema update + seeding)
  - bom_export.py dataclass/service/CSV changes
  - topologyplan.html BOM panel column additions

T9 (regression guards) must PASS — they protect existing DAC/ACC behavior.

Spec: #417  Architecture: #416  Parent: #415
"""
from __future__ import annotations

import csv

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from users.models import ObjectPermission

from dcim.models import (
    Device, DeviceRole, DeviceType, Manufacturer, Module, ModuleBay,
    ModuleType, ModuleTypeProfile, Site,
)

from netbox_hedgehog.choices import GenerationStatusChoices
from netbox_hedgehog.models.topology_planning import GenerationState, TopologyPlan
from netbox_hedgehog.services.bom_export import (
    get_plan_bom,
    get_plan_bom_by_device,
    render_bom_csv,
    render_bom_per_device_csv,
)

User = get_user_model()

_DETAIL_URL_NAME = 'plugins:netbox_hedgehog:topologyplan_detail'


# ---------------------------------------------------------------------------
# Shared fixture mixin
# ---------------------------------------------------------------------------

class _XcvrMetaFixtureMixin:
    """Shared infrastructure for all transceiver-metadata test classes."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, _ = Manufacturer.objects.get_or_create(
            name='XCVR-META-Vendor', defaults={'slug': 'xcvr-meta-vendor'},
        )
        cls.nic_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='XCVR-META-NIC-200G',
            defaults={'attribute_data': {
                'cage_type': 'QSFP112', 'medium': 'MMF',
                'connector': 'MPO-12', 'standard': 'TEST-200G',
                'reach_class': 'SR', 'lane_count': 2,
            }},
        )
        cls.xcvr_mt_mmf, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='XCVR-META-XCVR-MMF',
            defaults={'attribute_data': {
                'cage_type': 'QSFP112', 'medium': 'MMF',
                'connector': 'LC', 'standard': 'META-SR4',
                'reach_class': 'SR',
            }},
        )
        cls.xcvr_mt_dac, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='XCVR-META-XCVR-DAC',
            defaults={'attribute_data': {
                'cage_type': 'QSFP28', 'medium': 'DAC',
                'connector': 'Direct', 'standard': None,
            }},
        )
        cls.xcvr_mt_acc, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='XCVR-META-XCVR-ACC',
            defaults={'attribute_data': {
                'cage_type': 'QSFP28', 'medium': 'ACC',
                'connector': 'Direct', 'standard': None,
            }},
        )
        cls.xcvr_mt_aoc, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='XCVR-META-XCVR-AOC',
            defaults={'attribute_data': {
                'cage_type': 'QSFP112', 'medium': 'MMF',
                'connector': 'MPO-12', 'standard': 'META-AOC',
                'cable_assembly_type': 'AOC',
            }},
        )
        cls.server_role, _ = DeviceRole.objects.get_or_create(
            slug='server', defaults={'name': 'Server', 'color': 'aa1409'},
        )
        cls.leaf_role, _ = DeviceRole.objects.get_or_create(
            name='Leaf', defaults={'slug': 'leaf', 'color': '2196f3'},
        )
        cls.site, _ = Site.objects.get_or_create(
            name='XCVR-META-Site', defaults={'slug': 'xcvr-meta-site'},
        )
        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='XCVR-META-Server-DT',
            defaults={'slug': 'xcvr-meta-server-dt'},
        )
        cls.switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='XCVR-META-Switch-DT',
            defaults={'slug': 'xcvr-meta-switch-dt'},
        )
        cls.superuser, _ = User.objects.get_or_create(
            username='xcvr-meta-admin',
            defaults={'is_staff': True, 'is_superuser': True},
        )
        cls.superuser.set_password('testpass123')
        cls.superuser.save()
        ct = ContentType.objects.get_for_model(TopologyPlan)
        obj_perm, _ = ObjectPermission.objects.get_or_create(
            name='xcvr-meta-view-plan',
            defaults={'actions': ['view']},
        )
        obj_perm.object_types.set([ct])
        obj_perm.users.add(cls.superuser)

    def _make_plan_generated(self, name):
        plan = TopologyPlan.objects.create(name=name)
        GenerationState.objects.create(
            plan=plan, status=GenerationStatusChoices.GENERATED,
            device_count=0, interface_count=0, cable_count=0, snapshot={},
        )
        return plan

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

    def _install_nic(self, device, bay_name, mt):
        bay = ModuleBay.objects.create(device=device, name=bay_name)
        return Module.objects.create(
            device=device, module_bay=bay, module_type=mt, status='active',
        )

    def _install_nested_xcvr(self, device, nic_module, cage_name, mt):
        bay = ModuleBay.objects.create(device=device, module=nic_module, name=cage_name)
        return Module.objects.create(
            device=device, module_bay=bay, module_type=mt, status='planned',
        )

    def _install_switch_xcvr(self, device, port_name, mt):
        bay = ModuleBay.objects.create(device=device, name=port_name)
        return Module.objects.create(
            device=device, module_bay=bay, module_type=mt, status='planned',
        )


# ---------------------------------------------------------------------------
# T1: Profile schema declares new fields
# Fails until migration 0047 adds them to the Network Transceiver profile.
# ---------------------------------------------------------------------------

class TransceiverMetadataProfileSchemaTestCase(_XcvrMetaFixtureMixin, TestCase):
    """T1.1-T1.8: Profile schema must declare all 5 new fields."""

    def _get_props(self):
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        self.assertIsNotNone(profile, "Network Transceiver profile must exist")
        return profile.schema.get('properties', {})

    def test_t1_1_host_serdes_gbps_per_lane_in_schema(self):
        """T1.1: host_serdes_gbps_per_lane declared in profile schema. FAILS until 0047."""
        self.assertIn('host_serdes_gbps_per_lane', self._get_props())

    def test_t1_2_optical_lane_pattern_in_schema(self):
        """T1.2: optical_lane_pattern declared in profile schema. FAILS until 0047."""
        self.assertIn('optical_lane_pattern', self._get_props())

    def test_t1_3_gearbox_present_in_schema(self):
        """T1.3: gearbox_present declared in profile schema. FAILS until 0047."""
        self.assertIn('gearbox_present', self._get_props())

    def test_t1_4_cable_assembly_type_in_schema(self):
        """T1.4: cable_assembly_type declared in profile schema. FAILS until 0047."""
        self.assertIn('cable_assembly_type', self._get_props())

    def test_t1_5_breakout_topology_in_schema(self):
        """T1.5: breakout_topology declared in profile schema. FAILS until 0047."""
        self.assertIn('breakout_topology', self._get_props())

    def test_t1_6_optical_lane_pattern_enum_values(self):
        """T1.6: optical_lane_pattern enum is correct. FAILS until 0047."""
        props = self._get_props()
        self.assertIn('optical_lane_pattern', props)
        enum = props['optical_lane_pattern'].get('enum', [])
        for val in ('SR', 'SR2', 'SR4', 'SR8', 'DR4', 'VR4', 'PSM4'):
            self.assertIn(val, enum, f"optical_lane_pattern enum missing {val!r}")

    def test_t1_7_cable_assembly_type_enum_values(self):
        """T1.7: cable_assembly_type enum is correct. FAILS until 0047."""
        props = self._get_props()
        self.assertIn('cable_assembly_type', props)
        enum = props['cable_assembly_type'].get('enum', [])
        for val in ('none', 'DAC', 'ACC', 'AOC'):
            self.assertIn(val, enum, f"cable_assembly_type enum missing {val!r}")

    # Regression guard — must PASS
    def test_t1_r1_existing_fields_still_in_schema(self):
        """T1.R1: reach_class, wavelength_nm, lane_count still in schema (regression guard)."""
        props = self._get_props()
        for field in ('reach_class', 'wavelength_nm', 'lane_count'):
            self.assertIn(field, props, f"Existing field {field!r} must not be removed")


# ---------------------------------------------------------------------------
# T2: Seeded module types carry new fields
# Fails until migration 0047 seeds attribute_data on existing module types.
# ---------------------------------------------------------------------------

class TransceiverMetadataSeededValuesTestCase(_XcvrMetaFixtureMixin, TestCase):
    """T2.1-T2.7: Seeded NVIDIA module types must have new fields in attribute_data."""

    def _get_bf3220(self):
        nvidia, _ = Manufacturer.objects.get_or_create(
            name='NVIDIA', defaults={'slug': 'nvidia'}
        )
        return ModuleType.objects.filter(
            manufacturer=nvidia, model='BlueField-3 BF3220'
        ).first()

    def _get_cx7_single(self):
        nvidia, _ = Manufacturer.objects.get_or_create(
            name='NVIDIA', defaults={'slug': 'nvidia'}
        )
        return ModuleType.objects.filter(
            manufacturer=nvidia, model='ConnectX-7 (Single-Port)'
        ).first()

    def _get_cx7_dual(self):
        nvidia, _ = Manufacturer.objects.get_or_create(
            name='NVIDIA', defaults={'slug': 'nvidia'}
        )
        return ModuleType.objects.filter(
            manufacturer=nvidia, model='ConnectX-7 (Dual-Port)'
        ).first()

    def test_t2_1_bf3220_optical_lane_pattern(self):
        """T2.1: BF3220 optical_lane_pattern == 'SR4'. FAILS until 0047 seeds it."""
        mt = self._get_bf3220()
        if mt is None:
            self.skipTest("BF3220 not seeded in this environment")
        self.assertEqual(mt.attribute_data.get('optical_lane_pattern'), 'SR4')

    def test_t2_2_bf3220_cable_assembly_type(self):
        """T2.2: BF3220 cable_assembly_type == 'none'. FAILS until 0047 seeds it."""
        mt = self._get_bf3220()
        if mt is None:
            self.skipTest("BF3220 not seeded")
        self.assertEqual(mt.attribute_data.get('cable_assembly_type'), 'none')

    def test_t2_3_bf3220_breakout_topology(self):
        """T2.3: BF3220 breakout_topology == '1x'. FAILS until 0047."""
        mt = self._get_bf3220()
        if mt is None:
            self.skipTest("BF3220 not seeded")
        self.assertEqual(mt.attribute_data.get('breakout_topology'), '1x')

    def test_t2_4_bf3220_lane_count_is_int(self):
        """T2.4: BF3220 lane_count is an integer. FAILS until 0047 seeds it."""
        mt = self._get_bf3220()
        if mt is None:
            self.skipTest("BF3220 not seeded")
        self.assertIsInstance(mt.attribute_data.get('lane_count'), int)

    def test_t2_5_cx7_single_cable_assembly_type(self):
        """T2.5: CX-7 Single cable_assembly_type == 'none' (NIC card, not an integrated assembly). FAILS until 0047."""
        mt = self._get_cx7_single()
        if mt is None:
            self.skipTest("CX-7 Single not seeded")
        self.assertEqual(mt.attribute_data.get('cable_assembly_type'), 'none')

    def test_t2_6_cx7_single_gearbox_present(self):
        """T2.6: CX-7 Single gearbox_present is None (not applicable for a NIC card). FAILS until 0047."""
        mt = self._get_cx7_single()
        if mt is None:
            self.skipTest("CX-7 Single not seeded")
        self.assertIsNone(mt.attribute_data.get('gearbox_present'))

    def test_t2_7_cx7_dual_breakout_topology(self):
        """T2.7: CX-7 Dual breakout_topology == '1x'. FAILS until 0047."""
        mt = self._get_cx7_dual()
        if mt is None:
            self.skipTest("CX-7 Dual not seeded")
        self.assertEqual(mt.attribute_data.get('breakout_topology'), '1x')


# ---------------------------------------------------------------------------
# T3: BOMLineItem carries all 8 new fields
# Fails until bom_export.py dataclass is updated.
# ---------------------------------------------------------------------------

class BOMLineItemMetadataFieldsTestCase(_XcvrMetaFixtureMixin, TestCase):
    """T3.1-T3.8: BOMLineItem must expose all new metadata fields."""

    def setUp(self):
        plan = self._make_plan_generated('T3-lineitem-fields')
        srv = self._server(plan, 'T3-srv')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_mmf)
        bom = get_plan_bom(plan)
        self.item = next(
            (i for i in bom.line_items if i.section == 'server_transceiver'), None
        )

    def _check_field(self, name):
        self.assertIsNotNone(self.item, "server_transceiver line item must exist")
        self.assertTrue(
            hasattr(self.item, name),
            f"BOMLineItem missing field {name!r}",
        )

    def test_t3_1_reach_class_field(self):
        """T3.1: BOMLineItem has reach_class. FAILS until bom_export.py updated."""
        self._check_field('reach_class')

    def test_t3_2_wavelength_nm_field(self):
        """T3.2: BOMLineItem has wavelength_nm. FAILS until bom_export.py updated."""
        self._check_field('wavelength_nm')

    def test_t3_3_lane_count_field(self):
        """T3.3: BOMLineItem has lane_count. FAILS until bom_export.py updated."""
        self._check_field('lane_count')

    def test_t3_4_host_serdes_gbps_per_lane_field(self):
        """T3.4: BOMLineItem has host_serdes_gbps_per_lane. FAILS until updated."""
        self._check_field('host_serdes_gbps_per_lane')

    def test_t3_5_optical_lane_pattern_field(self):
        """T3.5: BOMLineItem has optical_lane_pattern. FAILS until updated."""
        self._check_field('optical_lane_pattern')

    def test_t3_6_gearbox_present_field(self):
        """T3.6: BOMLineItem has gearbox_present. FAILS until updated."""
        self._check_field('gearbox_present')

    def test_t3_7_cable_assembly_type_field(self):
        """T3.7: BOMLineItem has cable_assembly_type. FAILS until updated."""
        self._check_field('cable_assembly_type')

    def test_t3_8_breakout_topology_field(self):
        """T3.8: BOMLineItem has breakout_topology. FAILS until updated."""
        self._check_field('breakout_topology')


# ---------------------------------------------------------------------------
# T4: Aggregate BOM CSV has new columns
# Fails until render_bom_csv updated.
# ---------------------------------------------------------------------------

class AggBOMCSVNewColumnsTestCase(_XcvrMetaFixtureMixin, TestCase):
    """T4.1-T4.9: Aggregate BOM CSV must include all new column headers."""

    def _get_header(self):
        plan = self._make_plan_generated('T4-agg-csv')
        srv = self._server(plan, 'T4-srv')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_mmf)
        bom = get_plan_bom(plan)
        csv_str = render_bom_csv(bom)
        return next(l for l in csv_str.splitlines() if l.strip())

    def test_t4_1_reach_class_column(self):
        """T4.1: CSV header contains reach_class. FAILS until render_bom_csv updated."""
        self.assertIn('reach_class', self._get_header())

    def test_t4_2_host_lane_count_column(self):
        """T4.2: CSV header contains host_lane_count (not lane_count). FAILS until updated."""
        self.assertIn('host_lane_count', self._get_header())

    def test_t4_3_host_serdes_column(self):
        """T4.3: CSV header contains host_serdes_gbps_per_lane. FAILS until updated."""
        self.assertIn('host_serdes_gbps_per_lane', self._get_header())

    def test_t4_4_optical_lane_pattern_column(self):
        """T4.4: CSV header contains optical_lane_pattern. FAILS until updated."""
        self.assertIn('optical_lane_pattern', self._get_header())

    def test_t4_5_gearbox_present_column(self):
        """T4.5: CSV header contains gearbox_present. FAILS until updated."""
        self.assertIn('gearbox_present', self._get_header())

    def test_t4_6_cable_assembly_type_column(self):
        """T4.6: CSV header contains cable_assembly_type. FAILS until updated."""
        self.assertIn('cable_assembly_type', self._get_header())

    def test_t4_7_breakout_topology_column(self):
        """T4.7: CSV header contains breakout_topology. FAILS until updated."""
        self.assertIn('breakout_topology', self._get_header())

    def test_t4_8_gearbox_null_renders_as_unknown(self):
        """T4.8: gearbox_present=None renders as 'Unknown' in CSV. FAILS until updated."""
        # xcvr_mt_mmf has no gearbox_present seeded → None → should render 'Unknown'
        plan = self._make_plan_generated('T4-gearbox-null')
        srv = self._server(plan, 'T4-g-srv')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_mmf)
        bom = get_plan_bom(plan)
        csv_str = render_bom_csv(bom)
        data = [l for l in csv_str.splitlines() if l.strip() and not l.startswith('#')]
        rows = list(csv.DictReader(iter(data)))
        xcvr_rows = [r for r in rows if r.get('section') == 'server_transceiver']
        self.assertTrue(xcvr_rows, "server_transceiver row must exist")
        self.assertEqual(xcvr_rows[0].get('gearbox_present'), 'Unknown')

    def test_t4_9_dac_optical_lane_pattern_is_empty(self):
        """T4.9: DAC module optical_lane_pattern is empty in CSV. FAILS until updated."""
        plan = self._make_plan_generated('T4-dac-opl')
        srv = self._server(plan, 'T4-dac-srv')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_dac)
        bom = get_plan_bom(plan)
        csv_str = render_bom_csv(bom)
        data = [l for l in csv_str.splitlines() if l.strip() and not l.startswith('#')]
        rows = list(csv.DictReader(iter(data)))
        xcvr_rows = [r for r in rows if r.get('section') == 'server_transceiver']
        self.assertTrue(xcvr_rows, "server_transceiver row for DAC must exist")
        self.assertEqual(xcvr_rows[0].get('optical_lane_pattern', 'MISSING'), '')


# ---------------------------------------------------------------------------
# T5: Per-device BOM CSV has new columns
# Mirror of T4 for render_bom_per_device_csv.
# ---------------------------------------------------------------------------

class PerDeviceBOMCSVNewColumnsTestCase(_XcvrMetaFixtureMixin, TestCase):
    """T5.1-T5.5: Per-device CSV must include all new column headers."""

    def _get_header(self):
        plan = self._make_plan_generated('T5-pd-csv')
        srv = self._server(plan, 'T5-pd-srv')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_mmf)
        bom = get_plan_bom_by_device(plan)
        csv_str = render_bom_per_device_csv(bom)
        return next(l for l in csv_str.splitlines() if l.strip())

    def test_t5_1_host_lane_count_column(self):
        """T5.1: Per-device CSV header has host_lane_count. FAILS until updated."""
        self.assertIn('host_lane_count', self._get_header())

    def test_t5_2_optical_lane_pattern_column(self):
        """T5.2: Per-device CSV header has optical_lane_pattern. FAILS until updated."""
        self.assertIn('optical_lane_pattern', self._get_header())

    def test_t5_3_gearbox_present_column(self):
        """T5.3: Per-device CSV header has gearbox_present. FAILS until updated."""
        self.assertIn('gearbox_present', self._get_header())

    def test_t5_4_cable_assembly_type_column(self):
        """T5.4: Per-device CSV header has cable_assembly_type. FAILS until updated."""
        self.assertIn('cable_assembly_type', self._get_header())

    def test_t5_5_breakout_topology_column(self):
        """T5.5: Per-device CSV header has breakout_topology. FAILS until updated."""
        self.assertIn('breakout_topology', self._get_header())


# ---------------------------------------------------------------------------
# T6: BOM UI panel has 3 new column headers
# Fails until topologyplan.html template updated.
# ---------------------------------------------------------------------------

class BOMPanelNewColumnsUITestCase(_XcvrMetaFixtureMixin, TestCase):
    """T6.1-T6.4: BOM panel template must show Reach Class, Wavelength, Optical Lane Pattern."""

    def setUp(self):
        self.client = Client()
        self.client.login(username='xcvr-meta-admin', password='testpass123')
        plan = self._make_plan_generated('T6-panel-cols')
        srv = self._server(plan, 'T6-srv')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_mmf)
        self.url = reverse(_DETAIL_URL_NAME, args=[plan.pk])

    def _content(self):
        return self.client.get(self.url).content.decode()

    def test_t6_1_reach_class_header(self):
        """T6.1: BOM panel has <th>Reach Class</th>. FAILS until template updated."""
        self.assertIn('Reach Class', self._content())

    def test_t6_2_wavelength_header(self):
        """T6.2: BOM panel has Wavelength (nm) header. FAILS until template updated."""
        self.assertIn('Wavelength (nm)', self._content())

    def test_t6_3_optical_lane_pattern_header(self):
        """T6.3: BOM panel has Optical Lane Pattern header. FAILS until template updated."""
        self.assertIn('Optical Lane Pattern', self._content())

    def test_t6_4_technical_fields_not_in_panel(self):
        """T6.4: Host Lane Count not in BOM panel (CSV-only). Must PASS."""
        self.assertNotIn('Host Lane Count', self._content())


# ---------------------------------------------------------------------------
# T7+T8: AOC suppression behavior
# T7 must FAIL (AOC currently not suppressed — medium='MMF' not in _CABLE_ASSEMBLY_MEDIUMS).
# T8 regression guards must PASS (existing DAC/ACC suppression unchanged).
# ---------------------------------------------------------------------------

class AOCSuppressionTestCase(_XcvrMetaFixtureMixin, TestCase):
    """T7.1-T7.3: Switch-side AOC must be suppressed. FAILS until bom_export.py updated."""

    def test_t7_1_switch_side_aoc_suppressed(self):
        """T7.1: Switch-side AOC not in line_items. FAILS — AOC medium='MMF' not suppressed yet."""
        plan = self._make_plan_generated('T7-aoc-suppress')
        sw = self._switch(plan, 'T7-sw')
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_aoc)
        bom = get_plan_bom(plan)
        sw_items = [i for i in bom.line_items if i.section == 'switch_transceiver']
        self.assertEqual(sw_items, [], "Switch-side AOC must be suppressed")

    def test_t7_2_aoc_suppressed_count_incremented(self):
        """T7.2: suppressed_count == 1 for switch-side AOC. FAILS until updated."""
        plan = self._make_plan_generated('T7-aoc-count')
        sw = self._switch(plan, 'T7-cnt-sw')
        self._install_switch_xcvr(sw, 'E1/2', self.xcvr_mt_aoc)
        bom = get_plan_bom(plan)
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 1)

    def test_t7_3_server_side_aoc_not_suppressed(self):
        """T7.3: Server-side AOC (nested xcvr) appears in line_items. Must PASS."""
        plan = self._make_plan_generated('T7-aoc-srv')
        srv = self._server(plan, 'T7-aoc-srv-dev')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_aoc)
        bom = get_plan_bom(plan)
        srv_items = [i for i in bom.line_items if i.section == 'server_transceiver']
        self.assertTrue(srv_items, "Server-side AOC must appear in line_items")


class CableAssemblyRegressionTestCase(_XcvrMetaFixtureMixin, TestCase):
    """T8: Existing DAC/ACC suppression unchanged. All must PASS (regression guards)."""

    def test_t8_1_switch_dac_suppressed(self):
        """T8.1: Switch-side DAC (medium='DAC') still suppressed. Must PASS."""
        plan = self._make_plan_generated('T8-dac')
        sw = self._switch(plan, 'T8-dac-sw')
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_dac)
        bom = get_plan_bom(plan)
        self.assertEqual([i for i in bom.line_items if i.section == 'switch_transceiver'], [])
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 1)

    def test_t8_2_switch_acc_suppressed(self):
        """T8.2: Switch-side ACC (medium='ACC') still suppressed. Must PASS."""
        plan = self._make_plan_generated('T8-acc')
        sw = self._switch(plan, 'T8-acc-sw')
        self._install_switch_xcvr(sw, 'E1/1', self.xcvr_mt_acc)
        bom = get_plan_bom(plan)
        self.assertEqual([i for i in bom.line_items if i.section == 'switch_transceiver'], [])
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 1)

    def test_t8_3_server_dac_is_cable_assembly(self):
        """T8.3: Server-side DAC has is_cable_assembly=True. Must PASS."""
        plan = self._make_plan_generated('T8-dac-srv')
        srv = self._server(plan, 'T8-dac-srv-dev')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_dac)
        bom = get_plan_bom(plan)
        item = next(i for i in bom.line_items if i.section == 'server_transceiver')
        self.assertTrue(item.is_cable_assembly)

    def test_t8_4_mmf_xcvr_not_cable_assembly(self):
        """T8.4: MMF standalone xcvr has is_cable_assembly=False. Must PASS."""
        plan = self._make_plan_generated('T8-mmf')
        srv = self._server(plan, 'T8-mmf-srv')
        nic = self._install_nic(srv, 'fe', self.nic_mt)
        self._install_nested_xcvr(srv, nic, 'cage-0', self.xcvr_mt_mmf)
        bom = get_plan_bom(plan)
        item = next(i for i in bom.line_items if i.section == 'server_transceiver')
        self.assertFalse(item.is_cable_assembly)
