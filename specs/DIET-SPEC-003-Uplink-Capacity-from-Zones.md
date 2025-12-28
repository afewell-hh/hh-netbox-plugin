# DIET-SPEC-003: Uplink Capacity from Zones

## Metadata
- **Spec ID:** DIET-SPEC-003
- **Status:** Draft
- **Authors:** Dev A (Agent A)
- **Created:** 2025-12-27
- **Updated:** 2025-12-27
- **Reviewers:** Dev B, Dev C, User
- **Related Issues:** #114
- **Related Specs:**
  - DIET-SPEC-001 (prerequisite)
  - DIET-SPEC-002 (prerequisite - uses similar zone query pattern)

---

## Summary

Enable optional uplink port count derivation from SwitchPortZone with `zone_type='uplink'`, while maintaining `PlanSwitchClass.uplink_ports_per_switch` as the primary/override value. Deprecate unused `DeviceTypeExtension.uplink_ports` field.

---

## Motivation

### Problem Statement

Current uplink port reservation uses only `PlanSwitchClass.uplink_ports_per_switch` (plan-level override), while `DeviceTypeExtension.uplink_ports` exists but is completely unused. There's no way to derive default uplink capacity from device type characteristics or port zones.

**Current Code Pattern (3 locations):**
```python
uplink_ports = switch_class.uplink_ports_per_switch  # Lines 241, 308, 571
```

**Issues:**
1. `DeviceTypeExtension.uplink_ports` field exists but is never used ❌
2. No way to derive uplink capacity from zones (inconsistent with server zones in SPEC-002) ❌
3. Every PlanSwitchClass must manually specify uplink_ports_per_switch ❌

### Current Behavior

**File:** `netbox_hedgehog/utils/topology_calculations.py`

**Lines 240-242 (calculate_switch_quantity):**
```python
# Step 6: Subtract uplink ports
uplink_ports = switch_class.uplink_ports_per_switch
available_ports_per_switch = logical_ports_per_switch - uplink_ports
```

**DeviceTypeExtension.uplink_ports field:**
```python
# From models/topology_planning/reference_data.py
uplink_ports = models.IntegerField(
    null=True,
    blank=True,
    help_text="Number of ports reserved for uplinks (optional)"
)
```

**Status:** Field exists, never queried in calculations.

### Desired Behavior

**Optional zone-based uplink derivation with override:**

```python
# Get server capacity from SPEC-002
capacity = get_port_capacity_for_connection(
    device_extension=device_extension,
    switch_class=switch_class,
    connection_type='server'
)
logical_ports_per_switch = capacity.port_count * breakout.logical_ports

# CRITICAL: Conditional uplink subtraction (SPEC-002 integration)
# - Zone-based (is_fallback=False): capacity already excludes uplinks, don't subtract
# - Fallback (is_fallback=True): capacity includes all ports, must subtract uplinks

if capacity.is_fallback:
    # Fallback path: total ports includes uplinks, must subtract
    uplink_ports = get_uplink_port_count(switch_class)  # This function
    available_ports_per_switch = logical_ports_per_switch - uplink_ports
else:
    # Zone-based path: server zone already excludes uplinks
    available_ports_per_switch = logical_ports_per_switch
    # Note: get_uplink_port_count() is NOT called (no subtraction needed)
```

**Benefits:**
- Derive uplink capacity from zones when configured ✅
- Allow plan-level override (PlanSwitchClass.uplink_ports_per_switch) ✅
- Maintain backward compatibility (existing plans work) ✅
- Deprecate unused DeviceTypeExtension.uplink_ports ✅
- **Avoid double-count:** Only subtract uplinks when capacity.is_fallback=True ✅

### Why Now

- **SPEC-002 establishes pattern:** Zone-based capacity derivation proven with conditional uplink subtraction
- **Consistency:** Align uplink logic with server zone-based logic (SPEC-002)
- **Technical debt:** Remove unused DeviceTypeExtension.uplink_ports
- **Risk:** Low (purely additive, but requires conditional subtraction logic)

