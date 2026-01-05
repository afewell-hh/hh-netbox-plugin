"""
Integration Tests for Interface Template Reuse (Issue #138).

These tests verify that device generation reuses interface templates from
DeviceType instead of creating duplicate interfaces, and that UI/API flows
respect the new server_interface_template and legacy nic_slot modes.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from dcim.models import DeviceType, Manufacturer, Site, InterfaceTemplate, Device, Interface, CableTermination
from users.models import ObjectPermission

from netbox_hedgehog.api.serializers_simple import PlanServerConnectionSerializer
from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    DeviceTypeExtension,
    BreakoutOption,
    SwitchPortZone,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.choices import (
    TopologyPlanStatusChoices,
    ServerClassCategoryChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    PortZoneTypeChoices,
    AllocationStrategyChoices,
)

User = get_user_model()


def cable_terminations_for_interface(interface: Interface) -> int:
    content_type = ContentType.objects.get_for_model(Interface)
    return CableTermination.objects.filter(
        termination_type=content_type,
        termination_id=interface.pk,
    ).count()


class InterfaceReuseTestBase(TestCase):
    """Shared fixtures for interface reuse tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass',
            is_superuser=True,
        )

        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Test Manufacturer',
            defaults={'slug': 'test-manufacturer'},
        )

        cls.site, _ = Site.objects.get_or_create(
            name='Test Site',
            defaults={'slug': 'test-site'},
        )

        cls.server_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='Test-Server',
            defaults={'slug': 'test-server'},
        )

        cls.eth1_template, _ = InterfaceTemplate.objects.get_or_create(
            device_type=cls.server_device_type,
            name='eth1',
            defaults={'type': '200gbase-x-qsfp56'},
        )
        cls.eth2_template, _ = InterfaceTemplate.objects.get_or_create(
            device_type=cls.server_device_type,
            name='eth2',
            defaults={'type': '200gbase-x-qsfp56'},
        )

        cls.switch_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='Test-Switch',
            defaults={'slug': 'test-switch'},
        )

        cls.device_type_extension, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_device_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'supported_breakouts': ['4x200g', '2x400g'],
                'native_speed': 800,
                'uplink_ports': 0,
            },
        )

        cls.breakout_4x200, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={
                'from_speed': 800,
                'logical_ports': 4,
                'logical_speed': 200,
                'optic_type': 'QSFP-DD',
            },
        )

        cls.breakout_2x400, _ = BreakoutOption.objects.get_or_create(
            breakout_id='2x400g',
            defaults={
                'from_speed': 800,
                'logical_ports': 2,
                'logical_speed': 400,
                'optic_type': 'QSFP-DD',
            },
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def create_plan(self, name='Test Plan'):
        return TopologyPlan.objects.create(
            name=name,
            status=TopologyPlanStatusChoices.DRAFT,
        )

    def create_server_class(self, plan, server_device_type=None, server_class_id='srv', quantity=1):
        return PlanServerClass.objects.create(
            plan=plan,
            server_class_id=server_class_id,
            server_device_type=server_device_type or self.server_device_type,
            category=ServerClassCategoryChoices.GPU,
            quantity=quantity,
            gpus_per_server=8,
        )

    def create_switch_class(
        self,
        plan,
        switch_class_id='leaf',
        breakout=None,
        port_spec='1-8',
        zone_type=PortZoneTypeChoices.SERVER,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
        priority=100,
    ):
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id=switch_class_id,
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_type_extension,
            uplink_ports_per_switch=0,
            mclag_pair=False,
            calculated_quantity=1,
        )

        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-ports',
            zone_type=zone_type,
            port_spec=port_spec,
            breakout_option=breakout or self.breakout_4x200,
            allocation_strategy=allocation_strategy,
            priority=priority,
        )
        return switch_class


