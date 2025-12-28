# DIET-SPEC-002: Zone-Based Speed Derivation

## Metadata
- **Spec ID:** DIET-SPEC-002
- **Status:** Draft
- **Authors:** Dev A (Agent A)
- **Created:** 2025-12-27
- **Updated:** 2025-12-27
- **Reviewers:** Dev B, Dev C, User
- **Related Issues:** #114
- **Related Specs:**
  - DIET-SPEC-001 (prerequisite - must be implemented first)
  - DIET-SPEC-003 (blocks - uplink capacity from zones)

---

## Summary

Replace hardcoded `device_extension.native_speed` lookups with zone-based speed derivation that correctly handles mixed-port switches (e.g., ES1000: 48×1G + 4×25G) while maintaining backward compatibility through explicit fallback.

---

## Motivation

### Problem Statement

Current topology calculations assume all ports on a switch have uniform speed (`native_speed`), which breaks correctness for mixed-port switches with different speed zones.

**Current Code Pattern (6 locations):**
```python
native_speed = device_extension.native_speed or 800  # Lines 219, 292, 415
```

**Problem:** Mixed-port switch like ES1000 (48×1G server ports + 4×25G uplink ports) uses wrong speed:
- Server port calculations use 1G (native_speed=1) for all 52 ports ❌
- Should use 1G for server zone (ports 1-48) ✅
- Should use 25G for uplink zone (ports 49-52) ✅

### Current Behavior

**File:** `netbox_hedgehog/utils/topology_calculations.py`

**Lines 217-227 (calculate_switch_quantity):**
```python
device_extension = switch_class.device_type_extension
native_speed = device_extension.native_speed or 800
supported_breakouts = device_extension.supported_breakouts or []

breakout = determine_optimal_breakout(
    native_speed=native_speed,  # ❌ Wrong for mixed-port switches
    required_speed=primary_speed,
    supported_breakouts=supported_breakouts
)
```

**Impact:** Wrong breakout selection → wrong logical port count → wrong switch quantity.

### Desired Behavior

**Zone-based lookup with fallback:**

```python
device_extension = switch_class.device_type_extension

# Get zone-specific capacity (speed + port count)
capacity = get_port_capacity_for_connection(
    device_extension=device_extension,
    switch_class=switch_class,
    connection_type='server'  # PortZoneTypeChoices.SERVER
)

breakout = determine_optimal_breakout(
    native_speed=capacity.native_speed,  # ✅ Zone-specific speed
    required_speed=primary_speed,
    supported_breakouts=supported_breakouts
)

physical_ports = capacity.port_count  # ✅ Zone-specific port count
```

**For ES1000:**
- Server connections (zone_type='server') → use 'server-ports' zone (1G, ports 1-48)
- Uplink connections (zone_type='uplink') → use 'spine-uplinks' zone (25G, ports 49-52)

### Why Now

- **SPEC-001 prerequisite:** After SPEC-001, port counts are dynamic
- **Correctness:** Mixed-port switches calculate incorrectly today
- **Data model exists:** SwitchPortZone already implemented, just unused
- **Risk:** Medium (requires fallback logic, but backward compatible)

---

## Goals and Non-Goals

### Goals

- Replace 6 `native_speed` lookups with zone-based speed derivation
- Support mixed-port switches (ES1000: 48×1G + 4×25G)
- Maintain backward compatibility for switches without zones defined
- Return structured capacity data (speed + port count + metadata)
- Fail fast with clear error messages for invalid configurations

### Non-Goals

- Changing SwitchPortZone or BreakoutOption models (use as-is)
- Modifying port allocation logic (DIET-SPEC-004)
- Adding new zone types beyond existing PortZoneTypeChoices
- UI changes for zone creation (already exists)
- Performance optimization via caching (defer to SPEC-005 if needed)
- Removing `DeviceTypeExtension.native_speed` field (keep as fallback)
- Multi-zone aggregation (use first matching zone only)

---

## NetBox Schema Alignment

This spec uses **custom DIET models** (not NetBox core) because NetBox doesn't model zone-based port capacity:

**Schema Used:**
- `netbox_hedgehog.SwitchPortZone` - Custom model for port allocation zones
- `netbox_hedgehog.BreakoutOption` - Custom model for breakout configurations
- `netbox_hedgehog.DeviceTypeExtension` - Custom extension with fallback `native_speed`

