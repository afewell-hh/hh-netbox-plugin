"""Fabric serializer hyperlink fault (DIET-653).

NetBox derives a model's UI view name by convention as
``plugins:<app>:<modelname>_detail``. Several plugin routes do not follow that
convention -- e.g. ``HedgehogFabric`` registers ``fabric_detail`` while NetBox
looks for ``hedgehogfabric_detail``, and ``VPC`` registers plain ``vpc``.

``NetBoxModelSerializer`` carries a ``display_url`` identity field that resolves
that name at serialization time. ``extras.events.serialize_for_event()`` calls
the serializer on every create/update/delete, so for the affected models the
lookup raises and the mutation fails AFTER the write has landed -- leaving the
object changed with no audit record, and returning a 500.

SAFETY: credential values here are synthetic sentinels only.
"""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import NoReverseMatch, reverse

from core.models import ObjectChange
from extras.events import serialize_for_event
from utilities.api import get_serializer_for_model
from utilities.views import get_viewname

from netbox_hedgehog.models.fabric import HedgehogFabric

User = get_user_model()

SYNTHETIC_TOKEN = 'SYNTHETIC-653-TOKEN-DO-NOT-USE'


def _models_with_display_url():
    """Plugin models whose serializer carries NetBox's display_url field."""
    out = []
    for model in apps.get_app_config('netbox_hedgehog').get_models():
        try:
            serializer = get_serializer_for_model(model)
        except Exception:
            continue
        try:
            if 'display_url' in serializer().fields:
                out.append(model)
        except Exception:
            continue
    return out


class FabricEventSerializationTestCase(TestCase):
    """The fault itself: serialization during the event/audit path."""

    @classmethod
    def setUpTestData(cls):
        cls.fabric = HedgehogFabric.objects.create(
            name='diet653-fabric', kubernetes_namespace='default',
            kubernetes_token=SYNTHETIC_TOKEN, sync_interval=300,
        )

    def test_fabric_serializes_for_event(self):
        """serialize_for_event() must not raise -- this is what breaks audit."""
        data = serialize_for_event(self.fabric)
        self.assertIsInstance(data, dict)

    def test_event_serialization_does_not_disclose_token(self):
        """DIET-625 guarantee must survive this fix: repairing the serializer
        must not re-expose the credential into event or changelog payloads."""
        data = serialize_for_event(self.fabric)
        self.assertNotIn(SYNTHETIC_TOKEN, str(data),
                         'event payload must not contain the credential')
        self.assertNotIn('kubernetes_token', data,
                         'kubernetes_token must remain write_only')

    def test_every_display_url_model_resolves_its_ui_viewname(self):
        """Systemic guard: any model whose serializer has display_url must have
        a UI route under the name NetBox derives, or its mutations will fail the
        same way.

        The derivation must match NetBoxURLHyperlinkedIdentityField exactly:
        get_viewname(model=model) with action=None, i.e. `plugins:<app>:<model>`
        with NO `_detail` suffix. Asserting the wrong derivation here would let
        this test pass while real serialization still failed.
        """
        unresolvable = []
        for model in _models_with_display_url():
            viewname = get_viewname(model=model)
            try:
                reverse(viewname, kwargs={'pk': 1})
            except NoReverseMatch:
                unresolvable.append(f'{model.__name__} -> {viewname}')
        self.assertEqual(
            unresolvable, [],
            'these models will raise during event serialization on every '
            'create/update/delete, losing the audit record:\n  ' + '\n  '.join(unresolvable))


class FabricMutationAuditTestCase(TestCase):
    """Mutations must succeed AND leave an audit record."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='diet653-admin', password='pass', is_staff=True, is_superuser=True)

    def setUp(self):
        self.client = Client()
        self.assertTrue(self.client.login(username='diet653-admin', password='pass'))

    def test_rest_detail_returns_200(self):
        fabric = HedgehogFabric.objects.create(
            name='diet653-rest', kubernetes_namespace='default', sync_interval=300)
        response = self.client.get(
            reverse('plugins-api:netbox_hedgehog-api:hedgehogfabric-detail', args=[fabric.pk]),
            headers={'Accept': 'application/json'})
        self.assertEqual(response.status_code, 200,
                         'fabric REST detail must return 200, not 500')

    def test_rest_list_returns_200(self):
        response = self.client.get(
            reverse('plugins-api:netbox_hedgehog-api:hedgehogfabric-list'),
            headers={'Accept': 'application/json'})
        self.assertEqual(response.status_code, 200,
                         'fabric REST list must return 200, not 500')

    def test_create_produces_an_audit_record(self):
        before = ObjectChange.objects.count()
        self.client.post(reverse('plugins:netbox_hedgehog:fabric_add'), data={
            'name': 'diet653-created', 'description': '', 'status': 'active',
            'kubernetes_server': '', 'kubernetes_token': '', 'kubernetes_ca_cert': '',
            'kubernetes_namespace': 'default', 'sync_interval': 300,
        })
        self.assertTrue(HedgehogFabric.objects.filter(name='diet653-created').exists(),
                        'authorized create must persist the fabric')
        self.assertGreater(ObjectChange.objects.count(), before,
                           'a fabric create must leave a changelog record')

    def test_delete_succeeds_and_is_audited(self):
        fabric = HedgehogFabric.objects.create(
            name='diet653-doomed', kubernetes_namespace='default', sync_interval=300)
        before = ObjectChange.objects.count()
        self.client.post(reverse('plugins:netbox_hedgehog:fabric_delete', args=[fabric.pk]))
        self.assertFalse(HedgehogFabric.objects.filter(pk=fabric.pk).exists(),
                         'authorized delete must remove the fabric')
        self.assertGreater(ObjectChange.objects.count(), before,
                           'a fabric delete must leave a changelog record')
