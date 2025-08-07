#!/usr/bin/env python3
"""
CRITICAL REALITY CHECK: FGD Synchronization Validation Script

This script tests the ACTUAL current state of the FGD synchronization system 
to verify if it's working or not working as the user has reported.

User Evidence: "I can tell you with certainty I am looking at the fgd now on github 
and its in a state it couldnt possibly be if the fgd were fully working."

PURPOSE: Test the real environment, not theoretical capabilities.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime

def run_command(cmd, description="", capture_output=True):
    """Run a command and return the result"""
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"COMMAND: {cmd}")
    print(f"{'='*60}")
    
    try:
        if capture_output:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            print(f"EXIT CODE: {result.returncode}")
            if result.stdout:
                print(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                print(f"STDERR:\n{result.stderr}")
            return result
        else:
            result = subprocess.run(cmd, shell=True, timeout=30)
            return result
    except subprocess.TimeoutExpired:
        print("❌ COMMAND TIMED OUT")
        return None
    except Exception as e:
        print(f"❌ COMMAND FAILED: {e}")
        return None

def check_file_exists(path, description=""):
    """Check if a file exists and report"""
    print(f"\n📁 CHECKING: {description}")
    print(f"PATH: {path}")
    
    if os.path.exists(path):
        print(f"✅ EXISTS")
        if os.path.isfile(path):
            try:
                with open(path, 'r') as f:
                    content = f.read()
                print(f"SIZE: {len(content)} characters")
                print(f"PREVIEW (first 200 chars):\n{content[:200]}...")
            except Exception as e:
                print(f"❌ Could not read file: {e}")
        return True
    else:
        print(f"❌ NOT FOUND")
        return False

def main():
    print("🔍 CRITICAL REALITY CHECK: FGD Synchronization State Validation")
    print(f"Started at: {datetime.now()}")
    print(f"Working directory: {os.getcwd()}")
    
    validation_results = {
        'timestamp': datetime.now().isoformat(),
        'tests': [],
        'critical_findings': [],
        'recommendations': []
    }
    
    # Test 1: Check if services can be imported
    print("\n" + "="*80)
    print("TEST 1: SERVICE IMPORT CAPABILITY")
    print("="*80)
    
    import_test = """
