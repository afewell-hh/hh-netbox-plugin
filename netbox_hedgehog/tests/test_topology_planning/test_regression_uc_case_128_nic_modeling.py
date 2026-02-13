"""
Regression test for UC Case 128 GPU with NIC modeling (DIET-173).

Validates that the setup_case_128gpu_odd_ports management command works
correctly with required nic_module_type and port_index fields.

Expected behavior:
- Command runs without errors
- All PlanServerConnection objects have nic_module_type set
- Frontend connections use BlueField-3 BF3220
- Backend rail connections use ConnectX-7 (Single-Port)
- Device generation succeeds
- YAML export includes Module metadata
"""

from django.test import TestCase
from django.core.management import call_command
from io import StringIO

from dcim.models import Device, Module, Interface, ModuleType

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanServerConnection,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.services.yaml_generator import YAMLGenerator


class UCCase128NICModelingRegressionTestCase(TestCase):
    """Regression test for UC Case 128 GPU (1 test)."""

    def test_uc_case_128_with_nic_modeling(self):
        """Test that UC Case 128 command works with NIC modeling."""
        # Run management command
        out = StringIO()
        err = StringIO()
        call_command('setup_case_128gpu_odd_ports', '--clean', '--generate', stdout=out, stderr=err)

        # Verify command succeeded by checking plan exists (not output string)
        plan = TopologyPlan.objects.filter(name__icontains='128GPU').first()
        self.assertIsNotNone(plan, "UC Case 128 plan should be created by management command")

        # Verify all connections have nic_module_type
        connections = PlanServerConnection.objects.filter(
            server_class__plan=plan
        )

        self.assertGreater(connections.count(), 0, "No connections found")

        for conn in connections:
            self.assertIsNotNone(
                conn.nic_module_type,
                f"Connection {conn.connection_id} missing nic_module_type"
            )
            self.assertIsNotNone(
                conn.port_index,
                f"Connection {conn.connection_id} missing port_index"
            )

        # Verify NIC types
        fe_conns = connections.filter(connection_id='fe')
        be_conns = connections.filter(connection_id__startswith='be-rail-')

        # Frontend should use BlueField-3
        for conn in fe_conns:
            self.assertEqual(conn.nic_module_type.model, 'BlueField-3 BF3220')

        # Backend should use ConnectX-7
        for conn in be_conns:
            self.assertIn('ConnectX-7', conn.nic_module_type.model)

        # Verify device generation works
        devices = Device.objects.filter(
            tags__slug='hedgehog-generated',
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        )

        self.assertGreater(devices.count(), 0, "No devices generated")

        # Verify Modules created for servers
        server_devices = devices.filter(role__name='Server')
        for server in server_devices[:1]:  # Check first server
            modules = Module.objects.filter(device=server)
            self.assertGreater(
                modules.count(),
                0,
                f"No modules found for server {server.name}"
            )

            # Verify interfaces auto-created
            for module in modules:
                interfaces = Interface.objects.filter(device=server, module=module)
                self.assertGreater(
                    interfaces.count(),
                    0,
                    f"No interfaces for module {module.module_type.model}"
                )

        # Verify YAML export includes module metadata
        yaml_gen = YAMLGenerator(plan)
        yaml_output = yaml_gen.generate()

        self.assertIn('modules:', yaml_output)
        self.assertIn('BlueField-3 BF3220', yaml_output)
        self.assertIn('cage_type:', yaml_output)
