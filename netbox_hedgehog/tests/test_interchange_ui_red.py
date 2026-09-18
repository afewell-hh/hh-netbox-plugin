"""#682 RED UI-first, paste-only interchange contract.

No application UI exists yet, so failures from this module must identify absent
UI/lifecycle behavior -- never a mocked substitute.  Every future success path
uses Django's real client, NetBox ObjectPermission records, and the production
``netbox_hedgehog.interchange`` service.

The product owner has approved configurable defaults for #681 §8.1. Transport
size belongs to NGINX Unit and receives no application source location; decoded
object/depth bounds require one. The application still rejects absent or
mismatched ``Content-Length`` by a bounded read, without fabricating a location.
"""

from __future__ import annotations

import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from netbox_hedgehog.models.interchange import (
    InterchangeAudit, InterchangeCatalogVersion, InterchangeDesignRevision,
)
from netbox_hedgehog.tests.interchange_ui_inventory import UI_PASTE_INVENTORY
from netbox_hedgehog.tests.seam_evidence import find_secret_leaks
from netbox_hedgehog.tests.test_interchange import fixtures


URLS = {
    "design_list": "plugins:netbox_hedgehog:interchangedesignrevision_list",
    "catalog_list": "plugins:netbox_hedgehog:interchangecatalogversion_list",
    "paste_import": "plugins:netbox_hedgehog:interchange_import",
    "design_detail": "plugins:netbox_hedgehog:interchangedesignrevision",
    "design_edit": "plugins:netbox_hedgehog:interchangedesignrevision_edit",
    "design_delete": "plugins:netbox_hedgehog:interchangedesignrevision_delete",
    "design_export": "plugins:netbox_hedgehog:interchangedesignrevision_export",
    "design_approve": "plugins:netbox_hedgehog:interchangedesignrevision_approve",
    "catalog_publish": "plugins:netbox_hedgehog:interchangecatalogversion_publish",
}

# Coverage is declared rather than inferred from names: the #682 dispatch has
# many adjacent UX rows, and an omitted dictionary entry must fail review rather
# than quietly becoming an untested promise.  A blocked row is deliberately not
# listed here: it has no behavior test until its governing decision is made.
DISPATCHED_UI_ROWS = frozenset(f"U{number}" for number in range(1, 36))

