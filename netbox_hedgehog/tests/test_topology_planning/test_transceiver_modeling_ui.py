"""
UI integration tests for transceiver_module_type FK on PlanServerConnection
and SwitchPortZone (DIET-334 Phase 3 RED).

Tests fail until Phase 4 adds:
- transceiver_module_type fields to both models (migration 0044)
- form fields in PlanServerConnectionForm and SwitchPortZoneForm
- template rendering in planserverconnection.html and switchportzone.html
"""

from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import DeviceType, Manufacturer, ModuleType, ModuleTypeProfile
from users.models import ObjectPermission

from netbox_hedgehog.choices import (
    AllocationStrategyChoices, ConnectionDistributionChoices,
    ConnectionTypeChoices, FabricClassChoices, FabricTypeChoices,
    HedgehogRoleChoices, PortZoneTypeChoices, TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption, DeviceTypeExtension, PlanServerClass,
    PlanServerConnection, PlanServerNIC, PlanSwitchClass,
    SwitchPortZone, TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import (
    get_test_nic_module_type,
    get_test_transceiver_module_type,
)

try:
    from django.contrib.auth import get_user_model
    User = get_user_model()
except Exception:
    from django.contrib.auth.models import User


def _make_ui_fixtures(cls):
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name='XCVRUI334-Mfg', defaults={'slug': 'xcvrui334-mfg'}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='XCVRUI-SRV', defaults={'slug': 'xcvrui-srv'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='XCVRUI-SW', defaults={'slug': 'xcvrui-sw'}
    )
    cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
        device_type=cls.switch_dt,
        defaults={
            'native_speed': 200, 'uplink_ports': 0,
            'supported_breakouts': ['1x200g'], 'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    cls.breakout, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x200g-xcvrui',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    cls.plan = TopologyPlan.objects.create(
        name='XCVRUI334-Plan', status=TopologyPlanStatusChoices.DRAFT
    )
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
        server_class=cls.server_class, nic_id='nic-fe',
        module_type=get_test_nic_module_type(),
    )


# =============================================================================
# Class G: PlanServerConnection UI with transceiver FK (8 tests)
# =============================================================================

class PSCTransceiverUITestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='xcvr-ui-admin', password='pass', is_staff=True, is_superuser=True,
        )
        cls.regular_user = User.objects.create_user(
            username='xcvr-ui-user', password='pass', is_staff=True, is_superuser=False,
        )
        _make_ui_fixtures(cls)
        cls.xcvr_mt = get_test_transceiver_module_type()
        cls.existing_psc = PlanServerConnection.objects.create(
            server_class=cls.server_class, connection_id='fe-ui-existing',
            nic=cls.nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=cls.zone, speed=200, port_type='data',
            transceiver_module_type=cls.xcvr_mt,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_list_loads_200(self):
        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_add_form_includes_transceiver_field(self):
        """Add form must include transceiver_module_type field."""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'transceiver_module_type',
            msg_prefix="Add form must include transceiver_module_type field",
        )

    def test_valid_post_with_transceiver_fk_creates_record(self):
        """POST with transceiver_module_type creates PSC with FK set."""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        post_data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-ui-new',
            'nic': self.nic.pk,
            'port_index': 1,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_zone': self.zone.pk,
            'speed': 200,
            'port_type': 'data',
            'transceiver_module_type': self.xcvr_mt.pk,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302, f"Expected redirect; got {response.status_code}")
        created = PlanServerConnection.objects.filter(connection_id='fe-ui-new').first()
        self.assertIsNotNone(created, "PSC must be created")
        self.assertEqual(
            created.transceiver_module_type_id, self.xcvr_mt.pk,
            "Created PSC must have transceiver_module_type set",
        )

    def test_detail_renders_transceiver(self):
        """Detail view renders transceiver_module_type model name."""
        url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_detail',
            args=[self.existing_psc.pk],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, self.xcvr_mt.model,
            msg_prefix="Detail must render transceiver ModuleType model name",
        )

    def test_edit_clears_transceiver_fk(self):
        """Edit POST with empty transceiver_module_type clears the FK."""
        psc = PlanServerConnection.objects.create(
            server_class=self.server_class, connection_id='fe-ui-edit',
            nic=self.nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=self.zone, speed=200, port_type='data',
            transceiver_module_type=self.xcvr_mt,
        )
        url = reverse('plugins:netbox_hedgehog:planserverconnection_edit', args=[psc.pk])
        post_data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe-ui-edit',
            'nic': self.nic.pk,
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_zone': self.zone.pk,
            'speed': 200,
            'port_type': 'data',
            'transceiver_module_type': '',
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        psc.refresh_from_db()
        self.assertIsNone(psc.transceiver_module_type)

    def test_delete_removes_psc(self):
        """Delete removes the PSC record."""
        psc = PlanServerConnection.objects.create(
            server_class=self.server_class, connection_id='fe-ui-del',
            nic=self.nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=self.zone, speed=200, port_type='data',
        )
        url = reverse('plugins:netbox_hedgehog:planserverconnection_delete', args=[psc.pk])
        response = self.client.post(url, {'confirm': True})
        self.assertIn(response.status_code, [200, 302])
        self.assertFalse(PlanServerConnection.objects.filter(pk=psc.pk).exists())

    def test_without_permission_returns_403(self):
        """Regular user without ObjectPermission gets 403."""
        self.client.force_login(self.regular_user)
        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_with_object_permission_succeeds(self):
        """Regular user with ObjectPermission gets 200."""
        self.client.force_login(self.regular_user)
        perm = ObjectPermission.objects.create(
            name='xcvr-psc-view',
            actions=['view'],
        )
        perm.object_types.set([
            ContentType.objects.get_for_model(PlanServerConnection)
        ])
        perm.users.add(self.regular_user)
        url = reverse('plugins:netbox_hedgehog:planserverconnection_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


# =============================================================================
# Class H: SwitchPortZone UI with transceiver FK (6 tests)
# =============================================================================

class SPZTransceiverUITestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='xcvr-spz-admin', password='pass', is_staff=True, is_superuser=True,
        )
        _make_ui_fixtures(cls)
        cls.xcvr_mt = get_test_transceiver_module_type()
        cls.existing_zone = SwitchPortZone.objects.create(
            switch_class=cls.switch_class, zone_name='zone-h-existing',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-32',
            breakout_option=cls.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=200,
            transceiver_module_type=cls.xcvr_mt,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_spz_list_loads_200(self):
        url = reverse('plugins:netbox_hedgehog:switchportzone_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_spz_add_form_includes_transceiver_field(self):
        """SPZ add form must include transceiver_module_type field."""
        url = reverse('plugins:netbox_hedgehog:switchportzone_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'transceiver_module_type',
            msg_prefix="SPZ add form must include transceiver_module_type field",
        )

    def test_spz_valid_post_with_transceiver_fk(self):
        """POST with transceiver_module_type creates SPZ with FK set."""
        url = reverse('plugins:netbox_hedgehog:switchportzone_add')
        post_data = {
            'switch_class': self.switch_class.pk,
            'zone_name': 'zone-h-new',
            'zone_type': PortZoneTypeChoices.SERVER,
            'port_spec': '33-48',
            'breakout_option': self.breakout.pk,
            'allocation_strategy': AllocationStrategyChoices.SEQUENTIAL,
            'priority': 300,
            'transceiver_module_type': self.xcvr_mt.pk,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302, f"Expected redirect; got {response.status_code}")
        created = SwitchPortZone.objects.filter(zone_name='zone-h-new').first()
        self.assertIsNotNone(created)
        self.assertEqual(created.transceiver_module_type_id, self.xcvr_mt.pk)

    def test_spz_detail_renders_transceiver(self):
        """Detail view renders transceiver_module_type model name."""
        url = reverse(
            'plugins:netbox_hedgehog:switchportzone',
            args=[self.existing_zone.pk],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, self.xcvr_mt.model,
            msg_prefix="SPZ detail must render transceiver ModuleType name",
        )

    def test_spz_edit_clears_transceiver_fk(self):
        """Edit POST with empty transceiver_module_type clears the FK."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class, zone_name='zone-h-edit',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='49-56',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=400,
            transceiver_module_type=self.xcvr_mt,
        )
        url = reverse('plugins:netbox_hedgehog:switchportzone_edit', args=[zone.pk])
        post_data = {
            'switch_class': self.switch_class.pk,
            'zone_name': 'zone-h-edit',
            'zone_type': PortZoneTypeChoices.SERVER,
            'port_spec': '49-56',
            'breakout_option': self.breakout.pk,
            'allocation_strategy': AllocationStrategyChoices.SEQUENTIAL,
            'priority': 400,
            'transceiver_module_type': '',
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        zone.refresh_from_db()
        self.assertIsNone(zone.transceiver_module_type)

    def test_spz_delete_removes_zone(self):
        """Delete removes the SwitchPortZone."""
        zone = SwitchPortZone.objects.create(
            switch_class=self.switch_class, zone_name='zone-h-del',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='57-64',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=500,
        )
        url = reverse('plugins:netbox_hedgehog:switchportzone_delete', args=[zone.pk])
        response = self.client.post(url, {'confirm': True})
        self.assertIn(response.status_code, [200, 302])
        self.assertFalse(SwitchPortZone.objects.filter(pk=zone.pk).exists())
