# NetBox Plugin Best Practices Research Summary for DIET Architecture

**Issue:** #114 - DIET Architecture Alignment
**Research Date:** 2025-12-27
**Full Guide:** See `NETBOX_PLUGIN_BEST_PRACTICES.md` for complete analysis

---

## Executive Summary

**Good News:** Your DIET architecture is already following most NetBox plugin best practices! The core approach of maintaining separate planning models that reference (not duplicate) core NetBox models is exactly right.

**Overall Assessment: 8.5/10**

**Main Gap:** Missing validation phase and generated object tracking between plans and created NetBox objects.

---

## What You're Already Doing Right ✅

1. **Proper Core Model References**
   - Using ForeignKey to `DeviceType` and `ModuleType` instead of duplicating hardware specs
   - Prevents data duplication and maintains single source of truth

2. **Extension Pattern for Metadata**
   - `DeviceTypeExtension` with OneToOneField to add Hedgehog-specific fields
   - Follows exact pattern used by mature plugins like netbox-lifecycle

3. **Separate Planning Schema**
   - TopologyPlan/PlanServerClass/PlanSwitchClass kept separate from operational inventory
   - Matches pattern from ntc-netbox-plugin-onboarding
   - Allows messy/incomplete plans without polluting production data

4. **Clean Model Organization**
   - Well-separated by concern (plans, reference_data, generation, naming)
   - Each model has clear responsibility

5. **Calculated + Override Pattern**
   - `calculated_quantity` (system-computed) + `override_quantity` (user control)
   - Good UX pattern for system recommendations with user override

---

## Key Findings from Ecosystem Research

### Studied Plugins

1. **netbox-inventory** (ArnesSI/netbox-inventory)
   - Asset tracking for hardware (installed + stored)
   - Uses status-driven logic with automatic transitions
   - Creates Asset model that *relates to* Device, doesn't replace it
   - Pattern: Separate lifecycle state from core inventory

