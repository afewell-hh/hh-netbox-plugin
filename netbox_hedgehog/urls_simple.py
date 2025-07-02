from django.urls import path
from django.views.generic import TemplateView

app_name = 'netbox_hedgehog'

# Simple overview view to test
class SimpleOverviewView(TemplateView):
    template_name = 'netbox_hedgehog/overview.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fabric_count'] = 0
        context['vpc_count'] = 0
        return context

urlpatterns = [
    path('', SimpleOverviewView.as_view(), name='overview'),
]