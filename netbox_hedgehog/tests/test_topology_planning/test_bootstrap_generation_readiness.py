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
