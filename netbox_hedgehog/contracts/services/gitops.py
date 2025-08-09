"""
GitOps Service Protocols

typing.Protocol definitions for GitOps operations including:
- Resource state management
- Drift detection and reconciliation
- State transitions and history tracking
"""

from typing import Protocol, List, Optional, Dict, Any, Tuple
from datetime import datetime


class GitOpsService(Protocol):
    """Service protocol for GitOps workflow operations"""
    
    def sync_from_git(self, fabric_id: int, force: bool = False) -> Dict[str, Any]:
        """Sync resources from Git repository"""
        ...
    
    def sync_to_kubernetes(self, fabric_id: int, resource_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """Sync resources to Kubernetes cluster"""
        ...
    
    def sync_from_kubernetes(self, fabric_id: int, resource_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """Sync resource states from Kubernetes cluster"""
        ...
    
    def commit_changes(self, resource_ids: List[int], commit_message: str, 
                      author_name: str, author_email: str) -> Dict[str, Any]:
        """Commit resource changes to Git repository"""
        ...
    
    def preview_changes(self, resource_ids: List[int]) -> Dict[str, Any]:
        """Preview changes that would be committed"""
        ...
    
    def rollback_to_commit(self, fabric_id: int, commit_sha: str) -> Dict[str, Any]:
        """Rollback fabric to specific Git commit"""
        ...
    
    def get_workflow_status(self, fabric_id: int) -> Dict[str, Any]:
        """Get overall GitOps workflow status for fabric"""
        ...


class StateTransitionService(Protocol):
    """Service protocol for resource state transitions"""
    
    def transition_resource(self, resource_id: int, target_state: str, 
                          trigger: str, reason: Optional[str] = None,
                          context: Optional[Dict[str, Any]] = None,
                          user_id: Optional[int] = None) -> bool:
        """Transition resource to target state"""
        ...
    
    def get_valid_transitions(self, resource_id: int) -> List[str]:
        """Get valid next states for resource"""
        ...
    
    def get_transition_history(self, resource_id: int, 
                             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get state transition history for resource"""
        ...
    
    def get_fabric_state_summary(self, fabric_id: int) -> Dict[str, Any]:
        """Get state summary for all resources in fabric"""
        ...
    
    def bulk_transition(self, resource_ids: List[int], target_state: str,
                       trigger: str, reason: Optional[str] = None,
                       user_id: Optional[int] = None) -> Dict[str, List[int]]:
        """Transition multiple resources to target state"""
        ...


class DriftDetectionService(Protocol):
    """Service protocol for drift detection and reconciliation"""
    
    def detect_drift(self, resource_id: int) -> Dict[str, Any]:
        """Detect drift for specific resource"""
        ...
    
    def detect_fabric_drift(self, fabric_id: int) -> Dict[str, Any]:
        """Detect drift for all resources in fabric"""
        ...
    
    def analyze_drift(self, resource_id: int) -> Dict[str, Any]:
        """Perform detailed drift analysis"""
        ...
    
    def calculate_drift_score(self, desired_spec: Dict[str, Any], 
                            actual_spec: Dict[str, Any]) -> float:
        """Calculate numerical drift score between specs"""
        ...
    
    def get_drift_recommendations(self, resource_id: int) -> List[Dict[str, Any]]:
        """Get recommendations for resolving drift"""
        ...
    
    def resolve_drift(self, resource_id: int, action: str, 
                     user_id: Optional[int] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Resolve drift with specified action"""
        ...
    
    def create_drift_alert(self, resource_id: int, drift_details: Dict[str, Any],
                          severity: str = "medium") -> int:
        """Create reconciliation alert for drift"""
        ...
    
    def get_drift_metrics(self, fabric_id: int, 
                        time_range: Optional[Tuple[datetime, datetime]] = None) -> Dict[str, Any]:
        """Get drift metrics for fabric"""
        ...
    
    def schedule_drift_scan(self, fabric_id: int, interval_seconds: int) -> bool:
        """Schedule periodic drift scanning"""
        ...
    
    def get_orphaned_resources(self, fabric_id: int) -> List[Dict[str, Any]]:
        """Find resources that exist in K8s but not in Git"""
        ...
    
    def get_missing_resources(self, fabric_id: int) -> List[Dict[str, Any]]:
        """Find resources that exist in Git but not in K8s"""
        ...


class ReconciliationService(Protocol):
    """Service protocol for reconciliation operations"""
    
    def reconcile_resource(self, resource_id: int, strategy: str = "auto") -> Dict[str, Any]:
        """Reconcile single resource using specified strategy"""
        ...
    
    def reconcile_fabric(self, fabric_id: int, strategy: str = "auto") -> Dict[str, Any]:
        """Reconcile all resources in fabric"""
        ...
    
    def get_reconciliation_strategies(self) -> List[Dict[str, Any]]:
        """Get available reconciliation strategies"""
        ...
    
    def validate_reconciliation_plan(self, resource_ids: List[int], 
                                   strategy: str) -> Dict[str, Any]:
        """Validate reconciliation plan before execution"""
        ...
    
    def execute_reconciliation_plan(self, plan_id: str, 
                                  dry_run: bool = False) -> Dict[str, Any]:
        """Execute validated reconciliation plan"""
        ...
    
    def get_reconciliation_history(self, fabric_id: int, 
                                 limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get reconciliation operation history"""
        ...


class WorkflowService(Protocol):
    """Service protocol for GitOps workflow management"""
    
    def create_pull_request(self, resource_ids: List[int], title: str,
                          description: str, target_branch: str = "main") -> Dict[str, Any]:
        """Create pull request for resource changes"""
        ...
    
    def approve_pull_request(self, pr_id: int, user_id: int) -> Dict[str, Any]:
        """Approve pull request"""
        ...
    
    def merge_pull_request(self, pr_id: int, merge_strategy: str = "squash") -> Dict[str, Any]:
        """Merge approved pull request"""
        ...
    
    def create_release(self, fabric_id: int, version: str, 
                      release_notes: str) -> Dict[str, Any]:
        """Create release tag for fabric state"""
        ...
    
    def deploy_release(self, fabric_id: int, version: str) -> Dict[str, Any]:
        """Deploy specific release version"""
        ...
    
    def get_deployment_history(self, fabric_id: int) -> List[Dict[str, Any]]:
        """Get deployment history for fabric"""
        ...
    
    def validate_workflow_permissions(self, user_id: int, fabric_id: int,
                                    operation: str) -> bool:
        """Validate user permissions for workflow operation"""
        ...
    
    def get_workflow_metrics(self, fabric_id: int) -> Dict[str, Any]:
        """Get workflow performance metrics"""
        ...