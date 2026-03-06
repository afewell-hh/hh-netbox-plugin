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
from netbox_hedgehog.models.topology_planning import SwitchPortZone
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

        self.assertEqual(server_count, 8)
        self.assertEqual(switch_count, 6)
        self.assertEqual(connection_count, 16)

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


class FeBorderLeafTestCase(TestCase):
    """Validate fe-border-leaf switch class, port zones, and server class additions (DIET-237)."""

    @classmethod
    def setUpTestData(cls):
        call_command("setup_case_128gpu_odd_ports", stdout=StringIO())
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)

    def test_fe_border_leaf_switch_class_exists(self):
        """fe-border-leaf must be present as a switch class with DS3000 extension."""
        border = PlanSwitchClass.objects.filter(
            plan=self.plan,
            switch_class_id='fe-border-leaf',
        ).first()
        self.assertIsNotNone(border, "fe-border-leaf switch class must exist")
        self.assertEqual(border.fabric, 'frontend')
        self.assertEqual(border.hedgehog_role, 'server-leaf')
        self.assertIsNotNone(border.device_type_extension)
        self.assertEqual(
            border.device_type_extension.hedgehog_profile_name,
            'celestica-ds3000',
        )

    def test_fe_border_leaf_port_zones(self):
        """fe-border-leaf must have 25G and 100G downlink zones with correct breakout options."""
        border = PlanSwitchClass.objects.get(plan=self.plan, switch_class_id='fe-border-leaf')
        zones = {z.zone_name: z for z in SwitchPortZone.objects.filter(switch_class=border)}

        self.assertIn('fe-border-25g-downlinks', zones, "25G downlink zone must exist")
        self.assertIn('fe-border-100g-downlinks', zones, "100G downlink zone must exist")

        z25 = zones['fe-border-25g-downlinks']
        self.assertEqual(z25.zone_type, 'server')
        self.assertIsNotNone(z25.breakout_option)
        self.assertEqual(z25.breakout_option.breakout_id, '4x25g',
                         "25G zone must use 4x25G breakout for admin node connections")

        z100 = zones['fe-border-100g-downlinks']
        self.assertEqual(z100.zone_type, 'server')
        self.assertIsNotNone(z100.breakout_option)
        self.assertEqual(z100.breakout_option.breakout_id, '1x100g',
                         "100G zone must use native 1x100G for controller/exo connections")

    def test_new_border_server_classes_exist(self):
        """All five new border server classes must be created."""
        expected_ids = ['admin-node', 'host-lfm-ctrl', 'hh-fe-ctrl', 'hh-be-ctrl', 'exo-kube']
        for sc_id in expected_ids:
            sc = PlanServerClass.objects.filter(plan=self.plan, server_class_id=sc_id).first()
            self.assertIsNotNone(sc, f"Server class '{sc_id}' must exist")

    def test_border_server_quantities(self):
        """Admin node, controllers = qty 1; exo-kube = qty 3."""
        for sc_id in ['admin-node', 'host-lfm-ctrl', 'hh-fe-ctrl', 'hh-be-ctrl']:
            sc = PlanServerClass.objects.get(plan=self.plan, server_class_id=sc_id)
            self.assertEqual(sc.quantity, 1, f"{sc_id} must have quantity 1")
        exo = PlanServerClass.objects.get(plan=self.plan, server_class_id='exo-kube')
        self.assertEqual(exo.quantity, 3, "exo-kube must have quantity 3")

    def test_border_server_connections_target_border_leaf(self):
        """All new border server connections must target fe-border-leaf zones."""
        border = PlanSwitchClass.objects.get(plan=self.plan, switch_class_id='fe-border-leaf')
        border_zone_ids = set(
            SwitchPortZone.objects.filter(switch_class=border).values_list('pk', flat=True)
        )
        for sc_id in ['admin-node', 'host-lfm-ctrl', 'hh-fe-ctrl', 'hh-be-ctrl', 'exo-kube']:
            sc = PlanServerClass.objects.get(plan=self.plan, server_class_id=sc_id)
            conns = PlanServerConnection.objects.filter(server_class=sc)
            self.assertGreater(conns.count(), 0, f"{sc_id} must have at least one connection")
            for conn in conns:
                self.assertIn(
                    conn.target_zone_id,
                    border_zone_ids,
                    f"{sc_id} connection must target fe-border-leaf zone",
                )

    def test_admin_node_uses_25g_breakout_zone(self):
        """admin-node connection must target the 4x25G breakout zone specifically."""
        sc = PlanServerClass.objects.get(plan=self.plan, server_class_id='admin-node')
        conn = PlanServerConnection.objects.filter(server_class=sc).first()
        self.assertIsNotNone(conn)
        self.assertEqual(conn.speed, 25, "admin-node connection must be 25G")
        self.assertEqual(
            conn.target_zone.zone_name,
            'fe-border-25g-downlinks',
            "admin-node must connect to 25G breakout zone",
        )

    def test_controller_connections_use_100g_zone(self):
        """Controller server connections must target 100G zone at 100G speed."""
        for sc_id in ['host-lfm-ctrl', 'hh-fe-ctrl', 'hh-be-ctrl']:
            sc = PlanServerClass.objects.get(plan=self.plan, server_class_id=sc_id)
            conn = PlanServerConnection.objects.filter(server_class=sc).first()
            self.assertIsNotNone(conn, f"{sc_id} must have a connection")
            self.assertEqual(conn.speed, 100, f"{sc_id} connection must be 100G")
            self.assertEqual(
                conn.target_zone.zone_name,
                'fe-border-100g-downlinks',
                f"{sc_id} must connect to 100G zone",
            )

    def test_fe_border_leaf_has_uplink_zone(self):
        """fe-border-leaf must have an uplink zone (ports 17-32) for capacity documentation."""
        border = PlanSwitchClass.objects.get(plan=self.plan, switch_class_id='fe-border-leaf')
        uplink_zone = SwitchPortZone.objects.filter(
            switch_class=border,
            zone_name='fe-border-uplinks',
        ).first()
        self.assertIsNotNone(uplink_zone, "fe-border-uplinks uplink zone must exist")
        self.assertEqual(uplink_zone.zone_type, 'uplink')
        self.assertEqual(uplink_zone.port_spec, '17-32')

    def test_fe_border_leaf_standalone_no_spine_demand(self):
        """uplink_ports_per_switch=0 on fe-border-leaf must yield 0 uplink port count.

        Even though an uplink zone exists (documenting physical capacity), the explicit
        uplink_ports_per_switch=0 signals this is a standalone leaf - no spine connections
        required. get_uplink_port_count() must return 0 in this case.
        """
        from netbox_hedgehog.utils.topology_calculations import get_uplink_port_count

        border = PlanSwitchClass.objects.get(plan=self.plan, switch_class_id='fe-border-leaf')
        self.assertEqual(border.uplink_ports_per_switch, 0)
        # Despite having an uplink zone, the explicit 0 overrides zone-derived count
        count = get_uplink_port_count(border)
        self.assertEqual(count, 0, "Standalone leaf (uplink_ports_per_switch=0) must contribute 0 spine demand")


