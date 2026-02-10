"""
Regression test for UC Case 128 GPU Odd Ports (DIET-165 Phase 4)

This test ensures backward compatibility after implementing the Phase 3 spec
changes for NIC modeling + multi-homing (issue #164).

The test validates that:
1. The Case 128 GPU plan can still be created
2. Device generation still produces the same counts (164 devices, 1096 interfaces, 548 cables)
3. YAML generation still produces valid Hedgehog configuration
4. hhfab validation still passes (if hhfab is available)

This is the 1 regression test specified in the Phase 3 spec addendum.
"""

from io import StringIO
from django.core.management import call_command
from django.test import TestCase

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


PLAN_NAME = "UX Case 128GPU Odd Ports"


class UCCase128GPURegressionTestCase(TestCase):
    """
    Regression test to ensure UC Case 128 GPU plan continues to work
    after NIC modeling + multi-homing changes.

    This test serves as a backward compatibility guarantee.
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

        # Server classes
        server_classes = PlanServerClass.objects.filter(plan=self.plan)
        self.assertEqual(
            server_classes.count(),
            4,
            "Expected 4 server classes (GPU, INF, OOB, Storage)"
        )

        # Switch classes
        switch_classes = PlanSwitchClass.objects.filter(plan=self.plan)
        self.assertEqual(
            switch_classes.count(),
            6,
            "Expected 6 switch classes (FE/BE leaf/spine, OOB leaf/spine)"
        )

        # Server connections
        connections = PlanServerConnection.objects.filter(server_class__plan=self.plan)
        self.assertEqual(
            connections.count(),
            12,
            "Expected 12 server connections (3 per server class)"
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

        # Validate counts match expected baseline
        self.assertEqual(
            result.device_count,
            164,
            f"Expected 164 devices, got {result.device_count}. "
            "This indicates a regression in device generation logic."
        )

        self.assertEqual(
            result.interface_count,
            1096,
            f"Expected 1096 interfaces, got {result.interface_count}. "
            "This indicates a regression in interface generation logic."
        )

        self.assertEqual(
            result.cable_count,
            548,
            f"Expected 548 cables, got {result.cable_count}. "
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
            self.assertIn('wiring:', yaml_content, "YAML should contain 'wiring:' key")
        except Exception as e:
            self.fail(f"YAML export failed: {e}")

        # =====================================================================
        # Part 4: Validate hhfab Validation (if available)
        # =====================================================================

        if is_hhfab_available():
            # hhfab is available - run full validation
            try:
                is_valid, stdout, stderr = validate_yaml(yaml_content)
                self.assertTrue(
                    is_valid,
                    f"hhfab validation failed. Output:\n{stdout}\n{stderr}\n\n"
                    "This indicates generated YAML is not valid for Hedgehog."
                )
            except Exception as e:
                self.fail(f"hhfab validation raised exception: {e}")
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

        After Phase 3 changes, connections should:
        - Still reference correct interface templates (if used)
        - Still support legacy nic_slot mode (if used)
        - Maintain correct ports_per_connection values
        """
        # GPU server class connections
        gpu_server = PlanServerClass.objects.get(
            plan=self.plan,
            server_class_id='GPU-B200'
        )

        connections = PlanServerConnection.objects.filter(server_class=gpu_server)
        self.assertGreater(connections.count(), 0, "GPU servers should have connections")

        # Verify connections have valid configuration
        for conn in connections:
            self.assertIsNotNone(conn.ports_per_connection)
            self.assertGreater(conn.ports_per_connection, 0)
            self.assertIsNotNone(conn.switch_class)

            # Either server_interface_template or nic_slot should be set
            # (depends on how the plan is configured)
            has_template = conn.server_interface_template is not None
            has_nic_slot = bool(conn.nic_slot)
            self.assertTrue(
                has_template or has_nic_slot,
                f"Connection {conn.connection_id} should have either "
                "server_interface_template or nic_slot configured"
            )
