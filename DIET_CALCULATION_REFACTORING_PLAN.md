# DIET Calculation Refactoring Plan
## Response to Dev C's Architectural Concerns

**Date:** 2025-12-27
**Context:** Issue #114 - DeviceTypeExtension native_speed/uplink_ports architecture

---

## Executive Summary

Dev C correctly identified three concrete gaps in current calculation logic:

1. ✅ **Confirmed:** `native_speed` is used in 6 locations in `topology_calculations.py`
2. ✅ **Confirmed:** `physical_ports = 64` is hardcoded in 3 calculation paths
3. ✅ **Confirmed:** `DeviceTypeExtension.uplink_ports` is unused (all calculations use `PlanSwitchClass.uplink_ports_per_switch`)

This document provides a concrete refactoring plan to migrate from native_speed + hardcoded ports to InterfaceTemplate-derived capacity.

---

## Part 1: Code Audit Results

### 1.1 native_speed Usage Locations

**File:** `netbox_hedgehog/utils/topology_calculations.py`

| Line | Function | Usage | Risk Level |
|------|----------|-------|------------|
| 219 | `calculate_switch_quantity()` | `native_speed = device_extension.native_speed or 800` | **HIGH** - Mixed-port switches get wrong speed |
| 224 | `calculate_switch_quantity()` | `determine_optimal_breakout(native_speed=native_speed, ...)` | **HIGH** - Breakout selection incorrect |
| 292 | `_calculate_rail_optimized_switches()` | `native_speed = device_extension.native_speed or 800` | **HIGH** - Same risk |
| 300 | `_calculate_rail_optimized_switches()` | `determine_optimal_breakout(native_speed=native_speed, ...)` | **HIGH** - Same risk |
| 415 | `calculate_spine_quantity()` | `native_speed = device_extension.native_speed or 800` | **MEDIUM** - Spines typically uniform |
| 562 | `calculate_spine_quantity()` | `determine_optimal_breakout(native_speed=native_speed, ...)` | **MEDIUM** - Same |

**Impact:** For switches with mixed port speeds (e.g., ES1000: 48×1G + 4×25G), calculations will use incorrect speed and select wrong breakouts.

---

### 1.2 Hardcoded physical_ports = 64 Locations

**File:** `netbox_hedgehog/utils/topology_calculations.py`

| Line | Function | Code | Risk Level |
|------|----------|------|------------|
| 236 | `calculate_switch_quantity()` | `physical_ports = 64  # MVP default for DS5000` | **HIGH** - Wrong for DS3000 (32 ports) |
| 306 | `_calculate_rail_optimized_switches()` | `physical_ports = 64  # MVP default for DS5000` | **HIGH** - Same |
| 568 | `calculate_spine_quantity()` | `physical_ports = 64  # MVP default for DS5000` | **MEDIUM** - Same |

**Impact:** All calculations assume 64-port switches. Switches with 32, 48, or other port counts will have incorrect capacity calculations.

**Evidence from Seed Data:**
```python
# DS3000 has only 32 ports, not 64!
DeviceTypeExtension(
    device_type=ds3000,
    native_speed=100,
    uplink_ports=4,
    # Actual ports: 32 (from InterfaceTemplate count)
)
```

---

### 1.3 DeviceTypeExtension.uplink_ports Status

**Finding:** Field exists but is **completely unused** in calculations.

**All uplink logic uses:** `PlanSwitchClass.uplink_ports_per_switch`

**Locations Verified:**
- `topology_calculations.py:241` - Uses `switch_class.uplink_ports_per_switch`
- `topology_calculations.py:308` - Same
- `topology_calculations.py:571` - Same

**Recommendation:** Mark `DeviceTypeExtension.uplink_ports` as deprecated or remove it entirely.

---

## Part 2: Root Cause Analysis

### Why These Abstractions Exist

