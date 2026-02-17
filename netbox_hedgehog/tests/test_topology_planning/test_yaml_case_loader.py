"""
RED tests for YAML test-case loader/scaffold (DIET-TEST Phase 3).

These tests define expected behavior for:
- YAML case discovery
- Case loading by ID
- Schema validation and error collection
- YAML anchors/aliases
- Parse error line-number reporting
"""

from __future__ import annotations

import importlib
import tempfile
from pathlib import Path

from django.test import SimpleTestCase


class YAMLCaseLoaderRedTestCase(SimpleTestCase):
    """RED: loader module contract tests."""

    def _import_loader(self):
        try:
            return importlib.import_module("netbox_hedgehog.test_cases.loader")
        except ModuleNotFoundError as exc:
            self.fail(
                "Missing module netbox_hedgehog.test_cases.loader. "
                "Phase 4 must implement YAML case loader. "
                f"Original error: {exc}"
            )

    def test_discover_case_files_returns_sorted_yaml_files(self):
        loader = self._import_loader()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "b_case.yaml").write_text("meta: {case_id: b_case, name: B, version: 1, managed_by: yaml}\nplan: {name: B, status: draft}\nswitch_classes: []\nserver_classes: []\nserver_connections: []\n")
            (root / "a_case.yaml").write_text("meta: {case_id: a_case, name: A, version: 1, managed_by: yaml}\nplan: {name: A, status: draft}\nswitch_classes: []\nserver_classes: []\nserver_connections: []\n")
            (root / "ignored.txt").write_text("ignore")

            files = loader.discover_case_files(root)
            self.assertEqual([p.name for p in files], ["a_case.yaml", "b_case.yaml"])

    def test_load_case_by_id_success(self):
        loader = self._import_loader()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ux_case_128gpu_odd_ports.yaml").write_text(
                "meta:\n"
                "  case_id: ux_case_128gpu_odd_ports\n"
                "  name: UX Case 128GPU Odd Ports\n"
                "  version: 1\n"
                "  managed_by: yaml\n"
                "plan:\n"
                "  name: UX Case 128GPU Odd Ports\n"
                "  status: draft\n"
                "switch_classes: []\n"
                "server_classes: []\n"
                "server_connections: []\n"
            )

            case = loader.load_case("ux_case_128gpu_odd_ports", root=root)
            self.assertEqual(case["meta"]["case_id"], "ux_case_128gpu_odd_ports")

    def test_load_case_rejects_missing_required_fields(self):
        loader = self._import_loader()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "invalid.yaml").write_text(
                "meta:\n"
                "  case_id: invalid\n"
                "  version: 1\n"
                "  managed_by: yaml\n"
                "plan:\n"
                "  status: draft\n"
            )

            with self.assertRaises(Exception):
                loader.load_case("invalid", root=root)

    def test_load_case_collects_multiple_validation_errors(self):
        loader = self._import_loader()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "multi_error.yaml").write_text(
                "meta:\n"
                "  case_id: bad-case-id\n"  # hyphen should fail v1 naming rule
                "  name: Multi Error\n"
                "  version: wrong_type\n"   # should be int
                "  managed_by: not_yaml\n"  # should be literal yaml
                "plan:\n"
                "  name: Multi Error\n"
                "  status: invalid_status\n"
                "switch_classes: not_a_list\n"
                "server_classes: not_a_list\n"
                "server_connections: not_a_list\n"
            )

            with self.assertRaises(Exception) as ctx:
                loader.load_case("multi_error", root=root)

            # The final implementation should include aggregated validation details.
            self.assertTrue(str(ctx.exception))

    def test_load_case_supports_yaml_anchors_and_aliases(self):
        loader = self._import_loader()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "anchors.yaml").write_text(
                "meta:\n"
                "  case_id: anchors\n"
                "  name: Anchors\n"
                "  version: 1\n"
                "  managed_by: yaml\n"
                "defaults: &status\n"
                "  status: draft\n"
                "plan:\n"
                "  name: Anchors\n"
                "  <<: *status\n"
                "switch_classes: []\n"
                "server_classes: []\n"
                "server_connections: []\n"
            )

            case = loader.load_case("anchors", root=root)
            self.assertEqual(case["plan"]["status"], "draft")

    def test_load_case_parse_error_includes_line_number(self):
        loader = self._import_loader()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "broken.yaml").write_text(
                "meta:\n"
                "  case_id: broken\n"
                "  name: Broken\n"
                "  version: 1\n"
                "  managed_by: yaml\n"
                "plan:\n"
                "  name: Broken\n"
                "  status: draft\n"
                "switch_classes: [\n"  # malformed YAML
            )

            with self.assertRaises(Exception) as ctx:
                loader.load_case("broken", root=root)

            self.assertIn("line", str(ctx.exception).lower())
