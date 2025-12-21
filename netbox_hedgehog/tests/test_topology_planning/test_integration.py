"""
Integration Tests for Topology Planning UI (DIET-004)

These tests verify the actual user experience by making real HTTP requests,
loading pages, submitting forms, and checking the full request/response cycle.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from dcim.models import DeviceType, Manufacturer

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    DeviceTypeExtension,
    PlanServerConnection,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    ServerClassCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    PortTypeChoices,
)

User = get_user_model()


class TopologyPlanIntegrationTestCase(TestCase):
    """Integration tests for TopologyPlan UI workflow"""

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

    def test_plan_list_page_loads(self):
        """Test that plan list page loads successfully"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        f"Plan list page failed to load: {response.status_code}")

    def test_plan_add_page_loads(self):
        """Test that plan add page loads successfully"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        f"Plan add page failed to load: {response.status_code}")

    def test_create_plan_workflow(self):
        """Test complete workflow: create plan, verify it appears in list"""
        # Step 1: Create a plan via POST
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        data = {
            'name': 'Integration Test Plan',
            'customer_name': 'Test Customer',
            'status': TopologyPlanStatusChoices.DRAFT,
            'description': 'Created via integration test',
        }
        response = self.client.post(url, data, follow=False)  # Don't follow to see redirect

        # Should get 302 redirect on success
        if response.status_code not in (200, 302):
            print(f"\n\nERROR DETAILS:")
            print(f"Status: {response.status_code}")
            if hasattr(response, 'content'):
                print(f"Content: {response.content.decode('utf-8')[:1000]}")
            if hasattr(response, 'context') and response.context and 'exception' in response.context:
                import traceback
                print(f"Exception: {response.context['exception']}")
                traceback.print_exception(type(response.context['exception']),
                                         response.context['exception'],
                                         response.context['exception'].__traceback__)
            print(f"\n")

        self.assertIn(response.status_code, [200, 302],
                     f"Plan creation failed: {response.status_code}")

        # Step 2: Verify plan was created in database
        plan = TopologyPlan.objects.filter(name='Integration Test Plan').first()
        self.assertIsNotNone(plan, "Plan was not created in database")
        self.assertEqual(plan.customer_name, 'Test Customer')

        # Step 3: Verify plan appears in list view
        list_url = reverse('plugins:netbox_hedgehog:topologyplan_list')
        list_response = self.client.get(list_url)
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, 'Integration Test Plan')

    def test_plan_detail_page_loads(self):
        """Test that plan detail page loads successfully"""
        plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=self.user
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        f"Plan detail page failed to load: {response.status_code}")
        self.assertContains(response, 'Test Plan')

    def test_plan_edit_workflow(self):
        """Test editing an existing plan"""
        plan = TopologyPlan.objects.create(
            name='Original Name',
            created_by=self.user
        )

        # Load edit page
        edit_url = reverse('plugins:netbox_hedgehog:topologyplan_edit', args=[plan.pk])
        get_response = self.client.get(edit_url)
        self.assertEqual(get_response.status_code, 200)

        # Submit changes
        data = {
            'name': 'Updated Name',
            'status': TopologyPlanStatusChoices.REVIEW,
        }
        post_response = self.client.post(edit_url, data, follow=True)
        self.assertEqual(post_response.status_code, 200)

        # Verify changes
        plan.refresh_from_db()
        self.assertEqual(plan.name, 'Updated Name')
        self.assertEqual(plan.status, TopologyPlanStatusChoices.REVIEW)

    def test_plan_delete_workflow(self):
        """Test deleting a plan"""
        plan = TopologyPlan.objects.create(
            name='Plan To Delete',
            created_by=self.user
        )

        # Load delete confirmation page
        delete_url = reverse('plugins:netbox_hedgehog:topologyplan_delete', args=[plan.pk])
        get_response = self.client.get(delete_url)
        self.assertEqual(get_response.status_code, 200)

        # Confirm deletion
        post_response = self.client.post(delete_url, {'confirm': True}, follow=True)
        self.assertEqual(post_response.status_code, 200)

        # Verify deletion
        self.assertFalse(TopologyPlan.objects.filter(pk=plan.pk).exists())


class ServerClassIntegrationTestCase(TestCase):
    """Integration tests for Server Class UI workflow"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
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

    def test_server_class_list_loads(self):
        """Test that server class list page loads"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_server_class_add_page_loads(self):
        """Test that server class add page loads"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_create_server_class_workflow(self):
        """Test creating a server class"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        data = {
            'plan': self.plan.pk,
            'server_class_id': 'GPU-001',
            'category': ServerClassCategoryChoices.GPU,
            'quantity': 10,
            'gpus_per_server': 8,
            'server_device_type': self.server_type.pk,
        }
        response = self.client.post(url, data, follow=True)

        self.assertEqual(response.status_code, 200,
                        f"Server class creation failed: {response.status_code}")

        # Verify creation
        server_class = PlanServerClass.objects.filter(server_class_id='GPU-001').first()
        self.assertIsNotNone(server_class)
        self.assertEqual(server_class.quantity, 10)
        self.assertEqual(server_class.gpus_per_server, 8)


class SwitchClassIntegrationTestCase(TestCase):
    """Integration tests for Switch Class UI workflow"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
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

    def test_switch_class_list_loads(self):
        """Test that switch class list page loads"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_switch_class_add_page_loads(self):
        """Test that switch class add page loads"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_create_switch_class_workflow(self):
        """Test creating a switch class"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'fe-leaf',
            'fabric': FabricTypeChoices.FRONTEND,
            'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 4,
            'mclag_pair': True,
        }
        response = self.client.post(url, data, follow=True)

        self.assertEqual(response.status_code, 200,
                        f"Switch class creation failed: {response.status_code}")

        # Verify creation
        switch_class = PlanSwitchClass.objects.filter(switch_class_id='fe-leaf').first()
        self.assertIsNotNone(switch_class)
        self.assertEqual(switch_class.fabric, FabricTypeChoices.FRONTEND)


class RecalculateIntegrationTestCase(TestCase):
    """Integration tests for recalculate functionality"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
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

        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=4,
            calculated_quantity=None  # Not yet calculated
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_recalculate_action(self):
        """Test that recalculate action works"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_recalculate', args=[self.plan.pk])

        # POST to recalculate endpoint
        response = self.client.post(url, follow=True)

        # Should redirect back to detail page
        self.assertEqual(response.status_code, 200,
                        f"Recalculate action failed: {response.status_code}")

        # Should show success message
        messages = list(response.context.get('messages', []))
        self.assertTrue(any('Recalculated' in str(m) for m in messages),
                       "No success message after recalculate")

        # Verify calculation was run
        self.switch_class.refresh_from_db()
        # calculated_quantity should now be set (even if 0)
        self.assertIsNotNone(self.switch_class.calculated_quantity,
                            "Calculation engine did not update calculated_quantity")


class PermissionIntegrationTestCase(TestCase):
    """Integration tests for permission enforcement"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        # Create superuser for setup
        cls.superuser = User.objects.create_user(
            username='admin',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )

        # Create non-superuser
        cls.regular_user = User.objects.create_user(
            username='regular',
            password='regular123',
            is_staff=True,
            is_superuser=False
        )

        # Create plan owned by regular user (for object-level permission test)
        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=cls.regular_user
        )

    def setUp(self):
        """Create fresh client for each test"""
        self.client = Client()

    def test_recalculate_requires_change_permission(self):
        """Test that non-superuser without change permission cannot recalculate"""
        # Login as regular user without change permission
        self.client.login(username='regular', password='regular123')

        url = reverse('plugins:netbox_hedgehog:topologyplan_recalculate', args=[self.plan.pk])
        response = self.client.post(url)

        # Should get 403 Forbidden
        self.assertEqual(response.status_code, 403,
                        "Non-superuser without change permission should get 403")

    def test_recalculate_with_change_permission(self):
        """Test that non-superuser with change permission can recalculate"""
        from users.models import ObjectPermission

        # Create NetBox object-level permission for regular user
        obj_perm = ObjectPermission.objects.create(
            name='Test change topologyplan permission',
            actions=['change', 'view']
        )
        obj_perm.object_types.add(
            ContentType.objects.get_for_model(TopologyPlan)
        )
        obj_perm.users.add(self.regular_user)

        # Use force_login to bypass caching issues
        self.client.force_login(self.regular_user)

        url = reverse('plugins:netbox_hedgehog:topologyplan_recalculate', args=[self.plan.pk])
        response = self.client.post(url, follow=False)

        # Should get 302 redirect (permission check passed)
        if response.status_code != 302:
            print(f"\nDEBUG: Status code: {response.status_code}")
            print(f"DEBUG: User permissions: {list(self.regular_user.get_all_permissions())}")
            if hasattr(response, 'content'):
                content = response.content.decode('utf-8')
                # Find the actual error message
                import re
                match = re.search(r'<title>(.*?)</title>', content)
                if match:
                    print(f"DEBUG: Page title: {match.group(1)}")
                # Look for error message in content
                if 'Access Denied' in content or 'Permission' in content:
                    start_idx = content.find('Access')
                    if start_idx > 0:
                        print(f"DEBUG: Error section: {content[start_idx:start_idx+200]}")

        self.assertEqual(response.status_code, 302,
                        f"User with change permission should get redirect, got {response.status_code}")

        # Verify redirect goes to detail page
        self.assertEqual(response.url, reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk]),
                        "Should redirect to plan detail page")


