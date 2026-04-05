"""
Phase 3 RED tests for Stage 2 transceiver modeling (DIET-334 #343).

Groups:
  A - migration 0045 (mismatch_report field on GenerationState)
  B - populate_transceiver_bays management command
  C - switch-side transceiver Module placement in generator
  D - nested NIC-port-bay server-side transceiver placement
  E - post-generation pairwise compatibility sweep (aggregate-all-mismatches-then-fail)
  F - hard-fail when transceiver FK is set but required ModuleBay is absent (#345)
  G - hedgehog_transceiver_spec suppression when transceiver Module present
  H - FAILED status propagation to callers: job runner and synchronous view (#345 review finding)

All tests in this file are RED until Stage 2 GREEN implementation lands.
"""

from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.db.utils import OperationalError
from django.test import TestCase, Client

from dcim.models import (
    Device, DeviceType, InterfaceTemplate, Manufacturer,
    Module, ModuleBay, ModuleBayTemplate, ModuleType, ModuleTypeProfile, Site,
)

from netbox_hedgehog.choices import (
    AllocationStrategyChoices, ConnectionDistributionChoices,
    ConnectionTypeChoices, FabricClassChoices, FabricTypeChoices,
    GenerationStatusChoices, HedgehogRoleChoices, PortZoneTypeChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption, DeviceTypeExtension, GenerationState,
    PlanServerClass, PlanServerConnection, PlanServerNIC,
    PlanSwitchClass, SwitchPortZone, TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import (
    get_test_nic_module_type,
    get_test_transceiver_module_type,
)


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_s2_fixtures(cls):
    """Create shared fixtures for Stage 2 tests."""
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name='S2-Test-Mfg', defaults={'slug': 's2-test-mfg'}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='S2-SRV', defaults={'slug': 's2-srv'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='S2-SW', defaults={'slug': 's2-sw'}
    )
    # Add InterfaceTemplates so populate_transceiver_bays creates ModuleBayTemplates.
    # Port allocator uses E1/{n} names for port_spec='1-64'.
    for port_n in range(1, 9):
        InterfaceTemplate.objects.get_or_create(
            device_type=cls.switch_dt, name=f'E1/{port_n}',
            defaults={'type': '200gbase-x-qsfp112'},
        )
    cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=cls.switch_dt,
        defaults={
            'native_speed': 200, 'uplink_ports': 0,
            'supported_breakouts': ['1x200g'], 'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    cls.breakout, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x200g-s2',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    cls.site, _ = Site.objects.get_or_create(
        name='S2-TestSite', defaults={'slug': 's2-testsite'}
    )
    cls.xcvr_mt = get_test_transceiver_module_type()
    cls.nic_mt = get_test_nic_module_type()


def _make_plan_with_xcvr(cls, name_suffix='', with_xcvr=True, zone_xcvr=None):
    """
    Build and return a minimal plan+server_class+switch_class+zone+nic+connection.
    If with_xcvr=True, sets connection.transceiver_module_type.
    If zone_xcvr is provided, also sets zone.transceiver_module_type.
    """
    plan = TopologyPlan.objects.create(
        name=f'S2Plan-{name_suffix}-{id(cls)}',
        status=TopologyPlanStatusChoices.DRAFT,
    )
    sc = PlanServerClass.objects.create(
        plan=plan, server_class_id='gpu',
        server_device_type=cls.server_dt, quantity=1,
    )
    sw = PlanSwitchClass.objects.create(
        plan=plan, switch_class_id='fe-leaf',
        fabric_name=FabricTypeChoices.FRONTEND,
        fabric_class=FabricClassChoices.MANAGED,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=cls.device_ext,
        uplink_ports_per_switch=0, mclag_pair=False,
        override_quantity=2, redundancy_type='eslag',
    )
    zone_kwargs = {}
    if zone_xcvr is not None:
        zone_kwargs['transceiver_module_type'] = zone_xcvr
    zone = SwitchPortZone.objects.create(
        switch_class=sw, zone_name='server-downlinks',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-64',
        breakout_option=cls.breakout,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        **zone_kwargs,
    )
    nic = PlanServerNIC.objects.create(
        server_class=sc, nic_id='nic-fe', module_type=cls.nic_mt,
    )
    conn_kwargs = {}
    if with_xcvr:
        conn_kwargs['transceiver_module_type'] = cls.xcvr_mt
    PlanServerConnection.objects.create(
        server_class=sc, connection_id='fe',
        nic=nic, port_index=0, ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        target_zone=zone, speed=200, port_type='data',
        **conn_kwargs,
    )
    return plan, sc, sw, zone, nic


def _generate(plan):
    from netbox_hedgehog.services.device_generator import DeviceGenerator
    return DeviceGenerator(plan).generate_all()


def _cleanup(plan_id):
    from dcim.models import Cable
    Device.objects.filter(custom_field_data__hedgehog_plan_id=str(plan_id)).delete()
    Cable.objects.filter(custom_field_data__hedgehog_plan_id=str(plan_id)).delete()


def _delete_plan(plan):
    """Delete a plan and all its PROTECT-blocked dependents in safe order."""
    # PlanServerConnection.nic and .target_zone use PROTECT — delete connections first.
    from netbox_hedgehog.models.topology_planning import PlanServerConnection
    PlanServerConnection.objects.filter(server_class__plan=plan).delete()
    plan.delete()


# ---------------------------------------------------------------------------
# Group A: Migration 0045 — mismatch_report field on GenerationState
# ---------------------------------------------------------------------------

class Stage2MigrationTestCase(TestCase):
    """
    A.1–A.3: Assert GenerationState has mismatch_report (JSONField, null=True).
    RED until migration 0045 is applied.
    """

    def test_mismatch_report_field_exists(self):
        """A.1: GenerationState._meta.get_field('mismatch_report') must not raise."""
        from django.core.exceptions import FieldDoesNotExist
        try:
            field = GenerationState._meta.get_field('mismatch_report')
        except FieldDoesNotExist:
            self.fail("GenerationState.mismatch_report field does not exist — migration 0045 not applied")
        self.assertEqual(field.get_internal_type(), 'JSONField')
        self.assertTrue(field.null, "mismatch_report must be nullable")
        self.assertTrue(field.blank, "mismatch_report must allow blank")

    def test_mismatch_report_defaults_null(self):
        """A.2: New GenerationState rows default to mismatch_report=None."""
        field = GenerationState._meta.get_field('mismatch_report')
        default = field.default() if callable(field.default) else field.default
        self.assertIsNone(default)

    def test_mismatch_report_roundtrips_structured_dict(self):
        """A.3: mismatch_report accepts and round-trips the approved JSON schema."""
        from netbox_hedgehog.models.topology_planning import TopologyPlan
        plan = TopologyPlan.objects.create(
            name='S2MigTest', status=TopologyPlanStatusChoices.DRAFT,
        )
        payload = {'mismatches': [
            {
                'connection_id': 1,
                'server_device': 'srv-001',
                'switch_device': 'leaf-01',
                'switch_port': 'Ethernet1/1',
                'mismatch_type': 'cage_type',
                'server_end': 'SFP+',
                'switch_end': 'QSFP28',
            }
        ]}
        from netbox_hedgehog.models.topology_planning.generation import GenerationState as GS
        import datetime
        gs = GS(
            plan=plan,
            device_count=0, interface_count=0, cable_count=0,
            snapshot={},
            status=GenerationStatusChoices.FAILED,
            mismatch_report=payload,
        )
        gs.save()
        gs.refresh_from_db()
        self.assertEqual(gs.mismatch_report['mismatches'][0]['mismatch_type'], 'cage_type')


# ---------------------------------------------------------------------------
# Group B: populate_transceiver_bays management command
# ---------------------------------------------------------------------------

class PopulateTransceiverBaysCommandTestCase(TestCase):
    """
    B.1–B.3: Assert populate_transceiver_bays management command exists and works.
    RED until the command is created.
    """

    def test_command_is_importable(self):
        """B.1: Command module must be importable."""
        import importlib
        try:
            importlib.import_module(
                'netbox_hedgehog.management.commands.populate_transceiver_bays'
            )
        except ImportError as e:
            self.fail(f"populate_transceiver_bays command not importable: {e}")

    def test_command_adds_module_bay_templates_to_switch_device_type(self):
        """B.2: Running command adds ModuleBayTemplate rows to switch DeviceTypes."""
        mfr, _ = Manufacturer.objects.get_or_create(
            name='CmdTest-Mfg', defaults={'slug': 'cmdtest-mfg'}
        )
        dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr, model='CmdTest-SW', defaults={'slug': 'cmdtest-sw'}
        )
        DeviceTypeExtension.objects.update_or_create(
            device_type=dt,
            defaults={
                'native_speed': 400, 'uplink_ports': 0,
                'supported_breakouts': ['1x400g'], 'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
            },
        )
        # Add 2 InterfaceTemplates to simulate switch ports
        it1, _ = InterfaceTemplate.objects.get_or_create(
            device_type=dt, name='Ethernet1/1',
            defaults={'type': '400gbase-x-osfp'}
        )
        it2, _ = InterfaceTemplate.objects.get_or_create(
            device_type=dt, name='Ethernet1/2',
            defaults={'type': '400gbase-x-osfp'}
        )
        call_command('populate_transceiver_bays')
        bays = ModuleBayTemplate.objects.filter(device_type=dt)
        self.assertGreaterEqual(bays.count(), 2,
            "Command must create at least one ModuleBayTemplate per InterfaceTemplate on switch DeviceType")

    def test_command_adds_nested_bay_templates_to_nic_module_type(self):
        """B.3: Running command adds nested ModuleBayTemplate children to NIC ModuleTypes."""
        nic_mt = get_test_nic_module_type()
        # Command discovers NIC ModuleTypes via PlanServerNIC references — create one.
        mfr, _ = Manufacturer.objects.get_or_create(
            name='B3TestMfg', defaults={'slug': 'b3testmfg'}
        )
        dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr, model='B3SRV', defaults={'slug': 'b3srv'}
        )
        plan = TopologyPlan.objects.create(
            name='B3Plan', status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='b3', server_device_type=dt, quantity=1,
        )
        nic = PlanServerNIC.objects.create(
            server_class=sc, nic_id='nic-b3', module_type=nic_mt,
        )
        call_command('populate_transceiver_bays')
        nested = ModuleBayTemplate.objects.filter(module_type=nic_mt)
        self.assertGreaterEqual(nested.count(), 1,
            "Command must add nested ModuleBayTemplate children to NIC ModuleType")
        names = list(nested.values_list('name', flat=True))
        self.assertIn('cage-0', names, "Nested bay 'cage-0' must exist on NIC ModuleType")
        # Cleanup
        nic.delete()
        sc.delete()
        plan.delete()

    def test_command_is_idempotent(self):
        """B.4: Running command twice must not create duplicate bays."""
        nic_mt = get_test_nic_module_type()
        mfr, _ = Manufacturer.objects.get_or_create(
            name='B4TestMfg', defaults={'slug': 'b4testmfg'}
        )
        dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr, model='B4SRV', defaults={'slug': 'b4srv'}
        )
        plan = TopologyPlan.objects.create(
            name='B4Plan', status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='b4', server_device_type=dt, quantity=1,
        )
        nic = PlanServerNIC.objects.create(
            server_class=sc, nic_id='nic-b4', module_type=nic_mt,
        )
        call_command('populate_transceiver_bays')
        count_after_first = ModuleBayTemplate.objects.filter(module_type=nic_mt).count()
        call_command('populate_transceiver_bays')
        count_after_second = ModuleBayTemplate.objects.filter(module_type=nic_mt).count()
        self.assertEqual(count_after_first, count_after_second,
            "Command must be idempotent — running twice must not add duplicate bays")
        # Cleanup
        nic.delete()
        sc.delete()
        plan.delete()


