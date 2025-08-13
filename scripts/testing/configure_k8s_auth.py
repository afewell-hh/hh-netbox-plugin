#!/usr/bin/env python3
"""
Kubernetes Authentication Configuration for Hedgehog Fabric

This script configures the fabric with the proper service account token
and tests the K8s connection functionality.
"""
import os
import sys
import django
import base64
import subprocess
import json
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
sys.path.insert(0, '/opt/netbox')
django.setup()

from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.choices import SyncStatusChoices, ConnectionStatusChoices

def get_service_account_token():
    """Retrieve the service account token from Kubernetes cluster"""
    try:
        result = subprocess.run([
            'kubectl', 'get', 'secret', 'hnp-sync-token', 
            '-o', 'jsonpath={.data.token}'
        ], capture_output=True, text=True, check=True)
        
        # Decode base64 token
        token = base64.b64decode(result.stdout).decode('utf-8')
        return token
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving token: {e}")
        return None

def get_ca_certificate():
    """Retrieve the CA certificate from Kubernetes cluster"""
    try:
        result = subprocess.run([
            'kubectl', 'get', 'secret', 'hnp-sync-token', 
            '-o', 'jsonpath={.data.ca\.crt}'
        ], capture_output=True, text=True, check=True)
        
        # Decode base64 CA cert
        ca_cert = base64.b64decode(result.stdout).decode('utf-8')
        return ca_cert
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving CA certificate: {e}")
        return None

def test_k8s_connection(fabric):
    """Test Kubernetes connection with the configured authentication"""
    import tempfile
    import yaml
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    
    try:
        # Create temporary kubeconfig with fabric credentials
        kubeconfig = {
            'apiVersion': 'v1',
            'kind': 'Config',
            'clusters': [{
                'name': 'fabric-cluster',
                'cluster': {
                    'server': fabric.kubernetes_server,
                    'certificate-authority-data': base64.b64encode(fabric.kubernetes_ca_cert.encode()).decode()
                }
            }],
            'users': [{
                'name': 'fabric-user',
                'user': {
                    'token': fabric.kubernetes_token
                }
            }],
            'contexts': [{
                'name': 'fabric-context',
                'context': {
                    'cluster': 'fabric-cluster',
                    'user': 'fabric-user',
                    'namespace': fabric.kubernetes_namespace
                }
            }],
            'current-context': 'fabric-context'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(kubeconfig, f)
            kubeconfig_path = f.name
        
        try:
            # Load the kubeconfig and test connection
            config.load_kube_config(config_file=kubeconfig_path)
            v1 = client.CoreV1Api()
            
            # Test API access
            namespaces = v1.list_namespace()
            print(f"✅ Successfully connected to K8s cluster: {fabric.kubernetes_server}")
            print(f"✅ Found {len(namespaces.items)} namespaces")
            
            # Test specific namespace access
            try:
                pods = v1.list_namespaced_pod(namespace=fabric.kubernetes_namespace)
                print(f"✅ Successfully accessed namespace '{fabric.kubernetes_namespace}' with {len(pods.items)} pods")
                return True, None
                
            except ApiException as e:
                if e.status == 403:
                    return True, f"Connection successful but insufficient permissions for namespace '{fabric.kubernetes_namespace}'"
                else:
                    return False, f"Error accessing namespace: {e}"
                    
        finally:
            os.unlink(kubeconfig_path)
            
    except Exception as e:
        return False, f"Connection test failed: {str(e)}"

def main():
    print("🔧 Configuring Kubernetes Authentication for Hedgehog Fabric")
    print("=" * 60)
    
    # Get the service account token
    print("\n1. Retrieving service account token from K8s cluster...")
    token = get_service_account_token()
    if not token:
        print("❌ Failed to retrieve service account token")
        return False
    
    print(f"✅ Retrieved token (length: {len(token)} characters)")
    
    # Get the CA certificate
    print("\n2. Retrieving CA certificate from K8s cluster...")
    ca_cert = get_ca_certificate()
    if not ca_cert:
        print("❌ Failed to retrieve CA certificate")
        return False
        
    print(f"✅ Retrieved CA certificate (length: {len(ca_cert)} characters)")
    
    # Find and update the fabric
    print("\n3. Updating fabric configuration...")
    try:
        fabrics = HedgehogFabric.objects.all()
        if not fabrics.exists():
            print("❌ No fabrics found in database")
            return False
            
        fabric = fabrics.first()
        print(f"✅ Found fabric: {fabric.name}")
        print(f"   Current K8s server: {fabric.kubernetes_server}")
        print(f"   Current sync status: {fabric.sync_status}")
        print(f"   Current connection status: {fabric.connection_status}")
        
        # Update authentication configuration
        fabric.kubernetes_token = token
        fabric.kubernetes_ca_cert = ca_cert
        
        # Update status to reflect that we're attempting connection
        fabric.connection_status = ConnectionStatusChoices.TESTING
        fabric.save()
        
        print("✅ Updated fabric with authentication credentials")
        
    except Exception as e:
        print(f"❌ Error updating fabric: {e}")
        return False
    
    # Test the connection
    print("\n4. Testing Kubernetes connection...")
    success, error = test_k8s_connection(fabric)
    
    if success:
        fabric.connection_status = ConnectionStatusChoices.CONNECTED
        if error:
            fabric.connection_error = error
            fabric.sync_status = SyncStatusChoices.ERROR
        else:
            fabric.connection_error = ""
            fabric.sync_status = SyncStatusChoices.READY
        fabric.save()
        
        print("✅ Connection test successful!")
        if error:
            print(f"⚠️  Warning: {error}")
            
    else:
        fabric.connection_status = ConnectionStatusChoices.FAILED
        fabric.connection_error = error
        fabric.sync_status = SyncStatusChoices.ERROR
        fabric.save()
        
        print(f"❌ Connection test failed: {error}")
        return False
    
    # Display final configuration
    fabric.refresh_from_db()
    print("\n5. Final Configuration Status:")
    print(f"   Fabric: {fabric.name}")
    print(f"   K8s Server: {fabric.kubernetes_server}")
    print(f"   Namespace: {fabric.kubernetes_namespace}")
    print(f"   Connection Status: {fabric.connection_status}")
    print(f"   Sync Status: {fabric.sync_status}")
    
    if fabric.connection_error:
        print(f"   Connection Error: {fabric.connection_error}")
    
    # Create evidence file
    evidence = {
        'timestamp': datetime.now().isoformat(),
        'fabric_name': fabric.name,
        'k8s_server': fabric.kubernetes_server,
        'k8s_namespace': fabric.kubernetes_namespace,
        'connection_status': fabric.connection_status,
        'sync_status': fabric.sync_status,
        'token_configured': bool(fabric.kubernetes_token),
        'ca_cert_configured': bool(fabric.kubernetes_ca_cert),
        'connection_test_success': success,
        'connection_error': fabric.connection_error or None,
        'token_length': len(fabric.kubernetes_token),
        'ca_cert_length': len(fabric.kubernetes_ca_cert)
    }
    
    with open(f'k8s_auth_config_evidence_{int(datetime.now().timestamp())}.json', 'w') as f:
        json.dump(evidence, f, indent=2)
    
    print(f"\n✅ Configuration complete! Evidence saved.")
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)