---

## Goals and Non-Goals

### Goals

- Enable optional uplink port count derivation from SwitchPortZone (zone_type='uplink')
- Maintain PlanSwitchClass.uplink_ports_per_switch as primary/override value
- Mark DeviceTypeExtension.uplink_ports as deprecated
- Fail fast with clear error when neither zones nor override are defined
- Maintain full backward compatibility for existing plans

### Non-Goals

- Removing PlanSwitchClass.uplink_ports_per_switch (keep as override)
- Forcing zone-based uplink configuration (optional, not required)
- Modifying uplink allocation logic (DIET-SPEC-004)
- Data migration from DeviceTypeExtension.uplink_ports to zones (optional guidance only)
- Removing DeviceTypeExtension.uplink_ports field (deprecate only, remove in v2.0)
- Supporting weighted uplink zones aggregation (e.g., 50% zone1 + 50% zone2)

**Note:** Simple cumulative sum across multiple uplink zones **IS supported** to handle switches with mixed port types (e.g., 2×10GbE + 2×25GbE uplinks). All uplink zones are summed to determine total uplink port demand that spines must satisfy.

---

## NetBox Schema Alignment

This spec uses **custom DIET models** (not NetBox core):

**Schema Used:**
- `netbox_hedgehog.SwitchPortZone` - Port allocation zones with zone_type='uplink'
- `netbox_hedgehog.PlanSwitchClass` - Plan-level uplink_ports_per_switch override
- `netbox_hedgehog.DeviceTypeExtension` - uplink_ports field (deprecated)

**Query Pattern:**
```python
# Get uplink zones for a switch class
uplink_zones = SwitchPortZone.objects.filter(
    switch_class=switch_class,
    zone_type='uplink'
)

# Sum port counts across zones
total_uplink_ports = sum(
    len(PortSpecification(zone.port_spec).parse())
    for zone in uplink_zones
)
```

**Why Custom Models:**
- NetBox doesn't model uplink reservation concepts
- DIET needs design-time capacity planning
- Zone-based configuration aligns with SPEC-002 pattern

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
         │ get_uplink_port_count()       │
         └───────────┬───────────────────┘
                     │
          ┌──────────┴────────────┐
          │                       │
    ┌─────▼─────────┐      ┌──────▼──────────┐
    │ Override set? │      │ No override     │
    │ (priority 1)  │      │                 │
    └─────┬─────────┘      └──────┬──────────┘
          │                       │
          │                ┌──────▼──────────┐
          │                │ Zones exist?    │
          │                │ (priority 2)    │
          │                └──────┬──────────┘
          │                       │
          │                ┌──────┴──────┐
          │                │             │
          │         ┌──────▼──────┐  ┌──▼──────────┐
          │         │ Zones exist │  │ No zones    │
          │         │ (derive)    │  │ (error)     │
          │         └──────┬──────┘  └──┬──────────┘
          │                │             │
          │                │             ▼
          │                │    ValidationError:
          │                │    "No uplink capacity"
          │                │
          └────────────────┴──────────────┐
                                          │
                                          ▼
                              uplink_port_count (int)
```

**Priority Order:**
1. **PlanSwitchClass.uplink_ports_per_switch** (highest - explicit override)
2. **SwitchPortZone.filter(zone_type='uplink')** (derived from zones)
3. **Error** (neither override nor zones defined)

### Data Model Changes

**Schema Changes Required:**

**Migration:** `0020_make_uplink_ports_per_switch_nullable.py`

**1. PlanSwitchClass.uplink_ports_per_switch - Make Nullable:**

```python
# File: netbox_hedgehog/models/topology_planning/topology_plans.py

class PlanSwitchClass(NetBoxModel):
    # ... other fields ...

    uplink_ports_per_switch = models.IntegerField(
        null=True,           # CHANGED: was default=0
        blank=True,          # CHANGED: added
        validators=[MinValueValidator(0)],
        help_text="Number of ports reserved for uplinks (explicit override). "
                  "If not set, uplink capacity will be derived from SwitchPortZone "
                  "with zone_type='uplink'. Either this field or uplink zones must be defined."
    )