class ServerInterfaceAssignmentTestCase(InterfaceReuseTestBase):
    """Category 1: Server Interface Assignment (3 tests)."""

    def test_single_port_connection_uses_existing_interface(self):
        plan = self.create_plan('Single Port Assignment')
        server_class = self.create_server_class(plan, server_class_id='srv-single')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-single')

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            server_interface_template=self.eth1_template,
            nic_slot='',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
        )

        result = DeviceGenerator(plan=plan, site=self.site).generate_all()
        self.assertEqual(result.device_count, 2)

        server_device = Device.objects.get(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
            custom_field_data__hedgehog_class='srv-single',
        )

        interface_names = set(server_device.interfaces.values_list('name', flat=True))
        self.assertEqual(interface_names, {'eth1', 'eth2'})

        eth1 = server_device.interfaces.get(name='eth1')
        eth2 = server_device.interfaces.get(name='eth2')
        self.assertEqual(cable_terminations_for_interface(eth1), 1)
        self.assertEqual(cable_terminations_for_interface(eth2), 0)

    def test_multi_port_connection_uses_sequential_interfaces(self):
        device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=self.manufacturer,
            model='Test-Server-BE',
            defaults={'slug': 'test-server-be'},
        )
        InterfaceTemplate.objects.get_or_create(
            device_type=device_type,
            name='eth1',
            defaults={'type': '200gbase-x-qsfp56'},
        )
        InterfaceTemplate.objects.get_or_create(
            device_type=device_type,
            name='eth2',
            defaults={'type': '200gbase-x-qsfp56'},
        )
        for index in range(1, 9):
            InterfaceTemplate.objects.get_or_create(
                device_type=device_type,
                name=f'cx7-{index}',
                defaults={'type': '400gbase-x-qsfpdd'},
            )

        plan = self.create_plan('Multi Port Assignment')
        server_class = self.create_server_class(plan, server_device_type=device_type, server_class_id='srv-multi')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-multi', breakout=self.breakout_2x400)

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='be-rail-0',
            server_interface_template=InterfaceTemplate.objects.get(
                device_type=device_type,
                name='cx7-1',
            ),
            nic_slot='',
            ports_per_connection=4,
            target_switch_class=switch_class,
            speed=400,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
        )

        DeviceGenerator(plan=plan, site=self.site).generate_all()
        server_device = Device.objects.get(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
            custom_field_data__hedgehog_class='srv-multi',
        )

        for index in range(1, 5):
            iface = server_device.interfaces.get(name=f'cx7-{index}')
            self.assertEqual(cable_terminations_for_interface(iface), 1)

        for index in range(5, 9):
            iface = server_device.interfaces.get(name=f'cx7-{index}')
            self.assertEqual(cable_terminations_for_interface(iface), 0)

    def test_interface_sequence_natural_sorting(self):
        device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=self.manufacturer,
            model='Test-Server-12NIC',
            defaults={'slug': 'test-server-12nic'},
        )
        InterfaceTemplate.objects.filter(device_type=device_type).delete()
        for name in ['cx7-1', 'cx7-10', 'cx7-11', 'cx7-12', 'cx7-2', 'cx7-3',
                     'cx7-4', 'cx7-5', 'cx7-6', 'cx7-7', 'cx7-8', 'cx7-9']:
            InterfaceTemplate.objects.create(
                device_type=device_type,
                name=name,
                type='400gbase-x-qsfpdd',
            )

        plan = self.create_plan('Natural Sort Assignment')
        server_class = self.create_server_class(plan, server_device_type=device_type, server_class_id='srv-sort')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-sort', breakout=self.breakout_2x400)

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='sort-conn',
            server_interface_template=InterfaceTemplate.objects.get(device_type=device_type, name='cx7-8'),
            nic_slot='',
            ports_per_connection=4,
            target_switch_class=switch_class,
            speed=400,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
        )

        DeviceGenerator(plan=plan, site=self.site).generate_all()
        server_device = Device.objects.get(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
            custom_field_data__hedgehog_class='srv-sort',
        )

        for expected_name in ['cx7-8', 'cx7-9', 'cx7-10', 'cx7-11']:
            iface = server_device.interfaces.get(name=expected_name)
            self.assertEqual(cable_terminations_for_interface(iface), 1)

        cx7_12 = server_device.interfaces.get(name='cx7-12')
        self.assertEqual(cable_terminations_for_interface(cx7_12), 0)


