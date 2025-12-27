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
from django.core.exceptions import ValidationError

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
    calculate_spine_quantity,
    determine_leaf_uplink_breakout,
    update_plan_calculations,
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

    def test_no_match_with_policy_raises_validation_error(self):
        """Test that no match with non-empty policy raises ValidationError"""
        # Policy set but doesn't include required breakout or 1x fallback
        with self.assertRaises(ValidationError) as cm:
            determine_optimal_breakout(
                native_speed=800,
                required_speed=50,  # No 50G option exists
                supported_breakouts=['2x400g', '4x200g']  # Policy excludes 1x800g
            )
        # Should raise ValidationError with helpful message
        self.assertIn('50', str(cm.exception))
        self.assertIn('800', str(cm.exception))
        self.assertIn('2x400g', str(cm.exception))

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

    def test_rail_optimized_distribution_calculates_per_rail(self):
        """Test rail-optimized connections calculate switches per rail"""
        # Create backend rail leaf switch class
        be_rail_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='be-rail-leaf',
            fabric='backend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
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

        # Create 8 rail-optimized connections (1 port per server per rail)
        for rail in range(8):
            PlanServerConnection.objects.create(
                server_class=server_class,
                connection_id=f'BE-RAIL-{rail}',
                ports_per_connection=1,
                hedgehog_conn_type='unbundled',
                distribution='rail-optimized',
                target_switch_class=be_rail_leaf,
                speed=400,
                rail=rail
            )

        # Calculate switch quantity
        result = calculate_switch_quantity(be_rail_leaf)

        # Expected calculation with rail-awareness:
        # - 8 rails with rail-optimized distribution
        # - 32 servers × 1 port per rail = 32 ports per rail
        # - 64 physical ports × 2 breakout (2x400G) = 128 logical ports
        # - 128 - 32 uplink = 96 available ports per switch
        # - 32 ports per rail ÷ 96 available = 0.33... → ceil = 1 switch per rail
        # - 1 switch × 8 rails = 8 switches total
        self.assertEqual(result, 8)


