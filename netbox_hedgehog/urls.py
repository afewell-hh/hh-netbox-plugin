from django.urls import path
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from netbox.views.generic import ObjectView

from .models import HedgehogFabric, VPC, External
from .forms import HedgehogFabricForm, VPCForm, ExternalForm
from .simple_sync import SimpleFabricSyncView, SimpleFabricTestConnectionView
# Import VPC API views
from .views.vpc_api import (
    VPCListView, VPCView, VPCEditView, VPCDeleteView,
    ExternalListView, ExternalView, ExternalEditView, ExternalDeleteView,
    IPv4NamespaceListView, IPv4NamespaceView, IPv4NamespaceEditView, IPv4NamespaceDeleteView,
    ExternalAttachmentListView, ExternalAttachmentView, ExternalAttachmentEditView, ExternalAttachmentDeleteView,
    ExternalPeeringListView, ExternalPeeringView, ExternalPeeringEditView, ExternalPeeringDeleteView,
    VPCAttachmentListView, VPCAttachmentView, VPCAttachmentEditView, VPCAttachmentDeleteView,
    VPCPeeringListView, VPCPeeringView, VPCPeeringEditView, VPCPeeringDeleteView
)
# Import Wiring API views
from .views.wiring_api import (
    ConnectionListView, ConnectionView, ConnectionEditView, ConnectionDeleteView,
    SwitchListView, SwitchView, SwitchEditView, SwitchDeleteView,
    ServerListView, ServerView, ServerEditView, ServerDeleteView,
    SwitchGroupListView, SwitchGroupView, SwitchGroupEditView, SwitchGroupDeleteView,
    VLANNamespaceListView, VLANNamespaceView, VLANNamespaceEditView, VLANNamespaceDeleteView
)
# from .views.crd_views import FabricCRDListView, CRDDetailView, ApplyCRDView, DeleteCRDView

# Other Views
class TopologyView(TemplateView):
    template_name = 'netbox_hedgehog/topology.html'

app_name = 'netbox_hedgehog'

# Database-backed views
class OverviewView(TemplateView):
    template_name = 'netbox_hedgehog/overview.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fabric_count'] = HedgehogFabric.objects.count()
        context['vpc_count'] = VPC.objects.count()
        context['recent_fabrics'] = HedgehogFabric.objects.order_by('-created')[:5]
        return context

# Fabric Views
class FabricListView(ListView):
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_list.html'
    context_object_name = 'fabrics'
    paginate_by = 25

class FabricDetailView(ObjectView):
    queryset = HedgehogFabric.objects.all()
    template_name = 'netbox_hedgehog/fabric_detail.html'

class FabricCreateView(CreateView):
    model = HedgehogFabric
    form_class = HedgehogFabricForm
    template_name = 'netbox_hedgehog/fabric_edit.html'
    success_url = '/plugins/netbox_hedgehog/fabrics/'

class FabricEditView(UpdateView):
    model = HedgehogFabric
    form_class = HedgehogFabricForm
    template_name = 'netbox_hedgehog/fabric_edit.html'
    success_url = '/plugins/netbox_hedgehog/fabrics/'

class FabricDeleteView(DeleteView):
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_confirm_delete.html'
    success_url = '/plugins/netbox_hedgehog/fabrics/'

# Other Views
class TopologyView(TemplateView):
    template_name = 'netbox_hedgehog/topology.html'

