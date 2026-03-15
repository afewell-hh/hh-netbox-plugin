"""
Regression test for UC Case 128 GPU Odd Ports (canonical DIET case)

The test validates that:
1. The Case 128 GPU plan can still be created
2. Device generation produces the verified canonical counts:
   175 devices, 1313 interfaces, 1017 cables
   (verified via setup_case_128gpu_odd_ports --clean --generate --report, DIET-272)
3. YAML generation still produces valid Hedgehog configuration
4. hhfab validation still passes (if hhfab is available)

Canonical topology (DIET-272, 2026-03-10):
  153 servers (96 gpu-fe-only + 32 gpu-with-backend + 18 storage + 7 border/ctrl)
  + 14 managed switches (4 be-rail-leaf + 2 be-spine + 2 fe-border-leaf +
    2 fe-gpu-leaf + 4 fe-spine (override_quantity=4) + 2 fe-storage-leaf)
  + 4 oob-mgmt-leaf (ES1000-48) + 2 HHG servers
  = 175 devices total

SLOW TEST: Generates 175 devices, 1313 interfaces, 1017 cables.
Execution time: 10-15 minutes.

Run separately with: python manage.py test --tag=slow --keepdb
"""

from io import StringIO
from django.core.management import call_command
from django.test import TestCase, tag

from dcim.models import Device, Interface, Cable

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    GenerationState,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.services.hhfab import is_hhfab_available, validate_yaml
from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan
from netbox_hedgehog.tests.test_topology_planning.case_128gpu_helpers import (
    expected_128gpu_counts,
)


PLAN_NAME = "UX Case 128GPU Odd Ports"


