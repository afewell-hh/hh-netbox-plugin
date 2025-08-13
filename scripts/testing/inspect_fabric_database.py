#!/usr/bin/env python3
"""
Real production validation script to inspect fabric database state
"""

import os
import sys
import django
from datetime import datetime, timezone

# Add the project directory to Python path
sys.path.insert(0, '/opt/netbox')

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

def inspect_fabric_database():
    """Inspect actual fabric database records"""
    try:
        from netbox_hedgehog.models import Fabric
        
        print("=== FABRIC DATABASE INSPECTION ===")
        print(f"Inspection time: {datetime.now()}")
        print()
        
        # Get all fabrics
        fabrics = Fabric.objects.all()
        print(f"Total fabrics found: {fabrics.count()}")
        print()
        
        if fabrics.count() == 0:
            print("❌ NO FABRICS FOUND - This explains why periodic sync has no targets")
            return
        
        for fabric in fabrics:
            print(f"Fabric ID: {fabric.id}")
            print(f"Name: {fabric.name}")
            print(f"Description: {fabric.description}")
            
            # Check sync-related fields
            print("\n--- SYNC CONFIGURATION ---")
            print(f"sync_enabled: {getattr(fabric, 'sync_enabled', 'FIELD NOT FOUND')}")
            print(f"sync_interval: {getattr(fabric, 'sync_interval', 'FIELD NOT FOUND')}")
            print(f"last_sync: {getattr(fabric, 'last_sync', 'FIELD NOT FOUND')}")
            print(f"next_sync: {getattr(fabric, 'next_sync', 'FIELD NOT FOUND')}")
            print(f"scheduler_enabled: {getattr(fabric, 'scheduler_enabled', 'FIELD NOT FOUND')}")
            
            # Check K8s config
            print("\n--- K8S CONFIGURATION ---")
            print(f"k8s_cluster_name: {getattr(fabric, 'k8s_cluster_name', 'FIELD NOT FOUND')}")
            print(f"k8s_namespace: {getattr(fabric, 'k8s_namespace', 'FIELD NOT FOUND')}")
            print(f"k8s_config_path: {getattr(fabric, 'k8s_config_path', 'FIELD NOT FOUND')}")
            print(f"k8s_token: {getattr(fabric, 'k8s_token', 'FIELD NOT FOUND') != None}")
            
            # Check all fields
            print("\n--- ALL FIELDS ---")
            for field in fabric._meta.get_fields():
                try:
                    value = getattr(fabric, field.name)
                    print(f"{field.name}: {value}")
                except Exception as e:
                    print(f"{field.name}: ERROR - {e}")
            
            print("\n" + "="*60 + "\n")
    
    except ImportError as e:
        print(f"❌ IMPORT ERROR: {e}")
        print("The netbox_hedgehog plugin may not be properly installed or configured")
    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        print("Could not connect to database or query fabric records")

def check_database_tables():
    """Check if the expected database tables exist"""
    from django.db import connection
    
    print("=== DATABASE TABLES CHECK ===")
    cursor = connection.cursor()
    
    # Check if hedgehog tables exist
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%hedgehog%'
        ORDER BY table_name;
    """)
    
    tables = cursor.fetchall()
    print(f"Hedgehog-related tables found: {len(tables)}")
    
    for table in tables:
        print(f"  - {table[0]}")
        
        # Get table structure
        cursor.execute(f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = '{table[0]}'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        print(f"    Columns ({len(columns)}):")
        for col in columns:
            print(f"      {col[0]} ({col[1]}) - nullable: {col[2]}, default: {col[3]}")
        print()

if __name__ == '__main__':
    print("Starting real production database validation...")
    print("=" * 60)
    
    check_database_tables()
    print()
    inspect_fabric_database()