**Original Intent (from Issue #83 PRD):**
- `native_speed`: Quick way to represent "dominant" port speed
- `uplink_ports`: Default uplink reservation per switch

**Why They're Insufficient:**

**Example: ES1000-48 Switch**
```
Actual hardware:
- 48 ports @ 1G (copper)
- 4 ports @ 25G (SFP+)

Current DIET representation:
- native_speed: 1  (wrong for 4×25G uplinks)
- uplink_ports: 2  (arbitrary, doesn't map to actual 4×25G ports)

Problem:
- Calculations assume all 52 ports are 1G
- Breakout selection fails for 25G uplinks
- Capacity calculation is wrong
```

**Example: Dell S5248F-ON (mixed-port switch)**
```
Actual hardware:
- 48 ports @ 25G
- 4 ports @ 100G
- 2 ports @ 200G

Current DIET representation:
- native_speed: 25  (wrong for 100G/200G ports)

Problem:
- Cannot model different port groups correctly
- Breakout selection assumes all ports are 25G
```

---

## Part 3: NetBox-Native Solution

### 3.1 InterfaceTemplate Query Pattern

**Correct way to get port count:**

```python
from dcim.models import InterfaceTemplate

# Get total physical ports for a device type
physical_ports = InterfaceTemplate.objects.filter(
    device_type=device_extension.device_type
).count()

# Get ports by type (for mixed-port switches)
data_ports_25g = InterfaceTemplate.objects.filter(
    device_type=device_type,
    type='25gbase-x-sfp28'
).count()

uplink_ports_100g = InterfaceTemplate.objects.filter(
    device_type=device_type,
    type='100gbase-x-qsfp28'
).count()
```

**Benefits:**
- ✅ Works for any port count (32, 48, 64, etc.)
- ✅ Supports mixed-port switches
- ✅ Leverages NetBox core schema
- ✅ No hardcoded values

---

### 3.2 SwitchPortZone Integration

**Current DIET has:** `SwitchPortZone` model

```python
class SwitchPortZone(models.Model):
    device_type_extension = models.ForeignKey(DeviceTypeExtension, ...)
    zone_name = models.CharField()  # e.g., "data", "uplink", "mgmt"
    start_port = models.IntegerField()
    end_port = models.IntegerField()
    native_speed = models.IntegerField()  # Zone-specific speed
    zone_type = models.CharField()  # downlink, uplink, fabric
```

**This model ALREADY solves the mixed-port problem!**

**Example: ES1000-48**
```python
# Zone 1: Data ports (1G copper)
SwitchPortZone(
    zone_name="data",
    start_port=1,
    end_port=48,
    native_speed=1,
    zone_type="downlink"
)

# Zone 2: Uplink ports (25G SFP+)
SwitchPortZone(
    zone_name="uplink",
    start_port=49,
    end_port=52,
    native_speed=25,
    zone_type="uplink"
)
```

**Benefits:**
- ✅ Zone-specific speeds (solves mixed-port problem)
- ✅ Port range mapping (start_port, end_port)
- ✅ Zone type classification (downlink, uplink, fabric)

**Missing Connection:**
- ❌ Calculations don't USE SwitchPortZone yet
- ❌ No query pattern to derive capacity from zones

---

## Part 4: Migration Plan

### Phase 1: Add InterfaceTemplate-Derived Port Counts (Immediate)

**Goal:** Replace `physical_ports = 64` with actual counts

**Changes:**

**File:** `topology_calculations.py`

```python
# BEFORE (line 236)
physical_ports = 64  # MVP default for DS5000

# AFTER
physical_ports = InterfaceTemplate.objects.filter(
    device_type=device_extension.device_type
).count()

# If no templates defined (edge case), fallback to 64
if physical_ports == 0:
    physical_ports = 64  # Fallback for legacy device types
```

**Impact:**
- ✅ Fixes DS3000 (will correctly use 32 ports)
- ✅ Supports future device types with any port count
- ✅ Low risk (read-only query)

**Testing:**
```python
def test_port_count_from_interface_template():
    """Verify calculations use actual port count, not hardcoded 64"""
    # Create device type with 32 ports (DS3000)
    device_type = DeviceType(slug='ds3000', model='DS3000')

    # Create 32 interface templates
    for i in range(1, 33):
        InterfaceTemplate.objects.create(
            device_type=device_type,
            name=f'Ethernet1/{i}',
            type='100gbase-x-qsfp28'
        )

    # Create extension
    ext = DeviceTypeExtension.objects.create(
        device_type=device_type,
        native_speed=100,
        supported_breakouts=['1x100g', '4x25g']
    )

    # Calculate switches
    result = calculate_switch_quantity(switch_class)

    # Verify calculation used 32 ports, not 64
    assert result == expected_for_32_ports
```

**Rollout:**
- Apply to all 3 hardcoded locations
- Add fallback for safety
- Test with DS3000 (32 ports) and DS5000 (64 ports)

---

### Phase 2: Zone-Based Speed Derivation (Short-term)

**Goal:** Replace `native_speed` with zone-based speed lookup

**Strategy:**

**Option A: Zone-aware calculation (preferred)**

```python
def get_port_capacity_for_connection(device_extension, connection):
    """
    Get port capacity for a specific connection type.

    For mixed-port switches, looks up appropriate zone.
    For uniform switches, uses all ports.
    """
    # Check if device has port zones defined
    zones = SwitchPortZone.objects.filter(
        device_type_extension=device_extension
    )

    if not zones.exists():
        # Fallback: No zones defined, use legacy native_speed
        native_speed = device_extension.native_speed or 800
        port_count = InterfaceTemplate.objects.filter(
            device_type=device_extension.device_type
        ).count() or 64

        return {
            'native_speed': native_speed,
            'port_count': port_count
        }

    # Zone-based: Find appropriate zone for this connection
    # Logic: If connection is downlink (server), use downlink zone
    #        If connection is uplink (spine), use uplink zone

    target_zone_type = 'downlink'  # or 'uplink' based on connection

    zone = zones.filter(zone_type=target_zone_type).first()
    if not zone:
        # Fallback to first zone
        zone = zones.first()

    port_count = zone.end_port - zone.start_port + 1
    native_speed = zone.native_speed

    return {
        'native_speed': native_speed,
        'port_count': port_count
    }
```

**Usage in calculate_switch_quantity:**

```python
# BEFORE (lines 217-236)
device_extension = switch_class.device_type_extension
native_speed = device_extension.native_speed or 800
supported_breakouts = device_extension.supported_breakouts or []

breakout = determine_optimal_breakout(
    native_speed=native_speed,
    required_speed=primary_speed,
    supported_breakouts=supported_breakouts
)

physical_ports = 64  # MVP default

# AFTER
device_extension = switch_class.device_type_extension
capacity = get_port_capacity_for_connection(device_extension, connection_type='downlink')

breakout = determine_optimal_breakout(
    native_speed=capacity['native_speed'],
    required_speed=primary_speed,
    supported_breakouts=device_extension.supported_breakouts or []
)

physical_ports = capacity['port_count']
```

**Benefits:**
- ✅ Supports mixed-port switches (ES1000)
- ✅ Zone-specific speed selection
- ✅ Backward compatible (fallback to native_speed)

---

### Phase 3: Uplink Capacity Derivation (Medium-term)

**Goal:** Derive uplink capacity from zones or InterfaceTemplate tags

**Option A: Use SwitchPortZone with zone_type='uplink'**

```python
def get_uplink_capacity(device_extension):
    """
    Get uplink port capacity from port zones.

    Returns number of uplink ports available for spine connections.
    """
    uplink_zones = SwitchPortZone.objects.filter(
        device_type_extension=device_extension,
        zone_type='uplink'
    )

    if not uplink_zones.exists():
        # Fallback: Use PlanSwitchClass.uplink_ports_per_switch
        # (This is per-instance override, not device type default)
        return None  # Signals caller to use plan-level override

    # Sum all uplink zone port counts
    total_uplink_ports = sum(
        zone.end_port - zone.start_port + 1
        for zone in uplink_zones
    )

    return total_uplink_ports
```

**Usage:**

```python
# In calculate_switch_quantity()

# BEFORE
uplink_ports = switch_class.uplink_ports_per_switch

# AFTER
# Try to derive from zones first
uplink_capacity = get_uplink_capacity(device_extension)

# If no zones defined, use plan-level override
if uplink_capacity is None:
    uplink_ports = switch_class.uplink_ports_per_switch
else:
    # Use zone-derived capacity
    # But allow plan to override if specified
    if switch_class.uplink_ports_per_switch:
        uplink_ports = switch_class.uplink_ports_per_switch
    else:
        uplink_ports = uplink_capacity
```

**Benefits:**
- ✅ Device type defines default uplink capacity (via zones)
- ✅ Plan can override per switch class (via PlanSwitchClass.uplink_ports_per_switch)
- ✅ Supports mixed-port uplinks (e.g., some 100G, some 400G)

**Deprecation:**
- Mark `DeviceTypeExtension.uplink_ports` as deprecated
- Add migration to copy values to SwitchPortZone if needed

---

## Part 5: Open Questions for Dev C

### Q1: NetBox-native mapping for "server NIC → leaf class"

**Current:** Custom `PlanServerConnection` model

**Question:** Is there a NetBox-native construct for this?

**Investigating:**
- InterfaceTemplate tags/roles
- Cable templates
- Custom fields on InterfaceTemplate

**Agent researching this now** - will update with findings.

---

### Q2: native_speed Migration Strategy

**Options:**

**A) Explicit Fallback (Recommended)**
- Keep `DeviceTypeExtension.native_speed` as fallback
- Mark as "legacy" in help text
- Only use when no zones defined
- Deprecate in future major version

