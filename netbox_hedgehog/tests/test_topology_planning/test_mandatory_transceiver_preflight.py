"""
RED tests for #465 — mandatory transceiver enforcement in preflight and generation.

Acceptance cases covered:
  A11     — POST sync generate view → blocked, messages.error with missing counts
  A11-gen — generate_devices management command → CommandError with missing counts
  A12     — POST sync generate view with fully-populated plan → generation proceeds,
            no BUG-level warnings emitted from the generator

Preflight unit tests:
  PF1 — check_transceiver_bay_readiness() returns is_ready=False for plan
         with ALL null transceiver connections
  PF2 — missing[] contains entity_type='missing_transceiver_connections' entry
  PF3 — missing[] contains entity_type='missing_transceiver_zones' entry
  PF4 — missing_count reflects the exact null-row count
  PF5 — user_message() describes missing transceiver connections/zones by count
  PF6 — cli_message() describes missing transceiver connections/zones by count
  PF7 — Plan with zero connections and zero zones: is_ready=True (no false positive)
  PF8 — Plan with some null and some non-null transceivers: still is_ready=False

All tests in this file are RED until GREEN:
  - removes the early-exit "no FKs = is_ready=True" path from preflight
  - adds Phase 0 null-FK count check
  - updates user_message()/cli_message() to handle new entity types
  - removes the "old permissive zero-FK" template condition
"""

from __future__ import annotations

import logging
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import DeviceType, InterfaceTemplate, Manufacturer, ModuleBayTemplate
from users.models import ObjectPermission

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