UI_ROW_TESTS = {
    "U1": ["UiPasteFlowRedTestCase.test_u1_lists_load_and_filter_by_object_permission"],
    "U2": ["UiPasteFlowRedTestCase.test_u2_add_form_loads_and_has_paste_not_file_control"],
    "U3": [
        "UiPasteFlowRedTestCase.test_u3_valid_paste_uses_production_core_and_redirects_to_draft",
        "UiPasteFlowRedTestCase.test_u3_view_delegates_to_core_import_service",
    ],
    "U4": ["UiPasteFlowRedTestCase.test_u4_detail_and_export_are_view_gated"],
    "U5/U6": ["UiPasteFlowRedTestCase.test_u5_u6_edit_and_delete_follow_real_draft_flow"],
    "U7": ["UiPasteFlowRedTestCase.test_u7_invalid_paste_renders_safe_source_location_in_response"],
    "U8": ["UiPasteFlowRedTestCase.test_u8_filename_and_content_type_do_not_select_format"],
    "U9/U12": ["UiPasteFlowRedTestCase.test_u9_u12_failure_and_identity_conflict_leave_no_partial_rows"],
    "U10/U11": ["UiPasteFlowRedTestCase.test_u10_u11_success_is_unapproved_and_retry_preserves_audit_history"],
    "U13/U18": ["PermissionAndLifecycleRedTestCase.test_u13_u18_filtered_detail_and_export_hide_out_of_scope_revision"],
    "U14/U15": ["PermissionAndLifecycleRedTestCase.test_u14_u15_denial_and_success_are_real_responses"],
    "U16": ["PermissionAndLifecycleRedTestCase.test_u16_reference_scope_is_checked_before_import_write"],
    "U17": [
        "PermissionAndLifecycleRedTestCase.test_u17_mixed_bundle_names_missing_catalog_capability",
        "PermissionAndLifecycleRedTestCase.test_u17_design_only_bundle_does_not_require_catalog_contributor",
    ],
    "U19": ["PermissionAndLifecycleRedTestCase.test_u19_locked_revision_rejects_change_without_constraint"],
    "U20/U33": ["PermissionAndLifecycleRedTestCase.test_u20_u33_transition_requires_custom_not_change_permission"],
    "U21": ["PermissionAndLifecycleRedTestCase.test_u21_existing_but_unauthorized_and_permitted_but_absent_do_not_disclose"],
    "U22": ["PasteLimitsSecretsAndSurfaceRedTestCase.test_u22_no_rest_or_graphql_interchange_surface"],
    "U23/U24/U25": ["PasteLimitsSecretsAndSurfaceRedTestCase.test_u23_u24_u25_artifact_class_is_visible_immutable_and_download_is_audited"],
    "U26": [
        "PasteLimitsSecretsAndSurfaceRedTestCase.test_u26_designated_credential_field_is_never_echoed",
        "PasteLimitsSecretsAndSurfaceRedTestCase.test_u26_invalid_free_text_is_not_retained_in_paste_control",
        "PasteLimitsSecretsAndSurfaceRedTestCase.test_u26_decoder_and_hostile_key_errors_never_escape_any_ui_sink",
    ],
    "U27": ["PasteLimitsSecretsAndSurfaceRedTestCase.test_u27_secret_absence_and_audit_presence_are_paired"],
    "U28": [
        "PasteLimitsSecretsAndSurfaceRedTestCase.test_u28_shipped_defaults_are_configurable",
        "PasteLimitsSecretsAndSurfaceRedTestCase.test_u28_encoded_body_over_default_is_rejected_without_location",
        "PasteLimitsSecretsAndSurfaceRedTestCase.test_u28_absent_or_mismatched_content_length_is_rejected_without_location",
        "PasteLimitsSecretsAndSurfaceRedTestCase.test_u28_decoded_object_and_depth_limits_are_source_located",
        "PasteLimitsSecretsAndSurfaceRedTestCase.test_u28_operation_ceiling_is_a_bounded_failure_not_a_timeout",
    ],
    "U29/U30/U31": ["PasteLimitsSecretsAndSurfaceRedTestCase.test_upload_rows_are_na_with_678_reason_and_no_file_control"],
    "U32": ["PasteLimitsSecretsAndSurfaceRedTestCase.test_u32_failure_audit_is_minimal_nonsecret_and_never_false_success"],
    "U34/U35": [
        "PermissionAndLifecycleRedTestCase.test_u34_all_lifecycle_permissions_are_declared_on_their_own_models",
        "PermissionAndLifecycleRedTestCase.test_u34_u35_declared_custom_permission_and_state_are_both_required",
    ],
}

UI_BLOCKED_ROWS = {}

IMPORT_LIMIT_DEFAULTS = {
    "max_encoded_body_bytes": 10 * 1024 * 1024,
    "max_objects": 5000,
    "max_nesting_depth": 32,
    "max_operation_seconds": 30,
}


def configured_import_limits():
    """The supported UI setting: defaults are part of the product contract,
    but deployment owners may override each value without changing code."""
    return settings.PLUGINS_CONFIG["netbox_hedgehog"]["interchange_import_limits"]


def with_import_limits(**overrides):
    plugin_config = dict(settings.PLUGINS_CONFIG.get("netbox_hedgehog", {}))
    limits = dict(IMPORT_LIMIT_DEFAULTS)
    limits.update(overrides)
    plugin_config["interchange_import_limits"] = limits
    config = dict(settings.PLUGINS_CONFIG)
    config["netbox_hedgehog"] = plugin_config
    return override_settings(PLUGINS_CONFIG=config)

# These rows are present but their current assertion cannot by itself prove the
# full GREEN claim. Keeping this record next to the map prevents a future pass
# from reading an implementation limitation as evidence.
UI_GREEN_PHASE_BINDINGS = {
    "S3/U27": (
        "U27 records that the T3 inventory is incomplete; inspecting inventory status "
        "is not paired secret-absence/audit-presence evidence. GREEN must exercise every "
        "implemented path with a synthetic secret and a corresponding audit assertion."
    ),
    "S4/U28 transport": (
        "Django's test client starts below NGINX Unit, so U28 proves the application "
        "Content-Length and bounded-read contract but cannot prove Unit's 10 MiB front-end "
        "request limit. GREEN needs a real HTTP probe through the deployment listener; it "
        "must remain distinct from decoded-content source-location assertions."
    ),
}

def ui_url(name, *args):
    """The absent route is the RED signal; never replace it with a stub."""
    return reverse(URLS[name], args=args)


