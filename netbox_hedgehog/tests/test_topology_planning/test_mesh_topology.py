"""
RED tests for #317: Explicit manual mesh topology mode.
All tests fail until GREEN (#318) is implemented.
"""
from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from django.urls import reverse
from dcim.models import Manufacturer, DeviceType, Site, Device, DeviceRole
from users.models import User

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan, PlanSwitchClass, DeviceTypeExtension,
    PlanMeshLink, SwitchPortZone, BreakoutOption,
    PlanServerClass, PlanServerConnection,
)
from netbox_hedgehog.choices import (
    PortZoneTypeChoices, FabricClassChoices, TopologyModeChoices,
    AllocationStrategyChoices,
)
from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot
from netbox_hedgehog.utils.topology_calculations import update_plan_calculations
from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _mfr_dt_ext():
    mfr, _ = Manufacturer.objects.get_or_create(
        name='Mesh317Mfr', defaults={'slug': 'mesh317-mfr'})
    dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='Mesh317Switch',
        defaults={'slug': 'mesh317-switch'})
    ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=dt,
        defaults={'native_speed': 400, 'uplink_ports': 0,
                  'supported_breakouts': ['1x400g', '4x100g'],
                  'hedgehog_roles': ['server-leaf']})
    return mfr, dt, ext


def _breakout():
    bo, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x400g-m317',
        defaults={'from_speed': 400, 'logical_ports': 1, 'logical_speed': 400})
    return bo


def _site():
    s, _ = Site.objects.get_or_create(
        name='Mesh317Site', defaults={'slug': 'mesh317-site'})
    return s


def _plan(name='M317 Plan'):
    return TopologyPlan.objects.create(name=name)


def _mesh_sc(plan, ext, sc_id='mesh-leaf', qty=2, fabric='backend'):
    """Create a mesh-mode switch class with override_quantity=qty."""
    return PlanSwitchClass.objects.create(
        plan=plan, switch_class_id=sc_id, fabric_name=fabric,
        fabric_class=FabricClassChoices.MANAGED,
        hedgehog_role='server-leaf', device_type_extension=ext,
        uplink_ports_per_switch=0,
        topology_mode='mesh', override_quantity=qty)


def _mesh_zone(sc, zone_name='mesh-ports', port_spec='1-4'):
    bo = _breakout()
    return SwitchPortZone.objects.create(
        switch_class=sc, zone_name=zone_name,
        zone_type=PortZoneTypeChoices.MESH, port_spec=port_spec,
        breakout_option=bo,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
        priority=10)


def _server_zone(sc, zone_name='srv-ports', port_spec='5-36'):
    bo = _breakout()
    return SwitchPortZone.objects.create(
        switch_class=sc, zone_name=zone_name,
        zone_type=PortZoneTypeChoices.SERVER, port_spec=port_spec,
        breakout_option=bo,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
        priority=20)


# ---------------------------------------------------------------------------
# 1. Choices
# ---------------------------------------------------------------------------

class Mesh317ChoicesTests(TestCase):
    def test_mesh_constant_exists_and_equals_mesh(self):
        self.assertEqual(TopologyModeChoices.MESH, 'mesh')

    def test_prefer_mesh_constant_absent(self):
        self.assertFalse(hasattr(TopologyModeChoices, 'PREFER_MESH'))

    def test_mesh_value_in_choices_list(self):
        values = [v for v, _ in TopologyModeChoices.CHOICES]
        self.assertIn('mesh', values)

    def test_prefer_mesh_value_not_in_choices_list(self):
        values = [v for v, _ in TopologyModeChoices.CHOICES]
        self.assertNotIn('prefer-mesh', values)


# ---------------------------------------------------------------------------
# 2. Model validation
# ---------------------------------------------------------------------------

