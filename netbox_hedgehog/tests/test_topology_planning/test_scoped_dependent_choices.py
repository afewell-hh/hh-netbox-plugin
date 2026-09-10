"""
Plan-scoped dependent form choices for PlanServerConnection (DIET-645).

#618 finding G8: the initial add form offered every NIC and target zone in the
install. A user could pick an option the form itself presented, then have it
rejected on submit with Django's generic "Select a valid choice" -- because the
queryset only narrows once server_class is resolvable.

These tests pin the corrected contract:
  - before a server class is chosen, `nic` and `target_zone` offer NOTHING and
    say why;
  - once chosen, both are constrained to that server class and its plan;
  - model/API integrity validation is unchanged (forged POSTs still rejected).

`nic` and `target_zone` are asserted together throughout so the two cannot drift.
"""

import re

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
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
from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic

User = get_user_model()

ADD_URL = 'plugins:netbox_hedgehog:planserverconnection_add'
EDIT_URL = 'plugins:netbox_hedgehog:planserverconnection_edit'


class ScopedDependentChoicesTestCase(TestCase):
    """Two plans, three server classes: enough to prove both scoping axes."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='scope-admin', password='pass', is_staff=True, is_superuser=True,
        )
        cls.limited_user = User.objects.create_user(
            username='scope-limited', password='pass', is_staff=True, is_superuser=False,
        )

        mfg, _ = Manufacturer.objects.get_or_create(name='Scope-Mfg', defaults={'slug': 'scope-mfg'})
        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfg, model='Scope-SRV', defaults={'slug': 'scope-srv'},
        )
        switch_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfg, model='Scope-SW', defaults={'slug': 'scope-sw'},
        )
        ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=switch_dt,
            defaults={
                'native_speed': 200, 'uplink_ports': 4,
                'supported_breakouts': ['1x200g'], 'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
            },
        )
        breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x200g-scope',
            defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
        )

        def make_plan(name, sc_id, zone_name):
            plan = TopologyPlan.objects.create(name=name, status=TopologyPlanStatusChoices.DRAFT)
            server_class = PlanServerClass.objects.create(
                plan=plan, server_class_id=sc_id, server_device_type=cls.server_dt, quantity=1,
            )
            switch_class = PlanSwitchClass.objects.create(
                plan=plan, switch_class_id=f'{sc_id}-leaf',
                fabric_name=FabricTypeChoices.FRONTEND,
                fabric_class=FabricClassChoices.MANAGED,
                hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
                device_type_extension=ext,
                uplink_ports_per_switch=0, mclag_pair=False,
                override_quantity=2, redundancy_type='eslag',
            )
            zone = SwitchPortZone.objects.create(
                switch_class=switch_class, zone_name=zone_name,
                zone_type=PortZoneTypeChoices.SERVER, port_spec='1-64',
                breakout_option=breakout,
                allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
            )
            return plan, server_class, zone

        # Plan A -- the in-scope context
        cls.plan_a, cls.sc_a, cls.zone_a = make_plan('Scope-Plan-A', 'gpu-a', 'zone-a-downlinks')
        cls.nic_a = get_test_server_nic(cls.sc_a, nic_id='nic-a')

        # Second server class in the SAME plan -- proves server-class scoping
        cls.sc_a2 = PlanServerClass.objects.create(
            plan=cls.plan_a, server_class_id='cpu-a2',
            server_device_type=cls.server_dt, quantity=1,
        )
        cls.nic_a2 = get_test_server_nic(cls.sc_a2, nic_id='nic-a2')

        # Plan B -- proves plan scoping
        cls.plan_b, cls.sc_b, cls.zone_b = make_plan('Scope-Plan-B', 'gpu-b', 'zone-b-downlinks')
        cls.nic_b = get_test_server_nic(cls.sc_b, nic_id='nic-b')

        cls.existing = PlanServerConnection.objects.create(
            server_class=cls.sc_a, connection_id='existing',
            nic=cls.nic_a, port_index=0, ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.ALTERNATING,
            target_zone=cls.zone_a, speed=200, port_type='data',
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='scope-admin', password='pass')

    def _valid_payload(self, **overrides):
        payload = {
            'server_class': self.sc_a.pk,
            'connection_id': 'new-conn',
            'connection_name': 'new',
            'nic': self.nic_a.pk,
            'port_index': 0,
            'ports_per_connection': 1,
            'hedgehog_conn_type': ConnectionTypeChoices.UNBUNDLED,
            'distribution': ConnectionDistributionChoices.ALTERNATING,
            'target_zone': self.zone_a.pk,
            'speed': 200,
            'port_type': 'data',
        }
        payload.update(overrides)
        return payload

    # --- 1. Initial add view: no choices offered before a server class -------

    def test_initial_add_form_offers_no_nic_choices(self):
        """G8: the unbound add form must not offer NICs from any plan."""
        response = self.client.get(reverse(ADD_URL))
        self.assertEqual(response.status_code, 200)
        qs = response.context['form'].fields['nic'].queryset
        self.assertEqual(
            list(qs), [],
            'Unbound add form must offer no NIC choices until a server class is selected',
        )

    def test_initial_add_form_offers_no_target_zone_choices(self):
        """Asserted alongside nic so the two fields cannot drift apart."""
        response = self.client.get(reverse(ADD_URL))
        self.assertEqual(response.status_code, 200)
        qs = response.context['form'].fields['target_zone'].queryset
        self.assertEqual(
            list(qs), [],
            'Unbound add form must offer no target zone choices until a server class is selected',
        )

    def _rendered_option_values(self, html, field_name):
        """
        Return the selectable option values inside <select name="field_name">.

        Scoped to the specific control on purpose: a bare `value="4"` search
        matches any element on the page carrying that value (other selects,
        numeric inputs), which produces false failures unrelated to this field.
        """
        match = re.search(
            rf'<select[^>]*\bname="{re.escape(field_name)}"[^>]*>(.*?)</select>',
            html, re.DOTALL,
        )
        self.assertIsNotNone(match, f'No <select name="{field_name}"> was rendered')
        return [
            value
            for value in re.findall(r'<option[^>]*\bvalue="([^"]*)"', match.group(1))
            if value  # ignore the empty placeholder option
        ]

    def test_initial_add_form_html_omits_foreign_options(self):
        """The rendered controls themselves must present no out-of-scope options."""
        response = self.client.get(reverse(ADD_URL))
        html = response.content.decode()

        self.assertEqual(
            self._rendered_option_values(html, 'nic'), [],
            'Unbound add form must render no selectable NIC options',
        )
        self.assertEqual(
            self._rendered_option_values(html, 'target_zone'), [],
            'Unbound add form must render no selectable target zone options',
        )

    def test_initial_add_form_explains_the_prerequisite(self):
        """The user must be told why the controls are empty."""
        response = self.client.get(reverse(ADD_URL))
        form = response.context['form']
        self.assertIn('Select a server class first', form.fields['nic'].help_text)
        self.assertIn('Select a server class first', form.fields['target_zone'].help_text)

    # --- 2. Dependent filtering once a server class is known ----------------

    def test_choices_scoped_to_selected_server_class(self):
        """With server_class bound, only that class's NICs and plan's zones appear."""
        response = self.client.post(reverse(ADD_URL), data=self._valid_payload(connection_id=''))
        form = response.context['form']

        nic_pks = set(form.fields['nic'].queryset.values_list('pk', flat=True))
        self.assertIn(self.nic_a.pk, nic_pks)
        self.assertNotIn(self.nic_a2.pk, nic_pks, 'Same-plan other server class NIC must be excluded')
        self.assertNotIn(self.nic_b.pk, nic_pks, 'Cross-plan NIC must be excluded')

        zone_pks = set(form.fields['target_zone'].queryset.values_list('pk', flat=True))
        self.assertIn(self.zone_a.pk, zone_pks)
        self.assertNotIn(self.zone_b.pk, zone_pks, 'Cross-plan zone must be excluded')

    # --- 3. Valid scoped create --------------------------------------------

    def test_valid_scoped_post_creates_connection(self):
        before = PlanServerConnection.objects.count()
        response = self.client.post(reverse(ADD_URL), data=self._valid_payload(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlanServerConnection.objects.count(), before + 1)
        self.assertTrue(
            PlanServerConnection.objects.filter(
                server_class=self.sc_a, connection_id='new-conn', nic=self.nic_a,
            ).exists()
        )

    # --- 4. Forged cross-scope POSTs still rejected -------------------------

    def test_forged_cross_server_class_nic_is_rejected(self):
        """Scoping the widget must not weaken server-class enforcement."""
        before = PlanServerConnection.objects.count()
        response = self.client.post(
            reverse(ADD_URL), data=self._valid_payload(nic=self.nic_a2.pk),
        )
        self.assertEqual(response.status_code, 200, 'Must re-render, not redirect')
        self.assertEqual(PlanServerConnection.objects.count(), before)
        self.assertTrue(response.context['form'].errors)

    def test_forged_cross_plan_nic_is_rejected(self):
        before = PlanServerConnection.objects.count()
        response = self.client.post(
            reverse(ADD_URL), data=self._valid_payload(nic=self.nic_b.pk),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlanServerConnection.objects.count(), before)
        self.assertTrue(response.context['form'].errors)

    def test_forged_cross_plan_target_zone_is_rejected(self):
        before = PlanServerConnection.objects.count()
        response = self.client.post(
            reverse(ADD_URL), data=self._valid_payload(target_zone=self.zone_b.pk),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlanServerConnection.objects.count(), before)
        self.assertTrue(response.context['form'].errors)

    # --- 5. Edit behaviour --------------------------------------------------

    def test_edit_form_scopes_to_instance_server_class(self):
        """Editing resolves scope from the instance, not from submitted data."""
        response = self.client.get(reverse(EDIT_URL, args=[self.existing.pk]))
        self.assertEqual(response.status_code, 200)
        form = response.context['form']

        nic_pks = set(form.fields['nic'].queryset.values_list('pk', flat=True))
        self.assertIn(self.nic_a.pk, nic_pks, 'Current selection must remain offered')
        self.assertNotIn(self.nic_a2.pk, nic_pks)
        self.assertNotIn(self.nic_b.pk, nic_pks)

        zone_pks = set(form.fields['target_zone'].queryset.values_list('pk', flat=True))
        self.assertIn(self.zone_a.pk, zone_pks, 'Current selection must remain offered')
        self.assertNotIn(self.zone_b.pk, zone_pks)

    def test_edit_saves_within_scope(self):
        payload = self._valid_payload(connection_id='existing', connection_name='renamed')
        response = self.client.post(
            reverse(EDIT_URL, args=[self.existing.pk]), data=payload, follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.connection_name, 'renamed')

    # --- 6. ObjectPermission behaviour --------------------------------------

    def test_add_view_denied_without_permission(self):
        self.client.logout()
        self.client.login(username='scope-limited', password='pass')
        response = self.client.get(reverse(ADD_URL))
        self.assertIn(response.status_code, (403, 302))

    def test_add_view_allowed_with_objectpermission(self):
        self.client.logout()
        self.client.login(username='scope-limited', password='pass')

        perm = ObjectPermission.objects.create(name='scope-add', actions=['view', 'add', 'change'])
        perm.users.add(self.limited_user)
        perm.object_types.add(ContentType.objects.get_for_model(PlanServerConnection))

        response = self.client.get(reverse(ADD_URL))
        self.assertEqual(response.status_code, 200)
        # Scoping must hold for permission-limited users too.
        self.assertEqual(list(response.context['form'].fields['nic'].queryset), [])
        self.assertEqual(list(response.context['form'].fields['target_zone'].queryset), [])
