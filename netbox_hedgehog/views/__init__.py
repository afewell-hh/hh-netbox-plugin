# Simplified views for initial plugin loading
from django.shortcuts import render
from django.views.generic import TemplateView

class FabricOverviewView(TemplateView):
    template_name = 'netbox_hedgehog/simple_dashboard.html'

# Add minimal stub views for URLs
class FabricListView(TemplateView):
    template_name = 'netbox_hedgehog/simple_list.html'
    
class FabricCreateView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'
    
class FabricDetailView(TemplateView):
    template_name = 'netbox_hedgehog/simple_detail.html'
    
class FabricEditView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'
    
class FabricDeleteView(TemplateView):
    template_name = 'netbox_hedgehog/simple_confirm.html'

class FabricTestConnectionView(TemplateView):
    template_name = 'netbox_hedgehog/simple_result.html'

class FabricSyncView(TemplateView):
    template_name = 'netbox_hedgehog/simple_result.html'

class FabricOnboardingView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'

class FabricBulkActionsView(TemplateView):
    template_name = 'netbox_hedgehog/simple_result.html'

# More stub views for URLs to work
class VPCListView(TemplateView):
    template_name = 'netbox_hedgehog/simple_list.html'

class VPCDetailView(TemplateView):
    template_name = 'netbox_hedgehog/simple_detail.html'
    
class VPCCreateView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'

class VPCApplyView(TemplateView):
    template_name = 'netbox_hedgehog/simple_result.html'

class VPCDeleteView(TemplateView):
    template_name = 'netbox_hedgehog/simple_confirm.html'

class VPCBulkActionsView(TemplateView):
    template_name = 'netbox_hedgehog/simple_result.html'

# Add other required stub views
class SwitchListView(TemplateView):
    template_name = 'netbox_hedgehog/simple_list.html'

class SwitchDetailView(TemplateView):
    template_name = 'netbox_hedgehog/simple_detail.html'

class ConnectionListView(TemplateView):
    template_name = 'netbox_hedgehog/simple_list.html'

class ConnectionDetailView(TemplateView):
    template_name = 'netbox_hedgehog/simple_detail.html'

class TopologyView(TemplateView):
    template_name = 'netbox_hedgehog/simple_dashboard.html'

class VLANNamespaceListView(TemplateView):
    template_name = 'netbox_hedgehog/simple_list.html'

class VLANNamespaceDetailView(TemplateView):
    template_name = 'netbox_hedgehog/simple_detail.html'

# Add stubs for all the other views referenced in URLs
class SwitchCreateView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'

class SwitchEditView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'

class SwitchDeleteView(TemplateView):
    template_name = 'netbox_hedgehog/simple_confirm.html'

class SwitchBulkActionsView(TemplateView):
    template_name = 'netbox_hedgehog/simple_result.html'

class ConnectionCreateView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'

class ConnectionEditView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'

class ConnectionDeleteView(TemplateView):
    template_name = 'netbox_hedgehog/simple_confirm.html'

class ConnectionBulkActionsView(TemplateView):
    template_name = 'netbox_hedgehog/simple_result.html'

class VLANNamespaceCreateView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'

class VLANNamespaceEditView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'

class VLANNamespaceDeleteView(TemplateView):
    template_name = 'netbox_hedgehog/simple_confirm.html'

class VLANNamespaceBulkActionsView(TemplateView):
    template_name = 'netbox_hedgehog/simple_result.html'

# Legacy views - add stubs
class ExternalListView(TemplateView):
    template_name = 'netbox_hedgehog/simple_list.html'

class ExternalView(TemplateView):
    template_name = 'netbox_hedgehog/simple_detail.html'

class ExternalEditView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'

class ExternalDeleteView(TemplateView):
    template_name = 'netbox_hedgehog/simple_confirm.html'

class IPv4NamespaceListView(TemplateView):
    template_name = 'netbox_hedgehog/simple_list.html'

class IPv4NamespaceView(TemplateView):
    template_name = 'netbox_hedgehog/simple_detail.html'

class IPv4NamespaceEditView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'

class IPv4NamespaceDeleteView(TemplateView):
    template_name = 'netbox_hedgehog/simple_confirm.html'

class ServerListView(TemplateView):
    template_name = 'netbox_hedgehog/simple_list.html'

class ServerView(TemplateView):
    template_name = 'netbox_hedgehog/simple_detail.html'

class ServerEditView(TemplateView):
    template_name = 'netbox_hedgehog/simple_form.html'

class ServerDeleteView(TemplateView):
    template_name = 'netbox_hedgehog/simple_confirm.html'

class CRDCatalogView(TemplateView):
    template_name = 'netbox_hedgehog/simple_dashboard.html'

class SyncAllView(TemplateView):
    template_name = 'netbox_hedgehog/simple_result.html'

# All views are available for import