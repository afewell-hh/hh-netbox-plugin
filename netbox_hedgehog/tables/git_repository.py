"""
Git Repository Tables
"""

import django_tables2 as tables
from netbox.tables import NetBoxTable, ChoiceFieldColumn, columns
from ..models import GitRepository


class GitRepositoryTable(NetBoxTable):
    """Table for displaying Git repositories"""
    
    name = tables.Column(
        linkify=True
    )
    
    url = tables.Column(
        verbose_name='Repository URL'
    )
    
    provider = ChoiceFieldColumn()
    
    authentication_type = ChoiceFieldColumn(
        verbose_name='Auth Type'
    )
    
    connection_status = ChoiceFieldColumn(
        verbose_name='Connection'
    )
    
    last_validated = columns.DateTimeColumn(
        verbose_name='Last Validated'
    )
    
    created_by = tables.Column(
        verbose_name='Owner'
    )
    
    class Meta(NetBoxTable.Meta):
        model = GitRepository
        fields = (
            'pk', 'id', 'name', 'url', 'provider', 'authentication_type',
            'connection_status', 'last_validated', 'created_by',
            'tags', 'created', 'last_updated'
        )
        default_columns = (
            'name', 'url', 'provider', 'authentication_type', 'connection_status',
            'last_validated', 'created_by'
        )