from .fabric import (
    FabricListView, FabricView, FabricEditView, FabricDeleteView
)
from .catalog import CRDCatalogView, SyncAllView
from .vpc_api import (
    VPCListView, VPCView, VPCEditView, VPCDeleteView,
    ExternalListView, ExternalView, ExternalEditView, ExternalDeleteView,
    IPv4NamespaceListView, IPv4NamespaceView, IPv4NamespaceEditView, IPv4NamespaceDeleteView,
)
from .wiring_api import (
    ConnectionListView, ConnectionView, ConnectionEditView, ConnectionDeleteView,
    SwitchListView, SwitchView, SwitchEditView, SwitchDeleteView,
    ServerListView, ServerView, ServerEditView, ServerDeleteView,
)

__all__ = [
    # Fabric views
    'FabricListView', 'FabricView', 'FabricEditView', 'FabricDeleteView',
    # Catalog views
    'CRDCatalogView', 'SyncAllView',
    # VPC API views
    'VPCListView', 'VPCView', 'VPCEditView', 'VPCDeleteView',
    'ExternalListView', 'ExternalView', 'ExternalEditView', 'ExternalDeleteView',
    'IPv4NamespaceListView', 'IPv4NamespaceView', 'IPv4NamespaceEditView', 'IPv4NamespaceDeleteView',
    # Wiring API views
    'ConnectionListView', 'ConnectionView', 'ConnectionEditView', 'ConnectionDeleteView',
    'SwitchListView', 'SwitchView', 'SwitchEditView', 'SwitchDeleteView',
    'ServerListView', 'ServerView', 'ServerEditView', 'ServerDeleteView',
]