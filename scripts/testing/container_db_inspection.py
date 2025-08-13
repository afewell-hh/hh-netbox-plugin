#!/usr/bin/env python3
"""
Database inspection script to run inside NetBox container
"""

print("=== HEDGEHOG PLUGIN DATABASE INSPECTION ===")

try:
    # Check if plugin is loaded
    from netbox_hedgehog.models import Fabric
    print("✅ netbox_hedgehog plugin imported successfully")
    
    # Get fabric count
    fabric_count = Fabric.objects.count()
    print(f"📊 Total fabrics in database: {fabric_count}")
    
    if fabric_count == 0:
        print("❌ ISSUE FOUND: No fabrics exist - periodic sync has no targets!")
    
    # Get all fabrics and inspect their sync settings
    for fabric in Fabric.objects.all():
        print(f"\n🔍 Fabric: {fabric.name} (ID: {fabric.id})")
        
        # Check for sync-related fields
        fields_to_check = [
            'sync_enabled', 'sync_interval', 'last_sync', 'next_sync', 
            'scheduler_enabled', 'k8s_cluster_name', 'k8s_namespace', 
            'k8s_config_path', 'k8s_token'
        ]
        
        print("   Sync Configuration:")
        for field_name in fields_to_check:
            if hasattr(fabric, field_name):
                value = getattr(fabric, field_name, None)
                if field_name == 'k8s_token' and value:
                    value = "[SET]"
                print(f"     {field_name}: {value}")
            else:
                print(f"     {field_name}: FIELD_NOT_FOUND")
        
        # Check the actual database columns
        print(f"   All Database Fields:")
        for field in fabric._meta.get_fields():
            try:
                value = getattr(fabric, field.name)
                if 'token' in field.name.lower() and value:
                    value = "[REDACTED]"
                print(f"     {field.name}: {value}")
            except Exception as e:
                print(f"     {field.name}: ERROR - {e}")

except ImportError as e:
    print(f"❌ PLUGIN NOT LOADED: {e}")
    print("The hedgehog plugin is not properly installed or enabled")

except Exception as e:
    print(f"❌ DATABASE ERROR: {e}")
    
# Check if task system is working
print("\n=== TASK SYSTEM CHECK ===")
try:
    import django_rq
    queue = django_rq.get_queue('default')
    print(f"✅ RQ Queue accessible: {len(queue)} jobs")
    
    # Check Redis connection
    import redis
    from django.conf import settings
    
    # Try to connect to Redis
    if hasattr(settings, 'RQ_QUEUES'):
        print(f"✅ RQ configuration found: {len(settings.RQ_QUEUES)} queues")
    else:
        print("❌ No RQ configuration found")
        
except Exception as e:
    print(f"❌ TASK SYSTEM ERROR: {e}")

print("\n=== PLUGIN INSTALLATION CHECK ===")
try:
    from django.conf import settings
    installed_apps = getattr(settings, 'INSTALLED_APPS', [])
    
    hedgehog_apps = [app for app in installed_apps if 'hedgehog' in app.lower()]
    
    if hedgehog_apps:
        print(f"✅ Hedgehog apps found: {hedgehog_apps}")
    else:
        print("❌ No hedgehog apps in INSTALLED_APPS")
        
    # Check plugins configuration
    if hasattr(settings, 'PLUGINS'):
        plugins = getattr(settings, 'PLUGINS', [])
        hedgehog_plugins = [p for p in plugins if 'hedgehog' in p.lower()]
        
        if hedgehog_plugins:
            print(f"✅ Hedgehog plugins configured: {hedgehog_plugins}")
        else:
            print("❌ No hedgehog plugins in PLUGINS configuration")
    
except Exception as e:
    print(f"❌ PLUGIN CHECK ERROR: {e}")