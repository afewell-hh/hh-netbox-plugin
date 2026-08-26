"""
DIET-611 Phase 3 RED tests — rack placement, preflight, and cleanup.

Encodes the approved #610 specification contract. These tests reference the
final intended API (PlanServerClass.place_in_racks / servers_per_rack /
membership_only, generated dcim.Rack placement, DeviceGenerator rack preflight
and constants) which does NOT exist yet — so they are expected to FAIL/ERROR
until Phase 4 implements the feature + migrations. No production code or
migrations are added in this phase.

Invariants covered here:
  I1  legacy default-off: no racks, no rows, Device.rack untouched
  I2  ceil(qty/spr) plan-scoped racks; planned status; u_height/starting_unit
  I3  deterministic membership + position; stable across regeneration
  I7  rack capacity conflict / invalid servers_per_rack -> hard preflight fail,
      prior generated state unchanged
  I9  u_height<=0 positioned -> hard fail; membership_only -> success, position null
  I10 foreign (non-plan) device in a generated rack -> hard fail before any delete
  I11 rack-enabled class with mixed distributions to one zone -> hard fail
  I13 non-multiple quantity/servers_per_rack -> final rack clipped at quantity-1
  Plus: canonical disabled-state normalization (model level).
"""

import math

from django.core.exceptions import ValidationError
from django.test import TestCase, tag

from dcim.models import Device, DeviceType, Manufacturer, Rack, Site

from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic
from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator


def _locality_range_model():
    """Lazy import so each test fails individually (RED) rather than the whole
    module erroring at collection while PlanLocalityRange does not yet exist."""
    from netbox_hedgehog.models.topology_planning import PlanLocalityRange
    return PlanLocalityRange


PLAN_ID_CF = 'hedgehog_plan_id'


def _make_switch_ext(model='SW-RACK-01', u_height=1, native_speed=400,
                     roles=None, breakouts=None):
    mfr, _ = Manufacturer.objects.get_or_create(
        name='Celestica-Rack', defaults={'slug': 'celestica-rack'},
    )
    switch_type, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model=model,
        defaults={'slug': model.lower(), 'u_height': u_height},
    )
    ext, _ = DeviceTypeExtension.objects.get_or_create(
        device_type=switch_type,
        defaults={
            'mclag_capable': False,
            'hedgehog_roles': roles or ['server-leaf'],
            'supported_breakouts': breakouts or [],
            'native_speed': native_speed,
            'uplink_ports': 0,
        },
    )
    return ext


def _make_server_type(model='SRV-RACK-01', u_height=2):
    mfr, _ = Manufacturer.objects.get_or_create(
        name='Celestica-Rack', defaults={'slug': 'celestica-rack'},
    )
    server_type, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model=model,
        defaults={'slug': model.lower(), 'u_height': u_height},
    )
    return server_type


def _make_same_switch_plan(name, quantity, num_switches, port_spec='1-64',
                           place_in_racks=False, servers_per_rack=None,
                           membership_only=False, server_u_height=2,
                           distribution='same-switch', allocation_strategy='sequential'):
    """Minimal plan: one server class, one leaf switch class + server zone."""
    ext = _make_switch_ext()
    server_type = _make_server_type(u_height=server_u_height)
    plan = TopologyPlan.objects.create(name=name, customer_name='Test')
    switch_class = PlanSwitchClass.objects.create(
        plan=plan,
        switch_class_id='fe-leaf',
        fabric='frontend',
        hedgehog_role='server-leaf',
        device_type_extension=ext,
        uplink_ports_per_switch=0,
        calculated_quantity=num_switches,
    )
    zone = SwitchPortZone.objects.create(
        switch_class=switch_class,
        zone_name='fe-server-ports',
        zone_type='server',
        port_spec=port_spec,
        allocation_strategy=allocation_strategy,
    )
    server_class = PlanServerClass.objects.create(
        plan=plan,
        server_class_id='gpu-server',
        server_device_type=server_type,
        quantity=quantity,
        place_in_racks=place_in_racks,
        servers_per_rack=servers_per_rack,
        membership_only=membership_only,
    )
    PlanServerConnection.objects.create(
        server_class=server_class,
        connection_id='FE-01',
        nic=get_test_server_nic(server_class),
        port_index=0,
        ports_per_connection=1,
        hedgehog_conn_type='unbundled',
        distribution=distribution,
        target_zone=zone,
        speed=400,
    )
    return plan, server_class, switch_class, zone


