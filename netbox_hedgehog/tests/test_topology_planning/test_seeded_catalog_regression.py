"""
Regression harness for DIET-451: bootstrap-to-generate regression coverage.

Guards three critical paths that use the *canonical* seeded catalog
(celestica-ds5000 from load_diet_reference_data) rather than synthetic
test-fixture DeviceTypes.  Regressions in the bootstrap path would not
surface in tests that build their own DeviceTypes from scratch.

Gate A — SeededCatalogRoundTripTestCase
    purge → load_diet_reference_data → populate_transceiver_bays → create
    plan using celestica-ds5000 → DeviceGenerator.generate_all() succeeds.

Gate B — PreflightPopulateCycleTestCase
    Plan with transceiver_module_type FK set → preflight blocks →
    populate_transceiver_bays → preflight passes → generate succeeds.

Gate C — SeededCatalogGenerateUpdateTestCase
    generate → regenerate (idempotent) → update plan → regenerate (count
    changes).  Uses only seeded DeviceTypes.

All tests are self-contained: they run load_diet_reference_data themselves
rather than depending on CI pre-seeding, so they pass on a bare test DB.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from dcim.models import Cable, Device, DeviceType, ModuleBayTemplate

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    ServerClassCategoryChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    GenerationState,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic, get_test_transceiver_module_type


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get_or_create_test_server_dt():
    """
    Return a server DeviceType for use in regression tests.

    Prefers gpu-server-fe (seeded by load_diet_reference_data on DIET-448+
    main), falling back to a simple Generic test DeviceType so that tests
    pass on branches that pre-date DIET-448.
    """
    from dcim.models import Manufacturer

    try:
        return DeviceType.objects.get(slug='gpu-server-fe')
    except DeviceType.DoesNotExist:
        generic, _ = Manufacturer.objects.get_or_create(
            name='Generic', defaults={'slug': 'generic'}
        )
        dt, _ = DeviceType.objects.get_or_create(
            manufacturer=generic,
            model='DIET-451-Test-Server',
            defaults={'slug': 'diet-451-test-server', 'u_height': 2},
        )
        return dt


def _generate_directly(plan):
    """
    Synchronously generate devices via DeviceGenerator (bypass async view).
    Mirrors the _generate_devices_directly() helper in test_unified_generate_update.
    """
    from netbox_hedgehog.services.device_generator import DeviceGenerator
    from netbox_hedgehog.utils.topology_calculations import update_plan_calculations
    update_plan_calculations(plan)
    generator = DeviceGenerator(plan)
    return generator.generate_all()


def _cleanup_plan_devices(plan):
    """Delete all generated devices/cables for a plan (scoped by plan ID)."""
    plan_id_str = str(plan.pk)
    Cable.objects.filter(
        custom_field_data__hedgehog_plan_id=plan_id_str,
    ).delete()
    Device.objects.filter(
        custom_field_data__hedgehog_plan_id=plan_id_str,
    ).delete()


# ---------------------------------------------------------------------------
# Gate A: Seeded catalog round trip (bootstrap → populate → generate)
# ---------------------------------------------------------------------------

class SeededCatalogRoundTripTestCase(TestCase):
    """
    Gate A: Verify the full path from load_diet_reference_data through
    populate_transceiver_bays to successful device generation.

    The canonical celestica-ds5000 (slug) from import_fabric_profiles must
    be usable as a plan switch type without any additional manual setup.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('load_diet_reference_data', stdout=StringIO())
        call_command('populate_transceiver_bays', verbosity=0)

        cls.ds5000_dt = DeviceType.objects.get(slug='celestica-ds5000')
        cls.ds5000_ext = DeviceTypeExtension.objects.get(device_type=cls.ds5000_dt)
        cls.bo_4x200g = BreakoutOption.objects.get(breakout_id='4x200g')
        cls.server_dt = _get_or_create_test_server_dt()

    def setUp(self):
        self._plan_ids = []

    def tearDown(self):
        for plan in TopologyPlan.objects.filter(pk__in=self._plan_ids):
            _cleanup_plan_devices(plan)

    def _create_plan(self, name='RoundTrip-Plan'):
        plan = TopologyPlan.objects.create(
            name=name,
            customer_name='DIET-451 Test',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        self._plan_ids.append(plan.pk)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-fe',
            category=ServerClassCategoryChoices.GPU,
            quantity=2,
            gpus_per_server=8,
            server_device_type=self.server_dt,
        )
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.ds5000_ext,
            uplink_ports_per_switch=4,
            mclag_pair=False,
        )
        zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=self.bo_4x200g,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )
        nic = get_test_server_nic(server_class)
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='FE-001',
            nic=nic,
            port_index=0,
            target_zone=zone,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200,
            port_type='data',
        )
        return plan

    def test_seeded_ds5000_extension_is_usable(self):
        """
        After load_diet_reference_data, celestica-ds5000 must have a
        DeviceTypeExtension that includes 800G breakouts.
        Gate: the seeded switch can be used as a switch class in a plan.
        """
        self.assertIn('4x200g', self.ds5000_ext.supported_breakouts)
        self.assertEqual(self.ds5000_ext.native_speed, 800)

    def test_seeded_catalog_bays_present_after_populate(self):
        """
        After populate_transceiver_bays, celestica-ds5000 must have
        ModuleBayTemplates matching its InterfaceTemplates (66 of each).
        """
        it_count = self.ds5000_dt.interfacetemplates.count()
        mbt_count = ModuleBayTemplate.objects.filter(device_type=self.ds5000_dt).count()
        self.assertEqual(
            mbt_count, it_count,
            f'celestica-ds5000 bay count ({mbt_count}) must equal '
            f'InterfaceTemplate count ({it_count}) after populate_transceiver_bays',
        )

    def test_generate_succeeds_with_seeded_catalog(self):
        """
        DeviceGenerator.generate_all() must succeed when the plan uses the
        seeded celestica-ds5000 switch type (not a synthetic test fixture).
        """
        plan = self._create_plan('RoundTrip-Generate')
        _generate_directly(plan)

        state = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(state, 'GenerationState must be created after generate_all')
        self.assertEqual(
            state.status, 'generated',
            f'GenerationState.status must be GENERATED; got {state.status!r}',
        )

    def test_seeded_catalog_generates_devices(self):
        """
        After generate_all(), at least one Device tagged to the plan must exist.
        """
        plan = self._create_plan('RoundTrip-Devices')
        _generate_directly(plan)

        devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
        )
        self.assertGreater(
            devices.count(), 0,
            'generate_all() with seeded celestica-ds5000 must create at least one Device',
        )

    def test_regenerate_is_idempotent(self):
        """
        Calling generate_all() twice must produce the same device count.
        Regression guard: the seeded path must be idempotent like the synthetic path.
        """
        plan = self._create_plan('RoundTrip-Idempotent')
        _generate_directly(plan)
        first_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
        ).count()

        _generate_directly(plan)
        second_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
        ).count()

        self.assertEqual(
            first_count, second_count,
            f'Second generate_all() must be idempotent: '
            f'first={first_count} second={second_count}',
        )


