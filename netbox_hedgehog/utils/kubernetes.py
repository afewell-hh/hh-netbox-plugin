import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False

from django.conf import settings
from ..models.fabric import HedgehogFabric
from ..choices import KubernetesStatusChoices

logger = logging.getLogger(__name__)

class KubernetesClient:
    """
    Kubernetes client wrapper for Hedgehog fabric operations.
    Handles authentication, configuration, and API interactions.
    """
    
    def __init__(self, fabric: HedgehogFabric):
        self.fabric = fabric
        self._api_client = None
        self._custom_api = None
        
        if not KUBERNETES_AVAILABLE:
            raise ImportError(
                "Kubernetes client library not available. "
                "Install with: pip install kubernetes"
            )
    
    def _get_api_client(self):
        """Get configured Kubernetes API client"""
        if self._api_client is None:
            fabric_config = self.fabric.get_kubernetes_config()
            
            if fabric_config:
                # Use fabric-specific configuration
                configuration = client.Configuration()
                configuration.host = fabric_config['host']
                
                if 'api_key' in fabric_config:
                    configuration.api_key = fabric_config['api_key']
                
                if 'ssl_ca_cert' in fabric_config:
                    configuration.ssl_ca_cert = fabric_config['ssl_ca_cert']
                    
                configuration.verify_ssl = fabric_config.get('verify_ssl', True)
                
                self._api_client = client.ApiClient(configuration)
            else:
                # Use default kubeconfig
                try:
                    config.load_kube_config()
                    self._api_client = client.ApiClient()
                except Exception as e:
                    logger.error(f"Failed to load kubeconfig: {e}")
                    raise
        
        return self._api_client
    
    def _get_custom_api(self):
        """Get custom objects API client"""
        if self._custom_api is None:
            api_client = self._get_api_client()
            self._custom_api = client.CustomObjectsApi(api_client)
        return self._custom_api
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to Kubernetes cluster.
        Returns connection status and cluster information.
        """
        try:
            api_client = self._get_api_client()
            v1 = client.CoreV1Api(api_client)
            
            # Try to get cluster version
            version_api = client.VersionApi(api_client)
            version_info = version_api.get_code()
            
            # Try to list namespaces to verify permissions
            namespaces = v1.list_namespace(limit=1)
            
            return {
                'success': True,
                'cluster_version': version_info.git_version,
                'platform': version_info.platform,
                'namespace_access': len(namespaces.items) > 0,
                'message': 'Connection successful'
            }
        
        except Exception as e:
            logger.error(f"Kubernetes connection test failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Connection failed'
            }
    
    def apply_crd(self, crd_instance) -> Dict[str, Any]:
        """
        Apply a CRD to Kubernetes cluster.
        Returns operation status and resource information.
        """
        try:
            custom_api = self._get_custom_api()
            manifest = crd_instance.to_kubernetes_manifest()
            
            # Extract CRD details
            group, version = manifest['apiVersion'].split('/')
            plural = self._get_plural_name(manifest['kind'])
            
            try:
                # Try to get existing resource
                existing = custom_api.get_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=manifest['metadata']['namespace'],
                    plural=plural,
                    name=manifest['metadata']['name']
                )
                
                # Update existing resource
                result = custom_api.patch_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=manifest['metadata']['namespace'],
                    plural=plural,
                    name=manifest['metadata']['name'],
                    body=manifest
                )
                operation = 'updated'
                
            except ApiException as e:
                if e.status == 404:
                    # Create new resource
                    result = custom_api.create_namespaced_custom_object(
                        group=group,
                        version=version,
                        namespace=manifest['metadata']['namespace'],
                        plural=plural,
                        body=manifest
                    )
                    operation = 'created'
                else:
                    raise
            
            # Update CRD instance with Kubernetes metadata
            crd_instance.kubernetes_uid = result['metadata']['uid']
            crd_instance.kubernetes_resource_version = result['metadata']['resourceVersion']
            crd_instance.kubernetes_status = KubernetesStatusChoices.APPLIED
            crd_instance.last_applied = datetime.now()
            crd_instance.sync_error = ''
            crd_instance.save()
            
            return {
                'success': True,
                'operation': operation,
                'uid': result['metadata']['uid'],
                'resource_version': result['metadata']['resourceVersion'],
                'message': f'CRD {operation} successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to apply CRD {crd_instance.name}: {e}")
            
            # Update CRD instance with error
            crd_instance.kubernetes_status = KubernetesStatusChoices.ERROR
            crd_instance.sync_error = str(e)
            crd_instance.save()
            
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to apply CRD: {e}'
            }
    
    def get_crd_status(self, crd_instance) -> Dict[str, Any]:
        """
        Get current status of a CRD from Kubernetes.
        Returns status information and updates the instance.
        """
        try:
            custom_api = self._get_custom_api()
            manifest = crd_instance.to_kubernetes_manifest()
            
            # Extract CRD details
            group, version = manifest['apiVersion'].split('/')
            plural = self._get_plural_name(manifest['kind'])
            
            try:
                result = custom_api.get_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=manifest['metadata']['namespace'],
                    plural=plural,
                    name=manifest['metadata']['name']
                )
                
                # Update CRD instance with current status
                crd_instance.kubernetes_uid = result['metadata']['uid']
                crd_instance.kubernetes_resource_version = result['metadata']['resourceVersion']
                
                # Determine status based on resource conditions
                status = self._determine_resource_status(result)
                crd_instance.kubernetes_status = status
                crd_instance.last_synced = datetime.now()
                crd_instance.sync_error = ''
                crd_instance.save()
                
                return {
                    'success': True,
                    'status': status,
                    'uid': result['metadata']['uid'],
                    'resource_version': result['metadata']['resourceVersion'],
                    'conditions': result.get('status', {}).get('conditions', [])
                }
                
            except ApiException as e:
                if e.status == 404:
                    # Resource not found
                    crd_instance.kubernetes_status = KubernetesStatusChoices.UNKNOWN
                    crd_instance.kubernetes_uid = ''
                    crd_instance.kubernetes_resource_version = ''
                    crd_instance.save()
                    
                    return {
                        'success': True,
                        'status': KubernetesStatusChoices.UNKNOWN,
                        'message': 'Resource not found in cluster'
                    }
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to get CRD status for {crd_instance.name}: {e}")
            
            crd_instance.kubernetes_status = KubernetesStatusChoices.ERROR
            crd_instance.sync_error = str(e)
            crd_instance.save()
            
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to get CRD status: {e}'
            }
    
    def delete_crd(self, crd_instance) -> Dict[str, Any]:
        """
        Delete a CRD from Kubernetes cluster.
        Returns operation status.
        """
        try:
            custom_api = self._get_custom_api()
            manifest = crd_instance.to_kubernetes_manifest()
            
            # Extract CRD details
            group, version = manifest['apiVersion'].split('/')
            plural = self._get_plural_name(manifest['kind'])
            
            try:
                result = custom_api.delete_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=manifest['metadata']['namespace'],
                    plural=plural,
                    name=manifest['metadata']['name']
                )
                
                # Update CRD instance status
                crd_instance.kubernetes_status = KubernetesStatusChoices.DELETING
                crd_instance.sync_error = ''
                crd_instance.save()
                
                return {
                    'success': True,
                    'message': 'CRD deletion initiated'
                }
                
            except ApiException as e:
                if e.status == 404:
                    # Resource already deleted
                    return {
                        'success': True,
                        'message': 'Resource not found (already deleted)'
                    }
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to delete CRD {crd_instance.name}: {e}")
            
            crd_instance.sync_error = str(e)
            crd_instance.save()
            
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to delete CRD: {e}'
            }
    
    def _get_plural_name(self, kind: str) -> str:
        """Convert Kubernetes kind to plural name"""
        kind_lower = kind.lower()
        
        # Special cases
        if kind_lower.endswith('s'):
            return kind_lower + 'es'
        elif kind_lower.endswith('y'):
            return kind_lower[:-1] + 'ies'
        else:
            return kind_lower + 's'
    
    def _determine_resource_status(self, resource: Dict[str, Any]) -> str:
        """
        Determine resource status based on Kubernetes resource state.
        This is a simplified implementation - real logic would depend on
        specific Hedgehog CRD status fields.
        """
        status_obj = resource.get('status', {})
        conditions = status_obj.get('conditions', [])
        
        # Check for ready condition
        for condition in conditions:
            if condition.get('type') == 'Ready':
                if condition.get('status') == 'True':
                    return KubernetesStatusChoices.LIVE
                else:
                    return KubernetesStatusChoices.ERROR
        
        # Default to applied if no conditions available
        return KubernetesStatusChoices.APPLIED

class KubernetesSync:
    """
    Synchronization service for managing CRD lifecycle.
    Handles batch operations and status monitoring.
    """
    
    def __init__(self, fabric: HedgehogFabric):
        self.fabric = fabric
        self.client = KubernetesClient(fabric)
    
    def sync_all_crds(self) -> Dict[str, Any]:
        """
        Synchronize all CRDs for this fabric.
        Returns summary of sync operations.
        """
        from ..models.base import BaseCRD
        
        results = {
            'success': True,
            'total': 0,
            'updated': 0,
            'errors': 0,
            'error_details': []
        }
        
        try:
            # Get all CRDs for this fabric
            crds = BaseCRD.objects.filter(fabric=self.fabric, auto_sync=True)
            results['total'] = len(crds)
            
            for crd in crds:
                try:
                    status_result = self.client.get_crd_status(crd)
                    if status_result['success']:
                        results['updated'] += 1
                    else:
                        results['errors'] += 1
                        results['error_details'].append({
                            'crd': str(crd),
                            'error': status_result.get('error', 'Unknown error')
                        })
                
                except Exception as e:
                    results['errors'] += 1
                    results['error_details'].append({
                        'crd': str(crd),
                        'error': str(e)
                    })
            
            # Update fabric sync timestamp
            if results['errors'] == 0:
                self.fabric.last_sync = datetime.now()
                self.fabric.sync_error = ''
            else:
                error_summary = f"{results['errors']} CRDs failed to sync"
                self.fabric.sync_error = error_summary
                results['success'] = False
            
            self.fabric.save()
            
        except Exception as e:
            logger.error(f"Fabric sync failed: {e}")
            results['success'] = False
            results['error_details'].append({
                'crd': 'fabric_sync',
                'error': str(e)
            })
        
        return results