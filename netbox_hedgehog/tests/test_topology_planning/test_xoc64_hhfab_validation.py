"""
RED tests for XOC-64 hhfab per-fabric wiring validation failures (DIET-577).

Two concrete bugs in yaml_generator.py reproduced via a minimal XOC-64-shaped
seeded fixture:

  Bug A — low-speed portBreakouts (inb-mgmt):
    SFP28-25G ports emit portBreakouts entries. hhfab rejects them because the
    DS2000 SFP28-25G profile is a Speed-only profile with no sub-lane breakout.
    Fix: from_speed < 100 → portSpeeds, from_speed >= 100 → portBreakouts.

  Bug B — device name normalization (soc-storage-scale-out):
    Connection CRD port refs use raw NetBox device names (underscores intact).
    Switch CRD names are sanitized (underscores → hyphens). hhfab does exact-name
    match → "switch not found". Fix: sanitize device names in all _create_*_crd()
    port reference strings.

Class A (XOC64PortConfigStructuralTestCase):
  Always-run structural assertions on the exported YAML shape. No hhfab required.

Class B (XOC64HHFabValidationGateTestCase):
  Calls hhfab.validate_yaml() and asserts success. @skipUnless(hhfab_available).
  These tests currently FAIL because the artifacts are hhfab-invalid.
"""

import unittest
import yaml

from dcim.models import DeviceRole, DeviceType, InterfaceTemplate, Manufacturer, Site
from django.test import TestCase

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricClassChoices,
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
from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

