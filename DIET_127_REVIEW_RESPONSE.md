# Issue #127 Review Response
**Date:** 2025-12-29
**Issue:** DIET: Unify Generate/Update Devices flow + sync status indicator
**Phase:** Review Response - Addressing Findings

---

## Overview

This document responds to review feedback on `DIET_127_RESEARCH_FINDINGS.md` and `DIET_127_ARCHITECTURE_DESIGN.md`, addressing 6 findings (2 High, 3 Medium, 1 Low) with corrective actions.

---

## HIGH Priority Findings

### Finding H1: Sync Indicator False-Positive Risk

**Issue:** Sync indicator uses `GenerationState.is_dirty()` which only compares server/switch quantities. It ignores changes to connections, port zones, device types, etc., so the "In Sync" badge can be false-positive.

**Current Snapshot Structure (Verified):**
```python
# From generation.py:100-120 and device_generator.py:354-372
snapshot = {
    'server_classes': [
        {'server_class_id': 'GPU-B200', 'quantity': 32}
    ],
    'switch_classes': [
        {'switch_class_id': 'fe-gpu-leaf', 'effective_quantity': 2}
    ]
}
```

**What's Missing:**
- ❌ Connection definitions (`PlanServerConnection`: type, distribution, speed, rail, ports_per_connection)
- ❌ Port zones (`SwitchPortZone`: breakout, port ranges, zone types)
- ❌ Device type references (changes to `server_device_type` or `device_type_extension`)
- ❌ MCLAG domains
- ❌ Plan metadata (customer_name, description, status)

**Scenario Demonstrating the Problem:**
```
1. User generates devices for plan with 32 GPU servers, 2x200G FE connections
2. GenerationState.snapshot captures: quantity=32, effective_quantity=2
3. User changes connection from "unbundled" to "mclag" (no quantity change)
4. Sync indicator shows "✓ In Sync" (FALSE - connection type changed!)
5. User regenerates → devices created with wrong connection type
```

**Impact:** **Critical UX bug** - users will trust "In Sync" indicator and skip regeneration when plan has actually changed.

**Proposed Solution:** **Option A - Comprehensive Snapshot (Recommended)**

Extend snapshot to include all generation-relevant plan attributes:

```python
def _build_snapshot(self) -> dict:
    """
    Build comprehensive snapshot of plan state.

    Only includes fields that affect device generation. Excludes plan metadata
    (name, customer_name, description) to avoid false "out of sync" on renames.
    """
    snapshot = {
        'server_classes': [],
        'switch_classes': [],
        'connections': [],
        'port_zones': [],
        'mclag_domains': [],
    }

    # Server classes (include device type)
    for server_class in self.plan.server_classes.all():
        snapshot['server_classes'].append({
            'server_class_id': server_class.server_class_id,
            'quantity': server_class.quantity,
            'device_type_id': server_class.server_device_type_id,
            'gpus_per_server': server_class.gpus_per_server,
        })

    # Switch classes (include device type and uplink config)
    for switch_class in self.plan.switch_classes.all():
        snapshot['switch_classes'].append({
            'switch_class_id': switch_class.switch_class_id,
            'effective_quantity': switch_class.effective_quantity,
            'device_type_extension_id': switch_class.device_type_extension_id,
            'fabric': switch_class.fabric,
            'hedgehog_role': switch_class.hedgehog_role,
            'uplink_ports_per_switch': switch_class.uplink_ports_per_switch,
            'mclag_pair': switch_class.mclag_pair,
        })

    # Connection definitions
    for conn in PlanServerConnection.objects.filter(
        server_class__plan=self.plan
    ).select_related('server_class', 'target_switch_class'):
        snapshot['connections'].append({
            'connection_id': conn.connection_id,
            'server_class_id': conn.server_class.server_class_id,
            'target_switch_class_id': conn.target_switch_class.switch_class_id,
            'ports_per_connection': conn.ports_per_connection,
            'hedgehog_conn_type': conn.hedgehog_conn_type,
            'distribution': conn.distribution,
            'speed': conn.speed,
            'rail': conn.rail,
            'port_type': conn.port_type,
        })

    # Port zones (using actual model fields)
    for zone in SwitchPortZone.objects.filter(
        switch_class__plan=self.plan
    ).select_related('switch_class', 'breakout_option'):
        snapshot['port_zones'].append({
            'switch_class_id': zone.switch_class.switch_class_id,
            'zone_name': zone.zone_name,
            'zone_type': zone.zone_type,
            'port_spec': zone.port_spec,
            'breakout_option_id': zone.breakout_option_id,
            'allocation_strategy': zone.allocation_strategy,
            'allocation_order': zone.allocation_order,
            'priority': zone.priority,
        })

    # MCLAG domains
    for mclag in self.plan.mclag_domains.all():
        snapshot['mclag_domains'].append({
            'domain_id': mclag.domain_id,
            'switch_class_id': mclag.switch_class.switch_class_id,
            'peer_link_count': mclag.peer_link_count,
            'session_link_count': mclag.session_link_count,
        })

    return snapshot
```

