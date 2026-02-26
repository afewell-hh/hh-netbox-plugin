"""
RED phase tests -- zone-targeted connections: generator, ingest, regression (#201).
All tests FAIL with current code. Passes after GREEN phase implementation.
"""
from django.test import TestCase, tag

from dcim.models import (
    Device, DeviceRole, DeviceType, Interface, InterfaceTemplate,
    Manufacturer, ModuleType, Site,
)

from netbox_hedgehog.models.topology_planning import (
    BreakoutOption, DeviceTypeExtension, PlanServerClass,
    PlanServerConnection, PlanSwitchClass, SwitchPortZone, TopologyPlan,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.test_cases.exceptions import TestCaseValidationError
from netbox_hedgehog.choices import (
    FabricTypeChoices, HedgehogRoleChoices, ServerClassCategoryChoices,
    ConnectionDistributionChoices,
)


def _gen_fixtures(cls):
    """Full generation fixtures shared across generator test classes."""
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name="ZT-Gen", defaults={"slug": "zt-gen"})
    cls.nic_mfr, _ = Manufacturer.objects.get_or_create(
        name="NIC-Gen", defaults={"slug": "nic-gen"})
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model="SRV-GEN", defaults={"slug": "srv-gen"})
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model="SW-GEN", defaults={"slug": "sw-gen"})
    cls.ext, _ = DeviceTypeExtension.objects.get_or_create(
        device_type=cls.switch_dt,
        defaults={"mclag_capable": False, "hedgehog_roles": ["server-leaf"],
                  "native_speed": 100, "uplink_ports": 2,
                  "supported_breakouts": ["1x100g"]})
    cls.bo, _ = BreakoutOption.objects.get_or_create(
        breakout_id="1x100g-zt",
        defaults={"from_speed": 100, "logical_ports": 1, "logical_speed": 100})
    cls.nic = ModuleType.objects.create(manufacturer=cls.nic_mfr, model="CX7-GEN-TEST")
    InterfaceTemplate.objects.create(module_type=cls.nic, name="{module}p0", type="other")
    InterfaceTemplate.objects.create(module_type=cls.nic, name="{module}p1", type="other")
    cls.site, _ = Site.objects.get_or_create(
        name="ZT-Site", defaults={"slug": "zt-site"})
    cls.role, _ = DeviceRole.objects.get_or_create(
        name="ZT-Role", defaults={"slug": "zt-role"})


