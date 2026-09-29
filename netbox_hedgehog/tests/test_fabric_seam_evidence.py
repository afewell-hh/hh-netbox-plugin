"""Completed emission-path inventory and paired evidence for the Fabric
credential/audit seam (DIET-665 / #662 T3).

SAFETY: every credential here is a synthetic sentinel. No real credential is
read, written, printed, or asserted against. Nothing in this module inspects,
mutates, or purges historical records -- #658 owns that separately.
"""

# interchange-security-ci: required

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from core.models import ObjectChange
from extras.events import serialize_for_event

from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.tests.seam_evidence import (
    EmissionPath,
    SeamInventory,
    find_audit_gaps,
    find_secret_leaks,
)

User = get_user_model()

SYNTHETIC_TOKEN = 'SYNTHETIC-665-TOKEN-DO-NOT-USE'
SYNTHETIC_CA = 'SYNTHETIC-665-CA-CERT-DO-NOT-USE'
SECRET_FIELDS = ('kubernetes_token', 'kubernetes_ca_cert')


#: The completed inventory. Dev A owns its completeness; Dev B reviews it.
FABRIC_SEAM = SeamInventory(
    seam='HedgehogFabric credential/audit',
    secret_fields=SECRET_FIELDS,
    touches_credentials=True,
    touches_audit=True,
    paths=(
        EmissionPath(
            'FabricSerializer', 'api_serializer', 'asserted',
            "fields='__all__' with write_only on both secret fields (#625); "
            'asserted by test_rest_paths_emit_no_secret.'),
        EmissionPath(
            'HedgehogFabricSerializer', 'event', 'asserted',
            'NetBox event-system alias; feeds serialize_for_event on every '
            'mutation (#653). Asserted by test_event_path_emits_no_secret.'),
        EmissionPath(
            'HedgehogFabric.serialize_object', 'snapshot', 'asserted',
            'Change-log snapshot path. Distinct from the REST serializers -- '
            'redacting those did NOT cover this (#653). Excluded via '
            'CHANGELOG_EXCLUDED_FIELDS; asserted by test_changelog_snapshot_*.'),
        EmissionPath(
            'HedgehogFabric.serialize_object', 'changelog', 'asserted',
            'Same call reached through ObjectChange persistence; asserted '
            'against a real mutation rather than a direct call.'),
        EmissionPath(
            'HedgehogFabricForm (forms/__init__)', 'model_serialization', 'asserted',
            'The form the legacy CRUD views bind. SECRET_FIELDS blanked in '
            '__init__ plus PasswordInput(render_value=False); asserted by '
            'test_form_render_emits_no_secret.'),
        EmissionPath(
            'fabric_edit.html', 'model_serialization', 'asserted',
            'Renders {{ form.kubernetes_token }} / _ca_cert; inherits the '
            'widget redaction above. Covered by the same rendered-response test.'),
        EmissionPath(
            'simple_sync connection_error', 'error_handling', 'unverified',
            'Connection-test failure text is persisted to '
            'HedgehogFabric.connection_error and re-emitted via messages.error '
            'and JsonResponse. connection_error is NOT write_only, so anything '
            'reaching it also reaches the REST and changelog paths. Whether the '
            'upstream Kubernetes client can place credential material in that '
            'text is NOT established here; test_error_field_leak_is_detected '
            'proves the check would catch it if it did.'),
        EmissionPath(
            'FabricForm (forms/fabric.py)', 'model_serialization', 'latent',
            'A second fabric form -- class name is FabricForm, NOT '
            'HedgehogFabricForm (corrected by Dev B review). Unredacted '
            'Textarea for both secret fields. Not imported anywhere, so it is '
            'unreachable today, but would emit secrets if wired up.'),
        EmissionPath(
            'HedgehogFabricForm (forms/fabric_forms.py)', 'model_serialization', 'latent',
            'A THIRD fabric form, missed in the original inventory. Its '
            '__init__ seeds the STORED kubeconfig into the rendered field: '
            "self.fields['kubeconfig_content'].initial = yaml.dump(...). That "
            'is the #625 shape exactly -- stored credential material rendered '
            'back into the page -- and a kubeconfig carries credentials. Not '
            'imported, so latent, but it is a live rendering pattern if wired '
            'up. Note kubeconfig_content is not among this seam\'s '
            'secret_fields; a reachable version would require extending them.'),
        EmissionPath(
            'simple_sync sync_error', 'error_handling', 'unverified',
            'Missed in the original inventory. Sync failures persist text to '
            'HedgehogFabric.sync_error, which like connection_error is NOT '
            'write_only, so it reaches the REST, event and changelog paths. '
            'simple_sync.py:252 assigns str(e) directly -- an arbitrary '
            'exception string, which carries more upstream context than the '
            'curated result.get("error") used for connection_error. Failures '
            'are also written to logger.error with a full traceback. Whether '
            'the Kubernetes client places credential material in either is NOT '
            'established; test_sync_error_field_leak_is_detected proves the '
            'check would catch it.'),
        EmissionPath(
            'simple_sync logger.error traceback', 'log', 'unverified',
            'Sync/connection failures log full tracebacks. Log content is not '
            'covered by write_only and is retained outside the database. Not '
            'established as leaking; enumerated so it is not omitted.'),
        EmissionPath(
            'HedgehogFabric.get_kubernetes_config()', 'cache', 'unverified',
            'Builds an in-process dict containing the bearer token for adapter '
            'use. Downgraded from asserted per Dev B review: no test in this '
            'repository proves its output never reaches a serialized or '
            'persisted path, and proving that negative across all callers is '
            'not attempted here. It returns the credential by design; the open '
            'question is caller discipline, not this function.'),
        EmissionPath(
            'historical ObjectChange rows', 'retention_backup', 'out_of_scope',
            'Records written before #653 may contain credential material. '
            'Forward redaction does not purge history.',
            owner_issue='#658'),
    ),
    notes='Enumerated from a full source survey of both secret field names '
          'across the plugin, excluding tests.',
)


