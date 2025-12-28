# DIET-SPEC-XXX: [Title]

## Metadata
- **Spec ID:** DIET-SPEC-XXX
- **Status:** Draft | Review | Approved | Implemented
- **Authors:** [Names]
- **Created:** YYYY-MM-DD
- **Updated:** YYYY-MM-DD
- **Reviewers:** [Names]
- **Related Issues:** #XXX, #YYY
- **Related Specs:** DIET-SPEC-YYY (depends on), DIET-SPEC-ZZZ (blocks)

---

## Summary
[2-3 sentence overview of what this spec achieves]

---

## Motivation

### Problem Statement
[Detailed description of the problem this spec solves]

### Current Behavior
[Exact description of how the system works today, with code examples]

### Desired Behavior
[Exact description of how the system should work after implementation]

### Why Now
[Why this needs to be addressed at this point]

---

## Goals and Non-Goals

### Goals
- [Specific, measurable goal 1]
- [Specific, measurable goal 2]

### Non-Goals
- [What this spec explicitly does NOT address]
- [What is deferred to future specs]

---

## Detailed Design

### Overview
[High-level architecture diagram or description]

### Data Model Changes

#### New Models
```python
class NewModel(models.Model):
    """
    [Detailed docstring explaining purpose]
    """
    field_name = models.CharField(
        max_length=100,
        help_text="[Exact help text for users]",
        validators=[...]  # Specify exact validators
    )
    # All fields with exact types, validators, defaults
```

#### Modified Models
```python
# BEFORE
class ExistingModel(models.Model):
    old_field = models.IntegerField()

# AFTER
class ExistingModel(models.Model):
    old_field = models.IntegerField(
        help_text="[DEPRECATED] Use new_field instead. Will be removed in v2.0."
    )
    new_field = models.IntegerField(
        help_text="[Exact help text]"
    )
```

#### Removed Models/Fields
[List any models or fields being removed, with deprecation timeline]

### Code Changes

#### New Functions/Classes

**File:** `path/to/file.py` (NEW FILE or existing)

```python
def new_function_name(
    param1: Type1,
    param2: Type2,
    optional_param: Optional[Type3] = None
) -> ReturnType:
    """
    [Detailed docstring following Google/NumPy style]

    Args:
        param1: [Exact description]
        param2: [Exact description]
        optional_param: [Exact description, default behavior]

    Returns:
        [Exact description of return value]

    Raises:
        ValidationError: [Exact condition that triggers this]
        ValueError: [Exact condition that triggers this]

    Examples:
        >>> new_function_name(val1, val2)
        expected_result

        >>> new_function_name(val1, val2, optional_param=val3)
        expected_result_2
    """
    # Pseudocode or actual implementation
    pass
```

#### Modified Functions

**File:** `path/to/existing_file.py:123`

```python
# BEFORE (lines 123-145)
def existing_function(param1):
    # old implementation
    return result

# AFTER
def existing_function(
    param1: Type1,
    new_param: Type2  # Added
) -> ReturnType:
    """
    [Updated docstring]
    """
    # new implementation
    return result
```

### Algorithm Specifications

[For complex logic, provide step-by-step algorithm]

```
Algorithm: calculate_capacity

Input: device_extension, connection_type
Output: PortCapacity

1. Validate connection_type in ['downlink', 'uplink', 'fabric']
   - If invalid: raise ValidationError
2. Query SwitchPortZone.filter(device_extension=X, zone_type=Y)
3. If zones exist:
   a. Select first zone (ordered by start_port)
   b. Calculate port_count = zone.end_port - zone.start_port + 1
   c. Return PortCapacity(native_speed=zone.speed, port_count=port_count, is_fallback=False)
4. Else (fallback path):
   a. If device_extension.native_speed is None: raise ValidationError
   b. Query InterfaceTemplate.filter(device_type=X).count()
   c. If count == 0: use default 64
   d. Return PortCapacity(native_speed=X, port_count=Y, is_fallback=True)
```

### Error Handling

#### New Exceptions
```python
class SpecificError(ValidationError):
    """Raised when [exact condition]"""
    pass
```

#### Error Cases

| Condition | Exception | Message | HTTP Status (if API) |
|-----------|-----------|---------|---------------------|
| connection_type invalid | ValidationError | "Invalid connection_type: {value}. Must be one of: downlink, uplink, fabric" | 400 |
| No zones AND no native_speed | ValidationError | "Device type {slug} has no zones and no native_speed fallback" | 400 |

### Validation Rules

[Exact validation logic]

```python
def clean(self):
    """Model validation"""
    if self.field_a and not self.field_b:
        raise ValidationError("If field_a is set, field_b is required")
```

### Database Queries

#### Query Patterns