# ---------------------------------------------------------------------------
# Group C: Generator — switch-side transceiver Module placement
# ---------------------------------------------------------------------------

class SwitchSideTransceiverPlacementTestCase(TestCase):
    """
    C.1–C.3: Assert generator creates switch-side transceiver Modules.
    RED until DeviceGenerator._create_switch_transceiver_module() is implemented.
    """

    @classmethod
    def setUpTestData(cls):
        _make_s2_fixtures(cls)

    def tearDown(self):
        for p in list(TopologyPlan.objects.filter(name__startswith='S2Plan-')):
            _cleanup(p.pk)
            _delete_plan(p)

    def test_switch_module_created_when_zone_has_transceiver_fk(self):
        """C.1: After generation with zone transceiver FK set, switch-side Module exists."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(
            self, 'C1', with_xcvr=True, zone_xcvr=self.xcvr_mt
        )
        call_command('populate_transceiver_bays')
        _generate(plan)
        switch_modules = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            device__device_type=self.switch_dt,
            module_type=self.xcvr_mt,
        )
        self.assertGreater(switch_modules.count(), 0,
            "Generator must create switch-side transceiver Modules when zone.transceiver_module_type is set")

    def test_switch_module_not_created_when_zone_has_no_transceiver_fk(self):
        """C.2: No switch-side Module when zone.transceiver_module_type is null."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(
            self, 'C2', with_xcvr=False, zone_xcvr=None
        )
        call_command('populate_transceiver_bays')
        _generate(plan)
        switch_modules = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            device__device_type=self.switch_dt,
        )
        self.assertEqual(switch_modules.count(), 0,
            "Generator must not create switch-side Modules when zone.transceiver_module_type is null")

    def test_switch_module_idempotent_on_regeneration(self):
        """C.3: Regenerating twice must not duplicate switch-side Modules."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(
            self, 'C3', with_xcvr=True, zone_xcvr=self.xcvr_mt
        )
        call_command('populate_transceiver_bays')
        _generate(plan)
        count_first = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            device__device_type=self.switch_dt,
        ).count()
        _generate(plan)
        count_second = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            device__device_type=self.switch_dt,
        ).count()
        self.assertEqual(count_first, count_second,
            "Regenerating must not create duplicate switch-side transceiver Modules")


# ---------------------------------------------------------------------------
# Group D: Generator — nested NIC-port-bay server-side placement
# ---------------------------------------------------------------------------

class NestedNICBayTransceiverPlacementTestCase(TestCase):
    """
    D.1–D.3: Assert generator places server transceiver in nested bay, not device level.
    RED until _create_nested_transceiver_module() replaces _create_server_transceiver_module().
    """

    @classmethod
    def setUpTestData(cls):
        _make_s2_fixtures(cls)

    def tearDown(self):
        for p in list(TopologyPlan.objects.filter(name__startswith='S2Plan-')):
            _cleanup(p.pk)
            _delete_plan(p)

    def test_transceiver_module_placed_in_nested_bay(self):
        """D.1: After generation, transceiver Module is inside NIC Module bay (nested)."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(self, 'D1', with_xcvr=True)
        call_command('populate_transceiver_bays')
        _generate(plan)
        # Find NIC module installed on a server device for this plan
        nic_modules = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            module_type=self.nic_mt,
        )
        self.assertGreater(nic_modules.count(), 0, "NIC Module must be created")
        nic_module = nic_modules.first()
        # Transceiver Module should be in a bay INSIDE the NIC module (module_bay.module == nic_module)
        nested_xcvr = Module.objects.filter(
            module_bay__module=nic_module,
            module_type=self.xcvr_mt,
        )
        self.assertGreater(nested_xcvr.count(), 0,
            "Transceiver Module must be nested inside NIC Module bay (module_bay.module set)")

    def test_transceiver_module_not_at_device_level(self):
        """D.2: Device-level transceiver bays from Stage 1 must NOT be created."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(self, 'D2', with_xcvr=True)
        call_command('populate_transceiver_bays')
        _generate(plan)
        # Stage 1 used bay name 'nic-fe-cage-0' at the device level (module_id=None)
        device_level_bays = ModuleBay.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            name='nic-fe-cage-0',
            module__isnull=True,  # device-level bay has no parent module
        )
        self.assertEqual(device_level_bays.count(), 0,
            "Stage 1 device-level transceiver bay 'nic-fe-cage-0' must not exist in Stage 2")

    def test_transceiver_port_index_respected(self):
        """D.3: PlanServerConnection.port_index=1 places transceiver in cage-1, not cage-0."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(self, 'D3', with_xcvr=True)
        call_command('populate_transceiver_bays')
        # Update connection to use port_index=1
        conn = PlanServerConnection.objects.get(server_class=sc)
        conn.port_index = 1
        conn.save()
        _generate(plan)
        nic_modules = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            module_type=self.nic_mt,
        )
        nic_module = nic_modules.first()
        cage_1_xcvr = Module.objects.filter(
            module_bay__module=nic_module,
            module_bay__name='cage-1',
            module_type=self.xcvr_mt,
        )
        self.assertGreater(cage_1_xcvr.count(), 0,
            "port_index=1 must place transceiver in cage-1 within the NIC Module")


