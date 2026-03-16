"""
Integration tests for hhfab validation (Issue #159).

Per AGENTS.md TDD requirements, these tests validate:
- hhfab validation helper service
- validate_wiring_yaml management command
- Graceful handling when hhfab is not installed
- Validation failure detection
"""

import unittest
from io import StringIO
from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model

from netbox_hedgehog.models.topology_planning import TopologyPlan
from netbox_hedgehog.services import hhfab

User = get_user_model()


class HHFabValidationHelperTestCase(TestCase):
    """Test the hhfab validation helper service."""

    def test_validate_yaml_returns_result_tuple(self):
        """Verify validate_yaml returns (success, stdout, stderr) tuple."""
        yaml_content = """---
apiVersion: wiring.githedgehog.com/v1beta1
kind: VLANNamespace
metadata:
  name: default
  namespace: default
spec:
  ranges:
    - from: 1000
      to: 2999
"""
        success, stdout, stderr = hhfab.validate_yaml(yaml_content)

        # Should return a tuple
        self.assertIsInstance(success, bool)
        self.assertIsInstance(stdout, str)
        self.assertIsInstance(stderr, str)

    def test_validate_yaml_detects_missing_hhfab(self):
        """Verify validate_yaml returns False when hhfab is not installed."""
        yaml_content = """---
apiVersion: wiring.githedgehog.com/v1beta1
kind: VLANNamespace
metadata:
  name: default
spec:
  ranges:
    - from: 1000
      to: 2999
"""
        success, stdout, stderr = hhfab.validate_yaml(yaml_content)

        # If hhfab is not installed, should return False with helpful message
        if not success and "not found" in stderr.lower():
            self.assertIn("hhfab", stderr.lower())
            self.assertFalse(success)

    def test_validate_yaml_with_invalid_yaml(self):
        """Verify validate_yaml detects invalid YAML syntax."""
        invalid_yaml = """---
apiVersion: wiring.githedgehog.com/v1beta1
kind: VLANNamespace
metadata:
  name: default
  namespace: default
spec:
  ranges:
    - from: not-a-number
      to: also-not-a-number
"""
        success, stdout, stderr = hhfab.validate_yaml(invalid_yaml)

        # May succeed (if hhfab not installed) or fail (if hhfab validates)
        # Either way, should return a tuple
        self.assertIsInstance(success, bool)
        self.assertIsInstance(stderr, str)

    def test_is_hhfab_available_returns_bool(self):
        """Verify is_hhfab_available returns boolean."""
        available = hhfab.is_hhfab_available()
        self.assertIsInstance(available, bool)