class CanonicalStorageZoneRegressionTestCase(TestCase):
    """
    Regression guard: canonical 128GPU case must stay storage-consolidated with
    correct zone names and port specs. Fails immediately on any re-split or revert.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_case_128gpu_odd_ports", stdout=StringIO())
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)

    # -------------------------------------------------------------------------
    # Storage consolidation: no *-a/*-b split classes allowed
    # -------------------------------------------------------------------------

    def test_no_split_storage_switch_classes(self):
        """fe-storage-leaf-a and fe-storage-leaf-b must not exist (storage is consolidated)."""
        self.assertFalse(
            PlanSwitchClass.objects.filter(plan=self.plan, switch_class_id='fe-storage-leaf-a').exists(),
            "fe-storage-leaf-a must not exist; storage switch is consolidated to fe-storage-leaf",
        )
        self.assertFalse(
            PlanSwitchClass.objects.filter(plan=self.plan, switch_class_id='fe-storage-leaf-b').exists(),
            "fe-storage-leaf-b must not exist; storage switch is consolidated to fe-storage-leaf",
        )

    def test_no_split_storage_server_classes(self):
        """storage-a and storage-b must not exist (storage is consolidated)."""
        self.assertFalse(
            PlanServerClass.objects.filter(plan=self.plan, server_class_id='storage-a').exists(),
            "storage-a must not exist; storage is consolidated to a single 'storage' class",
        )
        self.assertFalse(
            PlanServerClass.objects.filter(plan=self.plan, server_class_id='storage-b').exists(),
            "storage-b must not exist; storage is consolidated to a single 'storage' class",
        )

    def test_consolidated_storage_switch_class_exists(self):
        """Exactly one fe-storage-leaf switch class with correct fabric/role."""
        sc = PlanSwitchClass.objects.filter(plan=self.plan, switch_class_id='fe-storage-leaf')
        self.assertEqual(sc.count(), 1, "Exactly one fe-storage-leaf switch class must exist")
        self.assertEqual(sc.first().fabric, 'frontend')
        self.assertEqual(sc.first().hedgehog_role, 'server-leaf')

    def test_consolidated_storage_server_class_quantity(self):
        """Single storage server class with quantity=18."""
        sc = PlanServerClass.objects.get(plan=self.plan, server_class_id='storage')
        self.assertEqual(sc.quantity, 18, "Consolidated storage class must have quantity=18")

    def test_exactly_one_storage_connection(self):
        """Exactly one storage server connection targeting fe-storage-leaf."""
        sc = PlanServerClass.objects.get(plan=self.plan, server_class_id='storage')
        conns = PlanServerConnection.objects.filter(server_class=sc)
        self.assertEqual(conns.count(), 1, "storage class must have exactly one connection")
        storage_leaf = PlanSwitchClass.objects.get(plan=self.plan, switch_class_id='fe-storage-leaf')
        self.assertEqual(
            conns.first().target_zone.switch_class,
            storage_leaf,
            "storage connection must target fe-storage-leaf",
        )

    # -------------------------------------------------------------------------
    # Zone naming: required names and port specs
    # -------------------------------------------------------------------------

    def _get_zone(self, switch_class_id, zone_name):
        sc = PlanSwitchClass.objects.get(plan=self.plan, switch_class_id=switch_class_id)
        return SwitchPortZone.objects.get(switch_class=sc, zone_name=zone_name)

    def test_be_rail_leaf_uplinks_zone_port_spec(self):
        """be-rail-leaf/backend-uplinks must have port_spec 33-64."""
        zone = self._get_zone('be-rail-leaf', 'backend-uplinks')
        self.assertEqual(zone.port_spec, '33-64')

    def test_be_rail_leaf_downlinks_zone_name_and_port_spec(self):
        """be-rail-leaf server zone must be named be-leaf-downlinks with port_spec 1-33."""
        zone = self._get_zone('be-rail-leaf', 'be-leaf-downlinks')
        self.assertEqual(zone.zone_type, 'server')
        self.assertEqual(zone.port_spec, '1-33')
        # old generic name must not exist
        sc = PlanSwitchClass.objects.get(plan=self.plan, switch_class_id='be-rail-leaf')
        self.assertFalse(
            SwitchPortZone.objects.filter(switch_class=sc, zone_name='server-downlinks').exists(),
            "Generic 'server-downlinks' zone must not exist on be-rail-leaf",
        )

    def test_be_spine_downlinks_zone_name(self):
        """be-spine fabric zone must be named be-spine-downlinks."""
        zone = self._get_zone('be-spine', 'be-spine-downlinks')
        self.assertEqual(zone.zone_type, 'fabric')
        sc = PlanSwitchClass.objects.get(plan=self.plan, switch_class_id='be-spine')
        self.assertFalse(
            SwitchPortZone.objects.filter(switch_class=sc, zone_name='leaf-downlinks').exists(),
            "Generic 'leaf-downlinks' zone must not exist on be-spine",
        )

    def test_fe_gpu_leaf_zone_names(self):
        """fe-gpu-leaf zones must use fe-gpu-leaf-downlinks and fe-gpu-leaf-uplinks."""
        self._get_zone('fe-gpu-leaf', 'fe-gpu-leaf-downlinks')
        self._get_zone('fe-gpu-leaf', 'fe-gpu-leaf-uplinks')
        sc = PlanSwitchClass.objects.get(plan=self.plan, switch_class_id='fe-gpu-leaf')
        self.assertFalse(
            SwitchPortZone.objects.filter(switch_class=sc, zone_name='server-downlinks').exists(),
            "Generic 'server-downlinks' must not exist on fe-gpu-leaf",
        )
        self.assertFalse(
            SwitchPortZone.objects.filter(switch_class=sc, zone_name='uplinks').exists(),
            "Generic 'uplinks' must not exist on fe-gpu-leaf",
        )

    def test_fe_spine_downlinks_zone_name(self):
        """fe-spine fabric zone must be named fe-spine-downlinks."""
        zone = self._get_zone('fe-spine', 'fe-spine-downlinks')
        self.assertEqual(zone.zone_type, 'fabric')
        sc = PlanSwitchClass.objects.get(plan=self.plan, switch_class_id='fe-spine')
        self.assertFalse(
            SwitchPortZone.objects.filter(switch_class=sc, zone_name='leaf-downlinks').exists(),
            "Generic 'leaf-downlinks' zone must not exist on fe-spine",
        )

    def test_fe_storage_leaf_zone_names(self):
        """fe-storage-leaf must have fe-storage-leaf-downlinks and fe-storage-leaf-uplinks."""
        self._get_zone('fe-storage-leaf', 'fe-storage-leaf-downlinks')
        self._get_zone('fe-storage-leaf', 'fe-storage-leaf-uplinks')

    def test_canonical_counts_from_yaml(self):
        """Plan counts must match expected.counts in canonical YAML (DIET-239 persistence rule)."""
        from netbox_hedgehog.tests.test_topology_planning.case_128gpu_helpers import expected_128gpu_counts
        expected = expected_128gpu_counts()
        self.assertEqual(
            PlanServerClass.objects.filter(plan=self.plan).count(),
            expected['server_classes'],
        )
        self.assertEqual(
            PlanSwitchClass.objects.filter(plan=self.plan).count(),
            expected['switch_classes'],
        )
        self.assertEqual(
            PlanServerConnection.objects.filter(server_class__plan=self.plan).count(),
            expected['connections'],
        )