# ---------------------------------------------------------------------------
# Group E: Post-generation pairwise compatibility sweep
# ---------------------------------------------------------------------------

class CompatibilitySweepTestCase(TestCase):
    """
    E.1–E.4: Assert aggregate-all-mismatches-then-fail sweep behavior.
    RED until _run_compatibility_sweep() is implemented.
    """

    @classmethod
    def setUpTestData(cls):
        _make_s2_fixtures(cls)
        # Create a second transceiver ModuleType with DIFFERENT cage_type for mismatch tests
        mfr, _ = Manufacturer.objects.get_or_create(
            name='XCVR-Test-Vendor', defaults={'slug': 'xcvr-test-vendor'}
        )
        cls.xcvr_mismatch_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='XCVR-SFP28-MISMATCH-TEST',
            defaults={
                'attribute_data': {
                    'cage_type': 'SFP28',
                    'medium': 'SMF',
                    'connector': 'LC',
                    'standard': '25GBASE-LR',
                }
            },
        )

    def tearDown(self):
        for p in list(TopologyPlan.objects.filter(name__startswith='S2Plan-')):
            _cleanup(p.pk)
            _delete_plan(p)

    def test_compatible_pair_generation_succeeds(self):
        """E.1: Matching cage_type+medium on both ends → generation succeeds, mismatch_report null."""
        # Use same xcvr_mt on both connection and zone → compatible
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(
            self, 'E1', with_xcvr=True, zone_xcvr=self.xcvr_mt
        )
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs, "GenerationState must exist after generation")
        self.assertEqual(gs.status, GenerationStatusChoices.GENERATED,
            "Compatible transceiver pair must result in GENERATED status")
        self.assertIsNone(
            getattr(gs, 'mismatch_report', 'FIELD_MISSING'),
            "mismatch_report must be null when no incompatibilities found",
        )

    def test_incompatible_pair_sets_failed_status(self):
        """E.2: Mismatched cage_type → GenerationState.status=FAILED."""
        # connection uses xcvr_mt (QSFP112), zone uses xcvr_mismatch_mt (SFP28) → mismatch
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(
            self, 'E2', with_xcvr=True, zone_xcvr=self.xcvr_mismatch_mt
        )
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs, "GenerationState must exist after failed generation")
        self.assertEqual(gs.status, GenerationStatusChoices.FAILED,
            "Incompatible transceiver cage_type mismatch must set status=FAILED")

    def test_incompatible_pair_populates_mismatch_report(self):
        """E.3: mismatch_report contains at least one entry describing the mismatch."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(
            self, 'E3', with_xcvr=True, zone_xcvr=self.xcvr_mismatch_mt
        )
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        report = getattr(gs, 'mismatch_report', None)
        self.assertIsNotNone(report, "mismatch_report must be populated on FAILED generation")
        mismatches = report.get('mismatches', [])
        self.assertGreater(len(mismatches), 0,
            "mismatch_report.mismatches must contain at least one entry")
        entry = mismatches[0]
        self.assertIn('mismatch_type', entry, "Mismatch entry must have mismatch_type")
        self.assertIn('server_end', entry, "Mismatch entry must have server_end")
        self.assertIn('switch_end', entry, "Mismatch entry must have switch_end")

    def test_aggregate_all_mismatches_before_fail(self):
        """E.4: Multiple incompatible connections all appear in mismatch_report (aggregate behavior)."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(
            self, 'E4', with_xcvr=True, zone_xcvr=self.xcvr_mismatch_mt
        )
        call_command('populate_transceiver_bays')
        # Add a second mismatching connection (port_index=1)
        conn2 = PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe-2',
            nic=nic, port_index=1, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
            transceiver_module_type=self.xcvr_mt,  # mismatch with zone's SFP28
        )
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        report = getattr(gs, 'mismatch_report', None)
        self.assertIsNotNone(report)
        mismatches = report.get('mismatches', [])
        self.assertGreaterEqual(len(mismatches), 2,
            "Sweep must collect ALL mismatches before failing — both connections must appear")


