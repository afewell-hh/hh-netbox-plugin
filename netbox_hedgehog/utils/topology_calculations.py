"""
Topology Planning Calculation Engine (DIET-003)

Core switch quantity calculation logic for topology planning module.
Calculates required switch quantities based on server port demand, breakout math,
uplink reservations, and MCLAG pairing requirements.
"""

import math
from dataclasses import dataclass
from typing import Optional

from django.core.exceptions import ValidationError

from netbox_hedgehog.choices import PortZoneTypeChoices
from netbox_hedgehog.models.topology_planning import BreakoutOption, SwitchPortZone
from netbox_hedgehog.services.port_specification import PortSpecification


@dataclass
class PortCapacity:
    """
    Structured port capacity information for a connection type.

    Attributes:
        native_speed: Native port speed in Gbps (before breakout)
        port_count: Number of physical ports in the zone
        source_zone: SwitchPortZone if zone-based, None if fallback
        is_fallback: True if using DeviceTypeExtension.native_speed fallback

    Examples:
        Zone-based (ES1000 server zone):
        >>> PortCapacity(native_speed=1, port_count=48, source_zone=zone, is_fallback=False)

        Fallback (DS5000 with no zones):
        >>> PortCapacity(native_speed=800, port_count=64, source_zone=None, is_fallback=True)
    """
    native_speed: int
    port_count: int
    source_zone: Optional['SwitchPortZone']
    is_fallback: bool


def get_physical_port_count(device_type: 'DeviceType') -> int:
    """
    Get physical port count for a device type from InterfaceTemplate.

    Queries NetBox InterfaceTemplate to count the number of interface templates
    defined for the device type. This provides the accurate port count for
    switches with any number of ports (32, 48, 64, etc.).

    Args:
        device_type: NetBox DeviceType instance

    Returns:
        int: Number of physical ports on the device type
            - Returns actual count from InterfaceTemplate if available
            - Returns 64 (default) if no InterfaceTemplates defined

    Examples:
        >>> # DS5000 with 64 InterfaceTemplates
        >>> device_type = DeviceType.objects.get(slug='ds5000')
        >>> get_physical_port_count(device_type)
        64

        >>> # DS3000 with 32 InterfaceTemplates
        >>> device_type = DeviceType.objects.get(slug='ds3000')
        >>> get_physical_port_count(device_type)
        32

        >>> # Device type without InterfaceTemplates (legacy)
        >>> device_type = DeviceType.objects.get(slug='legacy-switch')
        >>> get_physical_port_count(device_type)
        64  # Fallback

    Note:
        This function counts ALL InterfaceTemplates, which is appropriate for
        uniform-port switches (DS5000, DS3000). For mixed-port switches
        (ES1000 with 48×1G + 4×25G), use zone-based capacity from DIET-SPEC-002.
    """
    from dcim.models import InterfaceTemplate

    port_count = InterfaceTemplate.objects.filter(
        device_type=device_type
    ).count()

    if port_count == 0:
        # No InterfaceTemplates defined - use fallback
        # This maintains backward compatibility for device types created
        # before InterfaceTemplates were added
        return 64

    return port_count