**Query Pattern:**
```python
# Get zones for a switch class and connection type
zones = SwitchPortZone.objects.filter(
    switch_class=switch_class,
    zone_type=connection_type  # 'server', 'uplink', 'fabric'
).select_related('breakout_option')

# Extract speed from BreakoutOption.from_speed
native_speed = zone.breakout_option.from_speed
```

**Why Custom Models:**
- NetBox InterfaceTemplate doesn't support zone-based capacity
- DIET needs design-time wiring rules, not operational inventory
- Zone allocation strategies (sequential, round-robin, custom) are DIET-specific

---

## Detailed Design

### Overview

```
┌─────────────────────────────────────────────────────────────┐
│ calculate_switch_quantity() [and 2 other functions]        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────────────┐
         │ get_port_capacity_for_connection │
         └───────────┬───────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
    ┌─────▼──────┐      ┌──────▼─────────┐
    │ Zones exist│      │ No zones       │
    │ (new path) │      │ (fallback)     │
    └─────┬──────┘      └──────┬─────────┘
          │                    │
          │                    ▼
          │          DeviceTypeExtension.native_speed
          │          InterfaceTemplate.count()
          │          (legacy behavior)
          │
          ▼
   SwitchPortZone.filter(zone_type=X)
   BreakoutOption.from_speed
   PortSpecification.parse().count()
          │
          ▼
     PortCapacity(
         native_speed=...,
         port_count=...,
         source_zone=...,
         is_fallback=False
     )
```

### Data Model Changes

**No database schema changes** - using existing models.

**New Dataclass** (runtime only):

```python
@dataclass
class PortCapacity:
    """
    Structured port capacity information for a connection type.
    """
    native_speed: int  # Gbps (from BreakoutOption or fallback)
    port_count: int    # Number of physical ports available
    source_zone: Optional['SwitchPortZone']  # Zone if zone-based, None if fallback
    is_fallback: bool  # True if using legacy native_speed fallback
```

### Code Changes

#### New Function

**File:** `netbox_hedgehog/utils/topology_calculations.py` (add at top, after imports)

```python
from dataclasses import dataclass
from typing import Optional

from netbox_hedgehog.models.topology_planning import SwitchPortZone
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
    from django.core.exceptions import ValidationError

    # Step 1: Validate connection_type
    # NOTE: Must match PortZoneTypeChoices values
    valid_types = ['server', 'uplink', 'fabric']
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
```

#### Modified Functions

**Pattern for all 3 functions:**

Replace this pattern:
```python
native_speed = device_extension.native_speed or 800
# ... later ...
physical_ports = 64  # or from SPEC-001
# ... later ...
uplink_ports = switch_class.uplink_ports_per_switch
available_ports_per_switch = logical_ports_per_switch - uplink_ports
```

With this pattern:
```python
capacity = get_port_capacity_for_connection(
    device_extension=device_extension,
    switch_class=switch_class,
    connection_type='server'  # or 'uplink' for spine calculations
)
native_speed = capacity.native_speed
physical_ports = capacity.port_count

logical_ports_per_switch = physical_ports * breakout.logical_ports

# CRITICAL: Conditional uplink subtraction to avoid double-count
# - Zone-based (is_fallback=False): capacity.port_count is server zone ONLY (excludes uplinks)
# - Fallback (is_fallback=True): capacity.port_count includes ALL ports (must subtract uplinks)
if capacity.is_fallback:
    # Fallback path: total ports includes uplinks, subtract them
    uplink_ports = get_uplink_port_count(switch_class)  # SPEC-003
    available_ports_per_switch = logical_ports_per_switch - uplink_ports
else:
    # Zone-based path: server zone already excludes uplinks, don't subtract
    available_ports_per_switch = logical_ports_per_switch
```

**Modified Locations:**

1. **`calculate_switch_quantity()` (lines 217-242)**
   - Use connection_type='server' (server port capacity)
   - Add conditional uplink subtraction based on capacity.is_fallback

2. **`_calculate_rail_optimized_switches()` (lines 290-313)**
   - Use connection_type='server' (server port capacity)
   - Add conditional uplink subtraction based on capacity.is_fallback

3. **`calculate_spine_quantity()` (lines 413-578)**
   - Use connection_type='uplink' (uplink port capacity from leaf perspective)
   - Add conditional uplink subtraction based on capacity.is_fallback

