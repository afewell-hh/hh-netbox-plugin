"""
Topology Planning Models for DIET (Design and Implementation Excellence Tools)

These models enable pre-sales topology planning and design workflows.

Reference Data (leverages NetBox core models):
- BreakoutOption: Custom model for breakout math
- DeviceTypeExtension: Hedgehog-specific metadata for NetBox DeviceTypes
- Switch/Server/NIC specs: Use dcim.DeviceType, dcim.ModuleType

Planning Models (to be implemented in future commits):
- TopologyPlan: Container for a topology plan
- PlanServerClass: Server class definition in a plan
- PlanSwitchClass: Switch class definition in a plan
- PlanServerConnection: Server connection definition
- PlanMCLAGDomain: MCLAG domain definition
"""

from .reference_data import (
    BreakoutOption,
    DeviceTypeExtension,
)

__all__ = [
    'BreakoutOption',
    'DeviceTypeExtension',
]
