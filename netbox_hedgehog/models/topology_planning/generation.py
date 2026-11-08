"""
Generation state models for topology planning.

GenerationState tracks the state of NetBox object generation from a TopologyPlan.
"""

import copy

from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.urls import reverse

from netbox_hedgehog.choices import GenerationStatusChoices
from netbox_hedgehog.utils.snapshot_builder import (
    build_plan_snapshot,
    compare_snapshots,
)

# Display-only sync classification values (issue #739).
SYNC_IN_SYNC = 'in_sync'
SYNC_CHANGED = 'changed'
SYNC_SNAPSHOT_INCOMPLETE = 'snapshot_incomplete'

# Server-class keys added to snapshots after some records were saved (DIET-607).
# When a saved record omits them, their historical values are UNKNOWN.
HISTORICAL_SERVER_CLASS_KEYS = ('place_in_racks', 'servers_per_rack', 'membership_only')

_SNAPSHOT_LIST_KEYS = (
    'server_classes', 'switch_classes', 'connections', 'port_zones', 'mclag_domains',
)


# Non-historical server-class fields every valid snapshot record must carry.
_REQUIRED_SERVER_CLASS_KEYS = (
    'server_class_id', 'quantity', 'device_type_id', 'gpus_per_server',
)
# Required fields per build_plan_snapshot(); nullable ones are always emitted
# (as None), so absence means missing evidence, not None.
_REQUIRED_SWITCH_CLASS_KEYS = (
    'switch_class_id', 'effective_quantity', 'device_type_extension_id',
    'fabric', 'fabric_name', 'fabric_class', 'hedgehog_role',
    'uplink_ports_per_switch', 'mclag_pair', 'topology_mode',
)
_REQUIRED_CONNECTION_KEYS = (
    'connection_id', 'server_class_id', 'target_zone_id', 'ports_per_connection',
    'hedgehog_conn_type', 'distribution', 'speed', 'rail', 'port_type',
)
_REQUIRED_PORT_ZONE_KEYS = (
    'switch_class_id', 'zone_name', 'zone_type', 'port_spec',
    'breakout_option_id', 'allocation_strategy', 'allocation_order', 'priority',
)
_REQUIRED_MCLAG_KEYS = (
    'domain_id', 'switch_class_id', 'peer_link_count', 'session_link_count',
)

# section -> (required keys, keys forming the unique stable identity)
_SECTION_CONTRACT = {
    'server_classes': (_REQUIRED_SERVER_CLASS_KEYS, ('server_class_id',)),
    'switch_classes': (_REQUIRED_SWITCH_CLASS_KEYS, ('switch_class_id',)),
    # PlanServerConnection.Meta.unique_together is [server_class, connection_id]
    'connections': (_REQUIRED_CONNECTION_KEYS, ('server_class_id', 'connection_id')),
    'port_zones': (_REQUIRED_PORT_ZONE_KEYS, ('switch_class_id', 'zone_name')),
    'mclag_domains': (_REQUIRED_MCLAG_KEYS, ('domain_id', 'switch_class_id')),
}


def _valid_server_class_index(snapshot):
    """
    Validate record shapes/identities; return server_class_id -> entry, or None.

    None means the evidence is malformed or unavailable: a non-list container,
    a non-dict record, a missing required field, or a missing/non-string/empty/
    duplicate identity. Historical keys (HISTORICAL_SERVER_CLASS_KEYS) are optional.
    """
    for key in _SNAPSHOT_LIST_KEYS:
        entries = snapshot.get(key)
        if not isinstance(entries, list):
            return None
        if any(not isinstance(entry, dict) for entry in entries):
            return None
    index = {}
    for section, (required, identity_keys) in _SECTION_CONTRACT.items():
        seen = set()
        for entry in snapshot[section]:
            if any(key not in entry for key in required):
                return None
            identity = tuple(entry[key] for key in identity_keys)
            if any(not isinstance(part, str) or not part for part in identity):
                return None
            if identity in seen:
                return None
            seen.add(identity)
            if section == 'server_classes':
                index[identity[0]] = entry
    return index


def _nic_extension_invalid(snapshot) -> bool:
    from netbox_hedgehog.services.nic_cage_layout import snapshot_extension_invalid

    return snapshot_extension_invalid(snapshot)