class UiRedFixtureMixin:
    def setUp(self):
        self.user = get_user_model().objects.create_user("ui-red", password="test")
        self.client.force_login(self.user)

    def grant(self, model, *actions, constraints=None):
        from users.models import ObjectPermission
        perm = ObjectPermission.objects.create(
            name=f"#682-{model._meta.model_name}-{'-'.join(actions)}",
            actions=list(actions), constraints=constraints,
        )
        perm.object_types.add(ContentType.objects.get_for_model(model))
        perm.users.add(self.user)
        return perm

    def valid_paste(self):
        return json.dumps(fixtures.valid_bundle())

    def paste_post(self, paste, **headers):
        """Browser-default urlencoded paste, never multipart upload data."""
        from urllib.parse import urlencode
        body = urlencode({"paste": paste}).encode()
        return self.client.generic(
            "POST", ui_url("paste_import"), body,
            content_type="application/x-www-form-urlencoded", **headers,
        )


class UiPasteFlowRedTestCase(UiRedFixtureMixin, TestCase):
    """U1--U13: real request shapes, RED until UI routes/views exist."""

    def test_u1_lists_load_and_filter_by_object_permission(self):
        self.grant(InterchangeDesignRevision, "view")
        self.grant(InterchangeCatalogVersion, "view")
        self.assertEqual(self.client.get(ui_url("design_list")).status_code, 200)
        self.assertEqual(self.client.get(ui_url("catalog_list")).status_code, 200)

    def test_u2_add_form_loads_and_has_paste_not_file_control(self):
        response = self.client.get(ui_url("paste_import"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="paste"')
        self.assertNotContains(response, 'type="file"')

    def test_u3_valid_paste_uses_production_core_and_redirects_to_draft(self):
        self.grant(InterchangeDesignRevision, "add", "view")
        self.grant(InterchangeCatalogVersion, "add", "view")
        response = self.paste_post(self.valid_paste())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InterchangeDesignRevision.objects.count(), 1)
        self.assertFalse(InterchangeDesignRevision.objects.get().approved)
        self.assertFalse(InterchangeCatalogVersion.objects.get().published)

    def test_u3_view_delegates_to_core_import_service(self):
        """Mechanism check paired with the unmocked request test above."""
        self.grant(InterchangeDesignRevision, "add", "view")
        self.grant(InterchangeCatalogVersion, "add", "view")
        from netbox_hedgehog import interchange

        with patch(
            "netbox_hedgehog.views.interchange.interchange.import_bundle",
            wraps=interchange.import_bundle,
        ) as import_bundle:
            response = self.paste_post(self.valid_paste())
        self.assertEqual(response.status_code, 302)
        import_bundle.assert_called_once()

    def test_u4_detail_and_export_are_view_gated(self):
        self.grant(InterchangeDesignRevision, "view")
        revision = InterchangeDesignRevision.objects.create(
            namespace="com.hedgehog.ui", slug="draft", revision="1", document={}, artifact_digest="a" * 64)
        detail = self.client.get(ui_url("design_detail", revision.pk))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(self.client.get(ui_url("design_export", revision.pk)).status_code, 200)

    def test_u5_u6_edit_and_delete_follow_real_draft_flow(self):
        self.grant(InterchangeDesignRevision, "view", "change", "delete")
        revision = InterchangeDesignRevision.objects.create(
            namespace="com.hedgehog.ui", slug="draft", revision="1", document={}, artifact_digest="b" * 64)
        self.assertEqual(self.client.post(ui_url("design_edit", revision.pk), {"revision": "1"}).status_code, 302)
        self.assertEqual(self.client.post(ui_url("design_delete", revision.pk)).status_code, 302)
        self.assertFalse(InterchangeDesignRevision.objects.filter(pk=revision.pk).exists())

    def test_u7_invalid_paste_renders_safe_source_location_in_response(self):
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        document = fixtures.valid_bundle()
        document["objects"][1]["topology"]["fabrics"][0]["family"] = "not-a-family"
        response = self.paste_post(json.dumps(document))
        self.assertEqual(response.status_code, 200)
        for token in ("member", "path", "line", "column"):
            self.assertContains(response, token)

    def test_u8_filename_and_content_type_do_not_select_format(self):
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        response = self.client.generic(
            "POST", ui_url("paste_import"), self.valid_paste(), content_type="text/plain",
        )
        self.assertEqual(response.status_code, 302)

    def test_u9_u12_failure_and_identity_conflict_leave_no_partial_rows(self):
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        before = (InterchangeDesignRevision.objects.count(), InterchangeCatalogVersion.objects.count())
        response = self.paste_post("not: [valid")
        self.assertEqual(response.status_code, 200)
        self.assertEqual((InterchangeDesignRevision.objects.count(), InterchangeCatalogVersion.objects.count()), before)

    def test_u10_u11_success_is_unapproved_and_retry_preserves_audit_history(self):
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        self.paste_post(self.valid_paste())
        first = InterchangeAudit.objects.count()
        retry = self.paste_post(self.valid_paste())
        self.assertEqual(retry.status_code, 302)
        self.assertEqual(InterchangeDesignRevision.objects.count(), 1)
        self.assertGreater(InterchangeAudit.objects.count(), first)


class PermissionAndLifecycleRedTestCase(UiRedFixtureMixin, TestCase):
    """U14--U21 and U33--U35: actual client/ObjectPermission contract."""

    def _revision(self, approved=False):
        return InterchangeDesignRevision.objects.create(
            namespace="com.hedgehog.ui", slug=f"r-{InterchangeDesignRevision.objects.count()}", revision="1",
            approved=approved, document={}, artifact_digest=f"{InterchangeDesignRevision.objects.count():064x}")

    def test_u14_u15_denial_and_success_are_real_responses(self):
        self.assertIn(self.client.get(ui_url("design_list")).status_code, (403, 404))
        self.grant(InterchangeDesignRevision, "view")
        self.assertEqual(self.client.get(ui_url("design_list")).status_code, 200)

    def test_u16_reference_scope_is_checked_before_import_write(self):
        self.grant(InterchangeDesignRevision, "add", constraints={"namespace": "com.hedgehog.allowed"})
        response = self.paste_post(self.valid_paste())
        self.assertIn(response.status_code, (403, 400))
        self.assertFalse(InterchangeDesignRevision.objects.exists())

    def test_u17_mixed_bundle_names_missing_catalog_capability(self):
        self.grant(InterchangeDesignRevision, "add")
        response = self.paste_post(self.valid_paste())
        self.assertIn(response.status_code, (403, 400))
        self.assertContains(response, "catalog", status_code=response.status_code)

    def test_u17_design_only_bundle_does_not_require_catalog_contributor(self):
        """The mixed-bundle rule must not erase the design-author capability."""
        from netbox_hedgehog import interchange

        bundle = fixtures.valid_bundle()
        catalog, design = bundle["objects"]
        InterchangeCatalogVersion.objects.create(
            namespace=catalog["identity"]["namespace"],
            slug=catalog["identity"]["slug"],
            version=catalog["version"],
            content=catalog["catalogContent"],
            content_algorithm=interchange.BINDING_ALGORITHM,
            content_digest=interchange.content_integrity_digest(catalog["catalogContent"]),
            artifact_digest="d" * 64,
        )
        bundle["objects"] = [design]
        bundle["manifest"]["objects"] = [bundle["manifest"]["objects"][1]]
        self.grant(InterchangeDesignRevision, "add")
        response = self.paste_post(json.dumps(bundle))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InterchangeDesignRevision.objects.count(), 1)

    def test_u19_locked_revision_rejects_change_without_constraint(self):
        self.grant(InterchangeDesignRevision, "change")
        revision = self._revision(approved=True)
        self.assertIn(self.client.post(ui_url("design_edit", revision.pk), {}).status_code, (403, 409))

    def test_u20_u33_transition_requires_custom_not_change_permission(self):
        self.grant(InterchangeDesignRevision, "change")
        revision = self._revision()
        self.assertIn(self.client.post(ui_url("design_approve", revision.pk)).status_code, (403, 404))

    def test_u34_u35_declared_custom_permission_and_state_are_both_required(self):
        from django.contrib.auth.models import Permission
        self.assertTrue(Permission.objects.filter(codename="approve_interchangedesignrevision").exists())
        self.grant(InterchangeDesignRevision, "approve")
        revision = self._revision(approved=True)
        self.assertIn(self.client.post(ui_url("design_approve", revision.pk)).status_code, (403, 409))

    def test_u34_all_lifecycle_permissions_are_declared_on_their_own_models(self):
        """A generic ``change`` grant must never stand in for a transition grant."""
        from django.contrib.auth.models import Permission

        expected = {
            InterchangeDesignRevision: {"approve_interchangedesignrevision"},
            InterchangeCatalogVersion: {
                "publish_interchangecatalogversion",
                "deprecate_interchangecatalogversion",
                "withdraw_interchangecatalogversion",
            },
        }
        for model, codenames in expected.items():
            with self.subTest(model=model._meta.label):
                declared = set(Permission.objects.filter(
                    content_type=ContentType.objects.get_for_model(model),
                    codename__in=codenames,
                ).values_list("codename", flat=True))
                self.assertSetEqual(declared, codenames)

    def test_u21_existing_but_unauthorized_and_permitted_but_absent_do_not_disclose(self):
        """The pair must be discriminating: one existing object is hidden,
        while the user is otherwise authorized to view an in-scope object."""
        permitted = self._revision()
        hidden = self._revision()
        self.grant(InterchangeDesignRevision, "view", constraints={"pk": permitted.pk})

        hidden_response = self.client.get(ui_url("design_detail", hidden.pk))
        absent_response = self.client.get(ui_url("design_detail", hidden.pk + 99999))
        self.assertEqual(hidden_response.status_code, absent_response.status_code)
        self.assertEqual(hidden_response.content, absent_response.content)

    def test_u13_u18_filtered_detail_and_export_hide_out_of_scope_revision(self):
        permitted = self._revision()
        hidden = self._revision()
        self.grant(InterchangeDesignRevision, "view", constraints={"pk": permitted.pk})
        self.assertEqual(self.client.get(ui_url("design_detail", permitted.pk)).status_code, 200)
        self.assertIn(self.client.get(ui_url("design_detail", hidden.pk)).status_code, (403, 404))
        self.assertIn(self.client.get(ui_url("design_export", hidden.pk)).status_code, (403, 404))


