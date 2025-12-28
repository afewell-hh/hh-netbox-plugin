# DIET-SPEC-001: Fix Hardcoded Port Counts

## Metadata
- **Spec ID:** DIET-SPEC-001
- **Status:** Draft (awaiting team review)
- **Authors:** Dev A (Claude/Agent A)
- **Created:** 2025-12-27
- **Updated:** 2025-12-27
- **Reviewers:** Dev B, Dev C
- **Related Issues:** #114
- **Related Specs:** Blocks DIET-SPEC-002
- **Priority:** HIGH (Phase 1)
- **Risk:** LOW

---

## Summary

Replace three instances of `physical_ports = 64` hardcoded values with dynamic port count derivation from NetBox `InterfaceTemplate` model, with safe fallback to 64 for backward compatibility.

---

## Motivation

### Problem Statement

Topology calculations assume all switches have 64 physical ports. This breaks for:
- **DS3000:** 32 ports (calculations think it has 64 → over-estimate capacity)
- **ES1000:** 52 ports (48×1G + 4×25G)
- **Future devices:** Any non-64-port switch

### Current Behavior

**File:** `netbox_hedgehog/utils/topology_calculations.py`

**Line 236:**
```python
# Step 5: Calculate logical ports per switch
# NOTE: For MVP, we assume all ports on the switch are the same
# TODO: Replace hardcoded port count with actual count from InterfaceTemplate
#       Query: dcim.InterfaceTemplate.objects.filter(
#           device_type=device_extension.device_type
#       ).count()
#       This will support switches with different port counts (32, 48, 64, etc.)
physical_ports = 64  # MVP default for DS5000
```

**Line 306:** (in `_calculate_rail_optimized_switches`)
```python
physical_ports = 64  # MVP default for DS5000
```

**Line 568:** (in `calculate_spine_quantity`)
```python
physical_ports = 64  # MVP default for DS5000
```

### Desired Behavior

Query actual port count from NetBox `InterfaceTemplate`:

```python
from dcim.models import InterfaceTemplate

physical_ports = InterfaceTemplate.objects.filter(
    device_type=device_extension.device_type
).count()

# Fallback for safety (device types without templates)
if physical_ports == 0:
    physical_ports = 64
```

### Why Now

- Blocks DS3000 support (customer requirement)
- Identified as HIGH RISK in Dev C's audit
- Easy fix with LOW RISK (read-only query + fallback)
- Foundation for DIET-SPEC-002 (zone-based speed)

---

## Goals and Non-Goals

### Goals
- ✅ Replace all 3 hardcoded `physical_ports = 64` with InterfaceTemplate query
- ✅ Support switches with 32, 48, 52, 64, or any port count
- ✅ Maintain backward compatibility (fallback to 64)
- ✅ Add test coverage for DS3000 (32 ports) and DS5000 (64 ports)
- ✅ Zero breaking changes to API or existing behavior

### Non-Goals
- ❌ **Zone-based port capacity** - Deferred to DIET-SPEC-002 (zone speed logic)
- ❌ **Mixed-port switch logic** - ES1000 with different speed zones deferred to DIET-SPEC-002
- ❌ **Differential port counting** - Counting only downlink vs uplink ports (DIET-SPEC-002)
- ❌ **Port speed derivation** - Still uses `native_speed` (DIET-SPEC-002 addresses this)
- ❌ **Caching or performance optimization** - COUNT query is fast enough (<5ms)
- ❌ **Module-derived ports** - Doesn't handle ports from installed modules (future work)
- ❌ **Breaking changes** - No API or schema changes, 100% backward compatible

---

## NetBox Schema Alignment

This spec aligns with NetBox's core device modeling:

**Schema Used:**
- `dcim.DeviceType` - Device type definition (e.g., DS5000, DS3000)
- `dcim.InterfaceTemplate` - Port templates on DeviceType (defines physical ports)

**Query Pattern:**
```python
InterfaceTemplate.objects.filter(device_type=device_type).count()
```

**What This Counts:**
- All InterfaceTemplates attached directly to the DeviceType
- Includes all interface types (1000base-t, 100gbase-x-qsfp28, etc.)
- Does NOT count module-derived ports (e.g., from installed ModuleBays)