def get_port_capacity_for_connection(
    device_extension: 'DeviceTypeExtension',
    switch_class: 'PlanSwitchClass',
    connection_type: str
) -> PortCapacity:
    """
    Get port capacity for a specific connection type (server/uplink/fabric).

    For switches with SwitchPortZone defined, returns zone-specific capacity.
    For switches without zones, falls back to DeviceTypeExtension.native_speed.

    Args:
        device_extension: DeviceTypeExtension with native_speed fallback
        switch_class: PlanSwitchClass with port zones
        connection_type: Connection type ('server', 'uplink', 'fabric')
                        Must match PortZoneTypeChoices values

    Returns:
        PortCapacity with native_speed, port_count, source_zone, is_fallback

    Raises:
        ValidationError: If connection_type invalid
        ValidationError: If no zones AND no native_speed fallback available
        ValidationError: If zone exists but has no breakout_option

    Examples:
        >>> # ES1000 with zones defined
        >>> capacity = get_port_capacity_for_connection(ext, switch_class, 'server')
        >>> capacity.native_speed  # 1 (from 'server-ports' zone)
        >>> capacity.port_count    # 48 (ports 1-48)
        >>> capacity.is_fallback   # False

        >>> # DS5000 without zones (legacy)
        >>> capacity = get_port_capacity_for_connection(ext, switch_class, 'server')
        >>> capacity.native_speed  # 800 (from ext.native_speed)
        >>> capacity.port_count    # 64 (from get_physical_port_count())
        >>> capacity.is_fallback   # True
    """
    # Step 1: Validate connection_type
    # NOTE: Must match PortZoneTypeChoices values
    valid_types = [
        PortZoneTypeChoices.SERVER,
        PortZoneTypeChoices.UPLINK,
        PortZoneTypeChoices.FABRIC
    ]
    if connection_type not in valid_types:
        raise ValidationError(
            f"Invalid connection_type: '{connection_type}'. "
            f"Must be one of: {', '.join(valid_types)}"
        )

    # Step 2: Query for zones matching connection type
    zones = SwitchPortZone.objects.filter(
        switch_class=switch_class,
        zone_type=connection_type
    ).select_related('breakout_option').order_by('priority')

    # Step 3: Zone-based path (new behavior)
    if zones.exists():
        # Use first zone (ordered by priority)
        zone = zones.first()

        # Validate zone has breakout_option
        if not zone.breakout_option:
            raise ValidationError(
                f"SwitchPortZone '{zone.zone_name}' has no breakout_option defined. "
                f"Cannot determine native speed."
            )

        # Get speed from breakout option
        native_speed = zone.breakout_option.from_speed

        # Parse port spec to get port count
        try:
            port_list = PortSpecification(zone.port_spec).parse()
            port_count = len(port_list)
        except ValidationError as e:
            raise ValidationError(
                f"Invalid port_spec in zone '{zone.zone_name}': {e}"
            )

        return PortCapacity(
            native_speed=native_speed,
            port_count=port_count,
            source_zone=zone,
            is_fallback=False
        )

    # Step 4: Fallback path (legacy behavior - backward compatible)
    # No zones defined - use DeviceTypeExtension.native_speed

    native_speed = device_extension.native_speed
    if not native_speed:
        raise ValidationError(
            f"Device type '{device_extension.device_type.slug}' has no zones "
            f"and no native_speed fallback defined. Cannot determine capacity."
        )

    # Reuse SPEC-001 function for port count (consistent logic)
    port_count = get_physical_port_count(device_extension.device_type)

    return PortCapacity(
        native_speed=native_speed,
        port_count=port_count,
        source_zone=None,
        is_fallback=True
    )


def get_uplink_port_count(switch_class: 'PlanSwitchClass') -> int:
    """
    Get uplink port count with override and zone-based derivation.

    Priority order:
    1. PlanSwitchClass.uplink_ports_per_switch (explicit override)
    2. SwitchPortZone with zone_type='uplink' (derived from zones)
    3. Error (neither override nor zones defined)

    Args:
        switch_class: PlanSwitchClass with optional uplink configuration

    Returns:
        int: Number of uplink ports to reserve

    Raises:
        ValidationError: If neither override nor zones are defined

    Examples:
        >>> # Case 1: Explicit override (highest priority)
        >>> switch_class.uplink_ports_per_switch = 8
        >>> get_uplink_port_count(switch_class)
        8

        >>> # Case 2: Derived from zones
        >>> # Zone: port_spec='49-52' → 4 ports
        >>> switch_class.uplink_ports_per_switch = None
        >>> get_uplink_port_count(switch_class)
        4

        >>> # Case 3: Override takes precedence over zones
        >>> # Even if zones exist, override wins
        >>> switch_class.uplink_ports_per_switch = 6
        >>> get_uplink_port_count(switch_class)  # Returns 6, not zone count
        6
    """
    # Priority 1: Explicit override (plan-level)
    if switch_class.uplink_ports_per_switch is not None:
        return switch_class.uplink_ports_per_switch

    # Priority 2: Derive from uplink zones
    uplink_zones = SwitchPortZone.objects.filter(
        switch_class=switch_class,
        zone_type=PortZoneTypeChoices.UPLINK
    )

    if uplink_zones.exists():
        # Sum port counts across all uplink zones
        total_uplink_ports = 0
        for zone in uplink_zones:
            try:
                port_list = PortSpecification(zone.port_spec).parse()
                total_uplink_ports += len(port_list)
            except ValidationError as e:
                raise ValidationError(
                    f"Invalid port_spec in uplink zone '{zone.zone_name}': {e}"
                )

        return total_uplink_ports

    # Priority 3: Error - no configuration found
    raise ValidationError(
        f"Switch class '{switch_class.switch_class_id}' has no uplink capacity defined. "
        f"Set PlanSwitchClass.uplink_ports_per_switch or create SwitchPortZone with zone_type='uplink'."
    )


