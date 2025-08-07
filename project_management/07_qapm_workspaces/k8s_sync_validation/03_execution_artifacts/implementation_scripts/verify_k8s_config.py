#!/usr/bin/env python3
"""
Verify K8s configuration was properly applied
"""

import os
import json
import requests
from urllib.parse import urljoin

# Load environment variables from .env file
def load_env_file(env_path='/home/ubuntu/cc/hedgehog-netbox-plugin/.env'):
    """Load environment variables from .env file"""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    os.environ[key] = value

# Load environment variables
load_env_file()

def verify_k8s_config():
    """Verify K8s configuration is properly applied"""
    netbox_url = os.getenv('NETBOX_URL', 'http://localhost:8000/')
    netbox_token = os.getenv('NETBOX_TOKEN')
    k8s_server = os.getenv('TEST_FABRIC_K8S_API_SERVER')
    k8s_token = os.getenv('TEST_FABRIC_K8S_TOKEN')
    k8s_ca_cert = os.getenv('TEST_FABRIC_K8S_API_SERVER_CA')
    fabric_id = 26
    
    session = requests.Session()
    session.headers.update({
        'Authorization': f'Token {netbox_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    print("=== VERIFYING K8S CONFIGURATION ===")
    
    try:
        url = urljoin(netbox_url, f'api/plugins/hedgehog/fabrics/{fabric_id}/')
        response = session.get(url)
        response.raise_for_status()
        
        fabric_data = response.json()
        
        print(f"Fabric: {fabric_data.get('name')} (ID: {fabric_data.get('id')})")
        print("\nK8s Configuration Verification:")
        
        # Check each field
        validations = []
        
        # kubernetes_server
        actual_server = fabric_data.get('kubernetes_server', '')
        server_ok = actual_server == k8s_server
        print(f"  ✅ kubernetes_server: {actual_server}" if server_ok else f"  ❌ kubernetes_server: Expected {k8s_server}, got {actual_server}")
        validations.append(('kubernetes_server', server_ok))
        
        # kubernetes_token  
        actual_token = fabric_data.get('kubernetes_token', '')
        token_ok = actual_token == k8s_token
        print(f"  ✅ kubernetes_token: ***CONFIGURED***" if token_ok else f"  ❌ kubernetes_token: NOT CONFIGURED CORRECTLY")
        validations.append(('kubernetes_token', token_ok))
        
        # kubernetes_ca_cert
        actual_cert = fabric_data.get('kubernetes_ca_cert', '')
        cert_ok = actual_cert == k8s_ca_cert
        print(f"  ✅ kubernetes_ca_cert: ***CONFIGURED***" if cert_ok else f"  ❌ kubernetes_ca_cert: NOT CONFIGURED CORRECTLY")
        validations.append(('kubernetes_ca_cert', cert_ok))
        
        # kubernetes_namespace
        actual_namespace = fabric_data.get('kubernetes_namespace', '')
        namespace_ok = actual_namespace == 'default'
        print(f"  ✅ kubernetes_namespace: {actual_namespace}" if namespace_ok else f"  ❌ kubernetes_namespace: Expected 'default', got '{actual_namespace}'")
        validations.append(('kubernetes_namespace', namespace_ok))
        
        # sync_status
        sync_status = fabric_data.get('sync_status', '')
        print(f"  ℹ️  sync_status: {sync_status}")
        
        # Overall validation
        all_valid = all(valid for _, valid in validations)
        
        print(f"\n{'✅ ALL K8S CONFIGURATION FIELDS VERIFIED' if all_valid else '❌ SOME K8S CONFIGURATION FIELDS FAILED'}")
        
        # Create verification report
        verification_report = {
            'fabric_id': fabric_id,
            'fabric_name': fabric_data.get('name'),
            'verification_timestamp': None,
            'k8s_config_verification': {
                'kubernetes_server': {'expected': k8s_server, 'actual': actual_server, 'valid': server_ok},
                'kubernetes_token': {'configured': bool(actual_token), 'valid': token_ok},
                'kubernetes_ca_cert': {'configured': bool(actual_cert), 'valid': cert_ok},
                'kubernetes_namespace': {'expected': 'default', 'actual': actual_namespace, 'valid': namespace_ok}
            },
            'overall_status': 'PASSED' if all_valid else 'FAILED',
            'sync_status': sync_status
        }
        
        import datetime
        verification_report['verification_timestamp'] = datetime.datetime.now().isoformat()
        
        # Save verification report
        os.makedirs('/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/k8s_sync_validation/04_evidence_collection/status_validation', exist_ok=True)
        
        with open('/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/k8s_sync_validation/04_evidence_collection/status_validation/k8s_config_verification.json', 'w') as f:
            json.dump(verification_report, f, indent=2)
            
        print(f"\n📄 Verification report saved to evidence collection")
        
        return all_valid
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Failed to retrieve fabric: {e}")
        return False

if __name__ == '__main__':
    success = verify_k8s_config()
    print(f"\nK8s configuration verification {'PASSED' if success else 'FAILED'}")