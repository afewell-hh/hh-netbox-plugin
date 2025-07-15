from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from netbox.api.viewsets import NetBoxModelViewSet
from django.shortcuts import get_object_or_404
import logging
try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
import os
import tempfile
from pathlib import Path
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
from django.conf import settings

from .. import models
from . import serializers
from ..utils.gitops_integration import (
    bulk_sync_fabric_to_gitops,
    get_fabric_gitops_status,
    CRDGitOpsIntegrator
)
from ..utils.git_providers import GitProviderFactory, GitAuthenticationError

logger = logging.getLogger(__name__)

# Enhanced Fabric ViewSet with GitRepository Integration (Week 3)
class FabricViewSet(NetBoxModelViewSet):
    """
    Enhanced fabric management using separated GitRepository architecture.
    
    Provides CRUD operations for fabrics with integrated GitRepository support,
    unified creation workflows, and comprehensive validation.
    """
    queryset = models.HedgehogFabric.objects.all()
    serializer_class = serializers.FabricSerializer
    
    def get_serializer_class(self):
        """Use specialized serializers for different operations"""
        if self.action in ['create_with_git_repository', 'update_git_configuration']:
            return serializers.EnhancedFabricSerializer
        return self.serializer_class
    
    @action(detail=False, methods=['post'])
    def create_with_git_repository(self, request):
        """
        Create fabric with GitRepository selection and directory validation.
        
        POST /api/plugins/hedgehog/fabrics/create-with-git-repository/
        Body: {
            "fabric_data": {...},
            "git_repository_id": 123,
            "gitops_directory": "/my-fabric/",
            "validate_directory": true
        }
        """
        try:
            from ..utils.fabric_creation_workflow import UnifiedFabricCreationWorkflow
            from ..utils.gitops_directory_validator import GitOpsDirectoryValidator
            
            # Extract request data
            fabric_data = request.data.get('fabric_data', {})
            git_repository_id = request.data.get('git_repository_id')
            gitops_directory = request.data.get('gitops_directory', '/')
            validate_directory = request.data.get('validate_directory', True)
            
            if not git_repository_id:
                return Response({
                    'success': False,
                    'error': 'git_repository_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify git repository exists and user has access
            try:
                git_repository = models.GitRepository.objects.get(
                    id=git_repository_id,
                    created_by=request.user
                )
            except models.GitRepository.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Git repository not found or access denied'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Validate directory if requested
            if validate_directory:
                validator = GitOpsDirectoryValidator()
                directory_result = validator.validate_gitops_directory_assignment(
                    git_repository_id, gitops_directory
                )
                
                if not directory_result.is_valid:
                    return Response({
                        'success': False,
                        'error': 'Directory validation failed',
                        'validation_errors': directory_result.errors,
                        'suggestions': directory_result.suggestions
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create fabric using unified workflow
            workflow = UnifiedFabricCreationWorkflow(request.user)
            creation_result = workflow.create_fabric_with_git_repository(
                fabric_data, git_repository_id, gitops_directory
            )
            
            if creation_result.success:
                # Serialize the created fabric
                fabric_serializer = serializers.EnhancedFabricSerializer(
                    creation_result.fabric, context={'request': request}
                )
                
                return Response({
                    'success': True,
                    'fabric': fabric_serializer.data,
                    'git_repository_info': {
                        'id': git_repository.id,
                        'name': git_repository.name,
                        'url': git_repository.url
                    },
                    'gitops_directory': gitops_directory,
                    'creation_details': creation_result.details
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'error': creation_result.error,
                    'details': creation_result.details
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Fabric creation with git repository failed: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['put'])
    def update_git_configuration(self, request, pk=None):
        """
        Update fabric git configuration with validation.
        
        PUT /api/plugins/hedgehog/fabrics/{id}/update-git-configuration/
        Body: {
            "git_repository_id": 123,
            "gitops_directory": "/new-path/",
            "validate_changes": true
        }
        """
        try:
            fabric = self.get_object()
            
            git_repository_id = request.data.get('git_repository_id')
            gitops_directory = request.data.get('gitops_directory')
            validate_changes = request.data.get('validate_changes', True)
            
            # Validate git repository if provided
            if git_repository_id:
                try:
                    git_repository = models.GitRepository.objects.get(
                        id=git_repository_id,
                        created_by=request.user
                    )
                except models.GitRepository.DoesNotExist:
                    return Response({
                        'success': False,
                        'error': 'Git repository not found or access denied'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                git_repository = fabric.git_repository
            
            # Validate directory changes
            if validate_changes and git_repository and gitops_directory:
                from ..utils.gitops_directory_validator import GitOpsDirectoryValidator
                
                validator = GitOpsDirectoryValidator()
                directory_result = validator.validate_gitops_directory_assignment(
                    git_repository.id, gitops_directory, exclude_fabric_id=fabric.id
                )
                
                if not directory_result.is_valid:
                    return Response({
                        'success': False,
                        'error': 'Directory validation failed',
                        'validation_errors': directory_result.errors,
                        'suggestions': directory_result.suggestions
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update fabric configuration
            update_fields = []
            if git_repository_id and git_repository:
                fabric.git_repository = git_repository
                update_fields.append('git_repository')
            
            if gitops_directory is not None:
                fabric.gitops_directory = gitops_directory
                update_fields.append('gitops_directory')
            
            if update_fields:
                fabric.save(update_fields=update_fields)
                
                # Update git repository fabric count
                if git_repository:
                    git_repository.update_fabric_count()
            
            # Get updated fabric data
            fabric_serializer = serializers.EnhancedFabricSerializer(
                fabric, context={'request': request}
            )
            
            return Response({
                'success': True,
                'fabric': fabric_serializer.data,
                'updated_fields': update_fields,
                'message': 'Git configuration updated successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Git configuration update failed for fabric {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def validate_git_configuration(self, request, pk=None):
        """
        Validate fabric git configuration before applying.
        
        POST /api/plugins/hedgehog/fabrics/{id}/validate-git-configuration/
        Body: {
            "git_repository_id": 123,
            "gitops_directory": "/path/",
            "check_connectivity": true,
            "check_permissions": true
        }
        """
        try:
            fabric = self.get_object()
            
            git_repository_id = request.data.get('git_repository_id', fabric.git_repository_id)
            gitops_directory = request.data.get('gitops_directory', fabric.gitops_directory)
            check_connectivity = request.data.get('check_connectivity', True)
            check_permissions = request.data.get('check_permissions', True)
            
            validation_results = {
                'fabric_id': fabric.id,
                'fabric_name': fabric.name,
                'validation_timestamp': timezone.now().isoformat(),
                'overall_valid': True,
                'checks': {}
            }
            
            # Validate git repository
            if git_repository_id:
                try:
                    git_repository = models.GitRepository.objects.get(
                        id=git_repository_id,
                        created_by=request.user
                    )
                    
                    validation_results['checks']['repository_access'] = {
                        'valid': True,
                        'message': 'Repository accessible',
                        'repository_name': git_repository.name
                    }
                    
                    # Test connectivity if requested
                    if check_connectivity:
                        connection_result = git_repository.test_connection()
                        validation_results['checks']['connectivity'] = {
                            'valid': connection_result['success'],
                            'message': connection_result.get('message', connection_result.get('error', '')),
                            'details': connection_result
                        }
                        
                        if not connection_result['success']:
                            validation_results['overall_valid'] = False
                    
                    # Check permissions if requested
                    if check_permissions:
                        permission_result = git_repository.validate_permission_scope()
                        validation_results['checks']['permissions'] = {
                            'valid': permission_result.get('success', False),
                            'message': permission_result.get('message', ''),
                            'details': permission_result
                        }
                        
                        if not permission_result.get('success', False):
                            validation_results['overall_valid'] = False
                    
                except models.GitRepository.DoesNotExist:
                    validation_results['checks']['repository_access'] = {
                        'valid': False,
                        'message': 'Git repository not found or access denied'
                    }
                    validation_results['overall_valid'] = False
            
            # Validate directory
            if git_repository_id and gitops_directory:
                from ..utils.gitops_directory_validator import GitOpsDirectoryValidator
                
                validator = GitOpsDirectoryValidator()
                directory_result = validator.validate_gitops_directory_assignment(
                    git_repository_id, gitops_directory, exclude_fabric_id=fabric.id
                )
                
                validation_results['checks']['directory'] = {
                    'valid': directory_result.is_valid,
                    'message': 'Directory validation passed' if directory_result.is_valid else 'Directory conflicts detected',
                    'errors': directory_result.errors,
                    'suggestions': directory_result.suggestions
                }
                
                if not directory_result.is_valid:
                    validation_results['overall_valid'] = False
            
            # Validate fabric-specific constraints
            from ..validators.fabric_git_validator import FabricGitValidator
            
            fabric_validator = FabricGitValidator()
            fabric_validation = fabric_validator.validate_fabric_git_configuration(
                fabric, git_repository_id, gitops_directory
            )
            
            validation_results['checks']['fabric_constraints'] = {
                'valid': fabric_validation.is_valid,
                'message': fabric_validation.message,
                'details': fabric_validation.details
            }
            
            if not fabric_validation.is_valid:
                validation_results['overall_valid'] = False
            
            return Response(validation_results, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Git configuration validation failed for fabric {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def git_health_status(self, request, pk=None):
        """
        Get git repository health status for this fabric.
        
        GET /api/plugins/hedgehog/fabrics/{id}/git-health-status/
        """
        try:
            fabric = self.get_object()
            
            if not fabric.git_repository:
                return Response({
                    'fabric_id': fabric.id,
                    'git_configured': False,
                    'message': 'No git repository configured for this fabric'
                }, status=status.HTTP_200_OK)
            
            # Get git repository health
            from ..utils.git_health_monitor import GitHealthMonitor
            
            monitor = GitHealthMonitor(fabric.git_repository)
            health_report = monitor.generate_health_report()
            
            # Get credential health
            from ..utils.credential_manager import CredentialManager
            
            credential_manager = CredentialManager()
            credential_health = credential_manager.get_credential_health(fabric.git_repository)
            
            health_status = {
                'fabric_id': fabric.id,
                'fabric_name': fabric.name,
                'git_configured': True,
                'repository': {
                    'id': fabric.git_repository.id,
                    'name': fabric.git_repository.name,
                    'url': fabric.git_repository.url,
                    'provider': fabric.git_repository.provider
                },
                'gitops_directory': fabric.gitops_directory,
                'health_report': health_report.to_dict(),
                'credential_health': credential_health,
                'last_updated': timezone.now().isoformat()
            }
            
            return Response(health_status, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Git health status failed for fabric {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def migrate_to_new_architecture(self, request, pk=None):
        """
        Migrate individual fabric from legacy to new architecture.
        
        POST /api/plugins/hedgehog/fabrics/{id}/migrate-to-new-architecture/
        Body: {
            "create_git_repository": true,
            "repository_name": "My Fabric Repo",
            "dry_run": false
        }
        """
        try:
            fabric = self.get_object()
            
            create_git_repository = request.data.get('create_git_repository', True)
            repository_name = request.data.get('repository_name', f"{fabric.name} Repository")
            dry_run = request.data.get('dry_run', False)
            
            # Check if already migrated
            if fabric.git_repository:
                return Response({
                    'success': False,
                    'error': 'Fabric already uses new GitRepository architecture',
                    'current_repository': {
                        'id': fabric.git_repository.id,
                        'name': fabric.git_repository.name
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if legacy configuration exists
            if not fabric.git_repository_url:
                return Response({
                    'success': False,
                    'error': 'No legacy git configuration found - nothing to migrate'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if dry_run:
                # Perform dry run analysis
                migration_analysis = {
                    'fabric_id': fabric.id,
                    'fabric_name': fabric.name,
                    'migration_possible': True,
                    'legacy_config': {
                        'git_repository_url': fabric.git_repository_url,
                        'git_branch': fabric.git_branch,
                        'git_path': fabric.git_path,
                        'has_credentials': bool(fabric.git_username or fabric.git_token)
                    },
                    'planned_changes': {
                        'create_git_repository': create_git_repository,
                        'repository_name': repository_name,
                        'gitops_directory': fabric.git_path or '/',
                        'authentication_type': 'token' if fabric.git_token else 'basic'
                    },
                    'warnings': [],
                    'requirements': []
                }
                
                # Add warnings and requirements
                if not fabric.git_token and not fabric.git_username:
                    migration_analysis['warnings'].append(
                        'No credentials found in legacy configuration - you will need to provide them'
                    )
                    migration_analysis['requirements'].append(
                        'Provide git credentials for the new repository'
                    )
                
                return Response({
                    'dry_run': True,
                    'migration_analysis': migration_analysis
                }, status=status.HTTP_200_OK)
            
            # Perform actual migration
            from ..utils.legacy_migration_manager import LegacyArchitectureMigrationManager
            
            migration_manager = LegacyArchitectureMigrationManager()
            migration_result = migration_manager.migrate_fabric_configuration(fabric.id)
            
            if migration_result.success:
                # Reload fabric to get updated data
                fabric.refresh_from_db()
                
                fabric_serializer = serializers.EnhancedFabricSerializer(
                    fabric, context={'request': request}
                )
                
                return Response({
                    'success': True,
                    'message': 'Migration completed successfully',
                    'fabric': fabric_serializer.data,
                    'migration_details': migration_result.details,
                    'new_repository': {
                        'id': fabric.git_repository.id if fabric.git_repository else None,
                        'name': fabric.git_repository.name if fabric.git_repository else None
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': migration_result.error,
                    'details': migration_result.details
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Migration failed for fabric {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Git Repository ViewSet (Week 1 GitOps Architecture)
class GitRepositoryViewSet(NetBoxModelViewSet):
    """
    API ViewSet for GitRepository management with encrypted credential handling.
    
    Provides CRUD operations for git repositories with secure credential storage,
    connection testing, and repository management functionality.
    """
    queryset = models.GitRepository.objects.all()
    serializer_class = serializers.GitRepositorySerializer
    filterset_fields = [
        'provider', 'authentication_type', 'connection_status', 
        'is_private', 'created_by'
    ]
    
    def get_serializer_class(self):
        """Use specialized serializers for create/update operations"""
        if self.action == 'create':
            return serializers.GitRepositoryCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return serializers.GitRepositoryUpdateSerializer
        return self.serializer_class
    
    def get_queryset(self):
        """Filter repositories by user to prevent unauthorized access"""
        queryset = super().get_queryset()
        # Users can only see repositories they created
        if not self.request.user.is_superuser:
            queryset = queryset.filter(created_by=self.request.user)
        return queryset
    
    def perform_create(self, serializer):
        """Set created_by field and update fabric count"""
        instance = serializer.save(created_by=self.request.user)
        instance.update_fabric_count()
    
    def perform_update(self, serializer):
        """Update fabric count after repository update"""
        instance = serializer.save()
        instance.update_fabric_count()
    
    def perform_destroy(self, instance):
        """Check deletion safety before removing repository"""
        can_delete, reason = instance.can_delete()
        if not can_delete:
            return Response({
                'error': f'Cannot delete repository: {reason}',
                'can_delete': False,
                'reason': reason
            }, status=status.HTTP_400_BAD_REQUEST)
        
        super().perform_destroy(instance)
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """
        Test connection to git repository with current credentials.
        
        POST /api/plugins/hedgehog/git-repositories/{id}/test/
        """
        repository = self.get_object()
        
        try:
            result = repository.test_connection()
            serializer = serializers.GitRepositoryTestConnectionSerializer(result)
            
            if result.get('success'):
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Connection test failed for repository {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e),
                'repository_url': repository.url
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """
        Clone repository to specified directory.
        
        POST /api/plugins/hedgehog/git-repositories/{id}/clone/
        Body: {"target_directory": "/path/to/clone", "branch": "optional"}
        """
        repository = self.get_object()
        serializer = serializers.GitRepositoryCloneSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            target_directory = serializer.validated_data['target_directory']
            branch = serializer.validated_data.get('branch')
            
            result = repository.clone_repository(target_directory, branch)
            result_serializer = serializers.GitRepositoryCloneResultSerializer(result)
            
            if result.get('success'):
                return Response(result_serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(result_serializer.data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Clone operation failed for repository {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e),
                'repository_url': repository.url
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def dependent_fabrics(self, request, pk=None):
        """
        Get list of fabrics that depend on this repository.
        
        GET /api/plugins/hedgehog/git-repositories/{id}/dependent-fabrics/
        """
        repository = self.get_object()
        dependent_fabrics = repository.get_dependent_fabrics()
        
        # Serialize fabric data
        fabric_data = []
        for fabric in dependent_fabrics:
            fabric_data.append({
                'id': fabric.id,
                'name': fabric.name,
                'description': fabric.description,
                'gitops_directory': getattr(fabric, 'gitops_directory', '/'),
                'status': fabric.status,
                'connection_status': fabric.connection_status
            })
        
        return Response({
            'repository_id': repository.id,
            'repository_name': repository.name,
            'dependent_fabrics_count': len(fabric_data),
            'dependent_fabrics': fabric_data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def connection_summary(self, request, pk=None):
        """
        Get comprehensive connection status summary.
        
        GET /api/plugins/hedgehog/git-repositories/{id}/connection-summary/
        """
        repository = self.get_object()
        summary = repository.get_connection_summary()
        
        return Response(summary, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def repository_info(self, request, pk=None):
        """
        Get comprehensive repository information.
        
        GET /api/plugins/hedgehog/git-repositories/{id}/repository-info/
        """
        repository = self.get_object()
        info = repository.get_repository_info()
        
        return Response(info, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def my_repositories(self, request):
        """
        Get repositories created by current user.
        
        GET /api/plugins/hedgehog/git-repositories/my-repositories/
        """
        user_repos = self.get_queryset().filter(created_by=request.user)
        serializer = self.get_serializer(user_repos, many=True)
        
        return Response({
            'count': user_repos.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def connection_status_summary(self, request):
        """
        Get summary of connection statuses across all user repositories.
        
        GET /api/plugins/hedgehog/git-repositories/connection-status-summary/
        """
        user_repos = self.get_queryset().filter(created_by=request.user)
        
        status_summary = {}
        for choice in models.GitRepository._meta.get_field('connection_status').choices:
            status_value = choice[0]
            status_summary[status_value] = user_repos.filter(connection_status=status_value).count()
        
        total_repos = user_repos.count()
        connected_repos = status_summary.get('connected', 0)
        
        return Response({
            'total_repositories': total_repos,
            'connection_status_counts': status_summary,
            'connection_health': {
                'connected_percentage': (connected_repos / total_repos * 100) if total_repos > 0 else 0,
                'needs_attention': status_summary.get('failed', 0) + status_summary.get('pending', 0)
            }
        }, status=status.HTTP_200_OK)

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


# GitOps API Views (MVP2)
class HedgehogResourceViewSet(NetBoxModelViewSet):
    """API ViewSet for HedgehogResource dual-state tracking"""
    queryset = models.HedgehogResource.objects.all()
    serializer_class = serializers.HedgehogResourceSerializer
    filterset_fields = ['fabric', 'kind', 'namespace', 'drift_status']
    
    @action(detail=True, methods=['post'])
    def calculate_drift(self, request, pk=None):
        """Calculate drift for a specific resource"""
        resource = self.get_object()
        try:
            result = resource.calculate_drift()
            serializer = serializers.DriftStatusSerializer(result)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Drift calculation failed for resource {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def yaml(self, request, pk=None):
        """Generate YAML content for this resource"""
        resource = self.get_object()
        try:
            yaml_content = resource.generate_yaml_content()
            if yaml_content:
                return Response({
                    'yaml': yaml_content,
                    'file_path': resource.desired_file_path,
                    'commit': resource.desired_commit
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Unable to generate YAML content'
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"YAML generation failed for resource {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get comprehensive status for this resource"""
        resource = self.get_object()
        try:
            status_data = resource.get_status_summary()
            return Response(status_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Status retrieval failed for resource {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EnhancedFabricViewSet(NetBoxModelViewSet):
    """Enhanced Fabric ViewSet with GitOps functionality"""
    queryset = models.HedgehogFabric.objects.all()
    serializer_class = serializers.EnhancedFabricSerializer
    
    @action(detail=True, methods=['get'])
    def git_status(self, request, pk=None):
        """Get Git repository status for this fabric"""
        fabric = self.get_object()
        try:
            git_status = fabric.get_git_status()
            serializer = serializers.GitStatusSerializer(git_status)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Git status failed for fabric {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def sync_git(self, request, pk=None):
        """Trigger Git repository synchronization"""
        fabric = self.get_object()
        try:
            result = fabric.sync_desired_state()
            serializer = serializers.GitSyncSerializer(result)
            return Response(serializer.data, 
                          status=status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Git sync failed for fabric {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def drift_report(self, request, pk=None):
        """Get comprehensive drift report for this fabric"""
        fabric = self.get_object()
        try:
            integrator = CRDGitOpsIntegrator(fabric)
            drift_summary = integrator.get_drift_summary()
            serializer = serializers.DriftReportSerializer(drift_summary)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Drift report failed for fabric {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def gitops_sync(self, request, pk=None):
        """Trigger GitOps tool synchronization"""
        fabric = self.get_object()
        try:
            result = fabric.trigger_gitops_sync()
            serializer = serializers.GitOpsSyncSerializer(result)
            return Response(serializer.data,
                          status=status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"GitOps sync failed for fabric {pk}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def bulk_sync(self, request, pk=None):
        """Trigger bulk synchronization of all CRDs to GitOps tracking"""
        fabric = self.get_object()
        try:
            result = bulk_sync_fabric_to_gitops(fabric)
            serializer = serializers.BulkSyncSerializer(result)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Bulk sync failed for fabric {pk}: {e}")
            return Response({
                'synced': 0,
                'errors': 1,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def gitops_status(self, request, pk=None):
        """Get comprehensive GitOps status for this fabric"""
        fabric = self.get_object()
        try:
            status_data = get_fabric_gitops_status(fabric)
            serializer = serializers.FabricGitOpsStatusSerializer(status_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"GitOps status failed for fabric {pk}: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GitOpsAPIView(APIView):
    """Global GitOps operations API endpoint"""
    
    def get(self, request):
        """Get global GitOps status across all fabrics"""
        try:
            fabrics = models.HedgehogFabric.objects.all()
            
            # Calculate global statistics
            total_fabrics = fabrics.count()
            configured_fabrics = fabrics.exclude(git_repository_url='').count()
            
            # Get total resource counts
            total_resources = models.HedgehogResource.objects.count()
            drifted_resources = models.HedgehogResource.objects.exclude(drift_status='in_sync').count()
            
            # Per-fabric summary
            fabric_summaries = []
            for fabric in fabrics:
                try:
                    integrator = CRDGitOpsIntegrator(fabric)
                    drift_summary = integrator.get_drift_summary()
                    fabric_summaries.append({
                        'fabric_id': fabric.id,
                        'fabric_name': fabric.name,
                        'git_configured': bool(fabric.git_repository_url),
                        'total_resources': drift_summary['total_resources'],
                        'drift_count': drift_summary['drifted'],
                        'drift_percentage': drift_summary['drift_percentage']
                    })
                except Exception as e:
                    logger.error(f"Failed to get summary for fabric {fabric.name}: {e}")
                    fabric_summaries.append({
                        'fabric_id': fabric.id,
                        'fabric_name': fabric.name,
                        'error': str(e)
                    })
            
            return Response({
                'global_stats': {
                    'total_fabrics': total_fabrics,
                    'configured_fabrics': configured_fabrics,
                    'total_resources': total_resources,
                    'drifted_resources': drifted_resources,
                    'global_drift_percentage': (drifted_resources / total_resources * 100) if total_resources > 0 else 0
                },
                'fabric_summaries': fabric_summaries
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Global GitOps status failed: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DriftAnalysisAPIView(APIView):
    """API endpoint for drift analysis operations"""
    
    def post(self, request):
        """Trigger drift analysis for specific fabric or all fabrics"""
        fabric_id = request.data.get('fabric_id')
        
        try:
            if fabric_id:
                # Analyze specific fabric
                fabric = get_object_or_404(models.HedgehogFabric, id=fabric_id)
                resources = models.HedgehogResource.objects.filter(fabric=fabric)
                
                results = {
                    'fabric': fabric.name,
                    'analyzed': 0,
                    'errors': 0,
                    'details': []
                }
                
                for resource in resources:
                    try:
                        drift_result = resource.calculate_drift()
                        results['analyzed'] += 1
                        if drift_result.get('success'):
                            results['details'].append({
                                'resource': f"{resource.kind}/{resource.name}",
                                'drift_status': drift_result['drift_status'],
                                'drift_score': drift_result['drift_score']
                            })
                        else:
                            results['errors'] += 1
                    except Exception as e:
                        results['errors'] += 1
                        logger.error(f"Drift analysis failed for {resource}: {e}")
                
                return Response(results, status=status.HTTP_200_OK)
            
            else:
                # Analyze all fabrics
                fabrics = models.HedgehogFabric.objects.all()
                results = {
                    'analyzed_fabrics': 0,
                    'total_resources': 0,
                    'errors': 0,
                    'fabric_results': []
                }
                
                for fabric in fabrics:
                    try:
                        resources = models.HedgehogResource.objects.filter(fabric=fabric)
                        fabric_analyzed = 0
                        fabric_errors = 0
                        
                        for resource in resources:
                            try:
                                resource.calculate_drift()
                                fabric_analyzed += 1
                            except Exception:
                                fabric_errors += 1
                        
                        results['fabric_results'].append({
                            'fabric': fabric.name,
                            'analyzed': fabric_analyzed,
                            'errors': fabric_errors
                        })
                        
                        results['analyzed_fabrics'] += 1
                        results['total_resources'] += fabric_analyzed
                        results['errors'] += fabric_errors
                        
                    except Exception as e:
                        results['errors'] += 1
                        logger.error(f"Fabric analysis failed for {fabric.name}: {e}")
                
                return Response(results, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Drift analysis failed: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GitAuthenticationAPIView(APIView):
    """API endpoint for Git authentication validation"""
    
    def post(self, request):
        """Validate Git authentication credentials"""
        if not GIT_AVAILABLE:
            return Response({
                'success': False,
                'error': 'Git functionality is not available. Please install GitPython dependency.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
        try:
            auth_method = request.data.get('method', 'token')
            repository_url = request.data.get('repository_url', '')
            branch = request.data.get('branch', 'main')
            
            if not repository_url:
                return Response({
                    'success': False,
                    'error': 'Repository URL is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create temporary directory for git operations
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    if auth_method == 'token':
                        token = request.data.get('token', '')
                        if not token:
                            return Response({
                                'success': False,
                                'error': 'Token is required for token authentication'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        
                        # Validate token format
                        if not self._validate_token_format(token):
                            return Response({
                                'success': False,
                                'error': 'Invalid token format'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        
                        # Test repository access with token
                        result = self._test_token_access(repository_url, token, branch, temp_dir)
                        
                    elif auth_method == 'ssh':
                        private_key = request.data.get('private_key', '')
                        passphrase = request.data.get('passphrase', '')
                        
                        if not private_key:
                            return Response({
                                'success': False,
                                'error': 'Private key is required for SSH authentication'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        
                        # Validate SSH key format
                        if not self._validate_ssh_key_format(private_key):
                            return Response({
                                'success': False,
                                'error': 'Invalid SSH key format'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        
                        # Test repository access with SSH key
                        result = self._test_ssh_access(repository_url, private_key, passphrase, branch, temp_dir)
                        
                    elif auth_method == 'basic':
                        username = request.data.get('username', '')
                        password = request.data.get('password', '')
                        
                        if not username or not password:
                            return Response({
                                'success': False,
                                'error': 'Username and password are required for basic authentication'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        
                        # Test repository access with basic auth
                        result = self._test_basic_auth_access(repository_url, username, password, branch, temp_dir)
                        
                    else:
                        return Response({
                            'success': False,
                            'error': 'Unsupported authentication method'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    return Response(result, status=status.HTTP_200_OK)
                    
                except GitAuthenticationError as e:
                    return Response({
                        'success': False,
                        'error': str(e)
                    }, status=status.HTTP_401_UNAUTHORIZED)
                    
                except Exception as e:
                    logger.error(f"Git authentication test failed: {e}")
                    return Response({
                        'success': False,
                        'error': f'Authentication test failed: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
        except Exception as e:
            logger.error(f"Git authentication validation failed: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _validate_token_format(self, token):
        """Validate token format for different providers"""
        token = token.strip()
        
        # GitHub personal access token format
        if token.startswith('ghp_') or token.startswith('github_pat_'):
            return len(token) > 20
        
        # GitLab personal access token format
        if token.startswith('glpat-'):
            return len(token) > 20
        
        # Generic token validation (at least 10 characters)
        return len(token) >= 10
    
    def _validate_ssh_key_format(self, private_key):
        """Validate SSH private key format"""
        private_key = private_key.strip()
        
        # Check for common SSH key headers
        valid_headers = [
            '-----BEGIN OPENSSH PRIVATE KEY-----',
            '-----BEGIN RSA PRIVATE KEY-----',
            '-----BEGIN DSA PRIVATE KEY-----',
            '-----BEGIN EC PRIVATE KEY-----',
            '-----BEGIN PRIVATE KEY-----'
        ]
        
        return any(header in private_key for header in valid_headers)
    
    def _test_token_access(self, repository_url, token, branch, temp_dir):
        """Test repository access with token authentication"""
        try:
            # Modify URL to include token
            if repository_url.startswith('https://github.com/'):
                auth_url = repository_url.replace('https://github.com/', f'https://{token}@github.com/')
            elif repository_url.startswith('https://gitlab.com/'):
                auth_url = repository_url.replace('https://gitlab.com/', f'https://oauth2:{token}@gitlab.com/')
            else:
                # Generic git provider
                auth_url = repository_url.replace('https://', f'https://token:{token}@')
            
            # Test clone operation
            repo = git.Repo.clone_from(auth_url, temp_dir, branch=branch, depth=1)
            
            # Get repository information
            remote = repo.remotes.origin
            remote_url = remote.url
            
            # Test fetch operation
            remote.fetch()
            
            return {
                'success': True,
                'message': 'Token authentication successful',
                'repository_info': {
                    'url': repository_url,
                    'branch': branch,
                    'accessible': True,
                    'permissions': 'read/write' if self._test_write_access(repo) else 'read-only'
                }
            }
            
        except git.exc.GitCommandError as e:
            if 'Authentication failed' in str(e) or 'access denied' in str(e).lower():
                raise GitAuthenticationError('Token authentication failed - check token permissions')
            elif 'Repository not found' in str(e):
                raise GitAuthenticationError('Repository not found or no access')
            else:
                raise GitAuthenticationError(f'Git operation failed: {str(e)}')
    
    def _test_ssh_access(self, repository_url, private_key, passphrase, branch, temp_dir):
        """Test repository access with SSH key authentication"""
        try:
            # Create temporary SSH key file
            ssh_key_file = os.path.join(temp_dir, 'id_rsa')
            with open(ssh_key_file, 'w') as f:
                f.write(private_key)
            os.chmod(ssh_key_file, 0o600)
            
            # Set up SSH command with key
            ssh_cmd = f'ssh -i {ssh_key_file} -o StrictHostKeyChecking=no'
            if passphrase:
                # Note: In production, use proper SSH agent or key management
                ssh_cmd += f' -o PasswordAuthentication=yes'
            
            # Set up git environment
            env = os.environ.copy()
            env['GIT_SSH_COMMAND'] = ssh_cmd
            
            # Test clone operation
            repo = git.Repo.clone_from(repository_url, temp_dir, branch=branch, depth=1, env=env)
            
            # Test fetch operation
            remote = repo.remotes.origin
            remote.fetch()
            
            return {
                'success': True,
                'message': 'SSH key authentication successful',
                'repository_info': {
                    'url': repository_url,
                    'branch': branch,
                    'accessible': True,
                    'permissions': 'read/write' if self._test_write_access(repo) else 'read-only'
                }
            }
            
        except git.exc.GitCommandError as e:
            if 'Permission denied' in str(e) or 'Authentication failed' in str(e):
                raise GitAuthenticationError('SSH key authentication failed - check key and permissions')
            elif 'Repository not found' in str(e):
                raise GitAuthenticationError('Repository not found or no access')
            else:
                raise GitAuthenticationError(f'Git operation failed: {str(e)}')
    
    def _test_basic_auth_access(self, repository_url, username, password, branch, temp_dir):
        """Test repository access with basic authentication"""
        try:
            # Modify URL to include credentials
            if repository_url.startswith('https://'):
                auth_url = repository_url.replace('https://', f'https://{username}:{password}@')
            else:
                raise GitAuthenticationError('Basic authentication requires HTTPS URL')
            
            # Test clone operation
            repo = git.Repo.clone_from(auth_url, temp_dir, branch=branch, depth=1)
            
            # Test fetch operation
            remote = repo.remotes.origin
            remote.fetch()
            
            return {
                'success': True,
                'message': 'Basic authentication successful',
                'repository_info': {
                    'url': repository_url,
                    'branch': branch,
                    'accessible': True,
                    'permissions': 'read/write' if self._test_write_access(repo) else 'read-only'
                }
            }
            
        except git.exc.GitCommandError as e:
            if 'Authentication failed' in str(e) or 'access denied' in str(e).lower():
                raise GitAuthenticationError('Basic authentication failed - check username and password')
            elif 'Repository not found' in str(e):
                raise GitAuthenticationError('Repository not found or no access')
            else:
                raise GitAuthenticationError(f'Git operation failed: {str(e)}')
    
    def _test_write_access(self, repo):
        """Test if we have write access to the repository"""
        try:
            # Create a test file
            test_file = os.path.join(repo.working_dir, '.hedgehog_test')
            with open(test_file, 'w') as f:
                f.write('test')
            
            # Stage and commit the test file
            repo.index.add([test_file])
            repo.index.commit('Test commit for permission check')
            
            # Try to push (this will fail if no write access)
            origin = repo.remotes.origin
            origin.push()
            
            return True
            
        except Exception:
            return False


class GitRepositoryValidationAPIView(APIView):
    """API endpoint for validating Git repository structure and content"""
    
    def post(self, request):
        """Validate Git repository structure and discover YAML files"""
        if not GIT_AVAILABLE:
            return Response({
                'success': False,
                'error': 'Git functionality is not available. Please install GitPython dependency.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
        try:
            repository_url = request.data.get('repository_url', '')
            branch = request.data.get('branch', 'main')
            path = request.data.get('path', 'hedgehog/')
            auth_data = request.data.get('auth_data', {})
            
            if not repository_url:
                return Response({
                    'success': False,
                    'error': 'Repository URL is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Clone repository with authentication
                    repo = self._clone_with_auth(repository_url, branch, temp_dir, auth_data)
                    
                    # Discover YAML files
                    yaml_files = self._discover_yaml_files(repo, path)
                    
                    # Validate YAML files
                    validation_results = self._validate_yaml_files(yaml_files)
                    
                    # Check directory structure
                    structure_analysis = self._analyze_directory_structure(repo, path)
                    
                    return Response({
                        'success': True,
                        'repository_info': {
                            'url': repository_url,
                            'branch': branch,
                            'path': path,
                            'total_files': len(yaml_files),
                            'valid_files': len([f for f in validation_results if f['valid']]),
                            'invalid_files': len([f for f in validation_results if not f['valid']])
                        },
                        'yaml_files': validation_results,
                        'structure_analysis': structure_analysis
                    }, status=status.HTTP_200_OK)
                    
                except Exception as e:
                    logger.error(f"Repository validation failed: {e}")
                    return Response({
                        'success': False,
                        'error': str(e)
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
        except Exception as e:
            logger.error(f"Git repository validation failed: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _clone_with_auth(self, repository_url, branch, temp_dir, auth_data):
        """Clone repository with appropriate authentication"""
        auth_method = auth_data.get('method', 'token')
        
        if auth_method == 'token':
            token = auth_data.get('token', '')
            if repository_url.startswith('https://github.com/'):
                auth_url = repository_url.replace('https://github.com/', f'https://{token}@github.com/')
            elif repository_url.startswith('https://gitlab.com/'):
                auth_url = repository_url.replace('https://gitlab.com/', f'https://oauth2:{token}@gitlab.com/')
            else:
                auth_url = repository_url.replace('https://', f'https://token:{token}@')
            
            return git.Repo.clone_from(auth_url, temp_dir, branch=branch)
            
        elif auth_method == 'ssh':
            private_key = auth_data.get('private_key', '')
            ssh_key_file = os.path.join(temp_dir, 'id_rsa')
            with open(ssh_key_file, 'w') as f:
                f.write(private_key)
            os.chmod(ssh_key_file, 0o600)
            
            env = os.environ.copy()
            env['GIT_SSH_COMMAND'] = f'ssh -i {ssh_key_file} -o StrictHostKeyChecking=no'
            
            return git.Repo.clone_from(repository_url, temp_dir, branch=branch, env=env)
            
        elif auth_method == 'basic':
            username = auth_data.get('username', '')
            password = auth_data.get('password', '')
            auth_url = repository_url.replace('https://', f'https://{username}:{password}@')
            
            return git.Repo.clone_from(auth_url, temp_dir, branch=branch)
            
        else:
            raise ValueError(f'Unsupported authentication method: {auth_method}')
    
    def _discover_yaml_files(self, repo, path):
        """Discover YAML files in the repository"""
        yaml_files = []
        search_path = os.path.join(repo.working_dir, path)
        
        if os.path.exists(search_path):
            for root, dirs, files in os.walk(search_path):
                for file in files:
                    if file.endswith(('.yaml', '.yml')):
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, repo.working_dir)
                        yaml_files.append({
                            'path': relative_path,
                            'name': file,
                            'size': os.path.getsize(file_path)
                        })
        
        return yaml_files
    
    def _validate_yaml_files(self, yaml_files):
        """Validate YAML files for Hedgehog CRD compatibility"""
        import yaml
        
        validation_results = []
        
        for file_info in yaml_files:
            try:
                with open(file_info['path'], 'r') as f:
                    content = f.read()
                
                # Parse YAML
                docs = list(yaml.safe_load_all(content))
                
                # Validate each document
                valid_docs = []
                invalid_docs = []
                
                for doc in docs:
                    if doc and isinstance(doc, dict):
                        # Check for Kubernetes resource structure
                        if 'apiVersion' in doc and 'kind' in doc:
                            # Check if it's a Hedgehog CRD
                            if self._is_hedgehog_crd(doc):
                                valid_docs.append(doc)
                            else:
                                invalid_docs.append({
                                    'doc': doc,
                                    'error': 'Not a Hedgehog CRD'
                                })
                        else:
                            invalid_docs.append({
                                'doc': doc,
                                'error': 'Missing required fields (apiVersion, kind)'
                            })
                    else:
                        invalid_docs.append({
                            'doc': doc,
                            'error': 'Invalid YAML document structure'
                        })
                
                validation_results.append({
                    'file': file_info['name'],
                    'path': file_info['path'],
                    'valid': len(invalid_docs) == 0,
                    'total_documents': len(docs),
                    'valid_documents': len(valid_docs),
                    'invalid_documents': len(invalid_docs),
                    'errors': [doc['error'] for doc in invalid_docs]
                })
                
            except yaml.YAMLError as e:
                validation_results.append({
                    'file': file_info['name'],
                    'path': file_info['path'],
                    'valid': False,
                    'error': f'YAML parsing error: {str(e)}'
                })
            except Exception as e:
                validation_results.append({
                    'file': file_info['name'],
                    'path': file_info['path'],
                    'valid': False,
                    'error': f'File validation error: {str(e)}'
                })
        
        return validation_results
    
    def _is_hedgehog_crd(self, doc):
        """Check if a document is a Hedgehog CRD"""
        hedgehog_kinds = [
            'VPC', 'External', 'ExternalAttachment', 'ExternalPeering', 
            'IPv4Namespace', 'VPCAttachment', 'VPCPeering',
            'Connection', 'Server', 'Switch', 'SwitchGroup', 'VLANNamespace'
        ]
        
        api_version = doc.get('apiVersion', '')
        kind = doc.get('kind', '')
        
        # Check for Hedgehog API versions
        if any(api in api_version for api in ['vpc.githedgehog.com', 'wiring.githedgehog.com']):
            return kind in hedgehog_kinds
        
        return False
    
    def _analyze_directory_structure(self, repo, path):
        """Analyze directory structure for recommended organization"""
        search_path = os.path.join(repo.working_dir, path)
        
        recommended_dirs = [
            'vpc', 'external', 'switch', 'connection', 'server', 'namespace'
        ]
        
        analysis = {
            'path_exists': os.path.exists(search_path),
            'recommended_structure': {},
            'custom_directories': [],
            'suggestions': []
        }
        
        if analysis['path_exists']:
            # Check for recommended directories
            for dir_name in recommended_dirs:
                dir_path = os.path.join(search_path, dir_name)
                analysis['recommended_structure'][dir_name] = {
                    'exists': os.path.exists(dir_path),
                    'file_count': len([f for f in os.listdir(dir_path) if f.endswith(('.yaml', '.yml'))]) if os.path.exists(dir_path) else 0
                }
            
            # Find custom directories
            if os.path.exists(search_path):
                for item in os.listdir(search_path):
                    item_path = os.path.join(search_path, item)
                    if os.path.isdir(item_path) and item not in recommended_dirs:
                        analysis['custom_directories'].append(item)
        
        # Generate suggestions
        if not analysis['path_exists']:
            analysis['suggestions'].append(f'Create base directory: {path}')
        
        for dir_name, info in analysis['recommended_structure'].items():
            if not info['exists']:
                analysis['suggestions'].append(f'Create recommended directory: {path}/{dir_name}')
        
        return analysis


# ArgoCD Setup Wizard API Views (Week 2 MVP2)
class ArgoCDPrerequisitesAPIView(APIView):
    """API endpoint for ArgoCD prerequisites checking"""
    
    def post(self, request):
        """Check ArgoCD installation prerequisites for a fabric"""
        try:
            fabric_id = request.data.get('fabric_id')
            if not fabric_id:
                return Response({
                    'success': False,
                    'error': 'fabric_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            fabric = get_object_or_404(models.HedgehogFabric, id=fabric_id)
            
            # Run async prerequisites check
            import asyncio
            
            async def run_prerequisites_check():
                try:
                    from ..utils.argocd_installer import ArgoCDIntegrationManager
                    integration_manager = ArgoCDIntegrationManager(fabric)
                    return await integration_manager.check_prerequisites()
                except Exception as e:
                    logger.error(f"Prerequisites check failed for fabric {fabric_id}: {e}")
                    return {
                        'success': False,
                        'error': str(e)
                    }
            
            result = asyncio.run(run_prerequisites_check())
            
            if result.get('success'):
                return Response({
                    'success': True,
                    'checks': {
                        'cluster_connection': result.get('cluster_accessible', False),
                        'cluster_permissions': result.get('cluster_admin', False),
                        'argocd_namespace': result.get('namespace_available', False),
                        'resource_availability': result.get('sufficient_resources', False),
                        'network_policies': result.get('network_compatible', False)
                    },
                    'details': result.get('details', 'Prerequisites check completed')
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': result.get('error', 'Prerequisites check failed'),
                    'checks': {
                        'cluster_connection': False,
                        'cluster_permissions': False,
                        'argocd_namespace': False,
                        'resource_availability': False,
                        'network_policies': False
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Prerequisites API failed: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ArgoCDSetupAPIView(APIView):
    """API endpoint for starting ArgoCD setup process"""
    
    def post(self, request):
        """Start ArgoCD setup process for a fabric"""
        try:
            fabric_id = request.data.get('fabric_id')
            if not fabric_id:
                return Response({
                    'success': False,
                    'error': 'fabric_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            fabric = get_object_or_404(models.HedgehogFabric, id=fabric_id)
            
            # Extract configuration from request
            argocd_config = request.data.get('argocd', {})
            repository_config = request.data.get('repository', {})
            application_config = request.data.get('application', {})
            
            # Update fabric with repository configuration
            if repository_config.get('url'):
                fabric.git_repository_url = repository_config['url']
                fabric.git_branch = repository_config.get('branch', 'main')
                fabric.git_path = repository_config.get('path', 'hedgehog/')
                fabric.git_token = repository_config.get('token', '')
                fabric.git_username = repository_config.get('username', '')
                fabric.save()
            
            # Store installation configuration
            installation_id = f"argocd-setup-{fabric_id}-{int(time.time())}"
            installation_config = {
                'installation_id': installation_id,
                'fabric_id': fabric_id,
                'argocd_config': argocd_config,
                'repository_config': repository_config,
                'application_config': application_config,
                'status': 'started',
                'current_step': 'validate-config',
                'completed_steps': [],
                'failed_steps': []
            }
            
            # Store installation state (in production, use Redis or database)
            if not hasattr(request, 'session'):
                request.session = {}
            if 'argocd_installations' not in request.session:
                request.session['argocd_installations'] = {}
            request.session['argocd_installations'][installation_id] = installation_config
            request.session.save()
            
            # Start async installation process
            import asyncio
            import threading
            
            def start_installation():
                """Start installation in background thread"""
                try:
                    async def run_installation():
                        try:
                            result = await fabric.setup_argocd_gitops(repository_config)
                            
                            # Update installation status
                            if installation_id in request.session.get('argocd_installations', {}):
                                request.session['argocd_installations'][installation_id].update({
                                    'status': 'completed' if result.get('overall_success') else 'error',
                                    'current_step': 'validate-setup',
                                    'completed_steps': ['validate-config', 'install-argocd', 'wait-ready', 'configure-repo', 'create-app', 'initial-sync', 'validate-setup'],
                                    'result': result,
                                    'argocd_status': result.get('argocd_status')
                                })
                                request.session.save()
                                
                        except Exception as e:
                            logger.error(f"Installation failed for {installation_id}: {e}")
                            if installation_id in request.session.get('argocd_installations', {}):
                                request.session['argocd_installations'][installation_id].update({
                                    'status': 'error',
                                    'error': str(e),
                                    'failed_steps': [request.session['argocd_installations'][installation_id].get('current_step', 'unknown')]
                                })
                                request.session.save()
                    
                    asyncio.run(run_installation())
                    
                except Exception as e:
                    logger.error(f"Installation thread failed for {installation_id}: {e}")
            
            # Start installation in background thread
            installation_thread = threading.Thread(target=start_installation)
            installation_thread.daemon = True
            installation_thread.start()
            
            return Response({
                'success': True,
                'installation_id': installation_id,
                'message': 'ArgoCD setup process started',
                'fabric_name': fabric.name
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"ArgoCD setup API failed: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ArgoCDProgressAPIView(APIView):
    """API endpoint for monitoring ArgoCD setup progress"""
    
    def get(self, request, installation_id):
        """Get installation progress for a specific installation ID"""
        try:
            # Retrieve installation state
            installations = request.session.get('argocd_installations', {})
            installation = installations.get(installation_id)
            
            if not installation:
                return Response({
                    'success': False,
                    'error': 'Installation not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Build progress response
            progress_data = {
                'installation_id': installation_id,
                'status': installation.get('status', 'unknown'),
                'current_step': installation.get('current_step'),
                'completed_steps': installation.get('completed_steps', []),
                'failed_steps': installation.get('failed_steps', []),
                'fabric_id': installation.get('fabric_id'),
            }
            
            # Add result data if available
            if installation.get('result'):
                progress_data['result'] = installation['result']
            
            # Add ArgoCD status if available
            if installation.get('argocd_status'):
                progress_data['argocd_status'] = installation['argocd_status']
            
            # Add error if available
            if installation.get('error'):
                progress_data['error'] = installation['error']
            
            return Response({
                'success': True,
                'progress': progress_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Progress monitoring failed for {installation_id}: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GitOpsTestConnectionAPIView(APIView):
    """API endpoint for testing Git repository connections (simplified for ArgoCD wizard)"""
    
    def post(self, request):
        """Test Git repository connection with simplified response"""
        try:
            url = request.data.get('url', '')
            branch = request.data.get('branch', 'main')
            auth_method = request.data.get('auth_method', 'token')
            token = request.data.get('token', '')
            username = request.data.get('username', '')
            
            if not url:
                return Response({
                    'success': False,
                    'error': 'Repository URL is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Use existing GitAuthenticationAPIView logic
            auth_view = GitAuthenticationAPIView()
            auth_request_data = {
                'method': auth_method,
                'repository_url': url,
                'branch': branch,
                'token': token,
                'username': username
            }
            
            # Create mock request for auth validation
            from django.http import HttpRequest
            mock_request = HttpRequest()
            mock_request.data = auth_request_data
            
            auth_response = auth_view.post(mock_request)
            auth_data = auth_response.data
            
            if auth_data.get('success'):
                # Get additional repository information
                repo_info = auth_data.get('repository_info', {})
                
                return Response({
                    'success': True,
                    'message': 'Repository connection successful',
                    'branch': branch,
                    'url': url,
                    'accessible': repo_info.get('accessible', True),
                    'permissions': repo_info.get('permissions', 'unknown'),
                    'latest_commit': 'abcd1234'  # Placeholder - in real implementation, get actual commit
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': auth_data.get('error', 'Connection test failed')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Git connection test failed: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Add time import for installation ID generation
import time