def determine_optimal_breakout(
    native_speed: int,
    required_speed: int,
    supported_breakouts: list[str]
) -> BreakoutOption:
    """
    Determine the optimal breakout option for a given connection speed requirement.

    Finds the best BreakoutOption from the database that matches:
    1. The native port speed
    2. The required logical port speed
    3. Is in the supported_breakouts list (if policy is set)

    Policy Semantics:
    - If supported_breakouts is empty: No policy enforced, synthetic fallback allowed
    - If supported_breakouts is non-empty: Strict allow-list, only listed breakouts permitted

    Args:
        native_speed: Native port speed in Gbps (e.g., 800 for 800G)
        required_speed: Required connection speed in Gbps (e.g., 200 for 200G)
        supported_breakouts: List of supported breakout IDs (empty = no policy)

    Returns:
        BreakoutOption: The optimal breakout configuration
            - If exact match found: returns matching BreakoutOption from DB
            - If no match but 1:1 in policy: returns 1:1 BreakoutOption from DB
            - If no match and no policy (empty list): creates synthetic 1:1 breakout

    Raises:
        ValidationError: If supported_breakouts is non-empty but has no suitable match

    Examples:
        >>> determine_optimal_breakout(800, 400, ['1x800g', '2x400g', '4x200g'])
        <BreakoutOption: 2x400G (from 800G)>

        >>> determine_optimal_breakout(800, 200, ['1x800g', '2x400g', '4x200g'])
        <BreakoutOption: 4x200G (from 800G)>

        >>> determine_optimal_breakout(100, 25, ['1x100g', '4x25g'])
        <BreakoutOption: 4x25G (from 100G)>

        >>> determine_optimal_breakout(800, 50, ['1x800g', '2x400g'])  # No 50G option
        <BreakoutOption: 1x800G (from 800G)>  # Falls back to native if in policy

        >>> determine_optimal_breakout(800, 200, [])  # Empty = no policy
        <SyntheticBreakout: 1x800G>  # Synthetic fallback allowed

        >>> determine_optimal_breakout(800, 50, ['2x400g', '4x200g'])  # No match in policy
        ValidationError  # No 50G or 1x800g in policy
    """
    # If supported_breakouts is non-empty (policy set), enforce strict allow-list
    if supported_breakouts:
        # Query for breakout options that match:
        # 1. Native speed matches
        # 2. Logical speed matches required speed
        # 3. Breakout ID is in supported list
        matching_breakout = BreakoutOption.objects.filter(
            from_speed=native_speed,
            logical_speed=required_speed,
            breakout_id__in=supported_breakouts
        ).first()

        if matching_breakout:
            return matching_breakout

        # No exact match - fallback to native speed (1:1)
        fallback_breakout = BreakoutOption.objects.filter(
            from_speed=native_speed,
            logical_ports=1,
            breakout_id__in=supported_breakouts
        ).first()

        if fallback_breakout:
            return fallback_breakout

        # No match found in allow-list - raise ValidationError
        raise ValidationError(
            f"No suitable breakout found for {required_speed}G connection on {native_speed}G port. "
            f"Supported breakouts: {', '.join(supported_breakouts)}. "
            f"Add a compatible breakout option (e.g., matching speed or 1x{native_speed}g) "
            f"to the device type's supported_breakouts list."
        )

    # No policy set (supported_breakouts is empty)
    # Create synthetic 1:1 breakout as fallback
    # This is not saved to DB, just used for calculation
    class SyntheticBreakout:
        """Synthetic breakout option for fallback when no policy exists"""
        def __init__(self, speed):
            self.breakout_id = f'1x{speed}g'
            self.from_speed = speed
            self.logical_ports = 1
            self.logical_speed = speed

    return SyntheticBreakout(native_speed)