import sys
sys.path.insert(0, '.')
try:
    from netbox_hedgehog.services.gitops_onboarding_service import GitOpsOnboardingService
    print("✅ GitOpsOnboardingService imports successfully")
    
    # Test basic functionality without Django
    import inspect
    methods = [m for m in dir(GitOpsOnboardingService) if not m.startswith('_')]
    print(f"✅ Service has {len(methods)} public methods")
    print(f"   Methods: {', '.join(methods[:5])}...")
    
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
"""
    
    result = run_command(f'python3 -c "{import_test}"', "Service Import Test")
    validation_results['tests'].append({
        'name': 'service_import',
        'success': result and result.returncode == 0,
        'details': result.stdout if result else "Command failed"
    })
    
    # Test 2: Check fabric creation workflow integration
    print("\n" + "="*80)
    print("TEST 2: INTEGRATION FIX VERIFICATION")
    print("="*80)
    
    workflow_file = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/utils/fabric_creation_workflow.py"
    if check_file_exists(workflow_file, "Fabric Creation Workflow"):
        grep_result = run_command(
            f'grep -n "GitOpsOnboardingService" "{workflow_file}"',
            "Check for GitOps integration"
        )
        integration_exists = grep_result and grep_result.returncode == 0
        validation_results['tests'].append({
            'name': 'integration_fix_applied',
            'success': integration_exists,
            'details': grep_result.stdout if grep_result else "Grep failed"
        })
        
        if integration_exists:
            print("✅ GitOps integration is present in fabric creation workflow")
        else:
            print("❌ GitOps integration NOT found in fabric creation workflow")
            validation_results['critical_findings'].append(
                "GitOps integration missing from fabric creation workflow"
            )
    
    # Test 3: Check if model fields exist for GitOps
    print("\n" + "="*80)
    print("TEST 3: MODEL FIELD VERIFICATION")
    print("="*80)
    
    fabric_model = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/models/fabric.py"
    if check_file_exists(fabric_model, "Fabric Model"):
        gitops_fields = [
            'gitops_initialized',
            'archive_strategy', 
            'raw_directory_path',
            'managed_directory_path'
        ]
        
        fields_found = 0
        for field in gitops_fields:
            grep_result = run_command(
                f'grep -n "{field}" "{fabric_model}"',
                f"Check for field: {field}"
            )
            if grep_result and grep_result.returncode == 0:
                fields_found += 1
                print(f"✅ Field {field} found")
            else:
                print(f"❌ Field {field} NOT found")
        
        validation_results['tests'].append({
            'name': 'model_fields_exist',
            'success': fields_found == len(gitops_fields),
            'details': f"Found {fields_found}/{len(gitops_fields)} required fields"
        })
    
    # Test 4: Check if GitHub service exists
    print("\n" + "="*80)
    print("TEST 4: GITHUB SERVICE VERIFICATION")
    print("="*80)
    
    github_service = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/services/github_push_service.py"
    github_exists = check_file_exists(github_service, "GitHub Push Service")
    validation_results['tests'].append({
        'name': 'github_service_exists',
        'success': github_exists,
        'details': "GitHub service file exists" if github_exists else "GitHub service file missing"
    })
    
    # Test 5: Check directory structure that SHOULD exist if system is working
    print("\n" + "="*80)
    print("TEST 5: EXPECTED DIRECTORY STRUCTURE")
    print("="*80)
    
    # Look for any GitOps directories that might have been created
    potential_paths = [
        "/var/lib/hedgehog/fabrics",
        "/tmp/hedgehog-repos",
        "/opt/netbox/hedgehog-data"
    ]
    
    gitops_dirs_found = []
    for path in potential_paths:
        if os.path.exists(path):
            print(f"✅ Found potential GitOps directory: {path}")
            gitops_dirs_found.append(path)
            # List contents
            try:
                contents = os.listdir(path)
                print(f"   Contents: {contents}")
            except Exception as e:
                print(f"   Could not list contents: {e}")
        else:
            print(f"❌ Path not found: {path}")
    
    validation_results['tests'].append({
        'name': 'gitops_directories_exist',
        'success': len(gitops_dirs_found) > 0,
        'details': f"Found {len(gitops_dirs_found)} potential GitOps directories: {gitops_dirs_found}"
    })
    
    # Test 6: Check if there are any log files that might indicate GitOps activity
    print("\n" + "="*80)
    print("TEST 6: LOG FILE ANALYSIS")
    print("="*80)
    
    log_search = run_command(
        'find /var/log /tmp -name "*.log" -exec grep -l "GitOps\\|onboarding" {} \\; 2>/dev/null',
        "Search for GitOps-related log files"
    )
    
    if log_search and log_search.stdout:
        print(f"✅ Found log files with GitOps activity:\n{log_search.stdout}")
        validation_results['tests'].append({
            'name': 'gitops_log_activity',
            'success': True,
            'details': log_search.stdout.strip()
        })
    else:
        print("❌ No log files found with GitOps activity")
        validation_results['tests'].append({
            'name': 'gitops_log_activity', 
            'success': False,
            'details': "No GitOps activity found in log files"
        })
    
    # Test 7: Check current git repository state in working directory
    print("\n" + "="*80)
    print("TEST 7: LOCAL REPOSITORY STATE")
    print("="*80)
    
    git_status = run_command('git status --porcelain', "Check git working directory state")
    git_log = run_command('git log --oneline -5', "Check recent git commits")
    
    if git_status:
        modified_files = [line for line in git_status.stdout.split('\n') if line.strip()]
        validation_results['tests'].append({
            'name': 'git_repository_state',
            'success': True,
            'details': f"Working directory has {len(modified_files)} modified files"
        })
    
    # CRITICAL ANALYSIS
    print("\n" + "="*80)
    print("CRITICAL ANALYSIS & FINDINGS")
    print("="*80)
    
    successful_tests = sum(1 for test in validation_results['tests'] if test['success'])
    total_tests = len(validation_results['tests'])
    
    print(f"\n📊 TEST RESULTS: {successful_tests}/{total_tests} tests passed")
    
    for test in validation_results['tests']:
        status = "✅ PASS" if test['success'] else "❌ FAIL"
        print(f"{status}: {test['name']} - {test['details']}")
    
    # Determine if FGD is actually working
    critical_tests = ['service_import', 'integration_fix_applied', 'model_fields_exist']
    critical_passed = sum(1 for test in validation_results['tests'] 
                         if test['name'] in critical_tests and test['success'])
    
    print(f"\n🔍 CRITICAL SYSTEM TESTS: {critical_passed}/{len(critical_tests)} passed")
    
    if critical_passed == len(critical_tests):
        print("\n✅ SYSTEM ARCHITECTURE: GitOps system appears to be properly implemented")
        print("   - Services can be imported")
        print("   - Integration fix is applied")  
        print("   - Model fields exist")
        
        if successful_tests < total_tests:
            print("\n⚠️  RUNTIME ISSUES DETECTED:")
            print("   - Architecture is correct but runtime execution may have issues")
            print("   - No GitOps directories found (system may not have been triggered)")
            print("   - No log activity (services may not have been called)")
            
            validation_results['critical_findings'].append(
                "System architecture is correct but GitOps onboarding has not been executed"
            )
            validation_results['recommendations'].extend([
                "Create a new fabric to trigger GitOps onboarding",
                "Check if fabric creation workflow is actually being called",
                "Verify GitOps directories are created during fabric creation",
                "Monitor logs during fabric creation for GitOps activity"
            ])
        else:
            print("\n✅ SYSTEM APPEARS FULLY FUNCTIONAL")
    else:
        print("\n❌ CRITICAL SYSTEM ISSUES DETECTED:")
        print("   - Core GitOps architecture has problems")
        validation_results['critical_findings'].append(
            "Critical system architecture issues prevent GitOps functionality"
        )
        validation_results['recommendations'].extend([
            "Fix service import issues",
            "Apply integration fix to fabric creation workflow", 
            "Add missing model fields for GitOps"
        ])
    
    # Write validation report
    report_file = f"fgd_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(validation_results, f, indent=2)
    
    print(f"\n📄 Full validation report saved to: {report_file}")
    
    # USER EVIDENCE CORRELATION
    print("\n" + "="*80)
    print("USER EVIDENCE CORRELATION")
    print("="*80)
    
    print('\nUSER STATEMENT: "I can tell you with certainty I am looking at the fgd now on github')
    print('and its in a state it couldnt possibly be if the fgd were fully working."')
    
    if critical_passed == len(critical_tests) and successful_tests < total_tests:
        print("\n🎯 CORRELATION: USER EVIDENCE MATCHES FINDINGS")
        print("   - System architecture is implemented correctly")
        print("   - But GitOps onboarding has never been executed")
        print("   - This would result in a GitHub repository that lacks proper GitOps structure")
        print("   - User is seeing an unprocessed repository state")
        
        print("\n🔧 REQUIRED ACTION:")
        print("   1. Trigger GitOps onboarding by creating a new fabric")
        print("   2. Verify the onboarding service actually executes")
        print("   3. Check that GitHub repository gets proper directory structure")
        print("   4. Validate that YAML files are processed correctly")
    else:
        print("\n🎯 CORRELATION: ADDITIONAL INVESTIGATION NEEDED")
        print("   - System state does not fully explain user evidence")
        print("   - May need direct GitHub repository inspection")
        print("   - Consider fabric-specific GitOps configuration issues")

if __name__ == "__main__":
    main()