# =============================================================================
# PlanServerConnection Integration Tests (DIET-005)
# =============================================================================

class ServerConnectionIntegrationTestCase(TestCase):
    """Integration tests for PlanServerConnection UI workflow"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
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

        # Create manufacturer and device types
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Dell',
            defaults={'slug': 'dell'}
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='PowerEdge R750',
            defaults={'slug': 'poweredge-r750'}
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'ds5000'}
        )

        # Create device extension
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

        # Create server class
        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='GPU-001',
            category=ServerClassCategoryChoices.GPU,
            quantity=10,
            gpus_per_server=8,
            server_device_type=cls.server_type
        )

        # Create switch class
        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=4
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_connection_list_loads(self):
        """Test that connection list page loads"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        f"Connection list page failed to load: {response.status_code}")

    def test_connection_add_page_loads(self):
        """Test that connection add page loads"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        f"Connection add page failed to load: {response.status_code}")

    def test_create_connection_workflow(self):
        """Test creating a server connection"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'FE-001',
            'connection_name': 'frontend',
            'ports_per_connection': 2,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
            'port_type': PortTypeChoices.DATA,
        }
        response = self.client.post(url, data, follow=True)


        self.assertEqual(response.status_code, 200,
                        f"Connection creation failed: {response.status_code}")

        # Verify creation
        connection = PlanServerConnection.objects.filter(connection_id='FE-001').first()
        self.assertIsNotNone(connection, "Connection was not created in database")
        self.assertEqual(connection.ports_per_connection, 2)
        self.assertEqual(connection.speed, 200)
        self.assertEqual(connection.distribution, ConnectionDistributionChoices.ALTERNATING)

    def test_connection_detail_page_loads(self):
        """Test that connection detail page loads"""
        connection = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='FE-001',
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_switch_class=self.switch_class,
            speed=200
        )

        url = reverse('plugins:netbox_hedgehog:planserverconnection_detail', args=[connection.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        f"Connection detail page failed to load: {response.status_code}")
        self.assertContains(response, 'FE-001')

    def test_connection_edit_workflow(self):
        """Test editing an existing connection"""
        connection = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='FE-001',
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_switch_class=self.switch_class,
            speed=200
        )

        # Load edit page
        edit_url = reverse('plugins:netbox_hedgehog:planserverconnection_edit', args=[connection.pk])
        get_response = self.client.get(edit_url)
        self.assertEqual(get_response.status_code, 200)

        # Submit changes
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'FE-001',
            'ports_per_connection': 4,  # Changed from 2
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,  # Changed
            'target_switch_class': self.switch_class.pk,
            'speed': 400,  # Changed from 200
        }
        post_response = self.client.post(edit_url, data, follow=True)
        self.assertEqual(post_response.status_code, 200)

        # Verify changes
        connection.refresh_from_db()
        self.assertEqual(connection.ports_per_connection, 4)
        self.assertEqual(connection.speed, 400)
        self.assertEqual(connection.distribution, ConnectionDistributionChoices.ALTERNATING)

    def test_connection_delete_workflow(self):
        """Test deleting a connection"""
        connection = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='FE-DELETE',
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_switch_class=self.switch_class,
            speed=200
        )

        # Load delete confirmation page
        delete_url = reverse('plugins:netbox_hedgehog:planserverconnection_delete', args=[connection.pk])
        get_response = self.client.get(delete_url)
        self.assertEqual(get_response.status_code, 200)

        # Confirm deletion
        post_response = self.client.post(delete_url, {'confirm': True}, follow=True)
        self.assertEqual(post_response.status_code, 200)

        # Verify deletion
        self.assertFalse(PlanServerConnection.objects.filter(pk=connection.pk).exists())


