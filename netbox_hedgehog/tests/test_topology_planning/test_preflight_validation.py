"""
RED tests for DIET-348 Phase 3: Transceiver Bay Pre-flight Validation

Tests define the expected behavior for:
- TransceiverBayReadinessResult service (check_transceiver_bay_readiness)
- View integration (async and sync generate views)
- Management command (generate_devices) pre-flight check
- Plan detail page advisory banner

All tests are RED: the service module `netbox_hedgehog.services.preflight` does
not exist yet and the view/template/command integrations are not implemented.
Import errors are expected at collection time for the service tests; view and
command tests fail because the blocking behavior is absent.

Related: #348 (epic), #351 (research), #352 (arch), #353 (spec), #354 (this issue).
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from dcim.models import (
    DeviceType,
    InterfaceTemplate,
    Manufacturer,
    ModuleBayTemplate,
    ModuleType,
    Site,
)
from users.models import ObjectPermission
from django.contrib.contenttypes.models import ContentType

from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic, get_test_transceiver_module_type
from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    DeviceTypeExtension,
    BreakoutOption,
    SwitchPortZone,
    GenerationState,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    ServerClassCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    PortZoneTypeChoices,
    AllocationStrategyChoices,
)

# NOTE: netbox_hedgehog.services.preflight does not exist yet.
# Imports are deferred into each test method so that individual tests
# fail with ImportError (missing implementation) rather than the entire
# module failing at collection time.

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _get_or_create_switch_fixtures():
    """Return (manufacturer, switch_device_type, device_ext, breakout_option, site)."""
    mfr, _ = Manufacturer.objects.get_or_create(
        name='Preflight-Test-Vendor',
        defaults={'slug': 'preflight-test-vendor'},
    )
    dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr,
        model='PF-Switch-100',
        defaults={'slug': 'pf-switch-100'},
    )
    bo, _ = BreakoutOption.objects.get_or_create(
        breakout_id='4x200g-pf',
        defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200},
    )
    ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=dt,
        defaults={
            'native_speed': 800,
            'supported_breakouts': ['1x800g', '4x200g'],
            'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    site, _ = Site.objects.get_or_create(
        name='Preflight-Test-Site',
        defaults={'slug': 'preflight-test-site'},
    )
    return mfr, dt, ext, bo, site


def _get_or_create_server_fixtures():
    """Return server_device_type."""
    mfr, _ = Manufacturer.objects.get_or_create(
        name='Preflight-Test-Vendor',
        defaults={'slug': 'preflight-test-vendor'},
    )
    srv_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr,
        model='PF-Server-100',
        defaults={'slug': 'pf-server-100'},
    )
    return srv_dt


def _build_plan_with_transceiver_fk(with_bays=False):
    """
    Build a TopologyPlan with transceiver_module_type FK set on a zone.

    If with_bays=True, run ModuleBayTemplate creation to make bays present.
    Returns (plan, switch_dt) so the caller can add/remove bays as needed.
    """
    _mfr, switch_dt, ext, bo, _site = _get_or_create_switch_fixtures()
    srv_dt = _get_or_create_server_fixtures()

    plan = TopologyPlan.objects.create(
        name='Preflight-FK-Plan',
        customer_name='Preflight Test Customer',
        status=TopologyPlanStatusChoices.DRAFT,
    )

    server_class = PlanServerClass.objects.create(
        plan=plan,
        server_class_id='pf-gpu',
        category=ServerClassCategoryChoices.GPU,
        quantity=2,
        gpus_per_server=8,
        server_device_type=srv_dt,
    )

    switch_class = PlanSwitchClass.objects.create(
        plan=plan,
        switch_class_id='pf-fe-leaf',
        fabric=FabricTypeChoices.FRONTEND,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=ext,
        uplink_ports_per_switch=4,
        mclag_pair=False,
    )

    xcvr_mt = get_test_transceiver_module_type()

    zone = SwitchPortZone.objects.create(
        switch_class=switch_class,
        zone_name='pf-server-ports',
        zone_type=PortZoneTypeChoices.SERVER,
        port_spec='1-48',
        breakout_option=bo,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
        priority=100,
        transceiver_module_type=xcvr_mt,
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
        transceiver_module_type=xcvr_mt,
    )

    if with_bays:
        # Switch-side: create one InterfaceTemplate and matching ModuleBayTemplate.
        iface_t, _ = InterfaceTemplate.objects.get_or_create(
            device_type=switch_dt,
            name='Ethernet1/1',
            defaults={'type': '100gbase-x-qsfp28'},
        )
        ModuleBayTemplate.objects.get_or_create(
            device_type=switch_dt,
            name='bay-Ethernet1/1',
        )
        # NIC-side: ensure the NIC ModuleType has at least one ModuleBayTemplate
        # (simulates what populate_transceiver_bays does for NIC cage bays).
        from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type
        nic_mt = get_test_nic_module_type()
        ModuleBayTemplate.objects.get_or_create(
            module_type=nic_mt,
            name='cage-0',
            defaults={'label': 'Transceiver cage 0'},
        )

    return plan, switch_dt


def _build_plan_without_transceiver_fk():
    """Build a minimal TopologyPlan with NO transceiver_module_type FK set."""
    _mfr, _switch_dt, ext, bo, _site = _get_or_create_switch_fixtures()
    srv_dt = _get_or_create_server_fixtures()

    plan = TopologyPlan.objects.create(
        name='Preflight-NoFK-Plan',
        customer_name='Preflight Test Customer',
        status=TopologyPlanStatusChoices.DRAFT,
    )

    server_class = PlanServerClass.objects.create(
        plan=plan,
        server_class_id='pf-gpu-nofk',
        category=ServerClassCategoryChoices.GPU,
        quantity=2,
        gpus_per_server=8,
        server_device_type=srv_dt,
    )

    switch_class = PlanSwitchClass.objects.create(
        plan=plan,
        switch_class_id='pf-fe-leaf-nofk',
        fabric=FabricTypeChoices.FRONTEND,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=ext,
        uplink_ports_per_switch=4,
        mclag_pair=False,
    )

    zone = SwitchPortZone.objects.create(
        switch_class=switch_class,
        zone_name='pf-server-ports-nofk',
        zone_type=PortZoneTypeChoices.SERVER,
        port_spec='1-48',
        breakout_option=bo,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
        priority=100,
        # transceiver_module_type intentionally NOT set
    )

    nic = get_test_server_nic(server_class, nic_id='pf-nic-nofk')
    PlanServerConnection.objects.create(
        server_class=server_class,
        connection_id='PF-FE-NOFK',
        nic=nic,
        port_index=0,
        target_zone=zone,
        ports_per_connection=2,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        speed=200,
        port_type='data',
        # transceiver_module_type intentionally NOT set
    )

    return plan


# ---------------------------------------------------------------------------
# S1 — Service unit tests: TransceiverBayReadinessService
# ---------------------------------------------------------------------------

class TransceiverBayReadinessServiceTestCase(TestCase):
    """
    Direct unit tests for check_transceiver_bay_readiness().

    These test the service function independently of the view layer.
    RED: all fail because netbox_hedgehog.services.preflight does not exist.
    """

    def test_noop_when_no_transceiver_fks(self):
        """
        S5.5 — Plan with no transceiver FKs: fast early-exit, is_ready=True,
        has_transceiver_fks=False.
        """
        from netbox_hedgehog.services.preflight import (
            check_transceiver_bay_readiness,
            TransceiverBayReadinessResult,
        )
        plan = _build_plan_without_transceiver_fk()
        result = check_transceiver_bay_readiness(plan)

        self.assertIsInstance(result, TransceiverBayReadinessResult)
        self.assertTrue(result.is_ready)
        self.assertFalse(result.has_transceiver_fks)
        self.assertEqual(result.missing, [])

    def test_not_ready_when_fk_set_but_bays_absent(self):
        """
        S5.6 — Plan with transceiver FK set, no ModuleBayTemplates present:
        is_ready=False, missing list non-empty.
        """
        from netbox_hedgehog.services.preflight import check_transceiver_bay_readiness
        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=False)

        # Ensure no ModuleBayTemplates exist for the switch DeviceType
        ModuleBayTemplate.objects.filter(device_type=switch_dt).delete()

        result = check_transceiver_bay_readiness(plan)

        self.assertFalse(result.is_ready)
        self.assertTrue(result.has_transceiver_fks)
        self.assertGreater(len(result.missing), 0)

    def test_ready_when_fk_set_and_bays_present(self):
        """
        Plan with transceiver FK set AND matching ModuleBayTemplates: is_ready=True.
        """
        from netbox_hedgehog.services.preflight import check_transceiver_bay_readiness
        _mfr, switch_dt, ext, _bo, _site = _get_or_create_switch_fixtures()

        # Ensure at least one InterfaceTemplate exists and has a matching bay
        iface_t, _ = InterfaceTemplate.objects.get_or_create(
            device_type=switch_dt,
            name='Ethernet1/1-ready',
            defaults={'type': '100gbase-x-qsfp28'},
        )
        ModuleBayTemplate.objects.get_or_create(
            device_type=switch_dt,
            name='bay-Ethernet1/1-ready',
        )

        plan, _ = _build_plan_with_transceiver_fk(with_bays=True)
        result = check_transceiver_bay_readiness(plan)

        self.assertTrue(result.is_ready)
        self.assertTrue(result.has_transceiver_fks)
        self.assertEqual(result.missing, [])

    def test_missing_entry_has_required_keys(self):
        """
        missing list entries must contain entity_type, entity_id, entity_name,
        missing_count, and hint.
        """
        from netbox_hedgehog.services.preflight import check_transceiver_bay_readiness
        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=False)
        ModuleBayTemplate.objects.filter(device_type=switch_dt).delete()

        result = check_transceiver_bay_readiness(plan)

        for entry in result.missing:
            self.assertIn('entity_type', entry)
            self.assertIn('entity_id', entry)
            self.assertIn('entity_name', entry)
            self.assertIn('missing_count', entry)
            self.assertIn('hint', entry)

    def test_user_message_contains_expected_text(self):
        """user_message() must reference populate_transceiver_bays."""
        from netbox_hedgehog.services.preflight import (
            check_transceiver_bay_readiness,
            user_message,
        )
        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=False)
        ModuleBayTemplate.objects.filter(device_type=switch_dt).delete()

        result = check_transceiver_bay_readiness(plan)
        msg = user_message(result)

        self.assertIn('populate_transceiver_bays', msg)

    def test_cli_message_contains_expected_text(self):
        """cli_message() must reference populate_transceiver_bays and affected entities."""
        from netbox_hedgehog.services.preflight import (
            check_transceiver_bay_readiness,
            cli_message,
        )
        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=False)
        ModuleBayTemplate.objects.filter(device_type=switch_dt).delete()

        result = check_transceiver_bay_readiness(plan)
        msg = cli_message(result)

        self.assertIn('populate_transceiver_bays', msg)
        self.assertIn('Affected', msg)


# ---------------------------------------------------------------------------
# S2/S3 — View integration tests: async TopologyPlanGenerateUpdateView
# ---------------------------------------------------------------------------

class TopologyPlanGenerateUpdateViewPreflightTestCase(TestCase):
    """
    Integration tests for TopologyPlanGenerateUpdateView pre-flight check.

    Uses NetBox ObjectPermission (not superuser) per AGENTS.md.
    RED: pre-flight check is not called by the view yet.
    """

    @classmethod
    def setUpTestData(cls):
        # Regular user with TopologyPlan ObjectPermission only (for block tests).
        cls.user = User.objects.create_user(
            username='pf-view-user',
            password='testpass123',
            is_staff=True,
        )
        ct = ContentType.objects.get_for_model(TopologyPlan)
        perm = ObjectPermission.objects.create(
            name='pf-generate-perm',
            actions=['view', 'add', 'change', 'delete'],
        )
        perm.object_types.set([ct])
        perm.users.add(cls.user)

        # Superuser for tests that expect generation to proceed (needs DCIM perms).
        cls.superuser = User.objects.create_user(
            username='pf-view-superuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='pf-view-user', password='testpass123')

    def test_post_blocked_when_bays_missing(self):
        """
        S5.3 — POST generate-update with transceiver FK set, bays absent:
        no GenerationState created, response does not indicate success.
        """
        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=False)
        ModuleBayTemplate.objects.filter(device_type=switch_dt).delete()
        initial_gs_count = GenerationState.objects.filter(plan=plan).count()

        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk},
        )
        response = self.client.post(url, follow=True)

        # Must not have created a new GenerationState
        new_gs_count = GenerationState.objects.filter(plan=plan).count()
        self.assertEqual(new_gs_count, initial_gs_count,
                         'GenerationState must NOT be created when bays are missing')

        # Response content must reference the pre-flight error
        self.assertContains(response, 'populate_transceiver_bays')

    def test_post_proceeds_when_bays_present(self):
        """
        S5.4 — POST generate-update with transceiver FK set, bays present:
        generation is dispatched (GenerationState created or plan status changes).

        Uses superuser to satisfy the DCIM permission check that follows the
        pre-flight check in TopologyPlanGenerateUpdateView.post().
        """
        plan, _ = _build_plan_with_transceiver_fk(with_bays=True)

        # Re-login as superuser so the DCIM permission check passes after pre-flight.
        self.client.logout()
        self.client.login(username='pf-view-superuser', password='testpass123')

        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk},
        )
        response = self.client.post(url, follow=True)

        # Generation was attempted — a GenerationState must now exist
        self.assertTrue(
            GenerationState.objects.filter(plan=plan).exists(),
            'GenerationState must be created when bays are present',
        )

    def test_detail_page_shows_advisory_when_bays_missing(self):
        """
        S3 — Plan detail page GET with transceiver FK set but bays absent:
        response contains the advisory banner copy referencing populate_transceiver_bays.
        """
        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=False)
        ModuleBayTemplate.objects.filter(device_type=switch_dt).delete()

        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'populate_transceiver_bays')


# ---------------------------------------------------------------------------
# S2/S3 — View integration tests: sync TopologyPlanGenerateView
# ---------------------------------------------------------------------------

class TopologyPlanGenerateSyncViewPreflightTestCase(TestCase):
    """
    Integration tests for the synchronous TopologyPlanGenerateView (GET + POST).

    RED: pre-flight check is not present in the sync view.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='pf-sync-view-user',
            password='testpass123',
            is_staff=True,
            is_superuser=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='pf-sync-view-user', password='testpass123')

    def test_generate_page_loads_clean_without_transceiver_fks(self):
        """
        S5.1 — GET generate page, no transceiver FK set: 200, no pre-flight error block.
        """
        plan = _build_plan_without_transceiver_fk()
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate',
            kwargs={'pk': plan.pk},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Must NOT contain the preflight error advisory
        self.assertNotContains(response, 'transceiver bays are missing')

    def test_generate_page_shows_preflight_error_when_bays_missing(self):
        """
        S5.2 — GET generate page, transceiver FK set but bays absent:
        200, response contains pre-flight error text.
        """
        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=False)
        ModuleBayTemplate.objects.filter(device_type=switch_dt).delete()

        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate',
            kwargs={'pk': plan.pk},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'populate_transceiver_bays')


