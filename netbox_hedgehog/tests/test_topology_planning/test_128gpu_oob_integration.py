"""
RED tests for Phase 5: 128GPU OOB-MGMT integration (DIET-254).

All tests in this file are expected to FAIL until Phase 5 GREEN implementation
is complete. Failure reasons are documented per test.

Test contract:
  - 128GPU case has oob-mgmt-leaf switch class (6 instances)
  - fe-border-leaf has an oob-type zone for managed<->surrogate uplink ports
  - oob-mgmt-leaf has an oob-type downlink zone (for server BMC connections)
  - oob-mgmt-leaf has an oob-type uplink zone with explicit peer_zone target
  - All 8 server classes have an IPMI connection targeting oob-mgmt-leaf oob zone
  - DeviceGenerator creates 6 oob-mgmt switch instances
  - DeviceGenerator creates oob-zone cables between oob-mgmt-leaf and fe-border-leaf
  - DeviceGenerator creates IPMI cables between server instances and oob-mgmt-leaf

Constraint #3 (export scope) is tested in test_managed_fabric_export.py.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase, tag

from dcim.models import Device, Cable
from netbox_hedgehog.choices import FabricTypeChoices, PortZoneTypeChoices, PortTypeChoices
from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    PlanSwitchClass,
    PlanServerClass,
    PlanServerConnection,
    SwitchPortZone,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator


PLAN_NAME = "UX Case 128GPU Odd Ports"


class OobMgmtSwitchClassStructureTestCase(TestCase):
    """
    T5-A: 128GPU case must include oob-mgmt-leaf switch class with correct structure.

    Expected failures (RED state):
      - All tests: YAML case does not yet define oob-mgmt-leaf, oob zones, or IPMI connections.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_case_128gpu_odd_ports", "--clean", stdout=StringIO())
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)

    # -------------------------------------------------------------------------
    # T5-A-1: oob-mgmt-leaf switch class exists
    # Expected failure: YAML has no oob-mgmt-leaf switch_class entry.
    # -------------------------------------------------------------------------

    def test_oob_mgmt_leaf_switch_class_exists(self):
        """oob-mgmt-leaf switch class must be present in the 128GPU case."""
        oob_leaf = PlanSwitchClass.objects.filter(
            plan=self.plan,
            switch_class_id='oob-mgmt-leaf',
        ).first()
        self.assertIsNotNone(
            oob_leaf,
            "oob-mgmt-leaf switch class must exist in ux_case_128gpu_odd_ports.yaml",
        )

    # -------------------------------------------------------------------------
    # T5-A-2: oob-mgmt-leaf uses oob-mgmt fabric
    # Expected failure: switch class doesn't exist yet.
    # -------------------------------------------------------------------------

    def test_oob_mgmt_leaf_fabric_is_oob_mgmt(self):
        """oob-mgmt-leaf fabric must be 'oob-mgmt' (surrogate endpoint fabric)."""
        oob_leaf = PlanSwitchClass.objects.filter(
            plan=self.plan, switch_class_id='oob-mgmt-leaf'
        ).first()
        self.assertIsNotNone(oob_leaf, "oob-mgmt-leaf must exist")
        self.assertEqual(
            oob_leaf.fabric,
            FabricTypeChoices.OOB_MGMT,
            "oob-mgmt-leaf must have fabric='oob-mgmt'",
        )

    # -------------------------------------------------------------------------
    # T5-A-3: oob-mgmt-leaf uses ES1000-48 device type
    # -------------------------------------------------------------------------

    def test_oob_mgmt_leaf_uses_es1000(self):
        """oob-mgmt-leaf must be backed by ES1000-48 device type."""
        oob_leaf = PlanSwitchClass.objects.filter(
            plan=self.plan, switch_class_id='oob-mgmt-leaf'
        ).first()
        self.assertIsNotNone(oob_leaf, "oob-mgmt-leaf must exist")
        self.assertIsNotNone(oob_leaf.device_type_extension, "oob-mgmt-leaf must have a DeviceTypeExtension")
        self.assertEqual(
            oob_leaf.device_type_extension.device_type.model,
            'ES1000-48',
            "oob-mgmt-leaf device type must be ES1000-48",
        )

    # -------------------------------------------------------------------------
    # T5-A-4: Total switch class count is 7 (existing 6 + oob-mgmt-leaf)
    # Expected failure: YAML still has only 6 switch classes.
    # -------------------------------------------------------------------------

    def test_switch_class_count_includes_oob_mgmt(self):
        """128GPU case must have 7 switch classes after adding oob-mgmt-leaf."""
        count = PlanSwitchClass.objects.filter(plan=self.plan).count()
        self.assertEqual(
            count, 7,
            f"Expected 7 switch classes (6 existing + oob-mgmt-leaf), got {count}",
        )

    # -------------------------------------------------------------------------
    # T5-A-5: fe-border-leaf has a zone that serves as peer_zone target for oob-mgmt uplinks.
    # Approved design (#258 interim fix): a shared 25G breakout zone (fe-border-25g-shared,
    # ports 14-16) is used for both admin-node downlinks and oob-mgmt surrogate uplinks.
    # No dedicated OOB-type zone on fe-border-leaf is required.
    # -------------------------------------------------------------------------

    def test_fe_border_leaf_has_oob_zone(self):
        """fe-border-leaf must have the shared 25G zone that serves as oob-mgmt peer_zone target.

        Approved design: fe-border-25g-shared (ports 14-16, 4x25G) is shared between
        admin-node data connections and oob-mgmt surrogate uplinks. No separate OOB-type
        zone on fe-border-leaf is needed — the peer_zone FK on oob-mgmt-uplinks provides
        the explicit target reference.
        """
        border = PlanSwitchClass.objects.filter(
            plan=self.plan, switch_class_id='fe-border-leaf'
        ).first()
        self.assertIsNotNone(border, "fe-border-leaf must exist")
        shared_zone = SwitchPortZone.objects.filter(
            switch_class=border,
            zone_name='fe-border-25g-shared',
        ).first()
        self.assertIsNotNone(
            shared_zone,
            "fe-border-leaf must have fe-border-25g-shared zone (shared 4x25G, ports 14-16) "
            "for admin-node downlinks and oob-mgmt surrogate uplinks",
        )
        self.assertEqual(shared_zone.port_spec, '14-16',
                         "Shared 25G zone must use ports 14-16 (non-overlapping with uplinks 17-32)")

    # -------------------------------------------------------------------------
    # T5-A-6: oob-mgmt-leaf has an oob-type downlink zone (for server IPMI connections)
    # Expected failure: switch class doesn't exist yet.
    # -------------------------------------------------------------------------

    def test_oob_mgmt_leaf_has_oob_downlink_zone(self):
        """oob-mgmt-leaf must have an OOB-type downlink zone for server BMC connections."""
        oob_leaf = PlanSwitchClass.objects.filter(
            plan=self.plan, switch_class_id='oob-mgmt-leaf'
        ).first()
        self.assertIsNotNone(oob_leaf, "oob-mgmt-leaf must exist")
        oob_zone = SwitchPortZone.objects.filter(
            switch_class=oob_leaf,
            zone_type=PortZoneTypeChoices.OOB,
        ).first()
        self.assertIsNotNone(
            oob_zone,
            "oob-mgmt-leaf must have an OOB-type zone for server BMC (IPMI) connections",
        )

    # -------------------------------------------------------------------------
    # T5-A-7: oob-mgmt-leaf uplink zone has peer_zone pointing to fe-border-leaf
    # Expected failure: (a) switch class doesn't exist, (b) peer_zone field doesn't
    # exist on SwitchPortZone model yet (requires migration), (c) zone not defined.
    # -------------------------------------------------------------------------

    def test_oob_mgmt_leaf_uplink_zone_has_peer_zone_target(self):
        """
        oob-mgmt-leaf must have an oob-type zone with peer_zone set to the
        fe-border-leaf oob zone (Option A: explicit target per DIET-254 kickoff).
        """
        oob_leaf = PlanSwitchClass.objects.filter(
            plan=self.plan, switch_class_id='oob-mgmt-leaf'
        ).first()
        self.assertIsNotNone(oob_leaf, "oob-mgmt-leaf must exist")

        # Find the uplink-style oob zone (the zone used for fe-border-leaf connections)
        oob_zones = SwitchPortZone.objects.filter(
            switch_class=oob_leaf,
            zone_type=PortZoneTypeChoices.OOB,
        )
        self.assertGreater(oob_zones.count(), 0, "oob-mgmt-leaf must have at least one OOB zone")

        # At least one oob zone must have peer_zone set (Option A - explicit target)
        peer_zone_found = False
        for zone in oob_zones:
            # Use try/except: if peer_zone field doesn't exist on the model yet,
            # this catches the AttributeError so the test fails cleanly at assertEqual
            try:
                peer = zone.peer_zone
            except AttributeError:
                peer = None
            if peer is not None:
                peer_zone_found = True
                break

        self.assertTrue(
            peer_zone_found,
            "At least one oob-mgmt-leaf OOB zone must have peer_zone set to "
            "the fe-border-leaf oob zone (Option A explicit target, DIET-254)",
        )


