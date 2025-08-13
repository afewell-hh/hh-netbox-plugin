#!/usr/bin/env python3
"""
Direct Fabric Update Script
Updates fabric ID 35 database record directly with K8s configuration
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

# Add the project directory to Python path
project_path = '/home/ubuntu/cc/hedgehog-netbox-plugin'
sys.path.insert(0, project_path)

try:
    django.setup()
    print("Django setup successful")
except Exception as e:
    print(f"Django setup failed: {e}")

try:
    # Direct database update using Django ORM
    from django.db import connection
    from django.utils import timezone
    
    cursor = connection.cursor()
    
    # Check current fabric state
    print("\n=== CURRENT FABRIC 35 STATE ===")
    cursor.execute("""
        SELECT 
            id, name, description, 
            kubernetes_server, kubernetes_namespace, kubernetes_token,
            sync_enabled, connection_status, sync_status,
            sync_error, connection_error
        FROM netbox_hedgehog_hedgehogfabric 
        WHERE id = 35
    """)
    
    row = cursor.fetchone()
    if row:
        print(f"ID: {row[0]}")
        print(f"Name: {row[1]}")
        print(f"Description: {row[2]}")
        print(f"K8s Server: {row[3] or 'NOT CONFIGURED'}")
        print(f"K8s Namespace: {row[4] or 'NOT CONFIGURED'}")
        print(f"K8s Token: {'SET' if row[5] else 'NOT SET'}")
        print(f"Sync Enabled: {row[6]}")
        print(f"Connection Status: {row[7]}")
        print(f"Sync Status: {row[8]}")
        print(f"Sync Error: {row[9] or 'None'}")
        print(f"Connection Error: {row[10] or 'None'}")
        
        # Update fabric with K8s configuration
        print("\n=== UPDATING FABRIC CONFIGURATION ===")
        
        k8s_server = 'https://vlab-art.l.hhdev.io:6443'
        k8s_namespace = 'default'
        k8s_token = 'test-token-placeholder'  # Will need real token
        
        cursor.execute("""
            UPDATE netbox_hedgehog_hedgehogfabric 
            SET 
                kubernetes_server = %s,
                kubernetes_namespace = %s,
                kubernetes_token = %s,
                sync_enabled = TRUE,
                sync_error = '',
                connection_error = '',
                last_change = %s
            WHERE id = 35
        """, [k8s_server, k8s_namespace, k8s_token, timezone.now()])
        
        print(f"✅ Updated fabric 35 with:")
        print(f"   Server: {k8s_server}")
        print(f"   Namespace: {k8s_namespace}")
        print(f"   Token: SET (placeholder)")
        print(f"   Sync Enabled: TRUE")
        
        # Verify update
        cursor.execute("""
            SELECT kubernetes_server, kubernetes_namespace, sync_enabled
            FROM netbox_hedgehog_hedgehogfabric 
            WHERE id = 35
        """)
        
        updated = cursor.fetchone()
        if updated:
            print(f"\n=== VERIFICATION ===")
            print(f"Server: {updated[0]}")
            print(f"Namespace: {updated[1]}")
            print(f"Sync Enabled: {updated[2]}")
            print("✅ Database update successful")
        
    else:
        print("❌ Fabric ID 35 not found!")
        
except Exception as e:
    print(f"Database operation failed: {e}")
    import traceback
    traceback.print_exc()

print("\n=== NEXT STEPS ===")
print("1. Get real service account token:")
print("   kubectl get secret hnp-sync-token -o jsonpath='{.data.token}' --server=https://vlab-art.l.hhdev.io:6443 --insecure-skip-tls-verify | base64 -d")
print("2. Update token in fabric record")
print("3. Test connectivity through NetBox GUI")
print("4. Verify fabric detail page shows K8s server")