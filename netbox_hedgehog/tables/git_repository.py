"""
Git Repository Tables
"""

import django_tables2 as tables
from django_tables2.utils import Accessor
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
    
    fabric_count = tables.Column(
        verbose_name='Fabrics'
    )
    
    last_validated = columns.DateTimeColumn(
        verbose_name='Last Validated'
    )
    
    created_by = tables.Column(
        verbose_name='Owner'
    )
    
    test_connection = tables.TemplateColumn(
        template_code="""
        <form method="post" action="{% url 'plugins:netbox_hedgehog:git_repository_test_connection' pk=record.pk %}" style="display: inline;">
            {% csrf_token %}
            <button type="submit" class="btn btn-sm btn-outline-primary" title="Test Connection">
                <i class="mdi mdi-connection"></i>
            </button>
        </form>
        """,
        verbose_name='',
        orderable=False
    )
    
    class Meta(NetBoxTable.Meta):
        model = GitRepository
        fields = (
            'pk', 'id', 'name', 'url', 'provider', 'authentication_type',
            'connection_status', 'fabric_count', 'last_validated', 'created_by',
            'test_connection', 'tags', 'created', 'last_updated'
        )
        default_columns = (
            'name', 'url', 'provider', 'authentication_type', 'connection_status',
            'fabric_count', 'last_validated', 'test_connection'
        )