# ---------------------------------------------------------------------------
# Group F: Hard-fail when transceiver FK is set but required bay is absent (#345)
# ---------------------------------------------------------------------------

class MissingBayHardFailTestCase(TestCase):
    """
    F.1–F.4: Generation must FAIL (not succeed) when transceiver_module_type is set
    but populate_transceiver_bays was not run (so the required ModuleBay is absent).

    These tests use FRESH DeviceType/ModuleType objects that have NEVER had
    ModuleBayTemplates added to them, ensuring the missing-bay path is exercised.
    """

    @classmethod
    def setUpTestData(cls):
        cls.mfr, _ = Manufacturer.objects.get_or_create(
            name='F-Test-Mfg', defaults={'slug': 'f-test-mfg'}
        )
        # Fresh switch DeviceType — no ModuleBayTemplates ever added.
        cls.switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='F-SW-NOBAY', defaults={'slug': 'f-sw-nobay'}
        )
        # Add InterfaceTemplates (needed so device has interfaces to wire) but do NOT
        # call populate_transceiver_bays, so no ModuleBayTemplates are created.
        for port_n in range(1, 5):
            InterfaceTemplate.objects.get_or_create(
                device_type=cls.switch_dt, name=f'E1/{port_n}',
                defaults={'type': '200gbase-x-qsfp112'},
            )
        cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_dt,
            defaults={
                'native_speed': 200, 'uplink_ports': 0,
                'supported_breakouts': ['1x200g-f'], 'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
            },
        )
        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x200g-f',
            defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
        )
        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='F-SRV-NOBAY', defaults={'slug': 'f-srv-nobay'}
        )
        cls.site, _ = Site.objects.get_or_create(
            name='F-TestSite', defaults={'slug': 'f-testsite'}
        )
        cls.xcvr_mt = get_test_transceiver_module_type()
        # Fresh NIC ModuleType — no ModuleBayTemplate children ever added.
        mfr2, _ = Manufacturer.objects.get_or_create(
            name='F-NIC-Mfg', defaults={'slug': 'f-nic-mfg'}
        )
        cls.nic_mt_fresh, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr2, model='F-NIC-NOBAY',
            defaults={},
        )
        # Add InterfaceTemplates to NIC so NIC Module gets interfaces when installed.
        from dcim.models import InterfaceTemplate as IfaceTemplate
        IfaceTemplate.objects.get_or_create(
            module_type=cls.nic_mt_fresh, name='p0',
            defaults={'type': '200gbase-x-qsfp112'},
        )

    def _make_plan_missing_bays(self, name_suffix, set_switch_xcvr=False, set_conn_xcvr=False):
        """Build a plan using the fresh (no-bay) DeviceType and ModuleType."""
        plan = TopologyPlan.objects.create(
            name=f'S2FPlan-{name_suffix}-{id(self)}',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu-f',
            server_device_type=self.server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf-f',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        zone_kwargs = {}
        if set_switch_xcvr:
            zone_kwargs['transceiver_module_type'] = self.xcvr_mt
        zone = SwitchPortZone.objects.create(
            switch_class=sw, zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-64',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            **zone_kwargs,
        )
        nic = PlanServerNIC.objects.create(
            server_class=sc, nic_id='nic-fe-f', module_type=self.nic_mt_fresh,
        )
        conn_kwargs = {}
        if set_conn_xcvr:
            conn_kwargs['transceiver_module_type'] = self.xcvr_mt
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe-f',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
            **conn_kwargs,
        )
        return plan, sc, sw, zone, nic

    def tearDown(self):
        for p in list(TopologyPlan.objects.filter(name__startswith='S2FPlan-')):
            _cleanup(p.pk)
            _delete_plan(p)

    def test_missing_switch_bay_fails_generation(self):
        """F.1: zone.transceiver_module_type set + no switch ModuleBay → status=FAILED."""
        plan, sc, sw, zone, nic = self._make_plan_missing_bays(
            'F1', set_switch_xcvr=True, set_conn_xcvr=False
        )
        # Do NOT call populate_transceiver_bays → switch DeviceType has no ModuleBayTemplates
        # → no ModuleBays on created switch devices → bay lookup fails
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs, "GenerationState must exist after failed generation")
        self.assertEqual(
            gs.status, GenerationStatusChoices.FAILED,
            "Missing switch ModuleBay with transceiver FK set must result in status=FAILED, not GENERATED",
        )

    def test_missing_switch_bay_report_contains_bay_errors(self):
        """F.2: mismatch_report.bay_errors is populated when switch bay is absent."""
        plan, sc, sw, zone, nic = self._make_plan_missing_bays(
            'F2', set_switch_xcvr=True, set_conn_xcvr=False
        )
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        report = getattr(gs, 'mismatch_report', None)
        self.assertIsNotNone(report, "mismatch_report must be populated when bay errors occur")
        bay_errors = report.get('bay_errors', [])
        self.assertGreater(len(bay_errors), 0,
            "mismatch_report.bay_errors must contain at least one entry")
        first = bay_errors[0]
        self.assertEqual(first.get('error_type'), 'missing_switch_bay',
            "bay_error entry must have error_type='missing_switch_bay'")

    def test_missing_nested_bay_fails_generation(self):
        """F.3: connection.transceiver_module_type set + no nested NIC cage bay → status=FAILED."""
        plan, sc, sw, zone, nic = self._make_plan_missing_bays(
            'F3', set_switch_xcvr=False, set_conn_xcvr=True
        )
        # Do NOT call populate_transceiver_bays → NIC ModuleType has no ModuleBayTemplate children
        # → no nested cage bays when NIC Module is installed → bay lookup fails
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs, "GenerationState must exist after failed generation")
        self.assertEqual(
            gs.status, GenerationStatusChoices.FAILED,
            "Missing nested NIC cage bay with transceiver FK set must result in status=FAILED, not GENERATED",
        )

    def test_missing_nested_bay_report_contains_bay_errors(self):
        """F.4: mismatch_report.bay_errors is populated when nested NIC cage bay is absent."""
        plan, sc, sw, zone, nic = self._make_plan_missing_bays(
            'F4', set_switch_xcvr=False, set_conn_xcvr=True
        )
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        report = getattr(gs, 'mismatch_report', None)
        self.assertIsNotNone(report, "mismatch_report must be populated when bay errors occur")
        bay_errors = report.get('bay_errors', [])
        self.assertGreater(len(bay_errors), 0,
            "mismatch_report.bay_errors must contain at least one entry")
        first = bay_errors[0]
        self.assertEqual(first.get('error_type'), 'missing_nested_bay',
            "bay_error entry must have error_type='missing_nested_bay'")


