"""
Tests for Option B: explicit redundancy_type required when distribution=alternating.

Issue: #246 — Model validation: distribution=alternating requires redundancy_type on
the target switch class.

Background:
- Option A (#244): calculate_switch_quantity() enforces min 2 at runtime (safety net).
- Option B (this issue): clean() rejects connections at authoring time if the switch
  class lacks redundancy_type, making the HA intent explicit in the model.

Option A remains in place as defense-in-depth fallback.
"""

from io import StringIO

from django.core.exceptions import ValidationError
from django.test import TestCase

from dcim.models import DeviceType, Manufacturer

from netbox_hedgehog.choices import (
    ConnectionTypeChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic


PLAN_NAME_128GPU = "UX Case 128GPU Odd Ports"


class AlternatingRedundancyValidationTestCase(TestCase):
    """
    Unit tests for the model-level validation rule:
    distribution=alternating requires target switch class to have redundancy_type set.
    """

    @classmethod
    def setUpTestData(cls):
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Test-RedV-Mfg', defaults={'slug': 'test-redv-mfg'}
        )
        cls.device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='Test-RedV-Switch',
            defaults={'slug': 'test-redv-switch'},
        )
        cls.breakout_1x100g, _ = BreakoutOption.objects.get_or_create(
            breakout_id='test-redv-1x100g',
            defaults={'from_speed': 100, 'logical_ports': 1, 'logical_speed': 100},
        )
        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.device_type,
            defaults={
                'mclag_capable': False,
                'supported_breakouts': ['test-redv-1x100g'],
                'native_speed': 100,
            },
        )
        cls.server_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='Test-RedV-Server',
            defaults={'slug': 'test-redv-server'},
        )

    def setUp(self):
        self.plan = TopologyPlan.objects.create(
            name=f'RedV-Test-Plan-{self._testMethodName}',
            customer_name='Test Customer',
        )

    def _make_switch_class(self, switch_class_id='border-leaf', redundancy_type=None,
                           redundancy_group=None):
        return PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id=switch_class_id,
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=0,
            redundancy_type=redundancy_type or '',
            redundancy_group=redundancy_group or '',
        )

    def _make_server_zone(self, switch_class, zone_name='downlinks'):
        return SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name=zone_name,
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-12',
            breakout_option=self.breakout_1x100g,
        )

    def _make_server_class(self, server_class_id='ctrl', quantity=1):
        return PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id=server_class_id,
            server_device_type=self.server_device_type,
            quantity=quantity,
        )

    def _build_connection(self, server_class, zone, distribution, connection_id='conn',
                          conn_type=ConnectionTypeChoices.UNBUNDLED):
        """Build (but do not save) a PlanServerConnection for full_clean() testing."""
        return PlanServerConnection(
            server_class=server_class,
            connection_id=connection_id,
            nic=get_test_server_nic(server_class),
            port_index=0,
            ports_per_connection=2,
            hedgehog_conn_type=conn_type,
            distribution=distribution,
            target_zone=zone,
            speed=100,
        )

    # =========================================================================
    # Test 1: alternating + bundled without redundancy_type raises ValidationError
    # Issue #303: unbundled alternating is exempt; bundled types still require it.
    # =========================================================================

    def test_alternating_bundled_requires_redundancy_type(self):
        """
        distribution=alternating with a bundled connection type (e.g. mclag) targeting
        a switch class with no redundancy_type must raise ValidationError naming the
        switch class and stating the fix.
        """
        switch_class = self._make_switch_class(switch_class_id='border-no-redund')
        zone = self._make_server_zone(switch_class)
        server_class = self._make_server_class()
        conn = self._build_connection(
            server_class, zone, distribution='alternating',
            conn_type=ConnectionTypeChoices.MCLAG,
        )

        with self.assertRaises(ValidationError) as ctx:
            conn.full_clean()

        error_text = str(ctx.exception)
        self.assertIn('redundancy_type', error_text.lower())
        self.assertIn('border-no-redund', error_text)

    # =========================================================================
    # Test 2: alternating unbundled WITHOUT redundancy_type passes (issue #303)
    # =========================================================================

    def test_alternating_unbundled_no_redundancy_type_passes(self):
        """
        distribution=alternating with hedgehog_conn_type=unbundled must pass
        validation even when the target switch class has no redundancy_type.
        Unbundled alternating is multi-homed placement without bonding — no HA
        shim is required (issue #303).
        """
        switch_class = self._make_switch_class(switch_class_id='leaf-unbundled-alt')
        zone = self._make_server_zone(switch_class)
        server_class = self._make_server_class()
        conn = self._build_connection(
            server_class, zone, distribution='alternating',
            conn_type=ConnectionTypeChoices.UNBUNDLED,
        )

        try:
            conn.full_clean()
        except ValidationError as e:
            errors = e.message_dict if hasattr(e, 'message_dict') else {}
            relevant = {k: v for k, v in errors.items() if 'redundancy' in str(v).lower()}
            self.assertEqual(relevant, {}, f"Unexpected redundancy validation error: {e}")

    # =========================================================================
    # Test 3: alternating WITH redundancy_type passes validation (unbundled)
    # =========================================================================

    def test_alternating_with_redundancy_type_passes(self):
        """
        distribution=alternating targeting a switch class with redundancy_type=eslag
        must pass model validation.
        """
        switch_class = self._make_switch_class(
            switch_class_id='border-eslag',
            redundancy_type='eslag',
            redundancy_group='border-eslag-group',
        )
        zone = self._make_server_zone(switch_class)
        server_class = self._make_server_class()
        conn = self._build_connection(server_class, zone, distribution='alternating')

        # Should not raise
        try:
            conn.full_clean()
        except ValidationError as e:
            # Filter out unrelated errors (e.g. unique_together on a new object)
            errors = e.message_dict if hasattr(e, 'message_dict') else {}
            relevant = {k: v for k, v in errors.items() if 'redundancy' in str(v).lower()}
            self.assertEqual(relevant, {}, f"Unexpected redundancy validation error: {e}")

    # =========================================================================
    # Test 4: non-alternating distribution with no redundancy_type passes
    # =========================================================================

    def test_non_alternating_no_redundancy_type_passes(self):
        """
        distribution=same-switch with no redundancy_type on the switch class
        must pass — the alternating rule must not apply globally.
        """
        switch_class = self._make_switch_class(switch_class_id='leaf-same')
        zone = self._make_server_zone(switch_class)
        server_class = self._make_server_class()
        conn = self._build_connection(server_class, zone, distribution='same-switch')

        try:
            conn.full_clean()
        except ValidationError as e:
            errors = e.message_dict if hasattr(e, 'message_dict') else {}
            relevant = {k: v for k, v in errors.items() if 'redundancy' in str(v).lower()}
            self.assertEqual(relevant, {}, f"Unexpected redundancy validation error: {e}")


