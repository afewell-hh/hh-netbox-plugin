from netbox_hedgehog.models import HedgehogFabric

# Get first fabric
fabric = HedgehogFabric.objects.first()
if fabric:
    print(f"Fabric: {fabric.name}")
    print(f"CRD Count (property): {fabric.crd_count}")
    print(f"Active CRD Count: {fabric.active_crd_count}")
    print(f"Error CRD Count: {fabric.error_crd_count}")
    print(f"Cached CRD Count: {fabric.cached_crd_count}")
    
    # Also check individual counts
    from netbox_hedgehog.models import Connection, Server, Switch, VPC
    print(f"\nDirect counts:")
    print(f"Connections: {Connection.objects.filter(fabric=fabric).count()}")
    print(f"Servers: {Server.objects.filter(fabric=fabric).count()}")
    print(f"Switches: {Switch.objects.filter(fabric=fabric).count()}")
    print(f"VPCs: {VPC.objects.filter(fabric=fabric).count()}")
else:
    print("No fabric found!")