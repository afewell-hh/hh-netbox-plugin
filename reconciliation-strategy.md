# Reconciliation Strategy Guide for DIET ↔ NetBox

## Executive Summary

This guide provides a comprehensive reconciliation strategy for managing the relationship between DIET planning objects (desired topology) and NetBox objects (actual state). It draws from proven patterns in Kubernetes operators, GitOps reconciliation, and Terraform state management.

**Key Recommendation**: Implement a Kubernetes-style reconciliation loop with server-side apply semantics, ownership tracking, and preview/apply workflow.

---

## 1. Core Reconciliation Concepts

### 1.1 The Reconciliation Loop

The fundamental pattern from Kubernetes operators consists of three phases:

1. **Observe** - Read the current state from NetBox
2. **Analyze** - Compare current state with desired state (DIET plan)
3. **Act** - Apply changes to move current state toward desired state

**Key Properties:**
- **Level-triggered, not edge-triggered**: Don't just react to changes; continuously ensure actual state matches desired state
- **Idempotent**: Running reconciliation multiple times produces the same result
- **Eventually consistent**: System converges toward desired state over time
- **Stateless**: Each reconciliation reads current state fresh from NetBox

### 1.2 Three-Way Merge

Modern systems (Helm 3, ArgoCD) use three-way merge to intelligently handle updates:

- **Original state**: What DIET last generated/applied
- **Desired state**: What DIET plan currently specifies
- **Current state**: What actually exists in NetBox

This enables:
- Detecting user modifications vs DIET-generated values
- Preserving manual overrides during regeneration
- Intelligent conflict resolution

**Example**: If DIET originally created device with name "leaf-01", user manually changed description to "Production leaf", and new plan changes name to "leaf-001", three-way merge can rename device while preserving the manual description change.

---

## 2. Field Ownership & Management

### 2.1 Server-Side Apply Pattern

Kubernetes Server-Side Apply (SSA) provides a robust model for field ownership:

**Core Concept**: Track which "field manager" owns which fields of an object.

```python
# Example ownership metadata
{
  "name": "leaf-01",  # owned by: diet-generator
  "description": "Production leaf switch",  # owned by: manual-edit
  "rack_id": 123,  # owned by: diet-generator
  "tags": ["prod", "fabric-a"]  # owned by: diet-generator, manual-edit
}
```

**Benefits:**
- Multiple actors can safely manage different fields without conflicts
- Field manager only updates fields it owns
- Conflicts are explicit when multiple managers try to own same field
- Can force-override with explicit acknowledgment

### 2.2 Ownership Tracking for DIET

**Implementation Approach:**

Use NetBox custom fields or tags to track ownership:

```python
# On each DIET-managed object
custom_fields = {
    "diet_managed": True,
    "diet_plan_id": "plan-123",
    "diet_generator_version": "v1.2.0",
    "diet_managed_fields": ["name", "device_type", "rack", "position"],
    "diet_last_applied": "2025-12-27T10:30:00Z"
}
```

**Owner References Pattern (Kubernetes-style):**

```python
# Child object references parent
cable = Cable(
    owner_reference={
        "kind": "DIETPlan",
        "name": "fabric-a-plan",
        "uid": "plan-123"
    }
)
```

This enables:
- Identifying all objects created by a specific plan
- Garbage collection when plan is deleted
- Preventing accidental deletion of non-managed objects

---

## 3. Drift Detection

### 3.1 What is Drift?

**Drift** occurs when actual NetBox state diverges from DIET plan's desired state.

**Types of Drift:**

1. **User modifications**: Manual edits to DIET-managed objects
2. **External changes**: Other systems modifying NetBox
3. **Orphaned objects**: Objects in NetBox not in current plan
4. **Missing objects**: Objects in plan not in NetBox

### 3.2 Detection Strategy

**Continuous Monitoring:**
- Run drift detection on schedule (e.g., hourly)
- Trigger detection on plan changes
- Alert on significant drift

**Implementation:**

```python
def detect_drift(plan):
    """Compare desired state (plan) vs actual state (NetBox)."""
    drift_report = {
        "modified": [],  # DIET objects modified by users
        "missing": [],   # Objects in plan but not in NetBox
        "orphaned": [],  # Objects in NetBox but not in plan
        "unmanaged_changes": []  # Changes to non-managed fields
    }

    # Get all DIET-managed objects
    managed_objects = get_managed_objects(plan.id)

    for desired_obj in plan.get_desired_objects():
        actual_obj = find_in_netbox(desired_obj.id)

        if not actual_obj:
            drift_report["missing"].append(desired_obj)
        else:
            # Compare managed fields only
            managed_fields = get_managed_fields(actual_obj)
            for field in managed_fields:
                if getattr(actual_obj, field) != getattr(desired_obj, field):
                    drift_report["modified"].append({
                        "object": actual_obj,
                        "field": field,
                        "desired": getattr(desired_obj, field),
                        "actual": getattr(actual_obj, field)
                    })

    # Find orphaned objects
    for actual_obj in managed_objects:
        if not plan.contains_object(actual_obj):
            drift_report["orphaned"].append(actual_obj)

    return drift_report
```

