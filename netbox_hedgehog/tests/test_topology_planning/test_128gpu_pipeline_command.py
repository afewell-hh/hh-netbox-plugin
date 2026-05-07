"""
Integration tests for validate_case_128gpu_pipeline management command (DIET-235).

Three test classes:

  PipelineHappyPathTestCase
    - Full pipeline with a real (but minimal) generated plan using --skip-setup.
    - Verifies summary block content: plan_id, paths, sha256, PASS markers.
    - Does NOT run setup_case_128gpu_odd_ports (too slow for unit suite).
    - hhfab gate tests are skipped if hhfab is not available.

  PipelineHHFabUnavailableTestCase
    - Patches hhfab.is_hhfab_available() to return False.
    - Verifies the command reports SKIPPED (not FAIL) and exits cleanly.

  PipelineExportFailureTestCase
    - Patches export_wiring_yaml call_command to raise CommandError.
    - Verifies the failure propagates immediately with an actionable message.

## Invariants
- Unchanged: generator, export, and validation logic.
- Changed: new pipeline orchestration command only.

## Running locally

    cd /home/ubuntu/afewell-hh/netbox-docker

    # Integration tests (fast, use existing plan)
    docker compose exec netbox python manage.py test \\
        netbox_hedgehog.tests.test_topology_planning.test_128gpu_pipeline_command \\
        --keepdb --verbosity=2

    # Full golden path (uses real 128GPU setup - slow, ~5 min)
    docker compose exec netbox python manage.py validate_case_128gpu_pipeline

    # Skip setup if 128GPU plan is already generated
    docker compose exec netbox python manage.py validate_case_128gpu_pipeline --skip-setup

    # Write artifacts to a specific directory
    docker compose exec netbox python manage.py validate_case_128gpu_pipeline \\
        --skip-setup --output-dir /tmp/my-artifacts
"""

import os
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from dcim.models import DeviceRole, DeviceType, InterfaceTemplate, Manufacturer, Site

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    FabricClassChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    GenerationStatusChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    ServerClassCategoryChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanServerClass,
    PlanServerConnection,
    PlanServerNIC,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services import hhfab
from netbox_hedgehog.services.device_generator import DeviceGenerator


PLAN_NAME = "UX Case 128GPU Odd Ports"


# ---------------------------------------------------------------------------
# Shared fixture: reuses the minimal _HHFabGateBase pattern - one fe-leaf,
# one server, fully generated. Named differently to avoid DB conflicts.
# ---------------------------------------------------------------------------
class _PipelineBase(TestCase):
    """
    Minimal generated plan used as the 'existing plan' when --skip-setup is passed.

    We inject the PLAN_NAME so the pipeline command can find it via get(name=PLAN_NAME),
    then restore it after each test class.
    """

    @classmethod
    def setUpTestData(cls):
        # We need the plan to be findable by the pipeline command's PLAN_NAME lookup.
        # Create a plan with that exact name for the test run.
        TopologyPlan.objects.filter(name=PLAN_NAME).delete()

        manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica-Pipeline',
            defaults={'slug': 'celestica-pipeline'}
        )
        nvidia, _ = Manufacturer.objects.get_or_create(
            name='NVIDIA-Pipeline',
            defaults={'slug': 'nvidia-pipeline'}
        )

        server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='GPU-Server-Pipeline',
            defaults={'slug': 'gpu-server-pipeline'}
        )
        for tpl_name in ('p0', 'p1'):
            InterfaceTemplate.objects.get_or_create(
                device_type=server_type,
                name=tpl_name,
                defaults={'type': '200gbase-x-qsfp56'}
            )

        switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='DS5000-Pipeline',
            defaults={'slug': 'ds5000-pipeline'}
        )
        device_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=switch_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'native_speed': 800,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g'],
                'uplink_ports': 0,
                'hedgehog_profile_name': 'celestica-ds5000',
            }
        )

        # Use canonical breakout IDs so hhfab accepts the emitted breakout names.
        breakout_4x200, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200}
        )
        breakout_1x800, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x800g',
            defaults={'from_speed': 800, 'logical_ports': 1, 'logical_speed': 800}
        )

        server_role, _ = DeviceRole.objects.get_or_create(
            name='Server-Pipeline', defaults={'slug': 'server', 'color': 'aa1409'}
        )
        site, _ = Site.objects.get_or_create(
            name='Pipeline-Site', defaults={'slug': 'pipeline-site'}
        )

        from dcim.models import ModuleType
        nic_module_type, created = ModuleType.objects.get_or_create(
            manufacturer=nvidia,
            model='BlueField-3-Pipeline',
        )
        if created:
            for n in ('m0', 'm1'):
                InterfaceTemplate.objects.create(
                    module_type=nic_module_type, name=n, type='other'
                )

        cls.plan = TopologyPlan.objects.create(
            name=PLAN_NAME,
            customer_name='Pipeline Test',
        )

        server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='pl-fe-gpu',
            server_device_type=server_type,
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            gpus_per_server=8,
        )
        switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='pl-fe-leaf',
            fabric_name='frontend',
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=device_ext,
            uplink_ports_per_switch=0,
            mclag_pair=False,
            calculated_quantity=1,
            override_quantity=1,
        )
        server_zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=breakout_4x200,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='uplink',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='49-50',
            breakout_option=breakout_1x800,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=200,
        )
        nic, _ = PlanServerNIC.objects.get_or_create(
            server_class=server_class,
            nic_id='nic-test',
            defaults={'module_type': nic_module_type},
        )
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='frontend',
            nic=nic,
            port_index=0,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_zone=server_zone,
            speed=200,
        )

        generator = DeviceGenerator(plan=cls.plan, site=site)
        generator.generate_all()

    @classmethod
    def managed_fabric_names(cls):
        return list(
            cls.plan.switch_classes.filter(
                fabric_class=FabricClassChoices.MANAGED,
            ).exclude(
                fabric_name='',
            ).order_by(
                'fabric_name',
            ).values_list(
                'fabric_name',
                flat=True,
            ).distinct()
        )