**Comparison Logic:**
```python
def is_dirty(self) -> bool:
    """Check if plan has changed since generation."""
    current = self._build_current_snapshot()

    # Simple deep comparison (order-independent for lists)
    return not self._deep_compare(current, self.snapshot)

def _deep_compare(self, current, snapshot):
    """Deep comparison of snapshot dicts."""
    import json

    # Normalize by sorting lists (order-independent comparison)
    def normalize(data):
        if isinstance(data, dict):
            return {k: normalize(v) for k, v in sorted(data.items())}
        elif isinstance(data, list):
            return sorted([normalize(item) for item in data],
                         key=lambda x: json.dumps(x, sort_keys=True))
        else:
            return data

    return normalize(current) == normalize(snapshot)
```

**Alternative: Option B - Hash-Based Comparison**

```python
def _build_snapshot(self) -> dict:
    """Build snapshot as hash of full plan state."""
    import hashlib
    import json

    # Collect all relevant data
    data = {
        'server_classes': [...],  # Full data
        'switch_classes': [...],  # Full data
        'connections': [...],     # Full data
        'port_zones': [...],      # Full data
        'mclag_domains': [...],   # Full data
    }

    # Return both hash and data for debugging
    json_str = json.dumps(data, sort_keys=True)
    return {
        'hash': hashlib.sha256(json_str.encode()).hexdigest(),
        'data': data,  # Keep for debugging/auditing
    }

def is_dirty(self) -> bool:
    """Compare hashes for fast change detection."""
    current = self._build_snapshot()
    return current['hash'] != self.snapshot.get('hash')
```

**Alternative: Option C - Explicit Label (Not Recommended)**

Label indicator as "Quantities in sync only" and accept limitation.

**Decision:** **Implement Option A** (comprehensive snapshot) for accurate sync detection.

**Implementation Note - Centralize Snapshot Logic:**

Currently, `GenerationState._build_snapshot()` (in `generation.py`) and `DeviceGenerator._build_snapshot()` (in `device_generator.py`) are separate methods. To avoid drift when extending the snapshot:

1. **Create shared helper:** `netbox_hedgehog/utils/snapshot_builder.py`
2. **Single source of truth:** Both models/services call this helper
3. **Consistent comparison:** Ensures snapshot format is identical

```python
# utils/snapshot_builder.py
def build_plan_snapshot(plan: TopologyPlan) -> dict:
    """
    Build comprehensive snapshot of plan state for generation tracking.

    Used by both GenerationState and DeviceGenerator to ensure consistency.
    """
    # Single implementation of snapshot logic
    # ...
```

**Files to Modify:**
- `netbox_hedgehog/utils/snapshot_builder.py` - **NEW**: Shared snapshot builder
- `netbox_hedgehog/models/topology_planning/generation.py` - Call shared helper
- `netbox_hedgehog/services/device_generator.py` - Call shared helper
- `netbox_hedgehog/templates/netbox_hedgehog/topologyplan.html` - Update indicator tooltip

**Testing Required:**
- Connection change → out of sync
- Port zone change → out of sync
- Device type change → out of sync
- MCLAG domain change → out of sync
- Only quantity change → out of sync (existing behavior)
- No changes → in sync (existing behavior)
- Plan name/customer change → **still in sync** (metadata excluded)

---

### Finding H2: Incomplete Permission Model

