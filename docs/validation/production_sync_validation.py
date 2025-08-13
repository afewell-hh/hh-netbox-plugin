#!/usr/bin/env python3
"""
Production Sync Validation Script
Tests the actual sync fixes claimed by the implementation team
"""

import requests
import time
import json
import sys
import os
from datetime import datetime

# Add the Django project path
sys.path.insert(0, '/opt/netbox')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

import django
django.setup()

from netbox_hedgehog.models import HedgehogFabric

class ProductionSyncValidator:
    def __init__(self, container_name='b05eb5eff181'):
        self.container = container_name
        self.base_url = 'http://localhost:8000'
        self.session = requests.Session()
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'container': container_name,
            'tests': []
        }
        
    def login_to_netbox(self):
        """Login to NetBox to get session"""
        try:
            # Get login page first to get CSRF token
            login_page = self.session.get(f'{self.base_url}/login/')
            if login_page.status_code != 200:
                return False, f"Cannot reach NetBox login page: {login_page.status_code}"
                
            # Extract CSRF token from login form
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(login_page.content, 'html.parser')
            csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
            
            if not csrf_token:
                return False, "Cannot find CSRF token in login form"
                
            # Attempt login with default credentials
            login_data = {
                'username': 'admin',
                'password': 'admin',
                'csrfmiddlewaretoken': csrf_token['value']
            }
            
            login_response = self.session.post(f'{self.base_url}/login/', data=login_data)
            if 'logout' in login_response.text or login_response.url.endswith('/'):
                return True, "Successfully logged in"
            else:
                return False, "Login failed - check credentials"
                
        except Exception as e:
            return False, f"Login exception: {e}"
    
    def get_fabric_for_testing(self):
        """Get or create a fabric for testing"""
        try:
            # Try to get existing fabric
            fabric = HedgehogFabric.objects.filter(
                kubernetes_server__isnull=False
            ).first()
            
            if fabric:
                return fabric, "Using existing configured fabric"
            
            # Create test fabric if none exists
            fabric = HedgehogFabric.objects.create(
                name='test-validation-fabric',
                kubernetes_server='https://vlab-art.l.hhdev.io:6443',
                kubernetes_namespace='default',
                sync_enabled=True,
                sync_interval=60
            )
            return fabric, "Created new test fabric"
            
        except Exception as e:
            return None, f"Fabric setup failed: {e}"
    
    def test_connection(self, fabric):
        """Test Kubernetes connection"""
        test_result = {
            'test': 'connection_test',
            'fabric_id': fabric.id,
            'fabric_name': fabric.name,
            'start_time': time.time(),
            'success': False,
            'error': None,
            'details': {}
        }
        
        try:
            # Test connection via HTTP API
            response = self.session.post(
                f'{self.base_url}/plugins/hedgehog/simple-test/{fabric.id}/',
                timeout=45  # Allow up to 45 seconds for connection test
            )
            
            test_result['http_status'] = response.status_code
            test_result['duration'] = time.time() - test_result['start_time']
            
            if response.status_code == 200:
                data = response.json()
                test_result['success'] = data.get('success', False)
                test_result['details'] = data.get('details', {})
                if not test_result['success']:
                    test_result['error'] = data.get('error', 'Unknown error')
            else:
                test_result['error'] = f"HTTP {response.status_code}: {response.text[:200]}"
                
        except Exception as e:
            test_result['error'] = str(e)
            test_result['duration'] = time.time() - test_result['start_time']
        
        self.results['tests'].append(test_result)
        return test_result
    
    def test_manual_sync(self, fabric):
        """Test manual sync operation"""
        sync_result = {
            'test': 'manual_sync',
            'fabric_id': fabric.id,
            'fabric_name': fabric.name,
            'start_time': time.time(),
            'success': False,
            'error': None,
            'details': {},
            'timeout_test': False
        }
        
        try:
            print(f"Starting manual sync test for fabric {fabric.name}...")
            
            # Record pre-sync state
            fabric.refresh_from_db()
            pre_sync_state = {
                'sync_status': fabric.sync_status,
                'last_sync': fabric.last_sync.isoformat() if fabric.last_sync else None,
                'sync_error': fabric.sync_error
            }
            sync_result['pre_sync_state'] = pre_sync_state
            
            # Trigger manual sync
            response = self.session.post(
                f'{self.base_url}/plugins/hedgehog/simple-sync/{fabric.id}/',
                timeout=45  # Test that sync completes within 45 seconds (not 2+ minutes)
            )
            
            sync_result['duration'] = time.time() - sync_result['start_time']
            sync_result['http_status'] = response.status_code
            
            # Check if we completed within timeout expectations
            if sync_result['duration'] <= 30:
                sync_result['timeout_test'] = True  # PASS: Under 30 seconds
                print(f"✅ Sync completed in {sync_result['duration']:.1f} seconds (under 30s limit)")
            else:
                sync_result['timeout_test'] = False  # FAIL: Over 30 seconds
                print(f"❌ Sync took {sync_result['duration']:.1f} seconds (over 30s limit)")
            
            if response.status_code == 200:
                data = response.json()
                sync_result['success'] = data.get('success', False)
                sync_result['details'] = data.get('stats', {})
                sync_result['message'] = data.get('message', '')
                
                if not sync_result['success']:
                    sync_result['error'] = data.get('error', 'Unknown sync error')
            else:
                sync_result['error'] = f"HTTP {response.status_code}: {response.text[:200]}"
            
            # Record post-sync state
            fabric.refresh_from_db()
            post_sync_state = {
                'sync_status': fabric.sync_status,
                'last_sync': fabric.last_sync.isoformat() if fabric.last_sync else None,
                'sync_error': fabric.sync_error,
                'cached_crd_count': getattr(fabric, 'cached_crd_count', 0)
            }
            sync_result['post_sync_state'] = post_sync_state
            
        except requests.Timeout:
            sync_result['error'] = "Sync timed out after 45 seconds"
            sync_result['duration'] = time.time() - sync_result['start_time']
            sync_result['timeout_test'] = False  # FAIL: Timed out
            print(f"❌ Sync timed out after {sync_result['duration']:.1f} seconds")
            
        except Exception as e:
            sync_result['error'] = str(e)
            sync_result['duration'] = time.time() - sync_result['start_time']
            print(f"❌ Sync failed with exception: {e}")
        
        self.results['tests'].append(sync_result)
        return sync_result
    
    def monitor_periodic_sync(self, fabric, monitoring_duration=300):
        """Monitor periodic sync for 5 minutes"""
        monitor_result = {
            'test': 'periodic_sync_monitor',
            'fabric_id': fabric.id,
            'fabric_name': fabric.name,
            'monitoring_duration': monitoring_duration,
            'start_time': time.time(),
            'sync_observations': [],
            'success': False,
            'error': None
        }
        
        try:
            print(f"Monitoring periodic sync for {monitoring_duration} seconds...")
            initial_sync_time = fabric.last_sync
            
            start_monitoring = time.time()
            while time.time() - start_monitoring < monitoring_duration:
                fabric.refresh_from_db()
                current_time = time.time() - start_monitoring
                
                # Check if sync time has updated
                if fabric.last_sync and (not initial_sync_time or fabric.last_sync > initial_sync_time):
                    observation = {
                        'elapsed_time': current_time,
                        'sync_timestamp': fabric.last_sync.isoformat(),
                        'sync_status': fabric.sync_status,
                        'sync_error': fabric.sync_error
                    }
                    monitor_result['sync_observations'].append(observation)
                    print(f"📊 Periodic sync detected at {current_time:.1f}s: {fabric.sync_status}")
                    initial_sync_time = fabric.last_sync
                
                time.sleep(10)  # Check every 10 seconds
            
            # Determine success based on observations
            if len(monitor_result['sync_observations']) > 0:
                monitor_result['success'] = True
                print(f"✅ Detected {len(monitor_result['sync_observations'])} periodic sync(s)")
            else:
                monitor_result['success'] = False
                monitor_result['error'] = f"No periodic syncs detected in {monitoring_duration}s"
                print(f"❌ No periodic syncs detected in {monitoring_duration} seconds")
                
        except Exception as e:
            monitor_result['error'] = str(e)
            print(f"❌ Periodic sync monitoring failed: {e}")
        
        monitor_result['duration'] = time.time() - monitor_result['start_time']
        self.results['tests'].append(monitor_result)
        return monitor_result
    
    def test_k8s_connectivity(self, fabric):
        """Test actual Kubernetes connectivity"""
        k8s_result = {
            'test': 'k8s_connectivity',
            'fabric_id': fabric.id,
            'fabric_name': fabric.name,
            'start_time': time.time(),
            'success': False,
            'error': None,
            'details': {}
        }
        
        try:
            print(f"Testing Kubernetes connectivity to {fabric.kubernetes_server}...")
            
            # Test direct connectivity
            import socket
            import ssl
            from urllib.parse import urlparse
            
            parsed_url = urlparse(fabric.kubernetes_server)
            host = parsed_url.hostname
            port = parsed_url.port or 443
            
            # Test TCP connection
            sock = socket.create_connection((host, port), timeout=10)
            k8s_result['tcp_connection'] = True
            
            # Test SSL handshake
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                k8s_result['ssl_handshake'] = True
                k8s_result['ssl_version'] = ssock.version()
            
            k8s_result['success'] = True
            k8s_result['details']['host'] = host
            k8s_result['details']['port'] = port
            
        except Exception as e:
            k8s_result['error'] = str(e)
            print(f"❌ Kubernetes connectivity failed: {e}")
        
        k8s_result['duration'] = time.time() - k8s_result['start_time']
        self.results['tests'].append(k8s_result)
        return k8s_result
    
    def generate_report(self):
        """Generate comprehensive validation report"""
        report = {
            'summary': {
                'timestamp': self.results['timestamp'],
                'total_tests': len(self.results['tests']),
                'passed_tests': len([t for t in self.results['tests'] if t['success']]),
                'failed_tests': len([t for t in self.results['tests'] if not t['success']])
            },
            'user_problem_validation': {},
            'detailed_results': self.results['tests']
        }
        
        # Validate against original user problems
        for test in self.results['tests']:
            if test['test'] == 'manual_sync':
                # Problem 1: Manual "Sync Now" button fails
                problem1_resolved = test['success'] and test.get('timeout_test', False)
                report['user_problem_validation']['manual_sync_button'] = {
                    'original_problem': 'Manual "Sync Now" button fails with error messages',
                    'resolved': problem1_resolved,
                    'evidence': {
                        'sync_completed': test['success'],
                        'under_30_seconds': test.get('timeout_test', False),
                        'duration': test.get('duration', 0),
                        'error': test.get('error')
                    }
                }
                
                # Problem 3: Sync operations hang for 2+ minutes
                problem3_resolved = test.get('duration', 999) < 120  # Under 2 minutes
                report['user_problem_validation']['no_timeout_hangs'] = {
                    'original_problem': 'Sync operations hang for 2+ minutes',
                    'resolved': problem3_resolved,
                    'evidence': {
                        'duration': test.get('duration', 0),
                        'under_2_minutes': problem3_resolved,
                        'timeout_occurred': test.get('error', '').lower().find('timeout') >= 0
                    }
                }
            
            elif test['test'] == 'periodic_sync_monitor':
                # Problem 2: Fabric not syncing at 60-second periodic interval
                problem2_resolved = test['success'] and len(test.get('sync_observations', [])) > 0
                report['user_problem_validation']['periodic_sync_interval'] = {
                    'original_problem': 'Fabric not syncing at 60-second periodic interval',
                    'resolved': problem2_resolved,
                    'evidence': {
                        'periodic_syncs_detected': len(test.get('sync_observations', [])),
                        'monitoring_duration': test.get('monitoring_duration', 0),
                        'sync_observations': test.get('sync_observations', [])
                    }
                }
        
        # Overall validation status
        all_problems = list(report['user_problem_validation'].values())
        problems_resolved = len([p for p in all_problems if p.get('resolved', False)])
        total_problems = len(all_problems)
        
        report['overall_validation'] = {
            'status': 'PASSED' if problems_resolved == total_problems else 'FAILED',
            'problems_resolved': problems_resolved,
            'total_problems': total_problems,
            'success_rate': f"{problems_resolved}/{total_problems}"
        }
        
        return report
    
    def run_validation(self):
        """Run complete validation suite"""
        print("🔍 PRODUCTION SYNC VALIDATION STARTING...")
        print("=" * 60)
        
        # Step 1: Login
        print("\n1️⃣ Authenticating with NetBox...")
        login_success, login_msg = self.login_to_netbox()
        if not login_success:
            print(f"❌ Login failed: {login_msg}")
            return None
        print(f"✅ {login_msg}")
        
        # Step 2: Get fabric
        print("\n2️⃣ Setting up test fabric...")
        fabric, setup_msg = self.get_fabric_for_testing()
        if not fabric:
            print(f"❌ Fabric setup failed: {setup_msg}")
            return None
        print(f"✅ {setup_msg} - ID: {fabric.id}, Name: {fabric.name}")
        
        # Step 3: Test connection
        print("\n3️⃣ Testing Kubernetes connection...")
        conn_result = self.test_connection(fabric)
        if conn_result['success']:
            print(f"✅ Connection successful in {conn_result['duration']:.1f}s")
        else:
            print(f"❌ Connection failed: {conn_result['error']}")
        
        # Step 4: Test manual sync
        print("\n4️⃣ Testing manual sync functionality...")
        sync_result = self.test_manual_sync(fabric)
        
        # Step 5: Test K8s connectivity
        print("\n5️⃣ Testing direct Kubernetes connectivity...")
        k8s_result = self.test_k8s_connectivity(fabric)
        
        # Step 6: Monitor periodic sync (shorter duration for validation)
        print("\n6️⃣ Monitoring periodic sync (2 minutes)...")
        periodic_result = self.monitor_periodic_sync(fabric, monitoring_duration=120)
        
        # Generate final report
        print("\n7️⃣ Generating validation report...")
        report = self.generate_report()
        
        # Save results
        with open('/tmp/production_validation_results.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print("\n" + "=" * 60)
        print("🔍 PRODUCTION SYNC VALIDATION COMPLETE")
        print(f"📊 Status: {report['overall_validation']['status']}")
        print(f"📈 Success Rate: {report['overall_validation']['success_rate']}")
        
        return report

if __name__ == '__main__':
    validator = ProductionSyncValidator()
    report = validator.run_validation()
    
    if report:
        print("\n📋 VALIDATION SUMMARY:")
        for problem, details in report['user_problem_validation'].items():
            status = "✅ RESOLVED" if details['resolved'] else "❌ NOT RESOLVED"
            print(f"  {problem}: {status}")
        
        print(f"\n💾 Full results saved to: /tmp/production_validation_results.json")
        sys.exit(0 if report['overall_validation']['status'] == 'PASSED' else 1)
    else:
        print("❌ Validation failed to complete")
        sys.exit(1)