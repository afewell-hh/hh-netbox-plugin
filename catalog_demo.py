#!/usr/bin/env python3
"""
Self-Service Catalog Demo for Hedgehog Fabric Management
A simple web interface to demonstrate the catalog functionality.
"""

import json
import time
from datetime import datetime
from kubernetes import client, config
from kubernetes.client.rest import ApiException

def load_k8s_client():
    """Load Kubernetes client"""
    try:
        config.load_kube_config()
        return client.CustomObjectsApi()
    except Exception as e:
        print(f"Failed to load Kubernetes config: {e}")
        return None

def get_cluster_inventory():
    """Get current cluster inventory"""
    custom_api = load_k8s_client()
    if not custom_api:
        return None
    
    inventory = {
        'switches': [],
        'connections': [],
        'vpcs': [],
        'ipv4_namespaces': [],
        'vlan_namespaces': []
    }
    
    try:
        # Get switches
        switches = custom_api.list_namespaced_custom_object(
            group='wiring.githedgehog.com',
            version='v1beta1',
            namespace='default',
            plural='switches'
        )
        
        for switch in switches.get('items', []):
            inventory['switches'].append({
                'name': switch['metadata']['name'],
                'role': switch['spec'].get('role', 'Unknown'),
                'asn': switch['spec'].get('asn', 'Unknown'),
                'description': switch['spec'].get('description', ''),
                'ip': switch['spec'].get('ip', ''),
                'status': 'Active'
            })
        
        # Get connections
        connections = custom_api.list_namespaced_custom_object(
            group='wiring.githedgehog.com',
            version='v1beta1',
            namespace='default',
            plural='connections'
        )
        
        for conn in connections.get('items', []):
            inventory['connections'].append({
                'name': conn['metadata']['name'],
                'type': conn['spec'].get('type', 'Unknown'),
                'status': 'Active'
            })
        
        # Get VPCs
        vpcs = custom_api.list_namespaced_custom_object(
            group='vpc.githedgehog.com',
            version='v1beta1',
            namespace='default',
            plural='vpcs'
        )
        
        for vpc in vpcs.get('items', []):
            subnets = vpc['spec'].get('subnets', {})
            inventory['vpcs'].append({
                'name': vpc['metadata']['name'],
                'ipv4_namespace': vpc['spec'].get('ipv4Namespace', ''),
                'vlan_namespace': vpc['spec'].get('vlanNamespace', ''),
                'subnet_count': len(subnets),
                'subnets': list(subnets.keys()),
                'created': vpc['metadata'].get('creationTimestamp', ''),
                'status': 'Active'
            })
        
        # Get IPv4 Namespaces
        ipv4ns = custom_api.list_namespaced_custom_object(
            group='vpc.githedgehog.com',
            version='v1beta1',
            namespace='default',
            plural='ipv4namespaces'
        )
        
        for ns in ipv4ns.get('items', []):
            inventory['ipv4_namespaces'].append({
                'name': ns['metadata']['name'],
                'subnets': ns['spec'].get('subnets', []),
                'status': 'Active'
            })
        
        # Get VLAN Namespaces
        vlanns = custom_api.list_namespaced_custom_object(
            group='wiring.githedgehog.com',
            version='v1beta1',
            namespace='default',
            plural='vlannamespaces'
        )
        
        for ns in vlanns.get('items', []):
            ranges = ns['spec'].get('ranges', [])
            inventory['vlan_namespaces'].append({
                'name': ns['metadata']['name'],
                'ranges': ranges,
                'status': 'Active'
            })
        
        return inventory
        
    except Exception as e:
        print(f"Error getting inventory: {e}")
        return None

def create_vpc_from_template(name, template_type="basic"):
    """Create a VPC from a template"""
    custom_api = load_k8s_client()
    if not custom_api:
        return False, "Failed to connect to cluster"
    
    # Validate name length
    if len(name) > 11:
        return False, f"VPC name '{name}' too long (max 11 characters)"
    
    # Get next available VLAN IDs
    next_vlan = 1200  # Start from 1200 to avoid conflicts
    
    templates = {
        "basic": {
            "description": "Basic single-subnet VPC",
            "subnets": {
                "main": {
                    "subnet": "10.0.10.0/24",
                    "gateway": "10.0.10.1",
                    "vlan": next_vlan,
                    "dhcp": {"enable": True}
                }
            }
        },
        "web-db": {
            "description": "Web and database tier VPC",
            "subnets": {
                "web": {
                    "subnet": "10.0.20.0/24",
                    "gateway": "10.0.20.1",
                    "vlan": next_vlan,
                    "dhcp": {"enable": True}
                },
                "db": {
                    "subnet": "10.0.21.0/24",
                    "gateway": "10.0.21.1",
                    "vlan": next_vlan + 1,
                    "dhcp": {"enable": True}
                }
            }
        },
        "three-tier": {
            "description": "Three-tier application VPC",
            "subnets": {
                "web": {
                    "subnet": "10.0.30.0/24",
                    "gateway": "10.0.30.1",
                    "vlan": next_vlan,
                    "dhcp": {"enable": True}
                },
                "app": {
                    "subnet": "10.0.31.0/24",
                    "gateway": "10.0.31.1",
                    "vlan": next_vlan + 1,
                    "dhcp": {"enable": True}
                },
                "db": {
                    "subnet": "10.0.32.0/24",
                    "gateway": "10.0.32.1",
                    "vlan": next_vlan + 2,
                    "dhcp": {"enable": True}
                }
            }
        }
    }
    
    template = templates.get(template_type)
    if not template:
        return False, f"Template '{template_type}' not found"
    
    vpc_manifest = {
        "apiVersion": "vpc.githedgehog.com/v1beta1",
        "kind": "VPC",
        "metadata": {
            "name": name,
            "namespace": "default",
            "labels": {
                "source": "netbox-hedgehog-plugin",
                "template": template_type,
                "created-by": "catalog-demo"
            },
            "annotations": {
                "description": template["description"]
            }
        },
        "spec": {
            "ipv4Namespace": "default",
            "vlanNamespace": "default",
            "subnets": template["subnets"]
        }
    }
    
    try:
        result = custom_api.create_namespaced_custom_object(
            group="vpc.githedgehog.com",
            version="v1beta1",
            namespace="default",
            plural="vpcs",
            body=vpc_manifest
        )
        
        return True, f"VPC '{name}' created successfully with {len(template['subnets'])} subnets"
        
    except ApiException as e:
        if e.status == 409:
            return False, f"VPC '{name}' already exists"
        else:
            return False, f"Failed to create VPC: {e.reason}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

