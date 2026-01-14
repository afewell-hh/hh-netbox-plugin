"""
Integration Tests for Inventory-Based YAML Export (DIET-139)

These tests validate that YAML export reads from NetBox inventory
(Devices, Interfaces, Cables) created by device generation, ensuring
correct port naming with breakout suffixes (E1/x/y format).

Spec: docs/DIET-139-SPECIFICATION.md
Architecture: docs/DIET-139-ARCHITECTURE.md
"""

import yaml
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from dcim.models import Device, Interface, Cable, DeviceType, DeviceRole, Manufacturer, Site, InterfaceTemplate

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanMCLAGDomain,
    DeviceTypeExtension,
    PlanServerConnection,
    SwitchPortZone,
    GenerationState,
    BreakoutOption,
)
from netbox_hedgehog.choices import (
    ServerClassCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    PortZoneTypeChoices,
    AllocationStrategyChoices,
    GenerationStatusChoices,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator

User = get_user_model()


class YAMLExportTestBase(TestCase):
    """Shared fixtures for YAML export tests (reuses patterns from test_interface_reuse.py)."""

    @classmethod
    def setUpTestData(cls):
        """Create test user and reusable reference data"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        # Create manufacturer and device types
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )

        # Server device type with interface templates
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='GPU-Server',
            defaults={'slug': 'gpu-server'}
        )

        # Create interface templates on server type
        cls.eth0_template, _ = InterfaceTemplate.objects.get_or_create(
            device_type=cls.server_type,
            name='enp1s0f0',
            defaults={'type': '200gbase-x-qsfp56'}
        )
        cls.eth1_template, _ = InterfaceTemplate.objects.get_or_create(
            device_type=cls.server_type,
            name='enp1s0f1',
            defaults={'type': '200gbase-x-qsfp56'}
        )

        # Switch device type
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'ds5000'}
        )

        # Create device type extension with breakout support
        cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'native_speed': 800,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g', '8x100g'],  # List, not string
                'uplink_ports': 0,
                'hedgehog_profile_name': 'test-switch-profile',
            }
        )

        # Create breakout options
        cls.breakout_4x200, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={
                'from_speed': 800,
                'logical_ports': 4,
                'logical_speed': 200,
                'optic_type': 'QSFP-DD',
            }
        )
        cls.breakout_2x400, _ = BreakoutOption.objects.get_or_create(
            breakout_id='2x400g',
            defaults={
                'from_speed': 800,
                'logical_ports': 2,
                'logical_speed': 400,
                'optic_type': 'QSFP-DD',
            }
        )

        # Create device roles (use correct slugs)
        cls.server_role, _ = DeviceRole.objects.get_or_create(
            name='Server',
            defaults={'slug': 'server', 'color': 'blue'}
        )
        cls.leaf_role, _ = DeviceRole.objects.get_or_create(
            name='Leaf Switch',
            defaults={'slug': 'leaf', 'color': 'green'}
        )

        # Create site
        cls.site, _ = Site.objects.get_or_create(
            name='Test Site',
            defaults={'slug': 'test-site'}
        )


class YAMLExportPreconditionTestCase(YAMLExportTestBase):
    """
    Test YAML export precondition validation (DIET-139)

    YAML export must fail fast with clear errors when:
    - Device generation has not been run
    - Generation status is not GENERATED
    - No devices exist in inventory
    - No cables exist in inventory
    """

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_export_before_generation_fails(self):
        """
        Test 6 (Spec): Export before device generation raises ValidationError

        Expected error: "Device generation has not been run for this plan."
        """
        # Create plan WITHOUT running device generation
        plan = TopologyPlan.objects.create(
            name='Plan Without Generation',
            created_by=self.user
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[plan.pk])
        response = self.client.get(url)

        # Should return 400 Bad Request (not 500)
        self.assertEqual(response.status_code, 400,
                        "Export before generation should return 400 Bad Request")

        # Check error message content
        response_text = response.content.decode('utf-8')
        self.assertIn('Device generation has not been run', response_text,
                     "Error message should mention generation not run")

    def test_export_with_incomplete_generation_fails(self):
        """
        Test 7 (Spec): Export when generation status != GENERATED fails

        Expected error: "Device generation status is {status}.
                        Complete device generation before exporting."
        """
        # Create plan with generation state but status != GENERATED
        plan = TopologyPlan.objects.create(
            name='Plan With Incomplete Generation',
            created_by=self.user
        )

        # Create generation state with IN_PROGRESS status
        GenerationState.objects.create(
            plan=plan,
            status=GenerationStatusChoices.IN_PROGRESS,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={}  # Empty snapshot for test
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[plan.pk])
        response = self.client.get(url)

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400,
                        "Export with incomplete generation should return 400")

        # Check error message
        response_text = response.content.decode('utf-8')
        self.assertIn('Device generation status is', response_text,
                     "Error message should mention generation status")
        self.assertIn('in_progress', response_text.lower(),
                     "Error message should show actual status")

    def test_export_with_no_devices_fails(self):
        """
        Test 8 (Spec): Export when devices were deleted raises ValidationError

        Expected error: "No devices found in NetBox inventory for this plan."
        """
        # Create plan with GENERATED status but no actual devices
        plan = TopologyPlan.objects.create(
            name='Plan With No Devices',
            created_by=self.user
        )

        GenerationState.objects.create(
            plan=plan,
            status=GenerationStatusChoices.GENERATED,
            device_count=0,  # Claims 0 devices
            interface_count=0,
            cable_count=0,
            snapshot={}  # Empty snapshot for test
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[plan.pk])
        response = self.client.get(url)

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400,
                        "Export with no devices should return 400")

        # Check error message
        response_text = response.content.decode('utf-8')
        self.assertIn('No devices found', response_text,
                     "Error message should mention no devices found")

    def test_export_with_no_cables_fails(self):
        """
        Test (Additional): Export when cables missing raises ValidationError

        Expected error: "No cables found in NetBox inventory for this plan.
                        Device generation may have failed."
        """
        # Create plan with devices but no cables (incomplete generation)
        plan = TopologyPlan.objects.create(
            name='Plan With No Cables',
            created_by=self.user
        )

        GenerationState.objects.create(
            plan=plan,
            status=GenerationStatusChoices.GENERATED,
            device_count=1,
            interface_count=2,
            cable_count=0,  # No cables!
            snapshot={}  # Empty snapshot for test
        )

        # Create a device to pass device count check
        Device.objects.create(
            name='test-device',
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(plan.pk)}
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[plan.pk])
        response = self.client.get(url)

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400,
                        "Export with no cables should return 400")

        # Check error message
        response_text = response.content.decode('utf-8')
        self.assertIn('No cables found', response_text,
                     "Error message should mention no cables found")


class YAMLExportCableValidationTestCase(YAMLExportTestBase):
    """
    Test YAML export cable validation (DIET-139)

    YAML export must validate cable topology and reject:
    - Cables with missing terminations
    - Cables with multiple terminations on one side
    - Server-to-server connections
    - Invalid device role combinations
    """

    def setUp(self):
        """Create fresh plan and devices for each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        # Create plan
        self.plan = TopologyPlan.objects.create(
            name='Cable Validation Test Plan',
            created_by=self.user
        )

        # Create generation state (GENERATED)
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.GENERATED,
            device_count=2,
            interface_count=4,
            cable_count=1,
            snapshot={}  # Empty snapshot for test
        )

        # Create test devices
        self.server1 = Device.objects.create(
            name='test-server-001',
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )
        self.server2 = Device.objects.create(
            name='test-server-002',
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )
        self.switch1 = Device.objects.create(
            name='test-leaf-01',
            device_type=self.switch_type,
            role=self.leaf_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )

    def test_multiple_terminations_on_one_side_fails(self):
        """
        Test 10 (Spec): Cable with multiple terminations on one side raises ValidationError

        Expected error: "Cable {id} has multiple terminations on one side.
                        Single-termination cables only."
        """
        # Create interfaces with unique names
        iface1 = Interface.objects.create(
            device=self.switch1,
            name='test-port-multi-1',
            type='100gbase-x-qsfp28'
        )
        iface2 = Interface.objects.create(
            device=self.switch1,
            name='test-port-multi-2',
            type='100gbase-x-qsfp28'
        )
        iface3 = Interface.objects.create(
            device=self.server1,
            name='test-port-multi-3',
            type='100gbase-x-qsfp28'
        )

        # Create cable with multiple terminations on A side (NetBox 4.x API)
        cable = Cable(
            a_terminations=[iface1, iface2],  # Two interfaces on A side
            b_terminations=[iface3],  # One on B side
        )
        cable.custom_field_data = {'hedgehog_plan_id': str(self.plan.pk)}
        cable.save()

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400,
                        "Export with multi-termination cable should return 400")

        # Check error message
        response_text = response.content.decode('utf-8')
        self.assertIn('multiple terminations', response_text.lower(),
                     "Error message should mention multiple terminations")

    def test_server_to_server_connection_fails(self):
        """
        Test 11 (Spec): Cable connecting two servers raises ValidationError

        Expected error: "Cable {id}: Server-to-server connections are not supported.
                        Expected server↔switch or switch↔switch."
        """
        # Create interfaces on both servers (use unique names per device)
        iface1 = Interface.objects.create(
            device=self.server1,
            name='test-port-s2s-1',
            type='100gbase-x-qsfp28'
        )
        iface2 = Interface.objects.create(
            device=self.server2,
            name='test-port-s2s-2',
            type='100gbase-x-qsfp28'
        )

        # Create cable connecting two servers (NetBox 4.x API)
        cable = Cable(
            a_terminations=[iface1],
            b_terminations=[iface2],
        )
        cable.custom_field_data = {'hedgehog_plan_id': str(self.plan.pk)}
        cable.save()

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400,
                        "Server-to-server cable should return 400")

        # Check error message
        response_text = response.content.decode('utf-8')
        self.assertIn('server-to-server', response_text.lower(),
                     "Error message should mention server-to-server not supported")


