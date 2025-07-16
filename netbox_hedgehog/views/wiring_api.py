from netbox.views import generic
from .. import models, tables, forms

# Connection Views
class ConnectionListView(generic.ObjectListView):
    queryset = models.Connection.objects.all()
    table = tables.ConnectionTable
    template_name = 'netbox_hedgehog/connection_list.html'

class ConnectionView(generic.ObjectView):
    queryset = models.Connection.objects.all()
    template_name = 'netbox_hedgehog/connection.html'

class ConnectionEditView(generic.ObjectEditView):
    queryset = models.Connection.objects.all()
    form = forms.ConnectionForm
    template_name = 'netbox_hedgehog/connection_edit.html'
    
    def get(self, request, *args, **kwargs):
        # Check if any fabrics exist before showing the form
        if not models.HedgehogFabric.objects.exists():
            from django.contrib import messages
            messages.error(request, 
                'No fabrics available. You must create a fabric before creating connections. '
                '<a href="/plugins/hedgehog/fabrics/add/">Create a fabric now</a>.',
                extra_tags='safe'
            )
            from django.shortcuts import redirect
            return redirect('plugins:netbox_hedgehog:fabric_list')
        
        return super().get(request, *args, **kwargs)

class ConnectionDeleteView(generic.ObjectDeleteView):
    queryset = models.Connection.objects.all()
    template_name = 'netbox_hedgehog/connection_delete.html'

# Switch Views
class SwitchListView(generic.ObjectListView):
    queryset = models.Switch.objects.all()
    table = tables.SwitchTable
    template_name = 'netbox_hedgehog/switch_list.html'

class SwitchView(generic.ObjectView):
    queryset = models.Switch.objects.all()
    template_name = 'netbox_hedgehog/switch.html'

class SwitchEditView(generic.ObjectEditView):
    queryset = models.Switch.objects.all()
    form = forms.SwitchForm
    template_name = 'netbox_hedgehog/switch_edit.html'
    
    def get(self, request, *args, **kwargs):
        # Check if any fabrics exist before showing the form
        if not models.HedgehogFabric.objects.exists():
            from django.contrib import messages
            messages.error(request, 
                'No fabrics available. You must create a fabric before creating switches. '
                '<a href="/plugins/hedgehog/fabrics/add/">Create a fabric now</a>.',
                extra_tags='safe'
            )
            from django.shortcuts import redirect
            return redirect('plugins:netbox_hedgehog:fabric_list')
        
        return super().get(request, *args, **kwargs)

class SwitchDeleteView(generic.ObjectDeleteView):
    queryset = models.Switch.objects.all()
    template_name = 'netbox_hedgehog/switch_delete.html'

# Server Views
class ServerListView(generic.ObjectListView):
    queryset = models.Server.objects.all()
    table = tables.ServerTable
    template_name = 'netbox_hedgehog/server_list.html'

class ServerView(generic.ObjectView):
    queryset = models.Server.objects.all()
    template_name = 'netbox_hedgehog/server.html'

class ServerEditView(generic.ObjectEditView):
    queryset = models.Server.objects.all()
    form = forms.ServerForm
    template_name = 'netbox_hedgehog/server_edit.html'
    
    def get(self, request, *args, **kwargs):
        # Check if any fabrics exist before showing the form
        if not models.HedgehogFabric.objects.exists():
            from django.contrib import messages
            messages.error(request, 
                'No fabrics available. You must create a fabric before creating servers. '
                '<a href="/plugins/hedgehog/fabrics/add/">Create a fabric now</a>.',
                extra_tags='safe'
            )
            from django.shortcuts import redirect
            return redirect('plugins:netbox_hedgehog:fabric_list')
        
        return super().get(request, *args, **kwargs)

class ServerDeleteView(generic.ObjectDeleteView):
    queryset = models.Server.objects.all()
    template_name = 'netbox_hedgehog/server_delete.html'

# SwitchGroup Views
class SwitchGroupListView(generic.ObjectListView):
    queryset = models.SwitchGroup.objects.all()
    table = tables.SwitchGroupTable
    template_name = 'netbox_hedgehog/switchgroup_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['switchgroups'] = context.get('object_list', [])
        return context

class SwitchGroupView(generic.ObjectView):
    queryset = models.SwitchGroup.objects.all()
    template_name = 'netbox_hedgehog/switchgroup_detail.html'

class SwitchGroupEditView(generic.ObjectEditView):
    queryset = models.SwitchGroup.objects.all()
    form = forms.SwitchGroupForm
    template_name = 'netbox_hedgehog/switchgroup_edit.html'
    
    def get(self, request, *args, **kwargs):
        # Check if any fabrics exist before showing the form
        if not models.HedgehogFabric.objects.exists():
            from django.contrib import messages
            messages.error(request, 
                'No fabrics available. You must create a fabric before creating switch groups. '
                '<a href="/plugins/hedgehog/fabrics/add/">Create a fabric now</a>.',
                extra_tags='safe'
            )
            from django.shortcuts import redirect
            return redirect('plugins:netbox_hedgehog:fabric_list')
        
        return super().get(request, *args, **kwargs)

class SwitchGroupDeleteView(generic.ObjectDeleteView):
    queryset = models.SwitchGroup.objects.all()
    template_name = 'netbox_hedgehog/switchgroup_confirm_delete.html'

# VLANNamespace Views
class VLANNamespaceListView(generic.ObjectListView):
    queryset = models.VLANNamespace.objects.all()
    table = tables.VLANNamespaceTable
    template_name = 'netbox_hedgehog/vlannamespace_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vlannamespaces'] = context.get('object_list', [])
        return context

class VLANNamespaceView(generic.ObjectView):
    queryset = models.VLANNamespace.objects.all()
    template_name = 'netbox_hedgehog/vlannamespace_detail.html'

class VLANNamespaceEditView(generic.ObjectEditView):
    queryset = models.VLANNamespace.objects.all()
    form = forms.VLANNamespaceForm
    template_name = 'netbox_hedgehog/vlannamespace_edit.html'
    
    def get(self, request, *args, **kwargs):
        # Check if any fabrics exist before showing the form
        if not models.HedgehogFabric.objects.exists():
            from django.contrib import messages
            messages.error(request, 
                'No fabrics available. You must create a fabric before creating VLAN namespaces. '
                '<a href="/plugins/hedgehog/fabrics/add/">Create a fabric now</a>.',
                extra_tags='safe'
            )
            from django.shortcuts import redirect
            return redirect('plugins:netbox_hedgehog:fabric_list')
        
        return super().get(request, *args, **kwargs)

class VLANNamespaceDeleteView(generic.ObjectDeleteView):
    queryset = models.VLANNamespace.objects.all()
    template_name = 'netbox_hedgehog/vlannamespace_confirm_delete.html'