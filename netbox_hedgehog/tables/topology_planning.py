"""
Topology Planning Tables (DIET Module)
Tables for displaying BreakoutOption and DeviceTypeExtension models.
"""

import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from ..models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    TopologyPlan,
    PlanServerClass,
    PlanSwitchClass,
    PlanServerConnection,
    SwitchPortZone,
)


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


# =============================================================================
# Topology Plan Tables (DIET-004)
# =============================================================================

class TopologyPlanTable(NetBoxTable):
    """
    Table for displaying TopologyPlans.

    Shows plan name, customer, status, and metadata with links to detail view.
    """

    name = tables.Column(
        linkify=True,
        verbose_name='Plan Name'
    )

    customer_name = tables.Column(
        verbose_name='Customer'
    )

    status = tables.Column(
        verbose_name='Status'
    )

    created_by = tables.Column(
        verbose_name='Created By',
        accessor='created_by__username',
        orderable=False
    )

    # Computed properties from model
    total_servers = tables.Column(
        verbose_name='Servers',
        accessor='pk',
        orderable=False,
        empty_values=()
    )

    total_switches = tables.Column(
        verbose_name='Switches',
        accessor='pk',
        orderable=False,
        empty_values=()
    )

    def render_total_servers(self, record):
        """Render total server count from plan property"""
        return sum(sc.quantity for sc in record.server_classes.all())

    def render_total_switches(self, record):
        """Render total switch count from plan property"""
        return sum(sc.effective_quantity for sc in record.switch_classes.all())

    class Meta(NetBoxTable.Meta):
        model = TopologyPlan
        fields = (
            'pk', 'id', 'name', 'customer_name', 'status', 'created_by',
            'total_servers', 'total_switches', 'description',
            'tags', 'created', 'last_updated'
        )
        default_columns = (
            'name', 'customer_name', 'status', 'total_servers', 'total_switches', 'created_by'
        )


class PlanServerClassTable(NetBoxTable):
    """
    Table for displaying PlanServerClasses.

    Shows server class details including quantities and GPU counts.
    """

    server_class_id = tables.Column(
        linkify=True,
        verbose_name='Server Class ID'
    )

    plan = tables.Column(
        linkify=True,
        verbose_name='Plan'
    )

    category = tables.Column(
        verbose_name='Category'
    )

    quantity = tables.Column(
        verbose_name='Quantity'
    )

    gpus_per_server = tables.Column(
        verbose_name='GPUs/Server'
    )

    total_gpus = tables.Column(
        verbose_name='Total GPUs',
        accessor='pk',
        orderable=False,
        empty_values=()
    )

    def render_total_gpus(self, record):
        """Render total GPU count (quantity × gpus_per_server)"""
        return record.quantity * record.gpus_per_server

    server_device_type = tables.Column(
        linkify=True,
        verbose_name='Device Type',
        accessor='server_device_type'
    )

    class Meta(NetBoxTable.Meta):
        model = PlanServerClass
        fields = (
            'pk', 'id', 'server_class_id', 'plan', 'description', 'category',
            'quantity', 'gpus_per_server', 'total_gpus', 'server_device_type',
            'tags', 'created', 'last_updated'
        )
        default_columns = (
            'server_class_id', 'plan', 'category', 'quantity', 'gpus_per_server', 'total_gpus'
        )