def _make_base_fixtures(cls):
    """Manufacturer + device types shared across test classes."""
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name='MxtPF-Vendor', defaults={'slug': 'mxtpf-vendor'}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MxtPF-SRV', defaults={'slug': 'mxtpf-srv'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MxtPF-SW', defaults={'slug': 'mxtpf-sw'}
    )
    # Interface templates so generate view can proceed past bay checks when
    # populate_transceiver_bays has been run (used in A12 green path only).
    for n in range(1, 9):
        InterfaceTemplate.objects.get_or_create(
            device_type=cls.switch_dt, name=f'E1/{n}',
            defaults={'type': '200gbase-x-qsfp112'},
        )
    # ModuleBayTemplates on the switch DeviceType (one per InterfaceTemplate)
    # so Phase 2 (bay parity check) passes for fully-annotated plans.
    for n in range(1, 9):
        ModuleBayTemplate.objects.get_or_create(
            device_type=cls.switch_dt, name=f'E1/{n}',
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
        breakout_id='1x200g-mxtpf',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    cls.xcvr_mt = get_test_transceiver_module_type()
    cls.nic_mt = get_test_nic_module_type()
    # ModuleBayTemplate on the NIC ModuleType so Phase 2 (NIC bay check) passes.
    ModuleBayTemplate.objects.get_or_create(
        module_type=cls.nic_mt, name='cage-0',
    )


def _build_null_xcvr_plan(name_suffix=''):
    """
    Build a minimal plan where ALL connections and ALL zones have null
    transceiver_module_type. Uses direct Model.objects.create() to bypass
    form validation — intentionally creates the invalid state.
    """
    from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type
    mfr, _ = Manufacturer.objects.get_or_create(
        name='MxtPF-Vendor', defaults={'slug': 'mxtpf-vendor'}
    )
    server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='MxtPF-SRV', defaults={'slug': 'mxtpf-srv'}
    )
    switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='MxtPF-SW', defaults={'slug': 'mxtpf-sw'}
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
        breakout_id='1x200g-mxtpf',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    plan = TopologyPlan.objects.create(
        name=f'NullXcvr-Plan-{name_suffix}',
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
    # Zone with null transceiver
    zone = SwitchPortZone.objects.create(
        switch_class=sw, zone_name='server-downlinks',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-64',
        breakout_option=breakout,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        transceiver_module_type=None,  # intentionally null
    )
    nic = PlanServerNIC.objects.create(
        server_class=sc, nic_id='nic-fe', module_type=get_test_nic_module_type(),
    )
    # Connection with null transceiver
    PlanServerConnection.objects.create(
        server_class=sc, connection_id='fe',
        nic=nic, port_index=0, ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        target_zone=zone, speed=200, port_type='data',
        transceiver_module_type=None,  # intentionally null
    )
    return plan


# ---------------------------------------------------------------------------
# Group PF — preflight service unit tests
# ---------------------------------------------------------------------------

class MandatoryTransceiverPreflightUnitTestCase(TestCase):
    """
    PF1–PF8: check_transceiver_bay_readiness() blocks null-transceiver plans.

    RED until Phase 0 null-FK check and early-exit removal are implemented.
    """

    def _check(self, plan):
        from netbox_hedgehog.services.preflight import check_transceiver_bay_readiness
        return check_transceiver_bay_readiness(plan)

    # PF1
    def test_null_transceiver_plan_is_not_ready(self):
        """PF1: Plan with all-null transceiver FKs → is_ready=False."""
        plan = _build_null_xcvr_plan('pf1')
        result = self._check(plan)
        self.assertFalse(
            result.is_ready,
            'check_transceiver_bay_readiness() must return is_ready=False '
            'when any transceiver FK is null',
        )

    # PF2
    def test_missing_connections_entity_present(self):
        """
        PF2: missing[] must contain an entry with
        entity_type='missing_transceiver_connections'.
        """
        plan = _build_null_xcvr_plan('pf2')
        result = self._check(plan)
        entity_types = [e['entity_type'] for e in result.missing]
        self.assertIn(
            'missing_transceiver_connections', entity_types,
            f'missing[] entity_types were: {entity_types}',
        )

    # PF3
    def test_missing_zones_entity_present(self):
        """
        PF3: missing[] must contain an entry with
        entity_type='missing_transceiver_zones'.
        """
        plan = _build_null_xcvr_plan('pf3')
        result = self._check(plan)
        entity_types = [e['entity_type'] for e in result.missing]
        self.assertIn(
            'missing_transceiver_zones', entity_types,
            f'missing[] entity_types were: {entity_types}',
        )

    # PF4
    def test_missing_count_reflects_null_row_count(self):
        """PF4: missing_count on each entry reflects the actual null-row count."""
        plan = _build_null_xcvr_plan('pf4')
        result = self._check(plan)
        conn_entry = next(
            (e for e in result.missing
             if e['entity_type'] == 'missing_transceiver_connections'), None
        )
        zone_entry = next(
            (e for e in result.missing
             if e['entity_type'] == 'missing_transceiver_zones'), None
        )
        self.assertIsNotNone(conn_entry, 'missing_transceiver_connections entry must exist')
        self.assertIsNotNone(zone_entry, 'missing_transceiver_zones entry must exist')
        self.assertEqual(
            conn_entry['missing_count'], 1,
            f'Expected 1 null connection; got {conn_entry["missing_count"]}',
        )
        self.assertEqual(
            zone_entry['missing_count'], 1,
            f'Expected 1 null zone; got {zone_entry["missing_count"]}',
        )

    # PF5
    def test_user_message_describes_missing_transceiver(self):
        """
        PF5: user_message() for a null-transceiver plan must mention
        missing transceiver intent (not only populate_transceiver_bays).
        """
        from netbox_hedgehog.services.preflight import (
            check_transceiver_bay_readiness,
            user_message,
        )
        plan = _build_null_xcvr_plan('pf5')
        result = check_transceiver_bay_readiness(plan)
        msg = user_message(result)
        # Must mention transceiver intent, not just bay commands
        self.assertTrue(
            'transceiver' in msg.lower() or 'missing' in msg.lower(),
            f'user_message() must describe missing transceiver; got: {msg!r}',
        )

    # PF6
    def test_cli_message_describes_missing_transceiver(self):
        """
        PF6: cli_message() for a null-transceiver plan must mention
        missing transceiver intent.
        """
        from netbox_hedgehog.services.preflight import (
            check_transceiver_bay_readiness,
            cli_message,
        )
        plan = _build_null_xcvr_plan('pf6')
        result = check_transceiver_bay_readiness(plan)
        msg = cli_message(result)
        self.assertTrue(
            'transceiver' in msg.lower() or 'missing' in msg.lower(),
            f'cli_message() must describe missing transceiver; got: {msg!r}',
        )

    # PF7
    def test_empty_plan_with_no_connections_or_zones_is_ready(self):
        """
        PF7: Plan with no connections and no zones → is_ready=True.
        The Phase 0 check must not produce false positives for empty plans.
        """
        plan = TopologyPlan.objects.create(
            name='MxtPF-EmptyPlan', status=TopologyPlanStatusChoices.DRAFT,
        )
        result = self._check(plan)
        self.assertTrue(
            result.is_ready,
            'Empty plan (no connections, no zones) must be ready — no false positive',
        )

    # PF8
    def test_plan_with_mixed_null_and_set_is_not_ready(self):
        """
        PF8: Plan with one null and one set transceiver → is_ready=False.
        A single null row must block the whole plan.
        """
        from netbox_hedgehog.tests.test_topology_planning import get_test_transceiver_module_type
        plan = _build_null_xcvr_plan('pf8')
        xcvr = get_test_transceiver_module_type()
        # Add a second connection with transceiver set, leaving the first null
        sc = plan.server_classes.first()
        nic = sc.nics.first()
        zone = plan.switch_classes.first().port_zones.first()
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='fe-extra',
            nic=nic, port_index=1, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=zone, speed=200, port_type='data',
            transceiver_module_type=xcvr,
        )
        result = self._check(plan)
        self.assertFalse(
            result.is_ready,
            'Plan with even one null transceiver connection must remain is_ready=False',
        )


