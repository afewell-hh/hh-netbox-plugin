"""
Wiring API Model Schemas

Pydantic schemas for Hedgehog Wiring API models:
- Connection: Logical/physical device connections
- Server: Server connection configuration
- Switch: Network switches with roles and configuration
- SwitchGroup: Switch groupings for redundancy
- VLANNamespace: VLAN range management

All Wiring API models inherit from BaseCRD and use api version 'wiring.githedgehog.com/v1beta1'
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, ConfigDict
from .core import BaseCRDSchema


class ConnectionSchema(BaseCRDSchema):
    """
    Schema for Connection model
    
    Defines logical/physical connections between devices.
    Supports multiple connection types: unbundled, bundled, MCLAG, fabric, etc.
    API Version: wiring.githedgehog.com/v1beta1
    Kind: Connection
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "server-01-connection",
                    "namespace": "default",
                    "spec": {
                        "unbundled": {
                            "link": {
                                "server": {
                                    "port": "Ethernet1"
                                },
                                "switch": {
                                    "port": "Ethernet1"
                                }
                            }
                        }
                    },
                    "labels": {
                        "connection-type": "server-access"
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )
    
    def get_api_version(self) -> str:
        return 'wiring.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'Connection'
    
    @property
    def connection_type(self) -> str:
        """Extract connection type from spec"""
        if not self.spec:
            return 'unknown'
        
        connection_types = ['unbundled', 'bundled', 'mclag', 'eslag', 'fabric', 'vpcLoopback', 'external']
        for conn_type in connection_types:
            if conn_type in self.spec:
                return conn_type
        return 'unknown'


class ServerSchema(BaseCRDSchema):
    """
    Schema for Server model
    
    Represents server connection configuration in the fabric.
    API Version: wiring.githedgehog.com/v1beta1
    Kind: Server
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "server-01",
                    "namespace": "default",
                    "spec": {
                        "description": "Production web server",
                        "interfaces": [
                            {
                                "name": "Ethernet1",
                                "ip": "dhcp"
                            }
                        ]
                    },
                    "labels": {
                        "role": "web-server",
                        "environment": "production"
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )
    
    def get_api_version(self) -> str:
        return 'wiring.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'Server'


class SwitchSchema(BaseCRDSchema):
    """
    Schema for Switch model
    
    Represents network switches with configurable roles, redundancy groups, and ports.
    API Version: wiring.githedgehog.com/v1beta1
    Kind: Switch
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "spine-01",
                    "namespace": "default",
                    "spec": {
                        "role": "spine",
                        "asn": 65100,
                        "ip": "10.0.1.1/32",
                        "portGroupSpeeds": [
                            "100G"
                        ],
                        "portSpeeds": [
                            "25G"
                        ],
                        "redundancyGroup": "spine-group"
                    },
                    "labels": {
                        "switch-role": "spine",
                        "tier": "core"
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )
    
    def get_api_version(self) -> str:
        return 'wiring.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'Switch'
    
    @property
    def switch_role(self) -> str:
        """Extract switch role from spec"""
        if not self.spec:
            return 'unknown'
        return self.spec.get('role', 'unknown')
    
    @property
    def asn(self) -> Optional[int]:
        """Extract ASN from spec"""
        if not self.spec:
            return None
        return self.spec.get('asn')


class SwitchGroupSchema(BaseCRDSchema):
    """
    Schema for SwitchGroup model
    
    Groups switches together for redundancy and management purposes.
    API Version: wiring.githedgehog.com/v1beta1
    Kind: SwitchGroup
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "spine-group",
                    "namespace": "default",
                    "spec": {
                        "type": "spine-group",
                        "redundancy": "active-active"
                    },
                    "labels": {
                        "group-type": "spine-redundancy"
                    },
                    "kubernetes_status": "LIVE",
                    "auto_sync": True
                }
            ]
        }
    )
    
    def get_api_version(self) -> str:
        return 'wiring.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'SwitchGroup'
    
    @property
    def group_type(self) -> str:
        """Extract group type from spec"""
        if not self.spec:
            return 'unknown'
        return self.spec.get('type', 'unknown')


class VLANNamespaceSchema(BaseCRDSchema):
    """
    Schema for VLANNamespace model
    
    Manages VLAN ranges and prevents VLAN range overlaps.
    API Version: wiring.githedgehog.com/v1beta1
    Kind: VLANNamespace
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "fabric": 1,
                    "name": "production-vlans",
                    "namespace": "default",
                    "spec": {
                        "ranges": [
                            "100-199",
                            "1000-1099"
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
        return 'wiring.githedgehog.com/v1beta1'
    
    def get_kind(self) -> str:
        return 'VLANNamespace'
    
    @property
    def vlan_ranges(self) -> List[str]:
        """Extract VLAN ranges from spec"""
        if not self.spec:
            return []
        ranges = self.spec.get('ranges', [])
        if isinstance(ranges, list):
            return ranges
        return []


# Export schemas for JSON Schema generation
def get_json_schemas() -> Dict[str, Dict[str, Any]]:
    """
    Generate JSON schemas for all Wiring API models.
    
    Returns:
        Dictionary mapping model names to their JSON schemas
    """
    return {
        "Connection": ConnectionSchema.model_json_schema(),
        "Server": ServerSchema.model_json_schema(),
        "Switch": SwitchSchema.model_json_schema(),
        "SwitchGroup": SwitchGroupSchema.model_json_schema(),
        "VLANNamespace": VLANNamespaceSchema.model_json_schema(),
    }


# Export example data for testing
def get_example_data() -> Dict[str, Any]:
    """
    Generate example data for all Wiring API models.
    
    Returns:
        Dictionary mapping model names to example instances
    """
    return {
        "Connection": ConnectionSchema.model_config["json_schema_extra"]["examples"][0],
        "Server": ServerSchema.model_config["json_schema_extra"]["examples"][0],
        "Switch": SwitchSchema.model_config["json_schema_extra"]["examples"][0],
        "SwitchGroup": SwitchGroupSchema.model_config["json_schema_extra"]["examples"][0],
        "VLANNamespace": VLANNamespaceSchema.model_config["json_schema_extra"]["examples"][0],
    }