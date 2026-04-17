"""
RED tests for #465 — mandatory transceiver enforcement on forms and models.

Acceptance cases covered:
  A1  — POST PSC add-form, transceiver blank → 200, required-field error
  A2  — POST PSC add-form, valid transceiver → 302
  A3  — POST SwitchPortZone add-form, transceiver blank → 200, required-field error
  A4  — POST SwitchPortZone add-form, valid transceiver → 302
  A5  — GET legacy null-transceiver PSC detail → 200 (readable)
  A6  — POST PSC edit-form, existing null row, no transceiver → 200, error
  A7  — POST PSC edit-form, existing null row, valid transceiver → 302
  A8  — POST SwitchPortZone edit-form, existing null row, no transceiver → 200, error
  A17 — Permission enforcement on add/edit is unchanged under tightened validation

Model clean() enforcement:
  MC1 — SwitchPortZone.full_clean() raises ValidationError when FK null
  MC2 — PlanServerConnection.full_clean() raises ValidationError when FK null
  MC3 — SwitchPortZone.full_clean() passes when FK set
  MC4 — PlanServerConnection.full_clean() passes when FK set

All tests in this file are RED until GREEN adds required=True to both forms
and the required-check to both model clean() methods.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import DeviceType, Manufacturer
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
from netbox_hedgehog.tests.test_topology_planning import (
    get_test_nic_module_type,
    get_test_server_nic,
    get_test_transceiver_module_type,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Exact validation messages from the spec
# ---------------------------------------------------------------------------

_CONN_REQUIRED_MSG = 'A transceiver ModuleType is required for every server connection.'
_ZONE_REQUIRED_MSG = 'A transceiver ModuleType is required for every switch port zone.'


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_fixtures(cls):
    """Create manufacturer, switch/server device types, plan, classes, zone, NIC."""
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name='MandXcvr-Vendor', defaults={'slug': 'mandxcvr-vendor'}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MandXcvr-SRV', defaults={'slug': 'mandxcvr-srv'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model='MandXcvr-SW', defaults={'slug': 'mandxcvr-sw'}
    )
    cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=cls.switch_dt,
        defaults={
            'native_speed': 200,
            'uplink_ports': 0,
            'supported_breakouts': ['1x200g'],
            'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    cls.breakout, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x200g-mandxcvr',
        defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
    )
    cls.plan = TopologyPlan.objects.create(
        name='MandXcvr-Plan', status=TopologyPlanStatusChoices.DRAFT,
    )
    cls.server_class = PlanServerClass.objects.create(
        plan=cls.plan, server_class_id='gpu',
        server_device_type=cls.server_dt, quantity=2,
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
    # Zone created WITHOUT transceiver (tests null-bearing legacy row)
    cls.null_zone = SwitchPortZone.objects.create(
        switch_class=cls.switch_class, zone_name='server-downlinks',
        zone_type=PortZoneTypeChoices.SERVER, port_spec='1-64',
        breakout_option=cls.breakout,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
    )
    cls.nic = PlanServerNIC.objects.create(
        server_class=cls.server_class, nic_id='nic-fe',
        module_type=get_test_nic_module_type(),
    )
    # PSC created WITHOUT transceiver (tests null-bearing legacy row)
    cls.null_conn = PlanServerConnection.objects.create(
        server_class=cls.server_class, connection_id='fe-null',
        nic=cls.nic, port_index=0, ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        target_zone=cls.null_zone, speed=200, port_type='data',
    )
    cls.xcvr_mt = get_test_transceiver_module_type()


def _grant_full_permission(user):
    """Grant view+add+change+delete on all relevant models via ObjectPermission."""
    from netbox_hedgehog.models.topology_planning import (
        SwitchPortZone, PlanServerConnection, TopologyPlan,
    )
    for model in (TopologyPlan, SwitchPortZone, PlanServerConnection):
        ct = ContentType.objects.get_for_model(model)
        perm, _ = ObjectPermission.objects.get_or_create(
            name=f'mxt-perm-{model.__name__}',
            defaults={'actions': ['view', 'add', 'change', 'delete']},
        )
        perm.object_types.add(ct)
        perm.users.add(user)


# ---------------------------------------------------------------------------
# Group MC — model clean() enforcement
# ---------------------------------------------------------------------------

class MandatoryTransceiverModelCleanTestCase(TestCase):
    """
    MC1–MC4: full_clean() raises ValidationError when transceiver FK is null.

    These are the innermost contract tests — they validate the model-layer
    enforcement independent of any form or view path.

    RED until SwitchPortZone.clean() and PlanServerConnection.clean()
    add the required-FK check.
    """

    @classmethod
    def setUpTestData(cls):
        _make_fixtures(cls)

    # ------------------------------------------------------------------
    # MC1 — SwitchPortZone.full_clean() rejects null transceiver
    # ------------------------------------------------------------------

    def test_zone_clean_rejects_null_transceiver(self):
        """
        MC1: SwitchPortZone.full_clean() must raise ValidationError with the
        exact required-field message when transceiver_module_type is null.
        """
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='clean-test-zone',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-10',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=50,
            transceiver_module_type=None,
        )
        with self.assertRaises(ValidationError) as ctx:
            zone.full_clean()
        errors = ctx.exception.message_dict
        self.assertIn(
            'transceiver_module_type', errors,
            'ValidationError must be keyed on transceiver_module_type',
        )
        self.assertIn(
            _ZONE_REQUIRED_MSG,
            errors['transceiver_module_type'],
            f'Error message must be exactly: {_ZONE_REQUIRED_MSG!r}',
        )

    # ------------------------------------------------------------------
    # MC2 — PlanServerConnection.full_clean() rejects null transceiver
    # ------------------------------------------------------------------

    def test_connection_clean_rejects_null_transceiver(self):
        """
        MC2: PlanServerConnection.full_clean() must raise ValidationError with the
        exact required-field message when transceiver_module_type is null.
        """
        conn = PlanServerConnection(
            server_class=self.server_class,
            connection_id='clean-test-conn',
            nic=self.nic,
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=self.null_zone,
            speed=200,
            port_type='data',
            transceiver_module_type=None,
        )
        with self.assertRaises(ValidationError) as ctx:
            conn.full_clean()
        errors = ctx.exception.message_dict
        self.assertIn(
            'transceiver_module_type', errors,
            'ValidationError must be keyed on transceiver_module_type',
        )
        self.assertIn(
            _CONN_REQUIRED_MSG,
            errors['transceiver_module_type'],
            f'Error message must be exactly: {_CONN_REQUIRED_MSG!r}',
        )

    # ------------------------------------------------------------------
    # MC3 — SwitchPortZone.full_clean() passes when FK is set
    # ------------------------------------------------------------------

    def test_zone_clean_passes_with_transceiver(self):
        """
        MC3: SwitchPortZone.full_clean() must not raise when transceiver_module_type
        is set to a valid Network Transceiver ModuleType.
        """
        zone = SwitchPortZone(
            switch_class=self.switch_class,
            zone_name='clean-pass-zone',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-10',
            breakout_option=self.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=60,
            transceiver_module_type=self.xcvr_mt,
        )
        try:
            zone.full_clean()
        except ValidationError as exc:
            if 'transceiver_module_type' in exc.message_dict:
                self.fail(
                    f'full_clean() raised transceiver_module_type error unexpectedly: '
                    f'{exc.message_dict["transceiver_module_type"]}'
                )

    # ------------------------------------------------------------------
    # MC4 — PlanServerConnection.full_clean() passes when FK is set
    # ------------------------------------------------------------------

    def test_connection_clean_passes_with_transceiver(self):
        """
        MC4: PlanServerConnection.full_clean() must not raise the required-field
        error when transceiver_module_type is set.
        """
        conn = PlanServerConnection(
            server_class=self.server_class,
            connection_id='clean-pass-conn',
            nic=self.nic,
            port_index=1,
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=self.null_zone,
            speed=200,
            port_type='data',
            transceiver_module_type=self.xcvr_mt,
        )
        try:
            conn.full_clean()
        except ValidationError as exc:
            errors = exc.message_dict
            if 'transceiver_module_type' in errors and _CONN_REQUIRED_MSG in errors.get(
                'transceiver_module_type', []
            ):
                self.fail(
                    f'full_clean() raised required-field error unexpectedly: '
                    f'{errors["transceiver_module_type"]}'
                )


# ---------------------------------------------------------------------------
# Group A-form — ServerConnection add/edit form enforcement
# ---------------------------------------------------------------------------

class MandatoryTransceiverConnectionFormTestCase(TestCase):
    """
    A1, A2, A5, A6, A7: PlanServerConnection add/edit form enforcement.

    A1 — POST add without transceiver → 200, required-field error in rendered HTML
    A2 — POST add with valid transceiver → 302 redirect
    A5 — GET detail of legacy null-transceiver row → 200 (readable, not blocked)
    A6 — POST edit of legacy null row without transceiver → 200, error
    A7 — POST edit of legacy null row with valid transceiver → 302

    RED until PlanServerConnectionForm gets required=True on transceiver_module_type.
    """

    @classmethod
    def setUpTestData(cls):
        _make_fixtures(cls)
        cls.superuser = User.objects.create_user(
            username='mxt-conn-admin', password='pass',
            is_staff=True, is_superuser=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def _valid_post_data(self, connection_id='fe-new', transceiver_pk=None):
        data = {
            'server_class': self.server_class.pk,
            'connection_id': connection_id,
            'nic': self.nic.pk,
            'port_index': 1,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_zone': self.null_zone.pk,
            'speed': 200,
            'port_type': 'data',
        }
        if transceiver_pk:
            data['transceiver_module_type'] = transceiver_pk
        return data

    # A1
    def test_add_form_rejects_missing_transceiver(self):
        """
        A1: POST PSC add form without transceiver_module_type → 200, error
        containing the required-field message.
        """
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.post(url, self._valid_post_data())
        self.assertEqual(
            response.status_code, 200,
            'Form must re-render (200) when transceiver_module_type is blank',
        )
        self.assertContains(
            response, _CONN_REQUIRED_MSG,
            msg_prefix='Required-field error message must appear in rendered HTML',
        )
        self.assertFalse(
            PlanServerConnection.objects.filter(connection_id='fe-new').exists(),
            'No PSC must be created when transceiver is missing',
        )

    # A2
    def test_add_form_accepts_valid_transceiver(self):
        """A2: POST PSC add form with valid transceiver → 302 redirect."""
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.post(
            url, self._valid_post_data(transceiver_pk=self.xcvr_mt.pk)
        )
        self.assertEqual(
            response.status_code, 302,
            f'Expected 302 redirect on valid submission; got {response.status_code}',
        )
        self.assertTrue(
            PlanServerConnection.objects.filter(
                connection_id='fe-new',
                transceiver_module_type=self.xcvr_mt,
            ).exists(),
            'Created PSC must have transceiver_module_type set',
        )

    # A5
    def test_detail_view_readable_for_null_transceiver_row(self):
        """
        A5: GET detail of a legacy null-transceiver PSC → 200.
        Legacy rows must remain readable even though they are now invalid state.
        """
        url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_detail',
            args=[self.null_conn.pk],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # A6
    def test_edit_form_rejects_missing_transceiver_on_null_row(self):
        """
        A6: POST edit form for a legacy null-transceiver PSC without providing
        transceiver → 200, required-field error. The row is not saved.
        """
        url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_edit',
            args=[self.null_conn.pk],
        )
        post_data = {
            'server_class': self.server_class.pk,
            'connection_id': self.null_conn.connection_id,
            'nic': self.nic.pk,
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_zone': self.null_zone.pk,
            'speed': 200,
            'port_type': 'data',
            # transceiver_module_type intentionally omitted
        }
        response = self.client.post(url, post_data)
        self.assertEqual(
            response.status_code, 200,
            'Edit form must re-render (200) when transceiver_module_type is blank',
        )
        self.assertContains(
            response, _CONN_REQUIRED_MSG,
            msg_prefix='Required-field error message must appear in edit form response',
        )
        self.null_conn.refresh_from_db()
        self.assertIsNone(
            self.null_conn.transceiver_module_type,
            'Row must not be modified when validation fails',
        )

    # A7
    def test_edit_form_accepts_valid_transceiver_for_null_row(self):
        """
        A7: POST edit form for legacy null-transceiver PSC with valid transceiver
        → 302 redirect, row updated.
        """
        url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_edit',
            args=[self.null_conn.pk],
        )
        post_data = {
            'server_class': self.server_class.pk,
            'connection_id': self.null_conn.connection_id,
            'nic': self.nic.pk,
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_zone': self.null_zone.pk,
            'speed': 200,
            'port_type': 'data',
            'transceiver_module_type': self.xcvr_mt.pk,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(
            response.status_code, 302,
            f'Expected redirect after successful edit; got {response.status_code}',
        )
        self.null_conn.refresh_from_db()
        self.assertEqual(
            self.null_conn.transceiver_module_type_id, self.xcvr_mt.pk,
            'PSC must have transceiver_module_type updated after valid edit',
        )


# ---------------------------------------------------------------------------
# Group A-zone — SwitchPortZone add/edit form enforcement
# ---------------------------------------------------------------------------

class MandatoryTransceiverZoneFormTestCase(TestCase):
    """
    A3, A4, A8: SwitchPortZone add/edit form enforcement.

    A3 — POST add without transceiver → 200, required-field error
    A4 — POST add with valid transceiver → 302
    A8 — POST edit of legacy null zone without transceiver → 200, error

    RED until SwitchPortZoneForm gets required=True on transceiver_module_type.
    """

    @classmethod
    def setUpTestData(cls):
        _make_fixtures(cls)
        cls.superuser = User.objects.create_user(
            username='mxt-zone-admin', password='pass',
            is_staff=True, is_superuser=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def _valid_post_data(self, zone_name='new-zone', transceiver_pk=None):
        data = {
            'switch_class': self.switch_class.pk,
            'zone_name': zone_name,
            'zone_type': PortZoneTypeChoices.SERVER,
            'port_spec': '1-16',
            'breakout_option': self.breakout.pk,
            'allocation_strategy': AllocationStrategyChoices.SEQUENTIAL,
            'priority': 50,
        }
        if transceiver_pk:
            data['transceiver_module_type'] = transceiver_pk
        return data

    # A3
    def test_add_form_rejects_missing_transceiver(self):
        """
        A3: POST SwitchPortZone add form without transceiver_module_type
        → 200, required-field error message in rendered HTML.
        """
        url = reverse('plugins:netbox_hedgehog:switchportzone_add')
        response = self.client.post(url, self._valid_post_data())
        self.assertEqual(
            response.status_code, 200,
            'Zone add form must re-render (200) when transceiver_module_type is blank',
        )
        self.assertContains(
            response, _ZONE_REQUIRED_MSG,
            msg_prefix='Required-field error message must appear in rendered HTML',
        )
        self.assertFalse(
            SwitchPortZone.objects.filter(zone_name='new-zone').exists(),
            'No zone must be created when transceiver is missing',
        )

    # A4
    def test_add_form_accepts_valid_transceiver(self):
        """A4: POST SwitchPortZone add form with valid transceiver → 302."""
        url = reverse('plugins:netbox_hedgehog:switchportzone_add')
        response = self.client.post(
            url, self._valid_post_data(transceiver_pk=self.xcvr_mt.pk)
        )
        self.assertEqual(
            response.status_code, 302,
            f'Expected redirect on valid submission; got {response.status_code}',
        )
        self.assertTrue(
            SwitchPortZone.objects.filter(
                zone_name='new-zone',
                transceiver_module_type=self.xcvr_mt,
            ).exists(),
            'Created zone must have transceiver_module_type set',
        )

    # A8
    def test_edit_form_rejects_missing_transceiver_on_null_zone(self):
        """
        A8: POST edit form for a legacy null-transceiver zone without transceiver
        → 200, required-field error.
        """
        url = reverse(
            'plugins:netbox_hedgehog:switchportzone_edit',
            args=[self.null_zone.pk],
        )
        post_data = {
            'switch_class': self.switch_class.pk,
            'zone_name': self.null_zone.zone_name,
            'zone_type': self.null_zone.zone_type,
            'port_spec': self.null_zone.port_spec,
            'breakout_option': self.breakout.pk,
            'allocation_strategy': AllocationStrategyChoices.SEQUENTIAL,
            'priority': 100,
            # transceiver_module_type intentionally omitted
        }
        response = self.client.post(url, post_data)
        self.assertEqual(
            response.status_code, 200,
            'Zone edit form must re-render (200) when transceiver is omitted',
        )
        self.assertContains(
            response, _ZONE_REQUIRED_MSG,
            msg_prefix='Required-field error must appear in zone edit response',
        )
        self.null_zone.refresh_from_db()
        self.assertIsNone(
            self.null_zone.transceiver_module_type,
            'Zone must not be modified when validation fails',
        )


# ---------------------------------------------------------------------------
# Group A17 — Permission enforcement (no regression)
# ---------------------------------------------------------------------------

class MandatoryTransceiverPermissionTestCase(TestCase):
    """
    A17: Permission enforcement is unchanged under tightened validation.

    An unpermissioned user receives 403 on add/edit endpoints regardless of
    whether they supply a transceiver or not.
    """

    @classmethod
    def setUpTestData(cls):
        _make_fixtures(cls)
        # User with no permissions at all
        cls.noperm_user = User.objects.create_user(
            username='mxt-noperm', password='pass', is_staff=True,
        )
        # User with view-only permission
        cls.viewonly_user = User.objects.create_user(
            username='mxt-viewonly', password='pass', is_staff=True,
        )
        ct_psc = ContentType.objects.get_for_model(PlanServerConnection)
        ct_zone = ContentType.objects.get_for_model(SwitchPortZone)
        view_perm, _ = ObjectPermission.objects.get_or_create(
            name='mxt-viewonly-perm',
            defaults={'actions': ['view']},
        )
        view_perm.object_types.add(ct_psc, ct_zone)
        view_perm.users.add(cls.viewonly_user)

    def _login(self, username):
        self.client = Client()
        self.client.login(username=username, password='pass')

    def test_connection_add_denied_without_add_permission(self):
        """A17a: POST add PSC without add permission → 403."""
        self._login('mxt-viewonly')
        url = reverse('plugins:netbox_hedgehog:planserverconnection_add')
        response = self.client.post(url, {
            'server_class': self.server_class.pk,
            'connection_id': 'perm-test',
            'transceiver_module_type': self.xcvr_mt.pk,
        })
        self.assertIn(
            response.status_code, (403, 302),
            'View-only user must not be able to add a server connection',
        )
        if response.status_code == 302:
            self.assertIn('login', response['Location'])

    def test_zone_add_denied_without_add_permission(self):
        """A17b: POST add SwitchPortZone without add permission → 403."""
        self._login('mxt-viewonly')
        url = reverse('plugins:netbox_hedgehog:switchportzone_add')
        response = self.client.post(url, {
            'switch_class': self.switch_class.pk,
            'zone_name': 'perm-zone',
            'transceiver_module_type': self.xcvr_mt.pk,
        })
        self.assertIn(
            response.status_code, (403, 302),
            'View-only user must not be able to add a switch port zone',
        )

    def test_connection_edit_denied_without_change_permission(self):
        """A17c: POST edit PSC without change permission → 403."""
        self._login('mxt-viewonly')
        url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_edit',
            args=[self.null_conn.pk],
        )
        response = self.client.post(url, {
            'transceiver_module_type': self.xcvr_mt.pk,
        })
        self.assertIn(
            response.status_code, (403, 302),
            'View-only user must not be able to edit a server connection',
        )
