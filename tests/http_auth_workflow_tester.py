#!/usr/bin/env python3
"""
HTTP-WORKFLOW-TESTER: Phase 2 Authentication Testing Suite

Critical Mission: Live system testing to validate Phase 1 findings and identify exact failure mechanisms.

Phase 1 Critical Findings to Validate:
1. Decorator execution order issue: @login_required executes before custom AJAX handling
2. Authentication state changes between page load and AJAX request
3. Session cookie scope affecting cross-origin requests

Test Methodology:
- Use real HTTP sessions (not mocked)
- Test exact user workflow: login → page → AJAX
- Capture all authentication-related headers and cookies
- Test with and without authentication decorators
"""

import requests
import json
import time
import os
import sys
from datetime import datetime
from urllib.parse import urljoin, urlparse
import logging
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('HTTP-AUTH-TESTER')

class HTTPAuthWorkflowTester:
    """
    Comprehensive HTTP authentication workflow tester for NetBox Hedgehog Plugin
    """
    
    def __init__(self, base_url: str = None, fabric_id: int = None):
        """Initialize the tester with base URL and fabric ID"""
        self.base_url = base_url or os.environ.get('NETBOX_URL', 'http://localhost:8000')
        self.fabric_id = fabric_id or os.environ.get('FABRIC_ID', '1')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'HTTP-Auth-Workflow-Tester/1.0'
        })
        
        # Test results storage
        self.test_results = {
            'timestamp': datetime.now().isoformat(),
            'base_url': self.base_url,
            'fabric_id': self.fabric_id,
            'tests': {}
        }
        
        logger.info(f"Initialized HTTP Auth Workflow Tester for {self.base_url}")
    
    def capture_request_details(self, response: requests.Response, test_name: str) -> Dict:
        """Capture comprehensive request/response details"""
        return {
            'test_name': test_name,
            'timestamp': datetime.now().isoformat(),
            'request': {
                'method': response.request.method,
                'url': response.request.url,
                'headers': dict(response.request.headers),
                'body': response.request.body.decode('utf-8') if response.request.body else None
            },
            'response': {
                'status_code': response.status_code,
                'reason': response.reason,
                'headers': dict(response.headers),
                'cookies': dict(response.cookies),
                'content_length': len(response.content),
                'elapsed_ms': response.elapsed.total_seconds() * 1000
            }
        }
    
    def test_authentication_login(self, username: str = 'admin', password: str = 'admin') -> Dict:
        """
        Test 1: Authentication Login Process
        Capture session establishment and cookie setup
        """
        logger.info("🔐 Testing authentication login process...")
        
        try:
            # Step 1: Get login page and CSRF token
            login_url = urljoin(self.base_url, '/login/')
            login_page_response = self.session.get(login_url)
            login_details = self.capture_request_details(login_page_response, 'login_page_load')
            
            # Extract CSRF token
            csrf_token = None
            if 'csrftoken' in self.session.cookies:
                csrf_token = self.session.cookies['csrftoken']
                logger.info(f"✅ CSRF token obtained: {csrf_token[:10]}...")
            else:
                logger.warning("❌ No CSRF token found in login page cookies")
            
            # Step 2: Perform login
            login_data = {
                'username': username,
                'password': password,
                'csrfmiddlewaretoken': csrf_token,
                'next': f'/plugins/hedgehog/fabrics/{self.fabric_id}/'
            }
            
            login_response = self.session.post(login_url, data=login_data, allow_redirects=False)
            login_auth_details = self.capture_request_details(login_response, 'login_authentication')
            
            # Check for successful login (redirect or session cookie)
            login_success = (
                login_response.status_code in [302, 200] and
                'sessionid' in self.session.cookies
            )
            
            session_cookie = self.session.cookies.get('sessionid', '')
            logger.info(f"🍪 Session cookie: {session_cookie[:15]}..." if session_cookie else "❌ No session cookie")
            
            return {
                'success': login_success,
                'login_page': login_details,
                'login_auth': login_auth_details,
                'session_cookie': session_cookie,
                'csrf_token': csrf_token,
                'cookies_after_login': dict(self.session.cookies)
            }
            
        except Exception as e:
            logger.error(f"❌ Login test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_page_load_authentication_state(self) -> Dict:
        """
        Test 2: Page Load Authentication State
        Verify user authentication during normal page load
        """
        logger.info("📄 Testing page load authentication state...")
        
        try:
            # Load fabric detail page
            fabric_url = urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/')
            page_response = self.session.get(fabric_url)
            page_details = self.capture_request_details(page_response, 'fabric_page_load')
            
            # Analyze response for authentication indicators
            page_content = page_response.text
            auth_indicators = {
                'user_authenticated': 'user_authenticated' in page_content,
                'login_required_redirect': page_response.status_code == 302 and 'login' in page_response.headers.get('Location', ''),
                'sync_buttons_present': 'test-connection-btn' in page_content or 'sync-btn' in page_content,
                'csrf_token_in_page': 'csrfmiddlewaretoken' in page_content,
                'user_menu_present': 'user-menu' in page_content or 'logout' in page_content
            }
            
            logger.info(f"🔍 Authentication indicators: {auth_indicators}")
            
            return {
                'success': page_response.status_code == 200,
                'page_details': page_details,
                'auth_indicators': auth_indicators,
                'cookies_during_page_load': dict(self.session.cookies),
                'page_size': len(page_content)
            }
            
        except Exception as e:
            logger.error(f"❌ Page load test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_ajax_authentication_state(self) -> Dict:
        """
        Test 3: AJAX Request Authentication State
        Test authentication during AJAX request and compare with page load
        """
        logger.info("⚡ Testing AJAX authentication state...")
        
        try:
            # Prepare AJAX request to sync endpoint
            sync_url = urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/sync/')
            
            # Get CSRF token from cookies
            csrf_token = self.session.cookies.get('csrftoken', '')
            
            # Prepare AJAX headers
            ajax_headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-CSRFToken': csrf_token,
                'Referer': urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/'),
                'Accept': 'application/json, text/javascript, */*; q=0.01'
            }
            
            # Make AJAX request
            ajax_data = {'csrfmiddlewaretoken': csrf_token}
            ajax_response = self.session.post(sync_url, data=ajax_data, headers=ajax_headers)
            ajax_details = self.capture_request_details(ajax_response, 'ajax_sync_request')
            
            # Analyze AJAX response
            ajax_analysis = {
                'status_code': ajax_response.status_code,
                'is_json_response': ajax_response.headers.get('content-type', '').startswith('application/json'),
                'auth_error_detected': ajax_response.status_code == 401,
                'redirect_detected': ajax_response.status_code == 302,
                'cookies_in_ajax': dict(ajax_response.cookies),
                'session_valid': 'sessionid' in self.session.cookies
            }
            
            # Try to parse JSON response
            try:
                ajax_json = ajax_response.json()
                ajax_analysis['json_response'] = ajax_json
                ajax_analysis['auth_error_in_json'] = (
                    'error' in ajax_json and 
                    'authentication' in ajax_json.get('error', '').lower()
                )
            except:
                ajax_analysis['json_response'] = None
                ajax_analysis['response_text'] = ajax_response.text[:500]
            
            logger.info(f"🔍 AJAX analysis: {ajax_analysis}")
            
            return {
                'success': ajax_response.status_code in [200, 400],  # 400 might be expected for test sync
                'ajax_details': ajax_details,
                'ajax_analysis': ajax_analysis,
                'cookies_during_ajax': dict(self.session.cookies)
            }
            
        except Exception as e:
            logger.error(f"❌ AJAX test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_decorator_execution_order(self) -> Dict:
        """
        Test 4: Decorator Execution Order Validation
        Test different endpoints to validate decorator behavior
        """
        logger.info("🔄 Testing decorator execution order...")
        
        try:
            results = {}
            
            # Test different sync endpoints
            sync_endpoints = [
                f'/plugins/hedgehog/fabrics/{self.fabric_id}/sync/',
                f'/plugins/hedgehog/fabrics/{self.fabric_id}/test-connection/',
                f'/plugins/hedgehog/fabrics/{self.fabric_id}/github-sync/'
            ]
            
            csrf_token = self.session.cookies.get('csrftoken', '')
            base_headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrf_token,
                'Referer': urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/')
            }
            
            for endpoint in sync_endpoints:
                try:
                    url = urljoin(self.base_url, endpoint)
                    response = self.session.post(url, headers=base_headers, data={'csrfmiddlewaretoken': csrf_token})
                    
                    endpoint_name = endpoint.split('/')[-2]  # Extract action name
                    results[endpoint_name] = {
                        'status_code': response.status_code,
                        'headers': dict(response.headers),
                        'cookies': dict(response.cookies),
                        'decorator_bypass': response.status_code != 401,  # If not 401, decorators might be bypassed
                        'custom_auth_executed': response.headers.get('content-type', '').startswith('application/json')
                    }
                    
                    # Check response content for custom auth messages
                    try:
                        json_resp = response.json()
                        results[endpoint_name]['custom_auth_message'] = (
                            'error' in json_resp and 
                            'Authentication required' in json_resp.get('error', '')
                        )
                    except:
                        results[endpoint_name]['custom_auth_message'] = False
                    
                    logger.info(f"📊 {endpoint_name}: {response.status_code} - Custom auth: {results[endpoint_name]['custom_auth_executed']}")
                    
                except Exception as e:
                    results[endpoint_name] = {'error': str(e)}
                    
                time.sleep(0.5)  # Small delay between requests
            
            return {
                'success': True,
                'endpoint_results': results,
                'session_cookies': dict(self.session.cookies)
            }
            
        except Exception as e:
            logger.error(f"❌ Decorator order test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_session_cookie_investigation(self) -> Dict:
        """
        Test 5: Session Cookie Investigation
        Analyze session cookie behavior and settings
        """
        logger.info("🍪 Testing session cookie investigation...")
        
        try:
            # Get current cookies
            current_cookies = dict(self.session.cookies)
            
            # Analyze session cookie properties
            sessionid_cookie = None
            csrf_cookie = None
            
            for cookie in self.session.cookies:
                if cookie.name == 'sessionid':
                    sessionid_cookie = {
                        'name': cookie.name,
                        'value': cookie.value[:15] + '...' if cookie.value else None,
                        'domain': cookie.domain,
                        'path': cookie.path,
                        'secure': cookie.secure,
                        'httponly': getattr(cookie, 'http_only', None),
                        'expires': cookie.expires
                    }
                elif cookie.name == 'csrftoken':
                    csrf_cookie = {
                        'name': cookie.name,
                        'value': cookie.value[:15] + '...' if cookie.value else None,
                        'domain': cookie.domain,
                        'path': cookie.path,
                        'secure': cookie.secure,
                        'expires': cookie.expires
                    }
            
            # Test cookie behavior with different request types
            cookie_tests = {}
            
            # Test 1: Regular page request
            page_url = urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/')
            page_resp = self.session.get(page_url)
            cookie_tests['page_request'] = {
                'cookies_sent': len(self.session.cookies),
                'cookies_received': len(page_resp.cookies),
                'sessionid_present': 'sessionid' in [c.name for c in self.session.cookies]
            }
            
            # Test 2: AJAX request
            ajax_url = urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/sync/')
            ajax_headers = {'X-Requested-With': 'XMLHttpRequest'}
            ajax_resp = self.session.post(ajax_url, headers=ajax_headers)
            cookie_tests['ajax_request'] = {
                'cookies_sent': len(self.session.cookies),
                'cookies_received': len(ajax_resp.cookies),
                'sessionid_present': 'sessionid' in [c.name for c in self.session.cookies]
            }
            
            logger.info(f"🍪 Session cookie: {sessionid_cookie}")
            logger.info(f"🍪 CSRF cookie: {csrf_cookie}")
            
            return {
                'success': True,
                'current_cookies': current_cookies,
                'sessionid_cookie': sessionid_cookie,
                'csrf_cookie': csrf_cookie,
                'cookie_tests': cookie_tests,
                'total_cookies': len(current_cookies)
            }
            
        except Exception as e:
            logger.error(f"❌ Cookie investigation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_authentication_without_decorators(self) -> Dict:
        """
        Test 6: Authentication Without Decorators
        Test endpoints to see behavior without @login_required decorator
        """
        logger.info("🔓 Testing authentication without decorators...")
        
        try:
            # Create a new session to test unauthenticated requests
            unauth_session = requests.Session()
            
            # Test unauthenticated access to fabric page
            fabric_url = urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/')
            unauth_page = unauth_session.get(fabric_url, allow_redirects=False)
            
            # Test unauthenticated AJAX request
            sync_url = urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/sync/')
            ajax_headers = {'X-Requested-With': 'XMLHttpRequest'}
            unauth_ajax = unauth_session.post(sync_url, headers=ajax_headers, allow_redirects=False)
            
            return {
                'success': True,
                'unauthenticated_page': {
                    'status_code': unauth_page.status_code,
                    'redirected_to_login': unauth_page.status_code == 302 and 'login' in unauth_page.headers.get('Location', ''),
                    'location_header': unauth_page.headers.get('Location')
                },
                'unauthenticated_ajax': {
                    'status_code': unauth_ajax.status_code,
                    'content_type': unauth_ajax.headers.get('content-type'),
                    'custom_auth_response': unauth_ajax.headers.get('content-type', '').startswith('application/json')
                },
                'decorator_behavior': {
                    'page_blocked_by_decorator': unauth_page.status_code == 302,
                    'ajax_handled_by_custom_auth': unauth_ajax.headers.get('content-type', '').startswith('application/json')
                }
            }
            
        except Exception as e:
            logger.error(f"❌ No-decorator test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def run_comprehensive_test_suite(self, username: str = 'admin', password: str = 'admin') -> Dict:
        """
        Run the complete HTTP authentication workflow test suite
        """
        logger.info("🚀 Starting comprehensive HTTP authentication workflow test suite...")
        
        # Test 1: Authentication Login
        self.test_results['tests']['login'] = self.test_authentication_login(username, password)
        
        # Test 2: Page Load Authentication State
        self.test_results['tests']['page_load'] = self.test_page_load_authentication_state()
        
        # Test 3: AJAX Authentication State
        self.test_results['tests']['ajax'] = self.test_ajax_authentication_state()
        
        # Test 4: Decorator Execution Order
        self.test_results['tests']['decorator_order'] = self.test_decorator_execution_order()
        
        # Test 5: Session Cookie Investigation
        self.test_results['tests']['cookies'] = self.test_session_cookie_investigation()
        
        # Test 6: Authentication Without Decorators
        self.test_results['tests']['no_decorators'] = self.test_authentication_without_decorators()
        
        # Generate summary
        self.test_results['summary'] = self.generate_test_summary()
        
        return self.test_results
    
    def generate_test_summary(self) -> Dict:
        """Generate comprehensive test summary with findings"""
        summary = {
            'total_tests': len(self.test_results['tests']),
            'successful_tests': sum(1 for test in self.test_results['tests'].values() if test.get('success')),
            'critical_findings': [],
            'authentication_analysis': {},
            'recommendations': []
        }
        
        # Analyze authentication state consistency
        login_success = self.test_results['tests']['login'].get('success', False)
        page_auth = self.test_results['tests']['page_load'].get('auth_indicators', {})
        ajax_auth = self.test_results['tests']['ajax'].get('ajax_analysis', {})
        
        if login_success:
            summary['authentication_analysis']['login_successful'] = True
            summary['authentication_analysis']['session_established'] = bool(self.test_results['tests']['login'].get('session_cookie'))
        
        # Check for authentication state changes
        if page_auth.get('user_authenticated') and ajax_auth.get('auth_error_detected'):
            summary['critical_findings'].append(
                "CRITICAL: Authentication state differs between page load and AJAX request"
            )
            summary['recommendations'].append(
                "Review decorator execution order in sync views"
            )
        
        # Check decorator execution
        decorator_results = self.test_results['tests']['decorator_order'].get('endpoint_results', {})
        custom_auth_working = any(
            result.get('custom_auth_executed', False) 
            for result in decorator_results.values() 
            if isinstance(result, dict)
        )
        
        if not custom_auth_working:
            summary['critical_findings'].append(
                "CRITICAL: Custom authentication in dispatch() method may not be executing"
            )
            summary['recommendations'].append(
                "Verify dispatch() method is being called before @login_required decorator"
            )
        
        # Cookie analysis
        cookie_info = self.test_results['tests']['cookies']
        if not cookie_info.get('sessionid_cookie'):
            summary['critical_findings'].append(
                "CRITICAL: Session cookie not properly established or configured"
            )
        
        return summary
    
    def save_results(self, filename: str = None) -> str:
        """Save test results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"http_auth_test_results_{timestamp}.json"
        
        filepath = os.path.join('/tmp', filename)
        with open(filepath, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        logger.info(f"💾 Test results saved to: {filepath}")
        return filepath


def main():
    """Main function to run the HTTP authentication workflow tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HTTP Authentication Workflow Tester')
    parser.add_argument('--url', default='http://localhost:8000', help='NetBox base URL')
    parser.add_argument('--fabric-id', default='1', help='Fabric ID to test')
    parser.add_argument('--username', default='admin', help='Login username')
    parser.add_argument('--password', default='admin', help='Login password')
    parser.add_argument('--output', help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Initialize tester
    tester = HTTPAuthWorkflowTester(args.url, args.fabric_id)
    
    # Run comprehensive test suite
    results = tester.run_comprehensive_test_suite(args.username, args.password)
    
    # Save results
    output_file = tester.save_results(args.output)
    
    # Print summary
    print("\n" + "="*80)
    print("HTTP AUTHENTICATION WORKFLOW TEST RESULTS")
    print("="*80)
    
    summary = results.get('summary', {})
    print(f"Total Tests: {summary.get('total_tests', 0)}")
    print(f"Successful Tests: {summary.get('successful_tests', 0)}")
    
    print("\nCRITICAL FINDINGS:")
    for finding in summary.get('critical_findings', []):
        print(f"  ❌ {finding}")
    
    print("\nRECOMMENDATIONS:")
    for rec in summary.get('recommendations', []):
        print(f"  💡 {rec}")
    
    print(f"\n📊 Full results saved to: {output_file}")
    
    return results


if __name__ == '__main__':
    main()