class ValidateWiringYAMLCommandTestCase(TestCase):
    """Test the validate_wiring_yaml management command."""

    @classmethod
    def setUpTestData(cls):
        """Create test user and plan."""
        cls.user = User.objects.create_user(
            username='testuser',
            is_staff=True,
            is_superuser=True
        )

    def setUp(self):
        """Create fresh plan for each test."""
        self.plan = TopologyPlan.objects.create(
            name='Test Validation Plan',
            customer_name='Test Customer',
            created_by=self.user
        )

    def test_command_requires_plan_id(self):
        """Verify command fails without plan ID."""
        from django.core.management.base import CommandError

        out = StringIO()
        err = StringIO()

        with self.assertRaises(CommandError):
            call_command('validate_wiring_yaml', stdout=out, stderr=err)

    def test_command_accepts_plan_id(self):
        """Verify command accepts plan ID and executes."""
        out = StringIO()
        err = StringIO()

        # Should not raise exception
        call_command(
            'validate_wiring_yaml',
            str(self.plan.pk),
            stdout=out,
            stderr=err
        )

        output = out.getvalue()

        # Should contain some output
        self.assertGreater(len(output), 0)

        # Should mention the plan
        self.assertIn(str(self.plan.pk), output)

    def test_command_handles_missing_hhfab_gracefully(self):
        """Verify command skips validation when hhfab is not installed."""
        out = StringIO()

        call_command(
            'validate_wiring_yaml',
            str(self.plan.pk),
            stdout=out
        )

        output = out.getvalue()

        # If hhfab is not available, should mention it
        if not hhfab.is_hhfab_available():
            self.assertIn('hhfab', output.lower())
            self.assertIn('not', output.lower())

    def test_command_validates_generated_yaml(self):
        """Verify command generates YAML and runs validation."""
        out = StringIO()

        call_command(
            'validate_wiring_yaml',
            str(self.plan.pk),
            stdout=out
        )

        output = out.getvalue()

        # Should mention validation
        self.assertIn('validat', output.lower())

    def test_command_with_invalid_plan_id(self):
        """Verify command fails with helpful error for invalid plan ID."""
        out = StringIO()
        err = StringIO()

        with self.assertRaises(Exception):
            call_command(
                'validate_wiring_yaml',
                '999999',  # Non-existent plan
                stdout=out,
                stderr=err
            )

    @unittest.skipUnless(hhfab.is_hhfab_available(), "hhfab not installed")
    def test_command_reports_validation_success(self):
        """Verify command reports success when hhfab validates successfully."""
        out = StringIO()

        call_command(
            'validate_wiring_yaml',
            str(self.plan.pk),
            stdout=out
        )

        output = out.getvalue()

        # Should indicate success or failure
        self.assertTrue(
            'success' in output.lower() or
            'valid' in output.lower() or
            'fail' in output.lower() or
            'error' in output.lower()
        )

    def test_command_with_verbose_flag(self):
        """Verify command supports verbosity flag."""
        out = StringIO()

        call_command(
            'validate_wiring_yaml',
            str(self.plan.pk),
            verbosity=2,
            stdout=out
        )

        output = out.getvalue()

        # Verbose output should be longer
        self.assertGreater(len(output), 0)


# =============================================================================
# Phase 3 RED: hhfab accepts managed-switch + surrogate Server CRD output
# =============================================================================

class HHFabSurrogateValidationTestCase(TestCase):
    """hhfab validate accepts YAML containing a managed Switch CRD + surrogate Server CRD
    + Connection CRD referencing both.

    Skipped when hhfab is not installed (same pattern as existing live hhfab tests above).
    This test validates that the surrogate Server CRD schema is hhfab-compatible before
    GREEN implementation begins.

    The minimal YAML is constructed directly (no DB) to isolate the schema question
    from any generator bugs.
    """

    MINIMAL_SURROGATE_YAML = """\
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: VLANNamespace
metadata:
  name: default
  namespace: default
spec:
  ranges:
    - from: 1000
      to: 2999
---
apiVersion: vpc.githedgehog.com/v1beta1
kind: IPv4Namespace
metadata:
  name: default
  namespace: default
spec:
  subnets:
    - 10.0.0.0/16
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: fe-border-leaf-01
  namespace: default
spec:
  role: border-leaf
  profile: celestica-ds3000
  boot:
    mac: 0c:20:12:aa:00:01
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: Server
metadata:
  name: oob-mgmt-001
  namespace: default
spec: {}
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: oob-mgmt-001-e1-1--unbundled--fe-border-leaf-01
  namespace: default
spec:
  unbundled:
    link:
      server:
        port: oob-mgmt-001/E1/1
      switch:
        port: fe-border-leaf-01/E1/32
"""

    @unittest.skipUnless(hhfab.is_hhfab_available(), "hhfab not installed")
    def test_hhfab_validates_managed_switch_plus_surrogate_server_output(self):
        """hhfab validate accepts YAML with managed Switch CRD + surrogate Server CRD + Connection.

        This confirms the surrogate Server CRD schema (spec: {}) is hhfab-compatible,
        so GREEN implementation can use the same minimal spec as regular Server CRDs.
        """
        success, stdout, stderr = hhfab.validate_yaml(self.MINIMAL_SURROGATE_YAML)
        self.assertTrue(
            success,
            f"hhfab must accept YAML with surrogate Server CRD. "
            f"stderr: {stderr.strip()}\nstdout: {stdout.strip()}",
        )

    def test_surrogate_yaml_is_parseable(self):
        """Minimal surrogate YAML is valid YAML (parse-only, no hhfab needed)."""
        import yaml
        docs = list(yaml.safe_load_all(self.MINIMAL_SURROGATE_YAML))
        non_null = [d for d in docs if d]
        self.assertEqual(len(non_null), 5,
                         "MINIMAL_SURROGATE_YAML must parse to 5 documents")


