#!/usr/bin/env python3
"""
Simple Sync Button 403 Error Investigation Agent
SCOPE: ONLY test sync button behavior and capture 403 error details using HTTP requests
"""

import os
import sys
import json
import requests
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

class SimpleSyncButton403Investigator:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.fabric_url = f"{self.base_url}/plugins/hedgehog/fabrics/35/"
        self.session = requests.Session()
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "task": "Simple Sync Button 403 Error Investigation",
            "scope": "ONLY test sync button behavior and capture 403 error details",
            "fabric_url": self.fabric_url,
            "login_successful": False,
            "page_loaded": False,
            "sync_button_found": False,
            "sync_endpoint_discovered": False,
            "sync_attempt_made": False,
            "error_403_captured": False,
            "exact_url_called": None,
            "exact_error_response": None,
            "csrf_error_found": False,
            "csrf_token_present": False,
            "csrf_token_value": None,
            "response_headers": {},
            "response_body": None,
            "status_code": None
        }

    def login_to_netbox(self):
        """Login to NetBox with admin credentials"""
        try:
            # Get login page to get CSRF token
            login_url = f"{self.base_url}/login/"
            response = self.session.get(login_url)
            
            if response.status_code != 200:
                self.results["login_error"] = f"Failed to access login page: {response.status_code}"
                return False
            
            # Extract CSRF token from login page
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
            
            if not csrf_input:
                self.results["login_error"] = "No CSRF token found on login page"
                return False
            
            csrf_token = csrf_input.get('value')
            
            # Login with credentials
            login_data = {
                'username': 'admin',
                'password': 'admin',
                'csrfmiddlewaretoken': csrf_token
            }
            
            response = self.session.post(login_url, data=login_data)
            
            # Check if login was successful (should redirect)
            if response.status_code == 200 and "/login/" in response.url:
                self.results["login_error"] = "Login failed - still on login page"
                return False
            
            self.results["login_successful"] = True
            return True
            
        except Exception as e:
            self.results["login_error"] = str(e)
            return False

    def load_fabric_page(self):
        """Load fabric page and check for sync button"""
        try:
            response = self.session.get(self.fabric_url)
            
            if response.status_code != 200:
                self.results["page_load_error"] = f"Failed to load fabric page: {response.status_code}"
                return False
            
            self.results["page_loaded"] = True
            
            # Parse page content to find sync button
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for sync-related buttons or forms
            sync_buttons = []
            
            # Check for buttons with sync-related text
            for button in soup.find_all(['button', 'input', 'a']):
                text = button.get_text().lower()
                onclick = button.get('onclick', '').lower()
                name = button.get('name', '').lower()
                value = button.get('value', '').lower()
                
                if any(term in f"{text} {onclick} {name} {value}" for term in ['sync', 'synchronize']):
                    sync_buttons.append({
                        'tag': button.name,
                        'text': button.get_text().strip(),
                        'onclick': button.get('onclick'),
                        'href': button.get('href'),
                        'name': button.get('name'),
                        'value': button.get('value'),
                        'form_action': button.find_parent('form').get('action') if button.find_parent('form') else None
                    })
            
            if sync_buttons:
                self.results["sync_button_found"] = True
                self.results["sync_buttons_found"] = sync_buttons
                
                # Try to determine sync endpoint
                for button in sync_buttons:
                    if button['onclick']:
                        # Extract URL from onclick
                        import re
                        url_match = re.search(r'["\']([^"\']*sync[^"\']*)["\']', button['onclick'])
                        if url_match:
                            self.results["sync_endpoint_discovered"] = True
                            self.results["sync_endpoint"] = url_match.group(1)
                            break
                    elif button['href']:
                        if 'sync' in button['href']:
                            self.results["sync_endpoint_discovered"] = True
                            self.results["sync_endpoint"] = button['href']
                            break
                    elif button['form_action']:
                        if 'sync' in button['form_action']:
                            self.results["sync_endpoint_discovered"] = True
                            self.results["sync_endpoint"] = button['form_action']
                            break
            
            # Extract CSRF token from page
            csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
            if csrf_input:
                self.results["csrf_token_present"] = True
                self.results["csrf_token_value"] = csrf_input.get('value')
            
            return True
            
        except Exception as e:
            self.results["page_load_error"] = str(e)
            return False

    def attempt_sync_request(self):
        """Attempt to make sync request and capture 403 error"""
        try:
            # Try common sync endpoints if not discovered
            potential_endpoints = []
            
            if self.results.get("sync_endpoint"):
                potential_endpoints.append(self.results["sync_endpoint"])
            
            # Add common sync endpoint patterns
            potential_endpoints.extend([
                f"/plugins/hedgehog/fabrics/35/sync/",
                f"/plugins/hedgehog/sync/35/",
                f"/plugins/hedgehog/fabrics/35/sync-from-fabric/",
                f"/api/plugins/hedgehog/fabrics/35/sync/",
                f"/plugins/hedgehog/ajax/sync/35/",
            ])
            
            for endpoint in potential_endpoints:
                try:
                    # Make endpoint absolute
                    if endpoint.startswith('/'):
                        full_url = f"{self.base_url}{endpoint}"
                    else:
                        full_url = urljoin(self.fabric_url, endpoint)
                    
                    self.results["exact_url_called"] = full_url
                    
                    # Prepare headers
                    headers = {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Referer': self.fabric_url,
                    }
                    
                    # Add CSRF token if available
                    if self.results.get("csrf_token_value"):
                        headers['X-CSRFToken'] = self.results["csrf_token_value"]
                    
                    # Try POST request (most likely for sync operation)
                    data = {}
                    if self.results.get("csrf_token_value"):
                        data['csrfmiddlewaretoken'] = self.results["csrf_token_value"]
                    
                    response = self.session.post(full_url, headers=headers, data=data)
                    
                    self.results["sync_attempt_made"] = True
                    self.results["status_code"] = response.status_code
                    self.results["response_headers"] = dict(response.headers)
                    
                    # Capture response body
                    try:
                        self.results["response_body"] = response.text[:1000]  # First 1000 chars
                    except:
                        self.results["response_body"] = "Unable to capture response body"
                    
                    if response.status_code == 403:
                        self.results["error_403_captured"] = True
                        self.results["exact_error_response"] = {
                            "status_code": response.status_code,
                            "reason": response.reason,
                            "url": full_url,
                            "headers": dict(response.headers),
                            "body": response.text[:500],  # First 500 chars
                            "endpoint_tested": endpoint
                        }
                        
                        # Check for CSRF-related errors
                        error_text = response.text.lower()
                        if any(term in error_text for term in ['csrf', 'forbidden', 'token', 'invalid token']):
                            self.results["csrf_error_found"] = True
                        
                        print(f"✅ Found 403 error on endpoint: {endpoint}")
                        return True
                    
                    elif response.status_code in [200, 302]:
                        self.results["sync_endpoint_works"] = True
                        self.results["working_endpoint"] = endpoint
                        print(f"✅ Found working sync endpoint: {endpoint}")
                        return True
                    
                    else:
                        print(f"🔍 Endpoint {endpoint} returned status: {response.status_code}")
                    
                except requests.exceptions.RequestException as e:
                    print(f"❌ Error testing endpoint {endpoint}: {str(e)}")
                    continue
            
            return False
            
        except Exception as e:
            self.results["sync_attempt_error"] = str(e)
            return False

    def investigate(self):
        """Main investigation method"""
        print("🔍 Starting Simple Sync Button 403 Error Investigation...")
        
        # Install BeautifulSoup if not available
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print("📦 Installing BeautifulSoup...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4"])
            from bs4 import BeautifulSoup
        
        # Step 1: Login
        print("📝 Logging into NetBox...")
        if not self.login_to_netbox():
            return self.results
        
        # Step 2: Load fabric page
        print("🔗 Loading fabric page...")
        if not self.load_fabric_page():
            return self.results
        
        # Step 3: Attempt sync request
        print("🖱️ Attempting sync requests...")
        self.attempt_sync_request()
        
        return self.results

    def save_results(self):
        """Save investigation results to file"""
        results_path = "/home/ubuntu/cc/hedgehog-netbox-plugin/tests/simple_sync_button_403_investigation_results.json"
        with open(results_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        return results_path

def main():
    investigator = SimpleSyncButton403Investigator()
    results = investigator.investigate()
    results_path = investigator.save_results()
    
    print("\n" + "="*60)
    print("🔍 SIMPLE SYNC BUTTON 403 ERROR INVESTIGATION COMPLETE")
    print("="*60)
    
    print(f"\n📊 INVESTIGATION SUMMARY:")
    print(f"   Login Successful: {results['login_successful']}")
    print(f"   Page Loaded: {results['page_loaded']}")
    print(f"   Sync Button Found: {results['sync_button_found']}")
    print(f"   Sync Endpoint Discovered: {results['sync_endpoint_discovered']}")
    print(f"   Sync Attempt Made: {results['sync_attempt_made']}")
    print(f"   403 Error Captured: {results['error_403_captured']}")
    print(f"   CSRF Error Found: {results['csrf_error_found']}")
    print(f"   CSRF Token Present: {results['csrf_token_present']}")
    
    if results['error_403_captured']:
        print(f"\n🚨 403 ERROR DETAILS:")
        error_response = results['exact_error_response']
        print(f"   URL Called: {error_response['url']}")
        print(f"   Status Code: {error_response['status_code']}")
        print(f"   Reason: {error_response['reason']}")
        print(f"   Endpoint Tested: {error_response['endpoint_tested']}")
        print(f"   Response Body Preview: {error_response['body'][:200]}...")
    
    if results['sync_button_found'] and 'sync_buttons_found' in results:
        print(f"\n🔘 SYNC BUTTONS FOUND ({len(results['sync_buttons_found'])}):")
        for i, button in enumerate(results['sync_buttons_found']):
            print(f"   Button {i+1}:")
            print(f"     Text: {button['text']}")
            print(f"     Tag: {button['tag']}")
            if button['onclick']:
                print(f"     OnClick: {button['onclick'][:50]}...")
            if button['href']:
                print(f"     Href: {button['href']}")
    
    print(f"\n📁 Results saved to: {results_path}")

if __name__ == "__main__":
    main()