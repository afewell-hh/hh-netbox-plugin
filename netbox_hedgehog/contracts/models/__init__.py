"""
Pydantic Model Schemas

Machine-readable schemas for all NetBox Hedgehog Plugin models.
Each schema provides:
- Complete field definitions with types and validation
- Relationship specifications
- JSON schema export capability
- Example data for testing
"""

from .core import HedgehogFabricSchema, GitRepositorySchema, BaseCRDSchema
from .gitops import HedgehogResourceSchema, StateTransitionHistorySchema, ReconciliationAlertSchema
from .vpc_api import (
    VPCSchema, ExternalSchema, ExternalAttachmentSchema, ExternalPeeringSchema,
    IPv4NamespaceSchema, VPCAttachmentSchema, VPCPeeringSchema
)
from .wiring_api import ConnectionSchema, ServerSchema, SwitchSchema, SwitchGroupSchema, VLANNamespaceSchema

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
]