"""
Integration tests for PlanServerConnection NIC modeling UI (DIET-294).

Rewritten for new schema: nic FK replaces nic_module_type on PlanServerConnection.
All tests fail RED until GREEN implementation adds PlanServerNIC and updates
PlanServerConnection to use the nic FK.

11 tests covering AGENTS.md minimum UX-accurate flows.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from users.models import ObjectPermission

from dcim.models import DeviceType, Manufacturer, ModuleType, InterfaceTemplate

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan, PlanServerClass, PlanSwitchClass, PlanServerConnection,
    PlanServerNIC, DeviceTypeExtension, BreakoutOption, SwitchPortZone,
)
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices, FabricTypeChoices, HedgehogRoleChoices,
    ConnectionTypeChoices, ConnectionDistributionChoices,
    ServerClassCategoryChoices, PortZoneTypeChoices, AllocationStrategyChoices,
    FabricClassChoices,
)

User = get_user_model()


class NICModelingUITestCase(TestCase):
    """Integration tests for PlanServerConnection NIC modeling UI (11 tests)."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='nic-ui-admin', password='pass', is_staff=True, is_superuser=True,
        )
        cls.regular_user = User.objects.create_user(
            username='nic-ui-user', password='pass', is_staff=True, is_superuser=False,
        )
        cls.nvidia, _ = Manufacturer.objects.get_or_create(name='NVIDIA', defaults={'slug': 'nvidia'})
        cls.test_mfg, _ = Manufacturer.objects.get_or_create(name='UI-Test-Mfg', defaults={'slug': 'ui-test-mfg'})

        cls.bf3_type, bf3_created = ModuleType.objects.get_or_create(
            manufacturer=cls.nvidia, model='BlueField-3 BF3220',
        )
        if bf3_created:
            InterfaceTemplate.objects.get_or_create(
                module_type=cls.bf3_type, name='p0', defaults={'type': '200gbase-x-qsfp112'},
            )
            InterfaceTemplate.objects.get_or_create(
                module_type=cls.bf3_type, name='p1', defaults={'type': '200gbase-x-qsfp112'},
            )

        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.test_mfg, model='UI-SRV', defaults={'slug': 'ui-srv'},
        )
        cls.switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.test_mfg, model='UI-SW', defaults={'slug': 'ui-sw'},
        )
        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_dt,
            defaults={
                'native_speed': 200, 'uplink_ports': 4,
                'supported_breakouts': ['1x200g'], 'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
            },
        )
        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x200g-ui',
            defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
        )
        cls.plan = TopologyPlan.objects.create(name='NIC-UI-Plan', status=TopologyPlanStatusChoices.DRAFT)
        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan, server_class_id='gpu',
            server_device_type=cls.server_dt, quantity=1,
        )
        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan, switch_class_id='fe-leaf',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )
        cls.zone = SwitchPortZone.objects.create(
            switch_class=cls.switch_class, zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-64',
            breakout_option=cls.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )
        cls.nic = PlanServerNIC.objects.create(
            server_class=cls.server_class, nic_id='nic-fe', module_type=cls.bf3_type,
        )
        cls.connection = PlanServerConnection.objects.create(
            server_class=cls.server_class, connection_id='fe',
            nic=cls.nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=cls.zone, speed=200, port_type='data',
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='nic-ui-admin', password='pass')

    def test_list_view_displays_nic_slot_column(self):
        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # List should show NIC slot info, not nic_module_type
        content = response.content.decode()
        self.assertNotIn('nic_module_type', content)

    def test_add_form_shows_nic_dropdown_not_nic_module_type(self):
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.get(url + f'?server_class={self.server_class.pk}')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('name="nic"', content)
        self.assertNotIn('name="nic_module_type"', content)

    def test_valid_post_creates_connection_with_nic_fk(self):
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-new',
            'nic': self.nic.pk,
            'port_index': 1,
            'ports_per_connection': 1,
            'hedgehog_conn_type': 'unbundled',
            'distribution': 'alternating',
            'target_zone': self.zone.pk,
            'speed': 200,
            'port_type': 'data',
            'tags': [],
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        conn = PlanServerConnection.objects.get(connection_id='fe-new')
        self.assertEqual(conn.nic, self.nic)

    def test_validation_enforces_nic_required(self):
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-noNIC',
            'nic': '',
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': 'unbundled',
            'distribution': 'alternating',
            'target_zone': self.zone.pk,
            'speed': 200,
            'port_type': 'data',
            'tags': [],
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)  # form re-render
        self.assertFalse(PlanServerConnection.objects.filter(connection_id='fe-noNIC').exists())

    def test_validation_port_index_against_nic_module_type(self):
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-badport',
            'nic': self.nic.pk,
            'port_index': 99,  # BF3 only has p0, p1
            'ports_per_connection': 1,
            'hedgehog_conn_type': 'unbundled',
            'distribution': 'alternating',
            'target_zone': self.zone.pk,
            'speed': 200,
            'port_type': 'data',
            'tags': [],
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)  # form error
        self.assertFalse(PlanServerConnection.objects.filter(connection_id='fe-badport').exists())

    def test_validation_ports_per_connection_vs_available(self):
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-toomany',
            'nic': self.nic.pk,
            'port_index': 1,  # only port1 left; requesting 2 from index 1 → overflow
            'ports_per_connection': 99,
            'hedgehog_conn_type': 'unbundled',
            'distribution': 'alternating',
            'target_zone': self.zone.pk,
            'speed': 200,
            'port_type': 'data',
            'tags': [],
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlanServerConnection.objects.filter(connection_id='fe-toomany').exists())

    def test_detail_view_renders_nic_slot_and_transceiver_data(self):
        url = reverse('plugins:netbox_hedgehog:planserverconnection_detail', args=[self.connection.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'nic-fe')

    def test_edit_workflow_updates_nic_and_transceiver_fields(self):
        url = reverse('plugins:netbox_hedgehog:planserverconnection_edit', args=[self.connection.pk])
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe',
            'nic': self.nic.pk,
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': 'unbundled',
            'distribution': 'alternating',
            'target_zone': self.zone.pk,
            'speed': 200,
            'port_type': 'data',
            'cage_type': 'OSFP',
            'medium': 'SMF',
            'connector': '',
            'standard': '',
            'tags': [],
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.cage_type, 'OSFP')

    def test_delete_workflow_removes_connection(self):
        conn = PlanServerConnection.objects.create(
            server_class=self.server_class, connection_id='fe-todel',
            nic=self.nic, port_index=1, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=self.zone, speed=200, port_type='data',
        )
        url = reverse('plugins:netbox_hedgehog:planserverconnection_delete', args=[conn.pk])
        response = self.client.post(url, {'confirm': True})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlanServerConnection.objects.filter(pk=conn.pk).exists())

    def test_without_permission_returns_403(self):
        self.client.login(username='nic-ui-user', password='pass')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_with_objectpermission_succeeds(self):
        ct = ContentType.objects.get_for_model(PlanServerConnection)
        perm = ObjectPermission.objects.create(name='nic-ui-view', actions=['view'])
        perm.object_types.add(ct)
        perm.users.add(self.regular_user)
        self.client.login(username='nic-ui-user', password='pass')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