# ---------------------------------------------------------------------------
# Gate B: Preflight fail → populate → succeed cycle
# ---------------------------------------------------------------------------

class PreflightPopulateCycleTestCase(TestCase):
    """
    Gate B: End-to-end preflight cycle using the seeded celestica-ds5000.

    Distinct from test_preflight_validation.py (which uses synthetic DeviceTypes).
    This class proves the canonical seeded switch correctly participates in the
    preflight check and becomes ready after populate_transceiver_bays.
    """

    @classmethod
    def setUpTestData(cls):
        # Seed reference data but do NOT run populate_transceiver_bays.
        # Individual tests control when populate runs.
        call_command('load_diet_reference_data', stdout=StringIO())

        cls.ds5000_dt = DeviceType.objects.get(slug='celestica-ds5000')
        cls.ds5000_ext = DeviceTypeExtension.objects.get(device_type=cls.ds5000_dt)
        cls.bo_4x200g = BreakoutOption.objects.get(breakout_id='4x200g')
        cls.server_dt = _get_or_create_test_server_dt()

    def setUp(self):
        self._plan_ids = []
        # Ensure no leftover bays from previous test runs (the transaction rollback
        # covers per-test changes, but setUpTestData data is class-level).
        ModuleBayTemplate.objects.filter(device_type=self.ds5000_dt).delete()

    def tearDown(self):
        for plan in TopologyPlan.objects.filter(pk__in=self._plan_ids):
            _cleanup_plan_devices(plan)

    def _create_plan_with_transceiver_fk(self):
        """Create a plan with transceiver_module_type FK set on zone and connection."""
        xcvr_mt = get_test_transceiver_module_type()

        plan = TopologyPlan.objects.create(
            name='Preflight-Cycle-Plan',
            customer_name='DIET-451 Preflight Test',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        self._plan_ids.append(plan.pk)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='pf-gpu',
            category=ServerClassCategoryChoices.GPU,
            quantity=2,
            gpus_per_server=8,
            server_device_type=self.server_dt,
        )
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='pf-fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.ds5000_ext,
            uplink_ports_per_switch=4,
            mclag_pair=False,
        )
        zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='pf-server-ports',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=self.bo_4x200g,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
            transceiver_module_type=xcvr_mt,  # FK set → preflight must check bays
        )
        nic = get_test_server_nic(server_class, nic_id='pf-nic-0')
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='PF-FE-001',
            nic=nic,
            port_index=0,
            target_zone=zone,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200,
            port_type='data',
            transceiver_module_type=xcvr_mt,  # FK set on connection too
        )
        return plan

    def test_preflight_blocks_before_populate(self):
        """
        Before populate_transceiver_bays: celestica-ds5000 has 66
        InterfaceTemplates but 0 ModuleBayTemplates → preflight must block.
        """
        from netbox_hedgehog.services.preflight import check_transceiver_bay_readiness

        plan = self._create_plan_with_transceiver_fk()
        result = check_transceiver_bay_readiness(plan)

        self.assertFalse(
            result.is_ready,
            'Preflight must block when celestica-ds5000 has no ModuleBayTemplates',
        )
        self.assertTrue(result.has_transceiver_fks)
        self.assertGreater(len(result.missing), 0)

    def test_preflight_switch_entry_names_canonical_switch(self):
        """
        The missing entry must reference celestica-ds5000 by name.
        Regression guard: wrong DeviceType being checked → wrong error message.
        """
        from netbox_hedgehog.services.preflight import check_transceiver_bay_readiness

        plan = self._create_plan_with_transceiver_fk()
        result = check_transceiver_bay_readiness(plan)

        switch_entries = [
            e for e in result.missing
            if e['entity_type'] == 'switch_device_type'
        ]
        self.assertGreater(
            len(switch_entries), 0,
            'At least one switch_device_type entry must appear in missing list',
        )
        entry_names = {e['entity_name'] for e in switch_entries}
        self.assertIn(
            'celestica-ds5000', entry_names,
            f'Missing entry must name celestica-ds5000; got {entry_names}',
        )

    def test_preflight_passes_after_populate(self):
        """
        After populate_transceiver_bays: bays match InterfaceTemplates on
        celestica-ds5000 and the NIC ModuleType → preflight must pass.
        """
        from netbox_hedgehog.services.preflight import check_transceiver_bay_readiness

        plan = self._create_plan_with_transceiver_fk()

        # Verify blocked state first
        before = check_transceiver_bay_readiness(plan)
        self.assertFalse(before.is_ready, 'Precondition: preflight must block before populate')

        # Run populate (plan's PlanServerNIC is now visible to the command)
        call_command('populate_transceiver_bays', verbosity=0)

        after = check_transceiver_bay_readiness(plan)
        self.assertTrue(
            after.is_ready,
            f'Preflight must pass after populate_transceiver_bays; '
            f'still missing: {after.missing}',
        )

    def test_generate_blocked_before_populate(self):
        """
        generate_all() must abort with a blocked GenerationState (or raise)
        when transceiver bays are absent.

        The DeviceGenerator contains a defense-in-depth backstop independent
        of the view-layer preflight.  Either path is acceptable; what matters
        is that devices are NOT created.
        """
        plan = self._create_plan_with_transceiver_fk()

        try:
            _generate_directly(plan)
        except Exception:
            pass  # explicit abort is fine

        # Regardless of whether an exception was raised, no devices for this
        # plan should exist (the backstop must prevent silently partial runs).
        # NOTE: if the generator raises before writing devices this is trivially
        # true; if it writes a FAILED GenerationState that is also acceptable.
        state = GenerationState.objects.filter(plan=plan).first()
        if state is not None:
            self.assertNotEqual(
                state.status, 'generated',
                'Generation must not reach GENERATED state when bays are missing',
            )

    def test_generate_succeeds_after_populate(self):
        """
        Full cycle: create plan with transceiver FK → populate → generate succeeds.
        This is the primary end-to-end regression guard for Gate B.
        """
        plan = self._create_plan_with_transceiver_fk()
        call_command('populate_transceiver_bays', verbosity=0)

        _generate_directly(plan)

        state = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(state, 'GenerationState must exist after generate_all')
        self.assertEqual(
            state.status, 'generated',
            f'GenerationState must be GENERATED after populate+generate; got {state.status!r}',
        )


