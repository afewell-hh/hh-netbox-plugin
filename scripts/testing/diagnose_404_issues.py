#!/usr/bin/env python3
"""
404 Issue Diagnosis Script

Identifies the root cause of 404 errors in fabric sync endpoints.
"""

import json
import os
from datetime import datetime

def analyze_plugin_configuration():
    """Analyze plugin configuration for routing issues"""
    results = {
        'plugin_config': {},
        'routing_issues': [],
        'expected_paths': {},
        'analysis': {}
    }
    
    print("🔍 PLUGIN CONFIGURATION ANALYSIS")
    print("=" * 40)
    
    try:
        # Read plugin config
        with open('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/__init__.py', 'r') as f:
            content = f.read()
        
        # Extract base_url
        if "base_url = " in content:
            for line in content.split('\n'):
                if "base_url = " in line:
                    base_url = line.split('=')[1].strip().strip('\'"')
                    results['plugin_config']['base_url'] = base_url
                    print(f"✅ Plugin base_url: '{base_url}'")
                    break
        
        # Extract plugin name
        if "name = " in content:
            for line in content.split('\n'):
                if "name = " in line and "verbose_name" not in line:
                    plugin_name = line.split('=')[1].strip().strip('\'"')
                    results['plugin_config']['name'] = plugin_name
                    print(f"✅ Plugin name: '{plugin_name}'")
                    break
        
        # Expected paths based on configuration
        base_url = results['plugin_config'].get('base_url', 'hedgehog')
        fabric_id = 35  # From mission brief
        
        expected_paths = {
            'plugin_root': f'/plugins/{base_url}/',
            'fabric_list': f'/plugins/{base_url}/fabrics/',
            'fabric_detail': f'/plugins/{base_url}/fabrics/{fabric_id}/',
            'fabric_sync': f'/plugins/{base_url}/fabrics/{fabric_id}/sync/',
            'test_connection': f'/plugins/{base_url}/fabrics/{fabric_id}/test-connection/',
            'github_sync': f'/plugins/{base_url}/fabrics/{fabric_id}/github-sync/',
        }
        
        results['expected_paths'] = expected_paths
        
        print("\n📍 Expected plugin paths:")
        for name, path in expected_paths.items():
            print(f"   {name}: {path}")
        
    except Exception as e:
        print(f"❌ Error reading plugin config: {e}")
        results['routing_issues'].append(f"Plugin config error: {e}")
    
    return results

def check_netbox_integration():
    """Check if the plugin is properly integrated with NetBox"""
    results = {
        'integration_issues': [],
        'files_checked': {},
        'recommendations': []
    }
    
    print("\n🔌 NETBOX INTEGRATION CHECK")
    print("=" * 30)
    
    # Check if plugin is in installed apps (would be in NetBox settings)
    # We can't directly check NetBox settings, but we can check plugin structure
    
    critical_files = [
        'netbox_hedgehog/__init__.py',
        'netbox_hedgehog/urls.py', 
        'netbox_hedgehog/views/',
        'netbox_hedgehog/models/',
        'setup.py',
    ]
    
    for file_path in critical_files:
        full_path = f'/home/ubuntu/cc/hedgehog-netbox-plugin/{file_path}'
        if os.path.exists(full_path):
            print(f"✅ {file_path} exists")
            results['files_checked'][file_path] = True
        else:
            print(f"❌ {file_path} missing")
            results['files_checked'][file_path] = False
            results['integration_issues'].append(f"Missing {file_path}")
    
    # Check setup.py for proper plugin registration
    try:
        setup_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/setup.py'
        if os.path.exists(setup_path):
            with open(setup_path, 'r') as f:
                content = f.read()
            
            if 'entry_points' in content and 'netbox.plugins' in content:
                print("✅ Plugin entry points configured in setup.py")
            else:
                print("❌ Plugin entry points missing in setup.py")
                results['integration_issues'].append("Plugin entry points not properly configured")
        
    except Exception as e:
        print(f"❌ Error checking setup.py: {e}")
        results['integration_issues'].append(f"Setup.py check failed: {e}")
    
    return results