class _XOC64FixtureBase(TestCase):
    """
    Minimal XOC-64-shaped plan with two MANAGED fabrics:

      inb-mgmt     — DS2000 switch (SFP28-25G, from_speed=25, breakout_id='1x25g')
                     switch_class_id='inb_mgmt_leaf'
                     device name: 'inb_mgmt_leaf-01'  (slugify keeps underscores)
                     CRD name:    'inb-mgmt-leaf-01'  (_sanitize_name replaces _ → -)

      soc-storage-scale-out — DS5000 switch (OSFP, from_speed=800, breakout_id='4x200g')
                     switch_class_id='soc_storage_scale_out_leaf'
                     device name: 'soc_storage_scale_out_leaf-01'
                     CRD name:    'soc-storage-scale-out-leaf-01'

    Both fabrics are explicitly set as FabricClassChoices.MANAGED so they appear
    as Switch CRDs and are discoverable by the managed-fabric resolution logic.
    """

    INB_FABRIC = 'inb-mgmt'
    SOC_FABRIC = 'soc-storage-scale-out'

    @classmethod
    def setUpTestData(cls):
        # --- Manufacturers (unique slugs to avoid inter-test conflicts) ---
        celestica, _ = Manufacturer.objects.get_or_create(
            name='Celestica-XOC64Red',
            defaults={'slug': 'celestica-xoc64-red'},
        )
        nvidia, _ = Manufacturer.objects.get_or_create(
            name='NVIDIA-XOC64Red',
            defaults={'slug': 'nvidia-xoc64-red'},
        )

        # --- DS2000 DeviceType (inb-mgmt switch, SFP28-25G) ---
        cls.ds2000_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=celestica,
            model='DS2000-XOC64Red',
            defaults={'slug': 'celestica-ds2000-xoc64-red'},
        )

        # --- DS5000 DeviceType (soc-storage switch, OSFP-800G) ---
        cls.ds5000_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=celestica,
            model='DS5000-XOC64Red',
            defaults={'slug': 'celestica-ds5000-xoc64-red'},
        )

        # --- Generic server DeviceType ---
        cls.server_dt, _ = DeviceType.objects.get_or_create(
            manufacturer=nvidia,
            model='XPU-Server-XOC64Red',
            defaults={'slug': 'xpu-server-xoc64-red'},
        )

        # --- NIC ModuleType for inb-mgmt connections (SFP28 NIC, 1 port) ---
        from dcim.models import ModuleType
        cls.inb_nic_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=nvidia,
            model='SFP28-NIC-XOC64Red',
        )
        InterfaceTemplate.objects.get_or_create(
            module_type=cls.inb_nic_mt,
            name='p0',
            defaults={'type': 'other'},
        )

        # --- NIC ModuleType for soc-storage connections (OSFP NIC, 1 port) ---
        cls.soc_nic_mt, _ = ModuleType.objects.get_or_create(
            manufacturer=nvidia,
            model='OSFP-NIC-XOC64Red',
        )
        InterfaceTemplate.objects.get_or_create(
            module_type=cls.soc_nic_mt,
            name='p0',
            defaults={'type': 'other'},
        )

        # --- DeviceTypeExtension: DS2000 (SFP28-25G profile) ---
        cls.ds2000_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.ds2000_dt,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'native_speed': 25,
                'supported_breakouts': ['1x25g'],
                'uplink_ports': 0,
                'hedgehog_profile_name': 'celestica-ds2000',
            },
        )

        # --- DeviceTypeExtension: DS5000 (OSFP-800G profile) ---
        cls.ds5000_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.ds5000_dt,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'native_speed': 800,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g'],
                'uplink_ports': 0,
                'hedgehog_profile_name': 'celestica-ds5000',
            },
        )

        # --- BreakoutOptions ---
        cls.bo_1x25, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x25g',
            defaults={'from_speed': 25, 'logical_ports': 1, 'logical_speed': 25},
        )
        cls.bo_4x200, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g',
            defaults={'from_speed': 800, 'logical_ports': 4, 'logical_speed': 200},
        )

        # --- Site + Roles ---
        cls.site, _ = Site.objects.get_or_create(
            name='XOC64Red-Site',
            defaults={'slug': 'xoc64-red-site'},
        )
        cls.server_role, _ = DeviceRole.objects.get_or_create(
            slug='server',
            defaults={'name': 'Server', 'color': 'aa1409'},
        )

        # --- Plan ---
        cls.plan = TopologyPlan.objects.create(
            name='XOC64 RED Validation Test Plan',
            customer_name='XOC64 RED',
        )

        # ==================================================================
        # inb-mgmt fabric: DS2000, SFP28-25G, switch_class_id has underscores
        # Device name:  inb_mgmt_leaf-01  (slugify preserves underscores)
        # CRD name:     inb-mgmt-leaf-01  (_sanitize_name converts _ → -)
        # ==================================================================
        cls.inb_switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='inb_mgmt_leaf',
            fabric_name=cls.INB_FABRIC,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ds2000_ext,
            uplink_ports_per_switch=0,
            mclag_pair=False,
            calculated_quantity=1,
            override_quantity=1,
        )
        cls.inb_zone = SwitchPortZone.objects.create(
            switch_class=cls.inb_switch_class,
            zone_name='inb_mgmt_server_25g',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-24',
            breakout_option=cls.bo_1x25,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )

        cls.inb_server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='inb_mgmt_server',
            server_device_type=cls.server_dt,
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            gpus_per_server=0,
        )
        cls.inb_nic = PlanServerNIC.objects.create(
            server_class=cls.inb_server_class,
            nic_id='inb_mgmt',
            module_type=cls.inb_nic_mt,
        )
        PlanServerConnection.objects.create(
            server_class=cls.inb_server_class,
            connection_id='inb-mgmt-conn',
            nic=cls.inb_nic,
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_zone=cls.inb_zone,
            speed=25,
        )

        # ==================================================================
        # soc-storage-scale-out fabric: DS5000, OSFP-800G
        # switch_class_id='soc_storage_scale_out_leaf'
        # Device name:  soc_storage_scale_out_leaf-01  (underscores!)
        # CRD name:     soc-storage-scale-out-leaf-01  (sanitized, hyphens)
        # Connection port ref: soc_storage_scale_out_leaf-01/E1/1  (BUG: raw name)
        # ==================================================================
        cls.soc_switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='soc_storage_scale_out_leaf',
            fabric_name=cls.SOC_FABRIC,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ds5000_ext,
            uplink_ports_per_switch=0,
            mclag_pair=False,
            calculated_quantity=1,
            override_quantity=1,
        )
        cls.soc_zone = SwitchPortZone.objects.create(
            switch_class=cls.soc_switch_class,
            zone_name='soc_storage_server_4x200',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-32',
            breakout_option=cls.bo_4x200,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )

        cls.soc_server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='soc_storage_server',
            server_device_type=cls.server_dt,
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            gpus_per_server=0,
        )
        cls.soc_nic = PlanServerNIC.objects.create(
            server_class=cls.soc_server_class,
            nic_id='soc_storage',
            module_type=cls.soc_nic_mt,
        )
        PlanServerConnection.objects.create(
            server_class=cls.soc_server_class,
            connection_id='soc-storage-conn',
            nic=cls.soc_nic,
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_zone=cls.soc_zone,
            speed=200,
        )

        # --- Generate all devices (creates switch and server devices + cables) ---
        generator = DeviceGenerator(plan=cls.plan, site=cls.site)
        generator.generate_all()

    # --- Helpers ---

    def _parse_fabric_yaml(self, fabric_name):
        """Export YAML for one fabric and return parsed documents as list."""
        content = generate_yaml_for_plan(self.plan, fabric=fabric_name)
        return [doc for doc in yaml.safe_load_all(content) if isinstance(doc, dict)]

    def _switch_crds(self, docs):
        return [d for d in docs if d.get('kind') == 'Switch']

    def _connection_crds(self, docs):
        return [d for d in docs if d.get('kind') == 'Connection']

    def _all_switch_port_refs(self, conn_crds):
        """Collect all switch-side port reference strings from Connection CRDs."""
        refs = []
        for crd in conn_crds:
            spec = crd.get('spec', {})
            for conn_type in ('unbundled', 'bundled', 'mclag', 'eslag', 'fabric', 'mesh'):
                block = spec.get(conn_type, {})
                # unbundled: spec.unbundled.link.switch.port
                if conn_type == 'unbundled':
                    port = block.get('link', {}).get('switch', {}).get('port', '')
                    if port:
                        refs.append(port)
                # bundled/mclag/eslag: spec.*.links[].switch.port
                elif conn_type in ('bundled', 'mclag', 'eslag'):
                    for link in block.get('links', []):
                        port = link.get('switch', {}).get('port', '')
                        if port:
                            refs.append(port)
                # fabric: spec.fabric.links[].leaf.port / .spine.port
                elif conn_type == 'fabric':
                    for link in block.get('links', []):
                        for side in ('leaf', 'spine'):
                            port = link.get(side, {}).get('port', '')
                            if port:
                                refs.append(port)
                # mesh: spec.mesh.links[].leaf1.port / .leaf2.port
                elif conn_type == 'mesh':
                    for link in block.get('links', []):
                        for side in ('leaf1', 'leaf2'):
                            port = link.get(side, {}).get('port', '')
                            if port:
                                refs.append(port)
        return refs


