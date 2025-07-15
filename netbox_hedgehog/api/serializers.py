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

# Git Repository Management Serializers (Week 1 GitOps Architecture)
class GitRepositorySerializer(NetBoxModelSerializer):
    """Serializer for GitRepository model with encrypted credential handling"""
    
    # Read-only computed fields
    connection_summary = serializers.ReadOnlyField(source='get_connection_summary')
    dependent_fabrics_count = serializers.ReadOnlyField(source='fabric_count')
    can_delete_info = serializers.SerializerMethodField()
    repository_info = serializers.ReadOnlyField(source='get_repository_info')
    
    # Write-only credentials field for secure credential setting
    credentials = serializers.DictField(write_only=True, required=False)
    
    class Meta:
        model = models.GitRepository
        fields = [
            'id', 'url', 'name', 'provider', 'authentication_type', 'description',
            'connection_status', 'last_validated', 'validation_error',
            'default_branch', 'is_private', 'fabric_count', 'created_by',
            'validate_ssl', 'timeout_seconds', 'created', 'last_updated',
            'connection_summary', 'dependent_fabrics_count', 'can_delete_info',
            'repository_info', 'credentials'
        ]
        read_only_fields = [
            'connection_status', 'last_validated', 'validation_error',
            'fabric_count', 'created_by', 'created', 'last_updated'
        ]
    
    def get_can_delete_info(self, obj):
        """Get deletion safety information"""
        can_delete, reason = obj.can_delete()
        return {'can_delete': can_delete, 'reason': reason}
    
    def create(self, validated_data):
        """Create GitRepository with encrypted credentials"""
        credentials = validated_data.pop('credentials', {})
        validated_data['created_by'] = self.context['request'].user
        
        instance = super().create(validated_data)
        
        if credentials:
            instance.set_credentials(credentials)
            instance.save()
        
        return instance
    
    def update(self, instance, validated_data):
        """Update GitRepository with optional credential updates"""
        credentials = validated_data.pop('credentials', None)
        
        instance = super().update(instance, validated_data)
        
        if credentials is not None:
            instance.set_credentials(credentials)
            instance.save()
        
        return instance
    
    def to_representation(self, instance):
        """Add computed fields to API response without exposing credentials"""
        data = super().to_representation(instance)
        
        # Add credential indicator (without exposing actual credentials)
        data['has_credentials'] = bool(instance.encrypted_credentials)
        
        # Add dependent fabrics list
        dependent_fabrics = instance.get_dependent_fabrics()
        data['dependent_fabrics'] = [
            {'id': fabric.id, 'name': fabric.name}
            for fabric in dependent_fabrics[:10]  # Limit to first 10
        ]
        
        return data


class GitRepositoryCreateSerializer(serializers.ModelSerializer):
    """Specialized serializer for creating git repositories with required credentials"""
    
    credentials = serializers.DictField(required=True, write_only=True)
    
    class Meta:
        model = models.GitRepository
        fields = [
            'name', 'url', 'provider', 'authentication_type', 'description',
            'default_branch', 'is_private', 'validate_ssl', 'timeout_seconds',
            'credentials'
        ]
    
    def validate_credentials(self, value):
        """Validate credentials based on authentication type"""
        auth_type = self.initial_data.get('authentication_type', 'token')
        
        if auth_type == 'token':
            if 'token' not in value or not value['token']:
                raise serializers.ValidationError("Token is required for token authentication")
        elif auth_type == 'basic':
            if 'username' not in value or not value['username']:
                raise serializers.ValidationError("Username is required for basic authentication")
            if 'password' not in value or not value['password']:
                raise serializers.ValidationError("Password is required for basic authentication")
        elif auth_type == 'ssh_key':
            if 'private_key' not in value or not value['private_key']:
                raise serializers.ValidationError("Private key is required for SSH key authentication")
        
        return value
    
    def create(self, validated_data):
        """Create repository with encrypted credentials"""
        credentials = validated_data.pop('credentials')
        validated_data['created_by'] = self.context['request'].user
        
        instance = super().create(validated_data)
        instance.set_credentials(credentials)
        instance.save()
        
        return instance


