from rest_framework import serializers
from netbox.api.serializers import NetBoxModelSerializer

from .. import models

class BaseCRDSerializer(NetBoxModelSerializer):
    """Base serializer for CRD models that disables hyperlinked relationships"""
    fabric = serializers.PrimaryKeyRelatedField(queryset=models.HedgehogFabric.objects.all())
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Disable hyperlinked relationships to prevent view name resolution errors
        for field_name, field in self.fields.items():
            if hasattr(field, 'view_name'):
                field.view_name = None

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
class VPCSerializer(BaseCRDSerializer):
    class Meta:
        model = models.VPC
        fields = '__all__'

class ExternalSerializer(BaseCRDSerializer):
    class Meta:
        model = models.External
        fields = '__all__'

class ExternalAttachmentSerializer(BaseCRDSerializer):
    class Meta:
        model = models.ExternalAttachment
        fields = '__all__'

class ExternalPeeringSerializer(BaseCRDSerializer):
    class Meta:
        model = models.ExternalPeering
        fields = '__all__'

class IPv4NamespaceSerializer(BaseCRDSerializer):
    class Meta:
        model = models.IPv4Namespace
        fields = '__all__'

class VPCAttachmentSerializer(BaseCRDSerializer):
    class Meta:
        model = models.VPCAttachment
        fields = '__all__'

class VPCPeeringSerializer(BaseCRDSerializer):
    class Meta:
        model = models.VPCPeering
        fields = '__all__'

# Wiring API Serializers
class ConnectionSerializer(BaseCRDSerializer):
    class Meta:
        model = models.Connection
        fields = '__all__'

class ServerSerializer(BaseCRDSerializer):
    class Meta:
        model = models.Server
        fields = '__all__'

class SwitchSerializer(BaseCRDSerializer):
    class Meta:
        model = models.Switch
        fields = '__all__'

class SwitchGroupSerializer(BaseCRDSerializer):
    class Meta:
        model = models.SwitchGroup
        fields = '__all__'

class VLANNamespaceSerializer(BaseCRDSerializer):
    class Meta:
        model = models.VLANNamespace
        fields = '__all__'


# =============================================================================
# Topology Planning Serializers (DIET Module)
# =============================================================================
# Import simple serializers (no REST API views yet, just needed for events/webhooks)
from .serializers_simple import (
    BreakoutOptionSerializer,
    DeviceTypeExtensionSerializer,
    TopologyPlanSerializer,
    PlanServerClassSerializer,
    PlanServerNICSerializer,
    PlanSwitchClassSerializer,
    PlanServerConnectionSerializer,
    PlanMCLAGDomainSerializer,
    SwitchPortZoneSerializer,
)


class PlanLocalityRangeSerializer(serializers.ModelSerializer):
    """Read-only serializer for the persisted rack-locality report (DIET-607).

    PlanLocalityRange is a plain models.Model, so this is a plain DRF
    ModelSerializer (not NetBoxModelSerializer). Read-only from the API.
    """

    rack_name = serializers.CharField(source='rack.name', read_only=True)
    switch_name = serializers.CharField(source='switch.name', read_only=True)
    zone_name = serializers.CharField(source='zone.zone_name', read_only=True)
    server_class_id = serializers.CharField(
        source='server_class.server_class_id', read_only=True)

    class Meta:
        model = models.PlanLocalityRange
        fields = [
            'id', 'plan', 'server_class', 'server_class_id', 'rack', 'rack_name',
            'rack_index', 'switch', 'switch_name', 'zone', 'zone_name',
            'distribution', 'alloc_seq_start', 'alloc_seq_end',
            'server_ordinal_start', 'server_ordinal_end', 'logical_name_first',
            'logical_name_last', 'logical_sequence', 'physical_sequence',
            'physical_ports_distinct', 'port_count', 'spans_boundary',
        ]