```

**2. DeviceTypeExtension.uplink_ports - Mark as Deprecated:**

```python
# File: netbox_hedgehog/models/topology_planning/reference_data.py

class DeviceTypeExtension(NetBoxModel):
    # ... other fields ...

    uplink_ports = models.IntegerField(
        null=True,
        blank=True,
        help_text="[DEPRECATED] Number of ports reserved for uplinks. "
                  "This field is unused in calculations. "
                  "Use PlanSwitchClass.uplink_ports_per_switch or "
                  "define SwitchPortZone with zone_type='uplink'. "
                  "Will be removed in v2.0."
    )
```

### Code Changes

#### New Function

**File:** `netbox_hedgehog/utils/topology_calculations.py` (add near PortCapacity/get_port_capacity_for_connection)

```python
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
    from django.core.exceptions import ValidationError

    # Priority 1: Explicit override (plan-level)
    if switch_class.uplink_ports_per_switch is not None:
        return switch_class.uplink_ports_per_switch

    # Priority 2: Derive from uplink zones
    uplink_zones = SwitchPortZone.objects.filter(
        switch_class=switch_class,
        zone_type='uplink'
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
```

#### Modified Functions

**Pattern for all 3 functions:**

Replace this pattern:
```python
uplink_ports = switch_class.uplink_ports_per_switch
```

With this pattern:
```python
uplink_ports = get_uplink_port_count(switch_class)
```

**Modified Locations:**

1. **`calculate_switch_quantity()` (line 241)**
   - Replace: `uplink_ports = switch_class.uplink_ports_per_switch`
   - With: `uplink_ports = get_uplink_port_count(switch_class)`

2. **`_calculate_rail_optimized_switches()` (line 308)**
   - Same replacement

3. **`calculate_spine_quantity()` (line 571)**
   - Same replacement

**Before/After Comparison:**

```python
# BEFORE (lines 240-242)
# Step 6: Subtract uplink ports
uplink_ports = switch_class.uplink_ports_per_switch
available_ports_per_switch = logical_ports_per_switch - uplink_ports

# AFTER
# Step 6: Subtract uplink ports (override or zone-derived)
uplink_ports = get_uplink_port_count(switch_class)
available_ports_per_switch = logical_ports_per_switch - uplink_ports
```

### Algorithm Specification

```
Algorithm: get_uplink_port_count

Input: switch_class (PlanSwitchClass)
Output: uplink_port_count (int)

1. If switch_class.uplink_ports_per_switch is not None:
   - Return switch_class.uplink_ports_per_switch
   - (Explicit override takes precedence)

2. Query uplink_zones = SwitchPortZone.filter(
       switch_class=switch_class,
       zone_type='uplink'
   )

3. If uplink_zones.exists():
   a. total_uplink_ports = 0
   b. For each zone in uplink_zones:
      - Parse port_spec to get port_list
      - If parsing fails: raise ValidationError
      - total_uplink_ports += len(port_list)
   c. Return total_uplink_ports

4. Else:
   - Raise ValidationError(
       "Switch class '{id}' has no uplink capacity defined. "
       "Set uplink_ports_per_switch or create uplink zone."
     )
```

### Error Handling

#### Error Cases

| Condition | Exception | Message | HTTP Status |
|-----------|-----------|---------|-------------|
| No override AND no zones | ValidationError | "Switch class '{id}' has no uplink capacity defined. Set uplink_ports_per_switch or create SwitchPortZone with zone_type='uplink'." | 400 |
| Invalid port_spec in zone | ValidationError | "Invalid port_spec in uplink zone '{zone_name}': {error}" | 400 |

#### Backward Compatibility Handling

**Existing plans with uplink_ports_per_switch set:**
- ✅ Continue to work (Priority 1 - override path)
- No changes needed

**New plans without uplink_ports_per_switch:**
- Must define uplink zones OR set override
- ValidationError guides user to fix configuration

### Edge Cases

| Edge Case | Behavior | Rationale |
|-----------|----------|-----------|
| **Override = 0 (no uplinks)** | Returns 0 (valid) | Spine-only switches may have no server uplinks |
| **Multiple uplink zones** | Sum all zones | Different uplink groups (e.g., spines + external) |
| **Override + Zones both exist** | Override wins (Priority 1) | Explicit plan override takes precedence |
| **DeviceTypeExtension.uplink_ports set** | Ignored (deprecated) | Field unused, migration guidance provided |

---

## Backward Compatibility

### Compatibility Matrix

| Component | Backward Compatible? | Migration Required? | Notes |
|-----------|---------------------|---------------------|-------|
| Database schema | Yes | No | No schema changes (deprecation only) |
| API contracts | Yes | No | Calculations return same structure |
| Python API | Yes | No | New function, existing signatures unchanged |
| Existing plans | **Partially** | **Maybe** | See migration guide |

**Breaking Change Alert:**

Plans with `uplink_ports_per_switch = None` AND no uplink zones will now **fail** with ValidationError.

**Before SPEC-003:**
```python
# This would fail silently or use None (bug)
uplink_ports = switch_class.uplink_ports_per_switch  # None
available_ports = logical_ports - None  # TypeError or wrong calculation
```

**After SPEC-003:**
```python
# This fails fast with clear error
uplink_ports = get_uplink_port_count(switch_class)
# Raises: "Switch class 'leaf' has no uplink capacity defined..."
```

**Impact:** Existing plans with `uplink_ports_per_switch = None` must be fixed.

### Deprecation Timeline

| Item | Deprecated In | Removed In | Migration Path |
|------|--------------|------------|----------------|
| DeviceTypeExtension.uplink_ports | SPEC-003 (v1.1) | v2.0 | Use PlanSwitchClass.uplink_ports_per_switch or zones |

### Migration Guide

**For Existing Deployments:**

**Step 1: Audit Plans with uplink_ports_per_switch = None**

```bash
# Find plans that may need fixes
cd /path/to/netbox
docker compose exec netbox python manage.py shell

from netbox_hedgehog.models.topology_planning import PlanSwitchClass

# Find switch classes with no uplink configuration
problematic = PlanSwitchClass.objects.filter(
    uplink_ports_per_switch__isnull=True
)

print(f"Found {problematic.count()} switch classes with no uplink config:")
for sc in problematic:
    print(f"  - Plan: {sc.plan.name}, Class: {sc.switch_class_id}")
```

**Step 2: Fix Configurations (Choose One)**

**Option A: Set plan-level override**
```python
# For each problematic switch class:
switch_class.uplink_ports_per_switch = 4  # Set appropriate value
switch_class.save()
```

**Option B: Create uplink zone**
```python
from netbox_hedgehog.models.topology_planning import SwitchPortZone, BreakoutOption

# Create zone with uplink ports
breakout = BreakoutOption.objects.get(breakout_id='1x800g')  # Or appropriate breakout

SwitchPortZone.objects.create(
    switch_class=switch_class,
    zone_name='spine-uplinks',
    zone_type='uplink',
    port_spec='61-64',  # Adjust to actual uplink ports
    breakout_option=breakout,
    priority=100
)
```

**For New Plans:**

**Recommendation:** Use zones for device-type defaults, override for plan-specific adjustments.

**Example: DS5000 with 4 uplink ports**
```python
# Create uplink zone (reusable across plans)
SwitchPortZone.objects.create(
    switch_class=switch_class,
    zone_name='spine-uplinks',
    zone_type='uplink',
    port_spec='61-64',
    breakout_option=breakout_800g,
    priority=100
)

# Optional: Override in specific plan if different
switch_class.uplink_ports_per_switch = 6  # This plan uses 6, not 4
```

**Data Migration from DeviceTypeExtension.uplink_ports (Optional):**

```python
# Migration script to create zones from old uplink_ports field

from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension, PlanSwitchClass, SwitchPortZone, BreakoutOption
)
from netbox_hedgehog.services.port_specification import PortSpecification

