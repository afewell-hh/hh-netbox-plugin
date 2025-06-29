from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from netbox.api.viewsets import NetBoxModelViewSet

from .. import models
from . import serializers

# Fabric ViewSet
class FabricViewSet(NetBoxModelViewSet):
    queryset = models.HedgehogFabric.objects.all()
    serializer_class = serializers.FabricSerializer

# VPC API ViewSets
class VPCViewSet(NetBoxModelViewSet):
    queryset = models.VPC.objects.all()
    serializer_class = serializers.VPCSerializer

class ExternalViewSet(NetBoxModelViewSet):
    queryset = models.External.objects.all()
    serializer_class = serializers.ExternalSerializer

class ExternalAttachmentViewSet(NetBoxModelViewSet):
    queryset = models.ExternalAttachment.objects.all()
    serializer_class = serializers.ExternalAttachmentSerializer

class ExternalPeeringViewSet(NetBoxModelViewSet):
    queryset = models.ExternalPeering.objects.all()
    serializer_class = serializers.ExternalPeeringSerializer

class IPv4NamespaceViewSet(NetBoxModelViewSet):
    queryset = models.IPv4Namespace.objects.all()
    serializer_class = serializers.IPv4NamespaceSerializer

class VPCAttachmentViewSet(NetBoxModelViewSet):
    queryset = models.VPCAttachment.objects.all()
    serializer_class = serializers.VPCAttachmentSerializer

class VPCPeeringViewSet(NetBoxModelViewSet):
    queryset = models.VPCPeering.objects.all()
    serializer_class = serializers.VPCPeeringSerializer

# Wiring API ViewSets
class ConnectionViewSet(NetBoxModelViewSet):
    queryset = models.Connection.objects.all()
    serializer_class = serializers.ConnectionSerializer

class ServerViewSet(NetBoxModelViewSet):
    queryset = models.Server.objects.all()
    serializer_class = serializers.ServerSerializer

class SwitchViewSet(NetBoxModelViewSet):
    queryset = models.Switch.objects.all()
    serializer_class = serializers.SwitchSerializer

class SwitchGroupViewSet(NetBoxModelViewSet):
    queryset = models.SwitchGroup.objects.all()
    serializer_class = serializers.SwitchGroupSerializer

class VLANNamespaceViewSet(NetBoxModelViewSet):
    queryset = models.VLANNamespace.objects.all()
    serializer_class = serializers.VLANNamespaceSerializer

# Custom API Views
class SyncAPIView(APIView):
    """API endpoint for triggering synchronization"""
    
    def post(self, request):
        # TODO: Implement sync logic
        return Response({
            'status': 'success',
            'message': 'Synchronization initiated'
        }, status=status.HTTP_200_OK)

class StatusAPIView(APIView):
    """API endpoint for checking fabric status"""
    
    def get(self, request):
        # TODO: Implement status checking
        fabrics = models.HedgehogFabric.objects.all()
        return Response({
            'fabrics': len(fabrics),
            'status': 'operational'
        }, status=status.HTTP_200_OK)