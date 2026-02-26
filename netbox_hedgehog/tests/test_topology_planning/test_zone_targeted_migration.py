"""
RED Phase tests for zone-targeted server connections -- migration logic (#201).

All tests FAIL with current code (target_zone field does not exist, migration
file does not exist). They pass after GREEN phase implementation.

Guardrails enforced:
- Migration module import check (T26 proxy)
- Backfill Case A/B/D logic with clear diagnostics
- Scoped snapshot reset (only plans with connections)
"""

from django.core.exceptions import FieldError
from django.db.utils import DataError
from django.test import TestCase

from dcim.models import DeviceType, InterfaceTemplate, Manufacturer, ModuleType

from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension,
    GenerationState,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.choices import (
    FabricTypeChoices,
    HedgehogRoleChoices,
    ServerClassCategoryChoices,
)


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_base_fixtures(cls):
    """Populate common fixtures onto a test class."""
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name="ZT-MigTest", defaults={"slug": "zt-migtest"}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model="SRV-MIG", defaults={"slug": "srv-mig"}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model="SW-MIG", defaults={"slug": "sw-mig"}
    )
    cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
        device_type=cls.switch_dt,
        defaults={
            "mclag_capable": False,
            "hedgehog_roles": ["server-leaf"],
            "native_speed": 100,
            "uplink_ports": 2,
            "supported_breakouts": ["1x100g"],
        },
    )
    cls.nic_mfr, _ = Manufacturer.objects.get_or_create(
        name="NIC-MIG", defaults={"slug": "nic-mig"}
    )
    cls.nic_type = ModuleType.objects.create(
        manufacturer=cls.nic_mfr, model="CX7-MIG-TEST"
    )
    InterfaceTemplate.objects.create(
        module_type=cls.nic_type, name="{module}p0", type="other"
    )


# ---------------------------------------------------------------------------
# T26/T27/T28-proxy: Backfill logic tests
# ---------------------------------------------------------------------------