class ZoneTargetedGeneratorTestCase(TestCase):
    """T16-T19: generator uses target_zone directly. FAILS RED."""

    @classmethod
    def setUpTestData(cls):
        _gen_fixtures(cls)
        cls.plan = TopologyPlan.objects.create(name="Gen-Plan")
        cls.sw = PlanSwitchClass.objects.create(
            plan=cls.plan, switch_class_id="sw-gen",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ext, calculated_quantity=1)
        cls.server_zone = SwitchPortZone.objects.create(
            switch_class=cls.sw, zone_name="server-gen",
            zone_type="server", port_spec="1-4",
            allocation_strategy="sequential", breakout_option=cls.bo)
        cls.sc = PlanServerClass.objects.create(
            plan=cls.plan, server_class_id="srv-gen",
            category=ServerClassCategoryChoices.GPU, quantity=1,
            server_device_type=cls.server_dt)
        # Attempt to create connection using NEW API. Fails in RED (no field).
        cls.setup_error = None
        try:
            cls.conn = PlanServerConnection.objects.create(
                server_class=cls.sc, connection_id="gen-01",
                nic_module_type=cls.nic, port_index=0,
                ports_per_connection=1, hedgehog_conn_type="unbundled",
                distribution="same-switch",
                target_zone=cls.server_zone,  # FAILS RED
                speed=100)
        except Exception as e:
            cls.setup_error = e

    def _require_setup(self):
        if self.setup_error:
            self.fail(
                f"Setup failed (expected in RED phase -- target_zone field absent): "
                f"{self.setup_error}")

    def test_generator_select_zone_method_absent(self):
        """T17: _select_zone_for_connection must not exist after GREEN. FAILS RED: it exists."""
        gen = DeviceGenerator(self.plan)
        # FAILS RED: method exists today
        self.assertFalse(
            hasattr(gen, "_select_zone_for_connection"),
            "_select_zone_for_connection still exists; must be deleted in GREEN phase.")

    def test_generator_map_zone_type_method_absent(self):
        """_map_zone_type must not exist after GREEN. FAILS RED: it exists."""
        gen = DeviceGenerator(self.plan)
        # FAILS RED: method exists today
        self.assertFalse(
            hasattr(gen, "_map_zone_type"),
            "_map_zone_type still exists; must be deleted in GREEN phase.")

    def test_generator_uses_target_zone_directly(self):
        """T16: generation routes cables to target_zone port range. FAILS RED: setup fails."""
        self._require_setup()
        gen = DeviceGenerator(self.plan)
        gen.generate_all()
        cables = list(Interface.objects.filter(
            device__name__icontains="sw-gen",
            custom_field_data__hedgehog_zone="server-gen"))
        self.assertGreater(len(cables), 0,
            "No switch-side interfaces tagged with zone 'server-gen'.")

    def test_rail_cache_key_is_per_zone(self):
        """T18: _get_total_rails_for_target cache key is (server_id, zone.pk). FAILS RED."""
        self._require_setup()
        # Create second zone on same switch class for a second rail-optimized connection
        zone2 = SwitchPortZone.objects.create(
            switch_class=self.sw, zone_name="rail-zone2",
            zone_type="server", port_spec="5-8",
            allocation_strategy="sequential", breakout_option=self.bo)
        try:
            conn2 = PlanServerConnection.objects.create(
                server_class=self.sc, connection_id="gen-rail-02",
                nic_module_type=self.nic, port_index=0,
                ports_per_connection=1, hedgehog_conn_type="unbundled",
                distribution="rail-optimized",
                target_zone=zone2, speed=100, rail=0)  # FAILS RED
        except Exception as e:
            self.fail(f"FAILS RED (expected): {e}")
        gen = DeviceGenerator(self.plan)
        # FAILS RED: _get_total_rails_for_target still takes switch_class not zone
        count_z1 = gen._get_total_rails_for_target(self.sc, self.server_zone)
        count_z2 = gen._get_total_rails_for_target(self.sc, zone2)
        key_z1 = (self.sc.server_class_id, self.server_zone.pk)
        key_z2 = (self.sc.server_class_id, zone2.pk)
        self.assertNotEqual(key_z1, key_z2)
        self.assertIn(key_z1, gen._rail_count_cache)
        self.assertIn(key_z2, gen._rail_count_cache)