# ---------------------------------------------------------------------------
# Test class 1: Happy path (real exports, real hhfab if available)
# ---------------------------------------------------------------------------
class PipelineHappyPathTestCase(_PipelineBase):
    """
    Happy path tests for validate_case_128gpu_pipeline --skip-setup.

    Uses the minimal generated plan from _PipelineBase as the 'existing plan'.
    hhfab validation tests are skipped if hhfab is not available.
    """

    def _run_pipeline(self, extra_args=None):
        """Helper: run pipeline with --skip-setup in a temp dir, return (stdout, tmpdir)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            args = ['validate_case_128gpu_pipeline', '--skip-setup', '--output-dir', tmpdir]
            if extra_args:
                args.extend(extra_args)
            call_command(*args, stdout=out)
            return out.getvalue(), tmpdir

    def test_pipeline_exits_cleanly(self):
        """Pipeline command completes without raising CommandError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            call_command(
                'validate_case_128gpu_pipeline',
                '--skip-setup',
                '--output-dir', tmpdir,
                stdout=out,
            )

    def test_pipeline_writes_full_artifact(self):
        """Pipeline writes 128gpu-full.yaml to output dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command(
                'validate_case_128gpu_pipeline',
                '--skip-setup', '--output-dir', tmpdir,
                stdout=StringIO(),
            )
            full_path = os.path.join(tmpdir, '128gpu-full.yaml')
            self.assertTrue(os.path.exists(full_path), "128gpu-full.yaml must be written")
            self.assertGreater(os.path.getsize(full_path), 0)

    def test_pipeline_writes_split_artifacts(self):
        """Pipeline writes one split artifact per discovered managed fabric."""
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command(
                'validate_case_128gpu_pipeline',
                '--skip-setup', '--output-dir', tmpdir,
                stdout=StringIO(),
            )
            fabrics = self.managed_fabric_names()
            self.assertGreaterEqual(len(fabrics), 1)
            for fabric in fabrics:
                path = os.path.join(tmpdir, f'128gpu-{fabric}.yaml')
                self.assertTrue(
                    os.path.exists(path),
                    f"128gpu-{fabric}.yaml must be written by --split-by-fabric"
                )

    def test_pipeline_summary_includes_plan_id(self):
        """Summary block includes the plan_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            call_command(
                'validate_case_128gpu_pipeline',
                '--skip-setup', '--output-dir', tmpdir,
                stdout=out,
            )
        output = out.getvalue()
        self.assertIn(str(self.plan.pk), output, "Summary must include plan_id")

    def test_pipeline_summary_includes_sha256(self):
        """Summary block includes sha256 for the full artifact and each split artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            call_command(
                'validate_case_128gpu_pipeline',
                '--skip-setup', '--output-dir', tmpdir,
                stdout=out,
            )
        output = out.getvalue()
        sha256_lines = [ln for ln in output.splitlines() if 'sha256' in ln]
        self.assertGreaterEqual(
            len(sha256_lines), 1 + len(self.managed_fabric_names()),
            "Summary must include sha256 for the full artifact and all split artifacts"
        )

    def test_pipeline_summary_includes_artifact_labels(self):
        """Summary block includes [full] and one label per discovered managed fabric."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            call_command(
                'validate_case_128gpu_pipeline',
                '--skip-setup', '--output-dir', tmpdir,
                stdout=out,
            )
        output = out.getvalue()
        for label in ['[full]'] + [f'[{fabric}]' for fabric in self.managed_fabric_names()]:
            self.assertIn(label, output, f"Summary must include {label} label")

    @unittest.skipUnless(hhfab.is_hhfab_available(), "hhfab not installed")
    def test_pipeline_hhfab_pass_in_summary(self):
        """When hhfab is available, summary shows PASS for each artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            call_command(
                'validate_case_128gpu_pipeline',
                '--skip-setup', '--output-dir', tmpdir,
                stdout=out,
            )
        output = out.getvalue()
        pass_lines = [ln for ln in output.splitlines() if 'hhfab  : PASS' in ln]
        self.assertGreaterEqual(
            len(pass_lines), 1,
            "At least one artifact must show 'hhfab  : PASS' in summary"
        )

    @unittest.skipUnless(hhfab.is_hhfab_available(), "hhfab not installed")
    def test_pipeline_overall_pass_message(self):
        """When all validations pass, final PASS message is printed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            call_command(
                'validate_case_128gpu_pipeline',
                '--skip-setup', '--output-dir', tmpdir,
                stdout=out,
            )
        self.assertIn('[PASS] Pipeline complete', out.getvalue())

    def test_pipeline_plan_not_found_raises_error(self):
        """--skip-setup with no existing plan raises CommandError."""
        with patch(
            'netbox_hedgehog.management.commands.validate_case_128gpu_pipeline.TopologyPlan.objects.get',
            side_effect=TopologyPlan.DoesNotExist,
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with self.assertRaises(CommandError) as ctx:
                    call_command(
                        'validate_case_128gpu_pipeline',
                        '--skip-setup', '--output-dir', tmpdir,
                        stdout=StringIO(),
                    )
        self.assertIn("not found", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# Test class 2: hhfab unavailable path
# ---------------------------------------------------------------------------
class PipelineHHFabUnavailableTestCase(_PipelineBase):
    """
    Tests for when hhfab is not installed.

    Patches hhfab.is_hhfab_available() to return False so the command
    takes the 'skip validation' branch regardless of the local environment.
    """

    def test_hhfab_unavailable_command_completes(self):
        """Pipeline completes without CommandError when hhfab is unavailable."""
        with patch(
            'netbox_hedgehog.management.commands.validate_case_128gpu_pipeline.hhfab.is_hhfab_available',
            return_value=False,
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                out = StringIO()
                # Should not raise
                call_command(
                    'validate_case_128gpu_pipeline',
                    '--skip-setup', '--output-dir', tmpdir,
                    stdout=out,
                )

    def test_hhfab_unavailable_shows_skip_message(self):
        """When hhfab is unavailable, output mentions hhfab not found."""
        with patch(
            'netbox_hedgehog.management.commands.validate_case_128gpu_pipeline.hhfab.is_hhfab_available',
            return_value=False,
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                out = StringIO()
                call_command(
                    'validate_case_128gpu_pipeline',
                    '--skip-setup', '--output-dir', tmpdir,
                    stdout=out,
                )
        output = out.getvalue()
        self.assertIn('hhfab', output.lower())
        self.assertIn('skip', output.lower())

    def test_hhfab_unavailable_summary_shows_skipped(self):
        """Summary shows SKIPPED (not FAIL) for each artifact when hhfab is unavailable."""
        with patch(
            'netbox_hedgehog.management.commands.validate_case_128gpu_pipeline.hhfab.is_hhfab_available',
            return_value=False,
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                out = StringIO()
                call_command(
                    'validate_case_128gpu_pipeline',
                    '--skip-setup', '--output-dir', tmpdir,
                    stdout=out,
                )
        output = out.getvalue()
        skipped_lines = [ln for ln in output.splitlines() if 'SKIPPED' in ln]
        self.assertGreaterEqual(
            len(skipped_lines), 1 + len(self.managed_fabric_names()),
            "Summary must show SKIPPED for the full artifact and all split artifacts"
        )

    def test_hhfab_unavailable_artifacts_still_written(self):
        """Even when hhfab is unavailable, export artifacts are still written."""
        with patch(
            'netbox_hedgehog.management.commands.validate_case_128gpu_pipeline.hhfab.is_hhfab_available',
            return_value=False,
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                call_command(
                    'validate_case_128gpu_pipeline',
                    '--skip-setup', '--output-dir', tmpdir,
                    stdout=StringIO(),
                )
                self.assertTrue(os.path.exists(os.path.join(tmpdir, '128gpu-full.yaml')))


# ---------------------------------------------------------------------------
# Test class 3: Export failure propagation
# ---------------------------------------------------------------------------
class PipelineExportFailureTestCase(_PipelineBase):
    """
    Tests that export failures propagate immediately with actionable errors.

    Patches call_command to raise CommandError on the export step, verifying
    the pipeline command wraps and re-raises with context.
    """

    def test_full_export_failure_raises_command_error(self):
        """CommandError from export_wiring_yaml (full) propagates as 'Full export failed'."""
        original_call = __import__('django.core.management', fromlist=['call_command']).call_command

        def _patched_call(cmd, *args, **kwargs):
            if cmd == 'export_wiring_yaml' and not kwargs.get('split_by_fabric'):
                raise CommandError("Simulated export disk failure")
            return original_call(cmd, *args, **kwargs)

        with patch(
            'netbox_hedgehog.management.commands.validate_case_128gpu_pipeline.call_command',
            side_effect=_patched_call,
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with self.assertRaises(CommandError) as ctx:
                    call_command(
                        'validate_case_128gpu_pipeline',
                        '--skip-setup', '--output-dir', tmpdir,
                        stdout=StringIO(),
                    )
        self.assertIn('Full export failed', str(ctx.exception))

    def test_split_export_failure_raises_command_error(self):
        """CommandError from export_wiring_yaml (split) propagates as 'Split export failed'."""
        original_call = __import__('django.core.management', fromlist=['call_command']).call_command

        def _patched_call(cmd, *args, **kwargs):
            if cmd == 'export_wiring_yaml' and kwargs.get('split_by_fabric'):
                raise CommandError("Simulated split export failure")
            return original_call(cmd, *args, **kwargs)

        with patch(
            'netbox_hedgehog.management.commands.validate_case_128gpu_pipeline.call_command',
            side_effect=_patched_call,
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with self.assertRaises(CommandError) as ctx:
                    call_command(
                        'validate_case_128gpu_pipeline',
                        '--skip-setup', '--output-dir', tmpdir,
                        stdout=StringIO(),
                    )
        self.assertIn('Split export failed', str(ctx.exception))

    def test_hhfab_validation_failure_raises_command_error(self):
        """hhfab returning success=False raises CommandError naming the failed artifact."""
        with patch(
            'netbox_hedgehog.management.commands.validate_case_128gpu_pipeline.hhfab.is_hhfab_available',
            return_value=True,
        ), patch(
            'netbox_hedgehog.management.commands.validate_case_128gpu_pipeline.hhfab.validate_yaml',
            return_value=(False, '', 'simulated hhfab error'),
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with self.assertRaises(CommandError) as ctx:
                    call_command(
                        'validate_case_128gpu_pipeline',
                        '--skip-setup', '--output-dir', tmpdir,
                        stdout=StringIO(),
                    )
        self.assertIn('Pipeline FAILED', str(ctx.exception))
        self.assertIn('full', str(ctx.exception))  # first failed artifact named
