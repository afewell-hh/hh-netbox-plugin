import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from ..models import Connection, Switch, Server, SwitchGroup, VLANNamespace

class ConnectionTable(NetBoxTable):
    """Table for displaying Connections"""
    
    name = tables.Column(
        linkify=True,
        verbose_name='Name'
    )
    
    fabric = tables.Column(
        linkify=True,
        verbose_name='Fabric'
    )
    
    namespace = tables.Column(
        verbose_name='Namespace'
    )
    
    connection_type = tables.Column(
        accessor='connection_type',
        verbose_name='Type',
        orderable=False
    )
    
    kubernetes_status = columns.ChoiceFieldColumn(
        verbose_name='K8s Status'
    )
    
    status_display = tables.Column(
        accessor='status_display',
        verbose_name='Status',
        orderable=False
    )
    
    class Meta(NetBoxTable.Meta):
        model = Connection
        fields = (
            'pk', 'id', 'name', 'fabric', 'namespace', 'connection_type',
            'kubernetes_status', 'status_display', 'last_applied',
            'last_synced', 'auto_sync', 'created', 'last_updated',
            'actions'
        )
        default_columns = (
            'name', 'fabric', 'namespace', 'connection_type', 
            'status_display', 'last_applied'
        )

class SwitchTable(NetBoxTable):
    """Table for displaying Switches"""
    
    name = tables.Column(
        linkify=True,
        verbose_name='Name'
    )
    
    fabric = tables.Column(
        linkify=True,
        verbose_name='Fabric'
    )
    
    namespace = tables.Column(
        verbose_name='Namespace'
    )
    
    switch_role = tables.Column(
        accessor='switch_role',
        verbose_name='Role',
        orderable=False
    )
    
    asn = tables.Column(
        accessor='asn',
        verbose_name='ASN',
        orderable=False
    )
    
    kubernetes_status = columns.ChoiceFieldColumn(
        verbose_name='K8s Status'
    )
    
    status_display = tables.Column(
        accessor='status_display',
        verbose_name='Status',
        orderable=False
    )
    
    class Meta(NetBoxTable.Meta):
        model = Switch
        fields = (
            'pk', 'id', 'name', 'fabric', 'namespace', 'switch_role', 'asn',
            'kubernetes_status', 'status_display', 'last_applied',
            'last_synced', 'auto_sync', 'created', 'last_updated',
            'actions'
        )
        default_columns = (
            'name', 'fabric', 'namespace', 'switch_role', 'asn',
            'status_display', 'last_applied'
        )

class ServerTable(NetBoxTable):
    """Table for displaying Servers"""
    
    name = tables.Column(
        linkify=True,
        verbose_name='Name'
    )
    
    fabric = tables.Column(
        linkify=True,
        verbose_name='Fabric'
    )
    
    namespace = tables.Column(
        verbose_name='Namespace'
    )
    
    kubernetes_status = columns.ChoiceFieldColumn(
        verbose_name='K8s Status'
    )
    
    status_display = tables.Column(
        accessor='status_display',
        verbose_name='Status',
        orderable=False
    )
    
    class Meta(NetBoxTable.Meta):
        model = Server
        fields = (
            'pk', 'id', 'name', 'fabric', 'namespace',
            'kubernetes_status', 'status_display', 'last_applied',
            'last_synced', 'auto_sync', 'created', 'last_updated',
            'actions'
        )
        default_columns = (
            'name', 'fabric', 'namespace', 'status_display',
            'last_applied', 'auto_sync'
        )

class SwitchGroupTable(NetBoxTable):
    """Table for displaying Switch Groups"""
    
    name = tables.Column(
        linkify=True,
        verbose_name='Name'
    )
    
    fabric = tables.Column(
        linkify=True,
        verbose_name='Fabric'
    )
    
    namespace = tables.Column(
        verbose_name='Namespace'
    )
    
    kubernetes_status = columns.ChoiceFieldColumn(
        verbose_name='K8s Status'
    )
    
    status_display = tables.Column(
        accessor='status_display',
        verbose_name='Status',
        orderable=False
    )
    
    class Meta(NetBoxTable.Meta):
        model = SwitchGroup
        fields = (
            'pk', 'id', 'name', 'fabric', 'namespace',
            'kubernetes_status', 'status_display', 'last_applied',
            'last_synced', 'auto_sync', 'created', 'last_updated',
            'actions'
        )
        default_columns = (
            'name', 'fabric', 'namespace', 'status_display',
            'last_applied', 'auto_sync'
        )

class VLANNamespaceTable(NetBoxTable):
    """Table for displaying VLAN Namespaces"""
    
    name = tables.Column(
        linkify=True,
        verbose_name='Name'
    )
    
    fabric = tables.Column(
        linkify=True,
        verbose_name='Fabric'
    )
    
    namespace = tables.Column(
        verbose_name='Namespace'
    )
    
    kubernetes_status = columns.ChoiceFieldColumn(
        verbose_name='K8s Status'
    )
    
    status_display = tables.Column(
        accessor='status_display',
        verbose_name='Status',
        orderable=False
    )
    
    class Meta(NetBoxTable.Meta):
        model = VLANNamespace
        fields = (
            'pk', 'id', 'name', 'fabric', 'namespace',
            'kubernetes_status', 'status_display', 'last_applied',
            'last_synced', 'auto_sync', 'created', 'last_updated',
            'actions'
        )
        default_columns = (
            'name', 'fabric', 'namespace', 'status_display',
            'last_applied', 'auto_sync'
        )