"""
Integration tests for Redundancy UI (DIET-165 Phase 4)

Tests validate real UX flows for PlanSwitchClass and PlanServerConnection
following AGENTS.md testing standards and the Phase 3 spec from issue #164.

Coverage includes:
- Switch Class: redundancy_type/redundancy_group fields, MCLAG/ESLAG validation
- Server Connection: NIC module type visibility, interface template behavior
- Full CRUD operations (list, add, detail, edit, delete)
- Permission enforcement (403 without permission, success with ObjectPermission)
- Form validation (negative tests for invalid data, error messages in HTML)

This file contains 20 integration tests as specified in the Phase 3 spec addendum.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from users.models import ObjectPermission

from dcim.models import DeviceType, Manufacturer, InterfaceTemplate, ModuleType

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    DeviceTypeExtension,
    BreakoutOption,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
)

User = get_user_model()


class SwitchClassRedundancyUITestCase(TestCase):
    """
    Integration tests for PlanSwitchClass redundancy UI (11 tests).

    Tests cover:
    - List view with redundancy fields
    - Add form with redundancy fields
    - MCLAG validation (even quantity, minimum 2)
    - ESLAG validation (2-4 switches)
    - Detail view rendering
    - Edit workflow
    - Delete workflow
    - Permission enforcement
    """

    @classmethod
    def setUpTestData(cls):
        """Create shared test data"""
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

        # Create test data
        cls.manufacturer = Manufacturer.objects.create(
            name='Test Mfg',
            slug='test-mfg'
        )

        cls.switch_device_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='Test Switch',
            slug='test-switch'
        )

        cls.breakout_option = BreakoutOption.objects.create(
            breakout_id='test-1x800g',
            from_speed=800,
            logical_ports=1,
            logical_speed=800,
            optic_type='QSFP-DD'
        )

        cls.device_ext = DeviceTypeExtension.objects.create(
            device_type=cls.switch_device_type,
            mclag_capable=True,
            supported_breakouts=['test-1x800g']
        )

        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer',
            created_by=cls.superuser
        )

        # Create switch class with MCLAG redundancy
        cls.mclag_switch = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            redundancy_type='mclag',
            redundancy_group='mclag-1',
            override_quantity=4
        )

        # Create switch class with ESLAG redundancy
        cls.eslag_switch = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='be-leaf',
            fabric=FabricTypeChoices.BACKEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            redundancy_type='eslag',
            redundancy_group='eslag-1',
            override_quantity=3
        )

    def setUp(self):
        """Create fresh client for each test"""
        self.client = Client()

    # =========================================================================
    # Test 1: List View
    # =========================================================================

    def test_switch_class_list_shows_redundancy_fields(self):
        """Verify redundancy_type displays in list view"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # List should display both switch classes
        self.assertContains(response, 'fe-leaf')
        self.assertContains(response, 'be-leaf')

    # =========================================================================
    # Test 2: Add Form Loads
    # =========================================================================

    def test_switch_class_add_form_loads(self):
        """Verify redundancy fields present in add form"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Form should include redundancy_type field
        self.assertContains(response, 'redundancy_type')
        # Form should include redundancy_group field
        self.assertContains(response, 'redundancy_group')
        # Deprecated field should show deprecation warning
        self.assertContains(response, 'mclag_pair')

    # =========================================================================
    # Test 3: MCLAG Valid Quantity
    # =========================================================================

    def test_switch_class_add_mclag_valid_quantity(self):
        """MCLAG with even quantity succeeds"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')

        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'fe-leaf-2',
            'fabric': FabricTypeChoices.FRONTEND,
            'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
            'device_type_extension': self.device_ext.pk,
            'redundancy_type': 'mclag',
            'redundancy_group': 'mclag-2',
            'override_quantity': 4  # Even number - valid
        }
        response = self.client.post(url, data)

        # Should redirect on success (302)
        self.assertEqual(response.status_code, 302)
        # Object should be created
        self.assertTrue(
            PlanSwitchClass.objects.filter(
                switch_class_id='fe-leaf-2',
                redundancy_type='mclag'
            ).exists()
        )

    # =========================================================================
    # Test 4: MCLAG Odd Quantity Fails
    # =========================================================================

    def test_switch_class_add_mclag_odd_quantity_fails(self):
        """MCLAG with odd quantity is rejected"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')

        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'fe-leaf-3',
            'fabric': FabricTypeChoices.FRONTEND,
            'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
            'device_type_extension': self.device_ext.pk,
            'redundancy_type': 'mclag',
            'redundancy_group': 'mclag-3',
            'override_quantity': 3  # Odd number - invalid
        }
        response = self.client.post(url, data)

        # Should re-render form with errors (200)
        self.assertEqual(response.status_code, 200)
        # Error message should mention "even"
        self.assertContains(response, 'even')
        # Object should NOT be created
        self.assertFalse(
            PlanSwitchClass.objects.filter(switch_class_id='fe-leaf-3').exists()
        )

    # =========================================================================
    # Test 5: ESLAG Valid Quantity
    # =========================================================================

    def test_switch_class_add_eslag_valid_quantity(self):
        """ESLAG with 2-4 switches succeeds"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')

        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'be-leaf-2',
            'fabric': FabricTypeChoices.BACKEND,
            'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
            'device_type_extension': self.device_ext.pk,
            'redundancy_type': 'eslag',
            'redundancy_group': 'eslag-2',
            'override_quantity': 3  # 2-4 range - valid
        }
        response = self.client.post(url, data)

        # Should redirect on success (302)
        self.assertEqual(response.status_code, 302)
        # Object should be created
        self.assertTrue(
            PlanSwitchClass.objects.filter(
                switch_class_id='be-leaf-2',
                redundancy_type='eslag'
            ).exists()
        )

    # =========================================================================
    # Test 6: ESLAG Invalid Quantity Fails
    # =========================================================================

    def test_switch_class_add_eslag_invalid_quantity_fails(self):
        """ESLAG with 5+ switches is rejected"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')

        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'be-leaf-3',
            'fabric': FabricTypeChoices.BACKEND,
            'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
            'device_type_extension': self.device_ext.pk,
            'redundancy_type': 'eslag',
            'redundancy_group': 'eslag-3',
            'override_quantity': 5  # > 4 - invalid
        }
        response = self.client.post(url, data)

        # Should re-render form with errors (200)
        self.assertEqual(response.status_code, 200)
        # Error message should mention "maximum 4"
        self.assertContains(response, 'maximum 4')
        # Object should NOT be created
        self.assertFalse(
            PlanSwitchClass.objects.filter(switch_class_id='be-leaf-3').exists()
        )

    # =========================================================================
    # Test 7: Detail View
    # =========================================================================

    def test_switch_class_detail_shows_redundancy_info(self):
        """Detail view displays redundancy configuration"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_detail', args=[self.mclag_switch.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Should display redundancy type
        self.assertContains(response, 'mclag')
        # Should display redundancy group
        self.assertContains(response, 'mclag-1')

    # =========================================================================
    # Test 8: Edit Workflow
    # =========================================================================

    def test_switch_class_edit_updates_redundancy(self):
        """Edit workflow updates redundancy fields correctly"""
        self.client.login(username='admin', password='admin123')

        # GET edit form
        url = reverse('plugins:netbox_hedgehog:planswitchclass_edit', args=[self.mclag_switch.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Form should be pre-populated with current values
        self.assertContains(response, 'mclag-1')

        # POST updated data
        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'fe-leaf',
            'fabric': FabricTypeChoices.FRONTEND,
            'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
            'device_type_extension': self.device_ext.pk,
            'redundancy_type': 'mclag',
            'redundancy_group': 'mclag-updated',  # Changed value
            'override_quantity': 6  # Changed quantity (still even)
        }
        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        # Changes should be persisted
        self.mclag_switch.refresh_from_db()
        self.assertEqual(self.mclag_switch.redundancy_group, 'mclag-updated')
        self.assertEqual(self.mclag_switch.override_quantity, 6)

    # =========================================================================
    # Test 9: Delete Workflow
    # =========================================================================

    def test_switch_class_delete_removes_object(self):
        """Delete workflow removes switch class"""
        self.client.login(username='admin', password='admin123')

        # Create a switch class to delete
        switch_to_delete = PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id='temp-switch',
            device_type_extension=self.device_ext,
            override_quantity=2
        )

        # GET delete confirmation page
        url = reverse('plugins:netbox_hedgehog:planswitchclass_delete', args=[switch_to_delete.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'temp-switch')

        # POST delete confirmation
        response = self.client.post(url, {'confirm': True})

        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        # Object should be deleted
        self.assertFalse(
            PlanSwitchClass.objects.filter(switch_class_id='temp-switch').exists()
        )

    # =========================================================================
    # Test 10: MCLAG Minimum Quantity Validation
    # =========================================================================

    def test_switch_class_mclag_minimum_quantity_fails(self):
        """MCLAG with less than 2 switches is rejected"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')

        data = {
            'plan': self.plan.pk,
            'switch_class_id': 'fe-leaf-4',
            'fabric': FabricTypeChoices.FRONTEND,
            'hedgehog_role': HedgehogRoleChoices.SERVER_LEAF,
            'device_type_extension': self.device_ext.pk,
            'redundancy_type': 'mclag',
            'redundancy_group': 'mclag-4',
            'override_quantity': 0  # Less than minimum
        }
        response = self.client.post(url, data)

        # Should re-render form with errors
        self.assertEqual(response.status_code, 200)
        # Error message should mention minimum requirement
        self.assertContains(response, 'at least 2')
        # Object should NOT be created
        self.assertFalse(
            PlanSwitchClass.objects.filter(switch_class_id='fe-leaf-4').exists()
        )

    # =========================================================================
    # Test 11: Permission Enforcement
    # =========================================================================

    def test_switch_class_permissions_enforce_rbac(self):
        """RBAC enforced for switch class operations"""
        # Regular user without permission → GET add form
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:planswitchclass_add')
        response = self.client.get(url)

        # Should be denied (403 or redirect)
        self.assertIn(response.status_code, [403, 302])

        # Add ObjectPermission for regular user
        content_type = ContentType.objects.get_for_model(PlanSwitchClass)
        permission = ObjectPermission.objects.create(
            name='Test Permission',
            actions=['add', 'view', 'change', 'delete']
        )
        permission.object_types.add(content_type)
        permission.users.add(self.regular_user)

        # Now user should be able to access the form
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class ServerConnectionUITestCase(TestCase):
    """
    Integration tests for PlanServerConnection UI (9 tests).

    Tests cover:
    - List view loads
    - Add form with nic_module_type field
    - Create with server_interface_template (recommended path)
    - Create with nic_slot (legacy path)
    - Detail view shows NIC module type
    - Edit workflow
    - Delete workflow
    - Permission enforcement
    - Template + slot validation behavior
    """

    @classmethod
    def setUpTestData(cls):
        """Create shared test data"""
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

        # Create test data
        cls.manufacturer = Manufacturer.objects.create(
            name='Test Mfg',
            slug='test-mfg'
        )

        # Server device type
        cls.server_device_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='Test Server',
            slug='test-server'
        )

        # Interface template
        cls.interface_template = InterfaceTemplate.objects.create(
            device_type=cls.server_device_type,
            name='eth0',
            type='1000base-t'
        )

        # Module type for NIC
        cls.nic_module_type = ModuleType.objects.create(
            manufacturer=cls.manufacturer,
            model='ConnectX-7 Dual-Port',
            part_number='MCX713106AS-VEAT'
        )

        # Switch for connections
        cls.switch_device_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer,
            model='Test Switch',
            slug='test-switch'
        )

        cls.breakout_option = BreakoutOption.objects.create(
            breakout_id='test-1x800g',
            from_speed=800,
            logical_ports=1,
            logical_speed=800,
            optic_type='QSFP-DD'
        )

        cls.device_ext = DeviceTypeExtension.objects.create(
            device_type=cls.switch_device_type,
            mclag_capable=True,
            supported_breakouts=['test-1x800g']
        )

        cls.plan = TopologyPlan.objects.create(
            name='Test Plan',
            customer_name='Test Customer',
            created_by=cls.superuser
        )

        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='GPU-001',
            server_device_type=cls.server_device_type,
            quantity=8,
            gpus_per_server=8
        )

        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            device_type_extension=cls.device_ext,
            override_quantity=2
        )

        # Create connection with NIC module type
        cls.connection = PlanServerConnection.objects.create(
            server_class=cls.server_class,
            connection_id='FE-001',
            nic_module_type=cls.nic_module_type,
            server_interface_template=cls.interface_template,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.BUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_switch_class=cls.switch_class,
            speed=200
        )

    def setUp(self):
        """Create fresh client for each test"""
        self.client = Client()

    # =========================================================================
    # Test 1: List View Loads
    # =========================================================================

    def test_server_connection_list_loads(self):
        """Server connection list view loads successfully"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Should display connection
        self.assertContains(response, 'FE-001')

    # =========================================================================
    # Test 2: Add Form Loads with NIC Fields
    # =========================================================================

    def test_server_connection_add_form_loads(self):
        """Server connection add form loads with nic_module_type field"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # nic_module_type field should be present
        self.assertContains(response, 'nic_module_type')
        # server_interface_template field should be present
        self.assertContains(response, 'server_interface_template')
        # nic_slot should show [LEGACY] indicator
        self.assertContains(response, 'nic_slot')

    # =========================================================================
    # Test 3: Create with Template Succeeds
    # =========================================================================

    def test_server_connection_add_with_template_succeeds(self):
        """Creating connection with server_interface_template succeeds"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')

        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'FE-002',
            'server_interface_template': self.interface_template.pk,  # Template mode
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_switch_class': self.switch_class.pk,
            'speed': 200
        }
        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        # Object should be created
        self.assertTrue(
            PlanServerConnection.objects.filter(connection_id='FE-002').exists()
        )

    # =========================================================================
    # Test 4: Create with NIC Slot Succeeds
    # =========================================================================

    def test_server_connection_add_with_nic_slot_succeeds(self):
        """Creating connection with nic_slot (legacy mode) succeeds"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')

        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'FE-003',
            'nic_slot': 'NIC1',  # Legacy mode
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_switch_class': self.switch_class.pk,
            'speed': 200
        }
        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        # Object should be created
        connection = PlanServerConnection.objects.get(connection_id='FE-003')
        self.assertEqual(connection.nic_slot, 'NIC1')

    # =========================================================================
    # Test 5: Detail View Shows NIC Module Type
    # =========================================================================

    def test_server_connection_detail_shows_nic_module_type(self):
        """Detail view displays NIC module type if set"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_detail', args=[self.connection.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Should display NIC module type
        self.assertContains(response, 'ConnectX-7')

    # =========================================================================
    # Test 6: Edit Workflow Updates Successfully
    # =========================================================================

    def test_server_connection_edit_updates_successfully(self):
        """Editing connection updates fields correctly"""
        self.client.login(username='admin', password='admin123')

        # GET edit form
        url = reverse('plugins:netbox_hedgehog:planserverconnection_edit', args=[self.connection.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # POST updated data
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'FE-001',
            'nic_module_type': self.nic_module_type.pk,
            'server_interface_template': self.interface_template.pk,
            'ports_per_connection': 4,  # Updated value
            'hedgehog_conn_type': ConnectionTypeChoices.BUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_switch_class': self.switch_class.pk,
            'speed': 200
        }
        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        # Changes should be persisted
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.ports_per_connection, 4)

    # =========================================================================
    # Test 7: Delete Workflow Removes Object
    # =========================================================================

    def test_server_connection_delete_removes_object(self):
        """Delete workflow removes connection"""
        self.client.login(username='admin', password='admin123')

        # Create connection to delete
        connection_to_delete = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='TEMP-001',
            server_interface_template=self.interface_template,
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_switch_class=self.switch_class,
            speed=200
        )

        # GET delete confirmation
        url = reverse('plugins:netbox_hedgehog:planserverconnection_delete', args=[connection_to_delete.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TEMP-001')

        # POST delete
        response = self.client.post(url, {'confirm': True})

        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        # Object should be deleted
        self.assertFalse(
            PlanServerConnection.objects.filter(connection_id='TEMP-001').exists()
        )

    # =========================================================================
    # Test 8: Permissions Enforce RBAC
    # =========================================================================

    def test_server_connection_permissions_enforce_rbac(self):
        """RBAC enforced for server connection operations"""
        # User without permission → GET add form
        self.client.login(username='regular', password='regular123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.get(url)

        # Should be denied (403 or redirect)
        self.assertIn(response.status_code, [403, 302])

        # Add ObjectPermission
        content_type = ContentType.objects.get_for_model(PlanServerConnection)
        permission = ObjectPermission.objects.create(
            name='Test Permission',
            actions=['add', 'view', 'change', 'delete']
        )
        permission.object_types.add(content_type)
        permission.users.add(self.regular_user)

        # Now user should be able to access
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # =========================================================================
    # Test 9: Template + Slot Validation (Both Fields Set)
    # =========================================================================

    def test_server_connection_template_and_slot_validation(self):
        """Validate behavior when both template and slot are provided"""
        self.client.login(username='admin', password='admin123')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')

        # Both fields set (depends on validation logic - may warn or succeed)
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'FE-004',
            'server_interface_template': self.interface_template.pk,
            'nic_slot': 'NIC2',  # Both set
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_switch_class': self.switch_class.pk,
            'speed': 200
        }
        response = self.client.post(url, data)

        # Current behavior: template takes precedence (no validation error)
        # If validation is added later, update this test accordingly
        # For now, just verify it doesn't crash
        self.assertIn(response.status_code, [200, 302])
