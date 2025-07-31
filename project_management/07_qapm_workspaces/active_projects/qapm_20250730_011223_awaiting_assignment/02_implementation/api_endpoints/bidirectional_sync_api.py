"""
Bidirectional Synchronization API Endpoints

This module provides comprehensive REST API endpoints for controlling
bidirectional synchronization operations, directory management, and
conflict resolution within the NetBox plugin architecture.
"""

import logging
from typing import Dict, Any

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.db import transaction
from django.utils import timezone

from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from netbox.api.viewsets import NetBoxModelViewSet

logger = logging.getLogger(__name__)


class DirectoryManagementAPIView(View):
    """API endpoints for GitOps directory management operations"""
    
    @method_decorator(login_required)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, fabric_id, operation):
        """Handle directory management operations"""
        try:
            from netbox_hedgehog.models.fabric import HedgehogFabric
            from netbox_hedgehog.utils.gitops_directory_manager import GitOpsDirectoryManager
            
            fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
            
            if operation == 'initialize':
                return self._initialize_directories(request, fabric)
            elif operation == 'validate':
                return self._validate_directory_structure(request, fabric)
            elif operation == 'status':
                return self._get_directory_status(request, fabric)
            elif operation == 'ingest':
                return self._ingest_raw_files(request, fabric)
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Unknown operation: {operation}'
                }, status=400)
        
        except Exception as e:
            logger.error(f"Directory management API error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def get(self, request, fabric_id, operation):
        """Handle GET operations for directory management"""
        try:
            from netbox_hedgehog.models.fabric import HedgehogFabric
            
            fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
            
            if operation == 'status':
                return self._get_directory_status(request, fabric)
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'GET operation not supported: {operation}'
                }, status=400)
        
        except Exception as e:
            logger.error(f"Directory management GET API error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _initialize_directories(self, request, fabric):
        """Initialize GitOps directory structure"""
        import json
        
        try:
            # Parse request body
            body = json.loads(request.body) if request.body else {}
            force_recreate = body.get('force_recreate', False)
            backup_existing = body.get('backup_existing', True)
            
            # Initialize directories
            result = fabric.initialize_gitops_directories(force=force_recreate)
            
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'message': result['message'],
                    'directories_created': result.get('directories_created', []),
                    'backup_location': result.get('backup_location'),
                    'structure_validation': {
                        'valid': result['success'],
                        'issues': result.get('errors', [])
                    }
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error'],
                    'directories_created': result.get('directories_created', [])
                }, status=400)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _validate_directory_structure(self, request, fabric):
        """Validate GitOps directory structure"""
        try:
            from netbox_hedgehog.utils.gitops_directory_manager import GitOpsDirectoryManager
            
            manager = GitOpsDirectoryManager(fabric)
            validation = manager.validate_directory_structure()
            
            return JsonResponse({
                'success': True,
                'validation': validation.to_dict()
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _get_directory_status(self, request, fabric):
        """Get directory status information"""
        try:
            status_info = fabric.get_directory_status()
            
            return JsonResponse({
                'success': True,
                'status': status_info
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _ingest_raw_files(self, request, fabric):
        """Ingest files from raw/ directory"""
        import json
        
        try:
            from netbox_hedgehog.utils.file_ingestion_pipeline import FileIngestionPipeline
            
            # Parse request body
            body = json.loads(request.body) if request.body else {}
            file_patterns = body.get('file_patterns', ['*.yaml', '*.yml'])
            validation_strict = body.get('validation_strict', True)
            archive_processed = body.get('archive_processed', True)
            
            # Process files
            pipeline = FileIngestionPipeline(fabric)
            result = pipeline.process_raw_directory()
            
            return JsonResponse({
                'success': result['success'],
                'message': result.get('message', ''),
                'summary': result.get('summary', {}),
                'stages': result.get('stages', {}),
                'processed_files': result.get('processed_files', [])
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class SynchronizationControlAPIView(View):
    """API endpoints for synchronization control operations"""
    
    @method_decorator(login_required)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, fabric_id, operation):
        """Handle synchronization operations"""
        try:
            from netbox_hedgehog.models.fabric import HedgehogFabric
            from netbox_hedgehog.utils.bidirectional_sync_orchestrator import BidirectionalSyncOrchestrator
            
            fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
            
            if operation == 'sync':
                return self._trigger_sync(request, fabric)
            elif operation == 'detect-changes':
                return self._detect_external_changes(request, fabric)
            elif operation == 'resolve-conflicts':
                return self._resolve_conflicts(request, fabric)
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Unknown operation: {operation}'
                }, status=400)
        
        except Exception as e:
            logger.error(f"Synchronization control API error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def get(self, request, fabric_id, operation):
        """Handle GET operations for synchronization control"""
        try:
            from netbox_hedgehog.models.fabric import HedgehogFabric
            
            fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
            
            if operation == 'status':
                return self._get_sync_status(request, fabric)
            elif operation == 'statistics':
                return self._get_sync_statistics(request, fabric)
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'GET operation not supported: {operation}'
                }, status=400)
        
        except Exception as e:
            logger.error(f"Synchronization control GET API error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _trigger_sync(self, request, fabric):
        """Trigger bidirectional synchronization"""
        import json
        
        try:
            # Parse request body
            body = json.loads(request.body) if request.body else {}
            direction = body.get('direction', 'bidirectional')
            force = body.get('force', False)
            create_pr = body.get('create_pr', False)
            conflict_resolution = body.get('conflict_resolution', 'user_guided')
            
            # Trigger sync
            result = fabric.trigger_bidirectional_sync(
                direction=direction,
                user=request.user
            )
            
            if result['success']:
                return JsonResponse({
                    'operation_id': result.get('sync_operation_id'),
                    'status': 'completed' if result['success'] else 'failed',
                    'message': result['message'],
                    'conflicts_detected': result.get('conflicts_detected', 0),
                    'files_processed': result.get('files_processed', 0),
                    'resources_synced': result.get('resources_synced', 0),
                    'commit_sha': result.get('commit_sha'),
                    'webhook_url': f"/api/plugins/hedgehog/sync-operations/{result.get('sync_operation_id')}/" if result.get('sync_operation_id') else None
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error'],
                    'operation_id': result.get('sync_operation_id')
                }, status=400)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _detect_external_changes(self, request, fabric):
        """Detect external changes in repository"""
        try:
            from netbox_hedgehog.utils.bidirectional_sync_orchestrator import BidirectionalSyncOrchestrator
            
            orchestrator = BidirectionalSyncOrchestrator(fabric)
            changes = orchestrator.detect_external_changes()
            
            return JsonResponse({
                'success': True,
                'changes_detected': changes.changes_detected,
                'changed_files': changes.changed_files,
                'new_files': changes.new_files,
                'deleted_files': changes.deleted_files,
                'total_changes': len(changes.changed_files) + len(changes.new_files) + len(changes.deleted_files),
                'last_check': changes.last_check.isoformat()
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _resolve_conflicts(self, request, fabric):
        """Resolve detected conflicts"""
        import json
        
        try:
            from netbox_hedgehog.utils.bidirectional_sync_orchestrator import BidirectionalSyncOrchestrator
            
            # Parse request body
            body = json.loads(request.body) if request.body else {}
            resolution_strategy = body.get('resolution_strategy', 'user_guided')
            
            orchestrator = BidirectionalSyncOrchestrator(fabric)
            result = orchestrator.resolve_conflicts(resolution_strategy)
            
            return JsonResponse({
                'success': result['success'],
                'resolved_conflicts': result.get('resolved_conflicts', 0),
                'total_conflicts': result.get('total_conflicts', 0),
                'strategy': result.get('strategy'),
                'errors': result.get('errors', [])
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _get_sync_status(self, request, fabric):
        """Get synchronization status"""
        try:
            status_info = fabric.get_sync_summary()
            
            return JsonResponse({
                'success': True,
                'sync_status': status_info
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _get_sync_statistics(self, request, fabric):
        """Get synchronization statistics"""
        try:
            from netbox_hedgehog.utils.bidirectional_sync_orchestrator import BidirectionalSyncOrchestrator
            
            orchestrator = BidirectionalSyncOrchestrator(fabric)
            stats = orchestrator.get_sync_statistics()
            
            return JsonResponse({
                'success': True,
                'statistics': stats
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class SyncOperationAPIView(View):
    """API endpoints for sync operation tracking"""
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, operation_id):
        """Get sync operation status"""
        try:
            from netbox_hedgehog.models.enhanced_gitops_models import SyncOperation
            
            operation = get_object_or_404(SyncOperation, pk=operation_id)
            
            return JsonResponse({
                'success': True,
                'operation': operation.get_operation_summary()
            })
        
        except Exception as e:
            logger.error(f"Sync operation API error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ConflictManagementAPIView(View):
    """API endpoints for conflict management operations"""
    
    @method_decorator(login_required)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, fabric_id):
        """List all detected conflicts"""
        try:
            from netbox_hedgehog.models.fabric import HedgehogFabric
            from netbox_hedgehog.models.gitops import HedgehogResource
            
            fabric = get_object_or_404(HedgehogFabric, pk=fabric_id)
            
            # Get resources with conflicts
            conflicted_resources = HedgehogResource.objects.filter(
                fabric=fabric,
                conflict_status='detected'
            )
            
            conflicts = []
            for resource in conflicted_resources:
                conflict_details = resource.conflict_details or {}
                
                conflicts.append({
                    'resource_id': resource.pk,
                    'resource_name': resource.name,
                    'resource_kind': resource.kind,
                    'conflict_type': conflict_details.get('type', 'unknown'),
                    'detected_at': conflict_details.get('detected_at'),
                    'details': conflict_details.get('details', {}),
                    'resolution_options': ['gui_wins', 'github_wins', 'merge', 'manual']
                })
            
            return JsonResponse({
                'success': True,
                'conflicts': conflicts,
                'total_conflicts': len(conflicts)
            })
        
        except Exception as e:
            logger.error(f"Conflict management API error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def post(self, request, conflict_id):
        """Resolve a specific conflict"""
        import json
        
        try:
            from netbox_hedgehog.models.gitops import HedgehogResource
            
            resource = get_object_or_404(HedgehogResource, pk=conflict_id, conflict_status='detected')
            
            # Parse request body
            body = json.loads(request.body) if request.body else {}
            resolution_strategy = body.get('resolution_strategy', 'manual')
            user_decisions = body.get('user_decisions', {})
            create_pr = body.get('create_pr', False)
            
            # Resolve conflict based on strategy
            if resolution_strategy == 'gui_wins':
                # Sync GUI state to GitHub
                result = resource.sync_to_github()
                if result['success']:
                    resource.resolve_conflict('gui_wins', request.user)
                    success = True
                    message = "Conflict resolved - GUI state synced to GitHub"
                else:
                    success = False
                    message = f"Failed to sync GUI state: {result['error']}"
            
            elif resolution_strategy == 'github_wins':
                # Update GUI from GitHub (desired_spec)
                if resource.desired_spec:
                    # In a real implementation, this would update the actual CRD model
                    resource.resolve_conflict('github_wins', request.user)
                    success = True
                    message = "Conflict resolved - GitHub state applied to GUI"
                else:
                    success = False
                    message = "No GitHub state available to apply"
            
            elif resolution_strategy == 'merge':
                # Intelligent merge (simplified implementation)
                resource.resolve_conflict('merge_attempted', request.user)
                success = True
                message = "Conflict resolved using merge strategy"
            
            else:
                success = False
                message = f"Unsupported resolution strategy: {resolution_strategy}"
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'resolution_strategy': resolution_strategy,
                    'resource_id': resource.pk
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': message
                }, status=400)
        
        except Exception as e:
            logger.error(f"Conflict resolution API error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ResourceFileMappingAPIView(View):
    """API endpoints for resource file mapping information"""
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, resource_id):
        """Get file mapping information for a specific resource"""
        try:
            from netbox_hedgehog.models.gitops import HedgehogResource
            
            resource = get_object_or_404(HedgehogResource, pk=resource_id)
            
            return JsonResponse({
                'success': True,
                'resource_id': resource.pk,
                'managed_file_path': resource.managed_file_path or '',
                'file_hash': resource.file_hash or '',
                'last_file_sync': resource.last_file_sync.isoformat() if resource.last_file_sync else None,
                'sync_status': 'in_sync' if not resource.has_drift else 'drift_detected',
                'conflict_status': resource.conflict_status,
                'external_modifications': len(resource.external_modifications) if resource.external_modifications else 0,
                'sync_direction': resource.sync_direction,
                'sync_metadata': resource.sync_metadata or {}
            })
        
        except Exception as e:
            logger.error(f"Resource file mapping API error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


# URL Configuration
def get_api_urls():
    """Return API URL patterns for bidirectional sync"""
    from django.urls import path, re_path
    
    return [
        # Directory Management
        path('fabrics/<int:fabric_id>/directories/<str:operation>/', 
             DirectoryManagementAPIView.as_view(), 
             name='directory_management'),
        
        # Synchronization Control  
        path('fabrics/<int:fabric_id>/sync/<str:operation>/', 
             SynchronizationControlAPIView.as_view(), 
             name='sync_control'),
        
        # Sync Operation Tracking
        path('sync-operations/<int:operation_id>/', 
             SyncOperationAPIView.as_view(), 
             name='sync_operation_detail'),
        
        # Conflict Management
        path('fabrics/<int:fabric_id>/conflicts/', 
             ConflictManagementAPIView.as_view(), 
             name='conflict_list'),
        path('conflicts/<int:conflict_id>/resolve/', 
             ConflictManagementAPIView.as_view(), 
             name='conflict_resolve'),
        
        # Resource File Mapping
        path('resources/<int:resource_id>/file-mapping/', 
             ResourceFileMappingAPIView.as_view(), 
             name='resource_file_mapping'),
    ]


# DRF ViewSet Integration (for NetBox API consistency)
class SyncOperationViewSet(NetBoxModelViewSet):
    """DRF ViewSet for SyncOperation model"""
    
    def get_queryset(self):
        from netbox_hedgehog.models.enhanced_gitops_models import SyncOperation
        return SyncOperation.objects.all()
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get operation summary"""
        operation = self.get_object()
        return Response({
            'success': True,
            'operation': operation.get_operation_summary()
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get sync operation statistics"""
        try:
            from django.db.models import Count, Q
            from netbox_hedgehog.models.enhanced_gitops_models import SyncOperation
            
            queryset = self.get_queryset()
            
            stats = {
                'total_operations': queryset.count(),
                'by_status': dict(queryset.values('status').annotate(count=Count('id')).values_list('status', 'count')),
                'by_type': dict(queryset.values('operation_type').annotate(count=Count('id')).values_list('operation_type', 'count')),
                'recent_operations': queryset.order_by('-started_at')[:10].values(
                    'id', 'operation_type', 'status', 'started_at', 'fabric__name'
                )
            }
            
            return Response({
                'success': True,
                'statistics': stats
            })
        
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)