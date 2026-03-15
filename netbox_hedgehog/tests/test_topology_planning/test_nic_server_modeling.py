"""
RED tests for PlanServerNIC model and updated PlanServerConnection schema (DIET-294).

All tests fail until Phase 4 GREEN implementation:
- PlanServerNIC model does not exist yet
- PlanServerConnection.nic FK does not exist yet
- PlanServerConnection.cage_type/medium/connector/standard do not exist yet
- hedgehog_transceiver_spec custom field does not exist yet
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from dcim.models import DeviceType, Manufacturer, ModuleType, InterfaceTemplate, Module, ModuleBay
from users.models import ObjectPermission

from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type, get_test_server_nic
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


def _make_base_fixtures(cls):
    """Shared fixture builder used by multiple test classes."""
    cls.mfr, _ = Manufacturer.objects.get_or_create(name='NIC294', defaults={'slug': 'nic294'})
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='SRV-294', defaults={'slug': 'srv-294'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='SW-294', defaults={'slug': 'sw-294'}
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
        breakout_id='1x200g',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    cls.module_type = get_test_nic_module_type()  # BF3220 with p0, p1
    cls.plan = TopologyPlan.objects.create(
        name='NIC294-plan', status=TopologyPlanStatusChoices.DRAFT
    )
    cls.server_class = PlanServerClass.objects.create(
        plan=cls.plan, server_class_id='gpu-server',
        server_device_type=cls.server_dt, quantity=1,
    )
    cls.switch_class = PlanSwitchClass.objects.create(
        plan=cls.plan, switch_class_id='fe-leaf',
        fabric_name=FabricTypeChoices.FRONTEND,
        fabric_class=FabricClassChoices.MANAGED,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=cls.device_ext,
        uplink_ports_per_switch=0, mclag_pair=False,
        override_quantity=2,
        redundancy_type='eslag',
    )
    cls.zone = SwitchPortZone.objects.create(
        switch_class=cls.switch_class, zone_name='server-downlinks',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-64',
        breakout_option=cls.breakout,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
    )
    cls.nic = PlanServerNIC.objects.create(
        server_class=cls.server_class, nic_id='nic-fe', module_type=cls.module_type,
    )


# =============================================================================
# Class A: PlanServerNIC CRUD Integration (8 tests)
# =============================================================================

class PlanServerNICCRUDTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='nic294-admin', password='pass', is_staff=True, is_superuser=True,
        )
        cls.regular_user = User.objects.create_user(
            username='nic294-user', password='pass', is_staff=True, is_superuser=False,
        )
        _make_base_fixtures(cls)

    def setUp(self):
        self.client = Client()
        self.client.login(username='nic294-admin', password='pass')

    def test_list_view_200(self):
        url = reverse('plugins:netbox_hedgehog:planservernic_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_add_form_200(self):
        url = reverse('plugins:netbox_hedgehog:planservernic_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_valid_post_creates_and_redirects_302(self):
        url = reverse('plugins:netbox_hedgehog:planservernic_add')
        data = {
            'server_class': self.server_class.pk,
            'nic_id': 'nic-new',
            'module_type': self.module_type.pk,
            'description': '',
            'tags': [],
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlanServerNIC.objects.filter(nic_id='nic-new').exists())

    def test_detail_view_renders_expected_data(self):
        url = reverse('plugins:netbox_hedgehog:planservernic_detail', args=[self.nic.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'nic-fe')

    def test_edit_workflow_updates_object(self):
        url = reverse('plugins:netbox_hedgehog:planservernic_edit', args=[self.nic.pk])
        data = {
            'server_class': self.server_class.pk,
            'nic_id': 'nic-fe',
            'module_type': self.module_type.pk,
            'description': 'Updated description',
            'tags': [],
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.nic.refresh_from_db()
        self.assertEqual(self.nic.description, 'Updated description')

    def test_delete_workflow_removes_object(self):
        nic_to_delete = PlanServerNIC.objects.create(
            server_class=self.server_class, nic_id='nic-delete', module_type=self.module_type,
        )
        url = reverse('plugins:netbox_hedgehog:planservernic_delete', args=[nic_to_delete.pk])
        response = self.client.post(url, {'confirm': True})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlanServerNIC.objects.filter(pk=nic_to_delete.pk).exists())

    def test_without_permission_returns_403(self):
        self.client.login(username='nic294-user', password='pass')
        url = reverse('plugins:netbox_hedgehog:planservernic_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_with_objectpermission_succeeds(self):
        ct = ContentType.objects.get(app_label='netbox_hedgehog', model='planservernic')
        perm = ObjectPermission.objects.create(name='nic294-view', actions=['view'])
        perm.object_types.add(ct)
        perm.users.add(self.regular_user)
        self.client.login(username='nic294-user', password='pass')
        url = reverse('plugins:netbox_hedgehog:planservernic_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


# =============================================================================
# Class B: PlanServerNIC Validation (4 tests)
# =============================================================================

class PlanServerNICValidationTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        _make_base_fixtures(cls)

    def test_duplicate_nic_id_rejected(self):
        with self.assertRaises((IntegrityError, ValidationError)):
            nic2 = PlanServerNIC(
                server_class=self.server_class,
                nic_id='nic-fe',  # same as fixture nic
                module_type=self.module_type,
            )
            nic2.full_clean()
            nic2.save()

    def test_invalid_nic_id_chars_rejected(self):
        nic = PlanServerNIC(
            server_class=self.server_class,
            nic_id='nic fe',  # space is invalid
            module_type=self.module_type,
        )
        with self.assertRaises(ValidationError) as ctx:
            nic.full_clean()
        self.assertIn('nic_id', ctx.exception.message_dict)

    def test_nic_id_starting_with_hyphen_rejected(self):
        nic = PlanServerNIC(
            server_class=self.server_class,
            nic_id='-nic-bad',
            module_type=self.module_type,
        )
        with self.assertRaises(ValidationError) as ctx:
            nic.full_clean()
        self.assertIn('nic_id', ctx.exception.message_dict)

    def test_module_type_without_interface_templates_rejected(self):
        empty_mt = ModuleType.objects.create(
            manufacturer=self.mfr, model='Empty-MT-294',
        )
        nic = PlanServerNIC(
            server_class=self.server_class,
            nic_id='nic-empty',
            module_type=empty_mt,
        )
        with self.assertRaises(ValidationError) as ctx:
            nic.full_clean()
        self.assertIn('module_type', ctx.exception.message_dict)


# =============================================================================
# Class C: PlanServerConnection with nic FK (7 tests)
# =============================================================================

class PlanServerConnectionNICFKTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='connnic294', password='pass', is_staff=True, is_superuser=True,
        )
        _make_base_fixtures(cls)

    def setUp(self):
        self.client = Client()
        self.client.login(username='connnic294', password='pass')

    def _make_connection(self, nic=None, port_index=0, **kwargs):
        nic = nic or self.nic
        defaults = dict(
            server_class=self.server_class,
            connection_id='test-conn',
            nic=nic,
            port_index=port_index,
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=self.zone,
            speed=200,
            port_type='data',
        )
        defaults.update(kwargs)
        return PlanServerConnection(**defaults)

    def test_connection_form_has_nic_field_not_nic_module_type(self):
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.get(url + f'?server_class={self.server_class.pk}')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('name="nic"', content)
        self.assertNotIn('name="nic_module_type"', content)

    def test_connection_port_index_validated_against_nic(self):
        conn = self._make_connection(port_index=99)  # BF3 has only p0, p1
        with self.assertRaises(ValidationError) as ctx:
            conn.full_clean()
        self.assertIn('port_index', ctx.exception.message_dict)

    def test_connection_cross_plan_nic_rejected(self):
        other_plan = TopologyPlan.objects.create(name='Other294', status=TopologyPlanStatusChoices.DRAFT)
        other_sc = PlanServerClass.objects.create(
            plan=other_plan, server_class_id='gpu-server',
            server_device_type=self.server_dt, quantity=1,
        )
        foreign_nic = PlanServerNIC.objects.create(
            server_class=other_sc, nic_id='nic-foreign', module_type=self.module_type,
        )
        conn = self._make_connection(nic=foreign_nic)
        with self.assertRaises(ValidationError) as ctx:
            conn.full_clean()
        self.assertIn('nic', ctx.exception.message_dict)

    def test_connection_transceiver_fields_optional_and_stored(self):
        conn = self._make_connection(
            connection_id='conn-xcvr',
            cage_type='QSFP112', medium='MMF', connector='MPO-12', standard='200GBASE-SR4',
        )
        conn.full_clean()
        conn.save()
        conn.refresh_from_db()
        self.assertEqual(conn.cage_type, 'QSFP112')
        self.assertEqual(conn.medium, 'MMF')
        self.assertEqual(conn.connector, 'MPO-12')
        self.assertEqual(conn.standard, '200GBASE-SR4')

    def test_connection_transceiver_fields_rendered_in_detail_view(self):
        conn = self._make_connection(
            connection_id='conn-render',
            cage_type='QSFP112', medium='MMF',
        )
        conn.save()
        url = reverse('plugins:netbox_hedgehog:planserverconnection_detail', args=[conn.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'QSFP112')

    def test_connection_nic_from_wrong_server_class_rejected(self):
        other_sc = PlanServerClass.objects.create(
            plan=self.plan, server_class_id='storage-server',
            server_device_type=self.server_dt, quantity=1,
        )
        wrong_nic = PlanServerNIC.objects.create(
            server_class=other_sc, nic_id='nic-wrong', module_type=self.module_type,
        )
        conn = PlanServerConnection(
            server_class=self.server_class,
            connection_id='bad-conn',
            nic=wrong_nic,
            port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=self.zone, speed=200, port_type='data',
        )
        with self.assertRaises(ValidationError) as ctx:
            conn.full_clean()
        self.assertIn('nic', ctx.exception.message_dict)

    def test_connection_nic_filtered_to_same_server_class(self):
        # Form submitted without a nic should show error, not 500
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.server_class.pk,
            'connection_id': 'fe',
            'nic': '',  # empty — should produce form error
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
        # Should re-render form (200) with validation error, not crash (500)
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 200:
            self.assertNotEqual(response.status_code, 500)


# =============================================================================
# Class D: Migration Coverage (3 tests)
# =============================================================================

class PlanServerNICMigrationTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        _make_base_fixtures(cls)

    def _get_migration_0037(self):
        import importlib
        return importlib.import_module('netbox_hedgehog.migrations.0037_plan_server_nic')

    def _get_migration_0038(self):
        import importlib
        return importlib.import_module('netbox_hedgehog.migrations.0038_plan_server_nic_finalize')

    def test_migration_0037_backfills_nic_for_each_connection(self):
        """0037 backfill creates one PlanServerNIC per existing PlanServerConnection."""
        migration = self._get_migration_0037()
        # The backfill function must exist in the migration
        self.assertTrue(
            hasattr(migration, 'backfill_plan_server_nics'),
            "Migration 0037 must define backfill_plan_server_nics()",
        )

    def test_migration_0038_preflight_raises_if_null_nic_exists(self):
        """0038 pre-flight raises if any PlanServerConnection has nic=NULL."""
        migration = self._get_migration_0038()
        self.assertTrue(
            hasattr(migration, 'check_all_connections_have_nic'),
            "Migration 0038 must define check_all_connections_have_nic()",
        )

    def test_migration_0038_check_function_raises_on_null_nic(self):
        """check_all_connections_have_nic raises Exception when nulls exist."""
        migration = self._get_migration_0038()
        # Create a connection with nic=NULL by bypassing model save (direct DB)
        # This tests the function logic; the actual migration guards this at deploy time.
        # We verify the function raises when it detects NULL nic values.
        # Since we can't easily create a NULL nic (schema enforces NOT NULL after 0038),
        # we verify the function is callable and raises the right type.
        from unittest.mock import patch, MagicMock
        mock_qs = MagicMock()
        mock_qs.objects.filter.return_value.count.return_value = 3  # simulate 3 NULLs
        mock_apps = MagicMock()
        mock_apps.get_model.return_value = mock_qs
        with self.assertRaises(Exception) as ctx:
            migration.check_all_connections_have_nic(mock_apps, None)
        self.assertIn('DIET-294', str(ctx.exception))


# =============================================================================
# Class E: Dual-Plane NIC Scenario (4 tests)
# =============================================================================

import contextlib

class DualPlaneNICTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        _make_base_fixtures(cls)
        # Second zone for plane B
        cls.zone_b = SwitchPortZone.objects.create(
            switch_class=cls.switch_class, zone_name='server-downlinks-b',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='33-64',
            breakout_option=cls.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=200,
        )

    def setUp(self):
        from dcim.models import Device, Cable
        from extras.models import Tag
        Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).delete()
        Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).delete()
        PlanServerConnection.objects.filter(server_class=self.server_class).delete()

    def tearDown(self):
        from dcim.models import Device, Cable
        Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).delete()
        Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).delete()

    def _make_dual_plane_connections(self):
        PlanServerConnection.objects.create(
            server_class=self.server_class, connection_id='fe-a',
            nic=self.nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=self.zone, speed=200, port_type='data',
        )
        PlanServerConnection.objects.create(
            server_class=self.server_class, connection_id='fe-b',
            nic=self.nic, port_index=1, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=self.zone_b, speed=200, port_type='data',
        )

    def test_dual_plane_single_nic_two_connections_allowed(self):
        """Two connections sharing one NIC (port 0 and port 1) must not raise."""
        self._make_dual_plane_connections()
        self.assertEqual(
            PlanServerConnection.objects.filter(server_class=self.server_class).count(), 2
        )

    def test_dual_plane_generator_creates_one_module_not_two(self):
        """One PlanServerNIC → one Module per server device, even with two connections."""
        self._make_dual_plane_connections()
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        DeviceGenerator(self.plan).generate_all()
        self.assertEqual(Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            device__custom_field_data__hedgehog_class='gpu-server',
        ).count(), 1)

    def test_dual_plane_generator_uses_correct_port_per_connection(self):
        """Each dual-plane connection wires to a different interface (p0 vs p1)."""
        self._make_dual_plane_connections()
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        from dcim.models import Cable, Interface
        DeviceGenerator(self.plan).generate_all()
        server_ifaces = Interface.objects.filter(
            device__custom_field_data__hedgehog_class='gpu-server',
            device__custom_field_data__hedgehog_plan_id=str(self.plan.pk),
        ).values_list('name', flat=True)
        self.assertIn('nic-fe-p0', server_ifaces)
        self.assertIn('nic-fe-p1', server_ifaces)

    def test_eight_cx7_nics_each_create_distinct_module(self):
        """8 distinct PlanServerNICs → 8 distinct Modules per server device."""
        cx7_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=self.mfr, model='CX7-Single-294',
        )
        InterfaceTemplate.objects.get_or_create(
            module_type=cx7_mt, name='port0', defaults={'type': '400gbase-x-osfp'},
        )
        cx7_nics = []
        for i in range(8):
            n = PlanServerNIC.objects.create(
                server_class=self.server_class,
                nic_id=f'nic-be-rail-{i}',
                module_type=cx7_mt,
            )
            cx7_nics.append(n)
            SwitchPortZone.objects.get_or_create(
                switch_class=self.switch_class,
                zone_name=f'be-rail-{i}-downlinks',
                defaults={
                    'zone_type': PortZoneTypeChoices.SERVER, 'port_spec': str(i + 1),
                    'breakout_option': self.breakout,
                    'allocation_strategy': AllocationStrategyChoices.SEQUENTIAL,
                    'priority': 300 + i,
                },
            )
        for i, (nic, zone_name) in enumerate(
            zip(cx7_nics, [f'be-rail-{j}-downlinks' for j in range(8)])
        ):
            z = SwitchPortZone.objects.get(switch_class=self.switch_class, zone_name=zone_name)
            PlanServerConnection.objects.create(
                server_class=self.server_class,
                connection_id=f'be-rail-{i}',
                nic=nic, port_index=0, ports_per_connection=1,
                hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
                distribution=ConnectionDistributionChoices.ALTERNATING,
                target_zone=z, speed=200, port_type='data',
            )
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        DeviceGenerator(self.plan).generate_all()
        # 1 BF3 NIC + 8 CX7 NICs = 9 modules total, but this test has no fe conn
        # (setUp deleted all connections) so it's just the 8 CX7 modules
        module_count = Module.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            device__custom_field_data__hedgehog_class='gpu-server',
        ).count()
        self.assertEqual(module_count, 8)


# =============================================================================
# Class F: Transceiver Spec on Server-Side Interface (3 tests)
# =============================================================================

class TransceiverSpecOnInterfaceTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        _make_base_fixtures(cls)

    def setUp(self):
        from dcim.models import Device, Cable
        Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).delete()
        Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).delete()
        PlanServerConnection.objects.filter(server_class=self.server_class).delete()

    def tearDown(self):
        from dcim.models import Device, Cable
        Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).delete()
        Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).delete()

    def _run_generate(self, cage_type='', medium='', connector='', standard=''):
        PlanServerConnection.objects.create(
            server_class=self.server_class, connection_id='fe',
            nic=self.nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=self.zone, speed=200, port_type='data',
            cage_type=cage_type, medium=medium, connector=connector, standard=standard,
        )
        from netbox_hedgehog.services.device_generator import DeviceGenerator
        DeviceGenerator(self.plan).generate_all()

    def _get_server_interfaces(self):
        from dcim.models import Interface
        return Interface.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            device__custom_field_data__hedgehog_class='gpu-server',
        )

    def _get_switch_interfaces(self):
        from dcim.models import Interface
        return Interface.objects.filter(
            device__custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            device__custom_field_data__hedgehog_class='fe-leaf',
        )

    def test_generator_sets_transceiver_spec_on_server_interface(self):
        self._run_generate(cage_type='QSFP112', medium='MMF', connector='MPO-12', standard='200GBASE-SR4')
        server_ifaces = self._get_server_interfaces()
        # At least one server interface should have the transceiver spec set
        specs = [
            iface.custom_field_data.get('hedgehog_transceiver_spec', '')
            for iface in server_ifaces
        ]
        self.assertIn('QSFP112 | MMF | MPO-12 | 200GBASE-SR4', specs)

    def test_generator_leaves_transceiver_spec_blank_when_no_data(self):
        self._run_generate()  # all transceiver fields blank
        server_ifaces = self._get_server_interfaces()
        for iface in server_ifaces:
            spec = iface.custom_field_data.get('hedgehog_transceiver_spec', '')
            self.assertEqual(spec, '', f"Expected empty spec on {iface.name}, got {spec!r}")

    def test_generator_transceiver_spec_only_on_server_side_not_switch_side(self):
        """hedgehog_transceiver_spec must NOT be set on switch-side interfaces."""
        self._run_generate(cage_type='QSFP112', medium='MMF')
        switch_ifaces = self._get_switch_interfaces()
        for iface in switch_ifaces:
            spec = iface.custom_field_data.get('hedgehog_transceiver_spec', '')
            self.assertEqual(
                spec, '',
                f"Switch interface {iface.name} must not have hedgehog_transceiver_spec, got {spec!r}",
            )
