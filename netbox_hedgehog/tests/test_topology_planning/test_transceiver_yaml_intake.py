"""
RED tests — DIET-427 Phase 3: Transceiver FK intake from topology-map YAML.

Covers:
- T1: SwitchPortZone.transceiver_module_type populated from YAML
- T2: PlanServerConnection.transceiver_module_type populated from YAML
- T3: Zone FK absent → stays null (backward compat, pre-green)
- T4: Connection FK absent → stays null (backward compat, pre-green)
- T5: Zone unknown ref → TestCaseValidationError unknown_reference
- T6: Connection unknown ref → TestCaseValidationError unknown_reference
- T7: Zone non-transceiver profile → TestCaseValidationError invalid_value
- T8: Connection non-transceiver profile → TestCaseValidationError validation_error
- T9: Compatible zone + connection refs import cleanly, both FKs set

Implementation gate: all tests except T3/T4 must fail before ingest.py is changed.
"""

from __future__ import annotations

import copy

from django.test import TestCase

from netbox_hedgehog.models.topology_planning import (
    PlanServerConnection,
    SwitchPortZone,
)
from netbox_hedgehog.test_cases.exceptions import TestCaseValidationError
from netbox_hedgehog.tests.test_topology_planning import (
    get_test_non_transceiver_module_type,
    get_test_transceiver_module_type,
)


