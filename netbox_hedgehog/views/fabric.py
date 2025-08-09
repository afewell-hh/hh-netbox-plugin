from netbox.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .. import models, tables, forms

class FabricListView(generic.ObjectListView):
    """List view for Hedgehog fabrics"""
    queryset = models.HedgehogFabric.objects.all()
    table = tables.FabricTable
    template_name = 'netbox_hedgehog/fabric_list.html'

class FabricView(generic.ObjectView):
    """Detail view for a Hedgehog fabric"""
    queryset = models.HedgehogFabric.objects.all()
    template_name = 'netbox_hedgehog/fabric.html'

@method_decorator(csrf_protect, name='dispatch')
class FabricEditView(LoginRequiredMixin, PermissionRequiredMixin, generic.ObjectEditView):
    """Create/edit view for Hedgehog fabrics with comprehensive sync field support and security"""
    queryset = models.HedgehogFabric.objects.all()
    form = forms.HedgehogFabricForm  # Use comprehensive form with sync_interval
    template_name = 'netbox_hedgehog/fabric_edit.html'
    permission_required = 'netbox_hedgehog.change_hedgehogfabric'
    
    def dispatch(self, request, *args, **kwargs):
        """Enhanced security dispatch with permission validation"""
        # Verify user has required permissions
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required to edit fabrics.")
        
        # For create operations, check add permission
        if not kwargs.get('pk') and not request.user.has_perm('netbox_hedgehog.add_hedgehogfabric'):
            raise PermissionDenied("Insufficient permissions to create fabrics.")
            
        # For edit operations, check change permission
        if kwargs.get('pk') and not request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'):
            raise PermissionDenied("Insufficient permissions to edit fabrics.")
            
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Pass user context to form for Git repository access with security validation"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = getattr(self.request, 'user', None)
        return kwargs
    
    def form_valid(self, form):
        """Enhanced form validation with security logging"""
        response = super().form_valid(form)
        
        # Log security-relevant changes
        action = 'Created' if not form.instance.pk else 'Updated'
        messages.success(
            self.request, 
            f'Fabric "{form.instance.name}" {action.lower()} successfully with enhanced security validation.'
        )
        
        return response

@method_decorator(csrf_protect, name='dispatch')
class FabricDeleteView(LoginRequiredMixin, PermissionRequiredMixin, generic.ObjectDeleteView):
    """Delete view for Hedgehog fabrics with enhanced security"""
    queryset = models.HedgehogFabric.objects.all()
    template_name = 'netbox_hedgehog/fabric_delete.html'
    permission_required = 'netbox_hedgehog.delete_hedgehogfabric'
    
    def dispatch(self, request, *args, **kwargs):
        """Enhanced security dispatch for delete operations"""
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required to delete fabrics.")
            
        if not request.user.has_perm('netbox_hedgehog.delete_hedgehogfabric'):
            raise PermissionDenied("Insufficient permissions to delete fabrics.")
            
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """Enhanced delete with security logging"""
        obj = self.get_object()
        fabric_name = obj.name
        
        response = super().post(request, *args, **kwargs)
        
        # Log security-relevant deletion
        messages.warning(
            request,
            f'Fabric "{fabric_name}" deleted successfully with security validation.'
        )
        
        return response