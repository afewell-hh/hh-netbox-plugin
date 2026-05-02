"""
Switch-Fabric Link Review service (DIET-460).

Produces one row per switch-fabric zone (zone_type not in SERVER/OOB).
Paired rows (peer_zone set) are emitted once using the lower-pk zone as
"near", avoiding double-emission when both ends carry the peer_zone FK.
Unpaired zones (standard leaf→spine uplinks with no static peer linkage)
appear as one-sided rows: outcome=None when xcvr is set, outcome='needs_review'
when transceiver_module_type is null.
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
    outcome: str | None            # None for unpaired+xcvr-ok; 'needs_review' for null-xcvr; 'match'|'needs_review'|'blocked' for paired
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
    using a two-pass strategy that is safe regardless of iteration order:

    Pass 1 — collect the PKs of every zone that is referenced as a far-end
    target (i.e. some other zone's peer_zone points to it).  These zones must
    never be emitted as unpaired rows, even if they appear in the queryset
    before the near-end zone that carries the peer_zone FK.

    Pass 2 — emit rows:
      * Zone with peer_zone set → emit paired row; mark both PKs as seen.
        Skip if peer.pk is already in seen_paired_pks (symmetric dedup).
      * Zone without peer_zone → skip if pk is in far_end_pks or
        seen_paired_pks; otherwise emit as honest one-sided row.

    Rows are sorted by near_fabric_name then near_zone_name.
    """
    from django.urls import reverse
    from netbox_hedgehog.models.topology_planning.port_zones import SwitchPortZone
    from netbox_hedgehog.services.transceiver_rules import evaluate_xcvr_pair, R_NULL

    zones = list(
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

    # Pass 1: collect PKs that will be consumed as far-end of a paired row.
    far_end_pks: set[int] = {
        z.peer_zone_id for z in zones if z.peer_zone_id is not None
    }

    rows = []
    seen_paired_pks: set[int] = set()

    for zone in zones:
        peer = zone.peer_zone

        if peer is not None:
            # Already emitted as the far-end of a previously-processed near zone.
            if peer.pk in seen_paired_pks:
                continue
            # Emit this as the canonical paired row; mark both ends as seen.
            seen_paired_pks.add(zone.pk)
            seen_paired_pks.add(peer.pk)

            near_xcvr_mt = zone.transceiver_module_type
            far_xcvr_mt = peer.transceiver_module_type

            near_attrs = near_xcvr_mt.attribute_data if near_xcvr_mt else None
            far_attrs = far_xcvr_mt.attribute_data if far_xcvr_mt else None

            # Null on either end is a review concern, not a generation blocker.
            if near_xcvr_mt is None or far_xcvr_mt is None:
                outcome, reason = 'needs_review', 'Transceiver intent missing on one or both zones'
            else:
                # Use the rule engine: treat near as "server" side, far as "zone" side
                xcvr_result = evaluate_xcvr_pair(near_attrs, far_attrs)
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
            # Skip zones that are the far-end target of some near zone's
            # peer_zone FK (caught by pass-1 pre-scan), or that were already
            # covered as the far end of an earlier paired row.
            if zone.pk in far_end_pks or zone.pk in seen_paired_pks:
                continue
            # Unpaired: one-sided row.
            # Null transceiver on an unpaired zone is a review concern, not a blocker.
            if zone.transceiver_module_type is None:
                unpaired_outcome = 'needs_review'
                unpaired_reason = 'Transceiver intent not specified on this zone'
            else:
                unpaired_outcome = None
                unpaired_reason = 'No peer_zone configured — standard leaf→spine zones are unpaired'
            rows.append(SwitchFabricRow(
                near_zone_name=zone.zone_name,
                near_fabric_name=zone.switch_class.fabric_name,
                near_zone_type=zone.zone_type,
                near_xcvr_label=_xcvr_label(zone.transceiver_module_type),
                far_zone_name=None,
                far_fabric_name=None,
                far_xcvr_label=None,
                is_paired=False,
                outcome=unpaired_outcome,
                reason=unpaired_reason,
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
