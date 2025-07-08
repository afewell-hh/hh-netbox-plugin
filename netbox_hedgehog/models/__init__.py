from .fabric import HedgehogFabric
from .base import BaseCRD
from .gitops import HedgehogResource
from .vpc_api import (
    VPC, External, ExternalAttachment, ExternalPeering,
    IPv4Namespace, VPCAttachment, VPCPeering
)
from .wiring_api import (
    Connection, Server, Switch, SwitchGroup, VLANNamespace
)

__all__ = [
    'HedgehogFabric',
    'BaseCRD',
    'HedgehogResource',
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
]