class GitRepositoryUpdateSerializer(serializers.ModelSerializer):
    """Specialized serializer for updating git repositories"""
    
    credentials = serializers.DictField(required=False, write_only=True)
    
    class Meta:
        model = models.GitRepository
        fields = [
            'name', 'description', 'default_branch', 'validate_ssl', 
            'timeout_seconds', 'credentials'
        ]
    
    def update(self, instance, validated_data):
        """Update repository with optional credential updates"""
        credentials = validated_data.pop('credentials', None)
        
        instance = super().update(instance, validated_data)
        
        if credentials is not None:
            instance.set_credentials(credentials)
            instance.save()
        
        return instance


class GitRepositoryTestConnectionSerializer(serializers.Serializer):
    """Serializer for git repository connection test results"""
    success = serializers.BooleanField()
    message = serializers.CharField(required=False)
    repository_url = serializers.URLField(required=False)
    default_branch = serializers.CharField(required=False)
    current_commit = serializers.CharField(required=False)
    authenticated = serializers.BooleanField(required=False)
    last_validated = serializers.DateTimeField(required=False)
    error = serializers.CharField(required=False)


class GitRepositoryCloneSerializer(serializers.Serializer):
    """Serializer for git repository clone operation requests"""
    target_directory = serializers.CharField(required=True)
    branch = serializers.CharField(required=False)


class GitRepositoryCloneResultSerializer(serializers.Serializer):
    """Serializer for git repository clone operation results"""
    success = serializers.BooleanField()
    message = serializers.CharField(required=False)
    repository_path = serializers.CharField(required=False)
    branch = serializers.CharField(required=False)
    commit_sha = serializers.CharField(required=False)
    commit_message = serializers.CharField(required=False)
    error = serializers.CharField(required=False)
    repository_url = serializers.URLField(required=False)
    target_directory = serializers.CharField(required=False)

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


