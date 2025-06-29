#!/usr/bin/env python3
"""
Test VPC creation with live Hedgehog cluster.
This script creates, monitors, and cleans up a test VPC.
"""

import sys
import json
import time
from datetime import datetime
from kubernetes import client, config
from kubernetes.client.rest import ApiException

def load_kubernetes_config():
    """Load Kubernetes configuration"""
    try:
        config.load_kube_config()
        print("✅ Kubernetes config loaded")
        return True
    except Exception as e:
        print(f"❌ Failed to load Kubernetes config: {e}")
        return False

def create_test_vpc():
    """Create a test VPC in the live cluster"""
    print("\n🏗️  Creating Test VPC...")
    
    # VPC manifest with valid configuration based on cluster validation
    vpc_manifest = {
        "apiVersion": "vpc.githedgehog.com/v1beta1",
        "kind": "VPC",
        "metadata": {
            "name": "test-vpc",  # Shortened name (≤ 11 chars)
            "namespace": "default",
            "labels": {
                "source": "netbox-hedgehog-plugin",
                "environment": "test",
                "created-by": "integration-test"
            }
        },
        "spec": {
            "ipv4Namespace": "default",
            "vlanNamespace": "default",
            "subnets": {
                "web": {  # Shortened subnet name
                    "subnet": "10.0.1.0/24",  # Within IPv4Namespace range
                    "gateway": "10.0.1.1",
                    "vlan": 1100,  # Within VLANNamespace range (1000-2999)
                    "dhcp": {
                        "enable": True
                    }
                },
                "db": {  # Shortened subnet name
                    "subnet": "10.0.2.0/24",  # Within IPv4Namespace range
                    "gateway": "10.0.2.1",
                    "vlan": 1101,  # Within VLANNamespace range (1000-2999)
                    "dhcp": {
                        "enable": True
                    }
                }
            }
        }
    }
    
    try:
        # Create custom objects API client
        custom_api = client.CustomObjectsApi()
        
        # Create the VPC
        result = custom_api.create_namespaced_custom_object(
            group="vpc.githedgehog.com",
            version="v1beta1",
            namespace="default",
            plural="vpcs",
            body=vpc_manifest
        )
        
        print(f"✅ VPC created successfully!")
        print(f"   Name: {result['metadata']['name']}")
        print(f"   UID: {result['metadata']['uid']}")
        print(f"   Creation Time: {result['metadata']['creationTimestamp']}")
        print(f"   Subnets: {list(vpc_manifest['spec']['subnets'].keys())}")
        
        return result['metadata']['name'], result['metadata']['uid']
        
    except ApiException as e:
        print(f"❌ Failed to create VPC: {e}")
        if e.status == 409:
            print("   VPC already exists - this is expected if running multiple times")
            return "test-vpc", None
        return None, None
    except Exception as e:
        print(f"❌ Unexpected error creating VPC: {e}")
        return None, None

def monitor_vpc_status(vpc_name, timeout=60):
    """Monitor VPC status until ready or timeout"""
    print(f"\n📊 Monitoring VPC Status (timeout: {timeout}s)...")
    
    custom_api = client.CustomObjectsApi()
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Get VPC status
            vpc = custom_api.get_namespaced_custom_object(
                group="vpc.githedgehog.com",
                version="v1beta1",
                namespace="default",
                plural="vpcs",
                name=vpc_name
            )
            
            status = vpc.get('status', {})
            conditions = status.get('conditions', [])
            
            print(f"⏱️  Status check at {time.time() - start_time:.1f}s:")
            
            if conditions:
                for condition in conditions:
                    condition_type = condition.get('type', 'Unknown')
                    condition_status = condition.get('status', 'Unknown')
                    message = condition.get('message', '')
                    print(f"   {condition_type}: {condition_status}")
                    if message:
                        print(f"      Message: {message}")
                        
                # Check if VPC is ready
                ready_condition = next((c for c in conditions if c.get('type') == 'Ready'), None)
                if ready_condition and ready_condition.get('status') == 'True':
                    print("✅ VPC is ready!")
                    return True
                    
            else:
                print("   No conditions found yet...")
                
            time.sleep(5)
            
        except ApiException as e:
            print(f"❌ Failed to get VPC status: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error monitoring VPC: {e}")
            return False
    
    print(f"⏰ Timeout reached after {timeout}s")
    return False

