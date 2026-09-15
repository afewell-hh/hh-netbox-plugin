"""#682 RED UI-first, paste-only interchange contract.

No application UI exists yet, so failures from this module must identify absent
UI/lifecycle behavior -- never a mocked substitute.  Every future success path
uses Django's real client, NetBox ObjectPermission records, and the production
``netbox_hedgehog.interchange`` service.
"""

from __future__ import annotations

import json
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from netbox_hedgehog.models.interchange import (
    InterchangeAudit, InterchangeCatalogVersion, InterchangeDesignRevision,
)
from netbox_hedgehog.tests import seam_evidence
from netbox_hedgehog.tests.interchange_ui_inventory import UI_PASTE_INVENTORY
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

LIMITS = {"encoded_body": 10 * 1024 * 1024, "objects": 5000, "depth": 32, "seconds": 30}
CUSTOM_PERMISSIONS = (
    "approve_interchangedesignrevision",
    "publish_interchangecatalogversion",
    "deprecate_interchangecatalogversion",
    "withdraw_interchangecatalogversion",
)


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


class UiPasteFlowRedTestCase(UiRedFixtureMixin, TestCase):
    """U1--U13: real request shapes, RED until UI routes/views exist."""

    def test_u1_lists_load_and_filter_by_object_permission(self):
        self.grant(InterchangeDesignRevision, "view")
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
        response = self.client.post(ui_url("paste_import"), {"paste": self.valid_paste()})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InterchangeDesignRevision.objects.count(), 1)
        self.assertFalse(InterchangeDesignRevision.objects.get().approved)
        self.assertFalse(InterchangeCatalogVersion.objects.get().published)

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

    def test_u7_invalid_paste_renders_source_location_in_response(self):
        self.grant(InterchangeDesignRevision, "add")
        response = self.client.post(ui_url("paste_import"), {"paste": "apiVersion: ["})
        self.assertEqual(response.status_code, 200)
        for token in ("member", "path", "line", "column"):
            self.assertContains(response, token)

    def test_u8_filename_and_content_type_do_not_select_format(self):
        response = self.client.post(ui_url("paste_import"), {"paste": self.valid_paste(), "filename": "wrong.txt"},
                                    content_type="text/plain")
        self.assertEqual(response.status_code, 302)

    def test_u9_u12_failure_and_identity_conflict_leave_no_partial_rows(self):
        before = (InterchangeDesignRevision.objects.count(), InterchangeCatalogVersion.objects.count())
        response = self.client.post(ui_url("paste_import"), {"paste": "not: [valid"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual((InterchangeDesignRevision.objects.count(), InterchangeCatalogVersion.objects.count()), before)

    def test_u10_u11_success_is_unapproved_and_retry_preserves_audit_history(self):
        self.grant(InterchangeDesignRevision, "add")
        self.grant(InterchangeCatalogVersion, "add")
        self.client.post(ui_url("paste_import"), {"paste": self.valid_paste()})
        first = InterchangeAudit.objects.count()
        retry = self.client.post(ui_url("paste_import"), {"paste": self.valid_paste()})
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
        response = self.client.post(ui_url("paste_import"), {"paste": self.valid_paste()})
        self.assertIn(response.status_code, (403, 400))
        self.assertFalse(InterchangeDesignRevision.objects.exists())

    def test_u17_mixed_bundle_names_missing_catalog_capability(self):
        self.grant(InterchangeDesignRevision, "add")
        response = self.client.post(ui_url("paste_import"), {"paste": self.valid_paste()})
        self.assertIn(response.status_code, (403, 400))
        self.assertContains(response, "catalog", status_code=response.status_code)

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

    def test_u21_authorization_precedes_lookup_and_response_does_not_disclose(self):
        existing = self._revision()
        existing_response = self.client.get(ui_url("design_detail", existing.pk))
        absent_response = self.client.get(ui_url("design_detail", existing.pk + 99999))
        self.assertEqual(existing_response.status_code, absent_response.status_code)
        self.assertEqual(existing_response.content, absent_response.content)

    def test_u13_u18_filtered_detail_and_export_hide_out_of_scope_revision(self):
        permitted = self._revision()
        hidden = self._revision()
        self.grant(InterchangeDesignRevision, "view", constraints={"pk": permitted.pk})
        self.assertEqual(self.client.get(ui_url("design_detail", permitted.pk)).status_code, 200)
        self.assertIn(self.client.get(ui_url("design_detail", hidden.pk)).status_code, (403, 404))
        self.assertIn(self.client.get(ui_url("design_export", hidden.pk)).status_code, (403, 404))


class PasteLimitsSecretsAndSurfaceRedTestCase(UiRedFixtureMixin, TestCase):
    """U22 and U26--U28: bounds, absence of API/upload, T3 paired evidence."""

    def test_u22_no_rest_or_graphql_interchange_surface(self):
        for path in ("/api/plugins/netbox-hedgehog/interchange-design-revisions/",
                     "/graphql/?query={interchangeDesignRevisions{id}}"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_u26_secret_is_path_only_and_never_echoed(self):
        sentinel = "K8S_TOKEN_SHOULD_NOT_RENDER"
        document = fixtures.valid_bundle()
        document["objects"][1]["assumptions"][0]["statement"] = sentinel
        response = self.client.post(ui_url("paste_import"), {"paste": json.dumps(document)})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, sentinel)
        self.assertContains(response, "path")

    def test_u27_secret_absence_and_audit_presence_are_paired(self):
        self.assertTrue(UI_PASTE_INVENTORY.touches_credentials)
        self.assertTrue(UI_PASTE_INVENTORY.touches_audit)
        self.assertEqual(UI_PASTE_INVENTORY.by_status("asserted"), [])
        self.assertTrue(UI_PASTE_INVENTORY.by_status("unverified"))

    def test_u28_exact_encoded_object_depth_and_time_limits(self):
        for label, payload in (
            ("encoded", "x" * (LIMITS["encoded_body"] + 1)),
            ("objects", json.dumps({"objects": [{}] * (LIMITS["objects"] + 1)})),
            ("depth", "[" * (LIMITS["depth"] + 1) + "]" * (LIMITS["depth"] + 1)),
        ):
            with self.subTest(limit=label):
                response = self.client.post(ui_url("paste_import"), {"paste": payload})
                self.assertEqual(response.status_code, 413)

    def test_u23_u24_u25_artifact_class_is_visible_immutable_and_download_is_audited(self):
        self.grant(InterchangeDesignRevision, "view")
        revision = InterchangeDesignRevision.objects.create(
            namespace="com.hedgehog.ui", slug="artifact", revision="1", document={}, artifact_digest="c" * 64)
        response = self.client.get(ui_url("design_export", revision.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "artifact")
        self.assertTrue(InterchangeAudit.objects.filter(outcome="download").exists())

    def test_u32_failure_audit_is_minimal_nonsecret_and_never_false_success(self):
        sentinel = "PASTE_SECRET_MUST_NOT_REACH_AUDIT"
        response = self.client.post(ui_url("paste_import"), {"paste": sentinel})
        self.assertEqual(response.status_code, 200)
        audit_payloads = list(InterchangeAudit.objects.values_list("payload", flat=True))
        self.assertFalse(any(sentinel in str(payload) for payload in audit_payloads))
        self.assertFalse(InterchangeAudit.objects.filter(outcome="success").exists())

    def test_upload_rows_are_na_with_678_reason_and_no_file_control(self):
        upload = next(p for p in UI_PASTE_INVENTORY.paths if p.name.startswith("file upload"))
        self.assertEqual(upload.status, "out_of_scope")
        self.assertEqual(upload.owner_issue, "#678")
        response = self.client.get(ui_url("paste_import"))
        self.assertNotContains(response, 'type="file"')
