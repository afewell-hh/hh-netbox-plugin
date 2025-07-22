# GitOps Features - GUI Visibility Guide

## 🔍 What You Should See in the GUI

### 1. Fabric Filtering on CR List Pages ✨

**Where to look**: Visit any CR list page (VPCs, Connections, Switches, etc.)
- **URL Examples**:
  - `/plugins/hedgehog/vpcs/`
  - `/plugins/hedgehog/connections/`
  - `/plugins/hedgehog/switches/`

**What you should see**:
- **Filter Card** at the top of the page with:
  - "Filter by Fabric" dropdown
  - "All Fabrics" option
  - "Clear Filter" button (when filter is active)
- **Test the filtering**:
  - Select a fabric from dropdown - page should reload showing only that fabric's CRs
  - URL should change to `?fabric=X` parameter
  - "View All CRDs for this Fabric" button appears

### 2. Enhanced Fabric Detail Page 🚀

**Where to look**: Visit a fabric detail page
- **URL**: `/plugins/hedgehog/fabrics/{fabric_id}/`

**What you should see**:
- **"Sync from HCKC" button** (blue) alongside "Sync from Git"
- **"Custom Resources" section** with:
  - "View All CRDs" button (primary blue)
  - Quick access buttons for VPCs, Connections, Switches
- **JavaScript functionality**: 
  - Buttons should show loading spinners when clicked
  - Success/error messages should appear

### 3. GitOps Edit Buttons on CR Detail Pages 💫

**Where to look**: Visit any CR detail page (VPC, Connection, etc.)
- **URL Examples**:
  - `/plugins/hedgehog/vpcs/{vpc_id}/`
  - `/plugins/hedgehog/connections/{conn_id}/`

**What you should see**:
- **GitOps Management Card** (blue border) with:
  - Current Status info (Fabric, Git File, Kubernetes Status, Last Synced)
  - **"Edit with GitOps" button** (primary blue)
  - "Preview YAML" button (outline info)
  - "GitOps Status" button (outline secondary)
- **Interactive modals** when clicking preview/status buttons

### 4. GitOps Edit Forms 📝

**Where to look**: Click "Edit with GitOps" button on any CR detail page
- **URLs**: `/plugins/hedgehog/gitops/{cr-type}/{id}/edit/`

**What you should see**:
- **GitOps Workflow Info** alert box explaining the workflow
- **Enhanced form** with:
  - All normal CR fields (spec, labels, annotations)
  - **"Git Commit Message" section** (blue card)
  - **Action buttons**: "Save with GitOps", "Preview YAML Changes", "Validate YAML"
  - **Current Status sidebar** showing GitOps information

### 5. New API Endpoints 🔧

**Test these URLs directly**:
- `/api/plugins/hedgehog/gitops-fabrics/{fabric_id}/hckc_sync/` (POST)
- `/api/plugins/hedgehog/gitops-fabrics/{fabric_id}/state-comparison/` (GET)
- `/plugins/hedgehog/api/gitops/yaml-preview/` (POST)
- `/plugins/hedgehog/fabrics/{fabric_id}/crds/` (GET)

## 🛠️ Troubleshooting - If You Don't See Changes

### Check 1: URL Routing
Verify our URLs are loaded by visiting:
- **Test URL**: `/plugins/hedgehog/` (should show overview)
- **Fabric List**: `/plugins/hedgehog/fabrics/` 
- **Any CR List**: `/plugins/hedgehog/vpcs/`

### Check 2: Template Loading
If pages show errors, check Django logs for:
```
TemplateDoesNotExist: netbox_hedgehog/components/fabric_filter.html
TemplateDoesNotExist: netbox_hedgehog/components/gitops_edit_button.html
```

### Check 3: Import Errors  
Look for Django startup errors related to:
```python
from .mixins import FabricFilterMixin
from .views import gitops_edit_views
from .services import HCKCStateService
```

### Check 4: Database Issues
Our changes require existing data:
- **Fabrics must exist** for filtering to work
- **CRs must exist** to see edit buttons
- **Git repositories** should be configured for full GitOps workflow

## 🧪 Quick Tests

### Test Fabric Filtering:
1. Go to `/plugins/hedgehog/vpcs/`
2. Look for filter dropdown at top
3. Select a fabric → URL should change to `/plugins/hedgehog/vpcs/?fabric=X`
4. Page should reload showing filtered results

### Test GitOps Edit:
1. Go to any VPC detail page: `/plugins/hedgehog/vpcs/{id}/`
2. Look for blue "GitOps Management" card
3. Click "Edit with GitOps" → should go to `/plugins/hedgehog/gitops/vpcs/{id}/edit/`
4. Form should show commit message field and GitOps info

### Test HCKC Sync:
1. Go to fabric detail: `/plugins/hedgehog/fabrics/{id}/`
2. Look for "Sync from HCKC" button (blue)
3. Click it → should show loading spinner and success/error message

## 📁 Files Changed/Added

**New Files Created**:
- `mixins/fabric_filter.py` - Fabric filtering logic
- `services/hckc_state_service.py` - Cluster state sync
- `services/gitops_edit_service.py` - Edit workflow
- `forms/gitops_forms.py` - Enhanced forms
- `views/gitops_edit_views.py` - Edit views
- `templates/components/fabric_filter.html` - Filter UI
- `templates/components/gitops_edit_button.html` - Edit button UI
- `templates/gitops/vpc_edit.html` - Sample edit template

**Modified Files**:
- `urls.py` - Added new URL patterns
- `templates/fabric_detail_simple.html` - Added HCKC sync button
- `templates/vpc_detail_simple.html` - Added GitOps edit button
- `templates/connection_detail_simple.html` - Added GitOps edit button
- `templates/vpc_list_simple.html` - Added fabric filter
- `templates/connection_list_simple.html` - Added fabric filter
- `templates/switch_list_simple.html` - Added fabric filter
- Multiple other list templates - Added fabric filter

If you still can't see the changes, the issue is likely:
1. **NetBox needs restart** to pick up new code
2. **URLs not properly loaded** - check Django admin or URL debug
3. **Template cache** - clear Django template cache
4. **Missing base templates** - check if base templates exist

Let me know what specific page you're looking at and what you see (or don't see) and I can help debug further!