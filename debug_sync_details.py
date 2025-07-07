#!/usr/bin/env python3
"""Debug sync process to see what's being fetched from Kubernetes"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
sys.path.append('/opt/netbox/netbox')
django.setup()

from netbox_hedgehog.models import HedgehogFabric
from netbox_hedgehog.utils.kubernetes import KubernetesSync

# Get first fabric
fabric = HedgehogFabric.objects.first()
if fabric:
    print(f"=== Debugging Sync for Fabric: {fabric.name} ===\n")
    
    sync = KubernetesSync(fabric)
    
    # First, let's see what CRD types are defined
    print("=== CRD Types Configured ===")
    for plural, info in sync.crd_types.items():
        print(f"{plural}: {info}")
    
    print("\n=== Fetching CRDs from Kubernetes ===")
    fetch_result = sync.fetch_crds_from_kubernetes()
    
    if fetch_result['success']:
        print("\nFetch successful!")
        print("\n=== CRDs Found by Type ===")
        for kind, resources in fetch_result['resources'].items():
            print(f"\n{kind}: {len(resources)} found")
            if resources:
                # Show first resource of each type
                first = resources[0]
                print(f"  Example: {first['metadata']['name']} (namespace: {first['metadata']['namespace']})")
    else:
        print(f"Fetch failed: {fetch_result['errors']}")
    
    # Check what's in the database
    print("\n=== Current Database State ===")
    from netbox_hedgehog.models import (
        Connection, Server, Switch, SwitchGroup, VLANNamespace, 
        IPv4Namespace, VPC
    )
    
    print(f"Connection: {Connection.objects.count()}")
    print(f"Server: {Server.objects.count()}")
    print(f"Switch: {Switch.objects.count()}")
    print(f"SwitchGroup: {SwitchGroup.objects.count()}")
    print(f"VLANNamespace: {VLANNamespace.objects.count()}")
    print(f"IPv4Namespace: {IPv4Namespace.objects.count()}")
    print(f"VPC: {VPC.objects.count()}")
else:
    print("No fabric found!")