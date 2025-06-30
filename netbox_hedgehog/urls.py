from django.urls import path
from django.views.generic import TemplateView

app_name = 'netbox_hedgehog'

# Simple template views for testing
class OverviewView(TemplateView):
    template_name = 'netbox_hedgehog/overview.html'

class FabricListView(TemplateView):
    template_name = 'netbox_hedgehog/fabric_list.html'

class VPCListView(TemplateView):
    template_name = 'netbox_hedgehog/vpc_list.html'

class TopologyView(TemplateView):
    template_name = 'netbox_hedgehog/topology.html'

urlpatterns = [
    path('', OverviewView.as_view(), name='overview'),
    path('fabrics/', FabricListView.as_view(), name='fabric_list'),
    path('vpcs/', VPCListView.as_view(), name='vpc_list'),
    path('topology/', TopologyView.as_view(), name='topology'),
]