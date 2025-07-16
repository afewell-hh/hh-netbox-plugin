"""
Custom fabric deletion view that bypasses serialization issues.
"""

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import View
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from netbox.views.generic import ObjectDeleteView
from django.db import transaction

from ..models import HedgehogFabric
import logging

logger = logging.getLogger(__name__)


class SafeFabricDeleteView(LoginRequiredMixin, View):
    """
    Safe fabric deletion view that bypasses problematic serialization.
    Performs the deletion directly without relying on NetBox's ObjectDeleteView.
    """
    
    def get(self, request, pk):
        """Show deletion confirmation page"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        # Simple HTML template for confirmation
        from django.template.response import TemplateResponse
        
        # Count related objects
        related_counts = self._get_related_object_counts(fabric)
        
        context = {
            'object': fabric,
            'fabric': fabric,
            'related_counts': related_counts,
            'confirm_url': reverse_lazy('plugins:netbox_hedgehog:fabric_delete_safe', kwargs={'pk': pk}),
            'return_url': reverse_lazy('plugins:netbox_hedgehog:fabric_detail', kwargs={'pk': pk}),
        }
        
        return TemplateResponse(
            request, 
            'netbox_hedgehog/fabric_delete_safe.html', 
            context
        )
    
    def post(self, request, pk):
        """Perform the actual deletion"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        fabric_name = fabric.name
        
        try:
            with transaction.atomic():
                logger.info(f"Starting safe deletion of fabric: {fabric_name}")
                
                # Count objects before deletion for logging
                related_counts = self._get_related_object_counts(fabric)
                logger.info(f"Related objects to be deleted: {related_counts}")
                
                # Perform the deletion - Django's CASCADE will handle related objects
                fabric.delete()
                
                logger.info(f"Successfully deleted fabric: {fabric_name}")
                
                # Success message
                messages.success(
                    request, 
                    f"Fabric '{fabric_name}' and all related objects have been deleted successfully."
                )
                
                # Redirect to fabric list
                return redirect('plugins:netbox_hedgehog:fabric_list')
                
        except Exception as e:
            logger.error(f"Failed to delete fabric {fabric_name}: {e}")
            messages.error(
                request,
                f"Failed to delete fabric '{fabric_name}': {str(e)}"
            )
            # Redirect back to fabric detail page
            return redirect('plugins:netbox_hedgehog:fabric_detail', pk=pk)
    
    def _get_related_object_counts(self, fabric):
        """Get counts of related objects that will be deleted"""
        counts = {}
        
        try:
            # Count VPCs
            counts['VPCs'] = fabric.vpc_set.count() if hasattr(fabric, 'vpc_set') else 0
        except Exception:
            counts['VPCs'] = 0
            
        try:
            # Count Connections  
            counts['Connections'] = fabric.connection_set.count() if hasattr(fabric, 'connection_set') else 0
        except Exception:
            counts['Connections'] = 0
            
        try:
            # Count Servers
            counts['Servers'] = fabric.server_set.count() if hasattr(fabric, 'server_set') else 0
        except Exception:
            counts['Servers'] = 0
            
        try:
            # Count Switches
            counts['Switches'] = fabric.switch_set.count() if hasattr(fabric, 'switch_set') else 0
        except Exception:
            counts['Switches'] = 0
            
        try:
            # Count GitOps resources
            counts['GitOps Resources'] = fabric.gitops_resources.count() if hasattr(fabric, 'gitops_resources') else 0
        except Exception:
            counts['GitOps Resources'] = 0
        
        # Remove zero counts for cleaner display
        return {k: v for k, v in counts.items() if v > 0}


class FabricDeleteView(ObjectDeleteView):
    """
    Standard NetBox deletion view for fabric.
    Falls back to SafeFabricDeleteView if there are serialization issues.
    """
    queryset = HedgehogFabric.objects.all()
    
    def post(self, request, *args, **kwargs):
        """Override post to catch serialization errors and fallback to safe deletion"""
        try:
            # Try the normal NetBox deletion flow
            return super().post(request, *args, **kwargs)
        except Exception as e:
            # If we get the hyperlinked serialization error, fall back to safe deletion
            if "Could not resolve URL for hyperlinked relationship" in str(e):
                logger.warning(f"Hyperlinked serialization error detected, falling back to safe deletion: {e}")
                # Redirect to our safe deletion view
                safe_view = SafeFabricDeleteView()
                safe_view.request = request
                return safe_view.post(request, kwargs.get('pk'))
            else:
                # Re-raise other errors
                raise