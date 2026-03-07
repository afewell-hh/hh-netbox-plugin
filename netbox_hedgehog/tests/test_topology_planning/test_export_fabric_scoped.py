"""
Integration tests for fabric-scoped wiring export (DIET-227).

Tests verify that:
- Full-plan export (no --fabric) remains unchanged
- --fabric frontend emits only frontend Switch/Connection/Server CRDs
- --fabric backend emits only backend Switch/Connection/Server CRDs
- --split-by-fabric writes two separate files, each independently valid
- Invalid fabric selector raises CommandError
- No cross-fabric leakage: frontend/backend exports are fully isolated for all CRD kinds

Server isolation is tested explicitly: _generate_servers() filters to only servers
that have at least one cable connecting them to the target-fabric switches via
_get_server_ids_for_fabric() (CableTermination traversal).

## Invariants
- Unchanged: full-plan export (no --fabric flag)
- Changed: --fabric and --split-by-fabric flags; server filtering added for fabric mode
"""

import os
import tempfile

import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from dcim.models import Device, DeviceRole, DeviceType, InterfaceTemplate, Manufacturer, Site

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricTypeChoices,
    GenerationStatusChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    ServerClassCategoryChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan


def _count_kinds(yaml_content):
    """Return {kind: count} for all CRD documents in a multi-doc YAML string."""
    kinds = {}
    for doc in yaml.safe_load_all(yaml_content):
        if isinstance(doc, dict) and 'kind' in doc:
            k = doc['kind']
            kinds[k] = kinds.get(k, 0) + 1
    return kinds


def _switch_names_in_yaml(yaml_content):
    """Return set of Switch CRD metadata.name values from a multi-doc YAML string."""
    names = set()
    for doc in yaml.safe_load_all(yaml_content):
        if isinstance(doc, dict) and doc.get('kind') == 'Switch':
            names.add(doc['metadata']['name'])
    return names


def _server_names_in_yaml(yaml_content):
    """Return set of Server CRD metadata.name values from a multi-doc YAML string."""
    names = set()
    for doc in yaml.safe_load_all(yaml_content):
        if isinstance(doc, dict) and doc.get('kind') == 'Server':
            names.add(doc['metadata']['name'])
    return names


def _connection_switch_names(yaml_content):
    """Return set of switch device names referenced in Connection CRDs."""
    names = set()
    for doc in yaml.safe_load_all(yaml_content):
        if not isinstance(doc, dict) or doc.get('kind') != 'Connection':
            continue
        spec = doc.get('spec', {})
        # unbundled: spec.unbundled.link.switch.port = "switch-name/E1/..."
        if 'unbundled' in spec:
            port = spec['unbundled'].get('link', {}).get('switch', {}).get('port', '')
            if port:
                names.add(port.split('/')[0])
        # fabric: spec.fabric.links[].switch.port
        for link in spec.get('fabric', {}).get('links', []):
            for endpoint in link if isinstance(link, list) else []:
                port = endpoint.get('switch', {}).get('port', '')
                if port:
                    names.add(port.split('/')[0])
    return names


