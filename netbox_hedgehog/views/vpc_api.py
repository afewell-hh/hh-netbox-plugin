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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ipv4namespaces'] = context.get('object_list', [])
        return context

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

# ExternalAttachment Views
class ExternalAttachmentListView(generic.ObjectListView):
    queryset = models.ExternalAttachment.objects.all()
    table = tables.ExternalAttachmentTable
    template_name = 'netbox_hedgehog/externalattachment_list.html'

class ExternalAttachmentView(generic.ObjectView):
    queryset = models.ExternalAttachment.objects.all()
    template_name = 'netbox_hedgehog/externalattachment_detail.html'

class ExternalAttachmentEditView(generic.ObjectEditView):
    queryset = models.ExternalAttachment.objects.all()
    form = forms.ExternalAttachmentForm
    template_name = 'netbox_hedgehog/externalattachment_edit.html'

class ExternalAttachmentDeleteView(generic.ObjectDeleteView):
    queryset = models.ExternalAttachment.objects.all()
    template_name = 'netbox_hedgehog/externalattachment_confirm_delete.html'

# ExternalPeering Views
class ExternalPeeringListView(generic.ObjectListView):
    queryset = models.ExternalPeering.objects.all()
    table = tables.ExternalPeeringTable
    template_name = 'netbox_hedgehog/externalpeering_list.html'

class ExternalPeeringView(generic.ObjectView):
    queryset = models.ExternalPeering.objects.all()
    template_name = 'netbox_hedgehog/externalpeering_detail.html'

class ExternalPeeringEditView(generic.ObjectEditView):
    queryset = models.ExternalPeering.objects.all()
    form = forms.ExternalPeeringForm
    template_name = 'netbox_hedgehog/externalpeering_edit.html'

class ExternalPeeringDeleteView(generic.ObjectDeleteView):
    queryset = models.ExternalPeering.objects.all()
    template_name = 'netbox_hedgehog/externalpeering_confirm_delete.html'

# VPCAttachment Views
class VPCAttachmentListView(generic.ObjectListView):
    queryset = models.VPCAttachment.objects.all()
    table = tables.VPCAttachmentTable
    template_name = 'netbox_hedgehog/vpcattachment_list.html'

class VPCAttachmentView(generic.ObjectView):
    queryset = models.VPCAttachment.objects.all()
    template_name = 'netbox_hedgehog/vpcattachment_detail.html'

class VPCAttachmentEditView(generic.ObjectEditView):
    queryset = models.VPCAttachment.objects.all()
    form = forms.VPCAttachmentForm
    template_name = 'netbox_hedgehog/vpcattachment_edit.html'

class VPCAttachmentDeleteView(generic.ObjectDeleteView):
    queryset = models.VPCAttachment.objects.all()
    template_name = 'netbox_hedgehog/vpcattachment_confirm_delete.html'

# VPCPeering Views
class VPCPeeringListView(generic.ObjectListView):
    queryset = models.VPCPeering.objects.all()
    table = tables.VPCPeeringTable
    template_name = 'netbox_hedgehog/vpcpeering_list.html'

class VPCPeeringView(generic.ObjectView):
    queryset = models.VPCPeering.objects.all()
    template_name = 'netbox_hedgehog/vpcpeering_detail.html'

class VPCPeeringEditView(generic.ObjectEditView):
    queryset = models.VPCPeering.objects.all()
    form = forms.VPCPeeringForm
    template_name = 'netbox_hedgehog/vpcpeering_edit.html'

class VPCPeeringDeleteView(generic.ObjectDeleteView):
    queryset = models.VPCPeering.objects.all()
    template_name = 'netbox_hedgehog/vpcpeering_confirm_delete.html'