2. **netbox-lifecycle** (DanSheps/netbox-lifecycle)
   - Tracks EOL/EOS, licenses, contracts
   - Extension pattern via ForeignKeys to DeviceType/ModuleType
   - Card-based UI integration (doesn't replace core views)
   - Pattern: Non-invasive metadata attachment

3. **ntc-netbox-plugin-onboarding** (Network to Code)
   - Device discovery → validation → creation workflow
   - Staged approach: plan/validate before materializing objects
   - Conditional creation flags (create_platform_if_missing, etc.)
   - Pattern: Staging objects before production creation

### Core NetBox Philosophy

**NetBox represents intended/designed state, not operational state.**

> "NetBox intends to represent the desired state of a network versus its operational state. As such, automated import of live network state is strongly discouraged. All data created in NetBox should first be vetted by a human to ensure its integrity."

**Implication for DIET:** Your design-time → deployment workflow is exactly aligned with NetBox's philosophy.

---

## Critical Best Practices

### CustomField vs Plugin Model Decision Tree

**Use CustomFields when:**
- Simple data types (string, int, boolean)
- User-configurable per-deployment
- No complex relationships
- No database constraints needed

**Use Plugin Models when:** (Your approach)
- Complex relationships (ForeignKey, ManyToMany)
- Structured data with business logic
- Workflow state requiring atomicity
- Data owned/managed by plugin

**Use Extension Pattern when:** (Your DeviceTypeExtension)
- Adding metadata to existing NetBox models
- Optional data (not all objects need it)
- Plugin-specific fields not generally applicable

### ForeignKey Best Practices

```python
# ✅ CORRECT (your current code)
server_device_type = models.ForeignKey(
    DeviceType,                          # Core model reference
    on_delete=models.PROTECT,            # Prevent deletion if in use
    related_name='plan_server_classes',  # Explicit, unlikely to conflict
)

# Reference core models by string to reduce coupling
target = models.ForeignKey(
    'dcim.Device',  # String reference, don't import
    ...
)
```

**Cascade Behavior:**
- `CASCADE`: Plugin owns child (plan → server_classes) ✅
- `PROTECT`: Reference to core model (server_class → DeviceType) ✅
- `SET_NULL`: Optional/user ownership (plan → created_by) ✅

### Performance Patterns

**From NetBox Core Optimization Research:**

```python
# ❌ N+1 queries
for server_class in PlanServerClass.objects.all():
    print(server_class.server_device_type.manufacturer.name)
    # Queries database every iteration!

# ✅ Optimized with select_related
for server_class in PlanServerClass.objects.select_related(
    'server_device_type__manufacturer'
):
    print(server_class.server_device_type.manufacturer.name)
    # All data in one query

# ✅ Bulk operations for generation
Device.objects.bulk_create(devices, batch_size=100)
```

---

## Recommended Enhancements

### High Priority

**1. Add Pre-Generation Validation**

Problem: Currently can attempt generation without validating plan completeness.

```python
class TopologyPlan(NetBoxModel):
    validation_errors = models.JSONField(default=list, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)

    def validate_for_generation(self):
        """Pre-flight checks before creating NetBox objects"""
        errors = []

        # Check required relationships
        if not self.switch_classes.exists():
            errors.append("Plan must have at least one switch class")

        # Check for zero quantities
        for switch_class in self.switch_classes.all():
            if switch_class.effective_quantity == 0:
                errors.append(
                    f"{switch_class.switch_class_id} has zero quantity"
                )

        # Check for naming conflicts with existing NetBox objects
        # ...

        self.validation_errors = errors
        if not errors:
            self.validated_at = timezone.now()
        self.save()

        return len(errors) == 0
```

**Benefit:** Catch errors before generation, show clear feedback to users.

**2. Track Generated Objects**

Problem: No link between TopologyPlan and the NetBox objects it created.

```python
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class GeneratedObject(NetBoxModel):
    """Track which NetBox objects were generated from which plan"""

    plan = models.ForeignKey(
        TopologyPlan,
        on_delete=models.CASCADE,
        related_name='generated_objects'
    )

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    object = GenericForeignKey('content_type', 'object_id')

    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['plan', 'content_type', 'object_id']]
```

**Benefits:**
- Show "What was created" in plan detail view
- Prevent duplicate generation
- Enable cleanup/rollback
- Audit trail

**3. Enhance Status Workflow**

Current: draft, in-review, approved, deployed, archived

Recommended addition:

```python
class TopologyPlanStatusChoices(ChoiceSet):
    STATUS_DRAFT = 'draft'
    STATUS_VALIDATED = 'validated'      # NEW: Passed validation
    STATUS_APPROVED = 'approved'
    STATUS_GENERATED = 'generated'      # NEW: NetBox objects created
    STATUS_DEPLOYED = 'deployed'
    STATUS_ARCHIVED = 'archived'
```

**Workflow:**
1. Draft → Validated (validation checks pass)
2. Validated → Approved (manager approves)
3. Approved → Generated (NetBox objects created)
4. Generated → Deployed (actually deployed to hardware)

**4. Optimize Generation Performance**

Current concern: Generating 128-GPU clusters creates thousands of objects.

```python
class BulkDeviceGenerator:
    """Optimize NetBox object generation with bulk operations"""

    def __init__(self, plan):
        self.plan = plan
        self.devices_to_create = []
        self.interfaces_to_create = []

    def add_device(self, **kwargs):
        self.devices_to_create.append(Device(**kwargs))

    def add_interface(self, **kwargs):
        self.interfaces_to_create.append(Interface(**kwargs))

    def commit(self):
        """Bulk create all queued objects"""
        with transaction.atomic():
            Device.objects.bulk_create(
                self.devices_to_create,
                batch_size=100
            )
            Interface.objects.bulk_create(
                self.interfaces_to_create,
                batch_size=500
            )

        return {
            'devices_created': len(self.devices_to_create),
            'interfaces_created': len(self.interfaces_to_create),
        }
```

**Benefits:**
- 10-100x faster for large plans
- Reduced database load
- Atomic operation (all or nothing)

### Medium Priority

**5. Add Calculation Metadata**

Track *when* and *how* calculations were performed:

```python
class PlanSwitchClass(NetBoxModel):
    # ... existing fields ...

    calculation_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadata about calculation"
    )

    def update_calculation(self, quantity, algorithm_version, inputs):
        """Update calculated quantity with metadata"""
        self.calculated_quantity = quantity
        self.calculation_metadata = {
            'algorithm_version': algorithm_version,
            'calculated_at': timezone.now().isoformat(),
            'inputs_hash': hashlib.sha256(
                json.dumps(inputs, sort_keys=True).encode()
            ).hexdigest(),
            'inputs': inputs,
        }
        self.save()
```

**Benefits:**
- Detect stale calculations
- Debug calculation issues
- Track algorithm version for migrations

**6. Improve Error Handling in Generation**

- Comprehensive validation before generation
- Transaction rollback on failure
- Clear error messages for users
- Structured logging for debugging

**7. Consider Plan Versioning**

- Save plan snapshots before major changes
- Compare plan versions
- Revert to previous versions
- Track changes over time (like git for plans)

### Low Priority / Future

**8. Integration with NetBox Branching**
- NetBox Labs has a branching feature (git-like)
- Could use for design variations
- May be overkill for current needs

**9. Export/Import Plans**
- Export plans as JSON/YAML
- Import from templates
- Share between NetBox instances
- Version control in git

**10. Visualization**
- Generate topology diagrams
- Show port allocation visually
- Preview before generation
- Integration with netbox-topology-views

---

## Common Anti-Patterns (You're Avoiding)

### ❌ Things You're NOT Doing (Good!)

1. **NOT duplicating core models** ✅
   - You reference DeviceType, don't recreate it
   - Follows single source of truth principle

2. **NOT polluting operational inventory** ✅
   - Plans are separate from actual Devices
   - Can delete plans without affecting production

3. **NOT modifying core NetBox models** ✅
   - Using extension pattern instead
   - Maintains plugin isolation

4. **NOT using underscores in model names** ✅
   - TopologyPlan (not Topology_Plan)
   - Prevents permission errors

5. **NOT bypassing NetBox generic views** ✅
   - Using ObjectListView, ObjectEditView, etc.
   - Leverages NetBox's built-in features

---

## Design-Time vs Runtime: Your Approach is Correct

**NetBox's Philosophy:**
- NetBox = intended/designed state (what you want)
- Discovery tools = operational state (what exists)
- Assurance tools = drift detection (differences)

**Your DIET Workflow:**
1. Design in DIET (TopologyPlan)
2. Validate plan
3. Generate NetBox objects (intended state)
4. Deploy to hardware
5. (Future) Discover actual state
6. (Future) Compare and remediate drift

**This matches NetBox's intended use exactly.**

**Alternative (Wrong for DIET):**
- Put everything in NetBox with status='planned'
- Problem: Pollutes production inventory
- Problem: Hard to clean up abandoned plans
- Problem: Risk of accidental deployment

**Your separation is the right pattern.**

---

## Compatibility and Coupling

### Avoiding Tight Coupling

**Critical Rule from NetBox Docs:**
> "Any part of the NetBox code base not documented is not part of the supported plugins API and should not be employed by a plugin."

**Safe to Use:**
- `netbox.models.NetBoxModel` ✅
- `dcim.models.*` for reading/ForeignKey ✅
- `netbox.views.generic.*` ✅
- `netbox.tables.*` ✅
- Standard Django patterns ✅

**Risky/Unsupported:**
- Monkey-patching NetBox classes ❌
- Undocumented internal APIs ❌
- Modifying core models ❌
- Direct database queries bypassing ORM ❌

**Your Code Review:** ✅ Using only documented APIs

### Version Compatibility

**NetBox v4.0 Migration Lessons:**
- Breaking changes happen in major versions
- Import paths can change
- Generic view APIs evolve
- Pin version requirements in pyproject.toml

**Recommendation:**
```toml
[tool.poetry.dependencies]
netbox = ">=4.1.0,<5.0.0"  # Allow minor updates, block major
```

---

## Namespace and Conflict Avoidance

### related_name Best Practices

**Your Current Code:**
```python
# ✅ GOOD: Descriptive, unlikely to conflict
server_device_type = models.ForeignKey(
    DeviceType,
    related_name='plan_server_classes',
)
```

**Alternative for Extra Safety:**
```python
# Also valid: Plugin-prefixed
server_device_type = models.ForeignKey(
    DeviceType,
    related_name='hedgehog_plan_servers',  # Plugin prefix
)

# Also valid: Suppress reverse (if not needed)
server_device_type = models.ForeignKey(
    DeviceType,
    related_name='+',  # No reverse relationship
)
```

**Conflict Example (Avoid):**
```python
# ❌ Multiple plugins doing this = conflict
device = models.ForeignKey(
    'dcim.Device',
    related_name='configs',  # Too generic!
)
```

---

## Specific DIET Implementation Checklist

### Already Implemented ✅
- [x] Reference DeviceType/ModuleType instead of duplicating
- [x] DeviceTypeExtension for Hedgehog metadata
- [x] Separate planning schema (TopologyPlan, etc.)
- [x] Calculated vs override quantities
- [x] Status workflow (draft → approved → deployed)
- [x] Clean model organization
- [x] Proper ForeignKey cascade behavior
- [x] Generation state tracking

### Recommended Additions
- [ ] Pre-generation validation method
- [ ] Validation errors storage in model
- [ ] GeneratedObject tracking model
- [ ] Enhanced status workflow (add 'validated', 'generated')
- [ ] Bulk operation optimization in generation
- [ ] Calculation metadata tracking
- [ ] Transaction handling in generation
- [ ] Plan versioning/snapshots (optional)

### Quick Wins

**1. Add Validation (1-2 hours):**
```python
# In topology_plans.py
def validate_for_generation(self):
    errors = []
    # Add checks
    self.validation_errors = errors
    return len(errors) == 0
```

**2. Track Generated Objects (2-3 hours):**
```python
# New model in generation.py
class GeneratedObject(NetBoxModel):
    plan = ForeignKey(TopologyPlan)
    content_type = ForeignKey(ContentType)
    object_id = PositiveIntegerField()
    # ...
```

**3. Optimize Bulk Creation (2-4 hours):**
```python
# In generation logic
devices = [Device(...) for ...]
Device.objects.bulk_create(devices, batch_size=100)
```

---

## Summary: You're on the Right Track

### Strengths
1. **Architecture is sound** - Proper separation, referencing not duplicating
2. **Following NetBox patterns** - Extension model, status workflow
3. **Good model design** - Clear responsibilities, proper relationships
4. **Performance-aware** - Already thinking about bulk operations

### Gaps (Minor)
1. **Validation phase** - Could be more explicit/enforced
2. **Object tracking** - Missing link between plan and generated objects
3. **Optimization** - Could use bulk operations for large plans
4. **Metadata** - Could track more about calculations

### Next Steps
1. Review full guide: `NETBOX_PLUGIN_BEST_PRACTICES.md`
2. Implement validation method (quick win)
3. Add GeneratedObject model (medium effort)
4. Optimize generation with bulk operations (medium effort)
5. Consider status workflow enhancements (low priority)

### Questions to Consider
1. Do you need plan versioning/snapshots?
2. Should plans be immutable after generation?
3. Do you need to support regeneration (update existing objects)?
4. Should there be approval workflow before generation?
5. Do you need role-based permissions (who can generate vs who can plan)?

---

## Research Sources

### Plugins Analyzed
- [netbox-inventory](https://github.com/ArnesSI/netbox-inventory) - Asset tracking patterns
- [netbox-lifecycle](https://github.com/DanSheps/netbox-lifecycle) - Metadata extension patterns
- [ntc-netbox-plugin-onboarding](https://github.com/networktocode/ntc-netbox-plugin-onboarding) - Workflow patterns
- [netbox-plugin-tutorial](https://github.com/netbox-community/netbox-plugin-tutorial) - Official guidance

### Documentation Reviewed
- NetBox Plugin Development Documentation
- NetBox Database Models Documentation
- NetBox v4.0 Migration Guide
- Community discussions on plugin architecture
- NetBox philosophy on design vs operational state

### Key Articles
- [Announcing NetBox Discovery: Bridge Infrastructure Design With Operational Reality](https://netboxlabs.com/blog/announcing-netbox-discovery-infrastructure-design-operational-reality/)
- [Navigating Network Automation with NetBox - Build and Deploy Stages](https://netboxlabs.com/blog/network-automation-with-netbox-build-and-deploy/)
- [The Design Stage: Navigating Network Automation Architecture](https://netboxlabs.com/blog/navigating-network-automation-with-netbox-the-design-stage/)

**Full research with all sources:** See `NETBOX_PLUGIN_BEST_PRACTICES.md`

---

## Conclusion

Your DIET architecture is well-designed and follows NetBox best practices. The main enhancements would be adding explicit validation, tracking generated objects, and optimizing bulk operations. These are evolutionary improvements to an already solid foundation, not fundamental restructuring.

**Recommendation:** Proceed with current architecture, add recommended enhancements incrementally as needed.