# Find all extensions with uplink_ports defined
extensions = DeviceTypeExtension.objects.filter(uplink_ports__isnull=False)

for ext in extensions:
    print(f"Processing {ext.device_type.slug}...")

    # Find all switch classes using this extension
    switch_classes = PlanSwitchClass.objects.filter(device_type_extension=ext)

    for sc in switch_classes:
        # Skip if already has zones or override
        if sc.uplink_ports_per_switch is not None:
            print(f"  - Skipping {sc.switch_class_id}: has override")
            continue

        existing_zones = SwitchPortZone.objects.filter(
            switch_class=sc,
            zone_type='uplink'
        )
        if existing_zones.exists():
            print(f"  - Skipping {sc.switch_class_id}: has zones")
            continue

        # Set override from old uplink_ports field
        sc.uplink_ports_per_switch = ext.uplink_ports
        sc.save()
        print(f"  - Set override to {ext.uplink_ports} for {sc.switch_class_id}")

print("Migration complete. Review and test before committing.")
```

---

## Testing

### Test Scenarios

#### Unit Tests

**New File:** `netbox_hedgehog/tests/test_topology_planning/test_uplink_capacity.py`

```python
from django.test import TestCase
from django.core.exceptions import ValidationError

from dcim.models import DeviceType, Manufacturer
from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension, TopologyPlan, PlanSwitchClass,
    SwitchPortZone, BreakoutOption
)
from netbox_hedgehog.utils.topology_calculations import get_uplink_port_count