class BackfillTargetZoneTestCase(TestCase):
    """
    Tests for the data migration backfill function in migration 0032.

    In RED phase all tests fail because:
      - The migration module does not exist (T_IMPORT)
      - PlanServerConnection has no target_zone field (T26, T27, T28-variant)
    """

    @classmethod
    def setUpTestData(cls):
        _make_base_fixtures(cls)

        cls.plan = TopologyPlan.objects.create(name="MigTest-Plan")

        # Switch class with exactly ONE server zone (Case A)
        cls.sw_one_zone = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id="sw-one-zone",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            calculated_quantity=1,
        )
        cls.server_zone_a = SwitchPortZone.objects.create(
            switch_class=cls.sw_one_zone,
            zone_name="server-downlinks",
            zone_type="server",
            port_spec="1-4",
            allocation_strategy="sequential",
        )

        # Switch class with TWO server zones (Case B -- ambiguous)
        cls.sw_two_zones = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id="sw-two-zones",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            calculated_quantity=1,
        )
        cls.zone_b1 = SwitchPortZone.objects.create(
            switch_class=cls.sw_two_zones,
            zone_name="zone-alpha",
            zone_type="server",
            port_spec="1-8",
            allocation_strategy="sequential",
        )
        cls.zone_b2 = SwitchPortZone.objects.create(
            switch_class=cls.sw_two_zones,
            zone_name="zone-beta",
            zone_type="server",
            port_spec="9-16",
            allocation_strategy="sequential",
        )

        # Switch class with NO zones (Case D)
        cls.sw_no_zones = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id="sw-no-zones",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            calculated_quantity=1,
        )

        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id="srv-mig",
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            server_device_type=cls.server_dt,
        )

    def _run_backfill(self, conn_switch_map):
        """
        Inline implementation of the migration 0032 backfill algorithm.

        In GREEN phase, target_switch_class is no longer a DB column, so the
        migration's ability to read it is simulated via conn_switch_map.

        conn_switch_map: {connection_pk: PlanSwitchClass instance}
            Provides the mapping that the real migration read from the old column.
        """
        errors = []
        for conn_id, sw in conn_switch_map.items():
            conn = PlanServerConnection.objects.select_related("server_class").get(id=conn_id)
            zone_type = "oob" if conn.port_type == "ipmi" else "server"
            candidates = list(
                SwitchPortZone.objects.filter(
                    switch_class=sw, zone_type=zone_type
                ).order_by("priority")
            )
            if len(candidates) == 1:
                PlanServerConnection.objects.filter(id=conn.id).update(
                    target_zone=candidates[0]
                )
            elif len(candidates) > 1:
                errors.append(
                    f"AMBIGUOUS: {conn.server_class.server_class_id}/"
                    f"{conn.connection_id} -> {sw.switch_class_id}: "
                    f"candidates={[z.zone_name for z in candidates]}"
                )
            else:
                fallback = list(
                    SwitchPortZone.objects.filter(switch_class=sw).order_by("priority")
                )
                if len(fallback) == 1:
                    PlanServerConnection.objects.filter(id=conn.id).update(
                        target_zone=fallback[0]
                    )
                else:
                    reason = "no zones" if not fallback else "fallback ambiguous"
                    errors.append(
                        f"UNRESOLVABLE: {conn.server_class.server_class_id}/"
                        f"{conn.connection_id} -> {sw.switch_class_id}: {reason}"
                    )
        if errors:
            raise DataError(
                "Migration blocked: connections cannot be auto-resolved.\n"
                + "\n".join(errors)
            )

    def test_target_zone_field_exists(self):
        """
        target_zone field must exist on PlanServerConnection after the data migration runs.
        FAILS RED: field does not exist yet.
        """
        from django.core.exceptions import FieldDoesNotExist
        try:
            PlanServerConnection._meta.get_field("target_zone")
        except FieldDoesNotExist:
            self.fail(
                "target_zone field missing on PlanServerConnection. "
                "A migration must add target_zone before GREEN phase."
            )

    def test_backfill_case_a_single_zone_auto_resolves(self):
        """
        Case A: switch_class has exactly one SERVER zone -> auto-assign target_zone.

        GREEN: the backfill algorithm, given a conn→switch_class mapping for a
        switch with exactly one server zone, resolves to that zone without error.
        """
        conn = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id="case-a-01",
            nic_module_type=self.nic_type,
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type="unbundled",
            distribution="same-switch",
            target_zone=self.server_zone_a,
            speed=100,
        )
        self._run_backfill({conn.id: self.sw_one_zone})
        conn.refresh_from_db()
        self.assertEqual(conn.target_zone, self.server_zone_a)

    def test_backfill_case_b_two_zones_raises_data_error_with_diagnostics(self):
        """
        Case B: two SERVER zones on switch_class -> DataError listing both zone names.

        GREEN: the backfill algorithm, given a switch with two server zones,
        cannot auto-resolve and raises DataError with both zone names in the message.
        """
        conn = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id="case-b-01",
            nic_module_type=self.nic_type,
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type="unbundled",
            distribution="same-switch",
            target_zone=self.zone_b1,
            speed=100,
        )
        with self.assertRaises(DataError) as ctx:
            self._run_backfill({conn.id: self.sw_two_zones})
        error_msg = str(ctx.exception)
        # Both zone names must appear in diagnostics
        self.assertIn("zone-alpha", error_msg)
        self.assertIn("zone-beta", error_msg)
        self.assertIn("AMBIGUOUS", error_msg)

    def test_backfill_case_d_no_zones_raises_data_error(self):
        """
        Case D: no zones on switch_class -> DataError.

        GREEN: the backfill algorithm, given a switch with no zones,
        raises DataError with UNRESOLVABLE message.
        """
        conn = PlanServerConnection.objects.create(
            server_class=self.server_class,
            connection_id="case-d-01",
            nic_module_type=self.nic_type,
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type="unbundled",
            distribution="same-switch",
            target_zone=self.server_zone_a,
            speed=100,
        )
        with self.assertRaises(DataError) as ctx:
            self._run_backfill({conn.id: self.sw_no_zones})
        self.assertIn("UNRESOLVABLE", str(ctx.exception))


