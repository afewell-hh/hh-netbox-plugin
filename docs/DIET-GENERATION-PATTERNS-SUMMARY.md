# DIET Generation Patterns Research Summary

## Overview

Researched deterministic object generation patterns from IaC tools, Kubernetes operators, and database performance studies to guide DIET's scaling to 10,000+ NetBox objects.

**Full Report**: See `docs/DIET-GENERATION-PATTERNS.md`

---

## Key Findings

### 1. Architecture Patterns

**Terraform Lesson**: Use stable identifiers (like `for_each` with map keys) instead of positional indices to avoid resource churn when adding/removing items.

**Kubernetes Operators**: Reconciliation loops focus on "desired vs actual" state, with idempotent operations that can be safely re-run.

**DIET Status**: ✅ Already follows three-phase pattern (PLAN → GENERATE → RECONCILE) with good separation of concerns.

### 2. Determinism & Idempotency

**Critical Requirements**:
- No random/timestamp components in names (Azure/Bicep best practice)
- Same inputs must always produce same outputs (IaC principle)
- Snapshot-based change detection (Kubernetes resource versioning pattern)

**DIET Status**:
- ✅ Deterministic naming via templates
- ✅ GenerationState tracks plan snapshots
- ⚠️ Snapshot should include connections/port zones (not just quantities)

### 3. Performance at Scale

**Research Shows**:
- Django `bulk_create()` is **10-100x faster** than individual saves
- Optimal batch size: **500-1000 objects** for Django ORM
- Single large batch typically outperforms multiple small batches (less network overhead)

**Current DIET Performance** (estimated):
- **128-GPU case**: 164 devices, 1,096 interfaces, 548 cables → ~18 seconds
- **10k server case** (projected with current code): ~23 minutes
- **10k with bulk_create**: ~2.3 minutes (10x speedup)

**Bottleneck**: Individual `device.save()` calls instead of `bulk_create()`

### 4. Relationship Management

**NetBox Specifics**:
- Cables must be deleted BEFORE devices (termination protection)
- Cable API requires object IDs (not names)
- Current caching pattern is efficient for in-memory generation

**DIET Status**: ✅ Correct deletion order, efficient caching

### 5. Testing Approaches

**Recommended Layers**:
1. **Unit tests**: Logic with mocked dependencies (current)
2. **Integration tests**: Real NetBox objects (current)
3. **Property-based tests**: Hypothesis library for invariants (NEW)
4. **Scale benchmarks**: Performance tracking for 1k/10k objects (NEW)
5. **Idempotency tests**: Run twice, verify same outcome (partial)

---

## Recommendations

### Immediate (Next Sprint)

1. **Migrate to bulk_create** (10x-100x speedup):
   ```python
   # Before
   for i in range(quantity):
       device = Device(...)
       device.save()

   # After
   devices = [Device(...) for i in range(quantity)]
   Device.objects.bulk_create(devices, batch_size=500)
   ```

2. **Add scale test** for 1,000 devices to catch performance regressions

3. **Expand snapshot** to include connection definitions and port zones

### Short-term

4. **Property-based testing** with Hypothesis library (find edge cases automatically)
5. **Performance metrics**: Track generation duration in GenerationState
6. **Naming validation**: Document/enforce no random/timestamp functions in templates

### Long-term

7. **Incremental updates**: Support "add 10 servers" without regenerating all 10,000
8. **Progress reporting**: Multi-phase commits with status updates for UX
9. **Validation phase**: Separate validation from generation for fail-fast behavior

---

## Impact Analysis

### Current 128-GPU Test Case
- 164 devices, 1,096 interfaces, 548 cables
- Works fine with current implementation

### Projected 10k Server Deployment
- 10,040 devices, 90,240 interfaces, 40,000 cables
- **Current code**: 23 minutes (unacceptable)
- **With bulk_create**: 2.3 minutes (acceptable)
- **With incremental updates**: <30 seconds for small changes

---

## Code Example: Bulk Create Migration

```python
def _create_switch_devices_bulk(self) -> dict[str, Device]:
    """Create switch devices using bulk_create for performance."""
    devices_to_create = []
    switch_devices = {}

    for switch_class in self.plan.switch_classes.all():
        role = self._ensure_role(...)
        for index in range(switch_class.effective_quantity):
            name = self._render_device_name(...)
            device = Device(
                name=name,
                device_type=switch_class.device_type_extension.device_type,
                role=role,
                site=self.site,
                status=DeviceStatusChoices.STATUS_PLANNED,
            )
            device.custom_field_data = {'hedgehog_plan_id': str(self.plan.pk), ...}
            devices_to_create.append(device)
            switch_devices[name] = device

    # Single bulk operation instead of N individual saves
    Device.objects.bulk_create(devices_to_create, batch_size=500)
    return switch_devices
```

**Benefits**:
- Reduces DB round-trips from N to N/500
- Enables 10k+ device generation in reasonable time
- Minimal code changes (same logic, different API)

---

## References Summary

**IaC Patterns**: Terraform for_each, Pulumi dynamic providers, Azure naming conventions
**State Management**: Kubernetes operator reconciliation loops, idempotency patterns
**Performance**: Django bulk_create, Azure SQL batching studies (10k row benchmarks)
**Testing**: Hypothesis property-based testing, Django integration test patterns
**NetBox**: Bulk import patterns, cable creation API requirements

**Full references**: See `docs/DIET-GENERATION-PATTERNS.md`

---

## Next Steps

1. Review findings with team
2. Prioritize bulk_create migration (high impact, low risk)
3. Add 1,000 device scale test to CI
4. Document naming template restrictions
5. Plan incremental update feature (future sprint)

---

**Related Issues**: #106 (if applicable)
**Document**: `/docs/DIET-GENERATION-PATTERNS.md`
**Author**: Research Agent
**Date**: 2025-12-27