class Mesh317ModelValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext = _mfr_dt_ext()
        cls.plan = _plan('M317 Validation Plan')

    def _sc(self, sc_id, **kwargs):
        return PlanSwitchClass(
            plan=self.plan, switch_class_id=sc_id,
            fabric_name='backend', fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf', device_type_extension=self.ext,
            uplink_ports_per_switch=0, **kwargs)

    def test_mesh_requires_override_quantity(self):
        sc = self._sc('mv-01', topology_mode='mesh', override_quantity=None)
        with self.assertRaises(ValidationError) as ctx:
            sc.full_clean()
        self.assertIn('override_quantity', ctx.exception.message_dict)

    def test_mesh_rejects_override_quantity_one(self):
        sc = self._sc('mv-02', topology_mode='mesh', override_quantity=1)
        with self.assertRaises(ValidationError) as ctx:
            sc.full_clean()
        self.assertIn('override_quantity', ctx.exception.message_dict)

    def test_mesh_rejects_override_quantity_four(self):
        sc = self._sc('mv-03', topology_mode='mesh', override_quantity=4)
        with self.assertRaises(ValidationError) as ctx:
            sc.full_clean()
        self.assertIn('override_quantity', ctx.exception.message_dict)

    def test_mesh_accepts_override_quantity_two(self):
        sc = self._sc('mv-04', topology_mode='mesh', override_quantity=2)
        sc.full_clean()  # no error

    def test_mesh_accepts_override_quantity_three(self):
        sc = self._sc('mv-05', topology_mode='mesh', override_quantity=3)
        sc.full_clean()  # no error

    def test_prefer_mesh_value_rejected(self):
        sc = self._sc('mv-06', topology_mode='prefer-mesh', override_quantity=2)
        with self.assertRaises(ValidationError):
            sc.full_clean()

    def test_mesh_spine_mutual_exclusion_mesh_blocked(self):
        PlanSwitchClass.objects.create(
            plan=self.plan, switch_class_id='mv-spine-a',
            fabric_name='mesh-fab', fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='spine', device_type_extension=self.ext,
            uplink_ports_per_switch=4)
        sc = self._sc('mv-07', topology_mode='mesh', override_quantity=2)
        sc.fabric_name = 'mesh-fab'
        with self.assertRaises(ValidationError) as ctx:
            sc.full_clean()
        self.assertIn('topology_mode', ctx.exception.message_dict)

    def test_mesh_fabric_invariant_mixed_modes_rejected(self):
        PlanSwitchClass.objects.create(
            plan=self.plan, switch_class_id='mv-spine-leaf-peer',
            fabric_name='inv-fab', fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf', device_type_extension=self.ext,
            uplink_ports_per_switch=0, topology_mode='spine-leaf')
        sc = self._sc('mv-08', topology_mode='mesh', override_quantity=2)
        sc.fabric_name = 'inv-fab'
        with self.assertRaises(ValidationError) as ctx:
            sc.full_clean()
        self.assertIn('topology_mode', ctx.exception.message_dict)


# ---------------------------------------------------------------------------
# 3. Calculation engine
# ---------------------------------------------------------------------------

class Mesh317CalculationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext = _mfr_dt_ext()

    def test_mesh_class_absent_from_calculation_summary(self):
        plan = _plan('M317 Calc Plan A')
        _mesh_sc(plan, self.ext, sc_id='calc-leaf', qty=2)
        result = update_plan_calculations(plan)
        self.assertNotIn('calc-leaf', result['summary'])

    def test_mesh_class_calculated_quantity_not_updated(self):
        plan = _plan('M317 Calc Plan B')
        sc = _mesh_sc(plan, self.ext, sc_id='calc-leaf-b', qty=2)
        update_plan_calculations(plan)
        sc.refresh_from_db()
        self.assertIsNone(sc.calculated_quantity)

    def test_no_mesh_feasibility_key_in_results(self):
        plan = _plan('M317 Calc Plan C')
        _mesh_sc(plan, self.ext, sc_id='calc-leaf-c', qty=2)
        result = update_plan_calculations(plan)
        self.assertNotIn('mesh_feasibility', result)

    def test_spine_leaf_class_still_calculated(self):
        """Regression: non-mesh classes still appear in summary."""
        plan = _plan('M317 Calc Plan D')
        srv_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=Manufacturer.objects.get(name='Mesh317Mfr'),
            model='M317Server', defaults={'slug': 'm317-server'})
        sc = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='sl-leaf', fabric_name='frontend',
            fabric_class=FabricClassChoices.MANAGED, hedgehog_role='server-leaf',
            device_type_extension=self.ext, uplink_ports_per_switch=0)
        bo = _breakout()
        zone = SwitchPortZone.objects.create(
            switch_class=sc, zone_name='sl-srv', zone_type='server',
            port_spec='1-32', breakout_option=bo,
            allocation_strategy='sequential', priority=10)
        srv = PlanServerClass.objects.create(
            plan=plan, server_class_id='sl-srv', quantity=2,
            server_device_type=srv_dt)
        PlanServerConnection.objects.create(
            server_class=srv, connection_id='fe-conn',
            nic=get_test_server_nic(srv), port_index=0,
            target_zone=zone, ports_per_connection=1,
            hedgehog_conn_type='unbundled', speed=400, port_type='data')
        result = update_plan_calculations(plan)
        self.assertIn('sl-leaf', result['summary'])


# ---------------------------------------------------------------------------
# 4. Generation validation (hard errors)
# ---------------------------------------------------------------------------

