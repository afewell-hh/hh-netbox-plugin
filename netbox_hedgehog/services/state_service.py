"""
State Transition Service for Six-State Resource Management

This service handles state transitions for CRD resources in the GitOps workflow.
It provides safe state transitions with proper validation and logging.
"""

import logging
from typing import Optional, Dict, Any
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class StateTransitionService:
    """
    Centralized service for managing six-state transitions of CRD resources.
    
    States: DRAFT → COMMITTED → SYNCED → LIVE → DRIFTED → ORPHANED
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def transition_resource_state(self, resource, new_state: str, trigger_reason: str, user: Optional[Any] = None) -> bool:
        """
        Safely transition resource state with proper validation and logging.
        
        Args:
            resource: The CRD resource instance
            new_state: Target state from ResourceStateChoices
            trigger_reason: Reason for the transition (e.g., "CRD created", "Git sync")
            user: User performing the action (optional)
            
        Returns:
            bool: True if transition was successful, False otherwise
        """
        try:
            # Import here to avoid circular dependencies
            from ..models.gitops import HedgehogResource, ResourceStateChoices
            from django.contrib.contenttypes.models import ContentType
            
            # Get or create GitOps resource
            content_type = ContentType.objects.get_for_model(resource)
            gitops_resource, created = HedgehogResource.objects.get_or_create(
                content_type=content_type,
                object_id=resource.pk,
                defaults={
                    'resource_state': ResourceStateChoices.DRAFT,
                    'fabric': getattr(resource, 'fabric', None),
                    'name': getattr(resource, 'name', f"{resource.__class__.__name__}_{resource.pk}"),
                    'kind': getattr(resource, 'get_kind', lambda: resource.__class__.__name__)(),
                    'created_by': user,
                }
            )
            
            # Validate state transition if not a new resource
            if not created and not self.can_transition(gitops_resource.resource_state, new_state):
                self.logger.warning(
                    f"Invalid state transition for {gitops_resource.name}: "
                    f"{gitops_resource.resource_state} → {new_state}"
                )
                return False
            
            # Perform the state transition
            with transaction.atomic():
                old_state = gitops_resource.resource_state if not created else None
                gitops_resource.resource_state = new_state
                gitops_resource.last_modified = timezone.now()
                if user:
                    gitops_resource.last_modified_by = user
                gitops_resource.save()
                
                # Log state change
                self.log_state_change(gitops_resource, old_state, new_state, trigger_reason, user)
                
                # Update fabric-level statistics
                self.update_fabric_stats(gitops_resource.fabric)
                
            self.logger.info(
                f"State transition successful: {gitops_resource.name} "
                f"{old_state or 'NEW'} → {new_state} ({trigger_reason})"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"State transition failed for {resource}: {e}")
            return False
    
    def can_transition(self, current_state: str, new_state: str) -> bool:
        """
        Check if a state transition is valid according to the six-state model.
        
        Args:
            current_state: Current resource state
            new_state: Proposed new state
            
        Returns:
            bool: True if transition is valid
        """
        try:
            from ..models.gitops import ResourceStateChoices
            
            # Allow any transition for now - can be made more strict later
            valid_states = [choice[0] for choice in ResourceStateChoices.choices]
            return new_state in valid_states
            
        except Exception as e:
            self.logger.error(f"State validation failed: {e}")
            return False
    
    def log_state_change(self, gitops_resource, old_state: Optional[str], new_state: str, 
                        trigger_reason: str, user: Optional[Any] = None):
        """
        Log state changes for audit trail and debugging.
        
        Args:
            gitops_resource: The HedgehogResource instance
            old_state: Previous state (None for new resources)
            new_state: New state
            trigger_reason: Reason for the transition
            user: User who triggered the change
        """
        try:
            # Import here to avoid circular dependencies
            from ..models.gitops import StateTransitionHistory
            
            StateTransitionHistory.objects.create(
                resource=gitops_resource,
                from_state=old_state,
                to_state=new_state,
                trigger=trigger_reason,
                timestamp=timezone.now(),
                user=user,
                details=f"Resource {gitops_resource.name} transitioned due to: {trigger_reason}"
            )
            
        except Exception as e:
            # Don't fail the main operation if logging fails
            self.logger.warning(f"Failed to log state change: {e}")
    
    def update_fabric_stats(self, fabric):
        """
        Update fabric-level statistics based on resource states.
        
        Args:
            fabric: HedgehogFabric instance
        """
        if not fabric:
            return
            
        try:
            from ..models.gitops import HedgehogResource, ResourceStateChoices
            
            # Count resources by state
            resource_counts = {}
            for state_value, state_label in ResourceStateChoices.choices:
                count = HedgehogResource.objects.filter(
                    fabric=fabric,
                    state=state_value
                ).count()
                resource_counts[state_value] = count
            
            # Update fabric drift statistics
            drift_count = resource_counts.get(ResourceStateChoices.DRIFTED, 0)
            orphaned_count = resource_counts.get(ResourceStateChoices.ORPHANED, 0)
            
            # Update fabric fields if they exist
            if hasattr(fabric, 'drift_count'):
                fabric.drift_count = drift_count + orphaned_count
                fabric.save(update_fields=['drift_count'])
            
            self.logger.debug(
                f"Updated fabric {fabric.name} stats: {resource_counts}"
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to update fabric stats: {e}")
    
    def get_resource_state(self, resource) -> Optional[str]:
        """
        Get the current GitOps state of a resource.
        
        Args:
            resource: The CRD resource instance
            
        Returns:
            str: Current state or None if not tracked
        """
        try:
            from ..models.gitops import HedgehogResource
            from django.contrib.contenttypes.models import ContentType
            
            content_type = ContentType.objects.get_for_model(resource)
            gitops_resource = HedgehogResource.objects.filter(
                content_type=content_type,
                object_id=resource.pk
            ).first()
            
            return gitops_resource.resource_state if gitops_resource else None
            
        except Exception as e:
            self.logger.error(f"Failed to get resource state: {e}")
            return None
    
    def bulk_transition_states(self, resources: list, new_state: str, trigger_reason: str, 
                             user: Optional[Any] = None) -> Dict[str, int]:
        """
        Perform bulk state transitions for multiple resources.
        
        Args:
            resources: List of CRD resource instances
            new_state: Target state for all resources
            trigger_reason: Reason for the transitions
            user: User performing the action
            
        Returns:
            dict: Statistics about the bulk operation
        """
        stats = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for resource in resources:
            try:
                if self.transition_resource_state(resource, new_state, trigger_reason, user):
                    stats['success'] += 1
                else:
                    stats['skipped'] += 1
            except Exception as e:
                stats['failed'] += 1
                self.logger.error(f"Bulk transition failed for {resource}: {e}")
        
        self.logger.info(
            f"Bulk state transition to {new_state}: "
            f"{stats['success']} success, {stats['failed']} failed, {stats['skipped']} skipped"
        )
        
        return stats


# Singleton instance for easy access
state_service = StateTransitionService()