### 3.3 Drift Remediation Strategies

**1. Auto-remediation (High Risk)**
- Automatically revert drift
- Use for non-production or specific fields only
- Requires manual approval setting

**2. Alert Only (Safe)**
- Report drift to users
- Require manual approval to reconcile
- Default for production systems

**3. Preserve Manual Changes (Recommended)**
- Track which fields were manually modified
- Don't override user changes during reconciliation
- Allow user to accept or reject specific drifts

---

## 4. Update Strategies

### 4.1 Full Replace (Naive)

**Approach**: Delete all objects and recreate from plan.

**Pros:**
- Simple to implement
- Guaranteed consistency

**Cons:**
- Destructive (loses manual modifications)
- Disrupts monitoring/references
- Can't handle incremental updates
- No preview capability

**When to Use**: Initial generation only, never for updates.

### 4.2 Minimal Diff + Patch (Smart)

**Approach**: Calculate differences and apply minimal changes.

**Pros:**
- Preserves existing objects and IDs
- Non-disruptive
- Can preview changes
- Faster for large topologies

**Cons:**
- More complex implementation
- Requires robust diff algorithm

**When to Use**: All updates after initial generation (recommended).

**Implementation:**

```python
def calculate_diff(desired_state, current_state):
    """Calculate minimal set of changes needed."""
    changes = {
        "create": [],
        "update": [],
        "delete": []
    }

    desired_by_id = {obj.identity: obj for obj in desired_state}
    current_by_id = {obj.identity: obj for obj in current_state}

    # Objects to create
    for identity, obj in desired_by_id.items():
        if identity not in current_by_id:
            changes["create"].append(obj)

    # Objects to update
    for identity, current_obj in current_by_id.items():
        if identity in desired_by_id:
            desired_obj = desired_by_id[identity]
            field_diffs = compare_objects(current_obj, desired_obj)
            if field_diffs:
                changes["update"].append({
                    "object": current_obj,
                    "changes": field_diffs
                })

    # Objects to delete (with safety checks)
    for identity, obj in current_by_id.items():
        if identity not in desired_by_id:
            if is_safe_to_delete(obj):
                changes["delete"].append(obj)

    return changes
```

### 4.3 Preview Changes (Terraform Plan Style)

**Approach**: Show what will change before applying.

**Essential for Production:**
- Preview gives users confidence
- Prevents accidental destructive changes
- Enables review workflow
- Standard in modern IaC tools (Terraform, Pulumi)

**Implementation:**

```python
def preview_changes(plan):
    """Generate preview without applying changes."""
    current_state = get_current_state(plan.id)
    desired_state = plan.get_desired_state()

    diff = calculate_diff(desired_state, current_state)

    # Format for display
    preview = {
        "summary": {
            "create": len(diff["create"]),
            "update": len(diff["update"]),
            "delete": len(diff["delete"])
        },
        "details": format_changes(diff)
    }

    return preview

def apply_changes(plan, preview_id):
    """Apply previously previewed changes."""
    # Verify preview is still valid
    current_preview = preview_changes(plan)
    stored_preview = get_stored_preview(preview_id)

    if not previews_match(current_preview, stored_preview):
        raise ValidationError("Plan changed since preview was generated")

    # Apply changes
    diff = calculate_diff(plan.get_desired_state(), get_current_state(plan.id))

    results = {
        "created": [],
        "updated": [],
        "deleted": [],
        "errors": []
    }

    # Create objects
    for obj in diff["create"]:
        try:
            created = create_in_netbox(obj)
            results["created"].append(created)
        except Exception as e:
            results["errors"].append({"object": obj, "error": str(e)})

    # Update objects
    for update in diff["update"]:
        try:
            updated = update_in_netbox(update["object"], update["changes"])
            results["updated"].append(updated)
        except Exception as e:
            results["errors"].append({"object": update["object"], "error": str(e)})

    # Delete objects
    for obj in diff["delete"]:
        try:
            delete_from_netbox(obj)
            results["deleted"].append(obj)
        except Exception as e:
            results["errors"].append({"object": obj, "error": str(e)})

    return results
```

---

## 5. Lifecycle Management

### 5.1 Object Identity

**Challenge**: How do we know if an object in NetBox corresponds to an object in the plan?

**Strategy 1: Stable Internal IDs**
```python
# Store DIET-generated ID on NetBox object
custom_fields = {
    "diet_object_id": "leaf-fabric-a-001"  # Deterministic ID
}
```

**Strategy 2: Natural Keys**
```python
# Use combination of fields as identity
identity = (device_type, rack, position)  # For devices
identity = (a_termination, b_termination)  # For cables
```

