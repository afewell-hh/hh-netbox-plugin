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
    """Create/edit view for Hedgehog fabrics"""
    queryset = models.HedgehogFabric.objects.all()
    form = forms.FabricForm
    template_name = 'netbox_hedgehog/fabric_edit.html'

class FabricDeleteView(generic.ObjectDeleteView):
    """Delete view for Hedgehog fabrics"""
    queryset = models.HedgehogFabric.objects.all()
    template_name = 'netbox_hedgehog/fabric_delete.html'