**B) Remove Entirely**
- Require all device types to define SwitchPortZone
- Migration: Create single zone from current native_speed
- Higher risk, forces data migration

**C) Rename to native_speed_fallback**
- Make intent explicit
- Keep for backward compatibility

**Recommendation:** **Option A** - Explicit fallback with deprecation notice.

---

### Q3: Zone vs InterfaceTemplate Type

**Current:** `SwitchPortZone.native_speed` (custom field)

**Alternative:** Derive speed from `InterfaceTemplate.type`

**Example:**
```python
# InterfaceTemplate has type field
InterfaceTemplate(
    name='Ethernet1/1',
    type='800gbase-x-qsfp-dd'  # NetBox built-in type
)

# Could derive speed from type
TYPE_SPEEDS = {
    '800gbase-x-qsfp-dd': 800,
    '400gbase-x-qsfp-dd': 400,
    '200gbase-x-qsfp56': 200,
    '100gbase-x-qsfp28': 100,
    '25gbase-x-sfp28': 25,
    '1000base-t': 1,
}

speed = TYPE_SPEEDS.get(interface_template.type)
```

**Trade-offs:**

| Approach | Pros | Cons |
|----------|------|------|
| SwitchPortZone.native_speed | Explicit, simple, already implemented | Redundant with InterfaceTemplate.type |
| Derive from InterfaceTemplate.type | Uses NetBox core schema | Complex mapping, fragile |

