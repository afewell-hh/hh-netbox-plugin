# Services package for business logic
# Import only services that don't have Django model dependencies at module level
from .github_sync_service import GitHubSyncService

# Lazy imports for services with Django dependencies
def get_hckc_state_service():
    from .hckc_state_service import HCKCStateService
    return HCKCStateService

def get_gitops_edit_service():
    from .gitops_edit_service import GitOpsEditService
    return GitOpsEditService

def get_gitops_onboarding_service():
    from .gitops_onboarding_service import GitOpsOnboardingService
    return GitOpsOnboardingService

def get_gitops_ingestion_service():
    from .gitops_ingestion_service import GitOpsIngestionService
    return GitOpsIngestionService

# Keep direct access for backward compatibility where possible
__all__ = ['GitHubSyncService', 'get_hckc_state_service', 'get_gitops_edit_service', 
           'get_gitops_onboarding_service', 'get_gitops_ingestion_service']