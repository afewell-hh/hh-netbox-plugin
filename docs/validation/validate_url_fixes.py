#!/usr/bin/env python3
"""
URL Fix Validation Script

Validates that all URL routing issues have been resolved.
"""

import json
import os
import re
from datetime import datetime

def validate_setup_py_fix():
    """Validate that setup.py now has proper plugin entry points"""
    results = {
        'setup_py_status': 'unknown',
        'entry_points_found': False,
        'entry_points_correct': False,
        'issues': []
    }
    
    print("🔧 VALIDATING SETUP.PY FIXES")
    print("=" * 30)
    
    try:
        with open('/home/ubuntu/cc/hedgehog-netbox-plugin/setup.py', 'r') as f:
            content = f.read()
        
        results['setup_py_status'] = 'loaded'
        
        # Check for entry_points section
        if 'entry_points=' in content:
            results['entry_points_found'] = True
            print("✅ entry_points section found")
            
            # Check for correct NetBox plugin entry point
            if 'netbox.plugins' in content and 'netbox_hedgehog' in content:
                results['entry_points_correct'] = True
                print("✅ NetBox plugin entry point correctly configured")
            else:
                results['issues'].append("NetBox plugin entry point not properly configured")
                print("❌ NetBox plugin entry point missing or incorrect")
        else:
            results['entry_points_found'] = False
            results['issues'].append("entry_points section missing from setup.py")
            print("❌ entry_points section not found")
    
    except Exception as e:
        results['issues'].append(f"Error reading setup.py: {e}")
        print(f"❌ Error reading setup.py: {e}")
    
    return results

def validate_url_patterns():
    """Validate URL patterns are correctly configured"""
    results = {
        'url_patterns_status': 'unknown',
        'sync_patterns': {},
        'view_imports': {},
        'issues': []
    }
    
    print("\n🔗 VALIDATING URL PATTERNS")
    print("=" * 25)
    
    try:
        with open('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/urls.py', 'r') as f:
            content = f.read()
        
        results['url_patterns_status'] = 'loaded'
        
        # Check for all required sync patterns
        sync_patterns = {
            'fabric_sync': r"path\(['\"]fabrics/<int:pk>/sync/['\"].*FabricSyncView.*name=['\"]fabric_sync['\"]",
            'fabric_test_connection': r"path\(['\"]fabrics/<int:pk>/test-connection/['\"].*FabricTestConnectionView.*name=['\"]fabric_test_connection['\"]",
            'fabric_github_sync': r"path\(['\"]fabrics/<int:pk>/github-sync/['\"].*FabricGitHubSyncView.*name=['\"]fabric_github_sync['\"]",
            'fabric_detail': r"path\(['\"]fabrics/<int:pk>/['\"].*name=['\"]fabric_detail['\"]",
            'fabric_list': r"path\(['\"]fabrics/['\"].*name=['\"]fabric_list['\"]",
        }
        
        for pattern_name, regex in sync_patterns.items():
            if re.search(regex, content, re.DOTALL):
                results['sync_patterns'][pattern_name] = 'found'
                print(f"✅ {pattern_name} pattern found")
            else:
                results['sync_patterns'][pattern_name] = 'missing'
                results['issues'].append(f"URL pattern {pattern_name} missing or incorrect")
                print(f"❌ {pattern_name} pattern missing")
        
        # Check view imports
        view_imports = [
            'FabricSyncView',
            'FabricTestConnectionView', 
            'FabricGitHubSyncView'
        ]
        
        for view_class in view_imports:
            if f'from .views.fabric_views import {view_class}' in content or \
               f'from .views.sync_views import {view_class}' in content:
                results['view_imports'][view_class] = 'imported'
                print(f"✅ {view_class} imported")
            else:
                results['view_imports'][view_class] = 'missing'
                results['issues'].append(f"View class {view_class} not imported")
                print(f"❌ {view_class} not imported")
                
    except Exception as e:
        results['issues'].append(f"Error reading urls.py: {e}")
        print(f"❌ Error reading urls.py: {e}")
    
    return results

def validate_view_classes():
    """Validate that all view classes exist and are properly defined"""
    results = {
        'view_files_status': {},
        'view_classes': {},
        'issues': []
    }
    
    print("\n👁️  VALIDATING VIEW CLASSES")
    print("=" * 25)
    
    view_files = {
        'sync_views.py': ['FabricTestConnectionView', 'FabricGitHubSyncView'],
        'fabric_views.py': ['FabricSyncView']
    }
    
    for filename, expected_classes in view_files.items():
        filepath = f'/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/{filename}'
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            results['view_files_status'][filename] = 'loaded'
            
            for class_name in expected_classes:
                if f'class {class_name}' in content:
                    results['view_classes'][class_name] = 'found'
                    print(f"✅ {class_name} class found in {filename}")
                    
                    # Check if class has required methods
                    if class_name == 'FabricTestConnectionView':
                        if 'def post(self, request, pk):' in content:
                            print(f"   ✅ {class_name} has post method")
                        else:
                            results['issues'].append(f"{class_name} missing post method")
                    elif class_name in ['FabricSyncView', 'FabricGitHubSyncView']:
                        if 'def post(self, request, pk):' in content:
                            print(f"   ✅ {class_name} has post method")
                        else:
                            results['issues'].append(f"{class_name} missing post method")
                else:
                    results['view_classes'][class_name] = 'missing'
                    results['issues'].append(f"View class {class_name} not found in {filename}")
                    print(f"❌ {class_name} class not found in {filename}")
        
        except Exception as e:
            results['view_files_status'][filename] = 'error'
            results['issues'].append(f"Error reading {filename}: {e}")
            print(f"❌ Error reading {filename}: {e}")
    
    return results

