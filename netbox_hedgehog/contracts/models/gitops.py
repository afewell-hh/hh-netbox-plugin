"""
GitOps Model Schemas

Pydantic schemas for GitOps-related NetBox Hedgehog Plugin models:
- HedgehogResource: GitOps resource state management
- StateTransitionHistory: Resource state change tracking  
- ReconciliationAlert: Drift detection and reconciliation alerts
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class ResourceState(str, Enum):
    """Resource state in GitOps workflow"""
    DRAFT = "draft"
    COMMITTED = "committed"
    SYNCED = "synced"
    DRIFTED = "drifted"
    ORPHANED = "orphaned"
    PENDING = "pending"


class DriftStatus(str, Enum):
    """Drift status between desired and actual state"""
    IN_SYNC = "in_sync"
    SPEC_DRIFT = "spec_drift"
    DESIRED_ONLY = "desired_only"
    ACTUAL_ONLY = "actual_only"
    CREATION_PENDING = "creation_pending"
    DELETION_PENDING = "deletion_pending"


class AlertType(str, Enum):
    """Types of reconciliation alerts"""
    DRIFT_DETECTED = "drift_detected"
    ORPHANED_RESOURCE = "orphaned_resource"
    CREATION_PENDING = "creation_pending"
    DELETION_PENDING = "deletion_pending"
    SYNC_FAILURE = "sync_failure"
    VALIDATION_ERROR = "validation_error"
    CONFLICT_DETECTED = "conflict_detected"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class SuggestedAction(str, Enum):
    """Suggested resolution actions"""
    IMPORT_TO_GIT = "import_to_git"
    DELETE_FROM_CLUSTER = "delete_from_cluster"
    UPDATE_GIT = "update_git"
    IGNORE = "ignore"
    MANUAL_REVIEW = "manual_review"


class HedgehogResourceSchema(BaseModel):
    """
    Schema for HedgehogResource model
    
    Represents a GitOps-managed Kubernetes resource with desired, draft, and actual states.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "example-vpc",
                    "namespace": "default",
                    "kind": "VPC",
                    "api_version": "vpc.githedgehog.com/v1alpha2",
                    "content_type": 45,
                    "object_id": 123,
                    "desired_spec": {
                        "subnets": ["10.1.0.0/24"],
                        "permit": ["any"]
                    },
                    "desired_commit": "abc123def456",
                    "desired_file_path": "/vpcs/example-vpc.yaml",
                    "desired_updated": "2024-01-15T10:00:00Z",
                    "draft_spec": {
                        "subnets": ["10.1.0.0/24", "10.1.1.0/24"],
                        "permit": ["any"]
                    },
                    "draft_updated": "2024-01-15T11:00:00Z",
                    "draft_updated_by": 5,
                    "actual_spec": {
                        "subnets": ["10.1.0.0/24"],
                        "permit": ["any"]
                    },
                    "actual_status": {
                        "state": "Ready",
                        "conditions": []
                    },
                    "actual_resource_version": "12345",
                    "actual_updated": "2024-01-15T10:05:00Z",
                    "resource_state": "drifted",
                    "last_state_change": "2024-01-15T11:00:00Z",
                    "state_change_reason": "Draft modified by user",
                    "drift_status": "spec_drift",
                    "drift_details": {
                        "fields_changed": ["subnets"],
                        "severity": "medium"
                    },
                    "drift_score": 0.3
                }
            ]
        }
    )

    # Primary key
    id: Optional[int] = Field(None, description="Database primary key")
    
    # Required relationships
    fabric: int = Field(..., description="HedgehogFabric ID this resource belongs to")
    
    # Required Kubernetes identity
    name: str = Field(..., max_length=253, description="DNS-1123 compliant resource name")
    kind: str = Field(..., max_length=50, description="Kubernetes resource kind")
    
    # Optional Kubernetes identity
    namespace: str = Field("default", max_length=253, description="Kubernetes namespace")
    api_version: str = Field("unknown/v1", max_length=100, description="Kubernetes API version")
    
    # Generic foreign key to linked CRD object
    content_type: Optional[int] = Field(None, description="Content type of linked CRD object")
    object_id: Optional[int] = Field(None, description="ID of linked CRD object")
    
    # Desired state (from Git)
    desired_spec: Optional[Dict[str, Any]] = Field(None, description="Desired spec from Git repository")
    desired_commit: Optional[str] = Field(None, max_length=40, description="Git commit SHA")
    desired_file_path: Optional[str] = Field(None, max_length=500, description="Path to YAML file in Git")
    desired_updated: Optional[datetime] = Field(None, description="When desired state was last updated")
    
    # Draft state (uncommitted changes)
    draft_spec: Optional[Dict[str, Any]] = Field(None, description="Draft spec (uncommitted)")
    draft_updated: Optional[datetime] = Field(None, description="When draft was last updated")
    draft_updated_by: Optional[int] = Field(None, description="User who last updated draft")
    
    # Actual state (from Kubernetes)
    actual_spec: Optional[Dict[str, Any]] = Field(None, description="Actual spec from Kubernetes")
    actual_status: Optional[Dict[str, Any]] = Field(None, description="Actual status from Kubernetes")
    actual_resource_version: Optional[str] = Field(None, max_length=50, description="K8s resource version")
    actual_updated: Optional[datetime] = Field(None, description="When actual state was last updated")
    
    # State management
    resource_state: ResourceState = Field(ResourceState.DRAFT, description="Current resource state")
    last_state_change: Optional[datetime] = Field(None, description="Timestamp of last state change")
    state_change_reason: Optional[str] = Field(None, description="Reason for last state change")
    
    # Drift detection
    drift_status: DriftStatus = Field(DriftStatus.IN_SYNC, description="Current drift status")
    drift_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed drift analysis")
    drift_score: float = Field(0.0, ge=0.0, le=1.0, description="Numerical drift score")
    
    # Relationships (many-to-many dependencies handled separately)
    dependent_resources: Optional[List[int]] = Field(None, description="List of dependent resource IDs")
    
    # Timestamps
    created: Optional[datetime] = Field(None, description="Creation timestamp")
    last_updated: Optional[datetime] = Field(None, description="Last modification timestamp")


