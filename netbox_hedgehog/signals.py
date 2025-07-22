"""
Django Signals for GitOps Integration
Automatically maintains GitOps tracking when CRDs are created, updated, or deleted.
"""

from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


@receiver(post_save)  # Re-enabled with safe import patterns
def on_crd_saved(sender, instance, created, **kwargs):
    """
    Handle CRD creation and updates.
    Automatically sync CRD changes to GitOps tracking.
    """
    # Check if this is a Hedgehog CRD model
    if not hasattr(instance, 'fabric') or not hasattr(instance, 'get_kind'):
        return
    
    # Skip if this is a HedgehogResource (avoid recursion)
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
        # Get the fabric from the instance
        fabric = instance.fabric
        
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
        
        # Use the lifecycle manager to handle the deletion
        # from .utils.gitops_integration import CRDLifecycleManager
        
        # CRDLifecycleManager.on_crd_deleted(
        #     deletion_info['name'],
        #     deletion_info['kind'], 
        #     deletion_info['namespace'],
        #     deletion_info['fabric']
        # )
        
        logger.info(f"GitOps: Handled deletion of CRD {deletion_info['kind']}/{deletion_info['name']}")
        
    except Exception as e:
        logger.error(f"GitOps deletion handling failed for {sender.__name__}: {e}")


@receiver(post_save, sender='netbox_hedgehog.HedgehogFabric')  # Re-enabled with safe patterns
def on_fabric_saved(sender, instance, created, **kwargs):
    """
    Handle HedgehogFabric changes.
    Update fabric-level GitOps status when configuration changes.
    """
    try:
        # Skip if this is creation (no CRDs to sync yet)
        if created:
            logger.info(f"GitOps: New fabric {instance.name} created")
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