"""
Integration tests for Reference Data UI (DIET-010)

Tests validate real UX flows for BreakoutOption and DeviceTypeExtension models
following AGENTS.md testing standards.

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

from dcim.models import DeviceType, Manufacturer

from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)

User = get_user_model()


class BreakoutOptionUITestCase(TestCase):
    """
    Integration tests for BreakoutOption CRUD UI.

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

        # Create test BreakoutOptions (use test- prefix to avoid conflicts with seed data)
        cls.breakout1 = BreakoutOption.objects.create(
            breakout_id='test-2x400g',
            from_speed=800,
            logical_ports=2,
            logical_speed=400,
            optic_type='QSFP-DD'
        )
        cls.breakout2 = BreakoutOption.objects.create(
            breakout_id='test-4x200g',
            from_speed=800,
            logical_ports=4,
            logical_speed=200,
            optic_type='QSFP-DD'
        )

    def setUp(self):
        """Create fresh client for each test"""
        self.client = Client()

    # =========================================================================
    # List View Tests
    # =========================================================================

    def test_list_view_loads_successfully(self):
        """Test that breakout option list view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'netbox_hedgehog/topology_planning/breakoutoption_list.html')

    def test_list_view_displays_all_objects(self):
        """Test that list view renders all breakout options"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_list')
        response = self.client.get(url)

        self.assertContains(response, 'test-2x400g')
        self.assertContains(response, 'test-4x200g')

    # =========================================================================
    # Detail View Tests
    # =========================================================================

    def test_detail_view_loads_successfully(self):
        """Test that breakout option detail view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption', args=[self.breakout1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'netbox_hedgehog/topology_planning/breakoutoption.html')

    def test_detail_view_renders_expected_data(self):
        """Test that detail view displays correct breakout option data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption', args=[self.breakout1.pk])
        response = self.client.get(url)

        self.assertContains(response, 'test-2x400g')
        self.assertContains(response, '800')  # from_speed
        self.assertContains(response, '2')    # logical_ports
        self.assertContains(response, '400')  # logical_speed
        self.assertContains(response, 'QSFP-DD')

    # =========================================================================
    # Add Form Tests
    # =========================================================================

    def test_add_form_loads_successfully(self):
        """Test that add form loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'netbox_hedgehog/topology_planning/breakoutoption_edit.html')

    def test_add_form_contains_required_fields(self):
        """Test that add form renders all required fields"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_add')
        response = self.client.get(url)

        # Check that form fields are present in HTML
        self.assertContains(response, 'name="breakout_id"')
        self.assertContains(response, 'name="from_speed"')
        self.assertContains(response, 'name="logical_ports"')
        self.assertContains(response, 'name="logical_speed"')

    # =========================================================================
    # Create (POST) Tests
    # =========================================================================

    def test_create_valid_object_succeeds(self):
        """Test that valid POST creates object and redirects"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_add')

        data = {
            'breakout_id': 'test-8x100g',
            'from_speed': 800,
            'logical_ports': 8,
            'logical_speed': 100,
            'optic_type': 'QSFP-DD',
        }

        response = self.client.post(url, data, follow=False)

        # Should redirect after successful creation (302)
        self.assertEqual(response.status_code, 302)

        # Verify object was created
        self.assertTrue(BreakoutOption.objects.filter(breakout_id='test-8x100g').exists())
        created = BreakoutOption.objects.get(breakout_id='test-8x100g')
        self.assertEqual(created.from_speed, 800)
        self.assertEqual(created.logical_ports, 8)
        self.assertEqual(created.logical_speed, 100)

    def test_create_invalid_data_shows_errors(self):
        """Test that invalid POST shows form errors in HTML"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_add')

        # Missing required field (breakout_id)
        data = {
            'from_speed': 800,
            'logical_ports': 4,
            'logical_speed': 200,
        }

        response = self.client.post(url, data)

        # Should NOT redirect (form re-renders with errors)
        self.assertEqual(response.status_code, 200)

        # Form should contain error message
        self.assertContains(response, 'This field is required')

    def test_create_negative_speed_shows_validation_error(self):
        """Test that negative speed values trigger validation errors"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_add')

        data = {
            'breakout_id': 'invalid',
            'from_speed': -100,  # Invalid: negative value
            'logical_ports': 2,
            'logical_speed': 200,
        }

        response = self.client.post(url, data)

        # Should NOT redirect (form re-renders with errors)
        self.assertEqual(response.status_code, 200)

        # Should contain validation error message
        # NetBox validation messages may vary, but should indicate invalid value
        self.assertTrue(
            'greater than or equal to' in response.content.decode().lower() or
            'positive' in response.content.decode().lower() or
            'valid' in response.content.decode().lower()
        )

    def test_create_duplicate_breakout_id_shows_error(self):
        """Test that duplicate breakout_id shows unique constraint error"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_add')

        # Try to create with same breakout_id as existing object
        data = {
            'breakout_id': 'test-2x400g',  # Already exists
            'from_speed': 400,
            'logical_ports': 2,
            'logical_speed': 200,
        }

        response = self.client.post(url, data)

        # Should NOT redirect (form re-renders with errors)
        self.assertEqual(response.status_code, 200)

        # Should contain unique constraint error
        self.assertContains(response, 'already exists')

    # =========================================================================
    # Edit Form Tests
    # =========================================================================

    def test_edit_form_loads_with_existing_data(self):
        """Test that edit form loads with 200 status and pre-filled data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_edit', args=[self.breakout1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test-2x400g')
        self.assertContains(response, 'value="800"')  # from_speed pre-filled

    def test_edit_updates_object_successfully(self):
        """Test that valid POST updates object"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_edit', args=[self.breakout1.pk])

        data = {
            'breakout_id': 'test-2x400g',  # Keep same ID
            'from_speed': 800,
            'logical_ports': 2,
            'logical_speed': 400,
            'optic_type': 'QSFP112',  # Changed from QSFP-DD
        }

        response = self.client.post(url, data)

        # Should redirect after successful update
        self.assertEqual(response.status_code, 302)

        # Verify object was updated
        self.breakout1.refresh_from_db()
        self.assertEqual(self.breakout1.optic_type, 'QSFP112')

    # =========================================================================
    # Delete Tests
    # =========================================================================

    def test_delete_confirmation_page_loads(self):
        """Test that delete confirmation page loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_delete', args=[self.breakout1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Verify object name appears in delete confirmation
        self.assertContains(response, 'test-2x400g')
        # Verify it's a delete confirmation form (check for standard NetBox delete elements)
        self.assertContains(response, 'type="submit"')

    def test_delete_post_removes_object(self):
        """Test that POST to delete endpoint removes object"""
        self.client.login(username='admin', password='admin123')

        # Create a temporary object for deletion
        temp_breakout = BreakoutOption.objects.create(
            breakout_id='test-temp-delete',
            from_speed=400,
            logical_ports=1,
            logical_speed=400,
        )

        url = reverse('plugins:netbox_hedgehog:breakoutoption_delete', args=[temp_breakout.pk])
        response = self.client.post(url, {'confirm': True})

        # Should redirect after successful deletion
        self.assertEqual(response.status_code, 302)

        # Verify object was deleted
        self.assertFalse(BreakoutOption.objects.filter(pk=temp_breakout.pk).exists())

    # =========================================================================
    # Permission Enforcement Tests
    # =========================================================================

    def test_list_view_without_permission_forbidden(self):
        """Test that list view returns 403 without view permission"""
        # Login as user with no permissions
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_list')
        response = self.client.get(url)

        # Should be forbidden (authenticated but unauthorized)
        self.assertEqual(response.status_code, 403)

    def test_add_view_without_permission_forbidden(self):
        """Test that add view returns 403 without add permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_edit_view_without_permission_forbidden(self):
        """Test that edit view returns 403 without change permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_edit', args=[self.breakout1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_delete_view_without_permission_forbidden(self):
        """Test that delete view returns 403 without delete permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:breakoutoption_delete', args=[self.breakout1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_crud_operations_with_object_permission_succeed(self):
        """Test that CRUD operations succeed with ObjectPermission"""
        # Grant all permissions to regular user via ObjectPermission
        content_type = ContentType.objects.get_for_model(BreakoutOption)

        # Create ObjectPermission with all actions
        permission = ObjectPermission.objects.create(
            name='Test BreakoutOption Permission',
            actions=['view', 'add', 'change', 'delete']
        )
        permission.object_types.add(content_type)
        permission.users.add(self.regular_user)

        # Login as regular user
        self.client.login(username='regular', password='regular123')

        # Test list view
        url = reverse('plugins:netbox_hedgehog:breakoutoption_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test detail view
        url = reverse('plugins:netbox_hedgehog:breakoutoption', args=[self.breakout1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test add view
        url = reverse('plugins:netbox_hedgehog:breakoutoption_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test edit view
        url = reverse('plugins:netbox_hedgehog:breakoutoption_edit', args=[self.breakout1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test delete view (GET)
        url = reverse('plugins:netbox_hedgehog:breakoutoption_delete', args=[self.breakout1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test create operation (POST)
        url = reverse('plugins:netbox_hedgehog:breakoutoption_add')
        data = {
            'breakout_id': 'test-perm-create',
            'from_speed': 400,
            'logical_ports': 2,
            'logical_speed': 200,
        }
        response = self.client.post(url, data)
        # Should redirect after successful creation (302)
        self.assertEqual(response.status_code, 302)
        # Verify object was created
        self.assertTrue(BreakoutOption.objects.filter(breakout_id='test-perm-create').exists())

        # Test edit operation (POST)
        url = reverse('plugins:netbox_hedgehog:breakoutoption_edit', args=[self.breakout1.pk])
        data = {
            'breakout_id': 'test-2x400g',
            'from_speed': 800,
            'logical_ports': 2,
            'logical_speed': 400,
            'optic_type': 'QSFP-UPDATED',  # Changed value
        }
        response = self.client.post(url, data)
        # Should redirect after successful update (302)
        self.assertEqual(response.status_code, 302)
        # Verify object was updated
        self.breakout1.refresh_from_db()
        self.assertEqual(self.breakout1.optic_type, 'QSFP-UPDATED')

        # Test delete operation (POST)
        # Create a temp object to delete
        temp_obj = BreakoutOption.objects.create(
            breakout_id='test-perm-delete',
            from_speed=100,
            logical_ports=1,
            logical_speed=100
        )
        url = reverse('plugins:netbox_hedgehog:breakoutoption_delete', args=[temp_obj.pk])
        response = self.client.post(url, {'confirm': True})
        # Should redirect after successful deletion (302)
        self.assertEqual(response.status_code, 302)
        # Verify object was deleted
        self.assertFalse(BreakoutOption.objects.filter(pk=temp_obj.pk).exists())


class DeviceTypeExtensionUITestCase(TestCase):
    """
    Integration tests for DeviceTypeExtension CRUD UI.

    Tests simulate real user interactions via HTTP requests and validate
    that rendered HTML contains expected content and behaves correctly.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test data shared across all test methods"""
        # Create superuser
        cls.superuser = User.objects.create_user(
            username='admin',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )

        # Create regular user with no permissions
        cls.regular_user = User.objects.create_user(
            username='regular',
            password='regular123',
            is_staff=True,
            is_superuser=False
        )

        # Create manufacturer and device types
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )

        cls.device_type1, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'celestica-ds5000'}
        )

        cls.device_type2, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='TEST-DS3000',
            defaults={'slug': 'test-ds3000'}
        )

        # Create DeviceTypeExtensions
        cls.extension1, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.device_type1,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf'],
                'supported_breakouts': ['1x800g', '2x400g', '4x200g'],
                'native_speed': 800,
                'uplink_ports': 4
            }
        )

    def setUp(self):
        """Create fresh client for each test"""
        self.client = Client()

    # =========================================================================
    # List View Tests
    # =========================================================================

    def test_list_view_loads_successfully(self):
        """Test that device type extension list view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'netbox_hedgehog/topology_planning/devicetypeextension_list.html')

    def test_list_view_displays_device_types(self):
        """Test that list view renders device type information"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_list')
        response = self.client.get(url)

        self.assertContains(response, 'DS5000')

    # =========================================================================
    # Detail View Tests
    # =========================================================================

    def test_detail_view_loads_successfully(self):
        """Test that device type extension detail view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension', args=[self.extension1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'netbox_hedgehog/topology_planning/devicetypeextension.html')

    def test_detail_view_renders_expected_data(self):
        """Test that detail view displays correct extension data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension', args=[self.extension1.pk])
        response = self.client.get(url)

        self.assertContains(response, 'DS5000')
        self.assertContains(response, '800')  # native_speed
        self.assertContains(response, '4')    # uplink_ports

    # =========================================================================
    # Add Form Tests
    # =========================================================================

    def test_add_form_loads_successfully(self):
        """Test that add form loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'netbox_hedgehog/topology_planning/devicetypeextension_edit.html')

    def test_add_form_contains_required_fields(self):
        """Test that add form renders all required fields"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_add')
        response = self.client.get(url)

        self.assertContains(response, 'name="device_type"')
        self.assertContains(response, 'name="mclag_capable"')

    # =========================================================================
    # Create (POST) Tests
    # =========================================================================

    def test_create_valid_object_succeeds(self):
        """Test that valid POST creates object and redirects"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_add')

        # Use device_type2 which doesn't have an extension yet
        data = {
            'device_type': self.device_type2.pk,
            'mclag_capable': True,
            'hedgehog_roles': ['spine', 'border-leaf'],
            'supported_breakouts': '["1x100g", "4x25g"]',
            'native_speed': 100,
            'uplink_ports': 2,
        }

        response = self.client.post(url, data, follow=False)

        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)

        # Verify object was created
        self.assertTrue(DeviceTypeExtension.objects.filter(device_type=self.device_type2).exists())

    def test_create_duplicate_device_type_shows_error(self):
        """Test that duplicate device_type shows unique constraint error"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_add')

        # Try to create extension for device_type1 which already has one
        data = {
            'device_type': self.device_type1.pk,
            'mclag_capable': False,
        }

        response = self.client.post(url, data)

        # Should NOT redirect (form re-renders with errors)
        self.assertEqual(response.status_code, 200)

        # Should contain error message about duplicate
        self.assertTrue(
            'already exists' in response.content.decode().lower() or
            'unique' in response.content.decode().lower()
        )

    def test_create_invalid_json_shows_error(self):
        """Test that invalid JSON in supported_breakouts shows validation error"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_add')

        # Create a device type without extension
        temp_device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='TEMP',
            slug='celestica-temp'
        )

        data = {
            'device_type': temp_device_type.pk,
            'mclag_capable': False,
            'supported_breakouts': 'not valid json',  # Invalid JSON
        }

        response = self.client.post(url, data)

        # Should NOT redirect (form re-renders with errors)
        self.assertEqual(response.status_code, 200)

        # Should contain validation error (exact message may vary)
        content = response.content.decode().lower()
        self.assertTrue(
            'json' in content or
            'valid' in content or
            'invalid' in content
        )

    # =========================================================================
    # Edit Form Tests
    # =========================================================================

    def test_edit_form_loads_with_existing_data(self):
        """Test that edit form loads with 200 status and pre-filled data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_edit', args=[self.extension1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DS5000')

    def test_edit_updates_object_successfully(self):
        """Test that valid POST updates object"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_edit', args=[self.extension1.pk])

        data = {
            'device_type': self.device_type1.pk,
            'mclag_capable': True,  # Changed from False
            'hedgehog_roles': ['spine'],
            'supported_breakouts': '["1x800g", "2x400g"]',
            'native_speed': 800,
            'uplink_ports': 8,  # Changed from 4
        }

        response = self.client.post(url, data)

        # Should redirect after successful update
        self.assertEqual(response.status_code, 302)

        # Verify object was updated
        self.extension1.refresh_from_db()
        self.assertEqual(self.extension1.mclag_capable, True)
        self.assertEqual(self.extension1.uplink_ports, 8)

    # =========================================================================
    # Delete Tests
    # =========================================================================

    def test_delete_confirmation_page_loads(self):
        """Test that delete confirmation page loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_delete', args=[self.extension1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Verify device type name appears in delete confirmation
        self.assertContains(response, 'DS5000')
        # Verify it's a delete confirmation form (check for standard NetBox delete elements)
        self.assertContains(response, 'type="submit"')

    def test_delete_post_removes_object(self):
        """Test that POST to delete endpoint removes object"""
        self.client.login(username='admin', password='admin123')

        # Create a temporary extension for deletion
        temp_device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='TEMP-DELETE',
            slug='celestica-temp-delete'
        )
        temp_extension = DeviceTypeExtension.objects.create(
            device_type=temp_device_type,
            mclag_capable=False
        )

        url = reverse('plugins:netbox_hedgehog:devicetypeextension_delete', args=[temp_extension.pk])
        response = self.client.post(url, {'confirm': True})

        # Should redirect after successful deletion
        self.assertEqual(response.status_code, 302)

        # Verify object was deleted
        self.assertFalse(DeviceTypeExtension.objects.filter(pk=temp_extension.pk).exists())

    # =========================================================================
    # Permission Enforcement Tests
    # =========================================================================

    def test_list_view_without_permission_forbidden(self):
        """Test that list view returns 403 without view permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_add_view_without_permission_forbidden(self):
        """Test that add view returns 403 without add permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_edit_view_without_permission_forbidden(self):
        """Test that edit view returns 403 without change permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_edit', args=[self.extension1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_delete_view_without_permission_forbidden(self):
        """Test that delete view returns 403 without delete permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_delete', args=[self.extension1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_crud_operations_with_object_permission_succeed(self):
        """Test that CRUD operations succeed with ObjectPermission"""
        # Grant all permissions to regular user via ObjectPermission
        content_type = ContentType.objects.get_for_model(DeviceTypeExtension)

        permission = ObjectPermission.objects.create(
            name='Test DeviceTypeExtension Permission',
            actions=['view', 'add', 'change', 'delete']
        )
        permission.object_types.add(content_type)
        permission.users.add(self.regular_user)

        device_type_ct = ContentType.objects.get_for_model(DeviceType)
        device_type_permission = ObjectPermission.objects.create(
            name='Test DeviceType View',
            actions=['view']
        )
        device_type_permission.object_types.add(device_type_ct)
        device_type_permission.users.add(self.regular_user)

        # Login as regular user
        self.client.login(username='regular', password='regular123')

        # Test list view
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test detail view
        url = reverse('plugins:netbox_hedgehog:devicetypeextension', args=[self.extension1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test add view
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test edit view
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_edit', args=[self.extension1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test delete view (GET)
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_delete', args=[self.extension1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test create operation (POST)
        # Create a new device type for the extension
        temp_device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='TEMP-PERM-CREATE',
            slug='celestica-temp-perm-create'
        )
        url = reverse('plugins:netbox_hedgehog:devicetypeextension_add')
        data = {
            'device_type': temp_device_type.pk,
            'mclag_capable': True,
            'hedgehog_roles': ['spine'],
            'supported_breakouts': '["1x100g"]',
            'native_speed': 100,
        }
        response = self.client.post(url, data)
        # Should redirect after successful creation (302)
        self.assertEqual(response.status_code, 302)


class SwitchPortZoneUITestCase(TestCase):
    """
    Integration tests for SwitchPortZone CRUD UI.
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

        cls.device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'celestica-ds5000'}
        )

        cls.device_type_extension, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.device_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf'],
                'supported_breakouts': ['1x800g', '2x400g'],
                'native_speed': 800,
                'uplink_ports': 4,
            }
        )

        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='test-4x200g',
            defaults={
                'from_speed': 800,
                'logical_ports': 4,
                'logical_speed': 200,
                'optic_type': 'QSFP-DD',
            }
        )

        cls.plan, _ = TopologyPlan.objects.get_or_create(
            name='Test Plan',
            defaults={'customer_name': 'Test Customer'}
        )

        cls.switch_class, _ = PlanSwitchClass.objects.get_or_create(
            plan=cls.plan,
            switch_class_id='fe-gpu-leaf',
            defaults={
                'fabric': 'frontend',
                'hedgehog_role': 'server-leaf',
                'device_type_extension': cls.device_type_extension,
                'uplink_ports_per_switch': 4,
            }
        )

        cls.zone, _ = SwitchPortZone.objects.get_or_create(
            switch_class=cls.switch_class,
            zone_name='server-ports',
            defaults={
                'zone_type': 'server',
                'port_spec': '1-48',
                'breakout_option': cls.breakout,
                'allocation_strategy': 'sequential',
            }
        )

    def setUp(self):
        self.client = Client()

    # =========================================================================
    # List View Tests
    # =========================================================================

    def test_list_view_loads_successfully(self):
        """Test that switch port zone list view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'netbox_hedgehog/topology_planning/switchportzone_list.html')

    def test_list_view_displays_zones(self):
        """Test that list view renders zone name"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_list')
        response = self.client.get(url)

        self.assertContains(response, 'server-ports')

    # =========================================================================
    # Detail View Tests
    # =========================================================================

    def test_detail_view_loads_successfully(self):
        """Test that switch port zone detail view loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:switchportzone', args=[self.zone.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'netbox_hedgehog/topology_planning/switchportzone.html')

    def test_detail_view_renders_expected_data(self):
        """Test that detail view displays zone data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:switchportzone', args=[self.zone.pk])
        response = self.client.get(url)

        self.assertContains(response, 'server-ports')
        self.assertContains(response, '1-48')

    # =========================================================================
    # Add Form Tests
    # =========================================================================

    def test_add_form_loads_successfully(self):
        """Test that add form loads with 200 status"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'netbox_hedgehog/topology_planning/switchportzone_edit.html')

    def test_add_form_contains_required_fields(self):
        """Test that add form renders required fields"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_add')
        response = self.client.get(url)

        self.assertContains(response, 'name="switch_class"')
        self.assertContains(response, 'name="zone_name"')
        self.assertContains(response, 'name="port_spec"')

    # =========================================================================
    # Create (POST) Tests
    # =========================================================================

    def test_create_valid_object_succeeds(self):
        """Test that valid POST creates object and redirects"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_add')

        data = {
            'switch_class': self.switch_class.pk,
            'zone_name': 'uplinks',
            'zone_type': 'uplink',
            'port_spec': '49-64',
            'breakout_option': '',
            'allocation_strategy': 'sequential',
            'priority': 200,
        }

        response = self.client.post(url, data, follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(SwitchPortZone.objects.filter(zone_name='uplinks').exists())

    def test_create_invalid_data_shows_errors(self):
        """Test that invalid POST shows form errors"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_add')

        data = {
            'switch_class': self.switch_class.pk,
            'zone_name': 'bad-zone',
            'zone_type': 'server',
            'port_spec': 'invalid-spec',
            'allocation_strategy': 'sequential',
            'priority': 100,
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'port_spec')

    # =========================================================================
    # Edit Form Tests
    # =========================================================================

    def test_edit_form_loads_with_existing_data(self):
        """Test that edit form loads with data"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_edit', args=[self.zone.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'server-ports')

    def test_edit_updates_object_successfully(self):
        """Test that valid POST updates object"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_edit', args=[self.zone.pk])

        data = {
            'switch_class': self.switch_class.pk,
            'zone_name': 'server-ports',
            'zone_type': 'server',
            'port_spec': '1-32',
            'breakout_option': self.breakout.pk,
            'allocation_strategy': 'sequential',
            'priority': 150,
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.zone.refresh_from_db()
        self.assertEqual(self.zone.port_spec, '1-32')
        self.assertEqual(self.zone.priority, 150)

    # =========================================================================
    # Delete Tests
    # =========================================================================

    def test_delete_confirmation_page_loads(self):
        """Test that delete confirmation page loads"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_delete', args=[self.zone.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'server-ports')
        self.assertContains(response, 'type="submit"')

    def test_delete_post_removes_object(self):
        """Test that POST to delete endpoint removes object"""
        self.client.login(username='admin', password='admin123')

        temp_zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class,
            zone_name='temp-delete',
            zone_type='server',
            port_spec='1-8',
            allocation_strategy='sequential',
        )

        url = reverse('plugins:netbox_hedgehog:switchportzone_delete', args=[temp_zone.pk])
        response = self.client.post(url, {'confirm': True})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SwitchPortZone.objects.filter(pk=temp_zone.pk).exists())

    # =========================================================================
    # Permission Enforcement Tests
    # =========================================================================

    def test_list_view_without_permission_forbidden(self):
        """Test that list view returns 403 without view permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_add_view_without_permission_forbidden(self):
        """Test that add view returns 403 without add permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_edit_view_without_permission_forbidden(self):
        """Test that edit view returns 403 without change permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_edit', args=[self.zone.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_delete_view_without_permission_forbidden(self):
        """Test that delete view returns 403 without delete permission"""
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:switchportzone_delete', args=[self.zone.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_crud_operations_with_object_permission_succeed(self):
        """Test that CRUD operations succeed with ObjectPermission"""
        content_type = ContentType.objects.get_for_model(SwitchPortZone)
        permission = ObjectPermission.objects.create(
            name='Test SwitchPortZone Permission',
            actions=['view', 'add', 'change', 'delete']
        )
        permission.object_types.add(content_type)
        permission.users.add(self.regular_user)

        switch_class_ct = ContentType.objects.get_for_model(PlanSwitchClass)
        switch_class_permission = ObjectPermission.objects.create(
            name='Test PlanSwitchClass View',
            actions=['view']
        )
        switch_class_permission.object_types.add(switch_class_ct)
        switch_class_permission.users.add(self.regular_user)

        self.client.login(username='regular', password='regular123')

        url = reverse('plugins:netbox_hedgehog:switchportzone_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        add_url = reverse('plugins:netbox_hedgehog:switchportzone_add')
        data = {
            'switch_class': self.switch_class.pk,
            'zone_name': 'perm-create',
            'zone_type': 'server',
            'port_spec': '1-4',
            'allocation_strategy': 'sequential',
            'priority': 100,
        }
        response = self.client.post(add_url, data, follow=False)
        self.assertEqual(response.status_code, 302)
        created = SwitchPortZone.objects.get(zone_name='perm-create')

        edit_url = reverse('plugins:netbox_hedgehog:switchportzone_edit', args=[created.pk])
        data['port_spec'] = '1-6'
        response = self.client.post(edit_url, data)
        self.assertEqual(response.status_code, 302)

        delete_url = reverse('plugins:netbox_hedgehog:switchportzone_delete', args=[created.pk])
        response = self.client.post(delete_url, {'confirm': True})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SwitchPortZone.objects.filter(pk=created.pk).exists())
