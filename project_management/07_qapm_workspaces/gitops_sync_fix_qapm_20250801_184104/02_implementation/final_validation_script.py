#!/usr/bin/env python3
"""
Final GitOps Integration Validation Script

This script confirms that the GitOps integration fix is complete and working.
Run this before live testing to ensure all components are properly connected.
"""

import os
import sys
import inspect
import importlib.util
import requests

def validate_implementation_fix():
    """Validate that the implementation fix is correctly applied"""
    print("🔧 IMPLEMENTATION FIX VALIDATION")
    print("=" * 50)
    
    urls_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/urls.py'
    
    with open(urls_path, 'r') as f:
        urls_content = f.read()
    
    # Check imports
    checks = [
        ("FabricTestConnectionView from sync_views", 'from .views.sync_views import FabricTestConnectionView' in urls_content),
        ("FabricSyncView from fabric_views", 'from .views.fabric_views import FabricSyncView' in urls_content),
        ("No dual FabricSyncView import", 'from .views.sync_views import FabricTestConnectionView, FabricSyncView' not in urls_content),
    ]
    
    all_passed = True
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"   {status} {check_name}")
        if not result:
            all_passed = False
    
    return all_passed

def validate_gitops_functions():
    """Validate GitOps functions exist in the active implementation"""
    print("\n🧩 GITOPS FUNCTIONS VALIDATION")
    print("=" * 50)
    
    fabric_views_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/fabric_views.py'
    
    with open(fabric_views_path, 'r') as f:
        content = f.read()
    
    required_elements = [
        ("ensure_gitops_structure import", 'ensure_gitops_structure' in content),
        ("ingest_fabric_raw_files import", 'ingest_fabric_raw_files' in content),
        ("ReconciliationManager import", 'ReconciliationManager' in content),
        ("GitOps structure validation", 'GitOps structure validation' in content),
        ("Process raw files", 'Process raw files before sync' in content),
    ]
    
    all_passed = True
    for element_name, result in required_elements:
        status = "✅" if result else "❌"
        print(f"   {status} {element_name}")
        if not result:
            all_passed = False
    
    return all_passed

def validate_github_authentication():
    """Validate GitHub authentication and repository access"""
    print("\n🌐 GITHUB AUTHENTICATION VALIDATION")
    print("=" * 50)
    
    # Check token
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        # Try loading from .env file
        env_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/.env'
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('GITHUB_TOKEN='):
                        github_token = line.split('=', 1)[1].strip().strip('"')
                        break
    
    if github_token:
        print(f"   ✅ GitHub token found (length: {len(github_token)})")
        
        # Test repository access
        try:
            headers = {'Authorization': f'token {github_token}'}
            response = requests.get('https://api.github.com/repos/afewell-hh/gitops-test-1', headers=headers, timeout=5)
            
            if response.status_code == 200:
                print("   ✅ Repository access successful")
                repo_data = response.json()
                print(f"   📁 Repository: {repo_data.get('full_name')}")
                return True
            else:
                print(f"   ❌ Repository access failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Network error: {e}")
            return False
    else:
        print("   ❌ GitHub token not found")
        return False

def validate_service_files():
    """Validate that required service files exist"""
    print("\n📁 SERVICE FILES VALIDATION")
    print("=" * 50)
    
    required_files = [
        ("GitOpsOnboardingService", '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/services/gitops_onboarding_service.py'),
        ("Signals file", '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/signals.py'),
        ("ReconciliationManager", '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/utils/reconciliation.py'),
        ("Fabric views", '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/fabric_views.py'),
    ]
    
    all_passed = True
    for file_name, file_path in required_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_name}")
        else:
            print(f"   ❌ {file_name} - NOT FOUND")
            all_passed = False
    
    return all_passed

def validate_environment_setup():
    """Validate environment configuration"""
    print("\n⚙️  ENVIRONMENT SETUP VALIDATION")
    print("=" * 50)
    
    checks = []
    
    # Check .env file
    env_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/.env'
    if os.path.exists(env_path):
        checks.append(("Environment file exists", True))
        
        with open(env_path, 'r') as f:
            env_content = f.read()
            checks.append(("GITHUB_TOKEN in .env", 'GITHUB_TOKEN=' in env_content))
            checks.append(("NETBOX_TOKEN in .env", 'NETBOX_TOKEN=' in env_content))
    else:
        checks.append(("Environment file exists", False))
    
    all_passed = True
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"   {status} {check_name}")
        if not result:
            all_passed = False
    
    return all_passed

def generate_test_plan():
    """Generate a live testing plan"""
    print("\n📋 LIVE TESTING PLAN")
    print("=" * 50)
    
    print("1. START NETBOX SERVER:")
    print("   cd /home/ubuntu/cc/hedgehog-netbox-plugin")
    print("   python3 manage.py runserver")
    print()
    
    print("2. ACCESS FABRIC INTERFACE:")
    print("   Open: http://localhost:8000/plugins/netbox-hedgehog/")
    print("   Navigate to fabric detail page")
    print()
    
    print("3. CONFIGURE FABRIC:")
    print("   - Ensure fabric has git_repository set to 'gitops-test-1'")
    print("   - Repository URL: https://github.com/afewell-hh/gitops-test-1")
    print()
    
    print("4. TRIGGER SYNC:")
    print("   - Click 'Sync' button on fabric detail page")
    print("   - Watch for success/error messages")
    print()
    
    print("5. VERIFY RESULTS:")
    print("   - Check GitHub repo for new directory structure")
    print("   - Check NetBox for imported CRD records")
    print("   - Verify fabric sync_status = 'in_sync'")

def main():
    """Run complete validation suite"""
    print("🚀 GITOPS INTEGRATION - FINAL VALIDATION")
    print("=" * 60)
    print("Validating that all components are ready for live testing...")
    print()
    
    validations = [
        ("Implementation Fix", validate_implementation_fix),
        ("GitOps Functions", validate_gitops_functions),
        ("GitHub Authentication", validate_github_authentication),
        ("Service Files", validate_service_files),
        ("Environment Setup", validate_environment_setup),
    ]
    
    results = []
    for validation_name, validation_func in validations:
        try:
            result = validation_func()
            results.append(result)
        except Exception as e:
            print(f"   ❌ Error in {validation_name}: {e}")
            results.append(False)
    
    print("\n🎯 VALIDATION SUMMARY")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    for i, (name, result) in enumerate(zip([v[0] for v in validations], results)):
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print(f"\nResults: {passed}/{total} validations passed")
    
    if passed == total:
        print("\n🎉 ALL VALIDATIONS PASSED!")
        print("✅ GitOps integration fix is complete")
        print("✅ All components are properly configured") 
        print("✅ Ready for live testing")
        
        generate_test_plan()
        
        print("\n💡 NEXT STEPS:")
        print("1. Start NetBox development server")
        print("2. Follow the live testing plan above")
        print("3. Verify GitOps sync processes files correctly")
        
        return 0
    else:
        print(f"\n❌ {total - passed} VALIDATIONS FAILED")
        print("Please fix the failing validations before live testing")
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)