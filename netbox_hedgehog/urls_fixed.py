from django.urls import path
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from netbox.views.generic import ObjectView

# Import models directly to avoid conflicts
from .models.fabric import HedgehogFabric
from .models.vpc_api import VPC

app_name = 'netbox_hedgehog'

# Database-backed views
class OverviewView(TemplateView):
    template_name = 'netbox_hedgehog/overview.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['fabric_count'] = HedgehogFabric.objects.count()
            context['vpc_count'] = VPC.objects.count()
            context['recent_fabrics'] = HedgehogFabric.objects.order_by('-created')[:5]
        except Exception:
            # Handle case where tables don't exist yet
            context['fabric_count'] = 0
            context['vpc_count'] = 0
            context['recent_fabrics'] = []
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

# Import forms only when needed to avoid circular imports
def get_fabric_form():
    from .forms import HedgehogFabricForm
    return HedgehogFabricForm

def get_vpc_form():
    from .forms import VPCForm
    return VPCForm

class FabricCreateView(CreateView):
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_edit.html'
    success_url = '/plugins/netbox_hedgehog/fabrics/'
    
    def get_form_class(self):
        return get_fabric_form()

class FabricEditView(UpdateView):
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_edit.html'
    success_url = '/plugins/netbox_hedgehog/fabrics/'
    
    def get_form_class(self):
        return get_fabric_form()

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
    template_name = 'netbox_hedgehog/vpc_edit.html'
    success_url = '/plugins/netbox_hedgehog/vpcs/'
    
    def get_form_class(self):
        return get_vpc_form()

class VPCEditView(UpdateView):
    model = VPC
    template_name = 'netbox_hedgehog/vpc_edit.html'
    success_url = '/plugins/netbox_hedgehog/vpcs/'
    
    def get_form_class(self):
        return get_vpc_form()

class VPCDeleteView(DeleteView):
    model = VPC
    template_name = 'netbox_hedgehog/vpc_confirm_delete.html'
    success_url = '/plugins/netbox_hedgehog/vpcs/'

# Import sync views dynamically to avoid import issues
def get_sync_views():
    try:
        from .views.sync_views import FabricSyncView, FabricTestConnectionView
        return FabricSyncView, FabricTestConnectionView
    except ImportError:
        # Fallback to simple sync if imports fail
        from .simple_sync import SimpleFabricSyncView, SimpleFabricTestConnectionView
        return SimpleFabricSyncView, SimpleFabricTestConnectionView

# Other Views
class TopologyView(TemplateView):
    template_name = 'netbox_hedgehog/topology.html'

# Get sync views
SyncView, TestConnectionView = get_sync_views()

urlpatterns = [
    path('', OverviewView.as_view(), name='overview'),
    
    # Fabric URLs
    path('fabrics/', FabricListView.as_view(), name='fabric_list'),
    path('fabrics/add/', FabricCreateView.as_view(), name='fabric_add'),
    path('fabrics/<int:pk>/', FabricDetailView.as_view(), name='fabric_detail'),
    path('fabrics/<int:pk>/edit/', FabricEditView.as_view(), name='fabric_edit'),
    path('fabrics/<int:pk>/delete/', FabricDeleteView.as_view(), name='fabric_delete'),
    path('fabrics/<int:pk>/sync/', SyncView.as_view(), name='fabric_sync'),
    path('fabrics/<int:pk>/test-connection/', TestConnectionView.as_view(), name='fabric_test_connection'),
    
    # VPC URLs
    path('vpcs/', VPCListView.as_view(), name='vpc_list'),
    path('vpcs/add/', VPCCreateView.as_view(), name='vpc_add'),
    path('vpcs/<int:pk>/', VPCDetailView.as_view(), name='vpc_detail'),
    path('vpcs/<int:pk>/edit/', VPCEditView.as_view(), name='vpc_edit'),
    path('vpcs/<int:pk>/delete/', VPCDeleteView.as_view(), name='vpc_delete'),
    
    # Other URLs
    path('topology/', TopologyView.as_view(), name='topology'),
]