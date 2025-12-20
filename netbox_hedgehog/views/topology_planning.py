"""
Topology Planning Views (DIET Module)
CRUD views for BreakoutOption and DeviceTypeExtension models.
"""

from netbox.views import generic
from .. import models, tables, forms


# BreakoutOption Views
class BreakoutOptionListView(generic.ObjectListView):
    """List view for BreakoutOptions"""
    queryset = models.BreakoutOption.objects.all()
    table = tables.BreakoutOptionTable
    template_name = 'netbox_hedgehog/topology_planning/breakoutoption_list.html'


class BreakoutOptionView(generic.ObjectView):
    """Detail view for a single BreakoutOption"""
    queryset = models.BreakoutOption.objects.all()
    template_name = 'netbox_hedgehog/topology_planning/breakoutoption.html'


class BreakoutOptionEditView(generic.ObjectEditView):
    """Create/Edit view for BreakoutOptions"""
    queryset = models.BreakoutOption.objects.all()
    form = forms.BreakoutOptionForm
    template_name = 'netbox_hedgehog/topology_planning/breakoutoption_edit.html'


class BreakoutOptionDeleteView(generic.ObjectDeleteView):
    """Delete view for BreakoutOptions"""
    queryset = models.BreakoutOption.objects.all()
    template_name = 'netbox_hedgehog/topology_planning/breakoutoption_delete.html'


# DeviceTypeExtension Views
class DeviceTypeExtensionListView(generic.ObjectListView):
    """List view for DeviceTypeExtensions"""
    queryset = models.DeviceTypeExtension.objects.all()
    table = tables.DeviceTypeExtensionTable
    template_name = 'netbox_hedgehog/topology_planning/devicetypeextension_list.html'


class DeviceTypeExtensionView(generic.ObjectView):
    """Detail view for a single DeviceTypeExtension"""
    queryset = models.DeviceTypeExtension.objects.all()
    template_name = 'netbox_hedgehog/topology_planning/devicetypeextension.html'


class DeviceTypeExtensionEditView(generic.ObjectEditView):
    """Create/Edit view for DeviceTypeExtensions"""
    queryset = models.DeviceTypeExtension.objects.all()
    form = forms.DeviceTypeExtensionForm
    template_name = 'netbox_hedgehog/topology_planning/devicetypeextension_edit.html'


class DeviceTypeExtensionDeleteView(generic.ObjectDeleteView):
    """Delete view for DeviceTypeExtensions"""
    queryset = models.DeviceTypeExtension.objects.all()
    template_name = 'netbox_hedgehog/topology_planning/devicetypeextension_delete.html'
