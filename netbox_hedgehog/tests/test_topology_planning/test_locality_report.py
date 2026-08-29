"""
DIET-611 Phase 3 RED tests — persisted PlanLocalityRange locality report.

Encodes the approved #610 contract for the durable, queryable locality
artifact. References the final intended PlanLocalityRange model and its
fields, which do NOT exist yet -> expected to FAIL/ERROR until Phase 4.

Invariants covered here:
  I4  persisted rows form ordered per-(rack,switch,zone) allocation-sequence
      ranges; each cell contiguous in allocation sequence
  I5  spans_boundary semantics per distribution mode
        I5a same-switch aligned  -> one cell/rack, spans_boundary=False
        I5b same-switch misaligned -> multiple cells, spans_boundary=True
        I5c alternating -> multiple cells, spans_boundary=False (no warning)
        I5d rail-optimized domain crossing -> True; capacity-share -> False
  I6  >999 servers: correct integer grouping + report ordering, names unchanged
  I8  allocation-strategy projections: sequential / :2 / interleaved / spaced /
      custom / breakout -> exact ordered logical_sequence & physical_sequence
  I12 duplicate (plan,server_class,rack,switch,zone) cell -> uniqueness violation
"""

from django.db import IntegrityError
from django.db.utils import DatabaseError
from django.test import TestCase, tag

from dcim.models import Device, DeviceType, Manufacturer, Rack

from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic
from netbox_hedgehog.tests.test_topology_planning.test_rack_placement import (
    _make_same_switch_plan,
    _make_switch_ext,
    _make_server_type,
    _plan_racks,
    _plan_servers,
    _locality_range_model,
    get_test_nic_with_ports,
    PLAN_ID_CF,
)
from netbox_hedgehog.models.topology_planning import (
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator


def _rows(plan):
    return list(
        _locality_range_model().objects.filter(plan=plan).order_by(
            'server_class', 'rack_index', 'switch__name',
            'zone__priority', 'zone__zone_name', 'alloc_seq_start',
        )
    )


def _assert_cell_contiguous(test, row):
    """Authoritative guarantee: alloc_seq forms a gapless run of port_count."""
    test.assertEqual(
        row.alloc_seq_end - row.alloc_seq_start + 1, row.port_count,
        'A cell must be contiguous in allocation sequence',
    )
    test.assertEqual(len(row.logical_sequence), row.port_count)
    test.assertEqual(len(row.physical_sequence), row.port_count)


# ---------------------------------------------------------------------------
# I4 — persisted rows, ordered, contiguous
# ---------------------------------------------------------------------------
class LocalityRowsPersistedTestCase(TestCase):

    def test_i4_rows_persisted_and_contiguous(self):
        plan, *_ = _make_same_switch_plan(
            'i4', quantity=64, num_switches=8,
            place_in_racks=True, servers_per_rack=8,
        )
        DeviceGenerator(plan).generate_all()

        rows = _rows(plan)
        self.assertTrue(rows, 'Locality report must persist PlanLocalityRange rows')
        # One aligned cell per rack (8 racks -> 8 cells for this single zone).
        self.assertEqual(len(rows), 8)
        for row in rows:
            self.assertEqual(row.plan_id, plan.pk)
            self.assertIsNotNone(row.rack_id, 'rack FK must be non-null')
            _assert_cell_contiguous(self, row)

    def test_i4_multizone_class_reports_per_zone_cells(self):
        """8 backend-400G + 2 frontend-400G example: multiple zones per class."""
        ext = _make_switch_ext(model='SW-MZ', roles=['server-leaf'])
        server_type = _make_server_type(model='SRV-MZ', u_height=2)
        plan = TopologyPlan.objects.create(name='mz', customer_name='Test')
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu', server_device_type=server_type,
            quantity=8, place_in_racks=True, servers_per_rack=8,
        )
        # Backend leaf: 8x 400G ports/server (same-switch); frontend leaf: 2x 400G.
        be_switch = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='be-leaf', fabric='backend',
            hedgehog_role='server-leaf', device_type_extension=ext,
            uplink_ports_per_switch=0, calculated_quantity=1,
        )
        be_zone = SwitchPortZone.objects.create(
            switch_class=be_switch, zone_name='be-ports', zone_type='server',
            port_spec='1-64', allocation_strategy='sequential', priority=1,
        )
        fe_switch = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='fe-leaf', fabric='frontend',
            hedgehog_role='server-leaf', device_type_extension=ext,
            uplink_ports_per_switch=0, calculated_quantity=1,
        )
        fe_zone = SwitchPortZone.objects.create(
            switch_class=fe_switch, zone_name='fe-ports', zone_type='server',
            port_spec='1-64', allocation_strategy='sequential', priority=2,
        )
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='BE',
            nic=get_test_nic_with_ports(sc, 'nic-be', 8),
            port_index=0, ports_per_connection=8, hedgehog_conn_type='unbundled',
            distribution='same-switch', target_zone=be_zone, speed=400,
        )
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='FE', nic=get_test_server_nic(sc, 'nic-fe'),
            port_index=0, ports_per_connection=2, hedgehog_conn_type='unbundled',
            distribution='same-switch', target_zone=fe_zone, speed=400,
        )
        DeviceGenerator(plan).generate_all()

        rows = _rows(plan)
        zones = {r.zone.zone_name for r in rows}
        self.assertEqual(zones, {'be-ports', 'fe-ports'},
                         'Report must include one cell set per targeted zone')
        be_cell = next(r for r in rows if r.zone.zone_name == 'be-ports')
        fe_cell = next(r for r in rows if r.zone.zone_name == 'fe-ports')
        self.assertEqual(be_cell.port_count, 8 * 8)   # 8 servers x 8 ports
        self.assertEqual(fe_cell.port_count, 8 * 2)   # 8 servers x 2 ports
        _assert_cell_contiguous(self, be_cell)
        _assert_cell_contiguous(self, fe_cell)


