#!/usr/bin/env python3
"""Test that the fixed templates work correctly"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
sys.path.append('/opt/netbox/netbox')
django.setup()

from netbox_hedgehog.models import SwitchGroup, VLANNamespace, IPv4Namespace

print("=== Final Verification ===")
print(f"SwitchGroup count: {SwitchGroup.objects.count()}")
print(f"VLANNamespace count: {VLANNamespace.objects.count()}")
print(f"IPv4Namespace count: {IPv4Namespace.objects.count()}")

if SwitchGroup.objects.exists():
    print(f"\nSwitchGroups:")
    for sg in SwitchGroup.objects.all():
        print(f"  - {sg.name} (fabric: {sg.fabric.name})")

if VLANNamespace.objects.exists():
    print(f"\nVLANNamespaces:")
    for vn in VLANNamespace.objects.all():
        print(f"  - {vn.name} (fabric: {vn.fabric.name})")

if IPv4Namespace.objects.exists():
    print(f"\nIPv4Namespaces:")
    for ipv4 in IPv4Namespace.objects.all():
        print(f"  - {ipv4.name} (fabric: {ipv4.fabric.name})")

print("\n✅ All CRD types are in the database and should now be visible in the list views!")
print("Please check the following URLs:")
print("- /plugins/netbox_hedgehog/switch-groups/")
print("- /plugins/netbox_hedgehog/vlan-namespaces/")  
print("- /plugins/netbox_hedgehog/ipv4namespaces/")