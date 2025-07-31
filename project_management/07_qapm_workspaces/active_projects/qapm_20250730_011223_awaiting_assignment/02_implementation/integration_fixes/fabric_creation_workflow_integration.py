"""
GitOps Integration Fix for Fabric Creation Workflow

This file contains the modified setup_fabric_git_integration method that integrates
GitOps directory initialization into the fabric creation process.

INTEGRATION PROBLEM SOLVED:
- Original method only validated directories but never initialized them
- No GitOps directory structure was created during fabric creation
- No commits/pushes occurred to upstream GitHub
- External GitOps tools (ArgoCD/Flux) never saw changes

SOLUTION IMPLEMENTED:
- Integrate GitOps directory initialization call
- Update fabric model with initialization status
- Maintain backward compatibility with existing functionality
- Proper error handling to prevent fabric creation failures
"""

import logging
from typing import Dict, Any, Optional
from django.utils import timezone
from dataclasses import dataclass

from netbox_hedgehog.models import HedgehogFabric
from netbox_hedgehog.utils.gitops_directory_validator import GitOpsDirectoryValidator
from netbox_hedgehog.utils.git_health_monitor import GitHealthMonitor
from netbox_hedgehog.utils.credential_manager import CredentialManager
from netbox_hedgehog.services.bidirectional_sync.gitops_directory_manager import GitOpsDirectoryManager

logger = logging.getLogger(__name__)


@dataclass
class IntegrationResult:
    """Result of git integration setup"""
    success: bool
    message: str
    health_status: dict = None
    credential_status: dict = None
    directory_validation: dict = None
    gitops_initialization: dict = None  # NEW: GitOps initialization result
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.health_status is None:
            self.health_status = {}
        if self.credential_status is None:
            self.credential_status = {}
        if self.directory_validation is None:
            self.directory_validation = {}
        if self.gitops_initialization is None:
            self.gitops_initialization = {}


def setup_fabric_git_integration_with_gitops(fabric: HedgehogFabric, user) -> IntegrationResult:
    """
    Enhanced setup git integration for newly created fabric WITH GitOps directory initialization.
    
    This is the INTEGRATION FIX that connects GitOps directory initialization to fabric creation.
    
    Args:
        fabric: Fabric instance to setup integration for
        user: User creating the fabric (for logging)
        
    Returns:
        IntegrationResult with integration status and GitOps initialization details
    """
    user_logger = logging.getLogger(f"{__name__}.{user.username}")
    
    try:
        if not fabric.git_repository:
            return IntegrationResult(
                success=False,
                message='No git repository configured for fabric',
                error='Git repository not assigned to fabric'
            )
        
        # STEP 1: Perform health check (existing functionality)
        try:
            monitor = GitHealthMonitor(fabric.git_repository)
            health_report = monitor.generate_health_report()
            health_status = health_report.to_dict()
        except Exception as e:
            user_logger.warning(f"Health check failed during integration setup: {e}")
            health_status = {'error': str(e), 'status': 'unknown'}
        
        # STEP 2: Check credential health (existing functionality)
        try:
            credential_manager = CredentialManager()
            credential_health = credential_manager.get_credential_health(fabric.git_repository)
            credential_status = credential_health
        except Exception as e:
            user_logger.warning(f"Credential health check failed: {e}")
            credential_status = {'error': str(e), 'healthy': False}
        
        # STEP 3: Validate directory assignment (existing functionality)
        try:
            validator = GitOpsDirectoryValidator()
            directory_result = validator.validate_gitops_directory_assignment(
                fabric.git_repository.id, 
                fabric.gitops_directory,
                exclude_fabric_id=fabric.id
            )
            directory_validation = {
                'valid': directory_result.is_valid,
                'errors': directory_result.errors,
                'suggestions': directory_result.suggestions
            }
        except Exception as e:
            user_logger.warning(f"Directory validation failed during integration: {e}")
            directory_validation = {'error': str(e), 'valid': False}
        
        # STEP 4: NEW - Initialize GitOps directory structure (THE INTEGRATION FIX)
        gitops_initialization = {'attempted': False, 'success': False}
        
        if fabric.git_repository and fabric.gitops_directory and directory_validation.get('valid', False):
            try:
                user_logger.info(f"Initializing GitOps directory structure for fabric {fabric.name}")
                
                # Initialize GitOps directory using existing GitOpsDirectoryManager
                manager = GitOpsDirectoryManager(fabric)
                init_result = manager.initialize_directory_structure(force=False)
                
                gitops_initialization = {
                    'attempted': True,
                    'success': init_result.success,
                    'message': init_result.message,
                    'directories_created': init_result.directories_created,
                    'errors': init_result.errors,
                    'warnings': init_result.warnings
                }
                
                if init_result.success:
                    # Update fabric GitOps initialization status
                    fabric.gitops_initialized = True
                    fabric.gitops_directory_status = 'initialized'
                    fabric.directory_init_error = ''
                    fabric.last_directory_sync = timezone.now()
                    fabric.save(update_fields=[
                        'gitops_initialized', 
                        'gitops_directory_status', 
                        'directory_init_error',
                        'last_directory_sync'
                    ])
                    
                    user_logger.info(f"GitOps directory initialized successfully for fabric {fabric.id}")
                else:
                    # Update fabric with error status but don't fail creation
                    fabric.gitops_directory_status = 'error'
                    fabric.directory_init_error = '; '.join(init_result.errors)
                    fabric.save(update_fields=['gitops_directory_status', 'directory_init_error'])
                    
                    user_logger.warning(f"GitOps directory initialization had errors for fabric {fabric.id}: {init_result.errors}")
                
            except Exception as e:
                error_msg = f"GitOps directory initialization failed for fabric {fabric.id}: {str(e)}"
                user_logger.error(error_msg)
                
                gitops_initialization = {
                    'attempted': True,
                    'success': False,
                    'error': str(e)
                }
                
                # Update fabric with error status but don't fail creation
                fabric.gitops_directory_status = 'error'
                fabric.directory_init_error = str(e)
                fabric.save(update_fields=['gitops_directory_status', 'directory_init_error'])
        else:
            user_logger.info(f"Skipping GitOps initialization for fabric {fabric.id} - prerequisites not met")
            gitops_initialization = {
                'attempted': False,
                'success': False,
                'reason': 'Prerequisites not met (repository, directory, or validation failed)'
            }
        
        # STEP 5: Update fabric timestamps (existing functionality)
        fabric.last_git_sync = timezone.now()
        fabric.save(update_fields=['last_git_sync'])
        
        # STEP 6: Determine overall integration success
        integration_success = (
            health_status.get('status') != 'critical' and
            credential_status.get('healthy', False) and
            directory_validation.get('valid', False)
        )
        
        # Note: We don't require GitOps initialization success for integration success
        # This maintains backward compatibility and prevents fabric creation failures
        
        success_message = 'Git integration setup completed'
        if gitops_initialization.get('success'):
            success_message += ' with GitOps directory initialization'
        elif gitops_initialization.get('attempted'):
            success_message += ' (GitOps initialization had warnings)'
        
        return IntegrationResult(
            success=integration_success,
            message=success_message,
            health_status=health_status,
            credential_status=credential_status,
            directory_validation=directory_validation,
            gitops_initialization=gitops_initialization  # NEW: Include GitOps results
        )
        
    except Exception as e:
        user_logger.error(f"Git integration setup failed: {e}")
        return IntegrationResult(
            success=False,
            message='Git integration setup failed',
            error=str(e),
            gitops_initialization={'attempted': False, 'success': False, 'error': str(e)}
        )


