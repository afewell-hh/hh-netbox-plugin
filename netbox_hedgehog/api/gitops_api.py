"""
Unified GitOps API
RESTful API coordinating all Phase 3 services with WebSocket integration
for the GitOps File Management System.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.generic import View
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.core.paginator import Paginator
from django.contrib.auth.mixins import LoginRequiredMixin

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes

from ..models.fabric import HedgehogFabric
from ..models.git_repository import GitRepository
from ..models.gitops import HedgehogResource
from ..services.file_management_service import FileManagementService
from ..services.conflict_resolution_engine import ConflictResolutionEngine
from ..services.configuration_template_engine import ConfigurationTemplateEngine
from ..services.yaml_duplicate_detector import YamlDuplicateDetector
from ..services.gitops_ingestion_service import GitOpsIngestionService
from ..utils.git_operations import GitOperations
from ..utils.environment_manager import EnvironmentManager

logger = logging.getLogger(__name__)


class GitOpsUnifiedAPIView(APIView):
    """
    Unified API view for coordinating all Phase 3 GitOps components.
    Provides centralized access to file operations, conflict resolution,
    and template engine functionality.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, fabric_id=None):
        """Get comprehensive GitOps status for fabric or global overview."""
        try:
            if fabric_id:
                fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
                data = self._get_fabric_status(fabric)
            else:
                data = self._get_global_status()
            
            return Response({
                'success': True,
                'data': data,
                'timestamp': timezone.now()
            })
            
        except Exception as e:
            logger.error(f"GitOps API error: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, fabric_id=None):
        """Execute GitOps operations on fabric or globally."""
        try:
            operation = request.data.get('operation')
            if not operation:
                return Response({
                    'success': False,
                    'error': 'Operation not specified'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if fabric_id:
                fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
                result = self._execute_fabric_operation(fabric, operation, request.data)
            else:
                result = self._execute_global_operation(operation, request.data)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"GitOps operation error: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_fabric_status(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get comprehensive status for a specific fabric."""
        try:
            # Initialize services
            base_directory = self._get_fabric_directory(fabric)
            file_manager = FileManagementService(base_directory)
            conflict_resolver = ConflictResolutionEngine(fabric, base_directory)
            template_engine = ConfigurationTemplateEngine(fabric)
            
            # Collect status from all Phase 3 components
            status_data = {
                'fabric': {
                    'id': fabric.id,
                    'name': fabric.name,
                    'description': fabric.description or '',
                    'created': fabric.created.isoformat() if hasattr(fabric, 'created') else None,
                    'resources_count': fabric.gitops_resources.count()
                },
                'file_management': self._get_file_management_status(file_manager),
                'conflict_resolution': self._get_conflict_resolution_status(conflict_resolver),
                'template_engine': self._get_template_engine_status(template_engine),
                'git_repository': self._get_git_repository_status(fabric),
                'workflows': self._get_workflow_status(fabric),
                'metrics': self._get_fabric_metrics(fabric)
            }
            
            return status_data
            
        except Exception as e:
            logger.error(f"Failed to get fabric status: {str(e)}")
            return {
                'fabric': {'id': fabric.id, 'name': fabric.name, 'error': str(e)},
                'error': str(e)
            }
    
    def _get_global_status(self) -> Dict[str, Any]:
        """Get global GitOps system status."""
        try:
            fabrics = HedgehogFabric.objects.all()
            
            global_status = {
                'system': {
                    'total_fabrics': fabrics.count(),
                    'active_fabrics': fabrics.filter(
                        git_repositories__sync_enabled=True
                    ).distinct().count(),
                    'total_resources': HedgehogResource.objects.count(),
                    'last_updated': timezone.now()
                },
                'health': self._get_system_health(),
                'performance': self._get_performance_metrics(),
                'recent_operations': self._get_recent_operations(),
                'fabric_summary': [
                    {
                        'id': fabric.id,
                        'name': fabric.name,
                        'status': self._get_fabric_summary_status(fabric)
                    }
                    for fabric in fabrics[:10]  # Limit to first 10
                ]
            }
            
            return global_status
            
        except Exception as e:
            logger.error(f"Failed to get global status: {str(e)}")
            return {'error': str(e)}
    
    def _execute_fabric_operation(self, fabric: HedgehogFabric, operation: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an operation on a specific fabric."""
        try:
            base_directory = self._get_fabric_directory(fabric)
            
            if operation == 'sync':
                return self._execute_sync_operation(fabric, data)
            elif operation == 'generate_templates':
                return self._execute_template_generation(fabric, data)
            elif operation == 'resolve_conflicts':
                return self._execute_conflict_resolution(fabric, data)
            elif operation == 'file_operation':
                return self._execute_file_operation(fabric, data)
            elif operation == 'initialize_gitops':
                return self._execute_gitops_initialization(fabric, data)
            else:
                return {
                    'success': False,
                    'error': f'Unknown operation: {operation}'
                }
                
        except Exception as e:
            logger.error(f"Fabric operation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _execute_global_operation(self, operation: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a global operation across all fabrics."""
        try:
            if operation == 'global_sync':
                return self._execute_global_sync(data)
            elif operation == 'system_health_check':
                return self._execute_system_health_check(data)
            elif operation == 'cleanup_resources':
                return self._execute_cleanup_resources(data)
            else:
                return {
                    'success': False,
                    'error': f'Unknown global operation: {operation}'
                }
                
        except Exception as e:
            logger.error(f"Global operation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _execute_sync_operation(self, fabric: HedgehogFabric, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sync operation for a fabric."""
        try:
            ingestion_service = GitOpsIngestionService()
            
            # Execute sync with all Phase 3 components
            sync_result = ingestion_service.sync_fabric_with_integration(
                fabric=fabric,
                include_file_operations=True,
                include_conflict_resolution=True,
                include_template_generation=True
            )
            
            return {
                'success': sync_result.get('success', False),
                'operation': 'sync',
                'fabric_id': fabric.id,
                'files_processed': sync_result.get('files_processed', 0),
                'conflicts_resolved': sync_result.get('conflicts_resolved', 0),
                'templates_generated': sync_result.get('templates_generated', 0),
                'execution_time': sync_result.get('execution_time', 0),
                'timestamp': timezone.now()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Sync operation failed: {str(e)}'
            }
    
    def _execute_template_generation(self, fabric: HedgehogFabric, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute template generation for a fabric."""
        try:
            template_engine = ConfigurationTemplateEngine(fabric)
            
            force_regenerate = data.get('force_regenerate', False)
            template_filter = data.get('template_filter')
            
            result = template_engine.generate_fabric_configuration(
                force_regenerate=force_regenerate,
                template_filter=template_filter
            )
            
            return {
                'success': result.success,
                'operation': 'generate_templates',
                'fabric_id': fabric.id,
                'files_generated': len(result.files_generated),
                'files_updated': len(result.files_updated),
                'validation_errors': len(result.validation_errors),
                'execution_time': result.execution_time,
                'timestamp': timezone.now()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Template generation failed: {str(e)}'
            }
    
    def _execute_conflict_resolution(self, fabric: HedgehogFabric, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute conflict resolution for a fabric."""
        try:
            base_directory = self._get_fabric_directory(fabric)
            
            # Detect conflicts first
            detector = YamlDuplicateDetector(base_directory, fabric.name)
            duplicate_groups = detector.detect_duplicates().get('duplicate_groups', [])
            
            if not duplicate_groups:
                return {
                    'success': True,
                    'operation': 'resolve_conflicts',
                    'fabric_id': fabric.id,
                    'conflicts_found': 0,
                    'conflicts_resolved': 0,
                    'message': 'No conflicts found'
                }
            
            # Resolve conflicts
            conflict_resolver = ConflictResolutionEngine(fabric, base_directory)
            resolution_result = conflict_resolver.resolve_conflicts(duplicate_groups)
            
            return {
                'success': True,
                'operation': 'resolve_conflicts',
                'fabric_id': fabric.id,
                'conflicts_found': len(duplicate_groups),
                'conflicts_resolved': resolution_result.get('conflicts_resolved', 0),
                'conflicts_requiring_manual_review': resolution_result.get('conflicts_requiring_manual_review', 0),
                'resolution_strategies': resolution_result.get('strategy_usage', {}),
                'timestamp': timezone.now()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Conflict resolution failed: {str(e)}'
            }
    
    def _execute_file_operation(self, fabric: HedgehogFabric, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file operation for a fabric."""
        try:
            base_directory = self._get_fabric_directory(fabric)
            file_manager = FileManagementService(base_directory)
            
            operation_type = data.get('type')
            file_path = data.get('file_path')
            
            if operation_type == 'create':
                result = file_manager.create_file(
                    file_path=file_path,
                    content=data.get('content', ''),
                    metadata=data.get('metadata')
                )
            elif operation_type == 'update':
                result = file_manager.update_file(
                    file_path=file_path,
                    content=data.get('content', '')
                )
            elif operation_type == 'delete':
                result = file_manager.delete_file(
                    file_path=file_path,
                    create_backup=data.get('create_backup', True)
                )
            elif operation_type == 'move':
                result = file_manager.move_file(
                    source_path=file_path,
                    target_path=data.get('target_path')
                )
            else:
                return {
                    'success': False,
                    'error': f'Unknown file operation: {operation_type}'
                }
            
            return {
                'success': result.get('success', False),
                'operation': f'file_{operation_type}',
                'fabric_id': fabric.id,
                'file_path': file_path,
                'result': result,
                'timestamp': timezone.now()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'File operation failed: {str(e)}'
            }
    
    def _get_file_management_status(self, file_manager: FileManagementService) -> Dict[str, Any]:
        """Get file management service status."""
        try:
            files_with_metadata = file_manager.list_files_with_metadata()
            
            return {
                'service_active': True,
                'total_files': len(files_with_metadata),
                'managed_files': len([f for f in files_with_metadata if 'managed' in str(f.file_path)]),
                'raw_files': len([f for f in files_with_metadata if 'raw' in str(f.file_path)]),
                'backup_files': sum(len(f.backup_paths) for f in files_with_metadata),
                'last_operation': max([f.modified_at for f in files_with_metadata], default=None)
            }
        except Exception as e:
            return {'service_active': False, 'error': str(e)}
    
    def _get_conflict_resolution_status(self, conflict_resolver: ConflictResolutionEngine) -> Dict[str, Any]:
        """Get conflict resolution service status."""
        try:
            return {
                'service_active': True,
                'resolution_enabled': conflict_resolver.backup_enabled,
                'dry_run_mode': conflict_resolver.dry_run,
                'max_conflicts_per_batch': conflict_resolver.max_conflicts_per_batch,
                'files_deleted_count': conflict_resolver.deleted_files_count,
                'files_moved_count': conflict_resolver.moved_files_count,
                'safety_limits': {
                    'max_files_to_delete': conflict_resolver.max_files_to_delete,
                    'max_files_to_move': conflict_resolver.max_files_to_move
                }
            }
        except Exception as e:
            return {'service_active': False, 'error': str(e)}
    
    def _get_template_engine_status(self, template_engine: ConfigurationTemplateEngine) -> Dict[str, Any]:
        """Get template engine service status."""
        try:
            engine_status = template_engine.get_engine_status()
            return {
                'service_active': True,
                'configuration': engine_status.get('configuration', {}),
                'services': engine_status.get('services', {}),
                'metrics': engine_status.get('metrics', {}),
                'cache_stats': engine_status.get('cache_stats', {}),
                'active_operations': engine_status.get('active_operations', []),
                'recent_operations': engine_status.get('recent_operations', 0)
            }
        except Exception as e:
            return {'service_active': False, 'error': str(e)}
    
    def _get_git_repository_status(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get Git repository status for the fabric."""
        try:
            git_repo = fabric.git_repositories.first()
            if not git_repo:
                return {'repository_configured': False}
            
            return {
                'repository_configured': True,
                'url': git_repo.url,
                'branch': git_repo.branch,
                'sync_enabled': git_repo.sync_enabled,
                'last_sync_time': git_repo.last_sync_time.isoformat() if git_repo.last_sync_time else None,
                'sync_status': git_repo.sync_status,
                'credentials_configured': bool(git_repo.auth_token or git_repo.username)
            }
        except Exception as e:
            return {'repository_configured': False, 'error': str(e)}
    
    def _get_workflow_status(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get workflow status for the fabric."""
        return {
            'sync_status': {
                'status': 'idle',
                'last_execution': None,
                'next_scheduled': None
            },
            'template_generation': {
                'status': 'idle',
                'last_execution': None,
                'templates_available': 0
            },
            'conflict_resolution': {
                'status': 'idle',
                'last_execution': None,
                'active_conflicts': 0
            },
            'file_operations': {
                'status': 'idle',
                'last_execution': None,
                'pending_operations': 0
            }
        }
    
    def _get_fabric_metrics(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get performance and usage metrics for the fabric."""
        return {
            'performance': {
                'avg_sync_time': 0.0,
                'avg_template_generation_time': 0.0,
                'avg_conflict_resolution_time': 0.0
            },
            'usage': {
                'total_syncs': 0,
                'successful_syncs': 0,
                'failed_syncs': 0,
                'templates_generated': 0,
                'conflicts_resolved': 0
            },
            'storage': {
                'total_files': 0,
                'total_size': 0,
                'backup_size': 0
            }
        }
    
    def _get_fabric_directory(self, fabric: HedgehogFabric) -> Path:
        """Get the base directory for fabric files."""
        base_dir = Path(getattr(settings, 'HEDGEHOG_GITOPS_BASE_DIR', '/tmp/hedgehog-gitops'))
        return base_dir / 'fabrics' / fabric.name
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        return {
            'status': 'healthy',
            'services': {
                'file_management': 'healthy',
                'conflict_resolution': 'healthy',
                'template_engine': 'healthy',
                'git_operations': 'healthy'
            },
            'last_check': timezone.now().isoformat()
        }
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get system-wide performance metrics."""
        return {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'avg_response_time': 0.0,
            'uptime': '0d 0h 0m',
            'memory_usage': '0MB',
            'cpu_usage': '0%'
        }
    
    def _get_recent_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent operations across all fabrics."""
        # This would be implemented with proper operation logging
        return []
    
    def _get_fabric_summary_status(self, fabric: HedgehogFabric) -> str:
        """Get summary status for a fabric."""
        git_repo = fabric.git_repositories.first()
        if git_repo and git_repo.sync_enabled:
            return 'active'
        return 'inactive'


# File Browser API Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gitops_file_browser_api(request, fabric_id):
    """API endpoint for file browser functionality."""
    try:
        fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
        path = request.GET.get('path', '/')
        
        # Use the dashboard view's file browser logic
        from ..views.gitops_dashboard import GitOpsManagementDashboardView
        dashboard_view = GitOpsManagementDashboardView()
        file_data = dashboard_view._get_file_browser_data(fabric, path)
        
        return Response({
            'success': True,
            'data': file_data
        })
        
    except Exception as e:
        logger.error(f"File browser API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gitops_file_preview_api(request, fabric_id):
    """API endpoint for file preview functionality."""
    try:
        fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
        file_path = request.GET.get('path')
        
        if not file_path:
            return Response({
                'success': False,
                'error': 'File path not specified'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Use the dashboard view's file preview logic
        from ..views.gitops_dashboard import GitOpsFilePreviewView
        preview_view = GitOpsFilePreviewView()
        
        # Simulate the request for the preview view
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.GET = {'path': file_path}
        
        mock_request = MockRequest(request.user)
        response = preview_view.get(mock_request, fabric_id)
        
        if hasattr(response, 'content'):
            import json
            return Response(json.loads(response.content))
        
        return response
        
    except Exception as e:
        logger.error(f"File preview API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gitops_visual_diff_api(request, fabric_id):
    """API endpoint for visual diff functionality."""
    try:
        fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
        
        # Use the dashboard view's visual diff logic
        from ..views.gitops_dashboard import GitOpsVisualDiffView
        diff_view = GitOpsVisualDiffView()
        
        class MockRequest:
            def __init__(self, user):
                self.user = user
        
        mock_request = MockRequest(request.user)
        response = diff_view.get(mock_request, fabric_id)
        
        if hasattr(response, 'content'):
            import json
            return Response(json.loads(response.content))
        
        return response
        
    except Exception as e:
        logger.error(f"Visual diff API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gitops_workflow_status_api(request, fabric_id):
    """API endpoint for workflow status functionality."""
    try:
        fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
        
        # Use the dashboard view's workflow status logic
        from ..views.gitops_dashboard import GitOpsWorkflowStatusView
        workflow_view = GitOpsWorkflowStatusView()
        
        class MockRequest:
            def __init__(self, user):
                self.user = user
        
        mock_request = MockRequest(request.user)
        response = workflow_view.get(mock_request, fabric_id)
        
        if hasattr(response, 'content'):
            import json
            return Response(json.loads(response.content))
        
        return response
        
    except Exception as e:
        logger.error(f"Workflow status API error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# URL patterns for the unified GitOps API
def get_gitops_api_urls():
    """Get URL patterns for the unified GitOps API."""
    from django.urls import path
    
    return [
        # Unified GitOps API
        path('gitops-api/', GitOpsUnifiedAPIView.as_view(), name='gitops-unified-api'),
        path('gitops-api/<int:fabric_id>/', GitOpsUnifiedAPIView.as_view(), name='gitops-unified-api-fabric'),
        
        # Dashboard API endpoints
        path('gitops-dashboard/<int:fabric_id>/file-browser/', gitops_file_browser_api, name='gitops-dashboard-file-browser-api'),
        path('gitops-dashboard/<int:fabric_id>/file-preview/', gitops_file_preview_api, name='gitops-dashboard-file-preview-api'),
        path('gitops-dashboard/<int:fabric_id>/visual-diff/', gitops_visual_diff_api, name='gitops-dashboard-visual-diff-api'),
        path('gitops-dashboard/<int:fabric_id>/workflow-status/', gitops_workflow_status_api, name='gitops-dashboard-workflow-status-api'),
    ]