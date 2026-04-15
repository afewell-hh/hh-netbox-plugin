"""
Phase 3 RED tests for Stage 2 transceiver modeling (DIET-334 #343).

Groups:
  A - migration 0045 (mismatch_report field on GenerationState)
  B - populate_transceiver_bays management command
  C - switch-side transceiver Module placement in generator
  D - nested NIC-port-bay server-side transceiver placement
  E - post-generation pairwise compatibility sweep (aggregate-all-mismatches-then-fail)
  F - hard-fail when transceiver FK is set but required ModuleBay is absent (#345)
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
        """H.3: Sync view must redirect to plan detail and show FAILED when sweep finds mismatch.

        Uses a mismatched connection transceiver (SFP28) vs zone (QSFP112) so the
        compatibility sweep fails.  populate_transceiver_bays is called first so
        the preflight check passes and generate_all() actually runs.
        """
        from django.urls import reverse

        plan = self._make_failed_plan('H3')

        # Add a mismatching server-side transceiver (SFP28 cage vs zone's QSFP112).
        # This ensures the preflight check passes (bays will exist) but the sweep fails.
        mfr, _ = Manufacturer.objects.get_or_create(
            name='H-Test-Mfg', defaults={'slug': 'h-test-mfg'}
        )
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        mismatch_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='H-XCVR-MISMATCH-H3',
            defaults={
                'profile': profile,
                'attribute_data': {'cage_type': 'SFP28', 'medium': 'MMF'},
            },
        )
        conn = PlanServerConnection.objects.filter(server_class__plan=plan).first()
        conn.transceiver_module_type = mismatch_mt
        conn.save()

        # Populate bays so preflight is ready; then the sweep can run and fail.
        call_command('populate_transceiver_bays')

        client = Client()
        client.login(username='h-test-admin', password='testpass123')

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', kwargs={'pk': plan.pk})
        response = client.post(url)

        # Should redirect to plan detail (not back to generate page)
        self.assertIn(response.status_code, [302, 200])
        if response.status_code == 302:
            self.assertIn(str(plan.pk), response['Location'],
                "On FAILED generation, view must redirect to plan detail, not generate page")

        plan.refresh_from_db()
        self.assertEqual(
            plan.generation_state.status, GenerationStatusChoices.FAILED,
            "GenerationState must be FAILED after sync view generation with mismatch",
        )


# ---------------------------------------------------------------------------
# Group I: Multi-port connection transceiver placement and natural-sort ordering
# ---------------------------------------------------------------------------

class MultiPortTransceiverPlacementTestCase(TestCase):
    """
    I.1–I.3: Assert that multi-port connections place one transceiver Module per
    wired port, and that populate_transceiver_bays uses natural sort order so
    cage-N aligns with the natural-sort port index for double-digit port names.
    """

    @classmethod
    def setUpTestData(cls):
        cls.mfr, _ = Manufacturer.objects.get_or_create(
            name='I-Test-Mfg', defaults={'slug': 'i-test-mfg'}
        )
        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='I-SRV', defaults={'slug': 'i-srv'}
        )
        cls.switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.mfr, model='I-SW', defaults={'slug': 'i-sw'}
        )
        for port_n in range(1, 9):
            InterfaceTemplate.objects.get_or_create(
                device_type=cls.switch_dt, name=f'E1/{port_n}',
                defaults={'type': '200gbase-x-qsfp112'},
            )
        cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_dt,
            defaults={
                'native_speed': 200, 'uplink_ports': 0,
                'supported_breakouts': ['1x200g-i'], 'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
            },
        )
        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x200g-i',
            defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
        )
        cls.site, _ = Site.objects.get_or_create(
            name='I-TestSite', defaults={'slug': 'i-testsite'}
        )
        cls.xcvr_mt = get_test_transceiver_module_type()

        # NIC ModuleType with 4 ports for multi-port test (I.1)
        cls.nic_mt_multi, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='I-NIC-4PORT', defaults={}
        )
        for pname in ('p0', 'p1', 'p2', 'p3'):
            from dcim.models import InterfaceTemplate as IfaceTemplate
            IfaceTemplate.objects.get_or_create(
                module_type=cls.nic_mt_multi, name=pname,
                defaults={'type': '200gbase-x-qsfp112'},
            )

        # NIC ModuleType with double-digit ports for natural-sort test (I.2, I.3)
        # Names p0..p9, p10 — lexicographic order puts p10 before p2
        cls.nic_mt_bigport, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='I-NIC-11PORT', defaults={}
        )
        from dcim.models import InterfaceTemplate as IfaceTemplate
        for pname in ('p0', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8', 'p9', 'p10'):
            IfaceTemplate.objects.get_or_create(
                module_type=cls.nic_mt_bigport, name=pname,
                defaults={'type': '200gbase-x-qsfp112'},
            )

    def _make_multiport_plan(self, name_suffix, nic_mt, ports_per_connection,
                              port_index=0, with_xcvr=True):
        plan = TopologyPlan.objects.create(
            name=f'S2IPlan-{name_suffix}-{id(self)}',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu-i',
            server_device_type=self.server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf-i',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        zone = SwitchPortZone.objects.create(
            switch_class=sw, zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-64',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )
        nic = PlanServerNIC.objects.create(
            server_class=sc, nic_id='nic-fe-i', module_type=nic_mt,
        )
        conn_kwargs = {}
        if with_xcvr:
            conn_kwargs['transceiver_module_type'] = self.xcvr_mt
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe-i',
            nic=nic, port_index=port_index,
            ports_per_connection=ports_per_connection,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
            **conn_kwargs,
        )
        return plan, sc, sw, zone, nic

    def tearDown(self):
        for p in list(TopologyPlan.objects.filter(name__startswith='S2IPlan-')):
            _cleanup(p.pk)
            _delete_plan(p)

    def test_multi_port_connection_places_transceiver_per_port(self):
        """I.1: ports_per_connection=2 with transceiver FK → two nested cage Modules, not one."""
        plan, sc, sw, zone, nic = self._make_multiport_plan(
            'I1', self.nic_mt_multi, ports_per_connection=2, port_index=0, with_xcvr=True
        )
        call_command('populate_transceiver_bays')
        _generate(plan)

        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(gs.status, GenerationStatusChoices.GENERATED,
            "Multi-port connection with bays present must succeed as GENERATED")

        # Both cage-0 and cage-1 should contain a transceiver Module
        nic_modules = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            module_type=self.nic_mt_multi,
        )
        self.assertGreater(nic_modules.count(), 0, "NIC Module must exist")
        nic_module = nic_modules.first()

        for cage in ('cage-0', 'cage-1'):
            xcvr = Module.objects.filter(
                module_bay__module=nic_module,
                module_bay__name=cage,
                module_type=self.xcvr_mt,
            )
            self.assertGreater(xcvr.count(), 0,
                f"Multi-port connection (ports_per_connection=2) must place transceiver in {cage}")

    def test_natural_sort_cage_alignment_for_double_digit_ports(self):
        """I.2: populate_transceiver_bays uses natural sort; cage-2 maps to p2, not p10."""
        # Create plan (and PlanServerNIC) FIRST so populate_transceiver_bays discovers
        # nic_mt_bigport via PlanServerNIC references.
        plan, sc, sw, zone, nic = self._make_multiport_plan(
            'I2', self.nic_mt_bigport, ports_per_connection=1,
            port_index=2, with_xcvr=True
        )
        call_command('populate_transceiver_bays')

        bays = ModuleBayTemplate.objects.filter(module_type=self.nic_mt_bigport)
        self.assertEqual(bays.count(), 11,
            "11-port NIC must produce 11 cage ModuleBayTemplates")

        # With natural sort: cage-0=p0, cage-1=p1, cage-2=p2, ..., cage-10=p10
        # With lexicographic sort: cage-2 would be p10 (wrong).
        # Verify by generating with port_index=2: cage-2 must exist for generation to succeed.
        _generate(plan)

        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(gs.status, GenerationStatusChoices.GENERATED,
            "Generation with port_index=2 on 11-port NIC must succeed "
            "(cage-2 must exist = natural sort used in populate_transceiver_bays)")

    def test_natural_sort_cage_count_matches_port_count(self):
        """I.3: Number of cage bays equals number of interface templates on NIC ModuleType."""
        # Create PlanServerNIC first so the command discovers nic_mt_bigport.
        plan, sc, sw, zone, nic = self._make_multiport_plan(
            'I3', self.nic_mt_bigport, ports_per_connection=1,
            port_index=0, with_xcvr=False
        )
        call_command('populate_transceiver_bays')
        iface_count = InterfaceTemplate.objects.filter(module_type=self.nic_mt_bigport).count()
        bay_count = ModuleBayTemplate.objects.filter(module_type=self.nic_mt_bigport).count()
        self.assertEqual(iface_count, bay_count,
            "cage bay count must equal interface template count on NIC ModuleType")


# ---------------------------------------------------------------------------
# Shared helper for DIET-350 Phase 3 connector/standard tests
# ---------------------------------------------------------------------------

def _make_xcvr_mt_350(connector=None, standard=None, cage_type='QSFP112', medium='MMF',
                      reach_class=None, model_suffix='default'):
    """Create a Network Transceiver ModuleType with the given attribute_data values.

    medium=None excludes the 'medium' key from attribute_data entirely (for null-skip tests).
    reach_class=None (default) excludes the 'reach_class' key.
    All other None params are also excluded.
    Existing callers that omit reach_class and pass medium='MMF' (or rely on the default)
    are unaffected — backward-compatible.
    """
    mfr, _ = Manufacturer.objects.get_or_create(
        name='XCVR-Test-Vendor', defaults={'slug': 'xcvr-test-vendor'}
    )
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    attrs = {'cage_type': cage_type}
    if medium is not None:
        attrs['medium'] = medium
    if connector is not None:
        attrs['connector'] = connector
    if standard is not None:
        attrs['standard'] = standard
    if reach_class is not None:
        attrs['reach_class'] = reach_class
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr,
        model=f'XCVR-350-{model_suffix}',
        defaults={'profile': profile, 'attribute_data': attrs},
    )
    return mt


def _make_350_plan_fixtures(cls):
    """Minimal plan fixtures for DIET-350 plan-save and sweep tests."""
    cls.mfr350, _ = Manufacturer.objects.get_or_create(
        name='T350-Mfg', defaults={'slug': 't350-mfg'}
    )
    cls.server_dt350, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr350, model='T350-SRV', defaults={'slug': 't350-srv'}
    )
    cls.switch_dt350, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr350, model='T350-SW', defaults={'slug': 't350-sw'}
    )
    for port_n in range(1, 9):
        InterfaceTemplate.objects.get_or_create(
            device_type=cls.switch_dt350, name=f'E1/{port_n}',
            defaults={'type': '200gbase-x-qsfp112'},
        )
    cls.device_ext350, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=cls.switch_dt350,
        defaults={
            'native_speed': 200, 'uplink_ports': 0,
            'supported_breakouts': ['1x200g-350'], 'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    cls.breakout350, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x200g-350',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    cls.site350, _ = Site.objects.get_or_create(
        name='T350-Site', defaults={'slug': 't350-site'}
    )
    cls.nic_mt350 = get_test_nic_module_type()


def _make_350_base_connection(server_class, nic, zone, connection_id='conn-350', **extra):
    """Create (and save) a PlanServerConnection for DIET-350 tests."""
    return PlanServerConnection.objects.create(
        server_class=server_class,
        connection_id=connection_id,
        nic=nic,
        port_index=0,
        ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        target_zone=zone,
        speed=200,
        port_type='data',
        **extra,
    )


# ---------------------------------------------------------------------------
# Group C: Plan-save connector validation (DIET-350 Phase 3)
# C.1, C.4 are RED until V2c/V6 added to _validate_transceiver_module_type().
# C.2, C.3, C.5, C.6, C.7 verify null-skip and positive cases.
# ---------------------------------------------------------------------------

class ConnectorPlanSaveValidationTestCase(TestCase):
    """
    C.1–C.7: Plan-save validation for connector dimension (DIET-350 #372).

    C.1: V2c — flat connector conflicts with own FK attribute_data → ValidationError
    C.2: V2c — flat connector matches FK attribute_data → no error
    C.3: V2c — flat connector set, FK has no connector in attribute_data → no error (null-skip)
    C.4: V6 — cross-end connector mismatch (both FKs set) → ValidationError
    C.5: V6 — cross-end connector match → no error
    C.6: V6 — zone FK has no connector in attribute_data → no error (null-skip)
    C.7: standard mismatch at plan-save → NO ValidationError (sweep-only guard)

    C.1 and C.4 are RED until GREEN adds V2c and V6.
    """

    @classmethod
    def setUpTestData(cls):
        _make_350_plan_fixtures(cls)
        cls.plan350 = TopologyPlan.objects.create(
            name='C-PlanSave-350', status=TopologyPlanStatusChoices.DRAFT,
        )
        cls.sc350 = PlanServerClass.objects.create(
            plan=cls.plan350, server_class_id='c-gpu',
            server_device_type=cls.server_dt350, quantity=1,
        )
        cls.sw350 = PlanSwitchClass.objects.create(
            plan=cls.plan350, switch_class_id='c-fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext350,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        # Zone without transceiver FK — used for V2c tests (C.1–C.3)
        cls.zone_no_xcvr = SwitchPortZone.objects.create(
            switch_class=cls.sw350, zone_name='c-server-ports-noxcvr',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-32',
            breakout_option=cls.breakout350,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )
        cls.nic350 = PlanServerNIC.objects.create(
            server_class=cls.sc350, nic_id='c-nic-fe', module_type=cls.nic_mt350,
        )
        # Transceiver MTs for test use
        cls.mt_mpo12 = _make_xcvr_mt_350(connector='MPO-12', standard='200GBASE-SR4',
                                          model_suffix='mpo12')
        # Same cage_type/medium as mt_mpo12 but connector='LC' — used for pure connector
        # cross-end mismatch test (C.4) so V4/V5 don't fire before V6.
        cls.mt_lc_mmf = _make_xcvr_mt_350(connector='LC', medium='MMF',
                                           standard='200GBASE-SR4', model_suffix='lc-mmf')
        cls.mt_direct = _make_xcvr_mt_350(connector='Direct', medium='DAC',
                                           standard='200GBASE-CR4', model_suffix='direct')
        cls.mt_no_connector = _make_xcvr_mt_350(connector=None, standard='200GBASE-SR4',
                                                 model_suffix='no-conn')
        cls.mt_standard_a = _make_xcvr_mt_350(connector='MPO-12', standard='200GBASE-SR4',
                                               model_suffix='std-a')
        cls.mt_standard_b = _make_xcvr_mt_350(connector='MPO-12', standard='400GBASE-SR4',
                                               model_suffix='std-b')

    def test_c1_v2c_flat_connector_conflicts_with_fk_raises(self):
        """C.1: V2c — flat connector='LC' conflicts with FK attribute_data connector='MPO-12' → ValidationError.

        RED until V2c is added to _validate_transceiver_module_type().
        """
        psc = _make_350_base_connection(
            self.sc350, self.nic350, self.zone_no_xcvr,
            connection_id='c1-conn',
            transceiver_module_type=self.mt_mpo12,
        )
        psc.connector = 'LC'  # flat field conflicts with FK attribute_data connector='MPO-12'
        with self.assertRaises(Exception) as ctx:
            psc.full_clean()
        from django.core.exceptions import ValidationError as DjangoVE
        self.assertIsInstance(ctx.exception, DjangoVE,
            "V2c: flat connector conflicting with FK attribute_data must raise ValidationError")
        self.assertIn('connector', ctx.exception.message_dict,
            "ValidationError must be on 'connector' field")
        self.assertIn(
            "conflicts with transceiver_module_type",
            str(ctx.exception),
            "Error message must mention 'conflicts with transceiver_module_type'",
        )

    def test_c2_v2c_flat_connector_matches_fk_ok(self):
        """C.2: V2c — flat connector='MPO-12' matches FK attribute_data connector='MPO-12' → no error."""
        psc = _make_350_base_connection(
            self.sc350, self.nic350, self.zone_no_xcvr,
            connection_id='c2-conn',
            transceiver_module_type=self.mt_mpo12,
        )
        psc.connector = 'MPO-12'
        psc.full_clean()  # must not raise

    def test_c3_v2c_flat_connector_set_fk_has_no_connector_no_error(self):
        """C.3: V2c null-skip — flat connector set, FK has no connector in attribute_data → no error."""
        psc = _make_350_base_connection(
            self.sc350, self.nic350, self.zone_no_xcvr,
            connection_id='c3-conn',
            transceiver_module_type=self.mt_no_connector,
        )
        psc.connector = 'LC'  # flat field set, but FK has no connector key
        psc.full_clean()  # null-skip: must not raise

    def test_c4_v6_cross_end_connector_mismatch_raises(self):
        """C.4: V6 — cross-end connector mismatch (MPO-12 server, LC zone) → ValidationError.

        Uses mt_lc_mmf for the zone: same cage_type/medium as mt_mpo12 (QSFP112/MMF) so V4/V5
        do not fire, isolating V6 (connector). RED until V6 added to
        _validate_transceiver_module_type().
        """
        # Zone uses LC connector (same medium=MMF so V5 doesn't fire first)
        zone_with_xcvr = SwitchPortZone.objects.create(
            switch_class=self.sw350, zone_name='c4-zone-lc',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='33-48',
            breakout_option=self.breakout350,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=200,
            transceiver_module_type=self.mt_lc_mmf,
        )
        psc = _make_350_base_connection(
            self.sc350, self.nic350, zone_with_xcvr,
            connection_id='c4-conn',
            transceiver_module_type=self.mt_mpo12,  # MPO-12 server vs LC zone
        )
        from django.core.exceptions import ValidationError as DjangoVE
        with self.assertRaises(DjangoVE) as ctx:
            psc.full_clean()
        exc_str = str(ctx.exception)
        self.assertIn("Server-side connector", exc_str,
            "V6: error message must mention 'Server-side connector'")
        self.assertIn("does not match zone transceiver connector", exc_str,
            "V6: error message must mention 'does not match zone transceiver connector'")
        self.assertIn("MPO-12", exc_str, "V6: server_end value must appear in error message")
        self.assertIn("LC", exc_str, "V6: zone connector value must appear in error message")

    def test_c5_v6_cross_end_connector_match_ok(self):
        """C.5: V6 — cross-end connector match (MPO-12 both ends) → no error."""
        zone_with_xcvr = SwitchPortZone.objects.create(
            switch_class=self.sw350, zone_name='c5-zone-mpo12',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='49-56',
            breakout_option=self.breakout350,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=210,
            transceiver_module_type=self.mt_mpo12,
        )
        psc = _make_350_base_connection(
            self.sc350, self.nic350, zone_with_xcvr,
            connection_id='c5-conn',
            transceiver_module_type=self.mt_mpo12,  # MPO-12 both ends
        )
        psc.full_clean()  # must not raise

    def test_c6_v6_zone_has_no_connector_no_error(self):
        """C.6: V6 null-skip — zone FK has no connector in attribute_data → no error."""
        zone_with_xcvr = SwitchPortZone.objects.create(
            switch_class=self.sw350, zone_name='c6-zone-noconn',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='57-64',
            breakout_option=self.breakout350,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=220,
            transceiver_module_type=self.mt_no_connector,  # no connector in attribute_data
        )
        psc = _make_350_base_connection(
            self.sc350, self.nic350, zone_with_xcvr,
            connection_id='c6-conn',
            transceiver_module_type=self.mt_mpo12,  # server has connector set
        )
        psc.full_clean()  # null-skip on zone side: must not raise

    def test_c7_standard_mismatch_at_save_does_not_raise(self):
        """C.7: standard is sweep-only — mismatching standard at plan-save must NOT raise.

        This test guards that standard is never added to clean() validation.
        """
        zone_with_xcvr = SwitchPortZone.objects.create(
            switch_class=self.sw350, zone_name='c7-zone-std',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-8',
            breakout_option=self.breakout350,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=230,
            transceiver_module_type=self.mt_standard_b,  # standard='400GBASE-SR4'
        )
        psc = _make_350_base_connection(
            self.sc350, self.nic350, zone_with_xcvr,
            connection_id='c7-conn',
            transceiver_module_type=self.mt_standard_a,  # standard='200GBASE-SR4'
        )
        psc.full_clean()  # standard mismatch must NOT raise at save time


# ---------------------------------------------------------------------------
# Group E (extended): Connector and standard sweep tests (DIET-350 Phase 3)
# E.5–E.12: RED until _SWEEP_DIMS extended and sweep tuple replaced.
# ---------------------------------------------------------------------------

class ConnectorStandardSweepTestCase(TestCase):
    """
    E.5–E.12: Post-generation sweep coverage for connector and standard (DIET-350 #372).

    E.5:  connector match → GENERATED, no connector mismatch entry
    E.6:  connector mismatch → FAILED, connector entry in mismatch_report  [RED]
    E.7:  standard match → GENERATED, no standard mismatch entry
    E.8:  standard mismatch → FAILED, standard entry in mismatch_report    [RED]
    E.9:  connector null on server end → sweep skips, no mismatch
    E.10: standard null on zone end → sweep skips, no mismatch
    E.11: _SWEEP_DIMS constant importable and contains connector+standard   [RED]
    E.12: regression — cage_type mismatch still fires (no regression)
    """

    @classmethod
    def setUpTestData(cls):
        _make_s2_fixtures(cls)
        # MPO-12 / MMF / 200GBASE-SR4  (same as default xcvr_mt from get_test_transceiver_module_type)
        cls.mt_mpo12_sr4 = get_test_transceiver_module_type()
        # Direct / DAC / 200GBASE-CR4  (medium mismatch vs MPO-12/MMF; kept for backward compat)
        mfr, _ = Manufacturer.objects.get_or_create(
            name='XCVR-Test-Vendor', defaults={'slug': 'xcvr-test-vendor'}
        )
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        cls.mt_direct_dac, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='XCVR-350-DIRECT-DAC',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112', 'medium': 'DAC',
                    'connector': 'Direct', 'standard': '200GBASE-CR4',
                },
            },
        )
        # MPO-12 / MMF / 400GBASE-SR4  (standard mismatch vs 200GBASE-SR4, connector match)
        cls.mt_mpo12_400g, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='XCVR-350-MPO12-400G',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112', 'medium': 'MMF',
                    'connector': 'MPO-12', 'standard': '400GBASE-SR4',
                },
            },
        )
        # No connector in attribute_data (null-skip test E.9)
        cls.mt_no_connector, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='XCVR-350-NO-CONN',
            defaults={
                'profile': profile,
                'attribute_data': {'cage_type': 'QSFP112', 'medium': 'MMF'},
            },
        )
        # No standard in attribute_data (null-skip test E.10)
        cls.mt_no_standard, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='XCVR-350-NO-STD',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112', 'medium': 'MMF', 'connector': 'MPO-12',
                },
            },
        )
        # OSFP cage_type mismatch (regression E.12)
        cls.mt_osfp, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='XCVR-350-OSFP-REG',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'OSFP', 'medium': 'MMF',
                    'connector': 'MPO-12', 'standard': '400GBASE-SR4',
                },
            },
        )
        # QSFP112 / MMF / LC — connector mismatch vs MPO-12, same cage+medium (E.6)
        cls.mt_qsfp112_mmf_lc, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr, model='XCVR-350-QSFP112-LC',
            defaults={
                'profile': profile,
                'attribute_data': {
                    'cage_type': 'QSFP112', 'medium': 'MMF',
                    'connector': 'LC', 'standard': '200GBASE-SR4',
                },
            },
        )

    def tearDown(self):
        for p in list(TopologyPlan.objects.filter(name__startswith='S2Plan-')):
            _cleanup(p.pk)
            _delete_plan(p)

    def _make_sweep_plan(self, suffix, server_mt, zone_mt):
        """Build a plan where connection has server_mt and zone has zone_mt."""
        plan, sc, sw, zone, nic = _make_plan_with_xcvr(
            self, suffix, with_xcvr=True, zone_xcvr=zone_mt
        )
        # Override connection's transceiver_module_type to server_mt
        conn = PlanServerConnection.objects.filter(server_class__plan=plan).first()
        conn.transceiver_module_type = server_mt
        conn.save()
        return plan

    def test_e5_connector_match_generation_succeeds(self):
        """E.5: connector match (MPO-12 both ends) → GENERATED, no connector mismatch entry."""
        plan = self._make_sweep_plan('E5', self.mt_mpo12_sr4, self.mt_mpo12_sr4)
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(gs.status, GenerationStatusChoices.GENERATED,
            "E.5: connector match must produce GENERATED status")
        if gs.mismatch_report:
            connector_entries = [
                e for e in gs.mismatch_report.get('mismatches', [])
                if e.get('mismatch_type') == 'connector'
            ]
            self.assertEqual(len(connector_entries), 0,
                "E.5: no connector mismatch entries expected when connectors match")

    def test_e6_connector_mismatch_sets_failed_status(self):
        """E.6: connector mismatch (MPO-12 server vs LC zone, same cage+medium) → FAILED + connector entry.

        Uses mt_qsfp112_mmf_lc (QSFP112/MMF/LC) as zone so only connector differs.
        The rule engine fires R_CONNECTOR_MISMATCH → mismatch_type='connector'.
        """
        plan = self._make_sweep_plan('E6', self.mt_mpo12_sr4, self.mt_qsfp112_mmf_lc)
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(gs.status, GenerationStatusChoices.FAILED,
            "E.6: connector mismatch must set status=FAILED")
        self.assertIsNotNone(gs.mismatch_report,
            "E.6: mismatch_report must be populated on connector mismatch")
        connector_entries = [
            e for e in gs.mismatch_report.get('mismatches', [])
            if e.get('mismatch_type') == 'connector'
        ]
        self.assertGreater(len(connector_entries), 0,
            "E.6: mismatch_report must contain a 'connector' mismatch entry")
        entry = connector_entries[0]
        self.assertEqual(entry.get('server_end'), 'MPO-12',
            "E.6: server_end must be 'MPO-12'")
        self.assertEqual(entry.get('switch_end'), 'LC',
            "E.6: switch_end must be 'LC'")

    def test_e7_standard_match_generation_succeeds(self):
        """E.7: standard match (200GBASE-SR4 both ends) → GENERATED, no standard entry."""
        plan = self._make_sweep_plan('E7', self.mt_mpo12_sr4, self.mt_mpo12_sr4)
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(gs.status, GenerationStatusChoices.GENERATED,
            "E.7: standard match must produce GENERATED status")

    def test_e8_standard_mismatch_does_not_fail(self):
        """E.8 (updated): standard mismatch alone (same cage/medium/connector) → GENERATED.

        The rule engine (DIET-450) intentionally does not check 'standard' as a
        blocking dimension; differing standards with matching cage, medium, and
        connector → R_MATCH → GENERATED status.  The _SWEEP_DIMS tuple retains
        'standard' for backward compatibility but the sweep loop no longer uses it.
        """
        plan = self._make_sweep_plan('E8', self.mt_mpo12_sr4, self.mt_mpo12_400g)
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(gs.status, GenerationStatusChoices.GENERATED,
            "E.8: standard-only mismatch must now produce GENERATED (rule engine ignores standard)")
        if gs.mismatch_report:
            standard_entries = [
                e for e in gs.mismatch_report.get('mismatches', [])
                if e.get('mismatch_type') == 'standard'
            ]
            self.assertEqual(len(standard_entries), 0,
                "E.8: no 'standard' mismatch entries expected — rule engine does not check standard")

    def test_e9_connector_null_on_server_end_sweep_skips(self):
        """E.9: server MT has no connector in attribute_data → sweep skips, no connector mismatch."""
        plan = self._make_sweep_plan('E9', self.mt_no_connector, self.mt_mpo12_sr4)
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        if gs.mismatch_report:
            connector_entries = [
                e for e in gs.mismatch_report.get('mismatches', [])
                if e.get('mismatch_type') == 'connector'
            ]
            self.assertEqual(len(connector_entries), 0,
                "E.9: null-skip — no connector mismatch when server end has no connector")

    def test_e10_standard_null_on_zone_end_sweep_skips(self):
        """E.10: zone MT has no standard in attribute_data → sweep skips, no standard mismatch."""
        plan = self._make_sweep_plan('E10', self.mt_mpo12_sr4, self.mt_no_standard)
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        if gs.mismatch_report:
            standard_entries = [
                e for e in gs.mismatch_report.get('mismatches', [])
                if e.get('mismatch_type') == 'standard'
            ]
            self.assertEqual(len(standard_entries), 0,
                "E.10: null-skip — no standard mismatch when zone end has no standard")

    def test_e11_sweep_dims_constant_importable_and_contains_new_dimensions(self):
        """E.11: _SWEEP_DIMS is a module-level constant in device_generator containing connector+standard.

        RED until _SWEEP_DIMS is added to device_generator.py.
        """
        try:
            from netbox_hedgehog.services.device_generator import _SWEEP_DIMS
        except ImportError:
            self.fail(
                "_SWEEP_DIMS must be importable from netbox_hedgehog.services.device_generator. "
                "Add it as a module-level constant."
            )
        self.assertIn('cage_type', _SWEEP_DIMS,
            "_SWEEP_DIMS must retain 'cage_type' (regression guard)")
        self.assertIn('medium', _SWEEP_DIMS,
            "_SWEEP_DIMS must retain 'medium' (regression guard)")
        self.assertIn('connector', _SWEEP_DIMS,
            "_SWEEP_DIMS must include 'connector' (new in DIET-350)")
        self.assertIn('standard', _SWEEP_DIMS,
            "_SWEEP_DIMS must include 'standard' (new in DIET-350)")

    def test_e12_regression_cage_type_mismatch_still_fires(self):
        """E.12: existing cage_type sweep check still fires after _SWEEP_DIMS change."""
        # mt_osfp has cage_type='OSFP'; default xcvr_mt has cage_type='QSFP112' → mismatch
        plan = self._make_sweep_plan('E12', self.mt_mpo12_sr4, self.mt_osfp)
        call_command('populate_transceiver_bays')
        _generate(plan)
        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(gs)
        self.assertEqual(gs.status, GenerationStatusChoices.FAILED,
            "E.12: cage_type regression — mismatch must still produce FAILED")
        cage_entries = [
            e for e in (gs.mismatch_report or {}).get('mismatches', [])
            if e.get('mismatch_type') == 'cage_type'
        ]
        self.assertGreater(len(cage_entries), 0,
            "E.12: cage_type mismatch entry must still appear after _SWEEP_DIMS refactor")


# ---------------------------------------------------------------------------
# Group R: reach_class plan-save validation (DIET-409 Phase 3)
# R.1, R.2, R.3, R.4, R.13 are RED until V7 is added to
# _validate_transceiver_module_type().
# R.5–R.12, R.14–R.16 verify compatible, null-skip, and regression cases.
# ---------------------------------------------------------------------------

class ReachClassPlanSaveValidationTestCase(TestCase):
    """
    R.1–R.16: Plan-save validation for reach_class / medium intra-connection invariant (DIET-409 #413).

    V7 enforces: reach_class='DAC' requires medium ∈ {DAC, ACC};
                 reach_class ∈ {SR, LR, DR} requires medium ∈ {MMF, SMF}.
    Null-skip when either value is absent.

    RED tests (require V7 implementation):
      R.1:  copper reach_class='DAC' + optical medium='MMF' → ValidationError
      R.2:  copper reach_class='DAC' + optical medium='SMF' → ValidationError
      R.3:  optical reach_class='SR' + copper medium='DAC' → ValidationError
      R.4:  optical reach_class='LR' + copper medium='ACC' → ValidationError
      R.13: copper reach_class='DAC' + no attr_data medium, flat medium='MMF' → ValidationError
             (fallback medium path)

    Green tests (pass without V7):
      R.5–R.9:   compatible pairs (no error expected)
      R.10–R.12: null-skip cases (no error expected)
      R.14:      compatible fallback medium path (no error expected)
      R.15–R.16: regression guards for seeded-like optical and copper NICs
    """

    @classmethod
    def setUpTestData(cls):
        _make_350_plan_fixtures(cls)
        cls.plan_r = TopologyPlan.objects.create(
            name='R-PlanSave-409', status=TopologyPlanStatusChoices.DRAFT,
        )
        cls.sc_r = PlanServerClass.objects.create(
            plan=cls.plan_r, server_class_id='r-gpu',
            server_device_type=cls.server_dt350, quantity=1,
        )
        cls.sw_r = PlanSwitchClass.objects.create(
            plan=cls.plan_r, switch_class_id='r-fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext350,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        # Zone without transceiver FK — prevents cross-end V4–V6 from firing.
        cls.zone_no_xcvr_r = SwitchPortZone.objects.create(
            switch_class=cls.sw_r, zone_name='r-server-ports-noxcvr',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-32',
            breakout_option=cls.breakout350,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )
        cls.nic_r = PlanServerNIC.objects.create(
            server_class=cls.sc_r, nic_id='r-nic-fe', module_type=cls.nic_mt350,
        )

        # --- Incompatible pairs (R.1–R.4): copper reach on optical medium, or vice versa ---
        cls.mt_dac_rc_mmf_med = _make_xcvr_mt_350(
            medium='MMF', reach_class='DAC', model_suffix='dac-rc-mmf-med')
        cls.mt_dac_rc_smf_med = _make_xcvr_mt_350(
            medium='SMF', reach_class='DAC', model_suffix='dac-rc-smf-med')
        cls.mt_sr_rc_dac_med = _make_xcvr_mt_350(
            medium='DAC', reach_class='SR', model_suffix='sr-rc-dac-med')
        cls.mt_lr_rc_acc_med = _make_xcvr_mt_350(
            medium='ACC', reach_class='LR', model_suffix='lr-rc-acc-med')

        # --- Compatible pairs (R.5–R.9) ---
        cls.mt_dac_rc_dac_med = _make_xcvr_mt_350(
            medium='DAC', reach_class='DAC', model_suffix='dac-rc-dac-med')
        cls.mt_dac_rc_acc_med = _make_xcvr_mt_350(
            medium='ACC', reach_class='DAC', model_suffix='dac-rc-acc-med')
        cls.mt_sr_rc_mmf_med = _make_xcvr_mt_350(
            medium='MMF', reach_class='SR', model_suffix='sr-rc-mmf-med')
        cls.mt_lr_rc_smf_med = _make_xcvr_mt_350(
            medium='SMF', reach_class='LR', model_suffix='lr-rc-smf-med')
        cls.mt_dr_rc_mmf_med = _make_xcvr_mt_350(
            medium='MMF', reach_class='DR', model_suffix='dr-rc-mmf-med')

        # --- Null-skip cases (R.10–R.12) ---
        # R.10: medium in attrs, no reach_class key
        cls.mt_no_rc = _make_xcvr_mt_350(
            medium='MMF', reach_class=None, model_suffix='no-rc')
        # R.11, R.14: reach_class='SR', no medium key — used with different flat medium values
        cls.mt_rc_no_med = _make_xcvr_mt_350(
            medium=None, reach_class='SR', model_suffix='rc-no-med')

        # --- Fallback-medium cases (R.13, R.14) ---
        # R.13: reach_class='DAC', no medium in attrs → fallback to flat self.medium
        cls.mt_dac_rc_no_med = _make_xcvr_mt_350(
            medium=None, reach_class='DAC', model_suffix='dac-rc-no-med')

        # --- Regression guards (R.15–R.16) ---
        # R.15: optical NIC like BF3220 (medium=MMF, reach_class=SR)
        cls.mt_reg_optical = _make_xcvr_mt_350(
            medium='MMF', reach_class='SR', connector='MPO-12',
            standard='200GBASE-SR4', model_suffix='reg-optical')
        # R.16: copper NIC like CX7 (medium=DAC, reach_class=DAC)
        cls.mt_reg_copper = _make_xcvr_mt_350(
            medium='DAC', reach_class='DAC', connector='Direct',
            standard='200GBASE-CR4', model_suffix='reg-copper')

    # -------------------------------------------------------------------------
    # R.1–R.4: Incompatible pairs — must raise ValidationError on
    #          'transceiver_module_type'. RED until V7 is added.
    # -------------------------------------------------------------------------

    def test_r1_v7_dac_reach_class_on_mmf_medium_raises(self):
        """R.1: V7 — reach_class='DAC' with medium='MMF' (optical) → ValidationError.

        RED until V7 is added to _validate_transceiver_module_type().
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r1-conn',
            transceiver_module_type=self.mt_dac_rc_mmf_med,
        )
        from django.core.exceptions import ValidationError as DjangoVE
        with self.assertRaises(DjangoVE) as ctx:
            psc.full_clean()
        self.assertIn('transceiver_module_type', ctx.exception.message_dict,
            "V7: error must be on 'transceiver_module_type' field")
        self.assertIn('DAC', str(ctx.exception),
            "V7: error message must mention the conflicting reach_class value 'DAC'")
        self.assertIn('MMF', str(ctx.exception),
            "V7: error message must mention the conflicting medium value 'MMF'")

    def test_r2_v7_dac_reach_class_on_smf_medium_raises(self):
        """R.2: V7 — reach_class='DAC' with medium='SMF' (optical) → ValidationError.

        RED until V7 is added to _validate_transceiver_module_type().
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r2-conn',
            transceiver_module_type=self.mt_dac_rc_smf_med,
        )
        from django.core.exceptions import ValidationError as DjangoVE
        with self.assertRaises(DjangoVE) as ctx:
            psc.full_clean()
        self.assertIn('transceiver_module_type', ctx.exception.message_dict,
            "V7: error must be on 'transceiver_module_type' field")
        self.assertIn('SMF', str(ctx.exception),
            "V7: error message must mention the conflicting medium value 'SMF'")

    def test_r3_v7_sr_reach_class_on_dac_medium_raises(self):
        """R.3: V7 — reach_class='SR' with medium='DAC' (copper) → ValidationError.

        RED until V7 is added to _validate_transceiver_module_type().
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r3-conn',
            transceiver_module_type=self.mt_sr_rc_dac_med,
        )
        from django.core.exceptions import ValidationError as DjangoVE
        with self.assertRaises(DjangoVE) as ctx:
            psc.full_clean()
        self.assertIn('transceiver_module_type', ctx.exception.message_dict,
            "V7: error must be on 'transceiver_module_type' field")
        self.assertIn('SR', str(ctx.exception),
            "V7: error message must mention the conflicting reach_class value 'SR'")
        self.assertIn('DAC', str(ctx.exception),
            "V7: error message must mention the conflicting medium value 'DAC'")

    def test_r4_v7_lr_reach_class_on_acc_medium_raises(self):
        """R.4: V7 — reach_class='LR' with medium='ACC' (copper) → ValidationError.

        Verifies LR (optical) + ACC (copper) is rejected. ACC is in the copper group.
        RED until V7 is added to _validate_transceiver_module_type().
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r4-conn',
            transceiver_module_type=self.mt_lr_rc_acc_med,
        )
        from django.core.exceptions import ValidationError as DjangoVE
        with self.assertRaises(DjangoVE) as ctx:
            psc.full_clean()
        self.assertIn('transceiver_module_type', ctx.exception.message_dict,
            "V7: error must be on 'transceiver_module_type' field")
        self.assertIn('LR', str(ctx.exception),
            "V7: error message must mention the conflicting reach_class value 'LR'")
        self.assertIn('ACC', str(ctx.exception),
            "V7: error message must mention the conflicting medium value 'ACC'")

    # -------------------------------------------------------------------------
    # R.5–R.9: Compatible pairs — must not raise. Green without V7.
    # -------------------------------------------------------------------------

    def test_r5_v7_dac_reach_class_dac_medium_ok(self):
        """R.5: V7 — reach_class='DAC', medium='DAC' → no error (copper-compatible)."""
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r5-conn',
            transceiver_module_type=self.mt_dac_rc_dac_med,
        )
        psc.full_clean()  # must not raise

    def test_r6_v7_dac_reach_class_acc_medium_ok(self):
        """R.6: V7 — reach_class='DAC', medium='ACC' → no error.

        ACC is in the copper group; DAC reach_class is correct for it.
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r6-conn',
            transceiver_module_type=self.mt_dac_rc_acc_med,
        )
        psc.full_clean()  # must not raise

    def test_r7_v7_sr_reach_class_mmf_medium_ok(self):
        """R.7: V7 — reach_class='SR', medium='MMF' → no error (optical-compatible)."""
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r7-conn',
            transceiver_module_type=self.mt_sr_rc_mmf_med,
        )
        psc.full_clean()  # must not raise

    def test_r8_v7_lr_reach_class_smf_medium_ok(self):
        """R.8: V7 — reach_class='LR', medium='SMF' → no error (optical-compatible, SMF variant)."""
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r8-conn',
            transceiver_module_type=self.mt_lr_rc_smf_med,
        )
        psc.full_clean()  # must not raise

    def test_r9_v7_dr_reach_class_mmf_medium_ok(self):
        """R.9: V7 — reach_class='DR', medium='MMF' → no error (DR is in the optical group)."""
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r9-conn',
            transceiver_module_type=self.mt_dr_rc_mmf_med,
        )
        psc.full_clean()  # must not raise

    # -------------------------------------------------------------------------
    # R.10–R.12: Null-skip cases — must not raise. Green without V7.
    # -------------------------------------------------------------------------

    def test_r10_v7_no_reach_class_null_skip(self):
        """R.10: V7 null-skip — reach_class absent from attribute_data → no error.

        When rc is falsy, the if-guard does not enter, regardless of medium.
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r10-conn',
            transceiver_module_type=self.mt_no_rc,  # medium='MMF', no reach_class key
        )
        psc.full_clean()  # null-skip: must not raise

    def test_r11_v7_reach_class_present_no_medium_anywhere_null_skip(self):
        """R.11: V7 null-skip — reach_class='SR', no medium in attribute_data, no flat medium.

        resolved_medium = None or '' = '' which is falsy → null-skip.
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r11-conn',
            transceiver_module_type=self.mt_rc_no_med,  # reach_class='SR', no medium key
        )
        # flat self.medium defaults to '' (empty string) — no override needed
        psc.full_clean()  # null-skip: must not raise

    def test_r12_v7_no_reach_class_flat_medium_set_null_skip(self):
        """R.12: V7 null-skip — reach_class absent, flat medium='MMF' set.

        When reach_class (rc) is falsy, the if-guard does not enter regardless of medium.
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r12-conn',
            transceiver_module_type=self.mt_no_rc,  # medium='MMF' in attrs, no reach_class
        )
        psc.medium = 'MMF'  # flat field set; V3 doesn't fire (same as attr_data); V7 skips (no rc)
        psc.full_clean()  # null-skip: must not raise

    # -------------------------------------------------------------------------
    # R.13–R.14: Fallback-medium path — medium resolved from flat self.medium.
    # -------------------------------------------------------------------------

    def test_r13_v7_dac_reach_class_fallback_medium_mmf_raises(self):
        """R.13: V7 — reach_class='DAC', no medium in attribute_data, flat self.medium='MMF' → raises.

        resolved_medium = xcvr_ad.get('medium') or self.medium = None or 'MMF' = 'MMF'.
        'MMF' ∈ optical_mediums, reach_class='DAC' → ValidationError.
        RED until V7 is added to _validate_transceiver_module_type().
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r13-conn',
            transceiver_module_type=self.mt_dac_rc_no_med,  # reach_class='DAC', no medium in attrs
        )
        psc.medium = 'MMF'  # flat medium; V3 null-skips (no attr_data medium); V7 uses as fallback
        from django.core.exceptions import ValidationError as DjangoVE
        with self.assertRaises(DjangoVE) as ctx:
            psc.full_clean()
        self.assertIn('transceiver_module_type', ctx.exception.message_dict,
            "V7: fallback medium path — error must be on 'transceiver_module_type' field")

    def test_r14_v7_sr_reach_class_fallback_medium_mmf_ok(self):
        """R.14: V7 — reach_class='SR', no medium in attribute_data, flat self.medium='MMF' → no error.

        resolved_medium = None or 'MMF' = 'MMF'. 'SR' + 'MMF' = optical/optical → compatible.
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r14-conn',
            transceiver_module_type=self.mt_rc_no_med,  # reach_class='SR', no medium in attrs
        )
        psc.medium = 'MMF'  # fallback medium — compatible with SR
        psc.full_clean()  # must not raise

    # -------------------------------------------------------------------------
    # R.15–R.16: Regression guards — seeded-like module types pass V7 cleanly.
    # -------------------------------------------------------------------------

    def test_r15_v7_regression_optical_nic_passes(self):
        """R.15: Regression — optical NIC (medium=MMF, reach_class=SR, like BF3220) passes V7.

        Ensures that the migration-seeded BF3220 attribute profile remains valid after V7 lands.
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r15-conn',
            transceiver_module_type=self.mt_reg_optical,
        )
        psc.full_clean()  # must not raise

    def test_r16_v7_regression_copper_nic_passes(self):
        """R.16: Regression — copper NIC (medium=DAC, reach_class=DAC, like CX7) passes V7.

        Ensures that the migration-seeded CX7 attribute profile remains valid after V7 lands.
        """
        psc = _make_350_base_connection(
            self.sc_r, self.nic_r, self.zone_no_xcvr_r,
            connection_id='r16-conn',
            transceiver_module_type=self.mt_reg_copper,
        )
        psc.full_clean()  # must not raise
