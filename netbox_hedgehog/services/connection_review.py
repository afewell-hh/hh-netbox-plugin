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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from netbox_hedgehog.models.topology_planning.topology_plans import TopologyPlan


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
    connection_xcvr: str | None,
    zone_xcvr: str | None,
) -> tuple[str, str]:
    """
    Derive (outcome, reason) for a connection group.

    Returns a 2-tuple (outcome_str, reason_str).
    """
    # Blocked: no breakout option on zone — switch quantity cannot be calculated
    if breakout_id is None:
        return 'blocked', 'No breakout option configured on switch zone'

    # Needs review: transceiver intent exists on one side only
    if connection_xcvr is not None and zone_xcvr is None:
        return (
            'needs_review',
            'Connection specifies a transceiver but the switch zone does not',
        )
    if connection_xcvr is None and zone_xcvr is not None:
        return (
            'needs_review',
            'Switch zone specifies a transceiver but the connection does not',
        )
    if (
        connection_xcvr is not None
        and zone_xcvr is not None
        and connection_xcvr != zone_xcvr
    ):
        return (
            'needs_review',
            f'Connection transceiver ({connection_xcvr}) differs from '
            f'zone transceiver ({zone_xcvr})',
        )

    # Needs review: breakout implies passive splitter but no transceiver is named
    if logical_ports is not None and logical_ports > 1 and connection_xcvr is None:
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
                breakout_id, logical_ports, connection_xcvr, zone_xcvr
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