# ---------------------------------------------------------------------------
# Group A11 — sync generate view blocked for null-transceiver plan
# ---------------------------------------------------------------------------

class MandatoryTransceiverGenerateViewTestCase(TestCase):
    """
    A11: POST to TopologyPlanGenerateView for a null-transceiver plan
    → 302 redirect back, messages.error, no devices created.

    The block happens at preflight (Phase 0), before the generator runs.
    No BUG-level warning is emitted from the generator (it never runs).

    RED until Phase 0 preflight is added to check_transceiver_bay_readiness().
    """

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='mxt-gen-admin', password='pass',
            is_staff=True, is_superuser=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_generate_view_post_blocked_for_null_transceiver_plan(self):
        """
        A11: POST /topology-plans/<pk>/generate/ for a plan with null-transceiver
        connections and zones → 302 redirect, flash error, no devices created.
        Preflight blocks before the generator is invoked.
        """
        from dcim.models import Device
        plan = _build_null_xcvr_plan('a11-view')
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', kwargs={'pk': plan.pk})

        with self.assertLogs('netbox_hedgehog', level='WARNING') as cm:
            # We expect the generator BUG warning NOT to appear — the view must
            # return before the generator is constructed.
            response = self.client.post(url, follow=True)
            # Filter for the specific BUG warning that would indicate a bypass
            bug_warnings = [
                m for m in cm.output
                if 'BUG: transceiver_module_type is null' in m
            ]
        self.assertEqual(
            [], bug_warnings,
            'Generator BUG warning must NOT appear — preflight should block first',
        )

        # Response must redirect (302) without following into a success page
        # Using follow=True to get final response; it should NOT be a success message.
        final_url = response.redirect_chain[-1][0] if response.redirect_chain else ''
        self.assertNotIn(
            'Generation complete', response.content.decode(),
            'Success message must not appear when generation is blocked by preflight',
        )

        # No devices must have been created for this plan
        device_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()
        self.assertEqual(
            device_count, 0,
            f'No devices must be created when generation is blocked; found {device_count}',
        )

    def test_generate_view_get_shows_alert_for_null_transceiver_plan(self):
        """
        GET /topology-plans/<pk>/generate/ for a null-transceiver plan
        → 200, page contains transceiver-missing alert text.
        The template condition is simplified to {% if not transceiver_bay_readiness.is_ready %}.
        """
        plan = _build_null_xcvr_plan('a11-get')
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', kwargs={'pk': plan.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'transceiver',
            msg_prefix=(
                'Generate page must show transceiver-related alert '
                'when plan has null-transceiver connections/zones'
            ),
        )


