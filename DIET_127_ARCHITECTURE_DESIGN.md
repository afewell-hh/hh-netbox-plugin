# Issue #127 Architecture Design
**Date:** 2025-12-29
**Issue:** DIET: Unify Generate/Update Devices flow + sync status indicator
**Phase:** Architecture/Design (Step 2 of 5)
**Prerequisites:** Research findings in `DIET_127_RESEARCH_FINDINGS.md`

---

## Design Goals

1. **Unified Action:** Replace two separate buttons with one intelligent "Generate/Update Devices" action
2. **Auto-Recalculate:** Automatically run switch quantity calculations before generation
3. **Sync Visibility:** Add clear "in sync / out of sync" indicator on detail page
4. **User Feedback:** Provide immediate visual confirmation after generation/update
5. **Idempotent:** Multiple clicks should be safe and deterministic
6. **Backward Compatible:** Don't break existing generated devices or workflows

---

## High-Level Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                   TopologyPlan Detail Page                       │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Plan Info Card:                                                 │
│    Name: Cambium 2MW                                            │
│    Customer: Cambium Networks                                   │
│    Status: Draft                                                │
│    Device Generation: [SYNC STATUS INDICATOR] ← NEW             │
│      ┌─────────────────────────────────────────┐               │
│      │ ✓ In Sync                                │               │
│      │ Generated 5 minutes ago (146 devices)    │               │
│      └─────────────────────────────────────────┘               │
│                        OR                                        │
│      ┌─────────────────────────────────────────┐               │
│      │ ⚠ Out of Sync                            │               │
│      │ Last generated 2 hours ago.              │               │
│      │ Plan has changed since generation.       │               │
│      └─────────────────────────────────────────┘               │
│                        OR                                        │
│      ┌─────────────────────────────────────────┐               │
│      │ ○ Not Generated                          │               │
│      └─────────────────────────────────────────┘               │
│                                                                  │
│  Actions Card:                                                   │
│    ┌────────────────────────────────────┐                      │
│    │ [Generate/Update Devices] ← UNIFIED BUTTON               │
│    │ (text changes based on state)                             │
│    └────────────────────────────────────┘                      │
│    [Export YAML]                                                │
│                                                                  │
└────────────────────────────────────────────────────────────────┘

                            ↓ User clicks button

┌────────────────────────────────────────────────────────────────┐
│                 POST to generate_update endpoint                 │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Auto-recalculate switch quantities                          │
│     └─→ update_plan_calculations(plan)                          │
│         └─→ Updates calculated_quantity on all switch classes   │
│                                                                  │
│  2. Run device generation                                       │
│     └─→ DeviceGenerator(plan).generate_all()                    │
│         ├─→ Delete old devices/cables (plan-scoped)             │
│         ├─→ Create switch devices                               │
│         ├─→ Create server devices                               │
│         ├─→ Create interfaces and cables                        │
│         ├─→ Tag everything with hedgehog-generated              │
│         └─→ Save GenerationState with snapshot                  │
│                                                                  │
│  3. Build enhanced success message                              │
│     └─→ "Devices updated: [146 devices] [292 interfaces] ..."  │
│                                                                  │
│  4. Redirect to detail page                                     │
│     └─→ Status indicator now shows "In Sync"                    │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

---

## Component Design

### 1. Unified View: `TopologyPlanGenerateUpdateView`

**Purpose:** Single endpoint that handles both initial generation and updates

**File:** `netbox_hedgehog/views/topology_planning.py`

**Design:**

