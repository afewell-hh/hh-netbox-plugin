from django.urls import path
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, DetailView
from netbox.views.generic import ObjectView

# Minimal safe imports
from .models import HedgehogFabric
from .models.vpc_api import VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering
from .models.wiring_api import Connection, Switch, Server, VLANNamespace, SwitchGroup

app_name = 'netbox_hedgehog'

# Working views from git history
class OverviewView(TemplateView):
    template_name = 'netbox_hedgehog/overview.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['fabric_count'] = HedgehogFabric.objects.count()
            context['recent_fabrics'] = HedgehogFabric.objects.order_by('-created')[:5]
        except Exception:
            context['fabric_count'] = 0
            context['recent_fabrics'] = []
        return context

class FabricListView(ListView):
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_list_simple.html'
    context_object_name = 'fabrics'
    paginate_by = 25

class FabricDetailView(DetailView):
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_detail_simple.html'
    context_object_name = 'object'

class FabricEditView(UpdateView):
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_edit_simple.html'
    fields = [
        'name', 'description', 'status', 'git_repository', 'gitops_directory', 
        'kubernetes_server', 'kubernetes_namespace', 'kubernetes_token', 'kubernetes_ca_cert'
    ]
    context_object_name = 'object'
    
    def get_success_url(self):
        return f'/plugins/hedgehog/fabrics/{self.object.pk}/'

class TopologyView(TemplateView):
    template_name = 'netbox_hedgehog/topology.html'

# Simple CR List Views
class VPCListView(ListView):
    model = VPC
    template_name = 'netbox_hedgehog/vpc_list_simple.html'
    context_object_name = 'vpcs'
    paginate_by = 25

class ConnectionListView(ListView):
    model = Connection
    template_name = 'netbox_hedgehog/connection_list_simple.html'
    context_object_name = 'connections'
    paginate_by = 25

class SwitchListView(ListView):
    model = Switch
    template_name = 'netbox_hedgehog/switch_list_simple.html'
    context_object_name = 'switches'
    paginate_by = 25

class ServerListView(ListView):
    model = Server
    template_name = 'netbox_hedgehog/server_list.html'
    context_object_name = 'servers'
    paginate_by = 25

class VLANNamespaceListView(ListView):
    model = VLANNamespace
    template_name = 'netbox_hedgehog/vlannamespace_list.html'
    context_object_name = 'vlannamespaces'
    paginate_by = 25

class SwitchGroupListView(ListView):
    model = SwitchGroup
    template_name = 'netbox_hedgehog/switchgroup_list.html'
    context_object_name = 'switchgroups'
    paginate_by = 25

# VPC API ListView classes
class ExternalListView(ListView):
    model = External
    template_name = 'netbox_hedgehog/external_list.html'
    context_object_name = 'externals'
    paginate_by = 25

class ExternalAttachmentListView(ListView):
    model = ExternalAttachment
    template_name = 'netbox_hedgehog/externalattachment_list.html'
    context_object_name = 'externalattachments'
    paginate_by = 25

class ExternalPeeringListView(ListView):
    model = ExternalPeering
    template_name = 'netbox_hedgehog/externalpeering_list.html'
    context_object_name = 'externalpeerings'
    paginate_by = 25

class IPv4NamespaceListView(ListView):
    model = IPv4Namespace
    template_name = 'netbox_hedgehog/ipv4namespace_list.html'
    context_object_name = 'ipv4namespaces'
    paginate_by = 25

class VPCAttachmentListView(ListView):
    model = VPCAttachment
    template_name = 'netbox_hedgehog/vpcattachment_list.html'
    context_object_name = 'vpcattachments'
    paginate_by = 25

class VPCPeeringListView(ListView):
    model = VPCPeering
    template_name = 'netbox_hedgehog/vpcpeering_list.html'
    context_object_name = 'vpcpeerings'
    paginate_by = 25

# Simple CR Detail Views
class VPCDetailView(DetailView):
    model = VPC
    template_name = 'netbox_hedgehog/vpc_detail_simple.html'
    context_object_name = 'object'

class ConnectionDetailView(DetailView):
    model = Connection
    template_name = 'netbox_hedgehog/connection_detail_simple.html'
    context_object_name = 'object'

class SwitchDetailView(DetailView):
    model = Switch
    template_name = 'netbox_hedgehog/switch_detail_simple.html'
    context_object_name = 'object'

class ServerDetailView(DetailView):
    model = Server
    template_name = 'netbox_hedgehog/server_detail.html'
    context_object_name = 'object'

class VLANNamespaceDetailView(DetailView):
    model = VLANNamespace
    template_name = 'netbox_hedgehog/vlannamespace_detail.html'
    context_object_name = 'object'

class SwitchGroupDetailView(DetailView):
    model = SwitchGroup
    template_name = 'netbox_hedgehog/switchgroup_detail.html'
    context_object_name = 'object'

# VPC API DetailView classes
class ExternalDetailView(DetailView):
    model = External
    template_name = 'netbox_hedgehog/external_detail.html'
    context_object_name = 'object'

class ExternalAttachmentDetailView(DetailView):
    model = ExternalAttachment
    template_name = 'netbox_hedgehog/externalattachment_detail.html'
    context_object_name = 'object'

class ExternalPeeringDetailView(DetailView):
    model = ExternalPeering
    template_name = 'netbox_hedgehog/externalpeering_detail.html'
    context_object_name = 'object'

class IPv4NamespaceDetailView(DetailView):
    model = IPv4Namespace
    template_name = 'netbox_hedgehog/ipv4namespace_detail.html'
    context_object_name = 'object'

class VPCAttachmentDetailView(DetailView):
    model = VPCAttachment
    template_name = 'netbox_hedgehog/vpcattachment_detail.html'
    context_object_name = 'object'