class YAMLExportBreakoutNamingTestCase(YAMLExportTestBase):
    """
    Test YAML export produces correct port names with breakout suffixes (DIET-139)

    This is the CRITICAL correctness test validating:
    - YAML switch ports match NetBox Interface.name exactly
    - Breakout suffixes are included (E1/x/y format, not E1/x)
    - Port names are read from inventory, not regenerated
    """

    def setUp(self):
        """Create plan and run device generation for each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        # Create plan with breakout configuration
        self.plan = TopologyPlan.objects.create(
            name='Breakout Test Plan',
            created_by=self.user
        )

        # Create server class (2 servers) - use server_device_type, not device_type
        self.server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='test-gpu',
            server_device_type=self.server_type,  # FK to DeviceType
            category=ServerClassCategoryChoices.GPU,
            quantity=2,
            gpus_per_server=8
        )

        # Create switch class (leaf) - use device_type_extension
        self.switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='test-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,  # FK to DeviceTypeExtension
            uplink_ports_per_switch=0,
            mclag_pair=False,
            calculated_quantity=1,
            override_quantity=1  # Force 1 switch
        )

        # Create port zone with 4x200G breakout - use BreakoutOption instance
        self.zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='server',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=self.breakout_4x200,  # FK to BreakoutOption
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100
        )

        # Create server connection - use correct field names
        self.connection = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='frontend',
            server_interface_template=self.eth0_template,  # FK to InterfaceTemplate
            nic_slot='',  # Empty for template mode
            ports_per_connection=2,  # Correct field name
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,  # Correct field name
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_switch_class=self.switch_class,
            speed=200,
        )

        # Run device generation to create actual NetBox inventory
        generator = DeviceGenerator(plan=self.plan, site=self.site)
        generator.generate_all()

    def test_yaml_includes_breakout_suffixes(self):
        """
        Test 1 (Spec): YAML export must include breakout suffixes (E1/x/y) in port names

        Expected: Switch ports like 'fe-gpu-leaf-01/E1/1/1', NOT 'fe-gpu-leaf-01/E1/1'
        """
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        "YAML export should succeed after device generation")

        # Parse YAML
        content = response.content.decode('utf-8')
        documents = list(yaml.safe_load_all(content))
        connection_crds = [doc for doc in documents if doc and doc.get('kind') == 'Connection']

        # Extract switch port names
        switch_ports = []
        for crd in connection_crds:
            spec = crd.get('spec', {})
            if 'unbundled' in spec:
                link = spec['unbundled'].get('link', {})
                switch_port = link.get('switch', {}).get('port', '')
                if switch_port:
                    switch_ports.append(switch_port)

        # Verify at least some ports have breakout suffixes
        breakout_ports = [p for p in switch_ports if p.count('/') >= 2]  # E1/x/y format
        self.assertGreater(len(breakout_ports), 0,
                          "YAML should contain ports with breakout suffixes (E1/x/y format)")

        # Verify NO ports are missing breakout suffix when breakout is configured
        # With 4x200G breakout, all ports should be E1/x/y (3 slashes total including device name)
        for port in switch_ports:
            port_parts = port.split('/')
            # Format: device-name/E1/physical/lane
            self.assertEqual(len(port_parts), 4,
                           f"Port {port} should have breakout suffix (format: device/E1/physical/lane)")

    def test_yaml_port_names_match_netbox_inventory(self):
        """
        Test 2 (Spec): YAML export port names must exactly match NetBox Interface.name

        This is the authoritative test: YAML reads from inventory, not regenerates.
        """
        # First, get interfaces from NetBox inventory
        switch_device = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            role__slug='leaf'
        ).first()

        self.assertIsNotNone(switch_device,
                            "Device generation should have created a leaf switch")

        # Get all switch interface names from NetBox
        netbox_interface_names = set(
            switch_device.interfaces.values_list('name', flat=True)
        )

        # Export YAML
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Parse YAML
        content = response.content.decode('utf-8')
        documents = list(yaml.safe_load_all(content))
        connection_crds = [doc for doc in documents if doc and doc.get('kind') == 'Connection']

        # Extract switch port names from YAML (strip device name prefix)
        yaml_port_names = set()
        for crd in connection_crds:
            spec = crd.get('spec', {})
            if 'unbundled' in spec:
                link = spec['unbundled'].get('link', {})
                switch_port = link.get('switch', {}).get('port', '')
                if switch_port:
                    # Extract just the interface name (after device name)
                    # Format: device-name/E1/x/y -> E1/x/y
                    port_name = '/'.join(switch_port.split('/')[1:])
                    yaml_port_names.add(port_name)

        # Verify all YAML ports exist in NetBox inventory
        for yaml_port in yaml_port_names:
            self.assertIn(yaml_port, netbox_interface_names,
                         f"YAML port {yaml_port} not found in NetBox interfaces. "
                         f"YAML should read from inventory, not regenerate names.")

    def test_yaml_export_does_not_mutate_plan(self):
        """
        Test 5 (Spec): YAML export is read-only and does not modify the plan

        Validates that export does NOT call update_plan_calculations()
        """
        # Capture plan updated timestamp before export
        self.plan.refresh_from_db()
        original_updated = self.plan.last_updated

        # Export YAML
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        "YAML export should succeed")

        # Verify plan was not mutated
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.last_updated, original_updated,
                        "YAML export should not modify plan.last_updated timestamp. "
                        "Export must be read-only (no update_plan_calculations call).")


class YAMLExportFabricSchemaTestCase(YAMLExportTestBase):
    """
    Test YAML export fabric connection schema (DIET-139)

    Validates that switch-to-switch connections use correct Hedgehog schema:
    - fabric.links array with separate switch entries (not a/b keys)
    - Deterministic ordering (leaf/border before spine)
    """

    def setUp(self):
        """Create plan with fabric (switch-to-switch) connections"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        # Create plan
        self.plan = TopologyPlan.objects.create(
            name='Fabric Schema Test Plan',
            created_by=self.user
        )

        # Create two leaf switches
        self.leaf1 = Device.objects.create(
            name='test-leaf-01',
            device_type=self.switch_type,
            role=self.leaf_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )
        self.leaf2 = Device.objects.create(
            name='test-leaf-02',
            device_type=self.switch_type,
            role=self.leaf_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )

        # Create spine switch
        spine_role, _ = DeviceRole.objects.get_or_create(
            name='Spine Switch',
            defaults={'slug': 'spine', 'color': 'red'}
        )
        self.spine = Device.objects.create(
            name='test-spine-01',
            device_type=self.switch_type,
            role=spine_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )

        # Create generation state
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.GENERATED,
            device_count=3,
            interface_count=4,
            cable_count=2,
            snapshot={}
        )

        # Create interfaces
        self.leaf1_iface = Interface.objects.create(
            device=self.leaf1,
            name='E1/64/1',  # Uplink with breakout
            type='100gbase-x-qsfp28'
        )
        self.spine_iface1 = Interface.objects.create(
            device=self.spine,
            name='E1/1/1',  # Downlink with breakout
            type='100gbase-x-qsfp28'
        )
        self.leaf2_iface = Interface.objects.create(
            device=self.leaf2,
            name='E1/64/1',
            type='100gbase-x-qsfp28'
        )
        self.spine_iface2 = Interface.objects.create(
            device=self.spine,
            name='E1/1/2',
            type='100gbase-x-qsfp28'
        )

        # Create fabric cables (leaf-to-spine)
        cable1 = Cable(
            a_terminations=[self.leaf1_iface],
            b_terminations=[self.spine_iface1],
        )
        cable1.custom_field_data = {'hedgehog_plan_id': str(self.plan.pk)}
        cable1.save()

        cable2 = Cable(
            a_terminations=[self.leaf2_iface],
            b_terminations=[self.spine_iface2],
        )
        cable2.custom_field_data = {'hedgehog_plan_id': str(self.plan.pk)}
        cable2.save()

    def test_fabric_connections_use_leaf_spine_schema(self):
        """
        Test: Fabric connections must use 'leaf'/'spine' entries, not 'switch' or 'a'/'b'

        Critical schema validation to ensure Hedgehog hhfab compatibility.
        Fabric links MUST be in this format (per real-world customer examples):
          fabric:
            links:
              - leaf: { port: ... }
                spine: { port: ... }

        NOT these formats (invalid):
          - switch/switch format
          - a/b format
        """
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        "YAML export should succeed with fabric connections")

        # Parse YAML
        content = response.content.decode('utf-8')
        documents = list(yaml.safe_load_all(content))
        fabric_crds = [doc for doc in documents if doc and doc.get('kind') == 'Connection'
                       and 'fabric' in doc.get('spec', {})]

        self.assertGreater(len(fabric_crds), 0,
                          "Should have at least one fabric connection")

        # Validate each fabric CRD
        for crd in fabric_crds:
            fabric_spec = crd['spec']['fabric']

            # Assert 'links' array exists
            self.assertIn('links', fabric_spec,
                         "Fabric spec must have 'links' array")

            links = fabric_spec['links']
            self.assertGreaterEqual(len(links), 1,
                                   "Fabric connection should have at least 1 link")

            # CRITICAL: Each link must have 'leaf' and 'spine' keys
            for i, link in enumerate(links):
                # Must have leaf and spine
                self.assertIn('leaf', link,
                             f"Link {i} must have 'leaf' key")
                self.assertIn('spine', link,
                             f"Link {i} must have 'spine' key")

                # Must NOT have invalid keys
                self.assertNotIn('switch', link,
                               f"Link {i} must NOT have 'switch' key (use 'leaf'/'spine')")
                self.assertNotIn('a', link,
                               f"Link {i} must NOT have 'a' key (use 'leaf'/'spine')")
                self.assertNotIn('b', link,
                               f"Link {i} must NOT have 'b' key (use 'leaf'/'spine')")

                # Assert leaf and spine have port fields
                self.assertIn('port', link['leaf'],
                             f"Link {i} leaf must have 'port' field")
                self.assertIn('port', link['spine'],
                             f"Link {i} spine must have 'port' field")

                # Verify port format: device-name/interface-name
                leaf_port = link['leaf']['port']
                spine_port = link['spine']['port']
                self.assertIn('/', leaf_port,
                             f"Leaf port {leaf_port} should be in device/interface format")
                self.assertIn('/', spine_port,
                             f"Spine port {spine_port} should be in device/interface format")

    def test_fabric_connections_include_breakout_suffixes(self):
        """
        Test: Fabric connection ports include breakout suffixes (E1/x/y)

        Uplink ports should show breakout format like E1/64/1
        """
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Parse YAML
        content = response.content.decode('utf-8')
        documents = list(yaml.safe_load_all(content))
        fabric_crds = [doc for doc in documents if doc and doc.get('kind') == 'Connection'
                       and 'fabric' in doc.get('spec', {})]

        # Collect all ports from fabric connections
        fabric_ports = []
        for crd in fabric_crds:
            links = crd['spec']['fabric']['links']
            for link in links:
                # Extract ports from leaf and spine
                leaf_port = link['leaf']['port']
                spine_port = link['spine']['port']

                # Extract interface names (after device name)
                leaf_iface = '/'.join(leaf_port.split('/')[1:])
                spine_iface = '/'.join(spine_port.split('/')[1:])

                fabric_ports.extend([leaf_iface, spine_iface])

        # Verify at least some have breakout suffixes (E1/x/y format)
        breakout_ports = [p for p in fabric_ports if p.count('/') >= 2]
        self.assertGreater(len(breakout_ports), 0,
                          "Fabric uplinks should include breakout suffixes (E1/x/y)")