**Recommended**: Hybrid approach using custom field for DIET ID + natural keys as fallback.

### 5.2 Garbage Collection

**Challenge**: When objects are removed from plan, should they be deleted from NetBox?

**Kubernetes Pattern:**
- Owner references enable cascading deletion
- Delete parent → automatically delete children
- Configurable deletion policies (orphan, foreground, background)

**DIET Implementation:**

```python
# Cascade deletion policy
class DeletionPolicy(Enum):
    ORPHAN = "orphan"      # Leave objects in NetBox
    DELETE = "delete"      # Delete objects from NetBox
    WARN = "warn"         # Require manual approval

def handle_removed_objects(plan, removed_objects):
    """Handle objects removed from plan."""
    policy = plan.deletion_policy

    if policy == DeletionPolicy.ORPHAN:
        # Remove DIET ownership markers but leave objects
        for obj in removed_objects:
            unmark_as_managed(obj)

    elif policy == DeletionPolicy.DELETE:
        # Delete objects and their children
        for obj in removed_objects:
            if has_external_references(obj):
                # Don't delete if referenced by non-DIET objects
                log_warning(f"Object {obj} has external references, skipping deletion")
            else:
                delete_cascade(obj)

    elif policy == DeletionPolicy.WARN:
        # Require manual approval
        raise RequiresApproval(f"Plan removes {len(removed_objects)} objects")
```

### 5.3 Preventing Accidental Deletion

**Safety Mechanisms:**

1. **Deletion Protection Flag**
```python
custom_fields = {
    "diet_managed": True,
    "diet_deletion_protected": True  # Require explicit flag to delete
}
```

2. **Reference Checking**
```python
def is_safe_to_delete(obj):
    """Check if object can be safely deleted."""
    # Check for external references
    if has_manual_cables(obj):
        return False
    if has_ip_addresses(obj):
        return False
    if referenced_by_non_diet_objects(obj):
        return False
    return True
```

3. **Dry-Run Mode**
```python
def reconcile(plan, dry_run=True):
    """Reconcile with dry-run option."""
    changes = calculate_diff(plan.get_desired_state(), get_current_state(plan.id))

    if dry_run:
        return preview_changes(changes)
    else:
        return apply_changes(changes)
```

---

## 6. Handling Specific DIET Scenarios

### 6.1 Scenario: Scale Change (96 → 128 servers)

**User Action**: Change server quantity from 96 to 128

**Reconciliation Logic:**

```python
def reconcile_server_quantity_change(plan, old_qty=96, new_qty=128):
    """Handle increase in server count."""

    # Calculate what needs to be added
    existing_servers = get_managed_devices(plan, role="server")

    if len(existing_servers) > new_qty:
        # Scaling down - more complex
        servers_to_remove = existing_servers[new_qty:]
        return {
            "action": "scale_down",
            "remove": servers_to_remove,
            "requires_approval": True
        }
    else:
        # Scaling up - straightforward
        servers_to_create = new_qty - len(existing_servers)
        new_servers = generate_servers(plan, count=servers_to_create)
        new_interfaces = generate_interfaces_for_servers(new_servers)
        new_cables = generate_cables_for_servers(new_servers, plan)

        return {
            "action": "scale_up",
            "create": {
                "servers": new_servers,
                "interfaces": new_interfaces,
                "cables": new_cables
            }
        }
```

**Changes Applied:**
- Create 32 new devices
- Create interfaces for new devices
- Create cables connecting new devices
- Preserve all existing 96 servers unchanged

### 6.2 Scenario: Naming Pattern Change

**User Action**: Change naming pattern from "leaf-{n}" to "leaf-fab{fabric}-{n:03d}"

**Challenge**: Renaming 1000 devices while preserving relationships

**Reconciliation Logic:**

```python
def reconcile_naming_change(plan):
    """Handle renaming based on new pattern."""

    managed_devices = get_managed_devices(plan)
    rename_operations = []

    for device in managed_devices:
        # Calculate new name based on pattern
        new_name = plan.naming_pattern.format(device)

        if device.name != new_name:
            rename_operations.append({
                "device_id": device.id,  # NetBox ID stays same
                "old_name": device.name,
                "new_name": new_name,
                "diet_id": device.custom_fields["diet_object_id"]  # Stable ID
            })

    # Preview
    preview = {
        "type": "bulk_rename",
        "count": len(rename_operations),
        "operations": rename_operations
    }

    return preview

def apply_rename(rename_operations):
    """Apply renaming while preserving relationships."""

    # NetBox relationships use IDs, not names, so cables/interfaces unaffected
    for op in rename_operations:
        device = Device.objects.get(id=op["device_id"])
        device.name = op["new_name"]
        device.save()

    # All cables, interfaces, etc. automatically follow via ID references
```

