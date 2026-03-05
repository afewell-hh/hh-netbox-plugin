"""
Integration tests for export completeness contracts and hhfab validation gate (DIET-228).

Two test classes:

  ExportCompletenessRegressionTestCase
    - Does NOT require hhfab.
    - Enforces structural completeness of every export: required CRD kinds present,
      minimum counts met, YAML parses as a complete document stream.
    - Acts as a regression guard: a truncated/partial artifact is caught immediately.

  ExportHHFabValidationGateTestCase
    - Requires hhfab (@unittest.skipUnless).
    - Runs the full export -> hhfab validate pipeline.
    - Asserts success=True; prints diagnostics on failure.
    - Also verifies the validate_wiring_yaml management command pipeline.

## Invariants
- Unchanged: topology generation semantics, yaml_generator output.
- Changed: completeness contract enforcement and hhfab validation gate.

## Reproducing CI validation locally

    # 1. Run completeness regression tests (fast, no hhfab required)
    cd /home/ubuntu/afewell-hh/netbox-docker
    docker compose exec netbox python manage.py test \\
        netbox_hedgehog.tests.test_topology_planning.test_export_hhfab_gate.ExportCompletenessRegressionTestCase \\
        --keepdb --verbosity=2

    # 2. Run hhfab gate tests (requires hhfab in container)
    docker compose exec netbox python manage.py test \\
        netbox_hedgehog.tests.test_topology_planning.test_export_hhfab_gate.ExportHHFabValidationGateTestCase \\
        --keepdb --verbosity=2

    # 3. Run both together
    docker compose exec netbox python manage.py test \\
        netbox_hedgehog.tests.test_topology_planning.test_export_hhfab_gate \\
        --keepdb --verbosity=2

    # 4. Run export + validate pipeline manually for the 128GPU case
    docker compose exec netbox python manage.py export_wiring_yaml <plan_id> --output /tmp/wiring.yaml
    docker compose exec netbox python manage.py validate_wiring_yaml <plan_id>
"""

import os
import tempfile
import unittest
from io import StringIO

import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from dcim.models import Device, DeviceRole, DeviceType, InterfaceTemplate, Manufacturer, Site

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricTypeChoices,
    GenerationStatusChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    ServerClassCategoryChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    GenerationState,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services import hhfab
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan


# ---------------------------------------------------------------------------
# Required CRD kinds for a complete wiring artifact
# ---------------------------------------------------------------------------
REQUIRED_CRD_KINDS = {'VLANNamespace', 'IPv4Namespace', 'Switch', 'Server', 'Connection'}


def _count_kinds(yaml_content):
    """Return {kind: count} for all non-null CRD documents."""
    kinds = {}
    for doc in yaml.safe_load_all(yaml_content):
        if isinstance(doc, dict) and 'kind' in doc:
            k = doc['kind']
            kinds[k] = kinds.get(k, 0) + 1
    return kinds


def _is_complete_yaml_stream(yaml_content):
    """Return True if yaml_content parses as a valid, non-empty document stream."""
    try:
        docs = [d for d in yaml.safe_load_all(yaml_content) if d is not None]
        return len(docs) > 0
    except yaml.YAMLError:
        return False


