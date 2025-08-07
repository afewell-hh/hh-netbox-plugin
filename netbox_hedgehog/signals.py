"""
Django Signals for GitOps Integration
Automatically maintains GitOps tracking when CRDs are created, updated, or deleted.
"""

from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.apps import apps
import logging
import traceback

logger = logging.getLogger(__name__)

# HIVE MIND RESEARCHER: Signal execution tracing
SIGNAL_TRACE_LOGGER = logging.getLogger('hedgehog.signals.trace')
SIGNAL_TRACE_LOGGER.setLevel(logging.DEBUG)

def trace_signal_execution(signal_name, sender, instance=None, **kwargs):
    """Trace signal execution for debugging"""
    try:
        instance_info = f"{instance.__class__.__name__}:{getattr(instance, 'name', 'unknown')}" if instance else "None"
        SIGNAL_TRACE_LOGGER.info(f"🔍 SIGNAL TRACE: {signal_name} | Sender: {sender.__name__} | Instance: {instance_info}")
        
        # Log stack trace to see who triggered the signal
        stack = traceback.format_stack()
        SIGNAL_TRACE_LOGGER.debug(f"🔍 SIGNAL STACK: {signal_name}\n{''.join(stack[-5:])}")
        
    except Exception as e:
        SIGNAL_TRACE_LOGGER.error(f"🔍 SIGNAL TRACE ERROR: {signal_name} - {e}")


def initialize_fabric_gitops(fabric):
    """
    Initialize GitOps structure for a fabric with strict error handling.
    
    Args:
        fabric: HedgehogFabric instance to initialize
        
    Raises:
        Exception: Any failure in GitOps initialization
    """
    try:
        logger.info(f"Initializing GitOps structure for fabric {fabric.name}")
        
        # Skip if already initialized
        if getattr(fabric, 'gitops_initialized', False):
            logger.info(f"GitOps structure already initialized for fabric {fabric.name}")
            return
        
        # Validate service availability first
        try:
            from .services.gitops_onboarding_service import GitOpsOnboardingService
        except ImportError as e:
            raise Exception(f"GitOpsOnboardingService not available: {e}")
        
        # Create onboarding service
        onboarding_service = GitOpsOnboardingService(fabric)
        
        # Initialize GitOps structure with validation
        result = onboarding_service.initialize_gitops_structure()
        
        if not result.get('success'):
            error_msg = f"GitOps initialization failed: {result.get('error', 'Unknown error')}"
            logger.error(f"GitOps initialization failed for fabric {fabric.name}: {error_msg}")
            raise Exception(error_msg)
        
        logger.info(f"GitOps initialization completed successfully for fabric {fabric.name}: {result['message']}")
        
        # Note: Ingestion is now handled within initialize_gitops_structure()
        # No need for separate ingest_fabric_raw_files() call since it's integrated
        
        return result
        
    except Exception as e:
        logger.error(f"GitOps initialization exception for fabric {fabric.name}: {str(e)}")
        raise  # Propagate all exceptions


def ingest_fabric_raw_files(fabric):
    """
    Ingest raw files for a fabric.
    
    Args:
        fabric: HedgehogFabric instance to process
    """
    try:
        logger.info(f"Processing raw files for fabric {fabric.name}")
        
        # Import here to avoid circular imports
        from .services.gitops_ingestion_service import GitOpsIngestionService
        
        # Create ingestion service
        ingestion_service = GitOpsIngestionService(fabric)
        
        # Process raw directory
        result = ingestion_service.process_raw_directory()
        
        if result['success']:
            logger.info(f"Raw file ingestion completed for fabric {fabric.name}: {result['message']}")
        else:
            logger.warning(f"Raw file ingestion had issues for fabric {fabric.name}: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Error during raw file ingestion for fabric {fabric.name}: {str(e)}")


def validate_gitops_structure(fabric):
    """
    Validate that a fabric's GitOps structure is properly initialized.
    
    Args:
        fabric: HedgehogFabric instance to validate
        
    Returns:
        dict: Validation result with success status and details
    """
    try:
        from .services.gitops_onboarding_service import GitOpsOnboardingService
        
        onboarding_service = GitOpsOnboardingService(fabric)
        return onboarding_service.validate_structure()
        
    except Exception as e:
        return {
            'valid': False,
            'errors': [f'Validation error: {str(e)}'],
            'fabric_name': fabric.name
        }