**Recommendation:** **Keep SwitchPortZone.native_speed** - simpler, more explicit.

---

## Part 6: Implementation Roadmap

### Week 1: Fix Hardcoded Port Counts

**Tasks:**
1. Replace `physical_ports = 64` with InterfaceTemplate query (3 locations)
2. Add fallback for safety
3. Add test case for DS3000 (32 ports)
4. Add test case for ES1000 (52 ports)

**Success Criteria:**
- All calculations use actual port counts
- Tests pass for 32, 48, 52, 64 port switches

**Risk:** Low (read-only query, fallback in place)

---

### Week 2-3: Zone-Based Capacity Derivation

**Tasks:**
1. Implement `get_port_capacity_for_connection()` helper
2. Refactor `calculate_switch_quantity()` to use it
3. Refactor `_calculate_rail_optimized_switches()` to use it
4. Refactor `calculate_spine_quantity()` to use it
5. Add fallback to `native_speed` for devices without zones
6. Add test cases for mixed-port switches (ES1000)
7. Mark `DeviceTypeExtension.native_speed` as deprecated in help text

**Success Criteria:**
- Mixed-port switches (ES1000) calculate correctly
- Backward compatibility maintained (fallback works)
- Tests pass for both zoned and non-zoned device types

**Risk:** Medium (changes calculation logic, but fallback reduces risk)

---

### Week 4: Uplink Capacity Derivation

**Tasks:**
1. Implement `get_uplink_capacity()` helper
2. Update calculations to use zone-derived uplink capacity
3. Add fallback to `PlanSwitchClass.uplink_ports_per_switch`
4. Mark `DeviceTypeExtension.uplink_ports` as deprecated
5. Add migration guidance for existing data

