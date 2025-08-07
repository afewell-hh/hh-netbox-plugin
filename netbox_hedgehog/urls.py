from django.urls import path
from django.views.generic import TemplateView, ListView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django import forms

# Minimal safe imports
from .models import HedgehogFabric, GitRepository
from .models.vpc_api import VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering
from .models.wiring_api import Connection, Switch, Server, VLANNamespace, SwitchGroup
from .views.crd_views import FabricCRDListView
from .views import gitops_edit_views
from .views.sync_views import FabricTestConnectionView, FabricGitHubSyncView
from .views.fabric_views import FabricSyncView
from netbox.views import generic

# Import fabric views
from .views.fabric_views import FabricCreateView, FabricEditView as ProperFabricEditView
from .views.debug_edit_view import DebugFabricEditView

# Import git repository views - temporarily disabled to test
# from .views.git_repository_views import GitRepositoryListView as ProperGitRepositoryListView, GitRepositoryView

# Import drift dashboard views
from .views.drift_dashboard import (
    DriftDetectionDashboardView,
    FabricDriftDetailView,
    DriftAnalysisAPIView
)

app_name = 'netbox_hedgehog'

# Working views from git history
class OverviewView(TemplateView):
    template_name = 'netbox_hedgehog/overview.html'
    
    def get_context_data(self, **kwargs):
        print("DEBUG: OverviewView.get_context_data() called")
        context = super().get_context_data(**kwargs)
        
        # Debug: Print to help track down the issue
        import logging
        logger = logging.getLogger('netbox_hedgehog')
        
        # Initialize safe defaults first
        context['fabric_count'] = 0
        context['recent_fabrics'] = []
        context['vpc_count'] = 0
        # Initialize GitOps stats - will be calculated below
        context['gitops_stats'] = {
            'in_sync_count': 0,
            'drift_detected_count': 0
        }
        
        # Try each section individually to isolate issues
        try:
            # Fabric statistics
            fabric_count = HedgehogFabric.objects.count()
            context['fabric_count'] = fabric_count
            context['recent_fabrics'] = HedgehogFabric.objects.order_by('-created')[:5]
            logger.info(f"Fabric count set successfully: {fabric_count}")
        except Exception as e:
            logger.error(f"Error getting fabric count: {e}")
            context['fabric_count'] = 0
        
        try:
            # VPC statistics
            vpc_count = VPC.objects.count()
            context['vpc_count'] = vpc_count
            logger.info(f"VPC count set successfully: {vpc_count}")
                
        except Exception as e:
            logger.error(f"Error getting VPC count: {e}")
            context['vpc_count'] = 0
        
        try:
            # GitOps sync statistics - calculate real sync status
            fabrics = HedgehogFabric.objects.all()
            in_sync_count = 0
            drift_detected_count = 0
            
            for fabric in fabrics:
                # Check fabric sync status using actual SyncStatusChoices values
                if hasattr(fabric, 'sync_status'):
                    sync_status = fabric.sync_status
                    # Based on SyncStatusChoices: 'in_sync', 'out_of_sync', 'syncing', 'error', 'never_synced'
                    if sync_status == 'in_sync' or sync_status == 'syncing':
                        in_sync_count += 1
                    elif sync_status == 'error' or sync_status == 'out_of_sync':
                        drift_detected_count += 1
                    # 'never_synced' counts as neither in sync nor drift - just not counted
                
                logger.info(f"Fabric {fabric.name}: sync_status={fabric.sync_status}, connection_status={getattr(fabric, 'connection_status', 'N/A')}")
            
            # Update context with real values
            context['gitops_stats'] = {
                'in_sync_count': in_sync_count,
                'drift_detected_count': drift_detected_count
            }
            logger.info(f"Sync status calculated: {in_sync_count} in sync, {drift_detected_count} drift detected")
            
        except Exception as e:
            logger.error(f"Error calculating sync status: {e}")
            # Keep default values of 0 if calculation fails
        
        # Final validation  
        print(f"DEBUG SYNC: Final context - in_sync: {context['gitops_stats']['in_sync_count']}, drift: {context['gitops_stats']['drift_detected_count']}")
        logger.info(f"Final context: fabric_count={context.get('fabric_count')}, vpc_count={context.get('vpc_count')}")
        
        return context

class FabricListView(ListView):
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_list_simple.html'
    context_object_name = 'fabrics'
    paginate_by = 25

class FabricDetailView(DetailView):
    model = HedgehogFabric
    template_name = 'netbox_hedgehog/fabric_detail_simple.html'
    context_object_name = 'object'

