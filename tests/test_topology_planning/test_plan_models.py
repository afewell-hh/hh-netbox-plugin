"""
Tests for Topology Planning Plan Models (DIET-002)

Following TDD approach - these tests define expected behavior before implementation.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from dcim.models import DeviceType, Manufacturer, ModuleType
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    ServerClassCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    ConnectionDistributionChoices,
    PortTypeChoices,
)

User = get_user_model()


class TopologyPlanTestCase(TestCase):
    """Test cases for TopologyPlan model"""

    def setUp(self):
        """Create test user"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_create_topology_plan(self):
        """Test basic TopologyPlan creation"""
        from netbox_hedgehog.models.topology_planning import TopologyPlan

        plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer',
            description='Test description',
            status=TopologyPlanStatusChoices.DRAFT,
            created_by=self.user
        )

        self.assertEqual(plan.name, 'Test Plan')
        self.assertEqual(plan.customer_name, 'Test Customer')
        self.assertEqual(plan.status, TopologyPlanStatusChoices.DRAFT)
        self.assertEqual(plan.created_by, self.user)

    def test_topology_plan_str(self):
        """Test __str__ returns plan name"""
        from netbox_hedgehog.models.topology_planning import TopologyPlan

        plan = TopologyPlan.objects.create(
            name='Cambium 2MW',
            created_by=self.user
        )
        self.assertEqual(str(plan), 'Cambium 2MW')

    def test_topology_plan_default_status(self):
        """Test TopologyPlan defaults to draft status"""
        from netbox_hedgehog.models.topology_planning import TopologyPlan

        plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=self.user
        )
        self.assertEqual(plan.status, TopologyPlanStatusChoices.DRAFT)

    def test_topology_plan_timestamps(self):
        """Test TopologyPlan has created_at and updated_at timestamps"""
        from netbox_hedgehog.models.topology_planning import TopologyPlan

        plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=self.user
        )

        self.assertIsNotNone(plan.created_at)
        self.assertIsNotNone(plan.updated_at)

    def test_topology_plan_cascade_delete(self):
        """Test TopologyPlan cascades delete to related objects"""
        from netbox_hedgehog.models.topology_planning import (
            TopologyPlan,
            PlanServerClass,
        )

        # Create manufacturer and device type for server
        manufacturer = Manufacturer.objects.create(
            name='Test Manufacturer',
            slug='test-manufacturer'
        )
        server_type = DeviceType.objects.create(
            manufacturer=manufacturer,
            model='TestServer',
            slug='testserver',
            u_height=2
        )

        plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=self.user
        )

        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='TEST-001',
            server_device_type=server_type,
            quantity=10
        )

        server_class_id = server_class.id
        plan.delete()

        # Server class should be deleted via cascade
        from netbox_hedgehog.models.topology_planning import PlanServerClass
        with self.assertRaises(PlanServerClass.DoesNotExist):
            PlanServerClass.objects.get(id=server_class_id)


class PlanServerClassTestCase(TestCase):
    """Test cases for PlanServerClass model"""

    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        from netbox_hedgehog.models.topology_planning import TopologyPlan
        self.plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=self.user
        )

        self.manufacturer = Manufacturer.objects.create(
            name='Dell',
            slug='dell'
        )

        self.server_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='PowerEdge R750',
            slug='poweredge-r750',
            u_height=2
        )

    def test_create_plan_server_class(self):
        """Test basic PlanServerClass creation"""
        from netbox_hedgehog.models.topology_planning import PlanServerClass

        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='GPU-B200',
            description='GPU training server',
            category=ServerClassCategoryChoices.GPU,
            server_device_type=self.server_type,
            quantity=32,
            gpus_per_server=8
        )

        self.assertEqual(server_class.server_class_id, 'GPU-B200')
        self.assertEqual(server_class.category, ServerClassCategoryChoices.GPU)
        self.assertEqual(server_class.quantity, 32)
        self.assertEqual(server_class.gpus_per_server, 8)

    def test_plan_server_class_str(self):
        """Test __str__ returns server_class_id"""
        from netbox_hedgehog.models.topology_planning import PlanServerClass

        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='GPU-B200',
            server_device_type=self.server_type,
            quantity=32
        )
        self.assertIn('GPU-B200', str(server_class))

    def test_plan_server_class_quantity_validation(self):
        """Test quantity must be positive"""
        from netbox_hedgehog.models.topology_planning import PlanServerClass

        server_class = PlanServerClass(
            plan=self.plan,
            server_class_id='TEST',
            server_device_type=self.server_type,
            quantity=-1
        )
        with self.assertRaises(ValidationError):
            server_class.full_clean()

    def test_plan_server_class_defaults(self):
        """Test PlanServerClass default values"""
        from netbox_hedgehog.models.topology_planning import PlanServerClass

        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='TEST',
            server_device_type=self.server_type,
            quantity=10
        )

        self.assertEqual(server_class.gpus_per_server, 0)


