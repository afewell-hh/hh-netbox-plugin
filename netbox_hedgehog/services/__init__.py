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

# Issue #16 Conflict Resolution Services
def get_yaml_duplicate_detector():
    from .yaml_duplicate_detector import YamlDuplicateDetector
    return YamlDuplicateDetector

def get_conflict_resolution_engine():
    from .conflict_resolution_engine import ConflictResolutionEngine
    return ConflictResolutionEngine

def get_fgd_conflict_service():
    from .fgd_conflict_service import FGDConflictService
    return FGDConflictService

# Phase 3 Configuration Template Engine Services
def get_configuration_generator():
    from .config_generator import ConfigurationGenerator
    return ConfigurationGenerator

def get_template_manager():
    from .template_manager import TemplateManager
    return TemplateManager

def get_schema_validator():
    from .schema_validator import SchemaValidator
    return SchemaValidator

def get_configuration_template_engine():
    from .configuration_template_engine import ConfigurationTemplateEngine
    return ConfigurationTemplateEngine

def get_file_management_service():
    from .file_management_service import FileManagementService
    return FileManagementService

# Keep direct access for backward compatibility where possible
__all__ = ['GitHubSyncService', 'get_hckc_state_service', 'get_gitops_edit_service', 
           'get_gitops_onboarding_service', 'get_gitops_ingestion_service',
           'get_yaml_duplicate_detector', 'get_conflict_resolution_engine', 'get_fgd_conflict_service',
           'get_configuration_generator', 'get_template_manager', 'get_schema_validator',
           'get_configuration_template_engine', 'get_file_management_service']