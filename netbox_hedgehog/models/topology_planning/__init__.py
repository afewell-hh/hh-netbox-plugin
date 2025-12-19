"""
Topology Planning Models

This module contains models for DIET (Design and Implementation Excellence Tools)
topology planning functionality. These models are separate from operational CRD
models and are used for design-time planning.

Reference Data Layer:
- SwitchModel: Physical switch specifications
- SwitchPortGroup: Port groups on switches with breakout capabilities
- NICModel: Server NIC specifications
- BreakoutOption: Breakout configurations for port speeds
"""

from .reference_data import (
    SwitchModel,
    SwitchPortGroup,
    NICModel,
    BreakoutOption,
)

__all__ = [
    'SwitchModel',
    'SwitchPortGroup',
    'NICModel',
    'BreakoutOption',
]