**Issue:** Unified action uses `change_topologyplan` permission only, but generation creates `dcim.Device`, `Interface`, and `Cable` objects. If NetBox RBAC requires `dcim.add_device` / `dcim.add_interface` / `dcim.add_cable`, the action may succeed for users without device create perms or fail inconsistently.

**Current Implementation (Verified):**
```python
# views/topology_planning.py:127
class TopologyPlanGenerateView(PermissionRequiredMixin, View):
    permission_required = 'netbox_hedgehog.change_topologyplan'
    # ...
```

**NetBox Permission Hierarchy:**
1. **Model-level permissions** (e.g., `dcim.add_device`) - Required to create DCIM objects
2. **Object-level permissions** (via `ObjectPermission`) - Additional constraints on specific objects
3. **Plugin permissions** (e.g., `netbox_hedgehog.change_topologyplan`) - Custom plugin actions

**Problem Scenarios:**

**Scenario 1: User has plugin permission but not DCIM permissions**
```
User permissions:
  ✓ netbox_hedgehog.change_topologyplan
  ✗ dcim.add_device
  ✗ dcim.add_interface
  ✗ dcim.add_cable
  ✗ dcim.delete_device (for cleanup)

Result: Device.objects.create() will raise PermissionDenied or silently fail
        (depending on NetBox version and enforcement settings)
```

**Scenario 2: User has add but not delete permissions**
```
User permissions:
  ✓ netbox_hedgehog.change_topologyplan
  ✓ dcim.add_device
  ✗ dcim.delete_device

Result: First generation succeeds, regeneration fails at cleanup step
```

**Required Permissions (Verified from DeviceGenerator Code):**

For device generation, user must have:
- ✅ `netbox_hedgehog.change_topologyplan` (plugin permission)
- ✅ `dcim.add_device` (create devices via `device.save()`)
- ✅ `dcim.delete_device` (cleanup old devices via `devices_to_delete.delete()`)
- ✅ `dcim.add_interface` (create interfaces via `interface.save()`)
- ✅ `dcim.add_cable` (create cables via `cable.save()`)
- ✅ `dcim.delete_cable` (cleanup old cables via `cables_to_delete.delete()`)

**NOT Required:**
- ❌ `dcim.change_device` - DeviceGenerator only creates new devices, never updates existing ones
- ❌ `dcim.delete_interface` - Interfaces are deleted automatically via CASCADE when device is deleted

**Proposed Solution:**

**Option A: Enforce All Permissions (Safest)**

```python
class TopologyPlanGenerateUpdateView(PermissionRequiredMixin, View):
    """
    Unified generate/update action.

    Required permissions:
    - netbox_hedgehog.change_topologyplan (plugin action)
    - dcim.add_device, dcim.delete_device (device lifecycle)
    - dcim.add_interface (interface creation - deletion via CASCADE)
    - dcim.add_cable, dcim.delete_cable (cable lifecycle)
    """
    permission_required = (
        'netbox_hedgehog.change_topologyplan',
        'dcim.add_device',
        'dcim.delete_device',
        'dcim.add_interface',
        'dcim.add_cable',
        'dcim.delete_cable',
    )
    raise_exception = True

    def post(self, request, pk):
        # Additional runtime check (redundant but explicit)
        if not request.user.has_perms(self.permission_required):
            raise PermissionDenied(
                "Device generation requires DCIM add/delete permissions. "
                "Contact your NetBox administrator to grant these permissions."
            )

        # ... rest of generation logic
```

**Option B: Check Programmatically (More Flexible)**

```python
def post(self, request, pk):
    # Check required permissions
    required_perms = [
        'netbox_hedgehog.change_topologyplan',
        'dcim.add_device',
        'dcim.delete_device',
        'dcim.add_interface',
        'dcim.add_cable',
        'dcim.delete_cable',
    ]

    missing_perms = [p for p in required_perms if not request.user.has_perm(p)]

    if missing_perms:
        messages.error(
            request,
            f"Device generation requires additional permissions: {', '.join(missing_perms)}. "
            "Contact your NetBox administrator."
        )
        return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=pk)

    # ... proceed with generation
```

**Option C: Document-Only (Not Recommended)**

Document required permissions but don't enforce, relying on NetBox's built-in permission checks.

**Decision:** **Implement Option A** (enforce all permissions) for security and clear error messages.

