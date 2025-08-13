#!/usr/bin/env python3
"""
Lightweight Sync Button Tester
Direct HTTP-based testing without browser automation
Date: August 11, 2025
"""

import requests
import json
import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LightweightSyncTester:
    def __init__(self):
        self.netbox_url = "http://localhost:8000"
        self.fabric_id = 35
        self.session = requests.Session()
        self.results = {
            "test_start": datetime.now().isoformat(),
            "authentication": {},
            "page_analysis": {},
            "sync_test": {},
            "error_analysis": {},
            "evidence": {}
        }
        
    def test_netbox_connection(self):
        """Test basic NetBox connectivity"""
        logger.info("🌐 Testing NetBox connectivity...")
        
        try:
            response = self.session.get(f"{self.netbox_url}/", timeout=10)
            
            self.results["authentication"]["netbox_accessible"] = response.status_code == 200
            self.results["authentication"]["status_code"] = response.status_code
            
            if response.status_code == 200:
                logger.info("✅ NetBox is accessible")
                
                # Check if authentication is required
                if "login" in response.text.lower():
                    self.results["authentication"]["login_required"] = True
                    logger.info("🔐 Authentication required")
                else:
                    self.results["authentication"]["login_required"] = False
                    logger.info("✅ No authentication required")
                    
                return True
            else:
                logger.error(f"❌ NetBox returned status {response.status_code}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"❌ NetBox connection failed: {e}")
            self.results["authentication"]["connection_error"] = str(e)
            return False
            
    def authenticate_to_netbox(self):
        """Attempt authentication to NetBox"""
        if not self.results["authentication"].get("login_required", False):
            return True
            
        logger.info("🔐 Attempting NetBox authentication...")
        
        try:
            # Get login page
            login_response = self.session.get(f"{self.netbox_url}/login/")
            
            # Extract CSRF token
            csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login_response.text)
            if not csrf_match:
                logger.error("❌ Could not extract CSRF token")
                return False
                
            csrf_token = csrf_match.group(1)
            
            # Try common credentials
            credentials = [
                ("admin", "admin"),
                ("netbox", "netbox"),
                ("admin", "password")
            ]
            
            for username, password in credentials:
                login_data = {
                    'csrfmiddlewaretoken': csrf_token,
                    'username': username,
                    'password': password
                }
                
                auth_response = self.session.post(
                    f"{self.netbox_url}/login/",
                    data=login_data,
                    allow_redirects=True
                )
                
                if "logout" in auth_response.text.lower() or auth_response.url != f"{self.netbox_url}/login/":
                    logger.info(f"✅ Successfully authenticated with {username}")
                    self.results["authentication"]["status"] = "success"
                    self.results["authentication"]["username"] = username
                    return True
                    
            logger.error("❌ All authentication attempts failed")
            self.results["authentication"]["status"] = "failed"
            return False
            
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            self.results["authentication"]["error"] = str(e)
            return False
            
    def analyze_fabric_page(self):
        """Analyze the fabric detail page"""
        logger.info(f"📄 Analyzing fabric page for ID {self.fabric_id}...")
        
        try:
            fabric_url = f"{self.netbox_url}/plugins/hedgehog/fabrics/{self.fabric_id}/"
            response = self.session.get(fabric_url)
            
            self.results["page_analysis"]["status_code"] = response.status_code
            self.results["page_analysis"]["url"] = fabric_url
            
            if response.status_code != 200:
                logger.error(f"❌ Fabric page returned {response.status_code}")
                if response.status_code == 404:
                    self.results["page_analysis"]["error"] = "fabric_not_found"
                elif response.status_code == 403:
                    self.results["page_analysis"]["error"] = "access_forbidden"
                else:
                    self.results["page_analysis"]["error"] = f"http_error_{response.status_code}"
                return False
                
            page_content = response.text
            
            # Analyze page structure
            analysis = {
                "has_sync_button": bool(re.search(r'onclick=["\'].*sync.*["\']', page_content, re.IGNORECASE)),
                "has_sync_status": "sync" in page_content.lower() and "status" in page_content.lower(),
                "has_error_messages": bool(re.search(r'class=["\'].*alert.*danger.*["\']', page_content)),
                "has_javascript": "<script" in page_content,
                "page_size": len(page_content),
                "title": self.extract_page_title(page_content)
            }
            
            # Find sync-related elements
            sync_buttons = re.findall(r'<button[^>]*onclick=["\']([^"\']*sync[^"\']*)["\'][^>]*>(.*?)</button>', page_content, re.IGNORECASE | re.DOTALL)
            analysis["sync_buttons_found"] = len(sync_buttons)
            analysis["sync_buttons_details"] = [{"onclick": onclick, "text": re.sub(r'<[^>]+>', '', text).strip()} for onclick, text in sync_buttons]
            
            # Look for sync status indicators
            status_badges = re.findall(r'<span[^>]*class=["\'][^"\']*badge[^"\']*["\'][^>]*>(.*?)</span>', page_content)
            analysis["status_badges"] = [badge.strip() for badge in status_badges if badge.strip()]
            
            # Check for error messages
            error_elements = re.findall(r'<div[^>]*class=["\'][^"\']*alert[^"\']*danger[^"\']*["\'][^>]*>(.*?)</div>', page_content, re.DOTALL)
            analysis["error_messages"] = [re.sub(r'<[^>]+>', '', error).strip() for error in error_elements]
            
            self.results["page_analysis"]["analysis"] = analysis
            
            if analysis["sync_buttons_found"] > 0:
                logger.info(f"✅ Found {analysis['sync_buttons_found']} sync buttons")
                for btn in analysis["sync_buttons_details"]:
                    logger.info(f"   Button: '{btn['text']}' -> {btn['onclick']}")
            else:
                logger.warning("⚠️ No sync buttons found")
                
            if analysis["error_messages"]:
                logger.warning(f"⚠️ Found {len(analysis['error_messages'])} error messages")
                for msg in analysis["error_messages"]:
                    logger.warning(f"   Error: {msg}")
                    
            return True
            
        except Exception as e:
            logger.error(f"❌ Page analysis failed: {e}")
            self.results["page_analysis"]["error"] = str(e)
            return False
            
    def extract_page_title(self, content):
        """Extract page title from HTML"""
        title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
        return title_match.group(1).strip() if title_match else "Unknown"
        
    def simulate_sync_request(self):
        """Simulate the sync API request"""
        logger.info("🔄 Simulating sync request...")
        
        # Common sync API endpoints to try
        sync_endpoints = [
            f"/plugins/hedgehog/fabrics/{self.fabric_id}/sync/",
            f"/plugins/hedgehog/api/fabrics/{self.fabric_id}/sync/",
            f"/api/plugins/hedgehog/fabrics/{self.fabric_id}/sync/",
            f"/plugins/hedgehog/sync/{self.fabric_id}/",
        ]
        
        sync_results = []
        
        for endpoint in sync_endpoints:
            full_url = f"{self.netbox_url}{endpoint}"
            logger.info(f"🔍 Testing endpoint: {endpoint}")
            
            try:
                # Try GET first
                get_response = self.session.get(full_url)
                get_result = {
                    "endpoint": endpoint,
                    "method": "GET",
                    "status_code": get_response.status_code,
                    "response_size": len(get_response.text),
                    "content_type": get_response.headers.get("content-type", "")
                }
                
                if get_response.status_code == 200:
                    get_result["response_preview"] = get_response.text[:500]
                elif get_response.status_code in [400, 404, 405, 500]:
                    get_result["error_content"] = get_response.text[:500]
                    
                sync_results.append(get_result)
                
                # Try POST if GET didn't work
                if get_response.status_code != 200:
                    # Extract CSRF token for POST
                    csrf_token = self.extract_csrf_token()
                    
                    post_data = {}
                    if csrf_token:
                        post_data["csrfmiddlewaretoken"] = csrf_token
                        
                    post_response = self.session.post(full_url, data=post_data)
                    post_result = {
                        "endpoint": endpoint,
                        "method": "POST",
                        "status_code": post_response.status_code,
                        "response_size": len(post_response.text),
                        "content_type": post_response.headers.get("content-type", "")
                    }
                    
                    if post_response.status_code == 200:
                        post_result["response_preview"] = post_response.text[:500]
                    elif post_response.status_code in [400, 404, 405, 500]:
                        post_result["error_content"] = post_response.text[:500]
                        
                    sync_results.append(post_result)
                    
            except Exception as e:
                sync_results.append({
                    "endpoint": endpoint,
                    "method": "FAILED",
                    "error": str(e)
                })
                
        self.results["sync_test"]["endpoint_tests"] = sync_results
        
        # Find the most promising result
        successful_tests = [r for r in sync_results if r.get("status_code") == 200]
        error_tests = [r for r in sync_results if r.get("status_code", 0) >= 400]
        
        if successful_tests:
            logger.info(f"✅ Found {len(successful_tests)} working endpoints")
            self.results["sync_test"]["status"] = "endpoints_found"
        elif error_tests:
            logger.warning(f"⚠️ Found {len(error_tests)} endpoints with errors")
            self.results["sync_test"]["status"] = "errors_found"
        else:
            logger.error("❌ No sync endpoints responded")
            self.results["sync_test"]["status"] = "no_endpoints"
            
        return len(successful_tests) > 0
        
    def extract_csrf_token(self):
        """Extract CSRF token from current session"""
        try:
            # Get a page that should have CSRF token
            response = self.session.get(f"{self.netbox_url}/plugins/hedgehog/fabrics/{self.fabric_id}/")
            csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.text)
            return csrf_match.group(1) if csrf_match else None
        except:
            return None
            
    def monitor_container_processes(self):
        """Monitor container and system processes"""
        logger.info("🖥️ Monitoring system processes...")
        
        def capture_system_info():
            info = {}
            
            # Check for Docker containers
            try:
                result = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    info["docker_containers"] = result.stdout
                else:
                    info["docker_error"] = result.stderr
            except:
                info["docker_check"] = "not_available"
                
            # Check Python processes
            try:
                result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
                python_processes = [line for line in result.stdout.split('\n') if 'python' in line.lower()]
                info["python_processes"] = python_processes
            except:
                info["process_check"] = "failed"
                
            # Check for NetBox/Django processes
            try:
                result = subprocess.run(["netstat", "-tlnp"], capture_output=True, text=True, timeout=5)
                port_8000 = [line for line in result.stdout.split('\n') if ':8000' in line]
                info["port_8000_listeners"] = port_8000
            except:
                info["netstat_check"] = "failed"
                
            self.results["evidence"]["system_info"] = info
            
        # Run in background
        monitor_thread = threading.Thread(target=capture_system_info)
        monitor_thread.start()
        monitor_thread.join(timeout=15)
        
    def generate_evidence_report(self):
        """Generate comprehensive evidence report"""
        logger.info("📊 Generating evidence report...")
        
        self.results["test_end"] = datetime.now().isoformat()
        
        # Analysis summary
        summary = {
            "netbox_accessible": self.results["authentication"].get("netbox_accessible", False),
            "authentication_successful": self.results["authentication"].get("status") == "success",
            "fabric_page_accessible": self.results["page_analysis"].get("status_code") == 200,
            "sync_buttons_found": self.results["page_analysis"].get("analysis", {}).get("sync_buttons_found", 0) > 0,
            "sync_endpoints_tested": len(self.results["sync_test"].get("endpoint_tests", [])),
            "working_endpoints_found": len([r for r in self.results["sync_test"].get("endpoint_tests", []) if r.get("status_code") == 200])
        }
        
        # Determine primary issue
        if not summary["netbox_accessible"]:
            primary_issue = "NetBox service is not running or not accessible on localhost:8000"
        elif not summary["authentication_successful"] and self.results["authentication"].get("login_required"):
            primary_issue = "Authentication failed - cannot log in to NetBox"
        elif not summary["fabric_page_accessible"]:
            primary_issue = f"Fabric {self.fabric_id} does not exist or is not accessible"
        elif not summary["sync_buttons_found"]:
            primary_issue = "Sync buttons not found on the fabric detail page"
        elif summary["working_endpoints_found"] == 0:
            primary_issue = "No working sync API endpoints found"
        else:
            primary_issue = "Sync functionality appears to be available but needs manual testing"
            
        self.results["summary"] = summary
        self.results["primary_issue"] = primary_issue
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"lightweight_sync_test_report_{timestamp}.json"
        
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        logger.info(f"✅ Evidence report saved: {report_path}")
        return self.results
        
    def run_complete_test(self):
        """Run the complete lightweight test"""
        logger.info("🚀 Starting Lightweight Sync Button Test")
        logger.info("=" * 50)
        
        try:
            # Test connectivity
            if not self.test_netbox_connection():
                return self.generate_evidence_report()
                
            # Try authentication
            if not self.authenticate_to_netbox():
                logger.warning("⚠️ Authentication failed, continuing without auth...")
                
            # Analyze fabric page
            if not self.analyze_fabric_page():
                return self.generate_evidence_report()
                
            # Test sync endpoints
            self.simulate_sync_request()
            
            # Monitor system
            self.monitor_container_processes()
            
            return self.generate_evidence_report()
            
        except Exception as e:
            logger.error(f"❌ Test failed with exception: {e}")
            self.results["fatal_error"] = str(e)
            return self.generate_evidence_report()