class PasteLimitsSecretsAndSurfaceRedTestCase(UiRedFixtureMixin, TestCase):
    """U22 and U26--U28: bounds, absence of API/upload, T3 paired evidence."""

    @staticmethod
    def _encoded_form(paste):
        from urllib.parse import urlencode
        return urlencode({"paste": paste}).encode()

    def _raw_paste_post(self, paste, **headers):
        return self.client.generic(
            "POST",
            ui_url("paste_import"),
            self._encoded_form(paste),
            content_type="application/x-www-form-urlencoded",
            **headers,
        )

    def _assert_decoded_limit_error(self, response, label):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, label)
        self.assertContains(response, 'data-source-location="true"')
        for token in ("path", "line", "column"):
            self.assertContains(response, token)
        self.assertFalse(InterchangeDesignRevision.objects.exists())
        self.assertFalse(InterchangeCatalogVersion.objects.exists())

    def _assert_transport_limit_error_without_location(self, response):
        self.assertNotIn(response.status_code, (302, 500))
        self.assertContains(response, "Content-Length", status_code=response.status_code)
        self.assertNotContains(response, 'data-source-location="true"', status_code=response.status_code)
        self.assertFalse(InterchangeDesignRevision.objects.exists())
        self.assertFalse(InterchangeCatalogVersion.objects.exists())

    def test_u28_shipped_defaults_are_configurable(self):
        self.assertDictEqual(configured_import_limits(), IMPORT_LIMIT_DEFAULTS)
        with with_import_limits(max_objects=2):
            self.assertEqual(configured_import_limits()["max_objects"], 2)

    def test_u28_encoded_body_over_default_is_rejected_without_location(self):
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        # The outer encoded request is what this limit governs, not the
        # decoded interchange document. The client can exercise the
        # application Content-Length gate; Unit's own front-end rejection is
        # recorded as a GREEN binding below.
        paste = "x" * (IMPORT_LIMIT_DEFAULTS["max_encoded_body_bytes"] + 1)
        body = self._encoded_form(paste)
        # Django's generic request-size guard is raised before a view can
        # apply its own configurable limit.  Lift only that framework guard
        # here so this real client request reaches the application boundary;
        # Unit's front-end enforcement remains separately documented.
        response = self._raw_paste_post(paste, CONTENT_LENGTH=str(len(body)))
        self._assert_transport_limit_error_without_location(response)

    def test_u28_absent_or_mismatched_content_length_is_rejected_without_location(self):
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        body = self._encoded_form(self.valid_paste())
        for label, content_length in (
            ("absent", ""),
            ("mismatched", str(len(body) - 1)),
        ):
            with self.subTest(content_length=label):
                response = self._raw_paste_post(
                    self.valid_paste(), CONTENT_LENGTH=content_length,
                )
                self._assert_transport_limit_error_without_location(response)

    def test_u28_decoded_object_and_depth_limits_are_source_located(self):
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        too_many_objects = json.dumps({"objects": [{}] * (IMPORT_LIMIT_DEFAULTS["max_objects"] + 1)})
        too_deep = "[" * (IMPORT_LIMIT_DEFAULTS["max_nesting_depth"] + 1)
        too_deep += "]" * (IMPORT_LIMIT_DEFAULTS["max_nesting_depth"] + 1)
        for label, payload in (("object", too_many_objects), ("depth", too_deep)):
            with self.subTest(limit=label):
                response = self.paste_post(payload)
                self._assert_decoded_limit_error(response, label)

    def test_u28_operation_ceiling_is_a_bounded_failure_not_a_timeout(self):
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        # Zero makes the configurable clock budget expire before core work
        # begins; the production core remains real and unmocked in the request.
        with with_import_limits(max_operation_seconds=0):
            response = self.paste_post(self.valid_paste())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "operation")
        self.assertNotContains(response, "timeout")
        self.assertNotContains(response, 'data-source-location="true"')
        self.assertFalse(InterchangeDesignRevision.objects.exists())
        self.assertFalse(InterchangeCatalogVersion.objects.exists())

    def test_u22_no_rest_or_graphql_interchange_surface(self):
        """Inspect registered API/GraphQL surfaces, not guessed public names."""
        from netbox_hedgehog.api.urls import router

        for prefix, viewset, _basename in router.registry:
            queryset = getattr(viewset, "queryset", None)
            model = getattr(queryset, "model", None)
            identifiers = (prefix, getattr(model._meta, "label_lower", "") if model else "")
            self.assertFalse(any("interchange" in value.lower() for value in identifiers))

        # GraphQL itself is a shared NetBox endpoint and legitimately answers
        # HTTP 200 for introspection.  No interchange root field *or type* may
        # be exposed, regardless of a future field's spelling.
        response = self.client.get(
            "/graphql/",
            {"query": "{__schema{queryType{fields{name}} types{name}}}"},
        )
        self.assertEqual(response.status_code, 200)
        schema = response.json()["data"]["__schema"]
        names = [field["name"] for field in schema["queryType"]["fields"]]
        names.extend(type_["name"] for type_ in schema["types"])
        self.assertFalse(any("interchange" in name.lower() for name in names))

    def test_u26_designated_credential_field_is_never_echoed(self):
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        sentinel = "K8S_TOKEN_SHOULD_NOT_RENDER"
        document = fixtures.valid_bundle()
        document["objects"][1]["password"] = sentinel
        response = self.paste_post(json.dumps(document))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, sentinel)
        self.assertContains(response, "line")
        self.assertContains(response, "column")
        self.assertNotContains(response, " path ")

    def test_u26_invalid_free_text_is_not_retained_in_paste_control(self):
        """Free text is allowed, but a failed paste must never echo it back."""
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        sentinel = "FREE_TEXT_SENTINEL_MUST_NOT_REAPPEAR"
        document = fixtures.valid_bundle()
        document["objects"][1]["assumptions"][0]["statement"] = sentinel
        # Make the document invalid independently of its free-text field.
        document["objects"][1]["topology"]["fabrics"][0]["family"] = "not-a-family"

        response = self.paste_post(json.dumps(document))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, sentinel)
        self.assertContains(response, '<textarea name="paste" rows="18"></textarea>')

    def test_u26_decoder_and_hostile_key_errors_never_escape_any_ui_sink(self):
        """#688: real requests prove the decoder boundary, not a view scrubber."""
        from django.core.signals import got_request_exception

        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        cases = (
            (
                "yaml-scanner",
                'kubernetes_token: "SENTINEL_YAML_VALUE_MUST_NOT_ESCAPE\n',
                "SENTINEL_YAML_VALUE_MUST_NOT_ESCAPE",
            ),
            (
                "json-key",
                '{"SENTINEL_JSON_KEY_MUST_NOT_ESCAPE":1,'
                '"SENTINEL_JSON_KEY_MUST_NOT_ESCAPE":2}',
                "SENTINEL_JSON_KEY_MUST_NOT_ESCAPE",
            ),
        )
        reported = []

        def exception_reporter(**kwargs):
            reported.append(kwargs)

        got_request_exception.connect(exception_reporter)
        try:
            for label, paste, sentinel in cases:
                with self.subTest(case=label), self.assertNoLogs(
                    "netbox_hedgehog", level="DEBUG"
                ):
                    response = self.paste_post(paste)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, sentinel)
                self.assertContains(response, 'data-source-location="true"')
                self.assertContains(response, "line")
                self.assertContains(response, "column")
                self.assertNotContains(response, " path ")
                failure = InterchangeAudit.objects.filter(
                    outcome="ui-import-failed"
                ).latest("pk")
                self.assertNotIn(sentinel, str(failure.payload))
                self.assertFalse(
                    InterchangeAudit.objects.filter(outcome="ui-import").exists()
                )
        finally:
            got_request_exception.disconnect(exception_reporter)
        self.assertEqual(reported, [], "handled decoder errors must not reach exception reporting")

    def test_u27_secret_absence_and_audit_presence_are_paired(self):
        self.grant(InterchangeDesignRevision, "add", "view")
        self.grant(InterchangeCatalogVersion, "add", "view")
        sentinel = "T3_UI_SECRET_MUST_NOT_ESCAPE"

        # First exercise the negative direction through the real request and
        # response: an authored designated credential never becomes a stored
        # or rendered artifact.
        rejected = fixtures.valid_bundle()
        rejected["objects"][1]["password"] = sentinel
        response = self.paste_post(json.dumps(rejected))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, sentinel)
        self.assertFalse(InterchangeDesignRevision.objects.exists())

        # Then exercise the paired positive direction.  A successful mutation
        # must create an actor/time/scope/provenance audit record, whose actual
        # structured payload and the persisted/exported artifact stay secret-free.
        response = self.paste_post(self.valid_paste())
        self.assertEqual(response.status_code, 302)
        revision = InterchangeDesignRevision.objects.get()
        audit = InterchangeAudit.objects.filter(outcome="ui-import").latest("pk")
        self.assertTrue({"actor", "time", "scope", "provenance", "request_id"}.issubset(audit.payload))
        self.assertRegex(audit.payload["request_id"], r"^[0-9a-f]{32}$")
        self.assertFalse(find_secret_leaks(audit.payload, (sentinel,), UI_PASTE_INVENTORY.secret_fields))
        self.assertFalse(find_secret_leaks(revision.document, (sentinel,), UI_PASTE_INVENTORY.secret_fields))
        exported = self.client.get(ui_url("design_export", revision.pk))
        self.assertEqual(exported.status_code, 200)
        self.assertNotContains(exported, sentinel)

        self.assertTrue(UI_PASTE_INVENTORY.touches_credentials)
        self.assertTrue(UI_PASTE_INVENTORY.touches_audit)
        self.assertTrue(UI_PASTE_INVENTORY.by_status("unverified"))
        self.assertGreaterEqual(len(UI_PASTE_INVENTORY.by_status("asserted")), 6)

    def test_u23_u24_u25_artifact_class_is_visible_immutable_and_download_is_audited(self):
        self.grant(InterchangeDesignRevision, "view")
        revision = InterchangeDesignRevision.objects.create(
            namespace="com.hedgehog.ui", slug="artifact", revision="1", document={}, artifact_digest="c" * 64)
        response = self.client.get(ui_url("design_export", revision.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "artifact")
        self.assertTrue(InterchangeAudit.objects.filter(outcome="download").exists())

    def test_u32_failure_audit_is_minimal_nonsecret_and_never_false_success(self):
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        sentinel = "PASTE_SECRET_MUST_NOT_REACH_AUDIT"
        response = self.paste_post(sentinel)
        self.assertEqual(response.status_code, 200)
        failure = InterchangeAudit.objects.filter(outcome="ui-import-failed").latest("pk")
        self.assertTrue({"actor", "time", "scope", "provenance", "request_id"}.issubset(failure.payload))
        self.assertRegex(failure.payload["request_id"], r"^[0-9a-f]{32}$")
        self.assertIsNotNone(failure.created)
        audit_payloads = list(InterchangeAudit.objects.values_list("payload", flat=True))
        self.assertFalse(any(sentinel in str(payload) for payload in audit_payloads))
        self.assertFalse(InterchangeAudit.objects.filter(outcome="success").exists())

    def test_upload_rows_are_na_with_678_reason_and_no_file_control(self):
        upload = next(p for p in UI_PASTE_INVENTORY.paths if p.name.startswith("file upload"))
        self.assertEqual(upload.status, "out_of_scope")
        self.assertEqual(upload.owner_issue, "#678")
        response = self.client.get(ui_url("paste_import"))
        self.assertNotContains(response, 'type="file"')


class InterchangeHostPrerequisiteTestCase(SimpleTestCase):
    """The plugin checks host posture; it never changes it (#684 lead gate)."""

    @staticmethod
    def _settings_with_limit(limit):
        config = dict(settings.PLUGINS_CONFIG)
        plugin = dict(config.get("netbox_hedgehog", {}))
        plugin["interchange_import_limits"] = dict(IMPORT_LIMIT_DEFAULTS)
        config["netbox_hedgehog"] = plugin
        return override_settings(
            PLUGINS_CONFIG=config,
            DATA_UPLOAD_MAX_MEMORY_SIZE=limit,
        )

    def test_host_equal_to_default_is_accepted_without_mutation(self):
        from netbox_hedgehog.checks import interchange_upload_limit_prerequisite

        with self._settings_with_limit(IMPORT_LIMIT_DEFAULTS["max_encoded_body_bytes"]):
            self.assertEqual(interchange_upload_limit_prerequisite(None), [])
            self.assertEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE,
                             IMPORT_LIMIT_DEFAULTS["max_encoded_body_bytes"])

    def test_host_greater_than_default_is_accepted_without_mutation(self):
        from netbox_hedgehog.checks import interchange_upload_limit_prerequisite

        host_limit = IMPORT_LIMIT_DEFAULTS["max_encoded_body_bytes"] + 1
        with self._settings_with_limit(host_limit):
            self.assertEqual(interchange_upload_limit_prerequisite(None), [])
            self.assertEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, host_limit)

    def test_host_lower_than_interchange_limit_is_actionably_rejected_without_mutation(self):
        from netbox_hedgehog.checks import interchange_upload_limit_prerequisite

        host_limit = IMPORT_LIMIT_DEFAULTS["max_encoded_body_bytes"] - 1
        with self._settings_with_limit(host_limit):
            errors = interchange_upload_limit_prerequisite(None)
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].id, "netbox_hedgehog.E001")
            self.assertIn(str(host_limit), errors[0].hint)
            self.assertIn(str(IMPORT_LIMIT_DEFAULTS["max_encoded_body_bytes"]), errors[0].hint)
            self.assertEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, host_limit)