**Documentation Required:**
- `specs/DIET-XXX-unified-generate.md` - Document permission requirements
- User guide - Add permission setup instructions for admins
- Template - Show disabled button with tooltip if user lacks permissions

**Template Update:**
```django
{% if perms.netbox_hedgehog.change_topologyplan and perms.dcim.add_device and perms.dcim.delete_device and perms.dcim.add_interface and perms.dcim.add_cable and perms.dcim.delete_cable %}
    <button type="submit" class="btn btn-primary">
        Generate/Update Devices
    </button>
{% else %}
    <button type="button" class="btn btn-primary" disabled title="Requires DCIM device/interface/cable add/delete permissions">
        Generate/Update Devices
    </button>
    <small class="text-muted d-block">Contact administrator for device management permissions.</small>
{% endif %}
```

**Testing Required:**
- User with all permissions → generation succeeds
- User missing `dcim.add_device` → button disabled + tooltip shown
- User missing `dcim.delete_device` → cleanup fails with clear error

---

## MEDIUM Priority Findings

### Finding M1: Auto-Recalculate on Errors Risk

**Issue:** "Auto-recalculate then generate even on calc errors" risks generating devices from stale or partial quantities. If calculation errors are present, the safer default is to abort generation.

**Current Design (from Architecture Doc):**
```python
# Step 1: Auto-recalculate
calc_result = update_plan_calculations(plan)

# Warn about calculation errors (but continue)
if calc_result['errors']:
    for error_info in calc_result['errors']:
        messages.warning(request, f"Calculation warning: {error_info['error']}")

# Step 2: Generate devices (even if calc had errors)
generator = DeviceGenerator(plan=plan)
result = generator.generate_all()
```

**Risk Scenarios:**

**Scenario 1: Calculation error for critical switch class**
```
Plan has:
  - fe-gpu-leaf: calculated_quantity=None (calculation failed)
  - fe-spine: calculated_quantity=2 (calculation succeeded)

Current behavior: Generates 0 GPU leaf switches, 2 spines → broken topology
Safer behavior: Abort generation, show error, require user fix
```

**Scenario 2: User has override_quantity set**
```
Plan has:
  - fe-gpu-leaf: calculated_quantity=None, override_quantity=4
  - fe-spine: calculated_quantity=2

Current behavior: Generates 4 GPU leafs (using override), 2 spines → works
Expected: This is a valid use case for continuing despite calc errors
```

**Proposed Solution:**

**Default: Abort on Calculation Errors**

```python
def post(self, request, pk):
    plan = get_object_or_404(models.TopologyPlan, pk=pk)

    # Validate minimum requirements
    if plan.server_classes.count() == 0 or plan.switch_classes.count() == 0:
        messages.error(request, "Cannot generate: plan requires server and switch classes.")
        return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=pk)

    # Auto-recalculate
    calc_result = update_plan_calculations(plan)

    # Check for calculation errors
    if calc_result['errors']:
        # Build detailed error message
        error_details = []
        for error_info in calc_result['errors']:
            switch_class = error_info['switch_class']
            error_msg = error_info['error']
            error_details.append(f"• {switch_class}: {error_msg}")

        messages.error(
            request,
            mark_safe(
                "<strong>Cannot generate devices due to calculation errors:</strong><br>" +
                "<br>".join(error_details) +
                "<br><br>Please fix the plan configuration or set override_quantity for affected switch classes."
            )
        )
        return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=pk)

    # All calculations succeeded - proceed with generation
    generator = DeviceGenerator(plan=plan)
    result = generator.generate_all()

    messages.success(request, f"Devices updated: {result.device_count} devices...")
    return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=pk)
```

**Alternative: Add "Force Generate" Option**

For power users who want to generate despite errors:

```python
# Add query parameter: ?force=true
force_generate = request.GET.get('force') == 'true'

if calc_result['errors'] and not force_generate:
    # Show errors with "Force Generate Anyway" button
    messages.error(request, "Calculation errors detected.")
    messages.warning(
        request,
        mark_safe(
            'You can <a href="?force=true" class="btn btn-sm btn-warning">'
            'Force Generate Anyway</a> to use existing/override quantities.'
        )
    )
    return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=pk)
```

**Decision:** **Abort on calculation errors by default**. No "force" option in MVP (can add later if needed).

