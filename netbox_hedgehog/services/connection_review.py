"""
Read-only connection review summary service (DIET-449).

Groups a plan's server connections by distinct connection type and assigns
each group one of three review outcomes:

  match        — connection intent is internally consistent and unambiguous.
  needs_review — something about this group requires engineer attention
                 (e.g. transceiver intent mismatch between connection and zone,
                 or a breakout case with no transceiver specified).
  blocked      — a structural problem that will prevent generation
                 (e.g. no breakout option configured on the zone).

The service is purely read-only: it never writes to the database and is
independent of GenerationState.  It is available on draft plans as well as
generated ones.

Distinct connection type key
----------------------------
Two PlanServerConnection objects belong to the same review group when they
share all of:
  - speed
  - hedgehog_conn_type
  - breakout_option on the target zone (by breakout_id, or None)
  - transceiver_module_type on the connection (by model string, or None)
  - transceiver_module_type on the target zone (by model string, or None)
  - port_type
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from netbox_hedgehog.models.topology_planning.topology_plans import TopologyPlan


def _xcvr_label(mt) -> str:
    """Description-first label for a ModuleType (used in review rows)."""
    if mt is None:
        return '—'
    desc = (mt.description or '').strip()
    if desc:
        return f'{desc} ({mt.model})'
    return f'{mt.manufacturer} {mt.model}'


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConnectionGroup:
    """
    One row in the connection review summary: a distinct connection type
    with a count and a review outcome.

    Fields
    ------
    speed : int
        Connection speed in Gbps.
    conn_type : str
        Internal hedgehog_conn_type value (e.g. 'unbundled').
    conn_type_display : str
        Human-readable connection type label.
    breakout_id : str | None
        BreakoutOption.breakout_id from the target zone (e.g. '4x200g'),
        or None if no breakout option is configured.
    connection_xcvr : str | None
        Model string of PlanServerConnection.transceiver_module_type, or None.
    zone_xcvr : str | None
        Model string of SwitchPortZone.transceiver_module_type, or None.
    port_type : str | None
        Port type value (e.g. 'data', 'ipmi'), or None if unset.
    count : int
        Number of physical connections of this type in the topology.
        Equals sum(server_class.quantity × ports_per_connection) across all
        PlanServerConnection rows that share this group key.  This matches
        the double loop in DeviceGenerator._create_connections().
    outcome : str
        One of 'match', 'needs_review', 'blocked'.
    reason : str
        Short human-readable explanation of the outcome.
    """
    speed: int
    conn_type: str
    conn_type_display: str
    breakout_id: str | None
    connection_xcvr: str | None
    zone_xcvr: str | None
    port_type: str | None
    count: int
    outcome: str
    reason: str


@dataclass
class ConnectionReviewSummary:
    """
    Full connection review summary for one TopologyPlan.

    Fields
    ------
    groups : list[ConnectionGroup]
        All distinct connection groups, sorted by (speed desc, conn_type, breakout_id).
    total_connections : int
        Total number of PlanServerConnection objects in the plan.
    match_count : int
        Number of groups with outcome='match'.
    needs_review_count : int
        Number of groups with outcome='needs_review'.
    blocked_count : int
        Number of groups with outcome='blocked'.
    """
    groups: list[ConnectionGroup] = field(default_factory=list)
    total_connections: int = 0
    match_count: int = 0
    needs_review_count: int = 0
    blocked_count: int = 0


# ---------------------------------------------------------------------------
# Outcome derivation
# ---------------------------------------------------------------------------

def _determine_outcome(
    breakout_id: str | None,
    logical_ports: int | None,
    server_attrs: dict | None,
    zone_attrs: dict | None,
) -> tuple[str, str]:
    """
    Derive (outcome, reason) for a connection group.

    Uses the transceiver rule engine (services/transceiver_rules.py) for all
    transceiver compatibility decisions.  Structural checks (zone breakout
    option, breakout-without-transceiver advisory) are applied around the
    rule engine call.

    Parameters
    ----------
    breakout_id:
        BreakoutOption.breakout_id from the target zone, or None if absent.
    logical_ports:
        BreakoutOption.logical_ports, or None if absent.
    server_attrs:
        ModuleType.attribute_data for the server-side transceiver, or None.
    zone_attrs:
        ModuleType.attribute_data for the zone-side transceiver, or None.

    Returns a 2-tuple (outcome_str, reason_str).
    """
    from netbox_hedgehog.services.transceiver_rules import evaluate_xcvr_pair, R_NULL

    # Structural: no breakout option on zone → blocked (switch quantity unknown)
    if breakout_id is None:
        return 'blocked', 'No breakout option configured on switch zone'

    # Delegate transceiver compatibility evaluation to the rule engine.
    xcvr_result = evaluate_xcvr_pair(server_attrs, zone_attrs)

    # Non-null result: the rule engine owns the outcome.
    # R_NULL means both endpoints have no transceiver FK; fall through to the
    # breakout advisory check below.
    if xcvr_result.reason_code != R_NULL:
        return xcvr_result.outcome, xcvr_result.reason

    # R_NULL path: both FKs absent.
    # Breakout with logical_ports > 1 and no transceiver named needs attention
    # because a passive splitter/DAC type should be specified.
    if logical_ports is not None and logical_ports > 1:
        return (
            'needs_review',
            f'{breakout_id} breakout: specify the splitter/DAC transceiver type',
        )

    return 'match', 'Connection intent is consistent'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_connection_review_summary(plan: "TopologyPlan") -> ConnectionReviewSummary:
    """
    Build a read-only connection review summary for *plan*.

    Queries all PlanServerConnection objects for the plan in a single pass,
    groups them by distinct connection type, and assigns each group an outcome.

    Count semantics
    ---------------
    Each PlanServerConnection row is a *template* that the generator expands
    over every server in the server class.  The meaningful count for the
    review panel is the number of physical connections of each type that will
    exist in the topology:

        count += server_class.quantity * ports_per_connection

    This matches the double loop in DeviceGenerator._create_connections()
    (outer: server_class.quantity; inner: ports_per_connection).

    Returns a ConnectionReviewSummary. Never raises; returns an empty summary
    if the plan has no connections.
    """
    from netbox_hedgehog.models.topology_planning.topology_plans import PlanServerConnection

    connections = (
        PlanServerConnection.objects
        .filter(server_class__plan=plan)
        .select_related(
            'server_class',
            'target_zone',
            'target_zone__breakout_option',
            'target_zone__transceiver_module_type',
            'transceiver_module_type',
        )
    )

    # Accumulate (key → {meta, count}) using a dict
    # key is a 6-tuple of plain Python primitives for hashability
    groups_acc: dict[tuple, dict] = {}

    for conn in connections:
        zone = conn.target_zone
        bo = zone.breakout_option if zone else None
        breakout_id = bo.breakout_id if bo else None
        logical_ports = bo.logical_ports if bo else None

        conn_xcvr_mt = conn.transceiver_module_type
        zone_xcvr_mt = zone.transceiver_module_type if zone else None

        connection_xcvr = conn_xcvr_mt.model if conn_xcvr_mt else None
        zone_xcvr = zone_xcvr_mt.model if zone_xcvr_mt else None
        server_attrs = conn_xcvr_mt.attribute_data if conn_xcvr_mt else None
        zone_xcvr_attrs = zone_xcvr_mt.attribute_data if zone_xcvr_mt else None

        key = (
            conn.speed,
            conn.hedgehog_conn_type,
            breakout_id,
            connection_xcvr,
            zone_xcvr,
            conn.port_type or None,
        )

        if key not in groups_acc:
            outcome, reason = _determine_outcome(
                breakout_id, logical_ports, server_attrs, zone_xcvr_attrs
            )
            groups_acc[key] = {
                'speed': conn.speed,
                'conn_type': conn.hedgehog_conn_type,
                'conn_type_display': conn.get_hedgehog_conn_type_display(),
                'breakout_id': breakout_id,
                'connection_xcvr': connection_xcvr,
                'zone_xcvr': zone_xcvr,
                'port_type': conn.port_type or None,
                'count': 0,
                'outcome': outcome,
                'reason': reason,
            }
        # Expand: each connection template applies to every server × every port
        groups_acc[key]['count'] += conn.server_class.quantity * conn.ports_per_connection

    # Build sorted list of ConnectionGroup objects
    sorted_keys = sorted(
        groups_acc,
        key=lambda k: (-k[0], k[1] or '', k[2] or '', k[5] or ''),
    )
    groups = [
        ConnectionGroup(**groups_acc[k])
        for k in sorted_keys
    ]

    total = sum(g.count for g in groups)
    match_count = sum(1 for g in groups if g.outcome == 'match')
    needs_review_count = sum(1 for g in groups if g.outcome == 'needs_review')
    blocked_count = sum(1 for g in groups if g.outcome == 'blocked')

    return ConnectionReviewSummary(
        groups=groups,
        total_connections=total,
        match_count=match_count,
        needs_review_count=needs_review_count,
        blocked_count=blocked_count,
    )


# ---------------------------------------------------------------------------
# Server-Link Review (DIET-460)
# One row per PlanServerConnection — instance-level, not template-grouped.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServerLinkRow:
    """One row in the Server-Link Review panel."""
    connection_id: str
    server_class_id: str
    speed: int
    conn_type: str
    conn_type_display: str
    server_xcvr_label: str   # '—' when null
    zone_xcvr_label: str     # '—' when null
    physical_count: int      # server_class.quantity × ports_per_connection
    server_transceiver_count: int
    outcome: str             # 'match' | 'needs_review' | 'blocked'
    reason: str
    edit_connection_url: str
    edit_zone_url: str


@dataclass(frozen=True)
class ZoneOpticAggregate:
    """Aggregate switch-side optic estimate for one SwitchPortZone."""
    zone_name: str
    breakout_id: str | None
    xcvr_label: str
    total_logical_links: int
    required_switch_optics: int
    edit_zone_url: str


@dataclass
class ServerLinkReviewSummary:
    """Full Server-Link Review for one TopologyPlan."""
    rows: list = field(default_factory=list)
    zone_aggregates: list = field(default_factory=list)
    total_connections: int = 0
    match_count: int = 0
    needs_review_count: int = 0
    blocked_count: int = 0


def _ceil_div(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return numerator
    return math.ceil(numerator / denominator)


def _select_switch_index(
    num_switches: int,
    distribution: str,
    server_index: int,
    port_index: int,
    rail: int | None = None,
    total_rails: int | None = None,
    servers_per_domain: int | None = None,
    total_servers: int | None = None,
) -> int:
    """Mirror DeviceGenerator._select_switch_instance() using indices only."""
    from netbox_hedgehog.choices import ConnectionDistributionChoices

    if num_switches <= 1:
        return 0

    if distribution == ConnectionDistributionChoices.ALTERNATING:
        return port_index % num_switches

    if distribution == ConnectionDistributionChoices.SAME_SWITCH:
        if total_servers is None or total_servers <= 0:
            return server_index % num_switches

        base_group_size = total_servers // num_switches
        extra_servers = total_servers % num_switches
        lower_bound = 0

        for switch_index in range(num_switches):
            group_size = base_group_size + (1 if switch_index < extra_servers else 0)
            upper_bound = lower_bound + group_size
            if server_index < upper_bound:
                return switch_index
            lower_bound = upper_bound

        return num_switches - 1

    if distribution == ConnectionDistributionChoices.RAIL_OPTIMIZED:
        if rail is None or total_rails is None or total_rails <= 0:
            return 0

        if num_switches >= total_rails:
            if servers_per_domain is None or servers_per_domain <= 0:
                return min(rail, num_switches - 1)
            domain_index = server_index // servers_per_domain
            switch_index = domain_index * total_rails + rail
        else:
            rails_per_switch = math.ceil(total_rails / num_switches)
            switch_index = rail // rails_per_switch

        return min(switch_index, num_switches - 1)

    return server_index % num_switches


def _rail_params(conn, zone, num_switches: int) -> tuple[int | None, int | None]:
    """Return (total_rails, servers_per_domain) for a rail-optimized connection."""
    rail_qs = conn.server_class.connections.filter(
        distribution='rail-optimized',
        target_zone=zone,
        rail__isnull=False,
    )
    distinct_rails = rail_qs.values_list('rail', flat=True).distinct()
    total_rails = len(distinct_rails)
    servers_per_domain = None
    if total_rails and num_switches >= total_rails:
        from netbox_hedgehog.services.port_allocator import PortAllocatorV2
        zone_capacity = PortAllocatorV2().capacity_for_zone(zone)
        ppc = conn.ports_per_connection or 1
        servers_per_domain = max(1, zone_capacity // ppc)
    return total_rails or None, servers_per_domain


def build_server_link_review(plan: "TopologyPlan") -> ServerLinkReviewSummary:
    """
    Build a per-instance server link review for *plan*.

    Returns one ServerLinkRow per PlanServerConnection, sorted by
    speed descending then hedgehog_conn_type.
    """
    from django.urls import reverse
    from netbox_hedgehog.models.topology_planning.topology_plans import PlanServerConnection

    connections = (
        PlanServerConnection.objects
        .filter(server_class__plan=plan)
        .select_related(
            'server_class',
            'target_zone',
            'target_zone__breakout_option',
            'target_zone__switch_class',
            'target_zone__transceiver_module_type',
            'target_zone__transceiver_module_type__manufacturer',
            'transceiver_module_type',
            'transceiver_module_type__manufacturer',
        )
        .order_by('-speed', 'hedgehog_conn_type')
    )

    rows = []
    # (zone_pk, switch_index) → logical link count
    zone_buckets: dict[tuple[int, int], int] = {}
    # zone_pk → zone metadata for aggregate construction
    zone_meta: dict[int, dict] = {}

    for conn in connections:
        zone = conn.target_zone
        bo = zone.breakout_option if zone else None
        breakout_id = bo.breakout_id if bo else None
        logical_ports = bo.logical_ports if bo else None

        conn_xcvr_mt = conn.transceiver_module_type
        zone_xcvr_mt = zone.transceiver_module_type if zone else None

        server_attrs = conn_xcvr_mt.attribute_data if conn_xcvr_mt else None
        zone_xcvr_attrs = zone_xcvr_mt.attribute_data if zone_xcvr_mt else None

        outcome, reason = _determine_outcome(
            breakout_id, logical_ports, server_attrs, zone_xcvr_attrs
        )

        edit_conn_url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_edit',
            args=[conn.pk],
        )
        edit_zone_url = reverse(
            'plugins:netbox_hedgehog:switchportzone_edit',
            args=[zone.pk],
        ) if zone else ''

        rows.append(ServerLinkRow(
            connection_id=conn.connection_id,
            server_class_id=conn.server_class.server_class_id,
            speed=conn.speed,
            conn_type=conn.hedgehog_conn_type,
            conn_type_display=conn.get_hedgehog_conn_type_display(),
            server_xcvr_label=_xcvr_label(conn_xcvr_mt),
            zone_xcvr_label=_xcvr_label(zone_xcvr_mt),
            physical_count=conn.server_class.quantity * conn.ports_per_connection,
            server_transceiver_count=(
                conn.server_class.quantity * conn.ports_per_connection
                if conn_xcvr_mt is not None else 0
            ),
            outcome=outcome,
            reason=reason,
            edit_connection_url=edit_conn_url,
            edit_zone_url=edit_zone_url,
        ))

        # Accumulate zone bucket data for the aggregate table
        if zone is not None:
            zone_pk = zone.pk
            if zone_pk not in zone_meta:
                zone_meta[zone_pk] = {
                    'zone_name': zone.zone_name,
                    'breakout_id': breakout_id,
                    'logical_ports': bo.logical_ports if bo else 1,
                    'xcvr_mt': zone_xcvr_mt,
                    'edit_zone_url': edit_zone_url,
                }

            num_switches = max(zone.switch_class.effective_quantity, 1)
            total_rails = None
            servers_per_domain = None
            if conn.distribution == 'rail-optimized':
                total_rails, servers_per_domain = _rail_params(conn, zone, num_switches)

            for server_index in range(conn.server_class.quantity):
                for port_index in range(conn.ports_per_connection):
                    switch_index = _select_switch_index(
                        num_switches=num_switches,
                        distribution=conn.distribution,
                        server_index=server_index,
                        port_index=port_index,
                        rail=conn.rail,
                        total_rails=total_rails,
                        servers_per_domain=servers_per_domain,
                        total_servers=conn.server_class.quantity,
                    )
                    key = (zone_pk, switch_index)
                    zone_buckets[key] = zone_buckets.get(key, 0) + 1

    # Build one ZoneOpticAggregate per zone, sorted by zone_name
    zone_aggregates = []
    for zone_pk, meta in zone_meta.items():
        logical_ports = max(meta['logical_ports'], 1)
        xcvr_mt = meta['xcvr_mt']
        sw_links = {
            switch_idx: cnt
            for (zpk, switch_idx), cnt in zone_buckets.items()
            if zpk == zone_pk
        }
        total_logical_links = sum(sw_links.values())
        if xcvr_mt is None:
            required_switch_optics = 0
        else:
            required_switch_optics = sum(
                _ceil_div(cnt, logical_ports) for cnt in sw_links.values()
            )
        zone_aggregates.append(ZoneOpticAggregate(
            zone_name=meta['zone_name'],
            breakout_id=meta['breakout_id'],
            xcvr_label=_xcvr_label(xcvr_mt),
            total_logical_links=total_logical_links,
            required_switch_optics=required_switch_optics,
            edit_zone_url=meta['edit_zone_url'],
        ))
    zone_aggregates.sort(key=lambda a: a.zone_name)

    total = len(rows)
    match_count = sum(1 for r in rows if r.outcome == 'match')
    needs_review_count = sum(1 for r in rows if r.outcome == 'needs_review')
    blocked_count = sum(1 for r in rows if r.outcome == 'blocked')

    return ServerLinkReviewSummary(
        rows=rows,
        zone_aggregates=zone_aggregates,
        total_connections=total,
        match_count=match_count,
        needs_review_count=needs_review_count,
        blocked_count=blocked_count,
    )
