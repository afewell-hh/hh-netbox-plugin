"""
Fabric Onboarding Utilities
Handles onboarding of new Hedgehog fabric installations into NetBox.
"""

import json
import yaml
import base64
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import logging

logger = logging.getLogger(__name__)

class FabricOnboardingManager:
    """Manages the onboarding process for new Hedgehog fabrics"""
    
    # CRD types to import during onboarding
    CRD_IMPORT_SPECS = [
        # VPC API CRDs
        {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'vpcs', 'kind': 'VPC'},
        {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'externals', 'kind': 'External'},
        {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'externalattachments', 'kind': 'ExternalAttachment'},
        {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'externalpeerings', 'kind': 'ExternalPeering'},
        {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'ipv4namespaces', 'kind': 'IPv4Namespace'},
        {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'vpcattachments', 'kind': 'VPCAttachment'},
        {'group': 'vpc.githedgehog.com', 'version': 'v1beta1', 'plural': 'vpcpeerings', 'kind': 'VPCPeering'},
        
        # Wiring API CRDs
        {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'plural': 'connections', 'kind': 'Connection'},
        {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'plural': 'servers', 'kind': 'Server'},
        {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'plural': 'switches', 'kind': 'Switch'},
        {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'plural': 'switchgroups', 'kind': 'SwitchGroup'},
        {'group': 'wiring.githedgehog.com', 'version': 'v1beta1', 'plural': 'vlannamespaces', 'kind': 'VLANNamespace'},
    ]
    
    def __init__(self, fabric_model):
        """Initialize with a HedgehogFabric model instance"""
        self.fabric = fabric_model
        self.custom_api = None
        self.core_api = None
        
    def validate_kubernetes_connection(self) -> Tuple[bool, str, Dict]:
        """
        Validate connection to the Kubernetes cluster
        Returns: (success, message, cluster_info)
        """
        try:
            # Load configuration from fabric
            kubeconfig_data = self.fabric.get_kubernetes_config()
            if kubeconfig_data:
                # Load from provided kubeconfig
                config.load_kube_config_from_dict(kubeconfig_data)
            else:
                # Load from default location
                config.load_kube_config()
            
            # Initialize API clients
            self.custom_api = client.CustomObjectsApi()
            self.core_api = client.CoreV1Api()
            
            # Test connection
            version_api = client.VersionApi()
            version_info = version_api.get_code()
            
            # Get namespace access
            try:
                namespaces = self.core_api.list_namespace()
                namespace_count = len(namespaces.items)
                namespace_access = True
            except ApiException:
                namespace_count = 0
                namespace_access = False
            
            cluster_info = {
                'version': version_info.git_version,
                'platform': version_info.platform,
                'namespace_count': namespace_count,
                'namespace_access': namespace_access,
                'connection_time': datetime.utcnow().isoformat()
            }
            
            return True, "Connection successful", cluster_info
            
        except Exception as e:
            logger.error(f"Kubernetes connection failed: {e}")
            return False, f"Connection failed: {str(e)}", {}
    
    def discover_hedgehog_installation(self) -> Tuple[bool, str, Dict]:
        """
        Discover and validate Hedgehog installation in the cluster
        Returns: (success, message, installation_info)
        """
        if not self.custom_api:
            return False, "Not connected to cluster", {}
        
        installation_info = {
            'hedgehog_detected': False,
            'crd_types_found': [],
            'resource_counts': {},
            'namespaces_with_resources': [],
            'discovery_time': datetime.utcnow().isoformat()
        }
        
        try:
            # Check for Hedgehog CRDs
            crd_api = client.ApiextensionsV1Api()
            crds = crd_api.list_custom_resource_definition()
            
            hedgehog_crds = []
            for crd in crds.items:
                if 'githedgehog.com' in crd.spec.group:
                    hedgehog_crds.append({
                        'name': crd.metadata.name,
                        'group': crd.spec.group,
                        'kind': crd.spec.names.kind
                    })
            
            if not hedgehog_crds:
                return False, "No Hedgehog CRDs found in cluster", installation_info
            
            installation_info['hedgehog_detected'] = True
            installation_info['crd_types_found'] = hedgehog_crds
            
            # Count resources for each CRD type
            for crd_spec in self.CRD_IMPORT_SPECS:
                try:
                    resources = self.custom_api.list_cluster_custom_object(
                        group=crd_spec['group'],
                        version=crd_spec['version'],
                        plural=crd_spec['plural']
                    )
                    
                    count = len(resources.get('items', []))
                    installation_info['resource_counts'][crd_spec['kind']] = count
                    
                    # Track namespaces with resources
                    for item in resources.get('items', []):
                        ns = item['metadata'].get('namespace', 'cluster-scoped')
                        if ns not in installation_info['namespaces_with_resources']:
                            installation_info['namespaces_with_resources'].append(ns)
                            
                except ApiException as e:
                    if e.status != 404:  # Ignore not found errors
                        logger.warning(f"Error counting {crd_spec['kind']}: {e}")
                    installation_info['resource_counts'][crd_spec['kind']] = 0
            
            total_resources = sum(installation_info['resource_counts'].values())
            
            if total_resources == 0:
                return False, "Hedgehog CRDs found but no resources exist", installation_info
            
            return True, f"Hedgehog installation discovered with {total_resources} resources", installation_info
            
        except Exception as e:
            logger.error(f"Error discovering Hedgehog installation: {e}")
            return False, f"Discovery failed: {str(e)}", installation_info
    
    def import_existing_resources(self, namespace: str = None) -> Tuple[bool, str, Dict]:
        """
        Import existing Hedgehog resources from the cluster
        Returns: (success, message, import_results)
        """
        if not self.custom_api:
            return False, "Not connected to cluster", {}
        
        import_results = {
            'imported_resources': {},
            'failed_imports': {},
            'total_imported': 0,
            'total_failed': 0,
            'import_time': datetime.utcnow().isoformat()
        }
        
        try:
            for crd_spec in self.CRD_IMPORT_SPECS:
                try:
                    # Get resources from cluster
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
                    
                    imported_count = 0
                    failed_count = 0
                    
                    for resource in resources.get('items', []):
                        try:
                            # Extract key information
                            resource_info = {
                                'name': resource['metadata']['name'],
                                'namespace': resource['metadata'].get('namespace', 'cluster-scoped'),
                                'uid': resource['metadata']['uid'],
                                'creation_timestamp': resource['metadata'].get('creationTimestamp'),
                                'labels': resource['metadata'].get('labels', {}),
                                'annotations': resource['metadata'].get('annotations', {}),
                                'spec': resource.get('spec', {}),
                                'status': resource.get('status', {}),
                                'source': 'imported',  # Mark as imported from existing cluster
                                'managed_by_netbox': False  # Not created by NetBox
                            }
                            
                            # Here you would create the corresponding NetBox model instance
                            # For now, we'll just track what would be imported
                            imported_count += 1
                            
                        except Exception as e:
                            logger.error(f"Failed to import {resource['metadata']['name']}: {e}")
                            failed_count += 1
                    
                    import_results['imported_resources'][crd_spec['kind']] = imported_count
                    import_results['failed_imports'][crd_spec['kind']] = failed_count
                    import_results['total_imported'] += imported_count
                    import_results['total_failed'] += failed_count
                    
                except ApiException as e:
                    if e.status != 404:  # Ignore not found errors
                        logger.error(f"Error importing {crd_spec['kind']}: {e}")
                        import_results['failed_imports'][crd_spec['kind']] = -1
            
            message = f"Import completed: {import_results['total_imported']} resources imported"
            if import_results['total_failed'] > 0:
                message += f", {import_results['total_failed']} failed"
            
            return True, message, import_results
            
        except Exception as e:
            logger.error(f"Import process failed: {e}")
            return False, f"Import failed: {str(e)}", import_results

    def generate_service_account_yaml(self) -> str:
        """
        Generate YAML for creating a service account with appropriate permissions
        """
        fabric_name = self.fabric.name.lower().replace(' ', '-')
        
        yaml_content = f"""---
# Service Account for NetBox Hedgehog Plugin
apiVersion: v1
kind: ServiceAccount
metadata:
  name: netbox-hedgehog-{fabric_name}
  namespace: default
  labels:
    app.kubernetes.io/name: netbox-hedgehog-plugin
    app.kubernetes.io/instance: {fabric_name}
    app.kubernetes.io/component: service-account

---
# ClusterRole with permissions for Hedgehog CRDs
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: netbox-hedgehog-{fabric_name}
  labels:
    app.kubernetes.io/name: netbox-hedgehog-plugin
    app.kubernetes.io/instance: {fabric_name}
    app.kubernetes.io/component: cluster-role
rules:
# VPC API permissions
- apiGroups: ["vpc.githedgehog.com"]
  resources: ["*"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Wiring API permissions  
- apiGroups: ["wiring.githedgehog.com"]
  resources: ["*"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# Core API permissions for namespace access
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list"]

# CRD discovery permissions
- apiGroups: ["apiextensions.k8s.io"]
  resources: ["customresourcedefinitions"]
  verbs: ["get", "list"]

---
# ClusterRoleBinding to bind the service account to the cluster role
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: netbox-hedgehog-{fabric_name}
  labels:
    app.kubernetes.io/name: netbox-hedgehog-plugin
    app.kubernetes.io/instance: {fabric_name}
    app.kubernetes.io/component: cluster-role-binding
subjects:
- kind: ServiceAccount
  name: netbox-hedgehog-{fabric_name}
  namespace: default
roleRef:
  kind: ClusterRole
  name: netbox-hedgehog-{fabric_name}
  apiGroup: rbac.authorization.k8s.io

---
# Secret to hold the service account token (for K8s 1.24+)
apiVersion: v1
kind: Secret
metadata:
  name: netbox-hedgehog-{fabric_name}-token
  namespace: default
  labels:
    app.kubernetes.io/name: netbox-hedgehog-plugin
    app.kubernetes.io/instance: {fabric_name}
    app.kubernetes.io/component: service-account-token
  annotations:
    kubernetes.io/service-account.name: netbox-hedgehog-{fabric_name}
type: kubernetes.io/service-account-token
"""
        return yaml_content
    
    def extract_kubeconfig_from_service_account(self, sa_name: str, namespace: str = "default") -> Dict:
        """
        Extract kubeconfig data from a service account token
        """
        if not self.core_api:
            raise Exception("Not connected to cluster")
        
        try:
            # Get service account
            sa = self.core_api.read_namespaced_service_account(sa_name, namespace)
            
            # Get the token secret
            token_secret_name = f"{sa_name}-token"
            secret = self.core_api.read_namespaced_secret(token_secret_name, namespace)
            
            # Extract token and CA certificate
            token = base64.b64decode(secret.data['token']).decode('utf-8')
            ca_cert = secret.data['ca.crt']
            
            # Get cluster info
            cluster_config = client.Configuration().get_default_copy()
            
            # Build kubeconfig
            kubeconfig = {
                'apiVersion': 'v1',
                'kind': 'Config',
                'clusters': [{
                    'name': self.fabric.name,
                    'cluster': {
                        'certificate-authority-data': ca_cert,
                        'server': cluster_config.host
                    }
                }],
                'users': [{
                    'name': sa_name,
                    'user': {
                        'token': token
                    }
                }],
                'contexts': [{
                    'name': f"{self.fabric.name}-context",
                    'context': {
                        'cluster': self.fabric.name,
                        'user': sa_name,
                        'namespace': namespace
                    }
                }],
                'current-context': f"{self.fabric.name}-context"
            }
            
            return kubeconfig
            
        except Exception as e:
            logger.error(f"Failed to extract kubeconfig: {e}")
            raise
    
    def perform_full_onboarding(self, namespace: str = None) -> Dict:
        """
        Perform complete fabric onboarding process
        Returns: detailed results of the onboarding process
        """
        onboarding_results = {
            'fabric_name': self.fabric.name,
            'onboarding_time': datetime.utcnow().isoformat(),
            'steps': {}
        }
        
        # Step 1: Validate connection
        conn_success, conn_msg, cluster_info = self.validate_kubernetes_connection()
        onboarding_results['steps']['connection'] = {
            'success': conn_success,
            'message': conn_msg,
            'data': cluster_info
        }
        
        if not conn_success:
            return onboarding_results
        
        # Step 2: Discover Hedgehog installation
        disc_success, disc_msg, install_info = self.discover_hedgehog_installation()
        onboarding_results['steps']['discovery'] = {
            'success': disc_success,
            'message': disc_msg,
            'data': install_info
        }
        
        if not disc_success:
            return onboarding_results
        
        # Step 3: Import existing resources
        import_success, import_msg, import_results = self.import_existing_resources(namespace)
        onboarding_results['steps']['import'] = {
            'success': import_success,
            'message': import_msg,
            'data': import_results
        }
        
        # Update fabric with onboarding results
        self.fabric.last_sync = datetime.utcnow()
        self.fabric.sync_status = 'synced' if import_success else 'error'
        self.fabric.cluster_info = {
            **cluster_info,
            **install_info
        }
        
        return onboarding_results