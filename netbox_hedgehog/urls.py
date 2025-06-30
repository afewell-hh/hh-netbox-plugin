from django.urls import path
from django.views.generic import TemplateView, ListView
from netbox.views.generic import ObjectView

from .models import HedgehogFabric, VPC

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

class FabricListView(ListView):
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_list.html'
    context_object_name = 'fabrics'
    paginate_by = 25

class FabricDetailView(ObjectView):
    queryset = HedgehogFabric.objects.all()
    template_name = 'netbox_hedgehog/fabric_detail.html'

class VPCListView(ListView):
    model = VPC
    template_name = 'netbox_hedgehog/vpc_list.html'
    context_object_name = 'vpcs'
    paginate_by = 25

class TopologyView(TemplateView):
    template_name = 'netbox_hedgehog/topology.html'

urlpatterns = [
    path('', OverviewView.as_view(), name='overview'),
    path('fabrics/', FabricListView.as_view(), name='fabric_list'),
    path('fabrics/<int:pk>/', FabricDetailView.as_view(), name='fabric_detail'),
    path('vpcs/', VPCListView.as_view(), name='vpc_list'),
    path('topology/', TopologyView.as_view(), name='topology'),
]