```python
# Query 1: Get zones for device
zones = SwitchPortZone.objects.filter(
    device_type_extension=device_extension,
    zone_type=connection_type
).select_related(
    'device_type_extension__device_type'
).order_by('start_port')

# Performance: Index on (device_type_extension_id, zone_type)
```

#### Query Optimization

- **Prefetch strategy:** [Specify when to use select_related vs prefetch_related]
- **N+1 prevention:** [How to avoid N+1 queries]
- **Indexes required:** [Exact index definitions]

### API Changes

#### REST API Endpoints (if any)

**Modified Endpoint:** `GET /api/plugins/hedgehog/topology-plans/{id}/`

**Request:** (unchanged)

**Response:** (changes)
```json
{
  "id": 123,
  "switch_classes": [
    {
      "calculated_quantity": 4,
      "capacity_details": {  // NEW
        "native_speed": 800,
        "port_count": 64,
        "is_fallback": false
      }
    }
  ]
}
```

### UI Changes

[If any UI changes, specify exact field additions/modifications]

### Configuration Changes

[Any settings changes]

```python
# settings.py or config.py
NEW_SETTING = {
    'default': 'value',
    'description': '[Exact description]'
}
```

---

## Backward Compatibility

### Compatibility Matrix

| Component | Backward Compatible? | Migration Required? | Notes |
|-----------|---------------------|---------------------|-------|
| Database schema | Yes | No | New fields nullable |
| API contracts | Yes | No | Response adds fields, doesn't remove |
| Python API | Yes | No | New parameters optional |

### Deprecation Timeline

| Item | Deprecated In | Removed In | Migration Path |
|------|--------------|------------|----------------|
| DeviceTypeExtension.native_speed | v1.1 | v2.0 | Use SwitchPortZone |

### Migration Guide

**For Existing Deployments:**

```bash
# Step 1: Apply migrations
python manage.py migrate netbox_hedgehog

# Step 2: [Any data migration steps]

# Step 3: [Any config changes]
```

**For Existing Code:**

```python
# BEFORE
native_speed = device_ext.native_speed

# AFTER
capacity = get_port_capacity_for_connection(device_ext, 'downlink')
native_speed = capacity.native_speed
```

---

## Testing

### Test Scenarios

#### Unit Tests

**File:** `tests/test_capacity.py` (NEW)

```python
class TestGetPortCapacityForConnection(TestCase):
    """Unit tests for get_port_capacity_for_connection"""

    def test_zone_based_capacity_returns_zone_speed(self):
        """When zones exist, should return zone native_speed"""
        # Given: Device with zone defined
        device_type = DeviceType.objects.create(slug='test-switch')
        ext = DeviceTypeExtension.objects.create(
            device_type=device_type,
            native_speed=100  # Fallback value
        )
        zone = SwitchPortZone.objects.create(
            device_type_extension=ext,
            zone_type='downlink',
            start_port=1,
            end_port=48,
            native_speed=25  # Different from fallback
        )

        # When: Get capacity
        capacity = get_port_capacity_for_connection(ext, 'downlink')

        # Then: Should use zone speed, not fallback
        self.assertEqual(capacity.native_speed, 25)
        self.assertEqual(capacity.port_count, 48)
        self.assertFalse(capacity.is_fallback)
        self.assertEqual(capacity.source_zone, zone)

    def test_fallback_when_no_zones_defined(self):
        """When no zones, should use native_speed fallback"""
        # Test implementation...
        pass

    def test_raises_validation_error_for_invalid_connection_type(self):
        """Should raise ValidationError for invalid connection_type"""
        # Test implementation...
        pass
```

#### Integration Tests

**File:** `tests/test_topology_planning/test_capacity_integration.py`

```python
class TestCapacityIntegration(TestCase):
    """Integration tests for capacity calculation in topology planning"""

    def test_mixed_port_switch_es1000_calculates_correctly(self):
        """ES1000 with 48×1G + 4×25G should calculate correctly"""
        # Full integration test with real topology plan
        pass
```

### Test Matrix

| Scenario | Zone Exists? | native_speed Set? | InterfaceTemplate Count | Expected Behavior |
|----------|--------------|-------------------|------------------------|-------------------|
| Happy path (zone) | Yes | Yes | 64 | Use zone speed & count |
| Fallback path | No | Yes | 64 | Use native_speed & template count |
| No templates | No | Yes | 0 | Use native_speed & default 64 |
| Error case | No | No | 64 | Raise ValidationError |
| Invalid type | N/A | N/A | N/A | Raise ValidationError |

### Performance Tests

```python
def test_capacity_calculation_performance(self):
    """Should calculate capacity for 1000 switches in <1 second"""
    # Create 1000 device types with zones
    # Measure time
    # Assert < 1000ms
```

### Regression Tests

