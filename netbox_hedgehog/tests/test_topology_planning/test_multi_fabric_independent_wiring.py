"""RED tests: per-managed-fabric independent wiring artifacts (Epic #287 Phase 3)."""
import os
import tempfile
import yaml
from django.core.management import call_command
from django.test import TestCase
from dcim.models import Cable, Device, DeviceRole, DeviceType, Interface, InterfaceTemplate, Manufacturer, Site
from netbox_hedgehog.choices import FabricClassChoices, GenerationStatusChoices
from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension, GenerationState, PlanMCLAGDomain, PlanSwitchClass, TopologyPlan,
)
from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan


def _kinds(content):
    counts = {}
    for doc in yaml.safe_load_all(content):
        if isinstance(doc, dict) and 'kind' in doc:
            k = doc['kind']
            counts[k] = counts.get(k, 0) + 1
    return counts


def _names_for_kind(content, kind):
    return {
        doc['metadata']['name']
        for doc in yaml.safe_load_all(content)
        if isinstance(doc, dict) and doc.get('kind') == kind
    }


def _conn_switch_names(content):
    names = set()
    for doc in yaml.safe_load_all(content):
        if not isinstance(doc, dict) or doc.get('kind') != 'Connection':
            continue
        spec = doc.get('spec', {})
        port = spec.get('unbundled', {}).get('link', {}).get('switch', {}).get('port', '')
        if port:
            names.add(port.split('/')[0])
    return names


def _make_ext(switch_type):
    ext, _ = DeviceTypeExtension.objects.get_or_create(
        device_type=switch_type,
        defaults={
            'mclag_capable': False, 'hedgehog_roles': ['server-leaf'],
            'native_speed': 100, 'supported_breakouts': ['1x100g'],
            'uplink_ports': 0, 'hedgehog_profile_name': 'mfab287-profile',
        },
    )
    return ext


def _iface(device, name):
    iface, _ = Interface.objects.get_or_create(
        device=device, name=name, defaults={'type': '100gbase-x-qsfp28'},
    )
    return iface


def _cable(plan_id, a, b, zone='server'):
    c = Cable(a_terminations=[a], b_terminations=[b])
    c.custom_field_data = {'hedgehog_plan_id': plan_id, 'hedgehog_zone': zone}
    c.save()
    return c


class _SharedInfra:
    """Mixin: sets up manufacturer, switch/server device types, roles, site."""

    @classmethod
    def _setup_infra(cls):
        mfg, _ = Manufacturer.objects.get_or_create(
            name='MFAB287-Mfg', defaults={'slug': 'mfab287-mfg'},
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=mfg, model='MFAB287-Switch', defaults={'slug': 'mfab287-switch'},
        )
        for n in ('E1/1', 'E1/2', 'E1/3'):
            InterfaceTemplate.objects.get_or_create(
                device_type=cls.switch_type, name=n, defaults={'type': '100gbase-x-qsfp28'},
            )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=mfg, model='MFAB287-Server', defaults={'slug': 'mfab287-server'},
        )
        for n in ('E1/1', 'E1/2'):
            InterfaceTemplate.objects.get_or_create(
                device_type=cls.server_type, name=n, defaults={'type': '100gbase-x-qsfp28'},
            )
        cls.leaf_role, _ = DeviceRole.objects.get_or_create(
            name='MFAB287-Leaf', defaults={'slug': 'mfab287-leaf', 'color': '0000ff'},
        )
        cls.server_role, _ = DeviceRole.objects.get_or_create(
            slug='server', defaults={'name': 'Server', 'color': 'aa1409'},
        )
        cls.site, _ = Site.objects.get_or_create(
            name='MFAB287-Site', defaults={'slug': 'mfab287-site'},
        )
        cls.ext = _make_ext(cls.switch_type)

    @classmethod
    def _make_switch(cls, name, fabric, fabric_class, mac_suffix, plan_id, hedgehog_class=None):
        return Device.objects.create(
            name=name, device_type=cls.switch_type, role=cls.leaf_role, site=cls.site,
            custom_field_data={
                'hedgehog_plan_id': plan_id,
                'hedgehog_fabric': fabric,
                'hedgehog_fabric_class': fabric_class,
                'hedgehog_class': hedgehog_class or name,
                'hedgehog_role': 'server-leaf',
                'boot_mac': f'0a:bb:01:00:00:{mac_suffix:02x}',
            },
        )

    @classmethod
    def _make_server(cls, name, plan_id):
        return Device.objects.create(
            name=name, device_type=cls.server_type, role=cls.server_role, site=cls.site,
            custom_field_data={'hedgehog_plan_id': plan_id},
        )


