from django.urls import path, include

from . import views

app_name = 'netbox_hedgehog'

urlpatterns = [
    # Fabric management
    path('fabrics/', views.FabricListView.as_view(), name='fabric_list'),
    path('fabrics/add/', views.FabricEditView.as_view(), name='fabric_add'),
    path('fabrics/<int:pk>/', views.FabricView.as_view(), name='fabric'),
    path('fabrics/<int:pk>/edit/', views.FabricEditView.as_view(), name='fabric_edit'),
    path('fabrics/<int:pk>/delete/', views.FabricDeleteView.as_view(), name='fabric_delete'),
    
    # CRD Catalog
    path('catalog/', views.CRDCatalogView.as_view(), name='catalog'),
    path('sync-all/', views.SyncAllView.as_view(), name='sync_all'),
    
    # VPC API URLs
    path('vpcs/', views.VPCListView.as_view(), name='vpc_list'),
    path('vpcs/add/', views.VPCEditView.as_view(), name='vpc_add'),
    path('vpcs/<int:pk>/', views.VPCView.as_view(), name='vpc'),
    path('vpcs/<int:pk>/edit/', views.VPCEditView.as_view(), name='vpc_edit'),
    path('vpcs/<int:pk>/delete/', views.VPCDeleteView.as_view(), name='vpc_delete'),
    
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
    
    # Wiring API URLs
    path('connections/', views.ConnectionListView.as_view(), name='connection_list'),
    path('connections/add/', views.ConnectionEditView.as_view(), name='connection_add'),
    path('connections/<int:pk>/', views.ConnectionView.as_view(), name='connection'),
    path('connections/<int:pk>/edit/', views.ConnectionEditView.as_view(), name='connection_edit'),
    path('connections/<int:pk>/delete/', views.ConnectionDeleteView.as_view(), name='connection_delete'),
    
    path('switches/', views.SwitchListView.as_view(), name='switch_list'),
    path('switches/add/', views.SwitchEditView.as_view(), name='switch_add'),
    path('switches/<int:pk>/', views.SwitchView.as_view(), name='switch'),
    path('switches/<int:pk>/edit/', views.SwitchEditView.as_view(), name='switch_edit'),
    path('switches/<int:pk>/delete/', views.SwitchDeleteView.as_view(), name='switch_delete'),
    
    path('servers/', views.ServerListView.as_view(), name='server_list'),
    path('servers/add/', views.ServerEditView.as_view(), name='server_add'),
    path('servers/<int:pk>/', views.ServerView.as_view(), name='server'),
    path('servers/<int:pk>/edit/', views.ServerEditView.as_view(), name='server_edit'),
    path('servers/<int:pk>/delete/', views.ServerDeleteView.as_view(), name='server_delete'),
    
    # API URLs
    path('api/', include('netbox_hedgehog.api.urls')),
]