**Key Insight**: NetBox relationships use IDs, so renaming doesn't break cables/interfaces.

### 6.3 Scenario: Manual User Edit

**User Action**: User manually edits a device description in NetBox

**Reconciliation Logic:**

```python
def reconcile_with_manual_changes(plan):
    """Handle objects with manual modifications."""

    desired_state = plan.get_desired_state()
    current_state = get_current_state(plan.id)

    diff = calculate_diff(desired_state, current_state)

    # Detect manual changes
    manual_changes = []
    for update in diff["update"]:
        obj = update["object"]
        changes = update["changes"]

        # Check if changes are in non-managed fields
        managed_fields = obj.custom_fields.get("diet_managed_fields", [])

        for field, (old_val, new_val) in changes.items():
            if field not in managed_fields:
                # This is a user-managed field, preserve it
                continue
            else:
                # This is a DIET-managed field that was modified
                manual_changes.append({
                    "object": obj,
                    "field": field,
                    "diet_value": new_val,
                    "current_value": old_val,
                    "conflict": True
                })

    if manual_changes:
        # Require user decision
        return {
            "status": "conflict",
            "conflicts": manual_changes,
            "options": {
                "keep_manual": "Preserve current value",
                "apply_diet": "Override with DIET value",
                "unmanage_field": "Remove field from DIET management"
            }
        }
```

**Options for User:**
1. **Preserve manual change**: Unmanage that field going forward
2. **Override with DIET**: Discard manual change, apply plan value
3. **Unmanage object**: Remove from DIET management entirely

### 6.4 Scenario: Delete Server Class

**User Action**: User deletes a server class from plan

**Reconciliation Logic:**

```python
def reconcile_server_class_deletion(plan, deleted_class):
    """Handle deletion of server class."""

    # Find all devices that were generated from this class
    affected_devices = get_managed_devices(
        plan,
        custom_fields__diet_source_class=deleted_class.id
    )

    # Check deletion policy
    policy = plan.deletion_policy

    if policy == DeletionPolicy.WARN or len(affected_devices) > 10:
        # Warn for large deletions
        return {
            "status": "requires_approval",
            "action": "delete_cascade",
            "message": f"Deleting class {deleted_class.name} will remove {len(affected_devices)} devices",
            "affected_objects": {
                "devices": affected_devices,
                "interfaces": count_interfaces(affected_devices),
                "cables": count_cables(affected_devices)
            }
        }
    elif policy == DeletionPolicy.DELETE:
        # Auto-delete if policy allows
        return delete_cascade(affected_devices)
    else:
        # Orphan the objects
        for device in affected_devices:
            device.custom_fields["diet_managed"] = False
            device.save()
```

**Safety Features:**
- Warn for large-scale deletions
- Show cascade impact (cables, interfaces affected)
- Require explicit approval
- Option to orphan instead of delete

---

## 7. Batch Operations

### 7.1 Bulk Renaming

**Pattern**: Process renames in transaction or batch

```python
def bulk_rename(plan, rename_ops):
    """Efficiently rename many devices."""

    # Batch operations for efficiency
    with transaction.atomic():
        for op in rename_ops:
            device = Device.objects.select_for_update().get(id=op["device_id"])
            device.name = op["new_name"]
            device.save()

    # Single bulk update if supported
    # Device.objects.bulk_update(devices, ["name"])
```

### 7.2 Adding Objects to Existing Topology

**Pattern**: Incremental addition without disrupting existing

```python
def add_to_existing_topology(plan, new_objects):
    """Add new objects to existing topology."""

    # Verify no conflicts with existing
    existing = get_managed_objects(plan)
    conflicts = check_conflicts(new_objects, existing)

    if conflicts:
        raise ValidationError(f"Conflicts detected: {conflicts}")

    # Create in dependency order
    for obj_type in ["devices", "interfaces", "cables"]:
        objects_of_type = [o for o in new_objects if o.type == obj_type]
        for obj in objects_of_type:
            create_in_netbox(obj)
```

### 7.3 Removing Obsolete Objects

**Pattern**: Safe deletion with dependency checking

```python
def remove_obsolete_objects(plan, obsolete_objects):
    """Remove objects no longer in plan."""

    # Sort by dependency order (cables → interfaces → devices)
    deletion_order = sort_by_dependencies(obsolete_objects, reverse=True)

    results = {
        "deleted": [],
        "failed": [],
        "skipped": []
    }

    for obj in deletion_order:
        if is_safe_to_delete(obj):
            try:
                delete_from_netbox(obj)
                results["deleted"].append(obj)
            except Exception as e:
                results["failed"].append({"object": obj, "error": str(e)})
        else:
            results["skipped"].append({
                "object": obj,
                "reason": "Has external references"
            })

    return results
```

### 7.4 Recabling Operations

**Pattern**: Replace cables while preserving terminations

