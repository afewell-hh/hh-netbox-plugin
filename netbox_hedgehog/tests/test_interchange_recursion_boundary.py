"""#693: pathological nesting must fail safely, not as an unhandled 500.

Real-request tests against the live paste surface. #672 requires a minimal
non-secret failure audit for every handled failure; #687/#688 established that
decoder diagnostics must be fixed text with no untrusted echo. A document
nested past the interpreter's stack satisfied neither: it returned HTTP 500
and wrote no audit row at all.

Measured on main before the fix:

    depth  100  -> 200, 1x ui-import-failed, "depth limit exceeded"
    depth 5000  -> 500, 0 audit rows

The configured ``max_nesting_depth`` is 32 and is correctly enforced from 33
up to roughly 400. Past that, ``_walk_restricted``/``_depth``/the YAML loader
exhaust the stack before the limit check can report, and RecursionError -- a
RuntimeError, not a ValueError -- escapes ``decode_document`` uncaught.

This module pins the contract that both depths produce the *same* observable
failure, and that the mapping is specific to recursion rather than a blanket
catch that would also swallow real defects.

Out of scope: #678 upload/quarantine/reaper, #658 historical remediation.
"""

from __future__ import annotations

import json
import re
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from netbox_hedgehog import interchange
from netbox_hedgehog.models.interchange import (
    InterchangeAudit, InterchangeCatalogVersion, InterchangeDesignRevision,
    InterchangeProvenance,
)
from netbox_hedgehog.tests.test_interchange import fixtures


#: Comfortably past max_nesting_depth (32) but well inside the C stack, so the
#: existing limit check reports normally. This is the reference contract.
DEPTH_WITHIN_STACK = 100

#: Past the interpreter recursion limit (1000) on every recursive pass in the
#: decode chain. Measured failure point is ~500; 5000 is unambiguous.
DEPTH_BEYOND_STACK = 5000

SENTINEL = "HH693_DEEP_VALUE_MUST_NOT_ESCAPE"


def nested_json(depth, leaf=f'"{SENTINEL}"'):
    return '{"a":' * depth + leaf + '}' * depth


def nested_yaml(depth):
    return '[' * depth + SENTINEL + ']' * depth


class RecursionBoundaryTestCase(TestCase):
    """Both depths must be indistinguishable to the caller."""

    def setUp(self):
        from users.models import ObjectPermission
        self.user = get_user_model().objects.create_user("hh693", password="t")
        for model in (InterchangeDesignRevision, InterchangeCatalogVersion):
            perm = ObjectPermission.objects.create(
                name=f"hh693-{model._meta.model_name}", actions=["add"])
            perm.object_types.add(ContentType.objects.get_for_model(model))
            perm.users.add(self.user)

    def paste(self, body, *, raise_request_exception=True):
        client = Client(raise_request_exception=raise_request_exception)
        client.force_login(self.user)
        return client.generic(
            "POST", reverse("plugins:netbox_hedgehog:interchange_import"),
            urlencode({"paste": body}).encode(),
            content_type="application/x-www-form-urlencoded")

    @staticmethod
    def rendered_message(response):
        found = re.search(rb'alert-danger">([^<]{0,80})', response.content)
        return found.group(1).decode().strip() if found else ""

    def assert_safe_failure(self, response, label):
        """The live paste failure contract, asserted in full."""
        self.assertEqual(response.status_code, 200, f"{label}: expected a handled failure")
        self.assertNotContains(response, SENTINEL)

        audits = list(InterchangeAudit.objects.all())
        self.assertEqual(
            [a.outcome for a in audits], ["ui-import-failed"],
            f"{label}: a handled failure owes exactly one minimal failure audit")
        payload = audits[0].payload
        self.assertTrue({"actor", "time", "scope", "provenance", "request_id"}.issubset(payload))
        self.assertRegex(payload["request_id"], r"^[0-9a-f]{32}$")
        self.assertNotIn(SENTINEL, str(payload))

        self.assertFalse(InterchangeDesignRevision.objects.exists(), f"{label}: durable write")
        self.assertFalse(InterchangeCatalogVersion.objects.exists(), f"{label}: durable write")
        self.assertFalse(InterchangeProvenance.objects.exists(), f"{label}: durable write")
        self.assertFalse(InterchangeAudit.objects.filter(outcome="ui-import").exists(),
                         f"{label}: false success")

    def test_depth_within_stack_is_the_reference_contract(self):
        """Guards the behaviour the deep case must be made to match."""
        response = self.paste(nested_json(DEPTH_WITHIN_STACK))
        self.assert_safe_failure(response, "within-stack")
        self.assertContains(response, 'data-source-location="true"')
        self.assertEqual(self.rendered_message(response), "depth limit exceeded")

    def test_depth_beyond_stack_is_handled_not_a_500(self):
        """The #693 defect: this returned 500 with zero audit rows."""
        response = self.paste(nested_json(DEPTH_BEYOND_STACK),
                              raise_request_exception=False)
        self.assert_safe_failure(response, "beyond-stack")

    def test_both_depths_are_indistinguishable_to_the_caller(self):
        """A caller must not learn where the server's stack gives out.

        Differing responses would report an implementation detail of the
        deployment, and would make "too deep" mean two different things.
        """
        shallow = self.paste(nested_json(DEPTH_WITHIN_STACK))
        shallow_message = self.rendered_message(shallow)
        InterchangeAudit.objects.all().delete()

        deep = self.paste(nested_json(DEPTH_BEYOND_STACK), raise_request_exception=False)

        self.assertEqual(deep.status_code, shallow.status_code)
        self.assertEqual(self.rendered_message(deep), shallow_message)

    def test_yaml_path_beyond_stack_is_handled_too(self):
        """The YAML branch exhausts the stack in its own loader, not in _depth."""
        response = self.paste(nested_yaml(DEPTH_BEYOND_STACK),
                              raise_request_exception=False)
        self.assert_safe_failure(response, "beyond-stack-yaml")

    def test_core_decoder_maps_recursion_to_an_interchange_error(self):
        """The mapping belongs to the decoder, not to the view.

        A view that rescued this would leave every other caller of
        decode_document -- a future API, a management command -- exposed.
        """
        with self.assertRaises(interchange.InterchangeError) as caught:
            interchange.decode_document(
                nested_json(DEPTH_BEYOND_STACK),
                limits={"max_objects": 5000, "max_nesting_depth": 32,
                        "max_operation_seconds": 30})
        self.assertNotIn(SENTINEL, str(caught.exception))


