"""
Integration tests for setup_case_128gpu_odd_ports management command.
"""

import yaml

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from users.models import ObjectPermission

from netbox_hedgehog.forms.topology_planning import PlanServerConnectionForm
from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    GenerationState,
)
from netbox_hedgehog.choices import (
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    GenerationStatusChoices,
)
from netbox_hedgehog.services.device_generator import GenerationResult


PLAN_NAME = "UX Case 128GPU Odd Ports"


class Case128GpuCommandTestCase(TestCase):
    """Validate the management command and related UX views."""

    @classmethod
    def setUpTestData(cls):
        call_command("setup_case_128gpu_odd_ports", stdout=StringIO())
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)

        User = get_user_model()
        cls.superuser = User.objects.create_user(
            username="case-admin",
            password="case-admin",
            is_staff=True,
            is_superuser=True,
        )

    def test_command_is_idempotent(self):
        call_command("setup_case_128gpu_odd_ports", stdout=StringIO())
        self.assertEqual(
            TopologyPlan.objects.filter(name=PLAN_NAME).count(),
            1,
            "Command should be idempotent for the case plan",
        )

    def test_plan_counts_match_expected(self):
        server_count = PlanServerClass.objects.filter(plan=self.plan).count()
        switch_count = PlanSwitchClass.objects.filter(plan=self.plan).count()
        connection_count = PlanServerConnection.objects.filter(
            server_class__plan=self.plan
        ).count()

        self.assertEqual(server_count, 4)
        self.assertEqual(switch_count, 6)
        self.assertEqual(connection_count, 12)

    def test_generate_preview_page_loads(self):
        self.client.force_login(self.superuser)
        url = reverse("plugins:netbox_hedgehog:topologyplan_generate", args=[self.plan.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Devices")
        self.assertContains(response, "Servers")
        self.assertContains(response, "Switches")

    def test_generate_post_creates_objects(self):
        self.client.force_login(self.superuser)
        url = reverse("plugins:netbox_hedgehog:topologyplan_generate", args=[self.plan.pk])

        def fake_generate(self):
            GenerationState.objects.filter(plan=self.plan).delete()
            GenerationState.objects.create(
                plan=self.plan,
                device_count=164,
                interface_count=1096,
                cable_count=548,
                snapshot={},
                status=GenerationStatusChoices.GENERATED,
            )
            return GenerationResult(164, 1096, 548)

        with patch(
            "netbox_hedgehog.views.topology_planning.DeviceGenerator.generate_all",
            new=fake_generate,
        ):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        state = GenerationState.objects.filter(plan=self.plan).first()
        self.assertIsNotNone(state, "GenerationState should be created after POST")
        self.assertEqual(state.device_count, 164)
        self.assertEqual(state.interface_count, 1096)
        self.assertEqual(state.cable_count, 548)

    def test_generate_requires_change_permission(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="case-viewer",
            password="case-viewer",
            is_staff=True,
            is_superuser=False,
        )

        view_perm = ObjectPermission.objects.create(
            name="case-view-only",
            actions=["view"],
        )
        view_perm.object_types.add(ContentType.objects.get_for_model(TopologyPlan))
        view_perm.users.add(user)

        self.client.force_login(user)
        url = reverse("plugins:netbox_hedgehog:topologyplan_generate", args=[self.plan.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_create_case_data_delegates_to_apply_case_id(self):
        """_create_case_data() must delegate to apply_case_id, not inline construction."""
        from unittest.mock import patch, MagicMock
        from netbox_hedgehog.management.commands.setup_case_128gpu_odd_ports import Command

        cmd = Command()
        mock_plan = MagicMock()

        with patch(
            "netbox_hedgehog.test_cases.runner.apply_case_id",
            return_value=mock_plan,
        ) as mock_apply:
            result = cmd._create_case_data()

        mock_apply.assert_called_once_with(
            "ux_case_128gpu_odd_ports",
            clean=False,
            prune=True,
            reference_mode="ensure",
        )
        self.assertEqual(result, mock_plan)

    def test_rail_requires_value_for_rail_optimized(self):
        connection = PlanServerConnection.objects.filter(server_class__plan=self.plan).first()
        form = PlanServerConnectionForm(
            data={
                "server_class": connection.server_class.pk,
                "connection_id": "rail-missing",
                "ports_per_connection": 1,
                "hedgehog_conn_type": ConnectionTypeChoices.UNBUNDLED,
                "distribution": ConnectionDistributionChoices.RAIL_OPTIMIZED,
                "target_zone": connection.target_zone.pk,
                "speed": 400,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("rail", form.errors)


class Case128GpuRailDistributionTestCase(TestCase):
    """Validate rail-optimized backend allocation distributes correctly across switches."""

    @classmethod
    def setUpTestData(cls):
        from dcim.models import Cable

        call_command(
            "setup_case_128gpu_odd_ports",
            "--clean",
            "--generate",
            stdout=StringIO(),
        )
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)
        cls.cables = Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(cls.plan.pk)
        )

    def test_backend_rails_distributed_across_switches(self):
        """Test that backend rails are distributed across switches, not servers."""
        from dcim.models import Device

        # Get backend rail leaf switches
        be_rail_switches = Device.objects.filter(
            name__startswith='be-rail-leaf-',
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        ).order_by('name')

        self.assertEqual(be_rail_switches.count(), 4, "Should have 4 be-rail-leaf switches")

        # Filter backend cables by checking terminations in Python
        # (Cable model uses generic 'terminations' field, not a_terminations/b_terminations for queries)
        backend_cables = []
        for cable in self.cables:
            a_terms = cable.a_terminations if isinstance(cable.a_terminations, list) else list(cable.a_terminations.all())
            b_terms = cable.b_terminations if isinstance(cable.b_terminations, list) else list(cable.b_terminations.all())

            if len(a_terms) > 0 and len(b_terms) > 0:
                a_device = a_terms[0].device
                b_device = b_terms[0].device

                if a_device.name.startswith('gpu-with-backend-') and b_device.name.startswith('be-rail-leaf-'):
                    backend_cables.append(cable)

        self.assertEqual(len(backend_cables), 256, "Should have 256 backend connections")

        # For each server, verify rails are distributed across different switches
        for server_num in range(1, 33):  # 32 servers
            server_name = f'gpu-with-backend-{server_num:03d}'

            # Get cables for this server
            server_cables = []
            for cable in backend_cables:
                a_terms = cable.a_terminations if isinstance(cable.a_terminations, list) else list(cable.a_terminations.all())
                if len(a_terms) > 0 and a_terms[0].device.name == server_name:
                    server_cables.append(cable)

            # Get the switches this server connects to
            connected_switches = set()
            for cable in server_cables:
                b_terms = cable.b_terminations if isinstance(cable.b_terminations, list) else list(cable.b_terminations.all())
                switch_name = b_terms[0].device.name
                connected_switches.add(switch_name)

            # Each server should connect to multiple switches (not all to one)
            self.assertGreater(
                len(connected_switches), 1,
                f"{server_name} backend NICs should connect to multiple switches, "
                f"but all connect to: {connected_switches}"
            )

    def test_rail_grouping_across_all_servers(self):
        """Test that all servers' rail N connects to the same switch(es)."""
        import math
        import re
        from dcim.models import Device

        be_rail_switches = list(
            Device.objects.filter(
                name__startswith='be-rail-leaf-',
                custom_field_data__hedgehog_plan_id=str(self.plan.pk)
            ).order_by('name')
        )

        # Filter backend cables by checking terminations in Python
        backend_cables = []
        for cable in self.cables:
            a_terms = cable.a_terminations if isinstance(cable.a_terminations, list) else list(cable.a_terminations.all())
            b_terms = cable.b_terminations if isinstance(cable.b_terminations, list) else list(cable.b_terminations.all())

            if len(a_terms) > 0 and len(b_terms) > 0:
                a_device = a_terms[0].device
                b_device = b_terms[0].device

                if a_device.name.startswith('gpu-with-backend-') and b_device.name.startswith('be-rail-leaf-'):
                    backend_cables.append(cable)

        # Group cables by server interface name (which corresponds to rail position)
        # We expect 8 different interface names (one per rail position)
        rail_to_switches = {}  # rail_position -> set of switch names

        for cable in backend_cables:
            a_terms = cable.a_terminations if isinstance(cable.a_terminations, list) else list(cable.a_terminations.all())
            b_terms = cable.b_terminations if isinstance(cable.b_terminations, list) else list(cable.b_terminations.all())

            server_interface = a_terms[0]
            switch_interface = b_terms[0]

            # Use interface name as rail identifier
            # (In 128-GPU case, server interfaces should be named consistently)
            interface_name = server_interface.name
            switch_name = switch_interface.device.name

            if interface_name not in rail_to_switches:
                rail_to_switches[interface_name] = set()
            rail_to_switches[interface_name].add(switch_name)

        # We should have 8 distinct interface names (8 rails)
        self.assertEqual(
            len(rail_to_switches), 8,
            f"Should have 8 distinct rail positions, found {len(rail_to_switches)}"
        )

        # Each rail should connect to exactly 1 switch (8 rails / 4 switches = 2 rails per switch)
        # So we expect each rail to consistently use one switch across all servers
        rails_per_switch = math.ceil(len(rail_to_switches) / len(be_rail_switches))
        for interface_name, switches in rail_to_switches.items():
            match = re.search(r'be-rail-(\d+)', interface_name)
            self.assertIsNotNone(
                match,
                f"Expected backend rail interface name to include rail number: {interface_name}"
            )
            rail = int(match.group(1))
            expected_switch = be_rail_switches[rail // rails_per_switch].name
            self.assertEqual(
                len(switches), 1,
                f"Rail interface {interface_name} should connect to exactly 1 switch across all servers, "
                f"but connects to {len(switches)} switches: {switches}"
            )
            self.assertEqual(
                list(switches)[0],
                expected_switch,
                f"Rail interface {interface_name} should map to {expected_switch}",
            )


class Case128GpuYamlExportTestCase(TestCase):
    """Validate YAML export works for the 128-GPU case data."""

    @classmethod
    def setUpTestData(cls):
        call_command(
            "setup_case_128gpu_odd_ports",
            "--clean",
            "--generate",
            stdout=StringIO(),
        )
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)

        User = get_user_model()
        cls.superuser = User.objects.create_user(
            username="case-exporter",
            password="case-exporter",
            is_staff=True,
            is_superuser=True,
        )

    def test_yaml_export_succeeds_for_case(self):
        self.client.force_login(self.superuser)
        url = reverse("plugins:netbox_hedgehog:topologyplan_export", args=[self.plan.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        documents = list(yaml.safe_load_all(response.content.decode("utf-8")))
        switch_docs = [
            doc for doc in documents
            if doc and doc.get("kind") == "Switch"
        ]
        self.assertTrue(switch_docs, "Expected Switch CRDs in export output")
        self.assertTrue(
            all(doc.get("spec", {}).get("profile") for doc in switch_docs),
            "All Switch CRDs must include spec.profile",
        )