# FabricEditView is now imported from views.fabric_views


# Git Repository Views - Inline working implementation
class WorkingGitRepositoryListView(LoginRequiredMixin, TemplateView):
    """Working inline Git repository list view"""
    template_name = 'netbox_hedgehog/git_repository_list.html'
    
    def get_context_data(self, **kwargs):
        print("DEBUG: WorkingGitRepositoryListView.get_context_data() called")
        context = super().get_context_data(**kwargs)
        repos = GitRepository.objects.all()
        print(f"DEBUG: Found {repos.count()} repositories")
        for repo in repos:
            print(f"DEBUG: - {repo.name}: {repo.url}")
        context['object_list'] = repos
        context['repositories'] = repos
        context['title'] = 'Git Repositories'
        print(f"DEBUG: Template being used: {self.template_name}")
        return context

class GitRepositoryDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'netbox_hedgehog/git_repository_detail_simple.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get repository manually for debugging
        try:
            repo_id = self.kwargs.get('pk')
            repository = GitRepository.objects.get(pk=repo_id)
            context['object'] = repository
            context['repository'] = repository
            
            # Add minimal context
            context['dependent_fabrics'] = []
            context['connection_summary'] = {}
            context['can_delete'] = True
            context['delete_reason'] = 'Debug mode'
            
            print(f"DEBUG: Successfully loaded repository {repository.name}")
            
        except Exception as e:
            print(f"DEBUG: Failed to load repository: {e}")
            context['object'] = None
            context['repository'] = None
            context['error'] = str(e)
        
        return context

# Simple CR List Views
class VPCListView(LoginRequiredMixin, ListView):
    model = VPC
    template_name = 'netbox_hedgehog/vpc_list_simple.html'
    context_object_name = 'vpcs'
    paginate_by = 25

class ConnectionListView(LoginRequiredMixin, ListView):
    model = Connection
    template_name = 'netbox_hedgehog/connection_list_simple.html'
    context_object_name = 'connections'
    paginate_by = 25

class SwitchListView(LoginRequiredMixin, ListView):
    model = Switch
    template_name = 'netbox_hedgehog/switch_list_simple.html'
    context_object_name = 'switches'
    paginate_by = 25

class ServerListView(ListView):
    model = Server
    template_name = 'netbox_hedgehog/server_list.html'
    context_object_name = 'servers'
    paginate_by = 25

class VLANNamespaceListView(ListView):
    model = VLANNamespace
    template_name = 'netbox_hedgehog/vlannamespace_list.html'
    context_object_name = 'vlannamespaces'
    paginate_by = 25

class SwitchGroupListView(TemplateView):
    template_name = 'netbox_hedgehog/switchgroup_list.html'
    
    def get_context_data(self, **kwargs):
        """Simple query with optional fabric filtering"""
        from .models.fabric import HedgehogFabric
        
        context = super().get_context_data(**kwargs)
        
        # Get all SwitchGroups, optionally filtered by fabric
        switchgroups = SwitchGroup.objects.all()
        fabric_id = self.request.GET.get('fabric')
        selected_fabric = None
        
        if fabric_id:
            try:
                selected_fabric = HedgehogFabric.objects.get(pk=fabric_id)
                switchgroups = switchgroups.filter(fabric=selected_fabric)
            except (ValueError, HedgehogFabric.DoesNotExist):
                # Invalid fabric ID - show all
                pass
        
        context['switchgroups'] = switchgroups
        context['selected_fabric'] = selected_fabric
        context['fabric_filter_id'] = fabric_id
        context['all_fabrics'] = HedgehogFabric.objects.all().order_by('name')
        context['show_fabric_filter'] = True
        
        return context

# VPC API ListView classes
class ExternalListView(ListView):
    model = External
    template_name = 'netbox_hedgehog/external_list.html'
    context_object_name = 'externals'
    paginate_by = 25

class ExternalAttachmentListView(ListView):
    model = ExternalAttachment
    template_name = 'netbox_hedgehog/externalattachment_list.html'
    context_object_name = 'externalattachments'
    paginate_by = 25

class ExternalPeeringListView(ListView):
    model = ExternalPeering
    template_name = 'netbox_hedgehog/externalpeering_list.html'
    context_object_name = 'externalpeerings'
    paginate_by = 25

class IPv4NamespaceListView(ListView):
    model = IPv4Namespace
    template_name = 'netbox_hedgehog/ipv4namespace_list.html'
    context_object_name = 'ipv4namespaces'
    paginate_by = 25