```python
class TopologyPlanGenerateUpdateView(PermissionRequiredMixin, View):
    """
    Unified generate/update action for TopologyPlans.

    Automatically recalculates switch quantities, then generates or updates
    NetBox devices/interfaces/cables to match the current plan state.

    POST only - no preview page (simplified workflow).
    """
    permission_required = 'netbox_hedgehog.change_topologyplan'
    raise_exception = True

    def post(self, request, pk):
        """
        Execute generate/update workflow.

        Steps:
        1. Validate plan has required data
        2. Auto-recalculate switch quantities
        3. Generate/update devices via DeviceGenerator
        4. Show enhanced success message
        5. Redirect to detail page
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

        # Step 1: Auto-recalculate
        calc_result = update_plan_calculations(plan)

        # Warn about calculation errors (but continue)
        if calc_result['errors']:
            for error_info in calc_result['errors']:
                messages.warning(
                    request,
                    f"Calculation warning for '{error_info['switch_class']}': "
                    f"{error_info['error']}. Using existing quantities."
                )

        # Step 2: Generate/update devices
        generator = DeviceGenerator(plan=plan)
        try:
            result = generator.generate_all()
        except ValidationError as exc:
            messages.error(request, f"Generation failed: {' '.join(exc.messages)}")
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)
        except Exception as exc:  # pragma: no cover
            messages.error(request, f"Generation failed: {exc}")
            return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)

        # Step 3: Enhanced success message
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

**Key Design Decisions:**
- ✅ POST-only (no GET/preview)
- ✅ Auto-recalculates before generation
- ✅ Shows warnings for calculation errors but continues
- ✅ Enhanced success message with link to generated devices
- ✅ Returns to detail page (where sync indicator updates)

---

### 2. Legacy Preview Flow (Optional Advanced Feature)

**Purpose:** Preserve preview capability for users who want to review before generating

**Design:**

```python
class TopologyPlanGeneratePreviewView(PermissionRequiredMixin, View):
    """
    OPTIONAL preview page for advanced users.

    Shows device/interface/cable counts and warnings before generation.
    Accessible via "Advanced" link on detail page, but NOT the default flow.
    """
    permission_required = 'netbox_hedgehog.change_topologyplan'
    raise_exception = True
    template_name = 'netbox_hedgehog/topology_planning/topologyplan_generate_preview.html'

    def get(self, request, pk):
        """Show preview page"""
        _require_topologyplan_change_permission(request)
        plan = get_object_or_404(models.TopologyPlan, pk=pk)

        # Auto-recalculate for preview (read-only context)
        update_plan_calculations(plan)

        context = self._build_preview_context(plan)
        return render(request, self.template_name, context)

    def post(self, request, pk):
        """
        Confirmed generation from preview page.
        Delegates to unified generate/update view.
        """
        # Redirect to unified endpoint
        return TopologyPlanGenerateUpdateView.as_view()(request, pk=pk)
```

**Template Location:** Rename existing `topologyplan_generate.html` to `topologyplan_generate_preview.html`

**Access:** Detail page shows small "Preview changes" link for advanced users

---

### 3. Sync Status Indicator Component

**Purpose:** Visual indicator showing whether devices are in sync with plan

**Design:**

**Template Snippet** (add to `topologyplan.html` lines 19-27 area):

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

**Visual States:**

| State | Badge | Icon | Color | Description |
|-------|-------|------|-------|-------------|
| **In Sync** | Success | `mdi-check-circle` | Green | Plan unchanged since generation |
| **Out of Sync** | Warning | `mdi-alert` | Orange | Plan modified after generation |
| **Not Generated** | Secondary | `mdi-help-circle` | Gray | Never generated |

---

### 4. Updated Button Design

**Purpose:** Single intelligent button that changes text based on state

**Template Snippet** (replace lines 44-52 in `topologyplan.html`):

```django
<div class="card">
    <h5 class="card-header">Actions</h5>
    <div class="card-body">
        {% if perms.netbox_hedgehog.change_topologyplan %}
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
        {% endif %}

        <a href="{% url 'plugins:netbox_hedgehog:topologyplan_export' pk=object.pk %}" class="btn btn-success mb-2">
            <i class="mdi mdi-download"></i> Export YAML
        </a>
    </div>
</div>
```

**Button Text Logic:**
| Condition | Button Text |
|-----------|-------------|
| Never generated (`last_generated_at` is None) | "Generate Devices" |
| Generated + out of sync (`needs_regeneration` is True) | "Update Devices" |
| Generated + in sync (`needs_regeneration` is False) | "Regenerate Devices" |

**Secondary Action:** "Preview Changes" link for advanced users

---

### 5. URL Routing Updates

**File:** `netbox_hedgehog/urls.py`

**Changes:**

```python
# Remove old separate endpoints
urlpatterns = [
    # ... other patterns ...

    # UNIFIED generate/update endpoint (POST only)
    path(
        'topology-plans/<int:pk>/generate-update/',
        views.TopologyPlanGenerateUpdateView.as_view(),
        name='topologyplan_generate_update'
    ),

    # OPTIONAL preview page for advanced users
    path(
        'topology-plans/<int:pk>/generate-preview/',
        views.TopologyPlanGeneratePreviewView.as_view(),
        name='topologyplan_generate_preview'
    ),

    # DEPRECATED - keep for backward compatibility but redirect to unified endpoint
    path(
        'topology-plans/<int:pk>/generate/',
        views.TopologyPlanGenerateLegacyRedirectView.as_view(),
        name='topologyplan_generate'  # Legacy name
    ),

    # REMOVE - recalculate is now automatic
    # path('topology-plans/<int:pk>/recalculate/', ...) ← DELETE THIS

    # ... other patterns ...
]
```

**Legacy Redirect View:**

```python
class TopologyPlanGenerateLegacyRedirectView(View):
    """
    Redirect old generate URL to new unified endpoint.
    Ensures backward compatibility.
    """
    def get(self, request, pk):
        # Redirect GET to preview page
        return redirect('plugins:netbox_hedgehog:topologyplan_generate_preview', pk=pk)

    def post(self, request, pk):
        # Redirect POST to unified endpoint
        return redirect('plugins:netbox_hedgehog:topologyplan_generate_update', pk=pk)
