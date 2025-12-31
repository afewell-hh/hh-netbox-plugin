"""
NetBox Hedgehog Plugin Models

Operational Models (CRD management):
- Connection, Server, Switch, etc. - Manage Hedgehog fabric CRDs

DIET Planning Models (topology planning):
- BreakoutOption - Breakout configurations
- DeviceTypeExtension - Hedgehog-specific metadata for NetBox DeviceTypes
- (Future: TopologyPlan, PlanServerClass, PlanSwitchClass, etc.)

Note: Switch/Server/NIC reference data now uses NetBox core models:
- Switch specs → dcim.DeviceType
- Server specs → dcim.DeviceType
- NIC specs → dcim.ModuleType
- Port specs → dcim.InterfaceTemplate
"""

# Operational CRD Models (existing structure)
from .fabric import HedgehogFabric
from .base import BaseCRD
from .vpc_api import (
    VPC, External, ExternalAttachment, ExternalPeering,
    IPv4Namespace, VPCAttachment, VPCPeering
)
from .wiring_api import (
    Connection, Server, Switch, SwitchGroup, VLANNamespace
)

# DIET Topology Planning Models (refactored to use NetBox core models)
from .topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    PlanMCLAGDomain,
    SwitchPortZone,
    GenerationState,
)

__all__ = [
    # Base
    'HedgehogFabric',
    'BaseCRD',
    # VPC API
    'VPC',
    'External',
    'ExternalAttachment',
    'ExternalPeering',
    'IPv4Namespace',
    'VPCAttachment',
    'VPCPeering',
    # Wiring API
    'Connection',
    'Server',
    'Switch',
    'SwitchGroup',
    'VLANNamespace',
    # DIET Planning Models
    'BreakoutOption',
    'DeviceTypeExtension',
    'TopologyPlan',
    'PlanServerClass',
    'PlanSwitchClass',
    'PlanServerConnection',
    'PlanMCLAGDomain',
    'SwitchPortZone',
    'GenerationState',
]
