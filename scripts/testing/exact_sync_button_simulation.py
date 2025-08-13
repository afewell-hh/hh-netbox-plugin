#!/usr/bin/env python3
"""
Exact Sync Button Simulation
Replicates the exact JavaScript behavior of the sync buttons
Date: August 11, 2025

This script discovers the EXACT error messages a user would see when clicking sync buttons.
"""

import requests
import json
import time
import subprocess
from datetime import datetime
import logging
import re
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExactSyncButtonSimulator:
    def __init__(self):
        self.netbox_url = "http://localhost:8000"
        self.fabric_id = 35
        self.session = requests.Session()
        
        # Replicate exact JavaScript headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        })
        
        self.results = {
            "test_start": datetime.now().isoformat(),
            "exact_sync_results": {},
            "user_visible_errors": {},
            "csrf_token_extraction": {},
            "backend_investigation": {},
            "final_diagnosis": {}
        }
        
    def extract_csrf_token_from_page(self):
        """Extract CSRF token exactly like the JavaScript does"""
        logger.info("🔐 Extracting CSRF token from fabric page...")
        
        try:
            # Get the fabric page
            fabric_url = f"{self.netbox_url}/plugins/hedgehog/fabrics/{self.fabric_id}/"
            response = self.session.get(fabric_url)
            
            if response.status_code != 200:
                logger.error(f"❌ Cannot access fabric page: HTTP {response.status_code}")
                self.results["csrf_token_extraction"]["error"] = f"page_not_accessible_{response.status_code}"
                return None
                
            page_content = response.text
            
            # Method 1: Look for csrfmiddlewaretoken input (Django standard)
            csrf_input_match = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', page_content)
            
            # Method 2: Look for meta csrf-token
            csrf_meta_match = re.search(r'<meta name=["\']csrf-token["\'] content=["\']([^"\']+)["\']', page_content)
            
            # Method 3: Check cookies (getCookie function equivalent)
            csrf_cookie = None
            for cookie in self.session.cookies:
                if cookie.name == 'csrftoken':
                    csrf_cookie = cookie.value
                    break
                    
            results = {
                "input_field_token": csrf_input_match.group(1) if csrf_input_match else None,
                "meta_tag_token": csrf_meta_match.group(1) if csrf_meta_match else None,
                "cookie_token": csrf_cookie,
                "page_size": len(page_content),
                "page_accessible": True
            }
            
            # Use same priority as JavaScript: input field -> meta tag -> cookie
            final_token = results["input_field_token"] or results["meta_tag_token"] or results["cookie_token"]
            
            if final_token:
                logger.info(f"✅ CSRF token extracted: {final_token[:8]}...")
                self.session.headers['X-CSRFToken'] = final_token
                results["selected_token"] = final_token
                results["token_source"] = "input_field" if results["input_field_token"] else ("meta_tag" if results["meta_tag_token"] else "cookie")
            else:
                logger.error("❌ No CSRF token found in any location")
                results["error"] = "no_csrf_token_found"
                
            self.results["csrf_token_extraction"] = results
            return final_token
            
        except Exception as e:
            logger.error(f"❌ CSRF token extraction failed: {e}")
            self.results["csrf_token_extraction"]["error"] = str(e)
            return None
            
    def simulate_triggerSync_button_click(self):
        """Simulate exact triggerSync(35) JavaScript function"""
        logger.info("⚡ Simulating triggerSync(35) button click...")
        
        # Extract the exact URL the JavaScript would use
        sync_url = f"{self.netbox_url}/plugins/hedgehog/fabrics/{self.fabric_id}/github-sync/"
        
        logger.info(f"🎯 Target URL: {sync_url}")
        
        try:
            start_time = time.time()
            
            # Make the exact same request as JavaScript
            response = self.session.post(sync_url, timeout=30)
            
            duration = time.time() - start_time
            
            result = {
                "button_name": "triggerSync (Sync from Git)",
                "target_url": sync_url,
                "method": "POST",
                "status_code": response.status_code,
                "response_time": duration,
                "content_type": response.headers.get("content-type", ""),
                "response_size": len(response.text),
                "timestamp": datetime.now().isoformat()
            }
            
            # Analyze response exactly like JavaScript would
            if response.status_code == 200:
                try:
                    # Try to parse as JSON (what JavaScript expects)
                    json_data = response.json()
                    result["json_response"] = json_data
                    result["javascript_would_show"] = self.analyze_success_response(json_data)
                except json.JSONDecodeError:
                    # Not JSON - JavaScript would fail here
                    result["json_parse_error"] = True
                    result["raw_content"] = response.text[:1000]
                    result["javascript_would_show"] = {
                        "error_type": "json_parse_error",
                        "user_message": "Sync failed: Unexpected response format",
                        "console_error": f"SyntaxError: Unexpected token in JSON"
                    }
                    
            elif response.status_code in [400, 401, 403, 404, 405, 500]:
                # JavaScript error handling for HTTP errors
                try:
                    error_data = response.json()
                    error_message = error_data.get('error') or error_data.get('detail') or f"HTTP {response.status_code}: {response.reason}"
                    result["javascript_would_show"] = {
                        "error_type": "http_error",
                        "user_message": f"Sync failed: {error_message}",
                        "console_error": f"Sync error: Error: {error_message}"
                    }
                except:
                    # Fallback error message
                    result["javascript_would_show"] = {
                        "error_type": "http_error_no_json",
                        "user_message": f"Sync failed: HTTP {response.status_code}: {response.reason}",
                        "console_error": f"Sync error: Error: HTTP {response.status_code}: {response.reason}"
                    }
                    
                result["error_content"] = response.text[:1000]
                
            self.results["exact_sync_results"]["triggerSync"] = result
            
            logger.info(f"📋 triggerSync result: HTTP {response.status_code}")
            if result.get("javascript_would_show"):
                logger.info(f"   User would see: {result['javascript_would_show']['user_message']}")
                
            return result
            
        except requests.exceptions.Timeout:
            result = {
                "button_name": "triggerSync (Sync from Git)",
                "error": "timeout",
                "javascript_would_show": {
                    "error_type": "network_timeout",
                    "user_message": "Sync failed: Request timeout",
                    "console_error": "Sync error: Error: Request timeout"
                }
            }
            self.results["exact_sync_results"]["triggerSync"] = result
            return result
            
        except Exception as e:
            result = {
                "button_name": "triggerSync (Sync from Git)",
                "error": str(e),
                "javascript_would_show": {
                    "error_type": "network_error",
                    "user_message": f"Sync failed: {str(e)}",
                    "console_error": f"Sync error: Error: {str(e)}"
                }
            }
            self.results["exact_sync_results"]["triggerSync"] = result
            return result
            
    def simulate_syncFromFabric_button_click(self):
        """Simulate exact syncFromFabric(35) JavaScript function"""
        logger.info("⚡ Simulating syncFromFabric(35) button click...")
        
        # Extract the exact URL the JavaScript would use
        sync_url = f"{self.netbox_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/"
        
        logger.info(f"🎯 Target URL: {sync_url}")
        
        try:
            start_time = time.time()
            
            # Make the exact same request as JavaScript
            response = self.session.post(sync_url, timeout=30)
            
            duration = time.time() - start_time
            
            result = {
                "button_name": "syncFromFabric (Sync from Fabric)",
                "target_url": sync_url,
                "method": "POST",
                "status_code": response.status_code,
                "response_time": duration,
                "content_type": response.headers.get("content-type", ""),
                "response_size": len(response.text),
                "timestamp": datetime.now().isoformat()
            }
            
            # Analyze response exactly like JavaScript would
            if response.status_code == 200:
                try:
                    # Try to parse as JSON (what JavaScript expects)
                    json_data = response.json()
                    result["json_response"] = json_data
                    result["javascript_would_show"] = self.analyze_success_response(json_data, is_fabric_sync=True)
                except json.JSONDecodeError:
                    # Not JSON - JavaScript would fail here
                    result["json_parse_error"] = True
                    result["raw_content"] = response.text[:1000]
                    result["javascript_would_show"] = {
                        "error_type": "json_parse_error",
                        "user_message": "Fabric sync failed: Unexpected response format",
                        "console_error": f"SyntaxError: Unexpected token in JSON"
                    }
                    
            elif response.status_code in [400, 401, 403, 404, 405, 500]:
                # JavaScript error handling for HTTP errors
                try:
                    error_data = response.json()
                    error_message = error_data.get('error') or error_data.get('detail') or f"HTTP {response.status_code}: {response.reason}"
                    result["javascript_would_show"] = {
                        "error_type": "http_error",
                        "user_message": f"Fabric sync failed: {error_message}",
                        "console_error": f"Fabric sync error: Error: {error_message}"
                    }
                except:
                    # Fallback error message
                    result["javascript_would_show"] = {
                        "error_type": "http_error_no_json",
                        "user_message": f"Fabric sync failed: HTTP {response.status_code}: {response.reason}",
                        "console_error": f"Fabric sync error: Error: HTTP {response.status_code}: {response.reason}"
                    }
                    
                result["error_content"] = response.text[:1000]
                
            self.results["exact_sync_results"]["syncFromFabric"] = result
            
            logger.info(f"📋 syncFromFabric result: HTTP {response.status_code}")
            if result.get("javascript_would_show"):
                logger.info(f"   User would see: {result['javascript_would_show']['user_message']}")
                
            return result
            
        except Exception as e:
            result = {
                "button_name": "syncFromFabric (Sync from Fabric)",
                "error": str(e),
                "javascript_would_show": {
                    "error_type": "network_error",
                    "user_message": f"Fabric sync failed: {str(e)}",
                    "console_error": f"Fabric sync error: Error: {str(e)}"
                }
            }
            self.results["exact_sync_results"]["syncFromFabric"] = result
            return result
            
    def analyze_success_response(self, json_data, is_fabric_sync=False):
        """Analyze JSON response exactly like JavaScript would"""
        prefix = "Fabric sync" if is_fabric_sync else "Sync"
        
        if json_data.get("success"):
            return {
                "alert_type": "success",
                "user_message": json_data.get("message", f"{prefix} completed successfully"),
                "page_reload": True,
                "reload_delay": 1500
            }
        else:
            error_msg = json_data.get("error") or json_data.get("message") or f"{prefix} failed"
            return {
                "alert_type": "danger", 
                "user_message": error_msg,
                "page_reload": False
            }
            
    def investigate_backend_sync_infrastructure(self):
        """Investigate the backend sync infrastructure"""
        logger.info("🔍 Investigating backend sync infrastructure...")
        
        investigation = {
            "rq_workers": [],
            "sync_tasks": [],
            "container_logs": "",
            "process_analysis": {}
        }
        
        # Check RQ workers
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
            processes = result.stdout.split('\n')
            
            rq_workers = [line for line in processes if 'rqworker' in line]
            investigation["rq_workers"] = rq_workers
            
            hedgehog_workers = [line for line in processes if 'hedgehog_sync' in line]
            investigation["hedgehog_sync_workers"] = hedgehog_workers
            
            if hedgehog_workers:
                logger.info(f"✅ Found {len(hedgehog_workers)} hedgehog sync workers")
            else:
                logger.warning("⚠️ No hedgehog sync workers found")
                
        except Exception as e:
            investigation["process_check_error"] = str(e)
            
        # Try to get container logs
        try:
            result = subprocess.run(
                ["sudo", "docker", "logs", "--tail", "50", "--since", "5m", "netbox"], 
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                investigation["container_logs"] = result.stdout
                
                # Look for sync-related errors in logs
                log_lines = result.stdout.split('\n')
                sync_errors = [line for line in log_lines if any(keyword in line.lower() for keyword in ['sync', 'error', 'exception', 'traceback'])]
                investigation["sync_related_log_entries"] = sync_errors
                
            else:
                investigation["container_logs_error"] = result.stderr
        except Exception as e:
            investigation["container_logs_error"] = str(e)
            
        self.results["backend_investigation"] = investigation
        return investigation
        
    def generate_final_diagnosis(self):
        """Generate final user-focused diagnosis"""
        logger.info("🏥 Generating final diagnosis...")
        
        trigger_sync = self.results["exact_sync_results"].get("triggerSync", {})
        fabric_sync = self.results["exact_sync_results"].get("syncFromFabric", {})
        
        # Extract user-visible error messages
        user_errors = []
        
        if trigger_sync.get("javascript_would_show"):
            user_errors.append({
                "button": "Sync from Git",
                "message": trigger_sync["javascript_would_show"]["user_message"],
                "error_type": trigger_sync["javascript_would_show"]["error_type"]
            })
            
        if fabric_sync.get("javascript_would_show"):
            user_errors.append({
                "button": "Sync from Fabric", 
                "message": fabric_sync["javascript_would_show"]["user_message"],
                "error_type": fabric_sync["javascript_would_show"]["error_type"]
            })
            
        # Determine root cause
        if trigger_sync.get("status_code") == 403 or fabric_sync.get("status_code") == 403:
            root_cause = "Authentication/Authorization Error"
            explanation = "The sync buttons require user authentication. The current session is not authenticated or lacks sufficient permissions."
            solution = "Login to NetBox with appropriate credentials before attempting sync operations."
        elif trigger_sync.get("status_code") == 404 or fabric_sync.get("status_code") == 404:
            root_cause = "Sync Endpoints Not Found"
            explanation = "The sync API endpoints are not properly configured or the URL patterns don't match."
            solution = "Check NetBox plugin installation and URL configuration."
        elif trigger_sync.get("status_code") == 500 or fabric_sync.get("status_code") == 500:
            root_cause = "Server-Side Error"
            explanation = "The sync functionality encounters internal server errors during execution."
            solution = "Check NetBox logs and backend sync worker processes."
        else:
            root_cause = "Network or JavaScript Error"
            explanation = "The sync requests fail due to network issues or JavaScript execution problems."
            solution = "Check network connectivity and browser JavaScript console for errors."
            
        diagnosis = {
            "user_visible_errors": user_errors,
            "root_cause": root_cause,
            "explanation": explanation,
            "recommended_solution": solution,
            "sync_buttons_found": len(user_errors),
            "all_buttons_fail": len(user_errors) == 2 and all(err["error_type"] != "success" for err in user_errors)
        }
        
        self.results["final_diagnosis"] = diagnosis
        return diagnosis
        
    def run_complete_simulation(self):
        """Run the complete exact sync button simulation"""
        logger.info("🎯 Starting Exact Sync Button Simulation")
        logger.info("=" * 60)
        
        try:
            # Extract CSRF token (required for sync requests)
            csrf_token = self.extract_csrf_token_from_page()
            
            # Simulate both sync button clicks
            trigger_result = self.simulate_triggerSync_button_click()
            fabric_result = self.simulate_syncFromFabric_button_click()
            
            # Investigate backend
            backend_info = self.investigate_backend_sync_infrastructure()
            
            # Generate final diagnosis
            diagnosis = self.generate_final_diagnosis()
            
            # Save comprehensive results
            self.results["test_end"] = datetime.now().isoformat()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = f"exact_sync_button_simulation_report_{timestamp}.json"
            
            with open(report_path, 'w') as f:
                json.dump(self.results, f, indent=2)
                
            logger.info(f"✅ Comprehensive report saved: {report_path}")
            
            return self.results
            
        except Exception as e:
            logger.error(f"❌ Simulation failed: {e}")
            self.results["fatal_error"] = str(e)
            return self.results

def main():
    """Main execution with user-friendly output"""
    simulator = ExactSyncButtonSimulator()
    results = simulator.run_complete_simulation()
    
    print("\n" + "=" * 60)
    print("🎯 EXACT SYNC BUTTON SIMULATION RESULTS")
    print("=" * 60)
    
    diagnosis = results.get("final_diagnosis", {})
    
    print(f"🔍 ROOT CAUSE: {diagnosis.get('root_cause', 'Unknown')}")
    print(f"📋 EXPLANATION: {diagnosis.get('explanation', 'No explanation available')}")
    print(f"💡 SOLUTION: {diagnosis.get('recommended_solution', 'No solution available')}")
    
    print(f"\n📊 SYNC BUTTONS TESTED: {diagnosis.get('sync_buttons_found', 0)}")
    
    user_errors = diagnosis.get("user_visible_errors", [])
    if user_errors:
        print(f"\n❌ USER WOULD SEE THESE ERROR MESSAGES:")
        for error in user_errors:
            print(f"   🔘 {error['button']}: \"{error['message']}\"")
            
    # Show technical details
    print(f"\n🔧 TECHNICAL DETAILS:")
    trigger_sync = results.get("exact_sync_results", {}).get("triggerSync", {})
    fabric_sync = results.get("exact_sync_results", {}).get("syncFromFabric", {})
    
    if trigger_sync:
        print(f"   • Sync from Git: HTTP {trigger_sync.get('status_code', 'N/A')} - {trigger_sync.get('target_url', 'N/A')}")
        
    if fabric_sync:
        print(f"   • Sync from Fabric: HTTP {fabric_sync.get('status_code', 'N/A')} - {fabric_sync.get('target_url', 'N/A')}")
        
    # Show CSRF token status
    csrf_info = results.get("csrf_token_extraction", {})
    if csrf_info.get("selected_token"):
        print(f"   • CSRF Token: Found ({csrf_info.get('token_source', 'unknown source')})")
    else:
        print(f"   • CSRF Token: Not found - this may cause authentication issues")
        
    return results

if __name__ == "__main__":
    main()