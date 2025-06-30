# Legacy views (for compatibility)
from .fabric import (
    FabricListView as LegacyFabricListView, 
    FabricView as LegacyFabricView, 
    FabricEditView as LegacyFabricEditView, 
    FabricDeleteView as LegacyFabricDeleteView
)
from .catalog import CRDCatalogView, SyncAllView
from .vpc_api import (
    VPCListView as LegacyVPCListView, 
    VPCView as LegacyVPCView, 
    VPCEditView as LegacyVPCEditView, 
    VPCDeleteView as LegacyVPCDeleteView,
    ExternalListView, ExternalView, ExternalEditView, ExternalDeleteView,
    IPv4NamespaceListView, IPv4NamespaceView, IPv4NamespaceEditView, IPv4NamespaceDeleteView,
)
from .wiring_api import (
    ConnectionListView as LegacyConnectionListView, 
    ConnectionView as LegacyConnectionView, 
    ConnectionEditView as LegacyConnectionEditView, 
    ConnectionDeleteView as LegacyConnectionDeleteView,
    SwitchListView as LegacySwitchListView, 
    SwitchView as LegacySwitchView, 
    SwitchEditView as LegacySwitchEditView, 
    SwitchDeleteView as LegacySwitchDeleteView,
    ServerListView, ServerView, ServerEditView, ServerDeleteView,
)

# Enhanced views (Phase 4 UI development)
from .fabric_views import (
    FabricOverviewView,
    FabricDetailView,
    FabricTestConnectionView,
    FabricSyncView,
    FabricOnboardingView,
    FabricListView,
    FabricCreateView,
    FabricEditView,
    FabricDeleteView,
)

from .vpc_views import (
    VPCListView,
    VPCDetailView,
    VPCCreateView,
    VPCApplyView,
    VPCDeleteView,
    VPCBulkActionsView,
)

from .wiring_views import (
    SwitchListView,
    SwitchDetailView,
    ConnectionListView,
    ConnectionDetailView,
    TopologyView,
    VLANNamespaceListView,
    VLANNamespaceDetailView,
)

__all__ = [
    # Enhanced fabric views (Phase 4)
    'FabricOverviewView',
    'FabricDetailView',
    'FabricTestConnectionView',
    'FabricSyncView',
    'FabricOnboardingView',
    'FabricListView',
    'FabricCreateView',
    'FabricEditView',
    'FabricDeleteView',
    
    # Enhanced VPC views (Phase 4)
    'VPCListView',
    'VPCDetailView',
    'VPCCreateView',
    'VPCApplyView',
    'VPCDeleteView',
    'VPCBulkActionsView',
    
    # Enhanced wiring views (Phase 4)
    'SwitchListView',
    'SwitchDetailView',
    'ConnectionListView',
    'ConnectionDetailView',
    'TopologyView',
    'VLANNamespaceListView',
    'VLANNamespaceDetailView',
    
    # Legacy views (for compatibility)
    'LegacyFabricListView', 'LegacyFabricView', 'LegacyFabricEditView', 'LegacyFabricDeleteView',
    'CRDCatalogView', 'SyncAllView',
    'LegacyVPCListView', 'LegacyVPCView', 'LegacyVPCEditView', 'LegacyVPCDeleteView',
    'ExternalListView', 'ExternalView', 'ExternalEditView', 'ExternalDeleteView',
    'IPv4NamespaceListView', 'IPv4NamespaceView', 'IPv4NamespaceEditView', 'IPv4NamespaceDeleteView',
    'LegacyConnectionListView', 'LegacyConnectionView', 'LegacyConnectionEditView', 'LegacyConnectionDeleteView',
    'LegacySwitchListView', 'LegacySwitchView', 'LegacySwitchEditView', 'LegacySwitchDeleteView',
    'ServerListView', 'ServerView', 'ServerEditView', 'ServerDeleteView',
]