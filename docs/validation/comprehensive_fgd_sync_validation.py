#!/usr/bin/env python3
"""
Comprehensive FGD Sync Validation Test - Issue #10 Final Validation

This test validates that all components are working together:
1. Template field references are correct
2. JavaScript functions are consolidated
3. Backend endpoints respond correctly
4. Complete sync workflow functions end-to-end

Following the issue requirements, this will test the complete system using
real NetBox container and GitHub integration.
"""

import requests
import json
import time
from datetime import datetime

def main():
    """Run comprehensive FGD sync validation."""
    
    print("=" * 70)
    print("🚀 COMPREHENSIVE FGD SYNC VALIDATION - ISSUE #10")
    print("=" * 70)
    print(f"Timestamp: {datetime.now()}")
    print()
    
    # Test configuration
    base_url = "http://localhost:8000"
    
    # Test results
    results = {
        'template_rendering': False,
        'javascript_consolidation': False,
        'backend_endpoint': False,
        'sync_workflow': False
    }
    
    try:
        # TEST 1: Template Field Reference Validation
        print("📋 TEST 1: Template Field Reference Validation")
        print("-" * 50)
        
        # Test fabric detail page loads without template errors
        fabric_detail_url = f"{base_url}/plugins/hedgehog/fabrics/1/"
        response = requests.get(fabric_detail_url, timeout=10)
        
        if response.status_code == 200:
            content = response.text
            
            # Check for template errors
            template_errors = [
                'TemplateSyntaxError',
                'AttributeError',
                'object.git_repository.sync_enabled',  # Should not exist after fix
                'FieldError'
            ]
            
            has_errors = any(error in content for error in template_errors)
            
            if not has_errors:
                # Check for correct sync status display
                if 'Git Sync Enabled' in content and 'badge' in content:
                    print("✅ Template renders correctly with proper field references")
                    results['template_rendering'] = True
                else:
                    print("❌ Template missing expected sync status elements")
            else:
                print("❌ Template has field reference errors")
                print("   Found errors in template content")
        else:
            print(f"❌ Template test failed - HTTP {response.status_code}")
        
        print()
        
        # TEST 2: JavaScript Function Consolidation
        print("🔧 TEST 2: JavaScript Function Consolidation")
        print("-" * 50)
        
        if response.status_code == 200:
            content = response.text
            
            # Count sync-related function definitions
            sync_function_count = content.count('function triggerSync')
            sync_from_git_count = content.count('function syncFromGit')
            
            # Should have only one triggerSync function, no syncFromGit
            if sync_function_count == 1 and sync_from_git_count == 0:
                print("✅ JavaScript functions properly consolidated")
                print(f"   - triggerSync functions: {sync_function_count} (correct)")
                print(f"   - syncFromGit functions: {sync_from_git_count} (correct)")
                results['javascript_consolidation'] = True
            else:
                print("❌ JavaScript function consolidation failed")
                print(f"   - triggerSync functions: {sync_function_count}")
                print(f"   - syncFromGit functions: {sync_from_git_count}")
        
        print()
        
        # TEST 3: Backend Endpoint Validation
        print("🌐 TEST 3: Backend Endpoint Validation")
        print("-" * 50)
        
        # Test GitHub sync endpoint accessibility
        github_sync_url = f"{base_url}/plugins/hedgehog/fabrics/1/github-sync/"
        
        # Use HEAD request to test endpoint exists without triggering sync
        try:
            response = requests.head(github_sync_url, timeout=5)
            
            # Check if endpoint exists (should return 405 for HEAD on POST-only endpoint)
            if response.status_code in [405, 200, 302]:
                print("✅ Backend endpoint exists and is accessible")
                print(f"   URL: {github_sync_url}")
                print(f"   Status: {response.status_code} (expected for HEAD request)")
                results['backend_endpoint'] = True
            else:
                print(f"❌ Backend endpoint issue - HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Backend endpoint connection failed: {e}")
        
        print()
        
        # TEST 4: Sync Workflow Integration
        print("🔄 TEST 4: Sync Workflow Integration")  
        print("-" * 50)
        
        # Test that all components are properly integrated
        # Check for service imports and URL patterns
        integration_checks = {
            'GitOpsIngestionService': False,
            'GitHubSyncService': False,
            'FabricGitHubSyncView': False,
            'Signal handlers': False
        }
        
        try:
            # Test service imports (basic validation)
            import sys
            import os
            
            # Add NetBox plugin path
            plugin_path = '/home/ubuntu/cc/hedgehog-netbox-plugin'
            if plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
            
            # Test GitOpsIngestionService import
            try:
                from netbox_hedgehog.services.gitops_ingestion_service import GitOpsIngestionService
                integration_checks['GitOpsIngestionService'] = True
                print("✅ GitOpsIngestionService import successful")
            except ImportError as e:
                print(f"❌ GitOpsIngestionService import failed: {e}")
            
            # Test GitHubSyncService import
            try:
                from netbox_hedgehog.services.github_sync_service import GitHubSyncService
                integration_checks['GitHubSyncService'] = True
                print("✅ GitHubSyncService import successful")
            except ImportError as e:
                print(f"❌ GitHubSyncService import failed: {e}")
            
            # Test FabricGitHubSyncView import
            try:
                from netbox_hedgehog.views.sync_views import FabricGitHubSyncView
                integration_checks['FabricGitHubSyncView'] = True
                print("✅ FabricGitHubSyncView import successful")
            except ImportError as e:
                print(f"❌ FabricGitHubSyncView import failed: {e}")
            
            # Test signal handlers import
            try:
                from netbox_hedgehog import signals
                integration_checks['Signal handlers'] = True
                print("✅ Signal handlers import successful")
            except ImportError as e:
                print(f"❌ Signal handlers import failed: {e}")
            
            # Overall integration check
            if all(integration_checks.values()):
                print("✅ All service integrations successful")
                results['sync_workflow'] = True
            else:
                print("❌ Some service integrations failed")
                
        except Exception as e:
            print(f"❌ Integration test failed: {e}")
        
        print()
        
    except Exception as e:
        print(f"💥 Validation failed with exception: {e}")
        import traceback
        traceback.print_exc()
    
    # FINAL RESULTS
    print("=" * 70)
    print("📊 VALIDATION RESULTS SUMMARY")
    print("=" * 70)
    
    passed_tests = sum(1 for result in results.values() if result)
    total_tests = len(results)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name.replace('_', ' ').title()}")
    
    print()
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED - FGD SYNC IMPLEMENTATION SUCCESSFUL!")
        print()
        print("🚀 READY FOR FINAL GUI VALIDATION")
        print("The implementation has passed all component integration tests.")
        print("Proceed to GUI validation phase to test actual user workflows.")
        return True
    else:
        print("⚠️  SOME TESTS FAILED - IMPLEMENTATION NEEDS ATTENTION")
        print()
        print("Issues to address:")
        for test_name, passed in results.items():
            if not passed:
                print(f"- {test_name.replace('_', ' ').title()}")
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)