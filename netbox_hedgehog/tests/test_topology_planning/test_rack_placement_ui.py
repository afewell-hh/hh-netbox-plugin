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

from dcim.models import Device, DeviceType, Manufacturer

from users.models import ObjectPermission

from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic
from netbox_hedgehog.tests.test_topology_planning.test_rack_placement import (
    _make_same_switch_plan,
    _make_server_type,
    _plan_racks,
    _locality_range_model,
)
from netbox_hedgehog.models.topology_planning import (
    GenerationState,
    PlanServerClass,
    TopologyPlan,
)
from netbox_hedgehog.choices import GenerationStatusChoices
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
    """Rack authorization at the HTTP gate of the unified generate/update view.

    `TopologyPlanGenerateUpdateView.post()` is ASYNCHRONOUS: on an allowed
    request it enqueues a DeviceGenerationJob, sets GenerationState=QUEUED, and
    redirects (302) to the job page — it does NOT create devices/racks
    synchronously. So these HTTP tests assert the permission outcome + enqueue
    only; actual rack / no-rack object creation is covered separately by the
    unmocked generator-integration tests (RackConstructionTestCase,
    LegacyNoRackTestCase, ByteIdenticalCompatTestCase).

    A rack-enabled plan must require dcim.add_rack/delete_rack (strict 403 at
    the gate, raised before enqueue); a non-rack plan must not.
    """

    DCIM_BASE = [
        'dcim.add_device', 'dcim.delete_device',
        'dcim.add_interface', 'dcim.add_cable', 'dcim.delete_cable',
    ]

    def _grant(self, user, codenames):
        for codename in codenames:
            app_label, code = codename.split('.')
            perm = Permission.objects.get(
                content_type__app_label=app_label, codename=code)
            user.user_permissions.add(perm)

    def _obj_perm(self, user, name):
        obj_perm = ObjectPermission.objects.create(
            name=name, actions=['view', 'change'])
        obj_perm.object_types.add(ContentType.objects.get_for_model(TopologyPlan))
        obj_perm.users.add(user)

    def _url(self, plan):
        return reverse('plugins:netbox_hedgehog:topologyplan_generate_update',
                       args=[plan.pk])

    def setUp(self):
        self.client = Client()

    def test_missing_rack_permission_strictly_forbidden(self):
        plan, *_ = _make_same_switch_plan(
            'auth-rack', quantity=8, num_switches=1,
            place_in_racks=True, servers_per_rack=8,
        )
        user = User.objects.create_user(
            username='no-rack', password='pw', is_staff=True)
        # change_topologyplan + base DCIM perms, but NOT dcim.add_rack/delete_rack.
        self._grant(user, ['netbox_hedgehog.change_topologyplan'] + self.DCIM_BASE)
        self._obj_perm(user, 'no-rack-op')
        self.client.login(username='no-rack', password='pw')

        resp = self.client.post(self._url(plan), follow=False)
        self.assertEqual(
            resp.status_code, 403,
            'Rack-enabled generation without dcim.add_rack must be a strict 403',
        )
        # Denial is raised before the enqueue step: nothing queued, nothing built.
        self.assertFalse(
            GenerationState.objects.filter(
                plan=plan, status=GenerationStatusChoices.QUEUED).exists(),
            'A 403 denial must not enqueue a generation job',
        )
        self.assertEqual(_plan_racks(plan).count(), 0)
        self.assertEqual(
            Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(plan.pk)).count(), 0,
            'A 403 denial must not have generated anything',
        )

    def _assert_enqueued_no_immediate_objects(self, plan):
        state = GenerationState.objects.filter(plan=plan).first()
        self.assertIsNotNone(state, 'An allowed request must create GenerationState')
        self.assertEqual(state.status, GenerationStatusChoices.QUEUED)
        self.assertIsNotNone(state.job, 'GenerationState must link the enqueued job')
        # Asynchronous: no devices/racks created synchronously by the HTTP call.
        self.assertEqual(_plan_racks(plan).count(), 0)
        self.assertEqual(
            Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(plan.pk)).count(), 0,
            'Generation is async; the POST must not create objects immediately',
        )

    def test_with_rack_permission_enqueues_job(self):
        plan, *_ = _make_same_switch_plan(
            'auth-rack-ok', quantity=8, num_switches=1,
            place_in_racks=True, servers_per_rack=8,
        )
        user = User.objects.create_user(
            username='has-rack', password='pw', is_staff=True)
        self._grant(user, [
            'netbox_hedgehog.change_topologyplan',
            'dcim.add_rack', 'dcim.delete_rack',
        ] + self.DCIM_BASE)
        self._obj_perm(user, 'has-rack-op')
        self.client.login(username='has-rack', password='pw')

        resp = self.client.post(self._url(plan), follow=False)
        self.assertEqual(resp.status_code, 302)
        self._assert_enqueued_no_immediate_objects(plan)

    def test_non_rack_plan_enqueues_without_rack_permission(self):
        """Regression: rack perms are NOT required to enqueue a place_in_racks=False plan."""
        plan, *_ = _make_same_switch_plan(
            'auth-norack', quantity=8, num_switches=1, place_in_racks=False,
        )
        user = User.objects.create_user(
            username='norack-user', password='pw', is_staff=True)
        # Base DCIM perms only, deliberately WITHOUT dcim.add_rack/delete_rack.
        self._grant(user, ['netbox_hedgehog.change_topologyplan'] + self.DCIM_BASE)
        self._obj_perm(user, 'norack-op')
        self.client.login(username='norack-user', password='pw')

        resp = self.client.post(self._url(plan), follow=False)
        self.assertNotEqual(
            resp.status_code, 403,
            'A non-rack plan must not require rack permissions',
        )
        self.assertEqual(resp.status_code, 302)
        self._assert_enqueued_no_immediate_objects(plan)


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