@tag("regression", "zone-targeted")
class DS3000ZoneRegressionTestCase(TestCase):
    """T20: admin-node routes to 10g-sfp zone; hh-controller routes to server-downlinks. FAILS RED."""

    @classmethod
    def setUpTestData(cls):
        _gen_fixtures(cls)
        cls.plan = TopologyPlan.objects.create(name="DS3000-Regression")
        cls.border_sw = PlanSwitchClass.objects.create(
            plan=cls.plan, switch_class_id="fe-border-leaf",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role="border-leaf",
            device_type_extension=cls.ext, calculated_quantity=1)
        cls.zone_100g = SwitchPortZone.objects.create(
            switch_class=cls.border_sw, zone_name="server-downlinks",
            zone_type="server", port_spec="1-16",
            allocation_strategy="sequential", breakout_option=cls.bo)
        cls.zone_10g = SwitchPortZone.objects.create(
            switch_class=cls.border_sw, zone_name="10g-sfp",
            zone_type="server", port_spec="33",
            allocation_strategy="sequential", breakout_option=cls.bo)
        cls.sc_ctrl = PlanServerClass.objects.create(
            plan=cls.plan, server_class_id="hh-controller",
            category=ServerClassCategoryChoices.GPU, quantity=1,
            server_device_type=cls.server_dt)
        cls.sc_admin = PlanServerClass.objects.create(
            plan=cls.plan, server_class_id="admin-node",
            category=ServerClassCategoryChoices.GPU, quantity=1,
            server_device_type=cls.server_dt)
        cls.setup_error = None
        try:
            PlanServerConnection.objects.create(
                server_class=cls.sc_ctrl, connection_id="fe-border",
                nic_module_type=cls.nic, port_index=0,
                ports_per_connection=1, hedgehog_conn_type="unbundled",
                distribution="same-switch",
                target_zone=cls.zone_100g, speed=100)  # FAILS RED
            PlanServerConnection.objects.create(
                server_class=cls.sc_admin, connection_id="fe-border",
                nic_module_type=cls.nic, port_index=0,
                ports_per_connection=1, hedgehog_conn_type="unbundled",
                distribution="same-switch",
                target_zone=cls.zone_10g, speed=100)  # FAILS RED
        except Exception as e:
            cls.setup_error = e

    def _require_setup(self):
        if self.setup_error:
            self.fail(f"FAILS RED (expected): {self.setup_error}")

    def test_admin_node_routes_to_10g_zone(self):
        """admin-node cables land on zone '10g-sfp' (port 33). FAILS RED: setup fails."""
        self._require_setup()
        gen = DeviceGenerator(self.plan)
        gen.generate_all()
        admin_switch_ifaces = Interface.objects.filter(
            device__name__icontains="fe-border-leaf",
            custom_field_data__hedgehog_zone="10g-sfp")
        self.assertEqual(admin_switch_ifaces.count(), 1,
            "admin-node cable must land on '10g-sfp' zone interface.")

    def test_hh_controller_routes_to_server_downlinks(self):
        """hh-controller cables land on 'server-downlinks'. FAILS RED: setup fails."""
        self._require_setup()
        gen = DeviceGenerator(self.plan)
        gen.generate_all()
        ctrl_ifaces = Interface.objects.filter(
            device__name__icontains="fe-border-leaf",
            custom_field_data__hedgehog_zone="server-downlinks")
        self.assertEqual(ctrl_ifaces.count(), 1,
            "hh-controller cable must land on 'server-downlinks' zone.")

    def test_zones_do_not_collide(self):
        """No cable from admin-node lands on ports 1-16; none from ctrl lands on port 33. FAILS RED."""
        self._require_setup()
        gen = DeviceGenerator(self.plan)
        gen.generate_all()
        # Port 33 must only be used by admin-node
        p33_ifaces = Interface.objects.filter(
            device__name__icontains="fe-border-leaf",
            name__endswith="33")
        for iface in p33_ifaces:
            zone_val = iface.custom_field_data.get("hedgehog_zone", "")
            self.assertEqual(zone_val, "10g-sfp",
                f"Port 33 interface {iface.name} has wrong zone '{zone_val}'.")