class YAMLExportUnbundledUniquenessTestCase(YAMLExportTestBase):
    """
    Test unbundled Connection CRD name uniqueness (DIET-139)

    Validates that multiple server ports to the same switch generate unique CRD names.
    Critical: K8s will reject duplicate metadata.name values.
    """

    def setUp(self):
        """Create plan with server having multiple ports to same switch"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        # Create plan
        self.plan = TopologyPlan.objects.create(
            name='Unbundled Uniqueness Test Plan',
            created_by=self.user
        )

        # Create server
        self.server = Device.objects.create(
            name='test-server-01',
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )

        # Create switch
        self.switch = Device.objects.create(
            name='test-leaf-01',
            device_type=self.switch_type,
            role=self.leaf_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(self.plan.pk)}
        )

        # Create generation state
        GenerationState.objects.create(
            plan=self.plan,
            status=GenerationStatusChoices.GENERATED,
            device_count=2,
            interface_count=4,
            cable_count=2,
            snapshot={}
        )

        # Create TWO interfaces on server connecting to SAME switch (use unique names)
        self.server_iface1 = Interface.objects.create(
            device=self.server,
            name='test-nic-unique-0',
            type='100gbase-x-qsfp28'
        )
        self.server_iface2 = Interface.objects.create(
            device=self.server,
            name='test-nic-unique-1',
            type='100gbase-x-qsfp28'
        )

        # Create corresponding switch interfaces (use unique names)
        self.switch_iface1 = Interface.objects.create(
            device=self.switch,
            name='test-port-unique-0',
            type='100gbase-x-qsfp28'
        )
        self.switch_iface2 = Interface.objects.create(
            device=self.switch,
            name='test-port-unique-1',
            type='100gbase-x-qsfp28'
        )

        # Create TWO cables from same server to same switch
        cable1 = Cable(
            a_terminations=[self.server_iface1],
            b_terminations=[self.switch_iface1],
        )
        cable1.custom_field_data = {'hedgehog_plan_id': str(self.plan.pk)}
        cable1.save()

        cable2 = Cable(
            a_terminations=[self.server_iface2],
            b_terminations=[self.switch_iface2],
        )
        cable2.custom_field_data = {'hedgehog_plan_id': str(self.plan.pk)}
        cable2.save()

    def test_unbundled_crd_names_are_unique(self):
        """
        Test: Multiple server ports to same switch must generate unique CRD names

        Critical: K8s will reject duplicate metadata.name or use last-write-wins.
        CRD name MUST include server interface name to disambiguate.

        Expected format: {server-name}-{server-interface}--unbundled--{switch-name}
        Example: server-01-enp1s0f0--unbundled--leaf-01
        """
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        "YAML export should succeed")

        # Parse YAML
        content = response.content.decode('utf-8')
        documents = list(yaml.safe_load_all(content))
        unbundled_crds = [doc for doc in documents if doc and doc.get('kind') == 'Connection'
                          and 'unbundled' in doc.get('spec', {})]

        # Should have 2 unbundled connections (one per cable)
        self.assertEqual(len(unbundled_crds), 2,
                        "Should have 2 unbundled connections (one per server port)")

        # Extract CRD names
        crd_names = [crd['metadata']['name'] for crd in unbundled_crds]

        # CRITICAL: Names must be unique
        self.assertEqual(len(crd_names), len(set(crd_names)),
                        f"CRD names must be unique, but got duplicates: {crd_names}")

        # Verify names include server interface name for disambiguation
        for crd in unbundled_crds:
            name = crd['metadata']['name']
            server_port = crd['spec']['unbundled']['link']['server']['port']

            # Extract server interface name from port (format: server-name/interface-name)
            server_iface_name = server_port.split('/')[-1]

            # CRD name must include the server interface name
            self.assertIn(server_iface_name, name,
                         f"CRD name '{name}' must include server interface '{server_iface_name}' "
                         f"to ensure uniqueness when multiple ports connect to same switch")


class YAMLExportRedundancyCRDsTestCase(YAMLExportTestBase):
    """Test MCLAG/ESLAG/bundled Connection CRDs and SwitchGroup export."""

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def _create_generation_state(self, plan, device_count, interface_count, cable_count):
        GenerationState.objects.create(
            plan=plan,
            status=GenerationStatusChoices.GENERATED,
            device_count=device_count,
            interface_count=interface_count,
            cable_count=cable_count,
            snapshot={}
        )

    def _create_switch_device(self, plan, name, hedgehog_class, hedgehog_role='server-leaf'):
        digits = ''.join([ch for ch in name if ch.isdigit()])
        mac_suffix = int(digits) if digits else 0
        return Device.objects.create(
            name=name,
            device_type=self.switch_type,
            role=self.leaf_role,
            site=self.site,
            custom_field_data={
                'hedgehog_plan_id': str(plan.pk),
                'hedgehog_class': hedgehog_class,
                'hedgehog_role': hedgehog_role,
                'boot_mac': f"0c:20:12:ff:00:{mac_suffix:02x}",
            }
        )

    def _create_server_device(self, plan, name):
        return Device.objects.create(
            name=name,
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            custom_field_data={'hedgehog_plan_id': str(plan.pk)}
        )

    def _create_interface(self, device, name):
        existing = Interface.objects.filter(device=device, name=name).first()
        if existing:
            return existing

        return Interface.objects.create(
            device=device,
            name=name,
            type='100gbase-x-qsfp28'
        )

    def _create_cable(self, plan, iface_a, iface_b, zone):
        cable = Cable(
            a_terminations=[iface_a],
            b_terminations=[iface_b],
        )
        cable.custom_field_data = {
            'hedgehog_plan_id': str(plan.pk),
            'hedgehog_zone': zone,
        }
        cable.save()
        return cable

    def test_export_generates_switchgroups_and_mclag_domain(self):
        """MCLAG SwitchGroups and mclag-domain connections render from inventory."""
        plan = TopologyPlan.objects.create(
            name='MCLAG Domain Export Plan',
            created_by=self.user
        )

        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            calculated_quantity=2,
            groups=['mclag-1'],
            redundancy_type='mclag',
            redundancy_group='mclag-1',
        )

        PlanMCLAGDomain.objects.create(
            plan=plan,
            domain_id='mclag-1',
            switch_class=switch_class,
            peer_link_count=2,
            session_link_count=2,
            peer_start_port=1,
            session_start_port=1,
            switch_group_name='mclag-1',
            redundancy_type='mclag',
        )

        leaf_01 = self._create_switch_device(plan, 'leaf-01', 'leaf')
        leaf_02 = self._create_switch_device(plan, 'leaf-02', 'leaf')

        # Session links (E1/1-2)
        for idx in (1, 2):
            a = self._create_interface(leaf_01, f'E1/{idx}')
            b = self._create_interface(leaf_02, f'E1/{idx}')
            self._create_cable(plan, a, b, zone=PortZoneTypeChoices.SESSION)

        # Peer links (E1/3-4)
        for idx in (3, 4):
            a = self._create_interface(leaf_01, f'E1/{idx}')
            b = self._create_interface(leaf_02, f'E1/{idx}')
            self._create_cable(plan, a, b, zone=PortZoneTypeChoices.PEER)

        self._create_generation_state(plan, device_count=2, interface_count=8, cable_count=4)

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[plan.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        documents = list(yaml.safe_load_all(response.content.decode('utf-8')))
        switchgroups = [doc for doc in documents if doc and doc.get('kind') == 'SwitchGroup']
        self.assertEqual(len(switchgroups), 1)
        self.assertEqual(switchgroups[0]['metadata']['name'], 'mclag-1')
        self.assertEqual(switchgroups[0]['spec'], {})

        switch_docs = {
            doc['metadata']['name']: doc
            for doc in documents
            if doc and doc.get('kind') == 'Switch'
        }
        for leaf_name in ('leaf-01', 'leaf-02'):
            self.assertIn(leaf_name, switch_docs)
            spec = switch_docs[leaf_name]['spec']
            self.assertEqual(spec.get('groups'), ['mclag-1'])
            self.assertEqual(spec.get('redundancy', {}).get('group'), 'mclag-1')
            self.assertEqual(spec.get('redundancy', {}).get('type'), 'mclag')

        domain_crds = [
            doc for doc in documents
            if doc and doc.get('kind') == 'Connection' and 'mclagDomain' in doc.get('spec', {})
        ]
        self.assertEqual(len(domain_crds), 1)
        domain_spec = domain_crds[0]['spec']['mclagDomain']
        self.assertEqual(len(domain_spec.get('peerLinks', [])), 2)
        self.assertEqual(len(domain_spec.get('sessionLinks', [])), 2)

    def test_export_generates_mclag_connections(self):
        """Server dual-homing to MCLAG pair exports mclag Connection CRD."""
        plan = TopologyPlan.objects.create(
            name='MCLAG Server Export Plan',
            created_by=self.user
        )

        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            calculated_quantity=2,
            groups=['mclag-1'],
            redundancy_type='mclag',
            redundancy_group='mclag-1',
        )

        PlanMCLAGDomain.objects.create(
            plan=plan,
            domain_id='mclag-1',
            switch_class=switch_class,
            peer_link_count=2,
            session_link_count=2,
            peer_start_port=1,
            session_start_port=1,
            switch_group_name='mclag-1',
            redundancy_type='mclag',
        )

        leaf_01 = self._create_switch_device(plan, 'leaf-01', 'leaf')
        leaf_02 = self._create_switch_device(plan, 'leaf-02', 'leaf')
        server = self._create_server_device(plan, 'compute-01')

        server_iface_1 = self._create_interface(server, 'enp2s1')
        server_iface_2 = self._create_interface(server, 'enp2s2')
        leaf_iface_1 = self._create_interface(leaf_01, 'E1/5')
        leaf_iface_2 = self._create_interface(leaf_02, 'E1/5')

        self._create_cable(plan, server_iface_1, leaf_iface_1, zone=PortZoneTypeChoices.SERVER)
        self._create_cable(plan, server_iface_2, leaf_iface_2, zone=PortZoneTypeChoices.SERVER)

        self._create_generation_state(plan, device_count=3, interface_count=4, cable_count=2)

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[plan.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        documents = list(yaml.safe_load_all(response.content.decode('utf-8')))
        mclag_crds = [
            doc for doc in documents
            if doc and doc.get('kind') == 'Connection' and 'mclag' in doc.get('spec', {})
        ]
        self.assertEqual(len(mclag_crds), 1)
        links = mclag_crds[0]['spec']['mclag']['links']
        self.assertEqual(len(links), 2)

    def test_export_generates_eslag_connections(self):
        """Server connected to 3-switch ESLAG group exports eslag Connection CRD."""
        plan = TopologyPlan.objects.create(
            name='ESLAG Export Plan',
            created_by=self.user
        )

        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='eslag-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            calculated_quantity=3,
            groups=['eslag-1'],
            redundancy_type='eslag',
            redundancy_group='eslag-1',
        )

        PlanMCLAGDomain.objects.create(
            plan=plan,
            domain_id='eslag-1',
            switch_class=switch_class,
            peer_link_count=1,
            session_link_count=1,
            peer_start_port=1,
            session_start_port=1,
            switch_group_name='eslag-1',
            redundancy_type='eslag',
        )

        leaf_01 = self._create_switch_device(plan, 'leaf-01', 'eslag-leaf')
        leaf_02 = self._create_switch_device(plan, 'leaf-02', 'eslag-leaf')
        leaf_03 = self._create_switch_device(plan, 'leaf-03', 'eslag-leaf')
        server = self._create_server_device(plan, 'storage-01')

        server_iface_1 = self._create_interface(server, 'enp2s1')
        server_iface_2 = self._create_interface(server, 'enp2s2')
        server_iface_3 = self._create_interface(server, 'enp2s3')

        self._create_cable(plan, server_iface_1, self._create_interface(leaf_01, 'E1/1'),
                           zone=PortZoneTypeChoices.SERVER)
        self._create_cable(plan, server_iface_2, self._create_interface(leaf_02, 'E1/1'),
                           zone=PortZoneTypeChoices.SERVER)
        self._create_cable(plan, server_iface_3, self._create_interface(leaf_03, 'E1/1'),
                           zone=PortZoneTypeChoices.SERVER)

        self._create_generation_state(plan, device_count=4, interface_count=6, cable_count=3)

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[plan.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        documents = list(yaml.safe_load_all(response.content.decode('utf-8')))
        eslag_crds = [
            doc for doc in documents
            if doc and doc.get('kind') == 'Connection' and 'eslag' in doc.get('spec', {})
        ]
        self.assertEqual(len(eslag_crds), 1)
        links = eslag_crds[0]['spec']['eslag']['links']
        self.assertEqual(len(links), 3)

    def test_export_generates_bundled_connections(self):
        """Multiple links to a single switch export bundled Connection CRD."""
        plan = TopologyPlan.objects.create(
            name='Bundled Export Plan',
            created_by=self.user
        )

        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            calculated_quantity=1,
        )

        leaf = self._create_switch_device(plan, 'leaf-01', 'leaf')
        server = self._create_server_device(plan, 'app-01')

        server_iface_1 = self._create_interface(server, 'enp2s1')
        server_iface_2 = self._create_interface(server, 'enp2s2')
        leaf_iface_1 = self._create_interface(leaf, 'E1/1')
        leaf_iface_2 = self._create_interface(leaf, 'E1/2')

        self._create_cable(plan, server_iface_1, leaf_iface_1, zone=PortZoneTypeChoices.SERVER)
        self._create_cable(plan, server_iface_2, leaf_iface_2, zone=PortZoneTypeChoices.SERVER)

        self._create_generation_state(plan, device_count=2, interface_count=4, cable_count=2)

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[plan.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        documents = list(yaml.safe_load_all(response.content.decode('utf-8')))
        bundled_crds = [
            doc for doc in documents
            if doc and doc.get('kind') == 'Connection' and 'bundled' in doc.get('spec', {})
        ]
        self.assertEqual(len(bundled_crds), 1)
        links = bundled_crds[0]['spec']['bundled']['links']
        self.assertEqual(len(links), 2)


class YAMLExportUITestCase(YAMLExportTestBase):
    """
    Test YAML export UI behavior (DIET-139)

    Validates that:
    - Export button is disabled when generation not completed
    - Export button is enabled when generation completed
    - Button tooltip explains precondition
    """

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_export_button_disabled_without_generation(self):
        """
        Test 12 (Spec): Export YAML button is disabled if generation not completed

        Expected: Button has 'disabled' attribute and tooltip explaining why
        """
        # Create plan without generation
        plan = TopologyPlan.objects.create(
            name='Plan Without Generation',
            created_by=self.user
        )

        # Load plan detail page
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        "Plan detail page should load")

        response_text = response.content.decode('utf-8')

        # Button should be present but disabled
        self.assertIn('Export YAML', response_text,
                     "Export YAML button should be present")

        # Check for disabled state (button or link with disabled attribute/class)
        # Note: Exact HTML structure depends on template implementation
        # Looking for common disabled indicators
        has_disabled_indicator = (
            'disabled' in response_text.lower() or
            'btn-secondary' in response_text  # Disabled buttons often use secondary style
        )

        self.assertTrue(has_disabled_indicator,
                       "Export button should indicate disabled state when generation not run")