# Helper function to patch the existing workflow class
def apply_gitops_integration_patch():
    """
    Apply the GitOps integration patch to the existing UnifiedFabricCreationWorkflow class.
    
    This function demonstrates how to integrate the fix into the existing codebase.
    """
    from netbox_hedgehog.utils.fabric_creation_workflow import UnifiedFabricCreationWorkflow
    
    # Store original method
    original_method = UnifiedFabricCreationWorkflow.setup_fabric_git_integration
    
    def patched_setup_fabric_git_integration(self, fabric: HedgehogFabric):
        """Patched version that includes GitOps directory initialization"""
        return setup_fabric_git_integration_with_gitops(fabric, self.user)
    
    # Replace method
    UnifiedFabricCreationWorkflow.setup_fabric_git_integration = patched_setup_fabric_git_integration
    
    return {
        'patch_applied': True,
        'original_method_saved': True,
        'description': 'GitOps directory initialization integrated into fabric creation workflow'
    }


"""
IMPLEMENTATION NOTES:

1. INTEGRATION STRATEGY:
   - Modified setup_fabric_git_integration to call GitOpsDirectoryManager.initialize_directory_structure()
   - Added GitOps initialization tracking to fabric model fields
   - Maintained backward compatibility with existing workflow

2. ERROR HANDLING:
   - GitOps initialization failures don't break fabric creation
   - Proper error logging and status tracking
   - Graceful degradation if GitOps components unavailable

3. STATUS TRACKING:
   - fabric.gitops_initialized = True on success
   - fabric.gitops_directory_status tracks initialization state
   - fabric.directory_init_error stores error messages
   - fabric.last_directory_sync tracks timing

4. GITHUB PUSH INTEGRATION:
   - GitOpsDirectoryManager.initialize_directory_structure() includes GitHub push
   - Existing GitHubSyncClient handles commit and push operations
   - Directory structure (raw/, unmanaged/, managed/) created in upstream repository

5. EXTERNAL GITOPS READY:
   - Directory structure visible in upstream GitHub repository
   - ArgoCD/Flux can detect and sync changes
   - Standard three-directory GitOps pattern implemented

TESTING REQUIREMENTS:
- Test fabric creation triggers GitOps initialization
- Verify directory structure created in GitHub repository
- Confirm upstream commits and pushes occur
- Validate fabric status fields updated correctly
- Test error handling doesn't break fabric creation
"""