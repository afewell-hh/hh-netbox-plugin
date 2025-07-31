#!/usr/bin/env python3
"""
Phase 1: System Preparation - Current State Analysis
Senior TDD Implementation Agent - HNP Fabric Sync
"""

import requests
import re
from datetime import datetime

def check_fabric_state():
    """Check current state of fabrics and git repositories"""
    print("=" * 60)
    print("PHASE 1: SYSTEM PREPARATION - CURRENT STATE ANALYSIS")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Check fabric list via API
    print("1. FABRIC ANALYSIS")
    print("-" * 30)
    
    try:
        response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/")
        if response.status_code == 200:
            content = response.text
            
            # Extract fabric ID
            import re
            fabric_links = re.findall(r'href="/plugins/hedgehog/fabrics/(\d+)/"', content)
            print(f"Fabrics found: {fabric_links}")
            
            if fabric_links:
                fabric_id = fabric_links[0]
                print(f"Analyzing fabric ID: {fabric_id}")
                
                # Get fabric detail
                detail_response = requests.get(f"http://localhost:8000/plugins/hedgehog/fabrics/{fabric_id}/")
                if detail_response.status_code == 200:
                    detail_content = detail_response.text
                    
                    # Check for git repository information
                    print("\nFabric Detail Analysis:")
                    if "git_repository" in detail_content.lower():
                        print("  ✓ Git repository field found in fabric detail")
                    else:
                        print("  ✗ Git repository field NOT found in fabric detail")
                    
                    if "gitops_directory" in detail_content.lower():
                        print("  ✓ GitOps directory field found")
                    else:
                        print("  ✗ GitOps directory field NOT found")
                        
                    if "connection_status" in detail_content.lower():
                        print("  ✓ Connection status field found")
                    else:
                        print("  ✗ Connection status field NOT found")
                        
                    # Check for test connection button
                    if "test connection" in detail_content.lower() or "test_connection" in detail_content.lower():
                        print("  ✓ Test Connection button found")
                    else:
                        print("  ✗ Test Connection button NOT found")
                        
                    # Check for sync button
                    if "sync" in detail_content.lower() and "button" in detail_content.lower():
                        print("  ✓ Sync button found")
                    else:
                        print("  ✗ Sync button NOT found")
                else:
                    print(f"  ✗ Failed to load fabric detail: HTTP {detail_response.status_code}")
            else:
                print("  ✗ No fabric IDs found in list")
        else:
            print(f"  ✗ Failed to load fabric list: HTTP {response.status_code}")
    except Exception as e:
        print(f"  ✗ Fabric analysis error: {e}")

    print()
    
    # 2. Check git repositories
    print("2. GIT REPOSITORY ANALYSIS")
    print("-" * 30)
    
    try:
        response = requests.get("http://localhost:8000/plugins/hedgehog/git-repositories/")
        if response.status_code == 200:
            content = response.text
            
            # Extract git repository IDs
            git_links = re.findall(r'href="/plugins/hedgehog/git-repositories/(\d+)/"', content)
            print(f"Git repositories found: {git_links}")
            
            if git_links:
                git_id = git_links[0]
                print(f"Analyzing git repository ID: {git_id}")
                
                # Get git repository detail
                detail_response = requests.get(f"http://localhost:8000/plugins/hedgehog/git-repositories/{git_id}/")
                if detail_response.status_code == 200:
                    detail_content = detail_response.text
                    
                    print("\nGit Repository Detail Analysis:")
                    # Check connection status
                    if "pending" in detail_content.lower():
                        print("  ⚠ Connection status appears to be 'pending'")
                    elif "connected" in detail_content.lower():
                        print("  ✓ Connection status appears to be 'connected'")
                    else:
                        print("  ? Connection status unclear")
                        
                    # Check directory path
                    if 'gitops/' in detail_content or 'hedgehog/' in detail_content:
                        print("  ✓ GitOps directory path found")
                    else:
                        print("  ✗ GitOps directory path NOT found or is root ('/')")
                else:
                    print(f"  ✗ Failed to load git repository detail: HTTP {detail_response.status_code}")
            else:
                print("  ✗ No git repository IDs found")
        else:
            print(f"  ✗ Failed to load git repository list: HTTP {response.status_code}")
    except Exception as e:
        print(f"  ✗ Git repository analysis error: {e}")

    print()
    
    # 3. Test specific failing test conditions
    print("3. MANDATORY FAILING TEST CONDITIONS")
    print("-" * 30)
    
    # Test fabric detail page for ID 12 (which should fail)
    try:
        response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
        print(f"Test: Fabric ID 12 detail page: HTTP {response.status_code} ({'EXPECTED' if response.status_code == 404 else 'UNEXPECTED'})")
    except Exception as e:
        print(f"Test: Fabric ID 12 error: {e}")
    
    # Test if we can find a working fabric ID
    if fabric_links:
        working_id = fabric_links[0]
        try:
            response = requests.get(f"http://localhost:8000/plugins/hedgehog/fabrics/{working_id}/")
            print(f"Test: Fabric ID {working_id} detail page: HTTP {response.status_code} ({'WORKING' if response.status_code == 200 else 'FAILING'})")
        except Exception as e:
            print(f"Test: Fabric ID {working_id} error: {e}")
    
    print()
    
    # 4. Summary of issues identified
    print("4. ISSUES IDENTIFIED FOR FIXING")
    print("-" * 30)
    print("Based on architectural requirements from research:")
    print("  [ ] GitRepository FK: fabric.git_repository may be None")
    print("  [ ] Directory Path: gitops_directory may be '/' instead of 'gitops/hedgehog/fabric-X/'")
    print("  [ ] Authentication: Repository connection_status may be 'pending' instead of 'connected'")
    print("  [ ] CRD Creation: All CRD counts are likely 0")
    print("  [ ] Test Configuration: Tests are hardcoded to use fabric ID 12 which doesn't exist")
    
    print()
    print("NEXT STEPS:")
    print("1. Fix test configuration to use existing fabric IDs")
    print("2. Run all 10 mandatory failing tests to document current failure state")
    print("3. Implement fixes for GitRepository FK, directory paths, authentication")
    print("4. Create actual CRD records from YAML files")
    print("5. Validate complete user workflow")
    
    print("=" * 60)

if __name__ == "__main__":
    check_fabric_state()