class ValidationTestCase(InterfaceReuseTestBase):
    """Category 2: Validation (6 tests)."""

    def test_validation_insufficient_interfaces(self):
        plan = self.create_plan('Validation Insufficient')
        server_class = self.create_server_class(plan, server_class_id='srv-insufficient')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-insufficient')

        connection = PlanServerConnection(
            server_class=server_class,
            connection_id='bad',
            server_interface_template=self.eth2_template,
            nic_slot='',
            ports_per_connection=2,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
        )

        with self.assertRaises(ValidationError) as exc:
            connection.clean()

        self.assertIn('ports_per_connection', exc.exception.message_dict)

    def test_validation_wrong_device_type(self):
        other_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=self.manufacturer,
            model='Other-Server',
            defaults={'slug': 'other-server'},
        )
        other_template, _ = InterfaceTemplate.objects.get_or_create(
            device_type=other_device_type,
            name='eth1',
            defaults={'type': '200gbase-x-qsfp56'},
        )

        plan = self.create_plan('Validation Wrong Type')
        server_class = self.create_server_class(plan, server_class_id='srv-wrong')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-wrong')

        connection = PlanServerConnection(
            server_class=server_class,
            connection_id='bad-type',
            server_interface_template=other_template,
            nic_slot='',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
        )

        with self.assertRaises(ValidationError) as exc:
            connection.clean()

        self.assertIn('server_interface_template', exc.exception.message_dict)

    def test_validation_missing_template_and_nic_slot(self):
        plan = self.create_plan('Validation Missing')
        server_class = self.create_server_class(plan, server_class_id='srv-missing')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-missing')

        connection = PlanServerConnection(
            server_class=server_class,
            connection_id='missing',
            server_interface_template=None,
            nic_slot='',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
        )

        with self.assertRaises(ValidationError) as exc:
            connection.clean()

        self.assertIn('server_interface_template', exc.exception.message_dict)

    def test_validation_accepts_template_only(self):
        plan = self.create_plan('Validation Template Only')
        server_class = self.create_server_class(plan, server_class_id='srv-template')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-template')

        connection = PlanServerConnection(
            server_class=server_class,
            connection_id='valid-template',
            server_interface_template=self.eth1_template,
            nic_slot='',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
        )

        connection.clean()

    def test_validation_accepts_nic_slot_only(self):
        plan = self.create_plan('Validation Legacy Only')
        server_class = self.create_server_class(plan, server_class_id='srv-legacy')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-legacy')

        connection = PlanServerConnection(
            server_class=server_class,
            connection_id='valid-legacy',
            server_interface_template=None,
            nic_slot='eth',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
        )

        connection.clean()

    def test_deleted_template_falls_back_to_legacy(self):
        plan = self.create_plan('Validation Deleted Template')
        server_class = self.create_server_class(plan, server_class_id='srv-deleted')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-deleted')

        template, _ = InterfaceTemplate.objects.get_or_create(
            device_type=self.server_device_type,
            name='eth-delete',
            defaults={'type': '200gbase-x-qsfp56'},
        )

        connection = PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='deleted-template',
            server_interface_template=template,
            nic_slot='legacy',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
        )

        template.delete()
        connection.refresh_from_db()
        self.assertIsNone(connection.server_interface_template)
        connection.clean()


class SwitchInterfaceGenerationTestCase(InterfaceReuseTestBase):
    """Category 3: Switch Interface Generation (3 tests)."""

    def test_switch_interfaces_use_e1_naming(self):
        plan = self.create_plan('Switch Naming')
        server_class = self.create_server_class(plan, server_class_id='srv-switch')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-switch', port_spec='1-2')

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            server_interface_template=self.eth1_template,
            nic_slot='',
            ports_per_connection=2,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
        )

        DeviceGenerator(plan=plan, site=self.site).generate_all()

        switch_device = Device.objects.get(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
            custom_field_data__hedgehog_class='leaf-switch',
        )

        for iface in switch_device.interfaces.all():
            self.assertRegex(iface.name, r'^E1/\d+(?:/\d+)?$')

    def test_switch_breakout_interface_naming(self):
        plan = self.create_plan('Switch Breakout Naming')
        server_class = self.create_server_class(plan, server_class_id='srv-breakout')
        switch_class = self.create_switch_class(
            plan,
            switch_class_id='leaf-breakout',
            breakout=self.breakout_2x400,
            port_spec='1',
        )

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='be',
            server_interface_template=self.eth1_template,
            nic_slot='',
            ports_per_connection=2,
            target_switch_class=switch_class,
            speed=400,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
        )

        DeviceGenerator(plan=plan, site=self.site).generate_all()

        switch_device = Device.objects.get(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
            custom_field_data__hedgehog_class='leaf-breakout',
        )

        names = set(switch_device.interfaces.values_list('name', flat=True))
        self.assertIn('E1/1/1', names)
        self.assertIn('E1/1/2', names)

    def test_seed_command_creates_e1_templates_isolated(self):
        test_manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Seed Test Manufacturer',
            defaults={'slug': 'seed-test-manufacturer'},
        )
        device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=test_manufacturer,
            model='Seed-Test-Switch',
            defaults={'slug': 'seed-test-switch'},
        )
        InterfaceTemplate.objects.filter(device_type=device_type).delete()
        for index in range(1, 65):
            InterfaceTemplate.objects.create(
                device_type=device_type,
                name=f'E1/{index}',
                type='800gbase-x-qsfpdd',
            )

        templates = InterfaceTemplate.objects.filter(device_type=device_type)
        self.assertEqual(templates.count(), 64)
        self.assertEqual(templates.filter(name__startswith='Ethernet1/').count(), 0)