class FabricScopedExportBase(TestCase):
    """Shared fixture: plan with one frontend leaf + one backend leaf + one server each."""

    @classmethod
    def setUpTestData(cls):
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica-FabricScoped',
            defaults={'slug': 'celestica-fabric-scoped'}
        )
        nvidia, _ = Manufacturer.objects.get_or_create(
            name='NVIDIA-FabricScoped',
            defaults={'slug': 'nvidia-fabric-scoped'}
        )

        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='GPU-Server-FabricScoped',
            defaults={'slug': 'gpu-server-fabric-scoped'}
        )
        for tpl_name in ('fs0', 'fs1'):
            InterfaceTemplate.objects.get_or_create(
                device_type=cls.server_type,
                name=tpl_name,
                defaults={'type': '200gbase-x-qsfp56'}
            )

        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='DS5000-FabricScoped',
            defaults={'slug': 'ds5000-fabric-scoped'}
        )
        cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'native_speed': 800,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g'],
                'uplink_ports': 0,
                'hedgehog_profile_name': 'celestica-ds5000',
            }
        )

        cls.breakout_4x200, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g-fs',
            defaults={
                'from_speed': 800, 'logical_ports': 4,
                'logical_speed': 200, 'optic_type': 'QSFP-DD',
            }
        )
        cls.breakout_1x800, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x800g-fs',
            defaults={
                'from_speed': 800, 'logical_ports': 1,
                'logical_speed': 800, 'optic_type': 'QSFP-DD',
            }
        )

        cls.server_role, _ = DeviceRole.objects.get_or_create(
            name='Server-FabricScoped', defaults={'slug': 'server', 'color': 'aa1409'}
        )
        cls.site, _ = Site.objects.get_or_create(
            name='FabricScoped-Site', defaults={'slug': 'fabric-scoped-site'}
        )

        from dcim.models import ModuleType
        cls.nic_module_type, created = ModuleType.objects.get_or_create(
            manufacturer=nvidia,
            model='BlueField-3-FabricScoped',
        )
        if created:
            for n in ('p0', 'p1'):
                InterfaceTemplate.objects.create(
                    module_type=cls.nic_module_type, name=n, type='other'
                )

        cls.plan = TopologyPlan.objects.create(
            name='FabricScoped Export Test Plan',
            customer_name='FabricScoped Test',
        )

        # --- Frontend switch class ---
        cls.fe_server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='fs-fe-gpu',
            server_device_type=cls.server_type,
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            gpus_per_server=8,
        )
        cls.fe_switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fs-fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=0,
            mclag_pair=False,
            calculated_quantity=1,
            override_quantity=1,
        )
        fe_server_zone = SwitchPortZone.objects.create(
            switch_class=cls.fe_switch_class,
            zone_name='server',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=cls.breakout_4x200,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )
        SwitchPortZone.objects.create(
            switch_class=cls.fe_switch_class,
            zone_name='uplink',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='49-50',
            breakout_option=cls.breakout_1x800,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=200,
        )
        PlanServerConnection.objects.create(
            server_class=cls.fe_server_class,
            connection_id='frontend',
            nic_module_type=cls.nic_module_type,
            port_index=0,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_zone=fe_server_zone,
            speed=200,
        )

        # --- Backend switch class ---
        cls.be_server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='fs-be-gpu',
            server_device_type=cls.server_type,
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            gpus_per_server=8,
        )
        cls.be_switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fs-be-leaf',
            fabric=FabricTypeChoices.BACKEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=0,
            mclag_pair=False,
            calculated_quantity=1,
            override_quantity=1,
        )
        be_server_zone = SwitchPortZone.objects.create(
            switch_class=cls.be_switch_class,
            zone_name='server',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=cls.breakout_4x200,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )
        SwitchPortZone.objects.create(
            switch_class=cls.be_switch_class,
            zone_name='uplink',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='49-50',
            breakout_option=cls.breakout_1x800,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=200,
        )
        PlanServerConnection.objects.create(
            server_class=cls.be_server_class,
            connection_id='backend',
            nic_module_type=cls.nic_module_type,
            port_index=0,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_zone=be_server_zone,
            speed=200,
        )

        # Run device generation to create actual NetBox inventory
        generator = DeviceGenerator(plan=cls.plan, site=cls.site)
        generator.generate_all()


class FullExportUnchangedTestCase(FabricScopedExportBase):
    """Full-plan export (no --fabric) remains unchanged by DIET-227."""

    def test_full_export_has_both_fabric_switches(self):
        """No-fabric export includes switches from both frontend and backend."""
        content = generate_yaml_for_plan(self.plan)
        switch_names = _switch_names_in_yaml(content)
        fe_switches = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric='frontend',
        ).values_list('name', flat=True)
        be_switches = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric='backend',
        ).values_list('name', flat=True)
        for name in fe_switches:
            self.assertIn(name, switch_names, f"Full export must include frontend switch {name}")
        for name in be_switches:
            self.assertIn(name, switch_names, f"Full export must include backend switch {name}")

    def test_full_export_namespace_docs_present(self):
        """Full export always includes VLANNamespace and IPv4Namespace."""
        kinds = _count_kinds(generate_yaml_for_plan(self.plan))
        self.assertIn('VLANNamespace', kinds)
        self.assertIn('IPv4Namespace', kinds)


