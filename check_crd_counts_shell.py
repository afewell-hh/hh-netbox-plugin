from netbox_hedgehog.models import (
    Connection, Server, Switch, SwitchGroup, VLANNamespace,
    VPC, External, ExternalAttachment, ExternalPeering,
    IPv4Namespace, VPCAttachment, VPCPeering, HedgehogFabric
)

print("=== CRD Database Counts ===")
print("\n--- Wiring API CRDs ---")
print(f"Connection count: {Connection.objects.count()}")
print(f"Server count: {Server.objects.count()}")
print(f"Switch count: {Switch.objects.count()}")
print(f"SwitchGroup count: {SwitchGroup.objects.count()}")
print(f"VLANNamespace count: {VLANNamespace.objects.count()}")

print("\n--- VPC API CRDs ---")
print(f"VPC count: {VPC.objects.count()}")
print(f"External count: {External.objects.count()}")
print(f"ExternalAttachment count: {ExternalAttachment.objects.count()}")
print(f"ExternalPeering count: {ExternalPeering.objects.count()}")
print(f"IPv4Namespace count: {IPv4Namespace.objects.count()}")
print(f"VPCAttachment count: {VPCAttachment.objects.count()}")
print(f"VPCPeering count: {VPCPeering.objects.count()}")

print(f"\n--- Fabrics ---")
print(f"HedgehogFabric count: {HedgehogFabric.objects.count()}")

# Check if any fabric has CRD counts
for fabric in HedgehogFabric.objects.all():
    print(f"\nFabric '{fabric.name}':")
    print(f"  - connections_count: {fabric.connections_count}")
    print(f"  - servers_count: {fabric.servers_count}")
    print(f"  - switches_count: {fabric.switches_count}")
    print(f"  - vpcs_count: {fabric.vpcs_count}")