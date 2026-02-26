"""
RED tests for YAML case ingestion engine (DIET-TEST Phase 3).

These tests define expected behavior for:
- upsert from validated YAML payload
- idempotent apply
- ownership conflict protection
- prune behavior
- require-reference strict mode
"""

from __future__ import annotations

import importlib

from django.test import TestCase

from netbox_hedgehog.models.topology_planning import TopologyPlan


class YAMLCaseIngestionRedTestCase(TestCase):
    """RED: ingestion contract tests."""

    def _import_ingest(self):
        try:
            return importlib.import_module("netbox_hedgehog.test_cases.ingest")
        except ModuleNotFoundError as exc:
            self.fail(
                "Missing module netbox_hedgehog.test_cases.ingest. "
                "Phase 4 must implement YAML ingestion engine. "
                f"Original error: {exc}"
            )

    def _minimal_case(self, case_id="case_min"):
        return {
            "meta": {
                "case_id": case_id,
                "name": f"Case {case_id}",
                "version": 1,
                "managed_by": "yaml",
            },
            "plan": {
                "name": f"Plan {case_id}",
                "status": "draft",
                "description": "yaml-managed test plan",
            },
            "switch_classes": [],
            "server_classes": [],
            "server_connections": [],
        }

    def test_apply_case_upserts_plan_graph(self):
        ingest = self._import_ingest()
        case = self._minimal_case("upsert_case")

        ingest.apply_case(case, clean=False, prune=False, reference_mode="ensure")

        self.assertTrue(TopologyPlan.objects.filter(name="Plan upsert_case").exists())

    def test_apply_case_is_idempotent(self):
        ingest = self._import_ingest()
        case = self._minimal_case("idempotent_case")

        ingest.apply_case(case, clean=False, prune=False, reference_mode="ensure")
        ingest.apply_case(case, clean=False, prune=False, reference_mode="ensure")

        self.assertEqual(TopologyPlan.objects.filter(name="Plan idempotent_case").count(), 1)

    def test_apply_case_rejects_ownership_conflict(self):
        ingest = self._import_ingest()
        TopologyPlan.objects.create(name="Plan conflict_case", status="draft")
        case = self._minimal_case("conflict_case")

        with self.assertRaises(Exception):
            ingest.apply_case(case, clean=False, prune=False, reference_mode="ensure")

    def test_apply_case_prune_deletes_removed_objects(self):
        ingest = self._import_ingest()
        case = self._minimal_case("prune_case")

        ingest.apply_case(case, clean=False, prune=False, reference_mode="ensure")
        self.assertTrue(TopologyPlan.objects.filter(name="Plan prune_case").exists())

        case["plan"]["name"] = "Plan prune_case_renamed"
        ingest.apply_case(case, clean=False, prune=True, reference_mode="ensure")

        self.assertFalse(TopologyPlan.objects.filter(name="Plan prune_case").exists())
        self.assertTrue(TopologyPlan.objects.filter(name="Plan prune_case_renamed").exists())

    def test_apply_case_require_reference_mode_fails_missing_reference(self):
        ingest = self._import_ingest()
        case = self._minimal_case("require_ref_case")
        case["reference_data"] = {
            "manufacturers": [{"name": "Missing Vendor", "slug": "missing-vendor"}],
        }

        with self.assertRaises(Exception):
            ingest.apply_case(case, clean=False, prune=False, reference_mode="require")
