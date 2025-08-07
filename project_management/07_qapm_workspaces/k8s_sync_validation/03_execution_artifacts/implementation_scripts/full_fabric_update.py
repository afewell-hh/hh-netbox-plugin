#!/usr/bin/env python3
"""
Full fabric update - get current values and update with K8s fields
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

def full_fabric_update():
    """Get current fabric and update with K8s config"""
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
    
    print("=== GETTING CURRENT FABRIC FOR FULL UPDATE ===")
    
    # Get current fabric data
    try:
        url = urljoin(netbox_url, f'api/plugins/hedgehog/fabrics/{fabric_id}/')
        response = session.get(url)
        response.raise_for_status()
        
        current_fabric = response.json()
        print(f"Current fabric retrieved: {current_fabric.get('name')}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR getting fabric: {e}")
        return None
    
    # Update the K8s fields
    current_fabric['kubernetes_server'] = k8s_server
    current_fabric['kubernetes_token'] = k8s_token
    current_fabric['kubernetes_ca_cert'] = k8s_ca_cert
    current_fabric['sync_status'] = 'in_sync'  # Fix the invalid 'synced' value
    
    # Remove read-only fields that shouldn't be in the update
    read_only_fields = ['id', 'display', 'created', 'last_updated', 
                       'custom_field_data', 'git_repository_url']
    for field in read_only_fields:
        current_fabric.pop(field, None)
    
    print(f"Updating fabric {fabric_id} with:")
    print(f"  kubernetes_server: {k8s_server}")
    print(f"  kubernetes_token: ***REDACTED***")
    print(f"  kubernetes_ca_cert: ***REDACTED***")
    print(f"  sync_status: in_sync")
    
    try:
        url = urljoin(netbox_url, f'api/plugins/hedgehog/fabrics/{fabric_id}/')
        response = session.put(url, json=current_fabric)
        
        if response.status_code == 200:
            print("✅ SUCCESS - Fabric updated with K8s configuration")
            updated_data = response.json()
            
            # Validate the update
            print("\nValidation:")
            print(f"  kubernetes_server: {'✅' if updated_data.get('kubernetes_server') == k8s_server else '❌'}")
            print(f"  kubernetes_token: {'✅' if updated_data.get('kubernetes_token') == k8s_token else '❌'}")
            print(f"  kubernetes_ca_cert: {'✅' if updated_data.get('kubernetes_ca_cert') == k8s_ca_cert else '❌'}")
            print(f"  sync_status: {'✅' if updated_data.get('sync_status') == 'in_sync' else '❌'}")
            
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
    result = full_fabric_update()
    if result:
        # Save result
        os.makedirs('/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/k8s_sync_validation/04_evidence_collection/status_validation', exist_ok=True)
        with open('/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/k8s_sync_validation/04_evidence_collection/status_validation/fabric_update_success.json', 'w') as f:
            json.dump(result, f, indent=2)
        print("\n✅ Update result saved to evidence collection")