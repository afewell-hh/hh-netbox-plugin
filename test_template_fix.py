#!/usr/bin/env python3
"""
Test script to verify template fixes are working
"""
import subprocess
import sys

def run_docker_cmd(cmd):
    """Run a command in the Docker container"""
    full_cmd = f"sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py shell -c \"{cmd}\""
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    return result.stdout

print("🔍 Testing Template Fixes")
print("=" * 50)

# Test 1: Check fabric CRD count
cmd1 = """
from netbox_hedgehog.models import HedgehogFabric
fabric = HedgehogFabric.objects.first()
print(f'Fabric ID: {fabric.pk}')
print(f'Fabric Name: {fabric.name}')
print(f'CRD Count: {fabric.crd_count}')
print(f'Should View CRDs button be enabled: {fabric.crd_count > 0}')
"""
print("1. Fabric CRD Count:")
output1 = run_docker_cmd(cmd1)
print(output1)

# Test 2: Check connection count
cmd2 = """
from netbox_hedgehog.models import Connection
total_connections = Connection.objects.count()
print(f'Total connections in database: {total_connections}')
"""
print("2. Connection Count:")
output2 = run_docker_cmd(cmd2)
print(output2)

# Test 3: Check template files exist and have correct content
print("3. Template File Verification:")
result = subprocess.run([
    "sudo", "docker", "exec", "netbox-docker-netbox-1", 
    "grep", "-c", "object.crd_count > 0", 
    "/opt/netbox/netbox/netbox_hedgehog/templates/netbox_hedgehog/fabric_detail.html"
], capture_output=True, text=True)

if result.returncode == 0:
    print(f"✅ fabric_detail.html contains 'object.crd_count > 0': {result.stdout.strip()} occurrences")
else:
    print("❌ fabric_detail.html does not contain the expected content")

result2 = subprocess.run([
    "sudo", "docker", "exec", "netbox-docker-netbox-1", 
    "grep", "-c", "object_list", 
    "/opt/netbox/netbox/netbox_hedgehog/templates/netbox_hedgehog/connection_list.html"
], capture_output=True, text=True)

if result2.returncode == 0:
    print(f"✅ connection_list.html contains 'object_list': {result2.stdout.strip()} occurrences")
else:
    print("❌ connection_list.html does not contain the expected content")

print("\n🎯 TROUBLESHOOTING STEPS FOR USER:")
print("=" * 50)
print("1. Clear your browser cache (Ctrl+F5 or Cmd+Shift+R)")
print("2. Try opening NetBox in an incognito/private browser window")
print("3. Navigate to: http://localhost:8000/plugins/hedgehog/fabrics/2/")
print("4. The 'View CRDs' button should show 'View CRDs (49)' and be clickable")
print("5. Navigate to: http://localhost:8000/plugins/hedgehog/connections/")
print("6. You should see 26 connections listed")
print("\nIf issues persist, the problem may be browser caching or Django template caching.")