class PlanSwitchClassTestCase(TestCase):
    """Test cases for PlanSwitchClass model"""

    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        from netbox_hedgehog.models.topology_planning import TopologyPlan
        self.plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=self.user
        )

        self.manufacturer = Manufacturer.objects.create(
            name='Celestica',
            slug='celestica'
        )

        self.switch_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='DS5000',
            slug='ds5000',
            u_height=1
        )

        self.device_type_ext = DeviceTypeExtension.objects.create(
            device_type=self.switch_type,
            mclag_capable=False,
            hedgehog_roles=['spine', 'server-leaf']
        )

    def test_create_plan_switch_class(self):
        """Test basic PlanSwitchClass creation"""
        from netbox_hedgehog.models.topology_planning import PlanSwitchClass

        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-gpu-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_type_ext,
            uplink_ports_per_switch=4,
            mclag_pair=True,
            calculated_quantity=4,
            override_quantity=6
        )

        self.assertEqual(switch_class.switch_class_id, 'fe-gpu-leaf')
        self.assertEqual(switch_class.fabric, FabricTypeChoices.FRONTEND)
        self.assertEqual(switch_class.hedgehog_role, HedgehogRoleChoices.SERVER_LEAF)
        self.assertEqual(switch_class.calculated_quantity, 4)
        self.assertEqual(switch_class.override_quantity, 6)
        self.assertTrue(switch_class.mclag_pair)

    def test_plan_switch_class_effective_quantity_override(self):
        """Test effective_quantity returns override when set"""
        from netbox_hedgehog.models.topology_planning import PlanSwitchClass

        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='test-switch',
            device_type_extension=self.device_type_ext,
            calculated_quantity=4,
            override_quantity=6
        )

        self.assertEqual(switch_class.effective_quantity, 6)

    def test_plan_switch_class_effective_quantity_calculated(self):
        """Test effective_quantity returns calculated when no override"""
        from netbox_hedgehog.models.topology_planning import PlanSwitchClass

        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='test-switch',
            device_type_extension=self.device_type_ext,
            calculated_quantity=4,
            override_quantity=None
        )

        self.assertEqual(switch_class.effective_quantity, 4)

    def test_plan_switch_class_effective_quantity_zero(self):
        """Test effective_quantity handles zero/None gracefully"""
        from netbox_hedgehog.models.topology_planning import PlanSwitchClass

        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='test-switch',
            device_type_extension=self.device_type_ext,
            calculated_quantity=None,
            override_quantity=None
        )

        self.assertEqual(switch_class.effective_quantity, 0)

    def test_plan_switch_class_str(self):
        """Test __str__ returns switch_class_id"""
        from netbox_hedgehog.models.topology_planning import PlanSwitchClass

        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            device_type_extension=self.device_type_ext
        )
        self.assertIn('fe-spine', str(switch_class))

    def test_plan_switch_class_defaults(self):
        """Test PlanSwitchClass default values"""
        from netbox_hedgehog.models.topology_planning import PlanSwitchClass

        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='test-switch',
            device_type_extension=self.device_type_ext
        )

        self.assertFalse(switch_class.mclag_pair)
        self.assertEqual(switch_class.uplink_ports_per_switch, 0)