urlpatterns = [
    path('', OverviewView.as_view(), name='overview'),
    
    # Fabric URLs
    path('fabrics/', FabricListView.as_view(), name='fabric_list'),
    path('fabrics/add/', FabricCreateView.as_view(), name='fabric_add'),
    path('fabrics/<int:pk>/', FabricDetailView.as_view(), name='fabric_detail'),
    path('fabrics/<int:pk>/edit/', FabricEditView.as_view(), name='fabric_edit'),
    path('fabrics/<int:pk>/delete/', FabricDeleteView.as_view(), name='fabric_delete'),
    path('fabrics/<int:pk>/sync/', SimpleFabricSyncView.as_view(), name='fabric_sync'),
    path('fabrics/<int:pk>/test-connection/', SimpleFabricTestConnectionView.as_view(), name='fabric_test_connection'),
    
    # CRD URLs - temporarily disabled
    # path('fabrics/<int:pk>/crds/', FabricCRDListView.as_view(), name='fabric_crds'),
    # path('fabrics/<int:fabric_pk>/crds/<str:crd_type>/<int:crd_pk>/', CRDDetailView.as_view(), name='crd_detail'),
    # path('fabrics/<int:fabric_pk>/crds/<str:crd_type>/<int:crd_pk>/apply/', ApplyCRDView.as_view(), name='crd_apply'),
    # path('fabrics/<int:fabric_pk>/crds/<str:crd_type>/<int:crd_pk>/delete/', DeleteCRDView.as_view(), name='crd_delete'),
    
    # VPC URLs
    path('vpcs/', VPCListView.as_view(), name='vpc_list'),
    path('vpcs/add/', VPCEditView.as_view(), name='vpc_add'),
    path('vpcs/<int:pk>/', VPCView.as_view(), name='vpc'),
    path('vpcs/<int:pk>/edit/', VPCEditView.as_view(), name='vpc_edit'),
    path('vpcs/<int:pk>/delete/', VPCDeleteView.as_view(), name='vpc_delete'),
    path('vpcs/<int:pk>/changelog/', VPCView.as_view(), name='vpc_changelog'),
    
    # External URLs
    path('externals/', ExternalListView.as_view(), name='external_list'),
    path('externals/add/', ExternalEditView.as_view(), name='external_add'),
    path('externals/<int:pk>/', ExternalView.as_view(), name='external_detail'),
    path('externals/<int:pk>/edit/', ExternalEditView.as_view(), name='external_edit'),
    path('externals/<int:pk>/delete/', ExternalDeleteView.as_view(), name='external_delete'),
    path('externals/<int:pk>/changelog/', ExternalView.as_view(), name='external_changelog'),
    
    # IPv4Namespace URLs
    path('ipv4namespaces/', IPv4NamespaceListView.as_view(), name='ipv4namespace_list'),
    path('ipv4namespaces/add/', IPv4NamespaceEditView.as_view(), name='ipv4namespace_add'),
    path('ipv4namespaces/<int:pk>/', IPv4NamespaceView.as_view(), name='ipv4namespace'),
    path('ipv4namespaces/<int:pk>/edit/', IPv4NamespaceEditView.as_view(), name='ipv4namespace_edit'),
    path('ipv4namespaces/<int:pk>/delete/', IPv4NamespaceDeleteView.as_view(), name='ipv4namespace_delete'),
    path('ipv4namespaces/<int:pk>/changelog/', IPv4NamespaceView.as_view(), name='ipv4namespace_changelog'),
    
    # ExternalAttachment URLs
    path('external-attachments/', ExternalAttachmentListView.as_view(), name='externalattachment_list'),
    path('external-attachments/add/', ExternalAttachmentEditView.as_view(), name='externalattachment_add'),
    path('external-attachments/<int:pk>/', ExternalAttachmentView.as_view(), name='externalattachment_detail'),
    path('external-attachments/<int:pk>/edit/', ExternalAttachmentEditView.as_view(), name='externalattachment_edit'),
    path('external-attachments/<int:pk>/delete/', ExternalAttachmentDeleteView.as_view(), name='externalattachment_delete'),
    path('external-attachments/<int:pk>/changelog/', ExternalAttachmentView.as_view(), name='externalattachment_changelog'),
    
    # ExternalPeering URLs
    path('external-peerings/', ExternalPeeringListView.as_view(), name='externalpeering_list'),
    path('external-peerings/add/', ExternalPeeringEditView.as_view(), name='externalpeering_add'),
    path('external-peerings/<int:pk>/', ExternalPeeringView.as_view(), name='externalpeering_detail'),
    path('external-peerings/<int:pk>/edit/', ExternalPeeringEditView.as_view(), name='externalpeering_edit'),
    path('external-peerings/<int:pk>/delete/', ExternalPeeringDeleteView.as_view(), name='externalpeering_delete'),
    path('external-peerings/<int:pk>/changelog/', ExternalPeeringView.as_view(), name='externalpeering_changelog'),
    
    # VPCAttachment URLs
    path('vpc-attachments/', VPCAttachmentListView.as_view(), name='vpcattachment_list'),
    path('vpc-attachments/add/', VPCAttachmentEditView.as_view(), name='vpcattachment_add'),
    path('vpc-attachments/<int:pk>/', VPCAttachmentView.as_view(), name='vpcattachment_detail'),
    path('vpc-attachments/<int:pk>/edit/', VPCAttachmentEditView.as_view(), name='vpcattachment_edit'),
    path('vpc-attachments/<int:pk>/delete/', VPCAttachmentDeleteView.as_view(), name='vpcattachment_delete'),
    path('vpc-attachments/<int:pk>/changelog/', VPCAttachmentView.as_view(), name='vpcattachment_changelog'),
    
    # VPCPeering URLs
    path('vpc-peerings/', VPCPeeringListView.as_view(), name='vpcpeering_list'),
    path('vpc-peerings/add/', VPCPeeringEditView.as_view(), name='vpcpeering_add'),
    path('vpc-peerings/<int:pk>/', VPCPeeringView.as_view(), name='vpcpeering_detail'),
    path('vpc-peerings/<int:pk>/edit/', VPCPeeringEditView.as_view(), name='vpcpeering_edit'),
    path('vpc-peerings/<int:pk>/delete/', VPCPeeringDeleteView.as_view(), name='vpcpeering_delete'),
    path('vpc-peerings/<int:pk>/changelog/', VPCPeeringView.as_view(), name='vpcpeering_changelog'),
    
    # Wiring API URLs
    # Connection URLs
    path('connections/', ConnectionListView.as_view(), name='connection_list'),
    path('connections/add/', ConnectionEditView.as_view(), name='connection_add'),
    path('connections/<int:pk>/', ConnectionView.as_view(), name='connection'),
    path('connections/<int:pk>/edit/', ConnectionEditView.as_view(), name='connection_edit'),
    path('connections/<int:pk>/delete/', ConnectionDeleteView.as_view(), name='connection_delete'),
    path('connections/<int:pk>/changelog/', ConnectionView.as_view(), name='connection_changelog'),
    
    # Switch URLs
    path('switches/', SwitchListView.as_view(), name='switch_list'),
    path('switches/add/', SwitchEditView.as_view(), name='switch_add'),
    path('switches/<int:pk>/', SwitchView.as_view(), name='switch'),
    path('switches/<int:pk>/edit/', SwitchEditView.as_view(), name='switch_edit'),
    path('switches/<int:pk>/delete/', SwitchDeleteView.as_view(), name='switch_delete'),
    path('switches/<int:pk>/changelog/', SwitchView.as_view(), name='switch_changelog'),
    
    # Server URLs
    path('servers/', ServerListView.as_view(), name='server_list'),
    path('servers/add/', ServerEditView.as_view(), name='server_add'),
    path('servers/<int:pk>/', ServerView.as_view(), name='server'),
    path('servers/<int:pk>/edit/', ServerEditView.as_view(), name='server_edit'),
    path('servers/<int:pk>/delete/', ServerDeleteView.as_view(), name='server_delete'),
    path('servers/<int:pk>/changelog/', ServerView.as_view(), name='server_changelog'),
    
    # SwitchGroup URLs
    path('switch-groups/', SwitchGroupListView.as_view(), name='switchgroup_list'),
    path('switch-groups/add/', SwitchGroupEditView.as_view(), name='switchgroup_add'),
    path('switch-groups/<int:pk>/', SwitchGroupView.as_view(), name='switchgroup'),
    path('switch-groups/<int:pk>/edit/', SwitchGroupEditView.as_view(), name='switchgroup_edit'),
    path('switch-groups/<int:pk>/delete/', SwitchGroupDeleteView.as_view(), name='switchgroup_delete'),
    path('switch-groups/<int:pk>/changelog/', SwitchGroupView.as_view(), name='switchgroup_changelog'),
    
    # VLANNamespace URLs
    path('vlan-namespaces/', VLANNamespaceListView.as_view(), name='vlannamespace_list'),
    path('vlan-namespaces/add/', VLANNamespaceEditView.as_view(), name='vlannamespace_add'),
    path('vlan-namespaces/<int:pk>/', VLANNamespaceView.as_view(), name='vlannamespace'),
    path('vlan-namespaces/<int:pk>/edit/', VLANNamespaceEditView.as_view(), name='vlannamespace_edit'),
    path('vlan-namespaces/<int:pk>/delete/', VLANNamespaceDeleteView.as_view(), name='vlannamespace_delete'),
    path('vlan-namespaces/<int:pk>/changelog/', VLANNamespaceView.as_view(), name='vlannamespace_changelog'),
    
    # Other URLs
    path('topology/', TopologyView.as_view(), name='topology'),
]