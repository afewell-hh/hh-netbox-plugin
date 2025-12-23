"""
Tests for Topology Planning Calculation Engine (DIET-003)

Tests the core switch quantity calculation logic including:
- Breakout selection based on connection speed
- Leaf switch sizing based on port demand
- MCLAG even-count enforcement
- Uplink port reservation
"""

from django.test import TestCase
from django.contrib.auth import get_user_model

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    BreakoutOption,
    DeviceTypeExtension,
)
from netbox_hedgehog.utils.topology_calculations import (
    determine_optimal_breakout,
    calculate_switch_quantity,
)
from dcim.models import DeviceType, Manufacturer

User = get_user_model()


class DetermineOptimalBreakoutTestCase(TestCase):
    """Test suite for determine_optimal_breakout() function"""

    @classmethod
    def setUpTestData(cls):
        """Get or create breakout options for testing (may already exist from seed data)"""
        # 800G breakout options
        cls.breakout_800g_1x, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x800g',
            defaults={'from_speed': 800, 'logical_ports': 1, 'logical_speed': 800}
        )
        cls.breakout_800g_2x, _ = BreakoutOption.objects.get_or_create(
            breakout_id='2x400g',
            defaults={'from_speed': 800, 'logical_ports': 2, 'logical_speed': 400}
        )
        cls.breakout_800g_4x, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200}
        )
        cls.breakout_800g_8x, _ = BreakoutOption.objects.get_or_create(
            breakout_id='8x100g',
            defaults={'from_speed': 800, 'logical_ports': 8, 'logical_speed': 100}
        )

        # 100G breakout options
        cls.breakout_100g_1x, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x100g',
            defaults={'from_speed': 100, 'logical_ports': 1, 'logical_speed': 100}
        )
        cls.breakout_100g_4x, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x25g',
            defaults={'from_speed': 100, 'logical_ports': 4, 'logical_speed': 25}
        )

    def test_exact_match_800g_to_400g(self):
        """Test finding exact match: 800G port with 400G connection speed"""
        breakout = determine_optimal_breakout(
            native_speed=800,
            required_speed=400,
            supported_breakouts=['1x800g', '2x400g', '4x200g', '8x100g']
        )
        self.assertEqual(breakout.breakout_id, '2x400g')
        self.assertEqual(breakout.logical_ports, 2)
        self.assertEqual(breakout.logical_speed, 400)

    def test_exact_match_800g_to_200g(self):
        """Test finding exact match: 800G port with 200G connection speed"""
        breakout = determine_optimal_breakout(
            native_speed=800,
            required_speed=200,
            supported_breakouts=['1x800g', '2x400g', '4x200g', '8x100g']
        )
        self.assertEqual(breakout.breakout_id, '4x200g')
        self.assertEqual(breakout.logical_ports, 4)
        self.assertEqual(breakout.logical_speed, 200)

    def test_exact_match_100g_to_25g(self):
        """Test finding exact match: 100G port with 25G connection speed"""
        breakout = determine_optimal_breakout(
            native_speed=100,
            required_speed=25,
            supported_breakouts=['1x100g', '4x25g']
        )
        self.assertEqual(breakout.breakout_id, '4x25g')
        self.assertEqual(breakout.logical_ports, 4)
        self.assertEqual(breakout.logical_speed, 25)

    def test_no_match_fallback_to_native(self):
        """Test fallback to native speed when no breakout matches"""
        breakout = determine_optimal_breakout(
            native_speed=800,
            required_speed=50,  # No 50G breakout exists
            supported_breakouts=['1x800g', '2x400g', '4x200g']
        )
        self.assertEqual(breakout.breakout_id, '1x800g')
        self.assertEqual(breakout.logical_ports, 1)
        self.assertEqual(breakout.logical_speed, 800)

    def test_empty_supported_breakouts_fallback(self):
        """Test fallback when supported_breakouts is empty"""
        breakout = determine_optimal_breakout(
            native_speed=800,
            required_speed=200,
            supported_breakouts=[]
        )
        # Should create a synthetic 1:1 breakout
        self.assertEqual(breakout.logical_ports, 1)
        self.assertEqual(breakout.logical_speed, 800)


