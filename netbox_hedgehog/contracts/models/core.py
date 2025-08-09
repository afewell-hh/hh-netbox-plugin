"""
Core Model Schemas

Pydantic schemas for core NetBox Hedgehog Plugin models:
- HedgehogFabric: Main fabric management entity
- GitRepository: Git repository configuration
- BaseCRD: Base class for Kubernetes Custom Resource Definitions
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from enum import Enum


class FabricStatus(str, Enum):
    """Fabric configuration status"""
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    DECOMMISSIONED = "DECOMMISSIONED"


class ConnectionStatus(str, Enum):
    """Connection status for external systems"""
    UNKNOWN = "UNKNOWN"
    CONNECTED = "CONNECTED"
    FAILED = "FAILED"
    TESTING = "TESTING"


class SyncStatus(str, Enum):
    """Synchronization status"""
    NEVER_SYNCED = "NEVER_SYNCED"
    IN_SYNC = "IN_SYNC"
    OUT_OF_SYNC = "OUT_OF_SYNC"
    SYNCING = "SYNCING"
    ERROR = "ERROR"


class GitProvider(str, Enum):
    """Git provider types"""
    GITHUB = "GITHUB"
    GITLAB = "GITLAB"
    BITBUCKET = "BITBUCKET"
    GENERIC = "GENERIC"


class AuthenticationType(str, Enum):
    """Authentication methods for Git repositories"""
    TOKEN = "TOKEN"
    BASIC = "BASIC"
    SSH = "SSH"
    OAUTH = "OAUTH"


class KubernetesStatus(str, Enum):
    """Kubernetes resource status"""
    LIVE = "LIVE"
    APPLIED = "APPLIED"
    PENDING = "PENDING"
    SYNCING = "SYNCING"
    ERROR = "ERROR"
    DELETING = "DELETING"
    UNKNOWN = "UNKNOWN"


class HedgehogFabricSchema(BaseModel):
    """
    Schema for HedgehogFabric model
    
    Represents a Hedgehog network fabric with Kubernetes and Git integration.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "name": "production-fabric",
                    "description": "Production Hedgehog fabric for datacenter A",
                    "status": "ACTIVE",
                    "connection_status": "CONNECTED", 
                    "sync_status": "IN_SYNC",
                    "kubernetes_server": "https://k8s-api.example.com:6443",
                    "kubernetes_namespace": "hedgehog-prod",
                    "sync_enabled": True,
                    "sync_interval": 300,
                    "last_sync": "2024-01-15T10:30:00Z",
                    "git_repository": 1,
                    "gitops_directory": "/fabrics/production/"
                }
            ]
        }
    )

    # Primary key
    id: Optional[int] = Field(None, description="Database primary key")
    
    # Required fields
    name: str = Field(..., max_length=100, description="Unique name for this Hedgehog fabric")
    
    # Optional fields
    description: Optional[str] = Field(None, description="Optional description of this fabric")
    status: FabricStatus = Field(FabricStatus.PLANNED, description="Configuration status")
    connection_status: ConnectionStatus = Field(ConnectionStatus.UNKNOWN, description="Connection status")
    sync_status: SyncStatus = Field(SyncStatus.NEVER_SYNCED, description="Sync status with Kubernetes")
    
    # Kubernetes configuration
    kubernetes_server: Optional[HttpUrl] = Field(None, description="Kubernetes API server URL")
    kubernetes_token: Optional[str] = Field(None, description="Service account token")
    kubernetes_ca_cert: Optional[str] = Field(None, description="CA certificate")
    kubernetes_namespace: str = Field("default", max_length=253, description="Default namespace")
    
    # Sync configuration
    sync_enabled: bool = Field(True, description="Enable automatic synchronization")
    sync_interval: int = Field(300, ge=0, description="Sync interval in seconds")
    last_sync: Optional[datetime] = Field(None, description="Last successful sync timestamp")
    sync_error: Optional[str] = Field(None, description="Last sync error message")
    connection_error: Optional[str] = Field(None, description="Last connection error message")
    
    # Git configuration
    git_repository: Optional[int] = Field(None, description="Reference to GitRepository")
    gitops_directory: str = Field("/", max_length=500, description="Directory path for CRDs")
    
    # Deprecated fields (maintained for backwards compatibility)
    git_repository_url: Optional[HttpUrl] = Field(None, description="[DEPRECATED] Use git_repository")
    git_branch: str = Field("main", max_length=100, description="[DEPRECATED] Managed by GitRepository")
    git_path: str = Field("hedgehog/", max_length=255, description="[DEPRECATED] Use gitops_directory")
    
    # Timestamps
    created: Optional[datetime] = Field(None, description="Creation timestamp")
    last_updated: Optional[datetime] = Field(None, description="Last modification timestamp")