def cleanup_test_vpc(vpc_name):
    """Clean up the test VPC"""
    print(f"\n🧹 Cleaning up test VPC: {vpc_name}")
    
    try:
        custom_api = client.CustomObjectsApi()
        
        # Delete the VPC
        custom_api.delete_namespaced_custom_object(
            group="vpc.githedgehog.com",
            version="v1beta1",
            namespace="default",
            plural="vpcs",
            name=vpc_name
        )
        
        print("✅ VPC deletion initiated")
        
        # Wait for deletion to complete
        for i in range(30):  # 30 second timeout
            try:
                custom_api.get_namespaced_custom_object(
                    group="vpc.githedgehog.com",
                    version="v1beta1", 
                    namespace="default",
                    plural="vpcs",
                    name=vpc_name
                )
                print(f"⏱️  Waiting for deletion... ({i+1}s)")
                time.sleep(1)
            except ApiException as e:
                if e.status == 404:
                    print("✅ VPC successfully deleted!")
                    return True
                else:
                    print(f"❌ Error checking deletion status: {e}")
                    return False
        
        print("⏰ Deletion timeout - VPC may still exist")
        return False
        
    except ApiException as e:
        if e.status == 404:
            print("✅ VPC already deleted")
            return True
        else:
            print(f"❌ Failed to delete VPC: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error during cleanup: {e}")
        return False

def list_existing_vpcs():
    """List existing VPCs for context"""
    print("\n📋 Listing existing VPCs...")
    
    try:
        custom_api = client.CustomObjectsApi()
        
        vpcs = custom_api.list_namespaced_custom_object(
            group="vpc.githedgehog.com",
            version="v1beta1",
            namespace="default",
            plural="vpcs"
        )
        
        items = vpcs.get('items', [])
        if items:
            print(f"   Found {len(items)} existing VPC(s):")
            for vpc in items:
                name = vpc['metadata']['name']
                created = vpc['metadata'].get('creationTimestamp', 'Unknown')
                subnets = list(vpc.get('spec', {}).get('subnets', {}).keys())
                print(f"   - {name} (created: {created}, subnets: {len(subnets)})")
        else:
            print("   No existing VPCs found")
            
        return len(items)
        
    except Exception as e:
        print(f"❌ Failed to list VPCs: {e}")
        return 0

def main():
    """Main test function"""
    print("🚀 Starting VPC Creation Test with Live Hedgehog Cluster")
    print("=" * 65)
    
    # Load Kubernetes config
    if not load_kubernetes_config():
        sys.exit(1)
    
    # List existing VPCs
    initial_vpc_count = list_existing_vpcs()
    
    # Create test VPC
    vpc_name, vpc_uid = create_test_vpc()
    if not vpc_name:
        print("❌ Failed to create VPC - aborting test")
        sys.exit(1)
    
    # Monitor VPC status
    vpc_ready = monitor_vpc_status(vpc_name)
    
    # List VPCs again to confirm creation
    final_vpc_count = list_existing_vpcs()
    
    # Clean up
    cleanup_success = cleanup_test_vpc(vpc_name)
    
    # Summary
    print("\n" + "=" * 65)
    print("📊 Test Summary:")
    print(f"   VPC Creation: {'✅ SUCCESS' if vpc_name else '❌ FAILED'}")
    print(f"   VPC Status Monitoring: {'✅ READY' if vpc_ready else '⏰ TIMEOUT'}")
    print(f"   VPC Cleanup: {'✅ SUCCESS' if cleanup_success else '❌ FAILED'}")
    print(f"   VPC Count Change: {initial_vpc_count} → {final_vpc_count}")
    
    if vpc_name and cleanup_success:
        print("🎉 VPC lifecycle test completed successfully!")
        return True
    else:
        print("🚨 VPC lifecycle test had issues")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)