"""
Form Validation Tests for Topology Planning UI (DIET-100)

These tests verify form validation behavior at the HTTP request/response level,
ensuring that validation errors are properly displayed to users in the UI.

Following AGENTS.md testing standards:
- Test actual HTTP POST requests, not just form.is_valid()
- Verify error messages appear in rendered HTML
- Verify form re-renders with errors (doesn't redirect)
- Test both valid and invalid submissions
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from dcim.models import DeviceType, Manufacturer, ModuleType

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    DeviceTypeExtension,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    ServerClassCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
)

User = get_user_model()


class TopologyPlanFormValidationTestCase(TestCase):
    """
    Test suite for TopologyPlan form validation via HTTP POST.

    Tests validation rules, error messages, and form rendering behavior.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test user with superuser permissions"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_plan_creation_valid_data(self):
        """Test that valid plan data creates object and redirects"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        data = {
            'name': 'Valid Plan',
            'customer_name': 'Test Customer',
            'status': TopologyPlanStatusChoices.DRAFT,
            'description': 'Test description',
        }

        response = self.client.post(url, data, follow=False)

        # Should redirect on success (302)
        self.assertEqual(response.status_code, 302,
                        f"Expected redirect (302) on valid submission, got {response.status_code}")

        # Verify object was created
        plan = TopologyPlan.objects.filter(name='Valid Plan').first()
        self.assertIsNotNone(plan, "Plan should have been created in database")
        self.assertEqual(plan.customer_name, 'Test Customer')

    def test_plan_name_required(self):
        """Test that name field is required - form should re-render with error"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        data = {
            # name is missing
            'customer_name': 'Test Customer',
            'status': TopologyPlanStatusChoices.DRAFT,
        }

        response = self.client.post(url, data, follow=False)

        # Should NOT redirect (200 = form re-rendered with errors)
        self.assertEqual(response.status_code, 200,
                        "Form should re-render (200) on validation error, not redirect")

        # Verify error message appears in HTML - contains 'name' field reference
        self.assertContains(response, 'name', status_code=200)
        # Verify error indicates field is required
        self.assertContains(response, 'required', status_code=200)

        # Verify no object was created
        plan = TopologyPlan.objects.filter(customer_name='Test Customer').first()
        self.assertIsNone(plan, "No plan should be created when validation fails")

    def test_plan_edit_validation(self):
        """Test editing a plan with invalid data shows errors"""
        # Create existing plan
        plan = TopologyPlan.objects.create(
            name='Original Plan',
            created_by=self.user
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_edit', args=[plan.pk])
        data = {
            # Empty name should fail validation
            'name': '',
            'status': TopologyPlanStatusChoices.REVIEW,
        }

        response = self.client.post(url, data, follow=False)

        # Should re-render form with error
        self.assertEqual(response.status_code, 200,
                        "Form should re-render on validation error")

        # Original data should be unchanged
        plan.refresh_from_db()
        self.assertEqual(plan.name, 'Original Plan',
                        "Plan name should not change when validation fails")


class PlanServerClassFormValidationTestCase(TestCase):
    """
    Test suite for PlanServerClass form validation via HTTP POST.

    Tests quantity validation, FK validation, and error rendering.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test fixtures"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        # Create parent plan
        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=cls.user
        )

        # Create manufacturer and device type
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Dell',
            defaults={'slug': 'dell'}
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='PowerEdge R750',
            defaults={'slug': 'poweredge-r750'}
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_server_class_creation_valid_data(self):
        """Test creating server class with valid data"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        data = {
            'plan': self.plan.pk,
            'server_class_id': 'GPU-001',
            'category': ServerClassCategoryChoices.GPU,
            'quantity': 10,
            'gpus_per_server': 8,
            'server_device_type': self.server_type.pk,
        }

        response = self.client.post(url, data, follow=False)

        # Should redirect on success
        self.assertEqual(response.status_code, 302,
                        f"Expected redirect on valid submission, got {response.status_code}")

        # Verify object created
        server_class = PlanServerClass.objects.filter(server_class_id='GPU-001').first()
        self.assertIsNotNone(server_class)
        self.assertEqual(server_class.quantity, 10)

    def test_server_class_quantity_required(self):
        """Test that quantity field is required"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        data = {
            'plan': self.plan.pk,
            'server_class_id': 'TEST-001',
            'server_device_type': self.server_type.pk,
            # quantity is missing
        }

        response = self.client.post(url, data, follow=False)

        # Should re-render form with error
        self.assertEqual(response.status_code, 200,
                        "Form should re-render on missing required field")

        # Verify error message mentions 'quantity' field
        self.assertContains(response, 'quantity', status_code=200)
        # Verify error indicates field is required
        self.assertContains(response, 'required', status_code=200)

    def test_server_class_quantity_positive(self):
        """Test that quantity must be positive (>= 1)"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')

        # Test with zero
        data_zero = {
            'plan': self.plan.pk,
            'server_class_id': 'TEST-ZERO',
            'quantity': 0,
            'server_device_type': self.server_type.pk,
        }

        response_zero = self.client.post(url, data_zero, follow=False)
        self.assertEqual(response_zero.status_code, 200,
                        "Form should reject quantity=0")

        # Test with negative
        data_negative = {
            'plan': self.plan.pk,
            'server_class_id': 'TEST-NEG',
            'quantity': -5,
            'server_device_type': self.server_type.pk,
        }

        response_negative = self.client.post(url, data_negative, follow=False)
        self.assertEqual(response_negative.status_code, 200,
                        "Form should reject negative quantity")

        # Verify error mentions quantity field
        self.assertContains(response_negative, 'quantity', status_code=200)

    def test_server_class_invalid_fk(self):
        """Test that invalid foreign key (plan or device_type) fails validation"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')

        # Test with non-existent plan ID
        data_bad_plan = {
            'plan': 99999,  # Non-existent plan
            'server_class_id': 'TEST-001',
            'quantity': 10,
            'server_device_type': self.server_type.pk,
        }

        response = self.client.post(url, data_bad_plan, follow=False)
        self.assertEqual(response.status_code, 200,
                        "Form should reject invalid FK reference")

    def test_server_class_server_class_id_required(self):
        """Test that server_class_id is required"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        data = {
            'plan': self.plan.pk,
            # server_class_id is missing
            'quantity': 10,
            'server_device_type': self.server_type.pk,
        }

        response = self.client.post(url, data, follow=False)

        # Should re-render with error
        self.assertEqual(response.status_code, 200,
                        "Form should re-render on missing server_class_id")

        # Verify error mentions server_class_id field
        self.assertContains(response, 'server_class_id', status_code=200)