class Mesh317GenerationValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext = _mfr_dt_ext()
        cls.site = _site()

    def _gen(self, plan):
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        return DeviceGenerator(plan, site=self.site).generate_all()

    def test_generation_fails_without_mesh_zones(self):
        plan = _plan('M317 Gen No-Zone')
        _mesh_sc(plan, self.ext, sc_id='nz-leaf', qty=2)
        # No MESH zone created
        with self.assertRaises((ValidationError, Exception)):
            self._gen(plan)

    def test_generation_fails_with_insufficient_mesh_ports(self):
        """3-switch mesh needs 2 ports/switch; zone has only 1."""
        plan = _plan('M317 Gen Few-Ports')
        sc = _mesh_sc(plan, self.ext, sc_id='fp-leaf', qty=3)
        _mesh_zone(sc, port_spec='1-1')  # only 1 port, need 2
        with self.assertRaises((ValidationError, Exception)):
            self._gen(plan)

    def test_generation_fails_fabric_sum_not_in_2_3(self):
        """Two mesh classes, each override_quantity=2, fabric-sum=4 → error."""
        plan = _plan('M317 Gen FabSum')
        _mesh_sc(plan, self.ext, sc_id='fs-leaf-a', qty=2, fabric='fab-sum')
        _mesh_sc(plan, self.ext, sc_id='fs-leaf-b', qty=2, fabric='fab-sum')
        with self.assertRaises((ValidationError, Exception)):
            self._gen(plan)

    def test_generation_fails_insufficient_server_capacity(self):
        """override_quantity=1 but server demand requires 2 switches."""
        plan = _plan('M317 Gen SrvCap')
        sc = _mesh_sc(plan, self.ext, sc_id='sc-leaf', qty=1, fabric='srv-cap')
        _mesh_zone(sc, port_spec='1-4')
        srv_zone = _server_zone(sc, port_spec='5-8')  # 4 server ports/switch
        srv_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=Manufacturer.objects.get(name='Mesh317Mfr'),
            model='M317SrvCap', defaults={'slug': 'm317-srvcap'})
        srv = PlanServerClass.objects.create(
            plan=plan, server_class_id='sc-srv', quantity=6,
            server_device_type=srv_dt)
        # 6 servers * 1 port = 6 demand; 4 ports/switch → needs 2, override=1
        PlanServerConnection.objects.create(
            server_class=srv, connection_id='sc-conn',
            nic=get_test_server_nic(srv), port_index=0,
            target_zone=srv_zone, ports_per_connection=1,
            hedgehog_conn_type='unbundled', speed=400, port_type='data')
        with self.assertRaises((ValidationError, Exception)):
            self._gen(plan)

    def test_generated_devices_have_no_topology_mode_custom_field(self):
        """After GREEN: hedgehog_topology_mode must NOT be set on devices."""
        from dcim.models import Device
        plan = _plan('M317 Gen NoField')
        sc = _mesh_sc(plan, self.ext, sc_id='nf-leaf', qty=2)
        _mesh_zone(sc, port_spec='1-4')
        self._gen(plan)
        for dev in Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(plan.pk)):
            self.assertNotIn('hedgehog_topology_mode',
                             dev.custom_field_data)
        # cleanup
        Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)).delete()


# ---------------------------------------------------------------------------
# 5. Export classification (plan-state, not device custom field)
# ---------------------------------------------------------------------------