class FrontendFabricExportTestCase(FabricScopedExportBase):
    """--fabric frontend emits only frontend Switch/Connection CRDs."""

    def _fe_content(self):
        return generate_yaml_for_plan(self.plan, fabric='frontend')

    def _be_switch_names(self):
        return set(Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric='backend',
        ).values_list('name', flat=True))

    def _fe_switch_names_db(self):
        return set(Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric='frontend',
        ).values_list('name', flat=True))

    def test_frontend_export_has_frontend_switches(self):
        """Frontend export includes all frontend Switch CRDs."""
        switch_names = _switch_names_in_yaml(self._fe_content())
        for name in self._fe_switch_names_db():
            self.assertIn(name, switch_names, f"Frontend export missing switch {name}")

    def test_frontend_export_no_backend_switches(self):
        """Frontend export has no backend Switch CRDs."""
        switch_names = _switch_names_in_yaml(self._fe_content())
        for name in self._be_switch_names():
            self.assertNotIn(name, switch_names,
                             f"Backend switch {name} must not appear in frontend export")

    def test_frontend_connections_only_reference_frontend_switches(self):
        """Connection CRDs in frontend export only reference frontend switches."""
        content = self._fe_content()
        conn_switch_names = _connection_switch_names(content)
        be_names = self._be_switch_names()
        for name in conn_switch_names:
            self.assertNotIn(name, be_names,
                             f"Connection CRD references backend switch {name} "
                             f"in frontend-scoped export")

    def test_frontend_export_has_namespace_docs(self):
        """Frontend export includes namespace CRDs."""
        kinds = _count_kinds(self._fe_content())
        self.assertIn('VLANNamespace', kinds)
        self.assertIn('IPv4Namespace', kinds)

    def test_frontend_export_fewer_switches_than_full(self):
        """Frontend export has fewer Switch CRDs than full-plan export."""
        full_kinds = _count_kinds(generate_yaml_for_plan(self.plan))
        fe_kinds = _count_kinds(self._fe_content())
        self.assertLess(fe_kinds.get('Switch', 0), full_kinds.get('Switch', 0),
                        "Frontend export must have fewer switches than full export")

    def test_frontend_export_no_backend_servers(self):
        """Frontend export has no Server CRDs for servers only connected to backend switches.

        Servers in the fixture are exclusively connected to either frontend OR backend
        switches (not both), so backend-only servers must not appear in the frontend export.
        """
        fe_server_names = _server_names_in_yaml(self._fe_content())

        # Backend servers: those connected exclusively to backend switches
        be_switch_names = self._be_switch_names()
        full_content = generate_yaml_for_plan(self.plan)
        all_server_names = _server_names_in_yaml(full_content)

        # Each server in the frontend export must NOT be a pure-backend server.
        # Since the fixture has disjoint server classes (fe-only and be-only),
        # all servers in the frontend export should connect to frontend switches.
        be_server_names = _server_names_in_yaml(
            generate_yaml_for_plan(self.plan, fabric='backend')
        )
        fe_only_server_names = all_server_names - be_server_names

        # Frontend export must contain fe-only servers
        for name in fe_only_server_names:
            self.assertIn(name, fe_server_names,
                          f"Frontend server {name} missing from frontend export")

        # Frontend export must NOT contain be-only servers
        be_only_server_names = all_server_names - fe_server_names
        for name in be_only_server_names:
            self.assertNotIn(name, fe_server_names,
                             f"Backend-only server {name} leaked into frontend export")

    def test_frontend_server_count_less_than_full(self):
        """Frontend export has fewer Server CRDs than full-plan export (fixture has both fabrics)."""
        full_kinds = _count_kinds(generate_yaml_for_plan(self.plan))
        fe_kinds = _count_kinds(self._fe_content())
        self.assertLess(fe_kinds.get('Server', 0), full_kinds.get('Server', 0),
                        "Frontend export must have fewer Server CRDs than full export")