class VPCAttachmentListView(ListView):
    model = VPCAttachment
    template_name = 'netbox_hedgehog/vpcattachment_list.html'
    context_object_name = 'vpcattachments'
    paginate_by = 25

class VPCPeeringListView(ListView):
    model = VPCPeering
    template_name = 'netbox_hedgehog/vpcpeering_list.html'
    context_object_name = 'vpcpeerings'
    paginate_by = 25

# Simple CR Detail Views
class VPCDetailView(DetailView):
    model = VPC
    template_name = 'netbox_hedgehog/vpc_detail_simple.html'
    context_object_name = 'object'

class ConnectionDetailView(DetailView):
    model = Connection
    template_name = 'netbox_hedgehog/connection_detail_simple.html'
    context_object_name = 'object'

class SwitchDetailView(DetailView):
    model = Switch
    template_name = 'netbox_hedgehog/switch_detail_simple.html'
    context_object_name = 'object'

class ServerDetailView(DetailView):
    model = Server
    template_name = 'netbox_hedgehog/server_detail.html'
    context_object_name = 'object'

class VLANNamespaceDetailView(DetailView):
    model = VLANNamespace
    template_name = 'netbox_hedgehog/vlannamespace_detail.html'
    context_object_name = 'object'

class SwitchGroupDetailView(DetailView):
    model = SwitchGroup
    template_name = 'netbox_hedgehog/switchgroup_detail.html'
    context_object_name = 'object'

# VPC API DetailView classes
class ExternalDetailView(DetailView):
    model = External
    template_name = 'netbox_hedgehog/external_detail.html'
    context_object_name = 'object'

class ExternalAttachmentDetailView(DetailView):
    model = ExternalAttachment
    template_name = 'netbox_hedgehog/externalattachment_detail.html'
    context_object_name = 'object'

class ExternalPeeringDetailView(DetailView):
    model = ExternalPeering
    template_name = 'netbox_hedgehog/externalpeering_detail.html'
    context_object_name = 'object'

class IPv4NamespaceDetailView(DetailView):
    model = IPv4Namespace
    template_name = 'netbox_hedgehog/ipv4namespace_detail.html'
    context_object_name = 'object'

class VPCAttachmentDetailView(DetailView):
    model = VPCAttachment
    template_name = 'netbox_hedgehog/vpcattachment_detail.html'
    context_object_name = 'object'

class VPCPeeringDetailView(DetailView):
    model = VPCPeering
    template_name = 'netbox_hedgehog/vpcpeering_detail.html'
    context_object_name = 'object'

# Simple placeholder for other pages
class PlaceholderView(TemplateView):
    template_name = 'netbox_hedgehog/simple_placeholder.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = getattr(self, 'page_title', 'Page')
        context['message'] = "System recovered - this page is being restored progressively"
        return context