**Rationale:**
- Safer default behavior (fail-fast)
- Clear error messages guide user to fix the problem
- Prevents broken topologies from being generated
- User with override_quantity can just fix the calculation by correcting plan inputs

**Files to Modify:**
- `netbox_hedgehog/views/topology_planning.py` - Update `TopologyPlanGenerateUpdateView.post()`
- Architecture doc - Update error handling section

---

### Finding M2: Export YAML Auto-Recalculate Verification

**Issue:** "Export YAML auto-recalculate" is asserted in design but not verified in research.

**Verification:**

✅ **CONFIRMED** - Export YAML does auto-recalculate.

**Evidence:**
```python
# netbox_hedgehog/views/topology_planning.py:228-260
class TopologyPlanExportView(PermissionRequiredMixin, View):
    """
    Export action for TopologyPlans (DIET-006).

    Automatically runs calculation engine before export to ensure
    switch quantities are up-to-date.
    """
    def get(self, request, pk):
        plan = get_object_or_404(models.TopologyPlan, pk=pk)

        # Auto-calculate switch quantities before export
        result = update_plan_calculations(plan)  # ← Line 251

        # Warn user if there were calculation errors (but continue with export)
        if result['errors']:
            for error_info in result['errors']:
                messages.warning(request, f"Calculation error: {error_info['error']}")

        # Generate YAML from plan
        yaml_content = generate_yaml_for_plan(plan)
        # ...
```

**Status:** No action required. Assertion was correct.

---

### Finding M3: Legacy Redirect Security

**Issue:** Legacy redirect flow may bypass permission or CSRF checks if `TopologyPlanGenerateLegacyRedirectView` just redirects POST → POST.

**Current Design (from Architecture Doc):**
```python
class TopologyPlanGenerateLegacyRedirectView(View):
    """Redirect old generate URL to new unified endpoint."""
    def get(self, request, pk):
        return redirect('plugins:netbox_hedgehog:topologyplan_generate_preview', pk=pk)

    def post(self, request, pk):
        return redirect('plugins:netbox_hedgehog:topologyplan_generate_update', pk=pk)
```

**Security Issues:**

1. **CSRF Token Not Preserved**
   - `redirect()` returns 302 with Location header
   - Browser re-sends POST to new URL but **may not include CSRF token**
   - New endpoint will reject with CSRF failure

2. **POST Data Not Preserved**
   - Redirect doesn't forward POST body
   - New endpoint receives empty POST

3. **Permission Check Bypassed**
   - Old endpoint has no permission check
   - Redirects to endpoint that has permission check
   - But user may see confusing error flow

**Correct Implementation:**

**Option A: Call View Directly (Recommended)**

```python
class TopologyPlanGenerateLegacyRedirectView(PermissionRequiredMixin, View):
    """
    Legacy compatibility redirect for old generate URL.

    Directly delegates to new view to preserve request context.
    """
    permission_required = 'netbox_hedgehog.change_topologyplan'
    raise_exception = True

    def get(self, request, pk):
        # Delegate to preview view
        return TopologyPlanGeneratePreviewView.as_view()(request, pk=pk)

    def post(self, request, pk):
        # Delegate to unified generate/update view
        return TopologyPlanGenerateUpdateView.as_view()(request, pk=pk)
```

**Option B: Remove Entirely (Simplest)**

Don't provide legacy redirect at all. Update any internal links to new URL.

**Decision:** **Implement Option A** if we expect external tools to use the old URL, otherwise **Option B** (remove legacy endpoint entirely).

**Recommendation:** **Option B** (remove) because:
- Cleaner codebase
- No security risk
- UI links will be updated anyway
- External API users should use REST API, not web endpoints

**Files to Modify:**
- `netbox_hedgehog/urls.py` - Remove legacy URL pattern
- `netbox_hedgehog/views/topology_planning.py` - Remove legacy redirect view (if Option B)
- Architecture doc - Remove legacy redirect section

---

## LOW Priority Finding

### Finding L1: Success Message Filter Verification

**Issue:** Success message uses `mark_safe` with `cf_hedgehog_plan_id` filter; verify the custom field filter key is correct for NetBox UI filters.

