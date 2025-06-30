from django.urls import path

from . import views

app_name = 'netbox_hedgehog'

urlpatterns = [
    # Main dashboard
    path('', views.FabricOverviewView.as_view(), name='overview'),
    
    # Fabric management
    path('fabrics/', views.FabricListView.as_view(), name='fabric_list'),
    path('fabrics/add/', views.FabricCreateView.as_view(), name='fabric_add'),
    path('fabrics/<int:pk>/', views.FabricDetailView.as_view(), name='fabric_detail'),
    path('fabrics/<int:pk>/edit/', views.FabricEditView.as_view(), name='fabric_edit'),
    path('fabrics/<int:pk>/delete/', views.FabricDeleteView.as_view(), name='fabric_delete'),
    path('fabrics/<int:pk>/test-connection/', views.FabricTestConnectionView.as_view(), name='fabric_test_connection'),
    path('fabrics/<int:pk>/sync/', views.FabricSyncView.as_view(), name='fabric_sync'),
    path('fabrics/<int:pk>/onboard/', views.FabricOnboardingView.as_view(), name='fabric_onboarding'),
    path('fabrics/bulk-actions/', views.FabricBulkActionsView.as_view(), name='fabric_bulk_actions'),
    
    # VPC management
    path('vpcs/', views.VPCListView.as_view(), name='vpc_list'),
    path('vpcs/create/', views.VPCCreateView.as_view(), name='vpc_create'),
    path('vpcs/<int:pk>/', views.VPCDetailView.as_view(), name='vpc_detail'),
    path('vpcs/<int:pk>/apply/', views.VPCApplyView.as_view(), name='vpc_apply'),
    path('vpcs/<int:pk>/delete/', views.VPCDeleteView.as_view(), name='vpc_delete'),
    path('vpcs/bulk-actions/', views.VPCBulkActionsView.as_view(), name='vpc_bulk_actions'),
    
    # Switch management
    path('switches/', views.SwitchListView.as_view(), name='switch_list'),
    path('switches/add/', views.SwitchCreateView.as_view(), name='switch_add'),
    path('switches/<int:pk>/', views.SwitchDetailView.as_view(), name='switch_detail'),
    path('switches/<int:pk>/edit/', views.SwitchEditView.as_view(), name='switch_edit'),
    path('switches/<int:pk>/delete/', views.SwitchDeleteView.as_view(), name='switch_delete'),
    path('switches/bulk-actions/', views.SwitchBulkActionsView.as_view(), name='switch_bulk_actions'),
    
    # Connection management
    path('connections/', views.ConnectionListView.as_view(), name='connection_list'),
    path('connections/add/', views.ConnectionCreateView.as_view(), name='connection_add'),
    path('connections/<int:pk>/', views.ConnectionDetailView.as_view(), name='connection_detail'),
    path('connections/<int:pk>/edit/', views.ConnectionEditView.as_view(), name='connection_edit'),
    path('connections/<int:pk>/delete/', views.ConnectionDeleteView.as_view(), name='connection_delete'),
    path('connections/bulk-actions/', views.ConnectionBulkActionsView.as_view(), name='connection_bulk_actions'),
    
    # VLAN Namespace management
    path('vlan-namespaces/', views.VLANNamespaceListView.as_view(), name='vlan_namespace_list'),
    path('vlan-namespaces/add/', views.VLANNamespaceCreateView.as_view(), name='vlan_namespace_add'),
    path('vlan-namespaces/<int:pk>/', views.VLANNamespaceDetailView.as_view(), name='vlan_namespace_detail'),
    path('vlan-namespaces/<int:pk>/edit/', views.VLANNamespaceEditView.as_view(), name='vlan_namespace_edit'),
    path('vlan-namespaces/<int:pk>/delete/', views.VLANNamespaceDeleteView.as_view(), name='vlan_namespace_delete'),
    path('vlan-namespaces/bulk-actions/', views.VLANNamespaceBulkActionsView.as_view(), name='vlan_namespace_bulk_actions'),
    
    # Additional features
    path('topology/', views.TopologyView.as_view(), name='topology'),
    path('externals/', views.ExternalListView.as_view(), name='external_list'),
    path('externals/add/', views.ExternalEditView.as_view(), name='external_add'),
    path('externals/<int:pk>/', views.ExternalView.as_view(), name='external'),
    path('externals/<int:pk>/edit/', views.ExternalEditView.as_view(), name='external_edit'),
    path('externals/<int:pk>/delete/', views.ExternalDeleteView.as_view(), name='external_delete'),
    
    path('ipv4-namespaces/', views.IPv4NamespaceListView.as_view(), name='ipv4namespace_list'),
    path('ipv4-namespaces/add/', views.IPv4NamespaceEditView.as_view(), name='ipv4namespace_add'),
    path('ipv4-namespaces/<int:pk>/', views.IPv4NamespaceView.as_view(), name='ipv4namespace'),
    path('ipv4-namespaces/<int:pk>/edit/', views.IPv4NamespaceEditView.as_view(), name='ipv4namespace_edit'),
    path('ipv4-namespaces/<int:pk>/delete/', views.IPv4NamespaceDeleteView.as_view(), name='ipv4namespace_delete'),
    
    path('servers/', views.ServerListView.as_view(), name='server_list'),
    path('servers/add/', views.ServerEditView.as_view(), name='server_add'),
    path('servers/<int:pk>/', views.ServerView.as_view(), name='server'),
    path('servers/<int:pk>/edit/', views.ServerEditView.as_view(), name='server_edit'),
    path('servers/<int:pk>/delete/', views.ServerDeleteView.as_view(), name='server_delete'),
    
    path('catalog/', views.CRDCatalogView.as_view(), name='catalog'),
    path('sync-all/', views.SyncAllView.as_view(), name='sync_all'),
]