#!/usr/bin/env python3
"""
Phase 3 Authentication Fix Validator
Validates that sync views properly handle AJAX authentication
"""

import os
import sys
import json
import subprocess
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_test(test_name, test_func):
    """Run a test and capture results"""
    print(f"\n📋 Running: {test_name}")
    try:
        result = test_func()
        if result['success']:
            print(f"✅ PASSED: {test_name}")
        else:
            print(f"❌ FAILED: {test_name}")
            print(f"   Error: {result.get('error', 'Unknown error')}")
        return result
    except Exception as e:
        print(f"❌ EXCEPTION in {test_name}: {str(e)}")
        return {'success': False, 'error': str(e), 'test': test_name}

def test_file_structure():
    """Test 1: Verify sync_views.py has been properly modified"""
    sync_views_path = 'netbox_hedgehog/views/sync_views.py'
    
    with open(sync_views_path, 'r') as f:
        content = f.read()
    
    # Check that login_required decorator is NOT present
    if '@method_decorator(login_required' in content:
        return {
            'success': False,
            'error': 'login_required decorator still present in sync_views.py'
        }
    
    # Check that dispatch methods handle authentication
    if 'if not request.user.is_authenticated:' not in content:
        return {
            'success': False,
            'error': 'Authentication check not found in dispatch methods'
        }
    
    # Check for proper AJAX handling
    if "request.headers.get('X-Requested-With') == 'XMLHttpRequest'" not in content:
        return {
            'success': False,
            'error': 'AJAX request detection not found'
        }
    
    # Check for JsonResponse with 401 status
    if 'status=401' not in content:
        return {
            'success': False,
            'error': '401 status code not found for unauthorized AJAX requests'
        }
    
    # Check for redirect_to_login import and usage
    if 'from django.contrib.auth.views import redirect_to_login' not in content:
        return {
            'success': False,
            'error': 'redirect_to_login import not found'
        }
    
    return {
        'success': True,
        'message': 'File structure validation passed',
        'checks': {
            'login_required_removed': True,
            'auth_check_in_dispatch': True,
            'ajax_handling': True,
            'proper_status_codes': True,
            'redirect_handling': True
        }
    }

def test_security_preserved():
    """Test 2: Verify security checks are still in place"""
    sync_views_path = 'netbox_hedgehog/views/sync_views.py'
    
    with open(sync_views_path, 'r') as f:
        content = f.read()
    
    # Check permission checks are still present
    if "request.user.has_perm('netbox_hedgehog.change_hedgehogfabric')" not in content:
        return {
            'success': False,
            'error': 'Permission checks removed - security vulnerability!'
        }
    
    # Check that authentication is still required in dispatch
    dispatch_count = content.count('def dispatch(self, request')
    auth_check_count = content.count('if not request.user.is_authenticated:')
    
    if dispatch_count != auth_check_count:
        return {
            'success': False,
            'error': f'Mismatch: {dispatch_count} dispatch methods but only {auth_check_count} auth checks'
        }
    
    return {
        'success': True,
        'message': 'Security validation passed',
        'checks': {
            'permission_checks_present': True,
            'all_dispatches_check_auth': True,
            'dispatch_count': dispatch_count,
            'auth_check_count': auth_check_count
        }
    }

def test_ajax_response_format():
    """Test 3: Verify AJAX responses are properly formatted"""
    sync_views_path = 'netbox_hedgehog/views/sync_views.py'
    
    with open(sync_views_path, 'r') as f:
        content = f.read()
    
    # Check for consistent JSON response structure
    required_fields = [
        "'success': False",
        "'error':",
        "'action': 'redirect_to_login'",
        "'login_url': '/login/'"
    ]
    
    for field in required_fields:
        if field not in content:
            return {
                'success': False,
                'error': f'Missing required JSON field: {field}'
            }
    
    return {
        'success': True,
        'message': 'AJAX response format validation passed',
        'checks': {
            'json_structure': True,
            'required_fields': required_fields
        }
    }

def test_views_consistency():
    """Test 4: Verify all three views have consistent authentication handling"""
    sync_views_path = 'netbox_hedgehog/views/sync_views.py'
    
    with open(sync_views_path, 'r') as f:
        content = f.read()
    
    views = [
        'FabricTestConnectionView',
        'FabricSyncView', 
        'FabricGitHubSyncView'
    ]
    
    for view in views:
        # Find the view class
        view_start = content.find(f'class {view}')
        if view_start == -1:
            return {
                'success': False,
                'error': f'View class {view} not found'
            }
        
        # Find the next class or end of file
        next_class = content.find('\nclass ', view_start + 1)
        view_content = content[view_start:next_class] if next_class != -1 else content[view_start:]
        
        # Check for dispatch method
        if 'def dispatch(self, request' not in view_content:
            return {
                'success': False,
                'error': f'{view} missing dispatch method'
            }
        
        # Check for authentication check
        if 'if not request.user.is_authenticated:' not in view_content:
            return {
                'success': False,
                'error': f'{view} missing authentication check in dispatch'
            }
        
        # Check for AJAX handling
        if "request.headers.get('X-Requested-With')" not in view_content:
            return {
                'success': False,
                'error': f'{view} missing AJAX request handling'
            }
    
    return {
        'success': True,
        'message': 'All views have consistent authentication handling',
        'views_checked': views
    }

def main():
    """Run all validation tests"""
    print("=" * 80)
    print("🔐 PHASE 3: Authentication Fix Validation")
    print(f"📅 Time: {datetime.now().isoformat()}")
    print("=" * 80)
    
    # Run all tests
    results = []
    results.append(run_test("File Structure Validation", test_file_structure))
    results.append(run_test("Security Preservation Check", test_security_preserved))
    results.append(run_test("AJAX Response Format Check", test_ajax_response_format))
    results.append(run_test("Views Consistency Check", test_views_consistency))
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 VALIDATION SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in results if r['success'])
    failed = len(results) - passed
    
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed/len(results)*100):.1f}%")
    
    # Save results
    validation_data = {
        'timestamp': datetime.now().isoformat(),
        'phase': 'authentication_fix_implementation',
        'tests_run': len(results),
        'tests_passed': passed,
        'tests_failed': failed,
        'success_rate': passed/len(results)*100,
        'results': results,
        'implementation_complete': passed == len(results)
    }
    
    with open('phase3_authentication_fix_validation.json', 'w') as f:
        json.dump(validation_data, f, indent=2)
    
    print(f"\n💾 Results saved to: phase3_authentication_fix_validation.json")
    
    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED! Ready to deploy to container.")
    else:
        print("\n⚠️  Some tests failed. Please review and fix issues.")
        sys.exit(1)

if __name__ == "__main__":
    main()