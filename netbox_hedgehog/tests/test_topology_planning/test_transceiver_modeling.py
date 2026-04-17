"""
RED tests for pluggable transceiver modeling (DIET-334 Phase 3).

Tests fail until Phase 4 GREEN implementation adds:
- PlanServerConnection.transceiver_module_type FK
- SwitchPortZone.transceiver_module_type FK
- DeviceGenerator._create_server_transceiver_module()
- Migration 0044
"""

import importlib

from django.core.exceptions import ValidationError
from django.test import TestCase

from dcim.models import (
    Device, DeviceType, Manufacturer, Module, ModuleBay,
    ModuleBayTemplate, ModuleType, ModuleTypeProfile, Site,
)

from netbox_hedgehog.choices import (
    AllocationStrategyChoices, ConnectionDistributionChoices,
    ConnectionTypeChoices, FabricClassChoices, FabricTypeChoices,
    HedgehogRoleChoices, PortZoneTypeChoices, TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption, DeviceTypeExtension, PlanServerClass,
    PlanServerConnection, PlanServerNIC, PlanSwitchClass,
    SwitchPortZone, TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import (
    get_test_nic_module_type,
    get_test_non_transceiver_module_type,
    get_test_transceiver_module_type,
)


def _make_xcvr_fixtures(cls):
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name='XCVR334-Mfg', defaults={'slug': 'xcvr334-mfg'}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='XCVR-SRV', defaults={'slug': 'xcvr-srv'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='XCVR-SW', defaults={'slug': 'xcvr-sw'}
    )
    # Add InterfaceTemplates so populate_transceiver_bays adds ModuleBayTemplates.
    # Port allocator names non-breakout ports E1/{n} for port_spec ranges.
    from dcim.models import InterfaceTemplate as _IT
    for _pn in range(1, 9):
        _IT.objects.get_or_create(
            device_type=cls.switch_dt, name=f'E1/{_pn}',
            defaults={'type': '200gbase-x-qsfp112'},
        )
    cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
        device_type=cls.switch_dt,
        defaults={
            'native_speed': 200, 'uplink_ports': 0,
            'supported_breakouts': ['1x200g'], 'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    cls.breakout, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x200g-xcvr',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    cls.site, _ = Site.objects.get_or_create(
        name='XCVRSite334', defaults={'slug': 'xcvrsite334'}
    )
    cls.plan = TopologyPlan.objects.create(
        name='XCVR334-Plan', status=TopologyPlanStatusChoices.DRAFT
    )
    cls.server_class = PlanServerClass.objects.create(
        plan=cls.plan, server_class_id='gpu',
        server_device_type=cls.server_dt, quantity=1,
    )
    cls.switch_class = PlanSwitchClass.objects.create(
        plan=cls.plan, switch_class_id='fe-leaf',
        fabric_name=FabricTypeChoices.FRONTEND,
        fabric_class=FabricClassChoices.MANAGED,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=cls.device_ext,
        uplink_ports_per_switch=0, mclag_pair=False,
        override_quantity=2, redundancy_type='eslag',
    )
    cls.zone = SwitchPortZone.objects.create(
        switch_class=cls.switch_class, zone_name='server-downlinks',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-64',
        breakout_option=cls.breakout,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
    )
    cls.nic = PlanServerNIC.objects.create(
        server_class=cls.server_class, nic_id='nic-fe',
        module_type=get_test_nic_module_type(),
    )


def _make_base_connection(server_class, nic, zone, connection_id='fe-001', **extra):
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


# =============================================================================
# Class A: PlanServerConnection.transceiver_module_type FK (8 tests)
# =============================================================================

class TransceiverFKOnConnectionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        _make_xcvr_fixtures(cls)
        cls.xcvr_mt = get_test_transceiver_module_type()
        cls.non_xcvr_mt = get_test_non_transceiver_module_type()
        cls.base_psc = _make_base_connection(cls.server_class, cls.nic, cls.zone)

    def test_psc_transceiver_fk_nullable_by_default(self):
        """PSC created without transceiver_module_type has the field as None."""
        self.assertTrue(
            hasattr(self.base_psc, 'transceiver_module_type'),
            "PlanServerConnection must have transceiver_module_type field (migration 0044 not applied)",
        )
        self.assertIsNone(self.base_psc.transceiver_module_type)

    def test_psc_transceiver_fk_valid_network_transceiver(self):
        """Setting FK to a Network Transceiver ModuleType passes full_clean()."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone,
            connection_id='fe-a2',
            transceiver_module_type=self.xcvr_mt,
        )
        psc.full_clean()  # must not raise

    def test_psc_transceiver_fk_rejects_non_transceiver_profile(self):
        """FK to a non-transceiver ModuleType raises ValidationError."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone, connection_id='fe-a3'
        )
        psc.transceiver_module_type = self.non_xcvr_mt
        with self.assertRaises(ValidationError) as ctx:
            psc.full_clean()
        self.assertIn(
            'Network Transceiver',
            str(ctx.exception),
            "Error message must mention 'Network Transceiver' profile",
        )

    def test_psc_transceiver_fk_set_null_on_module_type_delete(self):
        """Deleting the referenced ModuleType sets the FK to NULL (SET_NULL)."""
        tmp_mfr, _ = Manufacturer.objects.get_or_create(
            name='TmpXCVR334', defaults={'slug': 'tmpxcvr334'}
        )
        tmp_profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        tmp_mt = ModuleType.objects.create(
            manufacturer=tmp_mfr, model='TMP-XCVR-DEL',
            profile=tmp_profile,
            attribute_data={'cage_type': 'QSFP112', 'medium': 'MMF'},
        )
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone,
            connection_id='fe-a4',
            transceiver_module_type=tmp_mt,
        )
        tmp_mt.delete()
        psc.refresh_from_db()
        self.assertIsNone(psc.transceiver_module_type)

    def test_psc_flat_cage_type_mismatch_with_fk(self):
        """cage_type flat field conflicting with FK attribute_data raises ValidationError."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone, connection_id='fe-a5'
        )
        psc.transceiver_module_type = self.xcvr_mt  # QSFP112
        psc.cage_type = 'OSFP'
        with self.assertRaises(ValidationError) as ctx:
            psc.full_clean()
        self.assertIn('cage_type', ctx.exception.message_dict)

    def test_psc_flat_cage_type_matches_fk_ok(self):
        """cage_type flat field matching FK attribute_data passes full_clean()."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone, connection_id='fe-a6'
        )
        psc.transceiver_module_type = self.xcvr_mt  # QSFP112
        psc.cage_type = 'QSFP112'
        psc.full_clean()  # must not raise

    def test_psc_flat_medium_mismatch_with_fk(self):
        """medium flat field conflicting with FK attribute_data raises ValidationError."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone, connection_id='fe-a7'
        )
        psc.transceiver_module_type = self.xcvr_mt  # medium=MMF
        psc.medium = 'DAC'
        with self.assertRaises(ValidationError) as ctx:
            psc.full_clean()
        self.assertIn('medium', ctx.exception.message_dict)

    def test_existing_psc_without_fk_rejected(self):
        """DIET-466: PSC with no transceiver FK fails full_clean()."""
        with self.assertRaises(ValidationError) as ctx:
            self.base_psc.full_clean()
        self.assertIn('transceiver_module_type', ctx.exception.message_dict)


# =============================================================================
# Class B: SwitchPortZone.transceiver_module_type FK (5 tests)
# =============================================================================

class TransceiverFKOnZoneTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        _make_xcvr_fixtures(cls)
        cls.xcvr_mt = get_test_transceiver_module_type()
        cls.non_xcvr_mt = get_test_non_transceiver_module_type()

    def test_spz_transceiver_fk_nullable_by_default(self):
        """SwitchPortZone has transceiver_module_type field defaulting to None."""
        self.assertTrue(
            hasattr(self.zone, 'transceiver_module_type'),
            "SwitchPortZone must have transceiver_module_type field (migration 0044 not applied)",
        )
        self.assertIsNone(self.zone.transceiver_module_type)

    def test_spz_transceiver_fk_valid(self):
        """Setting transceiver_module_type to a Network Transceiver ModuleType passes."""
        zone2 = SwitchPortZone.objects.create(
            switch_class=self.switch_class, zone_name='zone-b2',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-32',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=200,
            transceiver_module_type=self.xcvr_mt,
        )
        zone2.full_clean()  # must not raise

    def test_spz_transceiver_fk_rejects_non_transceiver_profile(self):
        """Non-transceiver ModuleType raises ValidationError."""
        zone3 = SwitchPortZone.objects.create(
            switch_class=self.switch_class, zone_name='zone-b3',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='33-48',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=300,
        )
        zone3.transceiver_module_type = self.non_xcvr_mt
        with self.assertRaises(ValidationError) as ctx:
            zone3.full_clean()
        self.assertIn('Network Transceiver', str(ctx.exception))

    def test_spz_transceiver_fk_set_null_on_delete(self):
        """Deleting referenced ModuleType sets zone FK to NULL."""
        tmp_mfr, _ = Manufacturer.objects.get_or_create(
            name='TmpXCVRZ334', defaults={'slug': 'tmpxcvrz334'}
        )
        tmp_profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        tmp_mt = ModuleType.objects.create(
            manufacturer=tmp_mfr, model='TMP-XCVR-Z-DEL',
            profile=tmp_profile,
            attribute_data={'cage_type': 'QSFP112', 'medium': 'MMF'},
        )
        zone4 = SwitchPortZone.objects.create(
            switch_class=self.switch_class, zone_name='zone-b4',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='49-64',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=400,
            transceiver_module_type=tmp_mt,
        )
        tmp_mt.delete()
        zone4.refresh_from_db()
        self.assertIsNone(zone4.transceiver_module_type)

    def test_spz_transceiver_independent_of_other_fields(self):
        """transceiver_module_type does not interfere with port_spec or breakout validation."""
        zone5 = SwitchPortZone.objects.create(
            switch_class=self.switch_class, zone_name='zone-b5',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-8',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=500,
            transceiver_module_type=self.xcvr_mt,
        )
        zone5.full_clean()  # port_spec and breakout_option still valid


# =============================================================================
# Class C: Cross-end compatibility validation (8 tests)
# =============================================================================

class CrossEndCompatibilityTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        _make_xcvr_fixtures(cls)
        cls.xcvr_qsfp112_mmf = get_test_transceiver_module_type()  # QSFP112/MMF

        xcvr_profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        cls.xcvr_osfp_mmf, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='XCVR-OSFP-MMF-C',
            defaults={
                'profile': xcvr_profile,
                'attribute_data': {'cage_type': 'OSFP', 'medium': 'MMF'},
            },
        )
        cls.xcvr_dac, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.mfr, model='XCVR-DAC-C',
            defaults={
                'profile': xcvr_profile,
                'attribute_data': {'cage_type': 'QSFP112', 'medium': 'DAC'},
            },
        )
        # Zone with QSFP112/MMF transceiver intent
        cls.zone_qsfp112 = SwitchPortZone.objects.create(
            switch_class=cls.switch_class, zone_name='zone-c-qsfp112',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-32',
            breakout_option=cls.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=200,
            transceiver_module_type=cls.xcvr_qsfp112_mmf,
        )
        # Zone with DAC transceiver intent
        cls.zone_dac = SwitchPortZone.objects.create(
            switch_class=cls.switch_class, zone_name='zone-c-dac',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='33-48',
            breakout_option=cls.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=300,
            transceiver_module_type=cls.xcvr_dac,
        )

    def test_matching_cage_type_passes(self):
        """PSC QSFP112 FK + zone QSFP112 FK: full_clean() passes."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone_qsfp112,
            connection_id='fe-c1',
            transceiver_module_type=self.xcvr_qsfp112_mmf,
        )
        psc.full_clean()

    def test_mismatched_cage_type_raises(self):
        """PSC OSFP FK + zone QSFP112 FK: raises ValidationError."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone_qsfp112,
            connection_id='fe-c2',
            transceiver_module_type=self.xcvr_osfp_mmf,
        )
        with self.assertRaises(ValidationError):
            psc.full_clean()

    def test_dac_both_ends_ok(self):
        """PSC DAC FK + zone DAC FK: full_clean() passes."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone_dac,
            connection_id='fe-c3',
            transceiver_module_type=self.xcvr_dac,
        )
        psc.full_clean()

    def test_dac_server_fiber_zone_error(self):
        """PSC DAC medium + zone MMF medium: raises ValidationError."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone_qsfp112,
            connection_id='fe-c4',
            transceiver_module_type=self.xcvr_dac,
        )
        with self.assertRaises(ValidationError):
            psc.full_clean()

    def test_fiber_server_dac_zone_error(self):
        """PSC MMF medium + zone DAC medium: raises ValidationError."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone_dac,
            connection_id='fe-c5',
            transceiver_module_type=self.xcvr_qsfp112_mmf,
        )
        with self.assertRaises(ValidationError):
            psc.full_clean()

    def test_no_zone_transceiver_skips_cross_end_check(self):
        """Zone without transceiver FK: no cross-end check runs."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone,  # cls.zone has no transceiver FK
            connection_id='fe-c6',
            transceiver_module_type=self.xcvr_qsfp112_mmf,
        )
        psc.full_clean()  # must not raise

    def test_flat_cage_type_vs_xcvr_fk_mismatch(self):
        """DIET-450: cage_type='OSFP' flat conflicts with xcvr FK QSFP112: raises ValidationError."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone_qsfp112,
            connection_id='fe-c7',
            transceiver_module_type=self.xcvr_qsfp112_mmf,  # DIET-466: required
        )
        psc.cage_type = 'OSFP'  # conflicts with transceiver_module_type.attribute_data['cage_type']='QSFP112'
        with self.assertRaises(ValidationError) as ctx:
            psc.full_clean()
        self.assertIn('cage_type', ctx.exception.message_dict)

    def test_flat_medium_vs_xcvr_fk_mismatch(self):
        """DIET-450: medium='DAC' flat conflicts with xcvr FK medium='MMF': raises ValidationError."""
        psc = _make_base_connection(
            self.server_class, self.nic, self.zone_qsfp112,
            connection_id='fe-c8',
            transceiver_module_type=self.xcvr_qsfp112_mmf,  # DIET-466: required
        )
        psc.medium = 'DAC'  # conflicts with transceiver_module_type.attribute_data['medium']='MMF'
        with self.assertRaises(ValidationError) as ctx:
            psc.full_clean()
        self.assertIn('medium', ctx.exception.message_dict)