### Algorithm Specification

```
Algorithm: get_port_capacity_for_connection

Input: device_extension, switch_class, connection_type
Output: PortCapacity

1. Validate connection_type in ['server', 'uplink', 'fabric']
   - If invalid: raise ValidationError with valid options
   - NOTE: Must match PortZoneTypeChoices values

2. Query zones = SwitchPortZone.filter(
       switch_class=switch_class,
       zone_type=connection_type
   ).order_by('priority')

3. If zones.exists():
   a. Select first zone (ordered by priority)
   b. If zone.breakout_option is None:
      - Raise ValidationError (zone must have breakout_option)
   c. native_speed = zone.breakout_option.from_speed
   d. port_list = PortSpecification(zone.port_spec).parse()
   e. port_count = len(port_list)
   f. Return PortCapacity(
          native_speed=native_speed,
          port_count=port_count,
          source_zone=zone,
          is_fallback=False
      )

4. Else (fallback path - no zones defined):
   a. native_speed = device_extension.native_speed
   b. If native_speed is None:
      - Raise ValidationError (need zones OR native_speed)
   c. port_count = get_physical_port_count(device_extension.device_type)
      - Reuses SPEC-001 function for consistency
   d. Return PortCapacity(
          native_speed=native_speed,
          port_count=port_count,
          source_zone=None,
          is_fallback=True
      )
```

### Error Handling

#### Error Cases

| Condition | Exception | Message | HTTP Status |
|-----------|-----------|---------|-------------|
| Invalid connection_type | ValidationError | "Invalid connection_type: '{value}'. Must be one of: server, uplink, fabric" | 400 |
| Zone has no breakout_option | ValidationError | "SwitchPortZone '{zone_name}' has no breakout_option defined. Cannot determine native speed." | 400 |
| Invalid port_spec | ValidationError | "Invalid port_spec in zone '{zone_name}': {error}" | 400 |
| No zones AND no native_speed | ValidationError | "Device type '{slug}' has no zones and no native_speed fallback defined. Cannot determine capacity." | 400 |

#### Fallback Behavior

**Fallback triggers when:**
- No SwitchPortZone records exist for switch_class
- Zone query returns empty (no matching zone_type)

**Fallback logic:**
1. Use `DeviceTypeExtension.native_speed` (must be set, or error)
2. Use `InterfaceTemplate.count()` for port count (SPEC-001)
3. Mark `is_fallback=True` in returned PortCapacity

**Logging consideration (deferred):**
- Should we log warnings when fallback is used?
- **Decision:** No logging for MVP (same as SPEC-001)
- **Rationale:** Avoid noise for intentionally simple setups

### Edge Cases

| Edge Case | Behavior | Rationale |
|-----------|----------|-----------|
| **Multiple zones for same type** | Use first zone (order_by priority) | Simplest rule, priority field controls |
| **Zone with port_spec='1-48:2'** | Parse correctly (every 2nd port) | PortSpecification supports stride syntax |
| **Zone type='fabric'** | Supported (for ESLAG/fabric ports) | PortZoneTypeChoices includes 'fabric' |
| **Breakout_option is None** | Raise ValidationError | Zone must have speed defined |
| **No zones + native_speed=None** | Raise ValidationError | Need at least one speed source |
| **No zones + native_speed=800** | Fallback works (backward compatible) | Legacy behavior preserved |

⚠️ **CAVEAT: Zone Selection Rule**

This spec uses **"first zone by priority"** selection rule. For switches with multiple zones of the same type (e.g., two 'server' zones), only the highest priority zone is used.

**Example:**
```python
# Switch with two server zones
SwitchPortZone(zone_type='server', priority=100, port_spec='1-32')  # Used ✅
SwitchPortZone(zone_type='server', priority=200, port_spec='33-48') # Ignored ❌
```

**Mitigation for MVP:**
- Document clearly in function docstring
- Expect typical case: one zone per type
- **DEFER to SPEC-004:** Multi-zone aggregation for advanced allocation

---

## Backward Compatibility

### Compatibility Matrix

| Component | Backward Compatible? | Migration Required? | Notes |
|-----------|---------------------|---------------------|-------|
| Database schema | Yes | No | No schema changes |
| API contracts | Yes | No | Calculations return same structure |
| Python API | Yes | No | New function, no changes to existing signatures |
| Calculation results | Mostly | No | Switches without zones: same behavior; with zones: improved accuracy |

