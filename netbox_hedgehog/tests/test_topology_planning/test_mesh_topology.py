"""
Phase 3 RED tests for issue #308: Mesh topology support.

All tests in this file are expected to FAIL until Phase 4 (GREEN) is implemented.
Tests cover:
- PortZoneTypeChoices.MESH and TopologyModeChoices
- PlanSwitchClass.topology_mode field
- TopologyPlan.mesh_ip_pool field
- Mesh fabric invariants (mixed-mode validation)
- Spine/mesh mutual exclusion
- Mesh feasibility calculation
- PlanMeshLink model
- allocate_mesh_links() utility
- _determine_connection_type() returning 'mesh'
- Snapshot dirty-detection for mesh fields
"""

from django.test import TestCase
from django.core.exceptions import ValidationError

from dcim.models import Manufacturer, DeviceType

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanSwitchClass,
    DeviceTypeExtension,
    GenerationState,
)
from netbox_hedgehog.choices import (
    PortZoneTypeChoices,
    FabricClassChoices,
)
from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot


# =============================================================================
# Helpers
# =============================================================================

def _make_base_fixtures():
    """Return (manufacturer, device_type, device_type_ext) test fixtures."""
    mfr, _ = Manufacturer.objects.get_or_create(
        name='Mesh Test Mfg',
        defaults={'slug': 'mesh-test-mfg'},
    )
    dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr,
        model='Mesh Test Switch',
        defaults={'slug': 'mesh-test-switch'},
    )
    ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=dt,
        defaults={
            'native_speed': 400,
            'uplink_ports': 4,
            'supported_breakouts': ['1x400g'],
            'hedgehog_roles': ['server-leaf'],
        },
    )
    return mfr, dt, ext


def _make_plan(name='Mesh Test Plan'):
    return TopologyPlan.objects.create(name=name)


def _make_switch_class(plan, ext, switch_class_id='mesh-leaf-01',
                        fabric_name='backend', fabric_class=None,
                        hedgehog_role='server-leaf', **kwargs):
    if fabric_class is None:
        fabric_class = FabricClassChoices.MANAGED
    return PlanSwitchClass.objects.create(
        plan=plan,
        switch_class_id=switch_class_id,
        fabric_name=fabric_name,
        fabric_class=fabric_class,
        hedgehog_role=hedgehog_role,
        device_type_extension=ext,
        uplink_ports_per_switch=0,
        **kwargs,
    )


# =============================================================================
# Class 1: MeshChoicesTests — pure unit, no DB
# =============================================================================

class MeshChoicesTests(TestCase):
    """Unit tests for mesh-related choice constants (no DB)."""

    def test_mesh_zone_type_choice_exists(self):
        self.assertTrue(hasattr(PortZoneTypeChoices, 'MESH'))
        self.assertEqual(PortZoneTypeChoices.MESH, 'mesh')

    def test_mesh_topology_mode_choices_exist(self):
        from netbox_hedgehog.choices import TopologyModeChoices
        self.assertTrue(hasattr(TopologyModeChoices, 'SPINE_LEAF'))
        self.assertTrue(hasattr(TopologyModeChoices, 'PREFER_MESH'))


# =============================================================================
# Class 2: MeshTopologyModeFieldTests — DB
# =============================================================================