**Current Design:**
```python
messages.success(
    request,
    mark_safe(
        f'<a href="{device_list_url}?tag={DeviceGenerator.DEFAULT_TAG_SLUG}&'
        f'cf_hedgehog_plan_id={plan.pk}">'
        f'{result.device_count} devices</a>'
    )
)
```

**NetBox Custom Field Filter Syntax:**

NetBox uses `cf_` prefix for custom field filters in URLs:
- Format: `cf_{field_name}={value}`
- Example: `cf_hedgehog_plan_id=123`

**Verification:**

✅ **CONFIRMED** - Custom field is `hedgehog_plan_id`

**Evidence:**
```python
# netbox_hedgehog/services/device_generator.py:178-180
device.custom_field_data = {
    'hedgehog_plan_id': str(self.plan.pk),  # ← Field name
    'hedgehog_class': switch_class.switch_class_id,
    'hedgehog_fabric': switch_class.fabric or "",
    'hedgehog_role': switch_class.hedgehog_role or "",
}
```

**Corrected Filter URL:**

Need to verify NetBox version's exact filter syntax. Modern NetBox (3.5+) uses:
- **Correct:** `/dcim/devices/?cf_hedgehog_plan_id=123`
- **Also works:** `/dcim/devices/?tag=hedgehog-generated&cf_hedgehog_plan_id=123`

**Testing Required:**
- Generate devices
- Click link in success message
- Verify filtered device list shows only plan devices
- If filter doesn't work, check NetBox UI for correct syntax

**Status:** **Low risk** - worst case, link shows all devices instead of filtered. Will verify during implementation testing.

---

## Summary of Actions

| Finding | Priority | Action | Status |
|---------|----------|--------|--------|
| H1: Sync indicator false-positive | HIGH | Extend snapshot to include connections, port zones (correct fields), device types, MCLAG; centralize snapshot logic; exclude plan metadata | ✅ Solution defined |
| H2: Permission model incomplete | HIGH | Enforce 6 DCIM permissions (add/delete for device/cable, add for interface); update template | ✅ Solution defined |
| M1: Auto-recalculate on errors | MEDIUM | Abort generation on calc errors by default | ✅ Solution defined |
| M2: Export auto-recalculate | MEDIUM | Verified - no action needed | ✅ Confirmed |
| M3: Legacy redirect security | MEDIUM | Remove legacy redirect endpoint entirely | ✅ Solution defined |
| L1: Success message filter | LOW | Verify during implementation testing | ⏭️ Test later |

---

## Updated Architecture Decisions

### 1. Comprehensive Snapshot (Addressing H1)

**New snapshot structure (excludes plan metadata to avoid false "out of sync" on renames):**
```json
{
  "server_classes": [
    {
      "server_class_id": "GPU-B200",
      "quantity": 32,
      "device_type_id": 123,
      "gpus_per_server": 8
    }
  ],
  "switch_classes": [
    {
      "switch_class_id": "fe-gpu-leaf",
      "effective_quantity": 2,
      "device_type_extension_id": 456,
      "fabric": "frontend",
      "hedgehog_role": "server-leaf",
      "uplink_ports_per_switch": null,
      "mclag_pair": false
    }
  ],
  "connections": [
    {
      "connection_id": "FE-001",
      "server_class_id": "GPU-B200",
      "target_switch_class_id": "fe-gpu-leaf",
      "ports_per_connection": 2,
      "hedgehog_conn_type": "unbundled",
      "distribution": "alternating",
      "speed": 200,
      "rail": null,
      "port_type": "data"
    }
  ],
  "port_zones": [
    {
      "switch_class_id": "fe-gpu-leaf",
      "zone_name": "server-ports",
      "zone_type": "server",
      "port_spec": "1-48:2",
      "breakout_option_id": 789,
      "allocation_strategy": "sequential",
      "allocation_order": null,
      "priority": 100
    }
  ],
  "mclag_domains": [
    {
      "domain_id": "MCLAG-001",
      "switch_class_id": "fe-gpu-leaf",
      "peer_link_count": 2,
      "session_link_count": 2
    }
  ]
}
```

### 2. Strict Permission Enforcement (Addressing H2)