def _plan_racks(plan):
    return Rack.objects.filter(
        **{f'custom_field_data__{PLAN_ID_CF}': str(plan.pk)}
    )


def _plan_servers(plan):
    return Device.objects.filter(
        role__slug='server',
        **{f'custom_field_data__{PLAN_ID_CF}': str(plan.pk)},
    )


# ---------------------------------------------------------------------------
# Canonical disabled-state normalization (model level)
# ---------------------------------------------------------------------------
class DisabledStateNormalizationTestCase(TestCase):
    """place_in_racks=False MUST persist servers_per_rack=NULL, membership_only=False."""

    def test_disabled_class_normalizes_dormant_values_on_save(self):
        server_type = _make_server_type()
        plan = TopologyPlan.objects.create(name='norm-plan')
        sc = PlanServerClass(
            plan=plan,
            server_class_id='srv',
            server_device_type=server_type,
            quantity=8,
            place_in_racks=False,
            servers_per_rack=8,      # dormant value that must NOT survive
            membership_only=True,    # dormant value that must NOT survive
        )
        sc.full_clean()
        sc.save()
        sc.refresh_from_db()
        self.assertIsNone(sc.servers_per_rack,
                          'Disabled class must persist servers_per_rack=NULL')
        self.assertFalse(sc.membership_only,
                         'Disabled class must persist membership_only=False')

    def test_toggling_off_clears_previously_set_values(self):
        plan, sc, *_ = _make_same_switch_plan(
            'toggle-off', quantity=8, num_switches=1,
            place_in_racks=True, servers_per_rack=8,
        )
        sc.place_in_racks = False
        sc.full_clean()
        sc.save()
        sc.refresh_from_db()
        self.assertIsNone(sc.servers_per_rack)
        self.assertFalse(sc.membership_only)

    def test_enabled_requires_servers_per_rack(self):
        server_type = _make_server_type()
        plan = TopologyPlan.objects.create(name='req-spr')
        sc = PlanServerClass(
            plan=plan,
            server_class_id='srv',
            server_device_type=server_type,
            quantity=8,
            place_in_racks=True,
            servers_per_rack=None,
        )
        with self.assertRaises(ValidationError):
            sc.full_clean()


# ---------------------------------------------------------------------------
# I1 — legacy default-off behaviour
# ---------------------------------------------------------------------------
class LegacyNoRackTestCase(TestCase):

    def test_disabled_generation_creates_no_racks_or_rows(self):
        plan, *_ = _make_same_switch_plan(
            'legacy', quantity=8, num_switches=1, place_in_racks=False,
        )
        DeviceGenerator(plan).generate_all()

        self.assertEqual(_plan_racks(plan).count(), 0,
                         'Disabled plan must create zero racks')
        self.assertEqual(
            _locality_range_model().objects.filter(plan=plan).count(), 0,
            'Disabled plan must create zero locality rows',
        )
        for server in _plan_servers(plan):
            self.assertIsNone(server.rack,
                              'Disabled plan must leave Device.rack null')