class MeshTopologyModeFieldTests(TestCase):
    """Tests for topology_mode field on PlanSwitchClass and mesh_ip_pool on TopologyPlan."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext = _make_base_fixtures()
        cls.plan = _make_plan('Topology Mode Plan')

    def test_topology_mode_default_is_spine_leaf(self):
        sc = _make_switch_class(self.plan, self.ext, switch_class_id='tmd-leaf-01')
        self.assertEqual(sc.topology_mode, 'spine-leaf')

    def test_topology_mode_prefer_mesh_valid(self):
        sc = _make_switch_class(self.plan, self.ext, switch_class_id='tmd-leaf-02')
        sc.topology_mode = 'prefer-mesh'
        sc.full_clean()
        sc.save()
        sc.refresh_from_db()
        self.assertEqual(sc.topology_mode, 'prefer-mesh')

    def test_mesh_ip_pool_optional(self):
        plan = _make_plan('Mesh IP Pool Optional')
        # Should save without error when mesh_ip_pool is not set
        plan.save()

    def test_mesh_ip_pool_stores_cidr(self):
        plan = _make_plan('Mesh IP Pool CIDR')
        plan.mesh_ip_pool = '172.30.128.0/24'
        plan.save()
        plan.refresh_from_db()
        self.assertEqual(plan.mesh_ip_pool, '172.30.128.0/24')


# =============================================================================
# Class 3: MeshFabricInvariantTests — DB
# =============================================================================

class MeshFabricInvariantTests(TestCase):
    """Tests for mixed topology_mode validation within a fabric."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext = _make_base_fixtures()

    def test_first_switch_class_no_error(self):
        plan = _make_plan('Invariant Plan A')
        sc = _make_switch_class(plan, self.ext, switch_class_id='inv-leaf-01')
        sc.topology_mode = 'prefer-mesh'
        sc.full_clean()
        sc.save()

    def test_two_prefer_mesh_same_fabric_ok(self):
        plan = _make_plan('Invariant Plan B')
        sc1 = _make_switch_class(plan, self.ext, switch_class_id='inv-leaf-01')
        sc1.topology_mode = 'prefer-mesh'
        sc1.save()

        sc2 = PlanSwitchClass(
            plan=plan,
            switch_class_id='inv-leaf-02',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
        )
        sc2.full_clean()
        sc2.save()

    def test_mixed_mode_same_fabric_rejected(self):
        plan = _make_plan('Invariant Plan C')
        sc1 = _make_switch_class(plan, self.ext, switch_class_id='inv-leaf-01')
        sc1.topology_mode = 'prefer-mesh'
        sc1.save()

        sc2 = PlanSwitchClass(
            plan=plan,
            switch_class_id='inv-leaf-02',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='spine-leaf',
        )
        with self.assertRaises(ValidationError):
            sc2.full_clean()

    def test_invariant_scoped_to_fabric(self):
        plan = _make_plan('Invariant Plan D')
        sc_alpha = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='alpha-leaf-01',
            fabric_name='alpha',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
        )
        sc_beta = PlanSwitchClass(
            plan=plan,
            switch_class_id='beta-leaf-01',
            fabric_name='beta',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='spine-leaf',
        )
        sc_beta.full_clean()
        sc_beta.save()


# =============================================================================
# Class 4: MeshSpineLeafMutualExclusionTests — DB
# =============================================================================

class MeshSpineLeafMutualExclusionTests(TestCase):
    """Tests that spine and prefer-mesh classes cannot coexist in the same fabric."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext = _make_base_fixtures()

    def test_prefer_mesh_blocked_when_spine_exists(self):
        plan = _make_plan('Mutex Plan A')
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='spine-01',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='spine',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
        )
        sc_mesh = PlanSwitchClass(
            plan=plan,
            switch_class_id='mesh-leaf-01',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
        )
        with self.assertRaises(ValidationError):
            sc_mesh.full_clean()

    def test_spine_blocked_when_prefer_mesh_exists(self):
        plan = _make_plan('Mutex Plan B')
        sc_mesh = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='mesh-leaf-01',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
        )
        sc_spine = PlanSwitchClass(
            plan=plan,
            switch_class_id='spine-01',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='spine',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
        )
        with self.assertRaises(ValidationError):
            sc_spine.full_clean()


# =============================================================================
# Class 5: MeshFeasibilityTests — DB
# =============================================================================

class MeshFeasibilityTests(TestCase):
    """Tests for mesh feasibility key in update_plan_calculations() result."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext = _make_base_fixtures()

    def _make_prefer_mesh_class(self, plan, switch_class_id, override_quantity=1):
        return PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id=switch_class_id,
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
            override_quantity=override_quantity,
        )

    def test_2_switch_mesh_feasible(self):
        from netbox_hedgehog.utils.topology_calculations import update_plan_calculations
        plan = _make_plan('Feasibility 2-switch')
        self._make_prefer_mesh_class(plan, 'mf-leaf-01', override_quantity=1)
        self._make_prefer_mesh_class(plan, 'mf-leaf-02', override_quantity=1)
        result = update_plan_calculations(plan)
        self.assertIn('mesh_feasibility', result)
        self.assertTrue(result['mesh_feasibility']['backend']['feasible'])

    def test_4_switch_mesh_infeasible(self):
        from netbox_hedgehog.utils.topology_calculations import update_plan_calculations
        plan = _make_plan('Feasibility 4-switch')
        for i in range(1, 5):
            self._make_prefer_mesh_class(plan, f'mf-leaf-0{i}', override_quantity=1)
        result = update_plan_calculations(plan)
        self.assertIn('mesh_feasibility', result)
        fab = result['mesh_feasibility']['backend']
        self.assertFalse(fab['feasible'])
        self.assertFalse(fab['has_spine_fallback'])

    def test_infeasible_with_spine_fallback(self):
        from netbox_hedgehog.utils.topology_calculations import update_plan_calculations
        plan = _make_plan('Feasibility fallback')
        for i in range(1, 5):
            self._make_prefer_mesh_class(plan, f'mf-leaf-0{i}', override_quantity=1)
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='be-spine-01',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='spine',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
        )
        result = update_plan_calculations(plan)
        fab = result['mesh_feasibility']['backend']
        self.assertFalse(fab['feasible'])
        self.assertTrue(fab['has_spine_fallback'])