def analyze_common_404_causes():
    """Analyze common causes of 404 errors in NetBox plugins"""
    results = {
        'potential_causes': [],
        'url_patterns': [],
        'view_issues': [],
        'recommendations': []
    }
    
    print("\n🚨 COMMON 404 CAUSES ANALYSIS")
    print("=" * 35)
    
    # Check URL patterns in main urls.py
    try:
        with open('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/urls.py', 'r') as f:
            content = f.read()
        
        # Common issues to check for
        issues_to_check = [
            ('Missing trailing slash', r"path\(['\"][^'\"]*[^/]['\"]", "URLs without trailing slashes"),
            ('Incorrect pk parameter', r"<int:id>", "Using 'id' instead of 'pk' in URL patterns"),
            ('Missing view imports', r"path\(['\"][^'\"]*['\"][^,]*,[^,]*name=", "URL patterns without view classes"),
            ('Circular imports', r"from \. import", "Potential circular import issues"),
        ]
        
        for issue_name, pattern, description in issues_to_check:
            import re
            if re.search(pattern, content):
                print(f"⚠️  Potential issue: {issue_name}")
                results['potential_causes'].append(f"{issue_name}: {description}")
            else:
                print(f"✅ No {issue_name} found")
        
        # Check for specific sync view patterns
        sync_patterns = ['fabric_sync', 'test_connection', 'github_sync']
        for pattern in sync_patterns:
            if pattern in content:
                print(f"✅ {pattern} URL pattern exists")
            else:
                print(f"❌ {pattern} URL pattern missing")
                results['potential_causes'].append(f"Missing {pattern} URL pattern")
        
    except Exception as e:
        print(f"❌ Error analyzing URL patterns: {e}")
        results['potential_causes'].append(f"URL pattern analysis failed: {e}")
    
    # Generate recommendations
    recommendations = [
        "Ensure NetBox has the plugin installed and enabled",
        "Check that all view classes are properly imported in urls.py", 
        "Verify URL patterns use 'pk' parameter instead of 'id'",
        "Confirm plugin base_url matches expected paths",
        "Test URL resolution using Django's reverse() function",
        "Check NetBox logs for plugin loading errors",
        "Verify database migrations have been applied",
        "Ensure user has proper permissions for sync operations"
    ]
    
    results['recommendations'] = recommendations
    
    print("\n💡 RECOMMENDATIONS:")
    for i, rec in enumerate(recommendations, 1):
        print(f"   {i:2d}. {rec}")
    
    return results

def generate_test_commands():
    """Generate commands to test the URLs"""
    results = {
        'django_shell_tests': [],
        'curl_tests': [],
        'browser_tests': []
    }
    
    print("\n🧪 GENERATED TEST COMMANDS")
    print("=" * 30)
    
    fabric_id = 35
    
    # Django shell tests
    django_tests = [
        f"from django.urls import reverse",
        f"from netbox_hedgehog.models import HedgehogFabric",
        f"fabric = HedgehogFabric.objects.get(pk={fabric_id})",
        f"reverse('plugins:netbox_hedgehog:fabric_detail', args=[{fabric_id}])",
        f"reverse('plugins:netbox_hedgehog:fabric_sync', args=[{fabric_id}])",
        f"reverse('plugins:netbox_hedgehog:fabric_test_connection', args=[{fabric_id}])",
    ]
    
    results['django_shell_tests'] = django_tests
    
    print("Django shell tests:")
    for test in django_tests:
        print(f"   {test}")
    
    # cURL tests (assuming running on localhost:8000)
    curl_tests = [
        f"curl -I http://localhost:8000/plugins/hedgehog/fabrics/",
        f"curl -I http://localhost:8000/plugins/hedgehog/fabrics/{fabric_id}/",
        f"curl -I http://localhost:8000/plugins/hedgehog/fabrics/{fabric_id}/sync/",
        f"curl -I http://localhost:8000/plugins/hedgehog/fabrics/{fabric_id}/test-connection/",
    ]
    
    results['curl_tests'] = curl_tests
    
    print("\ncURL tests (check for 200 vs 404):")
    for test in curl_tests:
        print(f"   {test}")
    
    return results

def main():
    """Main diagnosis function"""
    print("🚀 404 ERROR DIAGNOSIS")
    print("=" * 50)
    
    all_results = {
        'timestamp': str(datetime.now()),
        'diagnosis_results': {},
        'summary': {
            'total_issues': 0,
            'critical_issues': [],
            'recommendations': []
        }
    }
    
    # Run all analyses
    analyses = [
        ('Plugin Configuration', analyze_plugin_configuration),
        ('NetBox Integration', check_netbox_integration),
        ('Common 404 Causes', analyze_common_404_causes),
        ('Test Commands', generate_test_commands),
    ]
    
    all_issues = []
    all_recommendations = []
    
    for name, func in analyses:
        print(f"\n{'=' * 15} {name} {'=' * 15}")
        try:
            results = func()
            all_results['diagnosis_results'][name.lower().replace(' ', '_')] = results
            
            # Collect issues
            issues = results.get('routing_issues', []) + \
                    results.get('integration_issues', []) + \
                    results.get('potential_causes', []) + \
                    results.get('view_issues', [])
            
            all_issues.extend(issues)
            
            # Collect recommendations
            recs = results.get('recommendations', [])
            all_recommendations.extend(recs)
            
        except Exception as e:
            print(f"❌ {name} analysis failed: {e}")
            all_issues.append(f"{name} analysis failed: {e}")
    
    # Generate summary
    all_results['summary']['total_issues'] = len(all_issues)
    all_results['summary']['critical_issues'] = all_issues
    all_results['summary']['recommendations'] = list(set(all_recommendations))  # Remove duplicates
    
    print("\n" + "=" * 50)
    print("📊 DIAGNOSIS SUMMARY") 
    print("=" * 50)
    
    if all_issues:
        print(f"❌ Found {len(all_issues)} potential issues:")
        for i, issue in enumerate(all_issues, 1):
            print(f"   {i:2d}. {issue}")
    else:
        print("✅ No major configuration issues found")
    
    print(f"\n💡 Top recommendations:")
    for i, rec in enumerate(all_recommendations[:5], 1):  # Top 5
        print(f"   {i}. {rec}")
    
    # Save results
    output_file = 'diagnosis_404_results.json'
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n💾 Detailed diagnosis saved to: {output_file}")
    
    return all_results

if __name__ == '__main__':
    results = main()