# ---------------------------------------------------------------------------
# I2 / I3 — rack construction, membership, position, determinism
# ---------------------------------------------------------------------------
class RackConstructionTestCase(TestCase):

    def _generate(self):
        plan, sc, _sw, _zone = _make_same_switch_plan(
            'rack64', quantity=64, num_switches=8,
            place_in_racks=True, servers_per_rack=8, server_u_height=2,
        )
        DeviceGenerator(plan).generate_all()
        return plan, sc

    def test_i2_rack_count_and_planned_construction(self):
        plan, _sc = self._generate()
        racks = _plan_racks(plan)
        self.assertEqual(racks.count(), math.ceil(64 / 8),
                         '64 servers / 8 per rack -> 8 racks')
        for rack in racks:
            self.assertEqual(rack.u_height, DeviceGenerator.DEFAULT_RACK_U_HEIGHT)
            self.assertEqual(rack.u_height, 42)
            self.assertEqual(rack.starting_unit,
                             DeviceGenerator.DEFAULT_RACK_STARTING_UNIT)
            self.assertEqual(rack.starting_unit, 1)
            self.assertEqual(rack.status, 'planned',
                             'Generated design-time rack must be status=planned')
            self.assertEqual(rack.site.slug, DeviceGenerator.DEFAULT_SITE_SLUG)

    def test_i3_membership_grouping_contiguous_by_ordinal(self):
        plan, _sc = self._generate()
        # Map server ordinal (trailing index-1) -> rack name.
        by_rack = {}
        for server in _plan_servers(plan):
            self.assertIsNotNone(server.rack, 'Placed server must have a rack')
            ordinal = int(server.name.rsplit('-', 1)[1]) - 1  # 0-based server_index
            by_rack.setdefault(server.rack.name, []).append(ordinal)
        self.assertEqual(len(by_rack), 8)
        # Each rack must hold a contiguous 8-ordinal block.
        for ordinals in by_rack.values():
            ordinals.sort()
            self.assertEqual(len(ordinals), 8)
            self.assertEqual(ordinals, list(range(ordinals[0], ordinals[0] + 8)))

    def test_i3_position_descending_stack(self):
        plan, _sc = self._generate()
        # server_index 0 -> slot 0 -> position = 42 - (0+1)*2 + 1 = 41
        # server_index 1 -> slot 1 -> position = 42 - (1+1)*2 + 1 = 39
        server_by_ordinal = {
            int(s.name.rsplit('-', 1)[1]) - 1: s for s in _plan_servers(plan)
        }
        u = 2
        for ordinal in (0, 1, 7, 8):
            slot = ordinal % 8
            expected = DeviceGenerator.DEFAULT_RACK_U_HEIGHT - (slot + 1) * u + 1
            self.assertEqual(
                server_by_ordinal[ordinal].position, expected,
                f'server_index={ordinal} expected U position {expected}',
            )

    def test_i3_regeneration_is_deterministic(self):
        plan, _sc = self._generate()
        first = {s.name: (s.rack.name, s.position) for s in _plan_servers(plan)}
        DeviceGenerator(plan).generate_all()  # regenerate
        second = {s.name: (s.rack.name, s.position) for s in _plan_servers(plan)}
        self.assertEqual(first, second,
                         'Rack membership and positions must be stable across regeneration')
        self.assertEqual(_plan_racks(plan).count(), 8,
                         'Regeneration must not leave orphan racks')


# ---------------------------------------------------------------------------
# I13 — final partial rack clipped at quantity-1
# ---------------------------------------------------------------------------
class PartialRackTestCase(TestCase):

    def test_i13_non_multiple_quantity_clips_final_rack(self):
        plan, _sc, *_ = _make_same_switch_plan(
            'partial', quantity=20, num_switches=3,
            place_in_racks=True, servers_per_rack=8,
        )
        DeviceGenerator(plan).generate_all()
        racks = _plan_racks(plan)
        self.assertEqual(racks.count(), math.ceil(20 / 8))  # 3 racks: 8/8/4

        counts = sorted(
            _plan_servers(plan).filter(rack=r).count() for r in racks
        )
        self.assertEqual(counts, [4, 8, 8],
                         'Final rack must hold the clipped remainder (4), not 8')


# ---------------------------------------------------------------------------
# I7 — capacity / invalid servers_per_rack preflight, state preservation
# ---------------------------------------------------------------------------
class RackCapacityPreflightTestCase(TestCase):

    def test_i7_capacity_conflict_hard_fails(self):
        # 8 servers/rack * 6U each = 48U > 42U rack -> capacity conflict.
        plan, *_ = _make_same_switch_plan(
            'cap-conflict', quantity=8, num_switches=1,
            place_in_racks=True, servers_per_rack=8, server_u_height=6,
        )
        with self.assertRaises(ValidationError):
            DeviceGenerator(plan).generate_all()
        self.assertEqual(_plan_racks(plan).count(), 0,
                         'Failed capacity preflight must write nothing')
        self.assertEqual(_plan_servers(plan).count(), 0)

    def test_i7_failed_regenerate_preserves_prior_state(self):
        plan, sc, *_ = _make_same_switch_plan(
            'preserve', quantity=8, num_switches=1,
            place_in_racks=True, servers_per_rack=8, server_u_height=2,
        )
        DeviceGenerator(plan).generate_all()
        prior_devices = set(_plan_servers(plan).values_list('name', flat=True))
        prior_racks = set(_plan_racks(plan).values_list('name', flat=True))
        self.assertTrue(prior_devices and prior_racks)

        # Mutate to an invalid capacity, regenerate -> must fail and leave prior intact.
        sc.server_device_type.u_height = 60
        sc.server_device_type.save()
        with self.assertRaises(ValidationError):
            DeviceGenerator(plan).generate_all()

        self.assertEqual(
            set(_plan_servers(plan).values_list('name', flat=True)), prior_devices,
            'Prior devices must be unchanged after a failed regenerate',
        )
        self.assertEqual(
            set(_plan_racks(plan).values_list('name', flat=True)), prior_racks,
            'Prior racks must be unchanged after a failed regenerate',
        )


