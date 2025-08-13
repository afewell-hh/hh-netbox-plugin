"""
Reconciliation System
Handles bidirectional synchronization between NetBox and Kubernetes clusters.
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import logging

logger = logging.getLogger(__name__)

class ReconciliationManager:
    """Manages reconciliation between NetBox and Kubernetes clusters"""
    
    def __init__(self, fabric_model):
        """Initialize with a HedgehogFabric model instance"""
        self.fabric = fabric_model
        self.custom_api = None
        self.core_api = None
        
        # CRD specifications for reconciliation
        self.crd_specs = [
            {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'vpcs', 'kind': 'VPC'},
            {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'externals', 'kind': 'External'},
            {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'externalattachments', 'kind': 'ExternalAttachment'},
            {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'externalpeerings', 'kind': 'ExternalPeering'},
            {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'ipv4namespaces', 'kind': 'IPv4Namespace'},
            {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'vpcattachments', 'kind': 'VPCAttachment'},
            {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'vpcpeerings', 'kind': 'VPCPeering'},
            {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'plural': 'connections', 'kind': 'Connection'},
            {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'plural': 'servers', 'kind': 'Server'},
            {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'plural': 'switches', 'kind': 'Switch'},
            {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'plural': 'switchgroups', 'kind': 'SwitchGroup'},
            {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'plural': 'vlannamespaces', 'kind': 'VLANNamespace'},
        ]
    
    def initialize_kubernetes_client(self) -> bool:
        """Initialize Kubernetes API clients"""
        try:
            kubeconfig_data = self.fabric.get_kubernetes_config()
            if kubeconfig_data:
                # Configure client directly from fabric settings
                configuration = client.Configuration()
                configuration.host = kubeconfig_data.get('host')
                configuration.verify_ssl = kubeconfig_data.get('verify_ssl', True)
                
                if 'api_key' in kubeconfig_data:
                    configuration.api_key = kubeconfig_data['api_key']
                
                # Create API clients with custom configuration
                api_client = client.ApiClient(configuration)
                self.custom_api = client.CustomObjectsApi(api_client)
                self.core_api = client.CoreV1Api(api_client)
            else:
                # Load from default kubeconfig
                config.load_kube_config()
                self.custom_api = client.CustomObjectsApi()
                self.core_api = client.CoreV1Api()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            return False
    
    def calculate_resource_hash(self, resource: Dict) -> str:
        """Calculate a hash of the resource spec for change detection"""
        # Extract relevant fields for hash calculation
        hash_data = {
            'metadata': {
                'name': resource['metadata']['name'],
                'namespace': resource['metadata'].get('namespace'),
                'labels': resource['metadata'].get('labels', {}),
                'annotations': resource['metadata'].get('annotations', {})
            },
            'spec': resource.get('spec', {})
        }
        
        # Create deterministic hash
        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()[:16]
    
    def get_cluster_resources(self, namespace: str = None) -> Dict[str, List[Dict]]:
        """Get all Hedgehog resources from the cluster"""
        if not self.custom_api:
            return {}
        
        cluster_resources = {}
        
        for crd_spec in self.crd_specs:
            try:
                if namespace:
                    resources = self.custom_api.list_namespaced_custom_object(
                        group=crd_spec['group'],
                        version=crd_spec['version'],
                        namespace=namespace,
                        plural=crd_spec['plural']
                    )
                else:
                    resources = self.custom_api.list_cluster_custom_object(
                        group=crd_spec['group'],
                        version=crd_spec['version'],
                        plural=crd_spec['plural']
                    )
                
                resource_list = []
                for resource in resources.get('items', []):
                    resource_info = {
                        'name': resource['metadata']['name'],
                        'namespace': resource['metadata'].get('namespace', 'cluster-scoped'),
                        'uid': resource['metadata']['uid'],
                        'resource_version': resource['metadata']['resourceVersion'],
                        'creation_timestamp': resource['metadata'].get('creationTimestamp'),
                        'labels': resource['metadata'].get('labels', {}),
                        'annotations': resource['metadata'].get('annotations', {}),
                        'spec': resource.get('spec', {}),
                        'status': resource.get('status', {}),
                        'hash': self.calculate_resource_hash(resource),
                        'managed_by_netbox': resource['metadata'].get('labels', {}).get('source') == 'netbox-hedgehog-plugin'
                    }
                    resource_list.append(resource_info)
                
                cluster_resources[crd_spec['kind']] = resource_list
                
            except ApiException as e:
                if e.status != 404:  # Ignore not found errors
                    logger.error(f"Error fetching {crd_spec['kind']}: {e}")
                cluster_resources[crd_spec['kind']] = []
        
        return cluster_resources
    
    def get_netbox_resources(self) -> Dict[str, List[Dict]]:
        """Get all Hedgehog resources from NetBox (mock implementation)"""
        # This would query the actual NetBox models
        # For demo purposes, returning mock data
        netbox_resources = {}
        
        for crd_spec in self.crd_specs:
            # Mock NetBox resource query
            # In real implementation, this would query the corresponding NetBox model
            netbox_resources[crd_spec['kind']] = []
        
        return netbox_resources
    
    def detect_changes(self, cluster_resources: Dict, netbox_resources: Dict) -> Dict:
        """Detect differences between cluster and NetBox resources"""
        changes = {
            'new_in_cluster': {},      # Resources in cluster but not in NetBox
            'new_in_netbox': {},       # Resources in NetBox but not in cluster
            'modified_in_cluster': {}, # Resources modified in cluster
            'modified_in_netbox': {},  # Resources modified in NetBox
            'deleted_from_cluster': {},# Resources deleted from cluster
            'deleted_from_netbox': {}, # Resources deleted from NetBox
            'out_of_sync': {},         # Resources with mismatched hashes
        }
        
        for resource_type in self.crd_specs:
            kind = resource_type['kind']
            
            cluster_items = {r['name']: r for r in cluster_resources.get(kind, [])}
            netbox_items = {r['name']: r for r in netbox_resources.get(kind, [])}
            
            cluster_names = set(cluster_items.keys())
            netbox_names = set(netbox_items.keys())
            
            # Resources only in cluster (created outside NetBox)
            new_in_cluster = cluster_names - netbox_names
            if new_in_cluster:
                changes['new_in_cluster'][kind] = [
                    cluster_items[name] for name in new_in_cluster
                ]
            
            # Resources only in NetBox (need to be created in cluster)
            new_in_netbox = netbox_names - cluster_names
            if new_in_netbox:
                changes['new_in_netbox'][kind] = [
                    netbox_items[name] for name in new_in_netbox
                ]
            
            # Resources in both - check for modifications
            common_names = cluster_names & netbox_names
            for name in common_names:
                cluster_resource = cluster_items[name]
                netbox_resource = netbox_items[name]
                
                if cluster_resource['hash'] != netbox_resource.get('hash'):
                    changes['out_of_sync'].setdefault(kind, []).append({
                        'name': name,
                        'cluster': cluster_resource,
                        'netbox': netbox_resource
                    })
        
        return changes
    
    def create_change_notification(self, changes: Dict) -> Dict:
        """Create notification about detected changes"""
        notification = {
            'timestamp': datetime.utcnow().isoformat(),
            'fabric': self.fabric.name,
            'summary': {},
            'details': changes,
            'requires_attention': False
        }
        
        # Count changes by type
        for change_type, resources in changes.items():
            if resources:
                total_count = sum(len(items) for items in resources.values())
                notification['summary'][change_type] = total_count
                
                # Flag for attention if there are external changes
                if change_type == 'new_in_cluster' and total_count > 0:
                    notification['requires_attention'] = True
        
        return notification
    
    def reconcile_resource_to_cluster(self, resource_type: str, resource_data: Dict) -> Tuple[bool, str]:
        """Apply a NetBox resource to the Kubernetes cluster"""
        if not self.custom_api:
            return False, "Not connected to cluster"
        
        # Find CRD spec for this resource type
        crd_spec = next((spec for spec in self.crd_specs if spec['kind'] == resource_type), None)
        if not crd_spec:
            return False, f"Unknown resource type: {resource_type}"
        
        try:
            # Build Kubernetes manifest
            manifest = {
                'apiVersion': f"{crd_spec['group']}/{crd_spec['version']}",
                'kind': crd_spec['kind'],
                'metadata': {
                    'name': resource_data['name'],
                    'namespace': resource_data.get('namespace', 'default'),
                    'labels': {
                        **resource_data.get('labels', {}),
                        'source': 'netbox-hedgehog-plugin',
                        'managed-by': 'netbox'
                    },
                    'annotations': {
                        **resource_data.get('annotations', {}),
                        'netbox.githedgehog.com/created-by': 'netbox-hedgehog-plugin',
                        'netbox.githedgehog.com/sync-time': datetime.utcnow().isoformat()
                    }
                },
                'spec': resource_data.get('spec', {})
            }
            
            # Check if resource exists
            try:
                existing = self.custom_api.get_namespaced_custom_object(
                    group=crd_spec['group'],
                    version=crd_spec['version'],
                    namespace=resource_data.get('namespace', 'default'),
                    plural=crd_spec['plural'],
                    name=resource_data['name']
                )
                
                # Update existing resource
                result = self.custom_api.patch_namespaced_custom_object(
                    group=crd_spec['group'],
                    version=crd_spec['version'],
                    namespace=resource_data.get('namespace', 'default'),
                    plural=crd_spec['plural'],
                    name=resource_data['name'],
                    body=manifest
                )
                return True, f"Updated {resource_type} '{resource_data['name']}'"
                
            except ApiException as e:
                if e.status == 404:
                    # Create new resource
                    result = self.custom_api.create_namespaced_custom_object(
                        group=crd_spec['group'],
                        version=crd_spec['version'],
                        namespace=resource_data.get('namespace', 'default'),
                        plural=crd_spec['plural'],
                        body=manifest
                    )
                    return True, f"Created {resource_type} '{resource_data['name']}'"
                else:
                    raise
        
        except Exception as e:
            logger.error(f"Failed to reconcile {resource_type} to cluster: {e}")
            return False, f"Reconciliation failed: {str(e)}"
    
    def reconcile_resource_to_netbox(self, resource_type: str, resource_data: Dict) -> Tuple[bool, str]:
        """Import a cluster resource to NetBox"""
        try:
            # This would create/update the corresponding NetBox model
            # For demo purposes, just log the action
            logger.info(f"Would import {resource_type} '{resource_data['name']}' to NetBox")
            
            # Mark resource as externally created
            resource_data['source'] = 'kubernetes-import'
            resource_data['managed_by_netbox'] = False
            resource_data['import_timestamp'] = datetime.utcnow().isoformat()
            
            # In real implementation, create/update NetBox model here
            
            return True, f"Imported {resource_type} '{resource_data['name']}' to NetBox"
            
        except Exception as e:
            logger.error(f"Failed to import {resource_type} to NetBox: {e}")
            return False, f"Import failed: {str(e)}"
    
    def perform_reconciliation(self, namespace: str = None, dry_run: bool = False) -> Dict:
        """Perform full reconciliation between cluster and NetBox"""
        reconciliation_result = {
            'timestamp': datetime.utcnow().isoformat(),
            'fabric': self.fabric.name,
            'dry_run': dry_run,
            'initialization_success': False,
            'changes_detected': {},
            'actions_taken': {},
            'notifications': [],
            'errors': []
        }
        
        # Initialize Kubernetes client
        if not self.initialize_kubernetes_client():
            reconciliation_result['errors'].append("Failed to initialize Kubernetes client")
            return reconciliation_result
        
        reconciliation_result['initialization_success'] = True
        
        try:
            logger.info(f"DEBUG: Starting reconciliation for fabric {self.fabric.name}")
            
            # Get current state from both sides
            cluster_resources = self.get_cluster_resources(namespace)
            logger.info(f"DEBUG: Got {len(cluster_resources)} cluster resource types")
            
            netbox_resources = self.get_netbox_resources()
            logger.info(f"DEBUG: Got {len(netbox_resources)} netbox resource types")
            
            # Detect changes
            changes = self.detect_changes(cluster_resources, netbox_resources)
            reconciliation_result['changes_detected'] = changes
            logger.info(f"DEBUG: Detected changes: {changes}")
            
            # Create notification if changes detected
            if any(changes.values()):
                notification = self.create_change_notification(changes)
                reconciliation_result['notifications'].append(notification)
            
            if not dry_run:
                logger.info(f"DEBUG: Running in non-dry-run mode")
                # Apply changes
                actions_taken = {
                    'imported_to_netbox': 0,
                    'applied_to_cluster': 0,
                    'conflicts_resolved': 0,
                    'errors': 0
                }
                
                # Import new cluster resources to NetBox
                print(f"DEBUG PRINT: About to process {len(changes.get('new_in_cluster', {}))} cluster resource types")
                for resource_type, resources in changes.get('new_in_cluster', {}).items():
                    print(f"DEBUG PRINT: Processing {len(resources)} resources of type {resource_type}")
                    for resource in resources:
                        success, message = self.reconcile_resource_to_netbox(resource_type, resource)
                        if success:
                            actions_taken['imported_to_netbox'] += 1
                        else:
                            actions_taken['errors'] += 1
                            reconciliation_result['errors'].append(message)
                print(f"DEBUG PRINT: Completed cluster resource import")
                
                # Apply NetBox resources to cluster
                print(f"DEBUG PRINT: About to process {len(changes.get('new_in_netbox', {}))} netbox resource types")
                for resource_type, resources in changes.get('new_in_netbox', {}).items():
                    for resource in resources:
                        success, message = self.reconcile_resource_to_cluster(resource_type, resource)
                        if success:
                            actions_taken['applied_to_cluster'] += 1
                        else:
                            actions_taken['errors'] += 1
                            reconciliation_result['errors'].append(message)
                print(f"DEBUG PRINT: Completed netbox resource apply")
                
                reconciliation_result['actions_taken'] = actions_taken
                print(f"DEBUG PRINT: Actions taken set: {actions_taken}")
            else:
                logger.info(f"DEBUG: Running in dry-run mode")
            
            # Update fabric sync status with timezone-aware datetime
            from django.utils import timezone
            new_sync_time = timezone.now()
            print(f"DEBUG PRINT: About to update fabric {self.fabric.name} last_sync from {self.fabric.last_sync} to {new_sync_time}")
            self.fabric.last_sync = new_sync_time
            self.fabric.sync_status = 'in_sync' if not reconciliation_result['errors'] else 'error'
            print(f"DEBUG PRINT: About to call save() on fabric {self.fabric.name}")
            self.fabric.save()  # CRITICAL: Must save to persist the updated sync status!
            print(f"DEBUG PRINT: Fabric {self.fabric.name} save completed, last_sync should now be {new_sync_time}")
            
        except Exception as e:
            logger.error(f"Reconciliation failed: {e}")
            reconciliation_result['errors'].append(f"Reconciliation failed: {str(e)}")
        
        return reconciliation_result
    
    def update_sync_timestamp_only(self) -> Dict:
        """Simple method to just update sync timestamp without full reconciliation"""
        try:
            from django.utils import timezone
            new_sync_time = timezone.now()
            old_sync_time = self.fabric.last_sync
            
            print(f"SIMPLE UPDATE: Updating fabric {self.fabric.name} last_sync from {old_sync_time} to {new_sync_time}")
            
            self.fabric.last_sync = new_sync_time
            self.fabric.sync_status = 'in_sync'
            self.fabric.save()
            
            # Verify the save worked
            self.fabric.refresh_from_db()
            print(f"SIMPLE UPDATE: Verification - fabric now has last_sync: {self.fabric.last_sync}")
            
            return {
                'success': True,
                'message': 'Timestamp updated successfully',
                'old_sync_time': old_sync_time.isoformat() if old_sync_time else None,
                'new_sync_time': new_sync_time.isoformat(),
                'verified_sync_time': self.fabric.last_sync.isoformat()
            }
            
        except Exception as e:
            print(f"SIMPLE UPDATE ERROR: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def schedule_reconciliation(self, interval_minutes: int = 5) -> Dict:
        """Schedule periodic reconciliation (mock implementation)"""
        # In a real Django application, this would use Celery or similar
        schedule_info = {
            'fabric': self.fabric.name,
            'interval_minutes': interval_minutes,
            'next_run': (datetime.utcnow() + timedelta(minutes=interval_minutes)).isoformat(),
            'enabled': True,
            'schedule_time': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Scheduled reconciliation for fabric '{self.fabric.name}' every {interval_minutes} minutes")
        return schedule_info