```python
def recable_topology(plan, recable_spec):
    """Update cabling based on new pattern."""

    old_cables = recable_spec["old_cables"]
    new_pattern = recable_spec["new_pattern"]

    # Generate new cables based on pattern
    new_cables = generate_cables(plan, new_pattern)

    # Match old to new by terminations
    replacements = []
    for old_cable in old_cables:
        new_cable = find_matching_cable(
            new_cables,
            a_termination=old_cable.a_termination,
            b_termination=old_cable.b_termination
        )

        if new_cable:
            # Check if anything changed
            if cables_differ(old_cable, new_cable):
                replacements.append({
                    "delete": old_cable,
                    "create": new_cable
                })

    # Apply replacements atomically
    with transaction.atomic():
        for r in replacements:
            r["delete"].delete()
            Cable.objects.create(**r["create"])
```

---

## 8. Reconciliation Architecture

### 8.1 Recommended Components

```
┌─────────────────┐
│   DIET Plan     │ (Desired State)
│  (User Input)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Generation      │
│ Engine          │ (Computes desired objects)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Reconciler      │
│                 │
│ ┌─────────────┐ │
│ │   Observe   │ │ Read NetBox
│ └──────┬──────┘ │
│        │        │
│ ┌──────▼──────┐ │
│ │   Analyze   │ │ Calculate diff
│ └──────┬──────┘ │
│        │        │
│ ┌──────▼──────┐ │
│ │   Preview   │ │ Show changes
│ └──────┬──────┘ │
│        │        │
│ ┌──────▼──────┐ │
│ │   Apply     │ │ Update NetBox
│ └──────┬──────┘ │
└────────┼────────┘
         │
         ▼
┌─────────────────┐
│    NetBox       │ (Actual State)
│  (Devices,      │
│   Interfaces,   │
│   Cables)       │
└─────────────────┘
```

### 8.2 Core Classes

```python
class DIETReconciler:
    """Reconcile DIET plans with NetBox state."""

    def __init__(self, plan):
        self.plan = plan
        self.generator = GenerationEngine(plan)
        self.netbox = NetBoxClient()

    def reconcile(self, dry_run=True):
        """Main reconciliation loop."""
        # 1. Observe
        current_state = self.observe()

        # 2. Analyze
        desired_state = self.generator.generate()
        diff = self.analyze(desired_state, current_state)

        # 3. Preview
        preview = self.preview(diff)

        if dry_run:
            return preview

        # 4. Apply
        results = self.apply(diff)

        # 5. Update status
        self.update_plan_status(results)

        return results

    def observe(self):
        """Read current state from NetBox."""
        managed_objects = self.netbox.get_managed_objects(
            plan_id=self.plan.id
        )
        return managed_objects

    def analyze(self, desired, current):
        """Calculate diff between desired and current state."""
        return calculate_diff(desired, current)

    def preview(self, diff):
        """Generate human-readable preview of changes."""
        return format_preview(diff)

    def apply(self, diff):
        """Apply changes to NetBox."""
        return apply_changes(diff)

    def update_plan_status(self, results):
        """Update plan with reconciliation status."""
        self.plan.last_reconciled = timezone.now()
        self.plan.last_reconciliation_status = results["status"]
        self.plan.save()


class GenerationEngine:
    """Generate NetBox objects from DIET plan."""

    def __init__(self, plan):
        self.plan = plan

    def generate(self):
        """Generate complete desired state."""
        devices = self.generate_devices()
        interfaces = self.generate_interfaces(devices)
        cables = self.generate_cables(devices, interfaces)

        return {
            "devices": devices,
            "interfaces": interfaces,
            "cables": cables
        }

    def generate_devices(self):
        """Generate all devices from plan."""
        devices = []

        # Generate spines
        for fabric in self.plan.fabrics.all():
            for i in range(fabric.spine_count):
                devices.append(self.create_spine(fabric, i))

        # Generate leaves
        for leaf_class in self.plan.leaf_classes.all():
            for i in range(leaf_class.quantity):
                devices.append(self.create_leaf(leaf_class, i))

        # Generate servers
        for server_class in self.plan.server_classes.all():
            for i in range(server_class.quantity):
                devices.append(self.create_server(server_class, i))

        return devices

    def create_spine(self, fabric, index):
        """Create a spine device."""
        return {
            "name": fabric.naming_pattern.format(role="spine", index=index),
            "device_type": fabric.spine_device_type,
            "role": "spine",
            "custom_fields": {
                "diet_managed": True,
                "diet_plan_id": self.plan.id,
                "diet_object_id": f"spine-{fabric.id}-{index}",
                "diet_source_fabric": fabric.id
            }
        }
```

### 8.3 Reconciliation Workflow