class InterfaceTypesTestCase(InterfaceReuseTestBase):
    """Category 4: Interface Types (2 tests)."""

    def test_switch_interfaces_use_speed_based_type(self):
        plan = self.create_plan('Switch Type Mapping')
        server_class = self.create_server_class(plan, server_class_id='srv-type')
        switch_class = self.create_switch_class(
            plan,
            switch_class_id='leaf-type',
            breakout=self.breakout_2x400,
            port_spec='1',
        )

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='be',
            server_interface_template=self.eth1_template,
            nic_slot='',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=400,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
        )

        DeviceGenerator(plan=plan, site=self.site).generate_all()
        switch_device = Device.objects.get(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
            custom_field_data__hedgehog_class='leaf-type',
        )
        iface = switch_device.interfaces.first()
        self.assertEqual(iface.type, '400gbase-x-qsfpdd')

    def test_server_interface_type_preserved_from_template(self):
        plan = self.create_plan('Server Type Preserve')
        server_class = self.create_server_class(plan, server_class_id='srv-template-type')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-template-type')

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            server_interface_template=self.eth1_template,
            nic_slot='',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
        )

        DeviceGenerator(plan=plan, site=self.site).generate_all()
        server_device = Device.objects.get(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
            custom_field_data__hedgehog_class='srv-template-type',
        )
        eth1 = server_device.interfaces.get(name='eth1')
        self.assertEqual(eth1.type, '200gbase-x-qsfp56')


