# NetBox Plugin Best Practices for DIET Architecture Alignment

**Research Date:** 2025-12-27
**Context:** Recommendations for hh-netbox-plugin DIET (Design and Implementation Excellence Tools) module

---

## Executive Summary

This guide synthesizes research from NetBox ecosystem plugins, official documentation, and community best practices to provide actionable recommendations for properly extending NetBox without creating parallel schema or conflicting with core functionality.

**Key Finding:** Your DIET architecture is already following many best practices. The models appropriately reference core DeviceType/ModuleType instead of duplicating them, and use the extension pattern for Hedgehog-specific metadata.

---

## 1. Mature Plugin Analysis

### 1.1 netbox-inventory (ArnesSI/netbox-inventory)

**Purpose:** Hardware asset tracking for installed and stored inventory

**Architectural Patterns:**
- **Extension Model:** Creates `Asset` model that *relates to* rather than *replaces* core Device/Module models
- **Status-Driven Logic:** Automatic state transitions (stored → assigned → stored) based on relationships
- **Bidirectional Links:** Assets reference Site, Location, Rack without duplicating that data
- **Configuration-First Design:** Extensive settings for behavior customization
- **Audit Trail Pattern:** Separate models for tracking verification and location history

**Key Lesson:** When tracking additional lifecycle states (design, stored, deployed), create separate models that reference core objects rather than extending Device itself.

**Relevance to DIET:** Similar pattern - DIET plans reference DeviceType/ModuleType for specifications, but maintain separate planning-specific state.

### 1.2 netbox-lifecycle (DanSheps/netbox-lifecycle)

**Purpose:** Hardware EOL/EOS, license, and support contract tracking

**Architectural Patterns:**
- **Non-Invasive Extension:** Attaches metadata to DeviceTypes and ModuleTypes via ForeignKeys, doesn't modify them
- **Card-Based UI Integration:** Adds information to existing pages without replacing core views
- **Scoped Relationships:** Creates its own Contract/License models that assign to core objects
- **Lazy-Loading Optimization:** Async loading of expired contracts for performance

**Key Lesson:** Use plugin-specific models for metadata that NetBox doesn't track, but reference core models rather than duplicating their fields.

**Relevance to DIET:** Your `DeviceTypeExtension` follows this exact pattern - one-to-one relationship adding Hedgehog-specific metadata without modifying DeviceType.

### 1.3 ntc-netbox-plugin-onboarding (Network to Code)

**Purpose:** Automated device discovery and onboarding via SSH/NETCONF

**Architectural Patterns:**
- **Staged Workflow:** Discovery → Validation → Creation phases
- **Conditional Creation:** Boolean flags control which NetBox objects get auto-created
- **Asynchronous Processing:** Django-RQ for background jobs
- **Minimal Synchronization:** Focuses on essential attributes, avoids full device sync
- **Extensibility Points:** Maps and hooks for customization without code changes

**Key Lesson:** For design-to-deployment workflows, use staging models that validate before materializing core NetBox objects.

**Relevance to DIET:** Your TopologyPlan → Generate NetBox objects workflow mirrors this pattern. Consider explicit staging/validation phases.

### 1.4 Other Notable Plugins

- **netbox-branching (NetBox Labs):** Git-like branching for NetBox - shows how to handle design variations
- **netbox-qrcode:** Extends existing objects without modifying them - pure presentation layer plugin
- **netbox-floorplan-plugin:** Adds visualization without schema changes - demonstrates UI-only extensions

---

## 2. Extension Patterns: CustomField vs Model

### 2.1 When to Use CustomFields

**Use CustomFields when:**
- Simple data type (string, integer, boolean, date)
- No complex relationships to other models
- User-configurable fields that vary by deployment
- Fields that may be added/removed without migrations
- Storing metadata for searching/filtering

**Limitations:**
- Stored as JSON in `custom_field_data` JSONField
- Performance overhead for complex queries
- No foreign key relationships
- No database-level constraints

**Example from Research:**
```python
# CustomFields are user-defined via UI, not in code
# Access via model.cf['field_name']
```

### 2.2 When to Create Plugin Models

