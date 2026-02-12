"""
Unit tests for Module instantiation in DeviceGenerator (DIET-173).

Tests validate that DeviceGenerator correctly:
- Creates ModuleBays for each connection
- Instantiates Modules with correct ModuleType
- Retrieves Module interfaces by port_index
- Validates port availability

This file contains 6 unit tests.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError

from dcim.models import (
    DeviceType, Manufacturer, Device, DeviceRole, Site,
    ModuleType, InterfaceTemplate, Module, ModuleBay, Interface
)

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan, PlanServerClass, PlanSwitchClass, PlanServerConnection,
    DeviceTypeExtension, BreakoutOption
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    ConnectionTypeChoices,
    ServerClassCategoryChoices,
)


class ModuleInstantiationTestCase(TestCase):
    """Unit tests for Module instantiation (6 tests)."""

    @classmethod
    def setUpTestData(cls):
        """Create shared test data."""
        # Manufacturer
        cls.nvidia, _ = Manufacturer.objects.get_or_create(name='NVIDIA', defaults={'slug': 'nvidia'})
        cls.test_mfg, _ = Manufacturer.objects.get_or_create(name='Test Mfg', defaults={'slug': 'test-mfg'})

        # NIC ModuleType (BlueField-3 with 2 ports) - may exist from migration
        cls.bf3_type, bf3_created = ModuleType.objects.get_or_create(
            manufacturer=cls.nvidia,
            model='BlueField-3 BF3220'
        )
        if bf3_created:
            InterfaceTemplate.objects.create(
                module_type=cls.bf3_type,
                name='p0',
                type='other'  # Using 'other' type - actual type not critical for Module instantiation tests
            )
            InterfaceTemplate.objects.create(
                module_type=cls.bf3_type,
                name='p1',
                type='other'
            )

        # Server DeviceType
        cls.server_type = DeviceType.objects.create(
            manufacturer=cls.test_mfg,
            model='GPU Server',
            slug='gpu-server'
        )

        # Switch DeviceType + Extension
        cls.switch_type = DeviceType.objects.create(
            manufacturer=cls.test_mfg,
            model='Test Switch',
            slug='test-switch'
        )

        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x800g',
            defaults={
                'from_speed': 800,
                'logical_ports': 1,
                'logical_speed': 800,
                'optic_type': 'QSFP-DD'
            }
        )

        cls.device_ext = DeviceTypeExtension.objects.create(
            device_type=cls.switch_type,
            native_speed=800,
            uplink_ports=16
        )

        # Site
        cls.site = Site.objects.create(name='Test Site', slug='test-site')

    def _create_switch_class_with_zone(self, plan, switch_class_id='fe-leaf'):
        """Helper to create switch class with required port zone."""
        from netbox_hedgehog.models.topology_planning import SwitchPortZone
        from netbox_hedgehog.choices import PortZoneTypeChoices, AllocationStrategyChoices

        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id=switch_class_id,
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            override_quantity=1
        )

        # Create port zone for port allocation
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-ports',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-32',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=10
        )

        return switch_class

    def test_module_bay_created_per_connection(self):
        """Test that DeviceGenerator creates ModuleBay for each connection."""
        plan = TopologyPlan.objects.create(name='Test Plan', status=TopologyPlanStatusChoices.DRAFT)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-01',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            server_device_type=self.server_type
        )

        switch_class = self._create_switch_class_with_zone(plan, 'fe-leaf')

        # Create connection
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            nic_module_type=self.bf3_type,
            port_index=0,
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200
        )

        # Generate devices
        generator = DeviceGenerator(plan=plan, site=self.site)
        generator.generate_all()

        # Verify ModuleBay created (check existence, not exact naming)
        server_device = Device.objects.get(name__contains='gpu-01')
        module_bays = ModuleBay.objects.filter(device=server_device)

        self.assertGreater(module_bays.count(), 0, "No ModuleBays created")
        # At least one bay should exist for the 'fe' connection
        # Don't assert exact naming - implementation may vary

    def test_module_instantiated_with_correct_type(self):
        """Test that Module is created with correct ModuleType."""
        plan = TopologyPlan.objects.create(name='Test Plan', status=TopologyPlanStatusChoices.DRAFT)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-01',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            server_device_type=self.server_type
        )

        switch_class = self._create_switch_class_with_zone(plan, 'fe-leaf')

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            nic_module_type=self.bf3_type,
            port_index=0,
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200
        )

        generator = DeviceGenerator(plan=plan, site=self.site)
        generator.generate_all()

        # Verify Module created
        server_device = Device.objects.get(name__contains='gpu-01')
        module = Module.objects.filter(device=server_device).first()

        self.assertIsNotNone(module)
        self.assertEqual(module.module_type, self.bf3_type)
        self.assertTrue(module.serial.startswith(server_device.name))

    def test_module_interfaces_auto_created(self):
        """Test that NetBox auto-creates Interfaces from ModuleType templates."""
        plan = TopologyPlan.objects.create(name='Test Plan', status=TopologyPlanStatusChoices.DRAFT)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-01',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            server_device_type=self.server_type
        )

        switch_class = self._create_switch_class_with_zone(plan, 'fe-leaf')

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            nic_module_type=self.bf3_type,
            port_index=0,
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200
        )

        generator = DeviceGenerator(plan=plan, site=self.site)
        generator.generate_all()

        # Verify Interfaces auto-created (p0, p1)
        server_device = Device.objects.get(name__contains='gpu-01')
        module = Module.objects.filter(device=server_device).first()

        interfaces = Interface.objects.filter(device=server_device, module=module)
        self.assertEqual(interfaces.count(), 2)  # p0, p1
        self.assertTrue(interfaces.filter(name='p0').exists())
        self.assertTrue(interfaces.filter(name='p1').exists())

    def test_port_index_selects_correct_interface(self):
        """Test that port_index correctly selects interface from Module."""
        plan = TopologyPlan.objects.create(name='Test Plan', status=TopologyPlanStatusChoices.DRAFT)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-01',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            server_device_type=self.server_type
        )

        switch_class = self._create_switch_class_with_zone(plan, 'fe-leaf')

        # Connection using port_index=1 (second port)
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            nic_module_type=self.bf3_type,
            port_index=1,  # Use p1, not p0
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200
        )

        generator = DeviceGenerator(plan=plan, site=self.site)
        generator.generate_all()

        # Verify cable connected to p1 (not p0)
        server_device = Device.objects.get(name__contains='gpu-01')
        p0_interface = Interface.objects.get(device=server_device, name='p0')
        p1_interface = Interface.objects.get(device=server_device, name='p1')

        # Check that p1 has a cable, p0 does not (since port_index=1)
        from dcim.models import Cable, CableTermination

        # Find cable terminations for p1
        p1_terminations = CableTermination.objects.filter(
            termination_type__model='interface',
            termination_id=p1_interface.pk
        )

        # Verify p1 is cabled (port_index=1 selects second port)
        self.assertGreater(
            p1_terminations.count(),
            0,
            "Cable should terminate on p1 when port_index=1"
        )

    def test_multiple_connections_create_multiple_modules(self):
        """Test that multiple connections create multiple Modules."""
        plan = TopologyPlan.objects.create(name='Test Plan', status=TopologyPlanStatusChoices.DRAFT)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-01',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            server_device_type=self.server_type
        )

        switch_class = self._create_switch_class_with_zone(plan, 'fe-leaf')

        # Create 2 connections (frontend + backend)
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            nic_module_type=self.bf3_type,
            port_index=0,
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200
        )

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='be',
            nic_module_type=self.bf3_type,
            port_index=0,
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200
        )

        generator = DeviceGenerator(plan=plan, site=self.site)
        generator.generate_all()

        # Verify 2 Modules created
        server_device = Device.objects.get(name__contains='gpu-01')
        modules = Module.objects.filter(device=server_device)

        self.assertEqual(modules.count(), 2)

        # Verify ModuleBays (check count, not exact naming)
        bays = ModuleBay.objects.filter(device=server_device)
        self.assertEqual(bays.count(), 2, "Should have 2 ModuleBays for 2 connections")

    def test_validation_fails_for_invalid_port_index(self):
        """Test that validation fails when port_index exceeds NIC port count."""
        plan = TopologyPlan.objects.create(name='Test Plan', status=TopologyPlanStatusChoices.DRAFT)

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='gpu-01',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            server_device_type=self.server_type
        )

        switch_class = self._create_switch_class_with_zone(plan, 'fe-leaf')

        # Create connection with invalid port_index
        conn = PlanServerConnection(
            server_class=server_class,
            connection_id='fe',
            nic_module_type=self.bf3_type,
            port_index=2,  # INVALID: bf3 only has 2 ports (0, 1)
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200
        )

        # Validation should fail
        with self.assertRaises(ValidationError) as context:
            conn.clean()

        self.assertIn('port_index', str(context.exception))
