# Fabric Template Architecture Consolidation Plan

## Current State Analysis

### Template Inventory (25 fabric-related templates identified):
1. **Core Templates (3)**:
   - `fabric_detail.html` (2491 lines) - Main detail view
   - `fabric_edit.html` (205 lines) - Edit form  
   - `fabric_list.html` (292 lines) - List view

2. **Variant Templates (13)**:
   - `fabric_detail_clean.html` (291 lines)
   - `fabric_detail_enhanced.html` (437 lines) 
   - `fabric_detail_minimal.html` (100 lines)
   - `fabric_detail_simple.html` (488 lines)
   - `fabric_detail_standalone.html` (286 lines)
   - `fabric_detail_working.html` (286 lines)
   - `fabric_edit_debug.html` (20 lines)
   - `fabric_edit_minimal.html` (19 lines)
   - `fabric_edit_simple.html` (203 lines)
   - `fabric_list_clean.html` (181 lines)
   - `fabric_list_fixed.html` (175 lines)
   - `fabric_list_simple.html` (90 lines)
   - `fabric_list_working.html` (176 lines)

3. **Specialized Templates (6)**:
   - `fabric_confirm_delete.html` (248 lines)
   - `fabric_crds.html` (192 lines)
   - `fabric_creation_workflow.html` (1185 lines)
   - `fabric_delete_safe.html` (61 lines)
   - `fabric_overview.html` (338 lines)
   - `pre_cluster_fabric_form.html` (included in count)

4. **Component Templates (3)**:
   - `components/fabric_filter.html`
   - `components/fabric_filter_enhanced.html`
   - `components/fabric_filter_simple.html`

**Total Line Count: 7,764 lines across 25 templates**

## Duplication Analysis

### Common Patterns Identified:
1. **Base Structure**: All extend "base/layout.html"
2. **CSS Includes**: Repeated hedgehog.css imports
3. **JavaScript**: Similar sync functionality across templates
4. **Status Indicators**: Repeated badge/status logic
5. **Form Structures**: Duplicate form elements
6. **Action Buttons**: Repeated button groups
7. **Navigation**: Similar breadcrumb/header patterns

### Code Duplication Metrics:
- **Estimated 60-70% code duplication** across variant templates
- **Common CSS blocks**: ~200 lines repeated 8+ times
- **JavaScript functions**: ~150 lines of sync code repeated 6+ times  
- **Status/badge logic**: ~50 lines repeated 12+ times

## Proposed Consolidation Architecture

### New Template Hierarchy:

```
base/layout.html (NetBox base)
└── fabric_master.html (NEW - Fabric base template)
    ├── fabric_detail.html (Consolidated detail view)
    ├── fabric_edit.html (Consolidated edit form)
    ├── fabric_list.html (Consolidated list view)
    ├── fabric_delete.html (Consolidated delete form)
    └── fabric_workflow.html (Consolidated workflow form)
```

### Component Structure:

```
components/
├── fabric/
│   ├── status_indicators.html (NEW)
│   ├── sync_controls.html (NEW)
│   ├── connection_info.html (NEW)
│   ├── git_config_panel.html (NEW)
│   ├── crd_stats.html (NEW)
│   ├── action_buttons.html (NEW)
│   └── filter_form.html (Consolidated)
└── shared/
    ├── progressive_disclosure.html (NEW)
    └── real_time_status.html (NEW)
```

## Implementation Strategy

### Phase 1: Master Template Creation
1. Create `fabric_master.html` with:
   - Common CSS/JS includes
   - Shared block definitions
   - Common navigation structure
   - Standard action patterns

### Phase 2: Component Extraction  
1. Extract reusable components:
   - Status indicators and badges
   - Sync control panels
   - Form field groups
   - Navigation elements

### Phase 3: Template Consolidation
1. Consolidate variants into single templates with:
   - Conditional rendering based on context
   - Block overrides for customization
   - Parameter-driven display modes

### Phase 4: Legacy Cleanup
1. Remove redundant templates:
   - Keep only core consolidated templates
   - Archive old variants as references
   - Update all URL references