class CalculateSpineQuantityTestCase(TestCase):
    """Test suite for calculate_spine_quantity() function"""

    @classmethod
    def setUpTestData(cls):
        """Create test data for spine quantity calculations"""
        cls.user = User.objects.create_user(username='testuser')

        # Get or create manufacturer
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )

        # Get or create switch device type (DS5000 - 64x800G)
        cls.switch_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={
                'slug': 'ds5000',
                'u_height': 1,
                'is_full_depth': True
            }
        )

        # Get or create device type extension
        cls.switch_extension, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_device_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf'],
                'supported_breakouts': ['1x800g', '2x400g', '4x200g', '8x100g'],
                'native_speed': 800,
                'uplink_ports': 32
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

        # Get or create breakout options
        BreakoutOption.objects.get_or_create(
            breakout_id='1x800g',
            defaults={'from_speed': 800, 'logical_ports': 1, 'logical_speed': 800}
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

    def test_calculate_spine_for_single_leaf(self):
        """Test spine sizing with single leaf switch"""
        # Create frontend spine
        fe_spine = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0,
            mclag_pair=False
        )

        # Create frontend leaf with 2 switches, each needing 32 uplink ports
        fe_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=True,
            calculated_quantity=2
        )

        # Calculate spine quantity
        result = calculate_spine_quantity(fe_spine)

        # Expected calculation:
        # - 2 leaf switches × 32 uplinks = 64 uplink ports needed
        # - Spine: 64 physical × 1 breakout (1x800G) = 64 logical ports
        # - 64 - 0 uplink = 64 available ports per spine
        # - 64 needed ÷ 64 available = 1 spine
        self.assertEqual(result, 1)

    def test_calculate_spine_with_multiple_leaves(self):
        """Test spine sizing with multiple leaf classes"""
        # Create frontend spine
        fe_spine = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0,
            mclag_pair=False
        )

        # Create multiple frontend leaf classes
        fe_gpu_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-gpu-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=True,
            calculated_quantity=2
        )
        fe_storage_leaf_a = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-storage-leaf-a',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False,
            calculated_quantity=1
        )
        fe_storage_leaf_b = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-storage-leaf-b',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False,
            calculated_quantity=1
        )

        # Calculate spine quantity
        result = calculate_spine_quantity(fe_spine)

        # Expected calculation:
        # - fe-gpu-leaf: 2 switches × 32 uplinks = 64 ports
        # - fe-storage-leaf-a: 1 switch × 32 uplinks = 32 ports
        # - fe-storage-leaf-b: 1 switch × 32 uplinks = 32 ports
        # - Total: 64 + 32 + 32 = 128 uplink ports needed
        # - Spine: 64 physical × 1 breakout (1x800G) = 64 logical ports
        # - 64 - 0 uplink = 64 available ports per spine
        # - 128 needed ÷ 64 available = 2 spines
        self.assertEqual(result, 2)

    def test_calculate_spine_ignores_different_fabric(self):
        """Test that spine calculation only considers leaves from same fabric"""
        # Create frontend spine
        fe_spine = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0,
            mclag_pair=False
        )

        # Create frontend leaf
        fe_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False,
            calculated_quantity=2
        )

        # Create backend leaf (should be ignored)
        be_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='be-leaf',
            fabric='backend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False,
            calculated_quantity=8
        )

        # Calculate frontend spine quantity
        result = calculate_spine_quantity(fe_spine)

        # Expected calculation:
        # - Only fe-leaf counted: 2 switches × 32 uplinks = 64 ports
        # - be-leaf ignored (different fabric)
        # - Spine: 64 physical × 1 breakout = 64 available
        # - 64 needed ÷ 64 available = 1 spine
        self.assertEqual(result, 1)

    def test_calculate_spine_returns_zero_when_no_leaves(self):
        """Test that spine calculation returns 0 when no leaves exist"""
        # Create spine with no leaves
        fe_spine = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0,
            mclag_pair=False
        )

        # Calculate spine quantity
        result = calculate_spine_quantity(fe_spine)

        # Expected: 0 spines needed
        self.assertEqual(result, 0)

    def test_calculate_spine_uses_override_quantity_from_leaves(self):
        """Test that spine calculation uses effective_quantity (override if set) from leaves"""
        # Create frontend spine
        fe_spine = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0,
            mclag_pair=False
        )

        # Create leaf with override_quantity set
        fe_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False,
            calculated_quantity=2,
            override_quantity=4  # Override to 4 switches
        )

        # Calculate spine quantity
        result = calculate_spine_quantity(fe_spine)

        # Expected calculation:
        # - Leaf effective_quantity = 4 (override set)
        # - 4 switches × 32 uplinks = 128 uplink ports needed
        # - Spine: 64 physical × 1 breakout = 64 available
        # - 128 needed ÷ 64 available = 2 spines
        self.assertEqual(result, 2)


