"""
Switch-Fabric Link Review service (DIET-460 / DIET-505).

Produces one row per switch-fabric zone (zone_type not in SERVER/OOB).
Explicit paired rows (peer_zone set) are emitted once, deduped by lower-pk.
Eligible standard uplink zones (managed fabric, leaf role, uplink_ports!=0,
no peer_zone) are auto-paired with managed spine FABRIC zones in the same
fabric via inference (DIET-505 Phase 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from netbox_hedgehog.models.topology_planning.topology_plans import TopologyPlan

_FABRIC_ZONE_TYPES = {'uplink', 'mclag', 'peer', 'session', 'fabric', 'mesh'}
_LEAF_ROLES = {'server-leaf', 'border-leaf'}


def _xcvr_label(mt) -> str:
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
    near_xcvr_label: str
    far_zone_name: str | None
    far_fabric_name: str | None
    far_xcvr_label: str | None
    is_paired: bool
    is_inferred: bool
    outcome: str | None
    reason: str
    edit_near_zone_url: str
    edit_far_zone_url: str | None


@dataclass
class SwitchFabricReviewSummary:
    """Full Switch-Fabric Link Review for one TopologyPlan."""
    rows: list = field(default_factory=list)
    paired_count: int = 0
    unpaired_count: int = 0
    inferred_count: int = 0
    match_count: int = 0
    needs_review_count: int = 0
    blocked_count: int = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _infer_outcome(near_xcvr_mt, far_xcvr_mt):
    """Outcome/reason for a direct (single-candidate) inferred pair."""
    from netbox_hedgehog.services.transceiver_rules import evaluate_xcvr_pair
    if near_xcvr_mt is None or far_xcvr_mt is None:
        return 'needs_review', 'Transceiver intent missing on one or both zones'
    result = evaluate_xcvr_pair(
        near_xcvr_mt.attribute_data,
        far_xcvr_mt.attribute_data,
    )
    return result.outcome, result.reason


def _pool_outcome(near_xcvr_mt, pool_zones):
    """
    Outcome/reason for a pooled multi-candidate inferred row.

    Rules (per #508 clarification):
    - near xcvr null → needs_review
    - any pool xcvr null → needs_review (missing intent)
    - pool xcvrs mixed (not all identical model) → needs_review
    - all pool xcvrs same non-null + near xcvr set → evaluate via rule engine
    """
    from netbox_hedgehog.services.transceiver_rules import evaluate_xcvr_pair

    n = len(pool_zones)

    if near_xcvr_mt is None:
        return 'needs_review', 'Transceiver intent missing on one or both zones'

    pool_mts = [z.transceiver_module_type for z in pool_zones]

    if any(mt is None for mt in pool_mts):
        return 'needs_review', (
            f'Transceiver intent missing on one or both zones '
            f'(managed spine pool — {n} zones)'
        )

    models = {mt.model for mt in pool_mts}
    if len(models) > 1:
        return 'needs_review', (
            f'Pool far-side transceiver specifications differ across '
            f'{n} managed spine zones'
        )

    # Uniform non-null pool: evaluate near vs representative pool xcvr.
    result = evaluate_xcvr_pair(
        near_xcvr_mt.attribute_data,
        pool_mts[0].attribute_data,
    )
    return result.outcome, result.reason


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_switch_fabric_review(plan: "TopologyPlan") -> SwitchFabricReviewSummary:
    """
    Build a switch-fabric link review for *plan*.

    Pass 0 — build candidate map: fabric_name → [managed spine FABRIC zones].
    Pass 1 — collect explicit far-end PKs (peer_zone targets) and inferred
              far-end PKs (spine FABRIC zones consumed by inference).
    Pass 2 — emit rows; eligible uplink zones without peer_zone get inferred
              or pool rows instead of bare unpaired rows.
    """
    from django.urls import reverse
    from netbox_hedgehog.choices import FabricClassChoices
    from netbox_hedgehog.models.topology_planning.port_zones import SwitchPortZone

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

    # Pass 0: map fabric_name → sorted list of managed spine FABRIC zones.
    spine_fabric_map: dict[str, list] = {}
    for z in zones:
        sc = z.switch_class
        if (
            z.zone_type == 'fabric'
            and sc.hedgehog_role == 'spine'
            and sc.fabric_class == FabricClassChoices.MANAGED
        ):
            spine_fabric_map.setdefault(sc.fabric_name, []).append(z)

    # Pass 1: explicit far-end PKs.
    explicit_far_pks: set[int] = {
        z.peer_zone_id for z in zones if z.peer_zone_id is not None
    }

    # Determine which spine FABRIC zones will be consumed as inferred far-ends
    # so they can be suppressed from standalone emission.
    inferred_far_pks: set[int] = set()
    for z in zones:
        if z.peer_zone_id is not None:
            continue  # explicit — handled separately
        sc = z.switch_class
        if not (
            z.zone_type == 'uplink'
            and sc.fabric_class == FabricClassChoices.MANAGED
            and sc.uplink_ports_per_switch != 0
            and sc.hedgehog_role in _LEAF_ROLES
        ):
            continue
        candidates = spine_fabric_map.get(sc.fabric_name, [])
        for c in candidates:
            inferred_far_pks.add(c.pk)

    far_end_pks = explicit_far_pks | inferred_far_pks

    rows = []
    seen_pair_keys: set[tuple[int, int]] = set()

    for zone in zones:
        peer = zone.peer_zone
        sc = zone.switch_class

        if peer is not None:
            # Explicit peer_zone — existing dedup logic unchanged.
            pair_key = tuple(sorted((zone.pk, peer.pk)))
            if pair_key in seen_pair_keys:
                continue
            seen_pair_keys.add(pair_key)

            near_xcvr_mt = zone.transceiver_module_type
            far_xcvr_mt = peer.transceiver_module_type

            if near_xcvr_mt is None or far_xcvr_mt is None:
                outcome, reason = 'needs_review', 'Transceiver intent missing on one or both zones'
            else:
                from netbox_hedgehog.services.transceiver_rules import evaluate_xcvr_pair
                xcvr_result = evaluate_xcvr_pair(
                    near_xcvr_mt.attribute_data, far_xcvr_mt.attribute_data
                )
                outcome, reason = xcvr_result.outcome, xcvr_result.reason

            rows.append(SwitchFabricRow(
                near_zone_name=zone.zone_name,
                near_fabric_name=sc.fabric_name,
                near_zone_type=zone.zone_type,
                near_xcvr_label=_xcvr_label(near_xcvr_mt),
                far_zone_name=peer.zone_name,
                far_fabric_name=peer.switch_class.fabric_name,
                far_xcvr_label=_xcvr_label(far_xcvr_mt),
                is_paired=True,
                is_inferred=False,
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
            # No explicit peer_zone.
            if zone.pk in far_end_pks:
                continue  # suppressed as far-end of another row

            is_eligible = (
                zone.zone_type == 'uplink'
                and sc.fabric_class == FabricClassChoices.MANAGED
                and sc.uplink_ports_per_switch != 0
                and sc.hedgehog_role in _LEAF_ROLES
            )

            near_xcvr_mt = zone.transceiver_module_type
            near_url = reverse(
                'plugins:netbox_hedgehog:switchportzone_edit', args=[zone.pk]
            )

            if not is_eligible:
                # Ineligible unpaired: emit with context-aware reason.
                if zone.zone_type == 'uplink' and sc.uplink_ports_per_switch == 0:
                    if near_xcvr_mt is None:
                        outcome = 'needs_review'
                        reason = (
                            'Non-standard uplink: uplink_ports_per_switch is 0 '
                            'and no peer_zone is set'
                        )
                    else:
                        outcome = None
                        reason = (
                            'Non-standard uplink: uplink_ports_per_switch is 0 '
                            'and no peer_zone is set'
                        )
                elif near_xcvr_mt is None:
                    outcome = 'needs_review'
                    reason = 'Transceiver intent not specified on this zone'
                else:
                    outcome = None
                    reason = 'No peer_zone configured — standard leaf→spine zones are unpaired'

                rows.append(SwitchFabricRow(
                    near_zone_name=zone.zone_name,
                    near_fabric_name=sc.fabric_name,
                    near_zone_type=zone.zone_type,
                    near_xcvr_label=_xcvr_label(near_xcvr_mt),
                    far_zone_name=None,
                    far_fabric_name=None,
                    far_xcvr_label=None,
                    is_paired=False,
                    is_inferred=False,
                    outcome=outcome,
                    reason=reason,
                    edit_near_zone_url=near_url,
                    edit_far_zone_url=None,
                ))
                continue

            # Eligible uplink: attempt inference.
            candidates = spine_fabric_map.get(sc.fabric_name, [])

            if len(candidates) == 0:
                # No spine candidate — genuinely unpaired.
                fabric = sc.fabric_name
                if near_xcvr_mt is None:
                    outcome = 'needs_review'
                    reason = (
                        f"Transceiver intent not specified — no managed spine "
                        f"FABRIC zone found in fabric '{fabric}'"
                    )
                else:
                    outcome = None
                    reason = (
                        f"No managed spine FABRIC zone found in fabric '{fabric}' "
                        f"— check switch class configuration"
                    )
                rows.append(SwitchFabricRow(
                    near_zone_name=zone.zone_name,
                    near_fabric_name=sc.fabric_name,
                    near_zone_type=zone.zone_type,
                    near_xcvr_label=_xcvr_label(near_xcvr_mt),
                    far_zone_name=None,
                    far_fabric_name=None,
                    far_xcvr_label=None,
                    is_paired=False,
                    is_inferred=False,
                    outcome=outcome,
                    reason=reason,
                    edit_near_zone_url=near_url,
                    edit_far_zone_url=None,
                ))

            elif len(candidates) == 1:
                # Single candidate — inferred pair.
                far = candidates[0]
                far_xcvr_mt = far.transceiver_module_type
                outcome, reason = _infer_outcome(near_xcvr_mt, far_xcvr_mt)
                rows.append(SwitchFabricRow(
                    near_zone_name=zone.zone_name,
                    near_fabric_name=sc.fabric_name,
                    near_zone_type=zone.zone_type,
                    near_xcvr_label=_xcvr_label(near_xcvr_mt),
                    far_zone_name=far.zone_name,
                    far_fabric_name=far.switch_class.fabric_name,
                    far_xcvr_label=_xcvr_label(far_xcvr_mt),
                    is_paired=True,
                    is_inferred=True,
                    outcome=outcome,
                    reason=reason,
                    edit_near_zone_url=near_url,
                    edit_far_zone_url=reverse(
                        'plugins:netbox_hedgehog:switchportzone_edit', args=[far.pk]
                    ),
                ))

            else:
                # Multiple candidates — pooled row.
                n = len(candidates)
                outcome, reason = _pool_outcome(near_xcvr_mt, candidates)
                pool_mts = [c.transceiver_module_type for c in candidates]
                non_null = [mt for mt in pool_mts if mt is not None]
                models = {mt.model for mt in non_null}
                if non_null and len(models) == 1:
                    far_xcvr_label = _xcvr_label(non_null[0])
                else:
                    far_xcvr_label = '—'
                rows.append(SwitchFabricRow(
                    near_zone_name=zone.zone_name,
                    near_fabric_name=sc.fabric_name,
                    near_zone_type=zone.zone_type,
                    near_xcvr_label=_xcvr_label(near_xcvr_mt),
                    far_zone_name=f'managed spine pool ({n} zones)',
                    far_fabric_name=sc.fabric_name,
                    far_xcvr_label=far_xcvr_label,
                    is_paired=True,
                    is_inferred=True,
                    outcome=outcome,
                    reason=reason,
                    edit_near_zone_url=near_url,
                    edit_far_zone_url=None,
                ))

    paired_count = sum(1 for r in rows if r.is_paired)
    unpaired_count = sum(1 for r in rows if not r.is_paired)
    inferred_count = sum(1 for r in rows if r.is_inferred)
    match_count = sum(1 for r in rows if r.outcome == 'match')
    needs_review_count = sum(1 for r in rows if r.outcome == 'needs_review')
    blocked_count = sum(1 for r in rows if r.outcome == 'blocked')

    return SwitchFabricReviewSummary(
        rows=rows,
        paired_count=paired_count,
        unpaired_count=unpaired_count,
        inferred_count=inferred_count,
        match_count=match_count,
        needs_review_count=needs_review_count,
        blocked_count=blocked_count,
    )