def calculate_switch_quantity(switch_class) -> int:
    """
    Calculate required switch quantity for a PlanSwitchClass based on port demand.

    Implements the core calculation algorithm:
    1. Sum port demand from all connections targeting this switch class
    2. For rail-optimized connections, calculate total demand across rails
    3. Determine optimal breakout based on connection speeds
    4. Calculate logical ports per switch (physical_ports × breakout_factor)
    5. Subtract uplink ports from available capacity
    6. Calculate switches needed: ceil(total_ports_needed / available_ports)
    7. Enforce MCLAG even-count requirement if mclag_pair=True

    Args:
        switch_class: PlanSwitchClass instance to calculate quantity for

    Returns:
        int: Required number of switches
            - Returns 0 if no connections target this switch class
            - Always returns even number if mclag_pair=True
            - For rail-optimized: rails can share switches when capacity allows

    Algorithm:
        # Check for rail-optimized connections
        if any connection has distribution='rail-optimized':
            # Calculate total demand across rails and allow sharing
            num_rails = count distinct rail values
            ports_per_rail = SUM(server_quantity × ports_per_connection) for each rail
            total_ports = SUM(ports_per_rail for all rails)
            switches_needed = CEILING(total_ports / available_ports)
            return switches_needed
        else:
            # Standard calculation
            total_ports_needed = SUM(server_class.quantity × connection.ports_per_connection)
            breakout = determine_optimal_breakout(native_speed, connection_speed, supported_breakouts)
            logical_ports_per_switch = physical_ports × breakout.logical_ports
            uplink_ports = get_uplink_port_count(switch_class)  # Override or zone-derived
            available_ports = logical_ports_per_switch - uplink_ports
            switches_needed = CEILING(total_ports_needed / available_ports)
            if mclag_pair and switches_needed % 2 != 0:
                switches_needed += 1
            return switches_needed

    Examples:
        >>> # 32 servers × 2x200G ports, DS5000 switch (64×800G), 4 uplinks
        >>> # Breakout: 4x200G → 256 logical ports, 256-4=252 available
        >>> # 64 ports needed ÷ 252 available = 0.25 → ceil = 1 switch
        >>> calculate_switch_quantity(switch_class)
        1

        >>> # 128 servers × 2x200G ports, same switch
        >>> # 256 ports needed ÷ 252 available = 1.015 → ceil = 2 switches
        >>> calculate_switch_quantity(switch_class)
        2

        >>> # Rail-optimized: 32 servers × 1x400G × 8 rails
        >>> # Total demand: 256 ports, 64 available → ceil(256/64) = 4 switches
        >>> calculate_switch_quantity(switch_class_rails)
        4
    """
    # Get all connections targeting this switch class
    connections = switch_class.incoming_connections.all()

    if not connections.exists():
        # No connections = no switches needed
        return 0

    # Check for rail-optimized connections
    rail_optimized_connections = connections.filter(distribution='rail-optimized')
    has_rail_optimized = rail_optimized_connections.exists()

    if has_rail_optimized:
        # Rail-optimized calculation: switches per rail
        # NOTE: This assumes ALL connections to this switch are rail-optimized
        # If mixing rail-optimized and non-rail connections, non-rail connections
        # will be ignored in the calculation, potentially under-counting switches.
        #
        # RECOMMENDATION: Add model-level validation to prevent mixing:
        #   - Option 1: Add "fabric_mode" field (normal|rail-only|rail-optimized)
        #               and enforce connection types based on mode
        #   - Option 2: Add clean() method to PlanServerConnection to validate
        #               that all connections to a rail-optimized switch are rail-optimized
        #
        # TODO(Agent A): Add validation when fabric_mode is implemented per Agent C feedback
        return _calculate_rail_optimized_switches(
            switch_class,
            rail_optimized_connections
        )

    # Standard (non-rail) calculation
    # Step 1: Calculate total port demand
    total_ports_needed = 0
    connection_speeds = []

    for connection in connections:
        server_quantity = connection.server_class.quantity
        ports_per_connection = connection.ports_per_connection
        total_ports_needed += server_quantity * ports_per_connection
        connection_speeds.append(connection.speed)

    # Step 2: Determine primary connection speed (use most common speed)
    # For MVP, we assume all connections use the same speed
    # TODO: Handle mixed speeds (multiple breakouts) in post-MVP
    primary_speed = connection_speeds[0] if connection_speeds else 800

    # Step 3: Get switch capacity from DeviceTypeExtension
    device_extension = switch_class.device_type_extension

    # Get zone-based capacity for server connections
    capacity = get_port_capacity_for_connection(
        device_extension=device_extension,
        switch_class=switch_class,
        connection_type=PortZoneTypeChoices.SERVER
    )
    native_speed = capacity.native_speed
    physical_ports = capacity.port_count
    supported_breakouts = device_extension.supported_breakouts or []

    # Step 4: Determine optimal breakout
    breakout = determine_optimal_breakout(
        native_speed=native_speed,
        required_speed=primary_speed,
        supported_breakouts=supported_breakouts
    )

    # Step 5: Calculate logical ports per switch
    logical_ports_per_switch = physical_ports * breakout.logical_ports

    # Step 6: Subtract uplink ports (conditional based on capacity source)
    # Zone-based (is_fallback=False): capacity.port_count is server zone ONLY (excludes uplinks)
    # Fallback (is_fallback=True): capacity.port_count includes ALL ports (must subtract uplinks)
    if capacity.is_fallback:
        # Fallback path: total ports includes uplinks, subtract them
        uplink_ports = get_uplink_port_count(switch_class)
        available_ports_per_switch = logical_ports_per_switch - uplink_ports
    else:
        # Zone-based path: server zone already excludes uplinks, don't subtract
        available_ports_per_switch = logical_ports_per_switch

    if available_ports_per_switch <= 0:
        # All ports reserved for uplinks, cannot accept server connections
        # This is likely a configuration error
        return 0

    # Step 7: Calculate switches needed
    switches_needed = math.ceil(total_ports_needed / available_ports_per_switch)

    # Step 8: Enforce MCLAG even-count requirement
    if switch_class.mclag_pair and switches_needed % 2 != 0:
        switches_needed += 1

    # Ensure at least 1 switch if there are connections
    if total_ports_needed > 0 and switches_needed == 0:
        switches_needed = 1

    return switches_needed