# ---------------------------------------------------------------------------
# Shared fixture: minimal plan with 1 frontend leaf + 1 server (fe) only.
# Keeps test setup fast while still exercising the full export+validate path.
# ---------------------------------------------------------------------------
class _HHFabGateBase(TestCase):
    """
    Shared fixture for DIET-228 gate tests.

    Creates:
      - 1 frontend server-leaf switch (quantity=1)
      - 1 frontend server class (quantity=1)
      - 1 server->switch connection (unbundled, 2 ports/connection)
      - DeviceGenerator.generate_all() -> sets GenerationState to GENERATED
    """

    @classmethod
    def setUpTestData(cls):
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica-HHFabGate',
            defaults={'slug': 'celestica-hhfab-gate'}
        )
        nvidia, _ = Manufacturer.objects.get_or_create(
            name='NVIDIA-HHFabGate',
            defaults={'slug': 'nvidia-hhfab-gate'}
        )

        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='GPU-Server-HHFabGate',
            defaults={'slug': 'gpu-server-hhfab-gate'}
        )
        for tpl_name in ('g0', 'g1'):
            InterfaceTemplate.objects.get_or_create(
                device_type=cls.server_type,
                name=tpl_name,
                defaults={'type': '200gbase-x-qsfp56'}
            )

        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='DS5000-HHFabGate',
            defaults={'slug': 'ds5000-hhfab-gate'}
        )
        cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'native_speed': 800,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g'],
                'uplink_ports': 0,
                'hedgehog_profile_name': 'celestica-ds5000',
            }
        )

        # Use canonical breakout IDs (no suffix) so yaml_generator produces
        # '4x200G' / '1x800G' - the exact strings hhfab accepts for DS5000.
        cls.breakout_4x200, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={
                'from_speed': 800, 'logical_ports': 4,
                'logical_speed': 200, 'optic_type': 'QSFP-DD',
            }
        )
        cls.breakout_1x800, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x800g',
            defaults={
                'from_speed': 800, 'logical_ports': 1,
                'logical_speed': 800, 'optic_type': 'QSFP-DD',
            }
        )

        cls.server_role, _ = DeviceRole.objects.get_or_create(
            name='Server-HHFabGate', defaults={'slug': 'server', 'color': 'aa1409'}
        )
        cls.site, _ = Site.objects.get_or_create(
            name='HHFabGate-Site', defaults={'slug': 'hhfab-gate-site'}
        )

        from dcim.models import ModuleType
        cls.nic_module_type, created = ModuleType.objects.get_or_create(
            manufacturer=nvidia,
            model='BlueField-3-HHFabGate',
        )
        if created:
            for n in ('p0', 'p1'):
                InterfaceTemplate.objects.create(
                    module_type=cls.nic_module_type, name=n, type='other'
                )

        cls.plan = TopologyPlan.objects.create(
            name='HHFabGate Export Test Plan',
            customer_name='HHFabGate Test',
        )

        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='hg-fe-gpu',
            server_device_type=cls.server_type,
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            gpus_per_server=8,
        )
        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='hg-fe-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=0,
            mclag_pair=False,
            calculated_quantity=1,
            override_quantity=1,
        )
        server_zone = SwitchPortZone.objects.create(
            switch_class=cls.switch_class,
            zone_name='server',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=cls.breakout_4x200,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )
        SwitchPortZone.objects.create(
            switch_class=cls.switch_class,
            zone_name='uplink',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='49-50',
            breakout_option=cls.breakout_1x800,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=200,
        )
        PlanServerConnection.objects.create(
            server_class=cls.server_class,
            connection_id='frontend',
            nic_module_type=cls.nic_module_type,
            port_index=0,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_zone=server_zone,
            speed=200,
        )

        generator = DeviceGenerator(plan=cls.plan, site=cls.site)
        generator.generate_all()


