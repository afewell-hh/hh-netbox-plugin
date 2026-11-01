"""
Plan-scoped Switch Port Zones list, filters and contextual add (#729).

Two plans, several switch classes and distinct zones prove isolation, explicit
All plans, search, empty/invalid contexts, retention, RBAC and safe return URLs.
"""

from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import DeviceType, Manufacturer
from users.models import ObjectPermission

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    FabricClassChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)

User = get_user_model()

LIST = 'plugins:netbox_hedgehog:switchportzone_list'
ADD = 'plugins:netbox_hedgehog:switchportzone_add'
EDIT = 'plugins:netbox_hedgehog:switchportzone_edit'
DELETE = 'plugins:netbox_hedgehog:switchportzone_delete'
DETAIL = 'plugins:netbox_hedgehog:switchportzone'


def _grant(user, model, actions, constraints=None):
    perm = ObjectPermission.objects.create(
        name=f'pz-{user.username}-{model.__name__}-{"-".join(actions)}',
        actions=list(actions),
        constraints=constraints,
    )
    perm.object_types.add(ContentType.objects.get_for_model(model))
    perm.users.add(user)
    return perm


class PortZoneContextBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='pz-admin', password='pass', is_staff=True, is_superuser=True)
        mfg, _ = Manufacturer.objects.get_or_create(name='PZ-Mfg', defaults={'slug': 'pz-mfg'})
        dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfg, model='PZ-SW', defaults={'slug': 'pz-sw'})
        cls.ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=dt,
            defaults={'native_speed': 200, 'uplink_ports': 4,
                      'supported_breakouts': ['1x200g'], 'mclag_capable': False,
                      'hedgehog_roles': ['server-leaf']},
        )
        cls.breakout, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x200g-pz',
            defaults={'from_speed': 200, 'logical_ports': 1, 'logical_speed': 200},
        )
        cls.plan_a = TopologyPlan.objects.create(name='PZ-Plan-A', status=TopologyPlanStatusChoices.DRAFT)
        cls.plan_b = TopologyPlan.objects.create(name='PZ-Plan-B', status=TopologyPlanStatusChoices.DRAFT)
        cls.plan_empty = TopologyPlan.objects.create(name='PZ-Plan-Empty', status=TopologyPlanStatusChoices.DRAFT)
        cls.sw_a1 = cls._switch(cls.plan_a, 'a-leaf-1')
        cls.sw_a2 = cls._switch(cls.plan_a, 'a-leaf-2')
        cls.sw_b1 = cls._switch(cls.plan_b, 'b-leaf-1')
        cls.sw_empty = cls._switch(cls.plan_empty, 'e-leaf-1')
        cls.z_a1 = cls._zone(cls.sw_a1, 'alpha-server')
        cls.z_a2 = cls._zone(cls.sw_a2, 'alpha-uplink')
        cls.z_b1 = cls._zone(cls.sw_b1, 'bravo-server')

    @classmethod
    def _switch(cls, plan, sc_id):
        return PlanSwitchClass.objects.create(
            plan=plan, switch_class_id=sc_id, fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED, hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ext, uplink_ports_per_switch=0, mclag_pair=False,
            override_quantity=2, redundancy_type='eslag',
        )

    @classmethod
    def _zone(cls, sw, name):
        return SwitchPortZone.objects.create(
            switch_class=sw, zone_name=name, zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-8', breakout_option=cls.breakout,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)

    def names(self, response):
        return {z.zone_name for z in response.context['table'].data}

    def get(self, **params):
        return self.client.get(reverse(LIST), params)


class ListContextTests(PortZoneContextBase):
    def test_initial_list_prompts_and_shows_no_rows(self):
        r = self.client.get(reverse(LIST))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Select a topology plan')
        self.assertNotContains(r, 'alpha-server')
        self.assertNotContains(r, 'bravo-server')
        self.assertEqual(len(r.context['table'].data), 0)

    def test_filter_form_labelled_and_offers_plans_and_all(self):
        r = self.client.get(reverse(LIST))
        self.assertContains(r, 'Topology Plan')
        self.assertContains(r, 'All plans')
        self.assertContains(r, 'PZ-Plan-A')
        self.assertContains(r, 'PZ-Plan-B')

    def test_plan_filter_isolates_plans(self):
        r = self.get(plan=self.plan_a.pk)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.names(r), {'alpha-server', 'alpha-uplink'})
        self.assertContains(r, 'PZ-Plan-A')
        self.assertContains(r, self.plan_a.get_absolute_url())
        r = self.get(plan=self.plan_b.pk)
        self.assertEqual(self.names(r), {'bravo-server'})

    def test_switch_class_filter(self):
        r = self.get(plan=self.plan_a.pk, switch_class=self.sw_a2.pk)
        self.assertEqual(self.names(r), {'alpha-uplink'})
        self.assertContains(r, self.sw_a2.get_absolute_url())

    def test_explicit_all_plans_with_plan_and_switch_columns(self):
        r = self.get(plan='all')
        self.assertEqual(self.names(r), {'alpha-server', 'alpha-uplink', 'bravo-server'})
        self.assertContains(r, 'PZ-Plan-A')
        self.assertContains(r, 'PZ-Plan-B')
        self.assertContains(r, 'a-leaf-1')
        self.assertContains(r, 'b-leaf-1')

    def test_search_and_zero_match(self):
        r = self.get(plan='all', q='server')
        self.assertEqual(self.names(r), {'alpha-server', 'bravo-server'})
        r = self.get(plan=self.plan_a.pk, q='zzz-none')
        self.assertEqual(self.names(r), set())
        self.assertContains(r, 'No port zones match')
        self.assertNotContains(r, 'has no port zones yet')

    def test_empty_plan_message_and_scoped_add(self):
        r = self.get(plan=self.plan_empty.pk)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'This plan has no port zones yet')
        self.assertContains(r, f'plan={self.plan_empty.pk}')

    def test_invalid_contexts_fail_clearly_without_rows(self):
        cases = [
            {'plan': '999999'},
            {'plan': 'abc'},
            {'plan': self.plan_a.pk, 'switch_class': self.sw_b1.pk},   # mismatched
            {'plan': self.plan_a.pk, 'switch_class': '999999'},
            {'switch_class': self.sw_a1.pk},                            # no plan
        ]
        for params in cases:
            with self.subTest(params=params):
                r = self.get(**params)
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, 'not valid')
                self.assertEqual(self.names(r), set())
                self.assertNotContains(r, 'bravo-server')
                self.assertNotContains(r, 'alpha-server')

    def test_pagination_sort_links_retain_filters(self):
        for i in range(3):
            self._zone(self.sw_a1, f'extra-{i}')
        r = self.client.get(reverse(LIST), {'plan': self.plan_a.pk, 'per_page': 2})
        html = r.content.decode()
        import re
        hrefs = re.findall(r'href="([^"]*)"', html)
        page_links = [h for h in hrefs if 'page=2' in h]
        sort_links = [h for h in hrefs if 'sort=' in h]
        self.assertTrue(page_links, 'pagination link expected')
        self.assertTrue(sort_links, 'sort link expected')
        for h in page_links + sort_links:
            self.assertIn(f'plan={self.plan_a.pk}', h)

    def test_selection_retained_in_form(self):
        r = self.get(plan=self.plan_a.pk, switch_class=self.sw_a1.pk, q='alpha')
        form = r.context['zone_filter_form']
        self.assertEqual(form.cleaned_data['plan'], str(self.plan_a.pk))
        self.assertEqual(form.cleaned_data['switch_class'], self.sw_a1)
        self.assertEqual(form.cleaned_data['q'], 'alpha')


