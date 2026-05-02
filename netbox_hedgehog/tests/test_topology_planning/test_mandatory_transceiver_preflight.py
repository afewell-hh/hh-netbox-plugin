"""
RED tests for #475 — simplified transceiver UX: preflight behavior.

Replaces DIET-466 mandatory-transceiver preflight tests with tests that
pin the approved target behavior from #474 §9.4 (PF1–PF5).

Target behavior (not yet implemented):
  - All-null transceiver plan → is_ready=True, has_transceiver_fks=False, missing=[]
  - Empty plan → is_ready=True, has_transceiver_fks=False, missing=[]
  - missing[] never contains 'missing_transceiver_connections' or
    'missing_transceiver_zones' entity types (Phase 0 removed)
  - Phase 2 bay checks still fire when FKs are set but bays missing (PF3)
  - Generate view / command no longer blocked by null transceiver (view-level)

All tests are RED until GREEN removes the Phase 0 block from
check_transceiver_bay_readiness() (preflight.py lines 90–118) and removes
the corresponding 'missing_transceiver_*' branches from user_message() and
cli_message().
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import DeviceType, InterfaceTemplate, Manufacturer, ModuleBayTemplate

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricClassChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
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
from netbox_hedgehog.tests.test_topology_planning import (
    get_test_nic_module_type,
    get_test_transceiver_module_type,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_pf_fixtures(cls):
    """Shared switch/server device types and extension for preflight tests."""
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name='MxtPF2-Vendor', defaults={'slug': 'mxtpf2-vendor'}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MxtPF2-SRV', defaults={'slug': 'mxtpf2-srv'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MxtPF2-SW', defaults={'slug': 'mxtpf2-sw'}
    )
    for n in range(1, 5):
        InterfaceTemplate.objects.get_or_create(
            device_type=cls.switch_dt, name=f'E1/{n}',
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
        breakout_id='1x200g-mxtpf2',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    cls.nic_mt = get_test_nic_module_type()

    cls.superuser, _ = User.objects.get_or_create(
        username='mxtpf2-admin',
        defaults={'is_staff': True, 'is_superuser': True},
    )
    cls.superuser.set_password('pass')
    cls.superuser.save()


def _build_null_xcvr_plan(suffix=''):
    """
    Build a plan where all connections and zones have null transceiver_module_type.
    Uses Model.objects.create() to bypass model clean() which currently blocks null FKs.
    """
    mfr, _ = Manufacturer.objects.get_or_create(
        name='MxtPF2-Vendor', defaults={'slug': 'mxtpf2-vendor'}
    )
    server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='MxtPF2-SRV', defaults={'slug': 'mxtpf2-srv'}
    )
    switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='MxtPF2-SW', defaults={'slug': 'mxtpf2-sw'}
    )
    device_ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=switch_dt,
        defaults={
            'native_speed': 200, 'uplink_ports': 0,
            'supported_breakouts': ['1x200g'], 'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    breakout, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x200g-mxtpf2',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    plan = TopologyPlan.objects.create(
        name=f'MxtPF2-NullPlan-{suffix}',
        status=TopologyPlanStatusChoices.DRAFT,
    )
    sc = PlanServerClass.objects.create(
        plan=plan, server_class_id='gpu',
        server_device_type=server_dt, quantity=2,
    )
    sw = PlanSwitchClass.objects.create(
        plan=plan, switch_class_id='fe-leaf',
        fabric_name=FabricTypeChoices.FRONTEND,
        fabric_class=FabricClassChoices.MANAGED,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=device_ext,
        uplink_ports_per_switch=0, mclag_pair=False,
        override_quantity=2, redundancy_type='eslag',
    )
    zone = SwitchPortZone.objects.create(
        switch_class=sw, zone_name='server-downlinks',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-4',
        breakout_option=breakout,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        transceiver_module_type=None,
    )
    nic = PlanServerNIC.objects.create(
        server_class=sc, nic_id='nic-fe', module_type=get_test_nic_module_type(),
    )
    PlanServerConnection.objects.create(
        server_class=sc, connection_id='fe',
        nic=nic, port_index=0, ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        target_zone=zone, speed=200, port_type='data',
        transceiver_module_type=None,
    )
    return plan


def _check(plan):
    from netbox_hedgehog.services.preflight import check_transceiver_bay_readiness
    return check_transceiver_bay_readiness(plan)


# ---------------------------------------------------------------------------
# PF1 — all-null transceiver plan → is_ready=True
# ---------------------------------------------------------------------------

class NullTransceiverPreflightPassTestCase(TestCase):
    """
    PF1: check_transceiver_bay_readiness() for a plan with all null transceiver
    FKs must return is_ready=True, has_transceiver_fks=False, missing=[].

    RED: currently Phase 0 sets is_ready=False when any FK is null.
    After GREEN (Phase 0 removed): null-transceiver plans pass preflight.
    """

    def test_pf1_all_null_plan_is_ready(self):
        """PF1: all-null transceiver plan → is_ready=True."""
        plan = _build_null_xcvr_plan('pf1')
        result = _check(plan)
        self.assertTrue(
            result.is_ready,
            'PF1: check_transceiver_bay_readiness() must return is_ready=True '
            'for plan with all-null transceiver FKs (Phase 0 removed)',
        )

    def test_pf1_all_null_has_no_transceiver_fks(self):
        """PF1: all-null plan → has_transceiver_fks=False."""
        plan = _build_null_xcvr_plan('pf1b')
        result = _check(plan)
        self.assertFalse(
            result.has_transceiver_fks,
            'PF1: has_transceiver_fks must be False when no FKs are set',
        )

    def test_pf1_all_null_missing_is_empty(self):
        """PF1: all-null plan → missing=[]."""
        plan = _build_null_xcvr_plan('pf1c')
        result = _check(plan)
        self.assertEqual(
            result.missing, [],
            f'PF1: missing must be empty for all-null plan; got: {result.missing}',
        )


# ---------------------------------------------------------------------------
# PF4 — empty plan (no connections, no zones) → is_ready=True
# ---------------------------------------------------------------------------

class EmptyPlanPreflightTestCase(TestCase):
    """
    PF4: Empty plan (no connections, no zones) → is_ready=True.
    The Phase 0 removal must not create false positives for empty plans.
    This test was already GREEN under DIET-466 (zero null connections = ok),
    but is included here as a regression guard for the new behavior.
    """

    def test_pf4_empty_plan_is_ready(self):
        """PF4: plan with no connections and no zones → is_ready=True."""
        plan = TopologyPlan.objects.create(
            name='MxtPF2-EmptyPlan', status=TopologyPlanStatusChoices.DRAFT,
        )
        result = _check(plan)
        self.assertTrue(
            result.is_ready,
            'PF4: empty plan must be ready — no false positive from preflight',
        )
        self.assertFalse(result.has_transceiver_fks)
        self.assertEqual(result.missing, [])


# ---------------------------------------------------------------------------
# PF5 — missing[] never contains Phase 0 entity types
# ---------------------------------------------------------------------------

class PhaseZeroEntityTypeRemovedTestCase(TestCase):
    """
    PF5: missing[] must never contain entity_type='missing_transceiver_connections'
    or entity_type='missing_transceiver_zones'. Phase 0 is removed; these
    entity types no longer exist.

    RED: currently Phase 0 adds these entity types when any FK is null.
    After GREEN: these entity types are never emitted.
    """

    def test_pf5_missing_transceiver_connections_never_appears(self):
        """PF5a: missing_transceiver_connections entity type must never appear."""
        plan = _build_null_xcvr_plan('pf5a')
        result = _check(plan)
        entity_types = [e['entity_type'] for e in result.missing]
        self.assertNotIn(
            'missing_transceiver_connections', entity_types,
            f'PF5a: Phase 0 entity type must not appear after removal; '
            f'got entity_types: {entity_types}',
        )

    def test_pf5_missing_transceiver_zones_never_appears(self):
        """PF5b: missing_transceiver_zones entity type must never appear."""
        plan = _build_null_xcvr_plan('pf5b')
        result = _check(plan)
        entity_types = [e['entity_type'] for e in result.missing]
        self.assertNotIn(
            'missing_transceiver_zones', entity_types,
            f'PF5b: Phase 0 entity type must not appear after removal; '
            f'got entity_types: {entity_types}',
        )


# ---------------------------------------------------------------------------
# PF2 / PF3 — Phase 2 bay checks: preserved behavior
# ---------------------------------------------------------------------------

class BayPresencePreflightPreservedTestCase(TestCase):
    """
    PF2: Some FKs set, bays present → is_ready=True.
    PF3: Some FKs set, bays missing → is_ready=False, missing contains bay entries.

    These test Phase 2 bay checks which are PRESERVED after Phase 0 removal.
    These should be GREEN before and after GREEN implementation (regression guards).
    """

    @classmethod
    def setUpTestData(cls):
        _make_pf_fixtures(cls)
        cls.xcvr_mt = get_test_transceiver_module_type()
        # Ensure the NIC has a ModuleBayTemplate for PF2 (bay present)
        ModuleBayTemplate.objects.get_or_create(
            module_type=cls.nic_mt, name='cage-0',
        )
        # Switch bays (must have ≥ interface template count)
        for n in range(1, 5):
            ModuleBayTemplate.objects.get_or_create(
                device_type=cls.switch_dt, name=f'E1/{n}',
            )

    def _build_plan_with_xcvr(self, suffix):
        plan = TopologyPlan.objects.create(
            name=f'MxtPF2-XcvrPlan-{suffix}',
            status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu',
            server_device_type=self.server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        zone = SwitchPortZone.objects.create(
            switch_class=sw, zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-4',
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
            transceiver_module_type=self.xcvr_mt,
        )
        return plan

    def test_pf2_fks_set_bays_present_is_ready(self):
        """PF2: FKs set and bays present → is_ready=True."""
        plan = self._build_plan_with_xcvr('pf2')
        result = _check(plan)
        self.assertTrue(
            result.is_ready,
            f'PF2: FKs set + bays present must be ready; missing: {result.missing}',
        )
        self.assertTrue(result.has_transceiver_fks)
        self.assertEqual(result.missing, [])

    def test_pf3_fks_set_bays_missing_not_ready(self):
        """PF3: FKs set but bays missing → is_ready=False with bay entity in missing."""
        # Build a plan using a different switch_dt that has NO ModuleBayTemplates
        mfr, _ = Manufacturer.objects.get_or_create(
            name='MxtPF2-NoBay-Vendor', defaults={'slug': 'mxtpf2-nobay-vendor'}
        )
        nobay_sw_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr, model='MxtPF2-NoBay-SW', defaults={'slug': 'mxtpf2-nobay-sw'}
        )
        # Add InterfaceTemplates but NO ModuleBayTemplates
        for n in range(1, 3):
            InterfaceTemplate.objects.get_or_create(
                device_type=nobay_sw_dt, name=f'E1/{n}',
                defaults={'type': '200gbase-x-qsfp112'},
            )
        nobay_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=nobay_sw_dt,
            defaults={
                'native_speed': 200, 'uplink_ports': 0,
                'supported_breakouts': ['1x200g'], 'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
            },
        )
        plan = TopologyPlan.objects.create(
            name='MxtPF2-NoBayPlan', status=TopologyPlanStatusChoices.DRAFT,
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu',
            server_device_type=self.server_dt, quantity=1,
        )
        sw = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-nobay',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=nobay_ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=1, redundancy_type='eslag',
        )
        zone = SwitchPortZone.objects.create(
            switch_class=sw, zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-2',
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
            transceiver_module_type=self.xcvr_mt,
        )

        result = _check(plan)
        self.assertFalse(
            result.is_ready,
            'PF3: FKs set + bays missing → is_ready must be False',
        )
        entity_types = [e['entity_type'] for e in result.missing]
        has_bay_entity = any(
            et in ('switch_device_type', 'nic_module_type') for et in entity_types
        )
        self.assertTrue(
            has_bay_entity,
            f'PF3: missing must contain switch_device_type or nic_module_type entry; '
            f'got: {entity_types}',
        )


# ---------------------------------------------------------------------------
# View-level — generate view no longer blocked for null-transceiver plans
# ---------------------------------------------------------------------------

class NullTransceiverGenerateViewTestCase(TestCase):
    """
    Generate view (POST /topology-plans/<pk>/generate/) for a null-transceiver plan
    must proceed to generation (not return early with preflight error).

    After GREEN: view reaches the generator and the plan reaches GENERATED status.
    Currently: view returns 302 but plan stays DRAFT / never reaches GENERATED
    because Phase 0 preflight blocks before the generator is called.

    RED: POST generate for null-transceiver plan → plan status = GENERATED.
    """

    @classmethod
    def setUpTestData(cls):
        _make_pf_fixtures(cls)
        cls.superuser, _ = User.objects.get_or_create(
            username='mxtpf2-gen-admin',
            defaults={'is_staff': True, 'is_superuser': True},
        )
        cls.superuser.set_password('pass')
        cls.superuser.save()

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_generate_view_proceeds_for_null_transceiver_plan(self):
        """
        POST /generate/ for all-null-transceiver plan must NOT be blocked by preflight.

        After GREEN: plan reaches GENERATED status (null FKs → no modules placed,
        no mismatches, sweep passes).

        Currently: Phase 0 preflight blocks and the plan never gets a GenerationState
        with status=GENERATED.
        """
        from netbox_hedgehog.models.topology_planning import GenerationState
        from netbox_hedgehog.choices import GenerationStatusChoices

        plan = _build_null_xcvr_plan('view-gen')
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', kwargs={'pk': plan.pk})
        self.client.post(url, follow=True)

        gs = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(
            gs,
            'Generate view for null-transceiver plan must create GenerationState '
            '(currently blocked by Phase 0 preflight before generator runs)',
        )
        if gs:
            self.assertEqual(
                gs.status, GenerationStatusChoices.GENERATED,
                f'After GREEN: null-transceiver plan must reach GENERATED status; '
                f'got: {gs.status}',
            )

    def test_generate_page_no_transceiver_missing_alert_for_null_plan(self):
        """
        GET generate page for null-transceiver plan must not show
        'transceiver intent missing' or 'required' alert text.

        After GREEN: has_transceiver_fks=False → no advisory banner rendered.
        Currently: Phase 0 sets is_ready=False → banner appears with
        'transceiver' alert text.
        """
        plan = _build_null_xcvr_plan('view-get')
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', kwargs={'pk': plan.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn(
            'Transceiver Bay Prerequisite Missing',
            content,
            'GET generate page for null-transceiver plan must not show '
            'transceiver-required alert after Phase 0 removal',
        )