**Use Plugin Models when:**
- Complex relationships (ForeignKey, ManyToMany)
- Multiple related objects forming a data structure
- Calculated/derived fields requiring business logic
- Workflow state that needs atomicity
- Data that plugins own and manage

**Best Practices:**
- Inherit from `NetBoxModel` for full feature support
- Use discrete mixins (`ChangeLoggingMixin`, `TagsMixin`) for selective features
- Reference core models by string: `ForeignKey('dcim.Device')` to reduce coupling
- Set `related_name='+'` or prefix with plugin name to avoid namespace conflicts

**Example from Your Code:**
```python
class DeviceTypeExtension(NetBoxModel):
    """Hedgehog-specific metadata for NetBox DeviceTypes"""
    device_type = models.OneToOneField(
        DeviceType,
        on_delete=models.CASCADE,
        related_name='hedgehog_metadata',  # ✅ Plugin-prefixed
    )
    mclag_capable = models.BooleanField(default=False)
```

### 2.3 Hybrid Approach: Extension Pattern

**Pattern:** One-to-one relationship to core model for plugin-specific metadata

**When to Use:**
- Need to add structured data to existing NetBox models
- Data is plugin-specific, not generally applicable
- Want optional metadata (not all objects need it)

**Your Implementation:**
```python
# ✅ CORRECT: Extension pattern
DeviceTypeExtension → DeviceType (OneToOne)

# ❌ WRONG: Would be duplicating core schema
class HedgehogDeviceType(NetBoxModel):
    manufacturer = ...  # Duplicates DeviceType.manufacturer
    model = ...         # Duplicates DeviceType.model
```

---

## 3. Design-Time vs Runtime State

### 3.1 NetBox's Core Philosophy

**NetBox represents intended/designed state, not operational state.**

From NetBox documentation:
> "NetBox intends to represent the desired state of a network versus its operational state. As such, automated import of live network state is strongly discouraged. All data created in NetBox should first be vetted by a human to ensure its integrity."

