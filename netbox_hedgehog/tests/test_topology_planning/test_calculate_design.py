"""
Integration tests for the calculation-only "Calculate design" action (#727).

Real requests/rendering against the existing ``topologyplan_recalculate`` route.
The calculator is NOT mocked. Expected quantities are hand-computed: the server
zone is ports 1-48 with a 4x200g breakout on an 800G switch = 192 logical ports
per switch, and each server uses ports_per_connection=2 (same-switch).
  * 2 servers   -> 4 ports   -> 1 switch
  * 100 servers -> 200 ports -> ceil(200/192) = 2 switches
"""

import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Job
from dcim.models import (
    Cable, Device, DeviceRole, DeviceType, Interface, Manufacturer, Module, ModuleBay, Site,
)
from users.models import ObjectPermission

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricTypeChoices,
    GenerationStatusChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    ServerClassCategoryChoices,
    TopologyModeChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    GenerationState,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import (
    get_test_non_transceiver_module_type,
    get_test_server_nic,
    get_test_transceiver_module_type,
)

User = get_user_model()


class CalculateDesignBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica', defaults={'slug': 'celestica'})
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer, model='DS5000', defaults={'slug': 'ds5000'})
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer, model='R760xa', defaults={'slug': 'r760xa'})
        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_type,
            defaults={
                'native_speed': 800,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g', '8x100g'],
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf'],
            })
        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200})
        cls.xcvr = get_test_transceiver_module_type()

        cls.superuser = User.objects.create_user(
            username='cd-admin', password='pw', is_staff=True, is_superuser=True)
        cls.plan = cls.make_plan('Calc Plan A', servers=2)
        cls.other_plan = cls.make_plan('Calc Plan B', servers=2)

    @classmethod
    def make_plan(cls, name, servers, override=None):
        plan = TopologyPlan.objects.create(name=name)
        server_class = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu', category=ServerClassCategoryChoices.GPU,
            quantity=servers, gpus_per_server=8, server_device_type=cls.server_type)
        switch_class = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf', fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext, uplink_ports_per_switch=4,
            mclag_pair=False, calculated_quantity=None, override_quantity=override)
        zone = SwitchPortZone.objects.create(
            switch_class=switch_class, zone_name='server-ports',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-48',
            breakout_option=cls.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100, transceiver_module_type=cls.xcvr)
        PlanServerConnection.objects.create(
            server_class=server_class, connection_id='FE-001',
            nic=get_test_server_nic(server_class), port_index=0, target_zone=zone,
            ports_per_connection=2, hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH, speed=200,
            port_type='data', transceiver_module_type=cls.xcvr)
        return plan

    # helpers -----------------------------------------------------------
    def url(self, plan=None):
        return reverse('plugins:netbox_hedgehog:topologyplan_recalculate',
                       args=[(plan or self.plan).pk])

    def detail_url(self, plan=None):
        return reverse('plugins:netbox_hedgehog:topologyplan_detail',
                       args=[(plan or self.plan).pk])

    def user_with_perm(self, username, actions=('view', 'change'), constraints=None,
                       extra_models=()):
        user = User.objects.create_user(username=username, password='pw', is_staff=True)
        perm = ObjectPermission.objects.create(
            name=f'{username}-perm', actions=list(actions), constraints=constraints)
        perm.object_types.add(ContentType.objects.get_for_model(TopologyPlan))
        for model in extra_models:
            perm.object_types.add(ContentType.objects.get_for_model(model))
        perm.users.add(user)
        return user

    def login(self, user, **client_kwargs):
        client = Client(**client_kwargs)
        client.force_login(user)
        return client

    def msgs(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def inventory_counts(self):
        return {
            'devices': Device.objects.count(),
            'interfaces': Interface.objects.count(),
            'cables': Cable.objects.count(),
            'modules': Module.objects.count(),
            'jobs': Job.objects.count(),
            'states': GenerationState.objects.count(),
        }

    def _make_busy(self, plan, status=GenerationStatusChoices.IN_PROGRESS, with_job=True):
        """Create a busy GenerationState, with a Job or with job=None (deleted/missing)."""
        job = None
        if with_job:
            job = Job.objects.create(
                object_type=ContentType.objects.get_for_model(plan), object_id=plan.pk,
                name='busy', user=self.superuser, job_id=uuid.uuid4())
        return GenerationState.objects.update_or_create(
            plan=plan, defaults={'status': status, 'job': job, 'snapshot': {},
                                 'device_count': 0, 'interface_count': 0,
                                 'cable_count': 0})[0]

    def make_sentinel_inventory(self):
        """Small valid synthetic inventory (Device/Interface/Cable/Module/Job)."""
        role, _ = DeviceRole.objects.get_or_create(
            slug='cd-sentinel-role', defaults={'name': 'CD Sentinel', 'color': 'aa1409'})
        site, _ = Site.objects.get_or_create(
            name='CD-Sentinel-Site', defaults={'slug': 'cd-sentinel-site'})
        plan_id = str(self.plan.pk)
        devs = [
            Device.objects.create(
                name=f'cd-sentinel-{suffix}', device_type=self.server_type, role=role,
                site=site, status='planned',
                custom_field_data={'hedgehog_plan_id': plan_id})
            for suffix in ('a', 'b')
        ]
        iface_a = Interface.objects.create(device=devs[0], name='eth0', type='1000base-t')
        iface_b = Interface.objects.create(device=devs[1], name='eth0', type='1000base-t')
        cable = Cable(a_terminations=[iface_a], b_terminations=[iface_b])
        cable.custom_field_data = {'hedgehog_plan_id': plan_id}
        cable.save()
        bay = ModuleBay.objects.create(device=devs[0], name='cd-bay')
        Module.objects.create(
            device=devs[0], module_bay=bay,
            module_type=get_test_non_transceiver_module_type())
        Job.objects.create(
            object_type=ContentType.objects.get_for_model(self.plan),
            object_id=self.plan.pk, name='sentinel-job', user=self.superuser,
            job_id=uuid.uuid4())

    def inventory_snapshot(self):
        """Identities plus relevant field values, so updates and count-neutral
        replacements (new pk, same count) are detected."""
        return {
            'devices': sorted(
                (d.pk, d.name, d.status, d.device_type_id, d.role_id, d.site_id,
                 str(d.custom_field_data), str(d.last_updated))
                for d in Device.objects.all()),
            'interfaces': sorted(
                (i.pk, i.device_id, i.name, i.type, i.cable_id, str(i.last_updated))
                for i in Interface.objects.all()),
            'cables': sorted(
                (c.pk, str(c.custom_field_data), c.status, str(c.last_updated))
                for c in Cable.objects.all()),
            'modules': sorted(
                (m.pk, m.device_id, m.module_bay_id, m.module_type_id, m.status,
                 str(m.last_updated))
                for m in Module.objects.all()),
            'jobs': sorted(
                (j.pk, str(j.job_id), j.name, j.status, j.object_id, j.user_id)
                for j in Job.objects.all()),
            'states': sorted(
                (g.pk, g.plan_id, g.status, g.job_id, g.device_count, g.interface_count,
                 g.cable_count, str(g.snapshot), str(g.generated_at))
                for g in GenerationState.objects.all()),
        }

    def qty(self, plan=None):
        sc = (plan or self.plan).switch_classes.get(switch_class_id='fe-leaf')
        return sc.calculated_quantity, sc.override_quantity


class CalculateDesignRenderTests(CalculateDesignBase):
    def test_button_rendered_with_text_for_change_permission_without_dcim_perms(self):
        user = self.user_with_perm('cd-nodcim')
        self.assertFalse(user.has_perm('dcim.add_device'))
        resp = self.login(user).get(self.detail_url())
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="calculate-design-btn"', html)
        self.assertIn('Calculate design', html)
        self.assertIn('Updates saved switch quantities only; does not create/update NetBox inventory.', html)
        self.assertIn(f'action="{self.url()}"', html)
        self.assertIn('csrfmiddlewaretoken', html)
        # DCIM-less user: Generate remains disabled, Calculate is enabled.
        btn = html.split('id="calculate-design-btn"')[1].split('>')[0]
        self.assertNotIn('disabled', btn)

    def test_button_hidden_for_view_only_user(self):
        user = self.user_with_perm('cd-viewonly', actions=('view',))
        resp = self.login(user).get(self.detail_url())
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('calculate-design-btn', resp.content.decode())

    def test_button_hidden_for_plan_outside_constraint(self):
        user = self.user_with_perm(
            'cd-constrained', constraints={'pk': self.plan.pk})
        client = self.login(user)
        self.assertIn('calculate-design-btn', client.get(self.detail_url()).content.decode())
        # Other plan is not even viewable under the constraint.
        self.assertEqual(client.get(self.detail_url(self.other_plan)).status_code, 404)

    def test_button_disabled_with_explanation_for_every_busy_status_with_or_without_job(self):
        for status in (GenerationStatusChoices.QUEUED, GenerationStatusChoices.IN_PROGRESS):
            for with_job in (True, False):
                with self.subTest(status=status, with_job=with_job):
                    self._make_busy(self.plan, status, with_job=with_job)
                    resp = self.login(self.superuser).get(self.detail_url())
                    html = resp.content.decode()
                    btn = html.split('id="calculate-design-btn"')[1].split('>')[0]
                    self.assertIn('disabled', btn)
                    self.assertIn(
                        'Unavailable while a generation job is queued or in progress.', html)

    def test_existing_generate_controls_still_render(self):
        html = self.login(self.superuser).get(self.detail_url()).content.decode()
        self.assertIn('id="generate-btn"', html)
        gen_url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update',
                          args=[self.plan.pk])
        self.assertIn(f'action="{gen_url}"', html)


