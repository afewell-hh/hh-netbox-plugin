"""
GitOps File Management API Views

Provides REST API endpoints for GitOps file management operations:
- Fabric onboarding
- Raw file ingestion
- GitOps status monitoring
"""

import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.utils import timezone

from ..models.fabric import HedgehogFabric
from ..services.gitops_onboarding_service import GitOpsOnboardingService
from ..services.gitops_ingestion_service import GitOpsIngestionService
from ..services.raw_directory_watcher import RawDirectoryWatcher, raw_directory_watcher_manager

logger = logging.getLogger(__name__)


class GitOpsOnboardingAPIView(APIView):
    """
    API endpoint for initializing GitOps file management structure.
    
    POST /api/plugins/hedgehog/fabrics/{id}/init-gitops/
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, fabric_id):
        """Initialize GitOps structure for a fabric."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
            
            # Check if already initialized
            force = request.data.get('force', False)
            if hasattr(fabric, 'gitops_initialized') and fabric.gitops_initialized and not force:
                return Response({
                    'success': True,
                    'message': 'GitOps structure already initialized',
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name,
                    'already_initialized': True
                }, status=status.HTTP_200_OK)
            
            # Initialize using GitOpsOnboardingService
            service = GitOpsOnboardingService(fabric)
            base_directory = request.data.get('base_directory')
            result = service.initialize_gitops_structure(base_directory)
            
            if result['success']:
                return Response({
                    'success': True,
                    'message': 'GitOps structure initialized successfully',
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name,
                    'directories_created': len(result.get('directories_created', [])),
                    'files_migrated': len(result.get('files_migrated', [])),
                    'files_archived': len(result.get('files_archived', [])),
                    'completed_at': result.get('completed_at')
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name,
                    'errors': result.get('errors', [])
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f'GitOps initialization API error: {str(e)}')
            return Response({
                'success': False,
                'error': str(e),
                'fabric_id': fabric_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GitOpsIngestionAPIView(APIView):
    """
    API endpoint for ingesting raw YAML files.
    
    POST /api/plugins/hedgehog/fabrics/{id}/ingest-raw/
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, fabric_id):
        """Ingest raw YAML files for a fabric."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
            
            # Check if GitOps is initialized
            if not getattr(fabric, 'gitops_initialized', False):
                return Response({
                    'success': False,
                    'error': 'GitOps structure not initialized. Run init-gitops first.',
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Process raw directory
            service = GitOpsIngestionService(fabric)
            
            # Check if single file specified
            file_path = request.data.get('file_path')
            if file_path:
                result = service.process_single_file(file_path)
            else:
                result = service.process_raw_directory()
            
            if result['success']:
                return Response({
                    'success': True,
                    'message': result.get('message', 'Files processed successfully'),
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name,
                    'files_processed': len(result.get('files_processed', [])),
                    'documents_extracted': len(result.get('documents_extracted', [])),
                    'files_created': len(result.get('files_created', [])),
                    'files_archived': len(result.get('files_archived', [])),
                    'completed_at': result.get('completed_at')
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name,
                    'errors': result.get('errors', [])
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f'GitOps ingestion API error: {str(e)}')
            return Response({
                'success': False,
                'error': str(e),
                'fabric_id': fabric_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GitOpsStatusAPIView(APIView):
    """
    API endpoint for getting GitOps status.
    
    GET /api/plugins/hedgehog/fabrics/{id}/gitops-status/
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, fabric_id):
        """Get GitOps status for a fabric."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
            
            # Get onboarding status
            onboarding_service = GitOpsOnboardingService(fabric)
            onboarding_status = onboarding_service.get_onboarding_status()
            
            # Get ingestion status
            ingestion_service = GitOpsIngestionService(fabric)
            ingestion_status = ingestion_service.get_ingestion_status()
            
            # Get watcher status if available
            watcher_status = None
            if fabric_id in raw_directory_watcher_manager.watchers:
                watcher = raw_directory_watcher_manager.watchers[fabric_id]
                watcher_status = watcher.get_status()
            
            return Response({
                'success': True,
                'fabric_id': fabric_id,
                'fabric_name': fabric.name,
                'gitops_initialized': onboarding_status.get('gitops_initialized', False),
                'onboarding_status': onboarding_status,
                'ingestion_status': ingestion_status,
                'watcher_status': watcher_status,
                'retrieved_at': timezone.now()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'GitOps status API error: {str(e)}')
            return Response({
                'success': False,
                'error': str(e),
                'fabric_id': fabric_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GitOpsWatcherAPIView(APIView):
    """
    API endpoint for managing raw directory watchers.
    
    POST /api/plugins/hedgehog/fabrics/{id}/start-watcher/
    POST /api/plugins/hedgehog/fabrics/{id}/stop-watcher/
    GET /api/plugins/hedgehog/fabrics/{id}/watcher-status/
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, fabric_id):
        """Start or stop watcher based on action parameter."""
        action = request.data.get('action')
        
        if action == 'start':
            return self._start_watcher(request, fabric_id)
        elif action == 'stop':
            return self._stop_watcher(request, fabric_id)
        else:
            return Response({
                'success': False,
                'error': 'Invalid action. Use "start" or "stop".',
                'fabric_id': fabric_id
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, fabric_id):
        """Get watcher status."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
            
            if fabric_id in raw_directory_watcher_manager.watchers:
                watcher = raw_directory_watcher_manager.watchers[fabric_id]
                watcher_status = watcher.get_status()
                
                return Response({
                    'success': True,
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name,
                    'watcher_status': watcher_status,
                    'retrieved_at': timezone.now()
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': True,
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name,
                    'watcher_status': None,
                    'message': 'No watcher running for this fabric',
                    'retrieved_at': timezone.now()
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f'GitOps watcher status API error: {str(e)}')
            return Response({
                'success': False,
                'error': str(e),
                'fabric_id': fabric_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _start_watcher(self, request, fabric_id):
        """Start watcher for fabric."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
            
            # Check if GitOps is initialized
            if not getattr(fabric, 'gitops_initialized', False):
                return Response({
                    'success': False,
                    'error': 'GitOps structure not initialized. Run init-gitops first.',
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Start watcher
            scan_interval = request.data.get('scan_interval', 30)
            result = raw_directory_watcher_manager.start_watcher_for_fabric(fabric, scan_interval)
            
            if result['success']:
                return Response({
                    'success': True,
                    'message': 'Watcher started successfully',
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name,
                    'scan_interval': scan_interval,
                    'raw_path': result.get('raw_path')
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f'GitOps start watcher API error: {str(e)}')
            return Response({
                'success': False,
                'error': str(e),
                'fabric_id': fabric_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _stop_watcher(self, request, fabric_id):
        """Stop watcher for fabric."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
            
            # Stop watcher
            result = raw_directory_watcher_manager.stop_watcher_for_fabric(fabric)
            
            if result['success']:
                return Response({
                    'success': True,
                    'message': 'Watcher stopped successfully',
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name,
                    'statistics': result.get('statistics')
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'fabric_id': fabric_id,
                    'fabric_name': fabric.name
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f'GitOps stop watcher API error: {str(e)}')
            return Response({
                'success': False,
                'error': str(e),
                'fabric_id': fabric_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GitOpsGlobalStatusAPIView(APIView):
    """
    API endpoint for getting global GitOps status across all fabrics.
    
    GET /api/plugins/hedgehog/gitops/global-status/
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get global GitOps status."""
        try:
            # Get all fabrics
            fabrics = HedgehogFabric.objects.all()
            
            fabric_statuses = []
            global_stats = {
                'total_fabrics': len(fabrics),
                'initialized_fabrics': 0,
                'active_watchers': 0,
                'pending_raw_files': 0,
                'managed_files': 0
            }
            
            for fabric in fabrics:
                try:
                    # Get basic status
                    onboarding_service = GitOpsOnboardingService(fabric)
                    onboarding_status = onboarding_service.get_onboarding_status()
                    
                    ingestion_service = GitOpsIngestionService(fabric)
                    ingestion_status = ingestion_service.get_ingestion_status()
                    
                    # Check watcher status
                    watcher_active = fabric.id in raw_directory_watcher_manager.watchers
                    if watcher_active:
                        watcher = raw_directory_watcher_manager.watchers[fabric.id]
                        watcher_active = watcher.is_watching
                    
                    fabric_status = {
                        'fabric_id': fabric.id,
                        'fabric_name': fabric.name,
                        'gitops_initialized': onboarding_status.get('gitops_initialized', False),
                        'watcher_active': watcher_active,
                        'raw_files_pending': ingestion_status.get('raw_files_pending', 0),
                        'managed_files_count': ingestion_status.get('managed_files_count', 0),
                        'last_ingestion': ingestion_status.get('last_ingestion')
                    }
                    
                    fabric_statuses.append(fabric_status)
                    
                    # Update global stats
                    if fabric_status['gitops_initialized']:
                        global_stats['initialized_fabrics'] += 1
                    if fabric_status['watcher_active']:
                        global_stats['active_watchers'] += 1
                    global_stats['pending_raw_files'] += fabric_status['raw_files_pending']
                    global_stats['managed_files'] += fabric_status['managed_files_count']
                    
                except Exception as e:
                    logger.error(f'Error getting status for fabric {fabric.name}: {str(e)}')
                    fabric_statuses.append({
                        'fabric_id': fabric.id,
                        'fabric_name': fabric.name,
                        'error': str(e)
                    })
            
            # Get watcher manager global stats
            watcher_global_status = raw_directory_watcher_manager.get_all_watcher_status()
            
            return Response({
                'success': True,
                'global_stats': global_stats,
                'fabric_statuses': fabric_statuses,
                'watcher_manager_status': watcher_global_status,
                'retrieved_at': timezone.now()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'GitOps global status API error: {str(e)}')
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GitOpsValidationAPIView(APIView):
    """
    API endpoint for validating GitOps structure.
    
    GET /api/plugins/hedgehog/fabrics/{id}/validate-gitops/
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, fabric_id):
        """Validate GitOps structure for a fabric."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
            
            # Validate structure
            service = GitOpsOnboardingService(fabric)
            validation_result = service.validate_structure()
            
            return Response({
                'success': True,
                'fabric_id': fabric_id,
                'fabric_name': fabric.name,
                'validation_result': validation_result,
                'validated_at': timezone.now()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'GitOps validation API error: {str(e)}')
            return Response({
                'success': False,
                'error': str(e),
                'fabric_id': fabric_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Utility function to generate API documentation
def get_gitops_api_docs():
    """Generate API documentation for GitOps endpoints."""
    return {
        'endpoints': [
            {
                'path': '/api/plugins/hedgehog/fabrics/{id}/init-gitops/',
                'method': 'POST',
                'description': 'Initialize GitOps file management structure',
                'parameters': {
                    'force': 'boolean - Force initialization even if already initialized',
                    'base_directory': 'string - Override base directory path'
                }
            },
            {
                'path': '/api/plugins/hedgehog/fabrics/{id}/ingest-raw/',
                'method': 'POST',
                'description': 'Ingest raw YAML files from raw/ directory',
                'parameters': {
                    'file_path': 'string - Process specific file instead of entire directory'
                }
            },
            {
                'path': '/api/plugins/hedgehog/fabrics/{id}/gitops-status/',
                'method': 'GET',
                'description': 'Get comprehensive GitOps status for fabric'
            },
            {
                'path': '/api/plugins/hedgehog/fabrics/{id}/watcher/',
                'method': 'POST',
                'description': 'Start or stop raw directory watcher',
                'parameters': {
                    'action': 'string - "start" or "stop"',
                    'scan_interval': 'integer - Scan interval in seconds (for start action)'
                }
            },
            {
                'path': '/api/plugins/hedgehog/fabrics/{id}/watcher/',
                'method': 'GET',
                'description': 'Get watcher status for fabric'
            },
            {
                'path': '/api/plugins/hedgehog/gitops/global-status/',
                'method': 'GET',
                'description': 'Get global GitOps status across all fabrics'
            },
            {
                'path': '/api/plugins/hedgehog/fabrics/{id}/validate-gitops/',
                'method': 'GET',
                'description': 'Validate GitOps structure for fabric'
            }
        ]
    }