"""
Service Interface Protocols

typing.Protocol definitions for all NetBox Hedgehog Plugin services.
These protocols define:
- CRUD operations for each model
- Sync operations (GitOps, GitHub sync)
- Validation services
- State transition services
"""

from .crud import (
    FabricService, GitRepositoryService, BaseCRDService,
    HedgehogResourceService, StateTransitionHistoryService, ReconciliationAlertService,
    VPCService, ExternalService, ExternalAttachmentService, ExternalPeeringService,
    IPv4NamespaceService, VPCAttachmentService, VPCPeeringService,
    ConnectionService, ServerService, SwitchService, SwitchGroupService, VLANNamespaceService
)
from .gitops import GitOpsService, StateTransitionService, DriftDetectionService
from .sync import KubernetesSyncService, GitSyncService, GitHubSyncService
from .validation import ValidationService, YAMLValidationService, SpecValidationService

__all__ = [
    # CRUD services
    "FabricService",
    "GitRepositoryService",
    "BaseCRDService",
    "HedgehogResourceService",
    "StateTransitionHistoryService",
    "ReconciliationAlertService",
    "VPCService",
    "ExternalService",
    "ExternalAttachmentService",
    "ExternalPeeringService", 
    "IPv4NamespaceService",
    "VPCAttachmentService",
    "VPCPeeringService",
    "ConnectionService",
    "ServerService",
    "SwitchService",
    "SwitchGroupService",
    "VLANNamespaceService",
    
    # GitOps services
    "GitOpsService",
    "StateTransitionService",
    "DriftDetectionService",
    
    # Sync services
    "KubernetesSyncService",
    "GitSyncService",
    "GitHubSyncService",
    
    # Validation services
    "ValidationService",
    "YAMLValidationService",
    "SpecValidationService",
]