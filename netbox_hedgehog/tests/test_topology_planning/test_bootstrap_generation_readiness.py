"""
#626: the documented bootstrap must leave a fresh environment generation-ready.

`load_diet_reference_data` is the canonical bootstrap command (see
management/commands/README.md).  Before #626 it seeded DeviceTypes,
ModuleTypes and BreakoutOptions but not the ModuleBayTemplate rows that
transceiver placement requires, so a fresh environment looked ready and then
failed every generation attempt with

    Generation failed: Transceiver bays missing. Run populate_transceiver_bays.

The bays were only ever created by a separate manual command that nothing in
the bootstrap or reset path invoked.  These tests pin the repaired contract:
bootstrap alone must be sufficient for generation against the bundled catalog.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from dcim.models import (
    DeviceType,
    InterfaceTemplate,
    Manufacturer,
    ModuleBayTemplate,
    ModuleType,
)

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricClassChoices,
    GenerationStatusChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    ServerClassCategoryChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanServerClass,
    PlanServerConnection,
    PlanServerNIC,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.seed_catalog import STATIC_NIC_MODULE_TYPES
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.services.preflight import check_transceiver_bay_readiness


def _seeded_nic_module_type():
    """Return a NIC ModuleType the bundled catalog seeds, with its ports."""
    for spec in STATIC_NIC_MODULE_TYPES:
        if not spec.get('interface_templates'):
            continue
        mt = ModuleType.objects.filter(
            manufacturer__slug=spec['manufacturer_slug'],
            model=spec['model'],
        ).first()
        if mt is not None:
            return mt
    raise AssertionError('bootstrap seeded no NIC ModuleType with ports')


def _seeded_transceiver_module_type():
    """Return any transceiver ModuleType the bundled catalog seeds."""
    mt = ModuleType.objects.filter(profile__name='Network Transceiver').first()
    if mt is None:
        raise AssertionError('bootstrap seeded no Network Transceiver ModuleType')
    return mt


class BootstrapGenerationReadinessTestCase(TestCase):
    """Bootstrap alone must be enough to generate against the bundled catalog."""

    @classmethod
    def setUpTestData(cls):
        # The documented bootstrap, and nothing else.  Deliberately does NOT
        # call populate_transceiver_bays -- that is the hidden manual step #626
        # exists to remove.
        call_command('load_diet_reference_data', stdout=StringIO(), verbosity=0)

        cls.switch_dt = DeviceType.objects.get(slug='celestica-ds5000')
        cls.switch_ext = DeviceTypeExtension.objects.get(device_type=cls.switch_dt)
        cls.breakout = BreakoutOption.objects.get(breakout_id='4x200g')
        cls.nic_mt = _seeded_nic_module_type()
        cls.xcvr_mt = _seeded_transceiver_module_type()

        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=Manufacturer.objects.get_or_create(
                name='Generic', defaults={'slug': 'generic'})[0],
            model='DIET-626 Server',
            defaults={'slug': 'diet-626-server', 'u_height': 2},
        )

    def _build_plan(self, *, name='DIET-626 Bootstrap Plan', with_transceivers=True):
        """A minimal plan built entirely from bundled-catalog reference data."""
        plan = TopologyPlan.objects.create(
            name=name, status=TopologyPlanStatusChoices.DRAFT,
        )
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='fe-leaf',
            fabric_name='frontend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.switch_ext,
            override_quantity=1,
        )
        zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-8',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
            transceiver_module_type=self.xcvr_mt if with_transceivers else None,
        )
        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-fe',
            category=ServerClassCategoryChoices.GPU,
            quantity=2,
            server_device_type=self.server_dt,
        )
        nic = PlanServerNIC.objects.create(
            server_class=server_class, nic_id='nic-fe', module_type=self.nic_mt,
        )
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe-001',
            nic=nic,
            port_index=0,
            target_zone=zone,
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200,
            port_type='data',
            transceiver_module_type=self.xcvr_mt if with_transceivers else None,
        )
        return plan

    # -- the two bays bootstrap must provide -------------------------------

    def test_bootstrap_populates_switch_bays(self):
        """Seeded switch DeviceTypes must have one bay per interface template."""
        it_count = InterfaceTemplate.objects.filter(device_type=self.switch_dt).count()
        mbt_count = ModuleBayTemplate.objects.filter(device_type=self.switch_dt).count()
        self.assertGreater(it_count, 0, 'fixture: seeded switch must have ports')
        self.assertEqual(
            mbt_count, it_count,
            'bootstrap must leave one ModuleBayTemplate per InterfaceTemplate '
            'on seeded switch DeviceTypes',
        )

    def test_bootstrap_populates_nic_cages(self):
        """Seeded NIC ModuleTypes must have one cage per port template."""
        it_count = InterfaceTemplate.objects.filter(module_type=self.nic_mt).count()
        mbt_count = ModuleBayTemplate.objects.filter(module_type=self.nic_mt).count()
        self.assertGreater(it_count, 0, 'fixture: seeded NIC must have ports')
        self.assertEqual(
            mbt_count, it_count,
            'bootstrap must leave one cage ModuleBayTemplate per port on '
            'seeded NIC ModuleTypes',
        )

    # -- the behaviour those bays exist for --------------------------------

    def test_preflight_ready_after_bootstrap_only(self):
        """#626 core: preflight must pass with no manual command in between."""
        plan = self._build_plan()
        readiness = check_transceiver_bay_readiness(plan)
        self.assertTrue(
            readiness.has_transceiver_fks,
            'fixture must set transceiver intent, or preflight early-exits',
        )
        self.assertTrue(
            readiness.is_ready,
            f'bootstrap alone must satisfy preflight; missing={readiness.missing}',
        )

    def test_generation_succeeds_after_bootstrap_only(self):
        """End-to-end: bootstrap → build plan → generate, with no manual step."""
        plan = self._build_plan(name='DIET-626 Generate Plan')

        result = DeviceGenerator(plan=plan).generate_all()

        plan.refresh_from_db()
        state = plan.generation_state
        self.assertEqual(
            state.status, GenerationStatusChoices.GENERATED,
            f'generation must succeed after bootstrap alone; '
            f'mismatch_report={state.mismatch_report}',
        )
        self.assertGreater(result.device_count, 0, 'devices must be created')
        self.assertGreater(result.cable_count, 0, 'cables must be created')

    # -- contract guards ---------------------------------------------------

    def test_bootstrap_is_idempotent_for_bays(self):
        """Re-running bootstrap must not duplicate bays (documented as safe to repeat)."""
        before_switch = ModuleBayTemplate.objects.filter(device_type=self.switch_dt).count()
        before_nic = ModuleBayTemplate.objects.filter(module_type=self.nic_mt).count()

        call_command('load_diet_reference_data', stdout=StringIO(), verbosity=0)

        self.assertEqual(
            ModuleBayTemplate.objects.filter(device_type=self.switch_dt).count(),
            before_switch, 'repeat bootstrap must not duplicate switch bays',
        )
        self.assertEqual(
            ModuleBayTemplate.objects.filter(module_type=self.nic_mt).count(),
            before_nic, 'repeat bootstrap must not duplicate NIC cages',
        )

    def test_populate_command_remains_available_and_idempotent(self):
        """The standalone command stays usable for inventory bootstrap didn't seed."""
        before = ModuleBayTemplate.objects.count()
        call_command('populate_transceiver_bays', stdout=StringIO(), verbosity=0)
        self.assertEqual(
            ModuleBayTemplate.objects.count(), before,
            'running the standalone command after bootstrap must be a no-op',
        )


