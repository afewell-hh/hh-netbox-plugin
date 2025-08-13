#!/usr/bin/env python3
"""
Session Timeout UX Validation Script
Tests the improved authentication handling for sync operations.
"""

import json
import requests
import time
import sys
from datetime import datetime


class SessionTimeoutValidator:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.evidence = []
        
    def log_evidence(self, test_name, success, details):
        """Log test evidence for validation"""
        evidence = {
            'timestamp': datetime.now().isoformat(),
            'test': test_name,
            'success': success,
            'details': details
        }
        self.evidence.append(evidence)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details.get('message', 'No details')}")
        
    def test_authenticated_sync(self):
        """Test sync operation with valid authentication"""
        test_name = "Authenticated Sync Request"
        
        try:
            # First login to get authenticated session
            login_data = {
                'username': 'admin',
                'password': 'admin'
            }
            
            login_response = self.session.post(
                f"{self.base_url}/login/",
                data=login_data,
                allow_redirects=False
            )
            
            if login_response.status_code not in [200, 302]:
                self.log_evidence(test_name, False, {
                    'message': f'Login failed with status {login_response.status_code}',
                    'response': login_response.text[:200]
                })
                return
            
            # Test authenticated sync request
            sync_response = self.session.post(
                f"{self.base_url}/plugins/hedgehog/fabrics/1/sync/",
                headers={'X-Requested-With': 'XMLHttpRequest'},
                json={}
            )
            
            if sync_response.status_code == 401:
                self.log_evidence(test_name, False, {
                    'message': 'Got 401 response even when authenticated',
                    'status_code': sync_response.status_code
                })
                return
            
            # Success if we get any response other than 401
            self.log_evidence(test_name, True, {
                'message': f'Authenticated request returned {sync_response.status_code}',
                'status_code': sync_response.status_code
            })
            
        except Exception as e:
            self.log_evidence(test_name, False, {
                'message': f'Test failed with exception: {str(e)}',
                'error': str(e)
            })
    
    def test_unauthenticated_sync(self):
        """Test sync operation without authentication"""
        test_name = "Unauthenticated Sync JSON Response"
        
        try:
            # Create new session without authentication
            unauth_session = requests.Session()
            
            # Test sync request without authentication
            sync_response = unauth_session.post(
                f"{self.base_url}/plugins/hedgehog/fabrics/1/sync/",
                headers={'X-Requested-With': 'XMLHttpRequest'},
                json={}
            )
            
            # Should get 401 status
            if sync_response.status_code != 401:
                self.log_evidence(test_name, False, {
                    'message': f'Expected 401 status, got {sync_response.status_code}',
                    'status_code': sync_response.status_code
                })
                return
            
            # Check if response is JSON
            try:
                response_json = sync_response.json()
                
                # Check for expected fields
                expected_fields = ['success', 'error', 'requires_login']
                missing_fields = [field for field in expected_fields if field not in response_json]
                
                if missing_fields:
                    self.log_evidence(test_name, False, {
                        'message': f'JSON response missing fields: {missing_fields}',
                        'response': response_json
                    })
                    return
                
                # Check field values
                if response_json.get('success') is not False:
                    self.log_evidence(test_name, False, {
                        'message': 'success field should be False',
                        'response': response_json
                    })
                    return
                
                if not response_json.get('requires_login'):
                    self.log_evidence(test_name, False, {
                        'message': 'requires_login field should be True',
                        'response': response_json
                    })
                    return
                
                self.log_evidence(test_name, True, {
                    'message': 'Proper JSON error response for unauthenticated request',
                    'response': response_json
                })
                
            except json.JSONDecodeError:
                self.log_evidence(test_name, False, {
                    'message': 'Response is not valid JSON - likely HTML login page',
                    'content_type': sync_response.headers.get('content-type', 'unknown'),
                    'response_preview': sync_response.text[:200]
                })
                
        except Exception as e:
            self.log_evidence(test_name, False, {
                'message': f'Test failed with exception: {str(e)}',
                'error': str(e)
            })
    
    def test_session_expired_scenario(self):
        """Test behavior when session expires mid-operation"""
        test_name = "Session Expiry Detection"
        
        try:
            # Login and get authenticated session
            login_data = {
                'username': 'admin',
                'password': 'admin'
            }
            
            self.session.post(f"{self.base_url}/login/", data=login_data)
            
            # Clear session cookies to simulate expiry
            self.session.cookies.clear()
            
            # Test sync request with expired session
            sync_response = self.session.post(
                f"{self.base_url}/plugins/hedgehog/fabrics/1/sync/",
                headers={'X-Requested-With': 'XMLHttpRequest'},
                json={}
            )
            
            if sync_response.status_code == 401:
                try:
                    response_json = sync_response.json()
                    self.log_evidence(test_name, True, {
                        'message': 'Session expiry properly detected and JSON returned',
                        'response': response_json
                    })
                except json.JSONDecodeError:
                    self.log_evidence(test_name, False, {
                        'message': 'Got 401 but response is not JSON',
                        'response_preview': sync_response.text[:200]
                    })
            else:
                self.log_evidence(test_name, False, {
                    'message': f'Expected 401 for expired session, got {sync_response.status_code}',
                    'status_code': sync_response.status_code
                })
                
        except Exception as e:
            self.log_evidence(test_name, False, {
                'message': f'Test failed with exception: {str(e)}',
                'error': str(e)
            })
    
    def test_github_sync_endpoint(self):
        """Test GitHub sync endpoint authentication handling"""
        test_name = "GitHub Sync Authentication"
        
        try:
            unauth_session = requests.Session()
            
            sync_response = unauth_session.post(
                f"{self.base_url}/plugins/hedgehog/fabrics/1/github-sync/",
                headers={'X-Requested-With': 'XMLHttpRequest'},
                json={}
            )
            
            if sync_response.status_code == 401:
                try:
                    response_json = sync_response.json()
                    self.log_evidence(test_name, True, {
                        'message': 'GitHub sync endpoint properly handles auth',
                        'response': response_json
                    })
                except json.JSONDecodeError:
                    self.log_evidence(test_name, False, {
                        'message': 'GitHub sync returned 401 but not JSON',
                        'response_preview': sync_response.text[:200]
                    })
            else:
                self.log_evidence(test_name, False, {
                    'message': f'GitHub sync unexpected status: {sync_response.status_code}',
                    'status_code': sync_response.status_code
                })
                
        except Exception as e:
            self.log_evidence(test_name, False, {
                'message': f'Test failed with exception: {str(e)}',
                'error': str(e)
            })
    
    def run_all_tests(self):
        """Run all validation tests"""
        print("🧪 Running Session Timeout UX Validation Tests")
        print("=" * 60)
        
        tests = [
            self.test_unauthenticated_sync,
            self.test_session_expired_scenario,  
            self.test_github_sync_endpoint,
            self.test_authenticated_sync
        ]
        
        for test in tests:
            test()
            time.sleep(0.5)  # Brief pause between tests
            
        print("\n" + "=" * 60)
        print("📊 Test Summary")
        
        passed = sum(1 for e in self.evidence if e['success'])
        total = len(self.evidence)
        
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {total - passed}")
        print(f"📈 Success Rate: {passed/total*100:.1f}%")
        
        # Save evidence
        evidence_file = f"auth_error_handling_validation_{int(time.time())}.json"
        with open(evidence_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total_tests': total,
                    'passed': passed,
                    'failed': total - passed,
                    'success_rate': f"{passed/total*100:.1f}%"
                },
                'test_results': self.evidence
            }, f, indent=2)
        
        print(f"📁 Evidence saved to: {evidence_file}")
        
        return passed == total


if __name__ == "__main__":
    validator = SessionTimeoutValidator()
    success = validator.run_all_tests()
    sys.exit(0 if success else 1)