### Deprecation Timeline

| Item | Status in SPEC-002 | Future Plan |
|------|-------------------|-------------|
| DeviceTypeExtension.native_speed | **Active fallback** | Mark deprecated in SPEC-003, remove in v2.0 |
| Hardcoded `or 800` fallback | Removed | Replaced with ValidationError if no speed source |

**Change in Fallback Behavior:**

**Before SPEC-002:**
```python
native_speed = device_extension.native_speed or 800  # Default to 800
```

**After SPEC-002:**
```python
# If no zones AND no native_speed: raise ValidationError
# No more silent default to 800
```

**Impact:** Switches with `native_speed=None` and no zones will fail (good - catches misconfigurations)

### Migration Guide

**For Existing Deployments:**

```bash
# No database migrations required
# No data migration needed
# Existing switches without zones continue to work via fallback
```

**For Existing Code:**

**Before SPEC-002:**
```python
native_speed = device_extension.native_speed or 800
```

**After SPEC-002 (internal calculations - no user code impact):**
```python
capacity = get_port_capacity_for_connection(
    device_extension=device_extension,
    switch_class=switch_class,
    connection_type='server'
)
native_speed = capacity.native_speed
```

**For New Switch Types:**

Recommendation: Define SwitchPortZone instead of relying on native_speed fallback.

**Example: ES1000 setup**
```python
# Create breakout options
breakout_1g = BreakoutOption.objects.create(
    breakout_id='1x1g',
    from_speed=1,
    logical_ports=1,
    logical_speed=1
)
breakout_25g = BreakoutOption.objects.create(
    breakout_id='1x25g',
    from_speed=25,
    logical_ports=1,
    logical_speed=25
)

# Create zones
SwitchPortZone.objects.create(
    switch_class=es1000_switch_class,
    zone_name='server-ports',
    zone_type='server',
    port_spec='1-48',
    breakout_option=breakout_1g,
    priority=100
)
SwitchPortZone.objects.create(
    switch_class=es1000_switch_class,
    zone_name='spine-uplinks',
    zone_type='uplink',
    port_spec='49-52',
    breakout_option=breakout_25g,
    priority=100
)
```

---

## Testing

### Test Scenarios

#### Unit Tests

**New File:** `netbox_hedgehog/tests/test_topology_planning/test_port_capacity.py`

