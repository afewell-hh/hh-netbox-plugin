#!/usr/bin/env python3
"""
Sync Button 403 Error Investigation Agent
SCOPE: ONLY test sync button behavior and capture 403 error details
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class SyncButton403Investigator:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.fabric_url = f"{self.base_url}/plugins/hedgehog/fabrics/35/"
        self.driver = None
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "task": "Sync Button 403 Error Investigation",
            "scope": "ONLY test sync button behavior and capture 403 error details",
            "fabric_url": self.fabric_url,
            "login_successful": False,
            "page_loaded": False,
            "sync_button_found": False,
            "sync_button_clickable": False,
            "sync_attempt_made": False,
            "error_403_captured": False,
            "exact_url_called": None,
            "exact_error_response": None,
            "csrf_error_found": False,
            "csrf_token_present": False,
            "network_requests": [],
            "button_attributes": {},
            "screenshot_taken": False,
            "raw_network_logs": []
        }

    def setup_driver(self):
        """Setup Chrome driver with network logging enabled"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Enable network logging
            chrome_options.add_argument("--enable-logging")
            chrome_options.add_argument("--log-level=0")
            chrome_options.set_capability('goog:loggingPrefs', {
                'performance': 'ALL',
                'browser': 'ALL'
            })
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            return True
        except Exception as e:
            self.results["setup_error"] = str(e)
            return False

    def login_to_netbox(self):
        """Login to NetBox with admin credentials"""
        try:
            self.driver.get(f"{self.base_url}/login/")
            
            # Wait for login form
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            password_field = self.driver.find_element(By.NAME, "password")
            
            # Enter credentials
            username_field.send_keys("admin")
            password_field.send_keys("admin")
            
            # Submit form
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Wait for redirect
            WebDriverWait(self.driver, 10).until(
                lambda driver: "/login/" not in driver.current_url
            )
            
            self.results["login_successful"] = True
            return True
            
        except Exception as e:
            self.results["login_error"] = str(e)
            return False

    def navigate_to_fabric_page(self):
        """Navigate to fabric 35 detail page"""
        try:
            self.driver.get(self.fabric_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Check if we're on the right page
            current_url = self.driver.current_url
            self.results["actual_url"] = current_url
            self.results["page_loaded"] = "fabrics/35" in current_url
            
            return self.results["page_loaded"]
            
        except Exception as e:
            self.results["navigation_error"] = str(e)
            return False

    def find_sync_button(self):
        """Find the sync button and capture its attributes"""
        try:
            # Common sync button selectors
            sync_button_selectors = [
                "button[onclick*='sync']",
                "a[onclick*='sync']",
                "input[onclick*='sync']",
                "button:contains('Sync')",
                "a:contains('Sync')",
                "[data-action*='sync']",
                ".sync-button",
                "#sync-button",
                "button[name*='sync']",
                "input[value*='Sync']"
            ]
            
            sync_button = None
            button_selector_used = None
            
            for selector in sync_button_selectors:
                try:
                    if "contains" in selector:
                        # Use XPath for text-based search
                        xpath_selector = f"//button[contains(text(), 'Sync')] | //a[contains(text(), 'Sync')]"
                        elements = self.driver.find_elements(By.XPATH, xpath_selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        sync_button = elements[0]
                        button_selector_used = selector
                        break
                except:
                    continue
            
            if sync_button:
                self.results["sync_button_found"] = True
                self.results["button_selector_used"] = button_selector_used
                
                # Capture button attributes
                self.results["button_attributes"] = {
                    "tag_name": sync_button.tag_name,
                    "text": sync_button.text,
                    "enabled": sync_button.is_enabled(),
                    "displayed": sync_button.is_displayed(),
                    "clickable": sync_button.is_enabled() and sync_button.is_displayed()
                }
                
                # Get all attributes
                try:
                    attributes = self.driver.execute_script(
                        "var items = {}; for (index = 0; index < arguments[0].attributes.length; ++index) { items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value }; return items;",
                        sync_button
                    )
                    self.results["button_attributes"]["all_attributes"] = attributes
                except:
                    pass
                
                self.results["sync_button_clickable"] = self.results["button_attributes"]["clickable"]
                
                return sync_button
            else:
                # Search for any button with sync-related text
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                
                sync_elements = []
                for element in all_buttons + all_links:
                    text = element.text.lower()
                    if "sync" in text:
                        sync_elements.append({
                            "tag": element.tag_name,
                            "text": element.text,
                            "enabled": element.is_enabled(),
                            "displayed": element.is_displayed()
                        })
                
                self.results["potential_sync_elements"] = sync_elements
                return None
                
        except Exception as e:
            self.results["button_search_error"] = str(e)
            return None

    def check_csrf_token(self):
        """Check for CSRF token presence"""
        try:
            # Check for CSRF token in forms
            csrf_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[name='csrfmiddlewaretoken']")
            if csrf_inputs:
                self.results["csrf_token_present"] = True
                self.results["csrf_token_value"] = csrf_inputs[0].get_attribute("value")[:20] + "..."
            
            # Check for CSRF token in meta tags
            csrf_meta = self.driver.find_elements(By.CSS_SELECTOR, "meta[name='csrf-token']")
            if csrf_meta:
                self.results["csrf_meta_present"] = True
            
        except Exception as e:
            self.results["csrf_check_error"] = str(e)

    def capture_network_logs(self):
        """Capture network logs before button click"""
        try:
            logs = self.driver.get_log('performance')
            for log in logs:
                message = json.loads(log['message'])
                if message['message']['method'] in ['Network.responseReceived', 'Network.requestWillBeSent']:
                    self.results["raw_network_logs"].append(message)
        except Exception as e:
            self.results["network_log_error"] = str(e)

    def click_sync_button_and_capture_error(self, sync_button):
        """Click sync button and capture 403 error details"""
        try:
            # Capture network logs before click
            self.capture_network_logs()
            
            # Click the sync button
            self.driver.execute_script("arguments[0].click();", sync_button)
            self.results["sync_attempt_made"] = True
            
            # Wait a moment for the request to complete
            time.sleep(2)
            
            # Capture network logs after click
            logs = self.driver.get_log('performance')
            
            # Parse network logs for 403 errors
            for log in logs:
                try:
                    message = json.loads(log['message'])
                    
                    if message['message']['method'] == 'Network.responseReceived':
                        response = message['message']['params']['response']
                        
                        if response['status'] == 403:
                            self.results["error_403_captured"] = True
                            self.results["exact_url_called"] = response['url']
                            self.results["exact_error_response"] = {
                                "status": response['status'],
                                "statusText": response['statusText'],
                                "url": response['url'],
                                "headers": response.get('headers', {}),
                                "mimeType": response.get('mimeType', ''),
                                "timestamp": log['timestamp']
                            }
                            
                            # Check for CSRF-related errors
                            if any(csrf_term in str(response).lower() for csrf_term in ['csrf', 'forbidden', 'token']):
                                self.results["csrf_error_found"] = True
                            
                        # Capture all network requests for context
                        self.results["network_requests"].append({
                            "url": response['url'],
                            "status": response['status'],
                            "method": response.get('requestHeaders', {}).get('method', 'Unknown'),
                            "timestamp": log['timestamp']
                        })
                        
                except Exception as e:
                    continue
            
            # Check for any visible error messages on the page
            try:
                error_elements = self.driver.find_elements(By.CSS_SELECTOR, ".alert-danger, .error, .alert-error")
                if error_elements:
                    self.results["visible_error_messages"] = [elem.text for elem in error_elements]
            except:
                pass
            
            # Check current URL for any changes
            self.results["url_after_click"] = self.driver.current_url
            
            return True
            
        except Exception as e:
            self.results["click_error"] = str(e)
            return False

    def take_screenshot(self):
        """Take screenshot of current page state"""
        try:
            screenshot_path = "/home/ubuntu/cc/hedgehog-netbox-plugin/tests/sync_button_403_screenshot.png"
            self.driver.save_screenshot(screenshot_path)
            self.results["screenshot_taken"] = True
            self.results["screenshot_path"] = screenshot_path
        except Exception as e:
            self.results["screenshot_error"] = str(e)

    def investigate(self):
        """Main investigation method"""
        print("🔍 Starting Sync Button 403 Error Investigation...")
        
        if not self.setup_driver():
            return self.results
        
        try:
            # Step 1: Login
            print("📝 Logging into NetBox...")
            if not self.login_to_netbox():
                return self.results
            
            # Step 2: Navigate to fabric page
            print("🔗 Navigating to fabric page...")
            if not self.navigate_to_fabric_page():
                return self.results
            
            # Step 3: Check CSRF token
            print("🔒 Checking CSRF token...")
            self.check_csrf_token()
            
            # Step 4: Find sync button
            print("🔍 Finding sync button...")
            sync_button = self.find_sync_button()
            
            if sync_button:
                # Step 5: Click and capture error
                print("🖱️ Clicking sync button and capturing error...")
                self.click_sync_button_and_capture_error(sync_button)
            
            # Step 6: Take screenshot
            print("📸 Taking screenshot...")
            self.take_screenshot()
            
        finally:
            if self.driver:
                self.driver.quit()
        
        return self.results

    def save_results(self):
        """Save investigation results to file"""
        results_path = "/home/ubuntu/cc/hedgehog-netbox-plugin/tests/sync_button_403_investigation_results.json"
        with open(results_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        self.results["results_saved_to"] = results_path
        return results_path

def main():
    investigator = SyncButton403Investigator()
    results = investigator.investigate()
    results_path = investigator.save_results()
    
    print("\n" + "="*60)
    print("🔍 SYNC BUTTON 403 ERROR INVESTIGATION COMPLETE")
    print("="*60)
    
    print(f"\n📊 INVESTIGATION SUMMARY:")
    print(f"   Login Successful: {results['login_successful']}")
    print(f"   Page Loaded: {results['page_loaded']}")
    print(f"   Sync Button Found: {results['sync_button_found']}")
    print(f"   Sync Button Clickable: {results['sync_button_clickable']}")
    print(f"   Sync Attempt Made: {results['sync_attempt_made']}")
    print(f"   403 Error Captured: {results['error_403_captured']}")
    print(f"   CSRF Error Found: {results['csrf_error_found']}")
    print(f"   CSRF Token Present: {results['csrf_token_present']}")
    
    if results['error_403_captured']:
        print(f"\n🚨 403 ERROR DETAILS:")
        print(f"   URL Called: {results['exact_url_called']}")
        print(f"   Status: {results['exact_error_response']['status']}")
        print(f"   Status Text: {results['exact_error_response']['statusText']}")
    
    if results['sync_button_found']:
        print(f"\n🔘 SYNC BUTTON DETAILS:")
        print(f"   Selector Used: {results.get('button_selector_used', 'N/A')}")
        print(f"   Button Text: {results['button_attributes'].get('text', 'N/A')}")
        print(f"   Enabled: {results['button_attributes'].get('enabled', 'N/A')}")
        print(f"   Displayed: {results['button_attributes'].get('displayed', 'N/A')}")
    
    print(f"\n📁 Results saved to: {results_path}")
    
    if results['screenshot_taken']:
        print(f"📸 Screenshot saved to: {results['screenshot_path']}")

if __name__ == "__main__":
    main()