class CalculateSwitchQuantityTestCase(TestCase):
    """Test suite for calculate_switch_quantity() function"""

    @classmethod
    def setUpTestData(cls):
        """Create test data for switch quantity calculations"""
        cls.user = User.objects.create_user(username='testuser')

        # Get or create manufacturer (may already exist from seed data)
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )

        # Get or create switch device type (DS5000 - 64x800G)
        cls.switch_device_type, created = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={
                'slug': 'ds5000',
                'u_height': 1,
                'is_full_depth': True
            }
        )

        # Get or create device type extension for switch
        # Use update_or_create to ensure values are current (important for --keepdb)
        cls.switch_extension, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_device_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf'],
                'supported_breakouts': ['1x800g', '2x400g', '4x200g', '8x100g'],
                'native_speed': 800,
                'uplink_ports': 4
            }
        )

        # Create server device type
        cls.server_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='GPU-Server-B200',
            defaults={
                'slug': 'gpu-server-b200',
                'u_height': 2
            }
        )

        # Get or create breakout options (may already exist from seed data)
        BreakoutOption.objects.get_or_create(
            breakout_id='1x800g',
            defaults={'from_speed': 800, 'logical_ports': 1, 'logical_speed': 800}
        )
        BreakoutOption.objects.get_or_create(
            breakout_id='2x400g',
            defaults={'from_speed': 800, 'logical_ports': 2, 'logical_speed': 400}
        )
        BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200}
        )

    def setUp(self):
        """Create fresh plan for each test"""
        self.plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer',
            created_by=self.user
        )

    def test_calculate_single_server_class_basic(self):
        """Test basic calculation: 32 servers with 2x200G ports"""
        # Create switch class
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-gpu-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=4,
            mclag_pair=False
        )

        # Create server class: 32 GPU servers
        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='GPU-B200',
            server_device_type=self.server_device_type,
            quantity=32,
            gpus_per_server=8
        )

        # Create connection: 2x200G ports per server
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='FE-001',
            ports_per_connection=2,
            hedgehog_conn_type='unbundled',
            distribution='alternating',
            target_switch_class=switch_class,
            speed=200
        )

        # Calculate switch quantity
        result = calculate_switch_quantity(switch_class)

        # Expected calculation:
        # - 32 servers × 2 ports = 64 total ports needed
        # - 64 physical ports × 4 breakout (4x200G) = 256 logical ports
        # - 256 - 4 uplink = 252 available ports
        # - 64 needed ÷ 252 available = 0.25... → ceil = 1 switch
        self.assertEqual(result, 1)

    def test_calculate_requires_two_switches(self):
        """Test calculation requiring 2 switches due to port demand"""
        # Create switch class
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-gpu-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=4,
            mclag_pair=False
        )

        # Create server class: 128 GPU servers
        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='GPU-B200',
            server_device_type=self.server_device_type,
            quantity=128,
            gpus_per_server=8
        )

        # Create connection: 2x200G ports per server
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='FE-001',
            ports_per_connection=2,
            hedgehog_conn_type='unbundled',
            distribution='alternating',
            target_switch_class=switch_class,
            speed=200
        )

        # Calculate switch quantity
        result = calculate_switch_quantity(switch_class)

        # Expected calculation:
        # - 128 servers × 2 ports = 256 total ports needed
        # - 64 physical ports × 4 breakout (4x200G) = 256 logical ports
        # - 256 - 4 uplink = 252 available ports
        # - 256 needed ÷ 252 available = 1.015... → ceil = 2 switches
        self.assertEqual(result, 2)

    def test_mclag_even_count_enforcement(self):
        """Test MCLAG pairs must have even switch count"""
        # Create switch class with MCLAG enabled
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-gpu-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=4,
            mclag_pair=True  # MCLAG enabled
        )

        # Create server class: 32 servers (would calculate to 1 switch)
        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='GPU-B200',
            server_device_type=self.server_device_type,
            quantity=32,
            gpus_per_server=8
        )

        # Create connection: 2x200G ports per server
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='FE-001',
            ports_per_connection=2,
            hedgehog_conn_type='mclag',
            distribution='alternating',
            target_switch_class=switch_class,
            speed=200
        )

        # Calculate switch quantity
        result = calculate_switch_quantity(switch_class)

        # Expected: Would calculate to 1, but MCLAG requires even count
        # so should round up to 2
        self.assertEqual(result, 2)

    def test_multiple_server_classes_same_target(self):
        """Test calculation with multiple server classes targeting same switch"""
        # Create switch class
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=4,
            mclag_pair=False
        )

        # Create GPU server class: 32 servers × 2 ports
        gpu_server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='GPU-B200',
            server_device_type=self.server_device_type,
            quantity=32,
            gpus_per_server=8
        )
        PlanServerConnection.objects.create(
            server_class=gpu_server_class,
            connection_id='FE-GPU',
            ports_per_connection=2,
            hedgehog_conn_type='unbundled',
            distribution='same-switch',
            target_switch_class=switch_class,
            speed=200
        )

        # Create storage server class: 16 servers × 2 ports
        storage_server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='STORAGE-A',
            server_device_type=self.server_device_type,
            quantity=16
        )
        PlanServerConnection.objects.create(
            server_class=storage_server_class,
            connection_id='FE-STORAGE',
            ports_per_connection=2,
            hedgehog_conn_type='bundled',
            distribution='same-switch',
            target_switch_class=switch_class,
            speed=200
        )

        # Calculate switch quantity
        result = calculate_switch_quantity(switch_class)

        # Expected calculation:
        # - GPU: 32 × 2 = 64 ports
        # - Storage: 16 × 2 = 32 ports
        # - Total: 96 ports needed
        # - 64 physical × 4 breakout = 256 logical - 4 uplink = 252 available
        # - 96 ÷ 252 = 0.38... → ceil = 1 switch
        self.assertEqual(result, 1)

    def test_no_connections_returns_zero(self):
        """Test that switch with no connections calculates to 0"""
        # Create switch class with no connections
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='unused-switch',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0,
            mclag_pair=False
        )

        # Calculate switch quantity (no connections exist)
        result = calculate_switch_quantity(switch_class)

        # Expected: 0 switches needed
        self.assertEqual(result, 0)

    def test_uplink_ports_reduce_available_capacity(self):
        """Test that uplink ports are correctly subtracted from available ports"""
        # Create switch class with many uplink ports
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=64,  # Use all physical ports for uplinks
            mclag_pair=False
        )

        # Create server class: 1 server
        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='GPU-B200',
            server_device_type=self.server_device_type,
            quantity=1
        )

        # Create connection: 1 port
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='FE-001',
            ports_per_connection=1,
            hedgehog_conn_type='unbundled',
            distribution='same-switch',
            target_switch_class=switch_class,
            speed=200
        )

        # Calculate switch quantity
        result = calculate_switch_quantity(switch_class)

        # Expected: With 64 uplink ports reserved,
        # 64 physical × 4 breakout = 256 logical - 64 uplink = 192 available
        # 1 port needed ÷ 192 available = ceil(0.005) = 1 switch
        self.assertEqual(result, 1)
