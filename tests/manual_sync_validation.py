#!/usr/bin/env python3
"""
Manual Sync Validation Script

This script performs manual validation of sync functionality by:
1. Making direct HTTP requests to sync endpoints
2. Analyzing response codes and content
3. Checking file system for required components
4. Testing configuration files
"""

import requests
import json
import os
import re
import subprocess
from datetime import datetime
import sys

class ManualSyncValidator:
    """Manual validation of sync system functionality"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tests_performed': [],
            'evidence_collected': [],
            'detected_failures': [],
            'summary': {}
        }
        
    def validate_sync_endpoints(self):
        """Test sync endpoints with manual HTTP requests"""
        print("🔍 Testing Sync Endpoints...")
        
        # Test various sync endpoint patterns
        endpoints_to_test = [
            '/plugins/hedgehog/fabrics/',
            '/plugins/hedgehog/fabrics/1/sync/',
            '/plugins/netbox_hedgehog/fabrics/',
            '/plugins/netbox_hedgehog/fabrics/1/sync/',
            '/api/plugins/hedgehog/sync/',
            '/hedgehog/sync/'
        ]
        
        endpoint_results = []
        
        for endpoint in endpoints_to_test:
            try:
                url = f"{self.base_url}{endpoint}"
                
                # Test GET request
                get_response = requests.get(url, timeout=10)
                
                # Test POST request  
                post_response = requests.post(url, timeout=10)
                
                result = {
                    'endpoint': endpoint,
                    'get_status': get_response.status_code,
                    'post_status': post_response.status_code,
                    'get_accessible': get_response.status_code != 404,
                    'post_accessible': post_response.status_code != 404,
                    'contains_sync_content': 'sync' in get_response.text.lower()
                }
                
                endpoint_results.append(result)
                
                if result['get_accessible'] or result['post_accessible']:
                    print(f"  ✓ {endpoint} - GET:{get_response.status_code}, POST:{post_response.status_code}")
                else:
                    print(f"  ✗ {endpoint} - Both GET/POST return 404")
                    
            except Exception as e:
                endpoint_results.append({
                    'endpoint': endpoint,
                    'error': str(e),
                    'accessible': False
                })
                print(f"  ✗ {endpoint} - Connection error: {e}")
        
        self.results['tests_performed'].append({
            'test_name': 'Sync Endpoints Validation',
            'results': endpoint_results
        })
        
        # Analyze results
        accessible_endpoints = [r for r in endpoint_results if r.get('get_accessible') or r.get('post_accessible')]
        
        if not accessible_endpoints:
            self.results['detected_failures'].append({
                'category': 'API Endpoints',
                'severity': 'critical',
                'description': 'No sync endpoints are accessible',
                'evidence': endpoint_results
            })
            return False
        
        print(f"  📊 Found {len(accessible_endpoints)} accessible sync endpoints")
        return True
    
    def validate_plugin_files(self):
        """Validate plugin file structure and content"""
        print("📁 Validating Plugin Files...")
        
        base_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog'
        
        # Check critical files
        critical_files = {
            'models/__init__.py': 'Model definitions',
            'models/fabric.py': 'Fabric model',
            'views/fabric_views.py': 'Fabric views',
            'views/sync_views.py': 'Sync views', 
            'urls.py': 'URL routing',
            '__init__.py': 'Plugin init'
        }
        
        file_status = {}
        
        for file_path, description in critical_files.items():
            full_path = os.path.join(base_path, file_path)
            
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r') as f:
                        content = f.read()
                    
                    # Analyze content for sync-related functionality
                    sync_mentions = len(re.findall(r'sync', content, re.IGNORECASE))
                    
                    file_status[file_path] = {
                        'exists': True,
                        'size': len(content),
                        'sync_mentions': sync_mentions,
                        'has_content': len(content.strip()) > 0
                    }
                    
                    print(f"  ✓ {file_path} - {len(content)} bytes, {sync_mentions} sync mentions")
                    
                except Exception as e:
                    file_status[file_path] = {
                        'exists': True,
                        'error': str(e)
                    }
                    print(f"  ⚠ {file_path} - exists but cannot read: {e}")
            else:
                file_status[file_path] = {'exists': False}
                print(f"  ✗ {file_path} - missing")
        
        self.results['tests_performed'].append({
            'test_name': 'Plugin Files Validation',
            'results': file_status
        })
        
        # Identify missing critical files
        missing_files = [path for path, status in file_status.items() if not status['exists']]
        
        if missing_files:
            self.results['detected_failures'].append({
                'category': 'Plugin Installation',
                'severity': 'critical',
                'description': f'Missing critical plugin files: {missing_files}',
                'evidence': file_status
            })
            return False
        
        return True
    
    def validate_static_files(self):
        """Validate JavaScript and CSS files"""
        print("🎨 Validating Static Files...")
        
        static_base = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/static/netbox_hedgehog'
        
        static_results = {
            'javascript_files': [],
            'css_files': [],
            'sync_related_files': []
        }
        
        # Check JavaScript files
        js_path = os.path.join(static_base, 'js')
        if os.path.exists(js_path):
            try:
                js_files = [f for f in os.listdir(js_path) if f.endswith('.js')]
                
                for js_file in js_files:
                    js_file_path = os.path.join(js_path, js_file)
                    try:
                        with open(js_file_path, 'r') as f:
                            content = f.read()
                        
                        sync_functions = len(re.findall(r'function.*sync|sync.*function', content, re.IGNORECASE))
                        ajax_calls = len(re.findall(r'ajax|fetch|XMLHttpRequest', content, re.IGNORECASE))
                        
                        file_info = {
                            'filename': js_file,
                            'size': len(content),
                            'sync_functions': sync_functions,
                            'ajax_calls': ajax_calls,
                            'is_sync_related': 'sync' in js_file.lower() or sync_functions > 0
                        }
                        
                        static_results['javascript_files'].append(file_info)
                        
                        if file_info['is_sync_related']:
                            static_results['sync_related_files'].append(file_info)
                            print(f"  ✓ JS: {js_file} - {sync_functions} sync functions, {ajax_calls} AJAX calls")
                        
                    except Exception as e:
                        print(f"  ⚠ JS: {js_file} - cannot read: {e}")
                        
            except Exception as e:
                print(f"  ✗ Cannot access JavaScript directory: {e}")
        
        # Check CSS files
        css_path = os.path.join(static_base, 'css')
        if os.path.exists(css_path):
            try:
                css_files = [f for f in os.listdir(css_path) if f.endswith('.css')]
                
                for css_file in css_files:
                    css_file_path = os.path.join(css_path, css_file)
                    try:
                        with open(css_file_path, 'r') as f:
                            content = f.read()
                        
                        static_results['css_files'].append({
                            'filename': css_file,
                            'size': len(content),
                            'is_sync_related': 'sync' in css_file.lower()
                        })
                        
                    except Exception as e:
                        print(f"  ⚠ CSS: {css_file} - cannot read: {e}")
                        
            except Exception as e:
                print(f"  ✗ Cannot access CSS directory: {e}")
        
        self.results['tests_performed'].append({
            'test_name': 'Static Files Validation',
            'results': static_results
        })
        
        # Check if we have sync-related JavaScript
        if not static_results['sync_related_files']:
            self.results['detected_failures'].append({
                'category': 'Frontend Assets',
                'severity': 'high',
                'description': 'No sync-related JavaScript files found',
                'evidence': static_results
            })
            return False
        
        print(f"  📊 Found {len(static_results['sync_related_files'])} sync-related JS files")
        return True
    
    def validate_database_models(self):
        """Check if sync-related database tables exist"""
        print("💾 Validating Database Structure...")
        
        # Try to find and examine database file
        potential_db_paths = [
            '/home/ubuntu/cc/hedgehog-netbox-plugin/db.sqlite3',
            '/opt/netbox/netbox/db.sqlite3',
            './db.sqlite3',
            '/var/lib/netbox/db.sqlite3'
        ]
        
        db_results = {
            'database_found': False,
            'database_path': None,
            'tables': [],
            'hedgehog_tables': []
        }
        
        for db_path in potential_db_paths:
            if os.path.exists(db_path):
                db_results['database_found'] = True
                db_results['database_path'] = db_path
                print(f"  ✓ Found database: {db_path}")
                
                try:
                    # Use sqlite3 command to check tables
                    result = subprocess.run([
                        'sqlite3', db_path, 
                        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%hedgehog%' OR name LIKE '%fabric%';"
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        tables = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                        db_results['tables'] = tables
                        
                        hedgehog_tables = [t for t in tables if 'hedgehog' in t.lower()]
                        db_results['hedgehog_tables'] = hedgehog_tables
                        
                        print(f"  📊 Found {len(hedgehog_tables)} hedgehog-related tables")
                        for table in hedgehog_tables:
                            print(f"    - {table}")
                    else:
                        print(f"  ⚠ Cannot query database: {result.stderr}")
                        
                except Exception as e:
                    print(f"  ⚠ Database query error: {e}")
                
                break
        
        self.results['tests_performed'].append({
            'test_name': 'Database Structure Validation',
            'results': db_results
        })
        
        if not db_results['database_found']:
            self.results['detected_failures'].append({
                'category': 'Database',
                'severity': 'high', 
                'description': 'No database file found',
                'evidence': db_results
            })
            return False
        
        if not db_results['hedgehog_tables']:
            self.results['detected_failures'].append({
                'category': 'Database',
                'severity': 'critical',
                'description': 'No hedgehog-related database tables found',
                'evidence': db_results
            })
            return False
        
        return True
    
    def validate_configuration(self):
        """Check plugin configuration and settings"""
        print("⚙️ Validating Configuration...")
        
        config_results = {
            'setup_py_exists': False,
            'urls_configured': False,
            'views_configured': False
        }
        
        # Check setup.py
        setup_py_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/setup.py'
        if os.path.exists(setup_py_path):
            config_results['setup_py_exists'] = True
            print("  ✓ setup.py exists")
        else:
            print("  ✗ setup.py missing")
        
        # Check URLs configuration
        urls_py_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/urls.py'
        if os.path.exists(urls_py_path):
            try:
                with open(urls_py_path, 'r') as f:
                    urls_content = f.read()
                
                sync_patterns = len(re.findall(r'sync', urls_content, re.IGNORECASE))
                if sync_patterns > 0:
                    config_results['urls_configured'] = True
                    print(f"  ✓ URLs configured with {sync_patterns} sync patterns")
                else:
                    print("  ⚠ URLs file exists but no sync patterns found")
                    
            except Exception as e:
                print(f"  ⚠ Cannot read URLs file: {e}")
        else:
            print("  ✗ urls.py missing")
        
        self.results['tests_performed'].append({
            'test_name': 'Configuration Validation',
            'results': config_results
        })
        
        missing_configs = [key for key, value in config_results.items() if not value]
        
        if missing_configs:
            self.results['detected_failures'].append({
                'category': 'Configuration',
                'severity': 'high',
                'description': f'Missing configurations: {missing_configs}',
                'evidence': config_results
            })
            return False
        
        return True
    
    def generate_failure_report(self):
        """Generate comprehensive failure report"""
        print("\n" + "=" * 70)
        print("📋 MANUAL SYNC VALIDATION REPORT")
        print("=" * 70)
        
        total_tests = len(self.results['tests_performed'])
        total_failures = len(self.results['detected_failures'])
        
        print(f"🧪 Tests Performed: {total_tests}")
        print(f"❌ Failures Detected: {total_failures}")
        
        if total_failures > 0:
            print(f"\n🚨 SYNC SYSTEM FAILURES CONFIRMED:")
            
            for i, failure in enumerate(self.results['detected_failures'], 1):
                severity_icon = "🚨" if failure['severity'] == 'critical' else "⚠️"
                print(f"{i}. {severity_icon} {failure['category']}: {failure['description']}")
        
        # Categorize failures
        critical_failures = [f for f in self.results['detected_failures'] if f['severity'] == 'critical']
        high_failures = [f for f in self.results['detected_failures'] if f['severity'] == 'high']
        
        self.results['summary'] = {
            'total_tests': total_tests,
            'total_failures': total_failures,
            'critical_failures': len(critical_failures),
            'high_failures': len(high_failures),
            'failure_rate': (total_failures / total_tests) * 100 if total_tests > 0 else 0
        }
        
        print(f"\n📊 Failure Analysis:")
        print(f"   🚨 Critical: {len(critical_failures)}")
        print(f"   ⚠️ High: {len(high_failures)}")
        print(f"   📈 Failure Rate: {self.results['summary']['failure_rate']:.1f}%")
        
        if total_failures > 0:
            print(f"\n✅ SUCCESS: Manual validation CONFIRMED {total_failures} sync system failures")
            print("This validates the user's report that sync functionality is broken.")
        else:
            print(f"\n⚠️ WARNING: No failures detected in manual validation")
            print("Either sync system is working or deeper testing is needed.")
        
        return self.results['summary']
    
    def save_results(self):
        """Save validation results"""
        results_file = '/home/ubuntu/cc/hedgehog-netbox-plugin/tests/manual_sync_validation_results.json'
        
        try:
            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"\n💾 Full validation results saved to: {results_file}")
        except Exception as e:
            print(f"❌ Could not save results: {e}")
    
    def run_full_validation(self):
        """Run complete manual validation suite"""
        print("🚀 Starting Manual Sync System Validation")
        print("=" * 70)
        
        validation_tests = [
            ('Sync Endpoints', self.validate_sync_endpoints),
            ('Plugin Files', self.validate_plugin_files),
            ('Static Files', self.validate_static_files),
            ('Database Structure', self.validate_database_models),
            ('Configuration', self.validate_configuration)
        ]
        
        passed_tests = 0
        
        for test_name, test_func in validation_tests:
            print(f"\n📋 {test_name} Validation")
            print("-" * 50)
            
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                print(f"  ❌ Validation error: {e}")
                self.results['detected_failures'].append({
                    'category': test_name,
                    'severity': 'high',
                    'description': f'Validation test failed with error: {e}',
                    'evidence': {'error': str(e)}
                })
        
        summary = self.generate_failure_report()
        self.save_results()
        
        return summary

def main():
    """Main execution"""
    validator = ManualSyncValidator()
    summary = validator.run_full_validation()
    
    # Return appropriate exit code
    if summary['total_failures'] > 0:
        return 0  # Success - we found the problems as expected
    else:
        return 1  # Warning - no problems found

if __name__ == '__main__':
    sys.exit(main())