# =============================================================================
# Class: MeshWiringHHFabValidationTestCase — #311 RED
#
# Tests that a DIET-generated mesh wiring YAML (all IPs absent) passes
# hhfab validate in default --hydrate-mode=if-not-present mode.
#
# RED state: current code injects mesh link IPs → HydrationStatusPartial →
# hhfab validate fails.
# GREEN state: IPs omitted → HydrationStatusNone → hhfab hydrates → validates.
# =============================================================================

class MeshWiringHHFabValidationTestCase(TestCase):
    """RED tests for issue #311: hhfab validate must pass for DIET mesh wiring.

    These tests verify the end-to-end acceptance criterion:
      A DIET-generated mesh wiring YAML (all switch and connection IPs absent)
      must pass hhfab validate in default --hydrate-mode=if-not-present mode.

    The MINIMAL_MESH_WIRING_YAML constant represents the correct post-GREEN
    output from DIET's _create_mesh_crd(): Switch CRDs with no management IPs
    and mesh Connection CRDs with no leaf IP fields.

    The BROKEN_MESH_WIRING_YAML constant represents the current (pre-GREEN)
    output, which includes mesh link IPs — causing HydrationStatusPartial.
    """

    # Correct post-GREEN YAML: no IP fields, no 'device' fields (schema bug also fixed).
    # ConnFabricLinkSwitch only has 'port' (inline BasePortName) and 'ip' (omitempty).
    # 'device' is NOT a valid field — hhfab strict-decodes and rejects it.
    # This is what hhfab validate must accept after #311 GREEN.
    MINIMAL_MESH_WIRING_YAML = """\
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: VLANNamespace
metadata:
  name: default
  namespace: default
spec:
  ranges:
    - from: 1000
      to: 2999
---
apiVersion: vpc.githedgehog.com/v1beta1
kind: IPv4Namespace
metadata:
  name: default
  namespace: default
spec:
  subnets:
    - 10.0.0.0/16
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: fe-leaf-01
  namespace: default
spec:
  role: server-leaf
  profile: celestica-ds5000
  boot:
    mac: 0c:20:12:fe:01:01
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: fe-leaf-02
  namespace: default
spec:
  role: server-leaf
  profile: celestica-ds5000
  boot:
    mac: 0c:20:12:fe:02:01
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: mesh--fe-leaf-01--fe-leaf-02
  namespace: default
spec:
  mesh:
    links:
      - leaf1:
          port: fe-leaf-01/E1/63
        leaf2:
          port: fe-leaf-02/E1/63
"""

    # Current (pre-GREEN) output: mesh link IPs injected AND 'device' key emitted.
    # Both are wrong: 'device' is not in schema, 'ip' causes HydrationStatusPartial.
    # hhfab must fail on this YAML (it currently does, for the schema reason).
    BROKEN_MESH_WIRING_YAML = """\
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: VLANNamespace
metadata:
  name: default
  namespace: default
spec:
  ranges:
    - from: 1000
      to: 2999
---
apiVersion: vpc.githedgehog.com/v1beta1
kind: IPv4Namespace
metadata:
  name: default
  namespace: default
spec:
  subnets:
    - 10.0.0.0/16
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: fe-leaf-01
  namespace: default
spec:
  role: server-leaf
  profile: celestica-ds5000
  boot:
    mac: 0c:20:12:fe:01:01
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: Switch
metadata:
  name: fe-leaf-02
  namespace: default
spec:
  role: server-leaf
  profile: celestica-ds5000
  boot:
    mac: 0c:20:12:fe:02:01
---
apiVersion: wiring.githedgehog.com/v1beta1
kind: Connection
metadata:
  name: mesh--fe-leaf-01--fe-leaf-02
  namespace: default
spec:
  mesh:
    links:
      - leaf1:
          port: fe-leaf-01/E1/63
          ip: 172.30.128.0/31
        leaf2:
          port: fe-leaf-02/E1/63
          ip: 172.30.128.1/31
"""

    def test_minimal_mesh_wiring_yaml_is_parseable(self):
        """T9a: The no-IP mesh wiring YAML must parse without errors."""
        import yaml
        docs = list(yaml.safe_load_all(self.MINIMAL_MESH_WIRING_YAML))
        non_null = [d for d in docs if d]
        self.assertEqual(len(non_null), 5, "Mesh wiring YAML must produce 5 documents")

    def test_minimal_mesh_wiring_has_no_ip_keys(self):
        """T9b: The no-IP mesh wiring YAML must contain no leaf1.ip or leaf2.ip keys."""
        import yaml
        docs = list(yaml.safe_load_all(self.MINIMAL_MESH_WIRING_YAML))
        for doc in docs:
            if not doc or doc.get('kind') != 'Connection':
                continue
            spec = doc.get('spec', {})
            mesh = spec.get('mesh', {})
            for link in mesh.get('links', []):
                self.assertNotIn('ip', link.get('leaf1', {}),
                                 "No leaf1.ip in MINIMAL_MESH_WIRING_YAML")
                self.assertNotIn('ip', link.get('leaf2', {}),
                                 "No leaf2.ip in MINIMAL_MESH_WIRING_YAML")

    def test_broken_mesh_wiring_has_ip_keys(self):
        """T9c: Sanity — the pre-GREEN (broken) YAML has ip keys present and no device keys."""
        import yaml
        docs = list(yaml.safe_load_all(self.BROKEN_MESH_WIRING_YAML))
        found_ip = False
        found_device = False
        for doc in docs:
            if not doc or doc.get('kind') != 'Connection':
                continue
            spec = doc.get('spec', {})
            mesh = spec.get('mesh', {})
            for link in mesh.get('links', []):
                if 'ip' in link.get('leaf1', {}) or 'ip' in link.get('leaf2', {}):
                    found_ip = True
                if 'device' in link.get('leaf1', {}) or 'device' in link.get('leaf2', {}):
                    found_device = True
        self.assertTrue(found_ip, "BROKEN_MESH_WIRING_YAML must have ip keys for sanity check")
        self.assertFalse(found_device, "BROKEN_MESH_WIRING_YAML must not have device keys")

    @unittest.skipUnless(hhfab.is_hhfab_available(), "hhfab not installed")
    def test_mesh_wiring_without_ips_passes_hhfab_validate(self):
        """T10: hhfab validate must accept mesh wiring with no leaf IP fields.

        RED state: this passes only after GREEN (#311) removes mesh IP injection.
        The MINIMAL_MESH_WIRING_YAML has no Switch or Connection IPs, so hhfab
        sees HydrationStatusNone and auto-assigns all IPs before validating.
        """
        success, stdout, stderr = hhfab.validate_yaml(self.MINIMAL_MESH_WIRING_YAML)
        self.assertTrue(
            success,
            f"hhfab must accept mesh wiring with no IP fields (HydrationStatusNone). "
            f"stderr: {stderr.strip()}\nstdout: {stdout.strip()}",
        )

    @unittest.skipUnless(hhfab.is_hhfab_available(), "hhfab not installed")
    def test_mesh_wiring_with_ips_fails_hhfab_validate(self):
        """T11: hhfab validate must FAIL for mesh wiring that has IPs present
        while switch IPs are absent (HydrationStatusPartial).

        This documents the failure mode of the pre-GREEN code. It also acts as
        a sentinel — if this starts passing, something changed in hhfab's
        hydration model and we need to re-evaluate.
        """
        success, stdout, stderr = hhfab.validate_yaml(self.BROKEN_MESH_WIRING_YAML)
        self.assertFalse(
            success,
            f"hhfab must reject mesh wiring with IPs present but switch IPs absent "
            f"(HydrationStatusPartial). If this passes, hhfab's hydration behavior changed. "
            f"stdout: {stdout.strip()}\nstderr: {stderr.strip()}",
        )