class MultiFabricArbitraryNamesExportTestCase(_SharedInfra, TestCase):
    """Two managed fabrics (fabric-alpha, fabric-beta), shared server, unmanaged oob.

    Confirmed RED: T_discovery (plan-first vs inventory-first for split command).
    Baseline confirmations: switch/server/namespace isolation, shared-server duplication.
    """

    @classmethod
    def setUpTestData(cls):
        cls._setup_infra()
        cls.plan = TopologyPlan.objects.create(name='MFAB287 Multi-Fabric Plan')
        GenerationState.objects.create(
            plan=cls.plan, device_count=0, interface_count=0,
            cable_count=0, snapshot={}, status=GenerationStatusChoices.GENERATED,
        )
        pid = str(cls.plan.pk)
        cls.alpha_leaf = cls._make_switch('alpha-leaf-01', 'fabric-alpha', 'managed', 1, pid, 'alpha-leaf-class')
        cls.beta_leaf = cls._make_switch('beta-leaf-01', 'fabric-beta', 'managed', 2, pid, 'beta-leaf-class')
        cls.oob_switch = cls._make_switch('oob-switch-01', 'mgmt-fabric', 'unmanaged', 3, pid)
        cls.server_alpha = cls._make_server('server-alpha-only', pid)
        cls.server_beta = cls._make_server('server-beta-only', pid)
        cls.server_shared = cls._make_server('server-shared', pid)
        _cable(pid, _iface(cls.server_alpha, 'E1/1'), _iface(cls.alpha_leaf, 'E1/1'))
        _cable(pid, _iface(cls.server_beta, 'E1/1'), _iface(cls.beta_leaf, 'E1/1'))
        _cable(pid, _iface(cls.server_shared, 'E1/1'), _iface(cls.alpha_leaf, 'E1/2'))
        _cable(pid, _iface(cls.server_shared, 'E1/2'), _iface(cls.beta_leaf, 'E1/2'))

    # --- Switch isolation (baseline) ---
    def test_alpha_export_includes_alpha_switch(self):
        self.assertIn('alpha-leaf-01', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-alpha'), 'Switch'))

    def test_alpha_export_excludes_beta_switch(self):
        self.assertNotIn('beta-leaf-01', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-alpha'), 'Switch'))

    def test_beta_export_includes_beta_switch(self):
        self.assertIn('beta-leaf-01', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-beta'), 'Switch'))

    def test_beta_export_excludes_alpha_switch(self):
        self.assertNotIn('alpha-leaf-01', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-beta'), 'Switch'))

    # --- Server isolation (baseline) ---
    def test_alpha_includes_alpha_only_server(self):
        self.assertIn('server-alpha-only', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-alpha'), 'Server'))

    def test_alpha_excludes_beta_only_server(self):
        self.assertNotIn('server-beta-only', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-alpha'), 'Server'))

    def test_beta_includes_beta_only_server(self):
        self.assertIn('server-beta-only', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-beta'), 'Server'))

    def test_beta_excludes_alpha_only_server(self):
        self.assertNotIn('server-alpha-only', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-beta'), 'Server'))

    # --- Shared server (connection-derived) ---
    def test_shared_server_in_alpha_export(self):
        self.assertIn('server-shared', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-alpha'), 'Server'))

    def test_shared_server_in_beta_export(self):
        self.assertIn('server-shared', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-beta'), 'Server'))

    def test_shared_server_once_in_alpha(self):
        names = [d['metadata']['name'] for d in yaml.safe_load_all(generate_yaml_for_plan(self.plan, fabric='fabric-alpha'))
                 if isinstance(d, dict) and d.get('kind') == 'Server']
        self.assertEqual(names.count('server-shared'), 1)

    def test_shared_server_once_in_beta(self):
        names = [d['metadata']['name'] for d in yaml.safe_load_all(generate_yaml_for_plan(self.plan, fabric='fabric-beta'))
                 if isinstance(d, dict) and d.get('kind') == 'Server']
        self.assertEqual(names.count('server-shared'), 1)

    # --- Connection scoping ---
    def test_alpha_connections_only_reference_alpha_switches(self):
        self.assertNotIn('beta-leaf-01', _conn_switch_names(generate_yaml_for_plan(self.plan, fabric='fabric-alpha')))

    def test_beta_connections_only_reference_beta_switches(self):
        self.assertNotIn('alpha-leaf-01', _conn_switch_names(generate_yaml_for_plan(self.plan, fabric='fabric-beta')))

    # --- Namespaces ---
    def test_alpha_export_has_namespaces(self):
        k = _kinds(generate_yaml_for_plan(self.plan, fabric='fabric-alpha'))
        self.assertIn('VLANNamespace', k)
        self.assertIn('IPv4Namespace', k)

    def test_beta_export_has_namespaces(self):
        k = _kinds(generate_yaml_for_plan(self.plan, fabric='fabric-beta'))
        self.assertIn('VLANNamespace', k)
        self.assertIn('IPv4Namespace', k)

    # --- Unmanaged exclusion ---
    def test_unmanaged_not_in_alpha_export(self):
        content = generate_yaml_for_plan(self.plan, fabric='fabric-alpha')
        self.assertNotIn('oob-switch-01', _names_for_kind(content, 'Switch') | _names_for_kind(content, 'Server'))

    def test_unmanaged_not_in_beta_export(self):
        content = generate_yaml_for_plan(self.plan, fabric='fabric-beta')
        self.assertNotIn('oob-switch-01', _names_for_kind(content, 'Switch') | _names_for_kind(content, 'Server'))

    # --- split-by-fabric ---
    def test_split_writes_arbitrary_named_files(self):
        with tempfile.TemporaryDirectory() as d:
            call_command('export_wiring_yaml', str(self.plan.pk), '--output', os.path.join(d, 'w'), '--split-by-fabric')
            self.assertTrue(os.path.exists(os.path.join(d, 'w-fabric-alpha.yaml')))
            self.assertTrue(os.path.exists(os.path.join(d, 'w-fabric-beta.yaml')))

    def test_split_alpha_equivalent_to_fabric_flag(self):
        """Full artifact equivalence: split file must match direct --fabric export for ALL CRD kinds.

        CONFIRMED RED: current split command uses plan-first fabric discovery which can produce
        differently scoped Connection and SwitchGroup CRDs compared to the direct generator path.
        Weak 4-kind check may pass accidentally; this full-equivalence check will catch divergence
        in Connection, SwitchGroup, or any other CRD kind.
        """
        direct = generate_yaml_for_plan(self.plan, fabric='fabric-alpha')
        with tempfile.TemporaryDirectory() as d:
            call_command('export_wiring_yaml', str(self.plan.pk), '--output', os.path.join(d, 'w'), '--split-by-fabric')
            with open(os.path.join(d, 'w-fabric-alpha.yaml')) as f:
                split = f.read()
        # Parse both artifacts into sorted doc lists keyed by kind
        def _sorted_docs(content):
            docs = {}
            for doc in yaml.safe_load_all(content):
                if isinstance(doc, dict) and 'kind' in doc:
                    docs.setdefault(doc['kind'], []).append(doc)
            return {k: sorted(v, key=lambda d: d.get('metadata', {}).get('name', '')) for k, v in docs.items()}
        direct_docs = _sorted_docs(direct)
        split_docs = _sorted_docs(split)
        all_kinds = set(direct_docs) | set(split_docs)
        for kind in sorted(all_kinds):
            self.assertEqual(
                direct_docs.get(kind, []),
                split_docs.get(kind, []),
                f'{kind} CRDs differ between --fabric=fabric-alpha and split artifact',
            )

    def test_invalid_fabric_name_raises(self):
        with self.assertRaises(ValueError):
            generate_yaml_for_plan(self.plan, fabric='does-not-exist')


class SwitchGroupFabricScopeTestCase(_SharedInfra, TestCase):
    """SwitchGroup CRDs must be scoped to the fabric of their referenced switches.

    CONFIRMED RED (T_beta_absent_from_alpha, T_alpha_absent_from_beta):
    Current _generate_switchgroups() emits all PlanMCLAGDomain groups plan-globally.
    """

    @classmethod
    def setUpTestData(cls):
        cls._setup_infra()
        cls.plan = TopologyPlan.objects.create(name='MFAB287 SwitchGroup Plan')
        GenerationState.objects.create(
            plan=cls.plan, device_count=0, interface_count=0,
            cable_count=0, snapshot={}, status=GenerationStatusChoices.GENERATED,
        )
        pid = str(cls.plan.pk)
        alpha_sc = PlanSwitchClass.objects.create(
            plan=cls.plan, switch_class_id='sg287-alpha-class',
            fabric_name='fabric-alpha', fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf', device_type_extension=cls.ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            calculated_quantity=1, override_quantity=1,
            redundancy_type='eslag', redundancy_group='alpha-sg-group',
        )
        beta_sc = PlanSwitchClass.objects.create(
            plan=cls.plan, switch_class_id='sg287-beta-class',
            fabric_name='fabric-beta', fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf', device_type_extension=cls.ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            calculated_quantity=1, override_quantity=1,
            redundancy_type='eslag', redundancy_group='beta-sg-group',
        )
        PlanMCLAGDomain.objects.create(
            plan=cls.plan, domain_id='alpha-mclag-287', switch_class=alpha_sc,
            peer_link_count=2, session_link_count=2, switch_group_name='alpha-sg-group',
        )
        PlanMCLAGDomain.objects.create(
            plan=cls.plan, domain_id='beta-mclag-287', switch_class=beta_sc,
            peer_link_count=2, session_link_count=2, switch_group_name='beta-sg-group',
        )
        cls._make_switch('sg287-alpha-pair-01', 'fabric-alpha', 'managed', 10, pid, 'sg287-alpha-class')
        cls._make_switch('sg287-beta-pair-01', 'fabric-beta', 'managed', 11, pid, 'sg287-beta-class')

    def test_alpha_group_in_alpha_export(self):
        self.assertIn('alpha-sg-group', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-alpha'), 'SwitchGroup'))

    def test_beta_group_absent_from_alpha_export(self):
        """CONFIRMED RED: current code leaks all SwitchGroups globally."""
        self.assertNotIn('beta-sg-group', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-alpha'), 'SwitchGroup'))

    def test_beta_group_in_beta_export(self):
        self.assertIn('beta-sg-group', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-beta'), 'SwitchGroup'))

    def test_alpha_group_absent_from_beta_export(self):
        """CONFIRMED RED: current code leaks all SwitchGroups globally."""
        self.assertNotIn('alpha-sg-group', _names_for_kind(generate_yaml_for_plan(self.plan, fabric='fabric-beta'), 'SwitchGroup'))

    def test_full_export_has_both_groups(self):
        groups = _names_for_kind(generate_yaml_for_plan(self.plan), 'SwitchGroup')
        self.assertIn('alpha-sg-group', groups)
        self.assertIn('beta-sg-group', groups)

    def test_no_dangling_switchgroup_refs_in_alpha(self):
        content = generate_yaml_for_plan(self.plan, fabric='fabric-alpha')
        docs = [d for d in yaml.safe_load_all(content) if d]
        sg_names = {d['metadata']['name'] for d in docs if d.get('kind') == 'SwitchGroup'}
        for doc in docs:
            if doc.get('kind') == 'Switch':
                for g in doc.get('spec', {}).get('groups', []):
                    self.assertIn(g, sg_names, f"Switch references group '{g}' absent from export")


class DegenerateScopedExportTestCase(_SharedInfra, TestCase):
    """Empty-fabric export must yield namespace-only artifact without raising.

    ALL CONFIRMED RED: current code raises ValueError('No managed fabrics found')
    at yaml_generator.py L95-96 when managed_switch_ids is empty for a scoped export.
    """

    @classmethod
    def setUpTestData(cls):
        cls._setup_infra()
        cls.plan = TopologyPlan.objects.create(name='MFAB287 Degenerate Plan')
        GenerationState.objects.create(
            plan=cls.plan, device_count=0, interface_count=0,
            cable_count=0, snapshot={}, status=GenerationStatusChoices.GENERATED,
        )
        PlanSwitchClass.objects.create(
            plan=cls.plan, switch_class_id='degen287-class',
            fabric_name='fabric-empty', fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role='server-leaf', device_type_extension=cls.ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            calculated_quantity=0, override_quantity=0,
        )
        # Intentionally NO devices with hedgehog_fabric='fabric-empty'

    def _get_content(self):
        return generate_yaml_for_plan(self.plan, fabric='fabric-empty')

    def test_empty_fabric_export_does_not_raise(self):
        """CONFIRMED RED: raises ValueError on current code."""
        try:
            self._get_content()
        except ValueError as e:
            self.fail(f'generate_yaml_for_plan raised ValueError for empty fabric: {e}')

    def test_empty_fabric_has_vlan_namespace(self):
        """CONFIRMED RED: blocked by same ValueError."""
        self.assertIn('VLANNamespace', _kinds(self._get_content()))

    def test_empty_fabric_has_ipv4_namespace(self):
        """CONFIRMED RED: blocked by same ValueError."""
        self.assertIn('IPv4Namespace', _kinds(self._get_content()))

    def test_empty_fabric_has_no_switches(self):
        """CONFIRMED RED: blocked by same ValueError."""
        self.assertEqual(_kinds(self._get_content()).get('Switch', 0), 0)

    def test_empty_fabric_has_no_servers(self):
        """CONFIRMED RED: blocked by same ValueError."""
        self.assertEqual(_kinds(self._get_content()).get('Server', 0), 0)

    def test_empty_fabric_has_no_connections(self):
        """CONFIRMED RED: blocked by same ValueError.

        A namespace-only (empty-fabric) artifact must contain zero Connection CRDs.
        No switches -> no server connections -> no Connection documents.
        """
        self.assertEqual(_kinds(self._get_content()).get('Connection', 0), 0)


class DiscoveryOrderTestCase(_SharedInfra, TestCase):
    """Managed-fabric discovery must be inventory-first, plan-second.

    Fixture deliberately has fabric-gamma in plan switch classes but NOT in inventory.
    CONFIRMED RED for test_split_excludes_gamma_file: current command is plan-first,
    finds fabric-gamma, tries to generate it, YAMLGenerator raises ValueError
    (gamma not in inventory-derived valid_fabrics) -> CommandError.
    """

    @classmethod
    def setUpTestData(cls):
        cls._setup_infra()
        cls.plan = TopologyPlan.objects.create(name='MFAB287 Discovery Order Plan')
        GenerationState.objects.create(
            plan=cls.plan, device_count=0, interface_count=0,
            cable_count=0, snapshot={}, status=GenerationStatusChoices.GENERATED,
        )
        pid = str(cls.plan.pk)
        for fab, sc_id in (('fabric-alpha', 'disc287-alpha'), ('fabric-beta', 'disc287-beta'), ('fabric-gamma', 'disc287-gamma')):
            PlanSwitchClass.objects.create(
                plan=cls.plan, switch_class_id=sc_id,
                fabric_name=fab, fabric_class=FabricClassChoices.MANAGED,
                hedgehog_role='server-leaf', device_type_extension=cls.ext,
                uplink_ports_per_switch=0, mclag_pair=False,
                calculated_quantity=1, override_quantity=1,
            )
        # Inventory: only fabric-alpha and fabric-beta devices (NOT gamma)
        cls._make_switch('disc287-alpha-leaf-01', 'fabric-alpha', 'managed', 20, pid, 'disc287-alpha')
        cls._make_switch('disc287-beta-leaf-01', 'fabric-beta', 'managed', 21, pid, 'disc287-beta')

    def test_split_excludes_gamma_file(self):
        """CONFIRMED RED: plan-first command includes gamma, generator rejects it -> CommandError."""
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, 'w')
            # Must succeed (no CommandError) and write only alpha+beta
            call_command('export_wiring_yaml', str(self.plan.pk), '--output', base, '--split-by-fabric')
            self.assertTrue(os.path.exists(f'{base}-fabric-alpha.yaml'))
            self.assertTrue(os.path.exists(f'{base}-fabric-beta.yaml'))
            self.assertFalse(os.path.exists(f'{base}-fabric-gamma.yaml'),
                             'gamma has no inventory; inventory-first discovery must exclude it')

    def test_gamma_fabric_invalid_for_generator(self):
        """gamma is plan-only; generate_yaml_for_plan must reject it (not in inventory)."""
        with self.assertRaises(ValueError):
            generate_yaml_for_plan(self.plan, fabric='fabric-gamma')
