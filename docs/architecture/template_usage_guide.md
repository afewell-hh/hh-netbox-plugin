# Fabric Template Architecture Usage Guide

## Overview

The new consolidated fabric template architecture provides a DRY (Don't Repeat Yourself) approach to template management with significant improvements in maintainability and performance.

## Architecture Components

### 1. Master Template: `fabric_master.html`

The base template that provides:
- Common layout structure
- Shared CSS and JavaScript includes
- Standard header, navigation, and footer
- Block definitions for customization

**Usage:**
```django
{% extends "fabric_master.html" %}
{% block fabric_content %}
    <!-- Your fabric-specific content -->
{% endblock %}
```

### 2. Consolidated Templates

#### `fabric_detail_consolidated.html`
Replaces all fabric detail variants with conditional rendering:
- Enhanced progressive disclosure mode (`view_mode="enhanced"`)  
- Simple traditional mode (default)
- Automatic component inclusion

**View Context:**
```python
context = {
    'object': fabric,
    'view_mode': 'enhanced',  # or 'simple'
    'fabric_sidebar': True,
}
```

#### `fabric_list_consolidated.html`
Unified list view with:
- Responsive table layout
- Integrated status indicators  
- Bulk action support
- Pagination handling

#### `fabric_edit_consolidated.html`
Consolidated edit form with:
- Modular form sections
- Enhanced validation
- Conditional field visibility
- Error handling

### 3. Reusable Components

Located in `components/fabric/`:

#### Status and Display Components:
- `status_bar.html` - Top-level status overview
- `status_indicator.html` - Individual status badges
- `connection_info_panel.html` - Connection details
- `git_config_panel.html` - Git configuration display
- `crd_stats_panel.html` - CRD statistics

#### Form Components:
- `edit_basic_info.html` - Basic information form section
- `edit_kubernetes_config.html` - Kubernetes configuration section
- `edit_git_config.html` - Git configuration section

#### Action Components:
- `action_buttons.html` - Fabric action buttons panel
- `table_action_buttons.html` - Table row actions
- `pagination.html` - Pagination controls

#### Data Display Components:
- `basic_info_table.html` - Basic fabric information table
- `git_sync_table.html` - Git sync status table
- `kubernetes_sync_table.html` - Kubernetes sync table
- `drift_info_table.html` - Drift detection information
- `error_info_table.html` - Error information display

#### JavaScript:
- `common_scripts.html` - Shared fabric JavaScript functions

## Usage Patterns

### 1. Creating New Fabric Views

```django
{% extends "fabric_master.html" %}
{% load static %}

{% block fabric_title %}My Custom View{% endblock %}

{% block fabric_header_title %}Custom Fabric View{% endblock %}

{% block fabric_content %}
    {% include "components/fabric/status_bar.html" %}
    
    <div class="custom-content">
        <!-- Your custom content -->
        {% include "components/fabric/basic_info_table.html" %}
    </div>
{% endblock %}

{% block fabric_sidebar %}
    {% include "components/fabric/git_config_panel.html" %}
    {% include "components/fabric/action_buttons.html" %}
{% endblock %}
```

### 2. Customizing Component Behavior

Components accept parameters via `with` statements:

```django
{% include "components/fabric/status_indicator.html" with type="connection" status=object.connection_status %}

{% include "components/fabric/action_buttons.html" with show_delete_actions=True %}

{% include "components/fabric/git_config_panel.html" with compact_mode=True %}
```

### 3. Adding New Components

1. Create component file in `components/fabric/`
2. Follow naming convention: `descriptive_name.html`
3. Accept parameters via context variables
4. Include appropriate CSS classes for consistency

Example component structure:
```django
{% load static %}

<div class="my-component card">
    <div class="card-header">
        <h5 class="card-title mb-0">
            <i class="mdi mdi-icon"></i> {{ title|default:"Default Title" }}
        </h5>
    </div>
    <div class="card-body">
        <!-- Component content -->
        {% if show_actions|default:True %}
            <div class="component-actions">
                <!-- Action buttons -->
            </div>
        {% endif %}
    </div>
</div>
```

## Block Reference

### `fabric_master.html` Blocks:

- `fabric_title` - Page title
- `fabric_subtitle` - Page subtitle  
- `fabric_styles` - Additional CSS
- `fabric_header_title` - Header title text
- `fabric_header_actions` - Header action buttons
- `fabric_breadcrumbs` - Breadcrumb items
- `fabric_content` - Main content area
- `fabric_sidebar` - Sidebar content (if `fabric_sidebar=True`)
- `fabric_scripts` - Additional JavaScript

### Context Variables:

- `object` - Current fabric object
- `fabric_sidebar` - Enable/disable sidebar (boolean)
- `show_status_bar` - Show/hide status bar (boolean)
- `show_breadcrumbs` - Show/hide breadcrumbs (boolean)
- `view_mode` - Template rendering mode ('enhanced', 'simple')

## JavaScript Integration

### Common Functions Available:

```javascript
// From common_scripts.html
window.FabricCommon = {
    performSync: function(fabricId, syncType, button) { ... },
    testConnection: function(fabricId, button) { ... },
    showAlert: function(type, message, duration) { ... },
    getCsrfToken: function() { ... }
};
```

### Adding Custom JavaScript:

```django
{% block fabric_scripts %}
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        // Your custom JavaScript
        
        // Use common functions
        document.querySelector('.my-sync-btn').addEventListener('click', function(e) {
            e.preventDefault();
            window.FabricCommon.performSync(fabricId, 'git', this);
        });
    });
    </script>
{% endblock %}
```

## CSS Classes Reference

### Standard Classes:
- `.fabric-wrapper` - Main container
- `.fabric-header` - Page header
- `.fabric-content` - Main content area
- `.fabric-sidebar` - Sidebar area
- `.fabric-actions` - Action button containers
- `.status-indicator` - Status badge components
- `.info-grid` - Information grid layout
- `.operation-controls` - Operation button groups

### Status Classes:
- `.bg-success` - Success/connected state
- `.bg-warning` - Warning/drift detected state
- `.bg-danger` - Error/failed state
- `.bg-info` - Information/in-progress state
- `.bg-secondary` - Inactive/disabled state

## Migration Guide

### From Old Templates to New:

1. **Replace extends:**
   ```django
   <!-- Old -->
   {% extends "base/layout.html" %}
   
   <!-- New -->
   {% extends "fabric_master.html" %}
   ```

2. **Update content blocks:**
   ```django
   <!-- Old -->
   {% block content %}
   
   <!-- New -->
   {% block fabric_content %}
   ```

3. **Replace duplicated code with components:**
   ```django
   <!-- Old -->
   <div class="status-info">
       <span class="badge bg-success">Connected</span>
   </div>
   
   <!-- New -->
   {% include "components/fabric/status_indicator.html" with type="connection" status="connected" %}
   ```

## Performance Considerations

### Template Caching:
- Components are cached automatically by Django
- Use `{% load cache %}` for expensive operations
- Consider fragment caching for dynamic content

### Asset Optimization:
- CSS/JS automatically minified in production
- Components loaded on-demand
- Reduced HTTP requests through consolidation

### Best Practices:
- Use conditional rendering instead of separate templates
- Minimize database queries in templates
- Leverage component reusability
- Implement progressive enhancement

## Troubleshooting

### Common Issues:

1. **Component not found:**
   - Check file path: `components/fabric/component_name.html`
   - Verify template directory structure
   - Ensure proper capitalization

2. **Missing context variables:**
   - Pass required variables via `with` statement
   - Check view context preparation
   - Verify variable names match

3. **JavaScript errors:**
   - Ensure `common_scripts.html` is included
   - Check for CSRF token availability
   - Verify event delegation setup

4. **Styling issues:**
   - Check CSS class names
   - Verify bootstrap classes
   - Ensure responsive grid usage

### Debugging:

```django
<!-- Enable template debugging -->
{% if debug %}
    <div class="debug-info">
        <strong>Template:</strong> {{ request.resolver_match.url_name }}<br>
        <strong>Object:</strong> {{ object }}<br>
        <strong>Context:</strong> {{ view_mode }}
    </div>
{% endif %}
```

## Future Enhancements

### Planned Features:
- Progressive Web App (PWA) support
- Advanced caching strategies  
- Component lazy loading
- Template performance analytics
- Automated accessibility testing

### Extension Points:
- Custom theme support
- Plugin architecture for components
- Template inheritance validation
- Performance monitoring hooks

---

For questions or issues, refer to the architectural documentation or create an issue in the project repository.