def delete_vpc(name):
    """Delete a VPC"""
    custom_api = load_k8s_client()
    if not custom_api:
        return False, "Failed to connect to cluster"
    
    try:
        custom_api.delete_namespaced_custom_object(
            group="vpc.githedgehog.com",
            version="v1beta1",
            namespace="default",
            plural="vpcs",
            name=name
        )
        
        return True, f"VPC '{name}' deletion initiated"
        
    except ApiException as e:
        if e.status == 404:
            return False, f"VPC '{name}' not found"
        else:
            return False, f"Failed to delete VPC: {e.reason}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

def print_catalog_interface():
    """Print a simple catalog interface"""
    print("🏗️  Hedgehog Fabric Self-Service Catalog")
    print("=" * 50)
    
    # Get inventory
    print("\n📊 Current Cluster Inventory:")
    inventory = get_cluster_inventory()
    
    if inventory:
        print(f"   Switches: {len(inventory['switches'])}")
        print(f"   Connections: {len(inventory['connections'])}")
        print(f"   VPCs: {len(inventory['vpcs'])}")
        print(f"   IPv4 Namespaces: {len(inventory['ipv4_namespaces'])}")
        print(f"   VLAN Namespaces: {len(inventory['vlan_namespaces'])}")
        
        # Show switches
        print("\n🖥️  Switches:")
        for switch in inventory['switches']:
            print(f"   - {switch['name']} ({switch['role']}) - ASN: {switch['asn']}")
        
        # Show VPCs
        print("\n🏢 VPCs:")
        if inventory['vpcs']:
            for vpc in inventory['vpcs']:
                print(f"   - {vpc['name']} ({vpc['subnet_count']} subnets: {', '.join(vpc['subnets'])})")
        else:
            print("   No VPCs found")
        
        # Show IPv4 namespaces
        print("\n🌐 IPv4 Namespaces:")
        for ns in inventory['ipv4_namespaces']:
            print(f"   - {ns['name']}: {', '.join(ns['subnets'])}")
        
        # Show VLAN namespaces
        print("\n🏷️  VLAN Namespaces:")
        for ns in inventory['vlan_namespaces']:
            ranges_str = ', '.join([f"{r['from']}-{r['to']}" for r in ns['ranges']])
            print(f"   - {ns['name']}: {ranges_str}")
    else:
        print("   Failed to retrieve inventory")

def demo_vpc_operations():
    """Demonstrate VPC operations"""
    print("\n" + "=" * 50)
    print("🧪 VPC Operations Demo")
    print("=" * 50)
    
    # Create VPCs from templates
    templates = ["basic", "web-db", "three-tier"]
    
    for i, template in enumerate(templates):
        vpc_name = f"demo-{i+1}"
        print(f"\n📝 Creating VPC '{vpc_name}' from template '{template}'...")
        
        success, message = create_vpc_from_template(vpc_name, template)
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        time.sleep(1)  # Brief pause between operations
    
    # Wait a moment then show updated inventory
    print("\n⏱️  Waiting 3 seconds for cluster sync...")
    time.sleep(3)
    
    # Show updated VPC list
    print("\n📋 Updated VPC List:")
    inventory = get_cluster_inventory()
    if inventory and inventory['vpcs']:
        for vpc in inventory['vpcs']:
            print(f"   - {vpc['name']} ({vpc['subnet_count']} subnets)")
    
    # Clean up demo VPCs
    print("\n🧹 Cleaning up demo VPCs...")
    for i in range(1, 4):
        vpc_name = f"demo-{i}"
        success, message = delete_vpc(vpc_name)
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        time.sleep(1)

def main():
    """Main catalog demo function"""
    print("🚀 Starting Hedgehog Fabric Self-Service Catalog Demo")
    print("=" * 60)
    
    # Show current inventory
    print_catalog_interface()
    
    # Demonstrate VPC operations
    demo_vpc_operations()
    
    print("\n" + "=" * 60)
    print("🎉 Catalog Demo Complete!")
    print("\nThis demonstrates the core functionality that would be")
    print("integrated into the NetBox plugin interface:")
    print("- Real-time cluster inventory")
    print("- Template-based VPC creation")
    print("- Resource lifecycle management")
    print("- Status monitoring and validation")

if __name__ == "__main__":
    main()