## Target Architecture Benefits

### Quantified Improvements:
- **Template Count**: 25 → 8 templates (68% reduction)
- **Code Lines**: 7,764 → ~3,500 lines (55% reduction)  
- **Duplication**: 60-70% → <10% duplication
- **Maintenance**: Single source of truth for each component

### Visual Preservation Strategy:
- **CSS Classes**: All existing classes preserved
- **DOM Structure**: Maintain identical element hierarchy
- **JavaScript**: Preserve all existing functionality
- **Responsive**: Maintain all breakpoint behaviors

## Implementation Plan

### Step 1: Create Master Template
```django
<!-- fabric_master.html -->
{% extends "base/layout.html" %}
{% load static %}

{% block header %}
    {{ block.super }}
    <link rel="stylesheet" href="{% static 'netbox_hedgehog/css/hedgehog.css' %}">
    {% block fabric_styles %}{% endblock %}
{% endblock %}

{% block content %}
<div class="fabric-wrapper">
    {% block fabric_header %}
        {% include "components/fabric/header.html" %}
    {% endblock %}
    
    {% block fabric_content %}{% endblock %}
</div>
{% endblock %}

{% block javascript %}
    {{ block.super }}
    {% include "components/fabric/scripts.html" %}
    {% block fabric_scripts %}{% endblock %}
{% endblock %}
```

### Step 2: Extract Components
1. **Status Indicators Component**:
   ```django
   <!-- components/fabric/status_indicators.html -->
   <div class="status-cards">
       <div class="status-card">
           <div class="status-card-title">{{ title }}</div>
           <div class="status-card-value">{{ value }}</div>
           <div class="status-card-subtitle">{{ subtitle }}</div>
       </div>
   </div>
   ```

2. **Sync Controls Component**:
   ```django
   <!-- components/fabric/sync_controls.html -->
   <div class="sync-controls">
       {% if object.sync_enabled %}
           <button class="btn btn-primary sync-btn" data-fabric-id="{{ object.pk }}">
               <i class="mdi mdi-sync"></i> Sync
           </button>
       {% endif %}
   </div>
   ```

### Step 3: Consolidate Templates
1. **Unified fabric_detail.html**:
   ```django
   {% extends "fabric_master.html" %}
   
   {% block fabric_content %}
       {% include "components/fabric/status_indicators.html" %}
       {% if view_mode == "enhanced" %}
           {% include "components/fabric/progressive_disclosure.html" %}
       {% endif %}
       {% include "components/fabric/connection_info.html" %}
   {% endblock %}
   ```

## Validation Strategy

### Visual Testing:
1. **Screenshot comparison** of all original templates
2. **DOM structure validation** using automated tools
3. **CSS class preservation** verification
4. **JavaScript functionality** testing

### Performance Metrics:
1. **Template rendering time** comparison
2. **File size reduction** measurements  
3. **HTTP request optimization** analysis
4. **Browser caching** efficiency gains

## Success Metrics

### Quantitative Goals:
- [ ] **68% reduction** in template count (25 → 8)
- [ ] **55% reduction** in total code lines  
- [ ] **<10% code duplication** remaining
- [ ] **Zero visual changes** in rendered output
- [ ] **100% functionality preservation**

### Qualitative Goals:
- [ ] Single source of truth for each UI component
- [ ] Improved maintainability and extensibility
- [ ] Consistent styling and behavior
- [ ] Enhanced developer experience
- [ ] Future-proof architecture for new features

## Risk Mitigation

### Identified Risks:
1. **Breaking visual consistency** - Mitigated by screenshot testing
2. **JavaScript functionality loss** - Mitigated by comprehensive testing
3. **Performance regression** - Mitigated by benchmarking
4. **Template inheritance complexity** - Mitigated by clear documentation

### Rollback Strategy:
1. **Preserve original templates** during development
2. **Feature flag system** for gradual rollout
3. **Automated testing suite** for regression detection
4. **Staged deployment** with validation checkpoints

---

**Next Phase**: Begin implementation with fabric_master.html creation and component extraction.