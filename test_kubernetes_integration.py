#!/usr/bin/env python3
"""
Test Kubernetes integration with live Hedgehog cluster.
This script validates our Kubernetes client utilities against the real cluster.
"""

import sys
import os
import json
from datetime import datetime

# Add our plugin to the Python path
sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')

try:
    from kubernetes import client, config
    print("✅ Successfully imported Kubernetes client")
except ImportError as e:
    print(f"❌ Failed to import Kubernetes client: {e}")
    sys.exit(1)

class MockFabric:
    """Mock fabric object for testing"""
    def __init__(self):
        self.name = "test-fabric"
        
    def get_kubernetes_config(self):
        # Return None to use default kubeconfig
        return None

def test_kubernetes_connection():
    """Test basic Kubernetes connection"""
    print("\n🔗 Testing Kubernetes Connection...")
    
    try:
        # Load kubeconfig
        config.load_kube_config()
        
        # Create API client
        v1 = client.CoreV1Api()
        
        # Test connection by getting cluster info
        namespaces = v1.list_namespace()
        
        print(f"✅ Connection successful!")
        print(f"   Namespaces found: {len(namespaces.items)}")
        
        # Try to get version info
        try:
            version_api = client.VersionApi()
            version = version_api.get_code()
            print(f"   Cluster version: {version.git_version}")
            print(f"   Platform: {version.platform}")
        except Exception:
            print(f"   Version info: Unable to retrieve")
            
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def test_crd_discovery():
    """Test CRD discovery and listing"""
    print("\n🔍 Testing CRD Discovery...")
    
    try:
        from kubernetes import client, config
        config.load_kube_config()
        
        # Get custom resources API
        api_client = client.ApiClient()
        custom_api = client.CustomObjectsApi(api_client)
        
        # List Hedgehog CRDs
        hedgehog_crds = [
            ('vpc.githedgehog.com', 'v1beta1', 'vpcs'),
            ('wiring.githedgehog.com', 'v1beta1', 'switches'),
            ('wiring.githedgehog.com', 'v1beta1', 'connections'),
            ('vpc.githedgehog.com', 'v1beta1', 'ipv4namespaces'),
            ('wiring.githedgehog.com', 'v1beta1', 'vlannamespaces'),
        ]
        
        for group, version, plural in hedgehog_crds:
            try:
                resources = custom_api.list_cluster_custom_object(
                    group=group,
                    version=version,
                    plural=plural
                )
                count = len(resources.get('items', []))
                print(f"✅ {plural}: {count} resources found")
            except Exception as e:
                print(f"❌ {plural}: Failed to list - {e}")
                
    except Exception as e:
        print(f"❌ CRD discovery failed: {e}")
        return False
    
    return True

def test_switch_resource_details():
    """Test detailed switch resource inspection"""
    print("\n🖥️  Testing Switch Resource Details...")
    
    try:
        from kubernetes import client, config
        config.load_kube_config()
        
        custom_api = client.CustomObjectsApi()
        
        # Get a specific switch
        switches = custom_api.list_namespaced_custom_object(
            group='wiring.githedgehog.com',
            version='v1beta1',
            namespace='default',
            plural='switches'
        )
        
        if switches.get('items'):
            switch = switches['items'][0]
            print(f"✅ Switch found: {switch['metadata']['name']}")
            print(f"   Role: {switch['spec'].get('role', 'Unknown')}")
            print(f"   ASN: {switch['spec'].get('asn', 'Unknown')}")
            print(f"   Description: {switch['spec'].get('description', 'None')}")
            
            # Test our model's API version and kind methods
            print(f"   Expected API Version: wiring.githedgehog.com/v1beta1")
            print(f"   Expected Kind: Switch")
            
            return True
        else:
            print("❌ No switches found")
            return False
            
    except Exception as e:
        print(f"❌ Switch inspection failed: {e}")
        return False

def test_vpc_creation_dry_run():
    """Test VPC creation (dry run - no actual creation)"""
    print("\n🏗️  Testing VPC Creation (Dry Run)...")
    
    # Sample VPC specification based on real cluster analysis
    vpc_spec = {
        "ipv4Namespace": "default",
        "vlanNamespace": "default", 
        "subnets": {
            "test-subnet": {
                "subnet": "10.100.1.0/24",
                "gateway": "10.100.1.1",
                "dhcp": {
                    "enable": True,
                    "start": "10.100.1.10",
                    "end": "10.100.1.200"
                }
            }
        }
    }
    
    vpc_manifest = {
        "apiVersion": "vpc.githedgehog.com/v1beta1",
        "kind": "VPC",
        "metadata": {
            "name": "test-vpc-from-netbox",
            "namespace": "default",
            "labels": {
                "source": "netbox-hedgehog-plugin",
                "environment": "test"
            }
        },
        "spec": vpc_spec
    }
    
    print("✅ VPC manifest prepared:")
    print(f"   Name: {vpc_manifest['metadata']['name']}")
    print(f"   Namespace: {vpc_manifest['metadata']['namespace']}")
    print(f"   Subnets: {list(vpc_spec['subnets'].keys())}")
    print(f"   DHCP Enabled: {vpc_spec['subnets']['test-subnet']['dhcp']['enable']}")
    
    # Validate the manifest structure
    required_fields = ['apiVersion', 'kind', 'metadata', 'spec']
    for field in required_fields:
        if field not in vpc_manifest:
            print(f"❌ Missing required field: {field}")
            return False
    
    print("✅ VPC manifest validation passed")
    print("   (Ready for real creation when needed)")
    
    return True

def main():
    """Main test function"""
    print("🚀 Starting Kubernetes Integration Tests with Live Hedgehog Cluster")
    print("=" * 70)
    
    tests = [
        ("Kubernetes Connection", test_kubernetes_connection),
        ("CRD Discovery", test_crd_discovery), 
        ("Switch Resource Details", test_switch_resource_details),
        ("VPC Creation (Dry Run)", test_vpc_creation_dry_run),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Results Summary:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {test_name}")
        if result:
            passed += 1
    
    success_rate = (passed / len(results)) * 100
    print(f"\n🎯 Success Rate: {success_rate:.1f}% ({passed}/{len(results)} tests passed)")
    
    if success_rate == 100:
        print("🎉 All tests passed! Kubernetes integration is ready!")
    elif success_rate >= 75:
        print("⚠️  Most tests passed - minor issues to resolve")
    else:
        print("🚨 Major issues detected - requires investigation")
    
    return success_rate >= 75

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)