**Success Criteria:**
- Uplink capacity derived from zones when available
- Plan-level override still works
- Tests pass for both zoned and non-zoned uplinks

**Risk:** Low (purely additive, doesn't break existing logic)

---

### Post-MVP: Full Deprecation

**Tasks:**
1. Add data migration to create SwitchPortZone from native_speed/uplink_ports
2. Require all device types to define zones
3. Remove fallback logic
4. Remove deprecated fields

**Risk:** High (breaking change, requires major version bump)

---

## Part 7: Testing Strategy

### Test Matrix

| Switch Type | Ports | Zones | Test Case |
|-------------|-------|-------|-----------|
| DS5000 | 64 | None | Legacy fallback (native_speed) |
| DS3000 | 32 | None | Legacy fallback with correct port count |
| ES1000 | 48×1G + 4×25G | 2 zones | Zone-based speed selection |
| Custom | Any | 3+ zones | Multi-zone capacity derivation |

### Critical Test Cases

**Test 1: Port count derivation**
```python
def test_port_count_derived_from_interface_template():
    # DS3000 with 32 InterfaceTemplates
    assert calculate_switch_quantity(...) uses 32, not 64
```

**Test 2: Mixed-port switch**
```python
def test_mixed_port_switch_es1000():
    # ES1000: 48×1G data + 4×25G uplink
    # Server connections should use 1G zone
    # Spine connections should use 25G zone
    assert downlink_speed == 1
    assert uplink_speed == 25
```

**Test 3: Fallback behavior**
```python
def test_fallback_to_native_speed_when_no_zones():
    # Device type with native_speed but no zones
    assert calculation_works_correctly()
```

---

## Part 8: Dev C's Questions - Answered

### Q: What is NetBox-native mapping for "server NIC ports attach to leaf class"?

**Status:** Research agent running (will update)

**Initial Assessment:**
- Custom `PlanServerConnection` is likely appropriate
- NetBox doesn't have design-time wiring templates
- Tags on InterfaceTemplate could help but aren't sufficient alone
- Will confirm with agent findings

---

### Q: Should native_speed be fallback-only or removed?

**Answer:** **Fallback-only** (Option A from above)

**Rationale:**
1. **Pragmatic:** Not all device types will have zones immediately
2. **Safe:** Maintains backward compatibility
3. **Clear migration path:** Fallback → deprecated → removed
4. **Low risk:** Doesn't force data migration in Phase 1-3

**Implementation:**
```python
# Update help_text
native_speed = models.IntegerField(
    help_text="[DEPRECATED] Native port speed in Gbps. "
              "Used as fallback when SwitchPortZone is not defined. "
              "New device types should use SwitchPortZone instead."
)
```

---

## Part 9: Summary for Team Discussion

### Confirmed Issues

1. ✅ **native_speed is coarse** - Breaks mixed-port switches
2. ✅ **physical_ports = 64 is hardcoded** - Wrong for DS3000, ES1000, etc.
3. ✅ **DeviceTypeExtension.uplink_ports unused** - Should remove or derive from zones

### Solution Path

**Phase 1 (Week 1):** Fix hardcoded 64 → use InterfaceTemplate.count()
**Phase 2 (Week 2-3):** Add zone-based speed derivation with native_speed fallback
**Phase 3 (Week 4):** Add zone-based uplink capacity derivation
**Post-MVP:** Full deprecation of native_speed/uplink_ports (major version)

### Key Decisions Needed

1. **Fallback strategy:** Explicit fallback (recommended) vs remove entirely
2. **NetBox mapping:** Wait for agent research on InterfaceTemplate patterns
3. **Migration timeline:** Incremental (recommended) vs big-bang refactor

### Next Steps

1. Dev C reviews this plan
2. Team discusses fallback strategy
3. Begin Phase 1 implementation (low risk)
4. Agent returns with NetBox mapping research
5. Update plan based on findings

---

**Document Status:** Draft for Dev C review
**Last Updated:** 2025-12-27
**Research Agent Status:** Running (NetBox NIC mapping)