def main():
    """Main execution"""
    tester = LightweightSyncTester()
    results = tester.run_complete_test()
    
    print("\n" + "=" * 50)
    print("🎯 LIGHTWEIGHT SYNC BUTTON TEST RESULTS")
    print("=" * 50)
    
    summary = results.get("summary", {})
    primary_issue = results.get("primary_issue", "Unknown")
    
    print(f"🌐 NetBox Accessible: {'✅' if summary.get('netbox_accessible') else '❌'}")
    print(f"🔐 Authentication: {'✅' if summary.get('authentication_successful') else '❌'}")
    print(f"📄 Fabric Page: {'✅' if summary.get('fabric_page_accessible') else '❌'}")
    print(f"🔘 Sync Buttons: {'✅' if summary.get('sync_buttons_found') else '❌'}")
    print(f"🔗 API Endpoints: {summary.get('working_endpoints_found', 0)}/{summary.get('sync_endpoints_tested', 0)}")
    
    print(f"\n🔍 PRIMARY ISSUE:")
    print(f"   {primary_issue}")
    
    # Show sync button details if found
    page_analysis = results.get("page_analysis", {}).get("analysis", {})
    if page_analysis.get("sync_buttons_details"):
        print(f"\n🔘 SYNC BUTTONS FOUND:")
        for btn in page_analysis["sync_buttons_details"]:
            print(f"   • '{btn['text']}' -> {btn['onclick']}")
            
    # Show error messages if found
    if page_analysis.get("error_messages"):
        print(f"\n❌ ERROR MESSAGES ON PAGE:")
        for msg in page_analysis["error_messages"]:
            print(f"   • {msg}")
            
    return results

if __name__ == "__main__":
    main()