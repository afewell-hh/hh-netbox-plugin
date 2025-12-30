# Issue #127 Research Findings
**Date:** 2025-12-29
**Issue:** DIET: Unify Generate/Update Devices flow + sync status indicator
**Phase:** Research (Step 1 of 5)

---

## Executive Summary

The topology plan detail page currently has **two separate buttons** that confuse users:
1. **"Generate Devices"** - Creates NetBox devices/interfaces/cables
2. **"Recalculate Switch Quantities"** - Updates calculated switch counts

**Key Finding:** Most of the infrastructure for unified generate/update is **already implemented**:
- ✅ `GenerationState` model tracks generation timestamp, counts, and plan snapshot
- ✅ `TopologyPlan.needs_regeneration` property detects plan changes
- ✅ `DeviceGenerator._cleanup_generated_objects()` deletes old devices before creating new ones
- ✅ Generation preview page shows sync status (but users don't see it until they click the button)

**The Problem:**
- Users perceive two distinct actions when there should be one
- Recalculate is manual when it should be automatic before generation
- Main detail page has **no sync status indicator** - user can't tell if devices are out of sync
- After clicking "Generate Devices", user gets redirected with a success message but no visible evidence of what changed

---

## Current Implementation Analysis

### 1. Button Actions (Template)

**File:** `netbox_hedgehog/templates/netbox_hedgehog/topologyplan.html`

```html
<!-- Lines 44-56 -->
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
```

**Issues:**
- Two buttons with unclear relationship
- "Generate Devices" is a link (GET) that leads to a preview page
- "Recalculate" is a form POST that redirects back to detail page
- No sync status indicator visible on this page

### 2. Generate Device Flow

**View:** `TopologyPlanGenerateView` in `netbox_hedgehog/views/topology_planning.py` (lines 120-189)

```python
def get(self, request, pk):
    # Shows preview page with counts and warnings
    plan = get_object_or_404(models.TopologyPlan, pk=pk)
    context = self._build_context(plan)  # Includes needs_regeneration
    return render(request, self.template_name, context)

def post(self, request, pk):
    # Actually runs generation
    generator = DeviceGenerator(plan=plan)
    result = generator.generate_all()

    messages.success(request, f"Generation complete: {result.device_count} devices, ...")
    return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=plan.pk)
```

**Preview Template:** `topologyplan_generate.html` (lines 52-64)

```html
{% if generation_state %}
    <p class="text-warning mb-1">
        Previously generated at {{ generation_state.generated_at }}
    </p>
    {% if needs_regeneration %}
        <p class="text-warning mb-0">Plan has changed since last generation.</p>
    {% else %}
        <p class="text-muted mb-0">Plan has not changed since last generation.</p>
    {% endif %}
{% else %}
    <p class="text-muted mb-0">No previous generation detected.</p>
{% endif %}
```

**Flow Diagram:**
```
User clicks "Generate Devices" button
    ↓
GET /topology-plans/{pk}/generate/
    ↓
Preview page shown (with sync status)
    ↓
User clicks "Generate Devices" on preview page
    ↓
POST /topology-plans/{pk}/generate/
    ↓
DeviceGenerator.generate_all() runs
    ├─→ _cleanup_generated_objects() - deletes old devices/cables
    ├─→ _create_switch_devices()
    ├─→ _create_server_devices()
    ├─→ _create_connections()
    ├─→ _tag_objects()
    └─→ _upsert_generation_state() - saves new GenerationState
    ↓
Redirect to detail page with success message
```

**Issues:**
- Two-step process (preview then confirm) for every generation
- Sync status only visible on preview page, not on main detail page
- Success message shows counts but user has no visual confirmation devices were created
- If generation fails silently (no exception), user sees success message anyway

### 3. Recalculate Flow

**View:** `TopologyPlanRecalculateView` in `netbox_hedgehog/views/topology_planning.py` (lines 191-226)

```python
def post(self, request, pk):
    plan = get_object_or_404(models.TopologyPlan, pk=pk)

    # Run calculation engine
    result = update_plan_calculations(plan)

    # Show success message
    messages.success(request, f"Recalculated {len(result['summary'])} switch classes...")

    # Redirect back to detail page
    return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=pk)
```

**Issues:**
- Separate manual action when it should be automatic before generation
- User must remember to click this before generating devices
- No indication on detail page whether recalculation is needed

### 4. Device Generation Implementation

**Service:** `DeviceGenerator` in `netbox_hedgehog/services/device_generator.py`

```python
class DeviceGenerator:
    def _cleanup_generated_objects(self) -> None:
        """Delete all previously generated objects for this plan."""
        # Delete cables first (to avoid termination protection)
        cables_to_delete = Cable.objects.filter(
            tags__slug=self.DEFAULT_TAG_SLUG,
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        )
        cables_to_delete.delete()

        # Delete devices (interfaces cascade)
        devices_to_delete = Device.objects.filter(
            tags__slug=self.DEFAULT_TAG_SLUG,
            custom_field_data__hedgehog_plan_id=str(self.plan.pk)
        )
        devices_to_delete.delete()

    @transaction.atomic
    def generate_all(self) -> GenerationResult:
        """Generate devices, interfaces, and cables. Deletes old objects first."""
        # Delete old generated objects
        self._cleanup_generated_objects()

        devices = []
        interfaces = []
        cables = []

        switch_devices = self._create_switch_devices(devices)
        server_devices = self._create_server_devices(devices)
        interfaces, cables = self._create_connections(switch_devices, server_devices)

        self._tag_objects(devices, interfaces, cables)
        self._upsert_generation_state(
            device_count=len(devices),
            interface_count=len(interfaces),
            cable_count=len(cables),
        )

        return GenerationResult(...)

    def _upsert_generation_state(self, device_count, interface_count, cable_count):
        """Save generation state with snapshot of plan."""
        GenerationState.objects.filter(plan=self.plan).delete()
        state = GenerationState(
            plan=self.plan,
            device_count=device_count,
            interface_count=interface_count,
            cable_count=cable_count,
            snapshot=self._build_snapshot(),
            status=GenerationStatusChoices.GENERATED,
        )
        state.save()
```

**Key Features:**
- ✅ Uses `hedgehog-generated` tag to mark all generated objects
- ✅ Uses `hedgehog_plan_id` custom field to scope objects to specific plan
- ✅ Deletes old objects before creating new ones (regeneration works!)
- ✅ Atomic transaction ensures all-or-nothing generation
- ✅ Saves GenerationState with snapshot for change detection

**Issues Found:**
- ❌ No explicit call to `update_plan_calculations()` before generation
- ❌ If calculated_quantity is None/0, generation will fail silently (0 switches created)

### 5. Sync Status Tracking

**Model:** `GenerationState` in `netbox_hedgehog/models/topology_planning/generation.py`

```python
class GenerationState(models.Model):
    """Tracks generation state for a TopologyPlan."""

    plan = models.OneToOneField(
        to='netbox_hedgehog.TopologyPlan',
        on_delete=models.CASCADE,
        related_name='generation_state',
    )

    generated_at = models.DateTimeField(auto_now_add=True)
    device_count = models.IntegerField()
    interface_count = models.IntegerField()
    cable_count = models.IntegerField()
    snapshot = models.JSONField()  # Plan state at generation time
    status = models.CharField(choices=GenerationStatusChoices, default='generated')

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
```

**TopologyPlan Properties:**

```python
@property
def last_generated_at(self):
    """Timestamp of last generation."""
    try:
        return self.generation_state.generated_at
    except AttributeError:
        return None  # Never generated

@property
def needs_regeneration(self):
    """Check if plan needs regeneration."""
    try:
        return self.generation_state.is_dirty()
    except AttributeError:
        return False  # Never generated
```

**Snapshot Structure:**
```json
{
  "server_classes": [
    {"server_class_id": "GPU-B200", "quantity": 32},
    {"server_class_id": "STORAGE-A", "quantity": 9}
  ],
  "switch_classes": [
    {"switch_class_id": "fe-gpu-leaf", "effective_quantity": 2},
    {"switch_class_id": "fe-spine", "effective_quantity": 2}
  ]
}
```

**Change Detection Logic:**
- Compares current `server_class.quantity` vs snapshot
- Compares current `switch_class.effective_quantity` vs snapshot
- Returns `True` if **any** class ID, quantity, or effective_quantity differs

**Issues:**
- ✅ Change detection works correctly
- ❌ Not displayed on main detail page (only on preview page)
- ❌ Doesn't track connection changes (only server/switch quantities)

---

## Root Cause Analysis

### Why Users See "Hang" After Generation

1. User clicks "Generate Devices" button
2. Browser navigates to preview page `/topology-plans/{pk}/generate/`
3. User sees preview, clicks "Generate Devices" on preview
4. POST request runs `generate_all()` successfully
5. Redirect to detail page `/topology-plans/{pk}/`
6. **Problem:** Detail page looks identical to before
   - No visible difference in UI
   - Success message appears in messages framework (top banner)
   - But user expects to SEE the generated devices somewhere on the page
   - No device list, no counts, no status change

**The "hang" is actually a UX problem:** The operation succeeds, but there's no visual feedback on the detail page itself showing what changed.

### Why Two Buttons Exist

Historical context (inferred):
- **"Recalculate"** was added first to update `calculated_quantity` fields
- **"Generate Devices"** was added later for actual NetBox object creation
- Originally separate concerns, but now tightly coupled:
  - Generation depends on calculated_quantity being up-to-date
  - User must manually ensure calculations are current before generating

**Should be:** One unified action that auto-recalculates then generates/updates.

---

## Gap Analysis

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| Single unified action | Two separate buttons | ❌ Need to merge |
| Auto-recalculate before generate | Manual "Recalculate" button | ❌ Need to integrate |
| Sync status on detail page | Only on preview page | ❌ Need to add indicator |
| Visual confirmation of generation | Success message only | ❌ Need device counts/links |
| Idempotent regeneration | ✅ Deletes old, creates new | ✅ Works |
| Change detection | ✅ GenerationState.is_dirty() | ✅ Works |
| Scoped cleanup | ✅ hedgehog_plan_id filter | ✅ Works |

---

## Proposed Solution (High-Level)

### 1. Unified Action Button

**Replace two buttons with one:**

```html
<!-- Current -->
<a href="...generate/" class="btn btn-warning">Generate Devices</a>
<form action="...recalculate/"><button>Recalculate</button></form>

<!-- Proposed -->
<form method="post" action="{% url 'plugins:netbox_hedgehog:topologyplan_generate_update' pk=object.pk %}">
    {% csrf_token %}
    <button type="submit" class="btn btn-primary">
        <i class="mdi mdi-sync"></i>
        {% if object.last_generated_at %}
            Update Devices
        {% else %}
            Generate Devices
        {% endif %}
    </button>
</form>
```

**Behavior:**
- POST directly (no preview page)
- Auto-recalculates before generation
- Returns to detail page with updated sync status

### 2. Sync Status Indicator on Detail Page

**Add to detail page template (lines 19-27 area):**

```html
<tr>
    <th scope="row">Device Generation</th>
    <td>
        {% if object.last_generated_at %}
            {% if object.needs_regeneration %}
                <span class="badge badge-warning">
                    <i class="mdi mdi-alert"></i> Out of Sync
                </span>
                <small class="text-muted d-block">
                    Last generated {{ object.last_generated_at|timesince }} ago.
                    Plan has changed since generation.
                </small>
            {% else %}
                <span class="badge badge-success">
                    <i class="mdi mdi-check"></i> In Sync
                </span>
                <small class="text-muted d-block">
                    Generated {{ object.last_generated_at|timesince }} ago
                    ({{ object.generation_state.device_count }} devices).
                </small>
            {% endif %}
        {% else %}
            <span class="badge badge-secondary">Not Generated</span>
        {% endif %}
    </td>
</tr>
```

### 3. Enhanced Success Feedback

**After generation succeeds, show:**
- Device count with link to device list filtered by plan
- Interface count
- Cable count
- Timestamp

```python
messages.success(
    request,
    mark_safe(
        f'Devices updated successfully: '
        f'<a href="{device_list_url}?hedgehog_plan_id={plan.pk}">'
        f'{result.device_count} devices</a>, '
        f'{result.interface_count} interfaces, '
        f'{result.cable_count} cables.'
    )
)
```

### 4. Auto-Recalculate Before Generation

**Modify `TopologyPlanGenerateView.post()` to:**

```python
def post(self, request, pk):
    plan = get_object_or_404(models.TopologyPlan, pk=pk)

    # Auto-recalculate before generation
    calc_result = update_plan_calculations(plan)

    # Warn if calculation had errors
    if calc_result['errors']:
        for error_info in calc_result['errors']:
            messages.warning(request, f"Calculation error: {error_info['error']}")

    # Run generation
    generator = DeviceGenerator(plan=plan)
    result = generator.generate_all()

    # Enhanced success message
    messages.success(request, ...)

    return redirect('plugins:netbox_hedgehog:topologyplan_detail', pk=pk)
```

---

## Files Requiring Changes

| File | Changes | Priority |
|------|---------|----------|
| `netbox_hedgehog/templates/netbox_hedgehog/topologyplan.html` | Replace two buttons with one; add sync indicator | HIGH |
| `netbox_hedgehog/views/topology_planning.py` | Merge generate/recalculate; auto-recalc before generate | HIGH |
| `netbox_hedgehog/urls.py` | Update URL patterns | MEDIUM |
| `specs/DIET-XXX-unified-generate.md` | New spec document | HIGH |
| `netbox_hedgehog/tests/test_topology_planning/test_unified_generate.py` | New integration tests | HIGH |

---

## Next Steps (Per Issue Requirements)

1. ✅ **Research** - COMPLETE (this document)
2. ⏭️ **Architecture / Design** - Design unified action flow
3. ⏭️ **Technical Specification** - Write spec in `specs/`
4. ⏭️ **Test Definitions** - Define UX-accurate integration tests
5. ⏭️ **Review Gate** - Present research + architecture + spec
6. ⏭️ **Implementation** - Only after approval

---

## Questions for Review

1. **Preview Page:** Should we keep the preview page as an optional "Advanced" flow, or eliminate it entirely?
   - **Recommendation:** Keep it as optional. Add "Advanced" link next to button for users who want to preview first.

2. **Recalculate Visibility:** Should "Recalculate" remain as a separate action for advanced users?
   - **Recommendation:** No. Auto-recalculate is safer and simpler. Advanced users can see calculated quantities in the table.

3. **Error Handling:** If recalculation fails, should generation proceed anyway or abort?
   - **Recommendation:** Show warnings but proceed. User may have override_quantity set.

4. **Sync Indicator Location:** Where should sync status appear?
   - **Recommendation:** In the main info card (lines 7-29) AND in the Actions card (lines 40-58).

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Users lose preview capability | Keep preview page accessible via "Advanced" link |
| Breaking existing workflows | Add tests for both new unified flow and legacy preview flow |
| Auto-recalculate changes quantities unexpectedly | Show calculation results in success/warning messages |
| Regeneration deletes devices user manually modified | Document that generated devices are managed by the plan; manual changes will be lost |

---

## Conclusion

**The good news:** Most infrastructure already exists. This is primarily a UX refactor, not a major architectural change.

**Required work:**
1. Merge two view actions into one
2. Add sync indicator to detail page template
3. Enhance success message feedback
4. Write comprehensive integration tests
5. Update documentation

**Estimated effort:** 2-3 days (including tests and review)

**Recommended approach:** Follow the strict process in issue #127:
1. Get approval on this research
2. Design detailed architecture
3. Write spec in `specs/`
4. Define integration tests
5. Get review approval
6. Implement

---
**End of Research Report**
