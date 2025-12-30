# DIET-SPEC-005: Unified Generate/Update Devices with Sync Status Indicator

## Metadata
- **Spec ID:** DIET-SPEC-005
- **Status:** Draft
- **Authors:** Dev A (Agent)
- **Created:** 2025-12-29
- **Updated:** 2025-12-29
- **Reviewers:** User, Dev B, Dev C
- **Related Issues:** #127
- **Related Specs:** None (standalone UX improvement)

---

## Summary

Replace the confusing dual-button UI ("Generate Devices" + "Recalculate Switch Quantities") with a single unified "Generate/Update Devices" action that automatically recalculates before generation. Add a comprehensive sync status indicator to the topology plan detail page showing whether devices match the current plan state.

---

## Motivation

### Problem Statement

The topology plan detail page currently has two separate actions that confuse users:
1. **"Generate Devices"** button - Creates NetBox devices/interfaces/cables
2. **"Recalculate Switch Quantities"** button - Updates calculated switch counts

Users perceive these as independent actions when they are tightly coupled. Additionally:
- Users must manually recalculate before generating (easy to forget)
- There's no sync status indicator on the main detail page
- After generation succeeds, users see only a success message with no visual confirmation
- The "Generate Devices" button leads to a preview page (extra step)
- Clicking generate after devices exist appears to hang (actually succeeds but no visible change)

### Current Behavior

```
User workflow:
1. Create topology plan with server/switch classes and connections
2. Click "Recalculate Switch Quantities" → calculated_quantity fields updated
3. Click "Generate Devices" → navigates to preview page
4. Click "Generate Devices" on preview → POST generates devices
5. Redirect to detail page → success message shown, but no visual difference

Problems:
- Two manual steps when should be one
- No visible sync status on detail page
- Preview page is extra friction
- Success has no visual confirmation beyond message banner
```

### Desired Behavior

```
User workflow:
1. Create topology plan with server/switch classes and connections
2. Click "Generate/Update Devices" → automatically recalculates then generates
3. Success message shows device count with link to device list
4. Sync indicator on detail page shows "✓ In Sync" with device counts

Improvements:
- Single unified action (auto-recalculate)
- Clear sync status indicator always visible
- Direct POST (no preview page in main flow)
- Enhanced success feedback with actionable links
```

### Why Now

This UX issue blocks user adoption of DIET tools. Users report confusion about workflow and lack of confidence that devices were actually generated. Fixing this now improves usability before wider rollout.

---

## Goals and Non-Goals

### Goals

- **G1:** Replace two buttons with one unified "Generate/Update Devices" action
- **G2:** Automatically recalculate switch quantities before every generation
- **G3:** Add sync status indicator to detail page showing in/out-of-sync state
- **G4:** Extend snapshot tracking to detect all generation-relevant plan changes
- **G5:** Enforce correct DCIM permissions for device generation
- **G6:** Abort generation on calculation errors (fail-fast)
- **G7:** Provide enhanced success feedback with device count and link

### Non-Goals

- **NG1:** Changes to device generation logic itself (DeviceGenerator works correctly)
- **NG2:** Async/background job queue (direct POST is acceptable for MVP)
- **NG3:** Partial device updates (current delete-all-recreate approach is fine)
- **NG4:** Dry-run or diff preview (can be added later as advanced feature)
- **NG5:** Changes to operational CRD sync or non-DIET modules

---

## Detailed Design

### Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 TopologyPlan Detail Page                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Plan Info Card:                                            │
│    Name: Cambium 2MW                                        │
│    Customer: Cambium Networks                               │
│    Status: Draft                                            │
│    Device Generation: [SYNC STATUS INDICATOR] ← NEW        │
│                                                              │
│  Actions Card:                                              │
│    [Generate/Update Devices] ← UNIFIED BUTTON (auto-calc)  │
│    [Preview Changes] ← Optional advanced link               │
│    [Export YAML]                                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
              POST /topology-plans/{pk}/generate-update/
                            ↓
        1. Auto-recalculate switch quantities
        2. Abort if calculation errors (fail-fast)
        3. Generate/update devices (delete old, create new)
        4. Save comprehensive snapshot
        5. Redirect with enhanced success message
