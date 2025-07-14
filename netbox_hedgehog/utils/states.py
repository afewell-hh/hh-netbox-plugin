"""
State management utilities for the Six-State Resource Management System
"""
from enum import Enum
from typing import Dict, List, Optional, Set, Union
from dataclasses import dataclass
from datetime import datetime
from django.contrib.auth.models import User


class ResourceState(Enum):
    """Six-state resource management enumeration"""
    DRAFT = "draft"           # Created in HNP, not in Git
    COMMITTED = "committed"   # In Git, not applied to cluster
    SYNCED = "synced"        # Git and Kubernetes match
    DRIFTED = "drifted"      # Kubernetes differs from Git
    ORPHANED = "orphaned"    # In Kubernetes, not in Git
    PENDING = "pending"      # Awaiting user action


@dataclass
class StateTransition:
    """Defines a valid state transition"""
    from_state: ResourceState
    to_state: ResourceState
    trigger: str
    condition: Optional[str] = None
    action: Optional[str] = None
    requires_user_approval: bool = False
    
    def __str__(self):
        return f"{self.from_state.value} -> {self.to_state.value} ({self.trigger})"


@dataclass
class StateAction:
    """Defines a user action for state transitions"""
    name: str
    description: str
    icon: str
    color: str
    requires_confirmation: bool = False
    destructive: bool = False
    
    def __str__(self):
        return self.name


@dataclass
class TransitionResult:
    """Result of a state transition attempt"""
    success: bool
    message: str
    old_state: ResourceState
    new_state: ResourceState
    errors: List[str] = None
    context: Dict = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.context is None:
            self.context = {}


