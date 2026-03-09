"""
RED tests for HHG class + FE spine zone implementation (DIET-260).
Tests in this class are fast (no generation). All tests FAIL until YAML changes are applied.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase, tag

from dcim.models import Device, Cable, DeviceType, ModuleType
from netbox_hedgehog.choices import FabricTypeChoices, PortZoneTypeChoices, PortTypeChoices
from netbox_hedgehog.models.topology_planning import (
    TopologyPlan, PlanServerClass, PlanServerConnection, SwitchPortZone, BreakoutOption,
)
from netbox_hedgehog.tests.test_topology_planning.case_128gpu_helpers import (
    load_case_128gpu, expected_128gpu_counts,
)

PLAN_NAME = "UX Case 128GPU Odd Ports"


class HhgYamlDefinitionTestCase(TestCase):
    """
    RED tests for HHG class + FE spine zone implementation (DIET-260).
    Tests in this class are fast (no generation). All tests FAIL until YAML changes are applied.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_case_128gpu_odd_ports", "--clean", stdout=StringIO())
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)

    # -------------------------------------------------------------------------
    # T-HHG-1: hhg server class exists
    # -------------------------------------------------------------------------

    def test_hhg_server_class_exists(self):
        """hhg server class must be defined in the canonical 128GPU case."""
        qs = PlanServerClass.objects.filter(plan=self.plan, server_class_id='hhg')
        self.assertTrue(
            qs.exists(),
            "hhg server class must be defined in canonical 128GPU case",
        )
        self.assertEqual(
            qs.first().quantity, 2,
            "hhg server class quantity must be 2",
        )

    # -------------------------------------------------------------------------
    # T-HHG-2: hhg device type has 2x200gbase interface templates
    # -------------------------------------------------------------------------

    def test_hhg_device_type_is_200g(self):
        """hhg-server-200g DeviceType must exist with 2x200gbase interface templates."""
        qs = DeviceType.objects.filter(slug='hhg-server-200g')
        self.assertTrue(
            qs.exists(),
            "hhg-server-200g DeviceType must exist",
        )
        device_type = qs.first()
        templates_200g = device_type.interfacetemplates.filter(type__icontains='200gbase')
        self.assertEqual(
            templates_200g.count(), 2,
            "hhg_server_dt must have 2x200gbase interface templates",
        )

    # -------------------------------------------------------------------------
    # T-HHG-3: nic_cx7_dual_200g module type exists
    # -------------------------------------------------------------------------

    def test_nic_cx7_dual_200g_module_exists(self):
        """nic_cx7_dual_200g ModuleType must exist with 2 interface templates."""
        qs = ModuleType.objects.filter(model='ConnectX-7 Dual-Port 200G')
        self.assertTrue(
            qs.exists(),
            "nic_cx7_dual_200g ModuleType must exist",
        )
        module_type = qs.first()
        self.assertEqual(
            module_type.interfacetemplates.count(), 2,
            "nic_cx7_dual_200g must have 2 interface templates",
        )

    # -------------------------------------------------------------------------
    # T-HHG-4: b_8x100 breakout exists
    # -------------------------------------------------------------------------

    def test_b8x100_breakout_exists(self):
        """b_8x100 breakout option must exist with correct speed and port parameters."""
        qs = BreakoutOption.objects.filter(breakout_id='8x100g')
        self.assertTrue(
            qs.exists(),
            "b_8x100 breakout option must exist",
        )
        breakout = qs.first()
        self.assertEqual(
            breakout.from_speed, 800,
            "b_8x100 from_speed must be 800",
        )
        self.assertEqual(
            breakout.logical_ports, 8,
            "b_8x100 must have 8 logical ports",
        )
        self.assertEqual(
            breakout.logical_speed, 100,
            "b_8x100 logical speed must be 100",
        )

    # -------------------------------------------------------------------------
    # T-HHG-5: hhg primary connection targets fe-spine-200G-downlinks
    # -------------------------------------------------------------------------

    def test_hhg_primary_connection_targets_fe_spine_200g(self):
        """hhg primary data connection must target fe-spine/fe-spine-200G-downlinks at 200G."""
        qs = PlanServerConnection.objects.filter(
            server_class__plan=self.plan,
            server_class__server_class_id='hhg',
            port_type=PortTypeChoices.DATA,
        )
        self.assertEqual(
            qs.count(), 1,
            "hhg must have exactly one data connection",
        )
        connection = qs.first()
        self.assertEqual(
            connection.target_zone.switch_class.switch_class_id, 'fe-spine',
        )
        self.assertEqual(
            connection.target_zone.zone_name, 'fe-spine-200G-downlinks',
        )
        self.assertEqual(
            connection.speed, 200,
        )

    # -------------------------------------------------------------------------
    # T-HHG-6: hhg primary connection uses 2 ports per connection
    # -------------------------------------------------------------------------

    def test_hhg_primary_ports_per_connection(self):
        """hhg primary connection must use 2 ports per connection."""
        qs = PlanServerConnection.objects.filter(
            server_class__plan=self.plan,
            server_class__server_class_id='hhg',
            port_type=PortTypeChoices.DATA,
        )
        self.assertEqual(qs.count(), 1, "hhg must have exactly one data connection")
        self.assertEqual(
            qs.first().ports_per_connection, 2,
            "hhg primary connection must use 2 ports",
        )

    # -------------------------------------------------------------------------
    # T-HHG-7: hhg primary connection uses alternating distribution
    # -------------------------------------------------------------------------

    def test_hhg_primary_distribution_is_alternating(self):
        """hhg primary connection must use alternating distribution."""
        qs = PlanServerConnection.objects.filter(
            server_class__plan=self.plan,
            server_class__server_class_id='hhg',
            port_type=PortTypeChoices.DATA,
        )
        self.assertEqual(qs.count(), 1, "hhg must have exactly one data connection")
        self.assertEqual(
            qs.first().distribution, 'alternating',
            "hhg primary connection must use alternating distribution",
        )

    # -------------------------------------------------------------------------
    # T-HHG-8: hhg BMC connection targets oob-mgmt-leaf at 1G
    # -------------------------------------------------------------------------

    def test_hhg_bmc_connection_exists(self):
        """hhg must have exactly one IPMI/BMC connection targeting oob-mgmt-leaf at 1G."""
        qs = PlanServerConnection.objects.filter(
            server_class__plan=self.plan,
            server_class__server_class_id='hhg',
            port_type=PortTypeChoices.IPMI,
        )
        self.assertEqual(
            qs.count(), 1,
            "hhg must have exactly one IPMI/BMC connection",
        )
        connection = qs.first()
        self.assertEqual(
            connection.target_zone.switch_class.switch_class_id, 'oob-mgmt-leaf',
        )
        self.assertEqual(
            connection.speed, 1,
        )

    # -------------------------------------------------------------------------
    # T-HHG-9: fe-spine-downlinks port_spec changed from 1-64 to 2-63
    # -------------------------------------------------------------------------

    def test_fe_spine_downlinks_port_spec_is_2_63(self):
        """fe-spine-downlinks port_spec must be 2-63 (not 1-64) to leave room for HHG zones."""
        qs = SwitchPortZone.objects.filter(
            switch_class__plan=self.plan,
            zone_name='fe-spine-downlinks',
        )
        self.assertTrue(
            qs.exists(),
            "fe-spine-downlinks zone must exist",
        )
        zone = qs.first()
        self.assertEqual(
            zone.port_spec, '2-63',
            "fe-spine-downlinks port_spec must be 2-63 (not 1-64)",
        )

    # -------------------------------------------------------------------------
    # T-HHG-10: fe-spine-200G-downlinks zone spec
    # -------------------------------------------------------------------------

    def test_fe_spine_200g_zone_spec(self):
        """fe-spine-200G-downlinks zone must exist covering port 1 with b_4x200 breakout."""
        qs = SwitchPortZone.objects.filter(
            switch_class__plan=self.plan,
            zone_name='fe-spine-200G-downlinks',
        )
        self.assertTrue(
            qs.exists(),
            "fe-spine-200G-downlinks zone must exist",
        )
        zone = qs.first()
        self.assertEqual(
            zone.zone_type, PortZoneTypeChoices.SERVER,
        )
        self.assertEqual(
            zone.port_spec, '1',
            "fe-spine-200G-downlinks must cover port 1 only",
        )
        self.assertEqual(
            zone.breakout_option.breakout_id, '4x200g',
            "fe-spine-200G-downlinks must use b_4x200 breakout",
        )

    # -------------------------------------------------------------------------
    # T-HHG-11: fe-spine-100G-downlinks zone spec
    # -------------------------------------------------------------------------

    def test_fe_spine_100g_zone_spec(self):
        """fe-spine-100G-downlinks zone must exist covering port 64 with b_8x100 breakout."""
        qs = SwitchPortZone.objects.filter(
            switch_class__plan=self.plan,
            zone_name='fe-spine-100G-downlinks',
        )
        self.assertTrue(
            qs.exists(),
            "fe-spine-100G-downlinks zone must exist",
        )
        zone = qs.first()
        self.assertEqual(
            zone.zone_type, PortZoneTypeChoices.SERVER,
        )
        self.assertEqual(
            zone.port_spec, '64',
            "fe-spine-100G-downlinks must cover port 64 only",
        )
        self.assertEqual(
            zone.breakout_option.breakout_id, '8x100g',
            "fe-spine-100G-downlinks must use b_8x100 breakout",
        )

    # -------------------------------------------------------------------------
    # T-HHG-12: expected.counts updated for server_classes and connections
    # -------------------------------------------------------------------------

    def test_expected_counts_updated(self):
        """expected.counts must reflect 9 server_classes and 26 connections."""
        counts = expected_128gpu_counts()
        self.assertEqual(
            counts.get('server_classes'), 9,
            f"expected.counts.server_classes must be 9, got {counts.get('server_classes')}",
        )
        self.assertEqual(
            counts.get('connections'), 26,
            f"expected.counts.connections must be 26, got {counts.get('connections')}",
        )