**The Gap:**
- **Design:** What you want to build (NetBox's primary domain)
- **Operational:** What actually exists (discovered reality)
- **Drift:** Differences between the two

### 3.2 Recommended Patterns for Design → Deployment

**Option 1: Separate Planning Models (Your Current Approach)**

✅ **Advantages:**
- Clear separation of concerns
- Planning data can be messy, incomplete, or speculative
- Can delete plans without affecting production inventory
- Supports multiple design iterations
- Allows validation before materialization

```python
TopologyPlan (DIET)
    ├── PlanServerClass → ForeignKey(DeviceType)
    ├── PlanSwitchClass → ForeignKey(DeviceTypeExtension)
    └── [Generate] → Creates actual Device objects in NetBox
```

**Option 2: Status-Based Workflow**

Alternative approach (not recommended for your use case):
```python
# All objects exist in NetBox with status field
Device(status='planned')  → Device(status='deployed')
```

❌ **Disadvantages:**
- Pollutes production inventory with hypothetical objects
- Harder to clean up abandoned plans
- Risk of accidental deployment

**Recommendation:** Your current approach (Option 1) is **correct** for DIET's use case.

### 3.3 Workflow Transition Best Practices

From ntc-netbox-plugin-onboarding analysis:

**Staged Approach:**
1. **Discovery/Planning Phase:** Create plugin-owned staging objects
2. **Validation Phase:** Check for conflicts, missing dependencies
3. **Materialization Phase:** Create actual NetBox objects transactionally
4. **Post-Creation:** Optionally maintain link between plan and realized objects

**Your Implementation Opportunities:**
```python
class TopologyPlan(NetBoxModel):
    status = models.CharField(
        choices=TopologyPlanStatusChoices,
        # draft → validated → approved → deployed
    )

    # Track generation state
    last_generated_at = property(...)  # ✅ Already implemented
    needs_regeneration = property(...) # ✅ Already implemented
```

**Enhancement Suggestion:**
Consider adding validation phase before generation:
```python
def validate_for_generation(self):
    """
    Pre-flight checks before creating NetBox objects.

    Returns:
        (bool, List[str]): (is_valid, error_messages)
    """
    errors = []

    # Check for required relationships
    if not self.switch_classes.exists():
        errors.append("Plan must have at least one switch class")

    # Check for conflicts with existing NetBox objects
    # ...

    return (len(errors) == 0, errors)
```

---

## 4. Data Model Principles

### 4.1 What Belongs in Plugin Models vs NetBox Core

| Data Type | Plugin Model | NetBox Core | Example |
|-----------|--------------|-------------|---------|
| Hardware specifications | ❌ Reference only | ✅ Own | DeviceType, ModuleType |
| Physical inventory | ❌ Reference only | ✅ Own | Device, Module, Site |
| Network addressing | ❌ Reference only | ✅ Own | IPAddress, Prefix |
| Plugin-specific metadata | ✅ Own | ❌ Don't modify | DeviceTypeExtension |
| Workflow/planning state | ✅ Own | ❌ Don't pollute | TopologyPlan, PlanServerClass |
| Calculated/derived values | ✅ Own (cached) | Maybe | calculated_quantity |

**Golden Rule:** If NetBox has a model for it, reference it. If NetBox doesn't track it, create it.

### 4.2 Referencing vs Duplicating Core Model Data

**✅ CORRECT Pattern (Your Code):**
```python
class PlanServerClass(NetBoxModel):
    server_device_type = models.ForeignKey(
        DeviceType,  # ✅ Reference, don't duplicate
        on_delete=models.PROTECT,
        related_name='plan_server_classes',
    )

    quantity = models.IntegerField(...)  # ✅ Planning-specific field
```

**❌ WRONG Pattern (Anti-pattern):**
```python
class PlanServerClass(NetBoxModel):
    manufacturer = models.CharField(...)  # ❌ Duplicates DeviceType.manufacturer
    model = models.CharField(...)         # ❌ Duplicates DeviceType.model
    u_height = models.IntegerField(...)   # ❌ Duplicates DeviceType.u_height
```

**Why Reference is Better:**
- Single source of truth
- Automatic updates when DeviceType changes
- Can query relationships: `device_type.plan_server_classes.all()`
- Leverages NetBox's existing validation and UI

### 4.3 Managing Calculated/Derived Values

**Performance Considerations:**

From NetBox core performance optimization research:
- Use `select_related()` for ForeignKey relationships
- Use `prefetch_related()` for reverse ForeignKeys and ManyToMany
- Cache expensive calculations in database fields
- Annotate querysets instead of Python loops

**Your Implementation:**
```python
class PlanSwitchClass(NetBoxModel):
    calculated_quantity = models.IntegerField(
        null=True,
        blank=True,
        editable=False,  # ✅ Good - prevents manual override
    )

    override_quantity = models.IntegerField(
        null=True,
        blank=True,  # ✅ Good - allows user override
    )

    @property
    def effective_quantity(self):
        """Return override if set, otherwise calculated"""
        if self.override_quantity is not None:
            return self.override_quantity
        return self.calculated_quantity or 0
```

**Enhancement Recommendations:**
1. Track calculation timestamp to detect stale data
2. Store calculation metadata (e.g., which algorithm version)
3. Consider using Django signals to auto-recalculate when dependencies change

**Example Enhancement:**
```python
class CalculationMetadata(models.Model):
    """Track when and how calculations were performed"""
    plan_switch_class = models.OneToOneField(
        PlanSwitchClass,
        on_delete=models.CASCADE,
        related_name='calc_metadata'
    )
    calculated_at = models.DateTimeField(auto_now=True)
    algorithm_version = models.CharField(max_length=50)
    inputs_hash = models.CharField(max_length=64)  # Detect changes
```

### 4.4 ForeignKey Best Practices

**From NetBox Plugin Tutorial and Community:**

```python
# ✅ CORRECT: Reference by string to reduce coupling
target_switch_class = models.ForeignKey(
    'topology_planning.PlanSwitchClass',  # String reference
    on_delete=models.PROTECT,
    related_name='incoming_connections',  # Prefixed or explicit
)

# ✅ CORRECT: Reference core models by app.Model
server_device_type = models.ForeignKey(
    'dcim.DeviceType',  # Don't import, use string
    on_delete=models.PROTECT,
    related_name='plan_server_classes',  # Avoid '+' for useful reverse
)

# ⚠️ CAUTION: Related name conflicts
# If multiple plugins add ForeignKeys to same core model,
# use plugin-prefixed related_name or '+' to disable reverse

# ✅ Safe from conflicts
device_type = models.ForeignKey(
    'dcim.DeviceType',
    related_name='hedgehog_plan_servers',  # Plugin prefix
)

# ✅ Also safe, but no reverse relationship
device_type = models.ForeignKey(
    'dcim.DeviceType',
    related_name='+',  # Suppress reverse
)
```

**Cascade Behavior Guidelines:**

| Scenario | on_delete Behavior | Rationale |
|----------|-------------------|-----------|
| Plugin owns child | `CASCADE` | Delete children when parent deleted |
| Reference to core model | `PROTECT` | Prevent deletion of core data |
| Optional reference | `SET_NULL` with `null=True` | Allow deletion, clear reference |
| User ownership | `SET_NULL` | Keep data if user deleted |

**Your Implementation Review:**
```python
# ✅ CORRECT
plan = models.ForeignKey(
    TopologyPlan,
    on_delete=models.CASCADE,  # ✅ Plan owns server classes
)

server_device_type = models.ForeignKey(
    DeviceType,
    on_delete=models.PROTECT,  # ✅ Don't allow deleting DeviceType in use
)

created_by = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,  # ✅ Keep plan if user deleted
    null=True,
)
```

---

## 5. Plugin Architecture Best Practices

### 5.1 Model Organization

**When to Split Models:**
- Each model represents a distinct concept
- Clear boundaries between lifecycle states
- Different access control requirements
- Different UI/API requirements

**When to Consolidate:**
- Objects always used together
- Avoiding excessive JOINs
- Simplifying foreign key relationships

**Your Current Structure (Analysis):**
```
topology_planning/
    ├── topology_plans.py      # ✅ Core planning models
    ├── reference_data.py      # ✅ Reusable specifications
    ├── generation.py          # ✅ Generation state tracking
    ├── port_zones.py          # ✅ Port allocation logic
    └── naming.py              # ✅ Naming convention logic
```

**Assessment:** ✅ Good separation of concerns. Each file has a clear purpose.

**Consideration:** As models grow, you might split `topology_plans.py`:
```
topology_planning/
    ├── plans.py           # TopologyPlan
    ├── servers.py         # PlanServerClass, PlanServerConnection
    ├── switches.py        # PlanSwitchClass
    ├── networking.py      # PlanMCLAGDomain
    └── ...
```

### 5.2 Avoiding Tight Coupling to NetBox Internals

**Critical Rules from NetBox Documentation:**

> "Any part of the NetBox code base not documented is not part of the supported plugins API and should not be employed by a plugin."

> "Plugins may not alter, remove, or override core NetBox models in any way."

**Supported APIs (Safe to Use):**
- `netbox.models.NetBoxModel` and documented mixins
- `netbox.views.generic.*` generic views
- `netbox.tables.NetBoxTable` and columns
- `netbox.forms.*` form classes
- `netbox.api.serializers.*` API serializers
- `dcim.models.*` (for reading/ForeignKey, not modifying)

**Unsupported/Risky (Avoid):**
- Monkey-patching NetBox classes
- Importing from `netbox.internal.*` or similar
- Relying on specific HTML structure in templates
- Using undocumented model methods
- Direct database queries bypassing ORM

**Your Implementation Review:**
```python
# ✅ CORRECT: Using documented APIs
from netbox.models import NetBoxModel
from dcim.models import DeviceType, ModuleType

# ✅ CORRECT: Standard Django patterns
class TopologyPlan(NetBoxModel):
    ...
```

### 5.3 Version Compatibility

**From NetBox v4.0 Migration Research:**

**Breaking Changes to Prepare For:**
- NetBox can increment major versions only from most recent minor version
- Plugins must declare compatible NetBox versions
- Import paths may change (e.g., `extras.plugins` → `netbox.plugins`)
- Generic view APIs evolve with breaking changes

**Best Practices:**
1. Pin NetBox version requirements in `pyproject.toml`:
   ```toml
   [tool.poetry.dependencies]
   netbox = ">=4.1.0,<5.0.0"
   ```

2. Use feature detection instead of version checks:
   ```python
   # ✅ GOOD
   if hasattr(NetBoxModel, 'some_new_method'):
       self.some_new_method()

   # ❌ FRAGILE
   if netbox_version >= '4.1':
       ...
   ```

3. Follow official migration guides for major versions

4. Test against multiple NetBox versions in CI

### 5.4 Bulk Operations and Performance

**From NetBox Core Performance Research:**

**N+1 Query Problems:**
```python
# ❌ BAD: N+1 queries
for plan_class in PlanServerClass.objects.all():
    print(plan_class.server_device_type.manufacturer.name)
    # Each iteration queries database!

# ✅ GOOD: Use select_related
for plan_class in PlanServerClass.objects.select_related(
    'server_device_type__manufacturer'
):
    print(plan_class.server_device_type.manufacturer.name)
    # All data fetched in one query
```

**Prefetch Related Objects:**
```python
# ✅ Optimize reverse ForeignKeys
plans = TopologyPlan.objects.prefetch_related(
    'server_classes__connections',
    'switch_classes__incoming_connections'
)

for plan in plans:
    for server_class in plan.server_classes.all():
        # No additional queries
        for conn in server_class.connections.all():
            ...
```

**Bulk Creation:**
```python
# ❌ SLOW: Individual saves
for i in range(1000):
    Device.objects.create(name=f"device-{i}", ...)

# ✅ FAST: Bulk create
devices = [
    Device(name=f"device-{i}", ...)
    for i in range(1000)
]
Device.objects.bulk_create(devices, batch_size=100)
```

**Your Generation Code Considerations:**
When generating NetBox objects from TopologyPlan:
1. Use `bulk_create()` for devices/interfaces
2. Use `select_related()` when reading plan data
3. Batch API calls if calling external services
4. Consider using Django transactions for atomicity

---

## 6. Common Anti-Patterns and Mistakes

### 6.1 Schema Anti-Patterns

**❌ Duplicating Core Models**
```python
# WRONG: Reimplementing what NetBox already has
class HedgehogDevice(NetBoxModel):
    name = models.CharField(...)
    site = models.ForeignKey(...)
    device_type = models.CharField(...)  # Should reference DeviceType!
```

**✅ Correct Approach:**
```python
# RIGHT: Reference core models
class HedgehogConfig(NetBoxModel):
    device = models.OneToOneField('dcim.Device', ...)
    hedgehog_specific_field = models.CharField(...)
```

**❌ Overly Generic Models**
```python
# WRONG: Trying to make one model do everything
class ConfigItem(NetBoxModel):
    object_type = models.CharField(...)  # device, interface, cable, etc.
    object_id = models.IntegerField(...)
    config_data = models.JSONField(...)  # Unstructured blob
```

**✅ Correct Approach:**
```python
# RIGHT: Specific models for specific purposes
class DeviceConfig(NetBoxModel):
    device = models.ForeignKey('dcim.Device', ...)
    startup_config = models.TextField(...)
    running_config = models.TextField(...)
```

### 6.2 Naming Conflicts

**❌ Common Mistake:**
```python
# Plugin 1
class BGPSession(NetBoxModel):
    device = models.ForeignKey(
        'dcim.Device',
        related_name='bgp_sessions'  # ⚠️ Potential conflict
    )

# Plugin 2 (different plugin!)
class BGPPeering(NetBoxModel):
    device = models.ForeignKey(
        'dcim.Device',
        related_name='bgp_sessions'  # 💥 Conflict!
    )
```

**✅ Correct Approach:**
```python
# Plugin 1
class BGPSession(NetBoxModel):
    device = models.ForeignKey(
        'dcim.Device',
        related_name='plugin1_bgp_sessions'  # ✅ Prefixed
    )

# Plugin 2
class BGPPeering(NetBoxModel):
    device = models.ForeignKey(
        'dcim.Device',
        related_name='plugin2_bgp_peerings'  # ✅ Different name
    )
```

**Your Review:**
```python
# ✅ Your code is good
server_device_type = models.ForeignKey(
    DeviceType,
    related_name='plan_server_classes',  # Descriptive, unlikely to conflict
)
```

### 6.3 Migration Mistakes

**❌ Underscores in Model Names:**
```python
# WRONG: Will cause permission errors
class Topology_Plan(NetBoxModel):  # ❌ Underscore!
    ...
```

**✅ Correct:**
```python
# RIGHT: CapWords (PEP8)
class TopologyPlan(NetBoxModel):  # ✅ Proper naming
    ...
```

**❌ Running makemigrations without DEVELOPER=True:**
```bash
# WRONG: Can corrupt schema
python manage.py makemigrations netbox_hedgehog
```

**✅ Correct:**
```python
# In configuration.py
DEVELOPER = True  # Enable migration generation
```

### 6.4 API and View Anti-Patterns

**❌ Bypassing NetBox Generic Views:**
```python
# WRONG: Reinventing the wheel
class MyCustomListView(View):
    def get(self, request):
        objects = MyModel.objects.all()
        # Custom pagination, filtering, etc.
```

**✅ Correct:**
```python
# RIGHT: Use NetBox generic views
from netbox.views.generic import ObjectListView

class MyModelListView(ObjectListView):
    queryset = MyModel.objects.all()
    table = MyModelTable
    filterset = MyModelFilterSet
    # NetBox handles pagination, filtering, permissions
```

---

## 7. Migration Strategies for Architectural Alignment

### 7.1 Current DIET Architecture Assessment

**✅ Already Following Best Practices:**
1. ✅ Referencing DeviceType/ModuleType instead of duplicating
2. ✅ Using DeviceTypeExtension for Hedgehog-specific metadata
3. ✅ Separate planning models (not polluting core inventory)
4. ✅ Proper ForeignKey cascade behavior
5. ✅ Calculated vs override fields for switch quantities
6. ✅ Clean model organization by concern

**Opportunities for Enhancement:**

### 7.2 Recommended Enhancements

**1. Add Validation Phase:**
```python
class TopologyPlan(NetBoxModel):
    # ... existing fields ...

    validation_errors = models.JSONField(
        default=list,
        blank=True,
        help_text="Pre-flight validation errors"
    )

    validated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When plan last passed validation"
    )

    def validate_for_generation(self):
        """Check if plan is ready to generate NetBox objects"""
        errors = []

        # Check required relationships
        if not self.switch_classes.exists():
            errors.append("Plan must have at least one switch class")

        # Check for port capacity issues
        for switch_class in self.switch_classes.all():
            if switch_class.effective_quantity == 0:
                errors.append(
                    f"Switch class {switch_class.switch_class_id} "
                    f"has zero quantity"
                )

        # Check for naming conflicts with existing NetBox objects
        # ...

        self.validation_errors = errors
        if not errors:
            self.validated_at = timezone.now()
        self.save()

        return len(errors) == 0
```

**2. Track Plan → NetBox Object Mapping:**
```python
class GeneratedObject(NetBoxModel):
    """
    Track which NetBox objects were generated from which plan.

    Enables:
    - Showing generated objects in plan detail view
    - Preventing re-generation
    - Cleanup if plan is deleted
    - Audit trail
    """
    plan = models.ForeignKey(
        TopologyPlan,
        on_delete=models.CASCADE,
        related_name='generated_objects'
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Type of generated object (Device, Interface, etc.)"
    )

    object_id = models.PositiveIntegerField(
        help_text="ID of generated object"
    )

    object = GenericForeignKey('content_type', 'object_id')

    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['plan', 'content_type', 'object_id']]
```

**3. Enhance Calculation Metadata:**
```python
class PlanSwitchClass(NetBoxModel):
    # ... existing fields ...

    calculation_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadata about calculation (inputs, algorithm version)"
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
            'inputs': inputs,  # For debugging
        }
        self.save()
```

**4. Add Bulk Operation Utilities:**
```python
# In generation.py or new utilities.py
class BulkDeviceGenerator:
    """Optimize NetBox object generation with bulk operations"""

    def __init__(self, plan):
        self.plan = plan
        self.devices_to_create = []
        self.interfaces_to_create = []

    def add_device(self, **kwargs):
        """Queue device for bulk creation"""
        self.devices_to_create.append(Device(**kwargs))

    def add_interface(self, **kwargs):
        """Queue interface for bulk creation"""
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

**5. Consider Status Workflow:**
```python
# In choices.py
class TopologyPlanStatusChoices(ChoiceSet):
    STATUS_DRAFT = 'draft'
    STATUS_VALIDATED = 'validated'
    STATUS_APPROVED = 'approved'
    STATUS_GENERATED = 'generated'
    STATUS_DEPLOYED = 'deployed'
    STATUS_ARCHIVED = 'archived'

    CHOICES = [
        (STATUS_DRAFT, 'Draft', 'gray'),
        (STATUS_VALIDATED, 'Validated', 'blue'),
        (STATUS_APPROVED, 'Approved', 'green'),
        (STATUS_GENERATED, 'Generated', 'cyan'),
        (STATUS_DEPLOYED, 'Deployed', 'purple'),
        (STATUS_ARCHIVED, 'Archived', 'red'),
    ]
```

### 7.3 Things You're Already Doing Right

**Do NOT Change These:**

1. ✅ **Referencing Core Models:**
   ```python
   server_device_type = models.ForeignKey(DeviceType, ...)
   ```
   Keep this pattern. It's the correct approach.

2. ✅ **Extension Pattern for Metadata:**
   ```python
   class DeviceTypeExtension(NetBoxModel):
       device_type = models.OneToOneField(DeviceType, ...)
   ```
   Perfect pattern for plugin-specific metadata.

3. ✅ **Separate Planning Schema:**
   ```python
   TopologyPlan
       ├── PlanServerClass
       ├── PlanSwitchClass
       └── PlanServerConnection
   ```
   This separation is exactly right for design-time workflows.

4. ✅ **Calculated + Override Pattern:**
   ```python
   calculated_quantity = IntegerField(editable=False)
   override_quantity = IntegerField(blank=True, null=True)
   ```
   Good pattern for user control over calculations.

---

## 8. Specific Recommendations for DIET

### 8.1 High-Priority Recommendations

**1. Add Pre-Generation Validation**
- Implement `TopologyPlan.validate_for_generation()`
- Store validation errors in the model
- Require validation before allowing generation
- Show validation errors in UI

**2. Track Generated Objects**
- Create `GeneratedObject` model to link plans → NetBox objects
- Enable showing "what was created" in plan detail view
- Support cleanup/rollback if needed
- Prevent duplicate generation

**3. Enhance Status Workflow**
- Add more status transitions (draft → validated → approved → generated)
- Enforce status requirements (can't generate unless approved)
- Add status change audit trail

**4. Optimize Generation Performance**
- Use bulk_create for devices/interfaces
- Use select_related when reading plan data
- Batch database operations
- Add progress tracking for large plans

### 8.2 Medium-Priority Recommendations

**5. Add Calculation Metadata**
- Track when calculations were performed
- Store algorithm version
- Hash inputs to detect staleness
- Enable debugging calculation issues

**6. Improve Error Handling**
- Comprehensive validation before generation
- Transaction rollback on failure
- Clear error messages for users
- Logging for debugging

**7. Consider Versioning**
- Allow saving plan versions/snapshots
- Compare plan versions
- Revert to previous versions
- Track changes over time

### 8.3 Low-Priority / Future Considerations

**8. Integration with NetBox Branching**
- Could use NetBox branching for design variations
- Explore if it fits DIET workflow
- May be overkill for current needs

**9. Export/Import Plans**
- Export plans as JSON/YAML
- Import plans from templates
- Share plans between NetBox instances
- Version control plans in git

**10. Visualization**
- Generate topology diagrams from plans
- Show port allocation visually
- Preview generated topology
- Integration with netbox-topology-views

---

## 9. Key Takeaways

### 9.1 Do's ✅

1. **DO** reference core NetBox models (DeviceType, ModuleType, etc.)
2. **DO** use extension pattern (OneToOne) for plugin-specific metadata
3. **DO** keep design/planning data separate from operational inventory
4. **DO** use string references for ForeignKeys to reduce coupling
5. **DO** inherit from NetBoxModel for full feature support
6. **DO** use select_related and prefetch_related for performance
7. **DO** use bulk operations for creating many objects
8. **DO** validate before materializing NetBox objects
9. **DO** track what was generated from what plan
10. **DO** use transactions for atomicity

### 9.2 Don'ts ❌

1. **DON'T** duplicate data that exists in core NetBox models
2. **DON'T** modify or extend core NetBox models directly
3. **DON'T** pollute operational inventory with planning data
4. **DON'T** use underscores in model class names
5. **DON'T** use undocumented NetBox internal APIs
6. **DON'T** create N+1 query problems
7. **DON'T** bypass NetBox generic views and forms
8. **DON'T** create related_name conflicts with other plugins
9. **DON'T** make migrations without DEVELOPER=True
10. **DON'T** assume NetBox internals won't change

### 9.3 Your Current Status

**Overall Assessment: 8.5/10**

Your DIET architecture is already following most best practices:
- ✅ Proper use of ForeignKeys to core models
- ✅ Extension pattern for metadata
- ✅ Separate planning schema
- ✅ Good model organization
- ✅ Calculated vs override pattern

**Main Gap:** Missing validation phase and generated object tracking.

**Recommended Next Steps:**
1. Add `TopologyPlan.validate_for_generation()` method
2. Create `GeneratedObject` model to track plan → NetBox object mapping
3. Enhance status workflow with validation/approval states
4. Optimize generation code with bulk operations

---

## 10. Additional Resources

### Official Documentation
- [NetBox Plugin Development](https://netboxlabs.com/docs/netbox/plugins/development/)
- [NetBox Database Models](https://netboxlabs.com/docs/netbox/development/models/)
- [Migrating Plugin to NetBox v4.0](https://netboxlabs.com/docs/netbox/plugins/development/migration-v4/)

### Example Plugins (GitHub)
- [netbox-inventory](https://github.com/ArnesSI/netbox-inventory) - Hardware asset tracking
- [netbox-lifecycle](https://github.com/DanSheps/netbox-lifecycle) - EOL/EOS tracking
- [ntc-netbox-plugin-onboarding](https://github.com/networktocode/ntc-netbox-plugin-onboarding) - Device discovery
- [netbox-plugin-tutorial](https://github.com/netbox-community/netbox-plugin-tutorial) - Official tutorial

### Community Resources
- [Awesome NetBox](https://github.com/netbox-community/awesome-netbox) - Curated plugin list
- [NetBox Discussions](https://github.com/netbox-community/netbox/discussions) - Q&A forum

---

## Appendix: Research Sources

### Web Search Sources
- [Plugins | NetBox Labs](https://netboxlabs.com/plugins/)
- [ArnesSI/netbox-inventory GitHub](https://github.com/ArnesSI/netbox-inventory)
- [Database Models | NetBox Documentation](https://netboxlabs.com/docs/netbox/en/stable/plugins/development/models/)
- [CustomField - NetBox Documentation](https://docs.netbox.dev/en/stable/models/extras/customfield/)
- [Customization and Extension | DeepWiki](https://deepwiki.com/netbox-community/netbox/8-customization-and-extension)
- [DanSheps/netbox-lifecycle GitHub](https://github.com/DanSheps/netbox-lifecycle)
- [networktocode/ntc-netbox-plugin-onboarding GitHub](https://github.com/networktocode/ntc-netbox-plugin-onboarding)
- [Migrating Your Plugin to NetBox v4.0](https://netboxlabs.com/docs/netbox/plugins/development/migration-v4/)
- [About Plugins - NetBox Documentation](https://netbox.readthedocs.io/en/stable/plugins/)
- [Plugin Development ForeignKey namespace Discussion](https://github.com/netbox-community/netbox/discussions/9208)
- [Announcing NetBox Discovery](https://netboxlabs.com/blog/announcing-netbox-discovery-infrastructure-design-operational-reality/)
- [Navigating Network Automation with NetBox - Build and Deploy](https://netboxlabs.com/blog/network-automation-with-netbox-build-and-deploy/)
- [Support PrimaryModel and OrganizationalModel in plugins](https://github.com/netbox-community/netbox/issues/13182)
- [Prefetch related properties in DeviceListView](https://github.com/netbox-community/netbox/issues/9694)

### Direct Source Analysis
- NetBox Plugin Tutorial (step02-models.md)
- netbox-inventory plugin architecture (GitHub)
- netbox-lifecycle plugin architecture (GitHub)
- ntc-netbox-plugin-onboarding workflow patterns (GitHub)
- Awesome NetBox plugin catalog

**Date Compiled:** 2025-12-27
**For:** hh-netbox-plugin DIET architecture review (Issue #114)
