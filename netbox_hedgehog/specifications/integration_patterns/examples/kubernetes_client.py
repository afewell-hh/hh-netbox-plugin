#!/usr/bin/env python3
"""
Kubernetes Client Integration Example
Demonstrates best practices for Kubernetes API integration.
"""

import os
import logging
from typing import Dict, Any, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)

class KubernetesIntegrationExample:
    """Example Kubernetes client integration"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize Kubernetes client"""
        self.config_path = config_path or os.environ.get('KUBECONFIG')
        self._client = None
        self._custom_client = None
        self._init_clients()
    
    def _init_clients(self):
        """Initialize Kubernetes API clients"""
        try:
            if self.config_path and os.path.exists(self.config_path):
                config.load_kube_config(config_file=self.config_path)
            else:
                config.load_incluster_config()
            
            self._client = client.CoreV1Api()
            self._custom_client = client.CustomObjectsApi()
            
            logger.info("Kubernetes clients initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes clients: {e}")
            raise
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Kubernetes connection"""
        try:
            version = self._client.get_code()
            nodes = self._client.list_node()
            
            return {
                'status': 'connected',
                'version': version.git_version,
                'node_count': len(nodes.items)
            }
        except ApiException as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def create_custom_resource(self, group: str, version: str, plural: str,
                              namespace: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Create custom resource"""
        try:
            result = self._custom_client.create_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                body=body
            )
            
            logger.info(f"Created custom resource: {body.get('metadata', {}).get('name')}")
            return result
            
        except ApiException as e:
            logger.error(f"Failed to create custom resource: {e}")
            raise

# Example usage
if __name__ == '__main__':
    k8s = KubernetesIntegrationExample()
    status = k8s.test_connection()
    print(f"Connection status: {status}")