class LinkTests(PortZoneContextBase):
    def test_plan_detail_links_to_plan_zones(self):
        r = self.client.get(self.plan_a.get_absolute_url())
        self.assertContains(r, f'{reverse(LIST)}?plan={self.plan_a.pk}')

    def test_switch_detail_links_to_switch_zones_and_add_returns(self):
        r = self.client.get(self.sw_a1.get_absolute_url())
        self.assertContains(r, f'plan={self.plan_a.pk}&amp;switch_class={self.sw_a1.pk}')
        self.assertContains(r, 'return_url=')

    def test_zone_detail_shows_plan_and_links(self):
        r = self.client.get(reverse(DETAIL, args=[self.z_a1.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'PZ-Plan-A')
        self.assertContains(r, self.plan_a.get_absolute_url())


class RbacTests(PortZoneContextBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_user(username='pz-limited', password='pass')
        _grant(cls.user, TopologyPlan, ['view'], {'pk': cls.plan_a.pk})
        _grant(cls.user, PlanSwitchClass, ['view'], {'plan_id': cls.plan_a.pk})
        _grant(cls.user, SwitchPortZone, ['view'], {'switch_class__plan_id': cls.plan_a.pk})

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_no_permission_denied(self):
        nobody = User.objects.create_user(username='pz-nobody', password='pass')
        c = Client()
        c.force_login(nobody)
        self.assertEqual(c.get(reverse(LIST), {'plan': 'all'}).status_code, 403)

    def test_choices_do_not_leak_hidden_plans(self):
        r = self.client.get(reverse(LIST))
        self.assertContains(r, 'PZ-Plan-A')
        self.assertNotContains(r, 'PZ-Plan-B')
        self.assertNotContains(r, 'PZ-Plan-Empty')

    def test_all_plans_is_still_restricted(self):
        r = self.get(plan='all')
        self.assertEqual(self.names(r), {'alpha-server', 'alpha-uplink'})
        self.assertNotContains(r, 'bravo-server')
        self.assertNotContains(r, 'PZ-Plan-B')

    def test_inaccessible_plan_is_invalid_not_all(self):
        r = self.get(plan=self.plan_b.pk)
        self.assertContains(r, 'not valid')
        self.assertEqual(self.names(r), set())
        self.assertNotContains(r, 'PZ-Plan-B')
        self.assertNotContains(r, 'bravo-server')

    def test_add_link_hidden_without_add_permission(self):
        r = self.get(plan=self.plan_a.pk)
        self.assertNotContains(r, 'Add Port Zone')
        _grant(self.user, SwitchPortZone, ['add'])
        r = self.get(plan=self.plan_a.pk)
        self.assertContains(r, 'Add Port Zone')

    def test_add_form_choices_restricted(self):
        _grant(self.user, SwitchPortZone, ['add'])
        r = self.client.get(reverse(ADD))
        self.assertEqual(r.status_code, 200)
        qs = r.context['form'].fields['switch_class'].queryset
        self.assertEqual(set(qs), {self.sw_a1, self.sw_a2})


class ContextualAddTests(PortZoneContextBase):
    def _payload(self, sw, name='new-zone'):
        return {
            'switch_class': sw.pk, 'zone_name': name,
            'zone_type': PortZoneTypeChoices.SERVER, 'port_spec': '20-24',
            'breakout_option': self.breakout.pk,
            'allocation_strategy': AllocationStrategyChoices.SEQUENTIAL, 'priority': 100,
        }

    def test_add_preselects_switch_class_and_cancel_returns(self):
        back = f'{reverse(LIST)}?plan={self.plan_a.pk}'
        url = f'{reverse(ADD)}?switch_class={self.sw_a2.pk}&return_url={quote(back, safe="")}'
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['form'].initial.get('switch_class'), str(self.sw_a2.pk))
        self.assertContains(r, back.replace('&', '&amp;'))

    def test_add_with_plan_limits_choices(self):
        r = self.client.get(reverse(ADD), {'plan': self.plan_a.pk})
        self.assertEqual(set(r.context['form'].fields['switch_class'].queryset), {self.sw_a1, self.sw_a2})
        r = self.client.get(reverse(ADD), {'plan': 'bogus'})
        self.assertEqual(list(r.context['form'].fields['switch_class'].queryset), [])

    def test_add_with_plan_rejects_other_plan_switch_class(self):
        url = f'{reverse(ADD)}?plan={self.plan_a.pk}'
        r = self.client.post(url, self._payload(self.sw_b1, 'cross'))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(SwitchPortZone.objects.filter(zone_name='cross').exists())

    def test_valid_save_redirects_to_safe_return_url(self):
        back = f'{reverse(LIST)}?plan={self.plan_a.pk}&switch_class={self.sw_a2.pk}'
        url = f'{reverse(ADD)}?switch_class={self.sw_a2.pk}&return_url={quote(back, safe="")}'
        r = self.client.post(url, self._payload(self.sw_a2))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], back)
        self.assertTrue(SwitchPortZone.objects.filter(zone_name='new-zone', switch_class=self.sw_a2).exists())

    def test_external_return_url_is_ignored(self):
        for bad in ('https://evil.example/x', '//evil.example/x', 'javascript:alert(1)', '/\\evil.example'):
            with self.subTest(bad=bad):
                url = f'{reverse(ADD)}?return_url={quote(bad, safe="")}'
                r = self.client.post(url, self._payload(self.sw_a1, f'z-{abs(hash(bad))}'))
                self.assertEqual(r.status_code, 302)
                self.assertNotIn('evil', r['Location'])
                self.assertTrue(r['Location'].startswith('/'))

    def test_invalid_post_shows_error(self):
        data = self._payload(self.sw_a1)
        data['port_spec'] = ''
        r = self.client.post(reverse(ADD), data)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['form'].errors)