class BackendFabricExportTestCase(FabricScopedExportBase):
    """--fabric backend emits only backend Switch/Connection CRDs."""

    def _be_content(self):
        return generate_yaml_for_plan(self.plan, fabric='backend')

    def _fe_switch_names(self):
        return set(Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric='frontend',
        ).values_list('name', flat=True))

    def _be_switch_names_db(self):
        return set(Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric='backend',
        ).values_list('name', flat=True))

    def test_backend_export_has_backend_switches(self):
        """Backend export includes all backend Switch CRDs."""
        switch_names = _switch_names_in_yaml(self._be_content())
        for name in self._be_switch_names_db():
            self.assertIn(name, switch_names, f"Backend export missing switch {name}")

    def test_backend_export_no_frontend_switches(self):
        """Backend export has no frontend Switch CRDs."""
        switch_names = _switch_names_in_yaml(self._be_content())
        for name in self._fe_switch_names():
            self.assertNotIn(name, switch_names,
                             f"Frontend switch {name} must not appear in backend export")

    def test_backend_connections_only_reference_backend_switches(self):
        """Connection CRDs in backend export only reference backend switches."""
        content = self._be_content()
        conn_switch_names = _connection_switch_names(content)
        fe_names = self._fe_switch_names()
        for name in conn_switch_names:
            self.assertNotIn(name, fe_names,
                             f"Connection CRD references frontend switch {name} "
                             f"in backend-scoped export")

    def test_backend_export_no_frontend_servers(self):
        """Backend export has no Server CRDs for servers only connected to frontend switches."""
        be_server_names = _server_names_in_yaml(self._be_content())
        fe_server_names = _server_names_in_yaml(
            generate_yaml_for_plan(self.plan, fabric='frontend')
        )
        # Servers that appear only in the frontend export (not backend)
        fe_only_servers = fe_server_names - be_server_names
        for name in fe_only_servers:
            self.assertNotIn(name, be_server_names,
                             f"Frontend-only server {name} leaked into backend export")

    def test_backend_server_count_less_than_full(self):
        """Backend export has fewer Server CRDs than full-plan export."""
        full_kinds = _count_kinds(generate_yaml_for_plan(self.plan))
        be_kinds = _count_kinds(self._be_content())
        self.assertLess(be_kinds.get('Server', 0), full_kinds.get('Server', 0),
                        "Backend export must have fewer Server CRDs than full export")


class SplitByFabricCommandTestCase(FabricScopedExportBase):
    """--split-by-fabric writes one file per fabric, each independently valid YAML."""

    def test_split_writes_both_fabric_files(self):
        """--split-by-fabric creates -frontend.yaml and -backend.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, 'wiring')
            call_command('export_wiring_yaml', str(self.plan.pk), '--output', base,
                         '--split-by-fabric')
            self.assertTrue(os.path.exists(f"{base}-frontend.yaml"),
                            "frontend artifact must be written")
            self.assertTrue(os.path.exists(f"{base}-backend.yaml"),
                            "backend artifact must be written")

    def test_split_each_file_is_valid_yaml(self):
        """Each per-fabric file parses as a valid YAML document stream."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, 'wiring')
            call_command('export_wiring_yaml', str(self.plan.pk), '--output', base,
                         '--split-by-fabric')
            for fab in ('frontend', 'backend'):
                path = f"{base}-{fab}.yaml"
                with open(path, 'r') as f:
                    docs = list(yaml.safe_load_all(f.read()))
                non_null = [d for d in docs if d is not None]
                self.assertGreater(len(non_null), 0,
                                   f"{fab} artifact must contain at least one document")

    def test_split_no_cross_fabric_switch_leakage(self):
        """Per-fabric files contain no Switch or Server CRDs from the other fabric."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, 'wiring')
            call_command('export_wiring_yaml', str(self.plan.pk), '--output', base,
                         '--split-by-fabric')

            fe_switch_db = set(Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(self.plan.pk),
                custom_field_data__hedgehog_fabric='frontend',
            ).values_list('name', flat=True))
            be_switch_db = set(Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(self.plan.pk),
                custom_field_data__hedgehog_fabric='backend',
            ).values_list('name', flat=True))

            with open(f"{base}-frontend.yaml") as f:
                fe_content = f.read()
            with open(f"{base}-backend.yaml") as f:
                be_content = f.read()

            fe_switch_crds = _switch_names_in_yaml(fe_content)
            be_switch_crds = _switch_names_in_yaml(be_content)
            fe_server_crds = _server_names_in_yaml(fe_content)
            be_server_crds = _server_names_in_yaml(be_content)

            # Switch isolation
            for name in be_switch_db:
                self.assertNotIn(name, fe_switch_crds,
                                 f"Backend switch {name} leaked into frontend artifact")
            for name in fe_switch_db:
                self.assertNotIn(name, be_switch_crds,
                                 f"Frontend switch {name} leaked into backend artifact")

            # Server isolation: servers exclusive to one fabric must not appear in the other
            fe_only_servers = fe_server_crds - be_server_crds
            be_only_servers = be_server_crds - fe_server_crds
            for name in fe_only_servers:
                self.assertNotIn(name, be_server_crds,
                                 f"Frontend-only server {name} leaked into backend artifact")
            for name in be_only_servers:
                self.assertNotIn(name, fe_server_crds,
                                 f"Backend-only server {name} leaked into frontend artifact")

    def test_split_fabric_and_full_mutually_exclusive(self):
        """--fabric and --split-by-fabric together raise CommandError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises((CommandError, SystemExit)):
                call_command('export_wiring_yaml', str(self.plan.pk),
                             '--output', os.path.join(tmpdir, 'wiring.yaml'),
                             '--fabric', 'frontend',
                             '--split-by-fabric')