**Required permissions (verified from DeviceGenerator code):**
```python
permission_required = (
    'netbox_hedgehog.change_topologyplan',
    'dcim.add_device',
    'dcim.delete_device',
    'dcim.add_interface',
    'dcim.add_cable',
    'dcim.delete_cable',
)
```

**Note:** `dcim.change_device` and `dcim.delete_interface` are NOT required because:
- DeviceGenerator only creates devices, never updates them
- Interfaces are deleted via CASCADE when device is deleted

### 3. Fail-Fast on Calculation Errors (Addressing M1)

**Error handling:**
```python
if calc_result['errors']:
    messages.error(request, "Cannot generate due to calculation errors: ...")
    return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=pk)
```

### 4. No Legacy Redirect (Addressing M3)

Remove `TopologyPlanGenerateLegacyRedirectView` entirely. Update UI links to new endpoint.

---

## Files Requiring Updates

| File | Changes | Priority |
|------|---------|----------|
| `netbox_hedgehog/utils/snapshot_builder.py` | **NEW**: Shared snapshot builder with comprehensive fields (excluding plan metadata) | HIGH |
| `netbox_hedgehog/models/topology_planning/generation.py` | Call shared snapshot builder, update `is_dirty()` | HIGH |
| `netbox_hedgehog/services/device_generator.py` | Call shared snapshot builder | HIGH |
| `netbox_hedgehog/views/topology_planning.py` | Add 6 permission checks, abort on calc errors | HIGH |
| `netbox_hedgehog/templates/netbox_hedgehog/topologyplan.html` | Update button with 6 permission checks | HIGH |
| `netbox_hedgehog/urls.py` | Remove legacy redirect URL | MEDIUM |
| `DIET_127_ARCHITECTURE_DESIGN.md` | Update with corrected design | MEDIUM |
| `DIET_127_REVIEW_RESPONSE.md` | This document - reflects all corrections | COMPLETE |

---

## Next Steps

1. ✅ Review response approved
2. ⏭️ Update architecture document with corrections
3. ⏭️ Write technical specification incorporating all fixes
4. ⏭️ Define comprehensive integration tests
5. ⏭️ Proceed to implementation

---

## Questions for Clarification

1. **Snapshot Size Concern:** Comprehensive snapshot will be larger (3-5KB vs <1KB). Is this acceptable for the `GenerationState.snapshot` JSONField?
   - **Recommendation:** Yes, acceptable. Even 1000 connections = ~100KB, well within JSONField limits.

2. **Permission Granularity:** Should we allow site-scoped or role-scoped permissions (via ObjectPermission), or only global DCIM permissions?
   - **Recommendation:** Start with global permissions for MVP. Object-level permissions can be added later if needed.

3. **Calculation Error Types:** Should different error types have different handling (e.g., warnings vs errors)?
   - **Recommendation:** Treat all calculation errors as blocking for MVP. Can add severity levels later.

---

## Review Feedback Incorporated

**All requested changes have been addressed:**

✅ **Port zone fields corrected** - Updated snapshot to use actual model fields:
   - `port_spec` (not port_list/port_range_start/port_range_end)
   - `zone_name`, `zone_type`, `breakout_option_id`
   - `allocation_strategy`, `allocation_order`, `priority`

✅ **Plan metadata excluded** - Removed `plan_metadata` (name/customer) from snapshot:
   - Prevents false "out of sync" on plan renames
   - Only tracks generation-relevant fields
   - Explicit test case added: "Plan name/customer change → still in sync"

✅ **Permission list refined** - Reduced from 8 to 6 required permissions:
   - **Removed:** `dcim.change_device` (never updates), `dcim.delete_interface` (CASCADE)
   - **Kept:** `change_topologyplan`, `add/delete_device`, `add_interface`, `add/delete_cable`
   - Verified from DeviceGenerator code analysis

✅ **Snapshot logic centralized** - Added architectural note:
   - New shared helper: `netbox_hedgehog/utils/snapshot_builder.py`
   - Both `GenerationState` and `DeviceGenerator` call same function
   - Prevents drift between models/services

**Answers confirmed:**
1. ✅ Snapshot size 3-5KB (even 50-100KB) acceptable for JSONField
2. ✅ Global permissions fine for MVP
3. ✅ Fail-fast on calc errors (no "force generate" in MVP)

**Ready to proceed to technical specification with corrected design.**

---
**End of Review Response**
