"""
Integration tests for leaf↔spine fabric connection generation (DIET-140).

These tests exercise the Generate Devices workflow and validate that
fabric cables are created using uplink/fabric port zones.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from dcim.models import DeviceType, Manufacturer, Device, Interface, Cable, CableTermination
from extras.models import Tag

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    DeviceTypeExtension,
    BreakoutOption,
    SwitchPortZone,
)
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


class FabricConnectionGenerationTestCase(TestCase):
    """Integration tests for fabric cabling during device generation."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='fabric-admin',
            password='testpass',
            is_superuser=True,
        )

        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Fabric Test Vendor',
            defaults={'slug': 'fabric-test-vendor'},
        )

        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='FabricSwitch',
            defaults={'slug': 'fabricswitch'},
        )

        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model='FabricServer',
            defaults={'slug': 'fabricserver'},
        )

        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_type,
            defaults={
                'native_speed': 800,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g'],
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf'],
            },
        )

        cls.breakout_1x800, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x800g',
            defaults={'from_speed': 800, 'logical_ports': 1, 'logical_speed': 800},
        )

        cls.breakout_2x400, _ = BreakoutOption.objects.get_or_create(
            breakout_id='2x400g',
            defaults={'from_speed': 800, 'logical_ports': 2, 'logical_speed': 400},
        )

        cls.breakout_4x200, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200},
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='fabric-admin', password='testpass')
        self._cleanup_all_generated_objects()

    def tearDown(self):
        self._cleanup_all_generated_objects()

    def _cleanup_all_generated_objects(self):
        """Remove any hedgehog-generated devices/interfaces/cables."""
        tag = Tag.objects.filter(slug='hedgehog-generated').first()
        if tag:
            Cable.objects.filter(tags=tag).delete()

        devices = Device.objects.all()
        for device in devices:
            if device.custom_field_data and 'hedgehog_plan_id' in device.custom_field_data:
                device.delete()

        Interface.objects.filter(device__isnull=True).delete()

    def _create_plan(self, name='Fabric Plan'):
        return TopologyPlan.objects.create(
            name=name,
            status=TopologyPlanStatusChoices.DRAFT,
        )

    def _create_server_class(self, plan, quantity=1):
        return PlanServerClass.objects.create(
            plan=plan,
            server_class_id='srv',
            category=ServerClassCategoryChoices.GPU,
            quantity=quantity,
            server_device_type=self.server_type,
        )

    def _create_switch_class(
        self,
        plan,
        switch_class_id,
        hedgehog_role,
        fabric=FabricTypeChoices.FRONTEND,
        quantity=1,
    ):
        return PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id=switch_class_id,
            fabric=fabric,
            hedgehog_role=hedgehog_role,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=None,
            mclag_pair=False,
            calculated_quantity=quantity,
            override_quantity=None,
        )

    def _create_zone(
        self,
        switch_class,
        zone_name,
        zone_type,
        port_spec,
        breakout_option,
        priority=100,
    ):
        return SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name=zone_name,
            zone_type=zone_type,
            port_spec=port_spec,
            breakout_option=breakout_option,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=priority,
        )

    def _interfaces_for_cable(self, cable):
        content_type = ContentType.objects.get_for_model(Interface)
        terminations = CableTermination.objects.filter(
            cable=cable,
            termination_type=content_type,
        )
        interface_ids = [t.termination_id for t in terminations]
        return list(Interface.objects.filter(pk__in=interface_ids))

    def _count_fabric_cables(self, plan):
        cables = Cable.objects.filter(custom_field_data__hedgehog_plan_id=str(plan.pk))
        count = 0
        for cable in cables:
            interfaces = self._interfaces_for_cable(cable)
            if len(interfaces) != 2:
                continue
            roles = {interfaces[0].device.role.slug, interfaces[1].device.role.slug}
            if roles == {'leaf', 'spine'}:
                count += 1
        return count

    def _fabric_cables_per_spine(self, plan):
        cables = Cable.objects.filter(custom_field_data__hedgehog_plan_id=str(plan.pk))
        counts = {}
        for cable in cables:
            interfaces = self._interfaces_for_cable(cable)
            if len(interfaces) != 2:
                continue
            spine_interface = None
            leaf_interface = None
            for interface in interfaces:
                if interface.device.role.slug == 'spine':
                    spine_interface = interface
                if interface.device.role.slug == 'leaf':
                    leaf_interface = interface
            if spine_interface and leaf_interface:
                spine_name = spine_interface.device.name
                counts[spine_name] = counts.get(spine_name, 0) + 1
        return counts

    def _create_minimal_server_connection(self, server_class, leaf_class):
        zone = self._create_zone(
            leaf_class,
            zone_name='server-downlinks',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-2',
            breakout_option=self.breakout_4x200,
        )

        return PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='fe',
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_zone=zone,
            speed=200,
        )

    def test_generate_creates_fabric_cables_full_mesh(self):
        plan = self._create_plan('Fabric Full Mesh')
        server_class = self._create_server_class(plan)

        leaf_class = self._create_switch_class(
            plan,
            switch_class_id='fe-leaf',
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            quantity=2,
        )
        spine_class = self._create_switch_class(
            plan,
            switch_class_id='fe-spine',
            hedgehog_role=HedgehogRoleChoices.SPINE,
            quantity=2,
        )

        self._create_minimal_server_connection(server_class, leaf_class)

        self._create_zone(
            leaf_class,
            zone_name='spine-uplinks',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='3-4',
            breakout_option=self.breakout_1x800,
            priority=10,
        )
        self._create_zone(
            spine_class,
            zone_name='leaf-downlinks',
            zone_type=PortZoneTypeChoices.FABRIC,
            port_spec='1-4',
            breakout_option=self.breakout_1x800,
            priority=10,
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan.pk])
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)

        # 2 leaves × 2 uplinks each = 4 leaf↔spine cables
        self.assertEqual(self._count_fabric_cables(plan), 4)

    def test_fabric_cable_distribution_respects_spine_order(self):
        plan = self._create_plan('Fabric Distribution')
        server_class = self._create_server_class(plan)

        leaf_class = self._create_switch_class(
            plan,
            switch_class_id='fe-leaf',
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            quantity=1,
        )
        spine_class = self._create_switch_class(
            plan,
            switch_class_id='fe-spine',
            hedgehog_role=HedgehogRoleChoices.SPINE,
            quantity=3,
        )

        self._create_minimal_server_connection(server_class, leaf_class)

        self._create_zone(
            leaf_class,
            zone_name='spine-uplinks',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='3-6',
            breakout_option=self.breakout_1x800,
            priority=10,
        )
        self._create_zone(
            spine_class,
            zone_name='leaf-downlinks',
            zone_type=PortZoneTypeChoices.FABRIC,
            port_spec='1-6',
            breakout_option=self.breakout_1x800,
            priority=10,
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan.pk])
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)

        counts = self._fabric_cables_per_spine(plan)
        self.assertEqual(counts.get('fe-spine-01'), 2)
        self.assertEqual(counts.get('fe-spine-02'), 1)
        self.assertEqual(counts.get('fe-spine-03'), 1)

    def test_fabric_breakout_interfaces_created(self):
        plan = self._create_plan('Fabric Breakout')
        server_class = self._create_server_class(plan)

        leaf_class = self._create_switch_class(
            plan,
            switch_class_id='fe-leaf',
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            quantity=1,
        )
        spine_class = self._create_switch_class(
            plan,
            switch_class_id='fe-spine',
            hedgehog_role=HedgehogRoleChoices.SPINE,
            quantity=1,
        )

        self._create_minimal_server_connection(server_class, leaf_class)

        self._create_zone(
            leaf_class,
            zone_name='spine-uplinks',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='3-3',
            breakout_option=self.breakout_2x400,
            priority=10,
        )
        self._create_zone(
            spine_class,
            zone_name='leaf-downlinks',
            zone_type=PortZoneTypeChoices.FABRIC,
            port_spec='1-1',
            breakout_option=self.breakout_2x400,
            priority=10,
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan.pk])
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)

        leaf_interfaces = Interface.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(plan.pk),
            device__role__slug='leaf',
            custom_field_data__hedgehog_zone='spine-uplinks',
        )
        leaf_names = {iface.name for iface in leaf_interfaces}
        self.assertIn('E1/3/1', leaf_names)
        self.assertIn('E1/3/2', leaf_names)

    def test_generate_fails_without_uplink_zone(self):
        plan = self._create_plan('Missing Uplink Zone')
        server_class = self._create_server_class(plan)

        leaf_class = self._create_switch_class(
            plan,
            switch_class_id='fe-leaf',
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            quantity=1,
        )
        spine_class = self._create_switch_class(
            plan,
            switch_class_id='fe-spine',
            hedgehog_role=HedgehogRoleChoices.SPINE,
            quantity=1,
        )

        self._create_minimal_server_connection(server_class, leaf_class)

        self._create_zone(
            spine_class,
            zone_name='leaf-downlinks',
            zone_type=PortZoneTypeChoices.FABRIC,
            port_spec='1-2',
            breakout_option=self.breakout_1x800,
            priority=10,
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan.pk])
        response = self.client.post(url, follow=True)

        messages = list(response.context['messages'])
        self.assertTrue(
            any('uplink' in str(message).lower() for message in messages),
            "Should report missing uplink zones",
        )

    def test_generate_fails_without_fabric_zone(self):
        plan = self._create_plan('Missing Fabric Zone')
        server_class = self._create_server_class(plan)

        leaf_class = self._create_switch_class(
            plan,
            switch_class_id='fe-leaf',
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            quantity=1,
        )
        spine_class = self._create_switch_class(
            plan,
            switch_class_id='fe-spine',
            hedgehog_role=HedgehogRoleChoices.SPINE,
            quantity=1,
        )

        self._create_minimal_server_connection(server_class, leaf_class)

        self._create_zone(
            leaf_class,
            zone_name='spine-uplinks',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='3-4',
            breakout_option=self.breakout_1x800,
            priority=10,
        )

        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan.pk])
        response = self.client.post(url, follow=True)

        messages = list(response.context['messages'])
        self.assertTrue(
            any('fabric' in str(message).lower() for message in messages),
            "Should report missing fabric zones",
        )

    def test_generate_requires_authentication(self):
        plan = self._create_plan('Auth Required')
        server_class = self._create_server_class(plan)
        leaf_class = self._create_switch_class(
            plan,
            switch_class_id='fe-leaf',
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            quantity=1,
        )
        spine_class = self._create_switch_class(
            plan,
            switch_class_id='fe-spine',
            hedgehog_role=HedgehogRoleChoices.SPINE,
            quantity=1,
        )
        self._create_minimal_server_connection(server_class, leaf_class)
        self._create_zone(
            leaf_class,
            zone_name='spine-uplinks',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='3-4',
            breakout_option=self.breakout_1x800,
            priority=10,
        )
        self._create_zone(
            spine_class,
            zone_name='leaf-downlinks',
            zone_type=PortZoneTypeChoices.FABRIC,
            port_spec='1-2',
            breakout_option=self.breakout_1x800,
            priority=10,
        )

        self.client.logout()
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', args=[plan.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