```python
# In DIET UI or management command

# 1. User modifies plan
plan.server_classes.get(name="compute").quantity = 128
plan.save()

# 2. Preview changes
reconciler = DIETReconciler(plan)
preview = reconciler.reconcile(dry_run=True)

# Show preview to user:
# - 32 devices to create
# - 128 interfaces to create
# - 256 cables to create

# 3. User approves
if user_confirms(preview):
    results = reconciler.reconcile(dry_run=False)

    # Show results:
    # - Created 32 devices
    # - Created 128 interfaces
    # - Created 256 cables
    # - 0 errors
```

---

## 9. Conflict Resolution Strategies

### 9.1 Conflict Types

**Type 1: Field Ownership Conflict**
- DIET wants to update field X
- User manually updated field X
- Both claim ownership

**Resolution:**
```python
def resolve_field_conflict(obj, field, diet_value, user_value):
    """Let user choose resolution."""
    return {
        "conflict_type": "field_ownership",
        "object": obj,
        "field": field,
        "diet_value": diet_value,
        "user_value": user_value,
        "options": [
            {"action": "use_diet", "label": "Apply DIET value"},
            {"action": "use_user", "label": "Keep manual change"},
            {"action": "unmanage", "label": "Remove from DIET management"}
        ]
    }
```

**Type 2: Object Existence Conflict**
- DIET wants to create device X
- Device X already exists (created manually)
- Naming collision

**Resolution:**
```python
def resolve_existence_conflict(desired_obj, existing_obj):
    """Handle naming collision."""
    return {
        "conflict_type": "object_existence",
        "desired": desired_obj,
        "existing": existing_obj,
        "options": [
            {"action": "adopt", "label": "Adopt existing object into DIET"},
            {"action": "rename_existing", "label": "Rename existing and create new"},
            {"action": "skip", "label": "Skip creation"}
        ]
    }
```

**Type 3: Deletion Conflict**
- DIET wants to delete object X
- Object X has external references
- Cascade would affect non-DIET objects

**Resolution:**
```python
def resolve_deletion_conflict(obj, references):
    """Handle deletion with external refs."""
    return {
        "conflict_type": "deletion_blocked",
        "object": obj,
        "references": references,
        "options": [
            {"action": "force_delete", "label": "Delete anyway (breaks refs)"},
            {"action": "orphan", "label": "Remove DIET ownership, keep object"},
            {"action": "skip", "label": "Skip deletion"}
        ]
    }
```

### 9.2 Conflict Resolution UI

**Preview with Conflicts:**

```
Reconciliation Preview for Plan: fabric-a-prod

Summary:
  ✓ 10 devices to create
  ✓ 20 interfaces to create
  ⚠️ 3 conflicts require resolution
  ✓ 5 devices to update

Conflicts:

1. Field Conflict: device "leaf-01" description
   - DIET value: "Leaf switch for fabric A"
   - Current value: "Production leaf - DO NOT MODIFY"
   - Last modified: 2025-12-20 by user@example.com

   Choose action:
   ( ) Apply DIET value
   (•) Keep manual change
   ( ) Unmanage this field

2. Existence Conflict: device "spine-02"
   - DIET wants to create this device
   - Device already exists (created manually 2025-12-15)

   Choose action:
   ( ) Adopt existing device
   (•) Rename existing to "spine-02-manual" and create new
   ( ) Skip creation

3. Deletion Conflict: device "old-leaf-03"
   - Removed from plan, but has external references:
     - IP Address 10.1.2.3 (assigned by IPAM team)
     - Custom field "monitoring_id" (set by monitoring system)

   Choose action:
   ( ) Force delete (breaks references)
   (•) Orphan (remove from DIET, keep in NetBox)
   ( ) Skip deletion

[Resolve Conflicts] [Cancel]
```

---

## 10. Status Reporting

### 10.1 Plan Status Fields

```python
class DIETPlan(models.Model):
    # ... existing fields ...

    # Reconciliation status
    reconciliation_status = models.CharField(
        choices=[
            ("in_sync", "In Sync"),
            ("drift_detected", "Drift Detected"),
            ("conflicts", "Conflicts"),
            ("reconciling", "Reconciling"),
            ("error", "Error")
        ]
    )
    last_reconciled = models.DateTimeField(null=True)
    last_drift_check = models.DateTimeField(null=True)
    drift_summary = models.JSONField(default=dict)
```

### 10.2 Drift Dashboard

```python
def get_drift_summary(plan):
    """Generate drift summary for dashboard."""
    drift = detect_drift(plan)

    return {
        "status": "drift_detected" if drift else "in_sync",
        "last_checked": timezone.now(),
        "summary": {
            "modified_objects": len(drift.get("modified", [])),
            "missing_objects": len(drift.get("missing", [])),
            "orphaned_objects": len(drift.get("orphaned", []))
        },
        "details": drift
    }
```

---

## 11. Implementation Roadmap

