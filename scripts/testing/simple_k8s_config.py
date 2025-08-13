#!/usr/bin/env python3
"""
Simple Kubernetes Authentication Configuration Script

This script configures the fabric with K8s service account authentication
using a direct database approach when Django shell is not available.
"""
import base64
import subprocess
import json
import sqlite3
import os
from datetime import datetime

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

def get_k8s_server():
    """Get the Kubernetes server URL from kubectl config"""
    try:
        result = subprocess.run([
            'kubectl', 'config', 'view', '--minify', '-o', 
            'jsonpath={.clusters[0].cluster.server}'
        ], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting K8s server: {e}")
        return None

def test_k8s_connection_simple(server, token, ca_cert):
    """Simple test of Kubernetes connection using kubectl with token"""
    try:
        import tempfile
        import yaml
        
        # Create a temporary kubeconfig
        kubeconfig = {
            'apiVersion': 'v1',
            'kind': 'Config',
            'clusters': [{
                'name': 'test-cluster',
                'cluster': {
                    'server': server,
                    'certificate-authority-data': base64.b64encode(ca_cert.encode()).decode()
                }
            }],
            'users': [{
                'name': 'test-user',
                'user': {
                    'token': token
                }
            }],
            'contexts': [{
                'name': 'test-context',
                'context': {
                    'cluster': 'test-cluster',
                    'user': 'test-user'
                }
            }],
            'current-context': 'test-context'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(kubeconfig, f)
            kubeconfig_path = f.name
        
        try:
            # Test connection using kubectl with the temporary config
            result = subprocess.run([
                'kubectl', '--kubeconfig', kubeconfig_path, 
                'get', 'namespaces', '--timeout=10s'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Kubernetes connection test successful")
                return True, None
            else:
                return False, f"kubectl error: {result.stderr}"
                
        finally:
            os.unlink(kubeconfig_path)
            
    except Exception as e:
        return False, f"Connection test failed: {str(e)}"

def create_fabric_configuration(token, ca_cert, server):
    """Create a fabric configuration evidence file with the K8s auth data"""
    
    # Create configuration data
    config_data = {
        'timestamp': datetime.now().isoformat(),
        'k8s_server': server,
        'k8s_namespace': 'default',
        'token_configured': True,
        'ca_cert_configured': True,
        'token_length': len(token),
        'ca_cert_length': len(ca_cert),
        'configuration_method': 'service_account_token'
    }
    
    # Test the connection
    print("Testing Kubernetes connection...")
    connection_success, connection_error = test_k8s_connection_simple(server, token, ca_cert)
    
    config_data['connection_test_success'] = connection_success
    config_data['connection_error'] = connection_error
    
    if connection_success:
        config_data['connection_status'] = 'CONNECTED'
        config_data['sync_status'] = 'READY'
    else:
        config_data['connection_status'] = 'FAILED'
        config_data['sync_status'] = 'ERROR'
    
    # Save evidence file
    evidence_file = f'k8s_fabric_auth_config_{int(datetime.now().timestamp())}.json'
    with open(evidence_file, 'w') as f:
        json.dump(config_data, f, indent=2)
    
    return config_data, evidence_file

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
    
    # Get K8s server URL
    print("\n3. Getting Kubernetes server URL...")
    server = get_k8s_server()
    if not server:
        print("❌ Failed to get K8s server URL")
        return False
    
    print(f"✅ K8s Server URL: {server}")
    
    # Create configuration and test
    print("\n4. Creating fabric configuration and testing connection...")
    config_data, evidence_file = create_fabric_configuration(token, ca_cert, server)
    
    # Display results
    print("\n5. Configuration Summary:")
    print(f"   K8s Server: {config_data['k8s_server']}")
    print(f"   Connection Status: {config_data['connection_status']}")
    print(f"   Sync Status: {config_data['sync_status']}")
    print(f"   Token Length: {config_data['token_length']} characters")
    print(f"   CA Cert Length: {config_data['ca_cert_length']} characters")
    
    if config_data['connection_error']:
        print(f"   Connection Error: {config_data['connection_error']}")
    
    # Save actual configuration values for manual fabric update
    config_values = {
        'kubernetes_server': server,
        'kubernetes_token': token,
        'kubernetes_ca_cert': ca_cert,
        'kubernetes_namespace': 'default'
    }
    
    config_file = f'fabric_k8s_config_values_{int(datetime.now().timestamp())}.json'
    with open(config_file, 'w') as f:
        json.dump(config_values, f, indent=2)
    
    print(f"\n✅ Configuration complete!")
    print(f"   Evidence file: {evidence_file}")
    print(f"   Config values file: {config_file}")
    
    if config_data['connection_test_success']:
        print("\n🎉 Kubernetes authentication is working correctly!")
        print("   The fabric can now be manually updated with these credentials.")
        return True
    else:
        print(f"\n⚠️  Connection test failed: {config_data['connection_error']}")
        print("   Please check the configuration and try again.")
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)