# GitOps Sync Trigger Analysis

## Critical Discovery: Multiple Sync Mechanisms Found

### 1. Fabric-Level GitOps Sync (MAIN ISSUE)
**Location**: `/netbox_hedgehog/models/fabric.py:836`
```python
def trigger_gitops_sync(self):
    """Sync CRs from Git repository directory into HNP database."""
    from ..utils.git_directory_sync import sync_fabric_from_git
    result = sync_fabric_from_git(self)
```

**API Endpoint**: 
- POST `/api/plugins/hedgehog/fabrics/{id}/gitops_sync/`
- Handled by: `HedgehogFabricViewSet.gitops_sync()`

### 2. NEW GitOps Processing APIs (DIFFERENT APPROACH)
**Location**: `/netbox_hedgehog/api/gitops_views.py`

#### A. Raw File Ingestion API
- POST `/api/plugins/hedgehog/fabrics/{id}/ingest-raw/`
- Service: `GitOpsIngestionService.process_raw_directory()`
- Purpose: Process files from raw/ directory

#### B. GitOps Onboarding API  
- POST `/api/plugins/hedgehog/fabrics/{id}/init-gitops/`
- Service: `GitOpsOnboardingService.sync_raw_directory()`
- Purpose: Initialize GitOps structure and process existing files

## 🚨 ROOT CAUSE HYPOTHESIS

The issue appears to be that there are **TWO DIFFERENT SYNC SYSTEMS**:

1. **Legacy Git Directory Sync**: 
   - Processes files from GitHub repository directly
   - Does NOT use raw/managed directory structure
   - Path: `gitops_directory` field on fabric

2. **New GitOps Architecture**:
   - Uses raw/managed/unmanaged directory structure
   - Processes files through GitOpsOnboardingService
   - May not be properly initialized or triggered

## Next Steps
1. Test the GitOpsOnboardingService.sync_raw_directory() method
2. Check if GitOps structure is initialized for test fabric
3. Identify which sync mechanism should be handling the 3 YAML files