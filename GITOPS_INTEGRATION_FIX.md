# GitOps Integration Fix

## Issues Identified

1. **Import Mismatches**: UI views importing older modules instead of new services
2. **API Endpoint Alignment**: Need to ensure JavaScript calls correct endpoints

## Required Fixes

### Fix 1: Update gitops_onboarding_views.py imports

Replace these imports:
```python
from ..utils.git_first_onboarding import GitFirstOnboardingWorkflow, GitRepositoryValidator  
from ..utils.git_providers import GitProviderFactory
from ..utils.git_monitor import GitRepositoryMonitor
from ..utils.states import StateTransitionManager
```

With:
```python
from ..services.gitops_onboarding_service import GitOpsOnboardingService
from ..services.gitops_ingestion_service import GitOpsIngestionService  
from ..services.raw_directory_watcher import RawDirectoryWatcher
```

### Fix 2: Update view method implementations

The view methods should call the new services instead of the old utilities.

### Fix 3: Ensure JavaScript API calls match backend

Verify that JavaScript files call:
- `/api/plugins/hedgehog/fabrics/{id}/init-gitops/` (correct)
- `/api/plugins/hedgehog/fabrics/{id}/ingest-raw/` (correct)
- `/api/plugins/hedgehog/fabrics/{id}/gitops-status/` (correct)

## Status
- Backend services: ✅ Complete and working
- API endpoints: ✅ Properly wired  
- Frontend UI: ✅ Created but needs import fixes
- Tests: ✅ Comprehensive coverage
- Integration: ⚠️ Minor fixes needed