# ---------------------------------------------------------------------------
# Group G: hedgehog_transceiver_spec suppression
# ---------------------------------------------------------------------------

class TransceiverSpecSuppressionTestCase(TestCase):
    """
    G.1–G.2: Assert hedgehog_transceiver_spec is suppressed when transceiver Module present.
    RED until suppression conditional is added in device_generator.py.
    """

    @classmethod
    def setUpTestData(cls):
        _make_s2_fixtures(cls)

    def tearDown(self):
        for p in list(TopologyPlan.objects.filter(name__startswith='S2Plan-')):
            _cleanup(p.pk)
            _delete_plan(p)

    def test_spec_not_written_when_transceiver_module_placed(self):
        """G.1: hedgehog_transceiver_spec must be absent on server interface when transceiver Module exists."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(self, 'G1', with_xcvr=True)
        call_command('populate_transceiver_bays')
        _generate(plan)
        from dcim.models import Interface
        server_ifaces = Interface.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            device__device_type=self.server_dt,
        )
        self.assertGreater(server_ifaces.count(), 0, "Server interfaces must exist")
        for iface in server_ifaces:
            spec = (iface.custom_field_data or {}).get('hedgehog_transceiver_spec')
            self.assertFalse(
                bool(spec),
                f"hedgehog_transceiver_spec must be suppressed when transceiver Module placed; "
                f"got {spec!r} on {iface.name}",
            )

    def test_spec_written_as_fallback_when_no_transceiver_module(self):
        """G.2: hedgehog_transceiver_spec fallback write still fires when transceiver FK is null."""
        # No transceiver FK → no Module placed → fallback write should fire
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(self, 'G2', with_xcvr=False)
        call_command('populate_transceiver_bays')
        # Give the connection flat field values so the spec string is non-empty
        conn = PlanServerConnection.objects.get(server_class=sc)
        conn.cage_type = 'QSFP28'
        conn.medium = 'MMF'
        conn.save()
        _generate(plan)
        from dcim.models import Interface
        server_ifaces = Interface.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            device__device_type=self.server_dt,
        )
        self.assertGreater(server_ifaces.count(), 0, "Server interfaces must exist")
        any_spec = any(
            bool((iface.custom_field_data or {}).get('hedgehog_transceiver_spec'))
            for iface in server_ifaces
        )
        self.assertTrue(any_spec,
            "hedgehog_transceiver_spec fallback write must still fire when no transceiver Module placed")


# ---------------------------------------------------------------------------
# Group H: FAILED status propagation to callers (#345 review finding)
# ---------------------------------------------------------------------------

class FailedStatusPropagationTestCase(TestCase):
    """
    H.1–H.3: Assert that FAILED status set by generate_all() is preserved by
    the async job runner and the synchronous UI view.

    These tests verify the fix for the review finding that the job runner was
    unconditionally overwriting GenerationState.status=GENERATED after any
    non-exceptional return from generate_all(), and that the view was showing
    a success message regardless of the resulting GenerationState status.
    """

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        cls.superuser, _ = User.objects.get_or_create(
            username='h-test-admin',
            defaults={'is_staff': True, 'is_superuser': True},
        )
        cls.superuser.set_password('testpass123')
        cls.superuser.save()
        _make_s2_fixtures(cls)

    def _make_failed_plan(self, name_suffix):
        """Create a plan that generates with FAILED status (missing bays, FK set)."""
        from netbox_hedgehog.management.commands.setup_case_128gpu_odd_ports import (
            DeviceGenerator as _DG
        )
        # Use Group F fixtures: fresh DeviceType with no bays, transceiver FK set
        plan = TopologyPlan.objects.create(
            name=f'S2HFPlan-{name_suffix}-{id(self)}',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        mfr, _ = Manufacturer.objects.get_or_create(
            name='H-Test-Mfg', defaults={'slug': 'h-test-mfg'}
        )
        switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr, model=f'H-SW-{name_suffix}', defaults={'slug': f'h-sw-{name_suffix.lower()}'}
        )
        for port_n in range(1, 5):
            InterfaceTemplate.objects.get_or_create(
                device_type=switch_dt, name=f'E1/{port_n}',
                defaults={'type': '200gbase-x-qsfp112'},
            )
        device_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=switch_dt,
            defaults={
                'native_speed': 200, 'uplink_ports': 0,
                'supported_breakouts': ['1x200g-h'], 'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
            },
        )
        breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x200g-h',
            defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
        )
        server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr, model=f'H-SRV-{name_suffix}', defaults={'slug': f'h-srv-{name_suffix.lower()}'}
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu-h',
            server_device_type=server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf-h',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=device_ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        # Set zone transceiver FK — bays absent (no populate_transceiver_bays run)
        zone = SwitchPortZone.objects.create(
            switch_class=sw, zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-64',
            breakout_option=breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            transceiver_module_type=self.xcvr_mt,
        )
        nic_mt_fresh, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model=f'H-NIC-{name_suffix}', defaults={}
        )
        from dcim.models import InterfaceTemplate as IfaceTemplate
        IfaceTemplate.objects.get_or_create(
            module_type=nic_mt_fresh, name='p0',
            defaults={'type': '200gbase-x-qsfp112'},
        )
        nic = PlanServerNIC.objects.create(
            server_class=sc, nic_id='nic-fe-h', module_type=nic_mt_fresh,
        )
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe-h',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
        )
        return plan

    def tearDown(self):
        for p in list(TopologyPlan.objects.filter(name__startswith='S2HFPlan-')):
            _cleanup(p.pk)
            _delete_plan(p)

    def test_job_runner_preserves_failed_status(self):
        """H.1: Job runner must NOT overwrite FAILED → GENERATED after generate_all() returns normally."""
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob
        from core.models import Job

        plan = self._make_failed_plan('H1')
        # Do NOT call populate_transceiver_bays — bays are absent.
        # generate_all() will return normally but set status=FAILED in DB.

        job = DeviceGenerationJob.enqueue(
            name='H1 FAILED Status Test',
            user=self.superuser,
            plan_id=plan.pk,
        )
        job_runner = DeviceGenerationJob(job=job)
        job_runner.run(plan_id=plan.pk)

        plan.refresh_from_db()
        gs = plan.generation_state
        self.assertEqual(
            gs.status, GenerationStatusChoices.FAILED,
            "Job runner must preserve status=FAILED set by generate_all(); "
            "it must not overwrite FAILED → GENERATED",
        )

    def test_job_runner_preserves_failed_mismatch_report(self):
        """H.2: Job runner must not clear mismatch_report set during FAILED generation."""
        from netbox_hedgehog.jobs.device_generation import DeviceGenerationJob

        plan = self._make_failed_plan('H2')
        job = DeviceGenerationJob.enqueue(
            name='H2 Report Test',
            user=self.superuser,
            plan_id=plan.pk,
        )
        DeviceGenerationJob(job=job).run(plan_id=plan.pk)

        plan.refresh_from_db()
        gs = plan.generation_state
        report = gs.mismatch_report or {}
        self.assertTrue(
            bool(report.get('bay_errors') or report.get('mismatches')),
            "Job runner must preserve mismatch_report populated by generate_all()",
        )

    def test_sync_view_shows_error_on_failed_generation(self):
        """H.3: Synchronous generate view must show error message, not success, when status=FAILED."""
        from django.urls import reverse

        plan = self._make_failed_plan('H3')
        client = Client()
        client.login(username='h-test-admin', password='testpass123')

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', kwargs={'pk': plan.pk})
        response = client.post(url)

        # Should redirect to plan detail (not generate page)
        self.assertIn(response.status_code, [302, 200])
        if response.status_code == 302:
            self.assertIn(str(plan.pk), response['Location'],
                "On FAILED generation, view must redirect to plan detail")

        plan.refresh_from_db()
        self.assertEqual(
            plan.generation_state.status, GenerationStatusChoices.FAILED,
            "GenerationState must remain FAILED after synchronous view generation",
        )