class UiRedCoverageMapTestCase(SimpleTestCase):
    """Coverage-map guards: a blocked row is recorded, never deleted."""

    @staticmethod
    def _expand_rows(labels):
        return {row for label in labels for row in label.split("/")}

    def test_every_dispatched_ui_row_is_covered_or_explicitly_blocked(self):
        covered = self._expand_rows(UI_ROW_TESTS)
        blocked = self._expand_rows(UI_BLOCKED_ROWS)
        self.assertEqual(covered & blocked, set(), "a blocked row cannot read as covered")
        self.assertEqual(DISPATCHED_UI_ROWS - (covered | blocked), set(),
                         "dispatched rows silently lost from the suite")
        self.assertEqual((covered | blocked) - DISPATCHED_UI_ROWS, set(),
                         "coverage names a row absent from the #682 dispatch")

    def test_every_covered_ui_row_names_at_least_one_test(self):
        self.assertEqual(sorted(row for row, tests in UI_ROW_TESTS.items() if not tests), [])

    def test_every_named_ui_test_exists(self):
        missing = []
        for row, tests in UI_ROW_TESTS.items():
            for dotted in tests:
                class_name, method_name = dotted.split(".")
                case = globals().get(class_name)
                if not isinstance(case, type) or not callable(getattr(case, method_name, None)):
                    missing.append(f"{row}: {dotted}")
        self.assertEqual(missing, [])

    def test_blocked_rows_are_mapped_and_substantive(self):
        for row, reason in UI_BLOCKED_ROWS.items():
            with self.subTest(row=row):
                self.assertNotIn(row, UI_ROW_TESTS)
                self.assertIn(row, DISPATCHED_UI_ROWS)
                self.assertGreater(len(reason), 180)

    def test_green_phase_bindings_are_recorded_with_reasons(self):
        for binding, reason in UI_GREEN_PHASE_BINDINGS.items():
            with self.subTest(binding=binding):
                self.assertGreater(len(reason), 180)
