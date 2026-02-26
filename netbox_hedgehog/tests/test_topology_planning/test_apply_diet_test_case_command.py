"""
RED tests for apply_diet_test_case management command (DIET-TEST Phase 3).
"""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from netbox_hedgehog.models.topology_planning import TopologyPlan


class ApplyDietTestCaseCommandRedTestCase(TestCase):
    """RED: command contract tests for YAML-driven case execution."""

    def test_list_shows_discovered_cases(self):
        out = StringIO()
        call_command("apply_diet_test_case", "--list", stdout=out, stderr=StringIO())
        output = out.getvalue()
        self.assertIn("ux_case_128gpu_odd_ports", output)

    def test_apply_single_case_success(self):
        out = StringIO()
        call_command(
            "apply_diet_test_case",
            "--case",
            "ux_case_128gpu_odd_ports",
            stdout=out,
            stderr=StringIO(),
        )
        self.assertTrue(TopologyPlan.objects.filter(name="UX Case 128GPU Odd Ports").exists())

    def test_apply_all_cases_success(self):
        out = StringIO()
        call_command("apply_diet_test_case", "--all", stdout=out, stderr=StringIO())
        output = out.getvalue()
        self.assertIn("Applied", output)

    def test_dry_run_does_not_persist(self):
        call_command(
            "apply_diet_test_case",
            "--case",
            "ux_case_128gpu_odd_ports",
            "--dry-run",
            stdout=StringIO(),
            stderr=StringIO(),
        )
        self.assertFalse(TopologyPlan.objects.filter(name="UX Case 128GPU Odd Ports").exists())

    def test_require_reference_mode_flag(self):
        out = StringIO()
        # Seed required reference data first in ensure mode.
        call_command(
            "apply_diet_test_case",
            "--case",
            "ux_case_128gpu_odd_ports",
            stdout=StringIO(),
            stderr=StringIO(),
        )
        call_command(
            "apply_diet_test_case",
            "--case",
            "ux_case_128gpu_odd_ports",
            "--require-reference",
            stdout=out,
            stderr=StringIO(),
        )
        self.assertIn("require", out.getvalue().lower())

    def test_invalid_case_id_returns_command_error(self):
        with self.assertRaises(CommandError):
            call_command(
                "apply_diet_test_case",
                "--case",
                "not_a_real_case",
                stdout=StringIO(),
                stderr=StringIO(),
            )