# URL patterns
urlpatterns = [
    
    # Test URL to verify basic routing works
    path('test-repos/', TemplateView.as_view(template_name='netbox_hedgehog/overview.html'), name='test_repositories'),
    
    # New simple test
    path('simple-test/', TemplateView.as_view(template_name='netbox_hedgehog/overview.html'), name='simple_test'),
    
    # Brand new URL to bypass any caching - unique timestamp suffix
    path('git-repos-v2-20250728/', WorkingGitRepositoryListView.as_view(), name='gitrepository_list_v2'),
    
    # Debug Git Repos URL - Disabled due to import issues
    # path('debug-git-repos/', ProperGitRepositoryListView.as_view(), name='debug_git_repos'),
    
    # Debug test - using WorkingGitRepositoryListView instead of overview
    path('debug-test/', WorkingGitRepositoryListView.as_view(), name='debug_test'),
    
    # Test with a working model (HedgehogFabric) using the same URL pattern
    path('test-working-list/', ListView.as_view(model=HedgehogFabric, template_name='netbox_hedgehog/fabric_list_simple.html', context_object_name='fabrics'), name='test_working_list'),
    
    # Git Repository Management URLs - Using the working implementation
    path('git-repositories/', WorkingGitRepositoryListView.as_view(), name='gitrepository_list'),
    path('repositories/', WorkingGitRepositoryListView.as_view(), name='gitrepository_list_alt'),
    path('git-repositories/<int:pk>/', GitRepositoryDetailView.as_view(), name='gitrepository_detail'),
    path('git-repositories/<int:pk>/test-connection/', TemplateView.as_view(template_name='netbox_hedgehog/git_repository_detail_simple.html'), name='gitrepository_test_connection'),
    
    # Debug URL to test if specific pattern is the issue
    path('debug-repo-detail/', TemplateView.as_view(template_name='netbox_hedgehog/overview.html'), name='debug_repo_detail'),
    
    # Core working pages
    path('', OverviewView.as_view(), name='overview'),
    path('fabrics/', FabricListView.as_view(), name='fabric_list'),
    path('fabrics/add/', FabricCreateView.as_view(), name='fabric_add'),
    path('fabrics/<int:pk>/', FabricDetailView.as_view(), name='fabric_detail'),
    path('fabrics/<int:pk>/edit-test/', ProperFabricEditView.as_view(), name='fabric_edit_test'),
    path('fabrics/<int:pk>/edit/', ProperFabricEditView.as_view(), name='fabric_edit'),
    path('fabrics/<int:pk>/debug-edit/', DebugFabricEditView.as_view(), name='fabric_debug_edit'),
    path('fabrics/<int:pk>/delete/', TemplateView.as_view(template_name='netbox_hedgehog/overview.html'), name='fabric_delete'),
    path('fabrics/<int:pk>/crds/', FabricCRDListView.as_view(), name='fabric_crds'),
    path('fabrics/<int:pk>/test-connection/', FabricTestConnectionView.as_view(), name='fabric_test_connection'),
    path('fabrics/<int:pk>/sync/', FabricSyncView.as_view(), name='fabric_sync'),
    path('fabrics/<int:pk>/github-sync/', FabricGitHubSyncView.as_view(), name='fabric_github_sync'),
    
    # Drift Detection Dashboard
    path('drift-detection/', DriftDetectionDashboardView.as_view(), name='drift_dashboard'),
    path('drift-detection/fabric/<int:fabric_id>/', FabricDriftDetailView.as_view(), name='fabric_drift_detail'),
    path('api/drift-analysis/', DriftAnalysisAPIView.as_view(), name='drift_analysis_api'),
    
    # CR List pages
    path('vpcs/', VPCListView.as_view(), name='vpc_list'),
    path('vpcs/<int:pk>/', VPCDetailView.as_view(), name='vpc_detail'),
    path('connections/', ConnectionListView.as_view(), name='connection_list'),
    path('connections/<int:pk>/', ConnectionDetailView.as_view(), name='connection_detail'),
    path('switches/', SwitchListView.as_view(), name='switch_list'),
    path('switches/<int:pk>/', SwitchDetailView.as_view(), name='switch_detail'),
    path('servers/', ServerListView.as_view(), name='server_list'),
    path('servers/<int:pk>/', ServerDetailView.as_view(), name='server_detail'),
    path('vlan-namespaces/', VLANNamespaceListView.as_view(), name='vlannamespace_list'),
    path('vlan-namespaces/<int:pk>/', VLANNamespaceDetailView.as_view(), name='vlannamespace_detail'),
    path('switch-groups/', SwitchGroupListView.as_view(), name='switchgroup_list'),
    path('switch-groups/<int:pk>/', SwitchGroupDetailView.as_view(), name='switchgroup_detail'),
    
    # VPC API CR pages
    path('externals/', ExternalListView.as_view(), name='external_list'),
    path('externals/<int:pk>/', ExternalDetailView.as_view(), name='external_detail'),
    path('external-attachments/', ExternalAttachmentListView.as_view(), name='externalattachment_list'),
    path('external-attachments/<int:pk>/', ExternalAttachmentDetailView.as_view(), name='externalattachment_detail'),
    path('external-peerings/', ExternalPeeringListView.as_view(), name='externalpeering_list'),
    path('external-peerings/<int:pk>/', ExternalPeeringDetailView.as_view(), name='externalpeering_detail'),
    path('ipv4namespaces/', IPv4NamespaceListView.as_view(), name='ipv4namespace_list'),
    path('ipv4namespaces/<int:pk>/', IPv4NamespaceDetailView.as_view(), name='ipv4namespace_detail'),
    path('vpc-attachments/', VPCAttachmentListView.as_view(), name='vpcattachment_list'),
    path('vpc-attachments/<int:pk>/', VPCAttachmentDetailView.as_view(), name='vpcattachment_detail'),
    path('vpc-peerings/', VPCPeeringListView.as_view(), name='vpcpeering_list'),
    path('vpc-peerings/<int:pk>/', VPCPeeringDetailView.as_view(), name='vpcpeering_detail'),
    
    # GitOps Edit URLs
    path('gitops/vpcs/<int:pk>/edit/', gitops_edit_views.GitOpsVPCEditView.as_view(), name='gitops_vpc_edit'),
    path('gitops/externals/<int:pk>/edit/', gitops_edit_views.GitOpsExternalEditView.as_view(), name='gitops_external_edit'),
    path('gitops/external-attachments/<int:pk>/edit/', gitops_edit_views.GitOpsExternalAttachmentEditView.as_view(), name='gitops_externalattachment_edit'),
    path('gitops/external-peerings/<int:pk>/edit/', gitops_edit_views.GitOpsExternalPeeringEditView.as_view(), name='gitops_externalpeering_edit'),
    path('gitops/ipv4namespaces/<int:pk>/edit/', gitops_edit_views.GitOpsIPv4NamespaceEditView.as_view(), name='gitops_ipv4namespace_edit'),
    path('gitops/vpc-attachments/<int:pk>/edit/', gitops_edit_views.GitOpsVPCAttachmentEditView.as_view(), name='gitops_vpcattachment_edit'),
    path('gitops/vpc-peerings/<int:pk>/edit/', gitops_edit_views.GitOpsVPCPeeringEditView.as_view(), name='gitops_vpcpeering_edit'),
    path('gitops/connections/<int:pk>/edit/', gitops_edit_views.GitOpsConnectionEditView.as_view(), name='gitops_connection_edit'),
    path('gitops/servers/<int:pk>/edit/', gitops_edit_views.GitOpsServerEditView.as_view(), name='gitops_server_edit'),
    path('gitops/switches/<int:pk>/edit/', gitops_edit_views.GitOpsSwitchEditView.as_view(), name='gitops_switch_edit'),
    path('gitops/switch-groups/<int:pk>/edit/', gitops_edit_views.GitOpsSwitchGroupEditView.as_view(), name='gitops_switchgroup_edit'),
    path('gitops/vlan-namespaces/<int:pk>/edit/', gitops_edit_views.GitOpsVLANNamespaceEditView.as_view(), name='gitops_vlannamespace_edit'),
    
    # GitOps API endpoints
    path('api/gitops/yaml-preview/', gitops_edit_views.YAMLPreviewView.as_view(), name='gitops_yaml_preview'),
    path('api/gitops/yaml-validation/', gitops_edit_views.YAMLValidationView.as_view(), name='gitops_yaml_validation'),
    path('api/gitops/workflow-status/<str:model_name>/<int:object_id>/', gitops_edit_views.GitOpsWorkflowStatusView.as_view(), name='gitops_workflow_status'),
    
    # Additional git repository URLs moved to top section
]