class PlanSwitchClassFormValidationTestCase(TestCase):
    """
    Test suite for PlanSwitchClass form validation via HTTP POST.

    Tests FK validation, uplink_ports validation, and MCLAG toggle behavior.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test fixtures"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=cls.user
        )

        # Create switch device type with extension
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

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_switch_class_creation_valid_data(self):
        """Test creating switch class with valid data"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'fe-leaf-01',
            'fabric': FabricTypeChoices.FRONTEND,
            'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 4,
            'mclag_pair': True,
        }

        response = self.client.post(url, data, follow=False)

        # Should redirect on success
        self.assertEqual(response.status_code, 302,
                        f"Expected redirect on valid submission, got {response.status_code}")

        # Verify object created
        switch_class = PlanSwitchClass.objects.filter(switch_class_id='fe-leaf-01').first()
        self.assertIsNotNone(switch_class)
        self.assertTrue(switch_class.mclag_pair)

    def test_switch_class_switch_class_id_required(self):
        """Test that switch_class_id is required"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        data = {
            'plan': self.plan.pk,
            # switch_class_id is missing
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 0,
        }

        response = self.client.post(url, data, follow=False)

        # Should re-render with error
        self.assertEqual(response.status_code, 200,
                        "Form should re-render on missing switch_class_id")

        # Verify error mentions switch_class_id field
        self.assertContains(response, 'switch_class_id', status_code=200)

    def test_switch_class_uplink_ports_non_negative(self):
        """Test that uplink_ports_per_switch must be non-negative"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'test-switch',
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': -5,  # Negative should fail
        }

        response = self.client.post(url, data, follow=False)

        # Should re-render with error
        self.assertEqual(response.status_code, 200,
                        "Form should reject negative uplink_ports")

        # Verify error mentions uplink_ports field
        self.assertContains(response, 'uplink_ports_per_switch', status_code=200)

    def test_switch_class_invalid_device_type_extension_fk(self):
        """Test that invalid device_type_extension FK fails validation"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'test-switch',
            'device_type_extension': 99999,  # Non-existent FK
            'uplink_ports_per_switch': 0,
        }

        response = self.client.post(url, data, follow=False)

        # Should re-render with error
        self.assertEqual(response.status_code, 200,
                        "Form should reject invalid FK reference")

    def test_switch_class_mclag_toggle(self):
        """Test that mclag_pair boolean field works correctly"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')

        # Test with mclag_pair=True
        data_true = {
            'plan': self.plan.pk,
            'switch_class_id': 'mclag-test',
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 0,
            'mclag_pair': True,
        }

        response_true = self.client.post(url, data_true, follow=False)
        self.assertEqual(response_true.status_code, 302, "Valid MCLAG=True should succeed")

        switch_true = PlanSwitchClass.objects.get(switch_class_id='mclag-test')
        self.assertTrue(switch_true.mclag_pair)

        # Test with mclag_pair=False (default)
        data_false = {
            'plan': self.plan.pk,
            'switch_class_id': 'no-mclag-test',
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 0,
            'mclag_pair': False,
        }

        response_false = self.client.post(url, data_false, follow=False)
        self.assertEqual(response_false.status_code, 302, "Valid MCLAG=False should succeed")

        switch_false = PlanSwitchClass.objects.get(switch_class_id='no-mclag-test')
        self.assertFalse(switch_false.mclag_pair)

    def test_switch_class_override_quantity_optional(self):
        """Test that override_quantity is optional (can be null/empty)"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'override-test',
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 0,
            'override_quantity': '',  # Empty should be treated as None
        }

        response = self.client.post(url, data, follow=False)

        # Should succeed
        self.assertEqual(response.status_code, 302,
                        "Empty override_quantity should be accepted (treated as None)")

        switch = PlanSwitchClass.objects.get(switch_class_id='override-test')
        self.assertIsNone(switch.override_quantity)


class PlanServerConnectionFormValidationTestCase(TestCase):
    """
    Test suite for PlanServerConnection form validation via HTTP POST.

    Tests ports_per_connection validation, speed validation, and rail validation.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test fixtures"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=cls.user
        )

        # Create server device type
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Dell',
            defaults={'slug': 'dell'}
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='PowerEdge R750',
            defaults={'slug': 'poweredge-r750'}
        )

        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='GPU-001',
            server_device_type=cls.server_type,
            quantity=10
        )

        # Create switch device type with extension
        cls.switch_manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.switch_manufacturer,
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

        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=4
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_connection_creation_valid_data(self):
        """Test creating connection with valid data"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-001',
            'connection_name': 'frontend',
            'ports_per_connection': 2,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
        }

        response = self.client.post(url, data, follow=False)

        # Should redirect on success
        self.assertEqual(response.status_code, 302,
                        f"Expected redirect on valid submission, got {response.status_code}")

        # Verify object created
        connection = PlanServerConnection.objects.filter(connection_id='fe-001').first()
        self.assertIsNotNone(connection)
        self.assertEqual(connection.ports_per_connection, 2)
        self.assertEqual(connection.speed, 200)

    def test_connection_ports_per_connection_positive(self):
        """Test that ports_per_connection must be positive (>= 1)"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')

        # Test with zero
        data_zero = {
            'server_class': self.server_class.pk,
            'connection_id': 'test-zero',
            'ports_per_connection': 0,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
        }

        response_zero = self.client.post(url, data_zero, follow=False)
        self.assertEqual(response_zero.status_code, 200,
                        "Form should reject ports_per_connection=0")

        # Test with negative
        data_negative = {
            'server_class': self.server_class.pk,
            'connection_id': 'test-neg',
            'ports_per_connection': -2,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
        }

        response_negative = self.client.post(url, data_negative, follow=False)
        self.assertEqual(response_negative.status_code, 200,
                        "Form should reject negative ports_per_connection")

    def test_connection_speed_positive(self):
        """Test that speed must be positive (>= 1)"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')

        # Test with zero
        data_zero = {
            'server_class': self.server_class.pk,
            'connection_id': 'test-speed-zero',
            'ports_per_connection': 1,
            'target_switch_class': self.switch_class.pk,
            'speed': 0,
        }

        response_zero = self.client.post(url, data_zero, follow=False)
        self.assertEqual(response_zero.status_code, 200,
                        "Form should reject speed=0")

        # Test with negative
        data_negative = {
            'server_class': self.server_class.pk,
            'connection_id': 'test-speed-neg',
            'ports_per_connection': 1,
            'target_switch_class': self.switch_class.pk,
            'speed': -100,
        }

        response_negative = self.client.post(url, data_negative, follow=False)
        self.assertEqual(response_negative.status_code, 200,
                        "Form should reject negative speed")

    def test_connection_rail_required_for_rail_optimized(self):
        """Test that rail field is required when distribution is rail-optimized"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')

        # Rail-optimized WITHOUT rail should fail
        data_no_rail = {
            'server_class': self.server_class.pk,
            'connection_id': 'rail-test-fail',
            'connection_name': 'backend-rail',
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.RAIL_OPTIMIZED,
            'target_switch_class': self.switch_class.pk,
            'speed': 400,
            # rail is missing
        }

        response_fail = self.client.post(url, data_no_rail, follow=False)

        # Should re-render with error
        self.assertEqual(response_fail.status_code, 200,
                        "Form should reject rail-optimized without rail")

        # Verify error message mentions rail and required
        self.assertContains(response_fail, 'rail', status_code=200)
        self.assertContains(response_fail, 'required', status_code=200)

        # Rail-optimized WITH rail should succeed
        data_with_rail = {
            'server_class': self.server_class.pk,
            'connection_id': 'rail-test-success',
            'connection_name': 'backend-rail-0',
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.RAIL_OPTIMIZED,
            'target_switch_class': self.switch_class.pk,
            'speed': 400,
            'rail': 0,
        }

        response_success = self.client.post(url, data_with_rail, follow=False)
        self.assertEqual(response_success.status_code, 302,
                        "Form should accept rail-optimized with rail=0")

        connection = PlanServerConnection.objects.get(connection_id='rail-test-success')
        self.assertEqual(connection.rail, 0)

    def test_connection_rail_not_required_for_other_distributions(self):
        """Test that rail is NOT required for non-rail-optimized distributions"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')

        # Alternating distribution WITHOUT rail should succeed
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'alt-test',
            'connection_name': 'frontend-alt',
            'ports_per_connection': 2,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
            # rail is omitted
        }

        response = self.client.post(url, data, follow=False)

        # Should succeed
        self.assertEqual(response.status_code, 302,
                        "Alternating distribution should not require rail")

    def test_connection_invalid_target_switch_class_fk(self):
        """Test that invalid target_switch_class FK fails validation"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'bad-fk-test',
            'ports_per_connection': 1,
            'target_switch_class': 99999,  # Non-existent FK
            'speed': 200,
        }

        response = self.client.post(url, data, follow=False)

        # Should re-render with error
        self.assertEqual(response.status_code, 200,
                        "Form should reject invalid FK reference")