# =============================================================================
# Class D: Generator - server-side transceiver Module creation (8 tests)
# =============================================================================

class ServerTransceiverGeneratorTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        _make_xcvr_fixtures(cls)
        cls.xcvr_mt = get_test_transceiver_module_type()

    def setUp(self):
        from dcim.models import Cable
        Device.objects.filter(custom_field_data__has_key='hedgehog_plan_id').delete()
        Cable.objects.all().delete()

    def tearDown(self):
        from dcim.models import Cable
        Device.objects.filter(custom_field_data__has_key='hedgehog_plan_id').delete()
        Cable.objects.all().delete()

    def _make_gen_plan(self, set_xcvr=True):
        plan = TopologyPlan.objects.create(
            name=f'GenXCVR334-{id(self)}', status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu', server_device_type=self.server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND, fabric_class=FabricClassChoices.MANAGED,
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
            server_class=sc, nic_id='nic-fe', module_type=get_test_nic_module_type(),
        )
        xcvr = self.xcvr_mt if set_xcvr else None
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
            transceiver_module_type=xcvr,
        )
        return plan

    def _generate(self, plan):
        from django.core.management import call_command as _cc
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        # Stage 2: populate bays before generation so nested placement works.
        _cc('populate_transceiver_bays')
        DeviceGenerator(plan).generate_all()

    def test_transceiver_module_created_when_fk_set(self):
        """Generation creates a transceiver Module on the server device when FK is set."""
        plan = self._make_gen_plan(set_xcvr=True)
        self._generate(plan)
        xcvr_modules = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            module_type=self.xcvr_mt,
        )
        self.assertEqual(xcvr_modules.count(), 1, "Expected 1 transceiver Module")

    def test_transceiver_module_bay_name(self):
        """Stage 2: transceiver is in nested bay 'cage-0' inside the NIC Module (not device-level)."""
        # Stage 2: intentional update from Stage 1 assertion (device-level 'nic-fe-cage-0').
        plan = self._make_gen_plan(set_xcvr=True)
        self._generate(plan)
        nic_modules = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            module_type=get_test_nic_module_type(),
        )
        self.assertGreater(nic_modules.count(), 0, "NIC Module must exist")
        nested_bay = ModuleBay.objects.filter(
            module=nic_modules.first(), name='cage-0',
        ).first()
        self.assertIsNotNone(nested_bay,
            "Stage 2: transceiver bay 'cage-0' must be nested inside NIC Module")

    def test_transceiver_module_status_is_planned(self):
        """Generated transceiver Module has status='planned'."""
        plan = self._make_gen_plan(set_xcvr=True)
        self._generate(plan)
        xcvr_mod = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            module_type=self.xcvr_mt,
        ).first()
        self.assertIsNotNone(xcvr_mod)
        self.assertEqual(xcvr_mod.status, 'planned')

    def test_transceiver_module_skipped_when_fk_null(self):
        """No transceiver Module created when transceiver_module_type FK is null."""
        plan = self._make_gen_plan(set_xcvr=False)
        self._generate(plan)
        xcvr_modules = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            module_type=self.xcvr_mt,
        )
        self.assertEqual(xcvr_modules.count(), 0)

    def test_transceiver_module_has_correct_module_type(self):
        """Created transceiver Module references the correct ModuleType."""
        plan = self._make_gen_plan(set_xcvr=True)
        self._generate(plan)
        xcvr_mod = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            module_type=self.xcvr_mt,
        ).first()
        self.assertIsNotNone(xcvr_mod)
        self.assertEqual(xcvr_mod.module_type_id, self.xcvr_mt.pk)

    def test_transceiver_module_cascade_deleted_on_device_delete(self):
        """Deleting the server Device cascades to transceiver ModuleBay and Module."""
        plan = self._make_gen_plan(set_xcvr=True)
        self._generate(plan)
        server_device = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
        ).filter(device_type=self.server_dt).first()
        self.assertIsNotNone(server_device)
        device_pk = server_device.pk
        server_device.delete()
        self.assertFalse(
            ModuleBay.objects.filter(device_id=device_pk).exists(),
            "ModuleBays must be cascade-deleted with Device",
        )
        self.assertFalse(
            Module.objects.filter(
                device_id=device_pk, module_type=self.xcvr_mt
            ).exists(),
            "Transceiver Modules must be cascade-deleted with Device",
        )