class ServerConnectionValidationTestCase(TestCase):
    """Integration tests for PlanServerConnection validation rules"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
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

        # Create manufacturer and device types
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Dell',
            defaults={'slug': 'dell'}
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='PowerEdge R750',
            defaults={'slug': 'poweredge-r750'}
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'ds5000'}
        )

        # Create device extension
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

        # Create server class
        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='GPU-001',
            category=ServerClassCategoryChoices.GPU,
            quantity=10,
            gpus_per_server=8,
            server_device_type=cls.server_type
        )

        # Create switch class
        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='be-rail-leaf',
            fabric=FabricTypeChoices.BACKEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=4
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_rail_required_for_rail_optimized(self):
        """Test that rail is required when distribution is rail-optimized"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'BE-RAIL-0',
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.RAIL_OPTIMIZED,
            'target_switch_class': self.switch_class.pk,
            'speed': 400,
            # rail is NOT provided - should cause validation error
        }

        response = self.client.post(url, data, follow=False)

        # Should NOT create connection (stays on form with errors)
        self.assertEqual(response.status_code, 200,
                        "Form should return 200 with validation errors")
        self.assertContains(response, 'Rail is required when distribution is set to rail-optimized',
                           msg_prefix="Missing expected validation error message")

        # Verify connection was not created
        self.assertFalse(PlanServerConnection.objects.filter(connection_id='BE-RAIL-0').exists(),
                        "Connection should not be created when validation fails")

    def test_rail_not_required_for_other_distributions(self):
        """Test that rail is NOT required for non-rail-optimized distributions"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'FE-001',
            'ports_per_connection': 2,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
            # rail is NOT provided - should be OK for alternating
        }
        response = self.client.post(url, data, follow=True)

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Verify connection was created
        connection = PlanServerConnection.objects.filter(connection_id='FE-001').first()
        self.assertIsNotNone(connection, "Connection should be created without rail for alternating distribution")
        self.assertIsNone(connection.rail, "Rail should be None for alternating distribution")

    def test_rail_accepted_for_rail_optimized(self):
        """Test that providing rail for rail-optimized distribution works"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'BE-RAIL-0',
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.RAIL_OPTIMIZED,
            'target_switch_class': self.switch_class.pk,
            'speed': 400,
            'rail': 0,  # Provided - should work
        }
        response = self.client.post(url, data, follow=True)

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Verify connection was created with rail
        connection = PlanServerConnection.objects.filter(connection_id='BE-RAIL-0').first()
        self.assertIsNotNone(connection, "Connection should be created with rail for rail-optimized")
        self.assertEqual(connection.rail, 0)


