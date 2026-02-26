"""
Snapshot builder for topology plan generation tracking.

Provides centralized snapshot logic used by both GenerationState and
DeviceGenerator to ensure consistency and prevent drift.

Per DIET #127: Comprehensive snapshot tracking for sync status detection.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from netbox_hedgehog.models.topology_planning import TopologyPlan


def build_plan_snapshot(plan: 'TopologyPlan') -> dict:
    """
    Build comprehensive snapshot of plan state for generation tracking.

    Captures all fields that affect device generation. Excludes plan metadata
    (name, customer_name, description) to avoid false "out of sync" on renames.

    Args:
        plan: TopologyPlan instance to snapshot

    Returns:
        dict with keys:
            - server_classes: List of server class snapshots
            - switch_classes: List of switch class snapshots
            - connections: List of connection snapshots
            - port_zones: List of port zone snapshots
            - mclag_domains: List of MCLAG domain snapshots

    Example:
        >>> plan = TopologyPlan.objects.get(pk=123)
        >>> snapshot = build_plan_snapshot(plan)
        >>> snapshot.keys()
        dict_keys(['server_classes', 'switch_classes', 'connections',
                   'port_zones', 'mclag_domains'])

    Note:
        All keys are always included (even if empty lists) for consistent
        comparison. Nullable fields are included as None to avoid
        missing-vs-None comparison issues.
    """
    from netbox_hedgehog.models.topology_planning import (
        PlanServerConnection,
        SwitchPortZone,
    )

    snapshot = {
        'server_classes': [],
        'switch_classes': [],
        'connections': [],
        'port_zones': [],
        'mclag_domains': [],
    }

    # Server classes (include device type and GPU config)
    for server_class in plan.server_classes.all():
        snapshot['server_classes'].append({
            'server_class_id': server_class.server_class_id,
            'quantity': server_class.quantity,
            'device_type_id': server_class.server_device_type_id,
            'gpus_per_server': server_class.gpus_per_server,
        })

    # Switch classes (include device type and configuration)
    for switch_class in plan.switch_classes.all():
        snapshot['switch_classes'].append({
            'switch_class_id': switch_class.switch_class_id,
            'effective_quantity': switch_class.effective_quantity,
            'device_type_extension_id': switch_class.device_type_extension_id,
            'fabric': switch_class.fabric or '',  # Normalize empty to ''
            'hedgehog_role': switch_class.hedgehog_role or '',  # Normalize empty to ''
            'uplink_ports_per_switch': switch_class.uplink_ports_per_switch,  # Can be None
            'mclag_pair': switch_class.mclag_pair,
        })

    # Connection definitions (all parameters that affect cable generation)
    for conn in PlanServerConnection.objects.filter(
        server_class__plan=plan
    ).select_related('server_class', 'target_zone', 'target_zone__switch_class'):
        snapshot['connections'].append({
            'connection_id': conn.connection_id,
            'server_class_id': conn.server_class.server_class_id,
            'target_zone_id': str(conn.target_zone),
            'ports_per_connection': conn.ports_per_connection,
            'hedgehog_conn_type': conn.hedgehog_conn_type,
            'distribution': conn.distribution or '',  # Normalize empty to ''
            'speed': conn.speed,
            'rail': conn.rail,  # Can be None
            'port_type': conn.port_type or '',  # Normalize empty to ''
        })

    # Port zones (actual model fields from SwitchPortZone)
    # IMPORTANT: Always include all keys, even if None, to ensure
    # consistent comparison (avoids false "out of sync" on null fields)
    for zone in SwitchPortZone.objects.filter(
        switch_class__plan=plan
    ).select_related('switch_class', 'breakout_option'):
        snapshot['port_zones'].append({
            'switch_class_id': zone.switch_class.switch_class_id,
            'zone_name': zone.zone_name,
            'zone_type': zone.zone_type,
            'port_spec': zone.port_spec,
            'breakout_option_id': zone.breakout_option_id,  # Can be None
            'allocation_strategy': zone.allocation_strategy,
            'allocation_order': zone.allocation_order,  # Can be None
            'priority': zone.priority,
        })

    # MCLAG domains
    for mclag in plan.mclag_domains.all():
        snapshot['mclag_domains'].append({
            'domain_id': mclag.domain_id,
            'switch_class_id': mclag.switch_class.switch_class_id,
            'peer_link_count': mclag.peer_link_count,
            'session_link_count': mclag.session_link_count,
        })

    return snapshot


def compare_snapshots(current: dict, previous: dict) -> bool:
    """
    Compare two plan snapshots for equality.

    Uses order-independent comparison for lists to handle different query
    ordering across snapshot builds. Handles None values correctly - all
    snapshot fields are always included (even if None) to ensure consistent
    comparison.

    Args:
        current: Current snapshot dict
        previous: Previous snapshot dict

    Returns:
        True if snapshots are equal, False otherwise

    Example:
        >>> snap1 = build_plan_snapshot(plan)
        >>> # ... modify plan ...
        >>> snap2 = build_plan_snapshot(plan)
        >>> compare_snapshots(snap1, snap2)
        False  # Plan changed

    Note:
        Snapshot builder always includes all keys, even if value is None,
        to avoid false "out of sync" due to missing-vs-None differences.
    """
    import json

    def normalize(data):
        """
        Normalize data for order-independent comparison.

        Handles None, empty strings, and other falsy values correctly.
        Sorts dict keys and list items for deterministic comparison.
        """
        if isinstance(data, dict):
            return {k: normalize(v) for k, v in sorted(data.items())}
        elif isinstance(data, list):
            return sorted(
                [normalize(item) for item in data],
                key=lambda x: json.dumps(x, sort_keys=True)
            )
        else:
            return data  # Preserves None, 0, "", False as-is

    return normalize(current) == normalize(previous)
