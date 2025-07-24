"""
HCKC Test Helpers for HNP End-to-End Testing

Utilities for HCKC cluster testing and Kubernetes operations.
"""

import subprocess
import json
import yaml
import tempfile
import os
from typing import Dict, List, Optional, Any


class HCKCTestHelper:
    """Helper for HCKC cluster operations during testing."""
    
    def __init__(self, kubeconfig_path="~/.kube/config"):
        self.kubeconfig_path = os.path.expanduser(kubeconfig_path)
        self.kubectl_cmd = ['kubectl']
        
        # Add kubeconfig if specified and exists
        if os.path.exists(self.kubeconfig_path):
            self.kubectl_cmd.extend(['--kubeconfig', self.kubeconfig_path])
    
    def check_cluster_connectivity(self) -> Dict[str, Any]:
        """
        Check if kubectl can connect to the cluster.
        
        Returns:
            Dictionary with connectivity status
        """
        result = {
            'connected': False,
            'error': None,
            'nodes': [],
            'namespaces': []
        }
        
        try:
            # Test basic connectivity
            nodes_result = subprocess.run(
                self.kubectl_cmd + ['get', 'nodes', '-o', 'json'],
                capture_output=True, text=True, timeout=30
            )
            
            if nodes_result.returncode == 0:
                result['connected'] = True
                nodes_data = json.loads(nodes_result.stdout)
                result['nodes'] = [node['metadata']['name'] for node in nodes_data.get('items', [])]
                
                # Get namespaces
                ns_result = subprocess.run(
                    self.kubectl_cmd + ['get', 'namespaces', '-o', 'json'],
                    capture_output=True, text=True, timeout=30
                )
                
                if ns_result.returncode == 0:
                    ns_data = json.loads(ns_result.stdout)
                    result['namespaces'] = [ns['metadata']['name'] for ns in ns_data.get('items', [])]
            else:
                result['error'] = nodes_result.stderr
                
        except subprocess.TimeoutExpired:
            result['error'] = "Kubectl command timed out"
        except json.JSONDecodeError as e:
            result['error'] = f"Failed to parse kubectl output: {e}"
        except Exception as e:
            result['error'] = f"Cluster connectivity check failed: {e}"
        
        return result
    
    def get_hedgehog_crds(self) -> Dict[str, Any]:
        """
        Get all Hedgehog CRDs from the cluster.
        
        Returns:
            Dictionary with CRD information
        """
        result = {
            'found_crds': [],
            'error': None,
            'total_count': 0
        }
        
        try:
            # Get all CRDs
            crds_result = subprocess.run(
                self.kubectl_cmd + ['get', 'crds', '-o', 'json'],
                capture_output=True, text=True, timeout=30
            )
            
            if crds_result.returncode == 0:
                crds_data = json.loads(crds_result.stdout)
                
                # Filter for Hedgehog CRDs
                hedgehog_crds = []
                for crd in crds_data.get('items', []):
                    name = crd['metadata']['name']
                    if 'hedgehog' in name or 'githedgehog.com' in name:
                        hedgehog_crds.append({
                            'name': name,
                            'group': crd['spec']['group'],
                            'version': crd['spec']['versions'][0]['name'] if crd['spec']['versions'] else 'unknown',
                            'kind': crd['spec']['names']['kind']
                        })
                
                result['found_crds'] = hedgehog_crds
                result['total_count'] = len(hedgehog_crds)
            else:
                result['error'] = crds_result.stderr
                
        except subprocess.TimeoutExpired:
            result['error'] = "Kubectl command timed out"
        except json.JSONDecodeError as e:
            result['error'] = f"Failed to parse kubectl output: {e}"
        except Exception as e:
            result['error'] = f"Failed to get CRDs: {e}"
        
        return result
    
    def get_cluster_resources(self, namespace: str = None, kind: str = None) -> Dict[str, Any]:
        """
        Get resources from the cluster.
        
        Args:
            namespace: Kubernetes namespace to query
            kind: Resource kind to filter by
            
        Returns:
            Dictionary with resource information
        """
        result = {
            'resources': [],
            'error': None,
            'total_count': 0
        }
        
        try:
            cmd = self.kubectl_cmd + ['get']
            
            if kind:
                cmd.append(kind.lower())
            else:
                cmd.append('all')
            
            if namespace:
                cmd.extend(['-n', namespace])
            else:
                cmd.append('--all-namespaces')
            
            cmd.extend(['-o', 'json'])
            
            resources_result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
            
            if resources_result.returncode == 0:
                resources_data = json.loads(resources_result.stdout)
                
                resources = []
                for item in resources_data.get('items', []):
                    resource_info = {
                        'name': item['metadata']['name'],
                        'namespace': item['metadata'].get('namespace', 'cluster-scoped'),
                        'kind': item.get('kind', 'unknown'),
                        'apiVersion': item.get('apiVersion', 'unknown'),
                        'uid': item['metadata'].get('uid', ''),
                        'resourceVersion': item['metadata'].get('resourceVersion', ''),
                        'creationTimestamp': item['metadata'].get('creationTimestamp', '')
                    }
                    
                    # Add spec if present
                    if 'spec' in item:
                        resource_info['spec'] = item['spec']
                    
                    # Add status if present
                    if 'status' in item:
                        resource_info['status'] = item['status']
                    
                    resources.append(resource_info)
                
                result['resources'] = resources
                result['total_count'] = len(resources)
            else:
                result['error'] = resources_result.stderr
                
        except subprocess.TimeoutExpired:
            result['error'] = "Kubectl command timed out"
        except json.JSONDecodeError as e:
            result['error'] = f"Failed to parse kubectl output: {e}"
        except Exception as e:
            result['error'] = f"Failed to get resources: {e}"
        
        return result
    
    def apply_resource(self, yaml_content: str) -> Dict[str, Any]:
        """
        Apply a resource to the cluster.
        
        Args:
            yaml_content: YAML content to apply
            
        Returns:
            Dictionary with apply result
        """
        result = {
            'success': False,
            'error': None,
            'applied_resources': []
        }
        
        try:
            # Write YAML to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(yaml_content)
                temp_file = f.name
            
            try:
                # Apply resource
                apply_result = subprocess.run(
                    self.kubectl_cmd + ['apply', '-f', temp_file],
                    capture_output=True, text=True, timeout=60
                )
                
                if apply_result.returncode == 0:
                    result['success'] = True
                    # Parse applied resources from output
                    for line in apply_result.stdout.strip().split('\n'):
                        if line:
                            result['applied_resources'].append(line)
                else:
                    result['error'] = apply_result.stderr
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except subprocess.TimeoutExpired:
            result['error'] = "Kubectl apply timed out"
        except Exception as e:
            result['error'] = f"Failed to apply resource: {e}"
        
        return result
    
    def delete_resource(self, kind: str, name: str, namespace: str = None) -> Dict[str, Any]:
        """
        Delete a resource from the cluster.
        
        Args:
            kind: Resource kind
            name: Resource name
            namespace: Resource namespace
            
        Returns:
            Dictionary with delete result
        """
        result = {
            'success': False,
            'error': None
        }
        
        try:
            cmd = self.kubectl_cmd + ['delete', kind, name]
            
            if namespace:
                cmd.extend(['-n', namespace])
            
            delete_result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
            
            if delete_result.returncode == 0:
                result['success'] = True
            else:
                result['error'] = delete_result.stderr
                
        except subprocess.TimeoutExpired:
            result['error'] = "Kubectl delete timed out"
        except Exception as e:
            result['error'] = f"Failed to delete resource: {e}"
        
        return result
    
    def create_test_namespace(self, namespace_name: str) -> Dict[str, Any]:
        """
        Create a test namespace.
        
        Args:
            namespace_name: Name of namespace to create
            
        Returns:
            Dictionary with creation result
        """
        result = {
            'success': False,
            'error': None,
            'existed': False
        }
        
        try:
            # Check if namespace already exists
            check_result = subprocess.run(
                self.kubectl_cmd + ['get', 'namespace', namespace_name],
                capture_output=True, text=True, timeout=30
            )
            
            if check_result.returncode == 0:
                result['success'] = True
                result['existed'] = True
                return result
            
            # Create namespace
            create_result = subprocess.run(
                self.kubectl_cmd + ['create', 'namespace', namespace_name],
                capture_output=True, text=True, timeout=30
            )
            
            if create_result.returncode == 0:
                result['success'] = True
            else:
                result['error'] = create_result.stderr
                
        except subprocess.TimeoutExpired:
            result['error'] = "Kubectl command timed out"
        except Exception as e:
            result['error'] = f"Failed to create namespace: {e}"
        
        return result
    
    def cleanup_test_resources(self, namespace: str = None, label_selector: str = None) -> Dict[str, Any]:
        """
        Clean up test resources from the cluster.
        
        Args:
            namespace: Namespace to clean up
            label_selector: Label selector for resources to delete
            
        Returns:
            Dictionary with cleanup result
        """
        result = {
            'success': False,
            'error': None,
            'deleted_resources': []
        }
        
        try:
            cmd = self.kubectl_cmd + ['delete', 'all']
            
            if namespace:
                cmd.extend(['-n', namespace])
            
            if label_selector:
                cmd.extend(['-l', label_selector])
            else:
                # Default to test resources
                cmd.extend(['-l', 'environment=test'])
            
            # Add timeout for cleanup
            cmd.extend(['--timeout=60s'])
            
            cleanup_result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            
            if cleanup_result.returncode == 0:
                result['success'] = True
                # Parse deleted resources
                for line in cleanup_result.stdout.strip().split('\n'):
                    if line and 'deleted' in line:
                        result['deleted_resources'].append(line)
            else:
                # Cleanup might partially succeed - don't treat as complete failure
                result['error'] = cleanup_result.stderr
                result['success'] = True  # Best effort cleanup
                
        except subprocess.TimeoutExpired:
            result['error'] = "Kubectl cleanup timed out"
            result['success'] = True  # Best effort
        except Exception as e:
            result['error'] = f"Failed to cleanup resources: {e}"
        
        return result
    
    def compare_desired_vs_actual(self, desired_resources: List[Dict], namespace: str = None) -> Dict[str, Any]:
        """
        Compare desired resources (from GitOps) vs actual cluster state.
        
        Args:
            desired_resources: List of desired resource definitions
            namespace: Namespace to compare
            
        Returns:
            Dictionary with comparison results
        """
        result = {
            'in_sync': [],
            'drift_detected': [],
            'only_in_gitops': [],
            'only_on_cluster': [],
            'total_desired': len(desired_resources),
            'total_actual': 0,
            'sync_percentage': 0.0
        }
        
        try:
            # Get all cluster resources
            cluster_result = self.get_cluster_resources(namespace=namespace)
            if cluster_result['error']:
                result['error'] = cluster_result['error']
                return result
            
            actual_resources = cluster_result['resources']
            result['total_actual'] = len(actual_resources)
            
            # Create lookup maps
            desired_map = {}
            for resource in desired_resources:
                key = f"{resource.get('kind', '')}/{resource.get('metadata', {}).get('name', '')}"
                desired_map[key] = resource
            
            actual_map = {}
            for resource in actual_resources:
                key = f"{resource.get('kind', '')}/{resource.get('name', '')}"
                actual_map[key] = resource
            
            # Compare resources
            for key, desired in desired_map.items():
                if key in actual_map:
                    actual = actual_map[key]
                    
                    # Simple comparison - could be enhanced
                    if self._resources_match(desired, actual):
                        result['in_sync'].append({
                            'kind': desired.get('kind'),
                            'name': desired.get('metadata', {}).get('name'),
                            'status': 'in_sync'
                        })
                    else:
                        result['drift_detected'].append({
                            'kind': desired.get('kind'),
                            'name': desired.get('metadata', {}).get('name'),
                            'status': 'drift_detected'
                        })
                else:
                    result['only_in_gitops'].append({
                        'kind': desired.get('kind'),
                        'name': desired.get('metadata', {}).get('name'),
                        'status': 'only_in_gitops'
                    })
            
            # Find resources only on cluster
            for key, actual in actual_map.items():
                if key not in desired_map:
                    # Skip system resources
                    if not self._is_system_resource(actual):
                        result['only_on_cluster'].append({
                            'kind': actual.get('kind'),
                            'name': actual.get('name'),
                            'status': 'only_on_cluster'
                        })
            
            # Calculate sync percentage
            if result['total_desired'] > 0:
                in_sync_count = len(result['in_sync'])
                result['sync_percentage'] = (in_sync_count / result['total_desired']) * 100
            
        except Exception as e:
            result['error'] = f"Failed to compare states: {e}"
        
        return result
    
    def _resources_match(self, desired: Dict, actual: Dict) -> bool:
        """
        Simple resource matching logic.
        
        Args:
            desired: Desired resource definition
            actual: Actual cluster resource
            
        Returns:
            True if resources match, False otherwise
        """
        try:
            # Compare basic metadata
            desired_name = desired.get('metadata', {}).get('name')
            actual_name = actual.get('name')
            
            if desired_name != actual_name:
                return False
            
            # Compare specs (simplified)
            desired_spec = desired.get('spec', {})
            actual_spec = actual.get('spec', {})
            
            # This is a simplified comparison - real implementation would be more sophisticated
            return str(desired_spec) == str(actual_spec)
            
        except Exception:
            return False
    
    def _is_system_resource(self, resource: Dict) -> bool:
        """
        Check if a resource is a system resource that should be ignored.
        
        Args:
            resource: Resource definition
            
        Returns:
            True if system resource, False otherwise
        """
        try:
            name = resource.get('name', '')
            namespace = resource.get('namespace', '')
            kind = resource.get('kind', '')
            
            # Skip system namespaces
            system_namespaces = {'kube-system', 'kube-public', 'kube-node-lease', 'default'}
            if namespace in system_namespaces:
                return True
            
            # Skip system resource kinds
            system_kinds = {
                'Pod', 'ReplicaSet', 'Deployment', 'Service', 'Endpoints',
                'Event', 'ConfigMap', 'Secret'
            }
            if kind in system_kinds:
                return True
            
            # Skip resources with system prefixes
            system_prefixes = ['kube-', 'system:', 'kubernetes-']
            for prefix in system_prefixes:
                if name.startswith(prefix):
                    return True
            
            return False
            
        except Exception:
            return True  # Err on side of caution