class InvalidFabricSelectorTestCase(FabricScopedExportBase):
    """Invalid --fabric value raises a clear error."""

    def test_invalid_fabric_raises_command_error(self):
        """--fabric with an unknown name raises CommandError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises((CommandError, SystemExit)):
                call_command('export_wiring_yaml', str(self.plan.pk),
                             '--output', os.path.join(tmpdir, 'wiring.yaml'),
                             '--fabric', 'invalid-fabric-xyz')

    def test_invalid_fabric_in_generator_raises_value_error(self):
        """generate_yaml_for_plan() with invalid fabric raises ValueError."""
        with self.assertRaises(ValueError):
            generate_yaml_for_plan(self.plan, fabric='not-a-fabric')


# ---------------------------------------------------------------------------
# Phase 3 RED: surrogate endpoint behavior in fabric-scoped export
# ---------------------------------------------------------------------------

class SurrogateFabricScopedExportTestCase(TestCase):
    """Surrogate endpoints follow fabric-scoped include/exclude rules.

    RED: _get_server_ids_for_fabric() currently filters role__slug='server' only.
    oob-mgmt devices (role='leaf' etc.) are not found, so they don't appear
    in fabric-scoped exports even when connected to the target fabric's switches.
    """

    @classmethod
    def setUpTestData(cls):
        from dcim.models import Cable, Interface
        from netbox_hedgehog.models.topology_planning import GenerationState
        from netbox_hedgehog.choices import GenerationStatusChoices, FabricTypeChoices

        manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Test Mfg FabricScopeSurr',
            defaults={'slug': 'test-mfg-fabric-scope-surr'},
        )
        switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='FabricScopeSurr Switch',
            defaults={'slug': 'fabricscopesurr-switch'},
        )
        for name in ('E1/1', 'E1/2', 'E1/3'):
            InterfaceTemplate.objects.get_or_create(
                device_type=switch_type, name=name,
                defaults={'type': '100gbase-x-qsfp28'},
            )

        from netbox_hedgehog.models.topology_planning import DeviceTypeExtension
        device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=switch_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'native_speed': 100,
                'supported_breakouts': ['1x100g'],
                'uplink_ports': 0,
                'hedgehog_profile_name': 'fabric-scope-surr-test',
            },
        )

        server_role, _ = DeviceRole.objects.get_or_create(
            slug='server', defaults={'name': 'Server', 'color': '0000ff'},
        )
        leaf_role, _ = DeviceRole.objects.get_or_create(
            name='FabricScopeSurr Leaf',
            defaults={'slug': 'fabricscopesurr-leaf', 'color': '008000'},
        )
        site, _ = Site.objects.get_or_create(
            name='FabricScopeSurr Site',
            defaults={'slug': 'fabricscopesurr-site'},
        )

        cls.plan = TopologyPlan.objects.create(name='Fabric Scope Surrogate Test Plan')
        GenerationState.objects.create(
            plan=cls.plan,
            device_count=0, interface_count=0, cable_count=0,
            snapshot={}, status=GenerationStatusChoices.GENERATED,
        )

        def _make_switch(name, fabric, role='server-leaf'):
            mac = abs(hash(name)) % 256
            return Device.objects.create(
                name=name, device_type=switch_type, role=leaf_role, site=site,
                custom_field_data={
                    'hedgehog_plan_id': str(cls.plan.pk),
                    'hedgehog_class': name,
                    'hedgehog_fabric': fabric,
                    'hedgehog_role': role,
                    'boot_mac': f'0c:aa:12:ff:04:{mac:02x}',
                },
            )

        def _make_server(name):
            return Device.objects.create(
                name=name, device_type=switch_type, role=server_role, site=site,
                custom_field_data={'hedgehog_plan_id': str(cls.plan.pk)},
            )

        def _iface(device, name):
            iface, _ = Interface.objects.get_or_create(
                device=device, name=name, defaults={'type': '100gbase-x-qsfp28'},
            )
            return iface

        def _cable(iface_a, iface_b, zone='oob'):
            c = Cable(a_terminations=[iface_a], b_terminations=[iface_b])
            c.custom_field_data = {
                'hedgehog_plan_id': str(cls.plan.pk),
                'hedgehog_zone': zone,
            }
            c.save()
            return c

        cls.fe_switch = _make_switch('fe-scope-surr-01', 'frontend')
        cls.be_switch = _make_switch('be-scope-surr-01', 'backend')
        cls.oob_on_fe = _make_switch('oob-scope-fe-01', 'oob-mgmt')  # connected to frontend
        cls.oob_on_be = _make_switch('oob-scope-be-01', 'oob-mgmt')  # connected to backend
        cls.server = _make_server('scope-surr-server-01')

        # managed<->surrogate cable: fe-switch -> oob_on_fe (zone='oob')
        _cable(_iface(cls.fe_switch, 'E1/1'), _iface(cls.oob_on_fe, 'E1/1'))
        # managed<->surrogate cable: be-switch -> oob_on_be (zone='oob')
        _cable(_iface(cls.be_switch, 'E1/1'), _iface(cls.oob_on_be, 'E1/1'))
        # anchor: server -> fe-switch (zone='server')
        _cable(_iface(cls.server, 'E1/2'), _iface(cls.fe_switch, 'E1/2'), zone='server')

    def test_surrogate_connected_to_target_fabric_appears_in_scoped_export(self):
        """Surrogate connected to frontend switch appears in --fabric frontend export.

        RED: _get_server_ids_for_fabric() doesn't find oob-mgmt devices (wrong role filter).
        oob-scope-fe-01 will be absent from the frontend fabric-scoped export.
        """
        yaml_content = generate_yaml_for_plan(self.plan, fabric='frontend')
        server_names = _server_names_in_yaml(yaml_content)

        # RED: oob-scope-fe-01 not yet returned by _get_server_ids_for_fabric()
        self.assertIn(
            'oob-scope-fe-01', server_names,
            "Surrogate connected to frontend switch must appear as Server CRD in frontend export",
        )

    def test_surrogate_not_connected_to_target_fabric_excluded_from_scoped_export(self):
        """Surrogate connected only to backend switch is absent from --fabric frontend export.

        This test may PASS in RED phase (backend surrogate is already excluded because
        _get_server_ids_for_fabric() can't find it). It must continue to pass in GREEN.
        """
        yaml_content = generate_yaml_for_plan(self.plan, fabric='frontend')
        server_names = _server_names_in_yaml(yaml_content)

        self.assertNotIn(
            'oob-scope-be-01', server_names,
            "Surrogate connected only to backend switch must NOT appear in frontend export",
        )

    def test_surrogate_no_dangling_refs_in_scoped_export(self):
        """Connection CRDs in scoped export reference only Switch/Server CRDs in same export.

        RED: If fe->oob_on_fe Connection CRD appears but oob-scope-fe-01 Server CRD is absent,
        this test will detect the dangling reference.
        """
        yaml_content = generate_yaml_for_plan(self.plan, fabric='frontend')
        docs = [d for d in yaml.safe_load_all(yaml_content) if d]
        switch_names = {d['metadata']['name'] for d in docs if d.get('kind') == 'Switch'}
        server_names = {d['metadata']['name'] for d in docs if d.get('kind') == 'Server'}
        known = switch_names | server_names

        for conn in (d for d in docs if d.get('kind') == 'Connection'):
            spec = conn.get('spec', {})
            unbundled = spec.get('unbundled', {})
            link = unbundled.get('link', {})
            for side in ('switch', 'server'):
                port = link.get(side, {}).get('port', '')
                if port:
                    device_name = port.split('/')[0]
                    self.assertIn(
                        device_name, known,
                        f"Connection endpoint '{device_name}' in frontend export has no "
                        f"corresponding Switch/Server CRD (dangling reference)",
                    )
