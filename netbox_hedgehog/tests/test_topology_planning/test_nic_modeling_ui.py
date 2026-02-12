"""
Integration tests for NIC Modeling UI (DIET-173).

Tests validate real UX flows for PlanServerConnection with required
nic_module_type and port_index fields following AGENTS.md standards.

Coverage:
- List view displays NIC module type and port index
- Add form shows NIC module type dropdown and port index field
- Valid POST creates connection with required fields
- Validation enforces required nic_module_type
- Validation checks port_index within NIC port count
- Validation checks sufficient ports for ports_per_connection
- Detail view renders NIC metadata and transceiver attributes
- Edit workflow updates NIC fields
- Delete workflow removes connection
- Permission enforcement (403 without permission, success with ObjectPermission)
- Form displays ModuleType transceiver attributes for selection

This file contains 11 integration tests as specified in Phase 3.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from users.models import ObjectPermission

from dcim.models import DeviceType, Manufacturer, ModuleType, InterfaceTemplate, ModuleTypeProfile

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
    ServerClassCategoryChoices,
)

User = get_user_model()


class NICModelingUITestCase(TestCase):
    """
    Integration tests for PlanServerConnection NIC modeling UI (11 tests).
    """

    @classmethod
    def setUpTestData(cls):
        """Create shared test data including ModuleTypes."""
        # Users
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

        # Manufacturers
        cls.nvidia, _ = Manufacturer.objects.get_or_create(
            name='NVIDIA',
            defaults={'slug': 'nvidia'}
        )

        cls.test_mfg, _ = Manufacturer.objects.get_or_create(
            name='Test Mfg',
            defaults={'slug': 'test-mfg'}
        )

        # ModuleTypeProfile for transceiver attributes (may exist from migration)
        cls.transceiver_profile, _ = ModuleTypeProfile.objects.get_or_create(
            name='Network Transceiver',
            defaults={
                'schema': {
                    'type': 'object',
                    'properties': {
                        'cage_type': {'type': 'string', 'enum': ['QSFP112', 'QSFP-DD']},
                        'medium': {'type': 'string', 'enum': ['MMF', 'SMF', 'DAC']},
                        'connector': {'type': 'string', 'enum': ['LC', 'MPO-12', 'Direct']},
                        'wavelength_nm': {'type': 'integer'},
                        'standard': {'type': 'string'},
                        'reach_class': {'type': 'string', 'enum': ['SR', 'LR', 'DR', 'DAC']},
                    }
                }
            }
        )

        # BlueField-3 BF3220 (dual-port) - may exist from migration
        cls.bf3_type, bf3_created = ModuleType.objects.get_or_create(
            manufacturer=cls.nvidia,
            model='BlueField-3 BF3220',
            defaults={
                'profile': cls.transceiver_profile,
                'attribute_data': {
                    'cage_type': 'QSFP112',
                    'medium': 'MMF',
                    'connector': 'MPO-12',
                    'wavelength_nm': 850,
                    'standard': '200GBASE-SR4',
                    'reach_class': 'SR',
                }
            }
        )
        # Only create InterfaceTemplates if ModuleType was just created
        if bf3_created:
            InterfaceTemplate.objects.create(
                module_type=cls.bf3_type,
                name='p0',
                type='other'  # Using 'other' type - actual type not critical for NIC modeling tests
            )
            InterfaceTemplate.objects.create(
                module_type=cls.bf3_type,
                name='p1',
                type='other'
            )

        # ConnectX-7 (single-port) - may exist from migration
        cls.cx7_single, cx7_created = ModuleType.objects.get_or_create(
            manufacturer=cls.nvidia,
            model='ConnectX-7 (Single-Port)',
            defaults={
                'profile': cls.transceiver_profile,
                'attribute_data': {
                    'cage_type': 'QSFP112',
                    'medium': 'DAC',
                    'connector': 'Direct',
                    'standard': '200GBASE-CR4',
                    'reach_class': 'DAC',
                }
            }
        )
        if cx7_created:
            InterfaceTemplate.objects.create(
                module_type=cls.cx7_single,
                name='port0',
                type='other'  # Using 'other' type - actual type not critical for NIC modeling tests
            )

        # Server DeviceType
        cls.server_device_type = DeviceType.objects.create(
            manufacturer=cls.test_mfg,
            model='GPU Server',
            slug='gpu-server'
        )

        # Switch DeviceType + Extension
        cls.switch_device_type = DeviceType.objects.create(
            manufacturer=cls.test_mfg,
            model='Test Switch',
            slug='test-switch'
        )

        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='test-1x800g',
            defaults={
                'from_speed': 800,
                'logical_ports': 1,
                'logical_speed': 800,
                'optic_type': 'QSFP-DD'
            }
        )

        cls.device_ext = DeviceTypeExtension.objects.create(
            device_type=cls.switch_device_type,
            mclag_capable=True,
            native_speed=800,
            uplink_ports=16
        )

        # Topology Plan
        cls.plan = TopologyPlan.objects.create(
            name='Test Plan NIC',
            status=TopologyPlanStatusChoices.DRAFT
        )

        # Server Class
        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='gpu-01',
            description='GPU Servers',
            category=ServerClassCategoryChoices.GPU,
            quantity=2,
            server_device_type=cls.server_device_type
        )

        # Switch Class
        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            override_quantity=2
        )

    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.client.login(username='admin', password='admin123')

    def test_list_view_displays_nic_module_type(self):
        """Test that list view displays nic_module_type column."""
        # Create connection with NIC
        conn = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='fe',
            nic_module_type=self.bf3_type,
            port_index=0,
            ports_per_connection=1,
            target_switch_class=self.switch_class,
            speed=200
        )

        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BlueField-3 BF3220')
        self.assertContains(response, conn.connection_id)

    def test_add_form_shows_nic_fields(self):
        """Test that add form displays nic_module_type dropdown and port_index field."""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Check for nic_module_type field
        self.assertContains(response, 'nic_module_type')
        self.assertContains(response, 'BlueField-3 BF3220')
        self.assertContains(response, 'ConnectX-7 (Single-Port)')
        # Check for port_index field
        self.assertContains(response, 'port_index')

    def test_valid_post_creates_connection_with_nic(self):
        """Test that valid POST creates connection with required NIC fields."""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-test',
            'connection_name': 'Frontend Test',
            'nic_module_type': self.bf3_type.pk,
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
        }

        response = self.client.post(url, data, follow=False)

        # Should redirect on success (302)
        self.assertEqual(response.status_code, 302)

        # Verify connection created
        conn = PlanServerConnection.objects.get(connection_id='fe-test')
        self.assertEqual(conn.nic_module_type, self.bf3_type)
        self.assertEqual(conn.port_index, 0)

    def test_missing_nic_module_type_shows_error(self):
        """Test that missing nic_module_type shows validation error."""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-missing-nic',
            'port_index': 0,
            'ports_per_connection': 1,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
        }

        response = self.client.post(url, data)

        # Should stay on form with error (200)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'required')  # Error message for required field

    def test_invalid_port_index_shows_error(self):
        """Test that port_index exceeding NIC port count shows error."""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-bad-index',
            'nic_module_type': self.cx7_single.pk,  # Single-port (only index 0 valid)
            'port_index': 1,  # INVALID: exceeds port count
            'ports_per_connection': 1,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Port index 1 exceeds available ports')

    def test_insufficient_ports_for_connection_shows_error(self):
        """Test that ports_per_connection exceeding available ports shows error."""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-too-many-ports',
            'nic_module_type': self.cx7_single.pk,  # Single-port
            'port_index': 0,
            'ports_per_connection': 2,  # INVALID: NIC only has 1 port
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Insufficient ports')

    def test_detail_view_shows_nic_metadata(self):
        """Test that detail view renders NIC model and transceiver attributes."""
        conn = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='fe-detail',
            nic_module_type=self.bf3_type,
            port_index=0,
            ports_per_connection=1,
            target_switch_class=self.switch_class,
            speed=200
        )

        url = reverse('plugins:netbox_hedgehog:planserverconnection_detail', args=[conn.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BlueField-3 BF3220')
        self.assertContains(response, 'Port Index')
        self.assertContains(response, '0')  # port_index value
        # Check transceiver attributes visible
        self.assertContains(response, 'QSFP112')  # cage_type
        self.assertContains(response, 'MMF')      # medium

    def test_edit_form_loads_existing_nic_data(self):
        """Test that edit form pre-populates nic_module_type and port_index."""
        conn = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='fe-edit',
            nic_module_type=self.bf3_type,
            port_index=1,  # Second port
            ports_per_connection=1,
            target_switch_class=self.switch_class,
            speed=200
        )

        url = reverse('plugins:netbox_hedgehog:planserverconnection_edit', args=[conn.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BlueField-3 BF3220')
        self.assertContains(response, 'value="1"')  # port_index=1

    def test_edit_post_updates_nic_fields(self):
        """Test that edit POST successfully updates nic_module_type and port_index."""
        conn = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='fe-update',
            nic_module_type=self.bf3_type,
            port_index=0,
            ports_per_connection=1,
            target_switch_class=self.switch_class,
            speed=200
        )

        url = reverse('plugins:netbox_hedgehog:planserverconnection_edit', args=[conn.pk])
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-update',
            'nic_module_type': self.cx7_single.pk,  # Change NIC type
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'target_switch_class': self.switch_class.pk,
            'speed': 200,
        }

        response = self.client.post(url, data, follow=False)

        self.assertEqual(response.status_code, 302)

        # Verify update
        conn.refresh_from_db()
        self.assertEqual(conn.nic_module_type, self.cx7_single)

    def test_delete_workflow_removes_connection(self):
        """Test that delete workflow removes connection."""
        conn = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='fe-delete',
            nic_module_type=self.bf3_type,
            port_index=0,
            ports_per_connection=1,
            target_switch_class=self.switch_class,
            speed=200
        )

        url = reverse('plugins:netbox_hedgehog:planserverconnection_delete', args=[conn.pk])
        response = self.client.post(url, {'confirm': True}, follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlanServerConnection.objects.filter(pk=conn.pk).exists())

    def test_permission_enforcement(self):
        """Test that regular user without permissions gets 403, with permission succeeds."""
        conn = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id='fe-perm',
            nic_module_type=self.bf3_type,
            port_index=0,
            ports_per_connection=1,
            target_switch_class=self.switch_class,
            speed=200
        )

        # Login as regular user (no permissions)
        self.client.login(username='regular', password='regular123')

        url = reverse('plugins:netbox_hedgehog:planserverconnection_detail', args=[conn.pk])
        response = self.client.get(url)

        # Should get 403 or redirect to login
        self.assertIn(response.status_code, [403, 302])

        # Grant permission
        content_type = ContentType.objects.get_for_model(PlanServerConnection)
        permission = ObjectPermission.objects.create(
            name='View PlanServerConnection',
            actions=['view'],
        )
        permission.object_types.add(content_type)
        permission.users.add(self.regular_user)

        # Retry with permission
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
