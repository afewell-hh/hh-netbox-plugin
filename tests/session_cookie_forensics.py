#!/usr/bin/env python3
"""
Session Cookie Forensics Script

Analyzes session cookie behavior, scope, and security settings to identify
authentication issues in containerized environments.
"""

import os
import sys
import requests
import json
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('COOKIE-FORENSICS')

class SessionCookieForensics:
    """
    Forensic analysis of session cookies and authentication behavior
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.environ.get('NETBOX_URL', 'http://localhost:8000')
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'base_url': self.base_url,
            'tests': {},
            'findings': []
        }
        logger.info(f"Initialized Session Cookie Forensics for {self.base_url}")
    
    def analyze_cookie_domains_and_paths(self) -> Dict:
        """Analyze cookie domain and path configurations"""
        logger.info("🔍 Analyzing cookie domains and paths...")
        
        try:
            session = requests.Session()
            
            # Test different URL patterns
            test_urls = [
                self.base_url,  # Base URL
                urljoin(self.base_url, '/login/'),  # Login page
                urljoin(self.base_url, '/admin/'),  # Admin page
                urljoin(self.base_url, '/plugins/hedgehog/'),  # Plugin base
                urljoin(self.base_url, '/api/'),  # API endpoint
            ]
            
            cookie_analysis = {}
            
            for test_url in test_urls:
                try:
                    response = session.get(test_url, allow_redirects=False)
                    url_path = urlparse(test_url).path
                    
                    # Analyze cookies set by this URL
                    cookies_info = []
                    for cookie in response.cookies:
                        cookie_info = {
                            'name': cookie.name,
                            'value': cookie.value[:15] + '...' if cookie.value else None,
                            'domain': cookie.domain,
                            'path': cookie.path,
                            'secure': cookie.secure,
                            'httponly': getattr(cookie, 'httponly', None),
                            'expires': cookie.expires,
                            'max_age': getattr(cookie, 'max_age', None)
                        }
                        cookies_info.append(cookie_info)
                    
                    cookie_analysis[url_path] = {
                        'status_code': response.status_code,
                        'cookies_set': len(response.cookies),
                        'cookies_info': cookies_info,
                        'total_cookies_in_session': len(session.cookies)
                    }
                    
                except Exception as e:
                    cookie_analysis[url_path] = {'error': str(e)}
                    
                time.sleep(0.2)  # Small delay
            
            # Analyze session cookies specifically
            session_cookies = []
            for cookie in session.cookies:
                if cookie.name in ['sessionid', 'csrftoken']:
                    session_cookies.append({
                        'name': cookie.name,
                        'domain': cookie.domain,
                        'path': cookie.path,
                        'secure': cookie.secure,
                        'httponly': getattr(cookie, 'httponly', None)
                    })
            
            return {
                'success': True,
                'url_analysis': cookie_analysis,
                'session_cookies': session_cookies,
                'total_cookies': len(session.cookies)
            }
            
        except Exception as e:
            logger.error(f"Cookie domain analysis failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_cookie_scope_with_subdomains(self) -> Dict:
        """Test cookie behavior with different subdomain scenarios"""
        logger.info("🌐 Testing cookie scope with subdomains...")
        
        try:
            # Parse base URL to test subdomain scenarios
            parsed_url = urlparse(self.base_url)
            base_domain = parsed_url.netloc
            
            # Test scenarios for containerized environments
            test_scenarios = [
                f"{parsed_url.scheme}://{base_domain}",  # Original URL
                f"{parsed_url.scheme}://www.{base_domain}",  # www subdomain
                f"{parsed_url.scheme}://app.{base_domain}",  # app subdomain
                f"{parsed_url.scheme}://localhost:8000",  # localhost fallback
                f"{parsed_url.scheme}://127.0.0.1:8000",  # IP fallback
            ]
            
            scenario_results = {}
            
            for scenario_url in test_scenarios:
                try:
                    session = requests.Session()
                    
                    # Try to get login page
                    login_url = urljoin(scenario_url, '/login/')
                    response = session.get(login_url, timeout=5, allow_redirects=False)
                    
                    # Analyze cookies for this scenario
                    cookies_received = []
                    for cookie in session.cookies:
                        cookies_received.append({
                            'name': cookie.name,
                            'domain': cookie.domain,
                            'path': cookie.path,
                            'matches_request_domain': cookie.domain in urlparse(scenario_url).netloc or not cookie.domain
                        })
                    
                    scenario_results[scenario_url] = {
                        'accessible': response.status_code < 400,
                        'status_code': response.status_code,
                        'cookies_received': len(session.cookies),
                        'cookie_details': cookies_received,
                        'domain_mismatch': any(not c['matches_request_domain'] for c in cookies_received)
                    }
                    
                except Exception as e:
                    scenario_results[scenario_url] = {
                        'accessible': False,
                        'error': str(e)
                    }
            
            return {
                'success': True,
                'test_scenarios': scenario_results,
                'base_domain': base_domain
            }
            
        except Exception as e:
            logger.error(f"Subdomain cookie test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def analyze_ajax_cookie_transmission(self) -> Dict:
        """Analyze cookie transmission in AJAX requests vs regular requests"""
        logger.info("⚡ Analyzing AJAX cookie transmission...")
        
        try:
            session = requests.Session()
            
            # Step 1: Establish session with login page
            login_url = urljoin(self.base_url, '/login/')
            login_response = session.get(login_url)
            cookies_after_login_page = dict(session.cookies)
            
            # Step 2: Make regular page request
            fabric_url = urljoin(self.base_url, '/plugins/hedgehog/fabrics/1/')
            page_response = session.get(fabric_url, allow_redirects=False)
            
            # Step 3: Make AJAX request to same domain
            ajax_headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': 'application/json, text/javascript, */*; q=0.01'
            }
            
            sync_url = urljoin(self.base_url, '/plugins/hedgehog/fabrics/1/sync/')
            ajax_response = session.post(sync_url, headers=ajax_headers, allow_redirects=False)
            
            # Step 4: Analyze cookie transmission
            cookie_transmission_analysis = {
                'login_page': {
                    'cookies_received': len(login_response.cookies),
                    'session_cookies': cookies_after_login_page,
                    'csrftoken_present': 'csrftoken' in cookies_after_login_page,
                    'sessionid_present': 'sessionid' in cookies_after_login_page
                },
                'regular_page_request': {
                    'status_code': page_response.status_code,
                    'cookies_sent': len(session.cookies),
                    'cookies_received': len(page_response.cookies),
                    'session_maintained': 'sessionid' in dict(session.cookies)
                },
                'ajax_request': {
                    'status_code': ajax_response.status_code,
                    'cookies_sent': len(session.cookies),
                    'cookies_received': len(ajax_response.cookies),
                    'session_maintained': 'sessionid' in dict(session.cookies),
                    'content_type': ajax_response.headers.get('content-type', ''),
                    'auth_error': ajax_response.status_code in [401, 403]
                }
            }
            
            # Check if cookies are being sent properly
            request_headers_analysis = {
                'page_request_has_cookies': bool(session.cookies),
                'ajax_request_has_cookies': bool(session.cookies),
                'cookie_header_sent': 'Cookie' in (page_response.request.headers if hasattr(page_response, 'request') else {})
            }
            
            return {
                'success': True,
                'cookie_transmission': cookie_transmission_analysis,
                'request_headers': request_headers_analysis,
                'session_cookies_final': dict(session.cookies)
            }
            
        except Exception as e:
            logger.error(f"AJAX cookie transmission analysis failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_cross_origin_cookie_behavior(self) -> Dict:
        """Test cookie behavior in cross-origin scenarios"""
        logger.info("🔀 Testing cross-origin cookie behavior...")
        
        try:
            session = requests.Session()
            
            # Establish session
            login_url = urljoin(self.base_url, '/login/')
            login_response = session.get(login_url)
            
            # Test different origin scenarios
            origin_tests = {}
            
            # Test 1: Same origin AJAX
            same_origin_headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': self.base_url,
                'Referer': urljoin(self.base_url, '/plugins/hedgehog/fabrics/1/')
            }
            
            sync_url = urljoin(self.base_url, '/plugins/hedgehog/fabrics/1/sync/')
            same_origin_response = session.post(sync_url, headers=same_origin_headers, allow_redirects=False)
            
            origin_tests['same_origin'] = {
                'status_code': same_origin_response.status_code,
                'cookies_sent': len(session.cookies),
                'auth_error': same_origin_response.status_code in [401, 403],
                'origin_header': same_origin_headers['Origin']
            }
            
            # Test 2: Different origin (simulate reverse proxy scenario)
            different_origin_headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'http://proxy.example.com',
                'Referer': 'http://proxy.example.com/plugins/hedgehog/fabrics/1/'
            }
            
            diff_origin_response = session.post(sync_url, headers=different_origin_headers, allow_redirects=False)
            
            origin_tests['different_origin'] = {
                'status_code': diff_origin_response.status_code,
                'cookies_sent': len(session.cookies),
                'auth_error': diff_origin_response.status_code in [401, 403],
                'origin_header': different_origin_headers['Origin']
            }
            
            # Test 3: No origin header
            no_origin_headers = {
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            no_origin_response = session.post(sync_url, headers=no_origin_headers, allow_redirects=False)
            
            origin_tests['no_origin'] = {
                'status_code': no_origin_response.status_code,
                'cookies_sent': len(session.cookies),
                'auth_error': no_origin_response.status_code in [401, 403]
            }
            
            return {
                'success': True,
                'origin_tests': origin_tests,
                'session_cookies': dict(session.cookies)
            }
            
        except Exception as e:
            logger.error(f"Cross-origin cookie test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def analyze_container_cookie_settings(self) -> Dict:
        """Analyze cookie settings specific to containerized deployments"""
        logger.info("🐳 Analyzing container cookie settings...")
        
        try:
            session = requests.Session()
            
            # Get initial cookies from login page
            login_url = urljoin(self.base_url, '/login/')
            response = session.get(login_url)
            
            # Analyze cookie security settings
            cookie_security_analysis = {}
            
            for cookie in response.cookies:
                security_info = {
                    'name': cookie.name,
                    'secure': cookie.secure,
                    'httponly': getattr(cookie, 'httponly', False),
                    'samesite': getattr(cookie, 'samesite', None),
                    'domain': cookie.domain,
                    'path': cookie.path
                }
                
                # Check for container-specific issues
                container_issues = []
                
                # Issue 1: Secure flag on HTTP
                if cookie.secure and not self.base_url.startswith('https://'):
                    container_issues.append("Secure flag set but using HTTP")
                
                # Issue 2: Domain mismatch in containers
                parsed_url = urlparse(self.base_url)
                if cookie.domain and cookie.domain not in parsed_url.netloc:
                    container_issues.append(f"Cookie domain '{cookie.domain}' doesn't match request domain '{parsed_url.netloc}'")
                
                # Issue 3: SameSite issues in reverse proxy
                if getattr(cookie, 'samesite', None) == 'Strict':
                    container_issues.append("SameSite=Strict may block reverse proxy requests")
                
                security_info['container_issues'] = container_issues
                cookie_security_analysis[cookie.name] = security_info
            
            # Test cookie persistence across requests
            persistence_test = {}
            
            # Make multiple requests and track cookie consistency
            test_urls = [
                urljoin(self.base_url, '/'),
                urljoin(self.base_url, '/plugins/hedgehog/'),
                urljoin(self.base_url, '/admin/'),
                urljoin(self.base_url, '/api/')
            ]
            
            for test_url in test_urls:
                try:
                    resp = session.get(test_url, allow_redirects=False)
                    url_path = urlparse(test_url).path
                    
                    persistence_test[url_path] = {
                        'status_code': resp.status_code,
                        'cookies_maintained': len(session.cookies),
                        'sessionid_consistent': 'sessionid' in dict(session.cookies)
                    }
                except:
                    pass
            
            return {
                'success': True,
                'cookie_security_analysis': cookie_security_analysis,
                'persistence_test': persistence_test,
                'base_url_protocol': urlparse(self.base_url).scheme
            }
            
        except Exception as e:
            logger.error(f"Container cookie analysis failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def run_comprehensive_forensics(self) -> Dict:
        """Run comprehensive session cookie forensics"""
        logger.info("🚀 Starting comprehensive session cookie forensics...")
        
        # Test 1: Cookie domains and paths
        self.results['tests']['domains_paths'] = self.analyze_cookie_domains_and_paths()
        
        # Test 2: Subdomain scenarios
        self.results['tests']['subdomains'] = self.test_cookie_scope_with_subdomains()
        
        # Test 3: AJAX cookie transmission
        self.results['tests']['ajax_transmission'] = self.analyze_ajax_cookie_transmission()
        
        # Test 4: Cross-origin behavior
        self.results['tests']['cross_origin'] = self.test_cross_origin_cookie_behavior()
        
        # Test 5: Container-specific settings
        self.results['tests']['container_settings'] = self.analyze_container_cookie_settings()
        
        # Generate findings
        self.generate_findings()
        
        return self.results
    
    def generate_findings(self):
        """Generate forensic findings and recommendations"""
        findings = []
        
        # Analyze domain/path issues
        domains_test = self.results['tests'].get('domains_paths', {})
        if domains_test.get('success'):
            session_cookies = domains_test.get('session_cookies', [])
            for cookie in session_cookies:
                if cookie.get('domain') and cookie['domain'] not in self.base_url:
                    findings.append(f"❌ Cookie domain mismatch: {cookie['name']} domain={cookie['domain']}")
        
        # Analyze AJAX transmission
        ajax_test = self.results['tests'].get('ajax_transmission', {})
        if ajax_test.get('success'):
            ajax_req = ajax_test.get('cookie_transmission', {}).get('ajax_request', {})
            if ajax_req.get('auth_error'):
                findings.append("❌ AJAX requests failing authentication despite valid session cookies")
        
        # Analyze cross-origin issues
        cross_origin_test = self.results['tests'].get('cross_origin', {})
        if cross_origin_test.get('success'):
            origin_tests = cross_origin_test.get('origin_tests', {})
            same_origin = origin_tests.get('same_origin', {})
            diff_origin = origin_tests.get('different_origin', {})
            
            if same_origin.get('auth_error') and diff_origin.get('auth_error'):
                findings.append("❌ Authentication failing for both same and different origins")
            elif diff_origin.get('auth_error') and not same_origin.get('auth_error'):
                findings.append("❌ Cross-origin requests blocked by cookie policy")
        
        # Analyze container settings
        container_test = self.results['tests'].get('container_settings', {})
        if container_test.get('success'):
            cookie_analysis = container_test.get('cookie_security_analysis', {})
            for cookie_name, cookie_info in cookie_analysis.items():
                issues = cookie_info.get('container_issues', [])
                for issue in issues:
                    findings.append(f"❌ {cookie_name}: {issue}")
        
        # Add recommendations based on findings
        if any('domain mismatch' in finding for finding in findings):
            findings.append("💡 RECOMMENDATION: Check Django ALLOWED_HOSTS and CSRF_COOKIE_DOMAIN settings")
        
        if any('AJAX requests failing' in finding for finding in findings):
            findings.append("💡 RECOMMENDATION: Verify CSRF token handling in AJAX requests")
        
        if any('Cross-origin' in finding for finding in findings):
            findings.append("💡 RECOMMENDATION: Configure CORS settings for reverse proxy scenarios")
        
        self.results['findings'] = findings
    
    def save_results(self, filename: str = None) -> str:
        """Save forensic results to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"session_cookie_forensics_{timestamp}.json"
        
        filepath = os.path.join('/tmp', filename)
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"💾 Forensic results saved to: {filepath}")
        return filepath


def main():
    """Main function to run session cookie forensics"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Session Cookie Forensics')
    parser.add_argument('--url', default='http://localhost:8000', help='NetBox base URL')
    parser.add_argument('--output', help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Initialize forensics
    forensics = SessionCookieForensics(args.url)
    
    # Run comprehensive analysis
    results = forensics.run_comprehensive_forensics()
    
    # Save results
    output_file = forensics.save_results(args.output)
    
    # Print findings
    print("\n" + "="*80)
    print("SESSION COOKIE FORENSICS RESULTS")
    print("="*80)
    
    print(f"Base URL: {args.url}")
    print(f"Total Tests: {len(results.get('tests', {}))}")
    
    print("\nFINDINGS:")
    for finding in results.get('findings', []):
        print(f"  {finding}")
    
    print(f"\n📊 Full results saved to: {output_file}")
    
    return results


if __name__ == '__main__':
    main()