# ---------------------------------------------------------------------------
# Test class 1: Completeness contracts (no hhfab required)
# ---------------------------------------------------------------------------
class ExportCompletenessRegressionTestCase(_HHFabGateBase):
    """
    Completeness contract tests for the wiring export.

    These tests run without hhfab and guard against:
    - Missing required CRD kinds (Switch, Server, Connection, namespaces)
    - Truncated/partial YAML streams
    - Minimum per-kind counts not met
    - Checksum changes across identical exports (reproducibility)

    A failure here means the export artifact is structurally incomplete.
    CI should fail immediately on any regression.
    """

    def test_export_yaml_is_complete_stream(self):
        """generate_yaml_for_plan() returns a parseable, non-empty YAML stream."""
        content = generate_yaml_for_plan(self.plan)
        self.assertTrue(
            _is_complete_yaml_stream(content),
            "Export must produce a parseable, non-empty YAML document stream."
        )

    def test_export_contains_all_required_crd_kinds(self):
        """Export includes all required CRD kinds: Switch, Server, Connection, namespaces."""
        kinds = set(_count_kinds(generate_yaml_for_plan(self.plan)).keys())
        missing = REQUIRED_CRD_KINDS - kinds
        self.assertEqual(
            missing, set(),
            f"Export is missing required CRD kinds: {missing}. Present: {kinds}"
        )

    def test_export_switch_count_matches_generated_devices(self):
        """Switch CRD count equals the number of generated switch devices in the plan."""
        switch_devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric='frontend',
        ).count()
        kinds = _count_kinds(generate_yaml_for_plan(self.plan))
        self.assertEqual(
            kinds.get('Switch', 0),
            switch_devices,
            f"Switch CRD count ({kinds.get('Switch', 0)}) must equal "
            f"generated switch device count ({switch_devices})."
        )

    def test_export_server_count_matches_generated_devices(self):
        """Server CRD count equals the number of generated server devices in the plan."""
        from dcim.models import DeviceRole as DR
        server_role = DR.objects.filter(slug='server').first()
        server_devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            role=server_role,
        ).count() if server_role else 0
        kinds = _count_kinds(generate_yaml_for_plan(self.plan))
        self.assertGreaterEqual(
            kinds.get('Server', 0), 1,
            "Export must include at least 1 Server CRD."
        )
        self.assertEqual(
            kinds.get('Server', 0),
            server_devices,
            f"Server CRD count ({kinds.get('Server', 0)}) must equal "
            f"generated server device count ({server_devices})."
        )

    def test_export_has_at_least_one_connection(self):
        """Export includes at least one Connection CRD for a plan with server connections."""
        kinds = _count_kinds(generate_yaml_for_plan(self.plan))
        self.assertGreaterEqual(
            kinds.get('Connection', 0), 1,
            "Export for a plan with server connections must include at least 1 Connection CRD."
        )

    def test_truncated_yaml_detected_as_incomplete(self):
        """A truncated YAML string is correctly identified as an incomplete stream."""
        content = generate_yaml_for_plan(self.plan)
        truncated = content[:len(content) // 2]  # cut at midpoint

        # Truncation either produces a YAML parse error or fewer documents
        try:
            full_kinds = _count_kinds(content)
            trunc_kinds = _count_kinds(truncated)
            total_full = sum(full_kinds.values())
            total_trunc = sum(trunc_kinds.values())
            self.assertLess(
                total_trunc, total_full,
                "A midpoint-truncated YAML stream must contain fewer documents than the full export."
            )
        except yaml.YAMLError:
            pass  # Parse error on truncated YAML is also acceptable evidence of truncation

    def test_export_command_produces_complete_artifact(self):
        """export_wiring_yaml management command writes a complete YAML artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'wiring.yaml')
            out = StringIO()
            call_command(
                'export_wiring_yaml',
                str(self.plan.pk),
                '--output', output_path,
                stdout=out,
            )
            self.assertTrue(os.path.exists(output_path))
            self.assertGreater(os.path.getsize(output_path), 0)

            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()

        kinds = set(_count_kinds(content).keys())
        missing = REQUIRED_CRD_KINDS - kinds
        self.assertEqual(
            missing, set(),
            f"export_wiring_yaml command artifact is missing required CRD kinds: {missing}"
        )

    def test_export_command_metadata_includes_document_count(self):
        """export_wiring_yaml stdout reports a non-zero document count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'wiring.yaml')
            out = StringIO()
            call_command(
                'export_wiring_yaml',
                str(self.plan.pk),
                '--output', output_path,
                stdout=out,
            )

        stdout = out.getvalue()
        doc_line = next((ln for ln in stdout.splitlines() if 'documents:' in ln), None)
        self.assertIsNotNone(doc_line, "export_wiring_yaml stdout must include a 'documents:' line")
        doc_count_str = doc_line.split('documents:')[-1].strip()
        doc_count = int(doc_count_str)
        self.assertGreaterEqual(
            doc_count,
            len(REQUIRED_CRD_KINDS),
            f"Reported document count ({doc_count}) must be at least {len(REQUIRED_CRD_KINDS)} "
            f"(one per required CRD kind)."
        )

    def test_export_reproducible_kind_counts(self):
        """Two exports of an unchanged plan produce identical CRD kind counts."""
        kinds1 = _count_kinds(generate_yaml_for_plan(self.plan))
        kinds2 = _count_kinds(generate_yaml_for_plan(self.plan))
        self.assertEqual(
            kinds1, kinds2,
            "Repeated exports of the same plan must produce identical CRD kind counts."
        )