class GitRepositorySchema(BaseModel):
    """
    Schema for GitRepository model
    
    Represents a Git repository with authentication configuration.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "name": "hedgehog-configs",
                    "url": "https://github.com/example/hedgehog-configs.git",
                    "provider": "GITHUB",
                    "authentication_type": "TOKEN",
                    "connection_status": "CONNECTED",
                    "last_validated": "2024-01-15T09:00:00Z",
                    "default_branch": "main",
                    "is_private": True,
                    "fabric_count": 3,
                    "validate_ssl": True,
                    "timeout_seconds": 30
                }
            ]
        }
    )

    # Primary key
    id: Optional[int] = Field(None, description="Database primary key")
    
    # Required fields
    name: str = Field(..., max_length=200, description="User-friendly repository name")
    url: HttpUrl = Field(..., description="Git repository URL")
    
    # Configuration fields
    provider: GitProvider = Field(GitProvider.GENERIC, description="Git provider type")
    authentication_type: AuthenticationType = Field(AuthenticationType.TOKEN, description="Authentication method")
    encrypted_credentials: Optional[str] = Field(None, description="Encrypted credentials JSON")
    
    # Status fields
    connection_status: ConnectionStatus = Field(ConnectionStatus.PENDING, description="Current connection status")
    last_validated: Optional[datetime] = Field(None, description="Last successful connection test")
    validation_error: Optional[str] = Field(None, description="Last validation error")
    
    # Repository configuration
    default_branch: str = Field("main", max_length=100, description="Default branch")
    is_private: bool = Field(False, description="Whether repository is private")
    fabric_count: int = Field(0, ge=0, description="Number of fabrics using this repository")
    
    # Metadata
    created_by: Optional[int] = Field(None, description="User who created this repository")
    description: Optional[str] = Field(None, description="Optional description")
    
    # Connection settings
    validate_ssl: bool = Field(True, description="Validate SSL certificates")
    timeout_seconds: int = Field(30, ge=1, le=300, description="Connection timeout")
    
    # Timestamps
    created: Optional[datetime] = Field(None, description="Creation timestamp")
    last_updated: Optional[datetime] = Field(None, description="Last modification timestamp")


class BaseCRDSchema(BaseModel):
    """
    Schema for BaseCRD model
    
    Base schema for Kubernetes Custom Resource Definitions.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "example-vpc",
                    "namespace": "default",
                    "spec": {
                        "subnets": ["10.1.0.0/24"],
                        "permit": ["any"]
                    },
                    "raw_spec": {
                        "apiVersion": "vpc.githedgehog.com/v1alpha2",
                        "kind": "VPC",
                        "metadata": {
                            "name": "example-vpc",
                            "namespace": "default"
                        }
                    },
                    "labels": {
                        "environment": "production",
                        "team": "networking"
                    },
                    "annotations": {
                        "managed-by": "netbox-hedgehog"
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )

    # Primary key
    id: Optional[int] = Field(None, description="Database primary key")
    
    # Required relationships
    fabric: int = Field(..., description="HedgehogFabric ID this CRD belongs to")
    
    # Required Kubernetes fields
    name: str = Field(..., max_length=253, description="DNS-1123 compliant resource name")
    spec: Dict[str, Any] = Field(..., description="CRD specification as JSON")
    
    # Optional Kubernetes fields
    namespace: str = Field("default", max_length=253, description="Kubernetes namespace")
    raw_spec: Dict[str, Any] = Field(default_factory=dict, description="Raw spec from YAML")
    labels: Dict[str, str] = Field(default_factory=dict, description="Kubernetes labels")
    annotations: Dict[str, str] = Field(default_factory=dict, description="Kubernetes annotations")
    
    # Status fields
    kubernetes_status: KubernetesStatus = Field(KubernetesStatus.UNKNOWN, description="Current K8s status")
    kubernetes_uid: Optional[str] = Field(None, max_length=36, description="Kubernetes resource UID")
    kubernetes_resource_version: Optional[str] = Field(None, max_length=50, description="K8s resource version")
    
    # Sync tracking
    last_applied: Optional[datetime] = Field(None, description="When CRD was last applied to K8s")
    last_synced: Optional[datetime] = Field(None, description="When CRD was last synced from K8s")
    sync_error: Optional[str] = Field(None, description="Last sync error message")
    
    # Git integration
    git_file_path: Optional[str] = Field(None, max_length=500, description="Path in Git repository")
    auto_sync: bool = Field(True, description="Enable automatic sync")
    
    # Timestamps
    created: Optional[datetime] = Field(None, description="Creation timestamp")
    last_updated: Optional[datetime] = Field(None, description="Last modification timestamp")


# Export schemas for JSON Schema generation
def get_json_schemas() -> Dict[str, Dict[str, Any]]:
    """
    Generate JSON schemas for all core models.
    
    Returns:
        Dictionary mapping model names to their JSON schemas
    """
    return {
        "HedgehogFabric": HedgehogFabricSchema.model_json_schema(),
        "GitRepository": GitRepositorySchema.model_json_schema(),
        "BaseCRD": BaseCRDSchema.model_json_schema(),
    }


# Export example data for testing
def get_example_data() -> Dict[str, Any]:
    """
    Generate example data for all core models.
    
    Returns:
        Dictionary mapping model names to example instances
    """
    return {
        "HedgehogFabric": HedgehogFabricSchema.model_config["json_schema_extra"]["examples"][0],
        "GitRepository": GitRepositorySchema.model_config["json_schema_extra"]["examples"][0],
        "BaseCRD": BaseCRDSchema.model_config["json_schema_extra"]["examples"][0],
    }