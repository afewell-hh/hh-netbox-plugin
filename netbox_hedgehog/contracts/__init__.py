"""
NetBox Hedgehog Plugin Contracts

Machine-readable component contracts for all models, services, and APIs.
This module provides:
- Pydantic model schemas for data validation and serialization
- typing.Protocol service interfaces for type safety
- OpenAPI specifications for REST API documentation

These contracts enable agents to understand and interact with the plugin
without reverse-engineering Django models or API implementations.
"""

from .models import *
from .services import *

__version__ = "1.0.0"
__all__ = [
    # Core models
    "HedgehogFabricSchema",
    "GitRepositorySchema", 
    "BaseCRDSchema",
    
    # GitOps models
    "HedgehogResourceSchema",
    "StateTransitionHistorySchema",
    "ReconciliationAlertSchema",
    
    # VPC API models
    "VPCSchema",
    "ExternalSchema",
    "ExternalAttachmentSchema", 
    "ExternalPeeringSchema",
    "IPv4NamespaceSchema",
    "VPCAttachmentSchema",
    "VPCPeeringSchema",
    
    # Wiring API models
    "ConnectionSchema",
    "ServerSchema",
    "SwitchSchema",
    "SwitchGroupSchema",
    "VLANNamespaceSchema",
    
    # Service protocols
    "FabricService",
    "GitRepositoryService",
    "GitOpsService",
    "SyncService",
    "ValidationService",
]