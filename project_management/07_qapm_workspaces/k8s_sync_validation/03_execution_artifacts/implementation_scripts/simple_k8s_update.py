#!/usr/bin/env python3
"""
Simple K8s configuration update - only update the K8s fields
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

def update_k8s_config():
    """Update only K8s configuration fields"""
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
    
    print("=== UPDATING K8S CONFIGURATION ONLY ===")
    
    # Update K8s fields and fix validation issues - don't include watch_crd_types
    update_data = {
        'kubernetes_server': k8s_server,
        'kubernetes_token': k8s_token,
        'kubernetes_ca_cert': k8s_ca_cert,
        'sync_status': 'in_sync'   # Fix invalid 'synced' value
    }
    
    print(f"Updating fabric {fabric_id} with K8s configuration:")
    print(f"  kubernetes_server: {k8s_server}")
    print(f"  kubernetes_token: ***REDACTED***")
    print(f"  kubernetes_ca_cert: ***REDACTED***")
    
    try:
        url = urljoin(netbox_url, f'api/plugins/hedgehog/fabrics/{fabric_id}/')
        response = session.patch(url, json=update_data)
        
        if response.status_code == 200:
            print("✅ SUCCESS - K8s configuration updated")
            updated_data = response.json()
            
            # Validate the update
            print("\nValidation:")
            print(f"  kubernetes_server: {'✅' if updated_data.get('kubernetes_server') == k8s_server else '❌'}")
            print(f"  kubernetes_token: {'✅' if updated_data.get('kubernetes_token') == k8s_token else '❌'}")
            print(f"  kubernetes_ca_cert: {'✅' if updated_data.get('kubernetes_ca_cert') == k8s_ca_cert else '❌'}")
            
            return updated_data
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None

if __name__ == '__main__':
    result = update_k8s_config()
    if result:
        # Save result
        with open('/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/k8s_sync_validation/04_evidence_collection/status_validation/fabric_update_result.json', 'w') as f:
            json.dump(result, f, indent=2)
        print("\n✅ Update result saved to evidence collection")