class FabricSeamInventoryTestCase(TestCase):
    """The inventory itself must stay honest and complete."""

    def test_inventory_declares_credential_and_audit_exposure(self):
        """#665 acceptance 3: evidence explicitly records whether the seam
        touches credential/audit paths. A 'no' would be valid but must be stated."""
        self.assertTrue(FABRIC_SEAM.touches_credentials)
        self.assertTrue(FABRIC_SEAM.touches_audit)

    def test_inventory_covers_the_required_path_categories(self):
        """Every category #661 F5 names that is applicable to this seam must be
        enumerated, so a category cannot be skipped by omission."""
        required = {
            'api_serializer', 'model_serialization', 'event',
            'snapshot', 'changelog', 'error_handling', 'retention_backup',
        }
        missing = required - FABRIC_SEAM.categories_covered()
        self.assertEqual(missing, set(), f'unenumerated emission categories: {sorted(missing)}')

    def test_non_asserted_paths_state_why(self):
        """An unverified/latent/out_of_scope path must carry a reason; silence
        is how a path gets forgotten."""
        for path in FABRIC_SEAM.paths:
            if path.status != 'asserted':
                self.assertTrue(
                    path.detail.strip(),
                    f'{path.name} is {path.status} and must explain why')
            if path.status == 'out_of_scope':
                self.assertTrue(path.owner_issue, f'{path.name} must name its owner')