class IngestGenerationReadinessTestCase(TestCase):
    """#626: case ingest must ready the inventory the case itself introduces.

    A case file may create DeviceTypes and NIC ModuleTypes of its own, which the
    bundled catalog knows nothing about.  Bootstrap therefore cannot ready them,
    so ``apply_case`` owns it — for **both** the v1 and v2 branches, which return
    from different points in the function.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('load_diet_reference_data', stdout=StringIO(), verbosity=0)

    def _case_local_nic(self, model):
        """A NIC ModuleType that is NOT part of the bundled catalog."""
        mfr, _ = Manufacturer.objects.get_or_create(
            name='DIET-626 Vendor', defaults={'slug': 'diet-626-vendor'},
        )
        mt, _ = ModuleType.objects.get_or_create(manufacturer=mfr, model=model)
        for name in ('port0', 'port1'):
            InterfaceTemplate.objects.get_or_create(
                module_type=mt, name=name, defaults={'type': '400gbase-x-osfp'},
            )
        return mfr, mt

    def test_v2_ingest_populates_cages_for_case_local_nic(self):
        """v2 branch: apply_case must ready a NIC the case introduced."""
        from netbox_hedgehog.test_cases.ingest import apply_case

        mfr, mt = self._case_local_nic('DIET626-V2-NIC')
        self.assertEqual(
            ModuleBayTemplate.objects.filter(module_type=mt).count(), 0,
            'fixture: case-local NIC must start with no cages',
        )

        case = {
            'apiVersion': 'diet/v2',
            'kind': 'TopologyPlan',
            'metadata': {
                'case_id': 'diet626_v2_nic',
                'name': 'DIET-626 v2 NIC case',
                'version': 2,
                'managed_by': 'yaml',
            },
            'spec': {
                'plan': {'name': 'DIET-626 v2 NIC plan', 'status': 'draft'},
                'switch_classes': [],
                'server_classes': [{
                    'server_class_id': 'gpu',
                    'quantity': 1,
                    'server_device_type': self._server_dt_slug(),
                }],
                'server_nics': [{
                    'server_class': 'gpu',
                    'nic_id': 'nic-0',
                    'module_type': {'manufacturer': mfr.slug, 'model': mt.model},
                }],
                'server_connections': [],
            },
        }
        apply_case(case, clean=True)

        self.assertEqual(
            ModuleBayTemplate.objects.filter(module_type=mt).count(), 2,
            'v2 ingest must leave one cage per port on a case-introduced NIC',
        )

    def test_v1_ingest_populates_cages_for_case_local_nic(self):
        """v1 branch: the same guarantee, from the other return point."""
        from netbox_hedgehog.test_cases.ingest import apply_case

        mfr, mt = self._case_local_nic('DIET626-V1-NIC')
        self.assertEqual(
            ModuleBayTemplate.objects.filter(module_type=mt).count(), 0,
            'fixture: case-local NIC must start with no cages',
        )

        # v1 resolves references through case-local ids declared in
        # reference_data; v2 resolves by slug.  That asymmetry is exactly why
        # both branches need their own coverage.
        server_dt = DeviceType.objects.get(slug=self._server_dt_slug())
        case = {
            'meta': {
                'case_id': 'diet626_v1_nic',
                'name': 'DIET-626 v1 NIC case',
                'version': 1,
                'managed_by': 'yaml',
            },
            'reference_data': {
                'manufacturers': [
                    {'id': 'vendor', 'name': mfr.name, 'slug': mfr.slug},
                    {
                        'id': 'srv_mfr',
                        'name': server_dt.manufacturer.name,
                        'slug': server_dt.manufacturer.slug,
                    },
                ],
                'device_types': [{
                    'id': 'srv_dt',
                    'manufacturer': 'srv_mfr',
                    'model': server_dt.model,
                    'slug': server_dt.slug,
                }],
                'module_types': [{
                    'id': 'case_nic',
                    'manufacturer': 'vendor',
                    'model': mt.model,
                }],
            },
            'plan': {'name': 'DIET-626 v1 NIC plan', 'status': 'draft'},
            'switch_classes': [],
            'server_classes': [{
                'server_class_id': 'gpu',
                'quantity': 1,
                'server_device_type': 'srv_dt',
            }],
            'server_nics': [{
                'server_class': 'gpu',
                'nic_id': 'nic-0',
                'module_type': 'case_nic',
            }],
            'server_connections': [],
        }
        apply_case(case, clean=True, reference_mode='ensure')

        self.assertEqual(
            ModuleBayTemplate.objects.filter(module_type=mt).count(), 2,
            'v1 ingest must leave one cage per port on a case-introduced NIC',
        )

    @staticmethod
    def _server_dt_slug():
        dt = DeviceType.objects.filter(slug='gpu-server-fe').first()
        return dt.slug if dt else DeviceType.objects.first().slug


class BootstrapLeavesUnrelatedInventoryAloneTestCase(TestCase):
    """#626: readying our own catalog must not touch anyone else's inventory.

    ``populate_transceiver_bays`` is scoped to switch DeviceTypes carrying a
    DeviceTypeExtension, NIC ModuleTypes referenced by a PlanServerNIC, and NIC
    ModuleTypes the bundled catalog seeds — matched on (manufacturer slug,
    model).  Nothing else may gain ModuleBayTemplates.  This matters because the
    plugin writes into NetBox-owned dcim tables: an over-broad scope would
    silently modify inventory that has nothing to do with HNP.
    """

    def test_bootstrap_does_not_add_bays_to_foreign_inventory(self):
        foreign_mfr, _ = Manufacturer.objects.get_or_create(
            name='Unrelated Vendor', defaults={'slug': 'unrelated-vendor'},
        )
        # A ModuleType with ports, not in the bundled catalog and not referenced
        # by any PlanServerNIC.
        foreign_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=foreign_mfr, model='Unrelated-NIC-2P',
        )
        for name in ('port0', 'port1'):
            InterfaceTemplate.objects.get_or_create(
                module_type=foreign_mt, name=name, defaults={'type': '400gbase-x-osfp'},
            )
        # A DeviceType with ports but no DeviceTypeExtension (not an HNP switch).
        foreign_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=foreign_mfr, model='Unrelated-Switch',
            defaults={'slug': 'unrelated-switch', 'u_height': 1},
        )
        InterfaceTemplate.objects.get_or_create(
            device_type=foreign_dt, name='Eth1', defaults={'type': '400gbase-x-osfp'},
        )

        call_command('load_diet_reference_data', stdout=StringIO(), verbosity=0)

        self.assertEqual(
            ModuleBayTemplate.objects.filter(module_type=foreign_mt).count(), 0,
            'bootstrap must not add cages to a ModuleType outside the bundled '
            'catalog and unreferenced by any plan',
        )
        self.assertEqual(
            ModuleBayTemplate.objects.filter(device_type=foreign_dt).count(), 0,
            'bootstrap must not add bays to a DeviceType with no '
            'DeviceTypeExtension',
        )


class IngestDoesNotReadyForeignPlansTestCase(TestCase):
    """#626 review: ingest readiness must not reach another plan's inventory.

    ``_ensure_transceiver_bays`` originally delegated to the global
    ``populate_transceiver_bays`` scope, which selects *every*
    ``PlanServerNIC.module_type`` in the database.  Ingesting one case therefore
    added ModuleBayTemplates to NICs owned by unrelated plans — and those
    templates change what every future Device of that type instantiates, so the
    blast radius is real rather than cosmetic.  It also contradicted the
    lifecycle rule the fix is built on: whoever creates the inventory owns
    readying it, and a case owns only what it declares.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('load_diet_reference_data', stdout=StringIO(), verbosity=0)

    def _registered_switch(self, model, slug):
        """A DeviceType registered with HNP (has a DeviceTypeExtension) and ports."""
        mfr, _ = Manufacturer.objects.get_or_create(
            name='DIET-626 Foreign Vendor', defaults={'slug': 'diet-626-foreign'},
        )
        dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr, model=model, defaults={'slug': slug, 'u_height': 1},
        )
        for i in (1, 2, 3):
            InterfaceTemplate.objects.get_or_create(
                device_type=dt, name=f'E1/{i}', defaults={'type': '400gbase-x-osfp'},
            )
        DeviceTypeExtension.objects.get_or_create(
            device_type=dt,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'supported_breakouts': ['1x400g'],
                'native_speed': 400,
            },
        )
        return dt

    def _nic_module_type(self, model):
        mfr, _ = Manufacturer.objects.get_or_create(
            name='DIET-626 Foreign Vendor', defaults={'slug': 'diet-626-foreign'},
        )
        mt, _ = ModuleType.objects.get_or_create(manufacturer=mfr, model=model)
        for name in ('port0', 'port1'):
            InterfaceTemplate.objects.get_or_create(
                module_type=mt, name=name, defaults={'type': '400gbase-x-osfp'},
            )
        return mfr, mt

    def test_ingest_readies_only_the_case_inventory(self):
        from netbox_hedgehog.test_cases.ingest import apply_case

        server_dt = DeviceType.objects.get(slug='gpu-server-fe')

        # (1) A foreign plan whose NIC ModuleType has ports and no cages.
        foreign_mfr, foreign_mt = self._nic_module_type('DIET626-FOREIGN-NIC')
        foreign_plan = TopologyPlan.objects.create(name='DIET-626 Foreign Plan')
        foreign_sc = PlanServerClass.objects.create(
            plan=foreign_plan,
            server_class_id='foreign-gpu',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            server_device_type=server_dt,
        )
        PlanServerNIC.objects.create(
            server_class=foreign_sc, nic_id='foreign-nic', module_type=foreign_mt,
        )
        self.assertEqual(
            ModuleBayTemplate.objects.filter(module_type=foreign_mt).count(), 0,
            'fixture: the foreign NIC must start with no cages',
        )

        # (2) Ingest a case that brings its own NIC.
        case_mfr, case_mt = self._nic_module_type('DIET626-CASE-NIC')
        case = {
            'apiVersion': 'diet/v2',
            'kind': 'TopologyPlan',
            'metadata': {
                'case_id': 'diet626_scope',
                'name': 'DIET-626 scope case',
                'version': 2,
                'managed_by': 'yaml',
            },
            'spec': {
                'plan': {'name': 'DIET-626 scope plan', 'status': 'draft'},
                'switch_classes': [],
                'server_classes': [{
                    'server_class_id': 'gpu',
                    'quantity': 1,
                    'server_device_type': server_dt.slug,
                }],
                'server_nics': [{
                    'server_class': 'gpu',
                    'nic_id': 'nic-0',
                    'module_type': {
                        'manufacturer': case_mfr.slug, 'model': case_mt.model,
                    },
                }],
                'server_connections': [],
            },
        }
        apply_case(case, clean=True)

        # (3) The case NIC is readied; the foreign plan's NIC is untouched.
        self.assertEqual(
            ModuleBayTemplate.objects.filter(module_type=case_mt).count(), 2,
            'ingest must ready the NIC the case declared',
        )
        self.assertEqual(
            ModuleBayTemplate.objects.filter(module_type=foreign_mt).count(), 0,
            'ingest must NOT ready a NIC belonging to an unrelated plan',
        )


    def test_ingest_readies_only_the_case_switch_types(self):
        """plan_scope() switch selection must be inclusive AND exclusive.

        The prior global scope readied every DeviceType carrying a
        DeviceTypeExtension, so ingesting any case readied the entire registered
        switch catalog.  Asserting only the negative half would pass even if
        plan_scope() selected no switches at all, so the case-owned switch
        carries an explicit positive assertion.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case

        foreign_dt = self._registered_switch(
            'DIET626-FOREIGN-SW', 'diet626-foreign-sw',
        )
        case_dt = self._registered_switch('DIET626-CASE-SW', 'diet626-case-sw')

        # A foreign plan that owns the foreign switch.
        foreign_plan = TopologyPlan.objects.create(name='DIET-626 Foreign Switch Plan')
        PlanSwitchClass.objects.create(
            plan=foreign_plan,
            switch_class_id='foreign-leaf',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=DeviceTypeExtension.objects.get(device_type=foreign_dt),
        )

        for dt in (foreign_dt, case_dt):
            self.assertEqual(
                ModuleBayTemplate.objects.filter(device_type=dt).count(), 0,
                f'fixture: {dt.model} must start with no bays',
            )

        case = {
            'apiVersion': 'diet/v2',
            'kind': 'TopologyPlan',
            'metadata': {
                'case_id': 'diet626_sw_scope',
                'name': 'DIET-626 switch scope case',
                'version': 2,
                'managed_by': 'yaml',
            },
            'spec': {
                'plan': {'name': 'DIET-626 switch scope plan', 'status': 'draft'},
                'switch_classes': [{
                    'switch_class_id': 'case-leaf',
                    'fabric_name': 'backend',
                    'fabric_class': 'managed',
                    'hedgehog_role': 'server-leaf',
                    'device_type': case_dt.slug,
                }],
                'server_classes': [],
                'server_connections': [],
            },
        }
        apply_case(case, clean=True)

        self.assertEqual(
            ModuleBayTemplate.objects.filter(device_type=case_dt).count(), 3,
            'ingest must ready the switch DeviceType the case declared '
            '(one bay per interface template)',
        )
        self.assertEqual(
            ModuleBayTemplate.objects.filter(device_type=foreign_dt).count(), 0,
            'ingest must NOT ready a switch DeviceType owned by an unrelated plan',
        )