**Multiple Interface Types:**
For switches with mixed-port speeds (e.g., ES1000: 48×1G + 4×25G), this spec counts **total physical ports** (52), not speed-differentiated groups. Speed-specific capacity is deferred to DIET-SPEC-002 (zone-based logic).

**Rationale:**
- Correct for uniform-port switches (DS5000, DS3000)
- Provides accurate total port count for mixed-port switches
- Foundation for zone-based speed derivation (DIET-SPEC-002)

---

## Edge Cases

### Identified Edge Cases

| Edge Case | Behavior | Rationale |
|-----------|----------|-----------|
| **No InterfaceTemplates defined** | Returns 64 (fallback) | Backward compatibility for legacy device types |
| **Zero ports (edge case)** | Returns 64 (fallback) | Prevents divide-by-zero in calculations |
| **Multiple interface types** | Counts all (52 for ES1000) | Total physical ports, not speed-specific |
| **Module-derived ports** | NOT counted | InterfaceTemplate on DeviceType only, not ModuleType |
| **Virtual interfaces** | Counted if InterfaceTemplate exists | No filtering by interface type (out of scope) |
| **Non-physical ports (LAG, tunnel)** | Counted if InterfaceTemplate exists | No type filtering (acceptable for MVP) |

⚠️ **CAVEAT: Non-Physical Template Over-Count Risk**

This spec counts **ALL** InterfaceTemplates, including management/virtual/LAG/tunnel interfaces. This can lead to port count over-estimation for devices with many non-physical templates.

**Example Risk:**
```python
# Switch with:
# - 64 physical data ports (800G)
# - 1 management interface (1G)
# - 2 LAG interfaces (virtual)
# Total InterfaceTemplates: 67

# This spec counts: 67 (includes non-physical)
# Actual physical ports: 64
# Over-count: 3 ports (4.6% error)
```

**Mitigation for MVP:**
- Acceptable for typical spine/leaf switches (few non-physical templates)
- Document limitation in code comments
- **DEFER to DIET-SPEC-002:** Zone-based capacity will distinguish physical vs virtual zones

**Action for SPEC-002:**
- Add interface type filtering or zone-based physical port identification
- Revisit this caveat when implementing zone logic

### Edge Case: Module-Derived Ports

**Not Handled:**
If a switch has ports defined in ModuleType (via ModuleBay), those ports are **not counted** by this spec.

**Example:**
```python
# DeviceType with 48 built-in ports + 2 module bays
# Each module bay can have a 4-port module installed
# Total physical ports: 48 + (2 × 4) = 56

# This spec counts: 48 (only DeviceType InterfaceTemplates)
# Missing: 8 ports from modules
```

**Mitigation:** Module-derived ports are rare for switches in DIET's use case (data center spine/leaf). If needed, addressed in future spec.