# =============================================================================
# Class 6: PlanMeshLinkModelTests — DB
# =============================================================================

class PlanMeshLinkModelTests(TestCase):
    """Tests for PlanMeshLink model (import inside methods so error is scoped)."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext = _make_base_fixtures()
        cls.plan = _make_plan('MeshLink Plan')
        cls.sc_a = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='ml-leaf-01',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=cls.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
        )
        cls.sc_b = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='ml-leaf-02',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=cls.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
        )

    def test_plan_mesh_link_importable(self):
        from netbox_hedgehog.models.topology_planning import PlanMeshLink  # noqa: F401

    def test_plan_mesh_link_fields(self):
        from netbox_hedgehog.models.topology_planning import PlanMeshLink
        link = PlanMeshLink(
            plan=self.plan,
            switch_class_a=self.sc_a,
            switch_class_b=self.sc_b,
            subnet='172.30.128.0/31',
            link_index=0,
            leaf1_port='E1/1',
            leaf2_port='E1/1',
            leaf1_name='ml-leaf-01-01',
            leaf2_name='ml-leaf-02-01',
        )
        link.full_clean()
        link.save()
        self.assertEqual(link.subnet, '172.30.128.0/31')

    def test_subnet_must_be_31(self):
        from netbox_hedgehog.models.topology_planning import PlanMeshLink
        link = PlanMeshLink(
            plan=self.plan,
            switch_class_a=self.sc_a,
            switch_class_b=self.sc_b,
            subnet='10.0.0.0/30',
            link_index=1,
            leaf1_port='E1/2',
            leaf2_port='E1/2',
        )
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_switch_a_alphabetically_first(self):
        from netbox_hedgehog.models.topology_planning import PlanMeshLink
        # sc_b.switch_class_id = 'ml-leaf-02' > sc_a.switch_class_id = 'ml-leaf-01'
        # Passing them in reversed order should raise ValidationError
        link = PlanMeshLink(
            plan=self.plan,
            switch_class_a=self.sc_b,  # deliberately reversed
            switch_class_b=self.sc_a,
            subnet='172.30.128.2/31',
            link_index=2,
            leaf1_port='E1/3',
            leaf2_port='E1/3',
        )
        with self.assertRaises(ValidationError):
            link.full_clean()


# =============================================================================
# Class 7: MeshIPAllocationTests — DB
# =============================================================================

class MeshIPAllocationTests(TestCase):
    """Tests for allocate_mesh_links() utility function."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext = _make_base_fixtures()

    def _make_mesh_plan(self, name, pool, n_switches):
        plan = TopologyPlan.objects.create(name=name, mesh_ip_pool=pool)
        for i in range(1, n_switches + 1):
            PlanSwitchClass.objects.create(
                plan=plan,
                switch_class_id=f'alloc-leaf-{i:02d}',
                fabric_name='backend',
                fabric_class=FabricClassChoices.MANAGED,
                hedgehog_role='server-leaf',
                device_type_extension=self.ext,
                uplink_ports_per_switch=0,
                topology_mode='prefer-mesh',
                override_quantity=1,
            )
        return plan

    def test_2_switch_allocation_creates_one_link(self):
        from netbox_hedgehog.utils.mesh_allocator import allocate_mesh_links
        from netbox_hedgehog.models.topology_planning import PlanMeshLink
        plan = self._make_mesh_plan('Alloc 2-switch', '172.30.128.0/24', 2)
        allocate_mesh_links(plan, 'backend')
        self.assertEqual(PlanMeshLink.objects.filter(
            switch_class_a__plan=plan
        ).count(), 1)

    def test_3_switch_allocation_creates_three_links(self):
        from netbox_hedgehog.utils.mesh_allocator import allocate_mesh_links
        from netbox_hedgehog.models.topology_planning import PlanMeshLink
        plan = self._make_mesh_plan('Alloc 3-switch', '172.30.128.0/24', 3)
        allocate_mesh_links(plan, 'backend')
        self.assertEqual(PlanMeshLink.objects.filter(
            switch_class_a__plan=plan
        ).count(), 3)

    def test_allocation_deterministic(self):
        from netbox_hedgehog.utils.mesh_allocator import allocate_mesh_links
        from netbox_hedgehog.models.topology_planning import PlanMeshLink
        plan = self._make_mesh_plan('Alloc deterministic', '172.30.128.0/24', 2)
        allocate_mesh_links(plan, 'backend')
        subnets_first = list(
            PlanMeshLink.objects.filter(switch_class_a__plan=plan)
            .order_by('link_index')
            .values_list('subnet', flat=True)
        )
        PlanMeshLink.objects.filter(switch_class_a__plan=plan).delete()
        allocate_mesh_links(plan, 'backend')
        subnets_second = list(
            PlanMeshLink.objects.filter(switch_class_a__plan=plan)
            .order_by('link_index')
            .values_list('subnet', flat=True)
        )
        self.assertEqual(subnets_first, subnets_second)

    def test_same_pair_stable_across_calls(self):
        from netbox_hedgehog.utils.mesh_allocator import allocate_mesh_links
        from netbox_hedgehog.models.topology_planning import PlanMeshLink
        plan = self._make_mesh_plan('Alloc stable', '172.30.128.0/24', 2)
        allocate_mesh_links(plan, 'backend')
        subnet_before = PlanMeshLink.objects.filter(
            switch_class_a__plan=plan
        ).first().subnet
        PlanMeshLink.objects.filter(switch_class_a__plan=plan).delete()
        allocate_mesh_links(plan, 'backend')
        subnet_after = PlanMeshLink.objects.filter(
            switch_class_a__plan=plan
        ).first().subnet
        self.assertEqual(subnet_before, subnet_after)

    def test_insufficient_pool_raises(self):
        from netbox_hedgehog.utils.mesh_allocator import allocate_mesh_links
        # Only one /31 available but 3 switches need 3 /31 subnets
        plan = self._make_mesh_plan('Alloc insufficient', '172.30.128.0/31', 3)
        with self.assertRaises(ValueError):
            allocate_mesh_links(plan, 'backend')


