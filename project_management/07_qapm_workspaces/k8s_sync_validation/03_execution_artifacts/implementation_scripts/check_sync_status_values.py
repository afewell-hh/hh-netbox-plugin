#!/usr/bin/env python3
"""
Check what sync_status values are valid in the database
"""

import subprocess

def check_valid_sync_status():
    """Check valid sync_status values in the database"""
    
    print("=== CHECKING VALID SYNC_STATUS VALUES ===")
    
    # Create a Django shell script to check the constraint
    django_script = '''
from netbox_hedgehog.models import HedgehogFabric
from django.db import connection

try:
    # Get the current fabric to see its sync_status
    fabric = HedgehogFabric.objects.get(id=26)
    print(f"Current sync_status: {fabric.sync_status}")
    
    # Try to get constraint info from the database
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT constraint_name, check_clause 
            FROM information_schema.check_constraints 
            WHERE constraint_name LIKE '%sync_status%'
        """)
        constraints = cursor.fetchall()
        
        print("\\nSync status constraints:")
        for constraint in constraints:
            print(f"  {constraint[0]}: {constraint[1]}")
    
    # Let's just try updating without changing sync_status
    print(f"\\nTrying to update without changing sync_status...")
    fabric.kubernetes_server = "https://172.18.0.8:6443"
    # Don't change sync_status - keep current value
    fabric.save()
    
    print("✅ SUCCESS - Fabric updated with K8s server only")
    
    # Save result
    result = {
        "success": True,
        "kubernetes_server": fabric.kubernetes_server,
        "sync_status": fabric.sync_status
    }
    
    import json
    with open('/tmp/sync_status_check.json', 'w') as f:
        json.dump(result, f, indent=2)
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    result = {"success": False, "error": str(e)}
    import json
    with open('/tmp/sync_status_check.json', 'w') as f:
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
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == '__main__':
    success = check_valid_sync_status()
    print(f"\nCheck {'succeeded' if success else 'failed'}")