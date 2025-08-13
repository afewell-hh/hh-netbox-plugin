#!/usr/bin/env python3
"""
Simple URL Analysis Script

Analyzes URL patterns without Django setup to identify routing issues.
"""

import json
import re
from datetime import datetime

def analyze_urls_file():
    """Analyze the main urls.py file"""
    results = {
        'timestamp': str(datetime.now()),
        'file_analysis': {},
        'sync_urls_found': [],
        'missing_patterns': [],
        'pattern_issues': [],
        'summary': {}
    }
    
    print("🔍 ANALYZING URL PATTERNS")
    print("=" * 40)
    
    try:
        # Read main urls.py
        with open('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/urls.py', 'r') as f:
            content = f.read()
        
        print("✅ Successfully loaded netbox_hedgehog/urls.py")
        results['file_analysis']['main_urls_loaded'] = True
        
        # Extract app_name
        app_name_match = re.search(r"app_name\s*=\s*['\"]([^'\"]+)['\"]", content)
        if app_name_match:
            app_name = app_name_match.group(1)
            print(f"✅ App name found: '{app_name}'")
            results['file_analysis']['app_name'] = app_name
        else:
            print("❌ No app_name found")
            results['pattern_issues'].append("No app_name defined")
        
        # Check for sync-related URL patterns
        sync_patterns = [
            (r"path\(['\"][^'\"]*sync[^'\"]*['\"]", "Generic sync pattern"),
            (r"path\(['\"][^'\"]*test-connection[^'\"]*['\"]", "Test connection pattern"),
            (r"path\(['\"][^'\"]*github-sync[^'\"]*['\"]", "GitHub sync pattern"),
            (r"FabricSyncView", "FabricSyncView reference"),
            (r"FabricTestConnectionView", "FabricTestConnectionView reference"),
            (r"FabricGitHubSyncView", "FabricGitHubSyncView reference"),
        ]
        
        print("\n📋 Checking for sync-related patterns:")
        for pattern, description in sync_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                print(f"✅ Found {description}: {len(matches)} matches")
                results['sync_urls_found'].append({
                    'pattern': description,
                    'matches': matches
                })
            else:
                print(f"❌ Missing {description}")
                results['missing_patterns'].append(description)
        
        # Extract specific fabric sync URLs
        fabric_url_patterns = re.findall(
            r"path\(['\"]([^'\"]*fabrics[^'\"]*)['\"].*?name=['\"]([^'\"]+)['\"]",
            content, 
            re.DOTALL
        )
        
        print(f"\n🎯 Found {len(fabric_url_patterns)} fabric URL patterns:")
        for url_pattern, name in fabric_url_patterns:
            print(f"   {name}: {url_pattern}")
        
        results['file_analysis']['fabric_patterns'] = [
            {'url_pattern': url, 'name': name} 
            for url, name in fabric_url_patterns
        ]
        
        # Check imports
        import_patterns = [
            (r"from \.views\.sync_views import", "sync_views import"),
            (r"from \.views\.fabric_views import", "fabric_views import"),
            (r"FabricSyncView", "FabricSyncView import"),
        ]
        
        print("\n📦 Checking imports:")
        for pattern, description in import_patterns:
            if re.search(pattern, content):
                print(f"✅ {description} found")
            else:
                print(f"❌ {description} missing")
                results['pattern_issues'].append(f"Missing {description}")
        
    except Exception as e:
        print(f"❌ Error reading urls.py: {e}")
        results['pattern_issues'].append(f"Error reading file: {e}")
    
    return results

def check_view_files():
    """Check if view files exist and contain required classes"""
    results = {
        'view_files': {},
        'missing_views': [],
        'issues_found': []
    }
    
    print("\n🔍 CHECKING VIEW FILES")
    print("=" * 30)
    
    view_files = [
        ('sync_views.py', ['FabricSyncView', 'FabricTestConnectionView', 'FabricGitHubSyncView']),
        ('fabric_views.py', ['FabricSyncView', 'FabricDetailView']),
    ]
    
    for filename, expected_classes in view_files:
        filepath = f'/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/{filename}'
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            print(f"✅ {filename} exists")
            results['view_files'][filename] = {'exists': True, 'classes_found': []}
            
            # Check for expected classes
            for class_name in expected_classes:
                if f'class {class_name}' in content:
                    print(f"   ✅ {class_name} found")
                    results['view_files'][filename]['classes_found'].append(class_name)
                else:
                    print(f"   ❌ {class_name} missing")
                    results['missing_views'].append(f"{class_name} in {filename}")
            
        except FileNotFoundError:
            print(f"❌ {filename} not found")
            results['view_files'][filename] = {'exists': False}
            results['issues_found'].append(f"{filename} file missing")
        except Exception as e:
            print(f"❌ Error reading {filename}: {e}")
            results['issues_found'].append(f"Error reading {filename}: {e}")
    
    return results

