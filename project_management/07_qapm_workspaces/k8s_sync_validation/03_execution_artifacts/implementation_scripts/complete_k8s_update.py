#!/usr/bin/env python3
"""
Complete K8s configuration update keeping valid sync_status
"""

import os
import json
import subprocess

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

def complete_k8s_update():
    """Complete K8s configuration update"""
    k8s_server = os.getenv('TEST_FABRIC_K8S_API_SERVER')
    k8s_token = os.getenv('TEST_FABRIC_K8S_TOKEN')
    k8s_ca_cert = os.getenv('TEST_FABRIC_K8S_API_SERVER_CA')
    fabric_id = 26
    
    print("=== COMPLETE K8S CONFIGURATION UPDATE ===")
    
    # Create a Django shell script to update all K8s fields
    django_script = f'''
from netbox_hedgehog.models import HedgehogFabric
import json

try:
    fabric = HedgehogFabric.objects.get(id={fabric_id})
    print(f"Found fabric: {{fabric.name}}")
    print(f"Current sync_status: {{fabric.sync_status}}")
    
    # Update all K8s fields but keep the current sync_status
    fabric.kubernetes_server = "{k8s_server}"
    fabric.kubernetes_token = "{k8s_token}"
    fabric.kubernetes_ca_cert = """{k8s_ca_cert}"""
    # Keep existing sync_status value
    
    # Save the fabric
    fabric.save()
    
    print("✅ SUCCESS - Fabric updated with complete K8s configuration")
    print(f"  kubernetes_server: {{fabric.kubernetes_server}}")
    print(f"  kubernetes_token: {{'***REDACTED***' if fabric.kubernetes_token else 'EMPTY'}}")
    print(f"  kubernetes_ca_cert: {{'***REDACTED***' if fabric.kubernetes_ca_cert else 'EMPTY'}}")
    print(f"  kubernetes_namespace: {{fabric.kubernetes_namespace}}")
    print(f"  sync_status: {{fabric.sync_status}}")
    
    # Export result for evidence
    result = {{
        "id": fabric.id,
        "name": fabric.name,
        "kubernetes_server": fabric.kubernetes_server,
        "kubernetes_token": "***REDACTED***",
        "kubernetes_ca_cert": "***REDACTED***",
        "kubernetes_namespace": fabric.kubernetes_namespace,
        "sync_status": fabric.sync_status,
        "update_success": True,
        "update_timestamp": "{{}}"
    }}
    
    import datetime
    result["update_timestamp"] = datetime.datetime.now().isoformat()
    
    with open('/tmp/complete_k8s_update_result.json', 'w') as f:
        json.dump(result, f, indent=2)
        
except Exception as e:
    print(f"❌ ERROR: {{e}}")
    import traceback
    traceback.print_exc()
    result = {{"error": str(e), "update_success": False}}
    with open('/tmp/complete_k8s_update_result.json', 'w') as f:
        json.dump(result, f, indent=2)
'''
    
    try:
        # Execute the Django shell script in the NetBox container
        cmd = [
            'sudo', 'docker', 'exec', '-i', 'netbox-docker-netbox-1',
            'python', '/opt/netbox/netbox/manage.py', 'shell'
        ]
        
        print("Executing complete K8s update in NetBox container...")
        result = subprocess.run(cmd, input=django_script, text=True, 
                              capture_output=True, timeout=60)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        # Copy the result file from the container
        os.makedirs('/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/k8s_sync_validation/04_evidence_collection/status_validation', exist_ok=True)
        
        copy_cmd = [
            'sudo', 'docker', 'cp',
            'netbox-docker-netbox-1:/tmp/complete_k8s_update_result.json',
            '/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/k8s_sync_validation/04_evidence_collection/status_validation/complete_k8s_update_result.json'
        ]
        
        subprocess.run(copy_cmd, check=True)
        print("\n✅ Update result copied to evidence collection")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == '__main__':
    success = complete_k8s_update()
    print(f"\nComplete K8s update {'succeeded' if success else 'failed'}")