# =============================================================================
# Class E: Migration tests (4 tests)
# =============================================================================

class TransceiverMigrationTestCase(TestCase):

    def _get_migration_0044(self):
        return importlib.import_module(
            'netbox_hedgehog.migrations.0044_transceiver_module_type'
        )

    def test_migration_0044_exists(self):
        """Migration 0044 module must be importable."""
        try:
            m = self._get_migration_0044()
            self.assertIsNotNone(m)
        except ModuleNotFoundError:
            self.fail("Migration 0044_transceiver_module_type does not exist yet")

    def test_migration_0044_has_psc_and_spz_addfields(self):
        """Migration 0044 must declare AddField operations for both models."""
        m = self._get_migration_0044()
        ops = m.Migration.operations
        op_reprs = [repr(op) for op in ops]
        all_ops = ' '.join(op_reprs).lower()
        self.assertIn('planserverconnection', all_ops,
                      "Migration must AddField on planserverconnection")
        self.assertIn('switchportzone', all_ops,
                      "Migration must AddField on switchportzone")

    def test_migration_0044_profile_update_function_exists(self):
        """Migration 0044 must define update_network_transceiver_profile callable."""
        m = self._get_migration_0044()
        self.assertTrue(
            hasattr(m, 'update_network_transceiver_profile'),
            "Migration 0044 must define update_network_transceiver_profile(apps, schema_editor)",
        )

    def test_profile_schema_updated_after_migration_function(self):
        """Running update_network_transceiver_profile adds OSFP, ACC, MPO-16."""
        m = self._get_migration_0044()
        from unittest.mock import MagicMock
        # Run against the real profile in the live test DB
        m.update_network_transceiver_profile(MagicMock(), None)
        profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        if profile is None:
            self.skipTest("Network Transceiver profile not present in test DB")
        schema = profile.schema or {}
        props = schema.get('properties', {})
        cage_enums = props.get('cage_type', {}).get('enum', [])
        medium_enums = props.get('medium', {}).get('enum', [])
        connector_enums = props.get('connector', {}).get('enum', [])
        self.assertIn('OSFP', cage_enums, "OSFP must be in cage_type enum after migration")
        self.assertIn('ACC', medium_enums, "ACC must be in medium enum after migration")
        self.assertIn('MPO-16', connector_enums, "MPO-16 must be in connector enum after migration")
        self.assertIn('lane_count', props, "lane_count must be added to profile schema")


