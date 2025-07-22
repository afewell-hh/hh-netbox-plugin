# Debug Steps: VPCs Page Not Showing Filter

## The Problem
You're visiting `/plugins/hedgehog/vpcs/` but not seeing the "Filter by Fabric" card.

## Possible Causes & Solutions

### 1. 🔄 **NetBox Needs Restart** (Most Likely)
**Problem**: NetBox is using cached Python code and hasn't loaded our changes.
**Solution**: 
```bash
# Restart your NetBox process
sudo systemctl restart netbox
# OR if running in development:
python manage.py runserver
```

### 2. 📁 **Template Loading Issue**
**Test**: Check if the template include is working by temporarily editing the template.

**Quick Test**:
Edit `/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/vpc_list_simple.html`

Replace line 9:
```html
{% include "netbox_hedgehog/components/fabric_filter.html" %}
```

With a simple test:
```html
<div class="alert alert-success">🧪 TEST: GitOps filter should appear here!</div>
```

Reload the page. If you see the green test message, templates are loading but the include has an issue.

### 3. 🎯 **Wrong URL Being Used**
**Check**: Make sure you're visiting the exact URL: `/plugins/hedgehog/vpcs/`

**Also try**:
- `/plugins/hedgehog/vpcs/?fabric=1` (should show filter with selection)
- `/plugins/hedgehog/connections/` (should also have filter)

### 4. 📊 **No Fabrics in Database**
**Problem**: Filter won't show if no fabrics exist.
**Check**: 
- Visit `/plugins/hedgehog/fabrics/` 
- Do you see any fabrics listed?
- If not, create a fabric first

### 5. 🐛 **Django Template Error**
**Check**: Look in Django/NetBox logs for errors like:
```
TemplateDoesNotExist: netbox_hedgehog/components/fabric_filter.html
TemplateSyntaxError: ...
```

### 6. 🔧 **View Context Issue**
The filter component expects certain context variables. Let me create a simple debug template:

**Create**: `/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/debug_filter.html`
```html
<div class="alert alert-info">
  <h6>Debug Info:</h6>
  <p>show_fabric_filter: {{ show_fabric_filter }}</p>
  <p>all_fabrics count: {{ all_fabrics|length }}</p>
  <p>selected_fabric: {{ selected_fabric }}</p>
  <p>fabric_filter_id: {{ fabric_filter_id }}</p>
</div>
```

Then in `vpc_list_simple.html`, replace the include with:
```html
{% include "netbox_hedgehog/debug_filter.html" %}
```

## 🚀 Quick Fix Attempt

Let me create a simplified version of the fabric filter that's more likely to work: