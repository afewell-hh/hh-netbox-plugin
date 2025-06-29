from django.shortcuts import render
from django.contrib import messages
from django.views.generic import View
from django.http import HttpResponseRedirect
from django.urls import reverse

from .. import models

class CRDCatalogView(View):
    """Self-service catalog view for creating CRDs"""
    template_name = 'netbox_hedgehog/catalog.html'
    
    def get(self, request):
        """Display the CRD catalog"""
        context = {
            'crd_types': [
                # VPC API CRDs
                {'name': 'VPC', 'type': 'vpc', 'description': 'Virtual Private Cloud configuration'},
                {'name': 'External', 'type': 'external', 'description': 'External system connection'},
                {'name': 'IPv4 Namespace', 'type': 'ipv4_namespace', 'description': 'IPv4 address namespace'},
                # Wiring API CRDs
                {'name': 'Connection', 'type': 'connection', 'description': 'Physical/logical connections'},
                {'name': 'Switch', 'type': 'switch', 'description': 'Network switch configuration'},
                {'name': 'Server', 'type': 'server', 'description': 'Server connection configuration'},
            ],
            'fabrics': models.HedgehogFabric.objects.filter(status='active'),
        }
        return render(request, self.template_name, context)

class SyncAllView(View):
    """View to trigger synchronization of all CRDs"""
    
    def post(self, request):
        """Trigger sync for all fabrics"""
        try:
            # TODO: Implement actual sync logic
            messages.success(request, 'Synchronization initiated for all fabrics.')
        except Exception as e:
            messages.error(request, f'Synchronization failed: {str(e)}')
        
        return HttpResponseRedirect(reverse('plugins:netbox_hedgehog:catalog'))