# =============================================================================
# Class F: Stage 2 assertions (replacing Stage 1 boundary guardrails)
# =============================================================================
# Stage 2: intentional replacement of Stage 1 Class F guardrail assertions.
# The original Stage 1 assertions tested temporary approximation boundaries
# ("not yet generated"). Stage 2 replaces each with the correct target behavior.
# All three tests below are RED until Stage 2 GREEN implementation lands.

class Stage1BoundaryTestCase(TestCase):
    """
    Stage 2 replacement of Stage 1 Class F guardrail tests.

    F.1 now asserts transceiver is NESTED inside NIC Module bay (not device-level).
    F.2 now asserts switch-side transceiver Modules ARE created when FK is set.
    F.3 now asserts NIC ModuleType HAS nested ModuleBayTemplate children after command.
    All three are intentionally RED until Stage 2 implementation is complete.
    """

    @classmethod
    def setUpTestData(cls):
        _make_xcvr_fixtures(cls)
        cls.xcvr_mt = get_test_transceiver_module_type()
        cls.nic_mt = get_test_nic_module_type()

    def setUp(self):
        from dcim.models import Cable
        Device.objects.filter(custom_field_data__has_key='hedgehog_plan_id').delete()
        Cable.objects.all().delete()

    def tearDown(self):
        from dcim.models import Cable
        Device.objects.filter(custom_field_data__has_key='hedgehog_plan_id').delete()
        Cable.objects.all().delete()

    def _make_and_generate(self):
        plan = TopologyPlan.objects.create(
            name=f'BoundaryPlan334-{id(self)}', status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu', server_device_type=self.server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND, fabric_class=FabricClassChoices.MANAGED,
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
            server_class=sc, nic_id='nic-fe', module_type=self.nic_mt,
        )
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
            transceiver_module_type=self.xcvr_mt,
        )
        from django.core.management import call_command as _cc
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        _cc('populate_transceiver_bays')
        DeviceGenerator(plan).generate_all()
        return plan

    def test_stage1_server_transceiver_bay_is_device_level_not_nested(self):
        """
        Stage 2: transceiver ModuleBay is NESTED inside NIC Module (module_id set, not device-level).
        Stage 2: intentional replacement of Stage 1 Class F guardrail assertion.
        RED until Stage 2 nested NIC-port-bay placement is implemented.
        """
        plan = self._make_and_generate()
        # In Stage 2 the transceiver bay is a child of the NIC Module, not at device level.
        # Find NIC module for this plan's server device.
        from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type
        nic_modules = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            module_type=get_test_nic_module_type(),
        )
        self.assertGreater(nic_modules.count(), 0, "NIC Module must be created by generator")
        nic_module = nic_modules.first()
        # Transceiver Module must be nested inside NIC module's bay.
        nested_xcvr = Module.objects.filter(
            module_bay__module=nic_module,
        )
        self.assertGreater(nested_xcvr.count(), 0,
            "Transceiver Module must be nested inside NIC Module bay in Stage 2 (module_bay.module set)")
        # Device-level bay 'nic-fe-cage-0' must NOT exist (Stage 1 scaffolding retired).
        device_level_bay = ModuleBay.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            name='nic-fe-cage-0',
            module__isnull=True,
        ).first()
        self.assertIsNone(device_level_bay,
            "Stage 1 device-level transceiver bay must not exist in Stage 2")

    def test_stage1_no_switch_side_transceiver_modules(self):
        """
        Stage 2: switch-side transceiver Modules ARE created when zone.transceiver_module_type is set.
        Stage 2: intentional replacement of Stage 1 Class F guardrail assertion.
        RED until Stage 2 switch-side Module placement is implemented.
        """
        plan = TopologyPlan.objects.create(
            name=f'F2BoundaryPlan-{id(self)}', status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu', server_device_type=self.server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND, fabric_class=FabricClassChoices.MANAGED,
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
            transceiver_module_type=self.xcvr_mt,
        )
        nic = PlanServerNIC.objects.create(
            server_class=sc, nic_id='nic-fe', module_type=self.nic_mt,
        )
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe',
            nic=nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
        )
        from django.core.management import call_command as _cc
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        _cc('populate_transceiver_bays')
        DeviceGenerator(plan).generate_all()
        switch_modules = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            device__device_type=self.switch_dt,
            status='planned',
        )
        self.assertGreater(
            switch_modules.count(), 0,
            "Stage 2 must generate switch-side transceiver Modules when zone.transceiver_module_type is set",
        )

    def test_stage1_no_nested_module_bay_templates_on_nic_module_types(self):
        """
        Stage 2: NIC ModuleType HAS nested ModuleBayTemplate children after populate_transceiver_bays.
        Stage 2: intentional replacement of Stage 1 Class F guardrail assertion.
        RED until populate_transceiver_bays command adds nested bay templates.
        """
        from django.core.management import call_command as _cc
        _cc('populate_transceiver_bays')
        nested_bays = ModuleBayTemplate.objects.filter(module_type=self.nic_mt)
        self.assertGreater(
            nested_bays.count(), 0,
            "Stage 2: populate_transceiver_bays must add nested ModuleBayTemplate children to NIC ModuleType",
        )