**Workaround:** Create InterfaceTemplates for all ports on DeviceType (don't use modules for switch ports).

---

## Detailed Design

### Overview

```
Current Flow:
  calculate_switch_quantity()
    → physical_ports = 64  (HARDCODED)
    → logical_ports = physical_ports × breakout.logical_ports
    → available_ports = logical_ports - uplink_ports
    → switches_needed = ceil(total_demand / available_ports)

New Flow:
  calculate_switch_quantity()
    → physical_ports = get_physical_port_count(device_type)  (DYNAMIC)
        ├─ Query InterfaceTemplate.count()
        └─ Fallback to 64 if count == 0
    → logical_ports = physical_ports × breakout.logical_ports
    → available_ports = logical_ports - uplink_ports
    → switches_needed = ceil(total_demand / available_ports)
```

### Data Model Changes

**None.** This spec only changes calculation logic, not database schema.

### Code Changes

#### New Helper Function

**File:** `netbox_hedgehog/utils/topology_calculations.py`

**Location:** Add after imports, before `determine_optimal_breakout()` (around line 15)

```python
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

        # NOTE: Future consideration (out of scope for this spec):
        # Should we log a warning when using fallback?
        # Pros: Alerts admins to incomplete device type definitions
        # Cons: Could be noisy for intentionally minimal setups
        # DECISION: Defer to operational experience; no logging for MVP

        return 64

    return port_count
```

**Fallback Logging Note:**
For devices without InterfaceTemplates, this function silently returns 64. Future consideration: add warning log to alert administrators of incomplete device type definitions. Deferred to avoid noise in MVP; revisit based on operational experience.

#### Modified Functions (3 locations)

All three functions follow the same pattern: replace `physical_ports = 64` with `get_physical_port_count(device_extension.device_type)`.

**1. `calculate_switch_quantity()` - Line 236:**
```python
# BEFORE:
physical_ports = 64  # MVP default for DS5000

# AFTER:
physical_ports = get_physical_port_count(device_extension.device_type)
```
- Remove 7 lines of obsolete TODO comments (lines 229-235)
- Replace hardcoded value with helper function call

**2. `_calculate_rail_optimized_switches()` - Line 306:**
```python
# BEFORE:
physical_ports = 64  # MVP default for DS5000

# AFTER:
physical_ports = get_physical_port_count(device_extension.device_type)
```
- Simple one-line replacement

**3. `calculate_spine_quantity()` - Line 568:**
```python
# BEFORE:
physical_ports = 64  # MVP default for DS5000

# AFTER:
physical_ports = get_physical_port_count(device_extension.device_type)
```
- Simple one-line replacement

### Algorithm Specification

**No algorithm changes.** This spec only changes how `physical_ports` is obtained.

### Error Handling

**No new errors.** The function returns a safe fallback (64) instead of raising exceptions.

**Rationale:**
- Maintains backward compatibility
- Prevents breaking existing device types without InterfaceTemplates
- Clear documentation that 64 is a fallback, not a bug

### Validation Rules

**No validation changes.** This is a calculation change, not a data validation change.

### Database Queries

#### New Query Pattern

```python
# Query: Count InterfaceTemplates for a device type
port_count = InterfaceTemplate.objects.filter(
    device_type=device_type
).count()
```

**Performance Characteristics:**
- **Query type:** COUNT query (fast)
- **Indexes:** Existing index on `interface_template.device_type_id`
- **Expected rows:** 32-64 per device type (small)
- **Query time:** <5ms (count only, no data transfer)

#### Query Optimization

**Current (no optimization needed):**
- COUNT queries are very fast (index-only operation)
- No N+1 risk (called once per switch class, not per switch instance)
- No complex joins

**Future optimization (out of scope for this spec):**
- Could cache port count in DeviceTypeExtension (DIET-SPEC-004)
- Could prefetch when loading multiple device types (DIET-SPEC-002)

### API Changes

**None.** Internal calculation change only, no API contract changes.

### UI Changes

**None.** No UI changes required.

---

## Backward Compatibility

### Compatibility Matrix

| Component | Backward Compatible? | Migration Required? | Notes |
|-----------|---------------------|---------------------|-------|
| Database schema | Yes | No | No schema changes |
| API contracts | Yes | No | No API changes |
| Python API | Yes | No | Internal change only |
| Existing calculations | Yes | No | Falls back to 64 if no templates |
| Test fixtures | Partial | Yes | See Test Data Migration |

### Compatibility Guarantees

1. **Device types WITH InterfaceTemplates:** Will use accurate port count
2. **Device types WITHOUT InterfaceTemplates:** Will use fallback (64) - same as current behavior
3. **All calculations:** Produce identical results for 64-port switches

### Test Data Migration

**Existing test fixtures must be updated:**

Many tests create `DeviceType` without creating `InterfaceTemplate`. These tests will get fallback value (64), which may not match test expectations for DS3000 (32 ports).

**Action Required:**
- Identify tests that use DS3000 device type
- Add InterfaceTemplate creation to test setup
- Verify expected port counts match

**Example Test Update:**

```python
# BEFORE
device_type = DeviceType.objects.create(
    slug='ds3000',
    model='DS3000'
)
# Calculations will use fallback (64) - WRONG for DS3000!

# AFTER
device_type = DeviceType.objects.create(
    slug='ds3000',
    model='DS3000'
)
# Create 32 InterfaceTemplates for DS3000
for i in range(1, 33):
    InterfaceTemplate.objects.create(
        device_type=device_type,
        name=f'Ethernet1/{i}',
        type='100gbase-x-qsfp28'
    )
# Calculations will use 32 - CORRECT!
```

---

## Testing

### Test Scenarios

#### Unit Tests

**New File:** `netbox_hedgehog/tests/test_topology_planning/test_port_count.py`

**Test Class:** `TestGetPhysicalPortCount`

| Test Method | Setup | Expected Result |
|-------------|-------|-----------------|
| `test_returns_64_for_device_type_with_64_templates` | DS5000 with 64 InterfaceTemplates | Returns 64 |
| `test_returns_32_for_device_type_with_32_templates` | DS3000 with 32 InterfaceTemplates | Returns 32 |
| `test_returns_52_for_device_type_with_52_templates` | ES1000 with 52 InterfaceTemplates (48×1G + 4×25G) | Returns 52 |
| `test_returns_64_fallback_when_no_templates_defined` | Device type with NO InterfaceTemplates | Returns 64 (fallback) |

**Example Test (DS3000):**
```python
def test_returns_32_for_device_type_with_32_templates(self):
    """Should return 32 when device type has 32 InterfaceTemplates (DS3000)"""
    # Setup: DS3000 with 32 InterfaceTemplates
    device_type = DeviceType.objects.create(slug='ds3000', ...)
    for i in range(1, 33):
        InterfaceTemplate.objects.create(
            device_type=device_type,
            name=f'Ethernet1/{i}',
            type='100gbase-x-qsfp28'
        )

    # Execute
    port_count = get_physical_port_count(device_type)

    # Verify
    self.assertEqual(port_count, 32)
```

*Full test implementations follow this pattern - see SPEC-001 appendix for complete code.*

**Test Helper Recommendation (Dev C feedback):**

To avoid repetitive InterfaceTemplate creation loops in tests, consider creating a helper function:

```python
def create_interface_templates(
    device_type: 'DeviceType',
    count: int,
    port_type: str = '100gbase-x-qsfp28',
    name_pattern: str = 'Ethernet1/{}'
) -> list['InterfaceTemplate']:
    """
    Helper to create multiple InterfaceTemplates for testing.

    Args:
        device_type: DeviceType to attach templates to
        count: Number of templates to create
        port_type: NetBox interface type (default: 100gbase-x-qsfp28)
        name_pattern: Name pattern with {} placeholder for index

    Returns:
        List of created InterfaceTemplate instances

    Example:
        >>> ds3000 = DeviceType.objects.create(slug='ds3000')
        >>> templates = create_interface_templates(ds3000, 32)
        >>> len(templates)
        32
    """
    return [
        InterfaceTemplate.objects.create(
            device_type=device_type,
            name=name_pattern.format(i),
            type=port_type
        )
        for i in range(1, count + 1)
    ]
```

**Usage in tests:**
```python
# Instead of inline loops:
for i in range(1, 33):
    InterfaceTemplate.objects.create(...)

# Use helper:
create_interface_templates(ds3000_type, 32)  # Creates 32 templates
```

This improves test readability and reduces boilerplate.

#### Integration Tests

**Modified File:** `netbox_hedgehog/tests/test_topology_planning/test_topology_calculations.py`

**New Test:** `test_calculate_switch_quantity_uses_actual_port_count_for_ds3000`

**Scenario:**
- Topology plan with DS3000 switch (32 ports, not 64)
- 100 servers × 1 port each = 100 ports demand
- 4 uplink ports reserved

**Expected Calculation:**
```
Available ports = 32 - 4 uplinks = 28 ports
Switches needed = ceil(100 / 28) = 4 switches
```

**Verification:**
- Assert `switches_needed == 4`
- Document wrong behavior (if used 64): `ceil(100 / 60) = 2` ❌

### Test Matrix

| Device Type | InterfaceTemplate Count | Expected port_count | Test Case |
|-------------|------------------------|---------------------|-----------|
| DS5000 | 64 | 64 | test_returns_64_for_device_type_with_64_templates |
| DS3000 | 32 | 32 | test_returns_32_for_device_type_with_32_templates |
| ES1000 | 52 (48+4) | 52 | test_returns_52_for_device_type_with_52_templates |
| Legacy (no templates) | 0 | 64 (fallback) | test_returns_64_fallback_when_no_templates_defined |
| DS3000 integration | 32 | 32 | test_calculate_switch_quantity_uses_actual_port_count_for_ds3000 |

### Performance Tests

**Not required for this spec.** COUNT queries are fast enough (<5ms) that no performance regression is expected.

**Future:** If performance becomes an issue, add test in DIET-SPEC-004 (caching).

### Regression Tests

**Existing tests must pass:**
- All tests in `test_topology_planning/test_topology_calculations.py`
- All tests in `test_topology_planning/test_integration.py`

**Action:** Run full test suite and verify no regressions.

```bash
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning
```

---

## Implementation Plan

### Prerequisites
- [ ] None (this is Phase 1, no dependencies)

### Step-by-Step Implementation

**Step 1: Add Helper Function**

File: `netbox_hedgehog/utils/topology_calculations.py`

1. Add `get_physical_port_count()` function after imports (line ~15)
2. Include full docstring with examples
3. Import `InterfaceTemplate` from `dcim.models`

**Step 2: Update calculate_switch_quantity()**

File: `netbox_hedgehog/utils/topology_calculations.py:229-236`

1. Replace lines 229-236 (7 lines) with 3 lines
2. Change comment to reflect new behavior
3. Call `get_physical_port_count(device_extension.device_type)`

**Step 3: Update _calculate_rail_optimized_switches()**

File: `netbox_hedgehog/utils/topology_calculations.py:305-306`

1. Replace line 306 with function call
2. Add comment explaining query

**Step 4: Update calculate_spine_quantity()**

File: `netbox_hedgehog/utils/topology_calculations.py:567-568`

1. Replace line 568 with function call
2. Add comment explaining query

**Step 5: Create Unit Tests**

File: `netbox_hedgehog/tests/test_topology_planning/test_port_count.py` (NEW)

1. Create new test file
2. Implement all 4 test cases from Test Scenarios
3. Run tests: `docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_topology_planning.test_port_count`

**Step 6: Add Integration Test**

File: `netbox_hedgehog/tests/test_topology_planning/test_topology_calculations.py`

1. Add `test_calculate_switch_quantity_uses_actual_port_count_for_ds3000()`
2. Run test: verify it passes

**Step 7: Update Existing Test Fixtures**

Files: Multiple test files

1. Search for tests creating DS3000 DeviceType
2. Add InterfaceTemplate creation for each
3. Run full test suite: verify no regressions

**Step 8: Manual Verification**

1. Start NetBox dev server
2. Create DS3000 device type with 32 InterfaceTemplates via UI
3. Create TopologyPlan using DS3000
4. Verify calculated switch quantity is correct

### File Changes Checklist

- [ ] `netbox_hedgehog/utils/topology_calculations.py:15` - ADD - `get_physical_port_count()` function
- [ ] `netbox_hedgehog/utils/topology_calculations.py:229-236` - MODIFY - Use helper in `calculate_switch_quantity()`
- [ ] `netbox_hedgehog/utils/topology_calculations.py:306` - MODIFY - Use helper in `_calculate_rail_optimized_switches()`
- [ ] `netbox_hedgehog/utils/topology_calculations.py:568` - MODIFY - Use helper in `calculate_spine_quantity()`
- [ ] `netbox_hedgehog/tests/test_topology_planning/test_port_count.py` - NEW - Unit tests
- [ ] `netbox_hedgehog/tests/test_topology_planning/test_topology_calculations.py` - MODIFY - Add integration test
- [ ] `netbox_hedgehog/tests/test_topology_planning/*.py` - MODIFY - Update test fixtures (as needed)

### Rollback Plan

If issues discovered:

1. **Revert code changes:**
   ```bash
   git revert <commit-hash>
   ```

2. **No database rollback needed** (no schema changes)

3. **Verify tests pass after revert:**
   ```bash
   docker compose exec netbox python manage.py test netbox_hedgehog
   ```

---

## Alternatives Considered

### Alternative 1: Query InterfaceTemplate Every Time (No Fallback)

**Description:** Raise error if InterfaceTemplate count is 0

**Pros:**
- Forces proper data setup
- No magic fallback value

**Cons:**
- Breaks backward compatibility
- Requires migration for all existing device types
- Higher risk

**Why Rejected:** Fallback approach is safer for MVP, can remove fallback in v2.0

### Alternative 2: Cache Port Count in DeviceTypeExtension

**Description:** Add `port_count` field to DeviceTypeExtension, cache the value

**Pros:**
- Faster (no query per calculation)
- Explicit value visible to users

**Cons:**
- Requires migration
- Requires sync logic when InterfaceTemplates change
- Adds complexity

**Why Rejected:** Premature optimization. COUNT query is fast enough (<5ms). Can add caching in DIET-SPEC-004 if needed.

### Alternative 3: Use SwitchPortZone.port_count

**Description:** Get port count from SwitchPortZone instead of InterfaceTemplate

**Pros:**
- Works for mixed-port switches
- More accurate for zone-based calculations

**Cons:**
- Requires zones to be defined (not all device types have them)
- More complex fallback logic
- Couples this spec to DIET-SPEC-002

**Why Rejected:** Out of scope. This spec is intentionally simple (just fix hardcoded 64). Zone-based logic is DIET-SPEC-002.

---

## Open Questions

### Question 1: Fallback Value
**Question:** Should fallback be 64 or raise ValidationError?
**Options:**
- A) Fallback to 64 (proposed)
- B) Raise ValidationError
**Recommendation:** Option A - safer for backward compatibility
**Decision:** Option A (approved 2025-12-27 by Dev A, pending team review)

