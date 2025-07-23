# GitOps Integration Fix Agent

## Agent Profile

You are a senior integration engineer responsible for ensuring seamless integration between independently developed components.

## Task: Fix GitOps Component Integration

Three agents have independently implemented GitOps file management components:
1. **File Manager Agent**: Created core services in `services/` directory
2. **Testing Agent**: Created comprehensive tests
3. **UI Agent**: Created user interfaces

**Problem**: Some integration mismatches need resolution since agents couldn't communicate.

## Specific Fixes Required

### Fix 1: Update gitops_onboarding_views.py

**File**: `netbox_hedgehog/views/gitops_onboarding_views.py`

**Current problematic imports** (lines 20-25):
```python
from ..models import HedgehogFabric, HedgehogResource
from ..models.gitops import ResourceStateChoices, StateTransitionHistory  
from ..utils.git_first_onboarding import GitFirstOnboardingWorkflow, GitRepositoryValidator
from ..utils.git_providers import GitProviderFactory
from ..utils.git_monitor import GitRepositoryMonitor
from ..utils.states import StateTransitionManager
```

**Replace with**:
```python
from ..models.fabric import HedgehogFabric
from ..services.gitops_onboarding_service import GitOpsOnboardingService
from ..services.gitops_ingestion_service import GitOpsIngestionService
from ..services.raw_directory_watcher import RawDirectoryWatcher
```

### Fix 2: Update view method implementations

The view methods should call the new services. Replace any calls to:
- `GitFirstOnboardingWorkflow` → `GitOpsOnboardingService`
- `GitRepositoryValidator` → Built into onboarding service
- `StateTransitionManager` → Remove (not needed)

### Fix 3: Verify JavaScript API Integration

**Check files**:
- `netbox_hedgehog/static/netbox_hedgehog/js/gitops-onboarding.js`
- `netbox_hedgehog/static/netbox_hedgehog/js/gitops-dashboard.js`

**Ensure they call correct endpoints**:
- POST `/api/plugins/hedgehog/fabrics/{id}/init-gitops/`
- POST `/api/plugins/hedgehog/fabrics/{id}/ingest-raw/`  
- GET `/api/plugins/hedgehog/fabrics/{id}/gitops-status/`

### Fix 4: Template Integration

**Verify templates use correct context**:
- Check `gitops_onboarding_wizard.html` expects correct context variables
- Ensure form submissions target correct API endpoints

## Success Criteria

1. ✅ No import errors when loading views
2. ✅ API endpoints return expected responses  
3. ✅ JavaScript can successfully call backend APIs
4. ✅ All tests still pass
5. ✅ UI flows work end-to-end

## Implementation Notes

- **Be Conservative**: Only fix obvious integration issues
- **Don't Break Working Code**: The core services are working well
- **Test After Changes**: Ensure no regressions
- **Focus on Imports**: Main issue is import mismatches

The bulk of the work is excellent - this is just integration cleanup!