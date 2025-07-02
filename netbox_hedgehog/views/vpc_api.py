from netbox.views import generic
from .. import models, tables, forms

# VPC Views
class VPCListView(generic.ObjectListView):
    queryset = models.VPC.objects.all()
    table = tables.VPCTable
    template_name = 'netbox_hedgehog/vpc_list.html'

class VPCView(generic.ObjectView):
    queryset = models.VPC.objects.all()
    template_name = 'netbox_hedgehog/vpc.html'

class VPCEditView(generic.ObjectEditView):
    queryset = models.VPC.objects.all()
    form = forms.VPCForm
    template_name = 'netbox_hedgehog/vpc_edit.html'

class VPCDeleteView(generic.ObjectDeleteView):
    queryset = models.VPC.objects.all()
    template_name = 'netbox_hedgehog/vpc_delete.html'

# External Views
class ExternalListView(generic.ObjectListView):
    queryset = models.External.objects.all()
    table = tables.ExternalTable
    template_name = 'netbox_hedgehog/external_list.html'

class ExternalView(generic.ObjectView):
    queryset = models.External.objects.all()
    template_name = 'netbox_hedgehog/external_detail.html'

class ExternalEditView(generic.ObjectEditView):
    queryset = models.External.objects.all()
    form = forms.ExternalForm
    template_name = 'netbox_hedgehog/external_edit.html'

class ExternalDeleteView(generic.ObjectDeleteView):
    queryset = models.External.objects.all()
    template_name = 'netbox_hedgehog/external_confirm_delete.html'

# IPv4Namespace Views
class IPv4NamespaceListView(generic.ObjectListView):
    queryset = models.IPv4Namespace.objects.all()
    table = tables.IPv4NamespaceTable
    template_name = 'netbox_hedgehog/ipv4namespace_list.html'

class IPv4NamespaceView(generic.ObjectView):
    queryset = models.IPv4Namespace.objects.all()
    template_name = 'netbox_hedgehog/ipv4namespace_detail.html'

class IPv4NamespaceEditView(generic.ObjectEditView):
    queryset = models.IPv4Namespace.objects.all()
    form = forms.IPv4NamespaceForm
    template_name = 'netbox_hedgehog/ipv4namespace_edit.html'

class IPv4NamespaceDeleteView(generic.ObjectDeleteView):
    queryset = models.IPv4Namespace.objects.all()
    template_name = 'netbox_hedgehog/ipv4namespace_confirm_delete.html'