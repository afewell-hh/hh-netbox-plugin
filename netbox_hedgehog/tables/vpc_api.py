import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from ..models import VPC, External, IPv4Namespace, ExternalAttachment, ExternalPeering, VPCAttachment, VPCPeering

class VPCTable(NetBoxTable):
    """Table for displaying VPCs"""
    
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
    
    last_applied = tables.DateTimeColumn(
        verbose_name='Last Applied'
    )
    
    class Meta(NetBoxTable.Meta):
        model = VPC
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

class ExternalTable(NetBoxTable):
    """Table for displaying External systems"""
    
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
        model = External
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

class IPv4NamespaceTable(NetBoxTable):
    """Table for displaying IPv4 Namespaces"""
    
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
        model = IPv4Namespace
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

class ExternalAttachmentTable(NetBoxTable):
    """Table for displaying External Attachments"""
    
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
        model = ExternalAttachment
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

class ExternalPeeringTable(NetBoxTable):
    """Table for displaying External Peerings"""
    
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
        model = ExternalPeering
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

class VPCAttachmentTable(NetBoxTable):
    """Table for displaying VPC Attachments"""
    
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
        model = VPCAttachment
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

class VPCPeeringTable(NetBoxTable):
    """Table for displaying VPC Peerings"""
    
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
        model = VPCPeering
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