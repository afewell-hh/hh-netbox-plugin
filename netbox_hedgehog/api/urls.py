from django.urls import path, include
from netbox.api.routers import NetBoxRouter

from . import views
from .sync_endpoints import HCKCSyncView, StateComparisonView
from .gitops_views import (
    GitOpsOnboardingAPIView, GitOpsIngestionAPIView, GitOpsStatusAPIView,
    GitOpsWatcherAPIView, GitOpsGlobalStatusAPIView, GitOpsValidationAPIView
)
# Bidirectional sync imports - ACTIVATED for GitOps system
from .bidirectional_sync_api import (
    DirectoryManagementAPIView, SynchronizationControlAPIView, SyncOperationAPIView,
    ConflictManagementAPIView, ResourceFileMappingAPIView, get_api_urls
)
# from .git_health_views import (
#     GitHealthSummaryView, GitRepositoryHealthDetailView, 
#     GitRepositoryHealthHistoryView, GitConnectionMetricsView, force_health_check
# )  # Temporarily disabled due to git dependency

router = NetBoxRouter()

# Fabric API
router.register('fabrics', views.FabricViewSet)

# Git Repository API (Week 1 GitOps Architecture) - Changed to avoid web UI conflict
router.register('git-repos-api', views.GitRepositoryViewSet)

# GitOps API (MVP2)
router.register('gitops-fabrics', views.EnhancedFabricViewSet, basename='gitopsfabric')
router.register('gitops-resources', views.HedgehogResourceViewSet)

# VPC API CRDs
router.register('vpcs', views.VPCViewSet)
router.register('externals', views.ExternalViewSet)
router.register('external-attachments', views.ExternalAttachmentViewSet)
router.register('external-peerings', views.ExternalPeeringViewSet)
router.register('ipv4-namespaces', views.IPv4NamespaceViewSet)
router.register('vpc-attachments', views.VPCAttachmentViewSet)
router.register('vpc-peerings', views.VPCPeeringViewSet)

# Wiring API CRDs
router.register('connections', views.ConnectionViewSet)
router.register('servers', views.ServerViewSet)
router.register('switches', views.SwitchViewSet)
router.register('switch-groups', views.SwitchGroupViewSet)
router.register('vlan-namespaces', views.VLANNamespaceViewSet)

urlpatterns = router.urls + [
    # Custom endpoints (MVP1)
    path('sync/', views.SyncAPIView.as_view(), name='sync'),
    path('status/', views.StatusAPIView.as_view(), name='status'),
    
    # GitOps endpoints (MVP2)
    path('gitops/', views.GitOpsAPIView.as_view(), name='gitops-global'),
    path('gitops/drift-analysis/', views.DriftAnalysisAPIView.as_view(), name='gitops-drift-analysis'),
    
    # Git Authentication endpoints (MVP2)
    path('git/auth/', views.GitAuthenticationAPIView.as_view(), name='git-authentication'),
    path('git/validate/', views.GitRepositoryValidationAPIView.as_view(), name='git-repository-validation'),
    
    # ArgoCD Setup Wizard endpoints (Week 2 MVP2)
    path('gitops/argocd/prerequisites/', views.ArgoCDPrerequisitesAPIView.as_view(), name='argocd-prerequisites'),
    path('gitops/argocd/setup/', views.ArgoCDSetupAPIView.as_view(), name='argocd-setup'),
    path('gitops/argocd/progress/<str:installation_id>/', views.ArgoCDProgressAPIView.as_view(), name='argocd-progress'),
    path('gitops/test-connection/', views.GitOpsTestConnectionAPIView.as_view(), name='gitops-test-connection'),
    
    # HCKC State Sync endpoints (GitOps Workflow)
    path('gitops-fabrics/<int:fabric_id>/hckc_sync/', HCKCSyncView.as_view(), name='hckc-sync'),
    path('gitops-fabrics/<int:fabric_id>/state-comparison/', StateComparisonView.as_view(), name='state-comparison'),
    
    # GitOps File Management endpoints (MVP2 Enhancement)
    path('fabrics/<int:fabric_id>/init-gitops/', GitOpsOnboardingAPIView.as_view(), name='gitops-init'),
    path('fabrics/<int:fabric_id>/ingest-raw/', GitOpsIngestionAPIView.as_view(), name='gitops-ingest'),
    path('fabrics/<int:fabric_id>/gitops-status/', GitOpsStatusAPIView.as_view(), name='gitops-status'),
    path('fabrics/<int:fabric_id>/watcher/', GitOpsWatcherAPIView.as_view(), name='gitops-watcher'),
    path('fabrics/<int:fabric_id>/validate-gitops/', GitOpsValidationAPIView.as_view(), name='gitops-validate'),
    path('gitops/global-status/', GitOpsGlobalStatusAPIView.as_view(), name='gitops-global-status'),
    
    # Bidirectional Sync endpoints (MVP3) - ACTIVATED for GitOps system
] + get_api_urls() + [
    
    # Git Repository Health Monitoring endpoints (Week 2 Integration) - Temporarily disabled
    # path('git-repositories/health-summary/', GitHealthSummaryView.as_view(), name='git-health-summary'),
    # path('git-repositories/<int:pk>/health-details/', GitRepositoryHealthDetailView.as_view(), name='git-health-details'),
    # path('git-repositories/<int:pk>/health-history/', GitRepositoryHealthHistoryView.as_view(), name='git-health-history'),
    # path('git-repositories/connection-metrics/', GitConnectionMetricsView.as_view(), name='git-connection-metrics'),
    # path('git-repositories/<int:pk>/force-health-check/', force_health_check, name='git-force-health-check'),
]