class PlanSwitchClassTable(NetBoxTable):
    """
    Table for displaying PlanSwitchClasses.

    Shows switch class details with calculated vs override vs effective quantities.
    """

    switch_class_id = tables.Column(
        linkify=True,
        verbose_name='Switch Class ID'
    )

    plan = tables.Column(
        linkify=True,
        verbose_name='Plan'
    )

    fabric = tables.Column(
        verbose_name='Fabric'
    )

    hedgehog_role = tables.Column(
        verbose_name='Role'
    )

    device_type_extension = tables.Column(
        verbose_name='Device Type',
        accessor='device_type_extension__device_type',
        linkify=lambda record: record.device_type_extension.device_type.get_absolute_url()
            if record.device_type_extension and record.device_type_extension.device_type else None
    )

    calculated_quantity = tables.Column(
        verbose_name='Calculated'
    )

    override_quantity = tables.Column(
        verbose_name='Override'
    )

    effective_quantity = tables.Column(
        verbose_name='Effective',
        accessor='pk',
        orderable=False,
        empty_values=()
    )

    def render_effective_quantity(self, record):
        """Render effective quantity (override ?? calculated)"""
        return record.effective_quantity

    mclag_pair = tables.BooleanColumn(
        verbose_name='MCLAG Pair'
    )

    class Meta(NetBoxTable.Meta):
        model = PlanSwitchClass
        fields = (
            'pk', 'id', 'switch_class_id', 'plan', 'fabric', 'hedgehog_role',
            'device_type_extension', 'calculated_quantity', 'override_quantity',
            'effective_quantity', 'mclag_pair', 'uplink_ports_per_switch',
            'tags', 'created', 'last_updated'
        )
        default_columns = (
            'switch_class_id', 'plan', 'fabric', 'hedgehog_role',
            'calculated_quantity', 'override_quantity', 'effective_quantity'
        )


# =============================================================================
# PlanServerConnection Table (DIET-005)
# =============================================================================

class PlanServerConnectionTable(NetBoxTable):
    """
    Table for displaying PlanServerConnections.

    Shows server connection details including distribution, target switch,
    speed, and rail assignment.
    """

    connection_id = tables.Column(
        linkify=True,
        verbose_name='Connection ID'
    )

    server_class = tables.Column(
        linkify=True,
        verbose_name='Server Class',
        accessor='server_class'
    )

    target_switch_class = tables.Column(
        linkify=True,
        verbose_name='Target Switch Class',
        accessor='target_switch_class'
    )

    hedgehog_conn_type = tables.Column(
        verbose_name='Connection Type'
    )

    distribution = tables.Column(
        verbose_name='Distribution'
    )

    ports_per_connection = tables.Column(
        verbose_name='Ports'
    )

    speed = tables.Column(
        verbose_name='Speed (Gbps)'
    )

    rail = tables.Column(
        verbose_name='Rail'
    )

    port_type = tables.Column(
        verbose_name='Port Type'
    )

    class Meta(NetBoxTable.Meta):
        model = PlanServerConnection
        fields = (
            'pk', 'id', 'connection_id', 'server_class', 'connection_name',
            'nic_slot', 'ports_per_connection', 'hedgehog_conn_type',
            'distribution', 'target_switch_class', 'speed', 'rail',
            'port_type', 'tags', 'created', 'last_updated'
        )
        default_columns = (
            'connection_id', 'server_class', 'hedgehog_conn_type',
            'distribution', 'target_switch_class', 'ports_per_connection', 'speed', 'rail'
        )


# =============================================================================
# SwitchPortZone Table (DIET-011)
# =============================================================================

class SwitchPortZoneTable(NetBoxTable):
    """
    Table for displaying SwitchPortZones.
    """

    zone_name = tables.Column(
        linkify=True,
        verbose_name='Zone Name'
    )

    switch_class = tables.Column(
        linkify=True,
        verbose_name='Switch Class'
    )

    zone_type = tables.Column(
        verbose_name='Zone Type'
    )

    port_spec = tables.Column(
        verbose_name='Port Spec'
    )

    breakout_option = tables.Column(
        verbose_name='Breakout'
    )

    allocation_strategy = tables.Column(
        verbose_name='Strategy'
    )

    priority = tables.Column(
        verbose_name='Priority'
    )

    class Meta(NetBoxTable.Meta):
        model = SwitchPortZone
        fields = (
            'pk', 'id', 'zone_name', 'switch_class', 'zone_type', 'port_spec',
            'breakout_option', 'allocation_strategy', 'priority', 'tags',
            'created', 'last_updated'
        )
        default_columns = (
            'zone_name', 'switch_class', 'zone_type', 'port_spec',
            'breakout_option', 'allocation_strategy', 'priority'
        )