class ZoneTargetedIngestTestCase(TestCase):
    """T22-T25: YAML ingest clean break. FAILS RED: old key still accepted."""

    @classmethod
    def setUpTestData(cls):
        _gen_fixtures(cls)

    def _minimal_case(self, connections):
        """Build a minimal but valid case dict with the given connections list."""
        return {
            "meta": {
                "case_id": "zt_ingest_test",
                "name": "Zone-Targeted Ingest Test",
                "version": 1,
                "managed_by": "yaml",
            },
            "plan": {"name": "ZT-Ingest-Plan", "status": "draft"},
            "reference_data": {
                "manufacturers": [{"name": "ZT-Gen", "slug": "zt-gen"}],
                "device_types": [],
                "module_types": [{"manufacturer": "NIC-Gen", "model": "CX7-GEN-TEST"}],
                "breakout_options": [{"breakout_id": "1x100g-zt",
                                      "from_speed": 100, "logical_ports": 1,
                                      "logical_speed": 100}],
                "device_type_extensions": [],
            },
            "switch_classes": [{
                "switch_class_id": "sw-ingest", "fabric": "frontend",
                "hedgehog_role": "server-leaf",
                "device_type_extension": None,
                "calculated_quantity": 1,
            }],
            "switch_port_zones": [{
                "switch_class": "sw-ingest", "zone_name": "server-ingest",
                "zone_type": "server", "port_spec": "1-4",
                "breakout_option": "1x100g-zt",
                "allocation_strategy": "sequential", "priority": 100,
            }],
            "server_classes": [{
                "server_class_id": "srv-ingest", "category": "gpu",
                "quantity": 1, "gpus_per_server": 0,
                "server_device_type": None,
            }],
            "server_connections": connections,
        }

    def test_ingest_target_zone_key_resolves(self):
        """T22: target_zone key resolves correctly. FAILS RED: ingest doesn't handle key."""
        from netbox_hedgehog.test_cases.ingest import apply_case
        case = self._minimal_case([{
            "server_class": "srv-ingest",
            "connection_id": "ingest-01",
            "nic_module_type": "CX7-GEN-TEST",
            "port_index": 0,
            "ports_per_connection": 1,
            "hedgehog_conn_type": "unbundled",
            "distribution": "same-switch",
            "target_zone": "sw-ingest/server-ingest",  # NEW key format
            "speed": 100,
        }])
        try:
            plan = apply_case(case, clean=True, reference_mode="skip")
        except Exception as e:
            self.fail(f"FAILS RED (expected): ingest does not handle target_zone key. {e}")
        conn = PlanServerConnection.objects.filter(connection_id="ingest-01").first()
        self.assertIsNotNone(conn)
        # FAILS RED: target_zone field absent
        self.assertEqual(conn.target_zone.zone_name, "server-ingest")

    def test_ingest_target_switch_class_key_rejected(self):
        """T23: old key raises deprecated_key error. FAILS RED: old key still accepted."""
        from netbox_hedgehog.test_cases.ingest import apply_case
        case = self._minimal_case([{
            "server_class": "srv-ingest",
            "connection_id": "ingest-02",
            "nic_module_type": "CX7-GEN-TEST",
            "port_index": 0,
            "ports_per_connection": 1,
            "hedgehog_conn_type": "unbundled",
            "distribution": "same-switch",
            "target_switch_class": "sw-ingest",  # OLD deprecated key
            "speed": 100,
        }])
        try:
            apply_case(case, clean=True, reference_mode="skip")
        except TestCaseValidationError as e:
            self.assertEqual(e.errors[0]["code"], "deprecated_key",
                f"Expected code='deprecated_key', got '{e.errors[0]['code']}'")
            return
        # FAILS RED: no exception raised (old key still silently accepted)
        self.fail("Expected TestCaseValidationError(deprecated_key) but no error raised. "
                  "FAILS RED: ingest still accepts target_switch_class key.")

    def test_ingest_missing_zone_key_raises_missing_field(self):
        """T24: missing both keys raises missing_field. Partially fails RED."""
        from netbox_hedgehog.test_cases.ingest import apply_case
        case = self._minimal_case([{
            "server_class": "srv-ingest",
            "connection_id": "ingest-03",
            "nic_module_type": "CX7-GEN-TEST",
            "port_index": 0,
            "ports_per_connection": 1,
            "hedgehog_conn_type": "unbundled",
            "distribution": "same-switch",
            "speed": 100,
            # Neither target_zone nor target_switch_class
        }])
        with self.assertRaises(TestCaseValidationError) as ctx:
            apply_case(case, clean=True, reference_mode="skip")
        # FAILS RED: current code raises 'unknown_reference', not 'missing_field'
        self.assertEqual(ctx.exception.errors[0]["code"], "missing_field")

    def test_ingest_unknown_zone_reference_raises_error(self):
        """T25: unknown target_zone raises unknown_reference. FAILS RED: key not handled."""
        from netbox_hedgehog.test_cases.ingest import apply_case
        case = self._minimal_case([{
            "server_class": "srv-ingest",
            "connection_id": "ingest-04",
            "nic_module_type": "CX7-GEN-TEST",
            "port_index": 0,
            "ports_per_connection": 1,
            "hedgehog_conn_type": "unbundled",
            "distribution": "same-switch",
            "target_zone": "nonexistent/no-such-zone",
            "speed": 100,
        }])
        with self.assertRaises(TestCaseValidationError) as ctx:
            apply_case(case, clean=True, reference_mode="skip")
        # FAILS RED: target_zone key not yet parsed
        self.assertEqual(ctx.exception.errors[0]["code"], "unknown_reference")
