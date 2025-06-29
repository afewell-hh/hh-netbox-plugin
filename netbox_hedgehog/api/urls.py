from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

# Fabric API
router.register('fabrics', views.FabricViewSet)

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

app_name = 'netbox_hedgehog-api'

urlpatterns = [
    path('', include(router.urls)),
    # Custom endpoints
    path('sync/', views.SyncAPIView.as_view(), name='sync'),
    path('status/', views.StatusAPIView.as_view(), name='status'),
]