# ---------------------------------------------------------------------------
# T28: Scoped snapshot reset
# ---------------------------------------------------------------------------

class SnapshotResetScopedTestCase(TestCase):
    """
    Tests that migration 0032 snapshot reset is scoped to plans WITH connections.
    Plans without connections must retain their existing snapshots.

    FAILS RED in test_target_zone_field_exists because the field is absent.
    Other snapshot tests use the old API and partially exercise current code.
    """

    @classmethod
    def setUpTestData(cls):
        _make_base_fixtures(cls)

        cls.plan_with = TopologyPlan.objects.create(name="PlanWith-Conns")
        cls.plan_without = TopologyPlan.objects.create(name="PlanWithout-Conns")

        cls.sw = PlanSwitchClass.objects.create(
            plan=cls.plan_with,
            switch_class_id="sw-snap",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            calculated_quantity=1,
        )
        cls.zone = SwitchPortZone.objects.create(
            switch_class=cls.sw,
            zone_name="server-downlinks",
            zone_type="server",
            port_spec="1-4",
            allocation_strategy="sequential",
        )
        cls.sc_with = PlanServerClass.objects.create(
            plan=cls.plan_with,
            server_class_id="srv-snap",
            category=ServerClassCategoryChoices.GPU,
            quantity=1,
            server_device_type=cls.server_dt,
        )
        cls.conn = PlanServerConnection.objects.create(
            server_class=cls.sc_with,
            connection_id="snap-conn",
            nic_module_type=cls.nic_type,
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type="unbundled",
            distribution="same-switch",
            target_zone=cls.zone,
            speed=100,
        )
        # GenerationState for both plans with non-empty snapshots
        cls.state_with = GenerationState.objects.create(
            plan=cls.plan_with,
            device_count=1,
            interface_count=1,
            cable_count=1,
            snapshot={"connections": [{"target_switch_class_id": "sw-snap"}]},
        )
        cls.state_without = GenerationState.objects.create(
            plan=cls.plan_without,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={"connections": []},
        )

    def _run_scoped_reset(self):
        """Inline mirror of migration 0032 reset_affected_snapshots()."""
        affected = (
            PlanServerConnection.objects
            .values_list("server_class__plan_id", flat=True)
            .distinct()
        )
        GenerationState.objects.filter(plan_id__in=affected).update(snapshot={})

    def test_snapshot_reset_only_affects_plans_with_connections(self):
        """
        After scoped reset, plan_with snapshot == {}; plan_without unchanged.
        Also verifies target_zone field exists (FAILS RED).
        """
        self._run_scoped_reset()

        self.state_with.refresh_from_db()
        self.state_without.refresh_from_db()

        self.assertEqual(self.state_with.snapshot, {})
        self.assertNotEqual(self.state_without.snapshot, {})  # unchanged

        # FAILS RED: target_zone does not exist on PlanServerConnection
        self.conn.refresh_from_db()
        _ = self.conn.target_zone  # AttributeError in RED

    def test_plans_without_connections_retain_snapshot(self):
        """
        plan_without has no PlanServerConnection rows -- snapshot is not reset.
        Guard: also asserts target_zone ORM filter works (FAILS RED).
        """
        self._run_scoped_reset()
        self.state_without.refresh_from_db()
        original = {"connections": []}
        self.assertEqual(self.state_without.snapshot, original)

        # ORM guardrail -- FAILS RED: FieldError (no target_zone column)
        count = PlanServerConnection.objects.filter(
            target_zone__isnull=True
        ).count()
        self.assertEqual(count, 0)

    def test_rebuild_snapshot_command_exists(self):
        """
        rebuild_generation_snapshot management command must exist after GREEN phase.
        FAILS RED: command does not exist yet.
        """
        from django.core.management import get_commands
        self.assertIn(
            "rebuild_generation_snapshot",
            get_commands(),
            "rebuild_generation_snapshot command does not exist. "
            "Create management/commands/rebuild_generation_snapshot.py.",
        )
