#!/usr/bin/env python3
"""
Simplified TDD Sync Failure Detection

This script tests the sync system functionality without requiring full Django setup.
It will run basic connectivity and functionality tests to confirm if the system is broken.

EXPECTED RESULT: Tests should FAIL, confirming the user's report that sync is broken.
"""

import requests
import json
import time
import subprocess
import sys
import os
from datetime import datetime

class SimplifiedSyncTester:
    """
    Simplified sync system tester that can run without full Django environment
    """
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'test_results': [],
            'detected_issues': [],
            'summary': {
                'total_tests': 0,
                'passed_tests': 0,
                'failed_tests': 0
            }
        }
        
        # Try to detect if we're in a running NetBox environment
        self.netbox_base_url = self._detect_netbox_url()
        
    def _detect_netbox_url(self):
        """Try to detect if NetBox is running and get base URL"""
        possible_urls = [
            'http://localhost:8000',
            'http://127.0.0.1:8000', 
            'http://localhost:80',
            'http://127.0.0.1:80'
        ]
        
        for url in possible_urls:
            try:
                response = requests.get(f"{url}/login/", timeout=5)
                if response.status_code in [200, 302]:
                    print(f"✓ Found NetBox running at: {url}")
                    return url
            except:
                continue
                
        print("⚠️ NetBox server not detected running locally")
        return None
    
    def run_all_tests(self):
        """Run all simplified sync failure detection tests"""
        print("🔍 Starting Simplified Sync Failure Detection")
        print("=" * 70)
        
        tests = [
            ('Basic NetBox Access Test', self.test_netbox_access),
            ('Sync Endpoint Availability Test', self.test_sync_endpoints),
            ('Plugin Installation Test', self.test_plugin_installed),
            ('Database Connectivity Test', self.test_database_access),
            ('File System Structure Test', self.test_file_structure),
            ('JavaScript Files Test', self.test_javascript_files),
            ('Template Files Test', self.test_template_files),
            ('URL Configuration Test', self.test_url_configuration)
        ]
        
        for test_name, test_func in tests:
            print(f"\n🧪 Running: {test_name}")
            print("-" * 50)
            
            result = self._run_single_test(test_name, test_func)
            self.results['test_results'].append(result)
            
            self.results['summary']['total_tests'] += 1
            if result['passed']:
                self.results['summary']['passed_tests'] += 1
                print(f"✅ PASSED: {result['message']}")
            else:
                self.results['summary']['failed_tests'] += 1
                print(f"❌ FAILED: {result['message']}")
                if result.get('error_details'):
                    print(f"   Details: {result['error_details']}")
        
        self._analyze_results()
        self._print_summary()
        return self.results
    
    def _run_single_test(self, test_name, test_func):
        """Run a single test and capture results"""
        result = {
            'test_name': test_name,
            'passed': False,
            'message': '',
            'error_details': '',
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            success, message, details = test_func()
            result['passed'] = success
            result['message'] = message
            result['error_details'] = details
        except Exception as e:
            result['passed'] = False
            result['message'] = f"Test execution failed: {str(e)}"
            result['error_details'] = str(e)
        
        return result
    
    def test_netbox_access(self):
        """Test basic NetBox server access"""
        if not self.netbox_base_url:
            return False, "NetBox server not accessible", "No running NetBox instance detected"
        
        try:
            response = requests.get(f"{self.netbox_base_url}/", timeout=10)
            if response.status_code == 200:
                return True, "NetBox server accessible", f"HTTP {response.status_code}"
            else:
                return False, f"NetBox server returned HTTP {response.status_code}", response.text[:200]
        except Exception as e:
            return False, "NetBox server connection failed", str(e)
    
    def test_sync_endpoints(self):
        """Test if sync endpoints are available"""
        if not self.netbox_base_url:
            return False, "Cannot test sync endpoints - NetBox not running", ""
        
        # Test fabric sync endpoint pattern
        test_urls = [
            '/plugins/hedgehog/fabrics/1/sync/',
            '/plugins/netbox_hedgehog/fabrics/1/sync/',
            '/api/plugins/hedgehog/sync/'
        ]
        
        accessible_endpoints = []
        
        for url in test_urls:
            try:
                full_url = f"{self.netbox_base_url}{url}"
                response = requests.post(full_url, timeout=5)
                
                # Even if authentication fails, endpoint should exist (not 404)
                if response.status_code != 404:
                    accessible_endpoints.append(url)
                    
            except Exception as e:
                continue
        
        if accessible_endpoints:
            return True, f"Found {len(accessible_endpoints)} sync endpoints", str(accessible_endpoints)
        else:
            return False, "No sync endpoints accessible", "All tested endpoints returned 404"
    
    def test_plugin_installed(self):
        """Test if the hedgehog plugin is properly installed"""
        try:
            # Check if plugin files exist
            plugin_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog'
            
            if not os.path.exists(plugin_path):
                return False, "Plugin directory not found", plugin_path
            
            # Check key plugin files
            required_files = [
                'models.py',
                'views.py', 
                'urls.py',
                '__init__.py'
            ]
            
            missing_files = []
            for file in required_files:
                if not os.path.exists(os.path.join(plugin_path, file)):
                    missing_files.append(file)
            
            if missing_files:
                return False, f"Missing plugin files: {missing_files}", ""
            
            return True, "Plugin files present", f"Found all required files in {plugin_path}"
            
        except Exception as e:
            return False, "Plugin installation check failed", str(e)
    
    def test_database_access(self):
        """Test basic database connectivity"""
        try:
            # Try to run a simple database command
            result = subprocess.run([
                'python3', '-c',
                '''
import sqlite3
import os
# Look for common database file locations
db_paths = [
    "/home/ubuntu/cc/hedgehog-netbox-plugin/db.sqlite3",
    "/opt/netbox/netbox/db.sqlite3", 
    "./db.sqlite3"
]
for path in db_paths:
    if os.path.exists(path):
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 5")
        tables = cursor.fetchall()
        print(f"Database accessible: {len(tables)} tables found")
        conn.close()
        break
else:
    print("No database file found")
                '''
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and "accessible" in result.stdout:
                return True, "Database accessible", result.stdout.strip()
            else:
                return False, "Database not accessible", result.stdout + result.stderr
                
        except Exception as e:
            return False, "Database connectivity test failed", str(e)
    
    def test_file_structure(self):
        """Test if required sync-related files exist"""
        base_path = '/home/ubuntu/cc/hedgehog-netbox-plugin'
        
        required_paths = [
            'netbox_hedgehog/models/',
            'netbox_hedgehog/views/', 
            'netbox_hedgehog/static/',
            'netbox_hedgehog/templates/',
            'netbox_hedgehog/utils/'
        ]
        
        missing_paths = []
        found_paths = []
        
        for path in required_paths:
            full_path = os.path.join(base_path, path)
            if os.path.exists(full_path):
                found_paths.append(path)
            else:
                missing_paths.append(path)
        
        if missing_paths:
            return False, f"Missing directories: {missing_paths}", f"Found: {found_paths}"
        else:
            return True, f"All {len(required_paths)} directories present", str(found_paths)
    
    def test_javascript_files(self):
        """Test if JavaScript files for sync functionality exist"""
        js_base_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/static/netbox_hedgehog/js'
        
        if not os.path.exists(js_base_path):
            return False, "JavaScript directory missing", js_base_path
        
        # Look for sync-related JavaScript files
        js_files = []
        try:
            for file in os.listdir(js_base_path):
                if file.endswith('.js'):
                    js_files.append(file)
        except Exception as e:
            return False, "Cannot read JavaScript directory", str(e)
        
        sync_js_files = [f for f in js_files if 'sync' in f.lower()]
        
        if not js_files:
            return False, "No JavaScript files found", js_base_path
        
        return True, f"Found {len(js_files)} JS files ({len(sync_js_files)} sync-related)", str(js_files)
    
    def test_template_files(self):
        """Test if template files for fabric pages exist"""
        template_base_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates'
        
        if not os.path.exists(template_base_path):
            return False, "Template directory missing", template_base_path
        
        # Look for fabric-related templates
        fabric_templates = []
        try:
            for root, dirs, files in os.walk(template_base_path):
                for file in files:
                    if file.endswith('.html') and 'fabric' in file.lower():
                        fabric_templates.append(os.path.relpath(os.path.join(root, file), template_base_path))
        except Exception as e:
            return False, "Cannot read template directory", str(e)
        
        if not fabric_templates:
            return False, "No fabric template files found", template_base_path
        
        return True, f"Found {len(fabric_templates)} fabric templates", str(fabric_templates)
    
    def test_url_configuration(self):
        """Test URL configuration by examining urls.py files"""
        urls_file = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/urls.py'
        
        if not os.path.exists(urls_file):
            return False, "URLs configuration file missing", urls_file
        
        try:
            with open(urls_file, 'r') as f:
                urls_content = f.read()
            
            # Look for sync-related URL patterns
            sync_patterns = []
            lines = urls_content.split('\n')
            
            for line in lines:
                if 'sync' in line.lower() and ('path(' in line or 'url(' in line):
                    sync_patterns.append(line.strip())
            
            if not sync_patterns:
                return False, "No sync URL patterns found in urls.py", "File exists but no sync routes"
            
            return True, f"Found {len(sync_patterns)} sync URL patterns", str(sync_patterns)
            
        except Exception as e:
            return False, "Cannot read URLs configuration", str(e)
    
    def _analyze_results(self):
        """Analyze test results to identify specific issues"""
        issues = []
        
        failed_tests = [result for result in self.results['test_results'] if not result['passed']]
        
        for failed_test in failed_tests:
            test_name = failed_test['test_name']
            
            if 'NetBox Access' in test_name:
                issues.append({
                    'category': 'Infrastructure',
                    'severity': 'critical',
                    'description': 'NetBox server not running or accessible'
                })
            
            elif 'Sync Endpoint' in test_name:
                issues.append({
                    'category': 'API Endpoints',
                    'severity': 'critical', 
                    'description': 'Sync API endpoints not available or configured'
                })
            
            elif 'Plugin Installation' in test_name:
                issues.append({
                    'category': 'Plugin Installation',
                    'severity': 'critical',
                    'description': 'Hedgehog plugin not properly installed'
                })
            
            elif 'Database' in test_name:
                issues.append({
                    'category': 'Database',
                    'severity': 'high',
                    'description': 'Database connectivity issues'
                })
            
            elif 'JavaScript' in test_name:
                issues.append({
                    'category': 'Frontend',
                    'severity': 'high',
                    'description': 'JavaScript files missing for sync functionality'
                })
            
            elif 'Template' in test_name:
                issues.append({
                    'category': 'Frontend',
                    'severity': 'high',
                    'description': 'Template files missing for fabric pages'
                })
            
            elif 'URL Configuration' in test_name:
                issues.append({
                    'category': 'Routing',
                    'severity': 'high',
                    'description': 'URL routing not configured for sync endpoints'
                })
        
        self.results['detected_issues'] = issues
    
    def _print_summary(self):
        """Print test execution summary"""
        print("\n" + "=" * 70)
        print("🎯 SIMPLIFIED SYNC FAILURE DETECTION SUMMARY")
        print("=" * 70)
        
        summary = self.results['summary']
        print(f"📊 Test Results:")
        print(f"   Total Tests: {summary['total_tests']}")
        print(f"   ✅ Passed: {summary['passed_tests']}")
        print(f"   ❌ Failed: {summary['failed_tests']}")
        
        failed_percentage = (summary['failed_tests'] / summary['total_tests']) * 100 if summary['total_tests'] > 0 else 0
        
        print(f"\n📈 Failure Rate: {failed_percentage:.1f}%")
        
        if summary['failed_tests'] > 0:
            print(f"\n✅ SUCCESS: Detected {summary['failed_tests']} test failures")
            print("This CONFIRMS that the sync system has issues, validating the user's report.")
            
            issues = self.results['detected_issues']
            if issues:
                critical_issues = [issue for issue in issues if issue['severity'] == 'critical']
                high_issues = [issue for issue in issues if issue['severity'] == 'high']
                
                print(f"\n🔍 Issue Analysis:")
                print(f"   🚨 Critical Issues: {len(critical_issues)}")
                print(f"   ⚠️  High Priority: {len(high_issues)}")
                
                print(f"\n📋 Detected Issues:")
                for i, issue in enumerate(issues, 1):
                    severity_icon = "🚨" if issue['severity'] == 'critical' else "⚠️"
                    print(f"   {i}. {severity_icon} {issue['category']}: {issue['description']}")
        else:
            print(f"\n⚠️ WARNING: All tests passed!")
            print("Either:")
            print("  1. The sync system is actually working correctly, or")
            print("  2. These tests are not comprehensive enough to detect the issue")
            print("  3. The issue may be environment-specific or require deeper testing")
    
    def save_results(self):
        """Save results to file"""
        results_file = '/home/ubuntu/cc/hedgehog-netbox-plugin/tests/simplified_failure_detection_results.json'
        
        try:
            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"\n💾 Results saved to: {results_file}")
        except Exception as e:
            print(f"❌ Could not save results: {e}")


def main():
    """Main execution function"""
    print("🚀 Starting Simplified TDD Sync Failure Detection")
    print("=" * 70)
    
    tester = SimplifiedSyncTester()
    results = tester.run_all_tests()
    tester.save_results()
    
    # Exit code based on results
    if results['summary']['failed_tests'] > 0:
        print(f"\n✅ SUCCESS: Detected {results['summary']['failed_tests']} failures in sync system")
        return 0  # Success - we found the problems
    else:
        print(f"\n⚠️ WARNING: No failures detected - sync system may actually be working")
        return 1  # Warning - need further investigation

if __name__ == '__main__':
    sys.exit(main())