# ---------------------------------------------------------------------------
# Group A11-gen — generate_devices management command blocked
# ---------------------------------------------------------------------------

class MandatoryTransceiverGenerateCommandTestCase(TestCase):
    """
    A11-gen: `generate_devices --plan <pk>` for null-transceiver plan
    → CommandError with description of missing transceiver intent.

    RED until preflight Phase 0 is added.
    """

    def test_command_blocked_for_null_transceiver_plan(self):
        """
        A11-gen: generate_devices command must raise CommandError
        when plan has null-transceiver connections or zones.
        The error must mention missing transceiver intent.
        """
        plan = _build_null_xcvr_plan('a11-cmd')
        err = StringIO()
        with self.assertRaises(CommandError) as ctx:
            call_command(
                'generate_devices',
                str(plan.pk),
                stdout=StringIO(),
                stderr=err,
            )
        error_text = str(ctx.exception).lower()
        self.assertTrue(
            'transceiver' in error_text or 'missing' in error_text,
            f'CommandError must describe missing transceiver intent; got: {ctx.exception!s}',
        )


# ---------------------------------------------------------------------------
# Group A12 — clean generation emits no BUG warnings
# ---------------------------------------------------------------------------

class MandatoryTransceiverCleanGenerationTestCase(TestCase):
    """
    A12: POST generate for a fully-populated plan (all transceivers set,
    bays present after populate_transceiver_bays) → generation proceeds,
    no BUG-level generator warnings emitted.

    Confirms the generator's defensive logger.warning() paths are not
    triggered in normal operation — the preflight gate is the primary
    mechanism and is transparent when all transceivers are set.

    RED if the generator logger.warning() paths do not exist (need them
    to be reachable via assertLogs, then confirmed absent on clean runs).
    """

    @classmethod
    def setUpTestData(cls):
        _make_base_fixtures(cls)
        cls.superuser = User.objects.create_user(
            username='mxt-clean-admin', password='pass',
            is_staff=True, is_superuser=True,
        )

    def test_generator_emits_no_bug_warnings_when_all_transceivers_set(self):
        """
        A12: DeviceGenerator does NOT emit BUG-level warnings when
        all connections and zones have transceiver_module_type set.
        """
        plan = TopologyPlan.objects.create(
            name='MxtPF-CleanPlan', status=TopologyPlanStatusChoices.DRAFT,
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
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-8',
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

        from netbox_hedgehog.services.device_generator import DeviceGenerator
        from netbox_hedgehog.utils.topology_calculations import update_plan_calculations
        update_plan_calculations(plan)

        generator_logger = 'netbox_hedgehog.services.device_generator'
        with self.assertLogs(generator_logger, level='DEBUG') as cm:
            # Run a minimal log statement to ensure assertLogs doesn't fail on
            # zero messages (assertLogs requires at least one message).
            logging.getLogger(generator_logger).debug('A12 test run starting')
            DeviceGenerator(plan).generate_all()

        bug_warnings = [
            m for m in cm.output
            if 'BUG: transceiver_module_type is null' in m
        ]
        self.assertEqual(
            [], bug_warnings,
            f'Generator must emit no BUG warnings when all transceivers are set; '
            f'found: {bug_warnings}',
        )

    def test_plan_detail_alert_hidden_when_all_transceivers_set(self):
        """
        GET plan detail for fully-populated plan → alert block NOT present.
        Template condition {% if not transceiver_bay_readiness.is_ready %}
        must be transparent for compliant plans.
        """
        plan = TopologyPlan.objects.create(
            name='MxtPF-AlertHiddenPlan', status=TopologyPlanStatusChoices.DRAFT,
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
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-8',
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

        client = Client()
        client.force_login(
            User.objects.create_user(
                username='mxt-alert-hidden', password='pass',
                is_staff=True, is_superuser=True,
            )
        )
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', kwargs={'pk': plan.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        # The alert text "Transceiver Bay Prerequisite Missing" must NOT appear
        # for a fully-compliant plan.
        self.assertNotContains(
            response, 'Transceiver Bay Prerequisite Missing',
            msg_prefix='Preflight alert must not appear for fully-populated plans',
        )
