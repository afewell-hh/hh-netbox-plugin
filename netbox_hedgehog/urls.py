from django.urls import path
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from netbox.views.generic import ObjectView

from .models import HedgehogFabric, VPC, External
from .forms import HedgehogFabricForm, VPCForm, ExternalForm
from .simple_sync import SimpleFabricSyncView, SimpleFabricTestConnectionView
from .views.vpc_api import (
    ExternalListView, ExternalView, ExternalEditView, ExternalDeleteView,
    IPv4NamespaceListView, IPv4NamespaceView, IPv4NamespaceEditView, IPv4NamespaceDeleteView,
    ExternalAttachmentListView, ExternalAttachmentView, ExternalAttachmentEditView, ExternalAttachmentDeleteView,
    ExternalPeeringListView, ExternalPeeringView, ExternalPeeringEditView, ExternalPeeringDeleteView,
    VPCAttachmentListView, VPCAttachmentView, VPCAttachmentEditView, VPCAttachmentDeleteView,
    VPCPeeringListView, VPCPeeringView, VPCPeeringEditView, VPCPeeringDeleteView
)
# from .views.crd_views import FabricCRDListView, CRDDetailView, ApplyCRDView, DeleteCRDView

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

# VPC Views
class VPCListView(ListView):
    model = VPC
    template_name = 'netbox_hedgehog/vpc_list.html'
    context_object_name = 'vpcs'
    paginate_by = 25

class VPCDetailView(ObjectView):
    queryset = VPC.objects.all()
    template_name = 'netbox_hedgehog/vpc_detail.html'

class VPCCreateView(CreateView):
    model = VPC
    form_class = VPCForm
    template_name = 'netbox_hedgehog/vpc_edit.html'
    success_url = '/plugins/netbox_hedgehog/vpcs/'

class VPCEditView(UpdateView):
    model = VPC
    form_class = VPCForm
    template_name = 'netbox_hedgehog/vpc_edit.html'
    success_url = '/plugins/netbox_hedgehog/vpcs/'

class VPCDeleteView(DeleteView):
    model = VPC
    template_name = 'netbox_hedgehog/vpc_confirm_delete.html'
    success_url = '/plugins/netbox_hedgehog/vpcs/'

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
    path('vpcs/add/', VPCCreateView.as_view(), name='vpc_add'),
    path('vpcs/<int:pk>/', VPCDetailView.as_view(), name='vpc_detail'),
    path('vpcs/<int:pk>/edit/', VPCEditView.as_view(), name='vpc_edit'),
    path('vpcs/<int:pk>/delete/', VPCDeleteView.as_view(), name='vpc_delete'),
    
    # External URLs
    path('externals/', ExternalListView.as_view(), name='external_list'),
    path('externals/add/', ExternalEditView.as_view(), name='external_add'),
    path('externals/<int:pk>/', ExternalView.as_view(), name='external_detail'),
    path('externals/<int:pk>/edit/', ExternalEditView.as_view(), name='external_edit'),
    path('externals/<int:pk>/delete/', ExternalDeleteView.as_view(), name='external_delete'),
    
    # IPv4Namespace URLs
    path('ipv4namespaces/', IPv4NamespaceListView.as_view(), name='ipv4namespace_list'),
    path('ipv4namespaces/add/', IPv4NamespaceEditView.as_view(), name='ipv4namespace_add'),
    path('ipv4namespaces/<int:pk>/', IPv4NamespaceView.as_view(), name='ipv4namespace_detail'),
    path('ipv4namespaces/<int:pk>/edit/', IPv4NamespaceEditView.as_view(), name='ipv4namespace_edit'),
    path('ipv4namespaces/<int:pk>/delete/', IPv4NamespaceDeleteView.as_view(), name='ipv4namespace_delete'),
    
    # ExternalAttachment URLs
    path('external-attachments/', ExternalAttachmentListView.as_view(), name='externalattachment_list'),
    path('external-attachments/add/', ExternalAttachmentEditView.as_view(), name='externalattachment_add'),
    path('external-attachments/<int:pk>/', ExternalAttachmentView.as_view(), name='externalattachment_detail'),
    path('external-attachments/<int:pk>/edit/', ExternalAttachmentEditView.as_view(), name='externalattachment_edit'),
    path('external-attachments/<int:pk>/delete/', ExternalAttachmentDeleteView.as_view(), name='externalattachment_delete'),
    
    # ExternalPeering URLs
    path('external-peerings/', ExternalPeeringListView.as_view(), name='externalpeering_list'),
    path('external-peerings/add/', ExternalPeeringEditView.as_view(), name='externalpeering_add'),
    path('external-peerings/<int:pk>/', ExternalPeeringView.as_view(), name='externalpeering_detail'),
    path('external-peerings/<int:pk>/edit/', ExternalPeeringEditView.as_view(), name='externalpeering_edit'),
    path('external-peerings/<int:pk>/delete/', ExternalPeeringDeleteView.as_view(), name='externalpeering_delete'),
    
    # VPCAttachment URLs
    path('vpc-attachments/', VPCAttachmentListView.as_view(), name='vpcattachment_list'),
    path('vpc-attachments/add/', VPCAttachmentEditView.as_view(), name='vpcattachment_add'),
    path('vpc-attachments/<int:pk>/', VPCAttachmentView.as_view(), name='vpcattachment_detail'),
    path('vpc-attachments/<int:pk>/edit/', VPCAttachmentEditView.as_view(), name='vpcattachment_edit'),
    path('vpc-attachments/<int:pk>/delete/', VPCAttachmentDeleteView.as_view(), name='vpcattachment_delete'),
    
    # VPCPeering URLs
    path('vpc-peerings/', VPCPeeringListView.as_view(), name='vpcpeering_list'),
    path('vpc-peerings/add/', VPCPeeringEditView.as_view(), name='vpcpeering_add'),
    path('vpc-peerings/<int:pk>/', VPCPeeringView.as_view(), name='vpcpeering_detail'),
    path('vpc-peerings/<int:pk>/edit/', VPCPeeringEditView.as_view(), name='vpcpeering_edit'),
    path('vpc-peerings/<int:pk>/delete/', VPCPeeringDeleteView.as_view(), name='vpcpeering_delete'),
    
    # Other URLs
    path('topology/', TopologyView.as_view(), name='topology'),
]