#!/usr/bin/env python3
"""
Script to trigger GitOps initialization and test GitHub push functionality.
This will help diagnose why GitHub pushes aren't working.
"""

import os
import sys
import json
import requests
from pathlib import Path

# Add the project directory to Python path
sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')

def test_github_repository():
    """Test current state of GitHub repository"""
    github_api_url = "https://api.github.com/repos/afewell-hh/gitops-test-1/contents/gitops/hedgehog/fabric-1"
    
    print("🔍 Checking current GitHub repository state...")
    try:
        response = requests.get(github_api_url)
        if response.status_code == 200:
            contents = response.json()
            print(f"✅ Found {len(contents)} items in gitops/hedgehog/fabric-1:")
            for item in contents:
                print(f"   - {item['name']} ({item['type']})")
        else:
            print(f"❌ GitHub API error: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Error accessing GitHub API: {e}")

def check_netbox_fabrics():
    """Check what fabrics exist in NetBox"""
    print("\n🔍 Checking NetBox fabrics...")
    
    # Try to access NetBox API
    netbox_base = "http://localhost:8000"
    api_url = f"{netbox_base}/api/plugins/hedgehog/fabrics/"
    
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            fabrics = data.get('results', [])
            print(f"✅ Found {len(fabrics)} fabrics:")
            for fabric in fabrics:
                print(f"   - ID: {fabric['id']}, Name: {fabric['name']}")
                print(f"     Git Repo: {fabric.get('git_repository_url', 'None')}")
                print(f"     GitOps Dir: {fabric.get('gitops_directory', 'None')}")
                print(f"     Initialized: {fabric.get('gitops_initialized', False)}")
            return fabrics
        else:
            print(f"❌ NetBox API error: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error accessing NetBox API: {e}")
        return []

def trigger_gitops_initialization(fabric_id):
    """Trigger GitOps initialization for a fabric"""
    print(f"\n🚀 Triggering GitOps initialization for fabric {fabric_id}...")
    
    netbox_base = "http://localhost:8000"
    api_url = f"{netbox_base}/api/plugins/hedgehog/fabrics/{fabric_id}/init-gitops/"
    
    payload = {
        "force": True  # Force initialization even if already done
    }
    
    try:
        response = requests.post(api_url, json=payload)
        result = response.json()
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code in [200, 201] and result.get('success'):
            print("✅ GitOps initialization completed")
            return True
        else:
            print(f"❌ GitOps initialization failed: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error triggering GitOps initialization: {e}")
        return False

def test_github_push():
    """Test if directories were actually created in GitHub"""
    print("\n🔍 Testing if GitHub repository was updated...")
    
    # Check for new directories that should have been created
    directories_to_check = [
        "gitops/hedgehog/fabric-1/raw",
        "gitops/hedgehog/fabric-1/managed",
        "gitops/hedgehog/fabric-1/unmanaged"
    ]
    
    for directory in directories_to_check:
        github_api_url = f"https://api.github.com/repos/afewell-hh/gitops-test-1/contents/{directory}"
        
        try:
            response = requests.get(github_api_url)
            if response.status_code == 200:
                print(f"✅ Directory {directory} exists in GitHub")
            else:
                print(f"❌ Directory {directory} NOT found in GitHub (status: {response.status_code})")
        except Exception as e:
            print(f"❌ Error checking {directory}: {e}")

def main():
    """Main execution flow"""
    print("🦔 Hedgehog NetBox Plugin - GitOps Push Investigation")
    print("=" * 60)
    
    # Step 1: Check current GitHub state
    test_github_repository()
    
    # Step 2: Check NetBox fabrics
    fabrics = check_netbox_fabrics()
    
    if not fabrics:
        print("❌ No fabrics found. Cannot proceed.")
        return
    
    # Step 3: Find the fabric to test with
    target_fabric = None
    for fabric in fabrics:
        if fabric.get('git_repository_url') and 'gitops-test-1' in fabric['git_repository_url']:
            target_fabric = fabric
            break
    
    if not target_fabric:
        print("❌ No fabric found with gitops-test-1 repository")
        return
    
    print(f"\n🎯 Using fabric: {target_fabric['name']} (ID: {target_fabric['id']})")
    
    # Step 4: Trigger GitOps initialization
    success = trigger_gitops_initialization(target_fabric['id'])
    
    if success:
        # Step 5: Test if GitHub was actually updated
        test_github_push()
    
    print("\n" + "=" * 60)
    print("Investigation complete!")

if __name__ == "__main__":
    main()