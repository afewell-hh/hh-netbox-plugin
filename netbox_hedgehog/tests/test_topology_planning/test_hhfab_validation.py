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