class PlanServerConnectionTestCase(TestCase):
    """Test cases for PlanServerConnection model"""

    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        from netbox_hedgehog.models.topology_planning import (
            TopologyPlan,
            PlanServerClass,
            PlanSwitchClass,
        )

        self.plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=self.user
        )

        manufacturer = Manufacturer.objects.create(
            name='Dell',
            slug='dell'
        )

        server_type = DeviceType.objects.create(
            manufacturer=manufacturer,
            model='PowerEdge R750',
            slug='poweredge-r750',
            u_height=2
        )

        self.server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='GPU-B200',
            server_device_type=server_type,
            quantity=32
        )

        switch_manufacturer = Manufacturer.objects.create(
            name='Celestica',
            slug='celestica'
        )

        switch_type = DeviceType.objects.create(
            manufacturer=switch_manufacturer,
            model='DS5000',
            slug='ds5000',
            u_height=1
        )

        device_type_ext = DeviceTypeExtension.objects.create(
            device_type=switch_type,
            mclag_capable=False
        )

        self.switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-gpu-leaf',
            device_type_extension=device_type_ext
        )

    def test_create_plan_server_connection(self):
        """Test basic PlanServerConnection creation"""
        from netbox_hedgehog.models.topology_planning import PlanServerConnection

        connection = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='FE-001',
            connection_name='frontend',
            ports_per_connection=2,
            hedgehog_conn_type='unbundled',
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_switch_class=self.switch_class,
            speed=200,
            port_type=PortTypeChoices.DATA
        )

        self.assertEqual(connection.connection_id, 'FE-001')
        self.assertEqual(connection.ports_per_connection, 2)
        self.assertEqual(connection.distribution, ConnectionDistributionChoices.ALTERNATING)
        self.assertEqual(connection.speed, 200)

    def test_plan_server_connection_optional_nic_module(self):
        """Test nic_module_type is optional"""
        from netbox_hedgehog.models.topology_planning import PlanServerConnection

        connection = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='TEST',
            ports_per_connection=1,
            target_switch_class=self.switch_class,
            nic_module_type=None  # Optional for MVP
        )

        self.assertIsNone(connection.nic_module_type)

    def test_plan_server_connection_str(self):
        """Test __str__ returns readable format"""
        from netbox_hedgehog.models.topology_planning import PlanServerConnection

        connection = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='FE-001',
            connection_name='frontend',
            ports_per_connection=2,
            target_switch_class=self.switch_class
        )

        self.assertIn('FE-001', str(connection))

    def test_plan_server_connection_cascade_delete(self):
        """Test connection is deleted when server_class is deleted"""
        from netbox_hedgehog.models.topology_planning import PlanServerConnection

        connection = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='TEST',
            ports_per_connection=1,
            target_switch_class=self.switch_class
        )

        connection_id = connection.id
        self.server_class.delete()

        with self.assertRaises(PlanServerConnection.DoesNotExist):
            PlanServerConnection.objects.get(id=connection_id)

    def test_plan_server_connection_defaults(self):
        """Test PlanServerConnection default values"""
        from netbox_hedgehog.models.topology_planning import PlanServerConnection

        connection = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='TEST',
            ports_per_connection=1,
            target_switch_class=self.switch_class
        )

        self.assertEqual(connection.speed, 0)


class PlanMCLAGDomainTestCase(TestCase):
    """Test cases for PlanMCLAGDomain model"""

    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        from netbox_hedgehog.models.topology_planning import (
            TopologyPlan,
            PlanSwitchClass,
        )

        self.plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=self.user
        )

        manufacturer = Manufacturer.objects.create(
            name='NVIDIA',
            slug='nvidia'
        )

        switch_type = DeviceType.objects.create(
            manufacturer=manufacturer,
            model='SN5600',
            slug='sn5600',
            u_height=1
        )

        device_type_ext = DeviceTypeExtension.objects.create(
            device_type=switch_type,
            mclag_capable=True
        )

        self.switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-gpu-leaf',
            device_type_extension=device_type_ext,
            mclag_pair=True
        )

    def test_create_plan_mclag_domain(self):
        """Test basic PlanMCLAGDomain creation"""
        from netbox_hedgehog.models.topology_planning import PlanMCLAGDomain

        mclag = PlanMCLAGDomain.objects.create(
            plan=self.plan,
            domain_id='MCLAG-001',
            switch_class=self.switch_class,
            peer_link_count=2,
            session_link_count=2,
            peer_start_port=1,
            session_start_port=3
        )

        self.assertEqual(mclag.domain_id, 'MCLAG-001')
        self.assertEqual(mclag.peer_link_count, 2)
        self.assertEqual(mclag.session_link_count, 2)

    def test_plan_mclag_domain_str(self):
        """Test __str__ returns domain_id"""
        from netbox_hedgehog.models.topology_planning import PlanMCLAGDomain

        mclag = PlanMCLAGDomain.objects.create(
            plan=self.plan,
            domain_id='MCLAG-001',
            switch_class=self.switch_class,
            peer_link_count=2,
            session_link_count=2
        )

        self.assertIn('MCLAG-001', str(mclag))

    def test_plan_mclag_domain_cascade_delete(self):
        """Test MCLAG domain is deleted when plan is deleted"""
        from netbox_hedgehog.models.topology_planning import PlanMCLAGDomain

        mclag = PlanMCLAGDomain.objects.create(
            plan=self.plan,
            domain_id='TEST',
            switch_class=self.switch_class,
            peer_link_count=2,
            session_link_count=2
        )

        mclag_id = mclag.id
        self.plan.delete()

        with self.assertRaises(PlanMCLAGDomain.DoesNotExist):
            PlanMCLAGDomain.objects.get(id=mclag_id)

    def test_plan_mclag_domain_defaults(self):
        """Test PlanMCLAGDomain default values"""
        from netbox_hedgehog.models.topology_planning import PlanMCLAGDomain

        mclag = PlanMCLAGDomain.objects.create(
            plan=self.plan,
            domain_id='TEST',
            switch_class=self.switch_class,
            peer_link_count=2,
            session_link_count=2
        )

        self.assertEqual(mclag.peer_start_port, 0)
        self.assertEqual(mclag.session_start_port, 0)
