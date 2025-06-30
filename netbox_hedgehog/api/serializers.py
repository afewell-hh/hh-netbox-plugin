from rest_framework import serializers
from netbox.api.serializers import NetBoxModelSerializer

from .. import models

class FabricSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.HedgehogFabric
        fields = '__all__'

# Alias for NetBox event system
class HedgehogFabricSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.HedgehogFabric
        fields = '__all__'

# VPC API Serializers
class VPCSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.VPC
        fields = '__all__'

class ExternalSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.External
        fields = '__all__'

class ExternalAttachmentSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.ExternalAttachment
        fields = '__all__'

class ExternalPeeringSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.ExternalPeering
        fields = '__all__'

class IPv4NamespaceSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.IPv4Namespace
        fields = '__all__'

class VPCAttachmentSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.VPCAttachment
        fields = '__all__'

class VPCPeeringSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.VPCPeering
        fields = '__all__'

# Wiring API Serializers
class ConnectionSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.Connection
        fields = '__all__'

class ServerSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.Server
        fields = '__all__'

class SwitchSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.Switch
        fields = '__all__'

class SwitchGroupSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.SwitchGroup
        fields = '__all__'

class VLANNamespaceSerializer(NetBoxModelSerializer):
    class Meta:
        model = models.VLANNamespace
        fields = '__all__'