class DetermineLeafUplinkBreakoutTestCase(TestCase):
    """Test suite for determine_leaf_uplink_breakout() function"""

    @classmethod
    def setUpTestData(cls):
        """Create test data for uplink breakout determination"""
        cls.user = User.objects.create_user(username='testuser')

        # Get or create manufacturer
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )

        # Get or create switch device type (DS5000 - 64x800G)
        cls.switch_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={
                'slug': 'ds5000',
                'u_height': 1,
                'is_full_depth': True
            }
        )

        # Get or create device type extension
        cls.switch_extension, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_device_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf'],
                'supported_breakouts': ['1x800g', '2x400g', '4x200g', '8x100g'],
                'native_speed': 800,
                'uplink_ports': 32
            }
        )

        # Get or create breakout options
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
        BreakoutOption.objects.get_or_create(
            breakout_id='8x100g',
            defaults={'from_speed': 800, 'logical_ports': 8, 'logical_speed': 100}
        )

    def setUp(self):
        """Create fresh plan for each test"""
        self.plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer',
            created_by=self.user
        )

    def test_no_breakout_needed_when_ports_exceed_spines(self):
        """Test that no breakout is needed when physical ports >= spines"""
        # Create leaf with 32 uplink ports
        leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False
        )

        # Scenario: 32 uplink ports, only 16 spines needed
        # No breakout required (32 physical >= 16 spines)
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=leaf,
            spines_needed=16,
            min_link_speed=800  # Spine connections at 800G
        )

        # Should return 1x800G (no breakout)
        self.assertEqual(breakout.breakout_id, '1x800g')
        self.assertEqual(breakout.logical_ports, 1)
        self.assertEqual(breakout.logical_speed, 800)

    def test_2x_breakout_for_double_spines(self):
        """Test 2x breakout when spines = 2x physical ports"""
        # Create leaf with 32 uplink ports
        leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False
        )

        # Scenario: 32 uplink ports, 64 spines needed
        # Requires 2x breakout: 32 × 2 = 64 logical ports
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=leaf,
            spines_needed=64,
            min_link_speed=400  # Spine connections at 400G
        )

        # Should return 2x400G breakout
        self.assertEqual(breakout.breakout_id, '2x400g')
        self.assertEqual(breakout.logical_ports, 2)
        self.assertEqual(breakout.logical_speed, 400)

    def test_4x_breakout_for_quad_spines(self):
        """Test 4x breakout when spines = 4x physical ports"""
        # Create leaf with 32 uplink ports
        leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False
        )

        # Scenario: 32 uplink ports, 128 spines needed
        # Requires 4x breakout: 32 × 4 = 128 logical ports
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=leaf,
            spines_needed=128,
            min_link_speed=200  # Spine connections at 200G
        )

        # Should return 4x200G breakout
        self.assertEqual(breakout.breakout_id, '4x200g')
        self.assertEqual(breakout.logical_ports, 4)
        self.assertEqual(breakout.logical_speed, 200)

    def test_rejects_breakout_below_min_speed(self):
        """Test that breakout is rejected if speed is too low"""
        # Create leaf with 32 uplink ports
        leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False
        )

        # Scenario: 32 uplink ports, 128 spines needed
        # Would need 4x breakout, but min_link_speed is 400G
        # 4x200G would only give 200G links, which is < 400G required
        # Should return None or raise error
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=leaf,
            spines_needed=128,
            min_link_speed=400  # Require 400G links
        )

        # Should return None (no valid breakout)
        self.assertIsNone(breakout)

    def test_no_valid_breakout_returns_none(self):
        """Test that None is returned when no breakout can satisfy requirements"""
        # Create leaf with 32 uplink ports
        leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False
        )

        # Scenario: 32 uplink ports, 512 spines needed
        # Would need 16x breakout (512/32), but max supported is 8x
        # No valid breakout exists
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=leaf,
            spines_needed=512,
            min_link_speed=100  # Even with low speed requirement
        )

        # Should return None
        self.assertIsNone(breakout)

    def test_chooses_smallest_valid_breakout(self):
        """Test that smallest breakout factor is chosen when multiple options work"""
        # Create leaf with 32 uplink ports
        leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False
        )

        # Scenario: 32 uplink ports, 48 spines needed
        # Could use 2x (32×2=64) or 4x (32×4=128) or 8x (32×8=256)
        # Should choose 2x as smallest factor that works
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=leaf,
            spines_needed=48,
            min_link_speed=200  # Allow 2x400G, 4x200G, 8x100G (all have >=200G? No, 8x100G is excluded)
        )

        # Should return 2x400G (smallest that satisfies 48 spines and >=200G speed)
        self.assertEqual(breakout.breakout_id, '2x400g')
        self.assertEqual(breakout.logical_ports, 2)


