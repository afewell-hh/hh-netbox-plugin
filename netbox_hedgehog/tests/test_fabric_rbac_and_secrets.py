"""Legacy fabric CRUD authorization and credential exposure (DIET-625).

Two defects reported under #618 and validated here as real request flows:

1. The legacy fabric CRUD routes are plain Django generic views
   (``ListView``/``CreateView``/``UpdateView``/``DeleteView`` in ``urls.py``)
   with no NetBox ObjectPermission enforcement, so any authenticated user can
   list, create, modify, and delete fabric configuration.

2. ``kubernetes_token`` is exposed on multiple paths: two REST serializers
   declaring ``fields = '__all__'`` (one of which is the NetBox event-system
   alias, so it can also reach changelog records) and the edit form/template,
   which render the stored value back into a textarea in cleartext.

SAFETY: every credential in this module is the synthetic sentinel below. No
real token is read, written, printed, or asserted against anywhere in these
tests. The sentinel is deliberately self-describing so it can never be mistaken
for a live credential in output.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from users.models import ObjectPermission

from netbox_hedgehog.models.fabric import HedgehogFabric

FABRIC_LIST = 'plugins:netbox_hedgehog:fabric_list'
FABRIC_ADD = 'plugins:netbox_hedgehog:fabric_add'
FABRIC_DETAIL = 'plugins:netbox_hedgehog:fabric_detail'
FABRIC_EDIT = 'plugins:netbox_hedgehog:fabric_edit'
FABRIC_DELETE = 'plugins:netbox_hedgehog:fabric_delete'

User = get_user_model()

#: Obviously-fake credential. Never a real token.
SYNTHETIC_TOKEN = 'SYNTHETIC-TEST-TOKEN-DO-NOT-USE-0000'
SYNTHETIC_CA = 'SYNTHETIC-TEST-CA-CERT-DO-NOT-USE-0000'


class _FabricSecurityBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username='fabric-admin', password='pass', is_staff=True, is_superuser=True,
        )
        # Least privilege: authenticated, but granted nothing on HedgehogFabric.
        cls.nobody = User.objects.create_user(
            username='fabric-nobody', password='pass', is_staff=True, is_superuser=False,
        )
        cls.fabric = HedgehogFabric.objects.create(
            name='synthetic-fabric',
            description='DIET-625 synthetic fixture',
            kubernetes_server='https://k8s.example.invalid:6443',
            kubernetes_token=SYNTHETIC_TOKEN,
            kubernetes_ca_cert=SYNTHETIC_CA,
            kubernetes_namespace='default',
        )

    @staticmethod
    def _grant(user, actions):
        perm = ObjectPermission.objects.create(name=f'fabric-{"-".join(actions)}', actions=actions)
        perm.users.add(user)
        perm.object_types.add(ContentType.objects.get_for_model(HedgehogFabric))
        return perm

    def _login(self, username):
        client = Client()
        self.assertTrue(client.login(username=username, password='pass'))
        return client


class LegacyFabricCrudAuthorizationTestCase(_FabricSecurityBase):
    """A user with no fabric permission must not be able to read or mutate fabrics."""

    def test_list_denied_without_permission(self):
        client = self._login('fabric-nobody')
        response = client.get(reverse(FABRIC_LIST))
        self.assertNotEqual(response.status_code, 404,
                            'a 404 is a routing error, not an authorization result')
        self.assertIn(response.status_code, (403, 302),
                      'fabric list must not be readable without view permission')

    def test_add_form_denied_without_permission(self):
        client = self._login('fabric-nobody')
        response = client.get(reverse(FABRIC_ADD))
        self.assertNotEqual(response.status_code, 404,
                            'a 404 is a routing error, not an authorization result')
        self.assertIn(response.status_code, (403, 302),
                      'fabric add form must not be reachable without add permission')

    def test_create_post_denied_without_permission(self):
        client = self._login('fabric-nobody')
        before = HedgehogFabric.objects.count()
        client.post(reverse(FABRIC_ADD), data={
            'name': 'unauthorized-fabric', 'status': 'active',
            'kubernetes_namespace': 'default', 'sync_interval': 300,
        })
        self.assertEqual(HedgehogFabric.objects.count(), before,
                         'unauthorized POST must not create a fabric')

    def test_edit_post_denied_without_permission(self):
        client = self._login('fabric-nobody')
        client.post(reverse(FABRIC_EDIT, args=[self.fabric.pk]), data={
            'name': 'renamed-by-unauthorized', 'status': 'active',
            'kubernetes_namespace': 'default', 'sync_interval': 300,
        })
        self.fabric.refresh_from_db()
        self.assertEqual(self.fabric.name, 'synthetic-fabric',
                         'unauthorized POST must not modify a fabric')

    def test_delete_post_denied_without_permission(self):
        client = self._login('fabric-nobody')
        client.post(reverse(FABRIC_DELETE, args=[self.fabric.pk]))
        self.assertTrue(HedgehogFabric.objects.filter(pk=self.fabric.pk).exists(),
                        'unauthorized POST must not delete a fabric')

    def test_create_allowed_with_objectpermission(self):
        """Authorized create must succeed as a real request flow."""
        self._grant(self.nobody, ['view', 'add'])
        client = self._login('fabric-nobody')
        before = HedgehogFabric.objects.count()
        client.post(reverse(FABRIC_ADD), data={
            'name': 'authorized-create', 'description': '', 'status': 'active',
            'kubernetes_server': '', 'kubernetes_token': '', 'kubernetes_ca_cert': '',
            'kubernetes_namespace': 'default', 'sync_interval': 300,
        })
        self.assertEqual(HedgehogFabric.objects.count(), before + 1,
                         'granted add permission must allow fabric creation')
        self.assertTrue(HedgehogFabric.objects.filter(name='authorized-create').exists())

    def test_delete_allowed_with_objectpermission(self):
        """Authorized delete must succeed as a real request flow."""
        self._grant(self.nobody, ['view', 'delete'])
        target = HedgehogFabric.objects.create(
            name='delete-me', kubernetes_namespace='default', sync_interval=300,
        )
        client = self._login('fabric-nobody')
        client.post(reverse(FABRIC_DELETE, args=[target.pk]))
        self.assertFalse(HedgehogFabric.objects.filter(pk=target.pk).exists(),
                         'granted delete permission must allow fabric deletion')

    def test_list_allowed_with_objectpermission(self):
        self._grant(self.nobody, ['view'])
        client = self._login('fabric-nobody')
        response = client.get(reverse(FABRIC_LIST))
        self.assertEqual(response.status_code, 200,
                         'granted view permission must allow the fabric list')

    def test_edit_allowed_with_objectpermission(self):
        self._grant(self.nobody, ['view', 'change'])
        client = self._login('fabric-nobody')
        response = client.get(reverse(FABRIC_EDIT, args=[self.fabric.pk]))
        self.assertEqual(response.status_code, 200,
                         'granted change permission must allow the edit form')


class FabricCredentialDisclosureTestCase(_FabricSecurityBase):
    """The stored token must never come back out in cleartext."""

    def test_rest_detail_does_not_disclose_token(self):
        """No status assertion: the fabric REST endpoint currently returns 500 on
        main from a pre-existing hyperlinked-relationship defect (reported
        separately). The disclosure property must hold at ANY status, so it is
        asserted unconditionally rather than gated behind a 200 this defect
        would prevent.
        """
        client = self._login('fabric-admin')
        response = client.get(
            reverse('plugins-api:netbox_hedgehog-api:hedgehogfabric-detail', args=[self.fabric.pk]),
            headers={'Accept': 'application/json'},
        )
        self.assertNotIn(SYNTHETIC_TOKEN, response.content.decode(),
                         'REST detail response must not disclose kubernetes_token')

    def test_rest_list_does_not_disclose_token(self):
        client = self._login('fabric-admin')
        response = client.get(
            reverse('plugins-api:netbox_hedgehog-api:hedgehogfabric-list'),
            headers={'Accept': 'application/json'},
        )
        self.assertNotIn(SYNTHETIC_TOKEN, response.content.decode(),
                         'REST list response must not disclose kubernetes_token')

    def test_rest_does_not_disclose_ca_cert(self):
        client = self._login('fabric-admin')
        response = client.get(
            reverse('plugins-api:netbox_hedgehog-api:hedgehogfabric-detail', args=[self.fabric.pk]),
            headers={'Accept': 'application/json'},
        )
        self.assertNotIn(SYNTHETIC_CA, response.content.decode(),
                         'REST response must not disclose kubernetes_ca_cert')

    def test_serializers_declare_secrets_write_only(self):
        """Mechanism check: absence from a response could be incidental; this
        asserts the serializers actually declare the fields write_only, on BOTH
        the REST serializer and the event-system alias that feeds change logging.
        """
        from netbox_hedgehog.api.serializers import FabricSerializer, HedgehogFabricSerializer
        for serializer_cls in (FabricSerializer, HedgehogFabricSerializer):
            fields = serializer_cls().fields
            for name in ('kubernetes_token', 'kubernetes_ca_cert'):
                self.assertTrue(
                    fields[name].write_only,
                    f'{serializer_cls.__name__}.{name} must be write_only so it is '
                    f'never emitted in a response or a changelog record')

    def test_edit_form_does_not_render_stored_token(self):
        """Even an authorised editor must not receive the stored secret back."""
        client = self._login('fabric-admin')
        response = client.get(reverse(FABRIC_EDIT, args=[self.fabric.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SYNTHETIC_TOKEN, response.content.decode(),
                         'edit form must not render the stored token back in cleartext')

    def test_edit_form_does_not_render_stored_ca_cert(self):
        """The CA cert is declared write_only in both serializers, so the form
        must not render it back either (Dev B review finding 1: the two were
        classified as sensitive but treated inconsistently)."""
        client = self._login('fabric-admin')
        response = client.get(reverse(FABRIC_EDIT, args=[self.fabric.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SYNTHETIC_CA, response.content.decode(),
                         'edit form must not render the stored CA certificate')

    def test_detail_view_does_not_render_token(self):
        client = self._login('fabric-admin')
        response = client.get(reverse(FABRIC_DETAIL, args=[self.fabric.pk]))
        if response.status_code == 200:
            self.assertNotIn(SYNTHETIC_TOKEN, response.content.decode(),
                             'fabric detail must not render the token')

    def test_blank_secret_field_preserves_stored_token(self):
        """Rotation safety: blank must mean "unchanged", not "clear".

        Exercised at form level because the legacy edit POST currently raises
        during change-log serialization on main (pre-existing defect, reported
        separately), which would mask this behaviour rather than test it.

        Without this, redaction becomes an outage: the field renders empty, an
        ordinary save submits empty, and every configured fabric silently loses
        its credential.
        """
        from netbox_hedgehog.forms import HedgehogFabricForm
        form = HedgehogFabricForm(
            data={
                'name': 'synthetic-fabric', 'description': 'edited', 'status': 'active',
                'kubernetes_server': 'https://k8s.example.invalid:6443',
                'kubernetes_token': '', 'kubernetes_ca_cert': '',
                'kubernetes_namespace': 'default', 'sync_interval': 300,
            },
            instance=self.fabric,
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        saved = form.save()
        self.assertEqual(saved.kubernetes_token, SYNTHETIC_TOKEN,
                         'a blank token field must preserve the stored value')
        self.assertEqual(saved.kubernetes_ca_cert, SYNTHETIC_CA,
                         'a blank CA field must preserve the stored value')
        self.assertEqual(saved.description, 'edited',
                         'other fields must still update normally')

    def test_explicit_new_token_replaces_stored_value(self):
        """The converse: a submitted value must still overwrite, or rotation
        would be impossible through the UI."""
        from netbox_hedgehog.forms import HedgehogFabricForm
        replacement = 'SYNTHETIC-REPLACEMENT-TOKEN-DO-NOT-USE'
        form = HedgehogFabricForm(
            data={
                'name': 'synthetic-fabric', 'description': 'rotated', 'status': 'active',
                'kubernetes_server': 'https://k8s.example.invalid:6443',
                'kubernetes_token': replacement, 'kubernetes_ca_cert': '',
                'kubernetes_namespace': 'default', 'sync_interval': 300,
            },
            instance=self.fabric,
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        saved = form.save()
        self.assertEqual(saved.kubernetes_token, replacement,
                         'an explicitly supplied token must replace the stored one')