def _calculate_rail_optimized_switches(switch_class, rail_connections) -> int:
    """
    Calculate switch quantity for rail-optimized connections.

    Rail-optimized distribution means servers spread across rails connect to
    switches such that all NICs on the same rail connect to the same switch.
    Multiple rails can share a switch when capacity allows.

    Args:
        switch_class: PlanSwitchClass instance
        rail_connections: QuerySet of rail-optimized connections

    Returns:
        int: Total switches needed based on total port demand across all rails

    Algorithm:
        1. Group connections by rail number
        2. Calculate TOTAL port demand across all rails
        3. Calculate total switches = ceil(total_demand / available_ports)
        4. Multiple rails share switches when capacity allows

    Example:
        32 servers × 1×400G NIC per rail × 8 rails = 256×400G total demand
        Each switch: 64×400G capacity
        Result: ceil(256/64) = 4 switches (2 rails per switch)
    """
    # Get device extension for switch specs
    device_extension = switch_class.device_type_extension

    # Get connection speed (assume all rail connections use same speed)
    primary_speed = rail_connections.first().speed if rail_connections.exists() else 800

    # Get zone-based capacity for server connections
    capacity = get_port_capacity_for_connection(
        device_extension=device_extension,
        switch_class=switch_class,
        connection_type=PortZoneTypeChoices.SERVER
    )
    native_speed = capacity.native_speed
    physical_ports = capacity.port_count
    supported_breakouts = device_extension.supported_breakouts or []

    # Determine optimal breakout
    breakout = determine_optimal_breakout(
        native_speed=native_speed,
        required_speed=primary_speed,
        supported_breakouts=supported_breakouts
    )

    # Calculate available ports per switch
    logical_ports_per_switch = physical_ports * breakout.logical_ports

    # Conditional uplink subtraction based on capacity source
    if capacity.is_fallback:
        # Fallback path: total ports includes uplinks, subtract them
        uplink_ports = get_uplink_port_count(switch_class)
        available_ports_per_switch = logical_ports_per_switch - uplink_ports
    else:
        # Zone-based path: server zone already excludes uplinks, don't subtract
        available_ports_per_switch = logical_ports_per_switch

    if available_ports_per_switch <= 0:
        return 0

    # Group connections by rail and calculate port demand per rail
    rails = {}
    for connection in rail_connections:
        rail_num = connection.rail
        if rail_num is None:
            # Skip connections without rail number
            continue

        if rail_num not in rails:
            rails[rail_num] = 0

        server_quantity = connection.server_class.quantity
        ports_per_connection = connection.ports_per_connection
        rails[rail_num] += server_quantity * ports_per_connection

    if not rails:
        # No valid rail connections
        return 0

    # Calculate TOTAL port demand across all rails
    # Rails can share switches when capacity allows
    total_port_demand = sum(rails.values())

    # Calculate total switches needed based on total demand
    total_switches = math.ceil(total_port_demand / available_ports_per_switch)

    # Ensure at least 1 switch if there's any demand
    if total_port_demand > 0 and total_switches == 0:
        total_switches = 1

    # Enforce MCLAG even-count requirement
    if switch_class.mclag_pair and total_switches % 2 != 0:
        total_switches += 1

    return total_switches


