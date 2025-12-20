"""
Topology Planning Calculation Engine (DIET-003)

Core switch quantity calculation logic for topology planning module.
Calculates required switch quantities based on server port demand, breakout math,
uplink reservations, and MCLAG pairing requirements.
"""

import math
from typing import Optional

from netbox_hedgehog.models.topology_planning import BreakoutOption


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
    3. Is in the supported_breakouts list

    Args:
        native_speed: Native port speed in Gbps (e.g., 800 for 800G)
        required_speed: Required connection speed in Gbps (e.g., 200 for 200G)
        supported_breakouts: List of supported breakout IDs (e.g., ['1x800g', '2x400g', '4x200g'])

    Returns:
        BreakoutOption: The optimal breakout configuration
            - If exact match found: returns matching BreakoutOption from DB
            - If no match found: creates synthetic 1:1 breakout (fallback)

    Examples:
        >>> determine_optimal_breakout(800, 400, ['1x800g', '2x400g', '4x200g'])
        <BreakoutOption: 2x400G (from 800G)>

        >>> determine_optimal_breakout(800, 200, ['1x800g', '2x400g', '4x200g'])
        <BreakoutOption: 4x200G (from 800G)>

        >>> determine_optimal_breakout(100, 25, ['1x100g', '4x25g'])
        <BreakoutOption: 4x25G (from 100G)>

        >>> determine_optimal_breakout(800, 50, ['1x800g', '2x400g'])  # No 50G option
        <BreakoutOption: 1x800G (from 800G)>  # Falls back to native
    """
    # Try to find exact match in supported breakouts
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

    # Ultimate fallback: create synthetic 1:1 breakout
    # This is not saved to DB, just used for calculation
    class SyntheticBreakout:
        """Synthetic breakout option for fallback"""
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
    2. Determine optimal breakout based on connection speeds
    3. Calculate logical ports per switch (physical_ports × breakout_factor)
    4. Subtract uplink ports from available capacity
    5. Calculate switches needed: ceil(total_ports_needed / available_ports)
    6. Enforce MCLAG even-count requirement if mclag_pair=True

    Args:
        switch_class: PlanSwitchClass instance to calculate quantity for

    Returns:
        int: Required number of switches
            - Returns 0 if no connections target this switch class
            - Always returns even number if mclag_pair=True

    Algorithm:
        total_ports_needed = SUM(server_class.quantity × connection.ports_per_connection)
                             for each connection targeting this switch_class

        breakout = determine_optimal_breakout(native_speed, connection_speed, supported_breakouts)
        logical_ports_per_switch = physical_ports × breakout.logical_ports
        available_ports = logical_ports_per_switch - uplink_ports_per_switch

        switches_needed = CEILING(total_ports_needed / available_ports)

        if mclag_pair and switches_needed % 2 != 0:
            switches_needed += 1  # Round up to even

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

        >>> # Same but with MCLAG enabled
        >>> # 32 servers would calculate to 1, but MCLAG requires even → 2
        >>> calculate_switch_quantity(switch_class_mclag)
        2
    """
    # Get all connections targeting this switch class
    connections = switch_class.incoming_connections.all()

    if not connections.exists():
        # No connections = no switches needed
        return 0

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
    native_speed = device_extension.native_speed or 800
    supported_breakouts = device_extension.supported_breakouts or []

    # Step 4: Determine optimal breakout
    breakout = determine_optimal_breakout(
        native_speed=native_speed,
        required_speed=primary_speed,
        supported_breakouts=supported_breakouts
    )

    # Step 5: Calculate logical ports per switch
    # NOTE: For MVP, we assume all ports on the switch are the same
    # Get port count from DeviceType's InterfaceTemplates
    # For now, using a default of 64 ports (DS5000 standard)
    # TODO: Query dcim.InterfaceTemplate.objects.filter(device_type=device_extension.device_type).count()
    physical_ports = 64  # MVP default for DS5000

    logical_ports_per_switch = physical_ports * breakout.logical_ports

    # Step 6: Subtract uplink ports
    uplink_ports = switch_class.uplink_ports_per_switch
    available_ports_per_switch = logical_ports_per_switch - uplink_ports

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


def update_plan_calculations(plan):
    """
    Update calculated_quantity for all switch classes in a topology plan.

    Convenience function to recalculate all switch quantities in a plan.
    This should be called whenever:
    - Server quantities change
    - Connection specifications change
    - Switch classes are added/modified

    Args:
        plan: TopologyPlan instance

    Returns:
        dict: Summary of calculations
            {
                'switch_class_id': {
                    'calculated': int,
                    'override': int or None,
                    'effective': int
                },
                ...
            }

    Example:
        >>> summary = update_plan_calculations(plan)
        >>> summary['fe-gpu-leaf']
        {'calculated': 2, 'override': None, 'effective': 2}
    """
    summary = {}

    for switch_class in plan.switch_classes.all():
        calculated = calculate_switch_quantity(switch_class)
        switch_class.calculated_quantity = calculated
        switch_class.save(update_fields=['calculated_quantity'])

        summary[switch_class.switch_class_id] = {
            'calculated': calculated,
            'override': switch_class.override_quantity,
            'effective': switch_class.effective_quantity
        }

    return summary