### Question 2: Caching
**Question:** Should we cache port count results?
**Options:**
- A) No caching (COUNT query is fast)
- B) Cache in DeviceTypeExtension
- C) Cache in memory per request
**Recommendation:** Option A for MVP, revisit in DIET-SPEC-004 if performance issues arise
**Decision:** Option A (approved 2025-12-27 by Dev A, pending team review)

---

## Security Considerations

**No security implications.**
- Read-only query
- No user input
- No sensitive data

---

## Performance Considerations

### Query Performance
- **Expected query count:** 1 per switch class (not per switch instance)
- **Indexes required:** Existing index on `dcim_interfacetemplate.device_type_id`
- **Query time:** <5ms (COUNT only)
- **No N+1 risk:** Called once per switch class, not in loop

### Memory Usage
- **No change:** COUNT query returns integer, not object list

### Time Complexity
- **No change:** Algorithm complexity unchanged (still O(n) for switch quantity calculation)

---

## Documentation Updates

### User-Facing Documentation

- [ ] Update `docs/USER_GUIDE.md` (not needed - internal change)
- [ ] Update `docs/API_REFERENCE.md` (not needed - no API changes)

### Developer Documentation

- [ ] Add inline docstring to `get_physical_port_count()`
- [ ] Update comments in topology_calculations.py (removing obsolete TODOs)

