"""
VPC API Model Schemas

Pydantic schemas for Hedgehog VPC API models:
- VPC: Virtual Private Cloud network isolation
- External: External systems connected to fabric  
- ExternalAttachment: Attachments of external systems to switches
- ExternalPeering: Peering between VPCs and external systems
- IPv4Namespace: IPv4 address namespace management
- VPCAttachment: Workload attachments to VPCs
- VPCPeering: Peering between different VPCs

All VPC API models inherit from BaseCRD and use api version 'vpc.githedgehog.com/v1beta1'
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from .core import BaseCRDSchema


class VPCSchema(BaseCRDSchema):
    """
    Schema for VPC model
    
    Represents a Hedgehog Virtual Private Cloud for network isolation.
    API Version: vpc.githedgehog.com/v1beta1
    Kind: VPC
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "production-vpc",
                    "namespace": "default",
                    "spec": {
                        "subnets": [
                            "10.1.0.0/16",
                            "192.168.100.0/24"
                        ],
                        "permit": [
                            "any"
                        ],
                        "vlanNamespace": "default"
                    },
                    "labels": {
                        "environment": "production",
                        "team": "platform"
                    },
                    "annotations": {
                        "description": "Production VPC for main workloads"
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )
    
    # VPC-specific computed properties from spec
    def get_api_version(self) -> str:
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'VPC'


class ExternalSchema(BaseCRDSchema):
    """
    Schema for External model
    
    Represents external systems connected to the Hedgehog fabric.
    API Version: vpc.githedgehog.com/v1beta1
    Kind: External
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "upstream-provider",
                    "namespace": "default",
                    "spec": {
                        "inbound": [
                            "0.0.0.0/0"
                        ],
                        "outbound": [
                            "10.0.0.0/8"
                        ]
                    },
                    "labels": {
                        "provider": "upstream-isp"
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )
    
    def get_api_version(self) -> str:
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'External'


class ExternalAttachmentSchema(BaseCRDSchema):
    """
    Schema for ExternalAttachment model
    
    Attaches external systems to fabric switches.
    API Version: vpc.githedgehog.com/v1beta1
    Kind: ExternalAttachment
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "upstream-attachment",
                    "namespace": "default",
                    "spec": {
                        "external": "upstream-provider",
                        "connection": "border-connection"
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )
    
    def get_api_version(self) -> str:
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'ExternalAttachment'


class ExternalPeeringSchema(BaseCRDSchema):
    """
    Schema for ExternalPeering model
    
    Enables peering between VPCs and external systems.
    API Version: vpc.githedgehog.com/v1beta1
    Kind: ExternalPeering
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "vpc-upstream-peering",
                    "namespace": "default",
                    "spec": {
                        "permit": {
                            "vpc": {
                                "name": "production-vpc"
                            },
                            "external": {
                                "name": "upstream-provider"
                            }
                        }
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )
    
    def get_api_version(self) -> str:
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'ExternalPeering'


class IPv4NamespaceSchema(BaseCRDSchema):
    """
    Schema for IPv4Namespace model
    
    Manages IPv4 address namespaces for network isolation.
    API Version: vpc.githedgehog.com/v1beta1
    Kind: IPv4Namespace
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "production-ipv4",
                    "namespace": "default",
                    "spec": {
                        "subnets": [
                            "10.0.0.0/8",
                            "192.168.0.0/16"
                        ]
                    },
                    "labels": {
                        "environment": "production"
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )
    
    def get_api_version(self) -> str:
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'IPv4Namespace'


class VPCAttachmentSchema(BaseCRDSchema):
    """
    Schema for VPCAttachment model
    
    Attaches workloads to VPCs.
    API Version: vpc.githedgehog.com/v1beta1
    Kind: VPCAttachment
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "server-vpc-attachment",
                    "namespace": "default",
                    "spec": {
                        "vpc": "production-vpc",
                        "connection": "server-01"
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )
    
    def get_api_version(self) -> str:
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'VPCAttachment'


class VPCPeeringSchema(BaseCRDSchema):
    """
    Schema for VPCPeering model
    
    Enables peering between different VPCs.
    API Version: vpc.githedgehog.com/v1beta1
    Kind: VPCPeering
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "prod-dev-peering",
                    "namespace": "default",
                    "spec": {
                        "permit": {
                            "vpc1": {
                                "name": "production-vpc"
                            },
                            "vpc2": {
                                "name": "development-vpc"
                            }
                        }
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )
    
    def get_api_version(self) -> str:
        return 'vpc.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'VPCPeering'


# Export schemas for JSON Schema generation
def get_json_schemas() -> Dict[str, Dict[str, Any]]:
    """
    Generate JSON schemas for all VPC API models.
    
    Returns:
        Dictionary mapping model names to their JSON schemas
    """
    return {
        "VPC": VPCSchema.model_json_schema(),
        "External": ExternalSchema.model_json_schema(),
        "ExternalAttachment": ExternalAttachmentSchema.model_json_schema(),
        "ExternalPeering": ExternalPeeringSchema.model_json_schema(),
        "IPv4Namespace": IPv4NamespaceSchema.model_json_schema(),
        "VPCAttachment": VPCAttachmentSchema.model_json_schema(),
        "VPCPeering": VPCPeeringSchema.model_json_schema(),
    }


# Export example data for testing
def get_example_data() -> Dict[str, Any]:
    """
    Generate example data for all VPC API models.
    
    Returns:
        Dictionary mapping model names to example instances
    """
    return {
        "VPC": VPCSchema.model_config["json_schema_extra"]["examples"][0],
        "External": ExternalSchema.model_config["json_schema_extra"]["examples"][0],
        "ExternalAttachment": ExternalAttachmentSchema.model_config["json_schema_extra"]["examples"][0],
        "ExternalPeering": ExternalPeeringSchema.model_config["json_schema_extra"]["examples"][0],
        "IPv4Namespace": IPv4NamespaceSchema.model_config["json_schema_extra"]["examples"][0],
        "VPCAttachment": VPCAttachmentSchema.model_config["json_schema_extra"]["examples"][0],
        "VPCPeering": VPCPeeringSchema.model_config["json_schema_extra"]["examples"][0],
    }