class AlternatingRedundancyIngestTestCase(TestCase):
    """
    Tests that the YAML ingest path enforces the alternating+bundled-requires-redundancy_type
    rule via full_clean() before saving PlanServerConnection records.

    Regression guard for the blocking finding on PR #247: ORM create paths previously
    bypassed clean(), so the constraint was only enforced through forms/API.

    Issue #303: unbundled alternating is exempt from this constraint.
    """

    @classmethod
    def setUpTestData(cls):
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Test-Ingest-Mfg', defaults={'slug': 'test-ingest-mfg'}
        )
        cls.device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='Test-Ingest-Switch',
            defaults={'slug': 'test-ingest-switch'},
        )
        cls.breakout_1x100g, _ = BreakoutOption.objects.get_or_create(
            breakout_id='test-ingest-1x100g',
            defaults={'from_speed': 100, 'logical_ports': 1, 'logical_speed': 100},
        )
        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.device_type,
            defaults={
                'mclag_capable': False,
                'supported_breakouts': ['test-ingest-1x100g'],
                'native_speed': 100,
            },
        )
        cls.server_device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='Test-Ingest-Server',
            defaults={'slug': 'test-ingest-server'},
        )

    def setUp(self):
        self.plan = TopologyPlan.objects.create(
            name=f'Ingest-Test-Plan-{self._testMethodName}',
            customer_name='Test Customer',
        )

    def _make_switch_class(self, switch_class_id='border-leaf', redundancy_type=None,
                           redundancy_group=None):
        return PlanSwitchClass.objects.create(
            plan=self.plan,
            switch_class_id=switch_class_id,
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=self.device_ext,
            uplink_ports_per_switch=0,
            redundancy_type=redundancy_type or '',
            redundancy_group=redundancy_group or '',
        )

    def _make_server_zone(self, switch_class, zone_name='downlinks'):
        return SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name=zone_name,
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-12',
            breakout_option=self.breakout_1x100g,
        )

    def _make_server_class(self, server_class_id='ctrl', quantity=1):
        return PlanServerClass.objects.create(
            plan=self.plan,
            server_class_id=server_class_id,
            server_device_type=self.server_device_type,
            quantity=quantity,
        )

    def test_ingest_rejects_bundled_alternating_without_redundancy_type(self):
        """
        The ingest build-validate-save path must reject bundled alternating connections
        (e.g. mclag) whose target switch class has no redundancy_type — even on the ORM path.

        This is the negative ingest test required by the blocking finding on PR #247.
        Issue #303: the check now scopes to bundled conn types only.
        """
        switch_class = self._make_switch_class(switch_class_id='no-redund-leaf')
        zone = self._make_server_zone(switch_class)
        server_class = self._make_server_class()

        # Simulate what ingest does: build-validate-save pattern (mclag = bundled)
        conn = PlanServerConnection(
            server_class=server_class,
            connection_id='test-conn',
            nic=get_test_server_nic(server_class),
            port_index=0,
            ports_per_connection=2,
            hedgehog_conn_type='mclag',
            distribution='alternating',
            target_zone=zone,
            speed=100,
        )

        from django.core.exceptions import ValidationError as DjangoValidationError
        with self.assertRaises(DjangoValidationError) as ctx:
            conn.full_clean()

        self.assertIn('no-redund-leaf', str(ctx.exception))

        # Also assert the record was NOT persisted
        self.assertFalse(
            PlanServerConnection.objects.filter(
                server_class=server_class, connection_id='test-conn'
            ).exists(),
            "Bundled alternating connection without redundancy_type must not be saved to DB"
        )

    def test_ingest_accepts_unbundled_alternating_without_redundancy_type(self):
        """
        Unbundled alternating connections must pass full_clean() AND be persistable even
        when the target switch class has no redundancy_type (issue #303).

        This mirrors the ingest build-validate-save pattern: construct → full_clean() → save().
        The record must exist in the DB after the call, proving the ORM path accepts it.
        """
        switch_class = self._make_switch_class(switch_class_id='no-redund-leaf-ub')
        zone = self._make_server_zone(switch_class)
        server_class = self._make_server_class(server_class_id='ctrl-ub')

        conn = PlanServerConnection(
            server_class=server_class,
            connection_id='test-conn-ub',
            nic=get_test_server_nic(server_class),
            port_index=0,
            ports_per_connection=2,
            hedgehog_conn_type='unbundled',
            distribution='alternating',
            target_zone=zone,
            speed=100,
        )

        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            conn.full_clean()
        except DjangoValidationError as e:
            errors = e.message_dict if hasattr(e, 'message_dict') else {}
            redundancy_errors = {k: v for k, v in errors.items()
                                 if 'redundancy' in str(v).lower()}
            self.assertEqual(redundancy_errors, {},
                             f"Unbundled alternating must not trigger redundancy validation: {e}")

        conn.save()

        self.assertTrue(
            PlanServerConnection.objects.filter(
                server_class=server_class, connection_id='test-conn-ub'
            ).exists(),
            "Unbundled alternating connection without redundancy_type must be saved to DB "
            "(issue #303: no HA shim required for unbundled multi-homed placement)"
        )


class AlternatingRedundancy128GpuRegressionTestCase(TestCase):
    """
    Regression guard: after updating the canonical 128GPU YAML to add
    redundancy_type=eslag to fe-border-leaf, the ingested switch class
    must have redundancy_type set.
    """

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command("setup_case_128gpu_odd_ports", stdout=StringIO())
        from netbox_hedgehog.models.topology_planning import TopologyPlan
        cls.plan = TopologyPlan.objects.get(name=PLAN_NAME_128GPU)

    def test_128gpu_border_leaf_has_redundancy_type(self):
        """
        After YAML update, fe-border-leaf must have redundancy_type=eslag.
        Validates that ingest.py reads redundancy_type from YAML and that
        the canonical YAML declares it.
        """
        border_leaf = PlanSwitchClass.objects.get(
            plan=self.plan,
            switch_class_id='fe-border-leaf',
        )
        self.assertEqual(
            border_leaf.redundancy_type,
            'eslag',
            "fe-border-leaf must declare redundancy_type=eslag in canonical YAML "
            "since its connections use distribution=alternating (issue #246)"
        )
        self.assertTrue(
            border_leaf.redundancy_group,
            "fe-border-leaf must have redundancy_group set (required by PlanSwitchClass.clean())"
        )
