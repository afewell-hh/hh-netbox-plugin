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
            'hedgehog_profile_name': model.lower(),
        },
    )
    return ext


def get_test_nic_with_ports(server_class, nic_id, port_count):
    """Create (or reuse) a PlanServerNIC whose ModuleType has ``port_count``
    interface templates — needed for multi-port connections."""
    from dcim.models import InterfaceTemplate, Manufacturer, ModuleType
    from netbox_hedgehog.models.topology_planning import PlanServerNIC

    mfr, _ = Manufacturer.objects.get_or_create(
        name='NVIDIA', defaults={'slug': 'nvidia'})
    mt, created = ModuleType.objects.get_or_create(
        manufacturer=mfr, model=f'WideNIC-{port_count}p')
    if created:
        for i in range(port_count):
            InterfaceTemplate.objects.get_or_create(
                module_type=mt, name=f'p{i}',
                defaults={'type': '200gbase-x-qsfp112'})
    nic, _ = PlanServerNIC.objects.get_or_create(
        server_class=server_class, nic_id=nic_id, defaults={'module_type': mt})
    return nic


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
                           distribution='same-switch', allocation_strategy='sequential',
                           ports_per_connection=1, with_breakout=False):
    """Minimal plan: one server class, one leaf switch class + server zone.

    ``with_breakout`` attaches a 1x (no-op) BreakoutOption to the zone, needed
    only by tests that drive the view's recalculation path (the direct generator
    does not recalc).
    """
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
    zone_kwargs = dict(
        switch_class=switch_class,
        zone_name='fe-server-ports',
        zone_type='server',
        port_spec=port_spec,
        allocation_strategy=allocation_strategy,
    )
    if with_breakout:
        from netbox_hedgehog.models.topology_planning import BreakoutOption
        bo, _ = BreakoutOption.objects.get_or_create(
            breakout_id='rack-1x', defaults={
                'from_speed': 400, 'logical_ports': 1, 'logical_speed': 400})
        zone_kwargs['breakout_option'] = bo
    zone = SwitchPortZone.objects.create(**zone_kwargs)
    server_class = PlanServerClass.objects.create(
        plan=plan,
        server_class_id='gpu-server',
        server_device_type=server_type,
        quantity=quantity,
        place_in_racks=place_in_racks,
        servers_per_rack=servers_per_rack,
        membership_only=membership_only,
    )
    nic = (
        get_test_server_nic(server_class)
        if ports_per_connection <= 2
        else get_test_nic_with_ports(server_class, 'nic-wide', ports_per_connection)
    )
    PlanServerConnection.objects.create(
        server_class=server_class,
        connection_id='FE-01',
        nic=nic,
        port_index=0,
        ports_per_connection=ports_per_connection,
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


def _plan_cable_pks(plan):
    from dcim.models import Cable
    return set(
        Cable.objects.filter(
            **{f'custom_field_data__{PLAN_ID_CF}': str(plan.pk)}
        ).values_list('pk', flat=True)
    )


def _switch_side_wiring(plan):
    """Deterministic switch-side (device_name, interface_name) pairs for every
    plan cable — a name-based wiring signature independent of primary keys."""
    from dcim.models import Cable
    from netbox_hedgehog.services.inventory_export import terminations_for_side
    pairs = set()
    for cable in Cable.objects.filter(
        **{f'custom_field_data__{PLAN_ID_CF}': str(plan.pk)}
    ):
        for side in ('a', 'b'):
            for term in terminations_for_side(cable, side):
                dev = getattr(term, 'device', None)
                if dev is not None and getattr(dev.role, 'slug', '') == 'leaf':
                    pairs.add((dev.name, term.name))
    return pairs


def _locality_signature(plan):
    """Full-contract ordered content signature of the persisted
    PlanLocalityRange rows — includes every provenance field so an
    unchanged-state check detects any locality-report mutation."""
    rows = _locality_range_model().objects.filter(plan=plan).order_by(
        'server_class', 'rack_index', 'switch__name',
        'zone__priority', 'zone__zone_name', 'alloc_seq_start',
    )
    return [
        (
            r.server_class_id, r.rack_index, r.switch.name, r.zone.zone_name,
            r.distribution,
            r.alloc_seq_start, r.alloc_seq_end,
            r.server_ordinal_start, r.server_ordinal_end,
            r.logical_name_first, r.logical_name_last,
            tuple(r.logical_sequence), tuple(r.physical_sequence),
            tuple(r.physical_ports_distinct),
            r.port_count, r.spans_boundary,
        )
        for r in rows
    ]


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
        # Snapshot ALL generated artifacts: devices, racks, cables, locality rows.
        prior_devices = set(_plan_servers(plan).values_list('name', flat=True))
        prior_racks = set(_plan_racks(plan).values_list('name', flat=True))
        prior_cables = _plan_cable_pks(plan)
        prior_rows = _locality_signature(plan)
        self.assertTrue(prior_devices and prior_racks and prior_cables and prior_rows)

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
        self.assertEqual(_plan_cable_pks(plan), prior_cables,
                         'Prior cables must be unchanged after a failed regenerate')
        self.assertEqual(_locality_signature(plan), prior_rows,
                         'Prior locality rows must be unchanged after a failed regenerate')


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

    def test_i9_failed_regenerate_preserves_prior_state(self):
        """A previously-valid generation must survive a later invalid regenerate."""
        plan, sc, *_ = _make_same_switch_plan(
            'zero-preserve', quantity=4, num_switches=1,
            place_in_racks=True, servers_per_rack=4, server_u_height=2,
        )
        DeviceGenerator(plan).generate_all()
        prior_devices = set(_plan_servers(plan).values_list('name', flat=True))
        prior_racks = set(_plan_racks(plan).values_list('name', flat=True))
        prior_cables = _plan_cable_pks(plan)
        prior_rows = _locality_signature(plan)

        # Flip the device type to zero-height (positioned placement now invalid).
        sc.server_device_type.u_height = 0
        sc.server_device_type.save()
        with self.assertRaises(ValidationError):
            DeviceGenerator(plan).generate_all()

        self.assertEqual(
            set(_plan_servers(plan).values_list('name', flat=True)), prior_devices)
        self.assertEqual(
            set(_plan_racks(plan).values_list('name', flat=True)), prior_racks)
        self.assertEqual(_plan_cable_pks(plan), prior_cables)
        self.assertEqual(_locality_signature(plan), prior_rows)


class MembershipOnlyPositiveHeightTestCase(TestCase):
    """membership_only is an explicit per-class option, valid for rackable
    (positive-height) device types too — rack set, position deliberately null."""

    def test_membership_only_positive_height_places_without_position(self):
        plan, *_ = _make_same_switch_plan(
            'membership-pos', quantity=8, num_switches=1,
            place_in_racks=True, servers_per_rack=8,
            membership_only=True, server_u_height=2,
        )
        DeviceGenerator(plan).generate_all()
        self.assertEqual(_plan_racks(plan).count(), 1)
        servers = list(_plan_servers(plan))
        self.assertEqual(len(servers), 8)
        for server in servers:
            self.assertIsNotNone(
                server.rack,
                'membership_only on a rackable type must still set the rack')
            self.assertIsNone(
                server.position,
                'membership_only must leave position null even for positive u_height')


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
        # Model clean() blocks this best-effort; bypass via bulk path (no clean)
        # to prove the generator preflight is the authoritative guard.
        PlanServerConnection.objects.bulk_create([PlanServerConnection(
            server_class=server_class,
            connection_id='FE-02',
            nic=get_test_server_nic(server_class, nic_id='nic-2'),
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type='unbundled',
            distribution='alternating',
            target_zone=zone,
            speed=400,
        )])
        with self.assertRaises(ValidationError):
            DeviceGenerator(plan).generate_all()
        self.assertEqual(_plan_racks(plan).count(), 0)

    def test_i11_mixed_distribution_rejected_at_model_clean(self):
        """Best-effort model-level guard: full_clean() blocks a rack-enabled
        class from saving a second connection with a different distribution to
        the same zone (form/API inherit this via full_clean)."""
        plan, server_class, _sw, zone = _make_same_switch_plan(
            'mixed-clean', quantity=8, num_switches=2,
            place_in_racks=True, servers_per_rack=4,
            distribution='same-switch',
        )
        second = PlanServerConnection(
            server_class=server_class,
            connection_id='FE-02',
            nic=get_test_server_nic(server_class, nic_id='nic-2'),
            port_index=0,
            ports_per_connection=1,
            hedgehog_conn_type='unbundled',
            distribution='alternating',  # differs from the same-switch sibling
            target_zone=zone,
            speed=400,
        )
        with self.assertRaises(ValidationError):
            second.full_clean()


class ByteIdenticalCompatTestCase(TestCase):
    """I1 (strengthened): with placement disabled, full device names and the
    generated wiring content must be byte-identical to the rack-agnostic
    baseline, and deterministic across regeneration."""

    def _make_control_plan(self, name):
        """Baseline plan whose server class does NOT touch the rack fields at
        all (rack-agnostic control)."""
        ext = _make_switch_ext()
        server_type = _make_server_type()
        plan = TopologyPlan.objects.create(name=name, customer_name='Test')
        switch_class = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf', fabric='frontend',
            hedgehog_role='server-leaf', device_type_extension=ext,
            uplink_ports_per_switch=0, calculated_quantity=1,
        )
        zone = SwitchPortZone.objects.create(
            switch_class=switch_class, zone_name='fe-server-ports',
            zone_type='server', port_spec='1-8', allocation_strategy='sequential',
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu-server',
            server_device_type=server_type, quantity=4,
        )
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='FE-01', nic=get_test_server_nic(sc),
            port_index=0, ports_per_connection=1, hedgehog_conn_type='unbundled',
            distribution='same-switch', target_zone=zone, speed=400,
        )
        return plan

    def test_i1_disabled_full_names_and_wiring_match_baseline(self):
        from dcim.models import Site

        control = self._make_control_plan('compat-control')
        DeviceGenerator(control, site=Site.objects.get_or_create(
            slug='compat-a', defaults={'name': 'compat-a'})[0]).generate_all()

        disabled, *_ = _make_same_switch_plan(
            'compat-disabled', quantity=4, num_switches=1,
            place_in_racks=False, port_spec='1-8',
        )
        DeviceGenerator(disabled, site=Site.objects.get_or_create(
            slug='compat-b', defaults={'name': 'compat-b'})[0]).generate_all()

        # Complete server device names must be identical (not merely suffixes).
        self.assertEqual(
            sorted(_plan_servers(control).values_list('name', flat=True)),
            sorted(_plan_servers(disabled).values_list('name', flat=True)),
        )
        self.assertEqual(
            sorted(_plan_servers(disabled).values_list('name', flat=True)),
            ['gpu-server-001', 'gpu-server-002', 'gpu-server-003', 'gpu-server-004'],
        )
        # Full switch-side wiring content must be identical.
        self.assertEqual(
            _switch_side_wiring(control), _switch_side_wiring(disabled),
            'Disabling placement must not change wiring content vs the baseline',
        )
        # And no rack leaked into either.
        self.assertFalse(any(s.rack for s in _plan_servers(disabled)))
        self.assertEqual(_plan_racks(disabled).count(), 0)

    def test_i1_disabled_generation_is_byte_stable(self):
        disabled, *_ = _make_same_switch_plan(
            'compat-stable', quantity=4, num_switches=1,
            place_in_racks=False, port_spec='1-8',
        )
        DeviceGenerator(disabled).generate_all()
        first = _switch_side_wiring(disabled)
        DeviceGenerator(disabled).generate_all()  # regenerate
        self.assertEqual(_switch_side_wiring(disabled), first,
                         'Disabled generation must be byte-stable across runs')

    @staticmethod
    def _yaml_wiring_body(plan):
        """Deterministic wiring-YAML document body for comparison.

        Comment/header lines (which carry plan name + generation timestamp) are
        stripped; the remaining CRD documents contain no plan-identity tokens
        (they are keyed by device names, identical across the two plans). This
        proves a *defined semantic equivalence* of the YAML wiring — the CRD
        documents are identical — not raw byte equality of the full file.
        """
        from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan
        text = generate_yaml_for_plan(plan)
        return '\n'.join(
            line for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith('#')
        )

    def test_i1_disabled_yaml_wiring_matches_baseline(self):
        from dcim.models import Site

        control = self._make_control_plan('compat-yaml-control')
        DeviceGenerator(control, site=Site.objects.get_or_create(
            slug='compat-ya', defaults={'name': 'compat-ya'})[0]).generate_all()

        disabled, *_ = _make_same_switch_plan(
            'compat-yaml-disabled', quantity=4, num_switches=1,
            place_in_racks=False, port_spec='1-8',
        )
        DeviceGenerator(disabled, site=Site.objects.get_or_create(
            slug='compat-yb', defaults={'name': 'compat-yb'})[0]).generate_all()

        self.assertEqual(
            self._yaml_wiring_body(control), self._yaml_wiring_body(disabled),
            'Disabling placement must not change the exported YAML wiring documents',
        )