class FormErrorRenderingTestCase(TestCase):
    """
    Test suite for form error HTML rendering behavior.

    Verifies that error messages appear correctly in the rendered HTML
    and that forms re-render (not redirect) on validation errors.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test user"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_form_errors_contain_field_name(self):
        """Test that field-level errors mention the field name in HTML"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        data = {
            # Missing required 'name' field
            'customer_name': 'Test',
        }

        response = self.client.post(url, data, follow=False)

        # Should render form with errors (200)
        self.assertEqual(response.status_code, 200)

        # Error HTML should contain field name
        self.assertContains(response, 'name', status_code=200)

    def test_form_error_messages_user_friendly(self):
        """Test that error messages are user-friendly (not technical)"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        data = {
            'name': '',  # Empty name
        }

        response = self.client.post(url, data, follow=False)

        # Error message should say field is required
        self.assertContains(response, 'required', status_code=200)

    def test_multiple_field_errors_displayed(self):
        """Test that multiple field errors are all displayed"""
        # Create a plan first
        plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=self.user
        )

        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        data = {
            'plan': plan.pk,
            # Missing server_class_id
            # Missing quantity
            # Missing server_device_type
        }

        response = self.client.post(url, data, follow=False)

        # Should re-render with multiple errors
        self.assertEqual(response.status_code, 200)

        # All missing fields should have errors mentioned
        self.assertContains(response, 'server_class_id', status_code=200)
        self.assertContains(response, 'quantity', status_code=200)

    def test_form_preserves_user_input_on_error(self):
        """Test that form re-displays user's input when validation fails"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        customer_name = 'Unique Customer Name 12345'
        data = {
            # Missing required 'name'
            'customer_name': customer_name,
            'description': 'Test description',
        }

        response = self.client.post(url, data, follow=False)

        # Should re-render form
        self.assertEqual(response.status_code, 200)

        # User's customer_name input should still be present
        self.assertContains(response, customer_name, status_code=200)
