#!/usr/bin/env python3
"""
Direct database update approach using Django management command
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

def update_fabric_via_container():
    """Update fabric directly via Django management in the container"""
    k8s_server = os.getenv('TEST_FABRIC_K8S_API_SERVER')
    k8s_token = os.getenv('TEST_FABRIC_K8S_TOKEN')
    k8s_ca_cert = os.getenv('TEST_FABRIC_K8S_API_SERVER_CA')
    fabric_id = 26
    
    print("=== UPDATING FABRIC VIA CONTAINER DJANGO SHELL ===")
    
    # Create a Django shell script to update the fabric
    django_script = f'''
from netbox_hedgehog.models import HedgehogFabric
import json

try:
    fabric = HedgehogFabric.objects.get(id={fabric_id})
    print(f"Found fabric: {{fabric.name}}")
    
    # Update K8s fields
    fabric.kubernetes_server = "{k8s_server}"
    fabric.kubernetes_token = "{k8s_token}"
    fabric.kubernetes_ca_cert = """{k8s_ca_cert}"""
    fabric.sync_status = "in_sync"  # Fix invalid 'synced' value
    
    # Save the fabric
    fabric.save()
    
    print("✅ SUCCESS - Fabric updated with K8s configuration")
    print(f"  kubernetes_server: {{fabric.kubernetes_server}}")
    print(f"  kubernetes_token: {{'***REDACTED***' if fabric.kubernetes_token else 'EMPTY'}}")
    print(f"  kubernetes_ca_cert: {{'***REDACTED***' if fabric.kubernetes_ca_cert else 'EMPTY'}}")
    print(f"  sync_status: {{fabric.sync_status}}")
    
    # Export result
    result = {{
        "id": fabric.id,
        "name": fabric.name,
        "kubernetes_server": fabric.kubernetes_server,
        "kubernetes_token": "***REDACTED***",
        "kubernetes_ca_cert": "***REDACTED***",
        "sync_status": fabric.sync_status,
        "update_success": True
    }}
    
    with open('/tmp/fabric_update_result.json', 'w') as f:
        json.dump(result, f, indent=2)
        
except Exception as e:
    print(f"❌ ERROR: {{e}}")
    result = {{"error": str(e), "update_success": False}}
    with open('/tmp/fabric_update_result.json', 'w') as f:
        json.dump(result, f, indent=2)
'''
    
    try:
        # Execute the Django shell script in the NetBox container
        cmd = [
            'sudo', 'docker', 'exec', '-i', 'netbox-docker-netbox-1',
            'python', '/opt/netbox/netbox/manage.py', 'shell'
        ]
        
        print("Executing Django shell script in NetBox container...")
        result = subprocess.run(cmd, input=django_script, text=True, 
                              capture_output=True, timeout=60)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        # Get the result file from the container
        copy_cmd = [
            'sudo', 'docker', 'cp',
            'netbox-docker-netbox-1:/tmp/fabric_update_result.json',
            '/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/k8s_sync_validation/04_evidence_collection/status_validation/fabric_direct_update_result.json'
        ]
        
        subprocess.run(copy_cmd, check=True)
        print("\n✅ Update result copied to evidence collection")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ ERROR: Command timed out")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ ERROR: Command failed: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == '__main__':
    success = update_fabric_via_container()
    print(f"\nUpdate {'succeeded' if success else 'failed'}")