from django.urls import path
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, DetailView
from netbox.views.generic import ObjectView

# Minimal safe imports
from .models import HedgehogFabric

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

class TopologyView(TemplateView):
    template_name = 'netbox_hedgehog/topology.html'

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
]

# Add placeholder pages for navigation
placeholder_pages = [
    ('gitops-onboarding/', 'gitops_onboarding', 'GitOps Onboarding'),
    ('fabrics/<int:pk>/edit/', 'fabric_edit', 'Edit Fabric'),
    ('git-repositories/', 'gitrepository_list', 'Git Repositories'),
    ('git-repositories/add/', 'gitrepository_add', 'Add Git Repository'),
    ('vpcs/', 'vpc_list', 'VPCs'),
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
    ('connections/', 'connection_list', 'Connections'),
    ('connections/add/', 'connection_add', 'Add Connection'),
    ('switches/', 'switch_list', 'Switches'),
    ('switches/add/', 'switch_add', 'Add Switch'),
    ('servers/', 'server_list', 'Servers'),
    ('servers/add/', 'server_add', 'Add Server'),
    ('switch-groups/', 'switchgroup_list', 'Switch Groups'),
    ('switch-groups/add/', 'switchgroup_add', 'Add Switch Group'),
    ('vlan-namespaces/', 'vlannamespace_list', 'VLAN Namespaces'),
    ('vlan-namespaces/add/', 'vlannamespace_add', 'Add VLAN Namespace'),
]

for url, name, title in placeholder_pages:
    view_class = type(f'{name}View', (PlaceholderView,), {'page_title': title})
    urlpatterns.append(path(url, view_class.as_view(), name=name))