```python
from django.test import TestCase
from django.core.exceptions import ValidationError

from dcim.models import DeviceType, Manufacturer, InterfaceTemplate
from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension, PlanSwitchClass, SwitchPortZone, BreakoutOption
)
from netbox_hedgehog.utils.topology_calculations import (
    get_port_capacity_for_connection, PortCapacity
)


class TestGetPortCapacityForConnection(TestCase):
    """Unit tests for zone-based port capacity derivation."""

    def setUp(self):
        """Create common test fixtures."""
        self.manufacturer = Manufacturer.objects.create(name='Test', slug='test')

    def test_zone_based_capacity_returns_zone_speed_and_count(self):
        """When zones exist, should return zone speed and port count."""
        # Create device type
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='ES1000',
            slug='es1000'
        )
        ext = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=1  # Fallback (not used when zones exist)
        )

        # Create topology plan and switch class
        plan = TopologyPlan.objects.create(plan_name='test')
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            device_type_extension=ext,
            switch_class_id='leaf',
            uplink_ports_per_switch=4
        )

        # Create breakout option
        breakout = BreakoutOption.objects.create(
            breakout_id='1x1g',
            from_speed=1,
            logical_ports=1,
            logical_speed=1
        )

        # Create zone
        zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-48',
            breakout_option=breakout,
            priority=100
        )

        # Execute
        capacity = get_port_capacity_for_connection(ext, switch_class, 'server')

        # Verify
        self.assertEqual(capacity.native_speed, 1)
        self.assertEqual(capacity.port_count, 48)
        self.assertEqual(capacity.source_zone, zone)
        self.assertFalse(capacity.is_fallback)

    def test_fallback_when_no_zones_defined(self):
        """When no zones, should use native_speed and InterfaceTemplate count."""
        # Create device type with templates
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='DS5000',
            slug='ds5000'
        )

        # Create 64 interface templates
        for i in range(1, 65):
            InterfaceTemplate.objects.create(
                device_type=device_type,
                name=f'Ethernet1/{i}',
                type='800gbase-x-qsfp-dd'
            )

        ext = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=800
        )

        plan = TopologyPlan.objects.create(plan_name='test')
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            device_type_extension=ext,
            switch_class_id='spine',
            uplink_ports_per_switch=0
        )

        # Execute (no zones exist)
        capacity = get_port_capacity_for_connection(ext, switch_class, 'server')

        # Verify fallback behavior
        self.assertEqual(capacity.native_speed, 800)
        self.assertEqual(capacity.port_count, 64)
        self.assertIsNone(capacity.source_zone)
        self.assertTrue(capacity.is_fallback)

    def test_raises_validation_error_for_invalid_connection_type(self):
        """Should raise ValidationError for invalid connection_type."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='Test',
            slug='test'
        )
        ext = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=800
        )
        plan = TopologyPlan.objects.create(plan_name='test')
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            device_type_extension=ext,
            switch_class_id='leaf',
            uplink_ports_per_switch=4
        )

        # Execute with invalid type
        with self.assertRaises(ValidationError) as cm:
            get_port_capacity_for_connection(ext, switch_class, 'invalid_type')

        # Verify error message
        self.assertIn("Invalid connection_type", str(cm.exception))
        self.assertIn("server, uplink, fabric", str(cm.exception))

    def test_raises_validation_error_when_zone_missing_breakout_option(self):
        """Should raise ValidationError when zone has no breakout_option."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='Test',
            slug='test'
        )
        ext = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=800
        )
        plan = TopologyPlan.objects.create(plan_name='test')
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            device_type_extension=ext,
            switch_class_id='leaf',
            uplink_ports_per_switch=4
        )

        # Create zone WITHOUT breakout_option
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='incomplete-zone',
            zone_type='server',
            port_spec='1-48',
            breakout_option=None,  # Missing!
            priority=100
        )

        # Execute
        with self.assertRaises(ValidationError) as cm:
            get_port_capacity_for_connection(ext, switch_class, 'server')

        # Verify error message
        self.assertIn("no breakout_option defined", str(cm.exception))

    def test_raises_validation_error_when_no_zones_and_no_native_speed(self):
        """Should raise ValidationError when no zones AND no native_speed."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='Incomplete',
            slug='incomplete'
        )
        ext = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=None  # No fallback!
        )
        plan = TopologyPlan.objects.create(plan_name='test')
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            device_type_extension=ext,
            switch_class_id='leaf',
            uplink_ports_per_switch=4
        )

        # Execute (no zones, no native_speed)
        with self.assertRaises(ValidationError) as cm:
            get_port_capacity_for_connection(ext, switch_class, 'server')

        # Verify error message
        self.assertIn("no zones and no native_speed", str(cm.exception))

    def test_mixed_port_switch_es1000_returns_correct_zone_speeds(self):
        """ES1000 with 48×1G + 4×25G should return different speeds per zone."""
        # Create ES1000 device type
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='ES1000-48',
            slug='es1000-48'
        )
        ext = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=1  # Fallback (not used)
        )
        plan = TopologyPlan.objects.create(plan_name='test')
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            device_type_extension=ext,
            switch_class_id='access',
            uplink_ports_per_switch=4
        )

        # Create breakout options
        breakout_1g = BreakoutOption.objects.create(
            breakout_id='1x1g',
            from_speed=1,
            logical_ports=1,
            logical_speed=1
        )
        breakout_25g = BreakoutOption.objects.create(
            breakout_id='1x25g',
            from_speed=25,
            logical_ports=1,
            logical_speed=25
        )

        # Create server zone (1G)
        server_zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='server-ports',
            zone_type='server',
            port_spec='1-48',
            breakout_option=breakout_1g,
            priority=100
        )

        # Create uplink zone (25G)
        uplink_zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='spine-uplinks',
            zone_type='uplink',
            port_spec='49-52',
            breakout_option=breakout_25g,
            priority=100
        )

        # Test server capacity
        server_capacity = get_port_capacity_for_connection(
            ext, switch_class, 'server'
        )
        self.assertEqual(server_capacity.native_speed, 1)
        self.assertEqual(server_capacity.port_count, 48)
        self.assertEqual(server_capacity.source_zone, server_zone)

        # Test uplink capacity
        uplink_capacity = get_port_capacity_for_connection(
            ext, switch_class, 'uplink'
        )
        self.assertEqual(uplink_capacity.native_speed, 25)
        self.assertEqual(uplink_capacity.port_count, 4)
        self.assertEqual(uplink_capacity.source_zone, uplink_zone)

    def test_zone_priority_ordering(self):
        """When multiple zones exist for same type, should use highest priority (lowest number)."""
        device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='Test',
            slug='test'
        )
        ext = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=800
        )
        plan = TopologyPlan.objects.create(plan_name='test')
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            device_type_extension=ext,
            switch_class_id='leaf',
            uplink_ports_per_switch=4
        )

        breakout_100g = BreakoutOption.objects.create(
            breakout_id='1x100g',
            from_speed=100,
            logical_ports=1,
            logical_speed=100
        )
        breakout_200g = BreakoutOption.objects.create(
            breakout_id='1x200g',
            from_speed=200,
            logical_ports=1,
            logical_speed=200
        )

        # Create two zones with same type, different priority
        high_priority_zone = SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='zone-high-priority',
            zone_type='server',
            port_spec='1-32',
            breakout_option=breakout_200g,
            priority=50  # Higher priority (lower number)
        )
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='zone-low-priority',
            zone_type='server',
            port_spec='33-48',
            breakout_option=breakout_100g,
            priority=200  # Lower priority
        )

        # Execute
        capacity = get_port_capacity_for_connection(ext, switch_class, 'server')

        # Verify high priority zone is used
        self.assertEqual(capacity.source_zone, high_priority_zone)
        self.assertEqual(capacity.native_speed, 200)
        self.assertEqual(capacity.port_count, 32)
```

