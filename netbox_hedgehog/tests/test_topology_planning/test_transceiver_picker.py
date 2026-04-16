"""
RED tests for DIET-460: transceiver picker label function and form rendering.

Tests reference _make_xcvr_label_fn() from forms/topology_planning.py
which does not exist yet. PKR-1 through PKR-5 from #461 spec.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from dcim.models import DeviceType as DcimDeviceType, Manufacturer, ModuleType, ModuleTypeProfile

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    ServerClassCategoryChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanServerClass,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import (
    get_test_server_nic,
    get_test_transceiver_module_type,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _xcvr_profile():
    return ModuleTypeProfile.objects.filter(name='Network Transceiver').first()


def _make_xcvr(model, description='', medium='MMF', cage='QSFP112',
               mfr_name='PKR-Vendor', mfr_slug='pkr-vendor'):
    mfr, _ = Manufacturer.objects.get_or_create(
        name=mfr_name, defaults={'slug': mfr_slug}
    )
    profile = _xcvr_profile()
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr, model=model,
        defaults={
            'profile': profile,
            'description': description,
            'attribute_data': {'cage_type': cage, 'medium': medium},
        },
    )
    return mt


def _filtered_qs():
    """Return the same filtered queryset that both forms use."""
    profile = _xcvr_profile()
    if profile is None:
        return ModuleType.objects.none()
    return (
        ModuleType.objects
        .filter(profile=profile)
        .select_related('manufacturer')
        .order_by('manufacturer__name', 'model')
    )


# ---------------------------------------------------------------------------
# PKR-1 through PKR-3: unit tests for _make_xcvr_label_fn
# ---------------------------------------------------------------------------

class TestXcvrLabelFn(TestCase):
    """Unit tests for the _make_xcvr_label_fn helper (forms/topology_planning.py)."""

    @classmethod
    def setUpTestData(cls):
        # Ensure the Network Transceiver profile exists
        ModuleTypeProfile.objects.get_or_create(
            name='Network Transceiver',
            defaults={'schema': {}},
        )

    def _fn(self):
        # RED: _make_xcvr_label_fn does not exist yet
        from netbox_hedgehog.forms.topology_planning import _make_xcvr_label_fn
        return _make_xcvr_label_fn

    # PKR-1: description set and unique → "{description} ({model})"
    def test_pkr1_unique_description_gives_desc_model_label(self):
        make_fn = self._fn()
        xcvr = _make_xcvr('PKR-UNIQUE', description='PKR 400G Unique Optic')
        qs = ModuleType.objects.filter(pk=xcvr.pk).select_related('manufacturer')
        label_fn = make_fn(qs)
        label = label_fn(xcvr)
        self.assertEqual(label, 'PKR 400G Unique Optic (PKR-UNIQUE)')

    # PKR-2: two ModuleTypes share same description → both get "[manufacturer]" appended
    def test_pkr2_collision_appends_manufacturer(self):
        make_fn = self._fn()
        mfr_a, _ = Manufacturer.objects.get_or_create(
            name='PKR-CollA', defaults={'slug': 'pkr-colla'}
        )
        mfr_b, _ = Manufacturer.objects.get_or_create(
            name='PKR-CollB', defaults={'slug': 'pkr-collb'}
        )
        profile = _xcvr_profile()
        xcvr_a, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr_a, model='PKR-COLL-A',
            defaults={
                'profile': profile,
                'description': 'Shared Description 200G',
                'attribute_data': {'cage_type': 'QSFP112', 'medium': 'MMF'},
            },
        )
        xcvr_b, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr_b, model='PKR-COLL-B',
            defaults={
                'profile': profile,
                'description': 'Shared Description 200G',
                'attribute_data': {'cage_type': 'QSFP112', 'medium': 'MMF'},
            },
        )
        qs = ModuleType.objects.filter(
            pk__in=[xcvr_a.pk, xcvr_b.pk]
        ).select_related('manufacturer')
        label_fn = make_fn(qs)

        label_a = label_fn(xcvr_a)
        label_b = label_fn(xcvr_b)

        # Both must include description
        self.assertIn('Shared Description 200G', label_a)
        self.assertIn('Shared Description 200G', label_b)
        # Both must include manufacturer to disambiguate
        self.assertIn('PKR-CollA', label_a)
        self.assertIn('PKR-CollB', label_b)
        # Labels must be distinct
        self.assertNotEqual(label_a, label_b)

    # PKR-3: description blank → "{manufacturer} {model}"
    def test_pkr3_blank_description_falls_back_to_mfr_model(self):
        make_fn = self._fn()
        xcvr = _make_xcvr('PKR-NODESC', description='')
        qs = ModuleType.objects.filter(pk=xcvr.pk).select_related('manufacturer')
        label_fn = make_fn(qs)
        label = label_fn(xcvr)
        self.assertIn('PKR-Vendor', label)
        self.assertIn('PKR-NODESC', label)
        # Must NOT contain parenthesised empty string
        self.assertNotIn('()', label)

    # Collision detection is per-queryset (a description unique in a smaller
    # filtered set is not marked as collision even if globally duplicated)
    def test_collision_is_scoped_to_provided_queryset(self):
        make_fn = self._fn()
        # Only xcvr_a in the queryset — its description is unique in that scope
        mfr_a, _ = Manufacturer.objects.get_or_create(
            name='PKR-ScopeA', defaults={'slug': 'pkr-scopea'}
        )
        mfr_b, _ = Manufacturer.objects.get_or_create(
            name='PKR-ScopeB', defaults={'slug': 'pkr-scopeb'}
        )
        profile = _xcvr_profile()
        xcvr_a, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr_a, model='PKR-SCOPE-A',
            defaults={
                'profile': profile,
                'description': 'Scoped Unique Desc',
                'attribute_data': {'cage_type': 'QSFP112', 'medium': 'MMF'},
            },
        )
        xcvr_b, _ = ModuleType.objects.get_or_create(
            manufacturer=mfr_b, model='PKR-SCOPE-B',
            defaults={
                'profile': profile,
                'description': 'Scoped Unique Desc',
                'attribute_data': {'cage_type': 'QSFP112', 'medium': 'MMF'},
            },
        )
        # Queryset contains only xcvr_a — description is unique in this scope
        qs = ModuleType.objects.filter(pk=xcvr_a.pk).select_related('manufacturer')
        label_fn = make_fn(qs)
        label = label_fn(xcvr_a)
        # No manufacturer disambiguation expected when description is unique in scope
        self.assertNotIn('[PKR-ScopeA]', label)
        self.assertEqual(label, 'Scoped Unique Desc (PKR-SCOPE-A)')


# ---------------------------------------------------------------------------
# PKR-4 and PKR-5: form render tests — labels appear in rendered HTML
# ---------------------------------------------------------------------------

class TestXcvrPickerFormRender(TestCase):
    """
    Integration tests: the transceiver picker in PlanServerConnectionForm and
    SwitchPortZoneForm must render description-first labels in the HTML.

    These tests load the add/edit form pages and assert that a known transceiver
    description appears in the rendered HTML, confirming label_from_instance is wired.
    """

    @classmethod
    def setUpTestData(cls):
        ModuleTypeProfile.objects.get_or_create(
            name='Network Transceiver',
            defaults={'schema': {}},
        )
        cls.xcvr = _make_xcvr('PKR-FORM-XCVR', description='PKR Form Label Optic 200G')
        cls.superuser = User.objects.create_user(
            username='pkr-su', password='pass', is_staff=True, is_superuser=True
        )

        # Build minimal plan + switch class + server class needed to render connection form
        from dcim.models import DeviceType as DT
        mfr, _ = Manufacturer.objects.get_or_create(
            name='PKR-SWVendor', defaults={'slug': 'pkr-swvendor'}
        )
        dt, _ = DT.objects.get_or_create(
            manufacturer=mfr, model='PKR-SW', defaults={'slug': 'pkr-sw'}
        )
        ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=dt,
            defaults={
                'native_speed': 400, 'supported_breakouts': ['1x400g'],
                'mclag_capable': False, 'hedgehog_roles': ['server-leaf'],
            },
        )
        srv_mfr, _ = Manufacturer.objects.get_or_create(
            name='PKR-SrvV', defaults={'slug': 'pkr-srvv'}
        )
        srv_dt, _ = DT.objects.get_or_create(
            manufacturer=srv_mfr, model='PKR-Srv', defaults={'slug': 'pkr-srv'}
        )
        cls.plan = TopologyPlan.objects.create(name='PKR-Plan', status=TopologyPlanStatusChoices.DRAFT)
        cls.sw = PlanSwitchClass.objects.create(
            plan=cls.plan, switch_class_id='pkr-fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=ext, uplink_ports_per_switch=4,
        )
        bo, _ = BreakoutOption.objects.get_or_create(
            breakout_id='pkr-1x400g',
            defaults={'from_speed': 400, 'logical_ports': 1, 'logical_speed': 400},
        )
        cls.zone = SwitchPortZone.objects.create(
            switch_class=cls.sw, zone_name='pkr-server-zone',
            zone_type=PortZoneTypeChoices.SERVER, port_spec='1-32',
            breakout_option=bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=100,
        )
        cls.sc = PlanServerClass.objects.create(
            plan=cls.plan, server_class_id='pkr-gpu',
            category=ServerClassCategoryChoices.GPU,
            quantity=2, gpus_per_server=8, server_device_type=srv_dt,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='pkr-su', password='pass')

    # PKR-4: server connection edit form renders description label
    def test_pkr4_connection_edit_form_shows_description_label(self):
        sc = self.__class__.sc
        plan = self.__class__.plan
        # Add form URL with server_class pre-set
        url = (reverse('plugins:netbox_hedgehog:planserverconnection_add')
               + f'?plan={plan.pk}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # The description text must appear in the select widget options
        self.assertIn('PKR Form Label Optic 200G', content)

    # PKR-5: zone edit form renders description label
    def test_pkr5_zone_edit_form_shows_description_label(self):
        url = reverse('plugins:netbox_hedgehog:switchportzone_edit',
                      args=[self.__class__.zone.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('PKR Form Label Optic 200G', content)

    # Raw model string must still appear (for search compatibility)
    def test_model_string_also_present_in_picker(self):
        url = reverse('plugins:netbox_hedgehog:switchportzone_edit',
                      args=[self.__class__.zone.pk])
        resp = self.client.get(url)
        self.assertContains(resp, 'PKR-FORM-XCVR')

    # Help text must tell the user where the switch-side optic is edited
    def test_connection_form_help_text_mentions_zone(self):
        plan = self.__class__.plan
        url = (reverse('plugins:netbox_hedgehog:planserverconnection_add')
               + f'?plan={plan.pk}')
        resp = self.client.get(url)
        content = resp.content.decode()
        self.assertIn('zone', content.lower())
        self.assertIn('switch-side', content.lower())
