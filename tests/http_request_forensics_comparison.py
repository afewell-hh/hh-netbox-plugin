#!/usr/bin/env python3
"""
HTTP Request Forensics Comparison

Compares successful page load requests vs failed AJAX requests to identify
exact failure points in authentication workflow.
"""

import requests
import json
import time
from datetime import datetime
from urllib.parse import urljoin
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('REQUEST-FORENSICS')

class HTTPRequestForensicsComparison:
    """
    Forensic comparison of successful vs failed authentication requests
    """
    
    def __init__(self, base_url: str = 'http://localhost:8000'):
        self.base_url = base_url
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'base_url': base_url,
            'comparisons': {},
            'forensic_analysis': {},
            'critical_differences': []
        }
    
    def capture_detailed_request_response(self, response: requests.Response, request_name: str) -> Dict:
        """Capture comprehensive request/response details for forensic analysis"""
        return {
            'request_name': request_name,
            'timestamp': datetime.now().isoformat(),
            'request': {
                'method': response.request.method,
                'url': response.request.url,
                'headers': dict(response.request.headers),
                'body': response.request.body.decode('utf-8') if response.request.body else None,
                'cookies_sent': len(response.request.headers.get('Cookie', '').split(';')) if 'Cookie' in response.request.headers else 0
            },
            'response': {
                'status_code': response.status_code,
                'reason': response.reason,
                'headers': dict(response.headers),
                'cookies': dict(response.cookies),
                'content_preview': response.text[:500] if response.text else None,
                'content_length': len(response.content),
                'elapsed_ms': response.elapsed.total_seconds() * 1000,
                'final_url': response.url,
                'redirect_chain': [resp.url for resp in response.history] if response.history else []
            },
            'authentication_indicators': {
                'has_sessionid_cookie': 'sessionid' in dict(response.cookies),
                'has_csrf_token': 'csrftoken' in dict(response.cookies),
                'redirected_to_login': response.status_code == 302 and 'login' in response.headers.get('Location', ''),
                'contains_login_form': 'login' in response.text.lower() if response.text else False,
                'contains_user_menu': 'logout' in response.text.lower() if response.text else False
            }
        }
    
    def compare_successful_page_vs_failed_ajax(self) -> Dict:
        """Compare successful page load vs failed AJAX request patterns"""
        logger.info("🔍 Comparing successful page load vs failed AJAX patterns...")
        
        session = requests.Session()
        
        # Test 1: Successful page load (should work)
        try:
            login_page_url = urljoin(self.base_url, '/login/')
            page_response = session.get(login_page_url)
            page_details = self.capture_detailed_request_response(page_response, 'successful_page_load')
        except Exception as e:
            page_details = {'error': str(e), 'request_name': 'successful_page_load'}
        
        # Test 2: Failed AJAX request (should fail authentication)
        try:
            sync_url = urljoin(self.base_url, '/plugins/hedgehog/fabrics/1/sync/')
            ajax_headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': 'application/json, text/javascript, */*; q=0.01'
            }
            
            csrf_token = session.cookies.get('csrftoken', '')
            ajax_data = {'csrfmiddlewaretoken': csrf_token}
            
            ajax_response = session.post(sync_url, headers=ajax_headers, data=ajax_data)
            ajax_details = self.capture_detailed_request_response(ajax_response, 'failed_ajax_request')
        except Exception as e:
            ajax_details = {'error': str(e), 'request_name': 'failed_ajax_request'}
        
        # Forensic comparison
        comparison = {
            'page_load': page_details,
            'ajax_request': ajax_details,
            'key_differences': self.identify_key_differences(page_details, ajax_details),
            'authentication_state_differences': self.compare_authentication_states(page_details, ajax_details)
        }
        
        return comparison
    
    def compare_authenticated_vs_unauthenticated_ajax(self) -> Dict:
        """Compare authenticated vs unauthenticated AJAX requests"""
        logger.info("🔐 Comparing authenticated vs unauthenticated AJAX requests...")
        
        # Test 1: Unauthenticated AJAX
        unauth_session = requests.Session()
        
        try:
            # Get CSRF token first
            login_url = urljoin(self.base_url, '/login/')
            unauth_session.get(login_url)
            
            sync_url = urljoin(self.base_url, '/plugins/hedgehog/fabrics/1/sync/')
            ajax_headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': unauth_session.cookies.get('csrftoken', '')
            }
            
            unauth_response = unauth_session.post(sync_url, headers=ajax_headers)
            unauth_details = self.capture_detailed_request_response(unauth_response, 'unauthenticated_ajax')
        except Exception as e:
            unauth_details = {'error': str(e), 'request_name': 'unauthenticated_ajax'}
        
        # Test 2: Simulated authenticated AJAX (with session cookie)
        auth_session = requests.Session()
        
        try:
            # Simulate having a session
            login_url = urljoin(self.base_url, '/login/')
            auth_session.get(login_url)
            
            # Add fake sessionid cookie to simulate authentication
            auth_session.cookies.set('sessionid', 'fake_session_for_testing_purposes_only')
            
            sync_url = urljoin(self.base_url, '/plugins/hedgehog/fabrics/1/sync/')
            ajax_headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': auth_session.cookies.get('csrftoken', '')
            }
            
            auth_response = auth_session.post(sync_url, headers=ajax_headers)
            auth_details = self.capture_detailed_request_response(auth_response, 'simulated_authenticated_ajax')
        except Exception as e:
            auth_details = {'error': str(e), 'request_name': 'simulated_authenticated_ajax'}
        
        comparison = {
            'unauthenticated': unauth_details,
            'simulated_authenticated': auth_details,
            'behavioral_differences': self.compare_authentication_behaviors(unauth_details, auth_details)
        }
        
        return comparison
    
    def test_decorator_bypass_hypothesis(self) -> Dict:
        """Test if requests bypass @login_required decorator and reach custom dispatch"""
        logger.info("🔄 Testing decorator bypass hypothesis...")
        
        session = requests.Session()
        
        # Get CSRF token
        login_url = urljoin(self.base_url, '/login/')
        session.get(login_url)
        
        # Test different sync endpoints
        test_endpoints = [
            '/plugins/hedgehog/fabrics/1/sync/',
            '/plugins/hedgehog/fabrics/1/test-connection/',
            '/plugins/hedgehog/fabrics/1/github-sync/'
        ]
        
        endpoint_tests = {}
        
        for endpoint in test_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                
                # Test with AJAX headers (should trigger custom dispatch if working)
                ajax_headers = {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': session.cookies.get('csrftoken', ''),
                    'Accept': 'application/json'
                }
                
                response = session.post(url, headers=ajax_headers)
                endpoint_details = self.capture_detailed_request_response(response, f'decorator_test_{endpoint.split("/")[-2]}')
                
                # Analyze if custom dispatch was reached
                custom_dispatch_indicators = {
                    'returns_json': response.headers.get('content-type', '').startswith('application/json'),
                    'has_custom_auth_message': 'Authentication required' in response.text if response.text else False,
                    'status_is_401_with_json': response.status_code == 401 and response.headers.get('content-type', '').startswith('application/json'),
                    'redirected_to_login': response.status_code == 302 and 'login' in response.headers.get('Location', ''),
                    'blocked_by_decorator': response.status_code == 302 and not response.headers.get('content-type', '').startswith('application/json')
                }
                
                endpoint_details['custom_dispatch_analysis'] = custom_dispatch_indicators
                endpoint_tests[endpoint] = endpoint_details
                
            except Exception as e:
                endpoint_tests[endpoint] = {'error': str(e)}
                
            time.sleep(0.2)  # Small delay
        
        return {
            'endpoint_tests': endpoint_tests,
            'decorator_bypass_summary': self.analyze_decorator_bypass_results(endpoint_tests)
        }
    
    def identify_key_differences(self, page_details: Dict, ajax_details: Dict) -> List[str]:
        """Identify key differences between successful page and failed AJAX"""
        differences = []
        
        if 'request' in page_details and 'request' in ajax_details:
            page_req = page_details['request']
            ajax_req = ajax_details['request']
            
            # Compare headers
            page_headers = set(page_req.get('headers', {}).keys())
            ajax_headers = set(ajax_req.get('headers', {}).keys())
            
            unique_to_ajax = ajax_headers - page_headers
            unique_to_page = page_headers - ajax_headers
            
            if unique_to_ajax:
                differences.append(f"AJAX has unique headers: {', '.join(unique_to_ajax)}")
            
            if unique_to_page:
                differences.append(f"Page has unique headers: {', '.join(unique_to_page)}")
            
            # Compare methods
            if page_req.get('method') != ajax_req.get('method'):
                differences.append(f"Different methods: Page={page_req.get('method')}, AJAX={ajax_req.get('method')}")
        
        if 'response' in page_details and 'response' in ajax_details:
            page_resp = page_details['response']
            ajax_resp = ajax_details['response']
            
            # Compare status codes
            if page_resp.get('status_code') != ajax_resp.get('status_code'):
                differences.append(f"Different status codes: Page={page_resp.get('status_code')}, AJAX={ajax_resp.get('status_code')}")
            
            # Compare content types
            page_content_type = page_resp.get('headers', {}).get('Content-Type', '')
            ajax_content_type = ajax_resp.get('headers', {}).get('Content-Type', '')
            
            if page_content_type != ajax_content_type:
                differences.append(f"Different content types: Page={page_content_type}, AJAX={ajax_content_type}")
        
        return differences
    
    def compare_authentication_states(self, page_details: Dict, ajax_details: Dict) -> Dict:
        """Compare authentication state indicators between requests"""
        comparison = {}
        
        if 'authentication_indicators' in page_details:
            comparison['page_auth'] = page_details['authentication_indicators']
        
        if 'authentication_indicators' in ajax_details:
            comparison['ajax_auth'] = ajax_details['authentication_indicators']
        
        # Compare states
        if 'page_auth' in comparison and 'ajax_auth' in comparison:
            comparison['differences'] = {}
            for key in comparison['page_auth']:
                if key in comparison['ajax_auth']:
                    if comparison['page_auth'][key] != comparison['ajax_auth'][key]:
                        comparison['differences'][key] = {
                            'page': comparison['page_auth'][key],
                            'ajax': comparison['ajax_auth'][key]
                        }
        
        return comparison
    
    def compare_authentication_behaviors(self, unauth_details: Dict, auth_details: Dict) -> Dict:
        """Compare behaviors between unauthenticated and authenticated requests"""
        behaviors = {}
        
        if 'response' in unauth_details and 'response' in auth_details:
            unauth_resp = unauth_details['response']
            auth_resp = auth_details['response']
            
            behaviors['status_code_difference'] = {
                'unauthenticated': unauth_resp.get('status_code'),
                'authenticated': auth_resp.get('status_code'),
                'same_behavior': unauth_resp.get('status_code') == auth_resp.get('status_code')
            }
            
            behaviors['content_type_difference'] = {
                'unauthenticated': unauth_resp.get('headers', {}).get('Content-Type', ''),
                'authenticated': auth_resp.get('headers', {}).get('Content-Type', ''),
                'same_content_type': unauth_resp.get('headers', {}).get('Content-Type') == auth_resp.get('headers', {}).get('Content-Type')
            }
        
        return behaviors
    
    def analyze_decorator_bypass_results(self, endpoint_tests: Dict) -> Dict:
        """Analyze decorator bypass test results"""
        summary = {
            'total_endpoints_tested': len(endpoint_tests),
            'custom_dispatch_reached': 0,
            'blocked_by_decorators': 0,
            'evidence_of_custom_auth': 0,
            'redirected_to_login': 0
        }
        
        for endpoint, test_result in endpoint_tests.items():
            if 'custom_dispatch_analysis' in test_result:
                analysis = test_result['custom_dispatch_analysis']
                
                if analysis.get('returns_json') or analysis.get('has_custom_auth_message'):
                    summary['custom_dispatch_reached'] += 1
                
                if analysis.get('blocked_by_decorator'):
                    summary['blocked_by_decorators'] += 1
                
                if analysis.get('has_custom_auth_message') or analysis.get('status_is_401_with_json'):
                    summary['evidence_of_custom_auth'] += 1
                
                if analysis.get('redirected_to_login'):
                    summary['redirected_to_login'] += 1
        
        # Generate conclusions
        summary['conclusions'] = []
        
        if summary['blocked_by_decorators'] > 0:
            summary['conclusions'].append("@login_required decorator is blocking requests before custom dispatch")
        
        if summary['evidence_of_custom_auth'] > 0:
            summary['conclusions'].append("Custom authentication logic is working when reached")
        
        if summary['custom_dispatch_reached'] == 0:
            summary['conclusions'].append("CRITICAL: Custom dispatch methods are not being reached")
        
        return summary
    
    def run_comprehensive_forensics(self) -> Dict:
        """Run comprehensive HTTP request forensics"""
        logger.info("🚀 Starting comprehensive HTTP request forensics...")
        
        # Test 1: Successful page vs failed AJAX
        self.results['comparisons']['page_vs_ajax'] = self.compare_successful_page_vs_failed_ajax()
        
        # Test 2: Authenticated vs unauthenticated AJAX
        self.results['comparisons']['auth_vs_unauth'] = self.compare_authenticated_vs_unauthenticated_ajax()
        
        # Test 3: Decorator bypass hypothesis
        self.results['comparisons']['decorator_bypass'] = self.test_decorator_bypass_hypothesis()
        
        # Generate forensic analysis
        self.generate_forensic_analysis()
        
        return self.results
    
    def generate_forensic_analysis(self):
        """Generate comprehensive forensic analysis"""
        analysis = {}
        
        # Analyze page vs AJAX comparison
        page_ajax = self.results['comparisons'].get('page_vs_ajax', {})
        if 'key_differences' in page_ajax:
            analysis['critical_differences'] = page_ajax['key_differences']
        
        # Analyze decorator bypass
        decorator_bypass = self.results['comparisons'].get('decorator_bypass', {})
        if 'decorator_bypass_summary' in decorator_bypass:
            analysis['decorator_behavior'] = decorator_bypass['decorator_bypass_summary']
        
        # Generate critical findings
        critical_differences = []
        
        if analysis.get('decorator_behavior', {}).get('custom_dispatch_reached', 0) == 0:
            critical_differences.append("CRITICAL: No endpoints successfully reached custom dispatch methods")
        
        if analysis.get('decorator_behavior', {}).get('blocked_by_decorators', 0) > 0:
            critical_differences.append("CRITICAL: @login_required decorators blocking custom authentication")
        
        auth_vs_unauth = self.results['comparisons'].get('auth_vs_unauth', {})
        if 'behavioral_differences' in auth_vs_unauth:
            behaviors = auth_vs_unauth['behavioral_differences']
            if behaviors.get('status_code_difference', {}).get('same_behavior', False):
                critical_differences.append("CRITICAL: Authenticated and unauthenticated requests have same behavior")
        
        self.results['forensic_analysis'] = analysis
        self.results['critical_differences'] = critical_differences
    
    def save_results(self, filename: str = None) -> str:
        """Save forensic results"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"http_forensics_comparison_{timestamp}.json"
        
        filepath = f"/tmp/{filename}"
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"💾 Forensic results saved to: {filepath}")
        return filepath


def main():
    """Main function"""
    print("🔍 HTTP Request Forensics Comparison")
    print("="*50)
    
    forensics = HTTPRequestForensicsComparison()
    results = forensics.run_comprehensive_forensics()
    
    # Save results
    output_file = forensics.save_results()
    
    # Print critical differences
    print("\nCRITICAL DIFFERENCES:")
    for diff in results.get('critical_differences', []):
        print(f"  ❌ {diff}")
    
    # Print decorator analysis
    decorator_analysis = results.get('forensic_analysis', {}).get('decorator_behavior', {})
    if decorator_analysis:
        print(f"\nDECORATOR ANALYSIS:")
        print(f"  Endpoints tested: {decorator_analysis.get('total_endpoints_tested', 0)}")
        print(f"  Custom dispatch reached: {decorator_analysis.get('custom_dispatch_reached', 0)}")
        print(f"  Blocked by decorators: {decorator_analysis.get('blocked_by_decorators', 0)}")
        print(f"  Evidence of custom auth: {decorator_analysis.get('evidence_of_custom_auth', 0)}")
    
    print(f"\n📊 Full forensic results saved to: {output_file}")
    
    return results


if __name__ == '__main__':
    main()