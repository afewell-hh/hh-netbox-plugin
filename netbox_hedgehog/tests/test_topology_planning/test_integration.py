"""
Integration Tests for Topology Planning UI (DIET-004)

These tests verify the actual user experience by making real HTTP requests,
loading pages, submitting forms, and checking the full request/response cycle.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from dcim.models import DeviceType, Manufacturer

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
