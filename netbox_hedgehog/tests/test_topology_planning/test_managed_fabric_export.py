"""
Integration and unit tests for managed-fabric export scoping (DIET-192 Phase 4 RED).

All tests in this file are expected to FAIL until Phase 5 (GREEN) is implemented.
"""

import yaml
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from dcim.models import Manufacturer, DeviceType, DeviceRole, Site, InterfaceTemplate

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanSwitchClass,
    DeviceTypeExtension,
    BreakoutOption,
    SwitchPortZone,
    GenerationState,
)
from netbox_hedgehog.choices import (
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    AllocationStrategyChoices,
    GenerationStatusChoices,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator

User = get_user_model()


# =============================================================================
# T7: Pure unit tests for FabricTypeChoices.is_hedgehog_managed() predicate
# =============================================================================

class TestFabricTypeChoicesPredicate(TestCase):
    """T7: Unit tests for FabricTypeChoices.is_hedgehog_managed() static method.

    These tests have no DB access. They fail RED because is_hedgehog_managed()
    does not yet exist on FabricTypeChoices.
    """

    def test_frontend_is_managed(self):
        self.assertTrue(FabricTypeChoices.is_hedgehog_managed('frontend'))

    def test_backend_is_managed(self):
        self.assertTrue(FabricTypeChoices.is_hedgehog_managed('backend'))

    def test_oob_mgmt_is_not_managed(self):
        self.assertFalse(FabricTypeChoices.is_hedgehog_managed('oob-mgmt'))

    def test_in_band_mgmt_is_not_managed(self):
        self.assertFalse(FabricTypeChoices.is_hedgehog_managed('in-band-mgmt'))

    def test_network_mgmt_is_not_managed(self):
        self.assertFalse(FabricTypeChoices.is_hedgehog_managed('network-mgmt'))

    def test_legacy_oob_is_not_managed(self):
        self.assertFalse(FabricTypeChoices.is_hedgehog_managed('oob'))

    def test_empty_string_is_not_managed(self):
        self.assertFalse(FabricTypeChoices.is_hedgehog_managed(''))

    def test_unknown_value_is_not_managed(self):
        self.assertFalse(FabricTypeChoices.is_hedgehog_managed('unknown-fabric'))


# =============================================================================
# Shared base class for integration tests
# =============================================================================

class ManagedFabricTestBase(TestCase):
    """Shared reference data for managed-fabric export integration tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='mf-test',
            password='mf-test',
            is_staff=True,
            is_superuser=True,
        )

        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Test Mfg MF',
            defaults={'slug': 'test-mfg-mf'},
        )

        cls.frontend_switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='MF Switch',
            defaults={'slug': 'mf-switch'},
        )

        # Create 4 InterfaceTemplates on the switch type
        for port_name in ('E1/1', 'E1/2', 'E1/3', 'E1/4'):
            InterfaceTemplate.objects.get_or_create(
                device_type=cls.frontend_switch_type,
                name=port_name,
                defaults={'type': '800gbase-x-qsfpdd'},
            )

        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='MF Server',
            defaults={'slug': 'mf-server'},
        )

        InterfaceTemplate.objects.get_or_create(
            device_type=cls.server_type,
            name='eth0',
            defaults={'type': '100gbase-x-qsfp28'},
        )

        cls.frontend_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.frontend_switch_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf', 'spine'],
                'native_speed': 800,
                'supported_breakouts': ['1x800g'],
                'uplink_ports': 2,
                'hedgehog_profile_name': 'mf-test-switch',
            },
        )

        cls.breakout_1x800, _ = BreakoutOption.objects.get_or_create(
            breakout_id='mf-1x800g',
            defaults={
                'from_speed': 800,
                'logical_ports': 1,
                'logical_speed': 800,
            },
        )

        # Use slug='server' so _generate_servers() (which filters role__slug='server') finds them.
        cls.server_role, _ = DeviceRole.objects.get_or_create(
            slug='server',
            defaults={'name': 'Server', 'color': '0000ff'},
        )

        cls.leaf_role, _ = DeviceRole.objects.get_or_create(
            name='MF Leaf Role',
            defaults={'slug': 'mf-leaf', 'color': '008000'},
        )

        cls.site, _ = Site.objects.get_or_create(
            name='MF Test Site',
            defaults={'slug': 'mf-test-site'},
        )

        # NIC ModuleType required by PlanServerConnection (DIET-179)
        from dcim.models import ModuleType
        nvidia, _ = Manufacturer.objects.get_or_create(
            name='NVIDIA',
            defaults={'slug': 'nvidia'},
        )
        cls.nic_module_type, created = ModuleType.objects.get_or_create(
            manufacturer=nvidia,
            model='BlueField-3 BF3220',
        )
        if created:
            InterfaceTemplate.objects.create(
                module_type=cls.nic_module_type,
                name='p0',
                type='other',
            )

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _make_plan_with_generation_state(self, name):
        """Create a TopologyPlan + GenerationState(GENERATED). Returns plan."""
        plan = TopologyPlan.objects.create(name=name, created_by=self.user)
        GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status=GenerationStatusChoices.GENERATED,
        )
        return plan

    def _make_switch_device(self, plan, name, fabric, role='server-leaf'):
        """Create a switch Device with hedgehog custom fields set."""
        from dcim.models import Device
        mac_index = abs(hash(name)) % 256
        return Device.objects.create(
            name=name,
            device_type=self.frontend_switch_type,
            role=self.leaf_role,
            site=self.site,
            custom_field_data={
                'hedgehog_plan_id': str(plan.pk),
                'hedgehog_class': name,
                'hedgehog_fabric': fabric,
                'hedgehog_role': role,
                'boot_mac': f'0c:20:12:ff:01:{mac_index:02x}',
            },
        )

    def _make_server_device(self, plan, name):
        """Create a server Device."""
        from dcim.models import Device
        return Device.objects.create(
            name=name,
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(plan.pk)},
        )

    def _make_interface(self, device, name):
        from dcim.models import Interface
        iface, _ = Interface.objects.get_or_create(
            device=device,
            name=name,
            defaults={'type': '100gbase-x-qsfp28'},
        )
        return iface

    def _make_cable(self, plan, iface_a, iface_b, zone='server'):
        from dcim.models import Cable
        cable = Cable(a_terminations=[iface_a], b_terminations=[iface_b])
        cable.custom_field_data = {
            'hedgehog_plan_id': str(plan.pk),
            'hedgehog_zone': zone,
        }
        cable.save()
        return cable

    def _export_url(self, plan):
        return reverse('plugins:netbox_hedgehog:topologyplan_export', args=[plan.pk])

    def _get_export_docs(self, plan):
        """GET the export URL and return parsed YAML docs list."""
        response = self.client.get(self._export_url(plan))
        self.assertEqual(response.status_code, 200)
        return [d for d in yaml.safe_load_all(response.content.decode()) if d]

    def _anchor_cable(self, plan, switch, suffix='anc'):
        """Add a minimal server+cable so the export view passes the cables-exist check."""
        server = self._make_server_device(plan, f'{switch.name}-{suffix}-srv')
        sw_iface = self._make_interface(switch, f'E1/1/{suffix}')
        srv_iface = self._make_interface(server, f'eth-{suffix}')
        return self._make_cable(plan, srv_iface, sw_iface)


# =============================================================================
# T1: Mixed plan export - managed switches appear, unmanaged do not
# =============================================================================

class TestMixedPlanExport(ManagedFabricTestBase):
    """T1: Mixed plan (frontend + oob-mgmt) export scoping.

    RED: unmanaged switches currently pass the fabric filter because no
    fabric filter exists in _generate_switches().
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_managed_switch_appears_in_yaml(self):
        """T1a: frontend switch is present in Switch CRDs."""
        plan = self._make_plan_with_generation_state('T1-Mixed-Appear')
        fe = self._make_switch_device(plan, 'fe-leaf-001', 'frontend', 'server-leaf')
        self._make_switch_device(plan, 'oob-leaf-001', 'oob-mgmt', 'server-leaf')
        self._anchor_cable(plan, fe)  # satisfy Check 4 (cables must exist)

        docs = self._get_export_docs(plan)
        switch_names = str([
            d.get('metadata', {}).get('name', '')
            for d in docs if d.get('kind') == 'Switch'
        ])
        self.assertIn('fe-leaf-001', switch_names)
        self.assertNotIn('oob-leaf-001', switch_names)

    def test_switch_crd_omits_empty_ecmp(self):
        """T1e (issue #302): Switch CRDs must NOT contain ecmp: {} — hhfab validate rejects it."""
        plan = self._make_plan_with_generation_state('T1-Ecmp-Omit')
        fe = self._make_switch_device(plan, 'fe-leaf-ecmp', 'frontend', 'server-leaf')
        self._anchor_cable(plan, fe)

        docs = self._get_export_docs(plan)
        switch_docs = [d for d in docs if d.get('kind') == 'Switch']
        self.assertTrue(switch_docs, "Expected at least one Switch CRD")
        for switch_doc in switch_docs:
            spec = switch_doc.get('spec', {})
            self.assertNotIn(
                'ecmp', spec,
                f"Switch CRD {switch_doc['metadata']['name']} must not contain 'ecmp' key "
                f"(hhfab validate rejects empty ecmp: {{}} — issue #302)"
            )

    def test_unmanaged_switch_appears_as_server_crd_surrogate(self):
        """T1b (revised DIET-250): oob-mgmt switch appears as Server CRD surrogate, not Switch CRD."""
        plan = self._make_plan_with_generation_state('T1-Mixed-Absent')
        fe = self._make_switch_device(plan, 'fe-leaf-002', 'frontend', 'server-leaf')
        self._make_switch_device(plan, 'oob-leaf-002', 'oob-mgmt', 'server-leaf')
        self._anchor_cable(plan, fe)

        response = self.client.get(self._export_url(plan))
        self.assertEqual(response.status_code, 200)
        yaml_str = response.content.decode()

        import yaml as yaml_lib
        docs = [d for d in yaml_lib.safe_load_all(yaml_str) if d]
        switch_names = [d['metadata']['name'] for d in docs if d.get('kind') == 'Switch']
        server_names = [d['metadata']['name'] for d in docs if d.get('kind') == 'Server']

        # oob-mgmt device must NOT appear as a Switch CRD
        self.assertNotIn('oob-leaf-002', switch_names,
                         "oob-mgmt device must not appear in Switch CRDs")
        # oob-mgmt device MUST appear as a Server CRD surrogate
        self.assertIn('oob-leaf-002', server_names,
                      "oob-mgmt device must appear as a Server CRD surrogate")


# =============================================================================
# T2: Server connection filtering - cables to unmanaged switches excluded
# =============================================================================

class TestServerConnectionFiltering(ManagedFabricTestBase):
    """T2: Connection CRDs exclude cables that terminate on unmanaged switches.

    RED: _generate_connection_crds() has no _endpoint_is_allowed() guard.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_server_to_managed_switch_connection_exported(self):
        """T2a: server->managed cable exports Connection CRD; server->surrogate does not.

        RED: After Phase 4 GREEN implementation:
        - managed-switch->oob-mgmt cable (zone='oob') must produce a Connection CRD.
        - server->oob-mgmt cable (zone='server') must NOT produce a Connection CRD
          (server<->surrogate is out of scope per #249/#252).
        - oob-mgmt device must appear as a Server CRD (surrogate).
        """
        plan = self._make_plan_with_generation_state('T2-Filter')
        fe_switch = self._make_switch_device(plan, 'fe-leaf-010', 'frontend', 'server-leaf')
        oob_switch = self._make_switch_device(plan, 'oob-leaf-010', 'oob-mgmt', 'server-leaf')
        server = self._make_server_device(plan, 'gpu-server-010')

        fe_iface = self._make_interface(fe_switch, 'E1/1/1')
        fe_iface2 = self._make_interface(fe_switch, 'E1/1/2')
        oob_server_iface = self._make_interface(oob_switch, 'E1/1/1')
        oob_fe_iface = self._make_interface(oob_switch, 'E1/1/2')
        srv_iface1 = self._make_interface(server, 'eth0')
        srv_iface2 = self._make_interface(server, 'eth1')

        self._make_cable(plan, srv_iface1, fe_iface)           # server -> managed (zone='server')
        self._make_cable(plan, srv_iface2, oob_server_iface)   # server -> surrogate (zone='server') — excluded
        self._make_cable(plan, fe_iface2, oob_fe_iface, zone='oob')  # managed -> surrogate (zone='oob') — included

        docs = self._get_export_docs(plan)
        conn_docs = [d for d in docs if d and d.get('kind') == 'Connection']
        all_conn_yaml = str(conn_docs)
        server_docs = [d for d in docs if d and d.get('kind') == 'Server']
        server_names = {d['metadata']['name'] for d in server_docs}

        # Server->managed cable: Connection CRD expected
        self.assertIn('gpu-server-010', all_conn_yaml)
        self.assertIn('fe-leaf-010', all_conn_yaml)

        # Managed->surrogate cable: Connection CRD expected (RED: currently fails)
        self.assertTrue(
            any('oob-leaf-010' in str(d) for d in conn_docs),
            "managed-switch->oob-mgmt cable must produce a Connection CRD",
        )

        # Server->surrogate cable: NO Connection CRD (server<->surrogate excluded)
        srv_to_oob_conns = [
            d for d in conn_docs
            if 'gpu-server-010' in str(d) and 'oob-leaf-010' in str(d)
        ]
        self.assertEqual(
            len(srv_to_oob_conns), 0,
            "server->oob-mgmt cable must NOT produce a Connection CRD (server<->surrogate excluded)",
        )

        # oob-mgmt device must appear as a Server CRD (surrogate) (RED: currently fails)
        self.assertIn(
            'oob-leaf-010', server_names,
            "oob-mgmt switch must appear as a Server CRD surrogate",
        )

    def test_server_excluded_when_only_surrogate_connections(self):
        """T2b (updated DIET-254): Server with only surrogate connections excluded from Server CRDs.

        Constraint #3: a server must NOT appear in wiring export solely due to
        surrogate-only (oob-mgmt) connectivity.
        """
        plan = self._make_plan_with_generation_state('T2-Server-Only')
        oob_switch = self._make_switch_device(plan, 'oob-leaf-011', 'oob-mgmt', 'server-leaf')
        server = self._make_server_device(plan, 'gpu-server-011')

        oob_iface = self._make_interface(oob_switch, 'E1/1/1')
        srv_iface = self._make_interface(server, 'eth0')
        self._make_cable(plan, srv_iface, oob_iface)

        response = self.client.get(self._export_url(plan))
        self.assertEqual(response.status_code, 200)

        docs = [d for d in yaml.safe_load_all(response.content.decode()) if d]
        server_docs = [d for d in docs if d and d.get('kind') == 'Server']
        self.assertFalse(
            any('gpu-server-011' in str(d) for d in server_docs),
            "Server CRD must NOT appear when connected only to surrogate (oob-mgmt) switches (constraint #3).",
        )


# =============================================================================
# T3: Cable count filtering - only managed cables produce Connection CRDs
# =============================================================================

class TestCableCountFiltering(ManagedFabricTestBase):
    """T3: Exactly N Connection CRDs appear for N managed cables (unmanaged excluded).

    RED: 4 Connection CRDs are exported currently because no endpoint guard exists.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_connection_crd_count_excludes_management_cables(self):
        """T3: Only managed cables produce Connection CRDs; non-surrogate mgmt cables excluded.

        Uses 4 cables:
        - 2 server->managed cables (zone='server'): produce Connection CRDs
        - 2 server->in-band-mgmt cables: excluded entirely (in-band-mgmt not in SURROGATE_SET)
        Leaves exactly 2 Connection CRDs.

        Note: oob-mgmt is NOT used here because managed->oob-mgmt cables now produce
        Connection CRDs (per #249/#252). in-band-mgmt remains fully excluded.
        """
        plan = self._make_plan_with_generation_state('T3-Count')
        fe_switch = self._make_switch_device(plan, 'fe-leaf-020', 'frontend', 'server-leaf')
        # in-band-mgmt is excluded entirely (not a surrogate, not managed)
        inband_switch = self._make_switch_device(plan, 'inband-leaf-020', 'in-band-mgmt', 'server-leaf')

        srv1 = self._make_server_device(plan, 'gpu-server-020a')
        srv2 = self._make_server_device(plan, 'gpu-server-020b')
        srv3 = self._make_server_device(plan, 'gpu-server-020c')
        srv4 = self._make_server_device(plan, 'gpu-server-020d')

        fe_iface1 = self._make_interface(fe_switch, 'E1/1/1')
        fe_iface2 = self._make_interface(fe_switch, 'E1/1/2')
        inband_iface1 = self._make_interface(inband_switch, 'E1/1/1')
        inband_iface2 = self._make_interface(inband_switch, 'E1/1/2')

        self._make_cable(plan, self._make_interface(srv1, 'eth0'), fe_iface1)        # managed cable 1
        self._make_cable(plan, self._make_interface(srv2, 'eth0'), fe_iface2)        # managed cable 2
        self._make_cable(plan, self._make_interface(srv3, 'eth0'), inband_iface1)    # excluded cable 1
        self._make_cable(plan, self._make_interface(srv4, 'eth0'), inband_iface2)    # excluded cable 2

        docs = self._get_export_docs(plan)
        conn_count = len([d for d in docs if d and d.get('kind') == 'Connection'])
        self.assertEqual(conn_count, 2,
            f"Expected 2 Connection CRDs (managed cables only, in-band-mgmt excluded), got {conn_count}.")


# =============================================================================
# T4: All-managed plan regression - nothing excluded when all fabrics are managed
# =============================================================================

class TestAllManagedPlanRegression(ManagedFabricTestBase):
    """T4: Plans with only frontend/backend fabrics still export everything.

    This test MAY pass in RED phase (documents expected behavior); that is
    acceptable. It will continue to pass post-implementation.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_all_frontend_switches_appear_in_yaml(self):
        """T4a: All frontend switches appear in Switch CRDs."""
        plan = self._make_plan_with_generation_state('T4-AllManaged')
        sw1 = self._make_switch_device(plan, 'fe-leaf-030', 'frontend', 'server-leaf')
        self._make_switch_device(plan, 'fe-leaf-031', 'frontend', 'server-leaf')
        self._anchor_cable(plan, sw1)  # satisfy Check 4

        docs = self._get_export_docs(plan)
        switch_names = str([
            d.get('metadata', {}).get('name', '')
            for d in docs if d and d.get('kind') == 'Switch'
        ])
        self.assertIn('fe-leaf-030', switch_names)
        self.assertIn('fe-leaf-031', switch_names)

    def test_all_managed_connections_appear_in_yaml(self):
        """T4b: All cables in an all-managed plan produce Connection CRDs."""
        plan = self._make_plan_with_generation_state('T4-AllConnections')
        fe_switch = self._make_switch_device(plan, 'fe-leaf-032', 'frontend', 'server-leaf')
        server = self._make_server_device(plan, 'gpu-server-030')

        fe_iface = self._make_interface(fe_switch, 'E1/1/1')
        srv_iface = self._make_interface(server, 'eth0')
        self._make_cable(plan, srv_iface, fe_iface)

        docs = self._get_export_docs(plan)
        conn_docs = [d for d in docs if d and d.get('kind') == 'Connection']
        self.assertTrue(len(conn_docs) >= 1,
            "At least 1 Connection CRD expected in an all-managed plan.")


# =============================================================================
# T5: Legacy 'oob' fabric excluded from YAML export
# =============================================================================

class TestLegacyOobFabric(ManagedFabricTestBase):
    """T5: Legacy 'oob' fabric value is treated as unmanaged (excluded from export).

    RED: legacy oob switch has hedgehog_role='server-leaf' (non-empty), so it
    currently passes the only filter and appears in YAML.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_legacy_oob_switch_excluded_from_yaml(self):
        """T5a: Switch with fabric='oob' (legacy) does not appear in Switch CRDs."""
        plan = self._make_plan_with_generation_state('T5-LegacyOob')
        # Also add a managed switch with anchor cable so Check 4 passes
        fe = self._make_switch_device(plan, 'fe-anchor-040', 'frontend', 'server-leaf')
        self._make_switch_device(plan, 'oob-legacy-040', 'oob', 'server-leaf')
        self._anchor_cable(plan, fe)

        docs = self._get_export_docs(plan)
        switch_names_str = str([d for d in docs if d and d.get('kind') == 'Switch'])
        self.assertNotIn('oob-legacy-040', switch_names_str)

    def test_legacy_oob_no_dangling_references(self):
        """T5b: Cables to legacy-oob switches do not appear as Connection CRDs."""
        plan = self._make_plan_with_generation_state('T5-LegacyOob2')
        fe_switch = self._make_switch_device(plan, 'fe-leaf-041', 'frontend', 'server-leaf')
        oob_switch = self._make_switch_device(plan, 'oob-legacy-041', 'oob', 'server-leaf')
        server = self._make_server_device(plan, 'gpu-server-041')

        fe_iface = self._make_interface(fe_switch, 'E1/1/1')
        oob_iface = self._make_interface(oob_switch, 'E1/1/1')
        srv_iface1 = self._make_interface(server, 'eth0')
        srv_iface2 = self._make_interface(server, 'eth1')

        self._make_cable(plan, srv_iface1, fe_iface)
        self._make_cable(plan, srv_iface2, oob_iface)

        response = self.client.get(self._export_url(plan))
        self.assertEqual(response.status_code, 200)
        yaml_str = response.content.decode()
        self.assertNotIn('oob-legacy-041', yaml_str)


# =============================================================================
# T6: DeviceGenerator does not create fabric cables for legacy 'oob' fabric
# =============================================================================

class TestDeviceGeneratorManagedFabricLoop(ManagedFabricTestBase):
    """T6: DeviceGenerator._create_fabric_connections() skips legacy oob fabric.

    RED: 'oob' IS in the current loop tuple so oob leaf+spine get fabric cables.
    Uses setUp() (not setUpTestData) because DeviceGenerator mutates the DB.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

        self.plan = TopologyPlan.objects.create(name='T6-DevGen')

        self.oob_leaf_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='oob-leaf',
            fabric='oob',
            hedgehog_role='server-leaf',
            device_type_extension=self.frontend_ext,
            calculated_quantity=None,
            override_quantity=1,
            uplink_ports_per_switch=2,
            mclag_pair=False,
        )

        self.oob_spine_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='oob-spine',
            fabric='oob',
            hedgehog_role='spine',
            device_type_extension=self.frontend_ext,
            calculated_quantity=None,
            override_quantity=1,
            uplink_ports_per_switch=0,
            mclag_pair=False,
        )

        SwitchPortZone.objects.create(
            switch_class=self.oob_leaf_class,
            zone_name='uplinks',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='1-2',
            breakout_option=self.breakout_1x800,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )

        SwitchPortZone.objects.create(
            switch_class=self.oob_spine_class,
            zone_name='fabric',
            zone_type=PortZoneTypeChoices.FABRIC,
            port_spec='1-4',
            breakout_option=self.breakout_1x800,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )

    def tearDown(self):
        from dcim.models import Cable, Device
        Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).delete()
        Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).delete()
        self.plan.delete()

    def test_no_fabric_cables_for_legacy_oob_switch_class(self):
        """T6: Legacy oob fabric classes must not get spine-leaf fabric cables."""
        DeviceGenerator(plan=self.plan).generate_all()

        from dcim.models import Cable
        cables = Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_zone='fabric',
        )
        self.assertEqual(
            cables.count(),
            0,
            "Legacy oob fabric classes must not get spine-leaf cables; "
            f"found {cables.count()} fabric cable(s).",
        )


# =============================================================================
# T8: PlanSwitchClass detail template shows Wiring Diagram inclusion badge
# =============================================================================

class TestPlanSwitchClassTemplateBadge(ManagedFabricTestBase):
    """T8: Detail template renders 'Included'/'Excluded' badge for wiring diagram.

    RED: template has no is_hedgehog_managed property reference; renders without
    badge row -> 'Included'/'Excluded' not in response.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_managed_switch_class_shows_included_badge(self):
        """T8a: Frontend switch class detail shows 'Included' badge."""
        plan = TopologyPlan.objects.create(name='T8-Badge', created_by=self.user)
        sc = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='badge-fe',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.frontend_ext,
            calculated_quantity=None,
            override_quantity=1,
            uplink_ports_per_switch=0,
            mclag_pair=False,
        )

        url = reverse('plugins:netbox_hedgehog:planswitchclass_detail', args=[sc.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Included')

    def test_unmanaged_switch_class_shows_excluded_badge(self):
        """T8b: oob-mgmt switch class detail shows 'Excluded' badge."""
        plan = TopologyPlan.objects.create(name='T8-Badge2', created_by=self.user)
        sc = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='badge-oob',
            fabric='oob-mgmt',
            hedgehog_role='server-leaf',
            device_type_extension=self.frontend_ext,
            calculated_quantity=None,
            override_quantity=1,
            uplink_ports_per_switch=0,
            mclag_pair=False,
        )

        url = reverse('plugins:netbox_hedgehog:planswitchclass_detail', args=[sc.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Excluded')


# =============================================================================
# T9: Legacy OOB form label + oob-mgmt export filtering
# =============================================================================

class TestLegacyOobFormAndExport(ManagedFabricTestBase):
    """T9: OOB choice shows DEPRECATED label in form; oob-mgmt cables excluded from export.

    RED (form): OOB choice label is 'Out-of-Band', not 'DEPRECATED'.
    RED (export): oob-mgmt cables appear in YAML because no endpoint guard exists.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_legacy_oob_choice_removed_from_form(self):
        """T9a: Legacy `oob` fabric choice is removed from the switch-class form.

        Fabric Class architecture replaces enum-backed fabric selection with
        explicit `fabric_name` and `fabric_class` fields. Legacy names survive
        only in stored data / fallback logic, not as selectable form choices.
        """
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="oob"')
        self.assertContains(response, 'name="fabric_name"')
        self.assertContains(response, 'name="fabric_class"')

    def test_oob_mgmt_export_surrogate_semantics(self):
        """T9b (revised): oob-mgmt switch exports as Server CRD surrogate; no Switch CRD.

        RED: Current code emits NO CRD for oob-mgmt-050. After GREEN implementation:
        - oob-mgmt device appears as a Server CRD (surrogate).
        - No Switch CRD for oob-mgmt device.
        - server->oob-mgmt cable (zone='server'): NO Connection CRD (server<->surrogate excluded).
        - A separate managed->oob-mgmt cable (zone='oob') would produce a Connection CRD,
          but this test focuses on the surrogate Server CRD emission and exclusion of
          server<->surrogate Connection CRDs.
        """
        plan = self._make_plan_with_generation_state('T9-OobMgmt')
        fe_switch = self._make_switch_device(plan, 'fe-leaf-050', 'frontend', 'server-leaf')
        oob_switch = self._make_switch_device(plan, 'oob-mgmt-050', 'oob-mgmt', 'server-leaf')
        server = self._make_server_device(plan, 'gpu-server-050')

        fe_iface = self._make_interface(fe_switch, 'E1/1/1')
        oob_iface = self._make_interface(oob_switch, 'E1/1/1')
        srv_iface1 = self._make_interface(server, 'eth0')
        srv_iface2 = self._make_interface(server, 'eth1')

        self._make_cable(plan, srv_iface1, fe_iface)          # server -> managed (zone='server')
        self._make_cable(plan, srv_iface2, oob_iface)         # server -> surrogate (zone='server') — excluded

        response = self.client.get(self._export_url(plan))
        self.assertEqual(response.status_code, 200)
        docs = [d for d in yaml.safe_load_all(response.content.decode()) if d]

        switch_names = {d['metadata']['name'] for d in docs if d.get('kind') == 'Switch'}
        server_names = {d['metadata']['name'] for d in docs if d.get('kind') == 'Server'}
        conn_docs = [d for d in docs if d.get('kind') == 'Connection']

        # oob-mgmt must appear as Server CRD surrogate (RED: currently fails)
        self.assertIn(
            'oob-mgmt-050', server_names,
            "oob-mgmt switch must appear as a Server CRD surrogate",
        )

        # oob-mgmt must NOT appear as Switch CRD
        self.assertNotIn(
            'oob-mgmt-050', switch_names,
            "oob-mgmt switch must never appear as a Switch CRD",
        )

        # server->oob-mgmt cable must NOT produce a Connection CRD (server<->surrogate excluded)
        srv_oob_conns = [
            d for d in conn_docs
            if 'oob-mgmt-050' in str(d) and 'gpu-server-050' in str(d)
        ]
        self.assertEqual(
            len(srv_oob_conns), 0,
            "server->oob-mgmt cable must NOT produce a Connection CRD (server<->surrogate out of scope)",
        )


# =============================================================================
# Phase 3 RED: New predicate unit tests
# =============================================================================

class TestSurrogateEndpointPredicate(TestCase):
    """Unit tests for FabricTypeChoices.is_surrogate_endpoint() and SURROGATE_ENDPOINT_SET.

    These tests have no DB access.
    RED: is_surrogate_endpoint() and SURROGATE_ENDPOINT_SET do not exist yet.
    """

    def test_oob_mgmt_is_surrogate(self):
        self.assertTrue(FabricTypeChoices.is_surrogate_endpoint('oob-mgmt'))

    def test_frontend_is_not_surrogate(self):
        self.assertFalse(FabricTypeChoices.is_surrogate_endpoint('frontend'))

    def test_backend_is_not_surrogate(self):
        self.assertFalse(FabricTypeChoices.is_surrogate_endpoint('backend'))

    def test_in_band_mgmt_is_not_surrogate(self):
        self.assertFalse(FabricTypeChoices.is_surrogate_endpoint('in-band-mgmt'))

    def test_network_mgmt_is_not_surrogate(self):
        self.assertFalse(FabricTypeChoices.is_surrogate_endpoint('network-mgmt'))

    def test_legacy_oob_is_not_surrogate(self):
        self.assertFalse(FabricTypeChoices.is_surrogate_endpoint('oob'))

    def test_empty_string_is_not_surrogate(self):
        self.assertFalse(FabricTypeChoices.is_surrogate_endpoint(''))

    def test_unknown_value_is_not_surrogate(self):
        self.assertFalse(FabricTypeChoices.is_surrogate_endpoint('something-else'))

    def test_surrogate_set_disjoint_from_managed_set(self):
        """SURROGATE_ENDPOINT_SET and HEDGEHOG_MANAGED_SET must be disjoint."""
        overlap = FabricTypeChoices.SURROGATE_ENDPOINT_SET & FabricTypeChoices.HEDGEHOG_MANAGED_SET
        self.assertEqual(overlap, set(), f"Sets must be disjoint but share: {overlap}")

    def test_in_band_mgmt_not_in_surrogate_set(self):
        """in-band-mgmt must not be auto-included in SURROGATE_ENDPOINT_SET."""
        self.assertNotIn('in-band-mgmt', FabricTypeChoices.SURROGATE_ENDPOINT_SET)

    def test_network_mgmt_not_in_surrogate_set(self):
        """network-mgmt must not be auto-included in SURROGATE_ENDPOINT_SET."""
        self.assertNotIn('network-mgmt', FabricTypeChoices.SURROGATE_ENDPOINT_SET)


# =============================================================================
# Phase 3 RED: Surrogate Server CRD emission (T10)
# =============================================================================

class TestSurrogateServerCrdEmission(ManagedFabricTestBase):
    """T10: oob-mgmt switch instances export as Server CRDs, never Switch CRDs.

    RED: _generate_servers() currently filters role__slug='server' only.
    oob-mgmt devices have role='leaf' (mf-leaf) so they are not found.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_oob_mgmt_switch_emits_server_crd(self):
        """T10a: oob-mgmt device appears as Server CRD; absent from Switch CRDs."""
        plan = self._make_plan_with_generation_state('T10a-Surrogate')
        fe = self._make_switch_device(plan, 'fe-leaf-100', 'frontend', 'server-leaf')
        oob = self._make_switch_device(plan, 'oob-mgmt-100', 'oob-mgmt', 'server-leaf')
        self._anchor_cable(plan, fe)

        docs = self._get_export_docs(plan)
        switch_names = {d['metadata']['name'] for d in docs if d.get('kind') == 'Switch'}
        server_names = {d['metadata']['name'] for d in docs if d.get('kind') == 'Server'}

        # RED: oob-mgmt-100 not yet in server_names (no surrogate logic)
        self.assertIn('oob-mgmt-100', server_names,
                      "oob-mgmt switch must appear as a Server CRD surrogate")
        self.assertNotIn('oob-mgmt-100', switch_names,
                         "oob-mgmt switch must never appear as a Switch CRD")

    def test_oob_mgmt_server_crd_has_minimal_spec(self):
        """T10b: Surrogate Server CRD spec contains only allowed fields (no Switch-specific fields)."""
        plan = self._make_plan_with_generation_state('T10b-Surrogate')
        fe = self._make_switch_device(plan, 'fe-leaf-101', 'frontend', 'server-leaf')
        self._make_switch_device(plan, 'oob-mgmt-101', 'oob-mgmt', 'server-leaf')
        self._anchor_cable(plan, fe)

        docs = self._get_export_docs(plan)
        surrogate_docs = [
            d for d in docs
            if d.get('kind') == 'Server' and d.get('metadata', {}).get('name') == 'oob-mgmt-101'
        ]
        # RED: surrogate_docs will be empty until GREEN implementation
        self.assertEqual(len(surrogate_docs), 1,
                         "Exactly one Server CRD for oob-mgmt-101 expected")
        spec = surrogate_docs[0].get('spec', {})
        forbidden_switch_fields = {'profile', 'boot', 'portBreakouts', 'redundancy', 'ecmp'}
        present_forbidden = forbidden_switch_fields & set(spec.keys())
        self.assertEqual(present_forbidden, set(),
                         f"Surrogate Server CRD must not contain switch-only fields: {present_forbidden}")

    def test_oob_mgmt_server_crd_name_is_dns_safe(self):
        """T10c: Surrogate Server CRD metadata.name is DNS-1123 compliant."""
        import re
        plan = self._make_plan_with_generation_state('T10c-Surrogate')
        fe = self._make_switch_device(plan, 'fe-leaf-102', 'frontend', 'server-leaf')
        self._make_switch_device(plan, 'oob-mgmt-102', 'oob-mgmt', 'server-leaf')
        self._anchor_cable(plan, fe)

        docs = self._get_export_docs(plan)
        surrogate_docs = [d for d in docs if d.get('kind') == 'Server'
                          and 'oob-mgmt-102' in d.get('metadata', {}).get('name', '')]
        # RED: will be empty until GREEN
        self.assertGreater(len(surrogate_docs), 0,
                           "Surrogate Server CRD for oob-mgmt-102 must exist")
        name = surrogate_docs[0]['metadata']['name']
        self.assertRegex(name, r'^[a-z0-9][a-z0-9-]*[a-z0-9]$',
                         f"Surrogate CRD name '{name}' must be DNS-1123 compliant")


# =============================================================================
# Phase 3 RED: managed-switch <-> surrogate Connection CRDs (T11)
# =============================================================================

class TestManagedSurrogateConnectionCrd(ManagedFabricTestBase):
    """T11: managed-switch <-> oob-mgmt cables produce Connection CRDs (unbundled).

    RED: _endpoint_is_allowed() blocks oob-mgmt devices entirely.
    All assertions about Connection CRDs containing oob-mgmt names will fail.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_managed_to_oob_mgmt_cable_produces_connection_crd(self):
        """T11a: One managed->oob-mgmt cable (zone='oob') produces one Connection CRD."""
        plan = self._make_plan_with_generation_state('T11a-MgdSurr')
        fe = self._make_switch_device(plan, 'fe-leaf-110', 'frontend', 'server-leaf')
        oob = self._make_switch_device(plan, 'oob-mgmt-110', 'oob-mgmt', 'server-leaf')

        fe_iface = self._make_interface(fe, 'E1/1/1')
        oob_iface = self._make_interface(oob, 'E1/1/1')
        self._make_cable(plan, fe_iface, oob_iface, zone='oob')
        # anchor: need at least one cable for export precondition
        server = self._make_server_device(plan, 'anchor-srv-110')
        self._make_cable(plan, self._make_interface(server, 'eth0'),
                         self._make_interface(fe, 'E1/1/2'))

        docs = self._get_export_docs(plan)
        conn_docs = [d for d in docs if d.get('kind') == 'Connection']

        # RED: oob-mgmt-110 currently filtered out; no Connection CRD for it
        oob_conns = [d for d in conn_docs if 'oob-mgmt-110' in str(d)]
        self.assertGreater(len(oob_conns), 0,
                           "managed->oob-mgmt cable must produce at least one Connection CRD")

    def test_connection_crd_names_both_endpoints(self):
        """T11b: Connection CRD for managed->surrogate cable names both endpoints correctly."""
        plan = self._make_plan_with_generation_state('T11b-MgdSurr')
        fe = self._make_switch_device(plan, 'fe-leaf-111', 'frontend', 'server-leaf')
        oob = self._make_switch_device(plan, 'oob-mgmt-111', 'oob-mgmt', 'server-leaf')

        fe_iface = self._make_interface(fe, 'E1/1/1')
        oob_iface = self._make_interface(oob, 'E1/1/1')
        self._make_cable(plan, fe_iface, oob_iface, zone='oob')
        server = self._make_server_device(plan, 'anchor-srv-111')
        self._make_cable(plan, self._make_interface(server, 'eth0'),
                         self._make_interface(fe, 'E1/1/2'))

        docs = self._get_export_docs(plan)
        conn_docs = [d for d in docs if d.get('kind') == 'Connection']
        oob_conns = [d for d in conn_docs if 'oob-mgmt-111' in str(d)]

        # RED: will be empty until GREEN
        self.assertGreater(len(oob_conns), 0,
                           "Connection CRD for managed->surrogate cable must exist")
        conn = oob_conns[0]
        conn_str = str(conn)
        self.assertIn('fe-leaf-111', conn_str,
                      "Connection CRD must name the managed switch endpoint")
        self.assertIn('oob-mgmt-111', conn_str,
                      "Connection CRD must name the surrogate endpoint")

    def test_no_dangling_refs_for_managed_surrogate_connection(self):
        """T11c: Every endpoint named in Connection CRDs resolves to a Switch or Server CRD."""
        plan = self._make_plan_with_generation_state('T11c-NoDangle')
        fe = self._make_switch_device(plan, 'fe-leaf-112', 'frontend', 'server-leaf')
        oob = self._make_switch_device(plan, 'oob-mgmt-112', 'oob-mgmt', 'server-leaf')

        fe_iface = self._make_interface(fe, 'E1/1/1')
        oob_iface = self._make_interface(oob, 'E1/1/1')
        self._make_cable(plan, fe_iface, oob_iface, zone='oob')
        server = self._make_server_device(plan, 'anchor-srv-112')
        self._make_cable(plan, self._make_interface(server, 'eth0'),
                         self._make_interface(fe, 'E1/1/2'))

        docs = self._get_export_docs(plan)
        switch_names = {d['metadata']['name'] for d in docs if d.get('kind') == 'Switch'}
        server_names = {d['metadata']['name'] for d in docs if d.get('kind') == 'Server'}
        known_endpoints = switch_names | server_names

        for conn in (d for d in docs if d.get('kind') == 'Connection'):
            spec = conn.get('spec', {})
            # unbundled: check switch and server port fields
            unbundled = spec.get('unbundled', {})
            link = unbundled.get('link', {})
            for side in ('switch', 'server'):
                port = link.get(side, {}).get('port', '')
                if port:
                    device_name = port.split('/')[0]
                    self.assertIn(
                        device_name, known_endpoints,
                        f"Connection endpoint '{device_name}' has no corresponding Switch/Server CRD",
                    )


# =============================================================================
# Phase 3 RED: surrogate<->surrogate exclusion (T12) — explicit per Dev C
# =============================================================================

class TestSurrogateSurrogateExclusion(ManagedFabricTestBase):
    """T12: surrogate<->surrogate cables never produce Connection CRDs (silent skip).

    RED: _endpoint_is_allowed() would let both surrogates through (both have non-empty
    hedgehog_fabric in SURROGATE_SET → is_surrogate → True after GREEN). But even after
    GREEN, _determine_connection_type must return 'excluded' for surrogate<->surrogate.
    Tests are RED now because surrogate Server CRDs don't yet emit.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_surrogate_to_surrogate_cable_no_connection_crd(self):
        """T12a: Cable between two oob-mgmt switches produces NO Connection CRD."""
        plan = self._make_plan_with_generation_state('T12a-SurrSurr')
        fe = self._make_switch_device(plan, 'fe-leaf-120', 'frontend', 'server-leaf')
        oob1 = self._make_switch_device(plan, 'oob-mgmt-120a', 'oob-mgmt', 'server-leaf')
        oob2 = self._make_switch_device(plan, 'oob-mgmt-120b', 'oob-mgmt', 'server-leaf')

        # Cable between the two surrogates (zone='oob')
        self._make_cable(plan,
                         self._make_interface(oob1, 'E1/1/1'),
                         self._make_interface(oob2, 'E1/1/1'),
                         zone='oob')
        # Anchor cable so export precondition (cables exist) passes
        self._anchor_cable(plan, fe)

        docs = self._get_export_docs(plan)
        conn_docs = [d for d in docs if d.get('kind') == 'Connection']
        surrogate_conns = [
            d for d in conn_docs
            if 'oob-mgmt-120a' in str(d) and 'oob-mgmt-120b' in str(d)
        ]
        self.assertEqual(len(surrogate_conns), 0,
                         "surrogate<->surrogate cable must produce NO Connection CRD")

    def test_surrogate_to_surrogate_both_appear_as_server_crds(self):
        """T12b: Both oob-mgmt devices still appear as Server CRDs even with no Connection CRD.

        RED: oob-mgmt devices not yet emitted as Server CRDs.
        """
        plan = self._make_plan_with_generation_state('T12b-SurrSurr')
        fe = self._make_switch_device(plan, 'fe-leaf-121', 'frontend', 'server-leaf')
        oob1 = self._make_switch_device(plan, 'oob-mgmt-121a', 'oob-mgmt', 'server-leaf')
        oob2 = self._make_switch_device(plan, 'oob-mgmt-121b', 'oob-mgmt', 'server-leaf')

        self._make_cable(plan,
                         self._make_interface(oob1, 'E1/1/1'),
                         self._make_interface(oob2, 'E1/1/1'),
                         zone='oob')
        self._anchor_cable(plan, fe)

        docs = self._get_export_docs(plan)
        server_names = {d['metadata']['name'] for d in docs if d.get('kind') == 'Server'}

        self.assertIn('oob-mgmt-121a', server_names,
                      "First oob-mgmt switch must appear as Server CRD even with no Connection CRD")
        self.assertIn('oob-mgmt-121b', server_names,
                      "Second oob-mgmt switch must appear as Server CRD even with no Connection CRD")


# =============================================================================
# Phase 3 RED: server<->surrogate exclusion (T13) — explicit per Dev C
# =============================================================================

class TestServerSurrogateExclusion(ManagedFabricTestBase):
    """T13: server<->surrogate (e.g. BMC->oob-mgmt) cables never produce Connection CRDs.

    Per #249/#252: server<->surrogate links are out of scope for this epic.
    Only managed-switch<->surrogate links produce Connection CRDs.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_server_to_surrogate_cable_no_connection_crd(self):
        """T13a: server->oob-mgmt cable (zone='oob') produces NO Connection CRD."""
        plan = self._make_plan_with_generation_state('T13a-SrvSurr')
        fe = self._make_switch_device(plan, 'fe-leaf-130', 'frontend', 'server-leaf')
        oob = self._make_switch_device(plan, 'oob-mgmt-130', 'oob-mgmt', 'server-leaf')
        server = self._make_server_device(plan, 'gpu-server-130')

        # server -> oob-mgmt cable (zone='oob')
        self._make_cable(plan,
                         self._make_interface(server, 'eth-bmc'),
                         self._make_interface(oob, 'E1/1/1'),
                         zone='oob')
        # anchor cable on managed switch so export precondition passes
        self._make_cable(plan,
                         self._make_interface(server, 'eth0'),
                         self._make_interface(fe, 'E1/1/1'))

        docs = self._get_export_docs(plan)
        conn_docs = [d for d in docs if d.get('kind') == 'Connection']
        srv_oob_conns = [
            d for d in conn_docs
            if 'oob-mgmt-130' in str(d) and 'gpu-server-130' in str(d)
        ]
        self.assertEqual(len(srv_oob_conns), 0,
                         "server->oob-mgmt cable must NOT produce a Connection CRD "
                         "(server<->surrogate out of scope per #249/#252)")

    def test_server_to_surrogate_zone_server_no_connection_crd(self):
        """T13b: server->oob-mgmt cable with zone='server' also produces NO Connection CRD."""
        plan = self._make_plan_with_generation_state('T13b-SrvSurr')
        fe = self._make_switch_device(plan, 'fe-leaf-131', 'frontend', 'server-leaf')
        oob = self._make_switch_device(plan, 'oob-mgmt-131', 'oob-mgmt', 'server-leaf')
        server = self._make_server_device(plan, 'gpu-server-131')

        # server -> oob-mgmt cable (zone='server' — wrong zone but still must be excluded)
        self._make_cable(plan,
                         self._make_interface(server, 'eth-bmc'),
                         self._make_interface(oob, 'E1/1/1'),
                         zone='server')
        self._make_cable(plan,
                         self._make_interface(server, 'eth0'),
                         self._make_interface(fe, 'E1/1/1'))

        docs = self._get_export_docs(plan)
        conn_docs = [d for d in docs if d.get('kind') == 'Connection']
        srv_oob_conns = [
            d for d in conn_docs
            if 'oob-mgmt-131' in str(d) and 'gpu-server-131' in str(d)
        ]
        self.assertEqual(len(srv_oob_conns), 0,
                         "server->oob-mgmt cable must NOT produce a Connection CRD "
                         "regardless of zone tag (server<->surrogate out of scope)")

    def test_non_surrogate_unmanaged_excluded_entirely(self):
        """T13c: in-band-mgmt device produces no Server CRD, no Switch CRD, no Connection CRD."""
        plan = self._make_plan_with_generation_state('T13c-Excluded')
        fe = self._make_switch_device(plan, 'fe-leaf-132', 'frontend', 'server-leaf')
        inband = self._make_switch_device(plan, 'inband-leaf-132', 'in-band-mgmt', 'server-leaf')
        server = self._make_server_device(plan, 'gpu-server-132')

        self._make_cable(plan,
                         self._make_interface(server, 'eth0'),
                         self._make_interface(fe, 'E1/1/1'))
        self._make_cable(plan,
                         self._make_interface(server, 'eth1'),
                         self._make_interface(inband, 'E1/1/1'))

        docs = self._get_export_docs(plan)
        all_names = {d.get('metadata', {}).get('name', '') for d in docs if d}

        self.assertNotIn('inband-leaf-132', all_names,
                         "in-band-mgmt device must not appear in any CRD")


# =============================================================================
# T14: Constraint #3 — server excluded from export if ONLY surrogate connections
# (DIET-254 Phase 5)
# =============================================================================

class TestServerExportScopeConstraint3(ManagedFabricTestBase):
    """
    T14: A server must NOT appear in Server CRDs solely because it has surrogate
    (oob-mgmt) connections. Servers appear in full-plan export only if they have
    at least one export-eligible (managed-switch) connection.

    Source: DIET-254 kickoff, Dev C constraint #3.

    Expected failure reasons (RED state):
      - T14a: _generate_servers() with no filter_ids includes ALL plan servers
        regardless of connections. A server with only oob-mgmt connections is
        incorrectly included in the full-plan Server CRD list.
      - T14b: passes trivially (server with managed conn always included) — used
        as sanity anchor alongside T14a.
      - T14c: variant of T14a with multiple servers, confirms filtering is correct
        when mixed-connectivity servers exist in the same plan.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    # -------------------------------------------------------------------------
    # T14a: server with ONLY oob-mgmt connections excluded from full-plan export
    # Expected failure: _generate_servers() includes all plan servers; server
    # with only surrogate connections is incorrectly included.
    # -------------------------------------------------------------------------

    def test_server_with_only_surrogate_connection_excluded_from_export(self):
        """
        T14a: A server whose only cable goes to an oob-mgmt (surrogate) switch
        must NOT appear in Server CRDs in full-plan export.
        """
        plan = self._make_plan_with_generation_state('T14a-SurrogateOnly')
        fe = self._make_switch_device(plan, 'fe-leaf-200', 'frontend', 'server-leaf')
        oob = self._make_switch_device(plan, 'oob-mgmt-200', 'oob-mgmt', 'server-leaf')

        # Server A: connects to BOTH managed and oob-mgmt (should appear)
        server_a = self._make_server_device(plan, 'server-200a')
        self._make_cable(plan, self._make_interface(server_a, 'eth0'),
                         self._make_interface(fe, 'E1/1/1'))
        self._make_cable(plan, self._make_interface(server_a, 'bmc'),
                         self._make_interface(oob, 'E1/1/1'))

        # Server B: connects ONLY to oob-mgmt (must NOT appear)
        server_b = self._make_server_device(plan, 'server-200b')
        self._make_cable(plan, self._make_interface(server_b, 'bmc'),
                         self._make_interface(oob, 'E1/1/2'))

        docs = self._get_export_docs(plan)
        server_names = {d['metadata']['name'] for d in docs if d and d.get('kind') == 'Server'}

        # Server A must appear (has managed switch connection)
        self.assertIn(
            'server-200a', server_names,
            "server-200a has a managed switch connection and must appear in Server CRDs",
        )

        # Server B must NOT appear (only oob-mgmt connection — surrogate only)
        self.assertNotIn(
            'server-200b', server_names,
            "server-200b has ONLY a surrogate (oob-mgmt) connection and must NOT appear "
            "in Server CRDs per DIET-254 constraint #3",
        )

    # -------------------------------------------------------------------------
    # T14b: server with managed + surrogate connections IS included (sanity check)
    # Expected to PASS even before GREEN — existing behavior is correct here.
    # Included to anchor T14a; if T14a is fixed, T14b must remain green.
    # -------------------------------------------------------------------------

    def test_server_with_managed_and_surrogate_connections_included(self):
        """
        T14b: A server with both managed-switch and oob-mgmt connections must
        appear in Server CRDs (managed connection qualifies it for export scope).
        """
        plan = self._make_plan_with_generation_state('T14b-Mixed')
        fe = self._make_switch_device(plan, 'fe-leaf-201', 'frontend', 'server-leaf')
        oob = self._make_switch_device(plan, 'oob-mgmt-201', 'oob-mgmt', 'server-leaf')
        server = self._make_server_device(plan, 'server-201')

        self._make_cable(plan, self._make_interface(server, 'eth0'),
                         self._make_interface(fe, 'E1/1/1'))
        self._make_cable(plan, self._make_interface(server, 'bmc'),
                         self._make_interface(oob, 'E1/1/1'))

        docs = self._get_export_docs(plan)
        server_names = {d['metadata']['name'] for d in docs if d and d.get('kind') == 'Server'}

        self.assertIn(
            'server-201', server_names,
            "server-201 has a managed switch connection and must appear in Server CRDs",
        )

    # -------------------------------------------------------------------------
    # T14c: multiple servers with mixed connectivity — only export-eligible appear
    # Expected failure: same as T14a — full-plan export does not filter servers.
    # -------------------------------------------------------------------------

    def test_mixed_plan_only_export_eligible_servers_appear(self):
        """
        T14c: In a plan with 3 servers:
          - server-A: connected to managed switch only → must appear
          - server-B: connected to managed switch + oob-mgmt → must appear
          - server-C: connected to oob-mgmt only → must NOT appear
        """
        plan = self._make_plan_with_generation_state('T14c-MixedPlan')
        fe = self._make_switch_device(plan, 'fe-leaf-202', 'frontend', 'server-leaf')
        oob = self._make_switch_device(plan, 'oob-mgmt-202', 'oob-mgmt', 'server-leaf')

        server_a = self._make_server_device(plan, 'server-202a')
        self._make_cable(plan, self._make_interface(server_a, 'eth0'),
                         self._make_interface(fe, 'E1/1/1'))

        server_b = self._make_server_device(plan, 'server-202b')
        self._make_cable(plan, self._make_interface(server_b, 'eth0'),
                         self._make_interface(fe, 'E1/1/2'))
        self._make_cable(plan, self._make_interface(server_b, 'bmc'),
                         self._make_interface(oob, 'E1/1/1'))

        server_c = self._make_server_device(plan, 'server-202c')
        self._make_cable(plan, self._make_interface(server_c, 'bmc'),
                         self._make_interface(oob, 'E1/1/2'))

        docs = self._get_export_docs(plan)
        server_names = {d['metadata']['name'] for d in docs if d and d.get('kind') == 'Server'}

        self.assertIn('server-202a', server_names,
                      "server-202a (managed only) must appear in Server CRDs")
        self.assertIn('server-202b', server_names,
                      "server-202b (managed + surrogate) must appear in Server CRDs")
        self.assertNotIn(
            'server-202c', server_names,
            "server-202c (surrogate only) must NOT appear in Server CRDs "
            "per DIET-254 constraint #3",
        )


# =============================================================================
# DIET-539 RED: MCLAG/ESLAG typing guard for zone='server' dispatch
# =============================================================================

class MCLAGTypingGuardTestCase(ManagedFabricTestBase):
    """
    DIET-539: RED tests for the MCLAG/ESLAG redundancy-type guard.

    The latent bug: _generate_connection_crds dispatch at lines 1415-1436 of
    yaml_generator.py unconditionally emits spec.mclag / spec.eslag for the
    'else' (different-switch) arms of the 2-link and 3+-link paths when cables
    have hedgehog_zone='server'.

    The fix adds _get_switch_redundancy_type() which gates spec.mclag/eslag
    on actual PlanSwitchClass.redundancy_type intent, falling back to
    N x spec.unbundled when the type is absent or the lookup fails.

    T1/T3 are GREEN guards (coincidentally correct today, must stay green after fix).
    T2/T4/T5/T6 are RED (fail today due to the missing guard).
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def _make_switch_class(self, plan, switch_device, redundancy_type=None):
        """Create a PlanSwitchClass with switch_class_id == switch_device.name.

        switch_class_id must equal the device's hedgehog_class CF so the
        _get_switch_redundancy_type helper can look up the class by name.
        objects.create() bypasses clean(), so redundancy_group=None is allowed
        even when redundancy_type is set.
        """
        return PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id=switch_device.name,
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.frontend_ext,
            calculated_quantity=None,
            override_quantity=1,
            uplink_ports_per_switch=0,
            mclag_pair=False,
            redundancy_type=redundancy_type,
        )

    def _get_conn_crds(self, plan):
        docs = self._get_export_docs(plan)
        return [d for d in docs if d and d.get('kind') == 'Connection']

    # ------------------------------------------------------------------
    # T1: True MCLAG 2-link — GREEN guard (must stay green after fix)
    # ------------------------------------------------------------------

    def test_t1_true_mclag_2link_emits_spec_mclag(self):
        """T1: 2 zone='server' cables to different switches, both with redundancy_type='mclag'.

        Expected: 1 spec.mclag CRD with 2 links.
        GREEN today (unconditional mclag path fires); must remain green after fix so the
        guard does not break the legitimate MCLAG case.
        """
        plan = self._make_plan_with_generation_state('T539-T1-MCLAG-2link')
        sw1 = self._make_switch_device(plan, 'fe-sw-539-t1a', 'frontend')
        sw2 = self._make_switch_device(plan, 'fe-sw-539-t1b', 'frontend')
        srv = self._make_server_device(plan, 'srv-539-t1')
        self._make_switch_class(plan, sw1, redundancy_type='mclag')
        self._make_switch_class(plan, sw2, redundancy_type='mclag')
        self._make_cable(plan, self._make_interface(srv, 'eth0'),
                         self._make_interface(sw1, 'E1/1'))
        self._make_cable(plan, self._make_interface(srv, 'eth1'),
                         self._make_interface(sw2, 'E1/1'))

        conns = self._get_conn_crds(plan)
        mclag_conns = [c for c in conns if 'mclag' in c.get('spec', {})]
        self.assertEqual(len(mclag_conns), 1,
            f"True MCLAG 2-link must emit exactly 1 spec.mclag CRD; got {len(mclag_conns)}")
        self.assertEqual(len(mclag_conns[0]['spec']['mclag']['links']), 2,
            "spec.mclag.links must have exactly 2 entries")

    # ------------------------------------------------------------------
    # T2: Non-MCLAG 2-link — RED (must emit 2 x spec.unbundled, not spec.mclag)
    # ------------------------------------------------------------------

    def test_t2_non_mclag_2link_emits_unbundled(self):
        """T2: 2 zone='server' cables to different switches, redundancy_type=None.

        Expected: 2 spec.unbundled CRDs, 0 spec.mclag CRDs.
        RED today: current code unconditionally emits spec.mclag for the 2-link
        different-switch arm regardless of PlanSwitchClass.redundancy_type.
        Implementation seam: _get_switch_redundancy_type(switch1) must return ''
        when redundancy_type is None, causing the else arm to emit unbundled.
        """
        plan = self._make_plan_with_generation_state('T539-T2-NonMCLAG-2link')
        sw1 = self._make_switch_device(plan, 'fe-sw-539-t2a', 'frontend')
        sw2 = self._make_switch_device(plan, 'fe-sw-539-t2b', 'frontend')
        srv = self._make_server_device(plan, 'srv-539-t2')
        self._make_switch_class(plan, sw1, redundancy_type=None)
        self._make_switch_class(plan, sw2, redundancy_type=None)
        self._make_cable(plan, self._make_interface(srv, 'eth0'),
                         self._make_interface(sw1, 'E1/1'))
        self._make_cable(plan, self._make_interface(srv, 'eth1'),
                         self._make_interface(sw2, 'E1/1'))

        conns = self._get_conn_crds(plan)
        mclag_conns = [c for c in conns if 'mclag' in c.get('spec', {})]
        unbundled_conns = [c for c in conns if 'unbundled' in c.get('spec', {})]

        self.assertEqual(len(mclag_conns), 0,
            f"Non-MCLAG 2-link must emit 0 spec.mclag CRDs; got {len(mclag_conns)}")
        self.assertEqual(len(unbundled_conns), 2,
            f"Non-MCLAG 2-link must emit 2 spec.unbundled CRDs; got {len(unbundled_conns)}")
        for crd in unbundled_conns:
            self.assertIn('--unbundled--', crd['metadata']['name'],
                "'--unbundled--' must appear in each fallback CRD name")

    # ------------------------------------------------------------------
    # T3: True ESLAG 3+-link — GREEN guard (must stay green after fix)
    # ------------------------------------------------------------------

    def test_t3_true_eslag_multilink_emits_spec_eslag(self):
        """T3: 4 zone='server' cables to 2 switches, both with redundancy_type='eslag'.

        Expected: 1 spec.eslag CRD with 4 links.
        GREEN today (unconditional eslag path fires); must remain green after fix so
        the guard does not break the legitimate ESLAG case.
        """
        plan = self._make_plan_with_generation_state('T539-T3-ESLAG-multi')
        sw1 = self._make_switch_device(plan, 'fe-sw-539-t3a', 'frontend')
        sw2 = self._make_switch_device(plan, 'fe-sw-539-t3b', 'frontend')
        srv = self._make_server_device(plan, 'srv-539-t3')
        self._make_switch_class(plan, sw1, redundancy_type='eslag')
        self._make_switch_class(plan, sw2, redundancy_type='eslag')
        # 2 cables to sw1, 2 cables to sw2
        self._make_cable(plan, self._make_interface(srv, 'eth0'),
                         self._make_interface(sw1, 'E1/1'))
        self._make_cable(plan, self._make_interface(srv, 'eth1'),
                         self._make_interface(sw1, 'E1/2'))
        self._make_cable(plan, self._make_interface(srv, 'eth2'),
                         self._make_interface(sw2, 'E1/1'))
        self._make_cable(plan, self._make_interface(srv, 'eth3'),
                         self._make_interface(sw2, 'E1/2'))

        conns = self._get_conn_crds(plan)
        eslag_conns = [c for c in conns if 'eslag' in c.get('spec', {})]
        self.assertEqual(len(eslag_conns), 1,
            f"True ESLAG multi-link must emit exactly 1 spec.eslag CRD; got {len(eslag_conns)}")
        self.assertEqual(len(eslag_conns[0]['spec']['eslag']['links']), 4,
            "spec.eslag.links must have exactly 4 entries")

    # ------------------------------------------------------------------
    # T4: Non-ESLAG 3+-link — RED (must emit N x spec.unbundled, not spec.eslag)
    # ------------------------------------------------------------------

    def test_t4_non_eslag_multilink_emits_unbundled(self):
        """T4: 4 zone='server' cables to 2 switches, redundancy_type=None.

        Expected: 4 spec.unbundled CRDs, 0 spec.eslag CRDs.
        RED today: current code unconditionally emits spec.eslag for the 3+-link
        multiple-switch arm regardless of PlanSwitchClass.redundancy_type.
        Implementation seam: _get_switch_redundancy_type(first_switch) must return ''
        when redundancy_type is None, causing the else arm to emit unbundled per link.
        """
        plan = self._make_plan_with_generation_state('T539-T4-NonESLAG-multi')
        sw1 = self._make_switch_device(plan, 'fe-sw-539-t4a', 'frontend')
        sw2 = self._make_switch_device(plan, 'fe-sw-539-t4b', 'frontend')
        srv = self._make_server_device(plan, 'srv-539-t4')
        self._make_switch_class(plan, sw1, redundancy_type=None)
        self._make_switch_class(plan, sw2, redundancy_type=None)
        self._make_cable(plan, self._make_interface(srv, 'eth0'),
                         self._make_interface(sw1, 'E1/1'))
        self._make_cable(plan, self._make_interface(srv, 'eth1'),
                         self._make_interface(sw1, 'E1/2'))
        self._make_cable(plan, self._make_interface(srv, 'eth2'),
                         self._make_interface(sw2, 'E1/1'))
        self._make_cable(plan, self._make_interface(srv, 'eth3'),
                         self._make_interface(sw2, 'E1/2'))

        conns = self._get_conn_crds(plan)
        eslag_conns = [c for c in conns if 'eslag' in c.get('spec', {})]
        unbundled_conns = [c for c in conns if 'unbundled' in c.get('spec', {})]

        self.assertEqual(len(eslag_conns), 0,
            f"Non-ESLAG multi-link must emit 0 spec.eslag CRDs; got {len(eslag_conns)}")
        self.assertEqual(len(unbundled_conns), 4,
            f"Non-ESLAG multi-link must emit 4 spec.unbundled CRDs; got {len(unbundled_conns)}")
        for crd in unbundled_conns:
            self.assertIn('--unbundled--', crd['metadata']['name'],
                "'--unbundled--' must appear in each fallback CRD name")

    # ------------------------------------------------------------------
    # T5: Missing PlanSwitchClass — fallback to unbundled (RED)
    # ------------------------------------------------------------------

    def test_t5_missing_switch_class_fallback_to_unbundled(self):
        """T5: 2 zone='server' cables to different switches with NO PlanSwitchClass.

        Expected: 2 spec.unbundled CRDs, 0 spec.mclag CRDs; no exception raised.
        RED today: current code emits spec.mclag regardless of switch class existence.
        Implementation seam: _get_switch_redundancy_type must catch DoesNotExist
        and return '' so the caller falls back to unbundled.
        """
        plan = self._make_plan_with_generation_state('T539-T5-NoClass')
        sw1 = self._make_switch_device(plan, 'fe-sw-539-t5a', 'frontend')
        sw2 = self._make_switch_device(plan, 'fe-sw-539-t5b', 'frontend')
        srv = self._make_server_device(plan, 'srv-539-t5')
        # Intentionally NO PlanSwitchClass for either switch.
        self._make_cable(plan, self._make_interface(srv, 'eth0'),
                         self._make_interface(sw1, 'E1/1'))
        self._make_cable(plan, self._make_interface(srv, 'eth1'),
                         self._make_interface(sw2, 'E1/1'))

        conns = self._get_conn_crds(plan)
        mclag_conns = [c for c in conns if 'mclag' in c.get('spec', {})]
        unbundled_conns = [c for c in conns if 'unbundled' in c.get('spec', {})]

        self.assertEqual(len(mclag_conns), 0,
            f"Missing PlanSwitchClass must fall back to unbundled, not mclag; "
            f"got {len(mclag_conns)} spec.mclag CRDs")
        self.assertEqual(len(unbundled_conns), 2,
            f"Missing PlanSwitchClass must emit 2 spec.unbundled CRDs; "
            f"got {len(unbundled_conns)}")

    # ------------------------------------------------------------------
    # T6: Helper returns '' when plan is None (RED — helper doesn't exist yet)
    # ------------------------------------------------------------------

    def test_t6_helper_returns_empty_string_when_plan_is_none(self):
        """T6: _get_switch_redundancy_type returns '' when self.plan is None.

        RED today: _get_switch_redundancy_type does not exist on YAMLGenerator;
        calling it raises AttributeError.
        Implementation seam: helper must guard self.plan is None before any DB
        lookup and return '' to signal 'not mclag/eslag'.

        Note: YAMLGenerator.__init__ requires a non-None plan to resolve managed
        fabrics; we construct with a real plan then null it out post-construction
        to exercise the helper's null-plan guard in isolation.
        """
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        from unittest.mock import MagicMock
        plan = self._make_plan_with_generation_state('T539-T6-PlanNone')
        sw = self._make_switch_device(plan, 'fe-sw-539-t6', 'frontend')
        self._make_cable(plan, self._make_interface(
            self._make_server_device(plan, 'srv-539-t6'), 'eth0'),
            self._make_interface(sw, 'E1/1'))
        generator = YAMLGenerator(plan=plan)
        generator.plan = None  # simulate the plan-less code path
        device = MagicMock()
        result = generator._get_switch_redundancy_type(device)
        self.assertEqual(result, '',
            "_get_switch_redundancy_type must return '' when plan is None")