```

---

## Data Flow Diagrams

### Unified Generate/Update Flow

```
┌──────────────┐
│ User clicks  │
│   "Update    │
│   Devices"   │
└──────┬───────┘
       │
       ▼
┌────────────────────────────────────────┐
│ TopologyPlanGenerateUpdateView.post()  │
├────────────────────────────────────────┤
│ 1. Validate plan                       │
│    ├─ server_classes.count() > 0?      │
│    └─ switch_classes.count() > 0?      │
│                                        │
│ 2. Auto-recalculate                    │
│    └─→ update_plan_calculations(plan)  │
│        └─→ Updates calculated_quantity │
│                                        │
│ 3. Generate devices                    │
│    └─→ DeviceGenerator.generate_all()  │
│        ├─→ _cleanup_generated_objects()│
│        │   ├─→ Delete cables (scoped)  │
│        │   └─→ Delete devices (scoped) │
│        ├─→ _create_switch_devices()    │
│        ├─→ _create_server_devices()    │
│        ├─→ _create_connections()       │
│        ├─→ _tag_objects()              │
│        └─→ _upsert_generation_state()  │
│            ├─→ snapshot current plan   │
│            └─→ save GenerationState    │
│                                        │
│ 4. Success message                     │
│    └─→ "Devices updated: [N devices]"  │
│                                        │
│ 5. Redirect to detail page             │
│    └─→ Sync indicator refreshes        │
└────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│ Detail Page                       │
├──────────────────────────────────┤
│ Sync Indicator: "✓ In Sync"      │
│ Button: "Regenerate Devices"     │
└──────────────────────────────────┘
```

### Sync Status Detection Flow

```
┌──────────────────────────────────┐
│ TopologyPlan.needs_regeneration  │
│ (property)                       │
└────────────┬─────────────────────┘
             │
             ▼
      ┌────────────────┐
      │ GenerationState│
      │    exists?     │
      └────┬───────────┘
           │
    ┌──────┴──────┐
    │ No          │ Yes
    ▼             ▼
┌────────┐  ┌──────────────────┐
│ Return │  │ generation_state │
│ False  │  │   .is_dirty()    │
└────────┘  └────────┬─────────┘
                     │
                     ▼
          ┌───────────────────────┐
          │ Build current snapshot│
          │ from plan state       │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ Compare server classes│
          │ (ID + quantity)       │
          └───────────┬───────────┘
                      │
                ┌─────┴─────┐
                │ Match?    │
                └─────┬─────┘
                      │
             ┌────────┴────────┐
             │ No              │ Yes
             ▼                 ▼
        ┌────────┐  ┌──────────────────┐
        │ Return │  │ Compare switch   │
        │  True  │  │ classes          │
        │(dirty) │  │ (ID + effective) │
        └────────┘  └────────┬─────────┘
                             │
                       ┌─────┴─────┐
                       │ Match?    │
                       └─────┬─────┘
                             │
                    ┌────────┴────────┐
                    │ No              │ Yes
                    ▼                 ▼
               ┌────────┐       ┌────────┐
               │ Return │       │ Return │
               │  True  │       │ False  │
               │(dirty) │       │(clean) │
               └────────┘       └────────┘