class StateTransitionHistorySchema(BaseModel):
    """
    Schema for StateTransitionHistory model
    
    Tracks state transitions for HedgehogResource instances.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "resource": 1,
                    "from_state": "committed",
                    "to_state": "drifted",
                    "trigger": "drift_detection",
                    "reason": "Actual state differs from desired state in Git",
                    "context": {
                        "fields_changed": ["subnets"],
                        "drift_score": 0.3,
                        "detection_method": "periodic_scan"
                    },
                    "timestamp": "2024-01-15T11:00:00Z",
                    "user": None
                }
            ]
        }
    )

    # Primary key
    id: Optional[int] = Field(None, description="Database primary key")
    
    # Required relationships
    resource: int = Field(..., description="HedgehogResource ID this transition belongs to")
    
    # Required transition fields
    from_state: ResourceState = Field(..., description="Previous state")
    to_state: ResourceState = Field(..., description="New state")
    trigger: str = Field(..., max_length=50, description="What triggered the transition")
    
    # Optional fields
    reason: Optional[str] = Field(None, description="Reason for transition")
    context: Dict[str, Any] = Field(default_factory=dict, description="Transition context")
    timestamp: Optional[datetime] = Field(None, description="When transition occurred")
    user: Optional[int] = Field(None, description="User who triggered transition")


class ReconciliationAlertSchema(BaseModel):
    """
    Schema for ReconciliationAlert model
    
    Represents alerts generated during drift detection and reconciliation processes.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "resource": 1,
                    "alert_type": "drift_detected",
                    "severity": "medium",
                    "status": "active",
                    "title": "Configuration Drift Detected",
                    "message": "Resource spec has diverged from Git repository. Subnets field has been modified.",
                    "alert_context": {
                        "detection_time": "2024-01-15T11:00:00Z",
                        "drift_score": 0.3,
                        "affected_fields": ["subnets"]
                    },
                    "drift_details": {
                        "desired": {"subnets": ["10.1.0.0/24"]},
                        "actual": {"subnets": ["10.1.0.0/24", "10.1.1.0/24"]},
                        "diff": {"+": ["10.1.1.0/24"]}
                    },
                    "suggested_action": "update_git",
                    "created": "2024-01-15T11:00:00Z",
                    "expires_at": "2024-01-22T11:00:00Z"
                }
            ]
        }
    )

    # Primary key
    id: Optional[int] = Field(None, description="Database primary key")
    
    # Required relationships
    fabric: int = Field(..., description="HedgehogFabric ID this alert belongs to")
    resource: int = Field(..., description="HedgehogResource ID this alert is for")
    
    # Required alert fields
    alert_type: AlertType = Field(..., description="Type of reconciliation alert")
    title: str = Field(..., max_length=200, description="Alert title")
    message: str = Field(..., description="Detailed alert message")
    
    # Classification
    severity: AlertSeverity = Field(AlertSeverity.MEDIUM, description="Alert severity level")
    status: AlertStatus = Field(AlertStatus.ACTIVE, description="Current alert status")
    
    # Context and details
    alert_context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    drift_details: Dict[str, Any] = Field(default_factory=dict, description="Drift analysis details")
    
    # Resolution
    suggested_action: SuggestedAction = Field(SuggestedAction.MANUAL_REVIEW, description="Suggested action")
    resolved_action: Optional[SuggestedAction] = Field(None, description="Action taken to resolve")
    resolution_metadata: Dict[str, Any] = Field(default_factory=dict, description="Resolution metadata")
    
    # Timestamps
    created: Optional[datetime] = Field(None, description="When alert was created")
    acknowledged_at: Optional[datetime] = Field(None, description="When alert was acknowledged")
    resolved_at: Optional[datetime] = Field(None, description="When alert was resolved")
    expires_at: Optional[datetime] = Field(None, description="When alert expires")
    
    # Users
    created_by: Optional[int] = Field(None, description="User who created this alert")
    acknowledged_by: Optional[int] = Field(None, description="User who acknowledged this alert")
    resolved_by: Optional[int] = Field(None, description="User who resolved this alert")
    
    # Related alerts (many-to-many handled separately)
    related_alerts: Optional[List[int]] = Field(None, description="List of related alert IDs")


# Export schemas for JSON Schema generation
def get_json_schemas() -> Dict[str, Dict[str, Any]]:
    """
    Generate JSON schemas for all GitOps models.
    
    Returns:
        Dictionary mapping model names to their JSON schemas
    """
    return {
        "HedgehogResource": HedgehogResourceSchema.model_json_schema(),
        "StateTransitionHistory": StateTransitionHistorySchema.model_json_schema(),
        "ReconciliationAlert": ReconciliationAlertSchema.model_json_schema(),
    }


# Export example data for testing
def get_example_data() -> Dict[str, Any]:
    """
    Generate example data for all GitOps models.
    
    Returns:
        Dictionary mapping model names to example instances
    """
    return {
        "HedgehogResource": HedgehogResourceSchema.model_config["json_schema_extra"]["examples"][0],
        "StateTransitionHistory": StateTransitionHistorySchema.model_config["json_schema_extra"]["examples"][0],
        "ReconciliationAlert": ReconciliationAlertSchema.model_config["json_schema_extra"]["examples"][0],
    }