def determine_leaf_uplink_breakout(
    leaf_switch_class,
    spines_needed: int,
    min_link_speed: int = 800
):
    """
    Determine required uplink breakout for a leaf to connect to all spines.

    When the number of spines exceeds the physical uplink ports on a leaf,
    breakout is required to create enough logical ports for even distribution.

    Args:
        leaf_switch_class: PlanSwitchClass instance (leaf switch)
        spines_needed: Number of spine switches to connect to
        min_link_speed: Minimum acceptable link speed in Gbps (default: 800)

    Returns:
        BreakoutOption: Selected breakout configuration, or None if impossible

    Algorithm:
        1. Calculate required breakout factor: ceil(spines_needed / physical_ports)
        2. Find smallest supported breakout where:
           - logical_ports >= breakout_factor_needed
           - logical_speed >= min_link_speed
        3. Return None if no valid breakout exists

    Examples:
        >>> # 32 physical ports, 64 spines → needs 2x breakout
        >>> # Available: 2x400G (64 logical ports @ 400G)
        >>> determine_leaf_uplink_breakout(leaf, 64, 400)
        <BreakoutOption: 2x400G>

        >>> # 32 physical ports, 16 spines → no breakout needed
        >>> determine_leaf_uplink_breakout(leaf, 16, 800)
        <BreakoutOption: 1x800G>

        >>> # 32 physical ports, 512 spines → impossible (needs 16x)
        >>> determine_leaf_uplink_breakout(leaf, 512, 100)
        None
    """
    # Early exit for edge cases
    if spines_needed <= 0:
        # No spines = no uplink interfaces needed
        return None

    # Get physical uplink ports (use helper to support zone-based derivation)
    try:
        physical_uplink_ports = get_uplink_port_count(leaf_switch_class)
    except ValidationError:
        # No uplink configuration (neither override nor zones)
        # This is expected for switches that don't have uplinks (e.g., top-of-rack only)
        return None

    if physical_uplink_ports <= 0:
        # No uplink ports configured (override set to 0)
        return None

    # Get device extension for supported breakouts
    device_extension = leaf_switch_class.device_type_extension
    native_speed = device_extension.native_speed or 800
    supported_breakouts = device_extension.supported_breakouts or []

    # Calculate minimum breakout factor needed
    # If spines <= physical_ports, factor is 1 (no breakout)
    breakout_factor_needed = math.ceil(spines_needed / physical_uplink_ports)

    # If supported_breakouts is empty (no policy), create synthetic 1x when appropriate
    if not supported_breakouts:
        if breakout_factor_needed == 1 and native_speed >= min_link_speed:
            # No policy set - safe to create synthetic 1:1 breakout
            class SyntheticBreakout:
                """Synthetic 1x breakout for fallback when no policy exists"""
                def __init__(self, speed):
                    self.breakout_id = f'1x{speed}g'
                    self.from_speed = speed
                    self.logical_ports = 1
                    self.logical_speed = speed

            return SyntheticBreakout(native_speed)
        else:
            # No breakouts configured and need breakout (not 1x)
            return None

    # supported_breakouts is non-empty - enforce policy
    # Query for all supported breakout options from DB
    # Filter by: native speed matches, breakout_id is in supported list
    candidate_breakouts = BreakoutOption.objects.filter(
        from_speed=native_speed,
        breakout_id__in=supported_breakouts
    ).order_by('logical_ports')  # Order by factor (smallest first)

    # Find smallest breakout that satisfies both:
    # 1. logical_ports >= breakout_factor_needed
    # 2. logical_speed >= min_link_speed
    for breakout in candidate_breakouts:
        # Check if this breakout provides enough logical ports
        if breakout.logical_ports >= breakout_factor_needed:
            # Check if link speed is acceptable
            if breakout.logical_speed >= min_link_speed:
                return breakout

    # No valid breakout found in supported list
    # Do NOT create synthetic - policy explicitly excludes what we need
    return None