class TransceiverYAMLIntakeTestCase(TestCase):
    """
    Tests that the ingest path correctly populates transceiver_module_type FKs
    from YAML on both SwitchPortZone and PlanServerConnection.

    All module types are resolved through the existing refs["module_types"]
    mechanism. The 'XCVR-Test-Vendor' manufacturer is shared by both
    get_test_transceiver_module_type() and get_test_non_transceiver_module_type().
    """

    @classmethod
    def setUpTestData(cls):
        # Pre-create the ModuleType objects used in tests.
        # get_or_create → safe for --keepdb runs.
        cls.xcvr_mt = get_test_transceiver_module_type()
        # XCVR-QSFP112-MMF-TEST / mfr=XCVR-Test-Vendor
        # profile: Network Transceiver
        # attribute_data: {cage_type: QSFP112, medium: MMF, ...}

        cls.non_xcvr_mt = get_test_non_transceiver_module_type()
        # NON-XCVR-NIC-TEST / mfr=XCVR-Test-Vendor
        # no profile — used for NIC and wrong-profile tests

    def _base_case(self, case_id="xcvr_intake_test"):
        """
        Minimal valid YAML case dict.

        Both transceiver_module_type keys are absent by default.
        Per-test helpers add the key to zone/connection entries as needed.

        Manufacturer 'XCVR-Test-Vendor' (slug: xcvr-test-vendor) resolves to
        the one already created by setUpTestData via get_test_transceiver_module_type().

        module_types:
          xcvr_qsfp_mmf → XCVR-QSFP112-MMF-TEST (Network Transceiver profile)
          nic_non_xcvr  → NON-XCVR-NIC-TEST (no profile; used for NIC and wrong-profile tests)
        """
        return {
            "meta": {
                "case_id": case_id,
                "name": f"Transceiver Intake Test {case_id}",
                "version": 1,
                "managed_by": "yaml",
            },
            "plan": {
                "name": f"Transceiver Intake Plan {case_id}",
                "status": "draft",
            },
            "reference_data": {
                "manufacturers": [
                    {
                        "id": "mfr_xcvr_test",
                        "name": "XCVR-Test-Vendor",
                        "slug": "xcvr-test-vendor",
                    },
                ],
                "device_types": [
                    {
                        "id": "dt_sw",
                        "manufacturer": "mfr_xcvr_test",
                        "model": "SW-XcvrIntake-Test",
                        "slug": "sw-xcvr-intake-test",
                    },
                    {
                        "id": "dt_srv",
                        "manufacturer": "mfr_xcvr_test",
                        "model": "SRV-XcvrIntake-Test",
                        "slug": "srv-xcvr-intake-test",
                    },
                ],
                "device_type_extensions": [
                    {
                        "id": "dte_sw",
                        "device_type": "dt_sw",
                        "hedgehog_roles": ["server-leaf"],
                        "native_speed": 100,
                        "uplink_ports": 0,
                        "supported_breakouts": ["1x100g-xcvr-intake-test"],
                        "mclag_capable": False,
                    },
                ],
                "module_types": [
                    {
                        # Transceiver — has Network Transceiver profile
                        "id": "xcvr_qsfp_mmf",
                        "manufacturer": "mfr_xcvr_test",
                        "model": "XCVR-QSFP112-MMF-TEST",
                    },
                    {
                        # NIC / wrong-profile — no Network Transceiver profile
                        "id": "nic_non_xcvr",
                        "manufacturer": "mfr_xcvr_test",
                        "model": "NON-XCVR-NIC-TEST",
                    },
                ],
                "breakout_options": [
                    {
                        "id": "bo_1x100g",
                        "breakout_id": "1x100g-xcvr-intake-test",
                        "from_speed": 100,
                        "logical_ports": 1,
                        "logical_speed": 100,
                    },
                ],
            },
            "switch_classes": [
                {
                    "switch_class_id": "sw-xcvr-intake",
                    "fabric": "frontend",
                    "hedgehog_role": "server-leaf",
                    "device_type_extension": "dte_sw",
                },
            ],
            "switch_port_zones": [
                {
                    "switch_class": "sw-xcvr-intake",
                    "zone_name": "server-ports",
                    "zone_type": "server",
                    "port_spec": "1-4",
                    "breakout_option": "bo_1x100g",
                    "allocation_strategy": "sequential",
                    "priority": 100,
                    # transceiver_module_type added per-test
                },
            ],
            "server_classes": [
                {
                    "server_class_id": "srv-xcvr-intake",
                    "server_device_type": "dt_srv",
                    "quantity": 1,
                    "gpus_per_server": 0,
                },
            ],
            "server_nics": [
                {
                    "server_class": "srv-xcvr-intake",
                    "nic_id": "fe",
                    "module_type": "nic_non_xcvr",
                },
            ],
            "server_connections": [
                {
                    "server_class": "srv-xcvr-intake",
                    "connection_id": "fe-conn",
                    "connection_name": "frontend",
                    "nic": "fe",
                    "port_index": 0,
                    "ports_per_connection": 1,
                    "hedgehog_conn_type": "unbundled",
                    "distribution": "same-switch",
                    "target_zone": "sw-xcvr-intake/server-ports",
                    "speed": 100,
                    # transceiver_module_type added per-test
                },
            ],
        }

    # ------------------------------------------------------------------
    # T1: Zone FK populated from YAML
    # ------------------------------------------------------------------

    def test_zone_transceiver_fk_populated_from_yaml(self):
        """
        T1: switch_port_zones[*].transceiver_module_type resolves and is persisted
        on SwitchPortZone.transceiver_module_type.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case

        case = self._base_case("t1_zone_fk")
        case["switch_port_zones"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"
        # DIET-466: connection also required so pre-pass doesn't block
        case["server_connections"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"

        plan = apply_case(case, clean=True, reference_mode="ensure")

        zone = SwitchPortZone.objects.filter(
            switch_class__plan=plan,
            zone_name="server-ports",
        ).first()
        self.assertIsNotNone(zone, "SwitchPortZone must exist after ingest")
        self.assertIsNotNone(
            zone.transceiver_module_type,
            "SwitchPortZone.transceiver_module_type must be set when YAML key is present",
        )
        self.assertEqual(
            zone.transceiver_module_type.pk,
            self.xcvr_mt.pk,
            "SwitchPortZone.transceiver_module_type must resolve to the correct ModuleType",
        )

    # ------------------------------------------------------------------
    # T2: Connection FK populated from YAML
    # ------------------------------------------------------------------

    def test_connection_transceiver_fk_populated_from_yaml(self):
        """
        T2: server_connections[*].transceiver_module_type resolves and is persisted
        on PlanServerConnection.transceiver_module_type.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case

        case = self._base_case("t2_conn_fk")
        case["server_connections"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"
        # DIET-466: zone also required so pre-pass doesn't block
        case["switch_port_zones"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"

        apply_case(case, clean=True, reference_mode="ensure")

        conn = PlanServerConnection.objects.filter(connection_id="fe-conn").first()
        self.assertIsNotNone(conn, "PlanServerConnection must exist after ingest")
        self.assertIsNotNone(
            conn.transceiver_module_type,
            "PlanServerConnection.transceiver_module_type must be set when YAML key is present",
        )
        self.assertEqual(
            conn.transceiver_module_type.pk,
            self.xcvr_mt.pk,
            "PlanServerConnection.transceiver_module_type must resolve to the correct ModuleType",
        )

    # ------------------------------------------------------------------
    # T3: Zone FK absent → stays null (pre-green, backward compat)
    # ------------------------------------------------------------------

    def test_zone_transceiver_fk_absent_raises_missing_required(self):
        """
        T3 (DIET-466 update): When transceiver_module_type key is absent from
        switch_port_zones, the DIET-466 mandatory pre-pass raises missing_required.
        The old backward-compat "stays null" behavior is superseded by mandatory enforcement.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case

        case = self._base_case("t3_zone_absent")
        # No transceiver_module_type on zone — mandatory enforcement must block ingest
        case["server_connections"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"

        with self.assertRaises(Exception) as ctx:
            apply_case(case, clean=True, reference_mode="ensure")

        errors = ctx.exception.errors
        self.assertTrue(
            any(e.get("code") == "missing_required" for e in errors),
            f"Expected missing_required when zone xcvr absent, got: {errors}",
        )
        self.assertTrue(
            any("switch_port_zones" in e.get("path", "") for e in errors),
            f"Expected path to reference 'switch_port_zones', got: {errors}",
        )

    # ------------------------------------------------------------------
    # T4: Connection FK absent → stays null (pre-green, backward compat)
    # ------------------------------------------------------------------

    def test_connection_transceiver_fk_absent_raises_missing_required(self):
        """
        T4 (DIET-466 update): When transceiver_module_type key is absent from
        server_connections, the DIET-466 mandatory pre-pass raises missing_required.
        The old backward-compat "stays null" behavior is superseded by mandatory enforcement.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case

        case = self._base_case("t4_conn_absent")
        # No transceiver_module_type on connection — mandatory enforcement must block ingest
        case["switch_port_zones"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"

        with self.assertRaises(Exception) as ctx:
            apply_case(case, clean=True, reference_mode="ensure")

        errors = ctx.exception.errors
        self.assertTrue(
            any(e.get("code") == "missing_required" for e in errors),
            f"Expected missing_required when connection xcvr absent, got: {errors}",
        )
        self.assertTrue(
            any("server_connections" in e.get("path", "") for e in errors),
            f"Expected path to reference 'server_connections', got: {errors}",
        )

    # ------------------------------------------------------------------
    # T5: Zone unknown ref raises TestCaseValidationError
    # ------------------------------------------------------------------

    def test_zone_unknown_transceiver_ref_raises(self):
        """
        T5: When switch_port_zones[*].transceiver_module_type references an ID that
        is not in reference_data.module_types, intake must raise TestCaseValidationError
        with code='unknown_reference' and a path identifying the zone.

        RED: fails before implementation because the key is silently ignored and no
        error is raised.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case

        case = self._base_case("t5_zone_unknown")
        case["switch_port_zones"][0]["transceiver_module_type"] = "does_not_exist"
        # DIET-466: connection needs valid xcvr so pre-pass passes for connections
        case["server_connections"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"

        with self.assertRaises(TestCaseValidationError) as ctx:
            apply_case(case, clean=True, reference_mode="ensure")

        errors = ctx.exception.errors
        self.assertTrue(
            any(e.get("code") == "unknown_reference" for e in errors),
            f"Expected code='unknown_reference' in errors, got: {errors}",
        )
        self.assertTrue(
            any("switch_port_zones" in e.get("path", "") for e in errors),
            f"Expected path to reference 'switch_port_zones', got: {errors}",
        )

    # ------------------------------------------------------------------
    # T6: Connection unknown ref raises TestCaseValidationError
    # ------------------------------------------------------------------

    def test_connection_unknown_transceiver_ref_raises(self):
        """
        T6: When server_connections[*].transceiver_module_type references an ID that
        is not in reference_data.module_types, intake must raise TestCaseValidationError
        with code='unknown_reference' and a path identifying the connection.

        RED: fails before implementation because the key is silently ignored.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case

        case = self._base_case("t6_conn_unknown")
        case["server_connections"][0]["transceiver_module_type"] = "does_not_exist"
        # DIET-466: zone needs valid xcvr so pre-pass passes for zones
        case["switch_port_zones"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"

        with self.assertRaises(TestCaseValidationError) as ctx:
            apply_case(case, clean=True, reference_mode="ensure")

        errors = ctx.exception.errors
        self.assertTrue(
            any(e.get("code") == "unknown_reference" for e in errors),
            f"Expected code='unknown_reference' in errors, got: {errors}",
        )
        self.assertTrue(
            any("server_connections" in e.get("path", "") for e in errors),
            f"Expected path to reference 'server_connections', got: {errors}",
        )

    # ------------------------------------------------------------------
    # T7: Zone non-transceiver profile rejected
    # ------------------------------------------------------------------

    def test_zone_non_transceiver_profile_rejected(self):
        """
        T7: When switch_port_zones[*].transceiver_module_type resolves to a ModuleType
        without the 'Network Transceiver' profile, the inline intake guard must raise
        TestCaseValidationError with code='invalid_value' and a message referencing
        the Network Transceiver profile.

        RED: fails before implementation because no inline guard exists.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case

        case = self._base_case("t7_zone_bad_profile")
        # nic_non_xcvr resolves to NON-XCVR-NIC-TEST — no Network Transceiver profile
        case["switch_port_zones"][0]["transceiver_module_type"] = "nic_non_xcvr"
        # DIET-466: connection needs valid xcvr so pre-pass passes for connections
        case["server_connections"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"

        with self.assertRaises(TestCaseValidationError) as ctx:
            apply_case(case, clean=True, reference_mode="ensure")

        errors = ctx.exception.errors
        self.assertTrue(
            any(e.get("code") == "invalid_value" for e in errors),
            f"Expected code='invalid_value' in errors, got: {errors}",
        )
        self.assertTrue(
            any("Network Transceiver" in e.get("message", "") for e in errors),
            f"Expected 'Network Transceiver' in error message, got: {errors}",
        )

    # ------------------------------------------------------------------
    # T8: Connection non-transceiver profile rejected
    # ------------------------------------------------------------------

    def test_connection_non_transceiver_profile_rejected(self):
        """
        T8: When server_connections[*].transceiver_module_type resolves to a ModuleType
        without the 'Network Transceiver' profile, conn.full_clean() must catch it and
        the ingest must raise TestCaseValidationError with code='validation_error'.

        Note: error code differs from T7 (invalid_value) because the connection path
        relies on full_clean() wrapping rather than an inline guard. This asymmetry is
        intentional per Phase 1 architecture decision.

        RED: fails before implementation because the key is silently ignored and
        full_clean() never sees the invalid module type.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case

        case = self._base_case("t8_conn_bad_profile")
        case["server_connections"][0]["transceiver_module_type"] = "nic_non_xcvr"
        # DIET-466: zone needs valid xcvr so pre-pass passes for zones
        case["switch_port_zones"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"

        with self.assertRaises(TestCaseValidationError) as ctx:
            apply_case(case, clean=True, reference_mode="ensure")

        errors = ctx.exception.errors
        self.assertTrue(
            any(e.get("code") == "validation_error" for e in errors),
            f"Expected code='validation_error' in errors, got: {errors}",
        )
        self.assertTrue(
            any("Network Transceiver" in e.get("message", "") for e in errors),
            f"Expected 'Network Transceiver' in error message, got: {errors}",
        )

    # ------------------------------------------------------------------
    # T9: Compatible zone + connection refs import cleanly, both FKs set
    # ------------------------------------------------------------------

    def test_compatible_zone_and_connection_import_cleanly(self):
        """
        T9: When both switch_port_zones and server_connections carry matching
        transceiver_module_type refs (QSFP112/MMF on both sides), import completes
        without error and both FKs are populated.

        Cross-end compatibility (cage_type=QSFP112 vs QSFP112, medium=MMF vs MMF)
        is validated at intake time by conn.full_clean() (V4/V6, V5/V8). Matching
        types must not raise an error.

        RED: fails before implementation because neither FK is set.
        """
        from netbox_hedgehog.test_cases.ingest import apply_case

        case = self._base_case("t9_compatible")
        case["switch_port_zones"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"
        case["server_connections"][0]["transceiver_module_type"] = "xcvr_qsfp_mmf"

        plan = apply_case(case, clean=True, reference_mode="ensure")

        zone = SwitchPortZone.objects.filter(
            switch_class__plan=plan,
            zone_name="server-ports",
        ).first()
        conn = PlanServerConnection.objects.filter(connection_id="fe-conn").first()

        self.assertIsNotNone(zone, "SwitchPortZone must exist after ingest")
        self.assertIsNotNone(conn, "PlanServerConnection must exist after ingest")

        self.assertIsNotNone(
            zone.transceiver_module_type,
            "SwitchPortZone.transceiver_module_type must be set",
        )
        self.assertEqual(
            zone.transceiver_module_type.pk,
            self.xcvr_mt.pk,
            "SwitchPortZone.transceiver_module_type must be the correct ModuleType",
        )

        self.assertIsNotNone(
            conn.transceiver_module_type,
            "PlanServerConnection.transceiver_module_type must be set",
        )
        self.assertEqual(
            conn.transceiver_module_type.pk,
            self.xcvr_mt.pk,
            "PlanServerConnection.transceiver_module_type must be the correct ModuleType",
        )