# ---------------------------------------------------------------------------
# I9 — u_height <= 0 handling
# ---------------------------------------------------------------------------
class ZeroHeightDeviceTestCase(TestCase):

    def test_i9_positioned_zero_height_hard_fails(self):
        plan, *_ = _make_same_switch_plan(
            'zero-pos', quantity=4, num_switches=1,
            place_in_racks=True, servers_per_rack=4,
            membership_only=False, server_u_height=0,
        )
        with self.assertRaises(ValidationError):
            DeviceGenerator(plan).generate_all()
        self.assertEqual(_plan_racks(plan).count(), 0)

    def test_i9_membership_only_zero_height_succeeds_with_null_position(self):
        plan, *_ = _make_same_switch_plan(
            'zero-membership', quantity=4, num_switches=1,
            place_in_racks=True, servers_per_rack=4,
            membership_only=True, server_u_height=0,
        )
        DeviceGenerator(plan).generate_all()
        self.assertEqual(_plan_racks(plan).count(), 1)
        for server in _plan_servers(plan):
            self.assertIsNotNone(server.rack,
                                 'membership_only must still set the rack')
            self.assertIsNone(server.position,
                              'membership_only must leave position null')


# ---------------------------------------------------------------------------
# I10 — foreign occupant blocks cleanup before any delete
# ---------------------------------------------------------------------------
class ForeignOccupantTestCase(TestCase):

    def test_i10_foreign_device_blocks_regeneration_before_delete(self):
        plan, *_ = _make_same_switch_plan(
            'foreign', quantity=8, num_switches=1,
            place_in_racks=True, servers_per_rack=8,
        )
        DeviceGenerator(plan).generate_all()
        rack = _plan_racks(plan).first()
        self.assertIsNotNone(rack)

        # A manual (non-plan) device placed into the generated rack.
        foreign_type = _make_server_type(model='FOREIGN-SRV', u_height=1)
        role = Device.objects.filter(role__slug='server').first().role
        foreign = Device.objects.create(
            name='manual-intruder', device_type=foreign_type, role=role,
            site=Site.objects.get(slug=DeviceGenerator.DEFAULT_SITE_SLUG),
            status='active', rack=rack, position=1,
        )
        prior_devices = set(_plan_servers(plan).values_list('name', flat=True))

        with self.assertRaises(ValidationError):
            DeviceGenerator(plan).generate_all()

        # Nothing deleted: prior plan devices and the foreign device remain.
        self.assertEqual(
            set(_plan_servers(plan).values_list('name', flat=True)), prior_devices,
            'Foreign-occupant block must run before any cleanup deletion',
        )
        self.assertTrue(Device.objects.filter(pk=foreign.pk).exists())


# ---------------------------------------------------------------------------
# I11 — mixed distributions to one zone for a rack-enabled class
# ---------------------------------------------------------------------------
class MixedDistributionTestCase(TestCase):

    def test_i11_mixed_distribution_same_zone_rejected(self):
        plan, server_class, _sw, zone = _make_same_switch_plan(
            'mixed', quantity=8, num_switches=2,
            place_in_racks=True, servers_per_rack=4,
            distribution='same-switch',
        )
        # Second connection to the SAME zone with a different distribution.
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='FE-02',
            nic=get_test_server_nic(server_class, nic_id='nic-2'),
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type='unbundled',
            distribution='alternating',
            target_zone=zone,
            speed=400,
        )
        with self.assertRaises(ValidationError):
            DeviceGenerator(plan).generate_all()
        self.assertEqual(_plan_racks(plan).count(), 0)