class VPCPeeringDetailView(DetailView):
    model = VPCPeering
    template_name = 'netbox_hedgehog/vpcpeering_detail.html'
    context_object_name = 'object'

# Simple placeholder for other pages
class PlaceholderView(TemplateView):
    template_name = 'netbox_hedgehog/simple_placeholder.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = getattr(self, 'page_title', 'Page')
        context['message'] = "System recovered - this page is being restored progressively"
        return context

# URL patterns
urlpatterns = [
    # Core working pages
    path('', OverviewView.as_view(), name='overview'),
    path('topology/', TopologyView.as_view(), name='topology'),
    path('fabrics/', FabricListView.as_view(), name='fabric_list'),
    path('fabrics/<int:pk>/', FabricDetailView.as_view(), name='fabric_detail'),
    path('fabrics/<int:pk>/edit/', FabricEditView.as_view(), name='fabric_edit'),
    
    # CR List pages
    path('vpcs/', VPCListView.as_view(), name='vpc_list'),
    path('vpcs/<int:pk>/', VPCDetailView.as_view(), name='vpc_detail'),
    path('connections/', ConnectionListView.as_view(), name='connection_list'),
    path('connections/<int:pk>/', ConnectionDetailView.as_view(), name='connection_detail'),
    path('switches/', SwitchListView.as_view(), name='switch_list'),
    path('switches/<int:pk>/', SwitchDetailView.as_view(), name='switch_detail'),
    path('servers/', ServerListView.as_view(), name='server_list'),
    path('servers/<int:pk>/', ServerDetailView.as_view(), name='server_detail'),
    path('vlan-namespaces/', VLANNamespaceListView.as_view(), name='vlannamespace_list'),
    path('vlan-namespaces/<int:pk>/', VLANNamespaceDetailView.as_view(), name='vlannamespace_detail'),
    path('switch-groups/', SwitchGroupListView.as_view(), name='switchgroup_list'),
    path('switch-groups/<int:pk>/', SwitchGroupDetailView.as_view(), name='switchgroup_detail'),
    
    # VPC API CR pages
    path('externals/', ExternalListView.as_view(), name='external_list'),
    path('externals/<int:pk>/', ExternalDetailView.as_view(), name='external_detail'),
    path('external-attachments/', ExternalAttachmentListView.as_view(), name='externalattachment_list'),
    path('external-attachments/<int:pk>/', ExternalAttachmentDetailView.as_view(), name='externalattachment_detail'),
    path('external-peerings/', ExternalPeeringListView.as_view(), name='externalpeering_list'),
    path('external-peerings/<int:pk>/', ExternalPeeringDetailView.as_view(), name='externalpeering_detail'),
    path('ipv4namespaces/', IPv4NamespaceListView.as_view(), name='ipv4namespace_list'),
    path('ipv4namespaces/<int:pk>/', IPv4NamespaceDetailView.as_view(), name='ipv4namespace_detail'),
    path('vpc-attachments/', VPCAttachmentListView.as_view(), name='vpcattachment_list'),
    path('vpc-attachments/<int:pk>/', VPCAttachmentDetailView.as_view(), name='vpcattachment_detail'),
    path('vpc-peerings/', VPCPeeringListView.as_view(), name='vpcpeering_list'),
    path('vpc-peerings/<int:pk>/', VPCPeeringDetailView.as_view(), name='vpcpeering_detail'),
]

# Add remaining placeholder pages for navigation
placeholder_pages = [
    ('gitops-onboarding/', 'gitops_onboarding', 'GitOps Onboarding'),
    ('git-repositories/', 'gitrepository_list', 'Git Repositories'),
    ('git-repositories/add/', 'gitrepository_add', 'Add Git Repository'),
    ('vpcs/add/', 'vpc_add', 'Add VPC'),
    ('externals/', 'external_list', 'External Systems'),
    ('externals/add/', 'external_add', 'Add External System'),
    ('ipv4namespaces/', 'ipv4namespace_list', 'IPv4 Namespaces'),
    ('ipv4namespaces/add/', 'ipv4namespace_add', 'Add IPv4 Namespace'),
    ('external-attachments/', 'externalattachment_list', 'External Attachments'),
    ('external-attachments/add/', 'externalattachment_add', 'Add External Attachment'),
    ('external-peerings/', 'externalpeering_list', 'External Peerings'),
    ('external-peerings/add/', 'externalpeering_add', 'Add External Peering'),
    ('vpc-attachments/', 'vpcattachment_list', 'VPC Attachments'),
    ('vpc-attachments/add/', 'vpcattachment_add', 'Add VPC Attachment'),
    ('vpc-peerings/', 'vpcpeering_list', 'VPC Peerings'),
    ('vpc-peerings/add/', 'vpcpeering_add', 'Add VPC Peering'),
    ('connections/add/', 'connection_add', 'Add Connection'),
    ('switches/add/', 'switch_add', 'Add Switch'),
    ('servers/add/', 'server_add', 'Add Server'),
    ('servers/<int:pk>/', 'server_detail', 'Server Details'),
    ('switch-groups/add/', 'switchgroup_add', 'Add Switch Group'),
    ('switch-groups/<int:pk>/', 'switchgroup_detail', 'Switch Group Details'),
    ('vlan-namespaces/add/', 'vlannamespace_add', 'Add VLAN Namespace'),
    ('vlan-namespaces/<int:pk>/', 'vlannamespace_detail', 'VLAN Namespace Details'),
]

for url, name, title in placeholder_pages:
    view_class = type(f'{name}View', (PlaceholderView,), {'page_title': title})
    urlpatterns.append(path(url, view_class.as_view(), name=name))