"""
DIET-611 Phase 3 RED tests — UX-accurate integration + RBAC for rack placement.

Encodes the approved #610 UX contract:
  * Full AGENTS UX-TDD flow for the changed PlanServerClass form:
      list 200, add-form 200, valid POST->302, detail render, edit, delete,
      no-permission 403, ObjectPermission success.
  * Canonical disabled-state normalization via form and API.
  * Rack authorization gating: generation of a rack-enabled plan requires
      dcim.add_rack / dcim.delete_rack.
  * PlanLocalityRange read-only view RBAC (view_planlocalityrange 403/200).

References the final intended fields/URLs/permissions which do NOT exist yet ->
expected to FAIL/ERROR until Phase 4. No production code is added here.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import DeviceType, Manufacturer

from users.models import ObjectPermission

from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic
from netbox_hedgehog.tests.test_topology_planning.test_rack_placement import (
    _make_same_switch_plan,
    _make_server_type,
    _plan_racks,
    _locality_range_model,
)
from netbox_hedgehog.models.topology_planning import (
    PlanServerClass,
    TopologyPlan,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator

User = get_user_model()


# ---------------------------------------------------------------------------
# Full PlanServerClass UX-TDD flow (rack fields present + persisted)
# ---------------------------------------------------------------------------
class PlanServerClassRackUXTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='rack-admin', password='pw', is_staff=True, is_superuser=True,
        )
        cls.regular = User.objects.create_user(
            username='rack-regular', password='pw', is_staff=True,
        )
        cls.server_type = _make_server_type(model='SRV-UX', u_height=2)
        cls.plan = TopologyPlan.objects.create(name='UX-Plan')
        cls.existing = PlanServerClass.objects.create(
            plan=cls.plan, server_class_id='gpu-ux',
            server_device_type=cls.server_type, quantity=8,
        )

    def setUp(self):
        self.client = Client()

    def _post_data(self, **overrides):
        data = {
            'plan': self.plan.pk,
            'server_class_id': 'gpu-new',
            'quantity': 64,
            'gpus_per_server': 8,
            'server_device_type': self.server_type.pk,
            'place_in_racks': True,
            'servers_per_rack': 8,
            'membership_only': False,
        }
        data.update(overrides)
        return data

    def test_list_view_loads(self):
        self.client.login(username='rack-admin', password='pw')
        resp = self.client.get(
            reverse('plugins:netbox_hedgehog:planserverclass_list'))
        self.assertEqual(resp.status_code, 200)

    def test_add_form_loads_and_shows_rack_fields(self):
        self.client.login(username='rack-admin', password='pw')
        resp = self.client.get(
            reverse('plugins:netbox_hedgehog:planserverclass_add'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'place_in_racks')
        self.assertContains(resp, 'servers_per_rack')
        self.assertContains(resp, 'membership_only')

    def test_valid_post_creates_and_redirects(self):
        self.client.login(username='rack-admin', password='pw')
        resp = self.client.post(
            reverse('plugins:netbox_hedgehog:planserverclass_add'),
            self._post_data(), follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        created = PlanServerClass.objects.get(server_class_id='gpu-new')
        self.assertTrue(created.place_in_racks)
        self.assertEqual(created.servers_per_rack, 8)

    def test_detail_view_renders_rack_fields(self):
        self.existing.place_in_racks = True
        self.existing.servers_per_rack = 8
        self.existing.save()
        self.client.login(username='rack-admin', password='pw')
        resp = self.client.get(
            reverse('plugins:netbox_hedgehog:planserverclass_detail',
                    args=[self.existing.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Rack Placement')

    def test_edit_updates_rack_fields(self):
        self.client.login(username='rack-admin', password='pw')
        resp = self.client.post(
            reverse('plugins:netbox_hedgehog:planserverclass_edit',
                    args=[self.existing.pk]),
            self._post_data(server_class_id='gpu-ux', servers_per_rack=4),
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.existing.refresh_from_db()
        self.assertTrue(self.existing.place_in_racks)
        self.assertEqual(self.existing.servers_per_rack, 4)

    def test_delete_removes_object(self):
        self.client.login(username='rack-admin', password='pw')
        resp = self.client.post(
            reverse('plugins:netbox_hedgehog:planserverclass_delete',
                    args=[self.existing.pk]), follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(
            PlanServerClass.objects.filter(pk=self.existing.pk).exists())

    def test_invalid_servers_per_rack_shows_form_error(self):
        self.client.login(username='rack-admin', password='pw')
        resp = self.client.post(
            reverse('plugins:netbox_hedgehog:planserverclass_add'),
            self._post_data(servers_per_rack=''),  # required when enabled
        )
        self.assertEqual(resp.status_code, 200)  # re-render with error
        self.assertFalse(
            PlanServerClass.objects.filter(server_class_id='gpu-new').exists())

    # --- RBAC ---
    def test_add_without_permission_forbidden(self):
        self.client.login(username='rack-regular', password='pw')
        resp = self.client.get(
            reverse('plugins:netbox_hedgehog:planserverclass_add'))
        self.assertEqual(resp.status_code, 403)

    def test_crud_with_object_permission_succeeds(self):
        perm = ObjectPermission.objects.create(
            name='psc-all', actions=['view', 'add', 'change', 'delete'])
        perm.object_types.add(ContentType.objects.get_for_model(PlanServerClass))
        perm.users.add(self.regular)
        self.client.login(username='rack-regular', password='pw')
        resp = self.client.post(
            reverse('plugins:netbox_hedgehog:planserverclass_add'),
            self._post_data(server_class_id='gpu-objperm'), follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            PlanServerClass.objects.filter(server_class_id='gpu-objperm').exists())


# ---------------------------------------------------------------------------
# Canonical disabled-state normalization via form
# ---------------------------------------------------------------------------
class DisabledStateFormNormalizationTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='norm-admin', password='pw', is_staff=True, is_superuser=True,
        )
        cls.server_type = _make_server_type(model='SRV-NORM', u_height=2)
        cls.plan = TopologyPlan.objects.create(name='Norm-UX-Plan')

    def setUp(self):
        self.client = Client()
        self.client.login(username='norm-admin', password='pw')

    def test_form_post_disabled_normalizes_dormant_fields(self):
        resp = self.client.post(
            reverse('plugins:netbox_hedgehog:planserverclass_add'),
            {
                'plan': self.plan.pk,
                'server_class_id': 'gpu-off',
                'quantity': 8,
                'gpus_per_server': 0,
                'server_device_type': self.server_type.pk,
                'place_in_racks': False,
                'servers_per_rack': 8,      # dormant -> must persist NULL
                'membership_only': True,    # dormant -> must persist False
            },
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        sc = PlanServerClass.objects.get(server_class_id='gpu-off')
        self.assertIsNone(sc.servers_per_rack)
        self.assertFalse(sc.membership_only)


# ---------------------------------------------------------------------------
# Rack authorization gating on generation
# ---------------------------------------------------------------------------
class RackGenerationAuthorizationTestCase(TestCase):
    """Generating a rack-enabled plan must require dcim.add_rack/delete_rack."""

    def _grant(self, user, codenames):
        for codename in codenames:
            app_label, code = codename.split('.')
            perm = Permission.objects.get(
                content_type__app_label=app_label, codename=code)
            user.user_permissions.add(perm)

    def _rack_enabled_plan(self, name):
        plan, *_ = _make_same_switch_plan(
            name, quantity=8, num_switches=1,
            place_in_racks=True, servers_per_rack=8,
        )
        return plan

    def setUp(self):
        self.client = Client()
        self.plan = self._rack_enabled_plan('auth-plan')
        self.dcim_base = [
            'dcim.add_device', 'dcim.delete_device',
            'dcim.add_interface', 'dcim.add_cable', 'dcim.delete_cable',
        ]

    def _url(self):
        return reverse('plugins:netbox_hedgehog:topologyplan_generate',
                       args=[self.plan.pk])

    def test_missing_rack_permission_forbidden(self):
        user = User.objects.create_user(
            username='no-rack', password='pw', is_staff=True)
        self._grant(user, ['netbox_hedgehog.change_topologyplan'] + self.dcim_base)
        # Deliberately WITHOUT dcim.add_rack / dcim.delete_rack.
        obj_perm = ObjectPermission.objects.create(
            name='no-rack-plan', actions=['view', 'change'])
        obj_perm.object_types.add(ContentType.objects.get_for_model(TopologyPlan))
        obj_perm.users.add(user)
        self.client.login(username='no-rack', password='pw')

        resp = self.client.post(self._url(), follow=False)
        self.assertIn(resp.status_code, (403, 302))
        # Whatever the redirect, generation must NOT have created racks.
        self.assertEqual(_plan_racks(self.plan).count(), 0,
                         'Rack-enabled generation must be blocked without dcim.add_rack')

    def test_with_rack_permission_succeeds(self):
        user = User.objects.create_user(
            username='has-rack', password='pw', is_staff=True)
        self._grant(user, [
            'netbox_hedgehog.change_topologyplan',
            'dcim.add_rack', 'dcim.delete_rack',
        ] + self.dcim_base)
        obj_perm = ObjectPermission.objects.create(
            name='has-rack-plan', actions=['view', 'change'])
        obj_perm.object_types.add(ContentType.objects.get_for_model(TopologyPlan))
        obj_perm.users.add(user)
        self.client.login(username='has-rack', password='pw')

        resp = self.client.post(self._url(), follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(_plan_racks(self.plan).count(), 1)


# ---------------------------------------------------------------------------
# PlanLocalityRange read-only view RBAC
# ---------------------------------------------------------------------------
class LocalityRangeViewRBACTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.plan, *_ = _make_same_switch_plan(
            'lr-rbac', quantity=8, num_switches=1,
            place_in_racks=True, servers_per_rack=8,
        )

    def test_list_view_without_permission_forbidden(self):
        user = User.objects.create_user(
            username='lr-none', password='pw', is_staff=True)
        self.client.login(username='lr-none', password='pw')
        resp = self.client.get(
            reverse('plugins:netbox_hedgehog:planlocalityrange_list'))
        self.assertEqual(resp.status_code, 403)

    def test_list_view_with_permission_succeeds(self):
        user = User.objects.create_user(
            username='lr-view', password='pw', is_staff=True)
        perm = Permission.objects.get(
            content_type__app_label='netbox_hedgehog',
            codename='view_planlocalityrange')
        user.user_permissions.add(perm)
        obj_perm = ObjectPermission.objects.create(
            name='lr-view-op', actions=['view'])
        obj_perm.object_types.add(
            ContentType.objects.get_for_model(_locality_range_model()))
        obj_perm.users.add(user)
        self.client.login(username='lr-view', password='pw')
        resp = self.client.get(
            reverse('plugins:netbox_hedgehog:planlocalityrange_list'))
        self.assertEqual(resp.status_code, 200)