---

## Dependencies

### Depends On
- None

### Blocks
- DIET-SPEC-002 (zone-based speed depends on this being stable)

### Related
- None

---

## Metrics and Monitoring

### Success Metrics
- [ ] All 4 unit tests pass (100%)
- [ ] Integration test passes (DS3000 calculates correctly)
- [ ] Existing test suite passes (no regressions)
- [ ] Code coverage: new function has 100% coverage

### Monitoring
- **No new metrics needed** (internal calculation change)

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2025-12-27 | Dev A | Initial draft |

---

## Approval

### Reviewers

- [ ] **Dev A:** Architecture review (self-review complete)
- [ ] **Dev B:** Implementation review
- [ ] **Dev C:** Testing review (particularly important - identified the issue)
- [ ] **User:** Final approval

### Sign-off

- **Approved by:** (pending)
- **Approval date:** (pending)
- **Implementation start:** (pending approval)
- **Target completion:** 1 day after approval

---

## References

- [Issue #114](https://github.com/afewell-hh/hh-netbox-plugin/issues/114) - DevC's architectural concerns
- [DIET_CALCULATION_REFACTORING_PLAN.md](../DIET_CALCULATION_REFACTORING_PLAN.md) - Overall refactoring plan
- [NetBox InterfaceTemplate Documentation](https://netboxlabs.com/docs/netbox/models/dcim/interfacetemplate/)
- [DIET_NETBOX_DEVICE_MODELING_RESEARCH.md](../DIET_NETBOX_DEVICE_MODELING_RESEARCH.md) - Research findings