# =============================================================================
# Class 8: MeshYAMLExportTests — DB
# =============================================================================

class MeshYAMLExportTests(TestCase):
    """Tests for _determine_connection_type() returning 'mesh' for mesh fabrics."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext = _make_base_fixtures()

    def _make_device_stub(self, fabric, role_slug='server-leaf', topology_mode='spine-leaf'):
        """
        Build a minimal in-memory object that matches what YAMLGenerator
        introspects on a Device for _endpoint_kind / _determine_connection_type.
        Uses a real Device so custom_field_data is available.
        """
        from dcim.models import Device, DeviceRole, Site
        site, _ = Site.objects.get_or_create(
            slug='mesh-yaml-site',
            defaults={'name': 'Mesh YAML Site'},
        )
        role, _ = DeviceRole.objects.get_or_create(
            slug=role_slug,
            defaults={'name': role_slug, 'color': '0000ff'},
        )
        device = Device.objects.create(
            name=f'mesh-dev-{fabric}-{role_slug}-{Device.objects.count()}',
            device_type=self.dt,
            role=role,
            site=site,
        )
        device.custom_field_data['hedgehog_fabric'] = fabric
        device.custom_field_data['hedgehog_topology_mode'] = topology_mode
        device.save()
        return device

    def test_mesh_connection_type_returned(self):
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        plan = _make_plan('YAML Mesh Plan A')
        gen = YAMLGenerator(plan_id=plan.pk)
        dev_a = self._make_device_stub('backend', topology_mode='prefer-mesh')
        dev_b = self._make_device_stub('backend', topology_mode='prefer-mesh')
        conn_type = gen._determine_connection_type(dev_a, dev_b, cable_id=9001)
        self.assertEqual(conn_type, 'mesh')

    def test_fabric_connection_type_for_spine_leaf(self):
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        plan = _make_plan('YAML Mesh Plan B')
        gen = YAMLGenerator(plan_id=plan.pk)
        dev_a = self._make_device_stub('backend', topology_mode='spine-leaf')
        dev_b = self._make_device_stub('backend', topology_mode='spine-leaf')
        conn_type = gen._determine_connection_type(dev_a, dev_b, cable_id=9002)
        self.assertEqual(conn_type, 'fabric')

    def test_server_leaf_role_not_coerced(self):
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        plan = _make_plan('YAML Mesh Plan C')
        gen = YAMLGenerator(plan_id=plan.pk)
        dev = self._make_device_stub('backend', role_slug='server-leaf',
                                     topology_mode='prefer-mesh')
        # _endpoint_kind for a managed switch should still be 'managed_switch'
        kind = gen._endpoint_kind(dev)
        self.assertEqual(kind, 'managed_switch')

    def test_border_leaf_role_not_coerced(self):
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        plan = _make_plan('YAML Mesh Plan D')
        gen = YAMLGenerator(plan_id=plan.pk)
        dev = self._make_device_stub('backend', role_slug='border-leaf',
                                     topology_mode='prefer-mesh')
        kind = gen._endpoint_kind(dev)
        self.assertEqual(kind, 'managed_switch')


# =============================================================================
# Class 9: MeshGenerationStateTests — DB
# =============================================================================

class MeshGenerationStateTests(TestCase):
    """Tests for snapshot dirty-detection with mesh fields."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext = _make_base_fixtures()

    def test_mesh_ip_pool_in_snapshot(self):
        plan = TopologyPlan.objects.create(
            name='Snapshot IP Pool Plan',
            mesh_ip_pool='172.30.128.0/24',
        )
        snapshot = build_plan_snapshot(plan)
        self.assertIn('mesh_ip_pool', snapshot)

    def test_topology_mode_in_switch_class_snapshot(self):
        plan = _make_plan('Snapshot Topology Mode Plan')
        _make_switch_class(plan, self.ext, switch_class_id='snap-leaf-01',
                           topology_mode='prefer-mesh')
        snapshot = build_plan_snapshot(plan)
        sc_snap = snapshot['switch_classes'][0]
        self.assertIn('topology_mode', sc_snap)

    def test_changing_mesh_ip_pool_dirties_plan(self):
        plan = TopologyPlan.objects.create(
            name='Dirty IP Pool Plan',
            mesh_ip_pool='172.30.128.0/24',
        )
        snapshot = build_plan_snapshot(plan)
        state = GenerationState.objects.create(
            plan=plan,
            snapshot=snapshot,
            device_count=0,
            interface_count=0,
            cable_count=0,
            status='generated',
        )
        plan.mesh_ip_pool = '10.0.0.0/24'
        plan.save()
        self.assertTrue(state.is_dirty())

    def test_changing_topology_mode_dirties_plan(self):
        plan = _make_plan('Dirty Topology Mode Plan')
        sc = _make_switch_class(plan, self.ext, switch_class_id='dirty-leaf-01',
                                topology_mode='spine-leaf')
        snapshot = build_plan_snapshot(plan)
        state = GenerationState.objects.create(
            plan=plan,
            snapshot=snapshot,
            device_count=0,
            interface_count=0,
            cable_count=0,
            status='generated',
        )
        sc.topology_mode = 'prefer-mesh'
        sc.save()
        self.assertTrue(state.is_dirty())

    def test_plan_mesh_links_not_in_snapshot(self):
        plan = _make_plan('No MeshLinks Snapshot Plan')
        snapshot = build_plan_snapshot(plan)
        self.assertNotIn('mesh_links', snapshot)


