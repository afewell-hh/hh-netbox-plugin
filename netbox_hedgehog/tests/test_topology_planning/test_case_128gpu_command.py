"""
Integration tests for setup_case_128gpu_odd_ports management command.
"""

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

    def test_rail_requires_value_for_rail_optimized(self):
        connection = PlanServerConnection.objects.filter(server_class__plan=self.plan).first()
        form = PlanServerConnectionForm(
            data={
                "server_class": connection.server_class.pk,
                "connection_id": "rail-missing",
                "ports_per_connection": 1,
                "hedgehog_conn_type": ConnectionTypeChoices.UNBUNDLED,
                "distribution": ConnectionDistributionChoices.RAIL_OPTIMIZED,
                "target_switch_class": connection.target_switch_class.pk,
                "speed": 400,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("rail", form.errors)