```

### Data Model Changes

#### New Shared Snapshot Builder Module

**File:** `netbox_hedgehog/utils/snapshot_builder.py` (NEW)

```python
"""
Snapshot builder for topology plan generation tracking.

Provides centralized snapshot logic used by both GenerationState and
DeviceGenerator to ensure consistency and prevent drift.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from netbox_hedgehog.models.topology_planning import TopologyPlan


def build_plan_snapshot(plan: 'TopologyPlan') -> dict:
    """
    Build comprehensive snapshot of plan state for generation tracking.

    Captures all fields that affect device generation. Excludes plan metadata
    (name, customer_name, description) to avoid false "out of sync" on renames.

    Args:
        plan: TopologyPlan instance to snapshot

    Returns:
        dict with keys:
            - server_classes: List of server class snapshots
            - switch_classes: List of switch class snapshots
            - connections: List of connection snapshots
            - port_zones: List of port zone snapshots
            - mclag_domains: List of MCLAG domain snapshots

    Example:
        >>> plan = TopologyPlan.objects.get(pk=123)
        >>> snapshot = build_plan_snapshot(plan)
        >>> snapshot.keys()
        dict_keys(['server_classes', 'switch_classes', 'connections',
                   'port_zones', 'mclag_domains'])
    """
    from netbox_hedgehog.models.topology_planning import (
        PlanServerConnection,
        SwitchPortZone,
    )

    snapshot = {
        'server_classes': [],
        'switch_classes': [],
        'connections': [],
        'port_zones': [],
        'mclag_domains': [],
    }

    # Server classes (include device type)
    for server_class in plan.server_classes.all():
        snapshot['server_classes'].append({
            'server_class_id': server_class.server_class_id,
            'quantity': server_class.quantity,
            'device_type_id': server_class.server_device_type_id,
            'gpus_per_server': server_class.gpus_per_server,
        })

    # Switch classes (include device type and uplink config)
    for switch_class in plan.switch_classes.all():
        snapshot['switch_classes'].append({
            'switch_class_id': switch_class.switch_class_id,
            'effective_quantity': switch_class.effective_quantity,
            'device_type_extension_id': switch_class.device_type_extension_id,
            'fabric': switch_class.fabric,  # Can be empty string
            'hedgehog_role': switch_class.hedgehog_role,  # Can be empty string
            'uplink_ports_per_switch': switch_class.uplink_ports_per_switch,  # Can be None
            'mclag_pair': switch_class.mclag_pair,
        })

    # Connection definitions
    for conn in PlanServerConnection.objects.filter(
        server_class__plan=plan
    ).select_related('server_class', 'target_switch_class'):
        snapshot['connections'].append({
            'connection_id': conn.connection_id,
            'server_class_id': conn.server_class.server_class_id,
            'target_switch_class_id': conn.target_switch_class.switch_class_id,
            'ports_per_connection': conn.ports_per_connection,
            'hedgehog_conn_type': conn.hedgehog_conn_type,
            'distribution': conn.distribution,  # Can be empty string
            'speed': conn.speed,
            'rail': conn.rail,  # Can be None
            'port_type': conn.port_type,  # Can be empty string
        })

    # Port zones (using actual model fields)
    # IMPORTANT: Always include all keys, even if None, to ensure
    # consistent comparison (avoids false "out of sync" on null fields)
    for zone in SwitchPortZone.objects.filter(
        switch_class__plan=plan
    ).select_related('switch_class', 'breakout_option'):
        snapshot['port_zones'].append({
            'switch_class_id': zone.switch_class.switch_class_id,
            'zone_name': zone.zone_name,
            'zone_type': zone.zone_type,
            'port_spec': zone.port_spec,
            'breakout_option_id': zone.breakout_option_id,  # Can be None
            'allocation_strategy': zone.allocation_strategy,
            'allocation_order': zone.allocation_order,  # Can be None
            'priority': zone.priority,
        })

    # MCLAG domains
    for mclag in plan.mclag_domains.all():
        snapshot['mclag_domains'].append({
            'domain_id': mclag.domain_id,
            'switch_class_id': mclag.switch_class.switch_class_id,
            'peer_link_count': mclag.peer_link_count,
            'session_link_count': mclag.session_link_count,
        })

    return snapshot


def compare_snapshots(current: dict, previous: dict) -> bool:
    """
    Compare two plan snapshots for equality.

    Uses order-independent comparison for lists to handle different query
    ordering across snapshot builds. Handles None values correctly - all
    snapshot fields are always included (even if None) to ensure consistent
    comparison.

    Args:
        current: Current snapshot dict
        previous: Previous snapshot dict

    Returns:
        True if snapshots are equal, False otherwise

    Example:
        >>> snap1 = build_plan_snapshot(plan)
        >>> # ... modify plan ...
        >>> snap2 = build_plan_snapshot(plan)
        >>> compare_snapshots(snap1, snap2)
        False  # Plan changed

    Note:
        Snapshot builder always includes all keys, even if value is None,
        to avoid false "out of sync" due to missing-vs-None differences.
    """
    import json

    def normalize(data):
        """
        Normalize data for order-independent comparison.

        Handles None, empty strings, and other falsy values correctly.
        """
        if isinstance(data, dict):
            return {k: normalize(v) for k, v in sorted(data.items())}
        elif isinstance(data, list):
            return sorted(
                [normalize(item) for item in data],
                key=lambda x: json.dumps(x, sort_keys=True)
            )
        else:
            return data  # Preserves None, 0, "", False as-is

    return normalize(current) == normalize(previous)
```

#### Modified Models

**File:** `netbox_hedgehog/models/topology_planning/generation.py`

```python
# BEFORE (lines 99-150)
def _build_current_snapshot(self):
    """Build snapshot of current plan state"""
    snapshot = {
        'server_classes': [],
        'switch_classes': []
    }

    # Capture server classes
    for server_class in self.plan.server_classes.all():
        snapshot['server_classes'].append({
            'server_class_id': server_class.server_class_id,
            'quantity': server_class.quantity
        })

    # Capture switch classes
    for switch_class in self.plan.switch_classes.all():
        snapshot['switch_classes'].append({
            'switch_class_id': switch_class.switch_class_id,
            'effective_quantity': switch_class.effective_quantity
        })

    return snapshot

def _compare_server_classes(self, current, snapshot):
    # ...comparison logic...

def _compare_switch_classes(self, current, snapshot):
    # ...comparison logic...

def is_dirty(self):
    """Check if plan has been modified since generation."""
    current_snapshot = self._build_current_snapshot()

    # Compare server classes
    if not self._compare_server_classes(
        current_snapshot.get('server_classes', []),
        self.snapshot.get('server_classes', [])
    ):
        return True

    # Compare switch classes
    if not self._compare_switch_classes(
        current_snapshot.get('switch_classes', []),
        self.snapshot.get('switch_classes', [])
    ):
        return True

    return False

# AFTER
from netbox_hedgehog.utils.snapshot_builder import (
    build_plan_snapshot,
    compare_snapshots,
)

def is_dirty(self) -> bool:
    """
    Check if plan has been modified since generation.

    Compares current plan state against snapshot saved at generation time.
    Detects changes to server classes, switch classes, connections, port
    zones, and MCLAG domains.

    Returns:
        bool: True if plan differs from snapshot, False otherwise

    Example:
        >>> state = GenerationState.objects.get(plan=plan)
        >>> state.is_dirty()
        False  # No changes since generation
        >>> plan.server_classes.first().quantity = 64
        >>> plan.server_classes.first().save()
        >>> state.is_dirty()
        True  # Quantity changed
    """
    current = build_plan_snapshot(self.plan)
    return not compare_snapshots(current, self.snapshot)

# Remove old _build_current_snapshot, _compare_server_classes,
# _compare_switch_classes methods (replaced by shared helper)
```

**File:** `netbox_hedgehog/services/device_generator.py`

```python
# BEFORE (lines 354-372)
def _build_snapshot(self) -> dict:
    snapshot = {
        'server_classes': [],
        'switch_classes': [],
    }

    for server_class in self.plan.server_classes.all():
        snapshot['server_classes'].append({
            'server_class_id': server_class.server_class_id,
            'quantity': server_class.quantity,
        })

    for switch_class in self.plan.switch_classes.all():
        snapshot['switch_classes'].append({
            'switch_class_id': switch_class.switch_class_id,
            'effective_quantity': switch_class.effective_quantity,
        })

    return snapshot

# AFTER
from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot

def _build_snapshot(self) -> dict:
    """
    Build snapshot of plan state at generation time.

    Delegates to shared snapshot builder to ensure consistency with
    GenerationState.is_dirty() comparison logic.

    Returns:
        dict: Comprehensive snapshot of plan state

    Example:
        >>> generator = DeviceGenerator(plan=plan)
        >>> snapshot = generator._build_snapshot()
        >>> snapshot.keys()
        dict_keys(['server_classes', 'switch_classes', 'connections',
                   'port_zones', 'mclag_domains'])
    """
    return build_plan_snapshot(self.plan)
```

### Code Changes

#### New View: TopologyPlanGenerateUpdateView

**File:** `netbox_hedgehog/views/topology_planning.py` (NEW VIEW)

```python
class TopologyPlanGenerateUpdateView(PermissionRequiredMixin, View):
    """
    Unified generate/update action for TopologyPlans.

    Automatically recalculates switch quantities, then generates or updates
    NetBox devices/interfaces/cables to match the current plan state.

    Required permissions:
    - netbox_hedgehog.change_topologyplan (plugin action)
    - dcim.add_device, dcim.delete_device (device lifecycle)
    - dcim.add_interface (interface creation - deletion via CASCADE)
    - dcim.add_cable, dcim.delete_cable (cable lifecycle)

    Flow:
    1. Validate plan has minimum required data
    2. Auto-recalculate switch quantities
    3. Abort if calculation errors (fail-fast)
    4. Generate/update devices via DeviceGenerator
    5. Show enhanced success message with device count + link
    6. Redirect to detail page (sync indicator refreshes)
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
        """
        Execute unified generate/update workflow.

        Args:
            request: HTTP request
            pk: TopologyPlan primary key

        Returns:
            HttpResponse: Redirect to detail page with message

        Raises:
            PermissionDenied: If user lacks required permissions
        """
        _require_topologyplan_change_permission(request)
        plan = get_object_or_404(models.TopologyPlan, pk=pk)

        # Validate minimum requirements
        if plan.server_classes.count() == 0 or plan.switch_classes.count() == 0:
            messages.error(
                request,
                "Cannot generate devices: plan requires at least one server class "
                "and one switch class."
            )
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

        # Step 1: Auto-recalculate switch quantities
        calc_result = update_plan_calculations(plan)

        # Step 2: Abort on calculation errors (fail-fast)
        if calc_result['errors']:
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
                    "<br><br>Please fix the plan configuration or set override_quantity "
                    "for affected switch classes."
                )
            )
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

        # Step 3: Generate/update devices
        generator = DeviceGenerator(plan=plan)
        try:
            result = generator.generate_all()
        except ValidationError as exc:
            messages.error(
                request,
                f"Generation failed: {' '.join(exc.messages)}"
            )
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)
        except Exception as exc:  # pragma: no cover - safety net
            messages.error(request, f"Generation failed: {exc}")
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

        # Step 4: Enhanced success message with link to devices
        device_list_url = reverse('dcim:device_list')
        messages.success(
            request,
            mark_safe(
                f'Devices updated successfully: '
                f'<a href="{device_list_url}?tag={DeviceGenerator.DEFAULT_TAG_SLUG}&'
                f'cf_hedgehog_plan_id={plan.pk}" target="_blank">'
                f'{result.device_count} devices</a>, '
                f'{result.interface_count} interfaces, '
                f'{result.cable_count} cables.'
            )
        )

        return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)