class ServerConnectionFilteringTestCase(TestCase):
    """Integration tests for target_switch_class filtering (same plan only)"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        # Create TWO plans
        cls.plan1 = TopologyPlan.objects.create(
            name='Plan 1',
            created_by=cls.user
        )
        cls.plan2 = TopologyPlan.objects.create(
            name='Plan 2',
            created_by=cls.user
        )

        # Create manufacturer and device types
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Dell',
            defaults={'slug': 'dell'}
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='PowerEdge R750',
            defaults={'slug': 'poweredge-r750'}
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'ds5000'}
        )

        # Create device extension
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

        # Create server class in Plan 1
        cls.server_class_plan1 = PlanServerClass.objects.create(
            plan=cls.plan1,
            server_class_id='GPU-PLAN1',
            category=ServerClassCategoryChoices.GPU,
            quantity=10,
            gpus_per_server=8,
            server_device_type=cls.server_type
        )

        # Create switch classes in both plans
        cls.switch_class_plan1 = PlanSwitchClass.objects.create(
            plan=cls.plan1,
            switch_class_id='fe-leaf-plan1',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=4
        )

        cls.switch_class_plan2 = PlanSwitchClass.objects.create(
            plan=cls.plan2,
            switch_class_id='fe-leaf-plan2',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=4
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_cannot_use_switch_from_different_plan(self):
        """Test that you cannot select a switch class from a different plan"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class_plan1.pk,  # From Plan 1
            'connection_id': 'CROSS-PLAN',
            'ports_per_connection': 2,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.SAME_SWITCH,
            'target_switch_class': self.switch_class_plan2.pk,  # From Plan 2 - WRONG!
            'speed': 200,
        }
        response = self.client.post(url, data, follow=False)

        # Should NOT create connection (stays on form with errors)
        self.assertEqual(response.status_code, 200,
                        "Form should return 200 with validation errors")
        # Django's form validation rejects the choice because queryset filtering removes cross-plan switches
        self.assertContains(response, 'Select a valid choice',
                           msg_prefix="Missing expected validation error - queryset filtering prevents cross-plan selection")

        # Verify connection was not created
        self.assertFalse(PlanServerConnection.objects.filter(connection_id='CROSS-PLAN').exists(),
                        "Connection should not be created when switch is from different plan")

    def test_can_use_switch_from_same_plan(self):
        """Test that you can select a switch class from the same plan"""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class_plan1.pk,  # From Plan 1
            'connection_id': 'SAME-PLAN',
            'ports_per_connection': 2,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.SAME_SWITCH,
            'target_switch_class': self.switch_class_plan1.pk,  # Also from Plan 1 - CORRECT
            'speed': 200,
        }
        response = self.client.post(url, data, follow=True)

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Verify connection was created
        connection = PlanServerConnection.objects.filter(connection_id='SAME-PLAN').first()
        self.assertIsNotNone(connection, "Connection should be created when switch is from same plan")
        self.assertEqual(connection.server_class.plan, connection.target_switch_class.plan,
                        "Server and switch should be from the same plan")