class TestGetUplinkPortCount(TestCase):
    """Unit tests for uplink port count derivation."""

    def setUp(self):
        """Create common test fixtures."""
        self.manufacturer = Manufacturer.objects.create(name='Test', slug='test')
        self.device_type = DeviceType.objects.create(
            manufacturer=self.manufacturer,
            model='Test',
            slug='test'
        )
        self.ext = DeviceTypeExtension.objects.create(
            device_type=self.device_type,
            native_speed=800,
            uplink_ports=4  # Deprecated field (should be ignored)
        )
        self.plan = TopologyPlan.objects.create(plan_name='test')
        self.breakout = BreakoutOption.objects.create(
            breakout_id='1x800g',
            from_speed=800,
            logical_ports=1,
            logical_speed=800
        )

    def test_override_takes_precedence(self):
        """When override is set, should return override value (Priority 1)."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.ext,
            switch_class_id='leaf',
            uplink_ports_per_switch=8  # Explicit override
        )

        # Execute
        uplink_count = get_uplink_port_count(switch_class)

        # Verify override wins
        self.assertEqual(uplink_count, 8)

    def test_zone_derived_when_no_override(self):
        """When no override, should derive from uplink zones (Priority 2)."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.ext,
            switch_class_id='leaf',
            uplink_ports_per_switch=None  # No override
        )

        # Create uplink zone
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='spine-uplinks',
            zone_type='uplink',
            port_spec='61-64',  # 4 ports
            breakout_option=self.breakout,
            priority=100
        )

        # Execute
        uplink_count = get_uplink_port_count(switch_class)

        # Verify zone-derived count
        self.assertEqual(uplink_count, 4)

    def test_override_takes_precedence_over_zones(self):
        """Override wins even when zones exist."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.ext,
            switch_class_id='leaf',
            uplink_ports_per_switch=6  # Override
        )

        # Create zone (should be ignored)
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='spine-uplinks',
            zone_type='uplink',
            port_spec='61-64',  # 4 ports (ignored)
            breakout_option=self.breakout,
            priority=100
        )

        # Execute
        uplink_count = get_uplink_port_count(switch_class)

        # Verify override wins (6, not 4)
        self.assertEqual(uplink_count, 6)

    def test_multiple_uplink_zones_are_summed(self):
        """Multiple uplink zones should be aggregated."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.ext,
            switch_class_id='leaf',
            uplink_ports_per_switch=None
        )

        # Create two uplink zones
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='spine-uplinks-1',
            zone_type='uplink',
            port_spec='61-62',  # 2 ports
            breakout_option=self.breakout,
            priority=100
        )
        SwitchPortZone.objects.create(
            switch_class=switch_class,
            zone_name='spine-uplinks-2',
            zone_type='uplink',
            port_spec='63-64',  # 2 ports
            breakout_option=self.breakout,
            priority=100
        )

        # Execute
        uplink_count = get_uplink_port_count(switch_class)

        # Verify sum (2 + 2 = 4)
        self.assertEqual(uplink_count, 4)

    def test_raises_validation_error_when_no_configuration(self):
        """Should raise ValidationError when neither override nor zones exist."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.ext,
            switch_class_id='leaf',
            uplink_ports_per_switch=None  # No override
        )
        # No zones created

        # Execute
        with self.assertRaises(ValidationError) as cm:
            get_uplink_port_count(switch_class)

        # Verify error message
        self.assertIn("no uplink capacity defined", str(cm.exception))
        self.assertIn("uplink_ports_per_switch", str(cm.exception))
        self.assertIn("zone_type='uplink'", str(cm.exception))

    def test_override_zero_is_valid(self):
        """Override of 0 (no uplinks) should be valid."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.ext,
            switch_class_id='spine',
            uplink_ports_per_switch=0  # Spine has no uplinks
        )

        # Execute
        uplink_count = get_uplink_port_count(switch_class)

        # Verify 0 is valid
        self.assertEqual(uplink_count, 0)

    def test_deprecated_field_is_ignored(self):
        """DeviceTypeExtension.uplink_ports should be ignored (deprecated)."""
        switch_class = PlanSwitchClass.objects.create(
            plan=self.plan,
            device_type_extension=self.ext,  # ext.uplink_ports = 4
            switch_class_id='leaf',
            uplink_ports_per_switch=None
        )
        # No zones, no override, but ext.uplink_ports = 4 (deprecated)

        # Execute - should raise error (not use deprecated field)
        with self.assertRaises(ValidationError):
            get_uplink_port_count(switch_class)
