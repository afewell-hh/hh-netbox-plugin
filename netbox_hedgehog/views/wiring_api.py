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

class ServerDeleteView(generic.ObjectDeleteView):
    queryset = models.Server.objects.all()
    template_name = 'netbox_hedgehog/server_delete.html'