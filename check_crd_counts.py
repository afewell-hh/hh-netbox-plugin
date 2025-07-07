#!/usr/bin/env python3
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netbox.settings")

# Find the netbox directory
netbox_dir = None
for path in sys.path:
    if 'netbox' in path and os.path.exists(os.path.join(path, 'netbox', 'settings.py')):
        netbox_dir = path
        break

if netbox_dir:
    sys.path.insert(0, netbox_dir)

django.setup()

from netbox_hedgehog.models import (
    Connection, Server, Switch, VPC, ConnectivityProfile,
    IPPool, IPPrefix, BGPProfile, Interface, StaticRoute,
    VRF, ServerProfile
)

print("=== CRD Database Counts ===")
print(f"Connection count: {Connection.objects.count()}")
print(f"Server count: {Server.objects.count()}")
print(f"Switch count: {Switch.objects.count()}")
print(f"VPC count: {VPC.objects.count()}")
print(f"ConnectivityProfile count: {ConnectivityProfile.objects.count()}")
print(f"IPPool count: {IPPool.objects.count()}")
print(f"IPPrefix count: {IPPrefix.objects.count()}")
print(f"BGPProfile count: {BGPProfile.objects.count()}")
print(f"Interface count: {Interface.objects.count()}")
print(f"StaticRoute count: {StaticRoute.objects.count()}")
print(f"VRF count: {VRF.objects.count()}")
print(f"ServerProfile count: {ServerProfile.objects.count()}")

# Check fabrics too
from netbox_hedgehog.models import HedgehogFabric
print(f"\nHedgehogFabric count: {HedgehogFabric.objects.count()}")

# Check if any fabric has CRD counts
for fabric in HedgehogFabric.objects.all():
    print(f"\nFabric '{fabric.name}':")
    print(f"  - connections_count: {fabric.connections_count}")
    print(f"  - servers_count: {fabric.servers_count}")
    print(f"  - switches_count: {fabric.switches_count}")
    print(f"  - vpcs_count: {fabric.vpcs_count}")