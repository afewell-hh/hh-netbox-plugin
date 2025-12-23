"""
Tests for GenerationState model.

Test categories:
- Basic CRUD operations
- Snapshot content
- is_dirty() method behavior
- Status field validation
- Model constraints (OneToOne relationship)
- TopologyPlan properties integration

Following TDD approach: Tests written BEFORE implementation.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    GenerationState,
    DeviceTypeExtension,
)
from dcim.models import DeviceType, Manufacturer


class GenerationStateModelTestCase(TestCase):
    """Test suite for GenerationState model"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all test methods"""
        # Create manufacturer and device types
        cls.manufacturer = Manufacturer.objects.create(
            name="Test Manufacturer",
            slug="test-manufacturer"
        )

        cls.device_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model="Test Switch",
            slug="test-switch"
        )

        cls.device_type_ext = DeviceTypeExtension.objects.create(
            device_type=cls.device_type,
            native_speed=800,
            uplink_ports=16
        )

        # Create test plan
        cls.test_plan = TopologyPlan.objects.create(
            name="Test Plan"
        )

    # =========================================================================
    # 1. Basic CRUD Operations
    # =========================================================================

    def test_create_generation_state(self):
        """Test creating GenerationState"""
        plan = TopologyPlan.objects.create(name="New Plan")

        state = GenerationState.objects.create(
            plan=plan,
            device_count=100,
            interface_count=500,
            cable_count=400,
            snapshot={'test': 'data'},
            status='generated'
        )

        self.assertEqual(state.plan, plan)
        self.assertEqual(state.device_count, 100)
        self.assertEqual(state.interface_count, 500)
        self.assertEqual(state.cable_count, 400)
        self.assertEqual(state.snapshot, {'test': 'data'})
        self.assertEqual(state.status, 'generated')
        self.assertIsNotNone(state.generated_at)

    def test_str_representation(self):
        """Test __str__ returns readable format"""
        plan = TopologyPlan.objects.create(name="My Plan")

        state = GenerationState.objects.create(
            plan=plan,
            device_count=50,
            interface_count=200,
            cable_count=150,
            snapshot={},
            status='generated'
        )

        str_repr = str(state)
        self.assertIn("My Plan", str_repr)
        self.assertIn("50", str_repr)

    # =========================================================================
    # 2. Snapshot Content
    # =========================================================================

    def test_snapshot_contains_server_class_quantities(self):
        """Test snapshot captures server class quantities"""
        plan = TopologyPlan.objects.create(name="Plan")

        # Create server classes
        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        # Create snapshot
        snapshot = {
            'server_classes': [
                {
                    'server_class_id': 'gpu-b200',
                    'quantity': 96
                }
            ],
            'switch_classes': []
        }

        state = GenerationState.objects.create(
            plan=plan,
            device_count=96,
            interface_count=192,
            cable_count=192,
            snapshot=snapshot,
            status='generated'
        )

        self.assertIn('server_classes', state.snapshot)
        self.assertEqual(len(state.snapshot['server_classes']), 1)
        self.assertEqual(state.snapshot['server_classes'][0]['server_class_id'], 'gpu-b200')
        self.assertEqual(state.snapshot['server_classes'][0]['quantity'], 96)

    def test_snapshot_contains_switch_class_quantities(self):
        """Test snapshot captures switch class effective quantities"""
        plan = TopologyPlan.objects.create(name="Plan")

        # Create switch class
        PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="fe-leaf",
            device_type_extension=self.device_type_ext,
            uplink_ports_per_switch=16
        )

        # Create snapshot
        snapshot = {
            'server_classes': [],
            'switch_classes': [
                {
                    'switch_class_id': 'fe-leaf',
                    'effective_quantity': 12
                }
            ]
        }

        state = GenerationState.objects.create(
            plan=plan,
            device_count=12,
            interface_count=768,
            cable_count=192,
            snapshot=snapshot,
            status='generated'
        )

        self.assertIn('switch_classes', state.snapshot)
        self.assertEqual(len(state.snapshot['switch_classes']), 1)
        self.assertEqual(state.snapshot['switch_classes'][0]['switch_class_id'], 'fe-leaf')
        self.assertEqual(state.snapshot['switch_classes'][0]['effective_quantity'], 12)

    # =========================================================================
    # 3. is_dirty() Method
    # =========================================================================

    def test_is_dirty_returns_false_when_unchanged(self):
        """Test is_dirty() returns False when plan hasn't changed"""
        plan = TopologyPlan.objects.create(name="Plan")

        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        server = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        # Create snapshot matching current state
        snapshot = {
            'server_classes': [
                {
                    'server_class_id': 'gpu-b200',
                    'quantity': 96
                }
            ],
            'switch_classes': []
        }

        state = GenerationState.objects.create(
            plan=plan,
            device_count=96,
            interface_count=192,
            cable_count=192,
            snapshot=snapshot,
            status='generated'
        )

        self.assertFalse(state.is_dirty())

    def test_is_dirty_returns_true_when_server_quantity_changed(self):
        """Test is_dirty() detects server quantity changes"""
        plan = TopologyPlan.objects.create(name="Plan")

        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        server = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        # Create snapshot with old quantity
        snapshot = {
            'server_classes': [
                {
                    'server_class_id': 'gpu-b200',
                    'quantity': 96
                }
            ],
            'switch_classes': []
        }

        state = GenerationState.objects.create(
            plan=plan,
            device_count=96,
            interface_count=192,
            cable_count=192,
            snapshot=snapshot,
            status='generated'
        )

        # Change server quantity
        server.quantity = 128
        server.save()

        self.assertTrue(state.is_dirty())

    def test_is_dirty_returns_true_when_server_class_added(self):
        """Test is_dirty() detects new server classes"""
        plan = TopologyPlan.objects.create(name="Plan")

        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        # Create initial server
        PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        # Create snapshot with one server class
        snapshot = {
            'server_classes': [
                {
                    'server_class_id': 'gpu-b200',
                    'quantity': 96
                }
            ],
            'switch_classes': []
        }

        state = GenerationState.objects.create(
            plan=plan,
            device_count=96,
            interface_count=192,
            cable_count=192,
            snapshot=snapshot,
            status='generated'
        )

        # Add new server class
        PlanServerClass.objects.create(
            plan=plan,
            server_class_id="storage-a",
            quantity=32,
            server_device_type=server_dt
        )

        self.assertTrue(state.is_dirty())

    def test_is_dirty_returns_true_when_server_class_removed(self):
        """Test is_dirty() detects removed server classes"""
        plan = TopologyPlan.objects.create(name="Plan")

        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        # Create two server classes
        server1 = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        server2 = PlanServerClass.objects.create(
            plan=plan,
            server_class_id="storage-a",
            quantity=32,
            server_device_type=server_dt
        )

        # Create snapshot with both
        snapshot = {
            'server_classes': [
                {'server_class_id': 'gpu-b200', 'quantity': 96},
                {'server_class_id': 'storage-a', 'quantity': 32}
            ],
            'switch_classes': []
        }

        state = GenerationState.objects.create(
            plan=plan,
            device_count=128,
            interface_count=256,
            cable_count=256,
            snapshot=snapshot,
            status='generated'
        )

        # Remove one server class
        server2.delete()

        self.assertTrue(state.is_dirty())

    def test_is_dirty_returns_true_when_switch_quantity_changed(self):
        """Test is_dirty() detects switch quantity changes"""
        plan = TopologyPlan.objects.create(name="Plan")

        # Create switch class
        switch = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id="fe-leaf",
            device_type_extension=self.device_type_ext,
            uplink_ports_per_switch=16,
            override_quantity=12
        )

        # Create snapshot
        snapshot = {
            'server_classes': [],
            'switch_classes': [
                {
                    'switch_class_id': 'fe-leaf',
                    'effective_quantity': 12
                }
            ]
        }

        state = GenerationState.objects.create(
            plan=plan,
            device_count=12,
            interface_count=768,
            cable_count=0,
            snapshot=snapshot,
            status='generated'
        )

        # Change switch quantity
        switch.override_quantity = 16
        switch.save()

        self.assertTrue(state.is_dirty())

    # =========================================================================
    # 4. Status Field Validation
    # =========================================================================

    def test_status_choices(self):
        """Test status accepts valid choices"""
        plan = TopologyPlan.objects.create(name="Plan")

        valid_statuses = ['generated', 'dirty']

        for status in valid_statuses:
            state = GenerationState.objects.create(
                plan=plan,
                device_count=0,
                interface_count=0,
                cable_count=0,
                snapshot={},
                status=status
            )
            self.assertEqual(state.status, status)
            state.delete()

    def test_status_invalid_choice(self):
        """Test status rejects invalid choice"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status='invalid'
        )

        with self.assertRaises(ValidationError):
            state.full_clean()

    # =========================================================================
    # 5. Model Constraints
    # =========================================================================

    def test_one_to_one_relationship_with_plan(self):
        """Test GenerationState has OneToOne relationship with TopologyPlan"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status='generated'
        )

        # Attempt to create duplicate state for same plan
        with self.assertRaises(IntegrityError):
            GenerationState.objects.create(
                plan=plan,
                device_count=0,
                interface_count=0,
                cable_count=0,
                snapshot={},
                status='generated'
            )

    def test_cascade_delete_when_plan_deleted(self):
        """Test generation state is deleted when plan is deleted"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status='generated'
        )

        state_id = state.pk
        self.assertEqual(GenerationState.objects.filter(pk=state_id).count(), 1)

        plan.delete()

        self.assertEqual(GenerationState.objects.filter(pk=state_id).count(), 0)

    # =========================================================================
    # 6. Count Validations
    # =========================================================================

    def test_device_count_non_negative(self):
        """Test device_count must be non-negative"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState(
            plan=plan,
            device_count=-1,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status='generated'
        )

        with self.assertRaises(ValidationError):
            state.full_clean()

    def test_interface_count_non_negative(self):
        """Test interface_count must be non-negative"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState(
            plan=plan,
            device_count=0,
            interface_count=-1,
            cable_count=0,
            snapshot={},
            status='generated'
        )

        with self.assertRaises(ValidationError):
            state.full_clean()

    def test_cable_count_non_negative(self):
        """Test cable_count must be non-negative"""
        plan = TopologyPlan.objects.create(name="Plan")

        state = GenerationState(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=-1,
            snapshot={},
            status='generated'
        )

        with self.assertRaises(ValidationError):
            state.full_clean()


class TopologyPlanPropertiesTestCase(TestCase):
    """Test suite for TopologyPlan properties that interact with GenerationState"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all test methods"""
        cls.manufacturer = Manufacturer.objects.create(
            name="Test Manufacturer",
            slug="test-manufacturer"
        )

    # =========================================================================
    # TopologyPlan Properties
    # =========================================================================

    def test_last_generated_at_returns_none_when_never_generated(self):
        """Test last_generated_at property returns None before generation"""
        plan = TopologyPlan.objects.create(name="Plan")

        self.assertIsNone(plan.last_generated_at)

    def test_last_generated_at_returns_timestamp_after_generation(self):
        """Test last_generated_at property returns correct timestamp"""
        plan = TopologyPlan.objects.create(name="Plan")

        before = timezone.now()
        state = GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status='generated'
        )
        after = timezone.now()

        # Refresh plan to get property
        plan.refresh_from_db()

        self.assertIsNotNone(plan.last_generated_at)
        self.assertGreaterEqual(plan.last_generated_at, before)
        self.assertLessEqual(plan.last_generated_at, after)

    def test_needs_regeneration_returns_false_when_never_generated(self):
        """Test needs_regeneration returns False before first generation"""
        plan = TopologyPlan.objects.create(name="Plan")

        self.assertFalse(plan.needs_regeneration)

    def test_needs_regeneration_returns_false_when_clean(self):
        """Test needs_regeneration returns False when not dirty"""
        plan = TopologyPlan.objects.create(name="Plan")

        GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={'server_classes': [], 'switch_classes': []},
            status='generated'
        )

        # Refresh plan to get property
        plan.refresh_from_db()

        self.assertFalse(plan.needs_regeneration)

    def test_needs_regeneration_returns_true_when_plan_changed(self):
        """Test needs_regeneration returns True when plan modified"""
        plan = TopologyPlan.objects.create(name="Plan")

        server_dt = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model="GPU Server",
            slug="gpu-server"
        )

        # Create initial state
        snapshot = {'server_classes': [], 'switch_classes': []}
        GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot=snapshot,
            status='generated'
        )

        # Add server class (modifies plan)
        PlanServerClass.objects.create(
            plan=plan,
            server_class_id="gpu-b200",
            quantity=96,
            server_device_type=server_dt
        )

        # Refresh plan to get property
        plan.refresh_from_db()

        self.assertTrue(plan.needs_regeneration)