# ---------------------------------------------------------------------------
# Class A: Structural assertions (no hhfab required)
# ---------------------------------------------------------------------------

class XOC64PortConfigStructuralTestCase(_XOC64FixtureBase):
    """
    Always-run structural assertions proving the two bug shapes.

    These tests FAIL in the current RED state and will PASS after GREEN.

    Bug A (portBreakouts on SFP28): inb-mgmt Switch CRD currently emits
    portBreakouts entries for SFP28-25G ports. hhfab rejects those because the
    DS2000 SFP28-25G port profile has no sub-lane breakout capability.

    Bug B (raw device names): soc-storage-scale-out Connection CRDs currently
    embed the raw NetBox device name (underscores) in switch port refs. The
    Switch CRD name is sanitized (hyphens). hhfab exact-match → "switch not found".
    """

    # --- Bug A: inb-mgmt portBreakouts / portSpeeds ---

    def test_inb_mgmt_sfp28_ports_absent_from_portBreakouts(self):
        """
        RED: SFP28-25G ports must NOT appear in portBreakouts.

        Currently FAILS because _generate_port_configuration() unconditionally
        emits all breakout_option zones into portBreakouts, regardless of from_speed.
        After GREEN: from_speed=25 < 100 → portSpeeds, portBreakouts is absent.
        """
        docs = self._parse_fabric_yaml(self.INB_FABRIC)
        switches = self._switch_crds(docs)
        self.assertEqual(len(switches), 1,
                         f"Expected 1 Switch CRD for {self.INB_FABRIC}, got {len(switches)}")
        switch_spec = switches[0].get('spec', {})
        port_breakouts = switch_spec.get('portBreakouts', {})
        # Zone port_spec='1-24' means E1/1 through E1/24 should NOT be in portBreakouts.
        for port_num in range(1, 25):
            key = f'E1/{port_num}'
            self.assertNotIn(
                key, port_breakouts,
                f"SFP28-25G port {key} must not appear in portBreakouts "
                f"(from_speed=25 < 100 → portSpeeds). Current value: {port_breakouts.get(key)}"
            )

    def test_inb_mgmt_portSpeeds_populated_for_sfp28_zone(self):
        """
        RED: inb-mgmt Switch CRD portSpeeds must be non-empty.

        Currently FAILS because _generate_port_configuration() always returns
        portSpeeds={} regardless of from_speed.
        After GREEN: portSpeeds is populated with entries for every SFP28 port.
        """
        docs = self._parse_fabric_yaml(self.INB_FABRIC)
        switches = self._switch_crds(docs)
        self.assertEqual(len(switches), 1)
        switch_spec = switches[0].get('spec', {})
        port_speeds = switch_spec.get('portSpeeds', {})
        self.assertNotEqual(
            port_speeds, {},
            "portSpeeds must not be empty for a Switch with only SFP28-25G zones. "
            "Currently FAILS because portSpeeds is always {} in the broken generator."
        )

    def test_inb_mgmt_portSpeeds_value_is_bare_speed_string(self):
        """
        RED: portSpeeds values must be bare speed strings like '25G', not '1x25G'.

        hhfab's Speed profile expects a bare string ('10G', '25G', '100G') not
        breakout notation. This test fails in the RED state because portSpeeds is
        empty; after GREEN, portSpeeds is populated and the format is checked.
        """
        docs = self._parse_fabric_yaml(self.INB_FABRIC)
        switches = self._switch_crds(docs)
        self.assertEqual(len(switches), 1)
        switch_spec = switches[0].get('spec', {})
        port_speeds = switch_spec.get('portSpeeds', {})
        # Failing condition: portSpeeds is {} → assertNotEqual({}, {}) passes, but
        # the meaningful check requires at least one entry to be present.
        self.assertNotEqual(
            port_speeds, {},
            "portSpeeds must not be empty (RED: currently always {})"
        )
        for port_key, speed_val in port_speeds.items():
            self.assertEqual(
                speed_val, '25G',
                f"portSpeeds['{port_key}'] = '{speed_val}': must be bare '25G', "
                f"not breakout notation like '1x25G'"
            )

    def test_inb_mgmt_portSpeeds_covers_all_sfp28_zone_ports(self):
        """
        RED: Every port in the SFP28 zone (E1/1–E1/24) must appear in portSpeeds.

        After GREEN, portSpeeds has one entry per port in port_spec '1-24'.
        """
        docs = self._parse_fabric_yaml(self.INB_FABRIC)
        switches = self._switch_crds(docs)
        self.assertEqual(len(switches), 1)
        switch_spec = switches[0].get('spec', {})
        port_speeds = switch_spec.get('portSpeeds', {})
        for port_num in range(1, 25):
            key = f'E1/{port_num}'
            self.assertIn(
                key, port_speeds,
                f"portSpeeds must have an entry for {key} (SFP28-25G zone port_spec='1-24'). "
                f"Currently FAILS because portSpeeds is always empty."
            )

    # --- Bug B: soc-storage-scale-out name normalization ---

    def test_soc_storage_connection_switch_ref_has_no_underscores_in_device_name(self):
        """
        RED: Switch port refs in Connection CRDs must not contain underscores in
        the device-name prefix.

        Currently FAILS: _create_unbundled_crd() uses raw device.name
        ('soc_storage_scale_out_leaf-01') in the port ref. The Switch CRD name
        is sanitized ('soc-storage-scale-out-leaf-01'). hhfab exact-match fails.

        After GREEN: port refs use _sanitize_name(device.name) or the CRD name
        map, so the device-name prefix has hyphens only.
        """
        docs = self._parse_fabric_yaml(self.SOC_FABRIC)
        conn_crds = self._connection_crds(docs)
        self.assertGreater(
            len(conn_crds), 0,
            f"Expected at least 1 Connection CRD in {self.SOC_FABRIC} export"
        )
        switch_refs = self._all_switch_port_refs(conn_crds)
        self.assertGreater(
            len(switch_refs), 0,
            "Expected at least one switch port ref in Connection CRDs"
        )
        for port_ref in switch_refs:
            device_name_prefix = port_ref.split('/')[0]
            self.assertNotIn(
                '_', device_name_prefix,
                f"Switch port ref device-name prefix must not contain underscores. "
                f"Got: '{port_ref}' (prefix: '{device_name_prefix}'). "
                f"Currently FAILS because raw NetBox names are used instead of sanitized CRD names."
            )

    def test_soc_storage_connection_switch_ref_matches_switch_crd_name(self):
        """
        RED: The device-name prefix in Connection CRD switch port refs must exactly
        match the Switch CRD metadata.name for that switch.

        Currently FAILS: Switch CRD name is 'soc-storage-scale-out-leaf-01' but
        Connection port ref prefix is 'soc_storage_scale_out_leaf-01'.
        After GREEN: both are 'soc-storage-scale-out-leaf-01'.
        """
        docs = self._parse_fabric_yaml(self.SOC_FABRIC)
        switch_crd_names = {
            d['metadata']['name'] for d in self._switch_crds(docs)
        }
        self.assertGreater(
            len(switch_crd_names), 0,
            f"Expected at least 1 Switch CRD in {self.SOC_FABRIC} export"
        )
        conn_crds = self._connection_crds(docs)
        switch_refs = self._all_switch_port_refs(conn_crds)
        self.assertGreater(len(switch_refs), 0, "Expected at least one switch port ref")

        for port_ref in switch_refs:
            device_name_prefix = port_ref.split('/')[0]
            self.assertIn(
                device_name_prefix,
                switch_crd_names,
                f"Connection switch port ref prefix '{device_name_prefix}' not found in "
                f"Switch CRD names {switch_crd_names}. "
                f"Currently FAILS because raw names (underscores) don't match sanitized CRD names (hyphens)."
            )

    def test_soc_storage_switch_crd_name_is_already_sanitized(self):
        """
        Structural sanity: the Switch CRD name must already be sanitized (hyphens only).

        This asserts that Fix B's target state is achievable: the Switch CRD name
        is correct already (always was), and only Connection refs are broken.
        This test passes in both RED and GREEN states.
        """
        docs = self._parse_fabric_yaml(self.SOC_FABRIC)
        switches = self._switch_crds(docs)
        self.assertEqual(len(switches), 1)
        crd_name = switches[0]['metadata']['name']
        self.assertNotIn(
            '_', crd_name,
            f"Switch CRD metadata.name must not contain underscores. Got: '{crd_name}'"
        )
        self.assertEqual(
            crd_name,
            'soc-storage-scale-out-leaf-01',
            f"Expected 'soc-storage-scale-out-leaf-01', got '{crd_name}'"
        )