class LegacyCrudTests(PortZoneContextBase):
    def test_direct_routes_still_work(self):
        self.assertEqual(self.client.get(reverse(ADD)).status_code, 200)
        self.assertEqual(self.client.get(reverse(DETAIL, args=[self.z_a1.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse(EDIT, args=[self.z_a1.pk])).status_code, 200)

    def test_add_without_return_url_goes_to_detail_or_list(self):
        r = self.client.post(reverse(ADD), {
            'switch_class': self.sw_a1.pk, 'zone_name': 'legacy-add',
            'zone_type': PortZoneTypeChoices.SERVER, 'port_spec': '30-32',
            'breakout_option': self.breakout.pk,
            'allocation_strategy': AllocationStrategyChoices.SEQUENTIAL, 'priority': 100,
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(SwitchPortZone.objects.filter(zone_name='legacy-add').exists())

    def test_edit_updates_and_keeps_parent(self):
        r = self.client.post(reverse(EDIT, args=[self.z_a1.pk]), {
            'switch_class': self.sw_a1.pk, 'zone_name': 'alpha-renamed',
            'zone_type': PortZoneTypeChoices.SERVER, 'port_spec': '1-8',
            'breakout_option': self.breakout.pk,
            'allocation_strategy': AllocationStrategyChoices.SEQUENTIAL, 'priority': 100,
        })
        self.assertEqual(r.status_code, 302)
        self.z_a1.refresh_from_db()
        self.assertEqual(self.z_a1.zone_name, 'alpha-renamed')
        self.assertEqual(self.z_a1.switch_class_id, self.sw_a1.pk)

    def test_delete_removes_zone(self):
        r = self.client.post(reverse(DELETE, args=[self.z_b1.pk]), {'confirm': True})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(SwitchPortZone.objects.filter(pk=self.z_b1.pk).exists())
