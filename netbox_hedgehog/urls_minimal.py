from django.urls import path
from django.views.generic import TemplateView

app_name = 'netbox_hedgehog'

# Simple template view for testing
class SimpleView(TemplateView):
    template_name = 'netbox_hedgehog/simple_dashboard.html'

urlpatterns = [
    path('', SimpleView.as_view(), name='overview'),
]