# =============================================================================
# Class 10: MeshIPOmissionExportTests — DB (#311 RED)
#
# These tests verify that _create_mesh_crd() never emits leaf1.ip / leaf2.ip,
# regardless of whether mesh_ip_pool is set or PlanMeshLink.subnet is populated.
# All tests in this class are expected to FAIL until GREEN (#311) is implemented.
# =============================================================================

class MeshIPOmissionExportTests(TestCase):
    """RED tests for issue #311: mesh Connection CRDs must omit leaf IP fields."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext = _make_base_fixtures()

    def _make_mesh_plan_with_pool(self, name):
        """Return a plan with mesh_ip_pool set and two prefer-mesh switch classes."""
        plan = TopologyPlan.objects.create(name=name, mesh_ip_pool='172.30.128.0/24')
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='ip-omit-leaf-01',
            fabric_name='frontend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
            override_quantity=1,
        )
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='ip-omit-leaf-02',
            fabric_name='frontend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
            override_quantity=1,
        )
        return plan

    def _make_minimal_link_data(self):
        """Return minimal link_data dicts for _create_mesh_crd() using real Device stubs."""
        from dcim.models import Device, DeviceRole, Site
        site, _ = Site.objects.get_or_create(
            slug='mesh-ip-omit-site',
            defaults={'name': 'Mesh IP Omit Site'},
        )
        role, _ = DeviceRole.objects.get_or_create(
            slug='server-leaf',
            defaults={'name': 'server-leaf', 'color': '0000ff'},
        )
        count = Device.objects.count()
        dev_a = Device.objects.create(
            name=f'ip-omit-leaf-01-{count}',
            device_type=self.dt,
            role=role,
            site=site,
        )
        dev_b = Device.objects.create(
            name=f'ip-omit-leaf-02-{count+1}',
            device_type=self.dt,
            role=role,
            site=site,
        )
        from dcim.models import Interface
        iface_a = Interface.objects.create(
            device=dev_a,
            name='E1/1',
            type='1000base-t',
        )
        iface_b = Interface.objects.create(
            device=dev_b,
            name='E1/1',
            type='1000base-t',
        )
        links = [
            {
                'leaf1_device': dev_a,
                'leaf1_iface': iface_a,
                'leaf2_device': dev_b,
                'leaf2_iface': iface_b,
            }
        ]
        return dev_a, dev_b, links

    def test_mesh_crd_omits_leaf1_ip_when_pool_is_present(self):
        """T1: _create_mesh_crd() must not emit leaf1.ip even when mesh_ip_pool is set."""
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        from netbox_hedgehog.models.topology_planning import PlanMeshLink

        plan = self._make_mesh_plan_with_pool('IP Omit T1')
        gen = YAMLGenerator(plan_id=plan.pk)
        dev_a, dev_b, links = self._make_minimal_link_data()

        # Populate a PlanMeshLink with a real subnet (legacy data)
        sc_a = plan.switch_classes.get(switch_class_id='ip-omit-leaf-01')
        sc_b = plan.switch_classes.get(switch_class_id='ip-omit-leaf-02')
        PlanMeshLink.objects.create(
            plan=plan,
            fabric_name='frontend',
            switch_class_a=sc_a,
            switch_class_b=sc_b,
            subnet='172.30.128.0/31',
            link_index=0,
            leaf1_name=dev_a.name,
            leaf2_name=dev_b.name,
        )

        crd = gen._create_mesh_crd(dev_a, dev_b, links)

        for link_entry in crd['spec']['mesh']['links']:
            self.assertNotIn(
                'ip', link_entry['leaf1'],
                "leaf1.ip must be absent from mesh Connection CRD (hhfab hydration contract)"
            )
            self.assertNotIn(
                'ip', link_entry['leaf2'],
                "leaf2.ip must be absent from mesh Connection CRD (hhfab hydration contract)"
            )
            # 'device' is not a valid field in ConnFabricLinkSwitch — hhfab strict-decodes
            self.assertNotIn(
                'device', link_entry['leaf1'],
                "leaf1.device must be absent — not a valid field in ConnFabricLinkSwitch schema"
            )
            self.assertNotIn(
                'device', link_entry['leaf2'],
                "leaf2.device must be absent — not a valid field in ConnFabricLinkSwitch schema"
            )

    def test_mesh_crd_omits_leaf2_ip_when_pool_is_present(self):
        """T2: _create_mesh_crd() must not emit leaf2.ip even when mesh_ip_pool is set."""
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        from netbox_hedgehog.models.topology_planning import PlanMeshLink

        plan = self._make_mesh_plan_with_pool('IP Omit T2')
        gen = YAMLGenerator(plan_id=plan.pk)
        dev_a, dev_b, links = self._make_minimal_link_data()

        sc_a = plan.switch_classes.get(switch_class_id='ip-omit-leaf-01')
        sc_b = plan.switch_classes.get(switch_class_id='ip-omit-leaf-02')
        PlanMeshLink.objects.create(
            plan=plan,
            fabric_name='frontend',
            switch_class_a=sc_a,
            switch_class_b=sc_b,
            subnet='172.30.128.0/31',
            link_index=0,
            leaf1_name=dev_a.name,
            leaf2_name=dev_b.name,
        )

        crd = gen._create_mesh_crd(dev_a, dev_b, links)
        leaf2 = crd['spec']['mesh']['links'][0]['leaf2']
        self.assertNotIn('ip', leaf2)

    def test_mesh_crd_omits_ip_when_pool_absent(self):
        """T3: _create_mesh_crd() must not emit ip fields when mesh_ip_pool is absent."""
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator

        plan = TopologyPlan.objects.create(name='IP Omit T3 no pool')
        gen = YAMLGenerator(plan_id=plan.pk)
        dev_a, dev_b, links = self._make_minimal_link_data()

        crd = gen._create_mesh_crd(dev_a, dev_b, links)

        for link_entry in crd['spec']['mesh']['links']:
            self.assertNotIn('ip', link_entry['leaf1'])
            self.assertNotIn('ip', link_entry['leaf2'])

    def test_mesh_crd_does_not_emit_empty_string_ip(self):
        """T4: 'ip': '' is as bad as 'ip': '1.2.3.4' — the key must be absent entirely."""
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator

        plan = TopologyPlan.objects.create(name='IP Omit T4 no key')
        gen = YAMLGenerator(plan_id=plan.pk)
        dev_a, dev_b, links = self._make_minimal_link_data()

        crd = gen._create_mesh_crd(dev_a, dev_b, links)
        leaf1 = crd['spec']['mesh']['links'][0]['leaf1']
        # The 'ip' key must not appear at all, not even as an empty string
        self.assertNotIn('ip', leaf1, "Empty-string 'ip' key must not be emitted")

    def test_mesh_crd_backward_compat_legacy_pool_and_subnets(self):
        """T5: backward compat — plan with mesh_ip_pool + populated PlanMeshLink.subnet
        still produces wiring with no IP keys (legacy data is tolerated but not exported)."""
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        from netbox_hedgehog.models.topology_planning import PlanMeshLink

        plan = self._make_mesh_plan_with_pool('IP Omit T5 legacy')
        gen = YAMLGenerator(plan_id=plan.pk)
        dev_a, dev_b, links = self._make_minimal_link_data()

        # Simulate legacy state: subnet value present from old code path
        sc_a = plan.switch_classes.get(switch_class_id='ip-omit-leaf-01')
        sc_b = plan.switch_classes.get(switch_class_id='ip-omit-leaf-02')
        PlanMeshLink.objects.create(
            plan=plan,
            fabric_name='frontend',
            switch_class_a=sc_a,
            switch_class_b=sc_b,
            subnet='172.30.128.4/31',
            link_index=0,
            leaf1_name=dev_a.name,
            leaf2_name=dev_b.name,
        )

        crd = gen._create_mesh_crd(dev_a, dev_b, links)
        for link_entry in crd['spec']['mesh']['links']:
            self.assertNotIn('ip', link_entry['leaf1'])
            self.assertNotIn('ip', link_entry['leaf2'])


# =============================================================================
# Class 11: MeshGenerationWithoutPoolTests — DB (#311 RED)
#
# These tests verify that:
# - allocate_mesh_links() works without mesh_ip_pool (pairing-only mode)
# - PlanMeshLink.subnet allows blank
# - DeviceGenerator creates mesh cables without requiring mesh_ip_pool
# All tests are expected to FAIL until GREEN (#311) is implemented.
# =============================================================================

class MeshGenerationWithoutPoolTests(TestCase):
    """RED tests for issue #311: mesh generation must not require mesh_ip_pool."""

    @classmethod
    def setUpTestData(cls):
        cls.mfr, cls.dt, cls.ext = _make_base_fixtures()

    def test_plan_mesh_link_allows_blank_subnet(self):
        """T6: PlanMeshLink.clean() must accept blank subnet (not raise ValidationError)."""
        from netbox_hedgehog.models.topology_planning import PlanMeshLink

        plan = TopologyPlan.objects.create(name='Blank Subnet T6')
        sc_a = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='blank-leaf-01',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
        )
        sc_b = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='blank-leaf-02',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
        )
        link = PlanMeshLink(
            plan=plan,
            switch_class_a=sc_a,
            switch_class_b=sc_b,
            subnet='',  # blank — must be tolerated
            link_index=0,
            leaf1_name='blank-leaf-01-01',
            leaf2_name='blank-leaf-02-01',
        )
        # Must not raise ValidationError
        try:
            link.full_clean()
        except ValidationError as e:
            self.fail(f"PlanMeshLink.full_clean() raised ValidationError for blank subnet: {e}")
        link.save()
        self.assertEqual(PlanMeshLink.objects.filter(plan=plan).count(), 1)

    def test_allocate_mesh_links_without_pool_creates_pairing_rows(self):
        """T7: allocate_mesh_links() with no mesh_ip_pool must create PlanMeshLink rows
        with correct pairing (leaf names, switch class FKs) and blank subnet."""
        from netbox_hedgehog.utils.mesh_allocator import allocate_mesh_links
        from netbox_hedgehog.models.topology_planning import PlanMeshLink

        plan = TopologyPlan.objects.create(name='No Pool Pairing T7')  # no mesh_ip_pool
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='pair-leaf-01',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
            override_quantity=1,
        )
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='pair-leaf-02',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
            override_quantity=1,
        )

        links = allocate_mesh_links(plan, 'backend')

        self.assertEqual(len(links), 1, "Should create 1 pairing row for 2-switch mesh")
        link = links[0]
        self.assertEqual(link.leaf1_name, 'pair-leaf-01-01')
        self.assertEqual(link.leaf2_name, 'pair-leaf-02-01')
        self.assertEqual(link.subnet, '', "subnet must be blank when no pool is configured")

    def test_allocate_mesh_links_without_pool_does_not_raise(self):
        """T8: allocate_mesh_links() must not raise ValueError when mesh_ip_pool is absent."""
        from netbox_hedgehog.utils.mesh_allocator import allocate_mesh_links

        plan = TopologyPlan.objects.create(name='No Pool No Raise T8')
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='noraise-leaf-01',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
            override_quantity=1,
        )
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='noraise-leaf-02',
            fabric_name='backend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf',
            device_type_extension=self.ext,
            uplink_ports_per_switch=0,
            topology_mode='prefer-mesh',
            override_quantity=1,
        )
        try:
            allocate_mesh_links(plan, 'backend')
        except ValueError as e:
            self.fail(
                f"allocate_mesh_links() raised ValueError with no mesh_ip_pool: {e}"
            )
