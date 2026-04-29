"""
RED tests for #475 — simplified transceiver UX: form behavior.

Replaces the old DIET-466 mandatory-transceiver form tests with tests that
pin the approved target behavior from #474 §9.2 (F1–F5).

Target behavior (not yet implemented):
  - transceiver_module_type is OPTIONAL on both add and edit forms
  - POST with blank transceiver → 302 redirect (connection/zone created)
  - POST clearing transceiver → 302 redirect (updated to null)
  - GET add form → transceiver field not marked required; no flat fields present

Acceptance matrix IDs covered: F1, F2, F3, F4, F5
Also covers: permission enforcement with null transceiver (all operations
  require ObjectPermission; the null transceiver must not break that contract).

All tests are RED until GREEN removes required=True from both form fields and
removes flat fields (cage_type, medium, connector, standard) from Meta.fields.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import DeviceType, InterfaceTemplate, Manufacturer, ModuleBayTemplate
from users.models import ObjectPermission

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricClassChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanServerClass,
    PlanServerConnection,
    PlanServerNIC,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_form_fixtures(cls):
    """Set up shared DB fixtures for form tests."""
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name='MxtFm-Vendor', defaults={'slug': 'mxtfm-vendor'}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MxtFm-SRV', defaults={'slug': 'mxtfm-srv'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MxtFm-SW', defaults={'slug': 'mxtfm-sw'}
    )
    for n in range(1, 5):
        InterfaceTemplate.objects.get_or_create(
            device_type=cls.switch_dt, name=f'E1/{n}',
            defaults={'type': '200gbase-x-qsfp112'},
        )
        ModuleBayTemplate.objects.get_or_create(
            device_type=cls.switch_dt, name=f'E1/{n}',
        )
    cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=cls.switch_dt,
        defaults={
            'native_speed': 200, 'uplink_ports': 0,
            'supported_breakouts': ['1x200g'], 'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    cls.breakout, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x200g-mxtfm',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    cls.nic_mt = get_test_nic_module_type()

    # Superuser for all form tests
    cls.superuser, _ = User.objects.get_or_create(
        username='mxtfm-admin',
        defaults={'is_staff': True, 'is_superuser': True},
    )
    cls.superuser.set_password('pass')
    cls.superuser.save()


def _make_minimal_plan(cls):
    """Build a plan + switch class + zone + server class + NIC for form tests."""
    plan = TopologyPlan.objects.create(
        name=f'MxtFm-Plan-{id(cls)}',
        status=TopologyPlanStatusChoices.DRAFT,
    )
    sc = PlanServerClass.objects.create(
        plan=plan, server_class_id='gpu',
        server_device_type=cls.server_dt, quantity=1,
    )
    sw = PlanSwitchClass.objects.create(
        plan=plan, switch_class_id='fe-leaf',
        fabric_name=FabricTypeChoices.FRONTEND,
        fabric_class=FabricClassChoices.MANAGED,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=cls.device_ext,
        uplink_ports_per_switch=0, mclag_pair=False,
        override_quantity=2, redundancy_type='eslag',
    )
    # Zone created without transceiver to support F2/F4 re-use
    zone = SwitchPortZone.objects.create(
        switch_class=sw, zone_name='server-downlinks',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-4',
        breakout_option=cls.breakout,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        transceiver_module_type=None,
    )
    nic = PlanServerNIC.objects.create(
        server_class=sc, nic_id='nic-fe', module_type=cls.nic_mt,
    )
    return plan, sc, sw, zone, nic


# ---------------------------------------------------------------------------
# F1 — POST PSC add with blank transceiver → 302
# ---------------------------------------------------------------------------

class PlanServerConnectionAddNullTransceiverTestCase(TestCase):
    """
    F1: POST to planserverconnection_add with transceiver_module_type omitted
    must return HTTP 302 (connection created successfully).

    RED: currently returns 200 with 'A transceiver ModuleType is required'
    because PlanServerConnectionForm sets required=True on the field and
    PlanServerConnection.clean() raises ValidationError when FK is null.
    """

    @classmethod
    def setUpTestData(cls):
        _make_form_fixtures(cls)
        cls.plan, cls.sc, cls.sw, cls.zone, cls.nic = _make_minimal_plan(cls)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_f1_post_add_without_transceiver_creates_connection(self):
        """F1: omitting transceiver_module_type → 302, connection saved with null FK."""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.sc.pk,
            'connection_id': 'fe-f1',
            'nic': self.nic.pk,
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_zone': self.zone.pk,
            'speed': 200,
            'port_type': 'data',
            # transceiver_module_type intentionally omitted
        }
        response = self.client.post(url, data)
        self.assertEqual(
            response.status_code, 302,
            f'F1: POST with no transceiver must redirect (302); got {response.status_code}. '
            f'Form errors: {response.context["form"].errors if response.context else "(no context)"}',
        )
        conn = PlanServerConnection.objects.filter(
            server_class=self.sc, connection_id='fe-f1'
        ).first()
        self.assertIsNotNone(conn, 'F1: PlanServerConnection must be created')
        self.assertIsNone(
            conn.transceiver_module_type_id,
            'F1: transceiver_module_type must be null on saved connection',
        )

    def test_f1_null_transceiver_does_not_appear_as_required_error(self):
        """F1b: blank transceiver must not produce 'required' form error message."""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        data = {
            'server_class': self.sc.pk,
            'connection_id': 'fe-f1b',
            'nic': self.nic.pk,
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_zone': self.zone.pk,
            'speed': 200,
            'port_type': 'data',
        }
        response = self.client.post(url, data, follow=True)
        content = response.content.decode()
        self.assertNotIn(
            'A transceiver ModuleType is required',
            content,
            'F1b: Required-transceiver error must not appear when transceiver is optional',
        )


# ---------------------------------------------------------------------------
# F2 — POST SwitchPortZone add with blank transceiver → 302
# ---------------------------------------------------------------------------

class SwitchPortZoneAddNullTransceiverTestCase(TestCase):
    """
    F2: POST to switchportzone_add with transceiver_module_type omitted
    must return HTTP 302 (zone created successfully).

    RED: currently returns 200 with required-field error because
    SwitchPortZoneForm sets required=True and SwitchPortZone.clean() raises
    when FK is null.
    """

    @classmethod
    def setUpTestData(cls):
        _make_form_fixtures(cls)
        cls.plan, cls.sc, cls.sw, cls.zone, cls.nic = _make_minimal_plan(cls)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_f2_post_zone_add_without_transceiver_creates_zone(self):
        """F2: omitting transceiver_module_type on zone add → 302, zone saved with null FK."""
        url = reverse('plugins:netbox_hedgehog:switchportzone_add')
        data = {
            'switch_class': self.sw.pk,
            'zone_name': 'f2-zone',
            'zone_type': PortZoneTypeChoices.SERVER,
            'port_spec': '5-8',
            'breakout_option': self.breakout.pk,
            'allocation_strategy': AllocationStrategyChoices.SEQUENTIAL,
            'priority': 200,
            # transceiver_module_type intentionally omitted
        }
        response = self.client.post(url, data)
        self.assertEqual(
            response.status_code, 302,
            f'F2: POST with no transceiver must redirect (302); got {response.status_code}. '
            f'Form errors: {response.context["form"].errors if response.context else "(no context)"}',
        )
        zone = SwitchPortZone.objects.filter(
            switch_class=self.sw, zone_name='f2-zone'
        ).first()
        self.assertIsNotNone(zone, 'F2: SwitchPortZone must be created')
        self.assertIsNone(
            zone.transceiver_module_type_id,
            'F2: transceiver_module_type must be null on saved zone',
        )


# ---------------------------------------------------------------------------
# F3 — POST PSC edit clearing transceiver → 302
# ---------------------------------------------------------------------------

class PlanServerConnectionEditClearTransceiverTestCase(TestCase):
    """
    F3: POST to planserverconnection_edit with transceiver_module_type cleared
    must return HTTP 302 (connection updated to null transceiver).

    RED: currently the form's required=True means clearing → 200 + error.
    """

    @classmethod
    def setUpTestData(cls):
        _make_form_fixtures(cls)
        cls.plan, cls.sc, cls.sw, cls.zone, cls.nic = _make_minimal_plan(cls)
        from netbox_hedgehog.tests.test_topology_planning import get_test_transceiver_module_type
        xcvr = get_test_transceiver_module_type()
        # Create connection with transceiver set; we'll clear it in the test.
        cls.conn = PlanServerConnection.objects.create(
            server_class=cls.sc, connection_id='fe-f3',
            nic=cls.nic, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=cls.zone, speed=200, port_type='data',
            transceiver_module_type=xcvr,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_f3_edit_clearing_transceiver_redirects(self):
        """F3: POST edit with blank transceiver → 302, connection updated to null FK."""
        url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_edit',
            kwargs={'pk': self.conn.pk},
        )
        data = {
            'server_class': self.sc.pk,
            'connection_id': 'fe-f3',
            'nic': self.nic.pk,
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_zone': self.zone.pk,
            'speed': 200,
            'port_type': 'data',
            # transceiver_module_type cleared (omitted from POST data)
        }
        response = self.client.post(url, data)
        self.assertEqual(
            response.status_code, 302,
            f'F3: Clearing transceiver must redirect (302); got {response.status_code}. '
            f'Form errors: {response.context["form"].errors if response.context else "(no context)"}',
        )
        self.conn.refresh_from_db()
        self.assertIsNone(
            self.conn.transceiver_module_type_id,
            'F3: transceiver_module_type must be null after clearing',
        )


# ---------------------------------------------------------------------------
# F4 — POST SwitchPortZone edit clearing transceiver → 302
# ---------------------------------------------------------------------------

class SwitchPortZoneEditClearTransceiverTestCase(TestCase):
    """
    F4: POST to switchportzone_edit clearing transceiver_module_type → 302.

    RED: currently returns 200 + required-field error.
    """

    @classmethod
    def setUpTestData(cls):
        _make_form_fixtures(cls)
        cls.plan, cls.sc, cls.sw, _, cls.nic = _make_minimal_plan(cls)
        from netbox_hedgehog.tests.test_topology_planning import get_test_transceiver_module_type
        xcvr = get_test_transceiver_module_type()
        # Zone with transceiver set; we'll clear it.
        cls.zone_edit = SwitchPortZone.objects.create(
            switch_class=cls.sw, zone_name='f4-zone-edit',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='9-12',
            breakout_option=cls.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=300,
            transceiver_module_type=xcvr,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_f4_edit_zone_clearing_transceiver_redirects(self):
        """F4: POST zone edit with blank transceiver → 302, zone updated to null FK."""
        url = reverse(
            'plugins:netbox_hedgehog:switchportzone_edit',
            kwargs={'pk': self.zone_edit.pk},
        )
        data = {
            'switch_class': self.sw.pk,
            'zone_name': 'f4-zone-edit',
            'zone_type': PortZoneTypeChoices.SERVER,
            'port_spec': '9-12',
            'breakout_option': self.breakout.pk,
            'allocation_strategy': AllocationStrategyChoices.SEQUENTIAL,
            'priority': 300,
            # transceiver_module_type cleared
        }
        response = self.client.post(url, data)
        self.assertEqual(
            response.status_code, 302,
            f'F4: Clearing zone transceiver must redirect (302); got {response.status_code}. '
            f'Form errors: {response.context["form"].errors if response.context else "(no context)"}',
        )
        self.zone_edit.refresh_from_db()
        self.assertIsNone(
            self.zone_edit.transceiver_module_type_id,
            'F4: zone transceiver_module_type must be null after clearing',
        )


# ---------------------------------------------------------------------------
# F5 — GET add form: transceiver not required; no flat fields present
# ---------------------------------------------------------------------------

class PlanServerConnectionFormGetTestCase(TestCase):
    """
    F5: GET planserverconnection_add must return:
      - HTTP 200
      - transceiver_module_type field not marked required (no asterisk / required attr)
      - no cage_type / medium / connector / standard fields (removed by migration)

    RED:
      - Currently transceiver_module_type.required = True → asterisk present
      - Currently flat fields are in Meta.fields → rendered in the form
    """

    @classmethod
    def setUpTestData(cls):
        _make_form_fixtures(cls)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_f5_add_form_loads(self):
        """F5a: GET planserverconnection_add → 200."""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_f5_transceiver_field_not_required_in_form(self):
        """F5b: transceiver_module_type must not be marked required on the rendered form.

        After GREEN: form field required=False → no required marker in HTML.
        Currently: required=True → the form HTML will contain required attributes.
        """
        from netbox_hedgehog.forms.topology_planning import PlanServerConnectionForm
        form = PlanServerConnectionForm()
        transceiver_field = form.fields.get('transceiver_module_type')
        self.assertIsNotNone(transceiver_field, 'transceiver_module_type must be a form field')
        self.assertFalse(
            transceiver_field.required,
            'F5b: transceiver_module_type must not be required — '
            'null is valid after simplified-transceiver GREEN implementation',
        )

    def test_f5_zone_form_transceiver_not_required(self):
        """F5c: SwitchPortZoneForm.transceiver_module_type must not be required."""
        from netbox_hedgehog.forms.topology_planning import SwitchPortZoneForm
        form = SwitchPortZoneForm()
        transceiver_field = form.fields.get('transceiver_module_type')
        self.assertIsNotNone(transceiver_field, 'transceiver_module_type must be a form field')
        self.assertFalse(
            transceiver_field.required,
            'F5c: zone transceiver_module_type must not be required — '
            'null is valid after simplified-transceiver GREEN implementation',
        )

    def test_f5_flat_fields_absent_from_psc_form(self):
        """F5d: cage_type, medium, connector, standard must not be present in PSC form.

        These fields are removed by migration in the GREEN phase (#474 §1.2).
        After GREEN: Meta.fields excludes them; they do not exist on the model.
        Currently: Meta.fields still includes them.
        """
        from netbox_hedgehog.forms.topology_planning import PlanServerConnectionForm
        form = PlanServerConnectionForm()
        flat_fields = ['cage_type', 'medium', 'connector', 'standard']
        present = [f for f in flat_fields if f in form.fields]
        self.assertEqual(
            present, [],
            f'F5d: flat fields {present} must not be present in PlanServerConnectionForm '
            f'after migration removes them from the model',
        )


# ---------------------------------------------------------------------------
# Permission enforcement — null transceiver must not break RBAC
# ---------------------------------------------------------------------------

class NullTransceiverPermissionTestCase(TestCase):
    """
    Permission enforcement: add/edit with null transceiver still requires
    ObjectPermission. Null is now valid but the permission gate must remain.

    This is a regression guard — the DIET-466 null-blocking was not part of
    the permission system, but removing it must not accidentally open the form
    to unauthenticated or unpermissioned users.
    """

    @classmethod
    def setUpTestData(cls):
        _make_form_fixtures(cls)
        cls.plan, cls.sc, cls.sw, cls.zone, cls.nic = _make_minimal_plan(cls)

        # Unpermissioned user — should see 403 or redirect on add attempt
        cls.noperm_user, _ = User.objects.get_or_create(
            username='mxtfm-noperm',
            defaults={'is_staff': True, 'is_superuser': False},
        )
        cls.noperm_user.set_password('pass')
        cls.noperm_user.save()

        # Permissioned user
        cls.perm_user, _ = User.objects.get_or_create(
            username='mxtfm-perm',
            defaults={'is_staff': True, 'is_superuser': False},
        )
        cls.perm_user.set_password('pass')
        cls.perm_user.save()

        perm = ObjectPermission.objects.create(
            name='mxtfm-add-psc',
            actions=['add', 'change'],
        )
        perm.object_types.set([
            ContentType.objects.get_for_model(PlanServerConnection),
            ContentType.objects.get_for_model(SwitchPortZone),
        ])
        perm.users.add(cls.perm_user)

    def setUp(self):
        self.client = Client()

    def _psc_post_data(self, conn_id):
        return {
            'server_class': self.sc.pk,
            'connection_id': conn_id,
            'nic': self.nic.pk,
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_zone': self.zone.pk,
            'speed': 200,
            'port_type': 'data',
            # no transceiver
        }

    def test_perm_user_can_add_without_transceiver(self):
        """Permissioned user with null transceiver → 302 (after GREEN)."""
        self.client.force_login(self.perm_user)
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.post(url, self._psc_post_data('fe-perm'))
        self.assertEqual(
            response.status_code, 302,
            'Permissioned user must create connection with null transceiver',
        )

    def test_noperm_user_cannot_add(self):
        """Unpermissioned user → not 302 (access denied)."""
        self.client.force_login(self.noperm_user)
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.post(url, self._psc_post_data('fe-noperm'))
        self.assertNotEqual(
            response.status_code, 302,
            'Unpermissioned user must not be able to create connection',
        )