*Full test implementations follow this pattern.*

**Test Helper Recommendation (from SPEC-001):**

Consider creating test helper for zone creation:

```python
def create_port_zone(
    switch_class: 'PlanSwitchClass',
    zone_name: str,
    zone_type: str,
    port_spec: str,
    from_speed: int,
    priority: int = 100
) -> 'SwitchPortZone':
    """
    Helper to create SwitchPortZone with BreakoutOption for testing.

    Example:
        >>> create_port_zone(switch_class, 'data', 'server', '1-48', from_speed=1)
    """
    breakout = BreakoutOption.objects.create(
        breakout_id=f'{zone_name}-breakout',
        from_speed=from_speed,
        logical_ports=1,
        logical_speed=from_speed
    )
    return SwitchPortZone.objects.create(
        switch_class=switch_class,
        zone_name=zone_name,
        zone_type=zone_type,
        port_spec=port_spec,
        breakout_option=breakout,
        priority=priority
    )
```

#### Integration Tests

**Modified File:** `netbox_hedgehog/tests/test_topology_planning/test_topology_calculations.py`

**New Test:** `test_calculate_switch_quantity_with_mixed_port_switch_es1000`

**Scenario:**
- ES1000 switch (48×1G server ports + 4×25G uplink ports)
- 100 servers × 1G connection each
- Zones defined: 'server-ports' (1G, ports 1-48), 'spine-uplinks' (25G, ports 49-52)

**Expected Calculation:**
```
Downlink capacity: 1G × 48 ports (from 'server-ports' zone)
Breakout: 1x1g (no breakout needed)
Logical ports: 48 × 1 = 48
Uplink reservation: 4 ports
Available: 48 - 4 = 44 ports
Switches needed: ceil(100 / 44) = 3 switches
```

**Verification:**
- Assert `switches_needed == 3`
- Assert calculation used zone speed (1G), not fallback
- Document wrong behavior (if used native_speed=1 for all 52 ports): `ceil(100 / 48) = 3` (same by luck, but wrong logic)

### Test Matrix

| Switch Type | Zones Defined? | native_speed | Expected Behavior | Test Case |
|-------------|---------------|--------------|-------------------|-----------|
| DS5000 | No | 800 | Fallback: 800G, 64 ports | test_fallback_when_no_zones_defined |
| DS3000 | No | 100 | Fallback: 100G, 32 ports | test_fallback_with_interface_template_count |
| ES1000 | Yes (2 zones) | 1 | Zone-based: 1G/48 (downlink), 25G/4 (uplink) | test_mixed_port_switch_es1000 |
| ES1000 | Yes | None | Zone-based (native_speed not used) | test_zone_based_ignores_native_speed |
| Incomplete | No | None | ValidationError | test_raises_validation_error_no_fallback |
| With zone | Yes | 800 | Zone missing breakout_option → ValidationError | test_raises_validation_error_missing_breakout |
| Multi-zone | Yes (priority 50, 200) | 800 | Uses priority 50 zone | test_zone_priority_ordering |