# ---------------------------------------------------------------------------
# I5 — spans_boundary semantics
# ---------------------------------------------------------------------------
class SpansBoundaryTestCase(TestCase):

    def test_i5a_same_switch_aligned_single_cell_no_span(self):
        plan, *_ = _make_same_switch_plan(
            'i5a', quantity=8, num_switches=2,
            place_in_racks=True, servers_per_rack=4, distribution='same-switch',
        )
        DeviceGenerator(plan).generate_all()
        rows = _rows(plan)
        # 2 racks of 4, aligned to 2 leaves of 4 -> one cell per rack, no span.
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertFalse(row.spans_boundary,
                             'Aligned same-switch rack must not span a boundary')

    def test_i5b_same_switch_misaligned_spans(self):
        # 8 servers / 2 leaves (group size 4); racks of 3 -> rack boundaries
        # (0-2, 3-5, 6-7) cross the leaf group boundary at ordinal 4.
        plan, *_ = _make_same_switch_plan(
            'i5b', quantity=8, num_switches=2,
            place_in_racks=True, servers_per_rack=3, distribution='same-switch',
        )
        DeviceGenerator(plan).generate_all()
        rows = _rows(plan)
        spanning = [r for r in rows if r.spans_boundary]
        self.assertTrue(spanning,
                        'A rack crossing a same-switch group boundary must set spans_boundary')
        # The rack containing ordinal 3-5 straddles leaf-01/leaf-02 -> >=2 cells.
        by_rack = {}
        for r in rows:
            by_rack.setdefault(r.rack_index, []).append(r)
        self.assertTrue(any(len(v) >= 2 for v in by_rack.values()),
                        'Straddling rack must produce >=2 cells')

    def test_i5c_alternating_multi_cell_no_span(self):
        # Alternating fans by port_index, so a 2-port connection touches both
        # leaves (port0->leaf-a, port1->leaf-b) -> 2 cells, no ordinal span.
        plan, *_ = _make_same_switch_plan(
            'i5c', quantity=8, num_switches=2,
            place_in_racks=True, servers_per_rack=8, distribution='alternating',
            ports_per_connection=2,
        )
        DeviceGenerator(plan).generate_all()
        rows = _rows(plan)
        self.assertTrue(len(rows) >= 2,
                        'Alternating fans across switches -> multiple cells')
        for row in rows:
            self.assertFalse(
                row.spans_boundary,
                'Alternating has no ordinal partition -> spans_boundary must be False',
            )


