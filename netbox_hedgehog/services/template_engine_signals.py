"""
Template Engine Signal Handlers

Signal handlers for integrating the Configuration Template Engine with
the existing NetBox Hedgehog event system for automatic configuration
generation and updates.
"""

import logging
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from django.utils import timezone

from ..models.fabric import HedgehogFabric
from ..models.gitops import HedgehogResource
from ..models.git_repository import GitRepository
from ..signals import fabric_configuration_updated, resource_drift_detected
from .configuration_template_engine import handle_resource_change, generate_fabric_configurations

logger = logging.getLogger(__name__)


@receiver(post_save, sender=HedgehogResource)
def handle_resource_change_signal(sender, instance, created, **kwargs):
    """
    Handle resource changes by regenerating dependent configurations.
    
    This signal handler is triggered when:
    - New resources are created
    - Existing resources are updated
    """
    try:
        # Skip if this is just a metadata update (no spec changes)
        if not created and hasattr(instance, '_state') and not getattr(instance, '_spec_changed', True):
            logger.debug(f"Skipping config regeneration for metadata-only update: {instance.name}")
            return
        
        logger.info(f"Resource {'created' if created else 'updated'}: {instance.name} ({instance.kind})")
        
        # Regenerate configurations for dependent templates
        result = handle_resource_change(instance)
        
        if result.success:
            logger.info(f"Successfully regenerated {len(result.files_generated + result.files_updated)} "
                       f"configuration files for resource {instance.name}")
        else:
            logger.warning(f"Configuration regeneration failed for resource {instance.name}: "
                          f"{result.error_message}")
        
    except Exception as e:
        logger.error(f"Failed to handle resource change signal for {instance.name}: {str(e)}")


@receiver(post_delete, sender=HedgehogResource)
def handle_resource_deletion_signal(sender, instance, **kwargs):
    """
    Handle resource deletion by cleaning up related configurations.
    """
    try:
        logger.info(f"Resource deleted: {instance.name} ({instance.kind})")
        
        # For deleted resources, we might need to regenerate templates
        # to remove references or handle the absence of the resource
        if instance.fabric:
            result = generate_fabric_configurations(instance.fabric, force_regenerate=True)
            
            if result.success:
                logger.info(f"Successfully updated configurations after deletion of {instance.name}")
            else:
                logger.warning(f"Configuration update failed after deletion of {instance.name}: "
                              f"{result.error_message}")
        
    except Exception as e:
        logger.error(f"Failed to handle resource deletion signal for {instance.name}: {str(e)}")


@receiver(post_save, sender=HedgehogFabric)
def handle_fabric_change_signal(sender, instance, created, **kwargs):
    """
    Handle fabric changes by regenerating all fabric configurations.
    """
    try:
        logger.info(f"Fabric {'created' if created else 'updated'}: {instance.name}")
        
        # For fabric changes, regenerate all configurations
        result = generate_fabric_configurations(instance, force_regenerate=True)
        
        if result.success:
            logger.info(f"Successfully regenerated fabric configurations for {instance.name}: "
                       f"{len(result.files_generated + result.files_updated)} files")
        else:
            logger.warning(f"Fabric configuration regeneration failed for {instance.name}: "
                          f"{result.error_message}")
        
    except Exception as e:
        logger.error(f"Failed to handle fabric change signal for {instance.name}: {str(e)}")


@receiver(resource_drift_detected)
def handle_drift_detected_signal(sender, resource, drift_details, **kwargs):
    """
    Handle drift detection by potentially regenerating configurations.
    """
    try:
        logger.info(f"Drift detected for resource {resource.name}: {drift_details.get('drift_status')}")
        
        # For certain types of drift, we might want to regenerate configurations
        drift_status = drift_details.get('drift_status')
        
        if drift_status in ['desired_only', 'spec_drift']:
            # Resource needs to be updated or created - regenerate configurations
            result = handle_resource_change(resource)
            
            if result.success:
                logger.info(f"Successfully regenerated configurations after drift detection for {resource.name}")
            else:
                logger.warning(f"Configuration regeneration failed after drift detection: {result.error_message}")
        
    except Exception as e:
        logger.error(f"Failed to handle drift detection signal for {resource.name}: {str(e)}")


@receiver(fabric_configuration_updated)
def handle_configuration_updated_signal(sender, fabric, generation_id, files_generated, files_updated, **kwargs):
    """
    Handle configuration update notifications.
    """
    try:
        logger.info(f"Configuration updated for fabric {fabric.name}: "
                   f"generation_id={generation_id}, "
                   f"files_generated={len(files_generated)}, "
                   f"files_updated={len(files_updated)}")
        
        # Update fabric metadata with last configuration update time
        fabric.last_configuration_update = timezone.now()
        fabric.save(update_fields=['last_configuration_update'])
        
        # Optionally trigger downstream processes like Git commits, ArgoCD sync, etc.
        
    except Exception as e:
        logger.error(f"Failed to handle configuration updated signal: {str(e)}")


# Custom signal handlers for template engine events
def connect_template_engine_signals():
    """
    Connect template engine specific signals.
    This function should be called during Django app initialization.
    """
    logger.info("Template engine signal handlers connected")


def disconnect_template_engine_signals():
    """
    Disconnect template engine signals.
    Useful for testing or when disabling the template engine.
    """
    # Django's receiver decorator handles disconnection automatically
    # This function is provided for completeness
    logger.info("Template engine signal handlers would be disconnected")


# Signal validation helpers
def validate_resource_for_template_generation(resource: HedgehogResource) -> bool:
    """
    Validate if a resource should trigger template generation.
    
    Args:
        resource: Resource to validate
        
    Returns:
        True if the resource should trigger template generation
    """
    # Skip if resource is in draft state
    if hasattr(resource, 'resource_state') and resource.resource_state == 'draft':
        return False
    
    # Skip if fabric is disabled for template generation
    if hasattr(resource.fabric, 'template_generation_enabled') and not resource.fabric.template_generation_enabled:
        return False
    
    # Skip certain resource types that don't need configuration generation
    skip_kinds = getattr(resource.fabric, 'template_skip_kinds', [])
    if resource.kind in skip_kinds:
        return False
    
    return True


def should_regenerate_for_fabric(fabric: HedgehogFabric) -> bool:
    """
    Validate if fabric changes should trigger full regeneration.
    
    Args:
        fabric: Fabric to validate
        
    Returns:
        True if fabric changes should trigger regeneration
    """
    # Skip if fabric template generation is disabled
    if hasattr(fabric, 'template_generation_enabled') and not fabric.template_generation_enabled:
        return False
    
    # Check if fabric has any resources
    if not fabric.gitops_resources.exists():
        logger.debug(f"Fabric {fabric.name} has no resources, skipping regeneration")
        return False
    
    return True