def generate_url_test_matrix():
    """Generate a comprehensive URL test matrix"""
    results = {
        'test_urls': [],
        'expected_responses': {},
        'curl_commands': []
    }
    
    print("\n🧪 GENERATING URL TEST MATRIX")
    print("=" * 30)
    
    fabric_id = 35  # From mission brief
    base_url = "http://localhost:8000"  # Assuming standard NetBox setup
    
    test_urls = [
        {
            'name': 'Plugin Root',
            'path': '/plugins/hedgehog/',
            'expected_status': 200,
            'method': 'GET',
            'description': 'Main plugin overview page'
        },
        {
            'name': 'Fabric List',
            'path': '/plugins/hedgehog/fabrics/',
            'expected_status': 200,
            'method': 'GET',
            'description': 'List all fabrics'
        },
        {
            'name': 'Fabric Detail',
            'path': f'/plugins/hedgehog/fabrics/{fabric_id}/',
            'expected_status': 200,
            'method': 'GET',
            'description': f'Details for fabric {fabric_id}'
        },
        {
            'name': 'Test Connection',
            'path': f'/plugins/hedgehog/fabrics/{fabric_id}/test-connection/',
            'expected_status': 200,  # Should accept POST
            'method': 'POST',
            'description': f'Test connection for fabric {fabric_id}'
        },
        {
            'name': 'Manual Sync',
            'path': f'/plugins/hedgehog/fabrics/{fabric_id}/sync/',
            'expected_status': 200,  # Should accept POST
            'method': 'POST',
            'description': f'Manual sync for fabric {fabric_id}'
        },
        {
            'name': 'GitHub Sync',
            'path': f'/plugins/hedgehog/fabrics/{fabric_id}/github-sync/',
            'expected_status': 200,  # Should accept POST
            'method': 'POST',
            'description': f'GitHub sync for fabric {fabric_id}'
        }
    ]
    
    results['test_urls'] = test_urls
    
    print("Generated test matrix:")
    for test in test_urls:
        print(f"   {test['name']}: {test['method']} {test['path']}")
        
        # Generate curl command
        if test['method'] == 'GET':
            curl_cmd = f"curl -I {base_url}{test['path']}"
        else:
            curl_cmd = f"curl -X {test['method']} -H 'Content-Type: application/json' {base_url}{test['path']}"
        
        results['curl_commands'].append({
            'name': test['name'],
            'command': curl_cmd,
            'expected_status': test['expected_status']
        })
    
    print(f"\nGenerated {len(results['curl_commands'])} cURL test commands")
    
    return results

def main():
    """Main validation function"""
    print("🚀 URL FIX VALIDATION")
    print("=" * 50)
    
    all_results = {
        'timestamp': str(datetime.now()),
        'validation_results': {},
        'summary': {
            'total_issues': 0,
            'critical_issues': [],
            'fixes_applied': [],
            'remaining_issues': []
        }
    }
    
    # Run all validations
    validations = [
        ('Setup.py Fix', validate_setup_py_fix),
        ('URL Patterns', validate_url_patterns),
        ('View Classes', validate_view_classes),
        ('Test Matrix', generate_url_test_matrix),
    ]
    
    all_issues = []
    fixes_applied = []
    
    for name, func in validations:
        print(f"\n{'=' * 15} {name} {'=' * 15}")
        try:
            results = func()
            all_results['validation_results'][name.lower().replace(' ', '_')] = results
            
            # Collect issues
            issues = results.get('issues', [])
            all_issues.extend(issues)
            
            # Track fixes
            if name == 'Setup.py Fix' and results.get('entry_points_correct', False):
                fixes_applied.append("Added NetBox plugin entry points to setup.py")
            
        except Exception as e:
            print(f"❌ {name} validation failed: {e}")
            all_issues.append(f"{name} validation failed: {e}")
    
    # Generate summary
    all_results['summary']['total_issues'] = len(all_issues)
    all_results['summary']['critical_issues'] = all_issues
    all_results['summary']['fixes_applied'] = fixes_applied
    all_results['summary']['remaining_issues'] = all_issues
    
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    if fixes_applied:
        print("✅ Fixes applied:")
        for fix in fixes_applied:
            print(f"   • {fix}")
    
    if all_issues:
        print(f"\n❌ Remaining issues ({len(all_issues)}):")
        for i, issue in enumerate(all_issues, 1):
            print(f"   {i:2d}. {issue}")
    else:
        print("\n✅ No issues found - URL routing should be working correctly!")
    
    print(f"\n🎯 NEXT STEPS:")
    print("   1. Restart NetBox to load plugin with new entry points")
    print("   2. Run database migrations: python manage.py migrate") 
    print("   3. Test URLs using the generated cURL commands")
    print("   4. Check NetBox logs for any plugin loading errors")
    
    # Save results
    output_file = 'url_fix_validation_results.json'
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n💾 Detailed validation results saved to: {output_file}")
    
    return all_results

if __name__ == '__main__':
    results = main()