from netbox_hedgehog.models import (
    SwitchGroup, VLANNamespace, IPv4Namespace,
    Connection, Server, Switch
)

print("=== Database CRD Counts ===")
print(f"Connection count: {Connection.objects.count()}")
print(f"Server count: {Server.objects.count()}")
print(f"Switch count: {Switch.objects.count()}")
print(f"SwitchGroup count: {SwitchGroup.objects.count()}")
print(f"VLANNamespace count: {VLANNamespace.objects.count()}")
print(f"IPv4Namespace count: {IPv4Namespace.objects.count()}")

print("\n=== SwitchGroup Details ===")
for sg in SwitchGroup.objects.all():
    print(f"- {sg.name} (namespace: {sg.namespace}, fabric: {sg.fabric})")

print("\n=== VLANNamespace Details ===")
for vn in VLANNamespace.objects.all():
    print(f"- {vn.name} (namespace: {vn.namespace}, fabric: {vn.fabric})")

print("\n=== IPv4Namespace Details ===")
for ipv4 in IPv4Namespace.objects.all():
    print(f"- {ipv4.name} (namespace: {ipv4.namespace}, fabric: {ipv4.fabric})")