class CalculateDesignPermissionTests(CalculateDesignBase):
    def test_plan_scoped_change_permission_without_dcim_perms_can_calculate(self):
        user = self.user_with_perm('cd-scoped', constraints={'pk': self.plan.pk})
        self.assertFalse(user.has_perm('dcim.add_device'))
        before = self.inventory_counts()
        resp = self.login(user).post(self.url())
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, self.detail_url())
        self.assertEqual(self.qty(), (1, None))
        self.assertEqual(self.inventory_counts(), before)

    def test_constrained_permission_cannot_calculate_other_plan(self):
        user = self.user_with_perm('cd-other', constraints={'pk': self.plan.pk})
        resp = self.login(user).post(self.url(self.other_plan))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.qty(self.other_plan), (None, None))

    def test_view_only_user_denied(self):
        user = self.user_with_perm('cd-view', actions=('view',))
        resp = self.login(user).post(self.url())
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.qty(), (None, None))

    def test_user_without_any_permission_denied(self):
        user = User.objects.create_user(username='cd-none', password='pw')
        resp = self.login(user).post(self.url())
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.qty(), (None, None))

    def test_anonymous_denied(self):
        resp = Client().post(self.url())
        self.assertIn(resp.status_code, (302, 403))
        if resp.status_code == 302:
            self.assertIn('login', resp.url)
        self.assertEqual(self.qty(), (None, None))

    def test_get_not_allowed_and_does_not_calculate(self):
        resp = self.login(self.superuser).get(self.url())
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(self.qty(), (None, None))

    def test_post_without_csrf_token_rejected(self):
        client = self.login(self.superuser, enforce_csrf_checks=True)
        resp = client.post(self.url())
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.qty(), (None, None))