# ---------------------------------------------------------------------------
# Class B: hhfab validation gate (requires hhfab)
# ---------------------------------------------------------------------------

@unittest.skipUnless(hhfab.is_hhfab_available(), 'hhfab not installed — skipping XOC-64 validation gate')
class XOC64HHFabValidationGateTestCase(_XOC64FixtureBase):
    """
    End-to-end export → hhfab validate tests for the two failing XOC-64 fabrics.

    Both tests currently FAIL because the artifacts are hhfab-invalid.
    After GREEN:
      - inb-mgmt passes: portSpeeds replaces portBreakouts for SFP28 ports.
      - soc-storage-scale-out passes: sanitized device names in Connection port refs.

    Skipped when hhfab is not installed. In CI, hhfab must be present for these
    tests to run (treated as failures if skipped in CI).
    """

    def _assert_hhfab_success(self, success, stdout, stderr, context=''):
        if not success:
            diag = f"\nhhfab stdout:\n{stdout}\nhhfab stderr:\n{stderr}"
            self.fail(
                f"hhfab validate failed{(' for ' + context) if context else ''}.{diag}"
            )

    def test_inb_mgmt_artifact_passes_hhfab_validate(self):
        """
        RED: inb-mgmt per-fabric artifact must pass hhfab validate.

        Currently FAILS with:
          validating *v1beta1.Switch "inb-mgmt-leaf-01":
          port profile SFP28-25G for port E1/15 has no supported breakouts

        After GREEN: portSpeeds replaces portBreakouts for from_speed=25 zones.
        hhfab accepts the Speed-profile entries and validates successfully.
        """
        yaml_content = generate_yaml_for_plan(self.plan, fabric=self.INB_FABRIC)
        success, stdout, stderr = hhfab.validate_yaml(yaml_content)
        self._assert_hhfab_success(success, stdout, stderr, f'{self.INB_FABRIC} per-fabric artifact')

    def test_soc_storage_scale_out_artifact_passes_hhfab_validate(self):
        """
        RED: soc-storage-scale-out per-fabric artifact must pass hhfab validate.

        Currently FAILS with:
          validating *v1beta1.Connection "...-unbundled--soc-storage-sca":
          switch soc_storage_scale_out_leaf-01 not found

        After GREEN: Connection port refs use sanitized device names matching the
        Switch CRD name. hhfab exact-match succeeds.
        """
        yaml_content = generate_yaml_for_plan(self.plan, fabric=self.SOC_FABRIC)
        success, stdout, stderr = hhfab.validate_yaml(yaml_content)
        self._assert_hhfab_success(success, stdout, stderr, f'{self.SOC_FABRIC} per-fabric artifact')
