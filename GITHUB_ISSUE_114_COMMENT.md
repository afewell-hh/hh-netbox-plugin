## NetBox Plugin Best Practices Research - DIET Architecture Alignment

### Executive Summary

**Good news!** The DIET architecture is already following most NetBox plugin best practices. Your approach of maintaining separate planning models that reference (not duplicate) core NetBox models is exactly right.

**Overall Assessment: 8.5/10**

**Main Gap:** Missing validation phase and tracking of generated NetBox objects.

---

### What You're Already Doing Right ✅

1. **Proper Core Model References** - Using ForeignKey to `DeviceType` and `ModuleType` instead of duplicating hardware specs
2. **Extension Pattern for Metadata** - `DeviceTypeExtension` with OneToOneField adds Hedgehog-specific fields without modifying core
3. **Separate Planning Schema** - TopologyPlan/PlanServerClass kept separate from operational inventory (matches ntc-netbox-plugin-onboarding pattern)
4. **Clean Model Organization** - Well-separated by concern (plans, reference_data, generation, naming)
5. **Calculated + Override Pattern** - Good UX for system recommendations with user control

---

### Key Findings from Ecosystem Research

Analyzed 3 mature NetBox plugins:

#### 1. netbox-inventory (ArnesSI/netbox-inventory)
**Pattern:** Asset model *relates to* Device/Module, doesn't replace them
- Status-driven logic with automatic state transitions
- Tracks lifecycle (stored → assigned → deployed) separate from core inventory
- **Lesson:** Separate lifecycle state from core objects

