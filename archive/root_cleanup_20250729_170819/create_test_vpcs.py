#!/usr/bin/env python3
"""
Simple script to create test VPC objects to debug the dashboard count issue.
This should be run in the NetBox environment.
"""

import os
import sys
import django

# Add the plugin directory to Python path
sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

try:
    import django
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    print("This script needs to run in a NetBox environment")
    sys.exit(1)

def create_test_vpcs():
    """Create test VPC objects for debugging"""
    print("=== Creating Test VPCs ===")
    
    try:
        from netbox_hedgehog.models import HedgehogFabric, VPC
        
        # First ensure we have a fabric
        fabric, created = HedgehogFabric.objects.get_or_create(
            name='test-fabric',
            defaults={
                'description': 'Test fabric for VPC debugging',
                'status': 'active',
                'kubernetes_namespace': 'hedgehog-test',
            }
        )
        
        if created:
            print(f"Created test fabric: {fabric.name}")
        else:
            print(f"Using existing fabric: {fabric.name}")
        
        # Create test VPCs if they don't exist
        test_vpcs = [
            {
                'name': 'test-vpc-1',
                'spec': {'subnet': '10.1.0.0/24'},
                'namespace': 'default'
            },
            {
                'name': 'test-vpc-2', 
                'spec': {'subnet': '10.2.0.0/24'},
                'namespace': 'default'
            }
        ]
        
        for vpc_data in test_vpcs:
            vpc, created = VPC.objects.get_or_create(
                name=vpc_data['name'],
                fabric=fabric,
                defaults={
                    'spec': vpc_data['spec'],
                    'namespace': vpc_data['namespace'],
                    'kubernetes_status': 'pending'
                }
            )
            
            if created:
                print(f"Created VPC: {vpc.name}")
            else:
                print(f"VPC already exists: {vpc.name}")
        
        # Verify count
        total_vpcs = VPC.objects.count()
        print(f"\nTotal VPCs in database: {total_vpcs}")
        
        for vpc in VPC.objects.all():
            print(f"  - VPC {vpc.id}: {vpc.name} (Fabric: {vpc.fabric.name})")
        
    except Exception as e:
        print(f"Error creating test VPCs: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_test_vpcs()