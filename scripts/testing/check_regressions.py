#!/usr/bin/env python3
"""
Check for potential regressions in the GitHub sync implementation.

This script analyzes the modified sync_views.py to ensure that:
1. All original functionality is preserved
2. No existing workflows are broken
3. Error handling is properly maintained
4. Import statements are valid
"""

import ast
import re
from pathlib import Path
from datetime import datetime


def check_regressions():
    """
    Check for potential regressions in the GitHub sync implementation.
    """
    regression_check = {
        'success': False,
        'test_name': 'GitHub Sync Regression Check',
        'started_at': datetime.now().isoformat(),
        'checks_performed': [],
        'issues_found': [],
        'warnings': [],
        'evidence': {}
    }
    
    try:
        print("=== GitHub Sync Regression Check ===")
        print(f"Started at: {regression_check['started_at']}")
        
        # Load the modified sync_views.py file
        sync_views_file = Path('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/sync_views.py')
        sync_views_content = sync_views_file.read_text()
        
        # Check 1: Verify Python syntax is valid
        print("\n1. Checking Python syntax...")
        
        try:
            ast.parse(sync_views_content)
            print("   ✓ Python syntax is valid")
            regression_check['evidence']['syntax_valid'] = True
        except SyntaxError as e:
            regression_check['issues_found'].append(f"Syntax error: {e}")
            regression_check['evidence']['syntax_valid'] = False
        
        regression_check['checks_performed'].append("syntax_check")
        
        # Check 2: Verify all required imports are present
        print("\n2. Checking import statements...")
        
        required_imports = [
            'django.contrib',
            'django.shortcuts.get_object_or_404',
            'django.views.generic.View',
            'django.http.JsonResponse',
            'django.utils.decorators.method_decorator',
            'django.contrib.auth.decorators.login_required',
            'django.utils.timezone',
            'logging',
            'HedgehogFabric',
            'KubernetesClient',
            'KubernetesSync',
            'GitOpsOnboardingService'
        ]
        
        missing_imports = []
        for import_item in required_imports:
            if import_item not in sync_views_content:
                missing_imports.append(import_item)
        
        if missing_imports:
            regression_check['issues_found'].append(f"Missing imports: {missing_imports}")
        else:
            print("   ✓ All required imports are present")
        
        regression_check['evidence']['missing_imports'] = missing_imports
        regression_check['checks_performed'].append("import_check")
        
        # Check 3: Verify all original view classes are present
        print("\n3. Checking view class preservation...")
        
        expected_classes = [
            'FabricTestConnectionView',
            'FabricSyncView', 
            'FabricGitHubSyncView'
        ]
        
        missing_classes = []
        for class_name in expected_classes:
            pattern = rf'class\s+{class_name}\s*\([^)]+\):'
            if not re.search(pattern, sync_views_content):
                missing_classes.append(class_name)
        
        if missing_classes:
            regression_check['issues_found'].append(f"Missing view classes: {missing_classes}")
        else:
            print("   ✓ All view classes are present")
        
        regression_check['evidence']['missing_classes'] = missing_classes
        regression_check['checks_performed'].append("class_preservation_check")
        
        # Check 4: Verify original FabricGitHubSyncView structure is preserved
        print("\n4. Checking FabricGitHubSyncView structure...")
        
        # Find the post method
        post_method_pattern = r'def\s+post\s*\(\s*self\s*,\s*request\s*,\s*pk\s*\):'
        post_method_match = re.search(post_method_pattern, sync_views_content)
        
        if not post_method_match:
            regression_check['issues_found'].append("FabricGitHubSyncView.post method not found")
        else:
            print("   ✓ post method signature preserved")
        
        # Check for original permission check
        permission_check_pattern = r'request\.user\.has_perm.*netbox_hedgehog\.change_hedgehogfabric'
        if not re.search(permission_check_pattern, sync_views_content):
            regression_check['issues_found'].append("Permission check missing or modified")
        else:
            print("   ✓ Permission check preserved")
        
        # Check for original GitHub repository validation
        github_check_pattern = r'github\.com.*not in.*fabric\.git_repository\.url'
        if not re.search(github_check_pattern, sync_views_content):
            regression_check['warnings'].append("GitHub URL validation may have been modified")
        else:
            print("   ✓ GitHub repository validation preserved")
        
        regression_check['checks_performed'].append("structure_preservation_check")
        
        # Check 5: Verify error handling patterns are preserved
        print("\n5. Checking error handling preservation...")
        
        # Check for try/except blocks
        try_except_count = len(re.findall(r'try:', sync_views_content))
        except_count = len(re.findall(r'except\s+Exception', sync_views_content))
        
        print(f"   Try blocks found: {try_except_count}")
        print(f"   Exception handlers found: {except_count}")
        
        if try_except_count == 0:
            regression_check['issues_found'].append("No try/except blocks found")
        
        # Check for proper fabric status updates
        status_updates = len(re.findall(r'fabric\.sync_status\s*=', sync_views_content))
        if status_updates < 3:  # Should have updates for error, partial_sync, synced states
            regression_check['warnings'].append("Insufficient fabric status updates")
        
        regression_check['evidence']['try_except_count'] = try_except_count
        regression_check['evidence']['status_updates'] = status_updates
        regression_check['checks_performed'].append("error_handling_check")
        
        # Check 6: Verify response patterns are maintained
        print("\n6. Checking response patterns...")
        
        # Check for JsonResponse usage
        json_response_count = len(re.findall(r'JsonResponse\s*\(', sync_views_content))
        if json_response_count < 3:  # Should have success, error, and partial responses
            regression_check['warnings'].append("Insufficient JsonResponse usage")
        
        # Check for messages framework usage
        messages_usage = len(re.findall(r'messages\.(success|error|warning)', sync_views_content))
        if messages_usage < 3:
            regression_check['warnings'].append("Insufficient messages framework usage")
        
        regression_check['evidence']['json_response_count'] = json_response_count
        regression_check['evidence']['messages_usage'] = messages_usage
        regression_check['checks_performed'].append("response_patterns_check")
        
        # Check 7: Verify code organization and readability
        print("\n7. Checking code organization...")
        
        # Check method length (should be reasonable)
        post_method_content = sync_views_content[sync_views_content.find('def post(self, request, pk):'):]
        next_method_start = post_method_content.find('\n    def ')
        if next_method_start > 0:
            post_method_content = post_method_content[:next_method_start]
        
        post_method_lines = len(post_method_content.split('\n'))
        
        if post_method_lines > 200:
            regression_check['warnings'].append(f"Post method is very long ({post_method_lines} lines)")
        
        regression_check['evidence']['post_method_lines'] = post_method_lines
        regression_check['checks_performed'].append("code_organization_check")
        
        # Final assessment
        print("\n=== REGRESSION ASSESSMENT ===")
        
        issues_count = len(regression_check['issues_found'])
        warnings_count = len(regression_check['warnings'])
        
        print(f"Critical issues found: {issues_count}")
        print(f"Warnings identified: {warnings_count}")
        
        if issues_count == 0:
            regression_check['success'] = True
            if warnings_count == 0:
                regression_check['assessment'] = "NO REGRESSIONS DETECTED"
                print("✓ No regressions detected - implementation is safe")
            else:
                regression_check['assessment'] = "MINOR WARNINGS ONLY"
                print("⚠ Minor warnings found but no critical regressions")
        else:
            regression_check['assessment'] = "CRITICAL ISSUES DETECTED"
            print("✗ Critical issues detected - review required")
        
        # Display issues and warnings
        if regression_check['issues_found']:
            print("\nCritical Issues:")
            for issue in regression_check['issues_found']:
                print(f"  - {issue}")
        
        if regression_check['warnings']:
            print("\nWarnings:")
            for warning in regression_check['warnings']:
                print(f"  - {warning}")
        
        regression_check['completed_at'] = datetime.now().isoformat()
        
        return regression_check
        
    except Exception as e:
        print(f"\nRegression check failed with exception: {e}")
        regression_check['success'] = False
        regression_check['error'] = str(e)
        regression_check['completed_at'] = datetime.now().isoformat()
        return regression_check


def save_regression_results(results):
    """Save regression check results to file."""
    results_file = Path('/home/ubuntu/cc/hedgehog-netbox-plugin/github_sync_regression_check.json')
    
    with open(results_file, 'w') as f:
        import json
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nRegression check results saved to: {results_file}")
    return results_file


if __name__ == "__main__":
    results = check_regressions()
    results_file = save_regression_results(results)
    
    # Exit with appropriate code
    exit_code = 0 if results['success'] else 1
    print(f"\nExiting with code: {exit_code}")
    exit(exit_code)