### Performance Tests

**Not required for this spec.** Zone query with select_related('breakout_option') is fast (<10ms).

**Future:** If performance becomes an issue, add caching in SPEC-005.

---

## Implementation Plan

### Prerequisites

- [x] DIET-SPEC-001 implemented (InterfaceTemplate port count query)
- [ ] DIET-SPEC-001 approved and merged

### Step-by-Step Implementation

**Step 1: Add PortCapacity Dataclass and Function**
```bash
# File: netbox_hedgehog/utils/topology_calculations.py
# Add PortCapacity dataclass at top (after imports)
# Add get_port_capacity_for_connection() function
```

**Step 2: Modify calculate_switch_quantity()**
```bash
# File: netbox_hedgehog/utils/topology_calculations.py:217-236
# Replace native_speed/physical_ports logic with zone-based capacity
```

**Step 3: Modify _calculate_rail_optimized_switches()**
```bash
# File: netbox_hedgehog/utils/topology_calculations.py:290-306
# Same pattern as Step 2
```

**Step 4: Modify calculate_spine_quantity()**
```bash
# File: netbox_hedgehog/utils/topology_calculations.py:413-568
# Use connection_type='uplink' for spine calculations
```

**Step 5: Add Unit Tests**
```bash
# File: netbox_hedgehog/tests/test_topology_planning/test_port_capacity.py (NEW)
# Implement all 7+ test methods from Test Matrix
```

**Step 6: Add Integration Tests**
```bash
# File: netbox_hedgehog/tests/test_topology_planning/test_topology_calculations.py
# Add test_calculate_switch_quantity_with_mixed_port_switch_es1000
```

### File Changes Checklist

- [ ] `netbox_hedgehog/utils/topology_calculations.py` - MODIFIED - Add PortCapacity dataclass and get_port_capacity_for_connection()
- [ ] `netbox_hedgehog/utils/topology_calculations.py:217-236` - MODIFIED - calculate_switch_quantity() uses zone capacity
- [ ] `netbox_hedgehog/utils/topology_calculations.py:290-306` - MODIFIED - _calculate_rail_optimized_switches() uses zone capacity
- [ ] `netbox_hedgehog/utils/topology_calculations.py:413-568` - MODIFIED - calculate_spine_quantity() uses zone capacity
- [ ] `netbox_hedgehog/tests/test_topology_planning/test_port_capacity.py` - NEW - Unit tests for zone capacity
- [ ] `netbox_hedgehog/tests/test_topology_planning/test_topology_calculations.py` - MODIFIED - Integration test for ES1000

### Rollback Plan

If issues discovered after deployment:

1. Revert commit implementing SPEC-002
2. No database migration to rollback (no schema changes)
3. Re-run tests to verify fallback behavior restored
4. Investigate issue with zone configuration (likely cause)

**Low risk:** Fallback path maintains backward compatibility.

---

## Alternatives Considered

### Alternative 1: Remove native_speed Entirely

**Description:** Force all device types to define SwitchPortZone, remove fallback.

**Pros:**
- Cleaner code (no fallback path)
- Forces proper configuration

**Cons:**
- Breaking change for existing switches
- Forces immediate data migration
- Higher risk

**Why Rejected:** Too aggressive for Phase 2. Fallback approach allows incremental migration.

---

### Alternative 2: Aggregate Multiple Zones

**Description:** Sum capacity across all zones of same type.

**Pros:**
- Supports complex multi-zone configurations

**Cons:**
- More complex logic
- Unclear which speed to use (mixed speeds?)
- Not needed for current hardware

**Why Rejected:** YAGNI (You Aren't Gonna Need It). Current switches have one zone per type. Defer to SPEC-004 if needed.

---

### Alternative 3: Derive Speed from InterfaceTemplate.type

**Description:** Map NetBox interface types (e.g., '800gbase-x-qsfp-dd') to speeds.

**Pros:**
- Uses NetBox core schema

**Cons:**
- Fragile mapping (100+ interface types)
- Doesn't support zone-specific logic
- Redundant with BreakoutOption.from_speed

**Why Rejected:** SwitchPortZone + BreakoutOption already exists and works better.

---

## Open Questions

### Question 1: Fallback Logging

**Question:** Should we log a warning when fallback path is used?

**Options:**
- A) Log warning every time (alerts admins)
- B) No logging (silent fallback)
- C) Log only once per device type (reduce noise)

