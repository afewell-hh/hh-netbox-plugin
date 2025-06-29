import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from ..models import HedgehogFabric

class FabricTable(NetBoxTable):
    """Table for displaying Hedgehog fabrics"""
    
    name = tables.Column(
        linkify=True,
        verbose_name='Name'
    )
    
    status = columns.ChoiceFieldColumn(
        verbose_name='Status'
    )
    
    crd_count = tables.Column(
        accessor='crd_count',
        verbose_name='Total CRDs',
        orderable=False
    )
    
    active_crd_count = tables.Column(
        accessor='active_crd_count', 
        verbose_name='Active CRDs',
        orderable=False
    )
    
    error_crd_count = tables.Column(
        accessor='error_crd_count',
        verbose_name='Error CRDs', 
        orderable=False
    )
    
    last_sync = tables.DateTimeColumn(
        verbose_name='Last Sync'
    )
    
    class Meta(NetBoxTable.Meta):
        model = HedgehogFabric
        fields = (
            'pk', 'id', 'name', 'description', 'status', 
            'crd_count', 'active_crd_count', 'error_crd_count',
            'sync_enabled', 'last_sync', 'created', 'last_updated',
            'actions'
        )
        default_columns = (
            'name', 'description', 'status', 'crd_count', 
            'active_crd_count', 'error_crd_count', 'last_sync'
        )