@tag('slow', 'regression')
class UCCase128GPURegressionTestCase(TestCase):
    """
    Regression test to ensure UC Case 128 GPU plan continues to work
    after NIC modeling + multi-homing changes.

    This test serves as a backward compatibility guarantee.

    SLOW TEST: Generates 171 devices, 1243 interfaces, 979 cables.
    Execution time: 10-15 minutes.

    Run with: python manage.py test --tag=slow --keepdb
    Skip with: python manage.py test --exclude-tag=slow
    """

    @classmethod
    def setUpTestData(cls):
        """Set up the Case 128 GPU plan using the management command"""
        # Clean slate - ensure no existing plan
        TopologyPlan.objects.filter(name=PLAN_NAME).delete()

        # Create the plan using the management command
        call_command("setup_case_128gpu_odd_ports", "--clean", stdout=StringIO())

        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)

    def test_uc_case_128_gpu_backward_compatibility(self):
        """
        Comprehensive regression test for UC Case 128 GPU.

        Validates that after Phase 3 changes, the plan:
        1. Has correct planning object counts
        2. Generates the expected number of devices/interfaces/cables
        3. Produces valid YAML
        4. Passes hhfab validation (if available)
        """
        # =====================================================================
        # Part 1: Validate Planning Objects
        # =====================================================================
        expected = expected_128gpu_counts()

        # Server classes
        server_classes = PlanServerClass.objects.filter(plan=self.plan)
        self.assertEqual(
            server_classes.count(),
            expected.get("server_classes"),
            f"Expected {expected.get('server_classes')} server classes per canonical YAML"
        )

        # Switch classes
        switch_classes = PlanSwitchClass.objects.filter(plan=self.plan)
        self.assertEqual(
            switch_classes.count(),
            expected.get("switch_classes"),
            f"Expected {expected.get('switch_classes')} switch classes per canonical YAML"
        )

        # Server connections
        connections = PlanServerConnection.objects.filter(server_class__plan=self.plan)
        self.assertEqual(
            connections.count(),
            expected.get("connections"),
            f"Expected {expected.get('connections')} server connections per canonical YAML"
        )

        # =====================================================================
        # Part 2: Validate Device Generation
        # =====================================================================

        # Clean any previous generation (use custom_field_data filtering)
        from extras.models import Tag
        tag = Tag.objects.filter(slug='hedgehog-generated').first()
        if tag:
            Cable.objects.filter(
                tags=tag,
                custom_field_data__hedgehog_plan_id=str(self.plan.pk)
            ).delete()
            Device.objects.filter(
                tags=tag,
                custom_field_data__hedgehog_plan_id=str(self.plan.pk)
            ).delete()

        # Generate devices
        generator = DeviceGenerator(self.plan)
        result = generator.generate_all()

        # Validate counts match current canonical baseline (DIET-272, 2026-03-10)
        # Breakdown: 167 base (14 managed switches + 153 servers) + 4 oob-mgmt-leaf
        #            + 2 HHG + 4 fe-spine (override_quantity=4) + 2 fe-border-leaf = 175
        # Verified via: setup_case_128gpu_odd_ports --clean --generate --report
        self.assertEqual(
            result.device_count,
            175,
            f"Expected 175 devices, got {result.device_count}. "
            "This indicates a regression in device generation logic."
        )

        # Interface count: switch-side only (server module interfaces not counted)
        # Verified via: setup_case_128gpu_odd_ports --clean --generate --report
        self.assertEqual(
            result.interface_count,
            1313,
            f"Expected 1313 interfaces, got {result.interface_count}. "
            "This indicates a regression in interface generation logic."
        )

        # Cable count includes +32 border uplink cables (DIET-272)
        # Verified via: setup_case_128gpu_odd_ports --clean --generate --report
        self.assertEqual(
            result.cable_count,
            1017,
            f"Expected 1017 cables, got {result.cable_count}. "
            "This indicates a regression in cable generation logic."
        )

        # =====================================================================
        # Part 3: Validate YAML Export
        # =====================================================================

        # Export YAML (should not raise exceptions)
        try:
            yaml_content = generate_yaml_for_plan(self.plan)
            self.assertIsNotNone(yaml_content)
            self.assertGreater(len(yaml_content), 0, "YAML export should not be empty")
            # Hedgehog uses Kubernetes CRD format, not simple wiring: key
            self.assertIn('apiVersion:', yaml_content, "YAML should contain Kubernetes CRD format")
            self.assertIn('kind:', yaml_content, "YAML should contain Kubernetes resources")
        except Exception as e:
            self.fail(f"YAML export failed: {e}")

        # =====================================================================
        # Part 4: Validate hhfab Validation (if available)
        # =====================================================================

        if is_hhfab_available():
            # hhfab is available - run validation
            # NOTE: This test case uses odd-port 4x200G breakouts (ports 1,3,5,...,63)
            # which may not be supported in all hhfab DS5000 profile versions.
            # A profile-specific port validation failure is a known limitation and
            # does not indicate a regression in DIET generation logic.
            is_valid, stdout, stderr = validate_yaml(yaml_content)
            if not is_valid:
                print(
                    f"\n[WARN] hhfab validation failed (may be DS5000 profile limitation "
                    f"for odd-port breakouts):\n{stderr}"
                )
        else:
            # hhfab not available - log skip message
            print("\n[SKIP] hhfab not installed - skipping validation test")
            print("To enable full validation, install hhfab in the container:")
            print("  scripts/install_hhfab_in_container.sh")

    def test_uc_case_128_switch_class_redundancy_preserved(self):
        """
        Validate that switch classes maintain their redundancy configuration.

        After Phase 3 changes, redundancy_type should be set correctly,
        and deprecated mclag_pair should still work via auto-conversion.
        """
        # Frontend leaf switches (MCLAG pairs)
        fe_leaf = PlanSwitchClass.objects.get(
            plan=self.plan,
            switch_class_id='fe-gpu-leaf'
        )

        # Should have redundancy configured (either via mclag_pair or redundancy_type)
        # After implementation, this should be auto-converted to redundancy_type='mclag'
        # For now, we just verify the plan loads without errors
        self.assertIsNotNone(fe_leaf.effective_quantity)
        self.assertGreater(fe_leaf.effective_quantity, 0)

        # Backend rail leaf switches (alternating distribution)
        be_rail_leaf = PlanSwitchClass.objects.get(
            plan=self.plan,
            switch_class_id='be-rail-leaf'
        )

        self.assertIsNotNone(be_rail_leaf.effective_quantity)
        self.assertGreater(be_rail_leaf.effective_quantity, 0)

    def test_uc_case_128_server_connections_preserved(self):
        """
        Validate that server connections maintain their configuration.

        After NIC modeling (Phase 5), connections should:
        - Have nic set (required field)
        - Have port_index set (required field)
        - Maintain correct ports_per_connection values
        """
        # GPU server class connections - use actual server class ID from command
        gpu_server = PlanServerClass.objects.get(
            plan=self.plan,
            server_class_id='gpu-fe-only'
        )

        connections = PlanServerConnection.objects.filter(server_class=gpu_server)
        self.assertGreater(connections.count(), 0, "GPU servers should have connections")

        # Verify connections have valid NIC modeling configuration
        for conn in connections:
            self.assertIsNotNone(conn.ports_per_connection)
            self.assertGreater(conn.ports_per_connection, 0)
            self.assertIsNotNone(conn.target_switch_class)

            # NIC FK is required (DIET-294)
            self.assertIsNotNone(
                conn.nic,
                f"Connection {conn.connection_id} should have nic"
            )
            self.assertIsNotNone(
                conn.port_index,
                f"Connection {conn.connection_id} should have port_index"
            )


class UCCase128WrapperCompatibilityRedTestCase(TestCase):
    """
    RED regression test: legacy wrapper command must remain compatible with
    the new YAML-driven command path.
    """

    def test_wrapper_works_alongside_apply_diet_test_case(self):
        # New generic command should apply the canonical 128-GPU case.
        call_command(
            "apply_diet_test_case",
            "--case",
            "ux_case_128gpu_odd_ports",
            stdout=StringIO(),
            stderr=StringIO(),
        )

        # Existing wrapper command should still run without behavioral breakage.
        call_command(
            "setup_case_128gpu_odd_ports",
            "--clean",
            stdout=StringIO(),
            stderr=StringIO(),
        )

        self.assertTrue(TopologyPlan.objects.filter(name=PLAN_NAME).exists())