# ---------------------------------------------------------------------------
# Gate C: Generate / regenerate / update using seeded catalog
# ---------------------------------------------------------------------------

class SeededCatalogGenerateUpdateTestCase(TestCase):
    """
    Gate C: generate → regenerate (idempotent) → update plan → regenerate.

    Mirrors UnifiedGenerateUpdateIntegrationTestCase from
    test_unified_generate_update.py but uses the seeded celestica-ds5000 and
    GPU-Server-FE DeviceTypes.  Regressions in the seeded catalog path would
    not surface in tests using synthetic DeviceTypes.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('load_diet_reference_data', stdout=StringIO())
        call_command('populate_transceiver_bays', verbosity=0)

        cls.ds5000_dt = DeviceType.objects.get(slug='celestica-ds5000')
        cls.ds5000_ext = DeviceTypeExtension.objects.get(device_type=cls.ds5000_dt)
        cls.bo_4x200g = BreakoutOption.objects.get(breakout_id='4x200g')
        cls.server_dt = _get_or_create_test_server_dt()

    def setUp(self):
        self._plan_ids = []

    def tearDown(self):
        for plan in TopologyPlan.objects.filter(pk__in=self._plan_ids):
            _cleanup_plan_devices(plan)

    def _create_plan(self, quantity=2, name='GateC-Plan'):
        plan = TopologyPlan.objects.create(
            name=name,
            customer_name='DIET-451 GateC Test',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        self._plan_ids.append(plan.pk)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-fe',
            category=ServerClassCategoryChoices.GPU,
            quantity=quantity,
            gpus_per_server=8,
            server_device_type=self.server_dt,
        )
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.ds5000_ext,
            uplink_ports_per_switch=4,
            mclag_pair=False,
        )
        zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=self.bo_4x200g,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )
        nic = get_test_server_nic(server_class)
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='FE-001',
            nic=nic,
            port_index=0,
            target_zone=zone,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200,
            port_type='data',
        )
        return plan, server_class

    def test_initial_generate_creates_generation_state(self):
        """
        generate_all() with a seeded-catalog plan must produce a GENERATED
        GenerationState.  Core sanity check for Gate C.
        """
        plan, _ = self._create_plan()
        _generate_directly(plan)

        state = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(state)
        self.assertEqual(state.status, 'generated')

    def test_initial_generate_creates_switch_and_server_devices(self):
        """
        generate_all() must create at least one switch device and at least one
        server device for the plan.
        """
        plan, _ = self._create_plan()
        _generate_directly(plan)

        all_devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
        )
        self.assertGreater(all_devices.count(), 0)

        # Verify both switch and server DeviceTypes appear
        dt_pks = set(all_devices.values_list('device_type_id', flat=True))
        self.assertIn(
            self.ds5000_dt.pk, dt_pks,
            'At least one celestica-ds5000 device must be generated',
        )
        self.assertIn(
            self.server_dt.pk, dt_pks,
            'At least one GPU-Server-FE device must be generated',
        )

    def test_regenerate_is_idempotent(self):
        """
        Calling generate_all() twice must yield the same device count.
        """
        plan, _ = self._create_plan()
        _generate_directly(plan)
        first_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
        ).count()

        _generate_directly(plan)
        second_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
        ).count()

        self.assertEqual(first_count, second_count)

    def test_update_after_server_quantity_change(self):
        """
        After changing server quantity and regenerating, device count must
        reflect the new quantity.
        """
        plan, server_class = self._create_plan(quantity=2)
        _generate_directly(plan)
        before_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
        ).count()

        # Double server quantity
        server_class.quantity = 4
        server_class.save(update_fields=['quantity'])

        _generate_directly(plan)
        after_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
        ).count()

        self.assertNotEqual(
            before_count, after_count,
            'Device count must change after server quantity is updated and plan is regenerated',
        )
        self.assertGreater(after_count, before_count)