# ---------------------------------------------------------------------------
# S4 — Management command integration tests: generate_devices
# ---------------------------------------------------------------------------

class GenerateDevicesCommandPreflightTestCase(TestCase):
    """
    Tests that the `generate_devices` management command aborts with a
    non-zero exit when transceiver FKs are set but bays are absent.

    RED: the command does not yet call check_transceiver_bay_readiness().
    """

    def test_command_aborts_with_error_when_bays_missing(self):
        """
        generate_devices <plan_id> raises CommandError when FK set, bays absent.
        """
        from django.core.management import call_command
        from django.core.management.base import CommandError

        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=False)
        ModuleBayTemplate.objects.filter(device_type=switch_dt).delete()

        with self.assertRaises(CommandError) as ctx:
            call_command('generate_devices', str(plan.pk))

        self.assertIn('populate_transceiver_bays', str(ctx.exception))

    def test_command_proceeds_when_bays_present(self):
        """
        generate_devices <plan_id> does NOT raise CommandError when bays present.

        Note: generation itself may fail for other reasons (e.g. missing NIC
        module bay templates) in a minimal fixture; we only assert that the
        pre-flight check itself does not abort.
        """
        from io import StringIO
        from django.core.management import call_command

        plan, _ = _build_plan_with_transceiver_fk(with_bays=True)

        # If generation itself fails for non-preflight reasons, that is acceptable;
        # the test only checks the preflight does not fire when bays are present.
        # We wrap in a broad try/except and only re-raise if it mentions preflight.
        try:
            call_command('generate_devices', str(plan.pk), stdout=StringIO())
        except Exception as exc:
            # Pre-flight abort would contain 'populate_transceiver_bays'
            self.assertNotIn(
                'populate_transceiver_bays',
                str(exc),
                'Pre-flight should not abort when bays are present',
            )