class APIIntegrationTestCase(InterfaceReuseTestBase):
    """Category 5: API Integration (3 tests)."""

    def test_api_can_set_interface_template(self):
        plan = self.create_plan('API Set Template')
        server_class = self.create_server_class(plan, server_class_id='srv-api')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-api')

        serializer = PlanServerConnectionSerializer(data={
            'server_class': server_class.pk,
            'connection_id': 'api-conn',
            'server_interface_template': self.eth1_template.pk,
            'nic_slot': '',
            'ports_per_connection': 1,
            'target_switch_class': switch_class.pk,
            'speed': 200,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.SAME_SWITCH,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        obj = serializer.save()
        self.assertEqual(obj.server_interface_template, self.eth1_template)

    def test_api_returns_interface_template(self):
        plan = self.create_plan('API Return Template')
        server_class = self.create_server_class(plan, server_class_id='srv-api-ret')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-api-ret')

        connection = PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='api-return',
            server_interface_template=self.eth1_template,
            nic_slot='',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
        )
        data = PlanServerConnectionSerializer(connection).data
        self.assertEqual(data['server_interface_template'], self.eth1_template.pk)

    def test_api_validation_errors_insufficient_interfaces(self):
        plan = self.create_plan('API Validate Errors')
        server_class = self.create_server_class(plan, server_class_id='srv-api-bad')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-api-bad')

        serializer = PlanServerConnectionSerializer(data={
            'server_class': server_class.pk,
            'connection_id': 'api-bad',
            'server_interface_template': self.eth2_template.pk,
            'nic_slot': '',
            'ports_per_connection': 2,
            'target_switch_class': switch_class.pk,
            'speed': 200,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.SAME_SWITCH,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('ports_per_connection', serializer.errors)


class LegacyFallbackTestCase(InterfaceReuseTestBase):
    """Category 6: Legacy Fallback (1 test)."""

    def test_legacy_nic_slot_naming_used(self):
        plan = self.create_plan('Legacy Naming')
        server_class = self.create_server_class(plan, server_class_id='srv-legacy-name')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-legacy-name')

        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='legacy',
            server_interface_template=None,
            nic_slot='legacy-slot',
            ports_per_connection=2,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
        )

        DeviceGenerator(plan=plan, site=self.site).generate_all()
        server_device = Device.objects.get(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
            custom_field_data__hedgehog_class='srv-legacy-name',
        )
        names = set(server_device.interfaces.values_list('name', flat=True))
        self.assertTrue(any(name.startswith('legacy-slot') for name in names))


class UIUXIntegrationTestCase(InterfaceReuseTestBase):
    """Category 7: UI/UX Integration (9 tests)."""

    def test_planserverconnection_list_view_loads(self):
        plan = self.create_plan('List View')
        server_class = self.create_server_class(plan, server_class_id='srv-list')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-list')
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='LIST-001',
            server_interface_template=self.eth1_template,
            nic_slot='',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
        )

        response = self.client.get(reverse('plugins:netbox_hedgehog:planserverconnection_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LIST-001')

    def test_planserverconnection_add_form_loads(self):
        plan = self.create_plan('Add Form')
        server_class = self.create_server_class(plan, server_class_id='srv-add')
        response = self.client.get(
            reverse('plugins:netbox_hedgehog:planserverconnection_add'),
            {'server_class': server_class.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'server_interface_template')

    def test_planserverconnection_create_with_interface_template(self):
        plan = self.create_plan('Create Form')
        server_class = self.create_server_class(plan, server_class_id='srv-create')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-create')

        response = self.client.post(
            reverse('plugins:netbox_hedgehog:planserverconnection_add'),
            {
                'server_class': server_class.pk,
                'connection_id': 'CREATE-001',
                'server_interface_template': self.eth1_template.pk,
                'nic_slot': '',
                'ports_per_connection': 1,
                'target_switch_class': switch_class.pk,
                'speed': 200,
                'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
                'distribution': ConnectionDistributionChoices.SAME_SWITCH,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlanServerConnection.objects.filter(connection_id='CREATE-001').exists())

    def test_planserverconnection_detail_view_shows_interface_template(self):
        plan = self.create_plan('Detail View')
        server_class = self.create_server_class(plan, server_class_id='srv-detail')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-detail')
        connection = PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='DETAIL-001',
            server_interface_template=self.eth1_template,
            nic_slot='',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
        )

        response = self.client.get(
            reverse('plugins:netbox_hedgehog:planserverconnection_detail', args=[connection.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DETAIL-001')

    def test_planserverconnection_edit_workflow(self):
        plan = self.create_plan('Edit View')
        server_class = self.create_server_class(plan, server_class_id='srv-edit')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-edit')
        eth3, _ = InterfaceTemplate.objects.get_or_create(
            device_type=self.server_device_type,
            name='eth3',
            defaults={'type': '200gbase-x-qsfp56'},
        )
        connection = PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='EDIT-001',
            server_interface_template=self.eth1_template,
            nic_slot='',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
        )

        response = self.client.post(
            reverse('plugins:netbox_hedgehog:planserverconnection_edit', args=[connection.pk]),
            {
                'server_class': server_class.pk,
                'connection_id': 'EDIT-001',
                'server_interface_template': eth3.pk,
                'nic_slot': '',
                'ports_per_connection': 1,
                'target_switch_class': switch_class.pk,
                'speed': 200,
                'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
                'distribution': ConnectionDistributionChoices.SAME_SWITCH,
                'tags': [],
            },
        )
        self.assertEqual(response.status_code, 302)
        connection.refresh_from_db()
        self.assertEqual(connection.server_interface_template, eth3)

    def test_planserverconnection_delete_workflow(self):
        plan = self.create_plan('Delete View')
        server_class = self.create_server_class(plan, server_class_id='srv-delete')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-delete')
        connection = PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='DELETE-001',
            server_interface_template=self.eth1_template,
            nic_slot='',
            ports_per_connection=1,
            target_switch_class=switch_class,
            speed=200,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
        )

        response = self.client.post(
            reverse('plugins:netbox_hedgehog:planserverconnection_delete', args=[connection.pk]),
            {'confirm': True},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlanServerConnection.objects.filter(pk=connection.pk).exists())

    def test_planserverconnection_permission_denied(self):
        user = User.objects.create_user(username='noperm', password='testpass')
        self.client.force_login(user)

        response = self.client.get(reverse('plugins:netbox_hedgehog:planserverconnection_add'))
        self.assertIn(response.status_code, [302, 403])

    def test_planserverconnection_permission_with_object_permission(self):
        user = User.objects.create_user(username='hasperm', password='testpass')
        permission = ObjectPermission.objects.create(
            name='PlanServerConnection Permission',
            actions=['view', 'add', 'change', 'delete'],
        )
        permission.object_types.add(ContentType.objects.get_for_model(PlanServerConnection))
        permission.users.add(user)

        self.client.force_login(user)
        response = self.client.get(reverse('plugins:netbox_hedgehog:planserverconnection_add'))
        self.assertEqual(response.status_code, 200)

    def test_form_validation_error_displayed_in_ui(self):
        plan = self.create_plan('Form Error')
        server_class = self.create_server_class(plan, server_class_id='srv-error')
        switch_class = self.create_switch_class(plan, switch_class_id='leaf-error')

        response = self.client.post(
            reverse('plugins:netbox_hedgehog:planserverconnection_add'),
            {
                'server_class': server_class.pk,
                'connection_id': 'INVALID-001',
                'server_interface_template': '',
                'nic_slot': '',
                'ports_per_connection': 1,
                'target_switch_class': switch_class.pk,
                'speed': 200,
                'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
                'distribution': ConnectionDistributionChoices.SAME_SWITCH,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'server_interface_template')