**Recommendation:** **Option B** (No logging for MVP)

**Rationale:**
- Same decision as SPEC-001
- Avoid noise for intentionally simple setups
- Can add in SPEC-005 based on operational experience

**Decision:** [To be determined]

---

### Question 2: Zone Selection Rule for Multiple Zones

**Question:** When multiple zones exist for same connection_type, which to use?

**Current Behavior:** Use first zone ordered by priority (lowest number = highest priority)

**Alternatives:**
- A) Use first zone by priority (current)
- B) Raise ValidationError (force single zone per type)
- C) Aggregate capacity across all zones

**Recommendation:** **Option A** (Use priority)

**Rationale:**
- SwitchPortZone already has priority field
- Simplest implementation
- Supports future multi-zone use cases via priority

**Decision:** Approved in spec

---

## Performance Considerations

### Query Performance

**Expected query count:** 1-2 queries per calculation function
- 1 query: `SwitchPortZone.filter().select_related('breakout_option')`
- 1 query (fallback only): `InterfaceTemplate.filter().count()`

**Indexes required:** (already exist via Django Meta.ordering)
- Index on `(switch_class_id, zone_type, priority)`

**Cache strategy:** Not needed for MVP
- Query cost: <10ms (simple filter + select_related)
- Calculation runs once per plan save
- **Defer to SPEC-005** if caching becomes necessary

### Memory Usage

**Expected memory impact:** Minimal
- PortCapacity dataclass: ~200 bytes per instance
- Zone query results: <1KB per switch class

### Time Complexity

**Algorithm complexity:** O(1) per calculation (single zone query)

**Expected runtime:** <10ms per function call

---

## Documentation Updates

### User-Facing Documentation

- [ ] Update `docs/TOPOLOGY_PLANNING.md` section on port capacity
- [ ] Add note on zone-based vs fallback behavior
- [ ] Create example for ES1000 mixed-port setup

### Developer Documentation

- [ ] Add inline code comments explaining fallback logic
- [ ] Update `ARCHITECTURE.md` with zone capacity flow diagram
- [ ] Document PortCapacity dataclass usage

---

## Dependencies

### Depends On
- DIET-SPEC-001 (must be implemented first - uses InterfaceTemplate.count() in fallback)

### Blocks
- DIET-SPEC-003 (uplink capacity from zones - similar pattern)

### Related
- DIET-SPEC-004 (port allocation logic - will use PortCapacity)
- DIET-SPEC-005 (caching - may cache PortCapacity results)

---

## Metrics and Monitoring

### Success Metrics

- [ ] All tests pass (8+ unit tests, 1+ integration test)
- [ ] ES1000 mixed-port calculation produces correct results
- [ ] Backward compatibility: DS5000/DS3000 without zones still work
- [ ] Code coverage: >90% for new function

### Monitoring

**Metric to track:** None for MVP (no operational telemetry in calculations)

**Future:** If needed, track:
- Fallback usage rate (% of calculations using is_fallback=True)
- Zone query performance

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2025-12-27 | Dev A | Initial draft |

---

## Approval

### Reviewers

- [ ] **Dev B:** Implementation review
- [ ] **Dev C:** Testing review
- [ ] **User:** Final approval

### Sign-off

- **Approved by:** [Pending]
- **Approval date:** [Pending]
- **Implementation start:** [After SPEC-001 merged]
- **Target completion:** [TBD]

---

## References

- [DIET-SPEC-001: Fix Hardcoded Port Counts](DIET-SPEC-001-Fix-Hardcoded-Port-Counts.md)
- [Issue #114: DeviceTypeExtension native_speed architectural problems](https://github.com/afewell-hh/hh-netbox-plugin/issues/114)
- [DIET Calculation Refactoring Plan](../DIET_CALCULATION_REFACTORING_PLAN.md)
- [SwitchPortZone Model](../netbox_hedgehog/models/topology_planning/port_zones.py)
- [BreakoutOption Model](../netbox_hedgehog/models/topology_planning/reference_data.py)