class RailSpansBoundaryTestCase(TestCase):
    """Rail-optimized: domain crossing -> True; capacity-share -> False."""

    @classmethod
    def setUpTestData(cls):
        cls.ext = _make_switch_ext(model='SW-RAIL', roles=['server-leaf'])
        cls.server_type = _make_server_type(model='SRV-RAIL', u_height=2)

    def _make_rail_plan(self, name, num_servers, num_rails, ports_per_switch,
                        servers_per_rack):
        import math
        num_switches = math.ceil(num_servers * num_rails / ports_per_switch)
        plan = TopologyPlan.objects.create(name=name, customer_name='Test')
        switch_class = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='be-rail-leaf', fabric='backend',
            hedgehog_role='server-leaf', device_type_extension=self.ext,
            uplink_ports_per_switch=0, calculated_quantity=num_switches,
        )
        zone = SwitchPortZone.objects.create(
            switch_class=switch_class, zone_name='be-ports', zone_type='server',
            port_spec=f'1-{ports_per_switch}', allocation_strategy='sequential',
        )
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu', server_device_type=self.server_type,
            quantity=num_servers, place_in_racks=True,
            servers_per_rack=servers_per_rack,
        )
        for rail in range(num_rails):
            PlanServerConnection.objects.create(
                server_class=sc, connection_id=f'BE-{rail}',
                nic=get_test_server_nic(sc, nic_id=f'nic-rail-{rail}'),
                port_index=0, ports_per_connection=1, hedgehog_conn_type='unbundled',
                distribution='rail-optimized', target_zone=zone, speed=400, rail=rail,
            )
        return plan

    def test_i5d_rail_domain_crossing_spans(self):
        # 8 servers, 2 rails, 2 ports/switch -> 8 switches; servers_per_domain=2.
        # Rack of 3 crosses the 2-server domain boundary -> spans_boundary True.
        plan = self._make_rail_plan(
            'i5d-domain', num_servers=8, num_rails=2, ports_per_switch=2,
            servers_per_rack=3,
        )
        DeviceGenerator(plan).generate_all()
        rows = _rows(plan)
        self.assertTrue(any(r.spans_boundary for r in rows),
                        'Rack crossing a rail domain boundary must set spans_boundary')

    def test_i5d_rail_capacity_share_no_span(self):
        # 4 servers, 4 rails, 8 ports/switch -> 2 switches (capacity-sharing).
        # Switch chosen independent of ordinal -> spans_boundary must be False.
        plan = self._make_rail_plan(
            'i5d-capshare', num_servers=4, num_rails=4, ports_per_switch=8,
            servers_per_rack=2,
        )
        DeviceGenerator(plan).generate_all()
        rows = _rows(plan)
        self.assertTrue(rows)
        for row in rows:
            self.assertFalse(row.spans_boundary,
                             'Rail capacity-sharing has no ordinal partition -> False')


# ---------------------------------------------------------------------------
# I6 — >999 servers, integer grouping, names unchanged
# ---------------------------------------------------------------------------
@tag('slow')
class LargeScaleOrdinalTestCase(TestCase):

    def test_i6_thousand_servers_group_by_integer_ordinal(self):
        plan, *_ = _make_same_switch_plan(
            'i6', quantity=1000, num_switches=125,
            place_in_racks=True, servers_per_rack=8, port_spec='1-64',
        )
        DeviceGenerator(plan).generate_all()

        import math
        self.assertEqual(_plan_racks(plan).count(), math.ceil(1000 / 8))
        # Device names must be unchanged (no re-pad): ...-1000 exists, not ...-1000-padded.
        names = set(_plan_servers(plan).values_list('name', flat=True))
        self.assertIn('gpu-server-1000', names)
        self.assertNotIn('gpu-server-01000', names)
        # Report ordering by integer rack_index, not lexical.
        indices = list(
            _locality_range_model().objects.filter(plan=plan)
            .order_by('rack_index').values_list('rack_index', flat=True).distinct()
        )
        self.assertEqual(indices, sorted(indices))
        self.assertEqual(indices[:3], [0, 1, 2])


