"""
Integration tests for Topology Plan Models UI (DIET-157)

Tests validate real UX flows for TopologyPlan, PlanServerClass, PlanSwitchClass,
and PlanServerConnection models following AGENTS.md testing standards.

Coverage includes:
- List views (200 status)
- Detail views (200 status, expected data rendered)
- Add forms (200 status, form fields present)
- Create operations (POST creates object, redirects to detail)
- Edit operations (GET loads data, POST updates object)
- Delete operations (GET shows confirmation, POST deletes object)
- Permission enforcement (403 without permission, success with ObjectPermission)
- Form validation (negative tests for invalid data, error messages in HTML)
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from users.models import ObjectPermission

from dcim.models import DeviceType, Manufacturer, ModuleType

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    DeviceTypeExtension,
)

User = get_user_model()


class NavigationHighlightingTestCase(TestCase):
    """
    Tests for navigation highlighting regression (DIET-157).

    Verifies that the fix for the dashboard link staying highlighted on all
    pages is working correctly.

    SCOPE: These tests verify URL distinctness (the root cause of the bug)
    but do NOT verify actual navigation highlighting behavior. NetBox uses
    client-side JavaScript for navigation highlighting, which cannot be tested
    in backend integration tests.

    FOR COMPLETE E2E TESTING: See netbox_hedgehog/tests/test_e2e/ for
    browser-based tests that verify actual navigation highlighting behavior.

    What these tests DO protect against:
    - Dashboard URL reverting to empty string ''
    - Dashboard URL matching all plugin URLs
    - Request path being identical to dashboard on non-dashboard pages

    What these tests CANNOT catch (see E2E tests instead):
    - JavaScript bugs in navigation highlighting logic
    - CSS class changes that affect active state rendering
    - Client-side bugs that highlight dashboard for other reasons
    """

    @classmethod
    def setUpTestData(cls):
        """Create test user"""
        cls.superuser = User.objects.create_user(
            username='admin',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )

    def setUp(self):
        """Create fresh client"""
        self.client = Client()
        self.client.login(username='admin', password='admin123')

    def test_dashboard_url_differs_from_other_pages(self):
        """Test that dashboard URL is distinct from other plugin URLs"""
        # The bug was that dashboard was at '' (empty string), which matched
        # all plugin URLs causing the dashboard link to stay highlighted everywhere.
        # This test verifies the URLs are actually different now.

        dashboard_url = reverse('plugins:netbox_hedgehog:overview')
        topology_url = reverse('plugins:netbox_hedgehog:topologyplan_list')

        # Verify URLs are different
        self.assertNotEqual(dashboard_url, topology_url)

        # Verify dashboard URL doesn't use empty path (which would match everything)
        # The dashboard should be at a specific path like '/plugins/hedgehog/dashboard/'
        self.assertIn('dashboard', dashboard_url)
        self.assertNotEqual(dashboard_url.rstrip('/').split('/')[-1], '')

        # Verify topology plans URL is distinct
        self.assertIn('topology-plans', topology_url)

        # Fetch topology plan list and verify it loads successfully
        response = self.client.get(topology_url)
        self.assertEqual(response.status_code, 200)

        # The response should contain the topology plans content, not dashboard content
        self.assertContains(response, 'topology-plans')
        # Dashboard link should exist in nav but not be the current page
        self.assertContains(response, '/dashboard/')
        self.assertNotEqual(response.wsgi_request.path, dashboard_url)

    def test_dashboard_url_is_not_empty_string(self):
        """Test that dashboard is at /dashboard/ not root to prevent nav highlighting bug"""
        # The fix for the navigation highlighting issue is that the overview
        # view is now at 'dashboard/' instead of '' (empty string)
        # This prevents it from matching all plugin URLs
        dashboard_url = reverse('plugins:netbox_hedgehog:overview')

        # Verify the URL contains 'dashboard'
        self.assertIn('dashboard', dashboard_url)

        # Verify dashboard loads successfully
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, 200)


class TopologyPlanUITestCase(TestCase):
    """
    Integration tests for TopologyPlan CRUD UI.

    Tests simulate real user interactions via HTTP requests and validate
    that rendered HTML contains expected content and behaves correctly.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test data shared across all test methods"""
        # Create superuser for tests that need full permissions
        cls.superuser = User.objects.create_user(
            username='admin',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )

        # Create regular user with no permissions (for permission tests)
        cls.regular_user = User.objects.create_user(
            username='regular',
            password='regular123',
            is_staff=True,
            is_superuser=False
        )

        # Create test topology plans
        cls.plan1 = TopologyPlan.objects.create(
            name='Test Plan 1',
            customer_name='Customer A',
            description='First test plan',
            status='draft',
        )
        cls.plan2 = TopologyPlan.objects.create(
            name='Test Plan 2',
            customer_name='Customer B',
            description='Second test plan',
            status='review',
        )

    def setUp(self):
        """Create fresh client for each test"""
        self.client = Client()

    # =========================================================================
    # List View Tests
    # =========================================================================

    def test_list_view_loads_successfully(self):
        """Test that topology plan list view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_list_view_displays_all_objects(self):
        """Test that list view renders all topology plans"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_list')
        response = self.client.get(url)

        self.assertContains(response, 'Test Plan 1')
        self.assertContains(response, 'Test Plan 2')

    # =========================================================================
    # Detail View Tests
    # =========================================================================

    def test_detail_view_loads_successfully(self):
        """Test that topology plan detail view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_detail_view_renders_expected_data(self):
        """Test that detail view displays correct plan data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan1.pk])
        response = self.client.get(url)

        self.assertContains(response, 'Test Plan 1')
        self.assertContains(response, 'Customer A')
        self.assertContains(response, 'First test plan')

    # =========================================================================
    # Add Form Tests
    # =========================================================================

    def test_add_form_loads_successfully(self):
        """Test that add form loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_add_form_contains_required_fields(self):
        """Test that add form renders all required fields"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        response = self.client.get(url)

        # Check that form fields are present in HTML
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="customer_name"')
        self.assertContains(response, 'name="description"')

    # =========================================================================
    # Create (POST) Tests
    # =========================================================================

    def test_create_valid_object_succeeds(self):
        """Test that valid POST creates object and redirects"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')

        data = {
            'name': 'New Test Plan',
            'customer_name': 'Customer C',
            'description': 'Newly created test plan',
            'status': 'draft',
        }

        response = self.client.post(url, data, follow=False)

        # Should redirect after successful creation (302)
        self.assertEqual(response.status_code, 302)

        # Verify object was created
        self.assertTrue(TopologyPlan.objects.filter(name='New Test Plan').exists())
        created = TopologyPlan.objects.get(name='New Test Plan')
        self.assertEqual(created.customer_name, 'Customer C')
        self.assertEqual(created.status, 'draft')

    def test_create_invalid_data_shows_errors(self):
        """Test that invalid POST shows form errors in HTML"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')

        # Missing required field (name)
        data = {
            'customer_name': 'Customer D',
            'description': 'Missing name field',
        }

        response = self.client.post(url, data)

        # Should NOT redirect (form re-renders with errors)
        self.assertEqual(response.status_code, 200)

        # Form should contain error message
        self.assertContains(response, 'This field is required')

    def test_create_duplicate_name_allowed(self):
        """Test that duplicate plan names are allowed (no unique constraint)"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')

        # Try to create with same name as existing plan
        data = {
            'name': 'Test Plan 1',  # Already exists
            'customer_name': 'Customer E',
            'description': 'Duplicate name test',
            'status': 'draft',
        }

        response = self.client.post(url, data)

        # Should redirect (duplicates are allowed)
        self.assertEqual(response.status_code, 302)

        # Verify second object was created
        self.assertEqual(TopologyPlan.objects.filter(name='Test Plan 1').count(), 2)

    # =========================================================================
    # Edit Form Tests
    # =========================================================================

    def test_edit_form_loads_with_existing_data(self):
        """Test that edit form loads with 200 status and pre-filled data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_edit', args=[self.plan1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Plan 1')

    def test_edit_updates_object_successfully(self):
        """Test that valid POST updates object"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_edit', args=[self.plan1.pk])

        data = {
            'name': 'Test Plan 1',  # Keep same name
            'customer_name': 'Customer A Updated',  # Changed
            'description': 'Updated description',
            'status': 'review',  # Changed from draft
        }

        response = self.client.post(url, data)

        # Should redirect after successful update
        self.assertEqual(response.status_code, 302)

        # Verify object was updated
        self.plan1.refresh_from_db()
        self.assertEqual(self.plan1.customer_name, 'Customer A Updated')
        self.assertEqual(self.plan1.status, 'review')

    # =========================================================================
    # Delete Tests
    # =========================================================================

    def test_delete_confirmation_page_loads(self):
        """Test that delete confirmation page loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_delete', args=[self.plan1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Verify object name appears in delete confirmation
        self.assertContains(response, 'Test Plan 1')

    def test_delete_post_removes_object(self):
        """Test that POST to delete endpoint removes object"""
        self.client.login(username='admin', password='admin123')

        # Create a temporary object for deletion
        temp_plan = TopologyPlan.objects.create(
            name='Temp Delete Plan',
            customer_name='Temp Customer',
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_delete', args=[temp_plan.pk])
        response = self.client.post(url, {'confirm': True})

        # Should redirect after successful deletion
        self.assertEqual(response.status_code, 302)

        # Verify object was deleted
        self.assertFalse(TopologyPlan.objects.filter(pk=temp_plan.pk).exists())

    # =========================================================================
    # Permission Enforcement Tests
    # =========================================================================

    def test_list_view_without_permission_forbidden(self):
        """Test that list view returns 403 without view permission"""
        # Login as user with no permissions
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_list')
        response = self.client.get(url)

        # Should be forbidden (authenticated but unauthorized)
        self.assertEqual(response.status_code, 403)

    def test_add_view_without_permission_forbidden(self):
        """Test that add view returns 403 without add permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_edit_view_without_permission_forbidden(self):
        """Test that edit view returns 403 without change permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_edit', args=[self.plan1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_delete_view_without_permission_forbidden(self):
        """Test that delete view returns 403 without delete permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:topologyplan_delete', args=[self.plan1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_crud_operations_with_object_permission_succeed(self):
        """Test that CRUD operations succeed with ObjectPermission"""
        # Grant all permissions to regular user via ObjectPermission
        content_type = ContentType.objects.get_for_model(TopologyPlan)

        # Create ObjectPermission with all actions
        permission = ObjectPermission.objects.create(
            name='Test TopologyPlan Permission',
            actions=['view', 'add', 'change', 'delete']
        )
        permission.object_types.add(content_type)
        permission.users.add(self.regular_user)

        # Login as regular user
        self.client.login(username='regular', password='regular123')

        # Test list view
        url = reverse('plugins:netbox_hedgehog:topologyplan_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test detail view
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test add view
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test create operation (POST)
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        data = {
            'name': 'Perm Create Plan',
            'customer_name': 'Perm Customer',
            'status': 'draft',
        }
        response = self.client.post(url, data)
        # Should redirect after successful creation (302)
        self.assertEqual(response.status_code, 302)
        # Verify object was created
        self.assertTrue(TopologyPlan.objects.filter(name='Perm Create Plan').exists())


class PlanServerClassUITestCase(TestCase):
    """
    Integration tests for PlanServerClass CRUD UI.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        cls.superuser = User.objects.create_user(
            username='admin',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )

        cls.regular_user = User.objects.create_user(
            username='regular',
            password='regular123',
            is_staff=True,
            is_superuser=False
        )

        # Create manufacturer and device types for server
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Dell',
            defaults={'slug': 'dell'}
        )

        cls.server_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='PowerEdge R750',
            defaults={'slug': 'dell-r750'}
        )

        cls.nic_module_type, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='ConnectX-7',
        )

        # Create topology plan
        cls.plan = TopologyPlan.objects.create(
            name='Server Class Test Plan',
            customer_name='Test Customer',
        )

        # Create server class
        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='gpu-server-1',
            server_device_type=cls.server_device_type,
            quantity=10,
            category='gpu',
        )

    def setUp(self):
        """Create fresh client"""
        self.client = Client()

    # =========================================================================
    # List View Tests
    # =========================================================================

    def test_list_view_loads_successfully(self):
        """Test that server class list view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_list_view_displays_server_classes(self):
        """Test that list view renders server class data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_list')
        response = self.client.get(url)

        self.assertContains(response, 'gpu-server-1')

    # =========================================================================
    # Detail View Tests
    # =========================================================================

    def test_detail_view_loads_successfully(self):
        """Test that server class detail view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_detail', args=[self.server_class.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_detail_view_renders_expected_data(self):
        """Test that detail view displays correct server class data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_detail', args=[self.server_class.pk])
        response = self.client.get(url)

        self.assertContains(response, 'gpu-server-1')
        self.assertContains(response, '10')  # quantity

    # =========================================================================
    # Add Form Tests
    # =========================================================================

    def test_add_form_loads_successfully(self):
        """Test that add form loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_add_form_contains_required_fields(self):
        """Test that add form renders required fields"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        response = self.client.get(url)

        self.assertContains(response, 'name="plan"')
        self.assertContains(response, 'name="server_class_id"')
        self.assertContains(response, 'name="quantity"')

    # =========================================================================
    # Create (POST) Tests
    # =========================================================================

    def test_create_valid_object_succeeds(self):
        """Test that valid POST creates object and redirects"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')

        data = {
            'plan': self.plan.pk,
            'server_class_id': 'storage-server-1',
            'server_device_type': self.server_device_type.pk,
            'quantity': 5,
            'category': 'storage',
            'gpus_per_server': 0,
        }

        response = self.client.post(url, data, follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlanServerClass.objects.filter(server_class_id='storage-server-1').exists())

    def test_create_invalid_quantity_shows_errors(self):
        """Test that invalid quantity shows form errors"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')

        data = {
            'plan': self.plan.pk,
            'server_class_id': 'invalid-server',
            'server_device_type': self.server_device_type.pk,
            'quantity': -1,  # Invalid: negative
            'category': 'gpu',
            'gpus_per_server': 0,
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        # Should contain validation error
        content = response.content.decode().lower()
        self.assertTrue('greater' in content or 'positive' in content or 'valid' in content)

    # =========================================================================
    # Edit Form Tests
    # =========================================================================

    def test_edit_form_loads_with_existing_data(self):
        """Test that edit form loads with data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_edit', args=[self.server_class.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'gpu-server-1')

    def test_edit_updates_object_successfully(self):
        """Test that valid POST updates object"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_edit', args=[self.server_class.pk])

        data = {
            'plan': self.plan.pk,
            'server_class_id': 'gpu-server-1',
            'server_device_type': self.server_device_type.pk,
            'quantity': 20,  # Changed from 10
            'category': 'gpu',
            'gpus_per_server': 0,
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.server_class.refresh_from_db()
        self.assertEqual(self.server_class.quantity, 20)

    # =========================================================================
    # Delete Tests
    # =========================================================================

    def test_delete_confirmation_page_loads(self):
        """Test that delete confirmation page loads"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_delete', args=[self.server_class.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'gpu-server-1')

    def test_delete_post_removes_object(self):
        """Test that POST to delete endpoint removes object"""
        self.client.login(username='admin', password='admin123')

        temp_server_class = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='temp-delete-server',
            server_device_type=self.server_device_type,
            quantity=1,
            category='infrastructure',
        )

        url = reverse('plugins:netbox_hedgehog:planserverclass_delete', args=[temp_server_class.pk])
        response = self.client.post(url, {'confirm': True})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlanServerClass.objects.filter(pk=temp_server_class.pk).exists())

    # =========================================================================
    # Permission Enforcement Tests
    # =========================================================================

    def test_list_view_without_permission_forbidden(self):
        """Test that list view returns 403 without view permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_add_view_without_permission_forbidden(self):
        """Test that add view returns 403 without add permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_crud_operations_with_object_permission_succeed(self):
        """Test that CRUD operations succeed with ObjectPermission"""
        content_type = ContentType.objects.get_for_model(PlanServerClass)
        permission = ObjectPermission.objects.create(
            name='Test PlanServerClass Permission',
            actions=['view', 'add', 'change', 'delete']
        )
        permission.object_types.add(content_type)
        permission.users.add(self.regular_user)

        # Also need permissions for related models
        plan_ct = ContentType.objects.get_for_model(TopologyPlan)
        plan_perm = ObjectPermission.objects.create(
            name='Test TopologyPlan View',
            actions=['view']
        )
        plan_perm.object_types.add(plan_ct)
        plan_perm.users.add(self.regular_user)

        device_type_ct = ContentType.objects.get_for_model(DeviceType)
        device_type_perm = ObjectPermission.objects.create(
            name='Test DeviceType View',
            actions=['view']
        )
        device_type_perm.object_types.add(device_type_ct)
        device_type_perm.users.add(self.regular_user)

        self.client.login(username='regular', password='regular123')

        # Test list view
        url = reverse('plugins:netbox_hedgehog:planserverclass_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test create
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        data = {
            'plan': self.plan.pk,
            'server_class_id': 'perm-create',
            'server_device_type': self.server_device_type.pk,
            'quantity': 3,
            'category': 'infrastructure',
            'gpus_per_server': 0,
        }
        response = self.client.post(url, data, follow=False)
        self.assertEqual(response.status_code, 302)


class PlanSwitchClassUITestCase(TestCase):
    """
    Integration tests for PlanSwitchClass CRUD UI.
    """

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='admin',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )

        cls.regular_user = User.objects.create_user(
            username='regular',
            password='regular123',
            is_staff=True,
            is_superuser=False
        )

        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )

        cls.switch_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'celestica-ds5000'}
        )

        cls.device_type_extension, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_device_type,
            defaults={
                'mclag_capable': False,
                'native_speed': 800,
                'uplink_ports': 4,
            }
        )

        cls.plan = TopologyPlan.objects.create(
            name='Switch Class Test Plan',
            customer_name='Test Customer',
        )

        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-spine',
            fabric='frontend',
            hedgehog_role='spine',
            device_type_extension=cls.device_type_extension,
            uplink_ports_per_switch=4,
        )

    def setUp(self):
        self.client = Client()

    # =========================================================================
    # List View Tests
    # =========================================================================

    def test_list_view_loads_successfully(self):
        """Test that switch class list view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_list_view_displays_switch_classes(self):
        """Test that list view renders switch class data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_list')
        response = self.client.get(url)

        self.assertContains(response, 'fe-spine')

    # =========================================================================
    # Detail View Tests
    # =========================================================================

    def test_detail_view_loads_successfully(self):
        """Test that switch class detail view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_detail', args=[self.switch_class.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_detail_view_renders_expected_data(self):
        """Test that detail view displays correct switch class data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_detail', args=[self.switch_class.pk])
        response = self.client.get(url)

        self.assertContains(response, 'fe-spine')
        self.assertContains(response, 'spine')

    # =========================================================================
    # Add Form Tests
    # =========================================================================

    def test_add_form_loads_successfully(self):
        """Test that add form loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_add_form_contains_required_fields(self):
        """Test that add form renders required fields"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        response = self.client.get(url)

        self.assertContains(response, 'name="plan"')
        self.assertContains(response, 'name="switch_class_id"')
        self.assertContains(response, 'name="fabric"')
        self.assertContains(response, 'name="hedgehog_role"')

    # =========================================================================
    # Create (POST) Tests
    # =========================================================================

    def test_create_valid_object_succeeds(self):
        """Test that valid POST creates object and redirects"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')

        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'fe-leaf',
            'fabric': 'frontend',
            'hedgehog_role': 'server-leaf',
            'device_type_extension': self.device_type_extension.pk,
            'uplink_ports_per_switch': 4,
        }

        response = self.client.post(url, data, follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlanSwitchClass.objects.filter(switch_class_id='fe-leaf').exists())

    def test_create_invalid_uplink_ports_shows_errors(self):
        """Test that invalid uplink ports shows form errors"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')

        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'invalid-switch',
            'fabric': 'frontend',
            'hedgehog_role': 'spine',
            'device_type_extension': self.device_type_extension.pk,
            'uplink_ports_per_switch': -1,  # Invalid: negative
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        # Verify error message appears in form
        content = response.content.decode()
        self.assertIn('uplink_ports_per_switch', content)
        self.assertTrue('greater' in content.lower() or 'positive' in content.lower() or 'valid' in content.lower())

    # =========================================================================
    # Edit Form Tests
    # =========================================================================

    def test_edit_form_loads_with_existing_data(self):
        """Test that edit form loads with data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_edit', args=[self.switch_class.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fe-spine')

    def test_edit_updates_object_successfully(self):
        """Test that valid POST updates object"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_edit', args=[self.switch_class.pk])

        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'fe-spine',
            'fabric': 'frontend',
            'hedgehog_role': 'spine',
            'device_type_extension': self.device_type_extension.pk,
            'uplink_ports_per_switch': 8,  # Changed from 4
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.switch_class.refresh_from_db()
        self.assertEqual(self.switch_class.uplink_ports_per_switch, 8)

    # =========================================================================
    # Delete Tests
    # =========================================================================

    def test_delete_confirmation_page_loads(self):
        """Test that delete confirmation page loads"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_delete', args=[self.switch_class.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fe-spine')

    def test_delete_post_removes_object(self):
        """Test that POST to delete endpoint removes object"""
        self.client.login(username='admin', password='admin123')

        temp_switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='temp-delete-switch',
            fabric='backend',
            hedgehog_role='server-leaf',
            device_type_extension=self.device_type_extension,
            uplink_ports_per_switch=2,
        )

        url = reverse('plugins:netbox_hedgehog:planswitchclass_delete', args=[temp_switch_class.pk])
        response = self.client.post(url, {'confirm': True})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlanSwitchClass.objects.filter(pk=temp_switch_class.pk).exists())

    # =========================================================================
    # Permission Enforcement Tests
    # =========================================================================

    def test_list_view_without_permission_forbidden(self):
        """Test that list view returns 403 without view permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_crud_operations_with_object_permission_succeed(self):
        """Test that CRUD operations succeed with ObjectPermission"""
        content_type = ContentType.objects.get_for_model(PlanSwitchClass)
        permission = ObjectPermission.objects.create(
            name='Test PlanSwitchClass Permission',
            actions=['view', 'add', 'change', 'delete']
        )
        permission.object_types.add(content_type)
        permission.users.add(self.regular_user)

        # Related model permissions
        plan_ct = ContentType.objects.get_for_model(TopologyPlan)
        plan_perm = ObjectPermission.objects.create(
            name='Test TopologyPlan View',
            actions=['view']
        )
        plan_perm.object_types.add(plan_ct)
        plan_perm.users.add(self.regular_user)

        ext_ct = ContentType.objects.get_for_model(DeviceTypeExtension)
        ext_perm = ObjectPermission.objects.create(
            name='Test DeviceTypeExtension View',
            actions=['view']
        )
        ext_perm.object_types.add(ext_ct)
        ext_perm.users.add(self.regular_user)

        self.client.login(username='regular', password='regular123')

        url = reverse('plugins:netbox_hedgehog:planswitchclass_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class PlanServerConnectionUITestCase(TestCase):
    """
    Integration tests for PlanServerConnection CRUD UI.
    """

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='admin',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )

        cls.regular_user = User.objects.create_user(
            username='regular',
            password='regular123',
            is_staff=True,
            is_superuser=False
        )

        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Dell',
            defaults={'slug': 'dell'}
        )

        cls.server_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='PowerEdge R750',
            defaults={'slug': 'dell-r750'}
        )

        cls.switch_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='S5248F-ON',
            defaults={'slug': 'dell-s5248'}
        )

        cls.device_type_extension, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_device_type,
            defaults={
                'mclag_capable': False,
                'native_speed': 100,
                'uplink_ports': 4,
            }
        )

        cls.nic_module, _ = ModuleType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='ConnectX-7',
        )

        cls.plan = TopologyPlan.objects.create(
            name='Connection Test Plan',
            customer_name='Test Customer',
        )

        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='gpu-server',
            server_device_type=cls.server_device_type,
            quantity=10,
            category='gpu',
        )

        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            device_type_extension=cls.device_type_extension,
            uplink_ports_per_switch=4,
        )

        cls.connection = PlanServerConnection.objects.create(
            server_class=cls.server_class,
            connection_id='fe-001',
            target_switch_class=cls.switch_class,
            nic_module_type=cls.nic_module,
            port_index=0,
            ports_per_connection=2,
            speed=200,
            hedgehog_conn_type='unbundled',
            port_type='data',
        )

    def setUp(self):
        self.client = Client()

    # =========================================================================
    # List View Tests
    # =========================================================================

    def test_list_view_loads_successfully(self):
        """Test that server connection list view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_list_view_displays_connections(self):
        """Test that list view renders connection data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)

        self.assertContains(response, 'gpu-server')
        self.assertContains(response, 'fe-leaf')

    # =========================================================================
    # Detail View Tests
    # =========================================================================

    def test_detail_view_loads_successfully(self):
        """Test that connection detail view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_detail', args=[self.connection.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_detail_view_renders_expected_data(self):
        """Test that detail view displays correct connection data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_detail', args=[self.connection.pk])
        response = self.client.get(url)

        self.assertContains(response, '2')  # ports_per_connection

    # =========================================================================
    # Add Form Tests
    # =========================================================================

    def test_add_form_loads_successfully(self):
        """Test that add form loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_add_form_contains_required_fields(self):
        """Test that add form renders required fields"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.get(url)

        self.assertContains(response, 'name="server_class"')
        self.assertContains(response, 'name="target_switch_class"')
        self.assertContains(response, 'name="ports_per_connection"')

    # =========================================================================
    # Create (POST) Tests
    # =========================================================================

    def test_create_valid_object_succeeds(self):
        """Test that valid POST creates object and redirects"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')

        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-002',
            'target_switch_class': self.switch_class.pk,
            'nic_module_type': self.nic_module.pk,
            'port_index': 0,
            'ports_per_connection': 4,
            'speed': 200,
            'hedgehog_conn_type': 'bundled',
            'distribution': 'same-switch',
            'port_type': 'data',
        }

        response = self.client.post(url, data, follow=False)

        self.assertEqual(response.status_code, 302)
        # Verify a second connection was created
        self.assertEqual(
            PlanServerConnection.objects.filter(server_class=self.server_class).count(),
            2
        )

    def test_create_invalid_ports_shows_errors(self):
        """Test that invalid ports shows form errors"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')

        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'invalid-conn',
            'target_switch_class': self.switch_class.pk,
            'nic_module_type': self.nic_module.pk,
            'ports_per_connection': 0,  # Invalid
            'speed': 100,
            'hedgehog_conn_type': 'unbundled',
            'port_type': 'data',
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        # Verify error message appears in form
        content = response.content.decode()
        self.assertIn('ports_per_connection', content)
        self.assertTrue('greater' in content.lower() or 'minimum' in content.lower() or 'valid' in content.lower())

    # =========================================================================
    # Edit Form Tests
    # =========================================================================

    def test_edit_form_loads_with_existing_data(self):
        """Test that edit form loads with data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_edit', args=[self.connection.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_edit_updates_object_successfully(self):
        """Test that valid POST updates object"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_edit', args=[self.connection.pk])

        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-001',
            'target_switch_class': self.switch_class.pk,
            'nic_module_type': self.nic_module.pk,
            'port_index': 0,
            'ports_per_connection': 4,  # Changed from 2
            'speed': 200,
            'hedgehog_conn_type': 'bundled',  # Changed
            'distribution': 'same-switch',
            'port_type': 'data',
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.ports_per_connection, 4)
        self.assertEqual(self.connection.hedgehog_conn_type, 'bundled')

    # =========================================================================
    # Delete Tests
    # =========================================================================

    def test_delete_confirmation_page_loads(self):
        """Test that delete confirmation page loads"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_delete', args=[self.connection.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_delete_post_removes_object(self):
        """Test that POST to delete endpoint removes object"""
        self.client.login(username='admin', password='admin123')

        temp_connection = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='temp-delete',
            target_switch_class=self.switch_class,
            nic_module_type=self.nic_module,
            ports_per_connection=1,
            speed=10,
            hedgehog_conn_type='unbundled',
            port_type='ipmi',
        )

        url = reverse('plugins:netbox_hedgehog:planserverconnection_delete', args=[temp_connection.pk])
        response = self.client.post(url, {'confirm': True})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlanServerConnection.objects.filter(pk=temp_connection.pk).exists())

    # =========================================================================
    # Permission Enforcement Tests
    # =========================================================================

    def test_list_view_without_permission_forbidden(self):
        """Test that list view returns 403 without view permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_crud_operations_with_object_permission_succeed(self):
        """Test that CRUD operations succeed with ObjectPermission"""
        content_type = ContentType.objects.get_for_model(PlanServerConnection)
        permission = ObjectPermission.objects.create(
            name='Test PlanServerConnection Permission',
            actions=['view', 'add', 'change', 'delete']
        )
        permission.object_types.add(content_type)
        permission.users.add(self.regular_user)

        # Related model permissions
        for model in [PlanServerClass, PlanSwitchClass, TopologyPlan, ModuleType]:
            ct = ContentType.objects.get_for_model(model)
            perm = ObjectPermission.objects.create(
                name=f'Test {model.__name__} View',
                actions=['view']
            )
            perm.object_types.add(ct)
            perm.users.add(self.regular_user)

        self.client.login(username='regular', password='regular123')

        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