class NotBlanketSuppressionTestCase(TestCase):
    """The fix must catch recursion, not everything."""

    def setUp(self):
        from users.models import ObjectPermission
        self.user = get_user_model().objects.create_user("hh693b", password="t")
        for model in (InterchangeDesignRevision, InterchangeCatalogVersion):
            perm = ObjectPermission.objects.create(
                name=f"hh693b-{model._meta.model_name}", actions=["add"])
            perm.object_types.add(ContentType.objects.get_for_model(model))
            perm.users.add(self.user)

    def test_an_unrelated_defect_is_not_swallowed(self):
        """A genuine bug must still surface, not be reported as bad input.

        This is the discriminating half of #693. Mapping RecursionError to a
        validation failure is correct; mapping *any* exception would turn
        every future defect in the decode path into "your document is too
        deep", which is both wrong and unobservable.
        """
        client = Client(raise_request_exception=False)
        client.force_login(self.user)
        boom = RuntimeError("HH693_UNRELATED_DEFECT")

        with patch.object(interchange, "_validate_document", side_effect=boom):
            response = client.generic(
                "POST", reverse("plugins:netbox_hedgehog:interchange_import"),
                urlencode({"paste": json.dumps(fixtures.valid_bundle())}).encode(),
                content_type="application/x-www-form-urlencoded")

        self.assertEqual(
            response.status_code, 500,
            "an unrelated RuntimeError must not be converted into a handled "
            "validation failure; that would hide real defects behind a "
            "user-input error message")
        self.assertFalse(
            InterchangeAudit.objects.filter(outcome="ui-import-failed").exists(),
            "a server defect is not a user input failure and must not be "
            "recorded as one")

    def test_recursion_outside_the_decoder_is_not_mapped(self):
        """Only the decode boundary maps recursion.

        If import_bundle blew the stack, that would be a server defect on
        already-validated data, not oversized input, and must not be reported
        as a depth failure.
        """
        client = Client(raise_request_exception=False)
        client.force_login(self.user)

        with patch.object(interchange, "import_bundle", side_effect=RecursionError()):
            response = client.generic(
                "POST", reverse("plugins:netbox_hedgehog:interchange_import"),
                urlencode({"paste": json.dumps(fixtures.valid_bundle())}).encode(),
                content_type="application/x-www-form-urlencoded")

        self.assertEqual(response.status_code, 500)
