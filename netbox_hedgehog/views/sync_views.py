"""
Sync and connection testing views for fabrics
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views.generic import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import logging

from ..models import HedgehogFabric
from ..utils.kubernetes import KubernetesClient, KubernetesSync

logger = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class FabricTestConnectionView(View):
    """Test connection to a fabric's Kubernetes cluster"""
    
    def post(self, request, pk):
        """Test the Kubernetes connection"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        if not request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        try:
            # Use the real Kubernetes client to test connection
            k8s_client = KubernetesClient(fabric)
            result = k8s_client.test_connection()
            
            if result['success']:
                # Update fabric status
                fabric.connection_status = 'connected'
                fabric.connection_error = ''
                fabric.save()
                
                messages.success(request, f"Connection test successful for fabric '{fabric.name}'")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Connection test successful!',
                    'details': {
                        'cluster_version': result.get('cluster_version', 'Unknown'),
                        'platform': result.get('platform', 'Unknown'),
                        'namespace_access': result.get('namespace_access', False),
                        'namespace': fabric.kubernetes_namespace or 'default'
                    }
                })
            else:
                # Connection failed
                fabric.connection_status = 'error'
                fabric.connection_error = result.get('error', 'Unknown error')
                fabric.save()
                
                error_msg = result.get('error', 'Connection test failed')
                messages.error(request, f"Connection test failed for fabric '{fabric.name}': {error_msg}")
                
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                })
                
        except ImportError as e:
            # Kubernetes library not installed
            fabric.connection_status = 'error'
            fabric.connection_error = 'Kubernetes client library not installed'
            fabric.save()
            
            return JsonResponse({
                'success': False,
                'error': 'Kubernetes client library not installed. Please install: pip install kubernetes'
            })
            
        except Exception as e:
            fabric.connection_status = 'error'
            fabric.connection_error = str(e)
            fabric.save()
            
            logger.error(f"Connection test failed for fabric {fabric.name}: {e}")
            
            return JsonResponse({
                'success': False,
                'error': f'Connection test failed: {str(e)}'
            })


@method_decorator(login_required, name='dispatch')
class FabricSyncView(View):
    """Trigger reconciliation for a fabric"""
    
    def post(self, request, pk):
        """Perform reconciliation sync"""
        fabric = get_object_or_404(HedgehogFabric, pk=pk)
        
        if not request.user.has_perm('netbox_hedgehog.change_hedgehogfabric'):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        try:
            # Check if connection is available first
            if fabric.connection_status != 'connected':
                fabric.sync_status = 'error'
                fabric.sync_error = 'No active connection'
                fabric.save()
                
                messages.error(request, f"Cannot sync fabric '{fabric.name}': No active connection")
                
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot sync: Connection test required first. Please test connection before syncing.'
                })
            
            # Update sync status to syncing
            fabric.sync_status = 'syncing'
            fabric.save()
            
            # Use the real Kubernetes sync service with user context
            try:
                k8s_sync = KubernetesSync(fabric, user=request.user)
                sync_result = k8s_sync.sync_all_crds()
                
                if sync_result['success']:
                    # Sync completed successfully
                    fabric.sync_status = 'in_sync'
                    fabric.sync_error = ''
                    fabric.last_sync = timezone.now()
                    
                    # CRD counts are already updated by the sync service
                    # No need to update here as KubernetesSync.sync_all_crds() handles it
                    fabric.save()
                    
                    messages.success(request, f"Sync completed successfully for fabric '{fabric.name}'")
                    
                    return JsonResponse({
                        'success': True,
                        'message': f'Sync completed successfully! Fabric "{fabric.name}" is now synchronized.',
                        'stats': {
                            'total_crds': sync_result.get('total', 0),
                            'updated': sync_result.get('updated', 0),
                            'errors': sync_result.get('errors', 0),
                            'status': 'in_sync'
                        }
                    })
                else:
                    # Sync had errors
                    fabric.sync_status = 'error'
                    fabric.sync_error = f"{sync_result.get('errors', 0)} CRDs failed to sync"
                    fabric.save()
                    
                    error_details = sync_result.get('error_details', [])
                    error_summary = f"Sync completed with {sync_result.get('errors', 0)} errors"
                    
                    messages.warning(request, f"Sync completed with errors for fabric '{fabric.name}'")
                    
                    return JsonResponse({
                        'success': False,
                        'error': error_summary,
                        'stats': {
                            'total_crds': sync_result.get('total', 0),
                            'updated': sync_result.get('updated', 0),
                            'errors': sync_result.get('errors', 0),
                            'error_details': error_details[:5]  # Limit error details
                        }
                    })
                    
            except ImportError:
                fabric.sync_status = 'error'
                fabric.sync_error = 'Kubernetes client library not installed'
                fabric.save()
                
                return JsonResponse({
                    'success': False,
                    'error': 'Kubernetes client library not installed. Please install: pip install kubernetes'
                })
                
        except Exception as e:
            fabric.sync_status = 'error'
            fabric.sync_error = str(e)
            fabric.save()
            
            logger.error(f"Sync failed for fabric {fabric.name}: {e}")
            messages.error(request, f"Sync error: {str(e)}")
            
            return JsonResponse({
                'success': False,
                'error': f'Sync failed: {str(e)}'
            })