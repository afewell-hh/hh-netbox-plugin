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


# GitOps API Serializers (MVP2)
class HedgehogResourceSerializer(NetBoxModelSerializer):
    """Serializer for HedgehogResource dual-state model"""
    fabric = serializers.PrimaryKeyRelatedField(queryset=models.HedgehogFabric.objects.all())
    git_file_url = serializers.ReadOnlyField()
    has_drift = serializers.ReadOnlyField()
    has_desired_state = serializers.ReadOnlyField()
    has_actual_state = serializers.ReadOnlyField()
    resource_identifier = serializers.ReadOnlyField()
    
    class Meta:
        model = models.HedgehogResource
        fields = '__all__'
        
    def to_representation(self, instance):
        """Add computed fields to API response"""
        data = super().to_representation(instance)
        
        # Add GitOps status information
        data['gitops_status'] = {
            'drift_summary': instance.get_drift_summary(),
            'has_drift': instance.has_drift,
            'is_orphaned': instance.is_orphaned,
            'is_pending_creation': instance.is_pending_creation,
        }
        
        return data


class GitStatusSerializer(serializers.Serializer):
    """Serializer for Git repository status responses"""
    configured = serializers.BooleanField()
    repository_url = serializers.URLField(required=False)
    branch = serializers.CharField(required=False)
    path = serializers.CharField(required=False)
    last_commit = serializers.CharField(required=False)
    last_sync = serializers.DateTimeField(required=False)
    status = serializers.CharField(required=False)
    error = serializers.CharField(required=False)
    message = serializers.CharField(required=False)


class DriftStatusSerializer(serializers.Serializer):
    """Serializer for drift detection responses"""
    drift_status = serializers.CharField()
    drift_count = serializers.IntegerField(required=False)
    drift_score = serializers.FloatField(required=False)
    last_calculated = serializers.DateTimeField(required=False)
    details = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class GitOpsSyncSerializer(serializers.Serializer):
    """Serializer for GitOps sync operation responses"""
    success = serializers.BooleanField()
    message = serializers.CharField(required=False)
    tool = serializers.CharField(required=False)
    app_name = serializers.CharField(required=False)
    namespace = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class GitSyncSerializer(serializers.Serializer):
    """Serializer for Git synchronization responses"""
    success = serializers.BooleanField()
    message = serializers.CharField(required=False)
    repository_url = serializers.URLField(required=False)
    branch = serializers.CharField(required=False)
    sync_time = serializers.DateTimeField(required=False)
    commit_sha = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class DriftReportSerializer(serializers.Serializer):
    """Serializer for comprehensive drift reports"""
    fabric = serializers.CharField()
    total_resources = serializers.IntegerField()
    in_sync = serializers.IntegerField()
    drifted = serializers.IntegerField()
    drift_percentage = serializers.FloatField()
    drift_by_status = serializers.DictField()
    drift_by_kind = serializers.DictField()
    last_updated = serializers.DateTimeField()


class BulkSyncSerializer(serializers.Serializer):
    """Serializer for bulk synchronization responses"""
    synced = serializers.IntegerField()
    errors = serializers.IntegerField()
    details = serializers.DictField()
    fabric_stats = serializers.DictField(required=False)


class FabricGitOpsStatusSerializer(serializers.Serializer):
    """Serializer for comprehensive fabric GitOps status"""
    fabric_status = serializers.DictField()
    drift_summary = DriftReportSerializer()
    git_config = serializers.DictField()
    gitops_tool = serializers.DictField()


# Enhanced Fabric Serializer with GitOps fields
class EnhancedFabricSerializer(NetBoxModelSerializer):
    """Enhanced fabric serializer including GitOps fields and computed properties"""
    gitops_summary = serializers.ReadOnlyField(source='get_gitops_summary')
    crd_count = serializers.ReadOnlyField()
    active_crd_count = serializers.ReadOnlyField()
    error_crd_count = serializers.ReadOnlyField()
    
    class Meta:
        model = models.HedgehogFabric
        fields = '__all__'
        
    def to_representation(self, instance):
        """Add computed GitOps information to API response"""
        data = super().to_representation(instance)
        
        # Add GitOps status
        data['git_status'] = instance.get_git_status()
        data['drift_status_info'] = instance.calculate_drift_status()
        
        return data