@tag('slow', 'regression')
class HhgGenerationTestCase(TestCase):
    """
    RED generation tests. SLOW: requires full 128GPU generation. All tests FAIL until YAML changes are applied.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_case_128gpu_odd_ports", "--clean", "--generate", stdout=StringIO())
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)
        cls.all_cables = list(
            Cable.objects.filter(custom_field_data__hedgehog_plan_id=str(cls.plan.pk))
        )

    # -------------------------------------------------------------------------
    # T-HHG-13: 2 HHG server devices generated
    # -------------------------------------------------------------------------

    def test_hhg_devices_generated(self):
        """DeviceGenerator must produce exactly 2 HHG server devices (hhg-001, hhg-002)."""
        hhg_devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            role__slug='server',
            name__startswith='hhg-',
        )
        self.assertEqual(
            hhg_devices.count(), 2,
            "Expected 2 HHG server devices (hhg-001, hhg-002)",
        )

    # -------------------------------------------------------------------------
    # T-HHG-14: HHG devices use hhg-server-200g device type
    # -------------------------------------------------------------------------

    def test_hhg_device_type_is_hhg_server_200g(self):
        """Each HHG device must use device_type slug 'hhg-server-200g'."""
        hhg_devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            role__slug='server',
            name__startswith='hhg-',
        )
        for device in hhg_devices:
            self.assertEqual(
                device.device_type.slug, 'hhg-server-200g',
                f"Device {device.name} must use device_type slug 'hhg-server-200g'",
            )

    # -------------------------------------------------------------------------
    # T-HHG-15: 4 HHG→fe-spine primary cables
    # -------------------------------------------------------------------------

    def test_hhg_spine_cables_count(self):
        """Expected 4 HHG→fe-spine cables (2 servers × 2 ports, alternating across 2 spines)."""
        hhg_ids = set(Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            role__slug='server',
            name__startswith='hhg-',
        ).values_list('id', flat=True))

        spine_ids = set(Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric=FabricTypeChoices.FRONTEND,
            custom_field_data__hedgehog_role='spine',
        ).values_list('id', flat=True))

        hhg_spine_cables = []
        for cable in self.all_cables:
            a_terms = cable.a_terminations if isinstance(cable.a_terminations, list) else list(cable.a_terminations.all())
            b_terms = cable.b_terminations if isinstance(cable.b_terminations, list) else list(cable.b_terminations.all())
            if not a_terms or not b_terms:
                continue
            a_dev_id = a_terms[0].device_id
            b_dev_id = b_terms[0].device_id
            if (a_dev_id in hhg_ids and b_dev_id in spine_ids) or \
               (b_dev_id in hhg_ids and a_dev_id in spine_ids):
                hhg_spine_cables.append(cable)

        self.assertEqual(
            len(hhg_spine_cables), 4,
            "Expected 4 HHG→fe-spine cables (2 servers × 2 ports, alternating across 2 spines)",
        )

    # -------------------------------------------------------------------------
    # T-HHG-16: alternating distribution gives each spine exactly 2 HHG cables
    # -------------------------------------------------------------------------

    def test_hhg_alternating_distribution(self):
        """Each fe-spine must have exactly 2 HHG primary connections (alternating distribution)."""
        hhg_ids = set(Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            role__slug='server',
            name__startswith='hhg-',
        ).values_list('id', flat=True))

        spine_devices = list(Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric=FabricTypeChoices.FRONTEND,
            custom_field_data__hedgehog_role='spine',
        ))

        for spine in spine_devices:
            count = 0
            for cable in self.all_cables:
                a_terms = cable.a_terminations if isinstance(cable.a_terminations, list) else list(cable.a_terminations.all())
                b_terms = cable.b_terminations if isinstance(cable.b_terminations, list) else list(cable.b_terminations.all())
                if not a_terms or not b_terms:
                    continue
                a_dev_id = a_terms[0].device_id
                b_dev_id = b_terms[0].device_id
                if (a_dev_id == spine.id and b_dev_id in hhg_ids) or \
                   (b_dev_id == spine.id and a_dev_id in hhg_ids):
                    count += 1
            self.assertEqual(
                count, 2,
                f"Each fe-spine must have exactly 2 HHG primary connections (alternating distribution); "
                f"{spine.name} has {count}",
            )

    # -------------------------------------------------------------------------
    # T-HHG-17: 2 HHG BMC cables to oob-mgmt switches
    # -------------------------------------------------------------------------

    def test_hhg_bmc_cables_count(self):
        """Expected 2 HHG BMC cables (one per HHG server)."""
        hhg_ids = set(Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            role__slug='server',
            name__startswith='hhg-',
        ).values_list('id', flat=True))

        oob_ids = set(Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric=FabricTypeChoices.OOB_MGMT,
        ).values_list('id', flat=True))

        hhg_bmc_cables = []
        for cable in self.all_cables:
            a_terms = cable.a_terminations if isinstance(cable.a_terminations, list) else list(cable.a_terminations.all())
            b_terms = cable.b_terminations if isinstance(cable.b_terminations, list) else list(cable.b_terminations.all())
            if not a_terms or not b_terms:
                continue
            a_dev_id = a_terms[0].device_id
            b_dev_id = b_terms[0].device_id
            if (a_dev_id in hhg_ids and b_dev_id in oob_ids) or \
               (b_dev_id in hhg_ids and a_dev_id in oob_ids):
                hhg_bmc_cables.append(cable)

        self.assertEqual(
            len(hhg_bmc_cables), 2,
            "Expected 2 HHG BMC cables (one per HHG server)",
        )

    # -------------------------------------------------------------------------
    # T-HHG-18: total device count is 173
    # -------------------------------------------------------------------------

    def test_device_count_is_173(self):
        """Total device count must be 173 (171 base + 2 HHG)."""
        try:
            state = self.plan.generation_state
        except Exception:
            self.skipTest("No GenerationState found - generation may not have run")
        self.assertEqual(
            state.device_count, 173,
            f"Expected 173 devices (171 base + 2 HHG), got {state.device_count}",
        )

    # -------------------------------------------------------------------------
    # T-HHG-19: total interface count is 1259
    # -------------------------------------------------------------------------

    def test_interface_count_is_1259(self):
        """Total interface count must be 1259 after HHG addition."""
        try:
            state = self.plan.generation_state
        except Exception:
            self.skipTest("No GenerationState found - generation may not have run")
        self.assertEqual(
            state.interface_count, 1259,
            f"Expected 1259 interfaces, got {state.interface_count}",
        )

    # -------------------------------------------------------------------------
    # T-HHG-20: total cable count is 985
    # -------------------------------------------------------------------------

    def test_cable_count_is_985(self):
        """Total cable count must be 985 (979 base + 6 HHG)."""
        try:
            state = self.plan.generation_state
        except Exception:
            self.skipTest("No GenerationState found - generation may not have run")
        self.assertEqual(
            state.cable_count, 985,
            f"Expected 985 cables (979 base + 6 HHG), got {state.cable_count}",
        )


@tag('slow')
class HhgExportTestCase(TestCase):
    """
    RED export tests. SLOW: requires generation + YAML export. All tests FAIL until YAML changes are applied.
    """

    @classmethod
    def setUpTestData(cls):
        import yaml as pyyaml
        from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan

        call_command("setup_case_128gpu_odd_ports", "--clean", "--generate", stdout=StringIO())
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)
        yaml_content = generate_yaml_for_plan(cls.plan)
        cls.documents = list(pyyaml.safe_load_all(yaml_content))
        cls.switch_crds = [d for d in cls.documents if d and d.get('kind') == 'Switch']
        cls.server_crds = [d for d in cls.documents if d and d.get('kind') == 'Server']
        cls.connection_crds = [d for d in cls.documents if d and d.get('kind') == 'Connection']
        cls.switch_names = {d['metadata']['name'] for d in cls.switch_crds}
        cls.server_names = {d['metadata']['name'] for d in cls.server_crds}

    # -------------------------------------------------------------------------
    # T-HHG-21: HHG servers appear as Server CRDs
    # -------------------------------------------------------------------------

    def test_hhg_servers_in_server_crds(self):
        """HHG servers must appear as exactly 2 Server CRDs (hhg-001, hhg-002)."""
        names = [n for n in self.server_names if 'hhg' in n]
        self.assertEqual(
            len(names), 2,
            f"Expected 2 HHG Server CRDs (hhg-001, hhg-002), got {len(names)}: {names}",
        )

    # -------------------------------------------------------------------------
    # T-HHG-22: HHG servers do NOT appear as Switch CRDs
    # -------------------------------------------------------------------------

    def test_hhg_not_in_switch_crds(self):
        """HHG servers must NOT appear in Switch CRDs."""
        names = [n for n in self.switch_names if 'hhg' in n]
        self.assertEqual(
            len(names), 0,
            "HHG servers must NOT appear in Switch CRDs",
        )

    # -------------------------------------------------------------------------
    # T-HHG-23: HHG→spine connections are unbundled Connection CRDs
    # -------------------------------------------------------------------------

    def test_hhg_spine_connections_are_unbundled(self):
        """HHG→fe-spine links must produce 4 unbundled Connection CRDs."""
        hhg_conn_crds = [
            d for d in self.connection_crds
            if any('hhg' in str(v) for v in d.get('spec', {}).values())
        ]
        self.assertEqual(
            len(hhg_conn_crds), 4,
            f"Expected 4 unbundled Connection CRDs for HHG→fe-spine links, got {len(hhg_conn_crds)}",
        )

    # -------------------------------------------------------------------------
    # T-HHG-24: HHG BMC cables excluded from Connection CRDs
    # -------------------------------------------------------------------------

    def test_hhg_bmc_excluded_from_connections(self):
        """HHG BMC cables must NOT produce Connection CRDs (server↔surrogate excluded)."""
        hhg_oob_conn_crds = [
            d for d in self.connection_crds
            if any('hhg' in str(v) for v in d.get('spec', {}).values())
            and any('oob-mgmt' in str(v) for v in d.get('spec', {}).values())
        ]
        self.assertEqual(
            len(hhg_oob_conn_crds), 0,
            "HHG BMC cables must NOT produce Connection CRDs (server↔surrogate excluded)",
        )

    # -------------------------------------------------------------------------
    # T-HHG-25: oob-mgmt surrogate contract preserved (regression)
    # -------------------------------------------------------------------------

    def test_surrogate_contract_preserved(self):
        """oob-mgmt surrogates must still appear as 4 Server CRDs (regression)."""
        oob_server_names = [n for n in self.server_names if 'oob-mgmt' in n]
        self.assertEqual(
            len(oob_server_names), 4,
            f"oob-mgmt surrogates must still appear as 4 Server CRDs (regression), "
            f"got {len(oob_server_names)}: {oob_server_names}",
        )