def expected_vs_actual_urls():
    """Compare expected URLs with actual patterns"""
    results = {
        'expected_urls': {},
        'url_analysis': [],
        'routing_issues': []
    }
    
    print("\n🎯 EXPECTED VS ACTUAL URL ANALYSIS")
    print("=" * 40)
    
    # Define expected URLs for fabric ID 35 (from the mission brief)
    expected_urls = {
        'fabric_detail': '/plugins/hedgehog/fabrics/35/',
        'fabric_sync': '/plugins/hedgehog/fabrics/35/sync/',
        'fabric_test_connection': '/plugins/hedgehog/fabrics/35/test-connection/',
        'fabric_github_sync': '/plugins/hedgehog/fabrics/35/github-sync/',
        'fabric_list': '/plugins/hedgehog/fabrics/',
        'overview': '/plugins/hedgehog/',
    }
    
    results['expected_urls'] = expected_urls
    
    print("Expected URL patterns:")
    for name, url in expected_urls.items():
        print(f"   {name}: {url}")
    
    # Now check what patterns are actually defined
    try:
        with open('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/urls.py', 'r') as f:
            content = f.read()
        
        # Extract URL patterns with names
        pattern_regex = r"path\(['\"]([^'\"]+)['\"].*?name=['\"]([^'\"]+)['\"]"
        actual_patterns = re.findall(pattern_regex, content, re.DOTALL)
        
        print(f"\nActual URL patterns found ({len(actual_patterns)}):")
        
        # Check if our expected patterns exist
        for expected_name, expected_url in expected_urls.items():
            found = False
            for actual_pattern, actual_name in actual_patterns:
                # Convert pattern to expected URL format
                actual_url = actual_pattern.replace('<int:pk>', '35')
                if actual_url.startswith('/'):
                    full_actual_url = f"/plugins/hedgehog{actual_url}"
                else:
                    full_actual_url = f"/plugins/hedgehog/{actual_url}"
                
                if expected_name == actual_name or expected_url == full_actual_url:
                    print(f"   ✅ {expected_name}: {actual_pattern} -> {actual_name}")
                    found = True
                    break
            
            if not found:
                print(f"   ❌ {expected_name}: NOT FOUND")
                results['routing_issues'].append(f"Missing URL pattern for {expected_name}")
        
        # List all patterns for reference
        print(f"\nAll patterns in urls.py:")
        for pattern, name in actual_patterns:
            if 'fabric' in pattern.lower() or 'sync' in pattern.lower():
                print(f"   {name}: {pattern}")
        
    except Exception as e:
        print(f"❌ Error analyzing patterns: {e}")
        results['routing_issues'].append(f"Pattern analysis failed: {e}")
    
    return results

def main():
    """Run all analyses"""
    print("🚀 URL ROUTING ANALYSIS")
    print("=" * 50)
    
    all_results = {
        'timestamp': str(datetime.now()),
        'analyses': {}
    }
    
    analyses = [
        ('URL File Analysis', analyze_urls_file),
        ('View Files Check', check_view_files),
        ('Expected vs Actual', expected_vs_actual_urls),
    ]
    
    all_issues = []
    
    for name, func in analyses:
        print(f"\n{'=' * 10} {name} {'=' * 10}")
        try:
            results = func()
            all_results['analyses'][name.lower().replace(' ', '_')] = results
            
            # Collect issues
            issues = results.get('issues_found', []) + \
                    results.get('pattern_issues', []) + \
                    results.get('missing_patterns', []) + \
                    results.get('missing_views', []) + \
                    results.get('routing_issues', [])
            
            all_issues.extend(issues)
            
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            all_issues.append(f"{name} failed: {e}")
    
    # Final summary
    print("\n" + "=" * 50)
    print("📊 ANALYSIS SUMMARY")
    print("=" * 50)
    
    if all_issues:
        print(f"❌ Found {len(all_issues)} issues:")
        for i, issue in enumerate(all_issues, 1):
            print(f"   {i:2d}. {issue}")
    else:
        print("✅ No major issues found in URL configuration")
    
    all_results['summary'] = {
        'total_issues': len(all_issues),
        'issues': all_issues
    }
    
    # Save results
    output_file = 'url_analysis_results.json'
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    return all_results

if __name__ == '__main__':
    results = main()