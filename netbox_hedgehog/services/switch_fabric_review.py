"""
Switch-Fabric Link Review service (DIET-460).

Produces one row per switch-fabric zone (zone_type not in SERVER/OOB).
Paired rows (peer_zone set) are emitted once using the lower-pk zone as
"near", avoiding double-emission when both ends carry the peer_zone FK.
Unpaired zones (standard leaf→spine uplinks with no static peer linkage)
appear as honest one-sided rows with outcome=None.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from netbox_hedgehog.models.topology_planning.topology_plans import TopologyPlan

# Zone types included in Switch-Fabric Review (excludes SERVER and OOB)
_FABRIC_ZONE_TYPES = {'uplink', 'mclag', 'peer', 'session', 'fabric', 'mesh'}


def _xcvr_label(mt) -> str:
    """Description-first label for a ModuleType (used in review rows)."""
    if mt is None:
        return '—'
    desc = (mt.description or '').strip()
    if desc:
        return f'{desc} ({mt.model})'
    return f'{mt.manufacturer} {mt.model}'


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SwitchFabricRow:
    """One row in the Switch-Fabric Link Review panel."""
    near_zone_name: str
    near_fabric_name: str
    near_zone_type: str
    near_xcvr_label: str           # '—' when null
    far_zone_name: str | None      # None for unpaired rows
    far_fabric_name: str | None    # None for unpaired rows
    far_xcvr_label: str | None     # None for unpaired rows
    is_paired: bool
    outcome: str | None            # None for unpaired; 'match'|'needs_review'|'blocked' for paired
    reason: str
    edit_near_zone_url: str
    edit_far_zone_url: str | None  # None for unpaired rows


@dataclass
class SwitchFabricReviewSummary:
    """Full Switch-Fabric Link Review for one TopologyPlan."""
    rows: list = field(default_factory=list)
    paired_count: int = 0
    unpaired_count: int = 0
    match_count: int = 0
    needs_review_count: int = 0
    blocked_count: int = 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_switch_fabric_review(plan: "TopologyPlan") -> SwitchFabricReviewSummary:
    """
    Build a switch-fabric link review for *plan*.

    Queries all switch-fabric zones (zone_type not in SERVER/OOB) across all
    switch classes in the plan.  Paired rows (peer_zone set) are deduplicated
    by emitting the row only when zone.pk < zone.peer_zone.pk.  Unpaired zones
    appear as honest one-sided rows with outcome=None.

    Rows are sorted by near_fabric_name then near_zone_name.
    """
    from django.urls import reverse
    from netbox_hedgehog.models.topology_planning.port_zones import SwitchPortZone
    from netbox_hedgehog.services.transceiver_rules import evaluate_xcvr_pair, R_NULL

    zones = (
        SwitchPortZone.objects
        .filter(
            switch_class__plan=plan,
            zone_type__in=list(_FABRIC_ZONE_TYPES),
        )
        .select_related(
            'switch_class',
            'transceiver_module_type',
            'transceiver_module_type__manufacturer',
            'peer_zone',
            'peer_zone__transceiver_module_type',
            'peer_zone__transceiver_module_type__manufacturer',
            'peer_zone__switch_class',
        )
        .order_by('switch_class__fabric_name', 'zone_name')
    )

    rows = []
    seen_paired_pks: set[int] = set()

    for zone in zones:
        peer = zone.peer_zone

        if peer is not None:
            # Deduplicate: if the peer was already emitted as the "near" end of
            # a paired row, skip this zone (it was already included as "far").
            if peer.pk in seen_paired_pks:
                continue
            # Emit this as the canonical paired row; mark both ends as seen.
            seen_paired_pks.add(zone.pk)
            seen_paired_pks.add(peer.pk)

            near_xcvr_mt = zone.transceiver_module_type
            far_xcvr_mt = peer.transceiver_module_type

            near_attrs = near_xcvr_mt.attribute_data if near_xcvr_mt else None
            far_attrs = far_xcvr_mt.attribute_data if far_xcvr_mt else None

            # Use the rule engine: treat near as "server" side, far as "zone" side
            xcvr_result = evaluate_xcvr_pair(near_attrs, far_attrs)

            if xcvr_result.reason_code == R_NULL:
                outcome, reason = 'match', 'Connection intent is consistent'
            else:
                outcome, reason = xcvr_result.outcome, xcvr_result.reason

            rows.append(SwitchFabricRow(
                near_zone_name=zone.zone_name,
                near_fabric_name=zone.switch_class.fabric_name,
                near_zone_type=zone.zone_type,
                near_xcvr_label=_xcvr_label(near_xcvr_mt),
                far_zone_name=peer.zone_name,
                far_fabric_name=peer.switch_class.fabric_name,
                far_xcvr_label=_xcvr_label(far_xcvr_mt),
                is_paired=True,
                outcome=outcome,
                reason=reason,
                edit_near_zone_url=reverse(
                    'plugins:netbox_hedgehog:switchportzone_edit', args=[zone.pk]
                ),
                edit_far_zone_url=reverse(
                    'plugins:netbox_hedgehog:switchportzone_edit', args=[peer.pk]
                ),
            ))
        else:
            # If this zone appeared as the "far" end of an already-emitted paired
            # row (because its peer had peer_zone pointing at this zone), skip it.
            if zone.pk in seen_paired_pks:
                continue
            # Unpaired: honest one-sided row
            rows.append(SwitchFabricRow(
                near_zone_name=zone.zone_name,
                near_fabric_name=zone.switch_class.fabric_name,
                near_zone_type=zone.zone_type,
                near_xcvr_label=_xcvr_label(zone.transceiver_module_type),
                far_zone_name=None,
                far_fabric_name=None,
                far_xcvr_label=None,
                is_paired=False,
                outcome=None,
                reason='No peer_zone configured — standard leaf→spine zones are unpaired',
                edit_near_zone_url=reverse(
                    'plugins:netbox_hedgehog:switchportzone_edit', args=[zone.pk]
                ),
                edit_far_zone_url=None,
            ))

    paired_count = sum(1 for r in rows if r.is_paired)
    unpaired_count = sum(1 for r in rows if not r.is_paired)
    match_count = sum(1 for r in rows if r.outcome == 'match')
    needs_review_count = sum(1 for r in rows if r.outcome == 'needs_review')
    blocked_count = sum(1 for r in rows if r.outcome == 'blocked')

    return SwitchFabricReviewSummary(
        rows=rows,
        paired_count=paired_count,
        unpaired_count=unpaired_count,
        match_count=match_count,
        needs_review_count=needs_review_count,
        blocked_count=blocked_count,
    )
