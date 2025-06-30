from django.urls import path
from django.views.generic import TemplateView, ListView
from netbox.views.generic import ObjectView, ObjectEditView, ObjectDeleteView

from .models import HedgehogFabric, VPC
from .forms import HedgehogFabricForm, VPCForm

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

class FabricEditView(ObjectEditView):
    queryset = HedgehogFabric.objects.all()
    form = HedgehogFabricForm
    template_name = 'netbox_hedgehog/fabric_edit.html'

class FabricDeleteView(ObjectDeleteView):
    queryset = HedgehogFabric.objects.all()
    default_return_url = 'plugins:netbox_hedgehog:fabric_list'

# VPC Views
class VPCListView(ListView):
    model = VPC
    template_name = 'netbox_hedgehog/vpc_list.html'
    context_object_name = 'vpcs'
    paginate_by = 25

class VPCDetailView(ObjectView):
    queryset = VPC.objects.all()
    template_name = 'netbox_hedgehog/vpc_detail.html'

class VPCEditView(ObjectEditView):
    queryset = VPC.objects.all()
    form = VPCForm
    template_name = 'netbox_hedgehog/vpc_edit.html'

class VPCDeleteView(ObjectDeleteView):
    queryset = VPC.objects.all()
    default_return_url = 'plugins:netbox_hedgehog:vpc_list'

# Other Views
class TopologyView(TemplateView):
    template_name = 'netbox_hedgehog/topology.html'

urlpatterns = [
    path('', OverviewView.as_view(), name='overview'),
    
    # Fabric URLs
    path('fabrics/', FabricListView.as_view(), name='fabric_list'),
    path('fabrics/add/', FabricEditView.as_view(), name='fabric_add'),
    path('fabrics/<int:pk>/', FabricDetailView.as_view(), name='fabric_detail'),
    path('fabrics/<int:pk>/edit/', FabricEditView.as_view(), name='fabric_edit'),
    path('fabrics/<int:pk>/delete/', FabricDeleteView.as_view(), name='fabric_delete'),
    
    # VPC URLs
    path('vpcs/', VPCListView.as_view(), name='vpc_list'),
    path('vpcs/add/', VPCEditView.as_view(), name='vpc_add'),
    path('vpcs/<int:pk>/', VPCDetailView.as_view(), name='vpc_detail'),
    path('vpcs/<int:pk>/edit/', VPCEditView.as_view(), name='vpc_edit'),
    path('vpcs/<int:pk>/delete/', VPCDeleteView.as_view(), name='vpc_delete'),
    
    # Other URLs
    path('topology/', TopologyView.as_view(), name='topology'),
]