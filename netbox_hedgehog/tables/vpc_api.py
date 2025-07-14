import django_tables2 as tables
from netbox.tables import NetBoxTable, columns
from django.utils.html import format_html

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
    
    # GitOps columns (MVP2)
    git_status = tables.Column(
        accessor='get_git_status',
        verbose_name='Git Status',
        orderable=False,
        empty_values=()
    )
    
    drift_status = tables.Column(
        accessor='get_drift_status',
        verbose_name='Drift Status',
        orderable=False,
        empty_values=()
    )
    
    def render_git_status(self, record):
        """Render Git status badge"""
        try:
            # Check if this resource has a corresponding HedgehogResource
            from ..models.gitops import HedgehogResource
            gitops_resource = HedgehogResource.objects.filter(
                fabric=record.fabric,
                name=record.name,
                namespace=record.namespace,
                kind='VPC'
            ).first()
            
            if gitops_resource and gitops_resource.has_desired_state:
                return format_html(
                    '<span class="badge bg-success" title="Resource defined in Git"><i class="mdi mdi-git"></i> In Git</span>'
                )
            else:
                return format_html(
                    '<span class="badge bg-secondary" title="Manual resource - not in Git"><i class="mdi mdi-account"></i> Manual</span>'
                )
        except Exception:
            return format_html(
                '<span class="badge bg-light text-dark" title="GitOps status unknown"><i class="mdi mdi-help-circle"></i> Unknown</span>'
            )
    
    def render_drift_status(self, record):
        """Render drift status badge"""
        try:
            # Check if this resource has a corresponding HedgehogResource
            from ..models.gitops import HedgehogResource
            gitops_resource = HedgehogResource.objects.filter(
                fabric=record.fabric,
                name=record.name,
                namespace=record.namespace,
                kind='VPC'
            ).first()
            
            if gitops_resource and gitops_resource.has_desired_state:
                if gitops_resource.has_drift:
                    return format_html(
                        '<span class="badge bg-warning gitops-status-indicator has-drift" title="{}"><i class="mdi mdi-alert-circle"></i> Drift</span>',
                        gitops_resource.get_drift_summary()
                    )
                else:
                    return format_html(
                        '<span class="badge bg-success" title="Resource is in sync with Git"><i class="mdi mdi-check-circle"></i> In Sync</span>'
                    )
            else:
                return format_html(
                    '<span class="badge bg-light text-dark" title="No Git repository configured"><i class="mdi mdi-minus"></i> N/A</span>'
                )
        except Exception:
            return format_html(
                '<span class="badge bg-light text-dark" title="Drift status unknown"><i class="mdi mdi-help-circle"></i> Unknown</span>'
            )
    
    class Meta(NetBoxTable.Meta):
        model = VPC
        fields = (
            'pk', 'id', 'name', 'fabric', 'namespace', 
            'kubernetes_status', 'status_display', 'last_applied',
            'git_status', 'drift_status',
            'last_synced', 'auto_sync', 'created', 'last_updated'
        )
        default_columns = (
            'name', 'fabric', 'namespace', 'status_display', 
            'git_status', 'drift_status', 'last_applied'
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
            'last_synced', 'auto_sync', 'created', 'last_updated'
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
            'last_synced', 'auto_sync', 'created', 'last_updated'
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
            'last_synced', 'auto_sync', 'created', 'last_updated'
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
            'last_synced', 'auto_sync', 'created', 'last_updated'
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
            'last_synced', 'auto_sync', 'created', 'last_updated'
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
            'last_synced', 'auto_sync', 'created', 'last_updated'
        )
        default_columns = (
            'name', 'fabric', 'namespace', 'status_display',
            'last_applied', 'auto_sync'
        )