from netbox.views import generic
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

class FabricEditView(generic.ObjectEditView):
    """Create/edit view for Hedgehog fabrics with GitOps integration"""
    queryset = models.HedgehogFabric.objects.all()
    form = forms.FabricCreationWorkflowForm  # Use GitOps-integrated form
    template_name = 'netbox_hedgehog/fabric_edit.html'
    
    def get_form_kwargs(self):
        """Pass user context to form for Git repository access"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class FabricDeleteView(generic.ObjectDeleteView):
    """Delete view for Hedgehog fabrics"""
    queryset = models.HedgehogFabric.objects.all()
    template_name = 'netbox_hedgehog/fabric_delete.html'