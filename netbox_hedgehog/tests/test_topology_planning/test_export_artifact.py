"""
Integration tests for export_wiring_yaml management command (DIET-224).

These tests validate artifact capture reliability and observability:
- Complete YAML written to a deterministic path
- Integrity metadata emitted (sha256, bytes, lines, documents)
- Atomic write prevents partial-file artifacts
- Written file re-parses as a complete YAML document stream
- Invalid path/permission failure surfaces a clear error
- Rerun on unchanged inventory yields identical sha256

Tests do NOT use mocks for the YAML generator; they rely on the real
generate_yaml_for_plan() path, which always emits at least 2 CRD documents
(VLANNamespace + IPv4Namespace) even for plans with no generated devices.

## Invariants
- Unchanged: generation semantics, yaml_generator output, existing export view
- Changed: artifact capture reliability and observability only
"""

import hashlib
import os
import tempfile

import yaml

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from netbox_hedgehog.choices import GenerationStatusChoices
from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    GenerationState,
)


class ExportArtifactHappyPathTestCase(TestCase):
    """
    Integration tests for the export_wiring_yaml happy path.

    Uses a plan with GENERATED status and no device inventory.
    The real YAML generator always emits VLANNamespace + IPv4Namespace (2 docs minimum).
    """

    @classmethod
    def setUpTestData(cls):
        cls.plan = TopologyPlan.objects.create(
            name="Test Export Plan",
            customer_name="Test Customer",
        )
        GenerationState.objects.create(
            plan=cls.plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status=GenerationStatusChoices.GENERATED,
        )

    def test_export_writes_complete_yaml_file(self):
        """Export command writes a non-empty file that parses as complete YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "wiring.yaml")

            call_command(
                "export_wiring_yaml",
                str(self.plan.pk),
                "--output", output_path,
            )

            self.assertTrue(os.path.exists(output_path), "Output file must exist")
            self.assertGreater(os.path.getsize(output_path), 0, "Output file must be non-empty")

            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()

            docs = list(yaml.safe_load_all(content))
            non_null_docs = [d for d in docs if d is not None]
            self.assertGreater(len(non_null_docs), 0, "Written file must contain at least one document")

    def test_export_emits_required_metadata(self):
        """Export command stdout includes sha256, bytes, lines, documents, plan_id."""
        from io import StringIO

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "wiring.yaml")
            out = StringIO()

            call_command(
                "export_wiring_yaml",
                str(self.plan.pk),
                "--output", output_path,
                stdout=out,
            )

        output = out.getvalue()
        self.assertIn("sha256:", output)
        self.assertIn("bytes:", output)
        self.assertIn("lines:", output)
        self.assertIn("documents:", output)
        self.assertIn(f"plan_id:", output)
        self.assertIn("[OK] Export complete:", output)

    def test_export_sha256_matches_file_content(self):
        """sha256 in output matches actual sha256 of written file bytes."""
        from io import StringIO

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "wiring.yaml")
            out = StringIO()

            call_command(
                "export_wiring_yaml",
                str(self.plan.pk),
                "--output", output_path,
                stdout=out,
            )

            with open(output_path, "rb") as f:
                actual_sha256 = hashlib.sha256(f.read()).hexdigest()

        output = out.getvalue()
        sha256_line = [ln for ln in output.splitlines() if "sha256:" in ln][0]
        reported_sha256 = sha256_line.split("sha256:")[-1].strip()

        self.assertEqual(reported_sha256, actual_sha256, "Reported sha256 must match file content")

    def test_export_includes_minimum_crd_kinds(self):
        """Written file contains VLANNamespace and IPv4Namespace (minimum guaranteed documents)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "wiring.yaml")

            call_command(
                "export_wiring_yaml",
                str(self.plan.pk),
                "--output", output_path,
            )

            with open(output_path, "r", encoding="utf-8") as f:
                docs = list(yaml.safe_load_all(f.read()))

        kinds = {d.get("kind") for d in docs if isinstance(d, dict)}
        self.assertIn("VLANNamespace", kinds, "Export must include VLANNamespace CRD")
        self.assertIn("IPv4Namespace", kinds, "Export must include IPv4Namespace CRD")

    def test_export_reproducible_identical_checksum(self):
        """Rerun on unchanged inventory yields identical sha256."""
        from io import StringIO

        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = os.path.join(tmpdir, "run1.yaml")
            path2 = os.path.join(tmpdir, "run2.yaml")

            out1 = StringIO()
            call_command(
                "export_wiring_yaml",
                str(self.plan.pk),
                "--output", path1,
                stdout=out1,
            )

            out2 = StringIO()
            call_command(
                "export_wiring_yaml",
                str(self.plan.pk),
                "--output", path2,
                stdout=out2,
            )

        def extract_sha256(output):
            for ln in output.splitlines():
                if "sha256:" in ln:
                    return ln.split("sha256:")[-1].strip()
            return None

        sha1 = extract_sha256(out1.getvalue())
        sha2 = extract_sha256(out2.getvalue())

        self.assertIsNotNone(sha1)
        self.assertEqual(sha1, sha2, "Rerun on unchanged inventory must yield identical sha256")


class ExportArtifactPreconditionTestCase(TestCase):
    """Tests for precondition failures that must surface clear errors."""

    @classmethod
    def setUpTestData(cls):
        cls.plan_no_state = TopologyPlan.objects.create(
            name="Plan Without Generation State",
        )
        cls.plan_failed = TopologyPlan.objects.create(
            name="Plan With Failed Generation",
        )
        GenerationState.objects.create(
            plan=cls.plan_failed,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status=GenerationStatusChoices.FAILED,
        )

    def test_nonexistent_plan_raises_error(self):
        """Command raises CommandError for non-existent plan ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "export_wiring_yaml",
                    "999999",
                    "--output", os.path.join(tmpdir, "out.yaml"),
                )
        self.assertIn("does not exist", str(ctx.exception))

    def test_plan_without_generation_state_raises_error(self):
        """Command raises CommandError when plan has no generation state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "export_wiring_yaml",
                    str(self.plan_no_state.pk),
                    "--output", os.path.join(tmpdir, "out.yaml"),
                )
        self.assertIn("No generation state", str(ctx.exception))

    def test_failed_generation_state_raises_error(self):
        """Command raises CommandError when generation status is not GENERATED."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "export_wiring_yaml",
                    str(self.plan_failed.pk),
                    "--output", os.path.join(tmpdir, "out.yaml"),
                )
        self.assertIn("status", str(ctx.exception).lower())

    def test_nonexistent_output_directory_raises_error(self):
        """Command raises CommandError when output directory does not exist."""
        plan = TopologyPlan.objects.create(name="Plan For Bad Path Test")
        GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status=GenerationStatusChoices.GENERATED,
        )

        with self.assertRaises(CommandError) as ctx:
            call_command(
                "export_wiring_yaml",
                str(plan.pk),
                "--output", "/nonexistent/directory/wiring.yaml",
            )
        self.assertIn("does not exist", str(ctx.exception))
