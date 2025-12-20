"""
Tests for Topology Planning Forms (DIET Module)

Following TDD approach: tests written BEFORE implementation.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model

from dcim.models import DeviceType, Manufacturer

from netbox_hedgehog.forms.topology_planning import (
    TopologyPlanForm,
    PlanServerClassForm,
    PlanSwitchClassForm,
)
from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    DeviceTypeExtension,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    ServerClassCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
)

User = get_user_model()


class TopologyPlanFormTestCase(TestCase):
    """Test suite for TopologyPlanForm"""

    @classmethod
    def setUpTestData(cls):
        """Create test user for plan creation"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_create_minimal_plan(self):
        """Test creating a plan with minimal required fields"""
        form_data = {
            'name': 'Test Plan',
            'status': TopologyPlanStatusChoices.DRAFT,
        }
        form = TopologyPlanForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        plan = form.save(commit=False)
        plan.created_by = self.user
        plan.save()

        self.assertEqual(plan.name, 'Test Plan')
        self.assertEqual(plan.status, TopologyPlanStatusChoices.DRAFT)

    def test_create_complete_plan(self):
        """Test creating a plan with all fields"""
        form_data = {
            'name': 'Cambium 2MW',
            'customer_name': 'Cambium Networks',
            'description': 'Complete 2MW datacenter deployment',
            'status': TopologyPlanStatusChoices.REVIEW,
            'notes': 'Important notes here',
        }
        form = TopologyPlanForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        plan = form.save()
        self.assertEqual(plan.name, 'Cambium 2MW')
        self.assertEqual(plan.customer_name, 'Cambium Networks')
        self.assertEqual(plan.status, TopologyPlanStatusChoices.REVIEW)

    def test_name_required(self):
        """Test that name field is required"""
        form_data = {
            'customer_name': 'Test Customer',
        }
        form = TopologyPlanForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_update_plan(self):
        """Test updating an existing plan"""
        plan = TopologyPlan.objects.create(
            name='Original Name',
            created_by=self.user
        )

        form_data = {
            'name': 'Updated Name',
            'status': TopologyPlanStatusChoices.APPROVED,
        }
        form = TopologyPlanForm(data=form_data, instance=plan)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        updated_plan = form.save()
        self.assertEqual(updated_plan.name, 'Updated Name')
        self.assertEqual(updated_plan.status, TopologyPlanStatusChoices.APPROVED)


class PlanServerClassFormTestCase(TestCase):
    """Test suite for PlanServerClassForm"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=cls.user
        )
        # Create a server device type
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Dell',
            defaults={'slug': 'dell'}
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='PowerEdge R750',
            defaults={'slug': 'poweredge-r750'}
        )

    def test_create_minimal_server_class(self):
        """Test creating server class with minimal fields"""
        form_data = {
            'plan': self.plan.pk,
            'server_class_id': 'GPU-001',
            'category': ServerClassCategoryChoices.GPU,
            'quantity': 10,
            'gpus_per_server': 0,
            'server_device_type': self.server_type.pk,
        }
        form = PlanServerClassForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        server_class = form.save()
        self.assertEqual(server_class.server_class_id, 'GPU-001')
        self.assertEqual(server_class.quantity, 10)
        self.assertEqual(server_class.category, ServerClassCategoryChoices.GPU)

    def test_create_complete_server_class(self):
        """Test creating server class with all fields"""
        form_data = {
            'plan': self.plan.pk,
            'server_class_id': 'INF-B200',
            'description': 'Inference Server with 8x B200 GPUs',
            'category': ServerClassCategoryChoices.GPU,
            'quantity': 96,
            'gpus_per_server': 8,
            'server_device_type': self.server_type.pk,
            'notes': 'Special configuration notes',
        }
        form = PlanServerClassForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        server_class = form.save()
        self.assertEqual(server_class.quantity, 96)
        self.assertEqual(server_class.gpus_per_server, 8)
        self.assertEqual(server_class.server_device_type, self.server_type)

    def test_quantity_required(self):
        """Test that quantity field is required"""
        form_data = {
            'plan': self.plan.pk,
            'server_class_id': 'TEST-001',
        }
        form = PlanServerClassForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('quantity', form.errors)

    def test_quantity_validation_positive(self):
        """Test that quantity must be positive"""
        form_data = {
            'plan': self.plan.pk,
            'server_class_id': 'TEST-001',
            'quantity': -5,
        }
        form = PlanServerClassForm(data=form_data)
        self.assertFalse(form.is_valid())
        # Django's MinValueValidator should catch this

    def test_server_class_id_required(self):
        """Test that server_class_id is required"""
        form_data = {
            'plan': self.plan.pk,
            'quantity': 10,
        }
        form = PlanServerClassForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('server_class_id', form.errors)


class PlanSwitchClassFormTestCase(TestCase):
    """Test suite for PlanSwitchClassForm"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=cls.user
        )
        # Create a switch device type with extension
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'ds5000'}
        )
        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_type,
            defaults={
                'mclag_capable': True,
                'hedgehog_roles': ['spine', 'server-leaf'],
                'native_speed': 800,
                'uplink_ports': 4,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g']
            }
        )

    def test_create_minimal_switch_class(self):
        """Test creating switch class with minimal fields"""
        form_data = {
            'plan': self.plan.pk,
            'switch_class_id': 'fe-leaf-01',
            'fabric': FabricTypeChoices.FRONTEND,
            'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 4,
        }
        form = PlanSwitchClassForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        switch_class = form.save()
        self.assertEqual(switch_class.switch_class_id, 'fe-leaf-01')
        self.assertEqual(switch_class.fabric, FabricTypeChoices.FRONTEND)
        self.assertEqual(switch_class.hedgehog_role, HedgehogRoleChoices.SERVER_LEAF)

    def test_create_complete_switch_class(self):
        """Test creating switch class with all fields"""
        form_data = {
            'plan': self.plan.pk,
            'switch_class_id': 'be-spine',
            'fabric': FabricTypeChoices.BACKEND,
            'hedgehog_role': HedgehogRoleChoices.SPINE,
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 8,
            'mclag_pair': True,
            'override_quantity': 4,
            'notes': 'Backend spine switches',
        }
        form = PlanSwitchClassForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        switch_class = form.save()
        self.assertEqual(switch_class.fabric, FabricTypeChoices.BACKEND)
        self.assertEqual(switch_class.hedgehog_role, HedgehogRoleChoices.SPINE)
        self.assertEqual(switch_class.override_quantity, 4)
        self.assertTrue(switch_class.mclag_pair)

    def test_switch_class_id_required(self):
        """Test that switch_class_id is required"""
        form_data = {
            'plan': self.plan.pk,
            'device_type_extension': self.device_ext.pk,
        }
        form = PlanSwitchClassForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('switch_class_id', form.errors)

    def test_override_quantity_optional(self):
        """Test that override_quantity is optional (can be null)"""
        form_data = {
            'plan': self.plan.pk,
            'switch_class_id': 'test-switch',
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 0,
            'override_quantity': '',  # Empty string should be treated as None
        }
        form = PlanSwitchClassForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        switch_class = form.save()
        self.assertIsNone(switch_class.override_quantity)

    def test_calculated_quantity_defaults_to_none(self):
        """Test that calculated_quantity defaults to None (not yet calculated)"""
        form_data = {
            'plan': self.plan.pk,
            'switch_class_id': 'test-switch',
            'fabric': FabricTypeChoices.FRONTEND,
            'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 0,
        }
        form = PlanSwitchClassForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        switch_class = form.save()
        # calculated_quantity is None until calculation engine runs
        self.assertIsNone(switch_class.calculated_quantity)
