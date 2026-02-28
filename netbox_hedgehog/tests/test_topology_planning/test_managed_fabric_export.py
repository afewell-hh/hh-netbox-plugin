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
                'optic_type': 'QSFP-DD',
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

    def test_unmanaged_switch_absent_from_yaml(self):
        """T1b: oob-mgmt switch is absent from the YAML export entirely."""
        plan = self._make_plan_with_generation_state('T1-Mixed-Absent')
        fe = self._make_switch_device(plan, 'fe-leaf-002', 'frontend', 'server-leaf')
        self._make_switch_device(plan, 'oob-leaf-002', 'oob-mgmt', 'server-leaf')
        self._anchor_cable(plan, fe)

        response = self.client.get(self._export_url(plan))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('oob-leaf-002', response.content.decode())


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
        """T2a: Cable to managed switch appears; cable to unmanaged switch does not."""
        plan = self._make_plan_with_generation_state('T2-Filter')
        fe_switch = self._make_switch_device(plan, 'fe-leaf-010', 'frontend', 'server-leaf')
        oob_switch = self._make_switch_device(plan, 'oob-leaf-010', 'oob-mgmt', 'server-leaf')
        server = self._make_server_device(plan, 'gpu-server-010')

        fe_iface = self._make_interface(fe_switch, 'E1/1/1')
        oob_iface = self._make_interface(oob_switch, 'E1/1/1')
        srv_iface1 = self._make_interface(server, 'eth0')
        srv_iface2 = self._make_interface(server, 'eth1')

        self._make_cable(plan, srv_iface1, fe_iface)
        self._make_cable(plan, srv_iface2, oob_iface)

        docs = self._get_export_docs(plan)
        conn_docs = [d for d in docs if d and d.get('kind') == 'Connection']
        all_conn_yaml = str(conn_docs)

        self.assertIn('gpu-server-010', all_conn_yaml)
        self.assertIn('fe-leaf-010', all_conn_yaml)
        self.assertNotIn('oob-leaf-010', all_conn_yaml)

    def test_server_appears_regardless_of_mgmt_connections(self):
        """T2b: Server CRD is generated even when all its cables go to unmanaged switches."""
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
        self.assertTrue(
            any('gpu-server-011' in str(d) for d in server_docs),
            "Server CRD should appear even when connected only to unmanaged switches.",
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
        """T3: Only the 2 managed cables produce Connection CRDs, not the 2 unmanaged ones.

        Uses 4 separate servers (1 cable each) so each cable produces its own unbundled
        Connection CRD. The 2 unmanaged cables (server→oob_switch) are filtered out,
        leaving exactly 2 Connection CRDs.
        """
        plan = self._make_plan_with_generation_state('T3-Count')
        fe_switch = self._make_switch_device(plan, 'fe-leaf-020', 'frontend', 'server-leaf')
        oob_switch = self._make_switch_device(plan, 'oob-leaf-020', 'oob-mgmt', 'server-leaf')

        srv1 = self._make_server_device(plan, 'gpu-server-020a')
        srv2 = self._make_server_device(plan, 'gpu-server-020b')
        srv3 = self._make_server_device(plan, 'gpu-server-020c')
        srv4 = self._make_server_device(plan, 'gpu-server-020d')

        fe_iface1 = self._make_interface(fe_switch, 'E1/1/1')
        fe_iface2 = self._make_interface(fe_switch, 'E1/1/2')
        oob_iface1 = self._make_interface(oob_switch, 'E1/1/1')
        oob_iface2 = self._make_interface(oob_switch, 'E1/1/2')

        self._make_cable(plan, self._make_interface(srv1, 'eth0'), fe_iface1)    # managed cable 1
        self._make_cable(plan, self._make_interface(srv2, 'eth0'), fe_iface2)    # managed cable 2
        self._make_cable(plan, self._make_interface(srv3, 'eth0'), oob_iface1)   # unmanaged cable 1
        self._make_cable(plan, self._make_interface(srv4, 'eth0'), oob_iface2)   # unmanaged cable 2

        docs = self._get_export_docs(plan)
        conn_count = len([d for d in docs if d and d.get('kind') == 'Connection'])
        self.assertEqual(conn_count, 2,
            f"Expected 2 Connection CRDs (managed cables only), got {conn_count}.")


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

    def test_oob_choice_present_in_form_with_deprecated_label(self):
        """T9a: The PlanSwitchClass add form renders 'oob' choice with DEPRECATED label.

        RED: current OOB label is 'Out-of-Band' without any DEPRECATED marker.
        GREEN: label should contain 'DEPRECATED' as part of the Out-of-Band entry.
        The assertion checks for the OOB label text including DEPRECATED, not just
        any occurrence of DEPRECATED on the page.
        """
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="oob"')
        # Must assert the OOB *label* (rendered as option text) contains DEPRECATED.
        # 'Out-of-Band (DEPRECATED' will appear only after the GREEN implementation.
        # Currently the label is just 'Out-of-Band' so this assertion fails (RED).
        self.assertContains(response, 'Out-of-Band (DEPRECATED')

    def test_oob_mgmt_export_no_dangling_references(self):
        """T9b: Cables to oob-mgmt switches do not appear as Connection CRDs."""
        plan = self._make_plan_with_generation_state('T9-OobMgmt')
        fe_switch = self._make_switch_device(plan, 'fe-leaf-050', 'frontend', 'server-leaf')
        oob_switch = self._make_switch_device(plan, 'oob-mgmt-050', 'oob-mgmt', 'server-leaf')
        server = self._make_server_device(plan, 'gpu-server-050')

        fe_iface = self._make_interface(fe_switch, 'E1/1/1')
        oob_iface = self._make_interface(oob_switch, 'E1/1/1')
        srv_iface1 = self._make_interface(server, 'eth0')
        srv_iface2 = self._make_interface(server, 'eth1')

        self._make_cable(plan, srv_iface1, fe_iface)
        self._make_cable(plan, srv_iface2, oob_iface)

        response = self.client.get(self._export_url(plan))
        self.assertEqual(response.status_code, 200)
        yaml_str = response.content.decode()
        self.assertNotIn('oob-mgmt-050', yaml_str)