# ---------------------------------------------------------------------------
# I8 — allocation-strategy ordered projections
# ---------------------------------------------------------------------------
class AllocationStrategyProjectionTestCase(TestCase):
    """Exact ordered logical_sequence / physical_sequence per zone strategy.

    One rack, one leaf, 4 same-switch servers, 1 port each -> a single cell whose
    physical_sequence is exactly the allocator's emission order for the strategy.
    """

    def _single_cell(self, name, allocation_strategy, port_spec='1-8',
                     breakouts=None, breakout_id=None, quantity=4,
                     ports_per_connection=1, allocation_order=None):
        ext = _make_switch_ext(model=f'SW-{name}', roles=['server-leaf'],
                               breakouts=breakouts or [])
        server_type = _make_server_type(model=f'SRV-{name}', u_height=1)
        plan = TopologyPlan.objects.create(name=name, customer_name='Test')
        sc = PlanServerClass.objects.create(
            plan=plan, server_class_id='gpu', server_device_type=server_type,
            quantity=quantity, place_in_racks=True, servers_per_rack=quantity,
        )
        switch_class = PlanSwitchClass.objects.create(
            plan=plan, switch_class_id='leaf', fabric='frontend',
            hedgehog_role='server-leaf', device_type_extension=ext,
            uplink_ports_per_switch=0, calculated_quantity=1,
        )
        zone_kwargs = dict(
            switch_class=switch_class, zone_name='ports', zone_type='server',
            port_spec=port_spec, allocation_strategy=allocation_strategy,
        )
        if allocation_order is not None:
            zone_kwargs['allocation_order'] = allocation_order
        if breakout_id is not None:
            from netbox_hedgehog.models.topology_planning import BreakoutOption
            logical = int(breakout_id.split('x')[0])
            bo, _ = BreakoutOption.objects.get_or_create(
                breakout_id=breakout_id,
                defaults={'from_speed': 400, 'logical_ports': logical,
                          'logical_speed': 100},
            )
            zone_kwargs['breakout_option'] = bo
        zone = SwitchPortZone.objects.create(**zone_kwargs)
        conn_nic = (
            get_test_server_nic(sc)
            if ports_per_connection <= 2
            else get_test_nic_with_ports(sc, 'nic-wide', ports_per_connection)
        )
        PlanServerConnection.objects.create(
            server_class=sc, connection_id='C', nic=conn_nic,
            port_index=0, ports_per_connection=ports_per_connection,
            hedgehog_conn_type='unbundled', distribution='same-switch',
            target_zone=zone, speed=400,
        )
        DeviceGenerator(plan).generate_all()
        rows = _rows(plan)
        self.assertEqual(len(rows), 1, 'Expected exactly one cell for this fixture')
        return rows[0]

    def test_i8_sequential_contiguous(self):
        row = self._single_cell('seq', 'sequential', port_spec='1-8')
        self.assertEqual(row.physical_sequence, [1, 2, 3, 4])
        self.assertEqual(row.logical_sequence, ['E1/1', 'E1/2', 'E1/3', 'E1/4'])

    def test_i8_odd_only_stride(self):
        # port_spec ':2' yields odd-only physical ports [1,3,5,7] -> stride-contiguous.
        row = self._single_cell('odd', 'sequential', port_spec='1-32:2')
        self.assertEqual(row.physical_sequence, [1, 3, 5, 7])

    def test_i8_interleaved_order(self):
        row = self._single_cell('inter', 'interleaved', port_spec='1-8')
        # interleaved = odd-index-first: [1,3,5,7,2,4,6,8]; first 4 consumed.
        self.assertEqual(row.physical_sequence, [1, 3, 5, 7])

    def test_i8_spaced_declared_order(self):
        row = self._single_cell('spaced', 'spaced', port_spec='1-8')
        # spaced interleaves halves: [1,5,2,6,3,7,4,8]; first 4 consumed.
        self.assertEqual(row.physical_sequence, [1, 5, 2, 6])

    def test_i8_custom_declared_order(self):
        # custom allocation_order is honored verbatim; 4 servers consume all 4.
        row = self._single_cell(
            'custom', 'custom', port_spec='1-4', quantity=4,
            allocation_order=[4, 2, 1, 3],
        )
        self.assertEqual(row.physical_sequence, [4, 2, 1, 3])
        self.assertEqual(
            row.logical_sequence, ['E1/4', 'E1/2', 'E1/1', 'E1/3'])

    def test_i8_breakout_straddle_multiplicity(self):
        # 4x breakout: 1 server x 4 ports/connection -> lanes E1/1/1..E1/1/4.
        row = self._single_cell(
            'brk', 'sequential', port_spec='1-8',
            breakouts=['4x100G'], breakout_id='4x100G',
            quantity=1, ports_per_connection=4,
        )
        self.assertEqual(row.physical_sequence, [1, 1, 1, 1],
                         'Breakout lanes repeat the physical port (multiplicity)')
        self.assertEqual(
            row.logical_sequence, ['E1/1/1', 'E1/1/2', 'E1/1/3', 'E1/1/4'])
        self.assertTrue(
            len(set(row.physical_sequence)) < len(row.physical_sequence),
            'Breakout cell is straddled: distinct physical < logical count',
        )