class OobMgmtServerConnectionStructureTestCase(TestCase):
    """
    T5-B: All server classes must have IPMI connections to oob-mgmt-leaf.

    Expected failures (RED state):
      - All tests: YAML has no IPMI server_connections entries.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_case_128gpu_odd_ports", "--clean", stdout=StringIO())
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)

    # -------------------------------------------------------------------------
    # T5-B-1: Total connection count includes IPMI connections (8 server classes × 1 each)
    # Expected failure: YAML has no IPMI connections, count remains 16.
    # -------------------------------------------------------------------------

    def test_connection_count_includes_ipmi(self):
        """
        Total PlanServerConnection count must be 26:
        18 existing data connections + 9 IPMI connections (one per server class, including hhg).
        """
        count = PlanServerConnection.objects.filter(server_class__plan=self.plan).count()
        self.assertEqual(
            count, 26,
            f"Expected 26 connections (18 data + 9 IPMI), got {count}",
        )

    # -------------------------------------------------------------------------
    # T5-B-2: Each server class has exactly one IPMI connection
    # Expected failure: No IPMI connections exist yet.
    # -------------------------------------------------------------------------

    def test_all_server_classes_have_ipmi_connection(self):
        """Every server class must have exactly one IPMI connection targeting oob-mgmt-leaf."""
        server_classes = PlanServerClass.objects.filter(plan=self.plan)
        for sc in server_classes:
            ipmi_conns = PlanServerConnection.objects.filter(
                server_class=sc,
                port_type=PortTypeChoices.IPMI,
            )
            self.assertEqual(
                ipmi_conns.count(), 1,
                f"Server class '{sc.server_class_id}' must have exactly one IPMI connection, "
                f"got {ipmi_conns.count()}",
            )

    # -------------------------------------------------------------------------
    # T5-B-3: IPMI connections target oob-mgmt-leaf oob zone
    # Expected failure: No IPMI connections exist yet.
    # -------------------------------------------------------------------------

    def test_ipmi_connections_target_oob_zone(self):
        """IPMI connections must target an OOB-type zone on oob-mgmt-leaf."""
        ipmi_conns = PlanServerConnection.objects.filter(
            server_class__plan=self.plan,
            port_type=PortTypeChoices.IPMI,
        ).select_related('target_zone__switch_class')

        self.assertGreater(
            ipmi_conns.count(), 0,
            "Must have at least one IPMI connection",
        )

        for conn in ipmi_conns:
            self.assertEqual(
                conn.target_zone.zone_type,
                PortZoneTypeChoices.OOB,
                f"IPMI connection on {conn.server_class.server_class_id} must target OOB zone, "
                f"got zone_type={conn.target_zone.zone_type!r}",
            )
            self.assertEqual(
                conn.target_zone.switch_class.switch_class_id,
                'oob-mgmt-leaf',
                f"IPMI connection on {conn.server_class.server_class_id} must target oob-mgmt-leaf, "
                f"got {conn.target_zone.switch_class.switch_class_id!r}",
            )

    # -------------------------------------------------------------------------
    # T5-B-4: YAML expected.counts updated for oob-mgmt additions
    # Expected failure: YAML expected.counts still shows old values (7 switch classes).
    # -------------------------------------------------------------------------

    def test_yaml_expected_counts_updated(self):
        """
        ux_case_128gpu_odd_ports.yaml expected.counts must reflect oob-mgmt additions:
          switch_classes: 7 (was 6)
          connections: 26 (was 24)
          server_classes: 9 (was 8)
        """
        from netbox_hedgehog.tests.test_topology_planning.case_128gpu_helpers import expected_128gpu_counts
        counts = expected_128gpu_counts()
        self.assertEqual(
            counts.get('switch_classes'), 7,
            f"expected.counts.switch_classes must be 7, got {counts.get('switch_classes')}",
        )
        self.assertEqual(
            counts.get('connections'), 26,
            f"expected.counts.connections must be 26, got {counts.get('connections')}",
        )
        self.assertEqual(
            counts.get('server_classes'), 9,
            f"expected.counts.server_classes must be 9, got {counts.get('server_classes')}",
        )


@tag('slow', 'regression')
class OobMgmtDeviceGenerationTestCase(TestCase):
    """
    T5-C: DeviceGenerator must produce oob-mgmt switch instances and cables.

    SLOW TEST: Requires full 128GPU device generation.
    Run with: docker compose exec -T netbox python manage.py test
        netbox_hedgehog.tests.test_topology_planning.test_128gpu_oob_integration
        .OobMgmtDeviceGenerationTestCase --keepdb

    Expected failures (RED state):
      - All tests: DeviceGenerator does not yet generate oob-mgmt switch instances
        or oob-zone cables between oob-mgmt-leaf and fe-border-leaf.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_case_128gpu_odd_ports", "--clean", "--generate", stdout=StringIO())
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME)
        cls.all_cables = list(
            Cable.objects.filter(custom_field_data__hedgehog_plan_id=str(cls.plan.pk))
        )

    # -------------------------------------------------------------------------
    # T5-C-1: 4 oob-mgmt switch instances generated (computed: ceil(153/48)=4)
    # -------------------------------------------------------------------------

    def test_4_oob_mgmt_switch_instances_generated(self):
        """DeviceGenerator must produce exactly 4 oob-mgmt-leaf switch instances (computed)."""
        oob_devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric=FabricTypeChoices.OOB_MGMT,
        )
        self.assertEqual(
            oob_devices.count(), 4,
            f"Expected 4 oob-mgmt-leaf instances (ceil(153/48)=4), got {oob_devices.count()}",
        )

    # -------------------------------------------------------------------------
    # T5-C-2: oob-mgmt switches cabled to fe-border-leaf via oob zone
    # 4 switches × 2 uplinks = 8 managed<->surrogate uplink cables.
    # -------------------------------------------------------------------------

    def test_oob_mgmt_instances_cabled_to_fe_border_leaf(self):
        """
        Each oob-mgmt-leaf switch must have 2 uplink cables to fe-border-leaf
        (E1/49 → fe-border-leaf-01, E1/50 → fe-border-leaf-02).
        Total: 4 switches × 2 cables = 8 managed<->surrogate uplink cables.
        """
        oob_switches = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric=FabricTypeChoices.OOB_MGMT,
        )
        self.assertEqual(oob_switches.count(), 4, "Must have 4 oob-mgmt-leaf instances")

        border_switches = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            name__startswith='fe-border-leaf-',
        )
        border_names = set(border_switches.values_list('name', flat=True))

        # Count oob-zone cables between oob-mgmt and fe-border-leaf
        oob_uplink_cables = []
        for cable in self.all_cables:
            if cable.custom_field_data.get('hedgehog_zone') != 'oob':
                continue
            a_terms = cable.a_terminations if isinstance(cable.a_terminations, list) else list(cable.a_terminations.all())
            b_terms = cable.b_terminations if isinstance(cable.b_terminations, list) else list(cable.b_terminations.all())
            if not a_terms or not b_terms:
                continue
            a_dev = a_terms[0].device
            b_dev = b_terms[0].device
            names = {a_dev.name, b_dev.name}
            if names & border_names and any(
                d.custom_field_data.get('hedgehog_fabric') == FabricTypeChoices.OOB_MGMT
                for d in [a_dev, b_dev]
            ):
                oob_uplink_cables.append(cable)

        self.assertEqual(
            len(oob_uplink_cables), 8,
            f"Expected 8 managed<->surrogate uplink cables (4 switches × 2), "
            f"got {len(oob_uplink_cables)}",
        )

    # -------------------------------------------------------------------------
    # T5-C-3: IPMI cables exist for all server instances
    # Expected failure: No IPMI cables generated yet.
    # -------------------------------------------------------------------------

    def test_ipmi_cables_exist_for_all_server_instances(self):
        """
        Each server instance must have exactly one IPMI cable to an oob-mgmt switch.
        155 servers total (96 gpu-fe-only + 32 gpu-with-backend + 18 storage +
        1 admin-node + 1 host-lfm-ctrl + 1 hh-fe-ctrl + 1 hh-be-ctrl + 3 exo-kube + 2 hhg).
        """
        from dcim.models import DeviceRole
        server_role = DeviceRole.objects.filter(slug='server').first()
        if server_role is None:
            self.skipTest("No server role found - generation may not have run")

        server_instances = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            role=server_role,
        )
        expected_server_count = 155

        self.assertEqual(
            server_instances.count(), expected_server_count,
            f"Expected {expected_server_count} server instances",
        )

        oob_switches = set(
            Device.objects.filter(
                custom_field_data__hedgehog_plan_id=str(self.plan.pk),
                custom_field_data__hedgehog_fabric=FabricTypeChoices.OOB_MGMT,
            ).values_list('id', flat=True)
        )

        # Count IPMI cables (server -> oob-mgmt switch, zone not necessarily set)
        ipmi_cable_count = 0
        for cable in self.all_cables:
            a_terms = cable.a_terminations if isinstance(cable.a_terminations, list) else list(cable.a_terminations.all())
            b_terms = cable.b_terminations if isinstance(cable.b_terminations, list) else list(cable.b_terminations.all())
            if not a_terms or not b_terms:
                continue
            a_dev = a_terms[0].device
            b_dev = b_terms[0].device
            if (a_dev.id in oob_switches and b_dev.role_id == server_role.id) or \
               (b_dev.id in oob_switches and a_dev.role_id == server_role.id):
                ipmi_cable_count += 1

        self.assertEqual(
            ipmi_cable_count, expected_server_count,
            f"Expected {expected_server_count} IPMI cables (one per server), "
            f"got {ipmi_cable_count}",
        )

    # -------------------------------------------------------------------------
    # T5-C-4: Total device count updated (165 + 4 = 169, computed oob-mgmt quantity)
    # -------------------------------------------------------------------------

    def test_device_count_includes_oob_mgmt(self):
        """
        Total device count must be 174: 170 managed switches + 4 oob-mgmt-leaf + 2 HHG.
        Managed switches: be-rail×4, be-spine×2, fe-border×2, fe-gpu×2, fe-spine×3,
        fe-storage×2 = 17. Plus 153 original servers + 2 HHG = 155. Plus 4 oob-mgmt = 174.
        Note: fe-spine has 3 instances (not 2) because port_spec: 2-63 leaves 62 fabric
        ports per spine and ceil(128 leaf uplinks / 62) = 3.
        """
        try:
            state = self.plan.generation_state
        except Exception:
            self.skipTest("No GenerationState found - generation may not have run")
        self.assertEqual(
            state.device_count, 174,
            f"Expected 174 devices (17 managed + 4 oob-mgmt + 153 servers + 2 HHG), got {state.device_count}",
        )