class BreakoutAwareSpineSizingIntegrationTestCase(TestCase):
    """Integration test for breakout-aware spine sizing workflow"""

    @classmethod
    def setUpTestData(cls):
        """Create test data for integration testing"""
        cls.user = User.objects.create_user(username='testuser')

        # Get or create manufacturer
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )

        # Get or create switch device type (DS5000 - 64x800G)
        cls.switch_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={
                'slug': 'ds5000',
                'u_height': 1,
                'is_full_depth': True
            }
        )

        # Get or create device type extension
        cls.switch_extension, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_device_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf'],
                'supported_breakouts': ['1x800g', '2x400g', '4x200g', '8x100g'],
                'native_speed': 800,
                'uplink_ports': 32
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

        # Get or create breakout options
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

    def test_breakout_aware_spine_sizing_workflow(self):
        """Test complete workflow: calculate spines, then determine required breakouts"""
        # Create frontend spine
        fe_spine = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0,
            mclag_pair=False
        )

        # Create 8 frontend leaf switches (large fabric scenario)
        # Each leaf: 32 uplink ports @ 800G
        fe_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False,
            calculated_quantity=8  # 8 leaf switches
        )

        # Step 1: Calculate spine quantity (bandwidth-based)
        # 8 leaves × 32 uplinks = 256 total uplink ports
        # Spine capacity: 64 ports
        # Spines needed: 256 ÷ 64 = 4 spines
        spines_calculated = calculate_spine_quantity(fe_spine)
        self.assertEqual(spines_calculated, 4)

        # Step 2: Determine required uplink breakout for leaves
        # Each leaf has 32 physical uplink ports
        # Must connect to 4 spines
        # 32 physical ports >= 4 spines, so no breakout needed
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=fe_leaf,
            spines_needed=spines_calculated,
            min_link_speed=800
        )
        self.assertEqual(breakout.breakout_id, '1x800g')
        self.assertEqual(breakout.logical_ports, 1)

    def test_breakout_required_for_many_spines(self):
        """Test scenario where breakout is required: 64 spines with 32 uplink ports"""
        # Create frontend spine
        fe_spine = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0,
            mclag_pair=False
        )

        # Create 64 frontend leaf switches (very large fabric)
        # Each leaf: 32 uplink ports @ 800G
        fe_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False,
            calculated_quantity=64  # 64 leaf switches
        )

        # Step 1: Calculate spine quantity
        # 64 leaves × 32 uplinks = 2048 total uplink ports
        # Spine capacity: 64 ports
        # Spines needed: 2048 ÷ 64 = 32 spines
        spines_calculated = calculate_spine_quantity(fe_spine)
        self.assertEqual(spines_calculated, 32)

        # Step 2: Determine required uplink breakout
        # Each leaf has 32 physical uplink ports
        # Must connect to 32 spines
        # 32 physical == 32 spines, so no breakout needed (exactly matches)
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=fe_leaf,
            spines_needed=spines_calculated,
            min_link_speed=800
        )
        self.assertEqual(breakout.breakout_id, '1x800g')

    def test_2x_breakout_required_scenario(self):
        """Test scenario requiring 2x breakout: 128 spines with 32 uplink ports"""
        # Create frontend spine
        fe_spine = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0,
            mclag_pair=False
        )

        # Create 128 frontend leaf switches (massive fabric)
        fe_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False,
            calculated_quantity=128  # 128 leaf switches
        )

        # Step 1: Calculate spine quantity
        # 128 leaves × 32 uplinks = 4096 total uplink ports
        # Spine capacity: 64 ports
        # Spines needed: 4096 ÷ 64 = 64 spines
        spines_calculated = calculate_spine_quantity(fe_spine)
        self.assertEqual(spines_calculated, 64)

        # Step 2: Determine required uplink breakout
        # Each leaf has 32 physical uplink ports
        # Must connect to 64 spines
        # Needs 2x breakout: 32 × 2 = 64 logical ports
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=fe_leaf,
            spines_needed=spines_calculated,
            min_link_speed=400  # Accept 400G links
        )
        self.assertEqual(breakout.breakout_id, '2x400g')
        self.assertEqual(breakout.logical_ports, 2)
        self.assertEqual(breakout.logical_speed, 400)