class Mesh317ExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _, cls.dt, cls.ext = _mfr_dt_ext()
        cls.site = _site()
        cls.role, _ = DeviceRole.objects.get_or_create(
            slug='m317-server-leaf',
            defaults={'name': 'M317 Server Leaf', 'color': '0000ff'})

    def _managed_device(self, name, plan, sc_id, fabric):
        d = Device.objects.create(
            name=name, device_type=self.dt, role=self.role, site=self.site)
        d.custom_field_data = {
            'hedgehog_fabric': fabric,
            'hedgehog_plan_id': str(plan.pk),
            'hedgehog_class': sc_id,
            'hedgehog_fabric_class': 'managed',
            'hedgehog_role': 'server-leaf',
        }
        # Deliberately omit hedgehog_topology_mode
        d.save()
        return d

    def test_export_returns_mesh_from_plan_state_not_custom_field(self):
        """Devices without hedgehog_topology_mode must still classify as mesh
        when their switch class has topology_mode='mesh'."""
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        plan = _plan('M317 Export PlanState')
        _, _, ext = _mfr_dt_ext()
        _mesh_sc(plan, ext, sc_id='exp-leaf', qty=2, fabric='exp-fab')
        dev_a = self._managed_device('exp-leaf-01', plan, 'exp-leaf', 'exp-fab')
        dev_b = self._managed_device('exp-leaf-02', plan, 'exp-leaf', 'exp-fab')
        gen = YAMLGenerator(plan_id=plan.pk)
        conn_type = gen._determine_connection_type(dev_a, dev_b, cable_id=1)
        self.assertEqual(conn_type, 'mesh')

    def test_export_ignores_stale_topology_mode_custom_field(self):
        """Devices with old hedgehog_topology_mode='prefer-mesh' but
        spine-leaf switch class must return 'fabric', not 'mesh'."""
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        plan = _plan('M317 Export Stale')
        # spine-leaf switch class (not mesh)
        PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='sl-exp-leaf',
            fabric_name='sl-fab', fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf', device_type_extension=self.ext,
            uplink_ports_per_switch=0, topology_mode='spine-leaf')
        dev_a = self._managed_device('sl-exp-01', plan, 'sl-exp-leaf', 'sl-fab')
        dev_b = self._managed_device('sl-exp-02', plan, 'sl-exp-leaf', 'sl-fab')
        # Inject old custom field (should be ignored)
        dev_a.custom_field_data['hedgehog_topology_mode'] = 'prefer-mesh'
        dev_a.save()
        dev_b.custom_field_data['hedgehog_topology_mode'] = 'prefer-mesh'
        dev_b.save()
        gen = YAMLGenerator(plan_id=plan.pk)
        conn_type = gen._determine_connection_type(dev_a, dev_b, cable_id=2)
        self.assertEqual(conn_type, 'fabric')

    def test_mesh_crd_omits_leaf_ips(self):
        """DIET-311 regression: mesh CRDs must never emit leaf1.ip/leaf2.ip."""
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        plan = _plan('M317 Export IPs')
        gen = YAMLGenerator(plan_id=plan.pk)
        dev_a = self._managed_device('ip-leaf-01', plan, 'ip-leaf', 'ip-fab')
        dev_b = self._managed_device('ip-leaf-02', plan, 'ip-leaf', 'ip-fab')
        link = {'leaf1': {'port': 'ip-leaf-01/E1/1'},
                'leaf2': {'port': 'ip-leaf-02/E1/1'}}
        crd = gen._create_mesh_crd(dev_a, dev_b, [link])
        for lnk in crd['spec']['mesh']['links']:
            self.assertNotIn('ip', lnk.get('leaf1', {}))
            self.assertNotIn('ip', lnk.get('leaf2', {}))


# ---------------------------------------------------------------------------
# 6. YAML ingest
# ---------------------------------------------------------------------------

class Mesh317IngestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext = _mfr_dt_ext()

    def _minimal_mesh_case(self, case_id, topo_mode='mesh'):
        from netbox_hedgehog.test_cases.ingest import apply_case
        case = {
            'meta': {'case_id': case_id, 'name': case_id,
                     'version': 1, 'managed_by': 'yaml'},
            'plan': {'name': case_id, 'status': 'draft'},
            'reference_data': {
                'manufacturers': [
                    {'id': 'ing-mfr', 'name': 'Mesh317Mfr', 'slug': 'mesh317-mfr'}],
                'device_types': [
                    {'id': 'ing-dt', 'manufacturer': 'ing-mfr',
                     'model': 'Mesh317Switch', 'slug': 'mesh317-switch',
                     'interface_templates': [
                         {'name': 'E1/1', 'type': '400gbase-x-osfp'}]}],
                'device_type_extensions': [
                    {'id': 'ing-ext', 'device_type': 'ing-dt',
                     'hedgehog_roles': ['server-leaf'], 'native_speed': 400,
                     'uplink_ports': 0, 'supported_breakouts': ['1x400g']}],
            },
            'switch_classes': [
                {'switch_class_id': 'ing-leaf', 'fabric_name': 'backend',
                 'fabric_class': 'managed', 'hedgehog_role': 'server-leaf',
                 'device_type_extension': 'ing-ext',
                 'topology_mode': topo_mode,
                 'override_quantity': 2}],
            'switch_port_zones': [],
            'server_classes': [],
            'server_nics': [],
            'server_connections': [],
        }
        return apply_case(case, clean=True, prune=True, reference_mode='ensure')

    def test_ingest_topology_mode_mesh_accepted(self):
        plan = self._minimal_mesh_case('ingest_mesh_ok')
        sc = PlanSwitchClass.objects.get(plan=plan, switch_class_id='ing-leaf')
        self.assertEqual(sc.topology_mode, 'mesh')

    def test_ingest_topology_mode_prefer_mesh_rejected(self):
        with self.assertRaises(Exception):
            self._minimal_mesh_case('ingest_prefer_mesh_bad',
                                    topo_mode='prefer-mesh')

    def test_ingest_mesh_ip_pool_in_plan_silently_ignored(self):
        """mesh_ip_pool in YAML plan section must not cause an error."""
        from netbox_hedgehog.test_cases.ingest import apply_case
        case = {
            'meta': {'case_id': 'ingest_pool_ignored', 'name': 'ingest_pool_ignored',
                     'version': 1, 'managed_by': 'yaml'},
            'plan': {'name': 'ingest_pool_ignored', 'status': 'draft',
                     'mesh_ip_pool': '172.30.0.0/24'},  # old field
            'reference_data': {
                'manufacturers': [
                    {'id': 'pi-mfr', 'name': 'Mesh317Mfr', 'slug': 'mesh317-mfr'}],
                'device_types': [
                    {'id': 'pi-dt', 'manufacturer': 'pi-mfr',
                     'model': 'Mesh317Switch', 'slug': 'mesh317-switch',
                     'interface_templates': [
                         {'name': 'E1/1', 'type': '400gbase-x-osfp'}]}],
                'device_type_extensions': [
                    {'id': 'pi-ext', 'device_type': 'pi-dt',
                     'hedgehog_roles': ['server-leaf'], 'native_speed': 400,
                     'uplink_ports': 0, 'supported_breakouts': ['1x400g']}],
            },
            'switch_classes': [
                {'switch_class_id': 'pi-leaf', 'fabric_name': 'backend',
                 'fabric_class': 'managed', 'hedgehog_role': 'server-leaf',
                 'device_type_extension': 'pi-ext',
                 'topology_mode': 'mesh', 'override_quantity': 2}],
            'switch_port_zones': [],
            'server_classes': [],
            'server_nics': [],
            'server_connections': [],
        }
        # Must not raise
        plan = apply_case(case, clean=True, prune=True, reference_mode='ensure')
        self.assertTrue(TopologyPlan.objects.filter(pk=plan.pk).exists())