[Tests to ensure existing behavior doesn't break]

---

## Implementation Plan

### Prerequisites
- [ ] Dependency A completed
- [ ] Dependency B reviewed

### Step-by-Step Implementation

**Step 1: Database Changes**
```bash
# File: migrations/XXXX_add_capacity_fields.py
# Create migration for any schema changes
```

**Step 2: Core Logic**
```bash
# File: utils/capacity.py (NEW)
# Implement get_port_capacity_for_connection()
```

**Step 3: Integration**
```bash
# File: utils/topology_calculations.py:236
# Replace hardcoded 64 with capacity query
```

**Step 4: Tests**
```bash
# File: tests/test_capacity.py (NEW)
# Implement all test scenarios
```

**Step 5: Documentation**
```bash
# File: docs/CAPACITY_CALCULATION.md (NEW)
# User-facing documentation
```

### File Changes Checklist

- [ ] `utils/capacity.py` - NEW - Core capacity logic
- [ ] `utils/topology_calculations.py:236` - MODIFIED - Use new helper
- [ ] `utils/topology_calculations.py:306` - MODIFIED - Use new helper
- [ ] `utils/topology_calculations.py:568` - MODIFIED - Use new helper
- [ ] `tests/test_capacity.py` - NEW - Unit tests
- [ ] `tests/test_topology_planning/test_capacity_integration.py` - MODIFIED - Integration tests
- [ ] `migrations/XXXX_add_fields.py` - NEW - If schema changes

### Rollback Plan

If issues discovered after deployment:

1. Revert commit [hash]
2. Run migration rollback: `python manage.py migrate netbox_hedgehog XXXX`
3. Clear cache: `python manage.py clear_cache`
4. Restart services

---

## Alternatives Considered

### Alternative 1: [Name]

**Description:** [How it would work]

**Pros:**
- [Advantage 1]
- [Advantage 2]

**Cons:**
- [Disadvantage 1]
- [Disadvantage 2]

**Why Rejected:** [Specific reason]

### Alternative 2: [Name]

[Same structure]

---

## Open Questions

### Question 1: [Topic]
**Question:** [Exact question]
**Options:**
- A) [Option description]
- B) [Option description]
**Recommendation:** [Option X] because [reason]
**Decision:** [To be determined / Decided: Option X on YYYY-MM-DD]

### Question 2: [Topic]
[Same structure]

---

## Security Considerations

[Any security implications]

- **Input validation:** [How user inputs are validated]
- **Authorization:** [Any permission changes]
- **Sensitive data:** [Any sensitive data handling]

---

## Performance Considerations

### Query Performance
- **Expected query count:** [Number of DB queries]
- **Indexes required:** [List specific indexes]
- **Cache strategy:** [What to cache, TTL]

### Memory Usage
- **Expected memory impact:** [Estimate]
- **Large dataset handling:** [How to handle 10k+ objects]

### Time Complexity
- **Algorithm complexity:** O(n) for [operation]
- **Expected runtime:** [Benchmarks]

---

## Documentation Updates

### User-Facing Documentation

- [ ] Update `docs/USER_GUIDE.md` section [X]
- [ ] Update `docs/API_REFERENCE.md` endpoint [Y]
- [ ] Create new `docs/CAPACITY_CALCULATION.md`

### Developer Documentation

- [ ] Update `ARCHITECTURE.md` with capacity flow
- [ ] Add inline code comments for complex logic
- [ ] Update `CONTRIBUTING.md` if dev workflow changes

---

## Dependencies

### Depends On
- DIET-SPEC-XXX (must be implemented first)

### Blocks
- DIET-SPEC-YYY (cannot start until this is done)

### Related
- DIET-SPEC-ZZZ (related work, can be parallel)

---

## Metrics and Monitoring

### Success Metrics
- [ ] All tests pass (100% of specified test scenarios)
- [ ] Performance: capacity calculation < 100ms for single switch
- [ ] No regression: existing tests still pass
- [ ] Code coverage: new code has >90% coverage

### Monitoring
- **Metric to track:** [Specific metric name]
- **Alert threshold:** [When to alert]
- **Dashboard:** [Link to dashboard]

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| YYYY-MM-DD | Name | Initial draft |
| YYYY-MM-DD | Name | Addressed review feedback |
| YYYY-MM-DD | Name | Approved for implementation |

---

## Approval

### Reviewers

- [ ] **Dev A:** [Name] - Architecture review
- [ ] **Dev B:** [Name] - Implementation review
- [ ] **Dev C:** [Name] - Testing review
- [ ] **Tech Lead:** [Name] - Final approval

### Sign-off

- **Approved by:** [Name]
- **Approval date:** YYYY-MM-DD
- **Implementation start:** YYYY-MM-DD
- **Target completion:** YYYY-MM-DD

---

## References

- [Issue #XXX](link)
- [Research Document](link)
- [Related Spec](link)
- [External Documentation](link)