class FabricSecretAbsenceTestCase(TestCase):
    """Direction 1 -- no secret leaves the system through an enumerated path."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='seam-admin', password='pass', is_staff=True, is_superuser=True)
        cls.fabric = HedgehogFabric.objects.create(
            name='seam-fabric', kubernetes_namespace='default', sync_interval=300,
            kubernetes_token=SYNTHETIC_TOKEN, kubernetes_ca_cert=SYNTHETIC_CA)

    def setUp(self):
        self.client = Client()
        self.assertTrue(self.client.login(username='seam-admin', password='pass'))

    def _assert_clean(self, payload, label, payload_kind='structured'):
        leaks = find_secret_leaks(
            payload, (SYNTHETIC_TOKEN, SYNTHETIC_CA), SECRET_FIELDS, payload_kind)
        self.assertEqual(leaks, [], f'{label} leaked: {leaks}')

    def test_event_path_emits_no_secret(self):
        self._assert_clean(serialize_for_event(self.fabric), 'event serialization')

    def test_rest_paths_emit_no_secret(self):
        for name, args in (
            ('hedgehogfabric-detail', [self.fabric.pk]),
            ('hedgehogfabric-list', []),
        ):
            response = self.client.get(
                reverse(f'plugins-api:netbox_hedgehog-api:{name}', args=args),
                headers={'Accept': 'application/json'})
            self._assert_clean(response.content.decode(), f'REST {name}')

    def test_form_render_emits_no_secret(self):
        response = self.client.get(
            reverse('plugins:netbox_hedgehog:fabric_edit', args=[self.fabric.pk]))
        self.assertEqual(response.status_code, 200)
        # markup: a field's name attribute is structural, not a disclosure.
        # The VALUE check still applies -- see
        # test_markup_mode_still_detects_a_rendered_secret_value.
        self._assert_clean(response.content.decode(), 'rendered edit form', 'markup')

    def test_changelog_snapshot_emits_no_secret(self):
        self._assert_clean(self.fabric.serialize_object(), 'changelog snapshot')

    # --- the regression shapes must actually be detectable ------------------

    def test_secret_emission_regression_is_detected(self):
        """#625 shape: a path that emits the credential must FAIL the check.

        Without this, a passing suite proves only that nothing was inspected.
        """
        leaks = find_secret_leaks(
            {'name': 'x', 'kubernetes_token': SYNTHETIC_TOKEN},
            (SYNTHETIC_TOKEN, SYNTHETIC_CA), SECRET_FIELDS)
        self.assertTrue(leaks, 'an emitted credential must be detected')
        self.assertTrue(any('VALUE' in leak for leak in leaks))
        self.assertTrue(any('KEY' in leak for leak in leaks))

    def test_markup_mode_still_detects_a_rendered_secret_value(self):
        """markup mode relaxes the KEY check only. The actual #625 leak was a
        Textarea rendering the stored credential as its content -- a VALUE -- so
        this proves the relaxation does not blind the original detection."""
        leaked_html = (
            f'<textarea name="kubernetes_token">{SYNTHETIC_TOKEN}</textarea>')
        leaks = find_secret_leaks(
            leaked_html, (SYNTHETIC_TOKEN,), SECRET_FIELDS, 'markup')
        self.assertTrue(leaks, 'a credential rendered into markup must be detected')
        self.assertTrue(any('VALUE' in leak for leak in leaks))

    def test_markup_mode_ignores_only_the_structural_field_name(self):
        """The converse: a form field name with no value present is not a leak."""
        clean_html = '<input name="kubernetes_token" value="" type="password">'
        leaks = find_secret_leaks(
            clean_html, (SYNTHETIC_TOKEN,), SECRET_FIELDS, 'markup')
        self.assertEqual(leaks, [], f'structural field name must not be a leak: {leaks}')

    def test_redacted_value_under_a_surviving_key_is_detected(self):
        """Blanking the value but leaving the key is not redaction; the field
        was merely emptied, which is how a later change silently re-exposes it."""
        leaks = find_secret_leaks(
            {'kubernetes_token': ''}, (SYNTHETIC_TOKEN,), SECRET_FIELDS)
        self.assertTrue(leaks, 'a surviving secret key must be detected')

    def test_nested_secret_key_is_detected(self):
        """A surviving secret key nested inside a structured payload must be
        caught. REST and event payloads nest routinely, so a top-level-only
        check would miss the likeliest real shape."""
        leaks = find_secret_leaks(
            {'spec': {'kubernetes_token': ''}}, (SYNTHETIC_TOKEN,), SECRET_FIELDS)
        self.assertTrue(leaks, 'a nested secret key must be detected')
        self.assertIn('spec.kubernetes_token', leaks[0])

    def test_list_nested_secret_key_is_detected(self):
        """Same, through a sequence -- list payloads are common in list endpoints."""
        leaks = find_secret_leaks(
            {'results': [{'kubernetes_ca_cert': ''}]}, (SYNTHETIC_TOKEN,), SECRET_FIELDS)
        self.assertTrue(leaks, 'a list-nested secret key must be detected')
        self.assertIn('results[0].kubernetes_ca_cert', leaks[0])

    def test_sync_error_field_leak_is_detected(self):
        """The second enumerated `unverified` error path. sync_error takes
        str(e) directly, so it carries whatever an upstream exception says."""
        leaks = find_secret_leaks(
            {'sync_error': f'401 Unauthorized: Bearer {SYNTHETIC_TOKEN}'},
            (SYNTHETIC_TOKEN,), SECRET_FIELDS)
        self.assertTrue(leaks, 'credential material in sync_error must be detected')

    def test_error_field_leak_is_detected(self):
        """The enumerated `unverified` path: connection_error is not write_only,
        so anything reaching it also reaches REST and changelog. This proves the
        check would catch it -- it does NOT claim the upstream client leaks."""
        leaks = find_secret_leaks(
            {'connection_error': f'auth failed: Bearer {SYNTHETIC_TOKEN}'},
            (SYNTHETIC_TOKEN,), SECRET_FIELDS)
        self.assertTrue(leaks, 'credential material in an error field must be detected')


class FabricAuditPresenceTestCase(TestCase):
    """Direction 2 -- a mutation must leave a correct audit record."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='seam-audit', password='pass', is_staff=True, is_superuser=True)

    def setUp(self):
        self.client = Client()
        self.assertTrue(self.client.login(username='seam-audit', password='pass'))

    def _record_for(self, pk):
        """Only the record for the object this test created. No historical scan."""
        return ObjectChange.objects.filter(
            changed_object_type=ContentType.objects.get_for_model(HedgehogFabric),
            changed_object_id=pk,
        ).order_by('-time').first()

    def test_mutation_produces_a_complete_audit_record(self):
        self.client.post(reverse('plugins:netbox_hedgehog:fabric_add'), data={
            'name': 'seam-audited', 'description': '', 'status': 'active',
            'kubernetes_server': '', 'kubernetes_token': SYNTHETIC_TOKEN,
            'kubernetes_ca_cert': SYNTHETIC_CA,
            'kubernetes_namespace': 'default', 'sync_interval': 300,
        })
        fabric = HedgehogFabric.objects.filter(name='seam-audited').first()
        self.assertIsNotNone(fabric, 'authorized create must persist the fabric')

        record = self._record_for(fabric.pk)
        gaps = find_audit_gaps(record)
        self.assertEqual(gaps, [], f'audit record incomplete: {gaps}')

    def test_audit_record_carries_no_secret(self):
        """Both directions on the same record: present AND redacted."""
        self.client.post(reverse('plugins:netbox_hedgehog:fabric_add'), data={
            'name': 'seam-both', 'description': '', 'status': 'active',
            'kubernetes_server': '', 'kubernetes_token': SYNTHETIC_TOKEN,
            'kubernetes_ca_cert': SYNTHETIC_CA,
            'kubernetes_namespace': 'default', 'sync_interval': 300,
        })
        fabric = HedgehogFabric.objects.filter(name='seam-both').first()
        record = self._record_for(fabric.pk)
        self.assertIsNotNone(record)
        leaks = find_secret_leaks(
            f'{record.prechange_data} {record.postchange_data}',
            (SYNTHETIC_TOKEN, SYNTHETIC_CA), SECRET_FIELDS)
        self.assertEqual(leaks, [], f'audit record leaked: {leaks}')

    # --- the regression shapes must actually be detectable ------------------

    def test_missing_audit_record_is_detected(self):
        """#653 shape: a mutation landing with no audit record at all."""
        gaps = find_audit_gaps(None)
        self.assertEqual(gaps, ['no audit record was produced for the mutation'])

    def test_empty_audit_record_is_detected(self):
        """An audit row that exists but carries nothing is not a neutral
        outcome -- #665 says an empty record is a failure."""

        class _Empty:
            user = None
            user_name = ''
            time = None
            changed_object_type = None
            changed_object_id = None
            object_repr = ''
            prechange_data = None
            postchange_data = None

        gaps = find_audit_gaps(_Empty())
        for expected in ('actor absent', 'time absent', 'scope absent', 'provenance absent'):
            self.assertTrue(
                any(expected in gap for gap in gaps),
                f'an empty audit record must report {expected!r}; got {gaps}')