def ensure_gitops_structure(fabric):
    """
    Ensure GitOps structure exists, initializing if necessary.
    
    Args:
        fabric: HedgehogFabric instance to check
        
    Returns:
        dict: Result of structure check/initialization
    """
    # Check if already initialized
    if getattr(fabric, 'gitops_initialized', False):
        # Validate existing structure
        validation = validate_gitops_structure(fabric)
        if validation['valid']:
            return {
                'success': True,
                'message': 'GitOps structure already exists and is valid',
                'action': 'validated'
            }
        else:
            logger.warning(f"GitOps structure validation failed for fabric {fabric.name}, reinitializing")
    
    # Initialize or reinitialize structure
    try:
        from .services.gitops_onboarding_service import GitOpsOnboardingService
        
        onboarding_service = GitOpsOnboardingService(fabric)
        result = onboarding_service.initialize_gitops_structure()
        
        return {
            'success': result['success'],
            'message': result.get('message', 'GitOps structure initialized'),
            'action': 'initialized',
            'details': result
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to ensure GitOps structure: {str(e)}',
            'action': 'failed'
        }


@receiver(post_save)  # Re-enabled with safe import patterns
def on_crd_saved(sender, instance, created, **kwargs):
    """
    Handle CRD creation and updates.
    Automatically sync CRD changes to GitOps tracking.
    """
    # HIVE MIND RESEARCHER: Trace signal execution
    trace_signal_execution('on_crd_saved', sender, instance, created=created, **kwargs)
    
    # HIVE MIND RESEARCHER: Simple diagnostic print
    print(f"🚨 SIGNAL FIRED: on_crd_saved for {sender.__name__} - {getattr(instance, 'name', 'unknown')}")
    
    # Check if this is a Hedgehog CRD model
    if not hasattr(instance, 'fabric') or not hasattr(instance, 'get_kind'):
        SIGNAL_TRACE_LOGGER.info(f"🔍 SKIPPING: {sender.__name__} - No fabric or get_kind method")
        return
    
    # Skip if this is a HedgehogResource (avoid recursion)
    if sender.__name__ == 'HedgehogResource':
        SIGNAL_TRACE_LOGGER.info(f"🔍 SKIPPING: {sender.__name__} - Avoid HedgehogResource recursion")
        return
        
    # Skip if sender is not a BaseCRD subclass
    try:
        from .models.base import BaseCRD
        if not issubclass(sender, BaseCRD):
            SIGNAL_TRACE_LOGGER.info(f"🔍 SKIPPING: {sender.__name__} - Not a BaseCRD subclass")
            return
    except ImportError:
        SIGNAL_TRACE_LOGGER.info(f"🔍 SKIPPING: {sender.__name__} - Could not import BaseCRD")
        return
    
    # Log that we're proceeding with signal processing
    SIGNAL_TRACE_LOGGER.info(f"🔍 PROCESSING: {sender.__name__} - {instance.name} (created={created})")
    
    try:
        # Get the fabric from the instance
        fabric = instance.fabric
        SIGNAL_TRACE_LOGGER.info(f"🔍 FABRIC: {fabric.name}")
        
        # Use the state service to handle the event
        from .services.state_service import state_service
        
        if created:
            # New CRD starts in DRAFT state
            state_service.transition_resource_state(
                instance, 
                'draft', 
                'CRD created via NetBox UI'
            )
            logger.info(f"GitOps: New CRD {instance.get_kind()}/{instance.name} → DRAFT state")
        else:
            # Updated CRD - check current state and potentially mark as needing sync
            current_state = state_service.get_resource_state(instance)
            if current_state in ['synced', 'committed']:
                # Mark as needing attention since it was modified
                state_service.transition_resource_state(
                    instance,
                    'draft',
                    'CRD modified in NetBox UI'
                )
                logger.info(f"GitOps: Updated CRD {instance.get_kind()}/{instance.name} → DRAFT state")
        
        # CRITICAL FIX: Actually sync to GitHub
        try:
            from .services.github_sync_service import GitHubSyncService
            
            logger.info(f"=== SIGNALS GITHUB SYNC TRIGGER ===")
            logger.info(f"CR: {instance.get_kind()}/{instance.name}")
            logger.info(f"Fabric: {fabric.name}")
            logger.info(f"Has git_repository_url: {hasattr(fabric, 'git_repository_url')}")
            if hasattr(fabric, 'git_repository_url'):
                logger.info(f"Git repository URL: {fabric.git_repository_url}")
            
            # Only sync if fabric has GitHub configured
            if hasattr(fabric, 'git_repository_url') and fabric.git_repository_url:
                logger.info(f"Creating GitHubSyncService for fabric {fabric.name}")
                github_service = GitHubSyncService(fabric)
                operation = 'create' if created else 'update'
                
                logger.info(f"Calling sync_cr_to_github with operation: {operation}")
                # Sync to GitHub
                result = github_service.sync_cr_to_github(
                    instance,
                    operation=operation,
                    user='signal_handler'
                )
                
                logger.info(f"=== SIGNALS GITHUB SYNC RESULT ===")
                logger.info(f"Success: {result['success']}")
                logger.info(f"Result: {result}")
                
                if result['success']:
                    logger.info(f"GitOps: Successfully synced {instance.get_kind()}/{instance.name} to GitHub")
                    # Update state to synced
                    state_service.transition_resource_state(
                        instance,
                        'synced',
                        f'Synced to GitHub: {result.get("commit_sha", "unknown")}'
                    )
                else:
                    logger.error(f"GitOps: Failed to sync to GitHub: {result.get('error')}")
            else:
                logger.debug(f"GitOps: No GitHub repository configured for fabric {fabric.name}")
                
        except Exception as sync_e:
            logger.error(f"GitOps: GitHub sync failed for {instance.name}: {sync_e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
    except Exception as e:
        # Log error but don't break CRD operations
        logger.error(f"GitOps sync failed for {sender.__name__} {getattr(instance, 'name', 'unknown')}: {e}")


@receiver(pre_delete)  # Re-enabled with safe import patterns
def on_crd_pre_delete(sender, instance, **kwargs):
    """
    Handle CRD deletion preparation.
    Store information needed for GitOps tracking update.
    """
    # Check if this is a Hedgehog CRD model
    if not hasattr(instance, 'fabric') or not hasattr(instance, 'get_kind'):
        return
    
    # Skip if this is a HedgehogResource (handled separately)
    if sender.__name__ == 'HedgehogResource':
        return
        
    # Skip if sender is not a BaseCRD subclass
    try:
        from .models.base import BaseCRD
        if not issubclass(sender, BaseCRD):
            return
    except ImportError:
        return
    
    try:
        # Store deletion info for post_delete handler
        # We need to capture this before the instance is deleted
        instance._gitops_deletion_info = {
            'name': instance.name,
            'kind': instance.get_kind(),
            'namespace': instance.namespace,
            'fabric': instance.fabric
        }
        
    except Exception as e:
        logger.error(f"Failed to prepare GitOps deletion info for {instance}: {e}")


@receiver(post_delete)  # Re-enabled with safe import patterns
def on_crd_deleted(sender, instance, **kwargs):
    """
    Handle CRD deletion.
    Update GitOps tracking to reflect resource removal.
    """
    # Check if deletion info was prepared
    if not hasattr(instance, '_gitops_deletion_info'):
        return
    
    try:
        deletion_info = instance._gitops_deletion_info
        fabric = deletion_info['fabric']
        
        # CRITICAL FIX: Actually delete from GitHub
        try:
            from .services.github_sync_service import GitHubSyncService
            
            # Only sync if fabric has GitHub configured
            if hasattr(fabric, 'git_repository_url') and fabric.git_repository_url:
                github_service = GitHubSyncService(fabric)
                
                # Delete from GitHub
                result = github_service.sync_cr_to_github(
                    instance,
                    operation='delete',
                    user='signal_handler'
                )
                
                if result['success']:
                    logger.info(f"GitOps: Successfully deleted {deletion_info['kind']}/{deletion_info['name']} from GitHub")
                else:
                    logger.error(f"GitOps: Failed to delete from GitHub: {result.get('error')}")
            else:
                logger.debug(f"GitOps: No GitHub repository configured for fabric {fabric.name}")
                
        except Exception as sync_e:
            logger.error(f"GitOps: GitHub deletion failed for {deletion_info['name']}: {sync_e}")
        
        logger.info(f"GitOps: Handled deletion of CRD {deletion_info['kind']}/{deletion_info['name']}")
        
    except Exception as e:
        logger.error(f"GitOps deletion handling failed for {sender.__name__}: {e}")


@receiver(post_save, sender='netbox_hedgehog.HedgehogFabric')  # Re-enabled with safe patterns
def on_fabric_saved(sender, instance, created, **kwargs):
    """
    Handle HedgehogFabric changes.
    Update fabric-level GitOps status when configuration changes.
    Initialize GitOps structure for new fabrics.
    """
    # HIVE MIND RESEARCHER: Trace fabric signal execution
    trace_signal_execution('on_fabric_saved', sender, instance, created=created, **kwargs)
    
    try:
        # Handle new fabric creation - initialize GitOps structure
        if created:
            logger.info(f"GitOps: New fabric {instance.name} created, initializing GitOps structure")
            # Execute immediately in current transaction context to prevent race conditions
            try:
                from django.db import transaction
                with transaction.atomic():
                    initialize_fabric_gitops(instance)
            except Exception as e:
                logger.error(f"GitOps initialization failed for fabric {instance.name}: {e}")
                # Set fabric status to indicate initialization failure
                try:
                    instance.sync_status = 'initialization_failed'
                    instance.save(update_fields=['sync_status'])
                except Exception as save_error:
                    logger.error(f"Failed to update fabric status after GitOps initialization failure: {save_error}")
                # Re-raise to ensure failure is visible
                raise
            return
        
        # Check if GitOps configuration has changed
        gitops_fields = [
            'git_repository_url', 'git_branch', 'git_path',
            'git_username', 'git_token', 'gitops_tool', 
            'gitops_app_name', 'gitops_namespace'
        ]
        
        # Get the previous instance to check for changes
        # This is a simplified check - in production you might want to track specific field changes
        logger.info(f"GitOps: Fabric {instance.name} configuration updated")
        
        # If Git configuration changed, we might want to trigger a resync
        if instance.git_repository_url:
            # Could trigger automatic Git sync here if desired
            logger.info(f"GitOps: Fabric {instance.name} has Git repository configured: {instance.git_repository_url}")
            
    except Exception as e:
        logger.error(f"GitOps fabric update handling failed for {instance.name}: {e}")


@receiver(post_save, sender='netbox_hedgehog.HedgehogResource')  # Re-enabled with safe patterns
def on_gitops_resource_saved(sender, instance, created, **kwargs):
    """
    Handle HedgehogResource changes.
    Update fabric-level drift statistics when resources change.
    """
    try:
        fabric = instance.fabric
        
        # Update fabric-level drift count
        from .models import HedgehogResource
        drift_count = HedgehogResource.objects.filter(
            fabric=fabric,
            drift_status__in=['spec_drift', 'desired_only', 'actual_only', 'creation_pending', 'deletion_pending']
        ).count()
        
        # Update fabric drift count if it changed
        if fabric.drift_count != drift_count:
            fabric.drift_count = drift_count
            
            # Update drift status based on count
            if drift_count == 0:
                fabric.drift_status = 'in_sync'
            elif drift_count > 0:
                fabric.drift_status = 'drift_detected'
            
            # Save without triggering signals recursively
            fabric.save(update_fields=['drift_count', 'drift_status'])
            
        logger.debug(f"GitOps: Updated fabric {fabric.name} drift count: {drift_count}")
        
    except Exception as e:
        logger.error(f"GitOps resource tracking update failed: {e}")


@receiver(post_delete, sender='netbox_hedgehog.HedgehogResource')  # Re-enabled with safe patterns
def on_gitops_resource_deleted(sender, instance, **kwargs):
    """
    Handle HedgehogResource deletion.
    Update fabric-level drift statistics.
    """
    try:
        fabric = instance.fabric
        
        # Update fabric-level drift count
        from .models import HedgehogResource
        drift_count = HedgehogResource.objects.filter(
            fabric=fabric,
            drift_status__in=['spec_drift', 'desired_only', 'actual_only', 'creation_pending', 'deletion_pending']
        ).count()
        
        # Update fabric drift count
        fabric.drift_count = drift_count
        
        # Update drift status based on count  
        if drift_count == 0:
            fabric.drift_status = 'in_sync'
        elif drift_count > 0:
            fabric.drift_status = 'drift_detected'
        
        # Save without triggering signals recursively
        fabric.save(update_fields=['drift_count', 'drift_status'])
        
        logger.debug(f"GitOps: Updated fabric {fabric.name} drift count after deletion: {drift_count}")
        
    except Exception as e:
        logger.error(f"GitOps resource deletion tracking failed: {e}")


# Batch operation handlers for performance
def bulk_sync_fabric_signals(fabric, enable=True):
    """
    Enable or disable GitOps signals for bulk operations.
    Use this during bulk imports to avoid excessive signal firing.
    
    Args:
        fabric: HedgehogFabric instance
        enable: Whether to enable (True) or disable (False) signals
    """
    if enable:
        # Re-enable signals (they're enabled by default)
        post_save.connect(on_crd_saved)
        pre_delete.connect(on_crd_pre_delete) 
        post_delete.connect(on_crd_deleted)
        logger.info(f"GitOps signals enabled for fabric {fabric.name}")
    else:
        # Temporarily disable signals for bulk operations
        post_save.disconnect(on_crd_saved)
        pre_delete.disconnect(on_crd_pre_delete)
        post_delete.disconnect(on_crd_deleted)
        logger.info(f"GitOps signals disabled for fabric {fabric.name} bulk operations")


def trigger_full_fabric_sync(fabric):
    """
    Trigger a full synchronization of all CRDs in a fabric to GitOps tracking.
    Use this after bulk operations or to repair GitOps tracking.
    
    Args:
        fabric: HedgehogFabric instance
        
    Returns:
        Sync results dict
    """
    try:
        # from .utils.gitops_integration import bulk_sync_fabric_to_gitops
        
        logger.info(f"GitOps: Starting full fabric sync for {fabric.name}")
        
        # Temporarily disable signals to avoid recursion during bulk sync
        bulk_sync_fabric_signals(fabric, enable=False)
        
        try:
            # Perform the bulk sync
            results = bulk_sync_fabric_to_gitops(fabric)
            
            # Update fabric-level statistics
            from .models import HedgehogResource
            total_resources = HedgehogResource.objects.filter(fabric=fabric).count()
            drift_count = HedgehogResource.objects.filter(
                fabric=fabric,
                drift_status__in=['spec_drift', 'desired_only', 'actual_only', 'creation_pending', 'deletion_pending']
            ).count()
            
            fabric.drift_count = drift_count
            fabric.drift_status = 'in_sync' if drift_count == 0 else 'drift_detected'
            fabric.save(update_fields=['drift_count', 'drift_status'])
            
            results['fabric_stats'] = {
                'total_resources': total_resources,
                'drift_count': drift_count,
                'drift_status': fabric.drift_status
            }
            
            logger.info(f"GitOps: Completed full fabric sync for {fabric.name}: {results['synced']} synced, {results['errors']} errors")
            return results
            
        finally:
            # Re-enable signals
            bulk_sync_fabric_signals(fabric, enable=True)
            
    except Exception as e:
        logger.error(f"Full fabric sync failed for {fabric.name}: {e}")
        # Make sure signals are re-enabled even if sync fails
        bulk_sync_fabric_signals(fabric, enable=True)
        raise


class GitOpsSignalManager:
    """
    Context manager for handling GitOps signals during bulk operations.
    """
    
    def __init__(self, fabric, disable_signals=True):
        self.fabric = fabric
        self.disable_signals = disable_signals
        self.signals_were_enabled = True
    
    def __enter__(self):
        if self.disable_signals:
            self.signals_were_enabled = True  # Assume they were enabled
            bulk_sync_fabric_signals(self.fabric, enable=False)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.disable_signals and self.signals_were_enabled:
            bulk_sync_fabric_signals(self.fabric, enable=True)
            
            # If operation completed successfully, trigger a final sync
            if exc_type is None:
                try:
                    trigger_full_fabric_sync(self.fabric)
                except Exception as e:
                    logger.error(f"Post-operation sync failed: {e}")


# Usage example:
# with GitOpsSignalManager(fabric, disable_signals=True):
#     # Perform bulk CRD operations
#     # Signals will be automatically re-enabled and final sync triggered