# Enhanced Fabric Serializer with GitRepository Integration (Week 3)
class EnhancedFabricSerializer(NetBoxModelSerializer):
    """Enhanced fabric serializer with complete GitRepository integration"""
    
    # Read-only computed fields
    gitops_summary = serializers.ReadOnlyField(source='get_gitops_summary')
    crd_count = serializers.ReadOnlyField()
    active_crd_count = serializers.ReadOnlyField()
    error_crd_count = serializers.ReadOnlyField()
    
    # GitRepository integration fields
    git_repository_info = serializers.SerializerMethodField()
    gitops_directory_validation = serializers.SerializerMethodField()
    git_health_status = serializers.SerializerMethodField()
    available_repositories = serializers.SerializerMethodField()
    
    # Legacy migration fields
    migration_status = serializers.SerializerMethodField()
    
    class Meta:
        model = models.HedgehogFabric
        fields = '__all__'
        
    def get_git_repository_info(self, obj):
        """Get detailed git repository information"""
        if not obj.git_repository:
            return {
                'configured': False,
                'using_legacy': bool(obj.git_repository_url),
                'legacy_url': obj.git_repository_url if obj.git_repository_url else None
            }
        
        return {
            'configured': True,
            'repository': {
                'id': obj.git_repository.id,
                'name': obj.git_repository.name,
                'url': obj.git_repository.url,
                'provider': obj.git_repository.provider,
                'authentication_type': obj.git_repository.authentication_type,
                'connection_status': obj.git_repository.connection_status,
                'last_validated': obj.git_repository.last_validated.isoformat() if obj.git_repository.last_validated else None
            },
            'gitops_directory': obj.gitops_directory,
            'fabric_count': obj.git_repository.fabric_count if obj.git_repository else 0
        }
    
    def get_gitops_directory_validation(self, obj):
        """Get GitOps directory validation status"""
        if not obj.git_repository or not obj.gitops_directory:
            return {'valid': True, 'message': 'No validation needed'}
        
        try:
            from netbox_hedgehog.utils.gitops_directory_validator import GitOpsDirectoryValidator
            
            validator = GitOpsDirectoryValidator()
            result = validator.validate_gitops_directory_assignment(
                obj.git_repository.id, obj.gitops_directory, exclude_fabric_id=obj.id
            )
            
            return {
                'valid': result.is_valid,
                'errors': result.errors,
                'suggestions': result.suggestions,
                'conflicts': result.conflicts
            }
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def get_git_health_status(self, obj):
        """Get git repository health status"""
        if not obj.git_repository:
            return {'available': False, 'message': 'No git repository configured'}
        
        try:
            from netbox_hedgehog.utils.git_health_monitor import GitHealthMonitor
            
            monitor = GitHealthMonitor(obj.git_repository)
            health_report = monitor.generate_health_report()
            
            return {
                'available': True,
                'status': health_report.overall_status,
                'connection_healthy': health_report.overall_status in ['healthy', 'degraded'],
                'last_check': health_report.check_timestamp.isoformat() if health_report.check_timestamp else None,
                'details': health_report.to_dict()
            }
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    def get_available_repositories(self, obj):
        """Get repositories available to current user"""
        request = self.context.get('request')
        if not request or not request.user:
            return []
        
        try:
            repositories = models.GitRepository.objects.filter(
                created_by=request.user
            ).values('id', 'name', 'url', 'provider', 'connection_status')
            
            return list(repositories)
        except Exception:
            return []
    
    def get_migration_status(self, obj):
        """Get migration status for legacy fabrics"""
        if obj.git_repository:
            return {
                'migrated': True,
                'using_new_architecture': True,
                'message': 'Using new GitRepository architecture'
            }
        
        if obj.git_repository_url:
            return {
                'migrated': False,
                'using_legacy_architecture': True,
                'migration_possible': True,
                'legacy_config': {
                    'url': obj.git_repository_url,
                    'branch': obj.git_branch,
                    'path': obj.git_path,
                    'has_credentials': bool(obj.git_username or obj.git_token)
                },
                'message': 'Ready for migration to new architecture'
            }
        
        return {
            'migrated': False,
            'using_legacy_architecture': False,
            'migration_possible': False,
            'message': 'No git configuration found'
        }
    
    def validate_gitops_directory(self, value):
        """Validate GitOps directory with conflict detection"""
        if not value:
            return value
        
        # Basic path validation
        if not value.startswith('/'):
            raise serializers.ValidationError("GitOps directory must start with '/'")
        
        if '..' in value:
            raise serializers.ValidationError("GitOps directory cannot contain '..' path segments")
        
        # Normalize path
        from pathlib import Path
        normalized = str(Path(value)).replace('\\', '/')
        if not normalized.startswith('/'):
            normalized = '/' + normalized
        
        return normalized
    
    def validate_git_repository_assignment(self, attrs):
        """Validate git repository and directory combination"""
        git_repository = attrs.get('git_repository')
        gitops_directory = attrs.get('gitops_directory', '/')
        
        if not git_repository:
            return attrs
        
        # Check if user has access to repository
        request = self.context.get('request')
        if request and request.user:
            if git_repository.created_by != request.user:
                raise serializers.ValidationError(
                    "You don't have permission to use this git repository"
                )
        
        # Validate directory assignment
        try:
            from netbox_hedgehog.utils.gitops_directory_validator import GitOpsDirectoryValidator
            
            validator = GitOpsDirectoryValidator()
            exclude_fabric_id = self.instance.id if self.instance else None
            
            result = validator.validate_gitops_directory_assignment(
                git_repository.id, gitops_directory, exclude_fabric_id=exclude_fabric_id
            )
            
            if not result.is_valid:
                raise serializers.ValidationError({
                    'gitops_directory': result.errors,
                    'suggestions': result.suggestions
                })
                
        except Exception as e:
            raise serializers.ValidationError(f"Directory validation failed: {str(e)}")
        
        return attrs
    
    def validate(self, attrs):
        """Perform comprehensive validation"""
        attrs = super().validate(attrs)
        
        # Validate git repository assignment
        if 'git_repository' in attrs or 'gitops_directory' in attrs:
            attrs = self.validate_git_repository_assignment(attrs)
        
        return attrs
    
    def to_representation(self, instance):
        """Add computed GitOps information to API response"""
        data = super().to_representation(instance)
        
        # Add legacy GitOps status for backward compatibility
        data['git_status'] = instance.get_git_status()
        data['drift_status_info'] = instance.calculate_drift_status()
        
        # Add enhanced capabilities information
        data['capabilities'] = {
            'git_repository_management': bool(instance.git_repository),
            'legacy_git_support': bool(instance.git_repository_url and not instance.git_repository),
            'migration_available': bool(instance.git_repository_url and not instance.git_repository),
            'health_monitoring': bool(instance.git_repository),
            'directory_validation': bool(instance.git_repository),
            'credential_management': bool(instance.git_repository)
        }
        
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