# ---------------------------------------------------------------------------
# 7. Migration end-state regression
# ---------------------------------------------------------------------------

class Mesh317MigrationRegressionTests(TestCase):
    def test_topologyplan_has_no_mesh_ip_pool_attribute(self):
        plan = _plan('M317 Mig Plan')
        self.assertFalse(hasattr(plan, 'mesh_ip_pool'))

    def test_hedgehog_topology_mode_custom_field_absent(self):
        from extras.models import CustomField
        self.assertFalse(
            CustomField.objects.filter(name='hedgehog_topology_mode').exists())

    def test_prefer_mesh_db_rows_renamed_to_mesh(self):
        """After migration, no rows with topology_mode='prefer-mesh' exist.
        Direct SQL insert bypasses model validation to simulate pre-migration data."""
        from django.db import connection
        _, _, ext = _mfr_dt_ext()
        plan = _plan('M317 Mig Rename')
        # Use update() to bypass model-level choice validation
        sc = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='mig-leaf',
            fabric_name='backend', fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf', device_type_extension=ext,
            uplink_ports_per_switch=0,
            topology_mode='mesh', override_quantity=2)
        # Force the old value at DB level
        PlanSwitchClass.objects.filter(pk=sc.pk).update(
            topology_mode='prefer-mesh')
        # Verify data migration logic: run the rename function
        from netbox_hedgehog.migrations.mesh_migration_helpers import rename_prefer_mesh
        rename_prefer_mesh()
        sc.refresh_from_db()
        self.assertEqual(sc.topology_mode, 'mesh')


# ---------------------------------------------------------------------------
# 8. Snapshot / dirty tracking
# ---------------------------------------------------------------------------

class Mesh317SnapshotTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext = _mfr_dt_ext()

    def test_snapshot_has_no_mesh_ip_pool_key(self):
        plan = _plan('M317 Snap NoPool')
        snap = build_plan_snapshot(plan)
        self.assertNotIn('mesh_ip_pool', snap)

    def test_topology_mode_in_switch_class_snapshot(self):
        plan = _plan('M317 Snap Mode')
        _mesh_sc(plan, self.ext, sc_id='snap-leaf', qty=2)
        snap = build_plan_snapshot(plan)
        sc_snaps = snap['switch_classes']
        self.assertTrue(any(
            s.get('topology_mode') == 'mesh' for s in sc_snaps))

    def test_changing_topology_mode_dirties_plan(self):
        from netbox_hedgehog.models.topology_planning import GenerationState
        import json
        plan = _plan('M317 Snap Dirty')
        sc = _mesh_sc(plan, self.ext, sc_id='dirty-leaf', qty=2)
        snap = build_plan_snapshot(plan)
        state = GenerationState.objects.create(
            plan=plan, status='generated',
            snapshot=json.dumps(snap),
            device_count=0, interface_count=0, cable_count=0)
        # Change topology_mode to spine-leaf
        PlanSwitchClass.objects.filter(pk=sc.pk).update(
            topology_mode='spine-leaf', override_quantity=None)
        self.assertTrue(state.is_dirty())


# ---------------------------------------------------------------------------
# 9. Views / permissions (AGENTS.md requirement)
# ---------------------------------------------------------------------------