#### 2. netbox-lifecycle (DanSheps/netbox-lifecycle)
**Pattern:** Non-invasive metadata attachment
- ForeignKeys to DeviceType/ModuleType for EOL/EOS data
- Card-based UI integration (doesn't replace core views)
- **Lesson:** Extension pattern for metadata NetBox doesn't track

#### 3. ntc-netbox-plugin-onboarding (Network to Code)
**Pattern:** Staged discovery → validation → creation workflow
- Plans/validates before materializing NetBox objects
- Conditional creation flags (create_platform_if_missing, etc.)
- Asynchronous background processing
- **Lesson:** Explicit validation phase before object creation

---

### NetBox's Core Philosophy Confirms Your Approach

> "NetBox intends to represent the desired state of a network versus its operational state. As such, automated import of live network state is strongly discouraged. All data created in NetBox should first be vetted by a human to ensure its integrity."

**Your DIET workflow matches this perfectly:**
1. Design in DIET (TopologyPlan) - design-time state
2. Validate plan
3. Generate NetBox objects - intended state
4. Deploy to hardware
5. (Future) Discover actual state and remediate drift

**Alternative approach (wrong for DIET):**
- Put everything in NetBox with `status='planned'`
- Problems: Pollutes production inventory, hard to clean up, accidental deployment risk

**Your separation is the correct pattern.**

---

### Recommended Enhancements

#### High Priority

**1. Add Pre-Generation Validation**

```python
class TopologyPlan(NetBoxModel):
    validation_errors = models.JSONField(default=list, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)

    def validate_for_generation(self):
        """Pre-flight checks before creating NetBox objects"""
        errors = []

        if not self.switch_classes.exists():
            errors.append("Plan must have at least one switch class")

        for switch_class in self.switch_classes.all():
            if switch_class.effective_quantity == 0:
                errors.append(f"{switch_class.switch_class_id} has zero quantity")

        self.validation_errors = errors
        if not errors:
            self.validated_at = timezone.now()
        self.save()

        return len(errors) == 0
```

**Benefit:** Catch errors before generation, clear user feedback

**2. Track Generated Objects**

```python
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class GeneratedObject(NetBoxModel):
    """Track which NetBox objects were generated from which plan"""
    plan = models.ForeignKey(TopologyPlan, on_delete=models.CASCADE, related_name='generated_objects')
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

```python
class TopologyPlanStatusChoices(ChoiceSet):
    STATUS_DRAFT = 'draft'
    STATUS_VALIDATED = 'validated'      # NEW: Passed validation
    STATUS_APPROVED = 'approved'
    STATUS_GENERATED = 'generated'      # NEW: NetBox objects created
    STATUS_DEPLOYED = 'deployed'
    STATUS_ARCHIVED = 'archived'
```

**Workflow:** Draft → Validated → Approved → Generated → Deployed

**4. Optimize Generation Performance**

For large plans (128-GPU clusters), use bulk operations:

```python
class BulkDeviceGenerator:
    """Optimize NetBox object generation"""
    def __init__(self, plan):
        self.plan = plan
        self.devices_to_create = []
        self.interfaces_to_create = []

    def add_device(self, **kwargs):
        self.devices_to_create.append(Device(**kwargs))

    def add_interface(self, **kwargs):
        self.interfaces_to_create.append(Interface(**kwargs))

    def commit(self):
        with transaction.atomic():
            Device.objects.bulk_create(self.devices_to_create, batch_size=100)
            Interface.objects.bulk_create(self.interfaces_to_create, batch_size=500)
        return {
            'devices_created': len(self.devices_to_create),
            'interfaces_created': len(self.interfaces_to_create),
        }
```

**Benefit:** 10-100x faster for large topologies

---

#### Medium Priority

**5. Add Calculation Metadata**

Track *when* and *how* calculations were performed:

```python
class PlanSwitchClass(NetBoxModel):
    calculation_metadata = models.JSONField(default=dict, blank=True)

    def update_calculation(self, quantity, algorithm_version, inputs):
        self.calculated_quantity = quantity
        self.calculation_metadata = {
            'algorithm_version': algorithm_version,
            'calculated_at': timezone.now().isoformat(),
            'inputs_hash': hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
            'inputs': inputs,
        }
        self.save()
```

**6. Improve Error Handling**
- Transaction rollback on generation failure
- Structured logging
- Clear error messages

**7. Consider Plan Versioning**
- Save snapshots before major changes
- Compare versions
- Revert capability

---

### Critical Best Practices Summary

#### CustomField vs Plugin Model vs Extension

**Use CustomFields when:**
- Simple data types
- User-configurable per-deployment
- No complex relationships

**Use Plugin Models when:** *(Your approach)*
- Complex relationships (ForeignKey, ManyToMany)
- Workflow state
- Business logic
- Plugin-owned data

**Use Extension Pattern when:** *(Your DeviceTypeExtension)*
- Adding metadata to existing NetBox models
- Optional data
- Plugin-specific fields

#### ForeignKey Best Practices

```python
# ✅ CORRECT (your current code)
server_device_type = models.ForeignKey(
    DeviceType,                          # Core model reference
    on_delete=models.PROTECT,            # Prevent deletion if in use
    related_name='plan_server_classes',  # Explicit, unlikely to conflict
)

# ✅ Also good: String reference to reduce coupling
target = models.ForeignKey(
    'dcim.Device',  # String reference, don't import
    on_delete=models.PROTECT,
    related_name='hedgehog_connections',  # Plugin-prefixed to avoid conflicts
)
```

**Cascade Behavior:**
- `CASCADE`: Plugin owns child (plan → server_classes) ✅
- `PROTECT`: Reference to core model (server_class → DeviceType) ✅
- `SET_NULL`: Optional/user ownership (plan → created_by) ✅

#### Performance Patterns

```python
# ❌ N+1 queries
for server_class in PlanServerClass.objects.all():
    print(server_class.server_device_type.manufacturer.name)  # Queries every iteration!

# ✅ Optimized
for server_class in PlanServerClass.objects.select_related('server_device_type__manufacturer'):
    print(server_class.server_device_type.manufacturer.name)  # One query

# ✅ Bulk operations
Device.objects.bulk_create(devices, batch_size=100)
```

---

### Common Anti-Patterns (You're Avoiding) ✅

1. **NOT duplicating core models** - You reference DeviceType, don't recreate it
2. **NOT polluting operational inventory** - Plans separate from actual Devices
3. **NOT modifying core NetBox models** - Using extension pattern
4. **NOT using underscores in model names** - TopologyPlan (not Topology_Plan)
5. **NOT bypassing NetBox generic views** - Using ObjectListView, etc.

---

### Compatibility and Versioning

**Critical Rule from NetBox Docs:**
> "Any part of the NetBox code base not documented is not part of the supported plugins API and should not be employed by a plugin."

**Safe to Use:** ✅
- `netbox.models.NetBoxModel`
- `dcim.models.*` for reading/ForeignKey
- `netbox.views.generic.*`
- Standard Django patterns

**Your Code Review:** ✅ Using only documented APIs

**Recommendation for pyproject.toml:**
```toml
[tool.poetry.dependencies]
netbox = ">=4.1.0,<5.0.0"  # Allow minor updates, block major breaking changes
```

---

### Implementation Checklist

#### Already Implemented ✅
- [x] Reference DeviceType/ModuleType instead of duplicating
- [x] DeviceTypeExtension for Hedgehog metadata
- [x] Separate planning schema
- [x] Calculated vs override quantities
- [x] Status workflow
- [x] Clean model organization
- [x] Proper ForeignKey cascade behavior
- [x] Generation state tracking

#### Recommended Additions
- [ ] Pre-generation validation method
- [ ] Validation errors storage
- [ ] GeneratedObject tracking model
- [ ] Enhanced status workflow (add 'validated', 'generated')
- [ ] Bulk operation optimization
- [ ] Calculation metadata tracking
- [ ] Transaction handling in generation
- [ ] Plan versioning (optional)

---

### Quick Wins

**1. Add Validation (1-2 hours):**
```python
def validate_for_generation(self):
    errors = []
    # Add checks
    self.validation_errors = errors
    return len(errors) == 0
```

**2. Track Generated Objects (2-3 hours):**
- Add GeneratedObject model
- Update generation logic to create tracking records

**3. Optimize Bulk Creation (2-4 hours):**
- Implement BulkDeviceGenerator
- Update generation to use bulk_create

---

### Supporting Documentation

Created two detailed guides:
1. **NETBOX_PLUGIN_BEST_PRACTICES.md** - Comprehensive 200+ line analysis with all research sources
2. **DIET_ARCHITECTURE_RESEARCH_SUMMARY.md** - Executive summary with implementation details

Both files include:
- Detailed plugin analysis (netbox-inventory, netbox-lifecycle, ntc-onboarding)
- Extension patterns (CustomField vs Model vs Extension)
- Design-time vs runtime best practices
- Data model principles (referencing vs duplicating)
- Performance optimization patterns
- Anti-patterns to avoid
- Migration strategies
- Full source citations

---

### Research Sources

**Plugins Analyzed:**
- [netbox-inventory](https://github.com/ArnesSI/netbox-inventory) - Asset tracking patterns
- [netbox-lifecycle](https://github.com/DanSheps/netbox-lifecycle) - Metadata extension
- [ntc-netbox-plugin-onboarding](https://github.com/networktocode/ntc-netbox-plugin-onboarding) - Workflow patterns

**Official Documentation:**
- [NetBox Plugin Development](https://netboxlabs.com/docs/netbox/plugins/development/)
- [Database Models](https://netboxlabs.com/docs/netbox/development/models/)
- [Migrating to v4.0](https://netboxlabs.com/docs/netbox/plugins/development/migration-v4/)
- [Plugin Tutorial](https://github.com/netbox-community/netbox-plugin-tutorial)

**Key Articles:**
- [NetBox Discovery: Bridge Design With Operational Reality](https://netboxlabs.com/blog/announcing-netbox-discovery-infrastructure-design-operational-reality/)
- [Network Automation - Build and Deploy Stages](https://netboxlabs.com/blog/network-automation-with-netbox-build-and-deploy/)
- [Design Stage Navigation](https://netboxlabs.com/blog/navigating-network-automation-with-netbox-the-design-stage/)

**Community Resources:**
- [Awesome NetBox](https://github.com/netbox-community/awesome-netbox)
- [NetBox Discussions](https://github.com/netbox-community/netbox/discussions)
- Multiple GitHub issues on plugin architecture, performance, and compatibility

---

### Conclusion

**Your DIET architecture is well-designed and follows NetBox best practices.** The recommended enhancements are evolutionary improvements to an already solid foundation, not fundamental restructuring.

**Key Strengths:**
1. Architecture is sound - Proper separation, referencing not duplicating
2. Following NetBox patterns - Extension model, status workflow
3. Good model design - Clear responsibilities, proper relationships
4. Performance-aware - Already thinking about optimization

**Minor Gaps:**
1. Validation phase could be more explicit/enforced
2. Missing link between plan and generated objects
3. Could optimize bulk operations for large plans

**Recommendation:** Proceed with current architecture, add recommended enhancements incrementally as needed.

**Next Steps:**
1. Review detailed guides (NETBOX_PLUGIN_BEST_PRACTICES.md, DIET_ARCHITECTURE_RESEARCH_SUMMARY.md)
2. Implement validation method (quick win)
3. Add GeneratedObject model (medium effort)
4. Optimize generation with bulk operations (medium effort)
5. Consider status workflow enhancements (low priority)

**Questions for Discussion:**
1. Do you need plan versioning/snapshots?
2. Should plans be immutable after generation?
3. Do you need to support regeneration (update existing objects)?
4. Should there be approval workflow before generation?
5. Do you need role-based permissions (who can generate vs who can plan)?
