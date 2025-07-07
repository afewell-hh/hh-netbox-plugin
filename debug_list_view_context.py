#!/usr/bin/env python3
"""Test the list view context to see what's being passed to templates"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
sys.path.append('/opt/netbox/netbox')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from netbox_hedgehog.views.wiring_api import SwitchGroupListView, VLANNamespaceListView
from netbox_hedgehog.views.vpc_api import IPv4NamespaceListView
from netbox_hedgehog.models import SwitchGroup, VLANNamespace, IPv4Namespace

print("=== Testing List View Context ===")

# Create a request
factory = RequestFactory()
request = factory.get('/')
try:
    request.user = User.objects.first() or User.objects.create_user('test')
except:
    pass

print(f"\nDatabase counts:")
print(f"SwitchGroup: {SwitchGroup.objects.count()}")
print(f"VLANNamespace: {VLANNamespace.objects.count()}")
print(f"IPv4Namespace: {IPv4Namespace.objects.count()}")

# Test SwitchGroupListView
print(f"\n=== SwitchGroupListView ===")
view = SwitchGroupListView()
view.setup(request)
view.object_list = view.get_queryset()
context = view.get_context_data(object_list=view.object_list)
print(f"object_list count: {len(context.get('object_list', []))}")
print(f"switchgroups count: {len(context.get('switchgroups', []))}")
print(f"Available context keys: {list(context.keys())}")

# Test VLANNamespaceListView
print(f"\n=== VLANNamespaceListView ===")
view = VLANNamespaceListView()
view.setup(request)
view.object_list = view.get_queryset()
context = view.get_context_data(object_list=view.object_list)
print(f"object_list count: {len(context.get('object_list', []))}")
print(f"vlannamespaces count: {len(context.get('vlannamespaces', []))}")
print(f"Available context keys: {list(context.keys())}")

# Test IPv4NamespaceListView
print(f"\n=== IPv4NamespaceListView ===")
view = IPv4NamespaceListView()
view.setup(request)
view.object_list = view.get_queryset()
context = view.get_context_data(object_list=view.object_list)
print(f"object_list count: {len(context.get('object_list', []))}")
print(f"ipv4namespaces count: {len(context.get('ipv4namespaces', []))}")
print(f"Available context keys: {list(context.keys())}")

# Show some actual objects
print(f"\n=== Sample Objects ===")
for sg in SwitchGroup.objects.all()[:2]:
    print(f"SwitchGroup: {sg.name} (fabric: {sg.fabric})")

for vn in VLANNamespace.objects.all()[:2]:
    print(f"VLANNamespace: {vn.name} (fabric: {vn.fabric})")

for ipv4 in IPv4Namespace.objects.all()[:2]:
    print(f"IPv4Namespace: {ipv4.name} (fabric: {ipv4.fabric})")