# Add remaining placeholder pages for navigation
placeholder_pages = [
    ('gitops-onboarding/', 'gitops_onboarding', 'GitOps Onboarding'),
    ('vpcs/add/', 'vpc_add', 'Add VPC'),
    ('externals/', 'external_list', 'External Systems'),
    ('externals/add/', 'external_add', 'Add External System'),
    ('ipv4namespaces/', 'ipv4namespace_list', 'IPv4 Namespaces'),
    ('ipv4namespaces/add/', 'ipv4namespace_add', 'Add IPv4 Namespace'),
    ('external-attachments/', 'externalattachment_list', 'External Attachments'),
    ('external-attachments/add/', 'externalattachment_add', 'Add External Attachment'),
    ('external-peerings/', 'externalpeering_list', 'External Peerings'),
    ('external-peerings/add/', 'externalpeering_add', 'Add External Peering'),
    ('vpc-attachments/', 'vpcattachment_list', 'VPC Attachments'),
    ('vpc-attachments/add/', 'vpcattachment_add', 'Add VPC Attachment'),
    ('vpc-peerings/', 'vpcpeering_list', 'VPC Peerings'),
    ('vpc-peerings/add/', 'vpcpeering_add', 'Add VPC Peering'),
    ('connections/add/', 'connection_add', 'Add Connection'),
    ('switches/add/', 'switch_add', 'Add Switch'),
    ('servers/add/', 'server_add', 'Add Server'),
    ('servers/<int:pk>/', 'server_detail', 'Server Details'),
    ('switch-groups/add/', 'switchgroup_add', 'Add Switch Group'),
    ('switch-groups/<int:pk>/', 'switchgroup_detail', 'Switch Group Details'),
    ('vlan-namespaces/add/', 'vlannamespace_add', 'Add VLAN Namespace'),
    ('vlan-namespaces/<int:pk>/', 'vlannamespace_detail', 'VLAN Namespace Details'),
]

for url, name, title in placeholder_pages:
    view_class = type(f'{name}View', (PlaceholderView,), {'page_title': title})
    urlpatterns.append(path(url, view_class.as_view(), name=name))