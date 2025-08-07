#!/usr/bin/env python3
"""
Trigger K8s synchronization via Django management interface
"""

import os
import json
import subprocess
import time

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

def trigger_k8s_sync_via_django():
    """Trigger K8s synchronization via Django interface"""
    fabric_id = 26
    
    print("=== TRIGGERING K8S SYNCHRONIZATION VIA DJANGO ===")
    
    # Create a Django shell script to manually trigger sync
    django_script = f'''
from netbox_hedgehog.models import HedgehogFabric
from netbox_hedgehog.synchronization import KubernetesSynchronizer
import json
import traceback
from datetime import datetime

try:
    print("Getting fabric...")
    fabric = HedgehogFabric.objects.get(id={fabric_id})
    print(f"Found fabric: {{fabric.name}}")
    
    print("\\nChecking K8s configuration...")
    print(f"  kubernetes_server: {{fabric.kubernetes_server}}")
    print(f"  kubernetes_token: {{'SET' if fabric.kubernetes_token else 'EMPTY'}}")
    print(f"  kubernetes_ca_cert: {{'SET' if fabric.kubernetes_ca_cert else 'EMPTY'}}")
    print(f"  kubernetes_namespace: {{fabric.kubernetes_namespace}}")
    
    # Initialize the Kubernetes synchronizer
    print("\\nInitializing Kubernetes synchronizer...")
    k8s_sync = KubernetesSynchronizer(fabric)
    
    # Test connection first
    print("\\nTesting Kubernetes connection...")
    connection_result = k8s_sync.test_connection()
    print(f"Connection test result: {{connection_result}}")
    
    if connection_result.get('success', False):
        print("✅ Kubernetes connection successful")
        
        # Update fabric connection status
        fabric.connection_status = 'connected'
        fabric.connection_error = ''
        
        # Attempt synchronization
        print("\\nAttempting Kubernetes synchronization...")
        sync_result = k8s_sync.sync_from_kubernetes()
        print(f"Sync result: {{sync_result}}")
        
        if sync_result.get('success', False):
            print("✅ Kubernetes synchronization successful")
            fabric.sync_status = 'synced'
            fabric.sync_error = ''
            fabric.last_sync = datetime.now()
            
            # Update CRD counts if available
            if 'crd_counts' in sync_result:
                counts = sync_result['crd_counts']
                fabric.cached_crd_count = counts.get('total', 0)
                fabric.cached_vpc_count = counts.get('vpcs', 0) 
                fabric.cached_connection_count = counts.get('connections', 0)
                fabric.vpcs_count = counts.get('vpcs', 0)
                fabric.connections_count = counts.get('connections', 0)
                fabric.switches_count = counts.get('switches', 0)
                fabric.servers_count = counts.get('servers', 0)
                
            fabric.save()
            print("✅ Fabric state updated successfully")
            
        else:
            print("❌ Kubernetes synchronization failed")
            fabric.sync_status = 'error'
            fabric.sync_error = sync_result.get('error', 'Unknown sync error')
            fabric.save()
            
    else:
        print("❌ Kubernetes connection failed")
        fabric.connection_status = 'error'
        fabric.connection_error = connection_result.get('error', 'Unknown connection error')
        fabric.save()
    
    # Export final state
    fabric.refresh_from_db()
    result = {{
        "fabric_id": fabric.id,
        "fabric_name": fabric.name,
        "connection_status": fabric.connection_status,
        "connection_error": fabric.connection_error,
        "sync_status": fabric.sync_status,
        "sync_error": fabric.sync_error,
        "last_sync": fabric.last_sync.isoformat() if fabric.last_sync else None,
        "cached_crd_count": fabric.cached_crd_count,
        "cached_vpc_count": fabric.cached_vpc_count,
        "cached_connection_count": fabric.cached_connection_count,
        "vpcs_count": fabric.vpcs_count,
        "connections_count": fabric.connections_count,
        "switches_count": fabric.switches_count,
        "servers_count": fabric.servers_count,
        "drift_status": fabric.drift_status,
        "timestamp": datetime.now().isoformat()
    }}
    
    with open('/tmp/k8s_sync_result.json', 'w') as f:
        json.dump(result, f, indent=2)
        
    print("\\n=== FINAL FABRIC STATE ===")
    print(f"Connection Status: {{fabric.connection_status}}")
    print(f"Sync Status: {{fabric.sync_status}}")
    print(f"Last Sync: {{fabric.last_sync}}")
    print(f"CRD Count: {{fabric.cached_crd_count}}")
    print(f"Drift Status: {{fabric.drift_status}}")
        
except Exception as e:
    print(f"❌ ERROR: {{e}}")
    traceback.print_exc()
    
    result = {{
        "error": str(e),
        "traceback": traceback.format_exc(),
        "timestamp": datetime.now().isoformat()
    }}
    
    with open('/tmp/k8s_sync_result.json', 'w') as f:
        json.dump(result, f, indent=2)
'''
    
    try:
        # Execute the Django shell script in the NetBox container
        cmd = [
            'sudo', 'docker', 'exec', '-i', 'netbox-docker-netbox-1',
            'python', '/opt/netbox/netbox/manage.py', 'shell'
        ]
        
        print("Executing K8s sync script in NetBox container...")
        result = subprocess.run(cmd, input=django_script, text=True, 
                              capture_output=True, timeout=180)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        # Copy the result file from the container
        os.makedirs('/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/k8s_sync_validation/04_evidence_collection/test_results', exist_ok=True)
        
        copy_cmd = [
            'sudo', 'docker', 'cp',
            'netbox-docker-netbox-1:/tmp/k8s_sync_result.json',
            '/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/k8s_sync_validation/04_evidence_collection/test_results/k8s_sync_django_result.json'
        ]
        
        subprocess.run(copy_cmd, check=True)
        print("\n✅ Sync result copied to evidence collection")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ ERROR: Command timed out")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == '__main__':
    success = trigger_k8s_sync_via_django()
    print(f"\nK8s sync via Django {'succeeded' if success else 'failed'}")