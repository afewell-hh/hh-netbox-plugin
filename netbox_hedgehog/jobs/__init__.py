"""
NetBox Jobs for hh-netbox-plugin.

Background job implementations for long-running operations.
"""

from .device_generation import DeviceGenerationJob

__all__ = ['DeviceGenerationJob']