```

*Full test implementations follow this pattern.*

#### Integration Tests

**Modified File:** `netbox_hedgehog/tests/test_topology_planning/test_topology_calculations.py`

**New Test:** `test_calculate_switch_quantity_with_zone_derived_uplinks`

**Scenario:**
- Switch class with uplink zone (port_spec='61-64' → 4 ports)
- No uplink_ports_per_switch override
- 100 servers × 2 ports each

**Expected Calculation:**
```
Physical ports: 64
Uplink reservation: 4 (from zone)
Available: 64 - 4 = 60
Switches needed: ceil(200 / 60) = 4
```

**Verification:**
- Assert `switches_needed == 4`
- Assert uplink count derived from zones (not hardcoded)

### Test Matrix

| Configuration | Override Set? | Zones Exist? | Expected Behavior | Test Case |
|---------------|--------------|--------------|-------------------|-----------|
| Override only | Yes (8) | No | Returns 8 | test_override_takes_precedence |
| Zones only | No | Yes (4 ports) | Returns 4 | test_zone_derived_when_no_override |
| Override + Zones | Yes (6) | Yes (4 ports) | Returns 6 (override wins) | test_override_takes_precedence_over_zones |
| Multiple zones | No | Yes (2+2 ports) | Returns 4 (sum) | test_multiple_uplink_zones_are_summed |
| Neither | No | No | ValidationError | test_raises_validation_error_when_no_configuration |
| Override = 0 | Yes (0) | No | Returns 0 | test_override_zero_is_valid |
| Deprecated field | No | No | ValidationError (ignored) | test_deprecated_field_is_ignored |

### Performance Tests

**Not required for this spec.** Uplink zone query is simple filter (similar to SPEC-002).

---

## Implementation Plan

### Prerequisites

- [x] DIET-SPEC-001 approved
- [x] DIET-SPEC-002 approved (establishes zone query pattern)
- [ ] DIET-SPEC-002 implemented (optional - can implement in parallel)

### Step-by-Step Implementation

**Step 1: Mark DeviceTypeExtension.uplink_ports as Deprecated**
```bash
# File: netbox_hedgehog/models/topology_planning/reference_data.py
# Update help_text with deprecation notice
```

**Step 2: Add get_uplink_port_count() Function**
```bash
# File: netbox_hedgehog/utils/topology_calculations.py
# Add function near get_port_capacity_for_connection()
```

**Step 3: Modify calculate_switch_quantity()**
```bash
# File: netbox_hedgehog/utils/topology_calculations.py:241
# Replace: uplink_ports = switch_class.uplink_ports_per_switch
# With: uplink_ports = get_uplink_port_count(switch_class)
```

**Step 4: Modify _calculate_rail_optimized_switches()**
```bash
# File: netbox_hedgehog/utils/topology_calculations.py:308
# Same replacement
```

**Step 5: Modify calculate_spine_quantity()**
```bash
# File: netbox_hedgehog/utils/topology_calculations.py:571
# Same replacement
```

**Step 6: Add Unit Tests**
```bash
# File: netbox_hedgehog/tests/test_topology_planning/test_uplink_capacity.py (NEW)
# Implement all 7 test methods from Test Matrix
```

**Step 7: Add Integration Tests**
```bash
# File: netbox_hedgehog/tests/test_topology_planning/test_topology_calculations.py
# Add test_calculate_switch_quantity_with_zone_derived_uplinks
```

**Step 8: Audit Existing Plans (Deployment)**
```bash
# Run migration guide script to find plans needing fixes
# Fix configurations before deploying
```

### File Changes Checklist

- [ ] `netbox_hedgehog/models/topology_planning/reference_data.py` - MODIFIED - Deprecate uplink_ports field
- [ ] `netbox_hedgehog/utils/topology_calculations.py` - MODIFIED - Add get_uplink_port_count()
- [ ] `netbox_hedgehog/utils/topology_calculations.py:241` - MODIFIED - Use get_uplink_port_count()
- [ ] `netbox_hedgehog/utils/topology_calculations.py:308` - MODIFIED - Use get_uplink_port_count()
- [ ] `netbox_hedgehog/utils/topology_calculations.py:571` - MODIFIED - Use get_uplink_port_count()
- [ ] `netbox_hedgehog/tests/test_topology_planning/test_uplink_capacity.py` - NEW - Unit tests
- [ ] `netbox_hedgehog/tests/test_topology_planning/test_topology_calculations.py` - MODIFIED - Integration test

### Rollback Plan

If issues discovered after deployment:

1. Revert commit implementing SPEC-003
2. No database migration to rollback (deprecation only)
3. Existing plans with override continue to work
4. Plans relying on zones will fail (expected - requires configuration)

**Medium risk:** Plans with `uplink_ports_per_switch = None` will break. Audit before deploying.

---

## Alternatives Considered

### Alternative 1: Remove uplink_ports_per_switch

**Description:** Force zone-based uplink configuration only.

**Pros:**
- Simpler model (one way to configure)
- Aligns with zone-based approach

**Cons:**
- Breaking change for all existing plans
- Less flexibility (plan-level override is useful)

**Why Rejected:** Plan-level override provides valuable flexibility for special cases.

---

### Alternative 2: Use DeviceTypeExtension.uplink_ports as Fallback

**Description:** Instead of deprecating, use as fallback (Priority 3).

**Pros:**
- More backward compatible
- Existing data is used

**Cons:**
- Three configuration sources (confusing)
- Perpetuates unused field
- Inconsistent with SPEC-002 (no native_speed on DeviceTypeExtension for uplinks)

**Why Rejected:** Field is completely unused today. Clean deprecation better than complex fallback.

---

### Alternative 3: Aggregate Multiple Zones with Weighting

**Description:** Support weighted aggregation (e.g., 50% zone1 + 50% zone2).

**Pros:**
- Flexible for complex configurations

**Cons:**
- Over-engineered (YAGNI)
- Unclear use case

**Why Rejected:** Simple sum is sufficient. No known use case for weighting.

---

## Open Questions

### Question 1: Audit Script Scope

**Question:** Should we provide automated migration script or just guidance?

**Options:**
- A) Provide full migration script (copies uplink_ports to override)
- B) Provide audit script only (users manually fix)
- C) No script (documentation only)

**Recommendation:** **Option B** (Audit script in migration guide)

**Rationale:**
- Manual review ensures correct configuration
- Automated migration may not suit all cases
- Audit script identifies issues quickly

**Decision:** [To be determined]

---

### Question 2: Default Uplink Count

**Question:** Should we provide a default uplink count when neither override nor zones exist?

**Options:**
- A) Default to 0 (no uplinks)
- B) Default to 4 (common value)
- C) No default (error - current spec)

**Recommendation:** **Option C** (No default - error)

**Rationale:**
- Forces explicit configuration
- Prevents silent errors
- Aligns with fail-fast philosophy

**Decision:** Approved in spec

---

## Performance Considerations

### Query Performance

**Expected query count:** 1 query per calculation (if no override)
- 1 query: `SwitchPortZone.filter(zone_type='uplink')`

**Indexing:** Query performance should be adequate with existing foreign key indexes. Additional composite index on `(switch_class_id, zone_type)` may be beneficial for large deployments but is not required for MVP.

**Cache strategy:** Not needed for MVP

### Memory Usage

**Expected memory impact:** Minimal
- Zone query results: <1KB

### Time Complexity

**Algorithm complexity:** O(n) where n = number of uplink zones (typically 1-2)

**Expected runtime:** <10ms per function call

---

## Documentation Updates

### User-Facing Documentation

- [ ] Update `docs/TOPOLOGY_PLANNING.md` with uplink configuration guidance
- [ ] Add examples for zone-based vs override configuration
- [ ] Document deprecation of DeviceTypeExtension.uplink_ports

### Developer Documentation

- [ ] Update `ARCHITECTURE.md` with uplink capacity flow
- [ ] Document priority order (override > zones > error)
- [ ] Add migration guide for existing deployments

---

## Dependencies

### Depends On
- DIET-SPEC-001 (prerequisite)
- DIET-SPEC-002 (establishes pattern - not blocking)

### Blocks
- None

### Related
- DIET-SPEC-002 (similar zone-based derivation pattern)
- DIET-SPEC-004 (port allocation may use uplink zones)

---

## Metrics and Monitoring

### Success Metrics

- [ ] All tests pass (7+ unit tests, 1+ integration test)
- [ ] Backward compatibility: Existing plans with override continue to work
- [ ] Zone-based uplinks work correctly
- [ ] Code coverage: >90% for new function

### Monitoring

**Metric to track:** None for MVP

**Future:** Track configuration patterns:
- % of plans using override vs zones
- Average uplink port count

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
- **Implementation start:** [After SPEC-001/002 approved]
- **Target completion:** [TBD]

---

## References

- [DIET-SPEC-001: Fix Hardcoded Port Counts](DIET-SPEC-001-Fix-Hardcoded-Port-Counts.md)
- [DIET-SPEC-002: Zone-Based Speed Derivation](DIET-SPEC-002-Zone-Based-Speed-Derivation.md)
- [Issue #114: DeviceTypeExtension architectural problems](https://github.com/afewell-hh/hh-netbox-plugin/issues/114)
- [DIET Calculation Refactoring Plan](../DIET_CALCULATION_REFACTORING_PLAN.md)
- [SwitchPortZone Model](../netbox_hedgehog/models/topology_planning/port_zones.py)