```

---

## Error Handling Strategy

| Error Scenario | Handling | User Feedback |
|----------------|----------|---------------|
| No server classes | Abort before recalculate | Error: "Plan requires at least one server class" |
| No switch classes | Abort before recalculate | Error: "Plan requires at least one switch class" |
| Calculation error (single switch class) | Continue with warning | Warning: "Calculation error for 'fe-gpu-leaf': [error]. Using existing quantities." |
| Device generation ValidationError | Abort, show error | Error: "Generation failed: [validation messages]" |
| Device generation unexpected exception | Abort, show error | Error: "Generation failed: [exception message]" |
| Database transaction failure | Automatic rollback | Error: "Generation failed: [database error]" |

**Key Principle:** Fail fast with clear error messages. Never leave plan in partial state.

---

## Permission Model

**Required Permission:** `netbox_hedgehog.change_topologyplan`

**Enforcement Points:**
1. View-level: `PermissionRequiredMixin` with `raise_exception=True`
2. Template-level: `{% if perms.netbox_hedgehog.change_topologyplan %}`
3. Function-level: `_require_topologyplan_change_permission(request)`

**Sync Indicator Visibility:**
- ✅ Visible to all users with view permission (read-only indicator)
- ❌ Generate button only visible to users with change permission

---

## Backward Compatibility

### Preserving Existing Functionality

1. **Old Generate URL (`/topology-plans/{pk}/generate/`)**
   - GET: Redirects to preview page
   - POST: Redirects to unified endpoint
   - **Rationale:** External links/bookmarks continue to work

2. **Preview Page**
   - Kept as optional "advanced" feature
   - Accessible via "Preview Changes" link
   - **Rationale:** Power users may want to review before executing

3. **Existing Generated Devices**
   - No migration required
   - Already tagged with `hedgehog-generated` and `hedgehog_plan_id`
   - **Rationale:** Regeneration will clean up and recreate

### Breaking Changes (Intentional)

1. **Recalculate Button Removed**
   - Now automatic before generation
   - **Migration:** User behavior changes but outcome is better

2. **No Manual Recalculate Action**
   - Can no longer recalculate without generating
   - **Workaround:** Export YAML triggers auto-recalculate

---

## Testing Strategy

### Integration Tests Required

**File:** `netbox_hedgehog/tests/test_topology_planning/test_unified_generate.py`

**Test Cases:**

1. **Initial Generation (Never Generated)**
   ```python
   def test_initial_generation_creates_devices():
       """First-time generation creates all devices"""
       # Setup: plan with server/switch classes, no prior generation
       # Action: POST to generate_update
       # Assert:
       #   - Devices created
       #   - GenerationState created
       #   - needs_regeneration == False
       #   - Success message shown
   ```

2. **Update After Plan Change**
   ```python
   def test_update_after_plan_change():
       """Regeneration after plan modification updates devices"""
       # Setup: plan with generated devices, then modify quantities
       # Action: POST to generate_update
       # Assert:
       #   - Old devices deleted
       #   - New devices created with updated quantities
       #   - GenerationState updated
       #   - needs_regeneration == False after update
   ```

3. **Idempotent Regeneration (No Changes)**
   ```python
   def test_idempotent_regeneration():
       """Regenerating without plan changes is safe"""
       # Setup: plan with generated devices, no modifications
       # Action: POST to generate_update twice
       # Assert:
       #   - Device count unchanged
       #   - GenerationState timestamp updated
       #   - needs_regeneration == False
   ```

4. **Auto-Recalculate Before Generation**
   ```python
   def test_auto_recalculate():
       """Generation auto-recalculates switch quantities"""
       # Setup: plan with calculated_quantity=None
       # Action: POST to generate_update
       # Assert:
       #   - calculated_quantity populated
       #   - Devices created based on calculated quantities
   ```

5. **Sync Indicator States**
   ```python
   def test_sync_indicator_not_generated():
       """Indicator shows 'Not Generated' for new plan"""

   def test_sync_indicator_in_sync():
       """Indicator shows 'In Sync' after generation"""

   def test_sync_indicator_out_of_sync():
       """Indicator shows 'Out of Sync' after plan modification"""
   ```

6. **Permission Enforcement**
   ```python
   def test_generate_requires_change_permission():
       """Generate button requires change permission"""
       # Setup: user without change_topologyplan permission
       # Action: POST to generate_update
       # Assert: 403 Forbidden
   ```

7. **Error Handling**
   ```python
   def test_error_no_server_classes():
       """Error shown when plan has no server classes"""

   def test_error_calculation_failure():
       """Warning shown but generation continues on calc error"""
   ```

### View Tests Required

1. **GET Detail Page**
   - Sync indicator renders correctly for all states
   - Button text changes based on state
   - Preview link visible

2. **POST Generate/Update**
   - 200 response with redirect
   - Success message includes device count
   - GenerationState created/updated

---

## Database Impact

### No Schema Changes Required

✅ All existing models support this design:
- `TopologyPlan` - already has `last_generated_at` and `needs_regeneration` properties
- `GenerationState` - already tracks snapshot and provides `is_dirty()`
- `Device`, `Interface`, `Cable` - already support custom fields and tags

### Data Migration

✅ No data migration needed:
- Existing GenerationState records remain valid
- Existing generated devices already have correct tags and custom fields

---

## Performance Considerations

| Operation | Complexity | Mitigation |
|-----------|------------|------------|
| Auto-recalculate | O(switch_classes) | Already optimized; runs in <1s for typical plans |
| Device cleanup | O(devices) | Scoped by plan_id; bulk delete; fast |
| Device creation | O(devices) | Bulk create where possible; atomic transaction |
| Snapshot comparison | O(classes) | JSON comparison; fast for typical plan sizes |

**Expected Performance:**
- Plan with 150 devices: <5 seconds total
- Plan with 1000 devices: <30 seconds total

**Timeout Consideration:**
- NetBox default request timeout: 300 seconds
- If generation exceeds timeout, consider async task queue (future enhancement)

---

## Security Considerations

1. **Permission Enforcement**
   - View-level and template-level checks
   - No IDOR vulnerability (plan lookup by PK with permission check)

2. **Scoped Deletion**
   - Only deletes devices with matching `hedgehog_plan_id`
   - Cannot accidentally delete devices from other plans

3. **Transaction Safety**
   - `@transaction.atomic` ensures all-or-nothing generation
   - Rollback on any failure prevents partial state

4. **XSS Protection**
   - Success message uses `mark_safe()` for HTML link
   - URL parameters properly escaped

---

## Future Enhancements (Out of Scope for This Issue)

1. **Async Generation**
   - For very large plans (>500 devices)
   - Background task with progress indicator
   - Requires Django-Q or Celery

2. **Dry-Run Mode**
   - Preview what would change without executing
   - Diff view showing adds/removes/updates

3. **Partial Updates**
   - Only update changed devices (vs delete-all-recreate)
   - More complex but faster for incremental changes

4. **Audit Log**
   - Track each generation with user, timestamp, change summary
   - Integration with NetBox change logging

5. **Connection Change Detection**
   - Currently only tracks server/switch class quantities
   - Could track connection definitions, port zones, etc.

---

## Migration Plan

### Phase 1: Implementation (This Issue)
1. Create `TopologyPlanGenerateUpdateView`
2. Update `topologyplan.html` template (button + sync indicator)
3. Update URLs (add unified endpoint, deprecate recalculate)
4. Add integration tests
5. Update user documentation

### Phase 2: Deprecation Notice
1. Add deprecation warning to old generate endpoint (if accessed directly)
2. Monitor usage via logging
3. After 2 releases, remove legacy redirect view

### Phase 3: Cleanup
1. Remove `TopologyPlanRecalculateView` entirely
2. Remove preview page if unused
3. Simplify URL patterns

---

## Success Criteria

| Criteria | Measurement |
|----------|-------------|
| Single button action | ✅ One "Generate/Update Devices" button replaces two |
| Auto-recalculate | ✅ No manual recalculate step required |
| Sync visibility | ✅ Indicator on detail page shows in/out of sync |
| User feedback | ✅ Success message includes device count + link |
| Idempotent | ✅ Multiple clicks safe, deterministic results |
| Tests passing | ✅ All integration tests green |
| No regressions | ✅ Existing generated devices still work |

---

## Questions for Review

1. **Preview Page:** Keep as optional or remove entirely?
   - **Proposed:** Keep as "Advanced" option for power users

2. **Recalculate Export:** Should YAML export still auto-recalculate?
   - **Proposed:** Yes, keep that behavior (already implemented)

3. **Button Text:** Is "Update Devices" clear enough when out of sync?
   - **Alternative:** "Sync Devices", "Regenerate Devices"

4. **Sync Indicator Location:** Info card only, or also in Actions card?
   - **Proposed:** Info card primary, Actions card summary

---

## Approval Checklist

- [ ] Research findings reviewed and accepted
- [ ] Architecture design reviewed and accepted
- [ ] Success criteria agreed upon
- [ ] Error handling strategy approved
- [ ] Testing strategy approved
- [ ] Ready to proceed to Technical Specification phase

---
**End of Architecture Design**