# ---------------------------------------------------------------------------
# Test class 2: hhfab validation gate (requires hhfab in PATH)
# ---------------------------------------------------------------------------
@unittest.skipUnless(hhfab.is_hhfab_available(), "hhfab not installed - skipping validation gate tests")
class ExportHHFabValidationGateTestCase(_HHFabGateBase):
    """
    End-to-end export -> hhfab validate pipeline tests.

    These tests are skipped when hhfab is not installed.  In CI, hhfab must be
    installed in the NetBox container image (see Dockerfile-Plugins in
    ci-diet-tests.yml).  A skip in CI is treated as a failure for this gate.

    If a test fails with a validation error, hhfab stdout/stderr is printed
    in the assertion message to aid diagnosis.
    """

    def _assert_hhfab_success(self, success, stdout, stderr, context=''):
        """Assert hhfab returned success; include output in failure message."""
        if not success:
            diag = f"\nhhfab stdout:\n{stdout}\nhhfab stderr:\n{stderr}"
            self.fail(
                f"hhfab validate failed{(' for ' + context) if context else ''}.{diag}"
            )

    def test_generated_yaml_passes_hhfab_validate(self):
        """generate_yaml_for_plan() output passes hhfab validate."""
        yaml_content = generate_yaml_for_plan(self.plan)
        success, stdout, stderr = hhfab.validate_yaml(yaml_content)
        self._assert_hhfab_success(success, stdout, stderr, 'full plan export')

    def test_validate_plan_yaml_helper_returns_success(self):
        """hhfab.validate_plan_yaml() convenience wrapper returns success=True."""
        # validate_plan_yaml only exists if GenerationState is GENERATED; it relies
        # on generate_yaml_for_plan internally so setUpTestData already ensures that.
        success, yaml_content, stdout, stderr = hhfab.validate_plan_yaml(self.plan)
        self._assert_hhfab_success(success, stdout, stderr, 'validate_plan_yaml helper')
        self.assertGreater(len(yaml_content), 0, "validate_plan_yaml must return non-empty YAML")

    def test_export_command_then_validate_command_pipeline(self):
        """export_wiring_yaml + validate_wiring_yaml command pipeline both succeed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'wiring.yaml')

            # Step 1: export
            export_out = StringIO()
            call_command(
                'export_wiring_yaml',
                str(self.plan.pk),
                '--output', output_path,
                stdout=export_out,
            )
            self.assertTrue(os.path.exists(output_path), "Export file must be written")

            # Step 2: validate using the exported file content via validate_yaml helper
            with open(output_path, 'r', encoding='utf-8') as f:
                yaml_content = f.read()

        success, stdout, stderr = hhfab.validate_yaml(yaml_content)
        self._assert_hhfab_success(
            success, stdout, stderr,
            'export_wiring_yaml artifact'
        )

    def test_validate_wiring_yaml_command_succeeds(self):
        """validate_wiring_yaml management command exits successfully."""
        out = StringIO()
        # This command generates YAML from the plan and runs hhfab validate.
        # It must not raise CommandError for a valid generated plan.
        try:
            call_command(
                'validate_wiring_yaml',
                str(self.plan.pk),
                stdout=out,
            )
        except CommandError as e:
            self.fail(f"validate_wiring_yaml raised CommandError: {e}\nOutput:\n{out.getvalue()}")

        output = out.getvalue()
        # The command should emit some validation-related output
        self.assertGreater(len(output), 0, "validate_wiring_yaml must produce output")

    def test_invalid_yaml_fails_hhfab_validate(self):
        """hhfab validate correctly rejects structurally invalid YAML content."""
        bad_yaml = "---\napiVersion: wiring.githedgehog.com/v1beta1\nkind: INVALID_KIND\nmetadata:\n  name: bad\n"
        success, stdout, stderr = hhfab.validate_yaml(bad_yaml)
        self.assertFalse(
            success,
            "hhfab validate must return success=False for a document with an invalid kind."
        )
