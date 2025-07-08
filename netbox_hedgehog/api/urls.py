from django.urls import path, include
from netbox.api.routers import NetBoxRouter

from . import views

router = NetBoxRouter()

# Fabric API
router.register('fabrics', views.FabricViewSet)

# GitOps API (MVP2)
router.register('gitops-fabrics', views.EnhancedFabricViewSet)
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
]