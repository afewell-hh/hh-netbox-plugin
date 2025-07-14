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


# Week 5 Reconciliation API Serializers
class ReconciliationAlertSerializer(NetBoxModelSerializer):
    """Serializer for ReconciliationAlert model"""
    fabric = serializers.PrimaryKeyRelatedField(queryset=models.HedgehogFabric.objects.all())
    resource = serializers.PrimaryKeyRelatedField(queryset=models.HedgehogResource.objects.all())
    suggested_actions = serializers.ReadOnlyField(source='get_suggested_actions')
    age_hours = serializers.ReadOnlyField()
    time_to_resolution = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = models.ReconciliationAlert
        fields = '__all__'
        
    def to_representation(self, instance):
        """Add computed fields to API response"""
        data = super().to_representation(instance)
        
        # Add alert summary
        data['alert_summary'] = instance.get_alert_summary()
        
        return data


class AlertResolutionSerializer(serializers.Serializer):
    """Serializer for alert resolution requests"""
    action = serializers.ChoiceField(choices=[
        ('import_to_git', 'Import to Git'),
        ('delete_from_cluster', 'Delete from Cluster'),
        ('update_git', 'Update Git'),
        ('ignore', 'Ignore'),
        ('manual_review', 'Manual Review'),
    ])
    dry_run = serializers.BooleanField(default=False)
    metadata = serializers.DictField(required=False)


class AlertResolutionResultSerializer(serializers.Serializer):
    """Serializer for alert resolution results"""
    success = serializers.BooleanField()
    action = serializers.CharField()
    message = serializers.CharField(required=False)
    details = serializers.DictField(required=False)
    dry_run = serializers.BooleanField()
    resolved = serializers.DictField(required=False)
    error = serializers.CharField(required=False)


class BatchOperationSerializer(serializers.Serializer):
    """Serializer for batch reconciliation operations"""
    batch_id = serializers.CharField(read_only=True)
    fabric_id = serializers.IntegerField()
    strategy = serializers.ChoiceField(choices=[
        ('sequential', 'Sequential'),
        ('parallel', 'Parallel'),
        ('dependency_aware', 'Dependency Aware'),
        ('priority_based', 'Priority Based'),
    ], default='sequential')
    resource_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    alert_types = serializers.ListField(child=serializers.CharField(), required=False)
    metadata = serializers.DictField(required=False)


class BatchOperationStatusSerializer(serializers.Serializer):
    """Serializer for batch operation status"""
    batch_id = serializers.CharField()
    status = serializers.CharField()
    strategy = serializers.CharField()
    total_items = serializers.IntegerField()
    processed_items = serializers.IntegerField()
    successful_items = serializers.IntegerField()
    failed_items = serializers.IntegerField()
    processing_time = serializers.FloatField()
    created_at = serializers.DateTimeField()
    started_at = serializers.DateTimeField(required=False)
    completed_at = serializers.DateTimeField(required=False)
    errors = serializers.ListField(child=serializers.CharField(), required=False)
    metadata = serializers.DictField(required=False)


class GitFirstOnboardingSerializer(serializers.Serializer):
    """Serializer for Git-first onboarding requests"""
    name = serializers.CharField()
    description = serializers.CharField(required=False)
    repository_url = serializers.URLField()
    branch = serializers.CharField(default='main')
    path = serializers.CharField(default='hedgehog/')
    access_token = serializers.CharField(required=False)
    username = serializers.CharField(required=False)
    validate_only = serializers.BooleanField(default=False)


class GitFirstOnboardingResultSerializer(serializers.Serializer):
    """Serializer for Git-first onboarding results"""
    success = serializers.BooleanField()
    fabric_id = serializers.IntegerField(required=False)
    created_resources = serializers.IntegerField(required=False)
    updated_resources = serializers.IntegerField(required=False)
    validation_errors = serializers.ListField(child=serializers.CharField(), required=False)
    warnings = serializers.ListField(child=serializers.CharField(), required=False)
    processing_time = serializers.FloatField(required=False)
    onboarding_metadata = serializers.DictField(required=False)


class RepositoryValidationSerializer(serializers.Serializer):
    """Serializer for repository validation requests"""
    repository_url = serializers.URLField()
    branch = serializers.CharField(default='main')
    path = serializers.CharField(default='hedgehog/')
    access_token = serializers.CharField(required=False)
    username = serializers.CharField(required=False)


class RepositoryValidationResultSerializer(serializers.Serializer):
    """Serializer for repository validation results"""
    is_accessible = serializers.BooleanField()
    has_hedgehog_directory = serializers.BooleanField()
    discovered_resources = serializers.ListField(child=serializers.CharField())
    validation_errors = serializers.ListField(child=serializers.CharField())
    repository_structure = serializers.DictField()


class YAMLWorkflowSerializer(serializers.Serializer):
    """Serializer for YAML-first workflow requests"""
    yaml_content = serializers.CharField()
    file_path = serializers.CharField(required=False)
    fabric_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=[
        ('create', 'Create'),
        ('validate', 'Validate'),
    ], default='create')


class YAMLWorkflowResultSerializer(serializers.Serializer):
    """Serializer for YAML-first workflow results"""
    success = serializers.BooleanField()
    action = serializers.CharField()
    resources_processed = serializers.ListField(child=serializers.CharField())
    resources_created = serializers.ListField(child=serializers.IntegerField(), required=False)
    resources_updated = serializers.ListField(child=serializers.IntegerField(), required=False)
    validation_errors = serializers.ListField(child=serializers.CharField(), required=False)
    warnings = serializers.ListField(child=serializers.CharField(), required=False)
    yaml_content = serializers.CharField(required=False)
    processing_time = serializers.FloatField(required=False)
    metadata = serializers.DictField(required=False)


class OrphanedResourceStatsSerializer(serializers.Serializer):
    """Serializer for orphaned resource statistics"""
    total_orphaned_alerts = serializers.IntegerField()
    by_severity = serializers.DictField()
    by_kind = serializers.DictField()
    by_fabric = serializers.DictField()
    oldest_orphaned = serializers.DictField(required=False)
    newest_orphaned = serializers.DictField(required=False)


class ConflictSummarySerializer(serializers.Serializer):
    """Serializer for conflict summary"""
    total_conflicts = serializers.IntegerField()
    by_severity = serializers.DictField()
    by_resource_kind = serializers.DictField()
    recent_conflicts = serializers.ListField(child=serializers.DictField())