class EdgeCaseValidationTestCase(TestCase):
    """Test edge cases and validation scenarios per Agent C review"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        cls.user = User.objects.create_user(username='testuser')

        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )

        cls.switch_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'ds5000', 'u_height': 1, 'is_full_depth': True}
        )

        cls.switch_extension, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_device_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf'],
                'supported_breakouts': ['1x800g', '2x400g', '4x200g', '8x100g'],
                'native_speed': 800,
                'uplink_ports': 32
            }
        )

        cls.server_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='GPU-Server-B200',
            defaults={'slug': 'gpu-server-b200', 'u_height': 2}
        )

        # Create breakout options
        BreakoutOption.objects.get_or_create(
            breakout_id='1x800g',
            defaults={'from_speed': 800, 'logical_ports': 1, 'logical_speed': 800}
        )
        BreakoutOption.objects.get_or_create(
            breakout_id='2x400g',
            defaults={'from_speed': 800, 'logical_ports': 2, 'logical_speed': 400}
        )

    def setUp(self):
        """Create fresh plan for each test"""
        self.plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer',
            created_by=self.user
        )

    def test_rail_mclag_raises_validation_error_for_incompatible_config(self):
        """Test that rail-optimized + MCLAG with odd rail count raises ValidationError"""
        # Create backend rail leaf with MCLAG
        be_rail_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='be-rail-leaf',
            fabric='backend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=True  # MCLAG enabled
        )

        # Create server class: 16 servers
        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='GPU-B200',
            server_device_type=self.server_device_type,
            quantity=16,
            gpus_per_server=8
        )

        # Create 3 rail-optimized connections (odd number of rails)
        # This is INCOMPATIBLE with MCLAG (can't split 3 rails into even pairs)
        for rail in range(3):
            PlanServerConnection.objects.create(
                server_class=server_class,
                connection_id=f'BE-RAIL-{rail}',
                ports_per_connection=1,
                hedgehog_conn_type='unbundled',
                distribution='rail-optimized',
                target_switch_class=be_rail_leaf,
                speed=400,
                rail=rail
            )

        # Calculate switch quantity should raise ValidationError
        with self.assertRaises(ValidationError) as cm:
            calculate_switch_quantity(be_rail_leaf)

        # Check error message is clear
        self.assertIn('rail', str(cm.exception).lower())
        self.assertIn('mclag', str(cm.exception).lower())

    def test_rail_mclag_works_with_even_rails(self):
        """Test that rail-optimized + MCLAG works correctly with even rail count"""
        # Create backend rail leaf with MCLAG
        be_rail_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='be-rail-leaf',
            fabric='backend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=True  # MCLAG enabled
        )

        # Create server class
        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='GPU-B200',
            server_device_type=self.server_device_type,
            quantity=16,
            gpus_per_server=8
        )

        # Create 4 rail-optimized connections (even number of rails)
        # Compatible with MCLAG (2 pairs of 2 rails each)
        for rail in range(4):
            PlanServerConnection.objects.create(
                server_class=server_class,
                connection_id=f'BE-RAIL-{rail}',
                ports_per_connection=1,
                hedgehog_conn_type='unbundled',
                distribution='rail-optimized',
                target_switch_class=be_rail_leaf,
                speed=400,
                rail=rail
            )

        # Calculate switch quantity
        result = calculate_switch_quantity(be_rail_leaf)

        # 4 rails × 1 switch per rail = 4 (even)
        # With MCLAG: 4 is already even, no adjustment needed
        self.assertEqual(result, 4)

    def test_zero_spines_returns_none_breakout(self):
        """Test that breakout returns None when no spines needed"""
        # Create leaf
        leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False
        )

        # Call with zero spines
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=leaf,
            spines_needed=0,
            min_link_speed=800
        )

        # Should return None (no uplink interfaces needed)
        self.assertIsNone(breakout)

    def test_missing_1x_breakout_returns_none_when_policy_set(self):
        """Test that missing 1x returns None when supported_breakouts explicitly excludes it"""
        # Create a different device type to avoid integrity constraint
        switch_type_no_1x, _ = DeviceType.objects.get_or_create(
            manufacturer=self.manufacturer,
            model='DS5000-NO1X',
            defaults={'slug': 'ds5000-no1x', 'u_height': 1, 'is_full_depth': True}
        )

        # Create device extension without 1x in supported list
        # This is an explicit policy: only 2x/4x/8x allowed
        switch_ext_no_1x, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=switch_type_no_1x,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'supported_breakouts': ['2x400g', '4x200g', '8x100g'],  # No 1x - intentional!
                'native_speed': 800,
                'uplink_ports': 32
            }
        )

        leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf-no1x',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=switch_ext_no_1x,
            uplink_ports_per_switch=32,
            mclag_pair=False
        )

        # Call with 16 spines (less than 32 physical ports)
        # Would need 1x breakout, but supported_breakouts explicitly excludes it
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=leaf,
            spines_needed=16,
            min_link_speed=800
        )

        # Should return None (policy violation - 1x not in allowed list)
        self.assertIsNone(breakout)

    def test_synthetic_1x_only_when_no_policy(self):
        """Test that synthetic 1x is created only when supported_breakouts is empty"""
        # Create device type with NO supported_breakouts policy
        switch_type_empty, _ = DeviceType.objects.get_or_create(
            manufacturer=self.manufacturer,
            model='DS5000-EMPTY',
            defaults={'slug': 'ds5000-empty', 'u_height': 1, 'is_full_depth': True}
        )

        switch_ext_empty, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=switch_type_empty,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'supported_breakouts': [],  # Empty = no policy
                'native_speed': 800,
                'uplink_ports': 32
            }
        )

        leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf-empty',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=switch_ext_empty,
            uplink_ports_per_switch=32,
            mclag_pair=False
        )

        # Call with 16 spines (no breakout needed)
        breakout = determine_leaf_uplink_breakout(
            leaf_switch_class=leaf,
            spines_needed=16,
            min_link_speed=800
        )

        # Should create synthetic 1x800g (no policy to violate)
        self.assertIsNotNone(breakout)
        self.assertEqual(breakout.logical_ports, 1)
        self.assertEqual(breakout.logical_speed, 800)

class UpdatePlanCalculationsErrorHandlingTestCase(TestCase):
    """Test error handling in update_plan_calculations()"""

    def setUp(self):
        """Set up test data"""
        self.plan = TopologyPlan.objects.create(
            name="Error Handling Test Plan",
            status='draft'
        )

        manufacturer = Manufacturer.objects.create(
            name="Test Manufacturer Error",
            slug="test-manufacturer-error"
        )
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer,
            model="TestSwitch-Error",
            slug="testswitch-error"
        )

        self.switch_extension = DeviceTypeExtension.objects.create(
            device_type=device_type,
            mclag_capable=True,
            hedgehog_roles=['server-leaf', 'spine'],
            supported_breakouts=['1x800g', '2x400g', '4x200g'],
            native_speed=800,
            uplink_ports=32
        )

        self.server_device_type = DeviceType.objects.create(
            manufacturer=manufacturer,
            model="TestServer-Error",
            slug="testserver-error"
        )

        # Get or create breakout options
        self.breakout_1x800, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x800g',
            defaults={
                'from_speed': 800,
                'logical_ports': 1,
                'logical_speed': 800,
                'optic_type': 'QSFP-DD'
            }
        )
        self.breakout_2x400, _ = BreakoutOption.objects.get_or_create(
            breakout_id='2x400g',
            defaults={
                'from_speed': 800,
                'logical_ports': 2,
                'logical_speed': 400,
                'optic_type': 'QSFP-DD'
            }
        )
        self.breakout_4x200, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={
                'from_speed': 800,
                'logical_ports': 4,
                'logical_speed': 200,
                'optic_type': 'QSFP-DD'
            }
        )

    def test_validation_error_caught_and_returned(self):
        """Test that ValidationError from calculations is caught and included in errors list"""
        # Create a rail-optimized backend leaf with MCLAG and odd number of rails
        # This should trigger ValidationError
        be_rail_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='be-rail-leaf-bad',
            fabric='backend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=True  # MCLAG with odd rails = error
        )

        # Create server class with 3 rail connections (odd number)
        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='gpu-server',
            description='GPU server with 3 rails',
            category='gpu',
            quantity=32,
            gpus_per_server=8,
            server_device_type=self.server_device_type
        )

        # Create 3 rail connections (odd number + MCLAG = incompatible)
        for rail in range(3):
            PlanServerConnection.objects.create(
                server_class=server_class,
                connection_id=f'be-rail-{rail}',
                connection_name=f'backend-rail-{rail}',
                ports_per_connection=1,
                hedgehog_conn_type='unbundled',
                distribution='rail-optimized',
                target_switch_class=be_rail_leaf,
                speed=400,
                rail=rail,
                port_type='data'
            )

        # Run update_plan_calculations - should catch ValidationError
        result = update_plan_calculations(self.plan)

        # Check return structure
        self.assertIn('summary', result)
        self.assertIn('errors', result)
        self.assertIsInstance(result['summary'], dict)
        self.assertIsInstance(result['errors'], list)

        # Should have one error for the incompatible switch class
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(result['errors'][0]['switch_class'], 'be-rail-leaf-bad')
        self.assertIn('rail', result['errors'][0]['error'].lower())
        self.assertIn('mclag', result['errors'][0]['error'].lower())

    def test_successful_calculations_still_appear_in_summary(self):
        """Test that successful calculations appear in summary even when some fail"""
        # Create a valid leaf switch
        fe_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf-good',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=True
        )

        # Create server class
        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='regular-server',
            description='Regular server',
            category='storage',
            quantity=96,
            gpus_per_server=0,
            server_device_type=self.server_device_type
        )

        # Create connection (2 ports = even, compatible with MCLAG)
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            connection_name='frontend',
            ports_per_connection=2,
            hedgehog_conn_type='unbundled',
            distribution='alternating',
            target_switch_class=fe_leaf,
            speed=200,
            port_type='data'
        )

        # Create an invalid rail switch (will fail)
        be_rail_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='be-rail-leaf-bad',
            fabric='backend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=True  # MCLAG with odd rails = error
        )

        gpu_server = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='gpu-server',
            description='GPU server',
            category='gpu',
            quantity=32,
            gpus_per_server=8,
            server_device_type=self.server_device_type
        )

        # Create 3 rail connections (odd number + MCLAG = error)
        for rail in range(3):
            PlanServerConnection.objects.create(
                server_class=gpu_server,
                connection_id=f'be-rail-{rail}',
                connection_name=f'backend-rail-{rail}',
                ports_per_connection=1,
                hedgehog_conn_type='unbundled',
                distribution='rail-optimized',
                target_switch_class=be_rail_leaf,
                speed=400,
                rail=rail,
                port_type='data'
            )

        # Run calculations
        result = update_plan_calculations(self.plan)

        # Should have successful calculation for fe-leaf-good
        self.assertIn('fe-leaf-good', result['summary'])
        self.assertIn('calculated', result['summary']['fe-leaf-good'])
        self.assertIsInstance(result['summary']['fe-leaf-good']['calculated'], int)

        # Should have error for be-rail-leaf-bad
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(result['errors'][0]['switch_class'], 'be-rail-leaf-bad')

    def test_empty_errors_when_all_succeed(self):
        """Test that errors list is empty when all calculations succeed"""
        # Create a valid leaf switch
        fe_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False
        )

        # Create server class
        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='regular-server',
            description='Regular server',
            category='storage',
            quantity=96,
            gpus_per_server=0,
            server_device_type=self.server_device_type
        )

        # Create connection
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            connection_name='frontend',
            ports_per_connection=2,
            hedgehog_conn_type='unbundled',
            distribution='alternating',
            target_switch_class=fe_leaf,
            speed=200,
            port_type='data'
        )

        # Run calculations
        result = update_plan_calculations(self.plan)

        # Should have empty errors list
        self.assertEqual(len(result['errors']), 0)
        self.assertEqual(result['errors'], [])

        # Should have successful calculation in summary
        self.assertIn('fe-leaf', result['summary'])
        self.assertGreater(result['summary']['fe-leaf']['calculated'], 0)

    def test_spine_calculation_error_handling(self):
        """Test that spine calculation errors are also caught"""
        # Create a spine switch
        fe_spine = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0
        )

        # Create a leaf that would require breakout not in supported list
        # This will create a scenario where spine calculation might fail
        fe_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False,
            calculated_quantity=100  # Many leaves to force high spine count
        )

        # Run calculations
        result = update_plan_calculations(self.plan)

        # Should handle any errors gracefully
        self.assertIn('summary', result)
        self.assertIn('errors', result)
        self.assertIsInstance(result['errors'], list)

    def test_spine_calculations_skipped_when_leaf_errors(self):
        """Test that spine calculations are skipped when leaf calculations fail"""
        # Create a spine switch
        fe_spine = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0
        )

        # Create an invalid rail-optimized leaf (will fail)
        be_rail_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='be-rail-leaf-bad',
            fabric='backend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=True  # MCLAG with odd rails = error
        )

        gpu_server = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='gpu-server',
            description='GPU server',
            category='gpu',
            quantity=32,
            gpus_per_server=8,
            server_device_type=self.server_device_type
        )

        # Create 3 rail connections (odd number + MCLAG = error)
        for rail in range(3):
            PlanServerConnection.objects.create(
                server_class=gpu_server,
                connection_id=f'be-rail-{rail}',
                connection_name=f'backend-rail-{rail}',
                ports_per_connection=1,
                hedgehog_conn_type='unbundled',
                distribution='rail-optimized',
                target_switch_class=be_rail_leaf,
                speed=400,
                rail=rail,
                port_type='data'
            )

        # Run calculations
        result = update_plan_calculations(self.plan)

        # Should have error for leaf
        leaf_errors = [e for e in result['errors'] if e['switch_class'] == 'be-rail-leaf-bad']
        self.assertEqual(len(leaf_errors), 1)

        # Should have skipped spine with explanatory message
        spine_errors = [e for e in result['errors'] if e['switch_class'] == 'fe-spine']
        self.assertEqual(len(spine_errors), 1)
        self.assertIn('skipped', spine_errors[0]['error'].lower())
        self.assertIn('leaf', spine_errors[0]['error'].lower())

        # Spine should NOT be in summary (calculation was skipped)
        self.assertNotIn('fe-spine', result['summary'])

    def test_spine_calculations_proceed_when_no_leaf_errors(self):
        """Test that spine calculations proceed normally when all leaf calculations succeed"""
        # Create valid leaf switch
        fe_leaf = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=32,
            mclag_pair=False,
            calculated_quantity=2
        )

        # Create spine switch
        fe_spine = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=self.switch_extension,
            uplink_ports_per_switch=0
        )

        # Create server class
        server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='regular-server',
            description='Regular server',
            category='storage',
            quantity=96,
            gpus_per_server=0,
            server_device_type=self.server_device_type
        )

        # Create connection
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            connection_name='frontend',
            ports_per_connection=2,
            hedgehog_conn_type='unbundled',
            distribution='alternating',
            target_switch_class=fe_leaf,
            speed=200,
            port_type='data'
        )

        # Run calculations
        result = update_plan_calculations(self.plan)

        # Should have empty errors list
        self.assertEqual(len(result['errors']), 0)

        # Both leaf and spine should be in summary
        self.assertIn('fe-leaf', result['summary'])
        self.assertIn('fe-spine', result['summary'])

        # Spine should have a calculated value
        self.assertIsInstance(result['summary']['fe-spine']['calculated'], int)
