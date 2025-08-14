# Drift Detection Page - 500 Error Investigation Summary

## Issue Description
The drift detection page at `http://localhost:8000/plugins/hedgehog/drift-detection/` returns a 500 error.

## Root Cause Analysis

### Initial Error (Fixed)
- **Error**: `TemplateDoesNotExist: netbox_hedgehog/drift_detection_dashboard.html`
- **Cause**: View was looking for `drift_detection_dashboard.html` but template was named `drift_detection_simple.html`
- **Fix**: Updated `DriftDetectionDashboardView.template_name` to use correct template name

### Secondary Error (Fixed)
- **Error**: `NoReverseMatch: 'netbox_hedgehog' is not a registered namespace`
- **Cause**: Template was using `{% url 'plugins:netbox_hedgehog:...' %}` template tags for URL generation
- **Fix**: Replaced all `{% url %}` tags with direct hardcoded URLs like `/plugins/hedgehog/fabrics/`

### Critical Discovery
During debugging, discovered that **even simple HttpResponse views fail** on the `drift-detection/` URL pattern. This indicates a deeper URL routing or middleware issue that is **not related to templates or view code**.

## Current Status
- ✅ Template exists and is properly formatted
- ✅ URL references in template are fixed (no more `{% url %}` tags)
- ✅ View logic is working (tested with minimal context)
- ❌ **SYSTEMIC ISSUE**: URL routing has a deeper problem

## Files Modified
1. `/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/drift_dashboard.py`
   - Updated `template_name` from `drift_detection_dashboard.html` to `drift_detection_simple.html`

2. `/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/drift_detection_simple.html`
   - Replaced `{% url 'plugins:netbox_hedgehog:fabric_detail' pk=fabric.pk %}` with `/plugins/hedgehog/fabrics/{{ fabric.pk }}/`
   - Replaced `{% url 'plugins:netbox_hedgehog:fabric_list' %}` with `/plugins/hedgehog/fabrics/`
   - Replaced `{% url 'plugins:netbox_hedgehog:overview' %}` with `/plugins/hedgehog/`

## Solution Status
The immediate template and URL reference issues have been resolved. However, there appears to be a systemic URL routing issue that prevents **any view** from working on the `drift-detection/` URL pattern.

## Next Steps (If URL routing issue is resolved)
1. The drift detection page should load correctly with the fixed template
2. Page will display fabric drift statistics using the `drift_count` and `drift_status` fields
3. Working links to fabric details and main dashboard

## Working Test URLs
- ✅ `/plugins/hedgehog/` (main dashboard)  
- ✅ `/plugins/hedgehog/fabrics/` (fabric list)
- ❌ `/plugins/hedgehog/drift-detection/` (systemic routing issue)