def calculate_spine_quantity(spine_switch_class) -> int:
    """
    Calculate required spine switch quantity based on leaf uplink demand.

    Spine switches aggregate uplinks from all leaf switches in the same fabric.
    This function calculates how many spine switches are needed to accommodate
    all leaf uplinks.

    IMPORTANT: After calculating spine quantity, use determine_leaf_uplink_breakout()
    to verify that leaves can physically connect to all spines (may require breakouts).

    Args:
        spine_switch_class: PlanSwitchClass instance with hedgehog_role='spine'

    Returns:
        int: Required number of spine switches
            - Returns 0 if no leaves exist in the same fabric
            - Based on total uplink demand from all leaves

    Algorithm:
        1. Find all leaf switches in the same fabric and plan
        2. Calculate total uplink demand: sum(leaf.effective_quantity × get_uplink_port_count(leaf))
           - get_uplink_port_count() returns override or zone-derived uplink count per leaf
        3. Calculate available downlink ports per spine
        4. Spine quantity = ceil(total_uplink_demand / available_downlink_ports)

    Usage Pattern:
        # Step 1: Calculate how many spines are needed (bandwidth-based)
        spines_needed = calculate_spine_quantity(spine_switch_class)

        # Step 2: For each leaf class, determine required uplink breakout
        for leaf in leaf_switches:
            breakout = determine_leaf_uplink_breakout(
                leaf_switch_class=leaf,
                spines_needed=spines_needed,
                min_link_speed=800  # Or appropriate speed for your topology
            )
            if breakout is None:
                # Error: Cannot connect to all spines with supported breakouts
                # Either reduce spine count or use different switch model
                raise ValidationError(...)
            # Use breakout during device generation to create proper interfaces

    Examples:
        >>> # 2 leaf switches × 32 uplinks = 64 uplink ports
        >>> # Spine: 64 ports available (no uplinks on spine)
        >>> # Result: ceil(64/64) = 1 spine
        >>> calculate_spine_quantity(fe_spine)
        1

        >>> # Multiple leaves: 2 GPU + 1 Storage-A + 1 Storage-B
        >>> # (2 + 1 + 1) × 32 uplinks = 128 uplink ports
        >>> # Spine: 64 ports available
        >>> # Result: ceil(128/64) = 2 spines
        >>> calculate_spine_quantity(fe_spine)
        2

        >>> # Large fabric: 128 leaves × 32 uplinks = 4096 uplink ports
        >>> # Spine: 64 ports available
        >>> # Result: ceil(4096/64) = 64 spines
        >>> # Note: Each leaf needs 2x breakout (64 spines ÷ 32 ports = 2x)
        >>> calculate_spine_quantity(fe_spine)
        64
    """
    # Get all switch classes in the same plan and fabric
    plan = spine_switch_class.plan
    fabric = spine_switch_class.fabric

    # Find all leaf switches (server-leaf, border-leaf) in the same fabric
    # Exclude spine switches themselves
    leaf_switches = plan.switch_classes.filter(
        fabric=fabric,
        hedgehog_role__in=['server-leaf', 'border-leaf']
    ).exclude(
        pk=spine_switch_class.pk
    )

    if not leaf_switches.exists():
        # No leaves = no spines needed
        return 0

    # Calculate total uplink demand from all leaves
    total_uplink_demand = 0
    for leaf in leaf_switches:
        # Use effective_quantity (respects overrides)
        leaf_quantity = leaf.effective_quantity

        # Get uplink port count (supports zone-based derivation)
        # Fail fast if any leaf lacks uplink configuration (per SPEC-003)
        try:
            uplink_ports = get_uplink_port_count(leaf)
        except ValidationError as e:
            raise ValidationError(
                f"Spine calculation failed: leaf switch class '{leaf.switch_class_id}' "
                f"has no uplink configuration. Either set uplink_ports_per_switch or "
                f"create SwitchPortZone with zone_type='uplink'. "
                f"For switches that intentionally have no spine uplinks, "
                f"set uplink_ports_per_switch=0."
            ) from e

        total_uplink_demand += leaf_quantity * uplink_ports

    if total_uplink_demand == 0:
        # No uplink demand
        return 0

    # Calculate available downlink ports on spine
    device_extension = spine_switch_class.device_type_extension

    # Get zone-based capacity for fabric connections (spine downlinks to leaves)
    # Spine's FABRIC zone is for leaf downlinks, UPLINK zone is for border/external
    capacity = get_port_capacity_for_connection(
        device_extension=device_extension,
        switch_class=spine_switch_class,
        connection_type=PortZoneTypeChoices.FABRIC
    )
    native_speed = capacity.native_speed
    physical_ports = capacity.port_count
    supported_breakouts = device_extension.supported_breakouts or []

    # Spines typically use 1x800G (no breakout) for leaf connections
    # Use the native speed for spine-to-leaf links
    breakout = determine_optimal_breakout(
        native_speed=native_speed,
        required_speed=native_speed,  # Use native speed for spine
        supported_breakouts=supported_breakouts
    )

    # Calculate available ports per spine
    logical_ports_per_spine = physical_ports * breakout.logical_ports

    # Conditional uplink subtraction based on capacity source
    # Spines may have uplink ports for border/external connections
    if capacity.is_fallback:
        # Fallback path: total ports includes uplinks, subtract them
        spine_uplink_ports = get_uplink_port_count(spine_switch_class)
        available_downlink_ports = logical_ports_per_spine - spine_uplink_ports
    else:
        # Zone-based path: uplink zone already configured for downlink capacity
        available_downlink_ports = logical_ports_per_spine

    if available_downlink_ports <= 0:
        # All ports reserved for uplinks, cannot accept leaf connections
        return 0

    # Calculate spines needed
    spines_needed = math.ceil(total_uplink_demand / available_downlink_ports)

    return spines_needed


def update_plan_calculations(plan):
    """
    Update calculated_quantity for all switch classes in a topology plan.

    Convenience function to recalculate all switch quantities in a plan.
    This should be called whenever:
    - Server quantities change
    - Connection specifications change
    - Switch classes are added/modified

    Calculation order:
    1. Calculate leaf switch quantities first (based on server connections)
    2. Calculate spine quantities second (based on leaf uplinks)

    Args:
        plan: TopologyPlan instance

    Returns:
        dict: Results containing summary and errors
            {
                'summary': {
                    'switch_class_id': {
                        'calculated': int,
                        'override': int or None,
                        'effective': int
                    },
                    ...
                },
                'errors': [
                    {
                        'switch_class': 'switch_class_id',
                        'error': 'error message'
                    },
                    ...
                ]
            }

    Example:
        >>> result = update_plan_calculations(plan)
        >>> result['summary']['fe-gpu-leaf']
        {'calculated': 2, 'override': None, 'effective': 2}
        >>> result['errors']
        []  # No errors
    """
    summary = {}
    errors = []

    # First pass: Calculate leaf switches (server-leaf, border-leaf)
    leaf_switches = plan.switch_classes.filter(
        hedgehog_role__in=['server-leaf', 'border-leaf']
    )
    for switch_class in leaf_switches:
        try:
            calculated = calculate_switch_quantity(switch_class)
            switch_class.calculated_quantity = calculated
            switch_class.save(update_fields=['calculated_quantity'])

            summary[switch_class.switch_class_id] = {
                'calculated': calculated,
                'override': switch_class.override_quantity,
                'effective': switch_class.effective_quantity
            }
        except ValidationError as e:
            errors.append({
                'switch_class': switch_class.switch_class_id,
                'error': str(e)
            })

    # Second pass: Calculate spine switches (based on leaf quantities)
    # Skip if leaf calculations failed - spines depend on accurate leaf quantities
    if errors:
        # Leaf errors exist - skip spine calculations to avoid inconsistent results
        spine_switches = plan.switch_classes.filter(hedgehog_role='spine')
        for switch_class in spine_switches:
            errors.append({
                'switch_class': switch_class.switch_class_id,
                'error': 'Skipped: spine calculation requires successful leaf calculations'
            })
    else:
        # No leaf errors - safe to calculate spines
        spine_switches = plan.switch_classes.filter(hedgehog_role='spine')
        for switch_class in spine_switches:
            try:
                calculated = calculate_spine_quantity(switch_class)
                switch_class.calculated_quantity = calculated
                switch_class.save(update_fields=['calculated_quantity'])

                summary[switch_class.switch_class_id] = {
                    'calculated': calculated,
                    'override': switch_class.override_quantity,
                    'effective': switch_class.effective_quantity
                }
            except ValidationError as e:
                errors.append({
                    'switch_class': switch_class.switch_class_id,
                    'error': str(e)
                })

    # Third pass: Any other switch types (virtual, etc.)
    other_switches = plan.switch_classes.exclude(
        hedgehog_role__in=['server-leaf', 'border-leaf', 'spine']
    )
    for switch_class in other_switches:
        try:
            calculated = calculate_switch_quantity(switch_class)
            switch_class.calculated_quantity = calculated
            switch_class.save(update_fields=['calculated_quantity'])

            summary[switch_class.switch_class_id] = {
                'calculated': calculated,
                'override': switch_class.override_quantity,
                'effective': switch_class.effective_quantity
            }
        except ValidationError as e:
            errors.append({
                'switch_class': switch_class.switch_class_id,
                'error': str(e)
            })

    return {
        'summary': summary,
        'errors': errors
    }