# ---------------------------------------------------------------------------
# S3 — Detail page advisory banner: no-FK plan does NOT show banner
# ---------------------------------------------------------------------------

class TopologyPlanDetailTransceiverAdvisoryTestCase(TestCase):
    """
    Tests that the plan detail page renders (or omits) the transceiver advisory
    banner based on transceiver_bay_readiness context injected by the view.

    RED: the view does not yet inject transceiver_bay_readiness into context.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='pf-detail-user',
            password='testpass123',
            is_staff=True,
            is_superuser=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='pf-detail-user', password='testpass123')

    def test_detail_page_no_banner_when_no_fks(self):
        """
        Detail page for a plan with no transceiver FKs must NOT show the advisory.
        """
        plan = _build_plan_without_transceiver_fk()
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'transceiver bays are missing')

    def test_detail_page_shows_banner_when_bays_missing(self):
        """
        Detail page for a plan with FK set but bays absent must show advisory.
        Advisory must reference populate_transceiver_bays command.
        """
        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=False)
        ModuleBayTemplate.objects.filter(device_type=switch_dt).delete()

        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'populate_transceiver_bays')

    def test_detail_page_no_banner_when_bays_present(self):
        """
        Detail page for a plan with FK set AND bays present must NOT show advisory.
        """
        plan, _ = _build_plan_with_transceiver_fk(with_bays=True)

        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'transceiver bays are missing')


# ---------------------------------------------------------------------------
# S6 — Mixed-plan scope narrowing: unrelated NICs and switch classes
#       must not cause over-blocking when they carry no transceiver intent.
# ---------------------------------------------------------------------------

def _get_or_create_unrelated_nic_module_type():
    """
    Return a second NIC ModuleType with no ModuleBayTemplates.

    This simulates a NIC whose PlanServerConnection carries no
    transceiver_module_type FK — it must NOT be checked by pre-flight.
    """
    mfr, _ = Manufacturer.objects.get_or_create(
        name='Preflight-Test-Vendor',
        defaults={'slug': 'preflight-test-vendor'},
    )
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr,
        model='Unrelated-NIC-NoBays',
    )
    # Deliberately no ModuleBayTemplates created.
    return mt


def _get_or_create_second_switch_fixtures():
    """
    Return (device_type_B, ext_B, breakout_option) for a second switch class.

    DeviceType PF-Switch-200 has InterfaceTemplates but NO ModuleBayTemplates —
    simulating a switch class whose zones carry no transceiver_module_type FK.
    """
    mfr, _ = Manufacturer.objects.get_or_create(
        name='Preflight-Test-Vendor',
        defaults={'slug': 'preflight-test-vendor'},
    )
    dt_b, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr,
        model='PF-Switch-200',
        defaults={'slug': 'pf-switch-200'},
    )
    # Add an InterfaceTemplate so the switch looks real, but no ModuleBayTemplate.
    InterfaceTemplate.objects.get_or_create(
        device_type=dt_b,
        name='Ethernet2/1',
        defaults={'type': '100gbase-x-qsfp28'},
    )
    bo, _ = BreakoutOption.objects.get_or_create(
        breakout_id='4x200g-pf',
        defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200},
    )
    ext_b, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=dt_b,
        defaults={
            'native_speed': 800,
            'supported_breakouts': ['1x800g', '4x200g'],
            'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    return dt_b, ext_b, bo


class MixedPlanPreflightTestCase(TestCase):
    """
    Regression tests for the narrowed pre-flight scope (review fix).

    A "mixed plan" has some connections/zones with transceiver FKs and some
    without.  Only the entities referenced by FK-bearing rows should be
    checked.  Unrelated NICs and switch classes must not cause over-blocking.
    """

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='pf-mixed-superuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True,
        )

    def setUp(self):
        self.client = Client()

    # ------------------------------------------------------------------
    # Service-level mixed-NIC test
    # ------------------------------------------------------------------

    def test_unrelated_nic_without_bays_does_not_block(self):
        """
        Mixed-NIC plan: one connection HAS transceiver FK (NIC module type has
        bays); a second connection in the SAME plan has no FK (NIC module type
        has NO bays).  Pre-flight must pass — only the FK-bearing connection's
        NIC type is checked.
        """
        from netbox_hedgehog.services.preflight import check_transceiver_bay_readiness
        from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type

        # Build the "prepared" half of the plan (FK set, bays present).
        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=True)

        # Add a second server class whose connection carries NO transceiver FK.
        # Its NIC uses an unrelated module type that has NO ModuleBayTemplates.
        srv_dt = _get_or_create_server_fixtures()
        unrelated_mt = _get_or_create_unrelated_nic_module_type()
        ModuleBayTemplate.objects.filter(module_type=unrelated_mt).delete()

        sc2 = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='pf-gpu-unrelated',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            gpus_per_server=8,
            server_device_type=srv_dt,
        )
        from netbox_hedgehog.models.topology_planning import PlanServerNIC
        nic2 = PlanServerNIC.objects.create(
            server_class=sc2,
            nic_id='pf-nic-unrelated',
            module_type=unrelated_mt,
        )
        # Reuse the existing zone from the plan (any zone works; no FK on this conn).
        from netbox_hedgehog.models.topology_planning import SwitchPortZone as SPZ
        zone = SPZ.objects.filter(switch_class__plan=plan).first()
        PlanServerConnection.objects.create(
            server_class=sc2,
            connection_id='PF-UNRELATED-001',
            nic=nic2,
            port_index=0,
            target_zone=zone,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200,
            port_type='data',
            # transceiver_module_type intentionally NOT set
        )

        result = check_transceiver_bay_readiness(plan)

        self.assertTrue(
            result.is_ready,
            'Mixed-NIC plan must be ready when only the FK-bearing NIC type has bays; '
            'unrelated NIC type (no FK, no bays) must not cause blocking.',
        )

    # ------------------------------------------------------------------
    # Service-level mixed-switch test
    # ------------------------------------------------------------------

    def test_unrelated_switch_class_without_bays_does_not_block(self):
        """
        Mixed-switch plan: one switch class has a zone WITH transceiver FK
        (device type has sufficient bays); a second switch class in the SAME
        plan has a zone WITHOUT transceiver FK (device type has NO bays).
        Pre-flight must pass — only the FK-bearing zone's device type is checked.
        """
        from netbox_hedgehog.services.preflight import check_transceiver_bay_readiness

        # Build the "prepared" half (zone FK set, switch DT has bays).
        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=True)

        # Add a second switch class whose zone carries NO transceiver FK.
        # Its device type has an InterfaceTemplate but NO ModuleBayTemplate.
        dt_b, ext_b, bo = _get_or_create_second_switch_fixtures()
        ModuleBayTemplate.objects.filter(device_type=dt_b).delete()

        sc2 = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='pf-fe-leaf-unrelated',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=ext_b,
            uplink_ports_per_switch=4,
            mclag_pair=False,
        )
        SwitchPortZone.objects.create(
            switch_class=sc2,
            zone_name='pf-unrelated-ports',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
            # transceiver_module_type intentionally NOT set
        )

        result = check_transceiver_bay_readiness(plan)

        self.assertTrue(
            result.is_ready,
            'Mixed-switch plan must be ready when only the FK-bearing zone\'s device '
            'type has bays; unrelated switch class (no FK, no bays) must not block.',
        )

    # ------------------------------------------------------------------
    # Integration-level view test: mixed-NIC plan is not over-blocked
    # ------------------------------------------------------------------

    def test_generate_update_view_not_blocked_by_unrelated_nic(self):
        """
        POST to generate-update on a mixed-NIC plan (FK-bearing NIC has bays,
        unrelated NIC has no bays) must NOT be blocked by pre-flight.

        The pre-flight passes, so the view proceeds to dispatch generation
        (a GenerationState is created).
        """
        from netbox_hedgehog.models.topology_planning import PlanServerNIC
        from netbox_hedgehog.models.topology_planning import SwitchPortZone as SPZ

        plan, switch_dt = _build_plan_with_transceiver_fk(with_bays=True)

        # Add the unrelated server class + connection with no transceiver FK.
        srv_dt = _get_or_create_server_fixtures()
        unrelated_mt = _get_or_create_unrelated_nic_module_type()
        ModuleBayTemplate.objects.filter(module_type=unrelated_mt).delete()

        sc2 = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='pf-gpu-view-unrelated',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            gpus_per_server=8,
            server_device_type=srv_dt,
        )
        nic2 = PlanServerNIC.objects.create(
            server_class=sc2,
            nic_id='pf-nic-view-unrelated',
            module_type=unrelated_mt,
        )
        zone = SPZ.objects.filter(switch_class__plan=plan).first()
        PlanServerConnection.objects.create(
            server_class=sc2,
            connection_id='PF-VIEW-UNRELATED-001',
            nic=nic2,
            port_index=0,
            target_zone=zone,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            speed=200,
            port_type='data',
            # transceiver_module_type intentionally NOT set
        )

        self.client.login(username='pf-mixed-superuser', password='testpass123')
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk},
        )
        self.client.post(url, follow=True)

        # Pre-flight passed → generation was dispatched → GenerationState exists
        self.assertTrue(
            GenerationState.objects.filter(plan=plan).exists(),
            'GenerationState must be created; pre-flight must not block mixed-NIC plan '
            'when only the FK-bearing NIC type has bays.',
        )