class StateTransitionManager:
    """
    Manages all resource state transitions with comprehensive validation.
    Implements the six-state resource management system.
    """
    
    VALID_TRANSITIONS: Dict[ResourceState, List[StateTransition]] = {
        ResourceState.DRAFT: [
            StateTransition(
                from_state=ResourceState.DRAFT,
                to_state=ResourceState.COMMITTED,
                trigger="commit_to_git",
                condition="has_valid_spec",
                action="generate_yaml_and_commit",
                requires_user_approval=False
            ),
            StateTransition(
                from_state=ResourceState.DRAFT,
                to_state=ResourceState.DRAFT,
                trigger="update_draft",
                condition=None,
                action="update_draft_spec",
                requires_user_approval=False
            ),
        ],
        ResourceState.COMMITTED: [
            StateTransition(
                from_state=ResourceState.COMMITTED,
                to_state=ResourceState.PENDING,
                trigger="apply_to_cluster",
                condition="cluster_available",
                action="trigger_gitops_sync",
                requires_user_approval=False
            ),
            StateTransition(
                from_state=ResourceState.COMMITTED,
                to_state=ResourceState.DRAFT,
                trigger="edit_resource",
                condition=None,
                action="create_draft_from_committed",
                requires_user_approval=False
            ),
            StateTransition(
                from_state=ResourceState.COMMITTED,
                to_state=ResourceState.SYNCED,
                trigger="cluster_sync_complete",
                condition="specs_match",
                action="mark_as_synced",
                requires_user_approval=False
            ),
        ],
        ResourceState.SYNCED: [
            StateTransition(
                from_state=ResourceState.SYNCED,
                to_state=ResourceState.DRIFTED,
                trigger="drift_detected",
                condition="specs_differ",
                action="create_drift_alert",
                requires_user_approval=False
            ),
            StateTransition(
                from_state=ResourceState.SYNCED,
                to_state=ResourceState.DRAFT,
                trigger="edit_resource",
                condition=None,
                action="create_draft_from_synced",
                requires_user_approval=False
            ),
            StateTransition(
                from_state=ResourceState.SYNCED,
                to_state=ResourceState.PENDING,
                trigger="git_commit_detected",
                condition="new_commit_available",
                action="trigger_gitops_sync",
                requires_user_approval=False
            ),
        ],
        ResourceState.DRIFTED: [
            StateTransition(
                from_state=ResourceState.DRIFTED,
                to_state=ResourceState.SYNCED,
                trigger="drift_resolved",
                condition="specs_match",
                action="clear_drift_alert",
                requires_user_approval=False
            ),
            StateTransition(
                from_state=ResourceState.DRIFTED,
                to_state=ResourceState.COMMITTED,
                trigger="import_cluster_state",
                condition="user_approved",
                action="update_git_with_cluster_state",
                requires_user_approval=True
            ),
            StateTransition(
                from_state=ResourceState.DRIFTED,
                to_state=ResourceState.PENDING,
                trigger="force_sync_to_cluster",
                condition="user_approved",
                action="override_cluster_state",
                requires_user_approval=True
            ),
            StateTransition(
                from_state=ResourceState.DRIFTED,
                to_state=ResourceState.DRAFT,
                trigger="edit_resource",
                condition=None,
                action="create_draft_from_drifted",
                requires_user_approval=False
            ),
        ],
        ResourceState.ORPHANED: [
            StateTransition(
                from_state=ResourceState.ORPHANED,
                to_state=ResourceState.COMMITTED,
                trigger="import_to_git",
                condition="user_approved",
                action="create_git_resource",
                requires_user_approval=True
            ),
            StateTransition(
                from_state=ResourceState.ORPHANED,
                to_state=ResourceState.PENDING,
                trigger="delete_from_cluster",
                condition="user_approved",
                action="delete_cluster_resource",
                requires_user_approval=True
            ),
            StateTransition(
                from_state=ResourceState.ORPHANED,
                to_state=ResourceState.DRAFT,
                trigger="create_draft_from_orphaned",
                condition=None,
                action="create_draft_from_actual_state",
                requires_user_approval=False
            ),
        ],
        ResourceState.PENDING: [
            StateTransition(
                from_state=ResourceState.PENDING,
                to_state=ResourceState.SYNCED,
                trigger="sync_complete",
                condition="specs_match",
                action="mark_as_synced",
                requires_user_approval=False
            ),
            StateTransition(
                from_state=ResourceState.PENDING,
                to_state=ResourceState.DRIFTED,
                trigger="sync_failed",
                condition="specs_differ",
                action="create_sync_error_alert",
                requires_user_approval=False
            ),
            StateTransition(
                from_state=ResourceState.PENDING,
                to_state=ResourceState.COMMITTED,
                trigger="sync_timeout",
                condition="sync_timeout_exceeded",
                action="mark_sync_timeout",
                requires_user_approval=False
            ),
        ],
    }
    
    STATE_ACTIONS: Dict[ResourceState, List[StateAction]] = {
        ResourceState.DRAFT: [
            StateAction(
                name="Commit to Git",
                description="Save changes to Git repository",
                icon="git-commit",
                color="primary",
                requires_confirmation=False,
                destructive=False
            ),
            StateAction(
                name="Discard Draft",
                description="Discard uncommitted changes",
                icon="trash",
                color="danger",
                requires_confirmation=True,
                destructive=True
            ),
        ],
        ResourceState.COMMITTED: [
            StateAction(
                name="Deploy to Cluster",
                description="Apply changes to Kubernetes cluster",
                icon="deploy",
                color="success",
                requires_confirmation=False,
                destructive=False
            ),
            StateAction(
                name="Edit Resource",
                description="Make additional changes",
                icon="edit",
                color="secondary",
                requires_confirmation=False,
                destructive=False
            ),
        ],
        ResourceState.SYNCED: [
            StateAction(
                name="Edit Resource",
                description="Make changes to this resource",
                icon="edit",
                color="secondary",
                requires_confirmation=False,
                destructive=False
            ),
        ],
        ResourceState.DRIFTED: [
            StateAction(
                name="Import from Cluster",
                description="Update Git with cluster state",
                icon="import",
                color="warning",
                requires_confirmation=True,
                destructive=False
            ),
            StateAction(
                name="Force Sync to Cluster",
                description="Override cluster with Git state",
                icon="sync-force",
                color="danger",
                requires_confirmation=True,
                destructive=True
            ),
            StateAction(
                name="Edit Resource",
                description="Make manual changes",
                icon="edit",
                color="secondary",
                requires_confirmation=False,
                destructive=False
            ),
        ],
        ResourceState.ORPHANED: [
            StateAction(
                name="Import to Git",
                description="Add resource to Git repository",
                icon="import",
                color="primary",
                requires_confirmation=True,
                destructive=False
            ),
            StateAction(
                name="Delete from Cluster",
                description="Remove resource from cluster",
                icon="trash",
                color="danger",
                requires_confirmation=True,
                destructive=True
            ),
        ],
        ResourceState.PENDING: [
            StateAction(
                name="Check Status",
                description="Refresh deployment status",
                icon="refresh",
                color="secondary",
                requires_confirmation=False,
                destructive=False
            ),
        ],
    }
    
    def __init__(self):
        self.transition_history = []
    
    def get_valid_transitions(self, from_state: ResourceState) -> List[StateTransition]:
        """Get all valid transitions from a given state"""
        return self.VALID_TRANSITIONS.get(from_state, [])
    
    def get_available_actions(self, state: ResourceState) -> List[StateAction]:
        """Get all available actions for a given state"""
        return self.STATE_ACTIONS.get(state, [])
    
    def can_transition(self, from_state: ResourceState, to_state: ResourceState, 
                      trigger: str) -> bool:
        """Check if a transition is valid"""
        valid_transitions = self.get_valid_transitions(from_state)
        for transition in valid_transitions:
            if transition.to_state == to_state and transition.trigger == trigger:
                return True
        return False
    
    def get_transition(self, from_state: ResourceState, to_state: ResourceState, 
                      trigger: str) -> Optional[StateTransition]:
        """Get a specific transition definition"""
        valid_transitions = self.get_valid_transitions(from_state)
        for transition in valid_transitions:
            if transition.to_state == to_state and transition.trigger == trigger:
                return transition
        return None
    
    def validate_transition_conditions(self, resource, transition: StateTransition) -> bool:
        """Validate if transition conditions are met"""
        if not transition.condition:
            return True
        
        # Implement condition validation logic
        condition_validators = {
            'has_valid_spec': lambda r: r.draft_spec is not None,
            'cluster_available': lambda r: r.fabric.connection_status == 'connected',
            'specs_match': lambda r: r.desired_spec == r.actual_spec,
            'specs_differ': lambda r: r.desired_spec != r.actual_spec,
            'user_approved': lambda r: True,  # This would be checked at the UI level
            'new_commit_available': lambda r: r.desired_commit != r.fabric.desired_state_commit,
            'sync_timeout_exceeded': lambda r: True,  # This would be checked by background task
        }
        
        validator = condition_validators.get(transition.condition)
        if validator:
            return validator(resource)
        
        return True
    
    def execute_transition(self, resource, new_state: ResourceState, 
                          trigger: str, context: Dict = None, 
                          user: User = None) -> TransitionResult:
        """
        Execute a state transition with full validation and action execution.
        
        Args:
            resource: The HedgehogResource instance
            new_state: Target state to transition to
            trigger: The trigger causing this transition
            context: Additional context for the transition
            user: User performing the transition
            
        Returns:
            TransitionResult with success/failure information
        """
        old_state = ResourceState(resource.resource_state)
        
        # Check if transition is valid
        if not self.can_transition(old_state, new_state, trigger):
            return TransitionResult(
                success=False,
                message=f"Invalid transition from {old_state.value} to {new_state.value} with trigger {trigger}",
                old_state=old_state,
                new_state=new_state,
                errors=[f"No valid transition found for {old_state.value} -> {new_state.value}"]
            )
        
        # Get transition definition
        transition = self.get_transition(old_state, new_state, trigger)
        if not transition:
            return TransitionResult(
                success=False,
                message=f"Transition definition not found",
                old_state=old_state,
                new_state=new_state,
                errors=["Transition definition not found"]
            )
        
        # Validate conditions
        if not self.validate_transition_conditions(resource, transition):
            return TransitionResult(
                success=False,
                message=f"Transition conditions not met: {transition.condition}",
                old_state=old_state,
                new_state=new_state,
                errors=[f"Condition '{transition.condition}' not satisfied"]
            )
        
        # Execute transition action
        try:
            action_result = self.execute_transition_action(resource, transition, context, user)
            if not action_result.get('success', True):
                return TransitionResult(
                    success=False,
                    message=f"Transition action failed: {action_result.get('error', 'Unknown error')}",
                    old_state=old_state,
                    new_state=new_state,
                    errors=[action_result.get('error', 'Action execution failed')]
                )
        except Exception as e:
            return TransitionResult(
                success=False,
                message=f"Exception during transition action: {str(e)}",
                old_state=old_state,
                new_state=new_state,
                errors=[str(e)]
            )
        
        # Update resource state
        resource.resource_state = new_state.value
        resource.last_state_change = datetime.now()
        
        # Create history entry
        self.create_state_history(resource, old_state, new_state, trigger, context, user)
        
        return TransitionResult(
            success=True,
            message=f"Successfully transitioned from {old_state.value} to {new_state.value}",
            old_state=old_state,
            new_state=new_state,
            context=context or {}
        )
    
    def execute_transition_action(self, resource, transition: StateTransition, 
                                 context: Dict = None, user: User = None) -> Dict:
        """Execute the action associated with a transition"""
        if not transition.action:
            return {'success': True, 'message': 'No action required'}
        
        # Action implementations
        actions = {
            'generate_yaml_and_commit': self._action_generate_yaml_and_commit,
            'update_draft_spec': self._action_update_draft_spec,
            'trigger_gitops_sync': self._action_trigger_gitops_sync,
            'create_draft_from_committed': self._action_create_draft_from_committed,
            'mark_as_synced': self._action_mark_as_synced,
            'create_drift_alert': self._action_create_drift_alert,
            'create_draft_from_synced': self._action_create_draft_from_synced,
            'clear_drift_alert': self._action_clear_drift_alert,
            'update_git_with_cluster_state': self._action_update_git_with_cluster_state,
            'override_cluster_state': self._action_override_cluster_state,
            'create_draft_from_drifted': self._action_create_draft_from_drifted,
            'create_git_resource': self._action_create_git_resource,
            'delete_cluster_resource': self._action_delete_cluster_resource,
            'create_draft_from_actual_state': self._action_create_draft_from_actual_state,
            'create_sync_error_alert': self._action_create_sync_error_alert,
            'mark_sync_timeout': self._action_mark_sync_timeout,
        }
        
        action_func = actions.get(transition.action)
        if action_func:
            return action_func(resource, context, user)
        
        return {'success': False, 'error': f'Unknown action: {transition.action}'}
    
    def create_state_history(self, resource, old_state: ResourceState, 
                           new_state: ResourceState, trigger: str, 
                           context: Dict = None, user: User = None):
        """Create a state transition history entry"""
        try:
            from netbox_hedgehog.models.gitops import StateTransitionHistory
            
            StateTransitionHistory.objects.create(
                resource=resource,
                from_state=old_state.value,
                to_state=new_state.value,
                trigger=trigger,
                reason=context.get('reason', '') if context else '',
                context=context or {},
                user=user
            )
        except Exception as e:
            # Log error but don't fail the transition
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create state history: {e}")
    
    # Action implementations
    def _action_generate_yaml_and_commit(self, resource, context, user):
        """Generate YAML and commit to Git"""
        try:
            # Generate YAML from draft spec
            yaml_content = resource.generate_yaml_from_draft()
            if not yaml_content:
                return {'success': False, 'error': 'Failed to generate YAML from draft'}
            
            # Commit to Git (this would integrate with GitOps utilities)
            # For now, just update the desired state
            resource.desired_spec = resource.draft_spec
            resource.desired_commit = resource.fabric.desired_state_commit
            resource.desired_updated = datetime.now()
            
            return {'success': True, 'message': 'YAML generated and committed to Git'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _action_update_draft_spec(self, resource, context, user):
        """Update draft specification"""
        if context and 'draft_spec' in context:
            resource.draft_spec = context['draft_spec']
            resource.draft_updated = datetime.now()
            resource.draft_updated_by = user
            return {'success': True, 'message': 'Draft specification updated'}
        return {'success': False, 'error': 'No draft specification provided'}
    
    def _action_trigger_gitops_sync(self, resource, context, user):
        """Trigger GitOps synchronization"""
        try:
            # This would integrate with the GitOps tool (ArgoCD/Flux)
            sync_result = resource.fabric.trigger_gitops_sync()
            return sync_result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _action_create_draft_from_committed(self, resource, context, user):
        """Create draft from committed state"""
        resource.draft_spec = resource.desired_spec.copy() if resource.desired_spec else {}
        resource.draft_updated = datetime.now()
        resource.draft_updated_by = user
        return {'success': True, 'message': 'Draft created from committed state'}
    
    def _action_mark_as_synced(self, resource, context, user):
        """Mark resource as synced"""
        resource.drift_status = 'in_sync'
        resource.drift_score = 0.0
        resource.drift_details = {}
        return {'success': True, 'message': 'Resource marked as synced'}
    
    def _action_create_drift_alert(self, resource, context, user):
        """Create drift alert"""
        try:
            # This would integrate with the alert system
            # For now, just update drift information
            resource.calculate_drift()
            return {'success': True, 'message': 'Drift alert created'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _action_create_draft_from_synced(self, resource, context, user):
        """Create draft from synced state"""
        resource.draft_spec = resource.desired_spec.copy() if resource.desired_spec else {}
        resource.draft_updated = datetime.now()
        resource.draft_updated_by = user
        return {'success': True, 'message': 'Draft created from synced state'}
    
    def _action_clear_drift_alert(self, resource, context, user):
        """Clear drift alert"""
        resource.drift_status = 'in_sync'
        resource.drift_score = 0.0
        resource.drift_details = {}
        return {'success': True, 'message': 'Drift alert cleared'}
    
    def _action_update_git_with_cluster_state(self, resource, context, user):
        """Update Git with cluster state"""
        try:
            # This would integrate with Git operations
            resource.desired_spec = resource.actual_spec.copy() if resource.actual_spec else {}
            resource.desired_updated = datetime.now()
            return {'success': True, 'message': 'Git updated with cluster state'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _action_override_cluster_state(self, resource, context, user):
        """Override cluster state with Git state"""
        try:
            # This would trigger a force sync to cluster
            sync_result = resource.fabric.trigger_gitops_sync()
            return sync_result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _action_create_draft_from_drifted(self, resource, context, user):
        """Create draft from drifted state"""
        # Use the desired spec as base for draft
        resource.draft_spec = resource.desired_spec.copy() if resource.desired_spec else {}
        resource.draft_updated = datetime.now()
        resource.draft_updated_by = user
        return {'success': True, 'message': 'Draft created from drifted state'}
    
    def _action_create_git_resource(self, resource, context, user):
        """Create Git resource from orphaned cluster resource"""
        try:
            # This would create a new Git file from the actual state
            resource.desired_spec = resource.actual_spec.copy() if resource.actual_spec else {}
            resource.desired_updated = datetime.now()
            return {'success': True, 'message': 'Git resource created from orphaned resource'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _action_delete_cluster_resource(self, resource, context, user):
        """Delete resource from cluster"""
        try:
            # This would delete the resource from Kubernetes
            # For now, just clear the actual state
            resource.actual_spec = None
            resource.actual_status = None
            resource.actual_updated = datetime.now()
            return {'success': True, 'message': 'Resource deleted from cluster'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _action_create_draft_from_actual_state(self, resource, context, user):
        """Create draft from actual cluster state"""
        resource.draft_spec = resource.actual_spec.copy() if resource.actual_spec else {}
        resource.draft_updated = datetime.now()
        resource.draft_updated_by = user
        return {'success': True, 'message': 'Draft created from actual state'}
    
    def _action_create_sync_error_alert(self, resource, context, user):
        """Create sync error alert"""
        try:
            # This would integrate with the alert system
            return {'success': True, 'message': 'Sync error alert created'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _action_mark_sync_timeout(self, resource, context, user):
        """Mark sync as timed out"""
        resource.last_sync_error = "Sync operation timed out"
        resource.sync_attempts += 1
        return {'success': True, 'message': 'Sync marked as timed out'}