class ServerConnectionPermissionTestCase(TestCase):
    """Integration tests for permission enforcement on PlanServerConnection"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        # Create superuser for setup
        cls.superuser = User.objects.create_user(
            username='admin',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )

        # Create non-superuser
        cls.regular_user = User.objects.create_user(
            username='regular',
            password='regular123',
            is_staff=True,
            is_superuser=False
        )

        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            created_by=cls.regular_user
        )

        # Create manufacturer and device types
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Dell',
            defaults={'slug': 'dell'}
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='PowerEdge R750',
            defaults={'slug': 'poweredge-r750'}
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'ds5000'}
        )

        # Create device extension
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

        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='GPU-001',
            category=ServerClassCategoryChoices.GPU,
            quantity=10,
            gpus_per_server=8,
            server_device_type=cls.server_type
        )

        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=4
        )

    def setUp(self):
        """Create fresh client for each test"""
        self.client = Client()

    def test_create_without_permission_fails(self):
        """Test that non-superuser without add permission cannot create"""
        # Login as regular user without add permission
        self.client.login(username='regular', password='regular123')

        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'FE-001',
            'ports_per_connection': 2,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
        }
        response = self.client.post(url, data, follow=False)

        # Should get 403 Forbidden
        self.assertEqual(response.status_code, 403,
                        "Non-superuser without add permission should get 403")

    def test_create_with_permission_succeeds(self):
        """Test that non-superuser with add permission can create"""
        from users.models import ObjectPermission

        # Create NetBox object-level permissions for regular user
        # Need permissions for PlanServerConnection, PlanServerClass, and PlanSwitchClass
        obj_perm = ObjectPermission.objects.create(
            name='Test add planserverconnection permission',
            actions=['add', 'view']
        )
        obj_perm.object_types.add(
            ContentType.objects.get_for_model(PlanServerConnection),
            ContentType.objects.get_for_model(PlanServerClass),
            ContentType.objects.get_for_model(PlanSwitchClass),
        )
        obj_perm.users.add(self.regular_user)

        # Use force_login to bypass caching issues
        self.client.force_login(self.regular_user)

        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'FE-001',
            'ports_per_connection': 2,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
        }
        response = self.client.post(url, data, follow=False)

        # Should get 302 redirect (permission check passed)
        self.assertEqual(response.status_code, 302,
                        f"User with add permission should get redirect, got {response.status_code}")


# =============================================================================
# YAML Export Integration Tests (DIET-006)
# =============================================================================

class YAMLExportIntegrationTestCase(TestCase):
    """Integration tests for YAML export functionality (DIET-006)"""

    @classmethod
    def setUpTestData(cls):
        """Create test data for export tests"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        # Create plan
        cls.plan = TopologyPlan.objects.create(
            name='Export Test Plan',
            customer_name='Test Customer',
            created_by=cls.user
        )

        # Create manufacturers and device types
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica',
            defaults={'slug': 'celestica'}
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='PowerEdge R750',
            defaults={'slug': 'poweredge-r750'}
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            defaults={'slug': 'ds5000'}
        )

        # Create device extension for switch
        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'native_speed': 800,
                'uplink_ports': 4,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g']
            }
        )

        # Create server class
        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='GPU-001',
            category=ServerClassCategoryChoices.GPU,
            quantity=2,  # 2 servers
            gpus_per_server=0,
            server_device_type=cls.server_type
        )

        # Create switch class
        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=4,
            calculated_quantity=1
        )

        # Create server connection (2 ports per server, alternating distribution)
        cls.connection = PlanServerConnection.objects.create(
            server_class=cls.server_class,
            connection_id='FE-001',
            connection_name='frontend',
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_switch_class=cls.switch_class,
            speed=200,
            port_type=PortTypeChoices.DATA
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_export_button_appears_on_plan_detail_page(self):
        """Test that export button is visible on plan detail page"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200,
                        "Plan detail page should load successfully")
        self.assertContains(response, 'Export YAML',
                           msg_prefix="Export button should appear on plan detail page")

    def test_export_returns_yaml_download(self):
        """Test that clicking export returns a downloadable YAML file"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        # Should return 200 OK
        self.assertEqual(response.status_code, 200,
                        "Export should return 200 OK")

        # Should have YAML content type
        self.assertIn('text/yaml', response.get('Content-Type', ''),
                     "Response should have YAML content type")

        # Should have Content-Disposition header with filename
        content_disposition = response.get('Content-Disposition', '')
        self.assertIn('attachment', content_disposition,
                     "Response should have attachment disposition")
        self.assertIn('export-test-plan', content_disposition.lower(),
                     "Filename should be based on plan name")
        self.assertIn('.yaml', content_disposition,
                     "Filename should have .yaml extension")

    def test_yaml_contains_expected_connection_count(self):
        """Test that YAML contains correct number of Connection CRDs"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Parse YAML content
        import yaml
        content = response.content.decode('utf-8')
        documents = list(yaml.safe_load_all(content))

        # Expected: 2 servers × 2 ports/connection = 4 Connection CRDs
        connection_crds = [doc for doc in documents if doc and doc.get('kind') == 'Connection']
        self.assertEqual(len(connection_crds), 4,
                        f"Expected 4 Connection CRDs (2 servers × 2 ports), got {len(connection_crds)}")

        # Verify each connection has required fields
        for crd in connection_crds:
            self.assertEqual(crd['apiVersion'], 'wiring.githedgehog.com/v1beta1',
                           "Connection should have correct apiVersion")
            self.assertIn('metadata', crd,
                         "Connection should have metadata")
            self.assertIn('name', crd['metadata'],
                         "Connection should have name")
            self.assertIn('spec', crd,
                         "Connection should have spec")

    def test_yaml_reflects_plan_state_changes(self):
        """Test that re-exporting after plan changes reflects new state"""
        # Initial export
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, 200)

        import yaml
        content1 = response1.content.decode('utf-8')
        docs1 = list(yaml.safe_load_all(content1))
        connections1 = [d for d in docs1 if d and d.get('kind') == 'Connection']
        initial_count = len(connections1)

        # Modify plan: change server quantity from 2 to 3
        self.server_class.quantity = 3
        self.server_class.save()

        # Re-export
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, 200)

        content2 = response2.content.decode('utf-8')
        docs2 = list(yaml.safe_load_all(content2))
        connections2 = [d for d in docs2 if d and d.get('kind') == 'Connection']
        new_count = len(connections2)

        # Should have 3 servers × 2 ports = 6 connections now (was 4)
        self.assertEqual(new_count, 6,
                        f"After increasing servers to 3, expected 6 connections, got {new_count}")
        self.assertNotEqual(initial_count, new_count,
                           "Connection count should change after modifying plan")

    def test_no_duplicate_switch_ports(self):
        """Test that port allocator doesn't assign duplicate switch ports"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        import yaml
        content = response.content.decode('utf-8')
        documents = list(yaml.safe_load_all(content))
        connection_crds = [doc for doc in documents if doc and doc.get('kind') == 'Connection']

        # Extract all switch ports from connections
        switch_ports = []
        for crd in connection_crds:
            spec = crd.get('spec', {})
            # Handle different connection types (unbundled, bundled, mclag, eslag)
            if 'unbundled' in spec:
                link = spec['unbundled'].get('link', {})
                switch_port = link.get('switch', {}).get('port', '')
                if switch_port:
                    switch_ports.append(switch_port)
            elif 'bundled' in spec:
                for link in spec['bundled'].get('links', []):
                    switch_port = link.get('switch', {}).get('port', '')
                    if switch_port:
                        switch_ports.append(switch_port)
            elif 'mclag' in spec:
                for link in spec['mclag'].get('links', []):
                    switch_port = link.get('switch', {}).get('port', '')
                    if switch_port:
                        switch_ports.append(switch_port)

        # Check for duplicates
        unique_ports = set(switch_ports)
        self.assertEqual(len(switch_ports), len(unique_ports),
                        f"Found duplicate switch ports: {[p for p in switch_ports if switch_ports.count(p) > 1]}")

    def test_export_without_permission_fails(self):
        """Test that user without view permission cannot export"""
        # Create non-superuser without permissions
        regular_user = User.objects.create_user(
            username='regular',
            password='regular123',
            is_staff=True,
            is_superuser=False
        )

        # Login as regular user
        self.client.logout()
        self.client.login(username='regular', password='regular123')

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        # Should get 403 Forbidden
        self.assertEqual(response.status_code, 403,
                        "User without view permission should get 403")

    def test_export_with_permission_succeeds(self):
        """Test that user with view permission can export"""
        from users.models import ObjectPermission

        # Create non-superuser
        regular_user = User.objects.create_user(
            username='regular',
            password='regular123',
            is_staff=True,
            is_superuser=False
        )

        # Grant view permission
        obj_perm = ObjectPermission.objects.create(
            name='Test view topologyplan permission',
            actions=['view']
        )
        obj_perm.object_types.add(
            ContentType.objects.get_for_model(TopologyPlan)
        )
        obj_perm.users.add(regular_user)

        # Login as regular user
        self.client.logout()
        self.client.force_login(regular_user)

        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200,
                        "User with view permission should be able to export")

    def test_yaml_is_syntactically_valid(self):
        """Test that exported YAML is syntactically valid"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        import yaml
        content = response.content.decode('utf-8')

        # Should parse without errors
        try:
            documents = list(yaml.safe_load_all(content))
            self.assertGreater(len(documents), 0,
                             "YAML should contain at least one document")
        except yaml.YAMLError as e:
            self.fail(f"YAML is not syntactically valid: {e}")


class YAMLExportMCLAGTestCase(TestCase):
    """Integration tests for YAML export with MCLAG connections"""

    @classmethod
    def setUpTestData(cls):
        """Create test data with MCLAG configuration"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        # Create plan
        cls.plan = TopologyPlan.objects.create(
            name='MCLAG Test Plan',
            created_by=cls.user
        )

        # Create manufacturers and device types
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='NVIDIA',
            defaults={'slug': 'nvidia'}
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='DGX-H100',
            defaults={'slug': 'dgx-h100'}
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='SN5600',
            defaults={'slug': 'sn5600'}
        )

        # Create MCLAG-capable device extension
        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_type,
            defaults={
                'mclag_capable': True,
                'hedgehog_roles': ['server-leaf'],
                'native_speed': 800,
                'uplink_ports': 4,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g']
            }
        )

        # Create server class
        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='DGX-001',
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            gpus_per_server=8,
            server_device_type=cls.server_type
        )

        # Create switch class with MCLAG pairing
        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=4,
            mclag_pair=True,
            calculated_quantity=2  # MCLAG pair
        )

        # Create MCLAG connection (2 ports, alternating between MCLAG pair)
        cls.connection = PlanServerConnection.objects.create(
            server_class=cls.server_class,
            connection_id='FE-MCLAG',
            connection_name='frontend-mclag',
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.MCLAG,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_switch_class=cls.switch_class,
            speed=200
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_mclag_connections_generated_correctly(self):
        """Test that MCLAG connections are generated with correct structure"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        import yaml
        content = response.content.decode('utf-8')
        documents = list(yaml.safe_load_all(content))
        connection_crds = [doc for doc in documents if doc and doc.get('kind') == 'Connection']

        # Should have MCLAG connections
        mclag_connections = [c for c in connection_crds if 'mclag' in c.get('spec', {})]
        self.assertGreater(len(mclag_connections), 0,
                          "Should generate MCLAG connection CRDs")

        # Verify MCLAG structure
        for crd in mclag_connections:
            spec = crd['spec']
            self.assertIn('mclag', spec,
                         "MCLAG connection should have mclag spec")
            self.assertIn('links', spec['mclag'],
                         "MCLAG spec should have links array")
            self.assertEqual(len(spec['mclag']['links']), 2,
                           "MCLAG should have 2 links (one per switch in pair)")