### Phase 1: Foundation (MVP)
- [ ] Implement ownership tracking (custom fields)
- [ ] Basic diff calculation (create/update/delete)
- [ ] Preview mode (dry-run)
- [ ] Simple reconciliation for devices only

### Phase 2: Core Features
- [ ] Full three-way merge support
- [ ] Field-level ownership tracking
- [ ] Conflict detection and resolution UI
- [ ] Reconciliation for interfaces and cables

### Phase 3: Advanced
- [ ] Drift detection on schedule
- [ ] Auto-remediation policies
- [ ] Batch operations (rename, scale)
- [ ] Rollback capability

### Phase 4: Production
- [ ] Comprehensive testing at scale
- [ ] Performance optimization
- [ ] Monitoring and alerting
- [ ] Documentation and training

---

## 12. Testing Strategy

### 12.1 Test Scenarios

**Reconciliation Tests:**
```python
class TestReconciliation(TestCase):
    def test_initial_generation(self):
        """Test creating objects from empty state."""
        plan = create_test_plan()
        reconciler = DIETReconciler(plan)

        preview = reconciler.reconcile(dry_run=True)

        assert preview["create"]["devices"] == 10
        assert preview["create"]["interfaces"] == 40
        assert preview["create"]["cables"] == 30

    def test_scale_up(self):
        """Test adding servers to existing topology."""
        plan = create_test_plan(servers=96)
        reconciler = DIETReconciler(plan)
        reconciler.reconcile(dry_run=False)  # Initial generation

        # Scale up
        plan.server_classes.first().quantity = 128
        preview = reconciler.reconcile(dry_run=True)

        assert preview["create"]["devices"] == 32
        assert preview["update"]["devices"] == 0  # Existing unchanged

    def test_rename_pattern(self):
        """Test bulk rename."""
        plan = create_test_plan()
        reconciler = DIETReconciler(plan)
        reconciler.reconcile(dry_run=False)

        # Change naming pattern
        plan.naming_pattern = "leaf-fab{fabric}-{index:03d}"
        preview = reconciler.reconcile(dry_run=True)

        assert preview["update"]["devices"] == 10  # All renamed
        assert preview["create"]["devices"] == 0  # None created

    def test_manual_modification_preserved(self):
        """Test that manual changes are detected."""
        plan = create_test_plan()
        reconciler = DIETReconciler(plan)
        reconciler.reconcile(dry_run=False)

        # Manually modify device
        device = Device.objects.first()
        device.description = "Manual change"
        device.save()

        # Reconcile again
        preview = reconciler.reconcile(dry_run=True)

        assert "conflicts" in preview
        assert preview["conflicts"][0]["type"] == "manual_modification"

    def test_deletion_with_references(self):
        """Test safe deletion with external references."""
        plan = create_test_plan()
        reconciler = DIETReconciler(plan)
        reconciler.reconcile(dry_run=False)

        # Add external reference
        device = Device.objects.first()
        IPAddress.objects.create(address="10.1.1.1", device=device)

        # Remove from plan
        plan.server_classes.first().quantity = 0
        preview = reconciler.reconcile(dry_run=True)

        assert "conflicts" in preview
        assert "external_references" in preview["conflicts"][0]
```

### 12.2 Scale Testing

```python
def test_reconciliation_scale():
    """Test reconciliation at scale."""

    # Test with realistic sizes
    test_cases = [
        {"servers": 96, "racks": 4},
        {"servers": 256, "racks": 8},
        {"servers": 1024, "racks": 32}
    ]

    for case in test_cases:
        plan = create_large_plan(**case)
        reconciler = DIETReconciler(plan)

        # Measure performance
        start = time.time()
        preview = reconciler.reconcile(dry_run=True)
        duration = time.time() - start

        assert duration < 30, f"Preview took {duration}s (too slow)"

        # Apply
        start = time.time()
        results = reconciler.reconcile(dry_run=False)
        duration = time.time() - start

        assert results["errors"] == 0
        assert duration < 300, f"Apply took {duration}s (too slow)"
```

---

## 13. References & Sources

