# DIET Object Generation Patterns at Scale

**Research Report: Deterministic Generation of Thousands of NetBox Objects**

This document synthesizes patterns from Infrastructure as Code (IaC) tools, Kubernetes operators, and database performance research to guide DIET's generation engine design for creating 10,000+ NetBox objects (Devices, Interfaces, Cables) from compact planning specifications.

---

## Table of Contents

1. [Generation Engine Architecture](#1-generation-engine-architecture)
2. [Determinism & Idempotency Strategies](#2-determinism--idempotency-strategies)
3. [Relationship Management Patterns](#3-relationship-management-patterns)
4. [Performance Patterns for Scale](#4-performance-patterns-for-scale)
5. [Testing Approaches](#5-testing-approaches)
6. [Current DIET Implementation Analysis](#6-current-diet-implementation-analysis)
7. [Recommendations](#7-recommendations)
8. [References](#references)

---

## 1. Generation Engine Architecture

### 1.1 IaC Tool Patterns

#### Terraform: Count vs For_Each

**Terraform's Evolution** shows the importance of stable resource addressing:

- **`count`**: Creates resources with numeric indexing (0, 1, 2...). Problem: Removing item from middle causes recreation of all subsequent resources.
- **`for_each`** (recommended): Creates resources keyed by map/set keys. More stable when adding/removing resources at scale.

**Key Insight**: Use stable, semantic identifiers rather than positional indices for addressability.

**Example from Terraform**:
```hcl
# Bad: Positional indexing (count)
resource "aws_instance" "server" {
  count = var.server_quantity
  # server[0], server[1], server[2]...
  # Removing server[1] recreates server[2], server[3]...
}

# Good: Stable identifiers (for_each)
resource "aws_instance" "server" {
  for_each = var.servers  # { "gpu-01" = {...}, "gpu-02" = {...} }
  # server["gpu-01"], server["gpu-02"]
  # Removing gpu-01 doesn't affect gpu-02
}
```

#### Pulumi: Programmatic Generation

Pulumi's **Dynamic Resource Providers** demonstrate:
- Full control over CRUD lifecycle hooks
- Ability to loop programmatically (not template-based)
- Direct integration with external APIs
- Pattern: Resource provider manages state transitions

**DIET Application**: DeviceGenerator already follows this pattern - custom logic for CREATE/UPDATE/DELETE operations.

#### Kubernetes Operators: Reconciliation Loop

**Core Pattern**: Level-triggered reconciliation (focus on desired vs actual state)

Key principles from operator best practices:
1. **Idempotent reconciliation**: Same observed state → same outcome
2. **Eventual consistency**: Continuously reconcile until desired = actual
3. **State snapshots**: Track what was generated to detect drift
4. **Plan-scoped operations**: Each reconciliation targets specific resources

**DIET Application**: GenerationState model tracks plan snapshots for drift detection.

### 1.2 Recommended Architecture for DIET

**Three-Phase Generator Pattern**:

```
┌─────────────────────────────────────────────────┐
│ Phase 1: PLAN                                   │
│ - Calculate object counts                       │
│ - Validate port availability                    │
│ - Build generation spec (deterministic)         │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ Phase 2: GENERATE                               │
│ - Delete old objects (plan-scoped)              │
│ - Create devices (bulk)                         │
│ - Create interfaces (bulk)                      │
│ - Create cables (bulk)                          │
│ - Atomic transaction                            │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ Phase 3: RECONCILE                              │
│ - Save GenerationState snapshot                 │
│ - Tag generated objects                         │
│ - Validate referential integrity                │
└─────────────────────────────────────────────────┘
```

**Current DIET Implementation** already follows this pattern (see `DeviceGenerator.generate_all()`).

---

## 2. Determinism & Idempotency Strategies

### 2.1 Core Principles from IaC Research

> "Idempotence means: check before you proceed. Do no change if system is already in desired state."
> — [Idempotency in Infrastructure as Code](https://skundunotes.com/2019/04/19/idempotency-in-infrastructure-as-code/)

> "Just as the same source code always generates the same binary, an IaC model generates the same environment every time it deploys."
> — [Microsoft Learn: What is IaC?](https://learn.microsoft.com/en-us/devops/deliver/what-is-infrastructure-as-code)

### 2.2 Deterministic Naming Patterns

**Requirements for Deterministic Names**:
- No random components (GUIDs, timestamps)
- Derived from input parameters only
- Consistent ordering (sorted iteration)
- Stable across regeneration

**Azure/Bicep Pattern**:
```bicep
// Bad: Non-deterministic
resource vm 'Microsoft.Compute/virtualMachines' {
  name: 'vm-${uniqueString(newGuid())}'  // FAILS on re-deploy
}

// Good: Deterministic
resource vm 'Microsoft.Compute/virtualMachines' {
  name: 'vm-${location}-${environment}-${index:03d}'
}
```

**DIET Implementation**:
```python
# Current pattern in DeviceGenerator._render_device_name()
def _render_device_name(self, category, class_id, index, ...):
    template = self._get_naming_template(category)
    if template:
        context = {
            'site': self.site.slug,
            'class': class_id,
            'index': index,  # Deterministic: 1-based sequential
            ...
        }
        return template.render(context)

    # Fallback: deterministic slugification
    return f"{slugify(class_id)}-{index:03d}"
```

**Strength**: Template-based with fallback ensures determinism.
**Enhancement Opportunity**: Document that templates must avoid non-deterministic functions.

### 2.3 Change Detection & Drift

**Pattern: Snapshot-Based Comparison**

Kubernetes operators use resource versioning:
```yaml
metadata:
  resourceVersion: "12345"  # Changes on any update
```

**DIET Pattern**: GenerationState stores plan snapshot
```python
snapshot = {
    'server_classes': [
        {'server_class_id': 'gpu-b200', 'quantity': 96},
        ...
    ],
    'switch_classes': [
        {'switch_class_id': 'fe-leaf', 'effective_quantity': 4},
        ...
    ]
}

def is_dirty(self):
    current = self._build_current_snapshot()
    return current != self.snapshot
```

**Strength**: Detect when plan has changed since generation.
**Enhancement Opportunity**: Include connection definitions and port zones in snapshot.

### 2.4 Stable Identifiers Across Regenerations

**Challenge**: How to track "this Device represents Server #42 from PlanServerClass gpu-b200"?

**DIET Solution**: Custom field `hedgehog_plan_id` + naming convention
```python
device.custom_field_data = {
    'hedgehog_plan_id': str(self.plan.pk),
    'hedgehog_class': server_class.server_class_id,
}
```

**Query Pattern**:
```python
# Find all devices for this plan
Device.objects.filter(
    custom_field_data__hedgehog_plan_id=str(plan.pk)
)
```

**Strength**: Plan-scoped cleanup and regeneration.
**Enhancement Opportunity**: Add `hedgehog_instance_index` to track specific instances for partial updates.

---

## 3. Relationship Management Patterns

### 3.1 Dependency Ordering

**Graph of Dependencies** (simplified):
```
TopologyPlan
    ├── PlanServerClass (quantity=96)
    │   └── Device instances × 96
    │       └── Interface instances × (96 × ports_per_server)
    └── PlanSwitchClass (effective_quantity=4)
        └── Device instances × 4
            └── Interface instances × (4 × ports_per_switch)
                └── Cable instances (connect server ↔ switch)
```

**Creation Order** (current implementation):
1. Switch Devices (no dependencies)
2. Server Devices (no dependencies)
3. Interfaces + Cables (depend on Devices)

**Deletion Order** (reverse):
1. Cables FIRST (termination protection)
2. Devices (cascades to Interfaces)

**Key Pattern from NetBox**:
```python
# CRITICAL: Delete cables before devices
cables_to_delete.delete()  # Must happen first
devices_to_delete.delete() # Cascades to interfaces
```

### 3.2 Cross-Reference Integrity

**Challenge**: Cable endpoints reference specific Interface objects by ID.

**NetBox Cable API** (v3+):
```json
{
  "a_terminations": [
    {"object_type": "dcim.interface", "object_id": 12345}
  ],
  "b_terminations": [
    {"object_type": "dcim.interface", "object_id": 67890}
  ]
}
```

**DIET Pattern**: In-memory caching during generation
```python
self._device_cache: dict[str, Device] = {}
self._interface_cache: dict[tuple[int, str], Interface] = {}

# Create interface once, reuse reference
cache_key = (device.pk, interface_name)
if cache_key not in self._interface_cache:
    interface = Interface(...)
    interface.save()
    self._interface_cache[cache_key] = interface
```

**Strength**: Ensures referential integrity within transaction.
**Performance**: O(1) lookups, avoids redundant queries.

### 3.3 Handling Cascading Deletes

**Django Cascade Behavior**:
```python
# When a Device is deleted:
Device.objects.filter(pk=device_id).delete()
# → Automatically deletes related Interfaces (ForeignKey on_delete=CASCADE)
```

**NetBox Termination Protection**:
- Cannot delete Interface if it's a Cable termination
- Must delete Cable first, then Interface/Device

**DIET Pattern**: Cables deleted before devices in `_cleanup_generated_objects()`.

---

## 4. Performance Patterns for Scale

### 4.1 Bulk vs Individual Creation

**Django `bulk_create()` Pattern**:

```python
# Bad: Individual creates (96 DB round-trips for 96 servers)
for i in range(96):
    Device.objects.create(name=f"server-{i}", ...)

# Good: Bulk create (1 DB round-trip)
devices = [Device(name=f"server-{i}", ...) for i in range(96)]
Device.objects.bulk_create(devices)
```

**Performance Research**:
- Django bulk_create can be **10-100x faster** for large datasets
- Accepts `batch_size` parameter to chunk large inserts
- **Limitation**: Does not call `save()` signals or return primary keys (before Django 4.1)

**DIET Current Implementation**:
```python
# DeviceGenerator._create_switch_devices()
for switch_class in self.plan.switch_classes.all():
    for index in range(switch_class.effective_quantity):
        device = Device(...)
        device.save()  # Individual saves
        devices.append(device)
```

**Analysis**: Current approach uses individual saves. This works for 128-GPU case (164 devices), but **may become bottleneck at 10k+ scale**.

### 4.2 Optimal Batch Sizes

**Research from Database Performance Studies**:

| Use Case | Recommended Batch Size | Source |
|----------|------------------------|--------|
| Django/ORM | 500-1000 objects | [Django ORM Performance](https://theorangeone.net/posts/django-orm-performance/) |
| JDBC | 100-200 rows | [Bulk Insert Optimization](https://medium.com/@AlexanderObregon/bulk-insert-optimization-with-spring-boot-and-jdbc-batching-57dd031ecad8) |
| SQL Server | 10,000-500,000 rows | [Azure SQL Batching](https://learn.microsoft.com/en-us/azure/azure-sql/performance-improve-use-batching?view=azuresql) |

**Key Insight**: "For 10,000-row batches, Microsoft tests showed a small performance gain when breaking them into two batches of 5,000."

**DIET Recommendation**: Use batch_size=500 for bulk_create operations.

### 4.3 Transaction Management

**Pattern: Atomic Generation**

Current implementation:
```python
@transaction.atomic
def generate_all(self) -> GenerationResult:
    self._cleanup_generated_objects()
    devices = []
    # ... create devices
    # ... create interfaces
    # ... create cables
    return GenerationResult(...)
```

**Strength**: All-or-nothing semantics. If cable creation fails, entire generation rolls back.

**Trade-off**: Large transactions hold locks longer. For 10k+ objects, consider:
- Progress reporting (not possible in single transaction)
- Partial failure recovery (must retry entire generation)

**Alternative Pattern**: Multi-phase commits
```python
# Phase 1: Devices (can commit independently)
with transaction.atomic():
    create_devices()

# Phase 2: Interfaces (can commit independently)
with transaction.atomic():
    create_interfaces()

# Phase 3: Cables (depends on interfaces)
with transaction.atomic():
    create_cables()
```

**Trade-off**: More complex rollback logic, but better progress visibility.

### 4.4 Memory Management

**Challenge**: Building 10,000 objects in memory before bulk insert.

**Pattern: Chunked Generation**
```python
def generate_devices_chunked(self, server_class, chunk_size=500):
    for chunk_start in range(0, server_class.quantity, chunk_size):
        chunk_end = min(chunk_start + chunk_size, server_class.quantity)
        devices = [
            Device(name=self._render_name(i), ...)
            for i in range(chunk_start, chunk_end)
        ]
        Device.objects.bulk_create(devices, batch_size=500)
        devices.clear()  # Free memory
```

**Research**: "Tests showed that several smaller multithreaded batches typically performed worse than a single larger batch, due to network overhead."

**DIET Recommendation**: Single bulk_create per object type, with batch_size parameter.

### 4.5 Port Allocation State

**Current Pattern**: PortAllocatorV2 uses in-memory state
```python
self._sequences: dict[tuple[str, int], list[PortSlot]] = {}
self._cursors: dict[tuple[str, int], int] = {}
```

**Analysis**: Efficient for generation phase (O(1) allocations), but state is lost after generation.

**Enhancement Opportunity**: Persist allocation state for incremental updates
```python
# Store in custom field on Interface
interface.custom_field_data = {
    'hedgehog_zone': 'server-ports',
    'hedgehog_physical_port': 1,
    'hedgehog_breakout_index': 2,
    'hedgehog_allocation_cursor': 42,  # NEW: Track allocation order
}
```

---

## 5. Testing Approaches

### 5.1 Unit Testing Generation Logic

**Current DIET Tests**: `test_device_generator.py`
- Test naming template application
- Test breakout metadata
- Test default site/role creation

**Pattern**: Mock external dependencies, focus on logic
```python
def test_generate_creates_devices_interfaces_cables_and_state(self):
    generator = DeviceGenerator(self.plan)
    result = generator.generate_all()

    self.assertEqual(result.device_count, 3)
    self.assertEqual(result.interface_count, 4)
    self.assertEqual(result.cable_count, 2)
```

### 5.2 Integration Testing with Real Backend

**Current DIET Tests**: `test_generate_integration.py`
- Full UX flow (preview GET, generate POST)
- Permission enforcement
- Regeneration scenarios
- Plan-scoped deletion

**Pattern**: Real Django test database, no mocks
```python
def test_generate_post_creates_devices(self):
    url = reverse('plugins:netbox_hedgehog:topologyplan_generate', ...)
    response = self.client.post(url, follow=True)

    self.assertEqual(Device.objects.count(), 3)
    self.assertEqual(Cable.objects.count(), 2)
```

**Strength**: Tests actual NetBox object creation and relationships.

### 5.3 Property-Based Testing for Invariants

**Pattern from Hypothesis** (Python property-based testing):

```python
from hypothesis import given, strategies as st

@given(
    server_quantity=st.integers(min_value=1, max_value=1000),
    ports_per_server=st.integers(min_value=1, max_value=8),
)
def test_generation_invariants(server_quantity, ports_per_server):
    """Test that generation satisfies invariants for arbitrary inputs."""
    plan = create_plan(server_quantity, ports_per_server)
    generator = DeviceGenerator(plan)
    result = generator.generate_all()

    # INVARIANT: Device count equals input quantity
    assert result.device_count == server_quantity + switch_count

    # INVARIANT: Each cable connects exactly 2 interfaces
    for cable in Cable.objects.all():
        assert len(cable.a_terminations) == 1
        assert len(cable.b_terminations) == 1

    # INVARIANT: No orphaned interfaces
    assert Interface.objects.filter(cable__isnull=True).count() == 0
```

**Benefits**:
- Tests thousands of random scenarios
- Finds edge cases humans miss
- Validates assumptions hold at scale

**DIET Application**: Test generation with randomized server/switch quantities.

### 5.4 Scale Testing (Performance Benchmarks)

**Current DIET Scale Test**: 128-GPU case
- 164 devices, 1,096 interfaces, 548 cables
- Uses mocked generation (doesn't test actual creation performance)

**Enhanced Scale Test Pattern**:
```python
import time

def test_10k_device_generation_performance(self):
    """Benchmark 10,000 device generation."""
    # Create plan with 10k servers
    plan = create_large_plan(server_quantity=10000)

    start = time.time()
    generator = DeviceGenerator(plan)
    result = generator.generate_all()
    elapsed = time.time() - start

    # Performance assertion: Should complete in < 60 seconds
    self.assertLess(elapsed, 60.0)

    # Correctness assertion
    self.assertEqual(result.device_count, 10000 + switch_count)
```

**Metrics to Track**:
- Time to generate (seconds)
- Memory usage (MB)
- Database query count
- Transaction lock duration

### 5.5 Idempotency Testing

**Pattern**: Run generation twice, verify same outcome
```python
def test_regeneration_is_idempotent(self):
    """Test that regenerating unchanged plan produces same result."""
    generator = DeviceGenerator(self.plan)

    # First generation
    result1 = generator.generate_all()
    devices1 = set(Device.objects.values_list('name', flat=True))

    # Second generation (no plan changes)
    result2 = generator.generate_all()
    devices2 = set(Device.objects.values_list('name', flat=True))

    # INVARIANT: Same device names
    self.assertEqual(devices1, devices2)

    # INVARIANT: Same counts
    self.assertEqual(result1.device_count, result2.device_count)
```

**DIET Test**: `test_regeneration_deletes_old_objects()` in integration tests.

---

## 6. Current DIET Implementation Analysis

### 6.1 Strengths

✅ **Clean separation of concerns**:
- `DeviceGenerator`: Orchestrates generation
- `PortAllocatorV2`: Handles port allocation logic
- `NamingTemplate`: Customizable naming patterns

✅ **Deterministic naming**:
- Template-based with fallback
- No random/timestamp components

✅ **Plan-scoped operations**:
- Custom field `hedgehog_plan_id` tracks ownership
- Cleanup only affects current plan

✅ **Atomic transactions**:
- `@transaction.atomic` ensures consistency

✅ **Comprehensive integration tests**:
- Full UX flows tested
- Regeneration scenarios covered
- Permission enforcement validated

### 6.2 Opportunities for Scale (10k+ Objects)

⚠️ **Individual object saves** (not bulk):
```python
# Current pattern
device.save()  # 1 query per device
devices.append(device)
```
**Impact**: 10,000 devices = 10,000 INSERT queries
**Solution**: Use `bulk_create(devices, batch_size=500)`

⚠️ **Interface creation in cable loop**:
```python
# Current pattern: Create interfaces on-demand during cable creation
for connection in connections:
    interface = self._get_or_create_interface(...)
```
**Impact**: Interfaces created one-by-one
**Solution**: Separate interface generation phase with bulk_create

⚠️ **No progress reporting** (single transaction):
**Impact**: 10k+ generation appears frozen for minutes
**Solution**: Multi-phase commits with status updates (if needed for UX)

⚠️ **Limited snapshot scope**:
```python
# Current snapshot: Only server/switch quantities
snapshot = {
    'server_classes': [...],
    'switch_classes': [...]
}
```
**Impact**: Doesn't detect connection or port zone changes
**Solution**: Include connection definitions in snapshot

⚠️ **No incremental update support**:
**Impact**: Changing 1 server requires regenerating all 10,000 devices
**Solution**: Track instance indices, support partial updates (future enhancement)

### 6.3 Current Performance Estimates

**Assumptions**:
- Django `save()`: ~10ms per object (with validation)
- `bulk_create()`: ~1ms per object (amortized)
- Transaction overhead: ~100ms

**128-GPU Case** (current):
- 164 devices × 10ms = 1.64s
- 1,096 interfaces × 10ms = 10.96s
- 548 cables × 10ms = 5.48s
- **Total: ~18 seconds**

**10k Server Case** (projected):
- 10,000 servers + 40 switches = 10,040 devices
- 10,000 × 8 ports = 80,000 server interfaces
- 40 × 256 ports = 10,240 switch interfaces
- Total: 90,240 interfaces
- ~40,000 cables

**Individual saves**: 10,040×10ms + 90,240×10ms + 40,000×10ms = **1,402 seconds (23 minutes)**

**Bulk creates**: 10,040×1ms + 90,240×1ms + 40,000×1ms = **140 seconds (2.3 minutes)**

**Recommendation**: Migrate to bulk_create for 10x-100x speedup.

---

## 7. Recommendations

### 7.1 Immediate (Next PR)

1. **Migrate to bulk_create** for Devices and Interfaces:
   ```python
   # Before
   for i in range(quantity):
       device = Device(...)
       device.save()

   # After
   devices = [Device(...) for i in range(quantity)]
   Device.objects.bulk_create(devices, batch_size=500)
   ```

2. **Add scale test** for 1,000 devices:
   ```python
   def test_1000_device_generation(self):
       plan = create_plan_with_1000_servers()
       result = DeviceGenerator(plan).generate_all()
       self.assertEqual(result.device_count, 1000 + switch_count)
   ```

3. **Expand snapshot scope** to include connections:
   ```python
   snapshot['connections'] = [
       {
           'connection_id': conn.connection_id,
           'ports_per_connection': conn.ports_per_connection,
           'speed': conn.speed,
       }
       for conn in all_connections
   ]
   ```

### 7.2 Short-term (Future Sprints)

4. **Property-based testing** with Hypothesis:
   - Install: `pip install hypothesis`
   - Add test: `test_generation_invariants_property_based()`
   - Validate: Cable endpoints always reference valid interfaces

5. **Performance benchmarking**:
   - Track generation time in GenerationState
   - Add metrics: `generation_duration_seconds`
   - Log slow operations (>5 seconds)

6. **Naming pattern validation**:
   - Document: "Templates must not use random/timestamp functions"
   - Add validator: Check for `random.`, `time.`, `uuid.` in pattern strings

### 7.3 Long-term (Future Enhancements)

7. **Incremental updates** (partial regeneration):
   - Add `hedgehog_instance_index` to custom fields
   - Support: "Add 10 servers to existing 100" without full regeneration
   - Requires: Stable indexing and allocation cursor persistence

8. **Multi-phase progress reporting**:
   ```python
   # Commit devices first
   with transaction.atomic():
       devices = create_devices()
       update_state(status='devices_created', progress=33)

   # Commit interfaces
   with transaction.atomic():
       interfaces = create_interfaces()
       update_state(status='interfaces_created', progress=66)

   # Commit cables
   with transaction.atomic():
       cables = create_cables()
       update_state(status='completed', progress=100)
   ```

9. **Validation phase separation**:
   - Pre-validate before transaction (fail fast)
   - Check: Port availability, naming conflicts, circular dependencies
   - Generate: Detailed validation report

---

## References

### IaC and Generation Patterns

- [Terraform: Count vs For_Each](https://www.pulumi.com/docs/iac/comparisons/terraform/)
- [Pulumi: Dynamic Resource Providers](https://www.pulumi.com/blog/dynamic-providers/)
- [Pulumi: Dynamic Providers Documentation](https://www.pulumi.com/docs/iac/concepts/resources/dynamic-providers/)
- [Azure: Name Generation Pattern](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/patterns-name-generation)
- [Azure: Use Stable Resource Identifier](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/linter-rule-use-stable-resource-identifier)

### Idempotency and State Management

- [Microsoft: What is Infrastructure as Code?](https://learn.microsoft.com/en-us/devops/deliver/what-is-infrastructure-as-code)
- [Idempotency in Infrastructure as Code](https://skundunotes.com/2019/04/19/idempotency-in-infrastructure-as-code/)
- [Kubernetes: Good Practices (Kubebuilder)](https://book.kubebuilder.io/reference/good-practices)
- [Kubernetes Operators 101: How Operators Work](https://developers.redhat.com/articles/2021/06/22/kubernetes-operators-101-part-2-how-operators-work)
- [Kubernetes Reconciliation Patterns](https://hkassaei.com/posts/kubernetes-and-reconciliation-patterns/)
- [State-Drift: Build Self-Healing Kubernetes Controllers](https://blog.anynines.com/external-state-drift-kubernetes-controller-self-healing-design/)

### Performance and Batching

- [Django ORM Performance](https://theorangeone.net/posts/django-orm-performance/)
- [Django: Database Optimization](https://docs.djangoproject.com/en/4.1/topics/db/optimization/)
- [How to Use Django Bulk Inserts](https://www.caktusgroup.com/blog/2019/01/09/django-bulk-inserts/)
- [Azure SQL: Use Batching to Improve Performance](https://learn.microsoft.com/en-us/azure/azure-sql/performance-improve-use-batching?view=azuresql)
- [Bulk Insert Optimization with Spring Boot and JDBC](https://medium.com/@AlexanderObregon/bulk-insert-optimization-with-spring-boot-and-jdbc-batching-57dd031ecad8)

### NetBox Integration

- [NetBox: Populating Data](https://netboxlabs.com/docs/netbox/getting-started/populating-data/)
- [NetBox: Bulk Import Interface Discussion](https://groups.google.com/g/netbox-discuss/c/efYuVqFmGKo)
- [NetBox: Cable Creation via API](https://github.com/netbox-community/pynetbox/discussions/673)

### Property-Based Testing

- [Hypothesis: Property-Based Testing for Python](https://github.com/HypothesisWorks/hypothesis)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [How to Use Hypothesis and Pytest](https://pytest-with-eric.com/pytest-advanced/hypothesis-testing-python/)
- [Property-Based Testing: Generative Testing for System Invariants](https://yrkan.com/blog/property-based-testing/)
- [An Empirical Evaluation of Property-Based Testing in Python (2025)](https://cseweb.ucsd.edu/~mcoblenz/assets/pdf/OOPSLA_2025_PBT.pdf)

---

## Appendix: Code Examples

### A. Bulk Create Pattern for DIET

```python
# File: netbox_hedgehog/services/device_generator.py

def _create_switch_devices_bulk(self, devices: list[Device]) -> dict[str, Device]:
    """Create switch devices using bulk_create for performance."""
    switch_devices: dict[str, Device] = {}
    devices_to_create = []

    for switch_class in self.plan.switch_classes.all():
        switch_role = self._resolve_switch_category(switch_class.hedgehog_role)
        role = self._ensure_role(switch_role)

        for index in range(switch_class.effective_quantity):
            name = self._render_device_name(
                category=switch_role,
                class_id=switch_class.switch_class_id,
                index=index + 1,
                fabric=switch_class.fabric or "",
                role=switch_class.hedgehog_role or "",
            )
            device = Device(
                name=name,
                device_type=switch_class.device_type_extension.device_type,
                role=role,
                site=self.site,
                status=DeviceStatusChoices.STATUS_PLANNED,
            )
            device.custom_field_data = {
                'hedgehog_plan_id': str(self.plan.pk),
                'hedgehog_class': switch_class.switch_class_id,
                'hedgehog_fabric': switch_class.fabric or "",
                'hedgehog_role': switch_class.hedgehog_role or "",
            }
            devices_to_create.append(device)
            switch_devices[name] = device  # Store reference

    # Bulk create with batch_size
    Device.objects.bulk_create(devices_to_create, batch_size=500)

    # Update devices list and cache
    devices.extend(devices_to_create)
    for device in devices_to_create:
        self._device_cache[device.name] = device

    return switch_devices
```

### B. Property-Based Test Example

```python
# File: netbox_hedgehog/tests/test_topology_planning/test_generation_properties.py

from hypothesis import given, strategies as st
from django.test import TestCase

class GenerationPropertyTests(TestCase):
    """Property-based tests for generation invariants."""

    @given(
        server_quantity=st.integers(min_value=1, max_value=100),
        switch_quantity=st.integers(min_value=1, max_value=10),
        ports_per_connection=st.integers(min_value=1, max_value=4),
    )
    def test_cable_count_invariant(self, server_quantity, switch_quantity, ports_per_connection):
        """Test that cable count equals servers × ports_per_connection."""
        plan = self._create_plan(server_quantity, switch_quantity, ports_per_connection)
        result = DeviceGenerator(plan).generate_all()

        expected_cables = server_quantity * ports_per_connection
        self.assertEqual(result.cable_count, expected_cables)

    @given(server_quantity=st.integers(min_value=1, max_value=100))
    def test_device_names_unique(self, server_quantity):
        """Test that all generated device names are unique."""
        plan = self._create_plan(server_quantity)
        DeviceGenerator(plan).generate_all()

        device_names = Device.objects.values_list('name', flat=True)
        self.assertEqual(len(device_names), len(set(device_names)),
                        "All device names must be unique")
```

---

**Document Version**: 1.0
**Last Updated**: 2025-12-27
**Author**: AI Research Agent for DIET Project