class CalculateDesignBehaviourTests(CalculateDesignBase):
    def post(self, plan=None):
        return self.login(self.superuser).post(self.url(plan))

    def test_calculates_expected_sizing_and_updates_after_edit(self):
        resp = self.post()
        self.assertEqual(self.qty(), (1, None))
        self.assertTrue(any('Recalculated 1 switch classes' in m for m in self.msgs(resp)))
        self.assertTrue(any('NetBox inventory was not changed' in m for m in self.msgs(resp)))
        # 100 servers x 2 ports = 200 > 192 logical ports per switch -> 2 switches
        PlanServerClass.objects.filter(plan=self.plan).update(quantity=100)
        self.post()
        self.assertEqual(self.qty(), (2, None))

    def test_explicit_override_is_preserved(self):
        plan = self.make_plan('Calc Override', servers=2, override=5)
        self.post(plan)
        self.assertEqual(self.qty(plan), (1, 5))

    def test_queued_and_in_progress_rejected_with_or_without_job(self):
        for status in (GenerationStatusChoices.QUEUED, GenerationStatusChoices.IN_PROGRESS):
            for with_job in (True, False):
                with self.subTest(status=status, with_job=with_job):
                    state = self._make_busy(self.plan, status, with_job=with_job)
                    self.assertEqual(state.job_id is not None, with_job)
                    before = self.inventory_snapshot()
                    resp = self.post()
                    self.assertEqual(resp.status_code, 302)
                    self.assertEqual(resp.url, self.detail_url())
                    self.assertTrue(
                        any('Cannot calculate design' in m for m in self.msgs(resp)))
                    self.assertEqual(self.qty(), (None, None))
                    self.assertEqual(self.inventory_snapshot(), before)
                    state.refresh_from_db()
                    self.assertEqual(state.status, status)
                    self.assertEqual(state.job_id is not None, with_job)

    def test_orphaned_busy_state_without_job_is_refused_and_left_untouched(self):
        GenerationState.objects.create(
            plan=self.plan, status=GenerationStatusChoices.QUEUED, snapshot={},
            device_count=0, interface_count=0, cable_count=0)
        before = self.inventory_snapshot()
        resp = self.post()
        self.assertTrue(any('Cannot calculate design' in m for m in self.msgs(resp)))
        self.assertEqual(self.qty(), (None, None))
        self.assertEqual(self.inventory_snapshot(), before)
        state = GenerationState.objects.get(plan=self.plan)
        self.assertEqual(state.status, GenerationStatusChoices.QUEUED)
        self.assertIsNone(state.job_id)

    def test_populated_inventory_and_jobs_unchanged_by_real_calculation(self):
        self.make_sentinel_inventory()
        before = self.inventory_snapshot()
        for key in ('devices', 'interfaces', 'cables', 'modules', 'jobs'):
            self.assertTrue(before[key], key)
        self.post()
        self.assertEqual(self.qty(), (1, None))  # the real calculation ran
        self.assertEqual(self.inventory_snapshot(), before)
        self.assertFalse(GenerationState.objects.filter(plan=self.plan).exists())

    def test_existing_generation_state_and_snapshot_unchanged(self):
        self.make_sentinel_inventory()
        snapshot = {'marker': {'servers': 8}}
        state = GenerationState.objects.create(
            plan=self.plan, status=GenerationStatusChoices.GENERATED, snapshot=snapshot,
            device_count=7, interface_count=11, cable_count=5)
        generated_at = state.generated_at
        before = self.inventory_snapshot()
        self.post()
        self.assertEqual(self.qty(), (1, None))
        self.assertEqual(self.inventory_snapshot(), before)
        state.refresh_from_db()
        self.assertEqual(state.status, GenerationStatusChoices.GENERATED)
        self.assertEqual(state.snapshot, snapshot)
        self.assertEqual((state.device_count, state.interface_count, state.cable_count),
                         (7, 11, 5))
        self.assertEqual(state.generated_at, generated_at)

    def test_calculation_failure_is_visible_and_not_reported_as_success(self):
        SwitchPortZone.objects.filter(
            switch_class__plan=self.plan).update(breakout_option=None)
        resp = self.post()
        messages = self.msgs(resp)
        self.assertTrue(any("Error calculating 'fe-leaf'" in m for m in messages), messages)
        self.assertFalse(any(m.startswith('Recalculated') for m in messages), messages)
        self.assertEqual(self.qty(), (None, None))

    def test_partial_failure_reports_partial_not_blanket_success(self):
        bad = PlanSwitchClass.objects.create(
            plan=self.plan, switch_class_id='fe-leaf-bad', fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext, uplink_ports_per_switch=4)
        bad_zone = SwitchPortZone.objects.create(
            switch_class=bad, zone_name='bad', zone_type=PortZoneTypeChoices.SERVER,
            transceiver_module_type=self.xcvr)
        server_class = self.plan.server_classes.get()
        PlanServerConnection.objects.create(
            server_class=server_class, connection_id='FE-002',
            nic=get_test_server_nic(server_class, nic_id='nic-bad'), port_index=0,
            target_zone=bad_zone, ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH, speed=200,
            port_type='data', transceiver_module_type=self.xcvr)
        messages = self.msgs(self.post())
        self.assertTrue(any('Partially calculated' in m for m in messages), messages)
        self.assertTrue(any("Error calculating 'fe-leaf-bad'" in m for m in messages), messages)
        self.assertFalse(any(m.startswith('Recalculated') for m in messages), messages)
        self.assertEqual(self.qty(), (1, None))

    def test_all_mesh_plan_reports_nothing_to_calculate(self):
        plan = TopologyPlan.objects.create(name='Calc Mesh')
        PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='mesh-leaf', fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            topology_mode=TopologyModeChoices.MESH,
            device_type_extension=self.device_ext, override_quantity=2)
        messages = self.msgs(self.post(plan))
        self.assertTrue(any('Nothing to calculate' in m for m in messages), messages)
        self.assertFalse(any(m.startswith('Recalculated') for m in messages), messages)
        sc = plan.switch_classes.get()
        self.assertEqual((sc.calculated_quantity, sc.override_quantity), (None, 2))

    def test_calculation_is_plan_scoped(self):
        self.post()
        self.assertEqual(self.qty(self.other_plan), (None, None))

    def test_existing_generate_update_still_rejects_busy_plan(self):
        self._make_busy(self.plan)
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate_update',
                      args=[self.plan.pk])
        resp = self.login(self.superuser).post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(any('Cannot start generation' in m for m in self.msgs(resp)))