### Kubernetes Operator Patterns
- [GitOps in 2025: From Old-School Updates to the Modern Way | CNCF](https://www.cncf.io/blog/2025/06/09/gitops-in-2025-from-old-school-updates-to-the-modern-way/)
- [Kubernetes Operators in 2025: Best Practices, Patterns, and Real-World Insights](https://outerbyte.com/kubernetes-operators-2025-guide/)
- [Understanding ArgoCD Reconciliation: How It Works, Why It Matters, and Best Practices](https://docs.rafay.co/blog/2025/08/04/understanding-argocd-reconciliation-how-it-works-why-it-matters-and-best-practices/)
- [Reconciliation loop - GitOps with ArgoCD](https://notes.kodekloud.com/docs/GitOps-with-ArgoCD/ArgoCD-Intermediate/Reconciliation-loop)
- [Controller reconcile function | Kube by Example](https://kubebyexample.com/learning-paths/operator-framework/operator-sdk-go/controller-reconcile-function)
- [Hands-on Kubernetes Operator Development: Reconcile loop](https://www.codereliant.io/p/hands-on-kubernetes-operator-development-part-2)
- [Good Practices - The Kubebuilder Book](https://book.kubebuilder.io/reference/good-practices)
- [Creating Custom Kubernetes Controllers](https://binaryscripts.com/kubernetes/2025/03/27/creating-custom-kubernetes-controllers-automating-complex-application-workflows.html)

### Three-Way Merge & Field Management
- [Helm 3 Explained: Key Features & Differences from Helm 2](https://devops.io/blog/changes-introduced-in-helm3/)
- [Server-Side Apply | Kubernetes](https://kubernetes.io/docs/reference/using-api/server-side-apply/)
- [Kubernetes Apply: Client-Side vs. Server-Side](https://support.tools/kubernetes-apply-client-side-vs-server-side/)
- [Server Side Apply Is Great And You Should Be Using It](https://kubernetes.io/blog/2022/10/20/advanced-server-side-apply/)

### Drift Detection
- [Understanding & Detecting Infrastructure Drift](https://scalr.com/learning-center/understanding-detecting-infrastructure-drift-part-1/)
- [Config Drift Detection: Top Open Source Tools for 2025](https://www.ai-infra-link.com/mastering-config-drift-detection-top-open-source-tools-for-2025/)
- [Take Infrastructure Drift Under Control](https://medium.com/@treezio/take-infrastructure-drift-under-control-before-it-becomes-a-production-incident-449a6a333688)
- [Infrastructure Drift Detection | How to Fix It With IaC Tool](https://spacelift.io/blog/drift-detection)
- [Detecting and Managing Drift with Terraform](https://www.hashicorp.com/en/blog/detecting-and-managing-drift-with-terraform)

### Terraform State Management
- [Use refresh-only mode to sync Terraform state](https://developer.hashicorp.com/terraform/tutorials/state/refresh)
- [Manage resource drift | Terraform](https://developer.hashicorp.com/terraform/tutorials/state/resource-drift)
- [Terraform Refresh Command: Examples and Best Practices](https://www.env0.com/blog/terraform-refresh-command)
- [Terraform Drift Detection and Remediation](https://spacelift.io/blog/terraform-drift-detection)
- [Terraform Plan Command Explained](https://www.npblue.com/cloud/terraform/terraform-plan)

### Garbage Collection
- [Garbage Collection | Kubernetes](https://kubernetes.io/docs/concepts/architecture/garbage-collection/)
- [Kubernetes Garbage Collection: Challenges & Best Practices](https://www.groundcover.com/learn/storage/kubernetes-garbage-collection)
- [Deletion and Garbage Collection of Kubernetes Objects](https://thenewstack.io/deletion-garbage-collection-kubernetes-objects/)

### Declarative Systems & GitOps
- [GitOps for Java Applications: Continuous Delivery Reimagined](https://www.javacodegeeks.com/2025/12/gitops-for-java-applications-continuous-delivery-reimagined.html)
- [From Manual to Automated Database Schema Migrations](https://atlasgo.io/blog/2025/05/11/auto-vs-manual)
- [Enterprise Kubernetes Operators 2025](https://support.tools/post/enterprise-kubernetes-operators-comprehensive-development-guide-2025/)
- [Best of 2025: The Evolution Of Kubernetes Workload Patterns](https://cloudnativenow.com/editorial-calendar/best-of-2025/the-evolution-of-kubernetes-workload-patterns-2/)

---

## 14. Conclusion

**Key Takeaways:**

1. **Adopt Kubernetes-style reconciliation loop**: Observe → Analyze → Act pattern with idempotent operations

2. **Implement field-level ownership tracking**: Use custom fields to track which fields DIET manages vs user-managed

3. **Preview before apply**: Always show users what will change (Terraform plan style)

4. **Handle drift gracefully**: Detect manual changes and offer resolution options rather than blindly overwriting

5. **Safe deletion**: Check for external references, require approval for large deletions, offer orphan option

6. **Stable identity**: Use deterministic IDs for DIET objects so renaming doesn't break tracking

7. **Batch operations**: Support efficient bulk updates for scale operations

8. **Comprehensive testing**: Test reconciliation at scale with realistic topology sizes

**Recommended Next Steps:**

1. Implement basic ownership tracking using NetBox custom fields
2. Build diff calculation engine for devices
3. Add preview mode to show changes before applying
4. Extend to interfaces and cables
5. Add conflict detection and resolution UI
6. Implement drift detection on schedule
7. Add comprehensive test coverage at scale

This reconciliation strategy provides a robust foundation for managing the relationship between DIET plans and NetBox objects, enabling users to work at scale while maintaining consistency and safety.
