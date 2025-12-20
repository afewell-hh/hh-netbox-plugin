"""
Topology Planning Tables (DIET Module)
Tables for displaying BreakoutOption and DeviceTypeExtension models.
"""

import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from ..models.topology_planning import BreakoutOption, DeviceTypeExtension


class BreakoutOptionTable(NetBoxTable):
    """
    Table for displaying BreakoutOptions.

    Shows breakout configurations with port counts and speeds.
    """

    breakout_id = tables.Column(
        linkify=True,
        verbose_name='Breakout ID'
    )

    from_speed = tables.Column(
        verbose_name='Native Speed (Gbps)'
    )

    logical_ports = tables.Column(
        verbose_name='Logical Ports'
    )

    logical_speed = tables.Column(
        verbose_name='Port Speed (Gbps)'
    )

    optic_type = tables.Column(
        verbose_name='Optic Type'
    )

    class Meta(NetBoxTable.Meta):
        model = BreakoutOption
        fields = (
            'pk', 'id', 'breakout_id', 'from_speed', 'logical_ports',
            'logical_speed', 'optic_type', 'tags', 'created', 'last_updated'
        )
        default_columns = (
            'breakout_id', 'from_speed', 'logical_ports', 'logical_speed', 'optic_type'
        )


class DeviceTypeExtensionTable(NetBoxTable):
    """
    Table for displaying DeviceTypeExtensions.

    Shows Hedgehog-specific metadata for NetBox DeviceTypes.
    """

    device_type = tables.Column(
        linkify=True,
        verbose_name='Device Type'
    )

    mclag_capable = tables.BooleanColumn(
        verbose_name='MCLAG'
    )

    hedgehog_roles = tables.Column(
        verbose_name='Hedgehog Roles',
        orderable=False
    )

    native_speed = tables.Column(
        verbose_name='Native Speed (Gbps)'
    )

    uplink_ports = tables.Column(
        verbose_name='Uplink Ports'
    )

    supported_breakouts = tables.Column(
        verbose_name='Supported Breakouts',
        orderable=False
    )

    class Meta(NetBoxTable.Meta):
        model = DeviceTypeExtension
        fields = (
            'pk', 'id', 'device_type', 'mclag_capable', 'hedgehog_roles',
            'native_speed', 'uplink_ports', 'supported_breakouts',
            'tags', 'created', 'last_updated'
        )
        default_columns = (
            'device_type', 'mclag_capable', 'hedgehog_roles', 'native_speed', 'uplink_ports'
        )