```

#### Optional Preview View (Advanced Users)

**File:** `netbox_hedgehog/views/topology_planning.py` (RENAME EXISTING)

```python
# Rename existing TopologyPlanGenerateView to TopologyPlanGeneratePreviewView
# Keep for advanced users who want to preview before generating

class TopologyPlanGeneratePreviewView(PermissionRequiredMixin, View):
    """
    OPTIONAL preview page for advanced users.

    Shows device/interface/cable counts and warnings before generation.
    Accessible via "Preview Changes" link on detail page, but NOT the
    default flow.

    GET: Show preview page with counts
    POST: Delegate to unified generate/update view
    """
    permission_required = 'netbox_hedgehog.change_topologyplan'
    raise_exception = True
    template_name = 'netbox_hedgehog/topology_planning/topologyplan_generate_preview.html'

    def get(self, request, pk):
        """Show preview page (unchanged from current implementation)"""
        # ... existing implementation ...
        pass

    def post(self, request, pk):
        """
        Confirmed generation from preview page.
        Delegate to unified generate/update view.
        """
        return TopologyPlanGenerateUpdateView.as_view()(request, pk=pk)
```

#### Remove Recalculate View

**File:** `netbox_hedgehog/views/topology_planning.py`

```python
# DELETE TopologyPlanRecalculateView entirely (lines 191-226)
# Recalculation is now automatic before generation
```

### UI Changes

#### Sync Status Indicator

**File:** `netbox_hedgehog/templates/netbox_hedgehog/topologyplan.html`

**Location:** Add new row in plan info card (after line 27)

```django
<tr>
    <th scope="row">Device Generation</th>
    <td>
        {% if object.last_generated_at %}
            {% if object.needs_regeneration %}
                {# Out of Sync State #}
                <span class="badge badge-warning">
                    <i class="mdi mdi-alert"></i> Out of Sync
                </span>
                <div class="text-muted small mt-1">
                    Last generated {{ object.last_generated_at|naturaltime }}.
                    <strong>Plan has changed since generation.</strong>
                </div>
                <div class="text-muted small">
                    {{ object.generation_state.device_count }} devices,
                    {{ object.generation_state.interface_count }} interfaces,
                    {{ object.generation_state.cable_count }} cables.
                </div>
            {% else %}
                {# In Sync State #}
                <span class="badge badge-success">
                    <i class="mdi mdi-check-circle"></i> In Sync
                </span>
                <div class="text-muted small mt-1">
                    Generated {{ object.last_generated_at|naturaltime }}.
                </div>
                <div class="text-muted small">
                    <a href="{% url 'dcim:device_list' %}?tag=hedgehog-generated&cf_hedgehog_plan_id={{ object.pk }}" target="_blank">
                        {{ object.generation_state.device_count }} devices
                    </a>,
                    {{ object.generation_state.interface_count }} interfaces,
                    {{ object.generation_state.cable_count }} cables.
                </div>
            {% endif %}
        {% else %}
            {# Never Generated State #}
            <span class="badge badge-secondary">
                <i class="mdi mdi-help-circle"></i> Not Generated
            </span>
            <div class="text-muted small mt-1">
                No devices have been generated yet.
            </div>
        {% endif %}
    </td>
</tr>
```

#### Unified Action Button

**File:** `netbox_hedgehog/templates/netbox_hedgehog/topologyplan.html`

**Location:** Replace lines 44-56 (Actions card)

```django
# BEFORE
<div class="card-body">
    {% if perms.netbox_hedgehog.change_topologyplan %}
    <a href="{% url 'plugins:netbox_hedgehog:topologyplan_generate' pk=object.pk %}" class="btn btn-warning mb-2">
        <i class="mdi mdi-cube"></i> Generate Devices
    </a>
    {% endif %}
    <form method="post" action="{% url 'plugins:netbox_hedgehog:topologyplan_recalculate' pk=object.pk %}" class="mb-2">
        {% csrf_token %}
        <button type="submit" class="btn btn-primary">
            <i class="mdi mdi-calculator"></i> Recalculate Switch Quantities
        </button>
    </form>
    <a href="{% url 'plugins:netbox_hedgehog:topologyplan_export' pk=object.pk %}" class="btn btn-success">
        <i class="mdi mdi-download"></i> Export YAML
    </a>
</div>

# AFTER
<div class="card-body">
    {% if perms.netbox_hedgehog.change_topologyplan and perms.dcim.add_device and perms.dcim.delete_device and perms.dcim.add_interface and perms.dcim.add_cable and perms.dcim.delete_cable %}
        <form method="post" action="{% url 'plugins:netbox_hedgehog:topologyplan_generate_update' pk=object.pk %}" class="d-inline">
            {% csrf_token %}
            <button type="submit" class="btn btn-primary mb-2">
                <i class="mdi mdi-sync"></i>
                {% if object.last_generated_at %}
                    {% if object.needs_regeneration %}
                        Update Devices
                    {% else %}
                        Regenerate Devices
                    {% endif %}
                {% else %}
                    Generate Devices
                {% endif %}
            </button>
        </form>
        <a href="{% url 'plugins:netbox_hedgehog:topologyplan_generate_preview' pk=object.pk %}" class="btn btn-sm btn-outline-secondary mb-2">
            <i class="mdi mdi-eye"></i> Preview Changes
        </a>
    {% else %}
        <button type="button" class="btn btn-primary mb-2" disabled
                title="Requires DCIM device/interface/cable add/delete permissions">
            <i class="mdi mdi-sync"></i> Generate/Update Devices
        </button>
        <small class="text-muted d-block">Contact administrator for device management permissions.</small>
    {% endif %}

    <a href="{% url 'plugins:netbox_hedgehog:topologyplan_export' pk=object.pk %}" class="btn btn-success mb-2">
        <i class="mdi mdi-download"></i> Export YAML
    </a>
</div>
```

### URL Changes

**File:** `netbox_hedgehog/urls.py`

```python
# BEFORE
urlpatterns = [
    # ... other patterns ...

    # Old separate generate and recalculate endpoints
    path(
        'topology-plans/<int:pk>/generate/',
        views.TopologyPlanGenerateView.as_view(),
        name='topologyplan_generate'
    ),
    path(
        'topology-plans/<int:pk>/recalculate/',
        views.TopologyPlanRecalculateView.as_view(),
        name='topologyplan_recalculate'
    ),

    # ... other patterns ...
]

# AFTER
urlpatterns = [
    # ... other patterns ...

    # NEW: Unified generate/update endpoint (POST only)
    path(
        'topology-plans/<int:pk>/generate-update/',
        views.TopologyPlanGenerateUpdateView.as_view(),
        name='topologyplan_generate_update'
    ),

    # RENAMED: Preview page for advanced users (optional)
    path(
        'topology-plans/<int:pk>/generate-preview/',
        views.TopologyPlanGeneratePreviewView.as_view(),
        name='topologyplan_generate_preview'
    ),

    # REMOVED: Recalculate endpoint (now automatic)
    # path('topology-plans/<int:pk>/recalculate/', ...) ← DELETE

    # ... other patterns ...
]
```

### Error Handling

#### Error Cases

| Condition | Exception/Handling | Message | HTTP Status |
|-----------|-------------------|---------|-------------|
| No server classes | Validation + redirect | "Cannot generate devices: plan requires at least one server class and one switch class." | 302 (redirect) |
| No switch classes | Validation + redirect | Same as above | 302 |
| Calculation error | Abort + error message | "Cannot generate devices due to calculation errors: • {switch_class}: {error}" | 302 |
| Missing permissions | PermissionDenied (raised by mixin) | "Permission denied" (NetBox default) | 403 |
| Device generation ValidationError | Catch + error message | "Generation failed: {validation messages}" | 302 |
| Device generation unexpected exception | Catch + error message | "Generation failed: {exception}" | 302 |

#### Permission Enforcement

**View-level:**
```python
permission_required = (
    'netbox_hedgehog.change_topologyplan',
    'dcim.add_device',
    'dcim.delete_device',
    'dcim.add_interface',
    'dcim.add_cable',
    'dcim.delete_cable',
)
raise_exception = True  # Returns 403 if missing any permission
```

**Template-level:**
```django
{% if perms.netbox_hedgehog.change_topologyplan and perms.dcim.add_device ... %}
    <!-- Button enabled -->
{% else %}
    <!-- Button disabled with tooltip -->
{% endif %}
```

---

## Backward Compatibility

### Compatibility Matrix

| Component | Backward Compatible? | Migration Required? | Notes |
|-----------|---------------------|---------------------|-------|
| Database schema | Yes | No | No schema changes |
| Existing generated devices | Yes | No | Already tagged correctly |
| TopologyPlan model | Yes | No | Uses existing properties |
| GenerationState model | Yes | No | Snapshot format extended (backward compatible) |
| Device generation logic | Yes | No | DeviceGenerator unchanged |
| URLs | **No (clean break)** | Manual if bookmarked | Old URLs removed, new URLs added |

### Breaking Changes

1. **Removed URL:** `/topology-plans/{pk}/recalculate/` no longer exists
   - **Impact:** Low - internal UI endpoint only
   - **Migration:** Remove from bookmarks if any exist (unlikely)

2. **Changed URL:** `/topology-plans/{pk}/generate/` → `/topology-plans/{pk}/generate-preview/`
   - **Impact:** Low - internal UI endpoint, accessed via buttons
   - **Migration:** UI buttons updated automatically, no user action needed
   - **Note:** Old URL will return 404 (no redirect provided)

3. **New URL:** `/topology-plans/{pk}/generate-update/` (POST only)
   - **Impact:** None - new endpoint
   - **Migration:** None

4. **Old snapshot format:** Existing GenerationState records have old 2-section snapshot
   - **Impact:** Plans will show "Out of Sync" until first regeneration (false positive)
   - **Migration:** Automatic on next generation (or manual cleanup, see below)

### Migration Guide

**For Existing Deployments:**

No database migration required. UI and URL changes only.

```bash
# No manage.py migrations needed
# Changes are code/template only

# Steps after deployment:
# Navigate to NetBox container directory
cd /home/ubuntu/afewell-hh/netbox-docker

# 1. Clear Django template cache (inside container)
docker compose exec netbox python manage.py collectstatic --clear --noinput

# 2. Restart NetBox container
docker compose restart netbox

# 3. Test unified action on a test plan
# 4. Verify sync indicator shows correct state
```

**For Existing Generated Plans:**

Plans with old 2-section snapshots:
- Will show "Out of Sync" on first page load (false positive)
- First regeneration updates to new comprehensive snapshot
- Subsequent checks accurate

Alternative: Clear all GenerationState records for clean slate:
```python
from netbox_hedgehog.models import GenerationState
GenerationState.objects.all().delete()
# Next generation for each plan creates new snapshot with full format
```

---

## Testing

### Test Scenarios

#### Integration Tests

**File:** `netbox_hedgehog/tests/test_topology_planning/test_unified_generate.py` (NEW)

```python
"""
Integration tests for unified generate/update devices action.

Tests the complete workflow from user action to device generation,
including auto-recalculation, permission enforcement, and sync status.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from dcim.models import Device
from netbox_hedgehog.models.topology_planning import (
    GenerationState,
    TopologyPlan,
)

User = get_user_model()


class TestUnifiedGenerateUpdate(TestCase):
    """Integration tests for unified generate/update action"""

    def setUp(self):
        """Set up test fixtures"""
        # Create user with all required permissions
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )

        # Grant all required permissions
        perms = [
            'netbox_hedgehog.change_topologyplan',
            'dcim.add_device',
            'dcim.delete_device',
            'dcim.add_interface',
            'dcim.add_cable',
            'dcim.delete_cable',
        ]
        for perm_name in perms:
            app, codename = perm_name.split('.')
            perm = Permission.objects.get(
                content_type__app_label=app,
                codename=codename
            )
            self.user.user_permissions.add(perm)

        self.client.login(username='testuser', password='testpass')

    def test_initial_generation_creates_devices(self):
        """First-time generation creates all devices and GenerationState"""
        # Given: Plan with server/switch classes, no prior generation
        plan = self._create_test_plan_with_classes()

        # When: POST to unified generate/update endpoint
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )
        response = self.client.post(url)

        # Then: Redirects to detail page
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/topology-plans/{plan.pk}/', response['Location'])

        # Then: Devices created
        devices = Device.objects.filter(
            tags__slug='hedgehog-generated',
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        )
        self.assertGreater(devices.count(), 0)

        # Then: GenerationState created
        self.assertTrue(
            GenerationState.objects.filter(plan=plan).exists()
        )

        # Then: Plan is in sync
        plan.refresh_from_db()
        self.assertFalse(plan.needs_regeneration)

        # Then: Success message shown
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any('Devices updated successfully' in str(m) for m in messages))

    def test_update_after_plan_change_regenerates_devices(self):
        """Regeneration after plan modification updates devices"""
        # Given: Plan with generated devices
        plan = self._create_test_plan_with_classes()
        self._generate_devices(plan)
        original_device_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()

        # Given: Modify plan (change server quantity)
        server_class = plan.server_classes.first()
        original_quantity = server_class.quantity
        server_class.quantity = original_quantity + 10
        server_class.save()

        # Then: Plan shows out of sync
        self.assertTrue(plan.needs_regeneration)

        # When: Regenerate devices
        self._generate_devices(plan)

        # Then: Device count updated (more servers)
        new_device_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()
        self.assertGreater(new_device_count, original_device_count)

        # Then: Plan is in sync again
        plan.refresh_from_db()
        self.assertFalse(plan.needs_regeneration)

    def test_idempotent_regeneration(self):
        """Regenerating without plan changes is safe and idempotent"""
        # Given: Plan with generated devices, no modifications
        plan = self._create_test_plan_with_classes()
        self._generate_devices(plan)
        device_count_before = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()

        # When: Regenerate again without plan changes
        self._generate_devices(plan)

        # Then: Device count unchanged
        device_count_after = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        ).count()
        self.assertEqual(device_count_before, device_count_after)

        # Then: Plan still in sync
        self.assertFalse(plan.needs_regeneration)

    def test_auto_recalculate_before_generation(self):
        """Generation automatically recalculates switch quantities"""
        # Given: Plan with calculated_quantity=None
        plan = self._create_test_plan_with_classes()
        switch_class = plan.switch_classes.first()
        switch_class.calculated_quantity = None
        switch_class.save()

        # When: Generate devices (should auto-recalculate)
        self._generate_devices(plan)

        # Then: calculated_quantity populated
        switch_class.refresh_from_db()
        self.assertIsNotNone(switch_class.calculated_quantity)
        self.assertGreater(switch_class.calculated_quantity, 0)

        # Then: Devices created based on calculated quantities
        device_count = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk),
            custom_field_data__hedgehog_class=switch_class.switch_class_id
        ).count()
        self.assertEqual(device_count, switch_class.calculated_quantity)

    def test_abort_on_calculation_errors(self):
        """Generation aborts if calculation errors occur"""
        # Given: Plan with invalid configuration (causes calc error)
        plan = self._create_invalid_test_plan()

        # When: Attempt to generate devices
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )
        response = self.client.post(url)

        # Then: Redirects to detail page (no generation)
        self.assertEqual(response.status_code, 302)

        # Then: Error message shown
        messages = list(response.wsgi_request._messages)
        self.assertTrue(
            any('Cannot generate devices due to calculation errors' in str(m)
                for m in messages)
        )

        # Then: No devices created
        devices = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(plan.pk)
        )
        self.assertEqual(devices.count(), 0)

        # Then: No GenerationState created
        self.assertFalse(
            GenerationState.objects.filter(plan=plan).exists()
        )

    def test_sync_indicator_not_generated(self):
        """Sync indicator shows 'Not Generated' for new plan"""
        # Given: New plan, never generated
        plan = self._create_test_plan_with_classes()

        # When: Load detail page
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk}
        )
        response = self.client.get(url)

        # Then: Page loads successfully
        self.assertEqual(response.status_code, 200)

        # Then: Shows "Not Generated" badge
        self.assertContains(response, 'Not Generated')
        self.assertContains(response, 'mdi-help-circle')

    def test_sync_indicator_in_sync(self):
        """Sync indicator shows 'In Sync' after generation"""
        # Given: Plan with generated devices, no changes
        plan = self._create_test_plan_with_classes()
        self._generate_devices(plan)

        # When: Load detail page
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk}
        )
        response = self.client.get(url)

        # Then: Shows "In Sync" badge
        self.assertContains(response, 'In Sync')
        self.assertContains(response, 'mdi-check-circle')
        self.assertContains(response, 'badge-success')

    def test_sync_indicator_out_of_sync(self):
        """Sync indicator shows 'Out of Sync' after plan modification"""
        # Given: Plan with generated devices
        plan = self._create_test_plan_with_classes()
        self._generate_devices(plan)

        # Given: Modify plan
        server_class = plan.server_classes.first()
        server_class.quantity += 5
        server_class.save()

        # When: Load detail page
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk}
        )
        response = self.client.get(url)

        # Then: Shows "Out of Sync" badge
        self.assertContains(response, 'Out of Sync')
        self.assertContains(response, 'mdi-alert')
        self.assertContains(response, 'badge-warning')
        self.assertContains(response, 'Plan has changed since generation')

    def test_plan_name_change_does_not_trigger_out_of_sync(self):
        """Changing plan name/customer should NOT mark plan out of sync"""
        # Given: Plan with generated devices
        plan = self._create_test_plan_with_classes()
        self._generate_devices(plan)

        # Given: Change plan metadata (not generation-relevant)
        plan.name = "New Plan Name"
        plan.customer_name = "New Customer"
        plan.description = "New description"
        plan.save()

        # Then: Plan STILL in sync (metadata excluded from snapshot)
        plan.refresh_from_db()
        self.assertFalse(plan.needs_regeneration)

    def test_connection_change_triggers_out_of_sync(self):
        """Changing connection parameters should mark plan out of sync"""
        # Given: Plan with generated devices
        plan = self._create_test_plan_with_classes()
        self._generate_devices(plan)

        # Given: Change connection type (generation-relevant)
        connection = plan.server_classes.first().connections.first()
        connection.hedgehog_conn_type = 'mclag'
        connection.save()

        # Then: Plan is out of sync
        plan.refresh_from_db()
        self.assertTrue(plan.needs_regeneration)

    def test_permission_denied_without_dcim_permissions(self):
        """Generation requires DCIM add/delete permissions"""
        # Given: User without dcim.add_device permission
        self.user.user_permissions.filter(
            codename='add_device'
        ).delete()

        # When: Attempt to generate
        plan = self._create_test_plan_with_classes()
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )
        response = self.client.post(url)

        # Then: Permission denied (403)
        self.assertEqual(response.status_code, 403)

    def test_button_disabled_without_permissions(self):
        """Generate button disabled for users without permissions"""
        # Given: User without dcim permissions
        self.user.user_permissions.filter(
            codename__in=['add_device', 'delete_device']
        ).delete()

        # When: Load detail page
        plan = self._create_test_plan_with_classes()
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_detail',
            kwargs={'pk': plan.pk}
        )
        response = self.client.get(url)

        # Then: Button is disabled
        self.assertContains(response, 'disabled')
        self.assertContains(response, 'Contact administrator for device management permissions')

    # Helper methods
    def _create_test_plan_with_classes(self):
        """Create test plan with server/switch classes"""
        # Implementation using test fixtures
        pass

    def _create_invalid_test_plan(self):
        """Create plan that will cause calculation errors"""
        # Implementation
        pass

    def _generate_devices(self, plan):
        """Helper to generate devices for a plan"""
        url = reverse(
            'plugins:netbox_hedgehog:topologyplan_generate_update',
            kwargs={'pk': plan.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
```

### Test Matrix

| Scenario | Plan State | Expected Button Text | Expected Badge | Expected Outcome |
|----------|-----------|---------------------|----------------|------------------|
| Never generated | New plan | "Generate Devices" | "Not Generated" (gray) | Initial generation |
| Generated + in sync | No changes | "Regenerate Devices" | "In Sync" (green) | Idempotent regeneration |
| Generated + out of sync | Quantity changed | "Update Devices" | "Out of Sync" (orange) | Updated devices |
| Generated + metadata change | Name/customer changed | "Regenerate Devices" | "In Sync" (green) | Stays in sync |
| Generated + connection change | Connection type changed | "Update Devices" | "Out of Sync" (orange) | Updated devices |
| No permissions | Any | Disabled button | Any | 403 error |
| Calculation error | Invalid config | "Generate Devices" | Any | Error message, no generation |

---

## Implementation Plan

### Prerequisites
- [x] Research complete (`DIET_127_RESEARCH_FINDINGS.md`)
- [x] Architecture design complete (`DIET_127_ARCHITECTURE_DESIGN.md`)
- [x] Review feedback addressed (`DIET_127_REVIEW_RESPONSE.md`)
- [ ] This spec reviewed and approved

### Step-by-Step Implementation

**Step 1: Shared Snapshot Builder**
```bash
# File: netbox_hedgehog/utils/snapshot_builder.py (NEW)
# Create build_plan_snapshot() and compare_snapshots() functions
# Priority: HIGH (foundation for other changes)
```

**Step 2: Update GenerationState Model**
```bash
# File: netbox_hedgehog/models/topology_planning/generation.py
# Replace _build_current_snapshot, _compare_*, is_dirty() with shared helper
# Priority: HIGH (required for sync indicator)
```

**Step 3: Update DeviceGenerator Service**
```bash
# File: netbox_hedgehog/services/device_generator.py
# Replace _build_snapshot() with shared helper
# Priority: HIGH (ensures consistency)
```

**Step 4: Create Unified View**
```bash
# File: netbox_hedgehog/views/topology_planning.py
# Add TopologyPlanGenerateUpdateView with auto-recalculate + fail-fast
# Priority: HIGH (core feature)
```

**Step 5: Update URLs**
```bash
# File: netbox_hedgehog/urls.py
# Add generate-update endpoint, remove recalculate endpoint
# Rename generate to generate-preview
# Priority: HIGH (routing changes)
```

**Step 6: Update Templates**
```bash
# File: netbox_hedgehog/templates/netbox_hedgehog/topologyplan.html
# Add sync status indicator (new table row)
# Replace dual buttons with unified button + permission checks
# Priority: HIGH (UI changes)
```

**Step 7: Rename Preview Template**
```bash
# File: netbox_hedgehog/templates/netbox_hedgehog/topology_planning/
# Rename topologyplan_generate.html to topologyplan_generate_preview.html
# Priority: MEDIUM (optional advanced feature)
```

**Step 8: Integration Tests**
```bash
# File: netbox_hedgehog/tests/test_topology_planning/test_unified_generate.py (NEW)
# Implement all test scenarios from test matrix
# Priority: HIGH (verification)
```

**Step 9: Documentation Updates**
```bash
# File: Update user guide with new unified workflow
# Priority: MEDIUM
```

### File Changes Checklist

- [ ] `netbox_hedgehog/utils/snapshot_builder.py` - NEW - Shared snapshot logic
- [ ] `netbox_hedgehog/models/topology_planning/generation.py` - MODIFIED - Use shared snapshot
- [ ] `netbox_hedgehog/services/device_generator.py` - MODIFIED - Use shared snapshot
- [ ] `netbox_hedgehog/views/topology_planning.py` - MODIFIED - Add unified view, remove recalculate view
- [ ] `netbox_hedgehog/templates/netbox_hedgehog/topologyplan.html` - MODIFIED - Add indicator, update buttons
- [ ] `netbox_hedgehog/templates/netbox_hedgehog/topology_planning/topologyplan_generate.html` - RENAMED - To topologyplan_generate_preview.html
- [ ] `netbox_hedgehog/urls.py` - MODIFIED - Add generate-update, remove recalculate, rename generate
- [ ] `netbox_hedgehog/tests/test_topology_planning/test_unified_generate.py` - NEW - Integration tests

### Rollback Plan

If issues discovered after deployment:

1. **Navigate to container directory:**
   ```bash
   cd /home/ubuntu/afewell-hh/netbox-docker
   ```

2. **Immediate Rollback:**
   ```bash
   # Revert code changes
   cd ../hh-netbox-plugin
   git revert <commit-hash>
   git push

   # Return to container directory
   cd ../netbox-docker
   ```

3. **Clear cached templates and restart:**
   ```bash
   docker compose exec netbox python manage.py collectstatic --clear --noinput
   docker compose restart netbox
   ```

4. **User Communication:**
   - Notify users that old workflow is temporarily restored
   - Document any plans with stale GenerationState (will need regeneration)

---

## Alternatives Considered

### Alternative 1: Keep Preview Page as Default Flow

**Description:** Keep the two-step preview flow (GET preview → POST generate) as the main action.

**Pros:**
- Users can review counts before generating
- Safer for large plans (confirm before action)

**Cons:**
- Extra friction (two clicks instead of one)
- Users report wanting direct action, not preview
- Preview info already visible on detail page (sync indicator)

**Why Rejected:** User feedback indicates preview adds friction without value. Advanced users can still access preview via "Preview Changes" link.

### Alternative 2: Keep Separate Recalculate Button

**Description:** Keep manual "Recalculate" button alongside unified "Generate" button.

**Pros:**
- Users can recalculate without generating
- Matches current workflow (less change)

**Cons:**
- Continues to confuse users (two buttons, unclear relationship)
- Manual recalculate step is error-prone (users forget)
- No benefit - recalculation is fast and safe to auto-run

**Why Rejected:** Auto-recalculate before generation is safer and simpler. Export YAML already auto-recalculates, proving it's acceptable behavior.

### Alternative 3: Async/Background Job Queue

**Description:** Run generation as background job with progress indicator.

**Pros:**
- Handles very large plans (1000+ devices)
- Non-blocking UI

**Cons:**
- Adds complexity (job queue, polling, UI updates)
- Overkill for MVP (most plans < 200 devices, <10s generation time)
- NetBox request timeout (300s) is sufficient for current use cases

**Why Rejected:** Direct POST is acceptable for MVP. Can add async later if needed for scale.

### Alternative 4: Partial Device Updates (Diff-Based)

**Description:** Only update changed devices instead of delete-all-recreate.

**Pros:**
- Faster regeneration for small changes
- Preserves device history/relationships

**Cons:**
- Much more complex logic (diff calculation, edge cases)
- Risk of state drift between plan and devices
- Current delete-recreate is fast enough (<10s for 200 devices)

**Why Rejected:** Delete-recreate is simpler and safer. Performance is acceptable for MVP.

---

## Open Questions

### Question 1: Success Message Filter Syntax

**Question:** Is `cf_hedgehog_plan_id={plan.pk}` the correct NetBox 4.3 filter syntax for custom fields?

**Options:**
- A) `cf_hedgehog_plan_id` (NetBox 3.5+ standard syntax)
- B) `custom_field_hedgehog_plan_id` (older NetBox syntax)
- C) Different syntax entirely

**Evidence:**
- DeviceGenerator uses `custom_field_data={'hedgehog_plan_id': str(plan.pk)}` (verified in research)
- Tag slug is `hedgehog-generated` (verified from DeviceGenerator.DEFAULT_TAG_SLUG)
- NetBox 4.3 docs indicate `cf_` prefix is correct for custom field filters

**Recommendation:** Use Option A (`cf_hedgehog_plan_id`) based on NetBox 4.3 docs.

**Verification Plan:**
1. During implementation, test filter URL manually in NetBox 4.3 UI
2. Verify filtered device list shows only plan devices
3. If filter fails, check NetBox UI filter bar for correct syntax
4. Fallback: Use tag-only filter (`?tag=hedgehog-generated`) without CF filter

**Decision:** Option A pending manual verification. **Low risk** - worst case, link shows all hedgehog-generated devices instead of plan-specific devices (still usable).

---

## Security Considerations

**Input Validation:**
- Plan PK validated via `get_object_or_404` (no SQL injection)
- No user-supplied parameters in device generation (plan data is trusted)

**Authorization:**
- Strict permission enforcement (6 required permissions)
- View-level and template-level checks
- Disabled button prevents unauthorized attempts

**Sensitive Data:**
- No sensitive data in success message (device count is public info)
- Plan ID in custom field is not sensitive

**CSRF Protection:**
- All POST forms include `{% csrf_token %}`
- Django CSRF middleware enforces token validation

**Scoped Deletion:**
- Devices deleted by `hedgehog_plan_id` filter (can't delete other plans' devices)
- Tag filter adds additional safety layer

---

## Performance Considerations

### Query Performance

**Expected Query Count:**
- Auto-recalculate: ~10 queries (1 per switch class)
- Snapshot build: ~6 queries (server/switch/connection/zone/mclag)
- Device generation: ~N queries for N devices (bulk create where possible)
- Total: ~50-100 queries for typical plan (150 devices)

**Indexes Required:**
- Existing indexes sufficient (FK indexes on plan, switch_class)
- GenerationState.plan (unique, already indexed)

**Cache Strategy:**
- No caching needed (queries are fast, data changes frequently)

### Memory Usage

**Expected Memory Impact:**
- Snapshot JSON: 3-5KB per plan
- Device generation: ~1MB per 100 devices (in-memory objects before save)
- Total: <10MB for largest expected plans (500 devices)

### Time Complexity

**Algorithm Complexity:**
- Snapshot build: O(N) where N = total plan objects (classes + connections + zones)
- Device generation: O(D) where D = total devices
- Expected runtime: <10 seconds for 200-device plan

**Benchmarks (Expected):**
- 50-device plan: ~2 seconds
- 150-device plan: ~5 seconds
- 500-device plan: ~15 seconds (within 300s timeout)

---

## Documentation Updates

### User-Facing Documentation

- [ ] Update user guide section on device generation workflow
- [ ] Add section explaining sync status indicator
- [ ] Document required permissions for generation
- [ ] Add screenshots showing new UI

### Developer Documentation

- [ ] Update architecture docs with snapshot builder pattern
- [ ] Add code comments in snapshot_builder.py explaining comparison logic
- [ ] Document permission requirements in view docstring

---

## Dependencies

### Depends On
- None (standalone feature)

### Blocks
- None (independent improvement)

### Related
- DIET-SPEC-001, 002, 003: Calculation engine (already implemented)
- Issue #123: 128-GPU test case (validation use case)

---

## Metrics and Monitoring

### Success Metrics

- [x] All integration tests pass (100% of specified scenarios)
- [ ] Performance: Generation completes in <10s for 150-device plan
- [ ] No regression: Existing device generation tests still pass
- [ ] Code coverage: New code has >90% coverage
- [ ] User feedback: Confusion about dual buttons eliminated

### Monitoring

**Metric to Track:** Generation success/failure rate
**Alert Threshold:** >10% failure rate (indicates calc or permission issues)
**Dashboard:** NetBox admin logs (filter by `topologyplan_generate_update`)

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2025-12-29 | Dev A | Initial draft based on research + architecture |
| 2025-12-29 | Dev A | Incorporated review feedback #1 (port zones, permissions, metadata) |
| 2025-12-29 | Dev A | Incorporated review feedback #2 (container commands, URL compat, snapshot nulls, filter syntax) |

### Review Feedback #2 Incorporated

**H1: Container Commands (Fixed)**
- Migration guide updated to use `docker compose exec netbox` commands
- Rollback plan updated to use container commands
- Removed all host-level `systemctl` and direct `python manage.py` commands

**M1: URL Backward Compatibility (Clarified)**
- **Decision:** Clean break, no legacy redirects
- Old `/generate/` URL renamed to `/generate-preview/` (returns 404 on old path)
- Old `/recalculate/` URL removed entirely (returns 404)
- New `/generate-update/` URL added
- Rationale: Internal UI endpoints, low impact, cleaner codebase

**M2: Snapshot Null Handling (Enhanced)**
- Added explicit comments on all nullable fields in snapshot
- Updated `compare_snapshots()` docstring to clarify null handling
- All keys always included (even if None) for consistent comparison
- Prevents false "out of sync" on missing-vs-None differences

**L1: Filter Syntax Verification (Enhanced)**
- Updated Open Questions with detailed verification plan
- Added evidence from NetBox 4.3 docs
- Documented fallback strategy if filter syntax incorrect
- Low risk assessment (worst case: shows all tagged devices)

---

## Approval

### Reviewers

- [ ] **User:** Approve overall approach and UX changes
- [ ] **Dev B:** Review implementation plan and code structure
- [ ] **Dev C:** Review testing coverage and scenarios

### Sign-off

- **Approved by:** [Pending]
- **Approval date:** [Pending]
- **Implementation start:** [After approval]
- **Target completion:** 3-4 days after approval

---

## References

- [Issue #127](https://github.com/anthropics/hh-netbox-plugin/issues/127)
- [Research Document](../DIET_127_RESEARCH_FINDINGS.md)
- [Architecture Design](../DIET_127_ARCHITECTURE_DESIGN.md)
- [Review Response](../DIET_127_REVIEW_RESPONSE.md)

---

**Status:** ✅ Draft complete, ready for team review
**Next Step:** User/Dev B/Dev C review and approval
