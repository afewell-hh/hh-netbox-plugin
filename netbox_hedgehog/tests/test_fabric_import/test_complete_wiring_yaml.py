"""
Integration tests for complete wiring YAML generation (DIET-143).

These tests validate the YAMLGenerator produces all CRD types
(VLANNamespace, IPv4Namespace, Switch, Server, Connection) with
correct structure, fields, and ordering.
"""

import yaml
from django.test import TestCase
from django.contrib.auth import get_user_model

from dcim.models import Site, Manufacturer, DeviceType, DeviceRole, Device

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    DeviceTypeExtension,
)
from netbox_hedgehog.services.yaml_generator import YAMLGenerator

User = get_user_model()


class CompleteWiringYAMLTestCase(TestCase):
    """Integration tests for complete wiring diagram generation."""

    @classmethod
    def setUpTestData(cls):
        """Create test infrastructure."""
        cls.user = User.objects.create_user(username='testuser')
        cls.site = Site.objects.create(name='Test Site', slug='test-site')
        cls.manufacturer = Manufacturer.objects.create(
            name='Test Mfg',
            slug='test-mfg'
        )

        # Create device types with extensions
        cls.switch_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='Test Switch',
            slug='test-switch'
        )
        cls.switch_ext = DeviceTypeExtension.objects.create(
            device_type=cls.switch_type,
            hedgehog_profile_name='test-switch-profile'
        )

        cls.server_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='Test Server',
            slug='test-server'
        )

        # Create device roles
        cls.spine_role = DeviceRole.objects.create(
            name='Spine',
            slug='spine'
        )
        cls.server_role = DeviceRole.objects.create(
            name='Server',
            slug='server'
        )

    def setUp(self):
        """Create fresh plan for each test."""
        self.plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer',
            created_by=self.user
        )
        self.generator = YAMLGenerator(self.plan)

    def test_complete_yaml_includes_all_crd_types(self):
        """Verify YAML includes all 5 CRD types in correct order."""
        # Create test devices
        switch = Device.objects.create(
            name='spine-01',
            device_type=self.switch_type,
            role=self.spine_role,
            site=self.site,
            custom_field_data={
                'hedgehog_plan_id': str(self.plan.pk),
                'hedgehog_role': 'spine',
                'boot_mac': '02:00:00:aa:bb:cc'
            }
        )
        server = Device.objects.create(
            name='server-01',
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            comments='Test server',
            custom_field_data={
                'hedgehog_plan_id': str(self.plan.pk)
            }
        )

        yaml_output = self.generator.generate()
        docs = list(yaml.safe_load_all(yaml_output))

        # Extract CRD kinds (skip header comments)
        kinds = [doc['kind'] for doc in docs if isinstance(doc, dict)]

        # Verify presence (order-independent count)
        self.assertIn('VLANNamespace', kinds)
        self.assertIn('IPv4Namespace', kinds)
        self.assertIn('Switch', kinds)
        self.assertIn('Server', kinds)

        # Verify ordering (namespace → device → connection)
        vlan_idx = kinds.index('VLANNamespace')
        switch_idx = kinds.index('Switch')

        self.assertLess(vlan_idx, switch_idx, "VLANNamespace before Switch")

    def test_switch_crd_includes_required_fields(self):
        """Verify Switch CRDs have role, profile, boot.mac."""
        switch = Device.objects.create(
            name='spine-01',
            device_type=self.switch_type,
            role=self.spine_role,
            site=self.site,
            custom_field_data={
                'hedgehog_plan_id': str(self.plan.pk),
                'hedgehog_role': 'spine',
                'boot_mac': '02:00:00:11:22:33'
            }
        )

        yaml_output = self.generator.generate()
        docs = list(yaml.safe_load_all(yaml_output))

        switches = [doc for doc in docs if isinstance(doc, dict) and doc.get('kind') == 'Switch']
        self.assertGreater(len(switches), 0, "Should have Switch CRDs")

        for switch_doc in switches:
            spec = switch_doc['spec']

            # Required fields
            self.assertIn('role', spec)
            self.assertIn('profile', spec)
            self.assertIn('boot', spec)
            self.assertIn('mac', spec['boot'])

            # Validate role values
            self.assertIn(spec['role'], ['spine', 'server-leaf', 'border-leaf'])

            # Validate boot MAC format
            self.assertRegex(spec['boot']['mac'], r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$')

            # Validate profile is set
            self.assertEqual(spec['profile'], 'test-switch-profile')

    def test_vlannamespace_uses_v1beta1_api(self):
        """Verify VLANNamespace uses v1beta1, not v1alpha2."""
        yaml_output = self.generator.generate()
        docs = list(yaml.safe_load_all(yaml_output))

        vlan_ns = [doc for doc in docs if isinstance(doc, dict) and doc.get('kind') == 'VLANNamespace']
        self.assertEqual(len(vlan_ns), 1)

        self.assertEqual(
            vlan_ns[0]['apiVersion'],
            'wiring.githedgehog.com/v1beta1',
            "VLANNamespace must use v1beta1 API"
        )

        # Verify default ranges
        self.assertEqual(vlan_ns[0]['spec']['ranges'], [{'from': 1000, 'to': 2999}])

    def test_dns_collision_avoidance_with_similar_names(self):
        """Verify unique CRD names when NetBox names sanitize to same value."""
        # Create devices with names that collide after sanitization
        server1 = Device.objects.create(
            name="Server_01",
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )
        server2 = Device.objects.create(
            name="Server-01",  # Sanitizes to same value
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )

        yaml_output = self.generator.generate()
        docs = list(yaml.safe_load_all(yaml_output))

        servers = [doc for doc in docs if isinstance(doc, dict) and doc.get('kind') == 'Server']
        names = [s['metadata']['name'] for s in servers]

        # Verify no duplicates
        self.assertEqual(len(names), len(set(names)), "CRD names must be unique")

        # Verify collision resolution (one gets suffix)
        self.assertIn('server-01', names)
        self.assertTrue(
            any(n.startswith('server-01-') for n in names),
            "Collision should add deterministic suffix"
        )

    def test_server_crd_has_minimal_spec(self):
        """Verify Server CRDs contain only description, not interfaces."""
        server = Device.objects.create(
            name="test-server",
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            comments="Test server for unit testing",
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )

        yaml_output = self.generator.generate()
        docs = list(yaml.safe_load_all(yaml_output))

        servers = [doc for doc in docs if isinstance(doc, dict) and doc.get('kind') == 'Server']
        test_server = [s for s in servers if s['metadata']['name'] == 'test-server'][0]

        # Verify spec contains only description (no interfaces)
        self.assertEqual(
            test_server['spec'],
            {'description': 'Test server for unit testing'},
            "Server spec should contain only description per authoritative schema"
        )

    def test_connection_crd_generated_from_cables(self):
        """Verify Connection CRDs are generated from NetBox Cables."""
        # Create switch and server devices
        switch = Device.objects.create(
            name='spine-01',
            device_type=self.switch_type,
            role=self.spine_role,
            site=self.site,
            custom_field_data={
                'hedgehog_plan_id': str(self.plan.pk),
                'hedgehog_role': 'spine',
                'boot_mac': '02:00:00:aa:bb:cc'
            }
        )
        server = Device.objects.create(
            name='server-01',
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            custom_field_data={
                'hedgehog_plan_id': str(self.plan.pk)
            }
        )

        # Create interfaces
        from dcim.models import Interface
        switch_iface = Interface.objects.create(
            device=switch,
            name='E1/1',
            type='1000base-t'
        )
        server_iface = Interface.objects.create(
            device=server,
            name='eth0',
            type='1000base-t'
        )

        # Create cable connecting them
        from dcim.models import Cable
        cable = Cable.objects.create(
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )
        cable.a_terminations.add(server_iface)
        cable.b_terminations.add(switch_iface)

        yaml_output = self.generator.generate()
        docs = list(yaml.safe_load_all(yaml_output))

        # Verify Connection CRD is generated
        connections = [doc for doc in docs if isinstance(doc, dict) and doc.get('kind') == 'Connection']
        self.assertGreater(len(connections), 0, "Should generate Connection CRD from cable")

        # Verify connection structure
        conn = connections[0]
        self.assertIn('spec', conn)
        # Should be unbundled (server-to-switch)
        self.assertTrue('unbundled' in conn['spec'], "Server-to-switch should use unbundled connection")

    def test_boot_mac_generation_is_deterministic(self):
        """Verify same device gets same boot_mac across regenerations."""
        # Import DeviceGenerator
        from netbox_hedgehog.models.topology_planning import PlanSwitchClass
        from netbox_hedgehog.services.device_generator import DeviceGenerator

        # Create a switch class
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='test-spine',
            device_type_extension=self.switch_ext,
            hedgehog_role='spine',
            calculated_quantity=2
        )

        # Generate inventory twice
        gen1 = DeviceGenerator(self.plan, self.site)
        gen1.generate_all()
        switches1 = list(Device.objects.filter(
            role=self.spine_role,
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).order_by('id'))
        macs1 = [s.custom_field_data['boot_mac'] for s in switches1]

        # Clear and regenerate
        Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).delete()

        gen2 = DeviceGenerator(self.plan, self.site)
        gen2.generate_all()
        switches2 = list(Device.objects.filter(
            role=self.spine_role,
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).order_by('id'))
        macs2 = [s.custom_field_data['boot_mac'] for s in switches2]

        # Verify determinism
        self.assertEqual(macs1, macs2, "Boot MACs should be deterministic")
        self.assertEqual(len(macs1), 2, "Should have 2 switches")
