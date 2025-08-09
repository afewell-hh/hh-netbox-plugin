"""
GitOps Management Dashboard Views
Unified interface for file management, conflict resolution, and template operations.
Provides professional GitOps management interface comparable to GitLab/GitHub.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import asdict

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.urls import reverse
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib import messages

from netbox.views import generic

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


class GitOpsManagementDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main GitOps Management Dashboard providing unified interface for all Phase 3 components.
    Professional UI comparable to GitLab/GitHub file management interfaces.
    """
    template_name = 'netbox_hedgehog/gitops_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Get fabric if specified
            fabric_id = kwargs.get('fabric_id') or self.request.GET.get('fabric_id')
            fabric = None
            if fabric_id:
                fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
            
            # Get dashboard overview data
            dashboard_data = self._get_dashboard_overview(fabric)
            
            context.update({
                'fabric': fabric,
                'dashboard_data': dashboard_data,
                'available_fabrics': HedgehogFabric.objects.all(),
                'page_title': f'GitOps Dashboard - {fabric.name}' if fabric else 'GitOps Dashboard',
                'can_manage_gitops': self.request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'),
                'websocket_url': self._get_websocket_url(),
                'api_base_url': self._get_api_base_url(),
                'refresh_interval': getattr(settings, 'GITOPS_DASHBOARD_REFRESH_INTERVAL', 30)
            })
            
        except Exception as e:
            logger.error(f"GitOps Dashboard context error: {str(e)}")
            messages.error(self.request, f"Error loading dashboard: {str(e)}")
            context.update({
                'error': str(e),
                'dashboard_data': self._get_empty_dashboard_data()
            })
        
        return context
    
    def _get_dashboard_overview(self, fabric: Optional[HedgehogFabric] = None) -> Dict[str, Any]:
        """Get comprehensive dashboard overview data."""
        try:
            overview = {
                'summary': {
                    'total_fabrics': HedgehogFabric.objects.count(),
                    'active_repositories': GitRepository.objects.filter(sync_enabled=True).count(),
                    'total_resources': HedgehogResource.objects.count(),
                    'pending_operations': 0,
                    'last_sync_time': None,
                    'system_health': 'healthy'
                },
                'fabric_details': None,
                'recent_operations': [],
                'file_browser': {
                    'current_path': '/',
                    'directories': [],
                    'files': []
                },
                'conflicts': {
                    'active_conflicts': 0,
                    'resolved_today': 0,
                    'resolution_rate': 100.0
                },
                'templates': {
                    'available_templates': 0,
                    'valid_templates': 0,
                    'last_validation': None
                }
            }
            
            if fabric:
                overview['fabric_details'] = self._get_fabric_details(fabric)
                overview['file_browser'] = self._get_file_browser_data(fabric)
                overview['conflicts'] = self._get_conflict_data(fabric)
                overview['templates'] = self._get_template_data(fabric)
                overview['recent_operations'] = self._get_recent_operations(fabric)
                
                # Update summary with fabric-specific data
                overview['summary'].update({
                    'total_resources': fabric.gitops_resources.count(),
                    'last_sync_time': self._get_last_sync_time(fabric)
                })
            
            return overview
            
        except Exception as e:
            logger.error(f"Failed to get dashboard overview: {str(e)}")
            return self._get_empty_dashboard_data()
    
    def _get_fabric_details(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get detailed fabric information."""
        try:
            git_repo = fabric.git_repositories.first()
            
            return {
                'name': fabric.name,
                'id': fabric.id,
                'description': fabric.description or '',
                'created': fabric.created.isoformat() if hasattr(fabric, 'created') else None,
                'modified': fabric.modified.isoformat() if hasattr(fabric, 'modified') else None,
                'git_repository': {
                    'url': git_repo.url if git_repo else None,
                    'branch': git_repo.branch if git_repo else 'main',
                    'sync_enabled': git_repo.sync_enabled if git_repo else False,
                    'last_sync': git_repo.last_sync_time.isoformat() if git_repo and git_repo.last_sync_time else None,
                    'sync_status': git_repo.sync_status if git_repo else 'unknown'
                },
                'resources_count': fabric.gitops_resources.count(),
                'managed_files': self._count_managed_files(fabric),
                'template_engine_status': self._get_template_engine_status(fabric)
            }
            
        except Exception as e:
            logger.error(f"Failed to get fabric details for {fabric.name}: {str(e)}")
            return {'name': fabric.name, 'id': fabric.id, 'error': str(e)}
    
    def _get_file_browser_data(self, fabric: HedgehogFabric, path: str = '/') -> Dict[str, Any]:
        """Get file browser data for the fabric."""
        try:
            # Initialize file management service
            base_directory = self._get_fabric_directory(fabric)
            if not base_directory.exists():
                return {
                    'current_path': path,
                    'directories': [],
                    'files': [],
                    'error': 'Fabric directory not initialized'
                }
            
            file_manager = FileManagementService(base_directory)
            current_dir = (base_directory / path.lstrip('/')).resolve()
            
            # Security check - ensure path is within fabric directory
            try:
                current_dir.relative_to(base_directory)
            except ValueError:
                current_dir = base_directory
                path = '/'
            
            directories = []
            files = []
            
            if current_dir.exists() and current_dir.is_dir():
                for item in sorted(current_dir.iterdir()):
                    if item.name.startswith('.'):
                        continue
                        
                    item_stat = item.stat()
                    item_data = {
                        'name': item.name,
                        'path': str(item.relative_to(base_directory)),
                        'size': item_stat.st_size,
                        'modified': datetime.fromtimestamp(item_stat.st_mtime).isoformat(),
                        'permissions': oct(item_stat.st_mode)[-3:],
                    }
                    
                    if item.is_dir():
                        item_data['type'] = 'directory'
                        item_data['items_count'] = len(list(item.iterdir()))
                        directories.append(item_data)
                    else:
                        item_data['type'] = 'file'
                        item_data['file_type'] = self._detect_file_type(item)
                        item_data['can_preview'] = self._can_preview_file(item)
                        files.append(item_data)
            
            return {
                'current_path': path,
                'parent_path': str(Path(path).parent) if path != '/' else None,
                'directories': directories,
                'files': files,
                'total_items': len(directories) + len(files)
            }
            
        except Exception as e:
            logger.error(f"Failed to get file browser data: {str(e)}")
            return {
                'current_path': path,
                'directories': [],
                'files': [],
                'error': str(e)
            }
    
    def _get_conflict_data(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get conflict resolution data for the fabric."""
        try:
            base_directory = self._get_fabric_directory(fabric)
            
            # Use conflict resolution engine to get current state
            conflict_resolver = ConflictResolutionEngine(fabric, base_directory)
            
            # This would need integration with YamlDuplicateDetector
            # For now, return mock data structure
            return {
                'active_conflicts': 0,
                'resolved_today': 0,
                'resolution_rate': 100.0,
                'recent_resolutions': [],
                'conflict_types': {
                    'duplicate_files': 0,
                    'content_conflicts': 0,
                    'metadata_conflicts': 0
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get conflict data: {str(e)}")
            return {
                'active_conflicts': 0,
                'resolved_today': 0,
                'resolution_rate': 0.0,
                'error': str(e)
            }
    
    def _get_template_data(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get template engine data for the fabric."""
        try:
            template_engine = ConfigurationTemplateEngine(fabric)
            engine_status = template_engine.get_engine_status()
            
            return {
                'available_templates': len(template_engine.template_manager.list_templates()),
                'valid_templates': 0,  # Would need validation results
                'last_validation': None,
                'engine_status': engine_status['services'],
                'performance_metrics': engine_status['metrics'],
                'cache_stats': engine_status['cache_stats']
            }
            
        except Exception as e:
            logger.error(f"Failed to get template data: {str(e)}")
            return {
                'available_templates': 0,
                'valid_templates': 0,
                'last_validation': None,
                'error': str(e)
            }
    
    def _get_recent_operations(self, fabric: HedgehogFabric, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent operations for the fabric."""
        try:
            # This would integrate with operation history from various services
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Failed to get recent operations: {str(e)}")
            return []
    
    def _get_fabric_directory(self, fabric: HedgehogFabric) -> Path:
        """Get the base directory for fabric files."""
        base_dir = Path(getattr(settings, 'HEDGEHOG_GITOPS_BASE_DIR', '/tmp/hedgehog-gitops'))
        return base_dir / 'fabrics' / fabric.name
    
    def _count_managed_files(self, fabric: HedgehogFabric) -> int:
        """Count managed files for the fabric."""
        try:
            fabric_dir = self._get_fabric_directory(fabric)
            managed_dir = fabric_dir / 'managed'
            
            if not managed_dir.exists():
                return 0
            
            return len(list(managed_dir.rglob('*.yaml'))) + len(list(managed_dir.rglob('*.yml')))
            
        except Exception as e:
            logger.error(f"Failed to count managed files: {str(e)}")
            return 0
    
    def _get_template_engine_status(self, fabric: HedgehogFabric) -> str:
        """Get template engine status for the fabric."""
        try:
            template_engine = ConfigurationTemplateEngine(fabric)
            return 'active' if template_engine else 'inactive'
        except Exception:
            return 'error'
    
    def _get_last_sync_time(self, fabric: HedgehogFabric) -> Optional[str]:
        """Get the last sync time for the fabric."""
        try:
            git_repo = fabric.git_repositories.first()
            if git_repo and git_repo.last_sync_time:
                return git_repo.last_sync_time.isoformat()
            return None
        except Exception:
            return None
    
    def _detect_file_type(self, file_path: Path) -> str:
        """Detect file type based on extension and content."""
        suffix = file_path.suffix.lower()
        if suffix in ['.yaml', '.yml']:
            return 'yaml'
        elif suffix in ['.json']:
            return 'json'
        elif suffix in ['.md', '.txt']:
            return 'text'
        elif suffix in ['.py']:
            return 'python'
        elif suffix in ['.sh']:
            return 'shell'
        else:
            return 'unknown'
    
    def _can_preview_file(self, file_path: Path) -> bool:
        """Check if file can be previewed in the browser."""
        file_type = self._detect_file_type(file_path)
        preview_types = ['yaml', 'json', 'text', 'python', 'shell']
        return file_type in preview_types and file_path.stat().st_size < 1024 * 1024  # 1MB limit
    
    def _get_websocket_url(self) -> str:
        """Get WebSocket URL for real-time updates."""
        # This would need WebSocket implementation
        return '/ws/gitops/dashboard/'
    
    def _get_api_base_url(self) -> str:
        """Get API base URL for dashboard operations."""
        return '/api/plugins/netbox-hedgehog/gitops-dashboard/'
    
    def _get_empty_dashboard_data(self) -> Dict[str, Any]:
        """Get empty dashboard data structure."""
        return {
            'summary': {
                'total_fabrics': 0,
                'active_repositories': 0,
                'total_resources': 0,
                'pending_operations': 0,
                'last_sync_time': None,
                'system_health': 'unknown'
            },
            'fabric_details': None,
            'recent_operations': [],
            'file_browser': {
                'current_path': '/',
                'directories': [],
                'files': []
            },
            'conflicts': {
                'active_conflicts': 0,
                'resolved_today': 0,
                'resolution_rate': 0.0
            },
            'templates': {
                'available_templates': 0,
                'valid_templates': 0,
                'last_validation': None
            }
        }


class GitOpsFileBrowserView(LoginRequiredMixin, View):
    """File browser API view for GitOps dashboard."""
    
    def get(self, request, fabric_id=None):
        """Get file browser data for a specific path."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id) if fabric_id else None
            path = request.GET.get('path', '/')
            
            if not fabric:
                return JsonResponse({'error': 'Fabric not specified'}, status=400)
            
            dashboard_view = GitOpsManagementDashboardView()
            file_data = dashboard_view._get_file_browser_data(fabric, path)
            
            return JsonResponse({
                'success': True,
                'data': file_data
            })
            
        except Exception as e:
            logger.error(f"File browser error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class GitOpsFilePreviewView(LoginRequiredMixin, View):
    """File preview API view for GitOps dashboard."""
    
    def get(self, request, fabric_id=None):
        """Get file content for preview."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id) if fabric_id else None
            file_path = request.GET.get('path')
            
            if not fabric or not file_path:
                return JsonResponse({'error': 'Fabric or file path not specified'}, status=400)
            
            # Get fabric directory and resolve file path
            dashboard_view = GitOpsManagementDashboardView()
            base_directory = dashboard_view._get_fabric_directory(fabric)
            full_file_path = (base_directory / file_path.lstrip('/')).resolve()
            
            # Security check
            try:
                full_file_path.relative_to(base_directory)
            except ValueError:
                return JsonResponse({'error': 'Invalid file path'}, status=400)
            
            if not full_file_path.exists() or not full_file_path.is_file():
                return JsonResponse({'error': 'File not found'}, status=404)
            
            # Check file size limit
            if full_file_path.stat().st_size > 1024 * 1024:  # 1MB
                return JsonResponse({'error': 'File too large for preview'}, status=400)
            
            # Read file content
            try:
                with open(full_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Try binary read for non-text files
                with open(full_file_path, 'rb') as f:
                    content = f.read()
                    content = f"Binary file ({len(content)} bytes)"
            
            file_type = dashboard_view._detect_file_type(full_file_path)
            
            return JsonResponse({
                'success': True,
                'data': {
                    'content': content,
                    'file_type': file_type,
                    'file_name': full_file_path.name,
                    'file_size': full_file_path.stat().st_size,
                    'modified': datetime.fromtimestamp(full_file_path.stat().st_mtime).isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"File preview error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class GitOpsVisualDiffView(LoginRequiredMixin, View):
    """Visual diff view for GitOps state comparison."""
    
    def get(self, request, fabric_id=None):
        """Get visual diff between NetBox and Git repository state."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id) if fabric_id else None
            
            if not fabric:
                return JsonResponse({'error': 'Fabric not specified'}, status=400)
            
            # This would integrate with the state comparison service
            # For now, return mock diff data
            diff_data = {
                'comparison_time': timezone.now().isoformat(),
                'netbox_state': {
                    'resources': fabric.gitops_resources.count(),
                    'last_updated': timezone.now().isoformat()
                },
                'git_state': {
                    'files': 0,
                    'last_commit': None
                },
                'differences': [],
                'summary': {
                    'additions': 0,
                    'modifications': 0,
                    'deletions': 0,
                    'conflicts': 0
                }
            }
            
            return JsonResponse({
                'success': True,
                'data': diff_data
            })
            
        except Exception as e:
            logger.error(f"Visual diff error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class GitOpsWorkflowStatusView(LoginRequiredMixin, View):
    """Workflow status view for tracking operations."""
    
    def get(self, request, fabric_id=None):
        """Get current workflow status for the fabric."""
        try:
            fabric = get_object_or_404(HedgehogFabric, id=fabric_id) if fabric_id else None
            
            if not fabric:
                return JsonResponse({'error': 'Fabric not specified'}, status=400)
            
            # Get workflow status from various services
            status_data = {
                'fabric_id': fabric.id,
                'fabric_name': fabric.name,
                'workflows': {
                    'sync_status': self._get_sync_status(fabric),
                    'template_generation': self._get_template_status(fabric),
                    'conflict_resolution': self._get_conflict_status(fabric),
                    'file_operations': self._get_file_operations_status(fabric)
                },
                'last_updated': timezone.now().isoformat()
            }
            
            return JsonResponse({
                'success': True,
                'data': status_data
            })
            
        except Exception as e:
            logger.error(f"Workflow status error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _get_sync_status(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get sync workflow status."""
        git_repo = fabric.git_repositories.first()
        return {
            'status': 'idle',
            'last_sync': git_repo.last_sync_time.isoformat() if git_repo and git_repo.last_sync_time else None,
            'next_sync': None,
            'sync_enabled': git_repo.sync_enabled if git_repo else False
        }
    
    def _get_template_status(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get template generation status."""
        return {
            'status': 'idle',
            'last_generation': None,
            'templates_count': 0,
            'generation_enabled': True
        }
    
    def _get_conflict_status(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get conflict resolution status."""
        return {
            'status': 'idle',
            'active_conflicts': 0,
            'last_resolution': None,
            'auto_resolution_enabled': True
        }
    
    def _get_file_operations_status(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get file operations status."""
        return {
            'status': 'idle',
            'pending_operations': 0,
            'last_operation': None,
            'operations_enabled': True
        }


# Dashboard URL patterns
def get_dashboard_urls():
    """Get URL patterns for GitOps dashboard."""
    from django.urls import path
    
    return [
        path('gitops-dashboard/', GitOpsManagementDashboardView.as_view(), name='gitops-dashboard'),
        path('gitops-dashboard/<int:fabric_id>/', GitOpsManagementDashboardView.as_view(), name='gitops-dashboard-fabric'),
        path('gitops-dashboard/<int:fabric_id>/file-browser/', GitOpsFileBrowserView.as_view(), name='gitops-file-browser'),
        path('gitops-dashboard/<int:fabric_id>/file-preview/', GitOpsFilePreviewView.as_view(), name='gitops-file-preview'),
        path('gitops-dashboard/<int:fabric_id>/visual-diff/', GitOpsVisualDiffView.as_view(), name='gitops-visual-diff'),
        path('gitops-dashboard/<int:fabric_id>/workflow-status/', GitOpsWorkflowStatusView.as_view(), name='gitops-workflow-status'),
    ]