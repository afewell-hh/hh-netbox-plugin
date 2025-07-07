from netbox_hedgehog.models import HedgehogFabric
from netbox_hedgehog.utils.kubernetes import KubernetesSync

# Get first fabric
fabric = HedgehogFabric.objects.first()
if fabric:
    print(f"Triggering sync for fabric: {fabric.name}")
    sync = KubernetesSync(fabric)
    result = sync.sync_all_crds()
    print(f"Sync result: {result}")
    
    # Refresh from DB to get updated counts
    fabric.refresh_from_db()
    print(f"\nUpdated counts:")
    print(f"  connections_count: {fabric.connections_count}")
    print(f"  servers_count: {fabric.servers_count}")
    print(f"  switches_count: {fabric.switches_count}")
    print(f"  vpcs_count: {fabric.vpcs_count}")
    print(f"  crd_count (property): {fabric.crd_count}")
else:
    print("No fabric found!")