def classify_snapshot_sync(current, saved) -> str:
    """
    Pure, read-only DISPLAY classification of current vs saved snapshots.

    Returns SYNC_IN_SYNC, SYNC_CHANGED or SYNC_SNAPSHOT_INCOMPLETE.

    SYNC_SNAPSHOT_INCOMPLETE means the ONLY discrepancy is omission of known
    historical server-class keys on correctly matched identities; those saved
    values are unknown (neither changed nor proved in sync). A temporary
    projection is used solely for this classification; it is never returned,
    persisted, or used by compare_snapshots()/is_dirty() or any admission logic.
    Record shapes, required fields and identities of BOTH snapshots are
    validated BEFORE any equality check: malformed, missing or duplicate
    evidence is incomplete (never in sync, never a claimed modification),
    even when the two inputs are identical.
    """
    if not isinstance(saved, dict) or not isinstance(current, dict):
        return SYNC_SNAPSHOT_INCOMPLETE

    # CAGE37 snapshot_contract_v1: an invalid/malformed/unknown-version NIC
    # cage extension on EITHER side is incomplete BEFORE any equality, even
    # when both inputs are identical. With no extension on either side this
    # is a no-op and base classification is unchanged.
    if _nic_extension_invalid(current) or _nic_extension_invalid(saved):
        return SYNC_SNAPSHOT_INCOMPLETE

    try:
        saved_index = _valid_server_class_index(saved)
        current_index = _valid_server_class_index(current)
        if saved_index is None or current_index is None:
            return SYNC_SNAPSHOT_INCOMPLETE

        if any(key not in entry for entry in current_index.values()
               for key in HISTORICAL_SERVER_CLASS_KEYS):
            return SYNC_SNAPSHOT_INCOMPLETE

        if compare_snapshots(current, saved):
            return SYNC_IN_SYNC

        projected = copy.deepcopy(saved)
        filled = False
        for entry in projected['server_classes']:
            match = current_index.get(entry['server_class_id'])
            if match is None:
                continue
            for key in HISTORICAL_SERVER_CLASS_KEYS:
                if key not in entry and key in match:
                    entry[key] = copy.deepcopy(match[key])
                    filled = True
        if filled and compare_snapshots(current, projected):
            return SYNC_SNAPSHOT_INCOMPLETE
        return SYNC_CHANGED
    except (TypeError, ValueError):
        return SYNC_SNAPSHOT_INCOMPLETE


class GenerationState(models.Model):
    """
    Tracks generation state for a TopologyPlan.

    Used to detect when a plan has been modified since objects were last generated,
    enabling reconciliation and re-generation workflows.
    """

    plan = models.OneToOneField(
        to='netbox_hedgehog.TopologyPlan',
        on_delete=models.CASCADE,
        related_name='generation_state',
        help_text="Topology plan this state belongs to"
    )

    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When generation occurred"
    )

    device_count = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Number of devices generated"
    )

    interface_count = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Number of interfaces generated"
    )

    cable_count = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Number of cables generated"
    )

    snapshot = models.JSONField(
        help_text="Plan state at generation time (for change detection)"
    )

    status = models.CharField(
        max_length=50,
        choices=GenerationStatusChoices,
        default=GenerationStatusChoices.GENERATED,
        help_text="Current generation status"
    )

    job = models.ForeignKey(
        to='core.Job',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='topology_generation',
        help_text="NetBox Job executing or that executed this generation"
    )

    mismatch_report = models.JSONField(
        null=True,
        blank=True,
        default=None,
        help_text=(
            'Structured list of transceiver incompatibilities found during '
            'post-generation pairwise sweep. Null when generation succeeded '
            'or has not run. Set before status=FAILED when mismatches found.'
        ),
    )

    class Meta:
        verbose_name = "Generation State"
        verbose_name_plural = "Generation States"

    def __str__(self):
        """String representation"""
        return f"{self.plan.name} - {self.device_count} devices"

    def get_absolute_url(self):
        """Get absolute URL for this object"""
        return reverse('plugins:netbox_hedgehog:generationstate', args=[self.pk])

    def is_dirty(self) -> bool:
        """
        Check if plan has been modified since generation.

        Compares current plan state against snapshot saved at generation time.
        Detects changes to server classes, switch classes, connections, port
        zones, and MCLAG domains.

        Returns:
            bool: True if plan differs from snapshot, False otherwise

        Example:
            >>> state = GenerationState.objects.get(plan=plan)
            >>> state.is_dirty()
            False  # No changes since generation
            >>> plan.server_classes.first().quantity = 64
            >>> plan.server_classes.first().save()
            >>> state.is_dirty()
            True  # Quantity changed

        Note:
            Uses shared snapshot builder (netbox_hedgehog.utils.snapshot_builder)
            to ensure consistency with DeviceGenerator snapshot logic.
        """
        current = build_plan_snapshot(self.plan)
        # snapshot_contract_v1: invalid extension on either side is dirty
        # BEFORE equality (including identical invalid). Missing-vs-present
        # extension is a key difference, so compare_snapshots reports dirty.
        if _nic_extension_invalid(current) or _nic_extension_invalid(self.snapshot):
            return True
        return not compare_snapshots(current, self.snapshot)

    def sync_display_state(self, current=None) -> str:
        """
        Read-only display classification: in_sync / changed / snapshot_incomplete.

        Does not alter is_dirty() or needs_regeneration; for an incomplete
        snapshot those remain True. Grants no generation or retry authority.
        """
        if current is None:
            current = build_plan_snapshot(self.plan)
        return classify_snapshot_sync(current, self.snapshot)
