import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from django.utils import timezone

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
        
        # Define Hedgehog CRD types and their API groups
        self.crd_types = {
            # VPC API CRDs
            'vpcs': {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'kind': 'VPC'},
            'externals': {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'kind': 'External'},
            'externalattachments': {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'kind': 'ExternalAttachment'},
            'externalpeerings': {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'kind': 'ExternalPeering'},
            'ipv4namespaces': {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'kind': 'IPv4Namespace'},
            'vpcattachments': {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'kind': 'VPCAttachment'},
            'vpcpeerings': {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'kind': 'VPCPeering'},
            # Wiring API CRDs
            'connections': {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'kind': 'Connection'},
            'servers': {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'kind': 'Server'},
            'switches': {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'kind': 'Switch'},
            'switchgroups': {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'kind': 'SwitchGroup'},
            'vlannamespaces': {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'kind': 'VLANNamespace'},
        }
    
    def sync_all_crds(self) -> Dict[str, Any]:
        """
        Synchronize all CRDs for this fabric by fetching from Kubernetes and importing into NetBox.
        Returns summary of sync operations.
        """
        results = {
            'success': True,
            'total': 0,
            'created': 0,
            'updated': 0,
            'errors': 0,
            'error_details': [],
            'totals_by_type': {}
        }
        
        try:
            # First, fetch CRDs from Kubernetes
            fetch_result = self.fetch_crds_from_kubernetes()
            
            if not fetch_result['success']:
                results['success'] = False
                results['error_details'] = fetch_result['errors']
                results['errors'] = len(fetch_result['errors'])
                
                # Update fabric with error status
                self.fabric.sync_error = '; '.join(fetch_result['errors'][:3])  # First 3 errors
                self.fabric.save()
                
                return results
            
            # Now import the fetched CRDs into NetBox models
            import_result = self.import_crds_to_netbox(fetch_result['resources'])
            
            # Merge results
            results['total'] = import_result['total']
            results['created'] = import_result['created']
            results['updated'] = import_result['updated']
            results['errors'] += import_result['errors']
            results['error_details'].extend(import_result['error_details'])
            results['totals_by_type'] = fetch_result['totals']
            
            if import_result['errors'] > 0:
                results['success'] = False
            
            # Update fabric CRD counts (these are used in templates)
            total_resources = sum(fetch_result['totals'].values())
            vpc_count = fetch_result['totals'].get('VPC', 0)
            connection_count = fetch_result['totals'].get('Connection', 0)
            
            # Prepare fabric update data
            from django.utils import timezone
            fabric_update = {
                'cached_crd_count': total_resources,
                'cached_vpc_count': vpc_count,
                'cached_connection_count': connection_count,
                'last_sync': timezone.now()
            }
            
            if results['success']:
                fabric_update['sync_error'] = ''
                logger.info(f"Successfully synced {results['total']} CRDs for fabric {self.fabric.name} "
                           f"({results['created']} created, {results['updated']} updated)")
            else:
                error_summary = f"{results['errors']} errors occurred during sync"
                fabric_update['sync_error'] = error_summary
                logger.warning(f"Sync completed with errors for fabric {self.fabric.name}: {error_summary}")
            
            # Use queryset update to bypass change logging
            HedgehogFabric.objects.filter(pk=self.fabric.pk).update(**fabric_update)
            
        except Exception as e:
            logger.error(f"Fabric sync failed: {e}")
            results['success'] = False
            results['error_details'].append({
                'crd': 'fabric_sync',
                'error': str(e)
            })
            results['errors'] = 1
            
            # Update fabric with error status
            self.fabric.sync_error = str(e)
            self.fabric.save()
        
        return results
    
    def import_crds_to_netbox(self, resources_by_kind: Dict[str, List]) -> Dict[str, Any]:
        """
        Import fetched Kubernetes CRDs into NetBox models.
        Creates or updates NetBox objects based on Kubernetes resources.
        """
        results = {
            'total': 0,
            'created': 0,
            'updated': 0,
            'errors': 0,
            'error_details': []
        }
        
        # Import the models we'll need
        from ..models import (
            VPC, External, IPv4Namespace, ExternalAttachment, ExternalPeering, 
            VPCAttachment, VPCPeering, Connection, Switch, Server, SwitchGroup, VLANNamespace
        )
        
        # Map Kubernetes kinds to NetBox model classes
        model_mapping = {
            'VPC': VPC,
            'External': External,
            'IPv4Namespace': IPv4Namespace,
            'ExternalAttachment': ExternalAttachment,
            'ExternalPeering': ExternalPeering,
            'VPCAttachment': VPCAttachment,
            'VPCPeering': VPCPeering,
            'Connection': Connection,
            'Switch': Switch,
            'Server': Server,
            'SwitchGroup': SwitchGroup,
            'VLANNamespace': VLANNamespace,
        }
        
        for kind, resources in resources_by_kind.items():
            if kind not in model_mapping:
                logger.warning(f"No NetBox model found for Kubernetes kind: {kind}")
                continue
                
            model_class = model_mapping[kind]
            
            for resource in resources:
                try:
                    # Extract metadata
                    metadata = resource.get('metadata', {})
                    spec = resource.get('spec', {})
                    status = resource.get('status', {})
                    
                    name = metadata.get('name', '')
                    namespace = metadata.get('namespace', 'default')
                    uid = metadata.get('uid', '')
                    resource_version = metadata.get('resourceVersion', '')
                    
                    if not name:
                        logger.warning(f"Skipping {kind} resource without name")
                        continue
                    
                    # Check if this CRD already exists in NetBox
                    existing = None
                    try:
                        existing = model_class.objects.get(
                            fabric=self.fabric,
                            name=name,
                            namespace=namespace
                        )
                    except model_class.DoesNotExist:
                        pass
                    except Exception as e:
                        logger.error(f"Error checking for existing {kind} {name}: {e}")
                        continue
                    
                    # Prepare data for NetBox model
                    model_data = {
                        'fabric': self.fabric,
                        'name': name,
                        'namespace': namespace,
                        'spec': spec,
                        'labels': metadata.get('labels', {}),
                        'annotations': metadata.get('annotations', {}),
                        'kubernetes_uid': uid,
                        'kubernetes_resource_version': resource_version,
                        'kubernetes_status': self.client._determine_resource_status(resource),
                        'last_synced': timezone.now(),
                        'sync_error': '',
                        'auto_sync': True,  # Mark as auto-synced from cluster
                    }
                    
                    if existing:
                        # Update existing object
                        try:
                            # Try direct database update to bypass change logging
                            update_data = {}
                            for field, value in model_data.items():
                                if field != 'fabric':  # Don't change fabric association
                                    update_data[field] = value
                            
                            logger.info(f"DEBUG: About to update {kind}: {name}")
                            # Use queryset update to bypass change logging and serialization
                            model_class.objects.filter(pk=existing.pk).update(**update_data)
                            logger.info(f"DEBUG: Successfully updated {kind}: {name}")
                            
                            results['updated'] += 1
                            logger.debug(f"Updated {kind}: {name}")
                            
                        except Exception as e:
                            logger.error(f"DEBUG: Exception during {kind} {name} update: {type(e).__name__}: {e}")
                            import traceback
                            logger.error(f"DEBUG: Full traceback: {traceback.format_exc()}")
                            error_msg = f"Failed to update {kind} {name}: {e}"
                            logger.error(error_msg)
                            results['errors'] += 1
                            results['error_details'].append({
                                'crd': f"{kind}/{name}",
                                'error': str(e),
                                'operation': 'update'
                            })
                    else:
                        # Create new object
                        try:
                            logger.info(f"DEBUG: About to create {kind}: {name}")
                            new_obj = model_class.objects.create(**model_data)
                            logger.info(f"DEBUG: Successfully created {kind}: {name}")
                            results['created'] += 1
                            logger.debug(f"Created {kind}: {name}")
                            
                        except Exception as e:
                            logger.error(f"DEBUG: Exception during {kind} {name} creation: {type(e).__name__}: {e}")
                            import traceback
                            logger.error(f"DEBUG: Full traceback: {traceback.format_exc()}")
                            error_msg = f"Failed to create {kind} {name}: {e}"
                            logger.error(error_msg)
                            results['errors'] += 1
                            results['error_details'].append({
                                'crd': f"{kind}/{name}",
                                'error': str(e),
                                'operation': 'create'
                            })
                    
                    results['total'] += 1
                    
                except Exception as e:
                    error_msg = f"Unexpected error processing {kind} resource: {e}"
                    logger.error(error_msg)
                    results['errors'] += 1
                    results['error_details'].append({
                        'crd': f"{kind}/unknown",
                        'error': str(e),
                        'operation': 'process'
                    })
        
        logger.info(f"Import completed: {results['total']} total, {results['created']} created, "
                   f"{results['updated']} updated, {results['errors']} errors")
        
        return results
    
    def fetch_crds_from_kubernetes(self) -> Dict[str, Any]:
        """
        Fetch all Hedgehog CRDs from Kubernetes cluster.
        Returns dict with CRD type as key and list of resources as value.
        """
        results = {
            'success': True,
            'resources': {},
            'totals': {},
            'errors': []
        }
        
        try:
            custom_api = self.client._get_custom_api()
            
            for plural, crd_info in self.crd_types.items():
                try:
                    # Fetch all resources of this type
                    response = custom_api.list_namespaced_custom_object(
                        group=crd_info['group'],
                        version=crd_info['version'],
                        namespace=self.fabric.kubernetes_namespace or 'default',
                        plural=plural
                    )
                    
                    resources = response.get('items', [])
                    results['resources'][crd_info['kind']] = resources
                    results['totals'][crd_info['kind']] = len(resources)
                    
                    logger.info(f"Fetched {len(resources)} {crd_info['kind']} resources from Kubernetes")
                    
                except ApiException as e:
                    if e.status == 404:
                        # CRD not found, skip
                        logger.warning(f"CRD {plural} not found in cluster")
                        results['resources'][crd_info['kind']] = []
                        results['totals'][crd_info['kind']] = 0
                    else:
                        error_msg = f"Failed to fetch {plural}: {e}"
                        logger.error(error_msg)
                        results['errors'].append(error_msg)
                        results['success'] = False
                        
                except Exception as e:
                    error_msg = f"Unexpected error fetching {plural}: {e}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
                    results['success'] = False
                    
        except Exception as e:
            error_msg = f"Failed to initialize Kubernetes client: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            results['success'] = False
            
        return results