# ---------------------------------------------------------------------------
# I12 — uniqueness of the cell key
# ---------------------------------------------------------------------------
class PartialRackReportTestCase(TestCase):
    """I13 (report side): the final partial rack's row must clip its ordinal
    range at quantity-1 and carry the correct spans_boundary."""

    def test_i13_report_clips_final_rack(self):
        # 20 servers, 8/rack, single switch -> racks 0(0-7),1(8-15),2(16-19).
        # Single leaf => one same-switch group => no partition crossing.
        plan, *_ = _make_same_switch_plan(
            'i13-report', quantity=20, num_switches=1,
            place_in_racks=True, servers_per_rack=8,
        )
        DeviceGenerator(plan).generate_all()
        rows = _rows(plan)

        by_index = {}
        for r in rows:
            by_index.setdefault(r.rack_index, []).append(r)
        self.assertEqual(sorted(by_index), [0, 1, 2])

        final = by_index[2]
        self.assertEqual(len(final), 1, 'Single switch -> one cell for final rack')
        final_row = final[0]
        self.assertEqual(
            final_row.server_ordinal_end, 20 - 1,
            'Final partial rack must clip server_ordinal_end at quantity-1',
        )
        self.assertEqual(final_row.server_ordinal_start, 16)
        self.assertEqual(final_row.port_count, 4)  # 4 servers in the final rack
        self.assertFalse(
            final_row.spans_boundary,
            'Single-switch same-switch rack must not span a boundary',
        )


class LocalityUniquenessTestCase(TestCase):

    def test_i12_duplicate_cell_rejected(self):
        plan, sc, switch_class, zone = _make_same_switch_plan(
            'i12', quantity=8, num_switches=1,
            place_in_racks=True, servers_per_rack=8,
        )
        DeviceGenerator(plan).generate_all()
        row = _rows(plan)[0]
        with self.assertRaises((IntegrityError, DatabaseError)):
            _locality_range_model().objects.create(
                plan=plan, server_class=sc, rack=row.rack, switch=row.switch,
                zone=row.zone, rack_index=row.rack_index, distribution='same-switch',
                alloc_seq_start=0, alloc_seq_end=0,
                server_ordinal_start=0, server_ordinal_end=0,
                logical_name_first='E1/1', logical_name_last='E1/1',
                logical_sequence=['E1/1'], physical_sequence=[1],
                physical_ports_distinct=[1], port_count=1, spans_boundary=False,
            )
