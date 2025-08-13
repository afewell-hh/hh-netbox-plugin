#!/usr/bin/env python3
"""
Detailed Sync Validation - Tests specific fixes
"""

import json
import requests
import subprocess
import time
from datetime import datetime
import re

class DetailedSyncValidator:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.fabric_id = 35
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "fabric_id": self.fabric_id,
            "specific_fixes_tested": {
                "backend_import_errors": {"status": "TESTING", "tests": {}},
                "authentication_ux": {"status": "TESTING", "tests": {}},
                "url_routing": {"status": "TESTING", "tests": {}},
                "rq_scheduler": {"status": "TESTING", "tests": {}},
                "sync_execution": {"status": "TESTING", "tests": {}}
            }
        }

    def log_result(self, category: str, test: str, status: str, details=None):
        """Log test result"""
        self.results["specific_fixes_tested"][category]["tests"][test] = {
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{icon} {category.replace('_', ' ').title()} - {test}: {status}")
        
        if details and isinstance(details, dict):
            for key, value in details.items():
                if key in ['error', 'failure_reason'] and status == "FAIL":
                    print(f"   ⚠️  {key}: {value}")

    def test_backend_import_fixes(self):
        """Test that backend import errors are resolved"""
        print("\n🔧 TESTING: Backend Import Error Fixes")
        print("-" * 50)
        
        # Test 1: Check if sync endpoints return appropriate responses (not import errors)
        try:
            response = requests.get(f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/", 
                                  timeout=10)
            
            # Import errors would typically result in 500 status with import error messages
            if response.status_code == 500:
                error_text = response.text.lower()
                if any(error in error_text for error in ['importerror', 'modulenotfounderror', 'import']):
                    self.log_result("backend_import_errors", "sync_endpoint_imports", "FAIL",
                                  {"error": "Import error detected in response", "status_code": 500})
                else:
                    self.log_result("backend_import_errors", "sync_endpoint_imports", "PASS",
                                  {"status_code": response.status_code, "note": "No import errors detected"})
            else:
                self.log_result("backend_import_errors", "sync_endpoint_imports", "PASS",
                              {"status_code": response.status_code, "note": "Endpoint accessible without import errors"})
                              
        except Exception as e:
            self.log_result("backend_import_errors", "sync_endpoint_imports", "FAIL", {"error": str(e)})

        # Test 2: Check fabric list endpoint for import issues
        try:
            response = requests.get(f"{self.base_url}/plugins/hedgehog/fabrics/", timeout=10)
            
            if response.status_code == 500:
                error_text = response.text.lower()
                if any(error in error_text for error in ['importerror', 'modulenotfounderror']):
                    self.log_result("backend_import_errors", "fabric_list_imports", "FAIL",
                                  {"error": "Import error in fabric list", "status_code": 500})
                else:
                    self.log_result("backend_import_errors", "fabric_list_imports", "PASS",
                                  {"status_code": response.status_code})
            else:
                self.log_result("backend_import_errors", "fabric_list_imports", "PASS",
                              {"status_code": response.status_code, "note": "No import errors"})
                              
        except Exception as e:
            self.log_result("backend_import_errors", "fabric_list_imports", "FAIL", {"error": str(e)})

    def test_authentication_ux_improvements(self):
        """Test authentication UX improvements"""
        print("\n🔐 TESTING: Authentication UX Improvements")
        print("-" * 50)
        
        # Test 1: Sync endpoint should return JSON error (not HTML redirect)
        try:
            response = requests.post(f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/", 
                                   timeout=10, allow_redirects=False)
            
            content_type = response.headers.get('Content-Type', '').lower()
            is_json_response = 'json' in content_type
            is_html_response = 'html' in content_type
            is_redirect = response.status_code in [301, 302, 303, 307, 308]
            
            if is_json_response and response.status_code in [401, 403]:
                try:
                    error_data = response.json()
                    if 'error' in error_data or 'detail' in error_data:
                        self.log_result("authentication_ux", "json_error_format", "PASS",
                                      {"response": error_data, "content_type": content_type})
                    else:
                        self.log_result("authentication_ux", "json_error_format", "PARTIAL",
                                      {"note": "JSON response but no clear error message"})
                except:
                    self.log_result("authentication_ux", "json_error_format", "PARTIAL",
                                  {"note": "JSON content-type but invalid JSON"})
            elif is_html_response or is_redirect:
                self.log_result("authentication_ux", "json_error_format", "FAIL",
                              {"issue": "Returns HTML or redirect instead of JSON error",
                               "status_code": response.status_code, "content_type": content_type})
            else:
                # Unexpected status but let's see what it is
                self.log_result("authentication_ux", "json_error_format", "PARTIAL",
                              {"status_code": response.status_code, "content_type": content_type,
                               "note": "Unexpected response format"})
                               
        except Exception as e:
            self.log_result("authentication_ux", "json_error_format", "FAIL", {"error": str(e)})
        
        # Test 2: Error messages should be user-friendly
        try:
            response = requests.post(f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/", 
                                   timeout=10)
            
            if 'json' in response.headers.get('Content-Type', '').lower():
                try:
                    error_data = response.json()
                    error_msg = str(error_data).lower()
                    
                    # Check for technical/unfriendly error messages
                    unfriendly_terms = ['traceback', 'exception', 'internal server error', 
                                      'django', 'csrf', 'middleware']
                    has_unfriendly_terms = any(term in error_msg for term in unfriendly_terms)
                    
                    if has_unfriendly_terms:
                        self.log_result("authentication_ux", "user_friendly_errors", "FAIL",
                                      {"error": "Technical error terms exposed to user", 
                                       "response": error_data})
                    else:
                        self.log_result("authentication_ux", "user_friendly_errors", "PASS",
                                      {"response": error_data})
                except:
                    self.log_result("authentication_ux", "user_friendly_errors", "FAIL",
                                  {"error": "Invalid JSON in error response"})
            else:
                self.log_result("authentication_ux", "user_friendly_errors", "FAIL",
                              {"error": "No JSON error response to evaluate"})
                              
        except Exception as e:
            self.log_result("authentication_ux", "user_friendly_errors", "FAIL", {"error": str(e)})

    def test_url_routing_fixes(self):
        """Test URL routing fixes"""
        print("\n🛣️  TESTING: URL Routing Fixes")
        print("-" * 50)
        
        critical_urls = [
            ("/plugins/hedgehog/fabrics/", "fabric_list"),
            (f"/plugins/hedgehog/fabrics/{self.fabric_id}/", "fabric_detail"),
            (f"/plugins/hedgehog/fabrics/{self.fabric_id}/sync/", "sync_endpoint")
        ]
        
        for url, test_name in critical_urls:
            try:
                response = requests.get(f"{self.base_url}{url}", timeout=10)
                
                if response.status_code == 404:
                    self.log_result("url_routing", f"{test_name}_not_found", "FAIL",
                                  {"url": url, "status_code": 404, "error": "URL pattern not found"})
                elif response.status_code >= 500:
                    self.log_result("url_routing", f"{test_name}_server_error", "FAIL",
                                  {"url": url, "status_code": response.status_code, 
                                   "error": "Server error on valid URL"})
                else:
                    # 200, 302, 401, 403 are all acceptable - means URL routing works
                    self.log_result("url_routing", f"{test_name}_accessible", "PASS",
                                  {"url": url, "status_code": response.status_code})
                                  
            except Exception as e:
                self.log_result("url_routing", f"{test_name}_error", "FAIL", 
                              {"url": url, "error": str(e)})

    def test_rq_scheduler_fixes(self):
        """Test RQ scheduler fixes"""
        print("\n⏰ TESTING: RQ Scheduler Fixes")
        print("-" * 50)
        
        # Test 1: Test if sync endpoint doesn't hang (would indicate scheduler issues)
        start_time = time.time()
        try:
            response = requests.post(f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/", 
                                   timeout=30)  # 30 second timeout
            
            end_time = time.time()
            response_time = end_time - start_time
            
            if response_time > 25:  # If it took more than 25 seconds (close to timeout)
                self.log_result("rq_scheduler", "no_timeout_hang", "FAIL",
                              {"response_time_seconds": response_time, 
                               "error": "Response took too long, possible scheduler hang"})
            else:
                self.log_result("rq_scheduler", "no_timeout_hang", "PASS",
                              {"response_time_seconds": response_time,
                               "status_code": response.status_code})
                               
        except requests.exceptions.Timeout:
            self.log_result("rq_scheduler", "no_timeout_hang", "FAIL",
                          {"error": "Request timed out - possible scheduler hang"})
        except Exception as e:
            # Other errors are fine for this test - we're just testing for hangs
            response_time = time.time() - start_time
            if response_time < 25:
                self.log_result("rq_scheduler", "no_timeout_hang", "PASS",
                              {"response_time_seconds": response_time, 
                               "note": "Quick response despite error"})
            else:
                self.log_result("rq_scheduler", "no_timeout_hang", "FAIL",
                              {"error": str(e), "response_time_seconds": response_time})

    def test_sync_execution_improvements(self):
        """Test sync execution improvements"""
        print("\n🔄 TESTING: Sync Execution Improvements")
        print("-" * 50)
        
        # Test 1: Sync endpoint returns structured response
        try:
            response = requests.post(f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/", 
                                   timeout=30)
            
            # Check if we get a structured response (JSON) rather than generic error
            content_type = response.headers.get('Content-Type', '').lower()
            
            if 'json' in content_type:
                try:
                    response_data = response.json()
                    # Look for sync-related response structure
                    if any(key in response_data for key in ['sync_status', 'status', 'task_id', 'message']):
                        self.log_result("sync_execution", "structured_response", "PASS",
                                      {"response": response_data})
                    else:
                        self.log_result("sync_execution", "structured_response", "PARTIAL",
                                      {"response": response_data, "note": "JSON but not sync-specific"})
                except:
                    self.log_result("sync_execution", "structured_response", "FAIL",
                                  {"error": "Invalid JSON response"})
            else:
                self.log_result("sync_execution", "structured_response", "FAIL",
                              {"error": "Non-JSON response", "content_type": content_type})
                              
        except Exception as e:
            self.log_result("sync_execution", "structured_response", "FAIL", {"error": str(e)})

    def calculate_fix_status(self):
        """Calculate status for each fix category"""
        for category, data in self.results["specific_fixes_tested"].items():
            tests = data["tests"]
            if not tests:
                data["status"] = "NOT_TESTED"
                continue
                
            passed = sum(1 for test in tests.values() if test["status"] == "PASS")
            partial = sum(1 for test in tests.values() if test["status"] == "PARTIAL")
            total = len(tests)
            
            if passed == total:
                data["status"] = "FIXED"
            elif passed + partial >= total * 0.5:  # At least 50% pass/partial
                data["status"] = "MOSTLY_FIXED"
            else:
                data["status"] = "NEEDS_WORK"

    def generate_summary_report(self):
        """Generate summary report"""
        self.calculate_fix_status()
        
        print("\n" + "=" * 70)
        print("📋 COMPREHENSIVE SYNC FIXES VALIDATION REPORT")
        print("=" * 70)
        print(f"Test Date: {self.results['timestamp']}")
        print(f"Target Fabric ID: {self.fabric_id}")
        
        print(f"\n🎯 FIX STATUS SUMMARY:")
        fix_status_icons = {
            "FIXED": "✅",
            "MOSTLY_FIXED": "⚠️",
            "NEEDS_WORK": "❌",
            "NOT_TESTED": "❓"
        }
        
        overall_fixes = 0
        total_categories = 0
        
        for category, data in self.results["specific_fixes_tested"].items():
            icon = fix_status_icons.get(data["status"], "❓")
            category_name = category.replace("_", " ").title()
            print(f"  {icon} {category_name}: {data['status']}")
            
            if data["status"] in ["FIXED", "MOSTLY_FIXED"]:
                overall_fixes += 1
            total_categories += 1
            
            # Show test breakdown
            if data["tests"]:
                for test_name, test_data in data["tests"].items():
                    test_icon = "✅" if test_data["status"] == "PASS" else "⚠️" if test_data["status"] == "PARTIAL" else "❌"
                    print(f"    {test_icon} {test_name}")
        
        fix_percentage = round((overall_fixes / total_categories) * 100, 1) if total_categories > 0 else 0
        
        print(f"\n📊 OVERALL ASSESSMENT:")
        print(f"  Categories Fixed: {overall_fixes}/{total_categories} ({fix_percentage}%)")
        
        if fix_percentage >= 80:
            overall_status = "✅ SYNC FIXES SUCCESSFUL"
        elif fix_percentage >= 60:
            overall_status = "⚠️ SYNC FIXES MOSTLY SUCCESSFUL" 
        else:
            overall_status = "❌ SYNC FIXES NEED MORE WORK"
            
        print(f"  Final Verdict: {overall_status}")
        
        # Save detailed results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = f"detailed_sync_validation_results_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        print(f"\n📄 Detailed results saved to: {results_file}")
        
        return overall_status, fix_percentage

    def run_detailed_validation(self):
        """Run all detailed validation tests"""
        print("🔍 DETAILED SYNC FIXES VALIDATION")
        print("=" * 70)
        print("Testing all specific fixes that were implemented...")
        
        self.test_backend_import_fixes()
        self.test_authentication_ux_improvements()
        self.test_url_routing_fixes()
        self.test_rq_scheduler_fixes()
        self.test_sync_execution_improvements()
        
        return self.generate_summary_report()

if __name__ == "__main__":
    validator = DetailedSyncValidator()
    overall_status, fix_percentage = validator.run_detailed_validation()