#!/usr/bin/env python3
"""
Critical validation script for GitHub sync fix
Tests the actual gitops-test-1 repository with files in raw/ directory
"""

import os
import sys
import django
from pathlib import Path

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
sys.path.insert(0, '/opt/netbox')
django.setup()

from netbox_hedgehog.models import HedgehogFabric
from netbox_hedgehog.services.gitops_onboarding_service import GitOpsOnboardingService
import traceback

def test_github_sync_fix():
    """Test the GitHub sync fix with the actual gitops-test-1 repository"""
    print("=" * 80)
    print("CRITICAL VALIDATION: GitHub Sync Fix with Real Repository")
    print("=" * 80)
    
    # Test 1: Find the fabric for gitops-test-1
    print("\n1. Finding fabric for gitops-test-1 repository...")
    fabric = None
    
    try:
        for f in HedgehogFabric.objects.all():
            if f.git_repository and 'afewell-hh/gitops-test-1' in f.git_repository.url:
                fabric = f
                break
        
        if not fabric:
            print("❌ CRITICAL: Could not find fabric for gitops-test-1 repository")
            print("Available fabrics:")
            for f in HedgehogFabric.objects.all():
                if f.git_repository:
                    print(f"  - {f.name}: {f.git_repository.url}")
            return False
            
        print(f"✅ Found fabric: {fabric.name}")
        print(f"   Repository: {fabric.git_repository.url}")
        print(f"   GitOps directory: {fabric.gitops_directory}")
        
    except Exception as e:
        print(f"❌ Error finding fabric: {e}")
        traceback.print_exc()
        return False
    
    # Test 2: Test the fixed GitHub sync
    print("\n2. Testing the fixed GitHub sync...")
    try:
        onboarding_service = GitOpsOnboardingService(fabric)
        
        # Test with validate_only=True first
        print("   Running validation sync...")
        validation_result = onboarding_service.sync_github_repository(validate_only=True)
        print(f"   Validation result: {validation_result}")
        
        if validation_result.get('success'):
            print("✅ Validation sync successful")
            print(f"   Files that would be processed: {validation_result.get('files_processed', 0)}")
            
            # Now run actual sync
            print("   Running actual sync...")
            github_result = onboarding_service.sync_github_repository(validate_only=False)
            print(f"   GitHub sync success: {github_result['success']}")
            print(f"   Files processed: {github_result['files_processed']}")
            
            if github_result.get('github_operations'):
                print("   Operations performed:")
                for op in github_result['github_operations']:
                    print(f"     - {op}")
            
            if not github_result['success']:
                print(f"❌ Sync failed: {github_result.get('error')}")
                return False
            else:
                print("✅ GitHub sync completed successfully")
                
        else:
            print(f"❌ Validation failed: {validation_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Sync failed with exception: {e}")
        traceback.print_exc()
        return False
    
    # Test 3: Verify GitHub client raw directory access
    print("\n3. Testing GitHub client raw directory access...")
    try:
        github_client = onboarding_service._get_github_client(fabric.git_repository)
        
        # Test the updated analyze_fabric_directory with raw path
        fabric_path = fabric.gitops_directory or "gitops/hedgehog/fabric-1"
        raw_fabric_path = f"{fabric_path}/raw"
        
        print(f"   Testing raw directory access: {raw_fabric_path}")
        analysis = github_client.analyze_fabric_directory(raw_fabric_path)
        
        yaml_files = analysis.get('yaml_files_in_root', [])
        print(f"   YAML files found in raw directory: {len(yaml_files)}")
        
        if yaml_files:
            print("   Files found:")
            for file_info in yaml_files:
                print(f"     - {file_info['name']} ({file_info['path']})")
            print("✅ GitHub client can access raw directory correctly")
        else:
            print("❌ No YAML files found in raw directory")
            print(f"   Full analysis result: {analysis}")
            return False
            
    except Exception as e:
        print(f"❌ GitHub client test failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 4: Check if files are actually processed locally
    print("\n4. Checking if files were processed locally...")
    try:
        # Check if any local files were created
        if hasattr(onboarding_service, 'raw_path') and onboarding_service.raw_path:
            raw_path = onboarding_service.raw_path
            if raw_path.exists():
                local_files = list(raw_path.glob('*.yaml'))
                print(f"   Local raw files created: {len(local_files)}")
                if local_files:
                    print("   Local files:")
                    for file in local_files:
                        print(f"     - {file}")
                    print("✅ Files successfully processed locally")
                else:
                    print("❌ No local files created")
                    return False
            else:
                print(f"❌ Raw path does not exist: {raw_path}")
                return False
        else:
            print("❌ No raw_path attribute found on onboarding service")
            return False
            
    except Exception as e:
        print(f"❌ Local file check failed: {e}")
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED - GitHub sync fix is working correctly!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    success = test_github_sync_fix()
    sys.exit(0 if success else 1)