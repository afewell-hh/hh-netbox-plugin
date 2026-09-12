"""Fabric serializer hyperlink fault (DIET-653).

``NetBoxURLHyperlinkedIdentityField.get_view_name()`` resolves a model's UI URL
via ``utilities.views.get_viewname(model=model)`` -- with **action=None**, which
yields ``plugins:<app>:<modelname>`` and **no** ``_detail`` suffix.

Six plugin routes did not match that derivation: ``HedgehogFabric`` registered
``fabric_detail`` (wrong on both counts -- its model name is ``hedgehogfabric``
and the convention takes no suffix), and External/ExternalAttachment/
ExternalPeering/VPCAttachment/VPCPeering each used a ``_detail`` suffix. The
other seven models already used the bare name and were never broken.

An earlier revision of this module asserted the ``_detail`` form. That was wrong,
and because the systemic guard asserted the same wrong rule it passed while real
serialization still failed. The guard below derives the name exactly as the field
does; do not reintroduce a ``_detail`` suffix here.

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

from core.choices import ObjectChangeActionChoices
from core.models import ObjectChange
from django.contrib.contenttypes.models import ContentType
from extras.events import serialize_for_event
from utilities.api import get_serializer_for_model
from utilities.views import get_viewname

from netbox_hedgehog.models.fabric import HedgehogFabric

User = get_user_model()

SYNTHETIC_TOKEN = 'SYNTHETIC-653-TOKEN-DO-NOT-USE'
SYNTHETIC_CA = 'SYNTHETIC-653-CA-CERT-DO-NOT-USE'


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
            kubernetes_token=SYNTHETIC_TOKEN, kubernetes_ca_cert=SYNTHETIC_CA,
            sync_interval=300,
        )

    def test_fabric_serializes_for_event(self):
        """serialize_for_event() must not raise -- this is what breaks audit."""
        data = serialize_for_event(self.fabric)
        self.assertIsInstance(data, dict)

    def test_event_serialization_discloses_neither_secret(self):
        """DIET-625 guarantee must survive this fix.

        #653 makes this serializer COMPLETE for the first time -- previously it
        raised, so the event surface was never actually exercised. That is
        precisely the condition under which a credential could start being
        emitted, so both secret fields are asserted here explicitly. REST and
        form coverage do not substitute for the changelog/event surface.
        """
        data = serialize_for_event(self.fabric)
        payload = str(data)
        for key in ('kubernetes_token', 'kubernetes_ca_cert'):
            self.assertNotIn(key, data,
                             f'{key} must remain write_only and absent from the event payload')
        for value, label in ((SYNTHETIC_TOKEN, 'token'), (SYNTHETIC_CA, 'CA certificate')):
            self.assertNotIn(value, payload,
                             f'event payload must not contain the {label} value')

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

    def _fabric_changes(self, pk=None):
        """ObjectChange rows for HedgehogFabric, optionally one object."""
        qs = ObjectChange.objects.filter(
            changed_object_type=ContentType.objects.get_for_model(HedgehogFabric))
        return qs.filter(changed_object_id=pk) if pk is not None else qs

    def _assert_record_carries_no_secret(self, change):
        """The audit record itself must not become a disclosure channel.

        A changelog entry is durable and outlives the object, so a credential
        captured here would survive rotation of the credential itself.
        """
        payload = f'{change.prechange_data} {change.postchange_data}'
        for key in ('kubernetes_token', 'kubernetes_ca_cert'):
            self.assertNotIn(key, payload,
                             f'{key} must not appear in the changelog record')
        for value, label in ((SYNTHETIC_TOKEN, 'token'), (SYNTHETIC_CA, 'CA certificate')):
            self.assertNotIn(value, payload,
                             f'changelog record must not contain the {label} value')

    def test_create_produces_a_correct_audit_record(self):
        """Identify the actual record -- a count increase proves only that
        *something* was logged, not that this fabric's create was."""
        self.client.post(reverse('plugins:netbox_hedgehog:fabric_add'), data={
            'name': 'diet653-created', 'description': '', 'status': 'active',
            'kubernetes_server': '', 'kubernetes_token': SYNTHETIC_TOKEN,
            'kubernetes_ca_cert': SYNTHETIC_CA,
            'kubernetes_namespace': 'default', 'sync_interval': 300,
        })
        fabric = HedgehogFabric.objects.filter(name='diet653-created').first()
        self.assertIsNotNone(fabric, 'authorized create must persist the fabric')

        changes = self._fabric_changes(fabric.pk)
        self.assertTrue(changes.exists(),
                        'the created fabric must have its own changelog record')
        change = changes.order_by('-time').first()
        self.assertEqual(change.action, ObjectChangeActionChoices.ACTION_CREATE)
        self.assertEqual(change.changed_object_type,
                         ContentType.objects.get_for_model(HedgehogFabric))
        self.assertEqual(change.changed_object_id, fabric.pk)
        self.assertIn('diet653-created', change.object_repr,
                      'the record must identify which fabric changed')
        self._assert_record_carries_no_secret(change)

    def test_delete_succeeds_and_is_correctly_audited(self):
        fabric = HedgehogFabric.objects.create(
            name='diet653-doomed', kubernetes_namespace='default',
            kubernetes_token=SYNTHETIC_TOKEN, kubernetes_ca_cert=SYNTHETIC_CA,
            sync_interval=300)
        pk = fabric.pk
        self.client.post(reverse('plugins:netbox_hedgehog:fabric_delete', args=[pk]))
        self.assertFalse(HedgehogFabric.objects.filter(pk=pk).exists(),
                         'authorized delete must remove the fabric')

        change = self._fabric_changes(pk).filter(
            action=ObjectChangeActionChoices.ACTION_DELETE).order_by('-time').first()
        self.assertIsNotNone(change,
                             'the deleted fabric must have a delete changelog record')
        self.assertEqual(change.changed_object_type,
                         ContentType.objects.get_for_model(HedgehogFabric))
        self.assertEqual(change.changed_object_id, pk)
        self.assertIn('diet653-doomed', change.object_repr,
                      'the record must identify which fabric was deleted')
        self._assert_record_carries_no_secret(change)
