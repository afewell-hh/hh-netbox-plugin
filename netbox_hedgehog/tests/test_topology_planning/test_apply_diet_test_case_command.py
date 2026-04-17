"""
RED tests for apply_diet_test_case management command (DIET-TEST Phase 3).
"""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from dcim.models import DeviceType

from netbox_hedgehog.models.topology_planning import (
    PlanServerConnection,
    SwitchPortZone,
    TopologyPlan,
)


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

    def test_xoc64_case_reuses_seeded_device_types_by_slug(self):
        """
        XOC-64 case apply must converge on pre-seeded DS2000/DS1000/DS5000
        device types even when the case YAML uses different model strings for
        the same manufacturer+slug pair.
        """
        call_command("load_diet_reference_data", stdout=StringIO(), stderr=StringIO())

        self.assertTrue(
            DeviceType.objects.filter(slug="celestica-ds2000").exists(),
            "Precondition: seeded celestica-ds2000 DeviceType must exist",
        )

        out = StringIO()
        call_command(
            "apply_diet_test_case",
            "--case",
            "training_xoc64_1xopg64_mesh_conv_sh",
            "--clean",
            "--prune",
            stdout=out,
            stderr=StringIO(),
        )

        plan = TopologyPlan.objects.get(
            custom_field_data__yaml_case_id="training_xoc64_1xopg64_mesh_conv_sh"
        )
        self.assertEqual(plan.name, "Training XOC-64 1x OPG-64 Mesh Converged SH")

        nonnull_conn_xcvrs = PlanServerConnection.objects.filter(
            server_class__plan=plan,
            transceiver_module_type__isnull=False,
        )
        self.assertEqual(
            nonnull_conn_xcvrs.count(),
            14,
            "XOC-64 SH case should define transceiver ModuleTypes for every server connection",
        )

        nonnull_zone_xcvrs = SwitchPortZone.objects.filter(
            switch_class__plan=plan,
            transceiver_module_type__isnull=False,
        )
        self.assertEqual(
            nonnull_zone_xcvrs.count(),
            7,
            "XOC-64 SH case should define switch-side transceiver ModuleTypes for all active connection zones",
        )

        self.assertTrue(
            nonnull_conn_xcvrs.filter(
                connection_id="soc-storage",
                transceiver_module_type__model="QSFP112-200GBASE-SR2",
            ).exists(),
            "soc-storage server connections must use the approved QSFP112 host optic",
        )
        self.assertTrue(
            nonnull_zone_xcvrs.filter(
                zone_name="soc_storage_server_4x200",
                transceiver_module_type__model="R4113-A9220-VR",
            ).exists(),
            "soc-storage zone must use the approved DS5000 asymmetric switch optic",
        )
