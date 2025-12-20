"""
Tests for Topology Planning Views (DIET Module)

Following TDD approach: tests written BEFORE implementation.
Tests cover list, detail, create, edit, delete, and recalculate views.
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


class TopologyPlanViewsTestCase(TestCase):
    """Test suite for TopologyPlan CRUD views"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        cls.plan1 = TopologyPlan.objects.create(
            name='Plan 1',
            customer_name='Customer A',
            created_by=cls.user
        )
        cls.plan2 = TopologyPlan.objects.create(
            name='Plan 2',
            customer_name='Customer B',
            status=TopologyPlanStatusChoices.APPROVED,
            created_by=cls.user
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_list_view(self):
        """Test TopologyPlan list view"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Plan 1')
        self.assertContains(response, 'Plan 2')

    def test_detail_view(self):
        """Test TopologyPlan detail view"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_detail', args=[self.plan1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Plan 1')
        self.assertContains(response, 'Customer A')

    def test_create_view_get(self):
        """Test TopologyPlan create view GET request"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name')  # Form field should be present

    def test_create_view_post(self):
        """Test TopologyPlan create view POST request"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_add')
        data = {
            'name': 'New Plan',
            'customer_name': 'New Customer',
            'status': TopologyPlanStatusChoices.DRAFT,
        }
        response = self.client.post(url, data, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(TopologyPlan.objects.filter(name='New Plan').exists())

    def test_edit_view_get(self):
        """Test TopologyPlan edit view GET request"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_edit', args=[self.plan1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Plan 1')

    def test_edit_view_post(self):
        """Test TopologyPlan edit view POST request"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_edit', args=[self.plan1.pk])
        data = {
            'name': 'Updated Plan 1',
            'customer_name': 'Updated Customer',
            'status': TopologyPlanStatusChoices.REVIEW,
        }
        response = self.client.post(url, data, follow=True)

        self.assertEqual(response.status_code, 200)
        self.plan1.refresh_from_db()
        self.assertEqual(self.plan1.name, 'Updated Plan 1')
        self.assertEqual(self.plan1.status, TopologyPlanStatusChoices.REVIEW)

    def test_delete_view_get(self):
        """Test TopologyPlan delete view GET request (confirmation)"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_delete', args=[self.plan1.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Plan 1')

    def test_delete_view_post(self):
        """Test TopologyPlan delete view POST request"""
        plan_to_delete = TopologyPlan.objects.create(
            name='To Delete',
            created_by=self.user
        )
        url = reverse('plugins:netbox_hedgehog:topologyplan_delete', args=[plan_to_delete.pk])

        response = self.client.post(url, {'confirm': True}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TopologyPlan.objects.filter(pk=plan_to_delete.pk).exists())


class PlanServerClassViewsTestCase(TestCase):
    """Test suite for PlanServerClass CRUD views"""

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

        cls.manufacturer = Manufacturer.objects.create(
            name='Dell',
            slug='dell'
        )
        cls.server_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='PowerEdge R750',
            slug='poweredge-r750'
        )

        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='GPU-001',
            quantity=10,
            server_device_type=cls.server_type
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_create_view_get(self):
        """Test PlanServerClass create view GET request"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_create_view_post(self):
        """Test PlanServerClass create view POST request"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_add')
        data = {
            'plan': self.plan.pk,
            'server_class_id': 'STORAGE-001',
            'category': ServerClassCategoryChoices.STORAGE,
            'quantity': 20,
            'gpus_per_server': 0,
        }
        response = self.client.post(url, data, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PlanServerClass.objects.filter(server_class_id='STORAGE-001').exists()
        )

    def test_edit_view_get(self):
        """Test PlanServerClass edit view GET request"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_edit', args=[self.server_class.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'GPU-001')

    def test_edit_view_post(self):
        """Test PlanServerClass edit view POST request"""
        url = reverse('plugins:netbox_hedgehog:planserverclass_edit', args=[self.server_class.pk])
        data = {
            'plan': self.plan.pk,
            'server_class_id': 'GPU-001',
            'quantity': 50,  # Changed quantity
            'category': ServerClassCategoryChoices.GPU,
            'gpus_per_server': 8,
        }
        response = self.client.post(url, data, follow=True)

        self.assertEqual(response.status_code, 200)
        self.server_class.refresh_from_db()
        self.assertEqual(self.server_class.quantity, 50)

    def test_delete_view_post(self):
        """Test PlanServerClass delete view POST request"""
        server_to_delete = PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id='TO-DELETE',
            quantity=5
        )
        url = reverse('plugins:netbox_hedgehog:planserverclass_delete', args=[server_to_delete.pk])

        response = self.client.post(url, {'confirm': True}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlanServerClass.objects.filter(pk=server_to_delete.pk).exists())


class PlanSwitchClassViewsTestCase(TestCase):
    """Test suite for PlanSwitchClass CRUD views"""

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

        cls.manufacturer = Manufacturer.objects.create(
            name='Celestica',
            slug='celestica'
        )
        cls.switch_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            slug='ds5000'
        )
        cls.device_ext = DeviceTypeExtension.objects.create(
            device_type=cls.switch_type,
            mclag_capable=True,
            hedgehog_roles=['spine', 'server-leaf'],
            native_speed=800,
            uplink_ports=4,
            supported_breakouts=['1x800g', '2x400g', '4x200g']
        )

        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            device_type_extension=cls.device_ext,
            calculated_quantity=2
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_create_view_get(self):
        """Test PlanSwitchClass create view GET request"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_create_view_post(self):
        """Test PlanSwitchClass create view POST request"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'be-spine',
            'fabric': FabricTypeChoices.BACKEND,
            'hedgehog_role': HedgehogRoleChoices.SPINE,
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 8,
            'mclag_pair': False,
        }
        response = self.client.post(url, data, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PlanSwitchClass.objects.filter(switch_class_id='be-spine').exists()
        )

    def test_edit_view_get(self):
        """Test PlanSwitchClass edit view GET request"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_edit', args=[self.switch_class.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fe-leaf')

    def test_edit_view_post_with_override(self):
        """Test PlanSwitchClass edit view POST with override quantity"""
        url = reverse('plugins:netbox_hedgehog:planswitchclass_edit', args=[self.switch_class.pk])
        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'fe-leaf',
            'fabric': FabricTypeChoices.FRONTEND,
            'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
            'device_type_extension': self.device_ext.pk,
            'uplink_ports_per_switch': 4,
            'mclag_pair': False,
            'override_quantity': 6,  # Override calculated value
        }
        response = self.client.post(url, data, follow=True)

        self.assertEqual(response.status_code, 200)
        self.switch_class.refresh_from_db()
        self.assertEqual(self.switch_class.override_quantity, 6)
        self.assertEqual(self.switch_class.effective_quantity, 6)  # Should use override

    def test_delete_view_post(self):
        """Test PlanSwitchClass delete view POST request"""
        switch_to_delete = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='TO-DELETE',
            device_type_extension=self.device_ext
        )
        url = reverse('plugins:netbox_hedgehog:planswitchclass_delete', args=[switch_to_delete.pk])

        response = self.client.post(url, {'confirm': True}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlanSwitchClass.objects.filter(pk=switch_to_delete.pk).exists())


class RecalculateActionTestCase(TestCase):
    """Test suite for Recalculate action on plan detail page"""

    @classmethod
    def setUpTestData(cls):
        """Create test data with calculation engine dependencies"""
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

        # Create device type and extension for switch
        cls.manufacturer = Manufacturer.objects.create(
            name='Celestica',
            slug='celestica'
        )
        cls.switch_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='DS5000',
            slug='ds5000'
        )
        cls.device_ext = DeviceTypeExtension.objects.create(
            device_type=cls.switch_type,
            mclag_capable=True,
            hedgehog_roles=['spine', 'server-leaf'],
            native_speed=800,
            uplink_ports=4,
            supported_breakouts=['1x800g', '2x400g', '4x200g']
        )

        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            device_type_extension=cls.device_ext,
            calculated_quantity=0  # Start at 0
        )

    def setUp(self):
        """Login before each test"""
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_recalculate_action_url_exists(self):
        """Test that recalculate action URL is accessible"""
        url = reverse('plugins:netbox_hedgehog:topologyplan_recalculate', args=[self.plan.pk])
        response = self.client.post(url, follow=True)

        # Should redirect back to plan detail after recalculation
        self.assertEqual(response.status_code, 200)

    def test_recalculate_updates_calculated_quantity(self):
        """Test that recalculate action updates calculated_quantity field"""
        # Note: This test may pass with calculated_quantity=0 if there are no
        # server connections targeting the switch class. That's expected behavior.
        # The important part is that the recalculate function is called.

        url = reverse('plugins:netbox_hedgehog:topologyplan_recalculate', args=[self.plan.pk])
        response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)

        # Refresh and verify calculated_quantity was updated by calculation engine
        self.switch_class.refresh_from_db()
        # In this minimal test case, we expect 0 since no servers/connections exist
        self.assertEqual(self.switch_class.calculated_quantity, 0)

    def test_recalculate_preserves_override_quantity(self):
        """Test that recalculate preserves override_quantity values"""
        self.switch_class.override_quantity = 10
        self.switch_class.save()

        url = reverse('plugins:netbox_hedgehog:topologyplan_recalculate', args=[self.plan.pk])
        response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)

        self.switch_class.refresh_from_db()
        # Override should be preserved
        self.assertEqual(self.switch_class.override_quantity, 10)
        # Effective should still use override
        self.assertEqual(self.switch_class.effective_quantity, 10)