class Mesh317ViewsPermissionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext = _mfr_dt_ext()
        cls.plan = _plan('M317 Views Plan')
        cls.superuser = User.objects.create_user(
            username='m317super', password='pass', is_staff=True,
            is_superuser=True)
        cls.plain_user = User.objects.create_user(
            username='m317plain', password='pass', is_staff=True,
            is_superuser=False)

    def setUp(self):
        self.client = Client()

    def test_list_view_loads(self):
        self.client.login(username='m317super', password='pass')
        r = self.client.get(reverse(
            'plugins:netbox_hedgehog:planswitchclass_list'))
        self.assertEqual(r.status_code, 200)

    def test_add_view_loads(self):
        self.client.login(username='m317super', password='pass')
        r = self.client.get(reverse(
            'plugins:netbox_hedgehog:planswitchclass_add'))
        self.assertEqual(r.status_code, 200)

    def test_valid_mesh_post_creates_and_redirects(self):
        self.client.login(username='m317super', password='pass')
        r = self.client.post(
            reverse('plugins:netbox_hedgehog:planswitchclass_add'),
            {
                'plan': self.plan.pk,
                'switch_class_id': 'views-mesh-leaf',
                'fabric_name': 'viewsfab',
                'fabric_class': 'managed',
                'hedgehog_role': 'server-leaf',
                'device_type_extension': self.ext.pk,
                'uplink_ports_per_switch': 0,
                'topology_mode': 'mesh',
                'override_quantity': 2,
            }, follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(PlanSwitchClass.objects.filter(
            plan=self.plan, switch_class_id='views-mesh-leaf').exists())

    def test_invalid_mesh_post_no_override_returns_form_error(self):
        self.client.login(username='m317super', password='pass')
        r = self.client.post(
            reverse('plugins:netbox_hedgehog:planswitchclass_add'),
            {
                'plan': self.plan.pk,
                'switch_class_id': 'views-bad-leaf',
                'fabric_name': 'viewsbad',
                'fabric_class': 'managed',
                'hedgehog_role': 'server-leaf',
                'device_type_extension': self.ext.pk,
                'uplink_ports_per_switch': 0,
                'topology_mode': 'mesh',
                # override_quantity intentionally omitted
            }, follow=False)
        self.assertEqual(r.status_code, 200)  # form re-rendered
        self.assertFalse(PlanSwitchClass.objects.filter(
            plan=self.plan, switch_class_id='views-bad-leaf').exists())

    def test_without_permission_returns_403(self):
        self.client.login(username='m317plain', password='pass')
        r = self.client.get(reverse(
            'plugins:netbox_hedgehog:planswitchclass_add'))
        self.assertIn(r.status_code, (403, 302))


# ---------------------------------------------------------------------------
# 10. Full-capacity multi-link mesh generation (#548 RED)
#
# Fails until GREEN (#546): _compute_cables_per_pair doesn't exist and
# current _create_mesh_connections() allocates count=1 per PlanMeshLink.
# ---------------------------------------------------------------------------

class Mesh544FullCapacityTests(TestCase):
    """
    RED tests for #548: full-capacity parallel link generation for explicit mesh fabrics.

    Current bottleneck: _create_mesh_connections() calls
    _allocate_ports_for_zones(..., count=1) per PlanMeshLink, producing
    exactly one cable per switch pair regardless of mesh zone port count.

    These tests will all be RED until GREEN (#546) implements:
    - _compute_cables_per_pair() helper
    - batch allocation (count=cables_per_pair)
    - zip-loop cable creation
    """

    @classmethod
    def setUpTestData(cls):
        _, _, cls.ext = _mfr_dt_ext()
        cls.site = _site()

    def _gen(self, plan):
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        return DeviceGenerator(plan, site=self.site).generate_all()

    def _make_gen(self, plan):
        """Return a DeviceGenerator instance without running generate_all()."""
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        return DeviceGenerator(plan, site=self.site)

    def _cable_count(self, plan):
        from dcim.models import Cable
        return Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()

    # -------------------------------------------------------------------
    # Section 1: _compute_cables_per_pair helper unit tests
    # All RED via AttributeError — method does not exist yet.
    # -------------------------------------------------------------------

    def test_helper_2switch_full_capacity_returns_N(self):
        """_compute_cables_per_pair: 2-switch, 4-port zone → 4."""
        plan = _plan('M544 Helper 2sw')
        sc = _mesh_sc(plan, self.ext, sc_id='h2sw-leaf', qty=2)
        _mesh_zone(sc, port_spec='1-4')
        gen = self._make_gen(plan)
        mesh_classes = list(plan.switch_classes.filter(fabric_name='backend'))
        result = gen._compute_cables_per_pair('backend', 2, mesh_classes)
        self.assertEqual(result, 4)

    def test_helper_3switch_divisible_capacity_returns_half(self):
        """_compute_cables_per_pair: 3-switch, 4-port zone → 4 // 2 = 2."""
        plan = _plan('M544 Helper 3sw')
        sc = _mesh_sc(plan, self.ext, sc_id='h3sw-leaf', qty=3)
        _mesh_zone(sc, port_spec='1-4')
        gen = self._make_gen(plan)
        mesh_classes = list(plan.switch_classes.filter(fabric_name='backend'))
        result = gen._compute_cables_per_pair('backend', 3, mesh_classes)
        self.assertEqual(result, 2)

    def test_helper_asymmetric_capacity_raises_validation_error(self):
        """_compute_cables_per_pair: class A (2 ports) vs class B (4 ports) → ValidationError."""
        plan = _plan('M544 Helper Asym')
        sc_a = _mesh_sc(plan, self.ext, sc_id='hasym-leaf-a', qty=1, fabric='hasym-fab')
        sc_b = _mesh_sc(plan, self.ext, sc_id='hasym-leaf-b', qty=1, fabric='hasym-fab')
        _mesh_zone(sc_a, zone_name='mesh-a', port_spec='1-2')
        _mesh_zone(sc_b, zone_name='mesh-b', port_spec='1-4')
        gen = self._make_gen(plan)
        mesh_classes = list(plan.switch_classes.filter(fabric_name='hasym-fab'))
        with self.assertRaises(ValidationError) as ctx:
            gen._compute_cables_per_pair('hasym-fab', 2, mesh_classes)
        self.assertIn('asymmetric', str(ctx.exception).lower())

    def test_helper_3switch_non_divisible_capacity_raises_validation_error(self):
        """_compute_cables_per_pair: 3-switch, 3-port zone (odd) → ValidationError."""
        plan = _plan('M544 Helper Odd')
        sc = _mesh_sc(plan, self.ext, sc_id='hodd-leaf', qty=3)
        _mesh_zone(sc, port_spec='1-3')
        gen = self._make_gen(plan)
        mesh_classes = list(plan.switch_classes.filter(fabric_name='backend'))
        with self.assertRaises(ValidationError) as ctx:
            gen._compute_cables_per_pair('backend', 3, mesh_classes)
        self.assertIn('divisible', str(ctx.exception).lower())

    # -------------------------------------------------------------------
    # Section 2: Generation behavior
    # T1, T2 fail RED (cable count wrong). T5/T6/T7 pass RED and GREEN.
    # -------------------------------------------------------------------

    def test_2switch_N_port_zone_creates_N_cables(self):
        """2-switch, port_spec='1-4' → 4 cables. RED: current code creates 1."""
        plan = _plan('M544 Gen 2sw 4port')
        sc = _mesh_sc(plan, self.ext, sc_id='g2n-leaf', qty=2)
        _mesh_zone(sc, port_spec='1-4')
        self._gen(plan)
        self.assertEqual(self._cable_count(plan), 4)

    def test_3switch_even_capacity_splits_evenly(self):
        """3-switch, port_spec='1-4' (4 ports) → 2 cables/pair, 6 total. RED: current code creates 3."""
        plan = _plan('M544 Gen 3sw 4port')
        sc = _mesh_sc(plan, self.ext, sc_id='g3ev-leaf', qty=3)
        _mesh_zone(sc, port_spec='1-4')
        self._gen(plan)
        self.assertEqual(self._cable_count(plan), 6)

    def test_2switch_single_port_still_creates_one_cable(self):
        """Regression: 2-switch, port_spec='1-1' → 1 cable. Passes RED and GREEN."""
        plan = _plan('M544 Reg 2sw 1port')
        sc = _mesh_sc(plan, self.ext, sc_id='g1reg-leaf', qty=2)
        _mesh_zone(sc, port_spec='1-1')
        self._gen(plan)
        self.assertEqual(self._cable_count(plan), 1)

    def test_3switch_2port_creates_1_cable_per_pair(self):
        """Regression: 3-switch, port_spec='1-2' → 1 cable/pair, 3 total. Passes RED and GREEN."""
        plan = _plan('M544 Reg 3sw 2port')
        sc = _mesh_sc(plan, self.ext, sc_id='g3reg-leaf', qty=3)
        _mesh_zone(sc, port_spec='1-2')
        self._gen(plan)
        self.assertEqual(self._cable_count(plan), 3)

    def test_planmeshlink_leaf1_port_is_first_allocated_port(self):
        """PlanMeshLink.leaf1_port stores the first port from the batch (E1/1 for port_spec='1-4')."""
        plan = _plan('M544 MeshLink FirstPort')
        sc = _mesh_sc(plan, self.ext, sc_id='fp4-leaf', qty=2)
        _mesh_zone(sc, port_spec='1-4')
        self._gen(plan)
        link = PlanMeshLink.objects.get(plan=plan)
        self.assertEqual(link.leaf1_port, 'E1/1')
        self.assertEqual(link.leaf2_port, 'E1/1')

    # -------------------------------------------------------------------
    # Section 3: Validation failures (new error substrings)
    # Both fail RED — current code raises no error for these cases.
    # -------------------------------------------------------------------

    def test_asymmetric_capacity_raises_before_allocation(self):
        """
        Two switch classes with mismatched mesh port counts → ValidationError with 'asymmetric'.
        RED: current code performs no symmetry check; 1 cable is created silently.
        Confirmed clean fail: no cables and no devices must exist after the exception.
        """
        from dcim.models import Cable, Device
        plan = _plan('M544 Val Asym')
        sc_a = _mesh_sc(plan, self.ext, sc_id='va-leaf-a', qty=1, fabric='va-fab')
        sc_b = _mesh_sc(plan, self.ext, sc_id='va-leaf-b', qty=1, fabric='va-fab')
        _mesh_zone(sc_a, zone_name='mesh-a', port_spec='1-2')
        _mesh_zone(sc_b, zone_name='mesh-b', port_spec='1-4')
        with self.assertRaises(ValidationError) as ctx:
            self._gen(plan)
        self.assertIn('asymmetric', str(ctx.exception).lower())
        self.assertEqual(
            Cable.objects.filter(
                custom_field_data__hedgehog_plan_id=str(plan.pk)
            ).count(), 0,
            "No cables should be created when asymmetric validation fires",
        )

    def test_3switch_non_divisible_capacity_raises_before_allocation(self):
        """
        3-switch, port_spec='1-3' (odd) → ValidationError mentioning divisibility.
        RED: current code raises no error; it creates 3 cables (1 per pair).
        """
        from dcim.models import Cable
        plan = _plan('M544 Val Odd3')
        sc = _mesh_sc(plan, self.ext, sc_id='vodd3-leaf', qty=3)
        _mesh_zone(sc, port_spec='1-3')
        with self.assertRaises(ValidationError) as ctx:
            self._gen(plan)
        err = str(ctx.exception).lower()
        self.assertTrue(
            'divisible' in err,
            f"Expected 'divisible' in ValidationError message, got: {ctx.exception}",
        )
        self.assertEqual(
            Cable.objects.filter(
                custom_field_data__hedgehog_plan_id=str(plan.pk)
            ).count(), 0,
            "No cables should be created when divisibility validation fires",
        )

    # -------------------------------------------------------------------
    # Section 4: Canonical motivating case (XOC-64 style)
    # -------------------------------------------------------------------

    def test_xoc64_style_32port_2switch_mesh_creates_32_cables(self):
        """
        XOC-64 motivating case: 2-switch, 32 odd-numbered mesh ports per switch → 32 cables.
        port_spec='1-63:2' → [1,3,5,...,63] = 32 ports.
        RED: current code creates exactly 1 cable.
        """
        plan = _plan('M544 XOC64 32port')
        sc = _mesh_sc(plan, self.ext, sc_id='xoc64-leaf', qty=2, fabric='scale-out')
        _mesh_zone(sc, zone_name='mesh-800', port_spec='1-63:2')
        self._gen(plan)
        self.assertEqual(self._cable_count(plan), 32)

    # -------------------------------------------------------------------
    # Section 5: Export regression guard
    # -------------------------------------------------------------------

    def test_mesh_export_crd_aggregates_all_cables_per_pair(self):
        """
        Export regression guard: after generating a 2-switch 4-port mesh,
        _generate_connection_crds() produces exactly 1 mesh CRD with 4 links.

        Verifies that yaml_generator.py already aggregates mesh cables by pair
        (mesh_links_by_pair dict) and passes the full list to _create_mesh_crd().

        RED: current generation creates 1 cable → CRD has 1 link, not 4.
        GREEN: 4 cables → 1 CRD with 4 links.

        Stop condition check: if this test fails for a reason other than link count
        (e.g., 0 mesh CRDs returned), the exporter aggregation is broken and
        GREEN scope must be reassessed before proceeding.
        """
        from netbox_hedgehog.services.yaml_generator import YAMLGenerator
        plan = _plan('M544 Export 4link')
        sc = _mesh_sc(plan, self.ext, sc_id='exp4l-leaf', qty=2, fabric='exp4-fab')
        _mesh_zone(sc, zone_name='mesh-exp', port_spec='1-4')
        self._gen(plan)

        gen = YAMLGenerator(plan=plan)
        conn_crds = gen._generate_connection_crds()
        mesh_crds = [c for c in conn_crds if 'mesh' in c.get('spec', {})]

        self.assertEqual(
            len(mesh_crds), 1,
            f"Expected exactly 1 mesh CRD; got {len(mesh_crds)}. "
            "If 0: exporter aggregation is broken — stop and report before GREEN.",
        )
        links = mesh_crds[0]['spec']['mesh']['links']
        self.assertEqual(
            len(links), 4,
            f"Expected 4 links in mesh CRD (one per cable), got {len(links)}. "
            "With current code this is 1 (RED). After GREEN it should be 4.",
        )
