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

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from netbox_hedgehog.views.wiring_api import ConnectionListView
from netbox_hedgehog.models import Connection

# Create a request factory
factory = RequestFactory()

# Create a GET request
request = factory.get('/plugins/netbox_hedgehog/connections/')
request.user = AnonymousUser()

# Create the view instance
view = ConnectionListView()
view.request = request

# Get the queryset
queryset = view.get_queryset()
print(f"ConnectionListView queryset count: {queryset.count()}")
print(f"Direct Connection.objects.all() count: {Connection.objects.count()}")

# Check if there's any filtering happening
if hasattr(view, 'filterset_class') and view.filterset_class:
    print(f"View has filterset_class: {view.filterset_class}")

# Get the table
table = view.get_table()
print(f"Table type: {type(table)}")
print(f"Table rows count: {len(list(table.rows))}")

# Check first few connections
for conn in Connection.objects.all()[:3]:
    print(f"\nConnection: {conn.name}")
    print(f"  Fabric: {conn.fabric}")
    print(f"  Namespace: {conn.namespace}")
    print(f"  Status: {conn.kubernetes_status}")