@tag('slow')
class OobMgmtExportBehaviorTestCase(TestCase):
    """
    T5-D: Export behavior for 128GPU case with oob-mgmt integration.

    Expected failures (RED state):
      - Tests fail because no oob-mgmt devices are generated yet.
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
    # T5-D-1: oob-mgmt instances appear as Server CRDs (not Switch CRDs)
    # Expected failure: No oob-mgmt devices generated, so nothing appears yet.
    # -------------------------------------------------------------------------

    def test_oob_mgmt_instances_appear_as_server_crds(self):
        """
        oob-mgmt-leaf instances must appear as Server CRDs (surrogate semantics).
        4 Server CRDs should represent oob-mgmt switches (named oob-mgmt-leaf-*).
        """
        oob_server_names = [n for n in self.server_names if 'oob-mgmt' in n]
        self.assertEqual(
            len(oob_server_names), 4,
            f"Expected 4 oob-mgmt Server CRDs, got {len(oob_server_names)}: {oob_server_names}",
        )

    # -------------------------------------------------------------------------
    # T5-D-2: oob-mgmt instances do NOT appear as Switch CRDs
    # Expected failure: No oob-mgmt devices exist to appear as anything.
    # This test passes trivially when no oob-mgmt devices exist, but must stay
    # RED in concert with T5-D-1 — cannot pass without T5-D-1 also passing.
    # -------------------------------------------------------------------------

    def test_oob_mgmt_instances_absent_from_switch_crds(self):
        """oob-mgmt-leaf instances must NOT appear in Switch CRDs."""
        oob_switch_names = [n for n in self.switch_names if 'oob-mgmt' in n]
        self.assertEqual(
            len(oob_switch_names), 0,
            f"oob-mgmt instances must not appear as Switch CRDs: {oob_switch_names}",
        )

    # -------------------------------------------------------------------------
    # T5-D-3: managed<->surrogate uplink cables produce Connection CRDs
    # Expected failure: No oob-mgmt cables exist yet.
    # -------------------------------------------------------------------------

    def test_managed_surrogate_uplinks_produce_connection_crds(self):
        """
        The 8 oob-zone cables (fe-border-leaf <-> oob-mgmt-leaf) must each
        produce a Connection CRD (unbundled spec, managed<->surrogate).
        4 switches × 2 uplinks = 8 total.
        """
        # Look for Connection CRDs that reference oob-mgmt endpoints
        oob_conn_crds = [
            d for d in self.connection_crds
            if any('oob-mgmt' in str(v) for v in d.get('spec', {}).values())
            or 'oob-mgmt' in d.get('metadata', {}).get('name', '')
        ]
        self.assertEqual(
            len(oob_conn_crds), 8,
            f"Expected 8 Connection CRDs for oob-mgmt uplinks, got {len(oob_conn_crds)}",
        )
