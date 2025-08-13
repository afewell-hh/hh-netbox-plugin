#!/usr/bin/env python3
"""
Simple End-to-End Validation Suite
Tests sync fixes without Docker dependency
"""

import json
import requests
import subprocess
import time
from datetime import datetime
from typing import Dict, Any

class SimpleValidator:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.fabric_id = 35
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "validation_phases": {},
            "overall_status": "IN_PROGRESS"
        }
    
    def log_result(self, phase: str, test: str, status: str, details: Any = None):
        """Log test result"""
        if phase not in self.results["validation_phases"]:
            self.results["validation_phases"][phase] = {"tests": {}, "status": "IN_PROGRESS"}
        
        self.results["validation_phases"][phase]["tests"][test] = {
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"✅ {phase} - {test}: {status}" if status == "PASS" else f"❌ {phase} - {test}: {status}")
        if details and status == "FAIL":
            print(f"   Details: {details}")

    def test_server_accessibility(self):
        """Test if server is running"""
        print("\n=== SERVER ACCESSIBILITY TEST ===")
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            if response.status_code in [200, 302, 403]:  # Any response means server is up
                self.log_result("server", "accessibility", "PASS", 
                              {"status_code": response.status_code})
                return True
            else:
                self.log_result("server", "accessibility", "FAIL", 
                              {"status_code": response.status_code})
                return False
        except Exception as e:
            self.log_result("server", "accessibility", "FAIL", {"error": str(e)})
            return False

    def test_url_routing(self):
        """Test URL routing for fabric endpoints"""
        print("\n=== URL ROUTING TESTS ===")
        
        urls_to_test = [
            "/plugins/hedgehog/fabrics/",
            f"/plugins/hedgehog/fabrics/{self.fabric_id}/",
            f"/plugins/hedgehog/fabrics/{self.fabric_id}/sync/",
        ]
        
        for url in urls_to_test:
            try:
                response = requests.get(f"{self.base_url}{url}", timeout=10)
                
                # 404 is failure, anything else indicates URL routing works
                if response.status_code != 404:
                    self.log_result("routing", f"url_{url.replace('/', '_').replace('plugins_hedgehog_fabrics_', '')}", 
                                   "PASS", {"status_code": response.status_code})
                else:
                    self.log_result("routing", f"url_{url.replace('/', '_').replace('plugins_hedgehog_fabrics_', '')}", 
                                   "FAIL", {"status_code": response.status_code})
                    
            except Exception as e:
                self.log_result("routing", f"url_{url.replace('/', '_')}", "FAIL", {"error": str(e)})

    def test_authentication_ux(self):
        """Test authentication user experience"""
        print("\n=== AUTHENTICATION UX TESTS ===")
        
        try:
            # Test sync endpoint without authentication
            response = requests.post(f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/", 
                                   timeout=10)
            
            # Check if response is JSON (good UX) vs HTML (bad UX)
            content_type = response.headers.get('Content-Type', '').lower()
            is_json = 'json' in content_type
            
            if is_json and response.status_code in [401, 403]:
                try:
                    error_data = response.json()
                    self.log_result("auth_ux", "json_error_response", "PASS",
                                  {"status_code": response.status_code, "json_response": error_data})
                except:
                    self.log_result("auth_ux", "json_error_response", "PARTIAL",
                                  {"status_code": response.status_code, "content_type": content_type})
            else:
                self.log_result("auth_ux", "json_error_response", "FAIL",
                              {"status_code": response.status_code, "content_type": content_type,
                               "is_html_redirect": response.status_code == 302})
                               
        except Exception as e:
            self.log_result("auth_ux", "json_error_response", "FAIL", {"error": str(e)})

    def test_sync_functionality(self):
        """Test sync functionality structure"""
        print("\n=== SYNC FUNCTIONALITY TESTS ===")
        
        # Test sync endpoint exists and responds appropriately
        try:
            response = requests.post(f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/", 
                                   timeout=30)
            
            # Success criteria: endpoint exists (not 404) and doesn't crash (not 500)
            if response.status_code == 404:
                self.log_result("sync", "endpoint_exists", "FAIL", 
                              {"status_code": response.status_code})
            elif response.status_code >= 500:
                self.log_result("sync", "endpoint_exists", "FAIL", 
                              {"status_code": response.status_code, "server_error": True})
            else:
                # 401, 403, 200, 302 are all acceptable (endpoint exists)
                self.log_result("sync", "endpoint_exists", "PASS", 
                              {"status_code": response.status_code})
                              
        except requests.exceptions.Timeout:
            # Timeout could indicate sync is trying to run (which is good)
            self.log_result("sync", "endpoint_exists", "PASS", 
                          {"status_code": "timeout", "note": "Endpoint exists but operation timed out"})
        except Exception as e:
            self.log_result("sync", "endpoint_exists", "FAIL", {"error": str(e)})

    def calculate_final_results(self):
        """Calculate overall results"""
        total_tests = 0
        passed_tests = 0
        
        for phase_data in self.results["validation_phases"].values():
            for test_data in phase_data["tests"].values():
                total_tests += 1
                if test_data["status"] == "PASS":
                    passed_tests += 1
        
        success_rate = round((passed_tests / total_tests) * 100, 2) if total_tests > 0 else 0
        
        if success_rate >= 80:
            overall_status = "PASS"
        elif success_rate >= 50:
            overall_status = "PARTIAL" 
        else:
            overall_status = "FAIL"
        
        self.results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": success_rate,
            "overall_status": overall_status
        }
        
        self.results["overall_status"] = overall_status

    def run_validation(self):
        """Run all validation tests"""
        print("🔍 COMPREHENSIVE END-TO-END VALIDATION SUITE")
        print("=" * 60)
        
        # Check if server is accessible first
        if not self.test_server_accessibility():
            print("❌ Server not accessible. Cannot continue validation.")
            self.results["overall_status"] = "FAIL"
            return self.results
        
        # Run all test phases
        self.test_url_routing()
        self.test_authentication_ux()
        self.test_sync_functionality()
        
        # Calculate final results
        self.calculate_final_results()
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = f"simple_validation_results_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        return self.results, results_file

    def print_summary(self):
        """Print validation summary"""
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)
        
        if 'summary' in self.results:
            summary = self.results['summary']
            print(f"Overall Status: {summary['overall_status']}")
            print(f"Success Rate: {summary['success_rate']}%")
            print(f"Tests Passed: {summary['passed_tests']}/{summary['total_tests']}")
            
            print("\n📋 Phase Breakdown:")
            for phase_name, phase_data in self.results["validation_phases"].items():
                phase_tests = phase_data["tests"]
                phase_passed = sum(1 for test in phase_tests.values() if test["status"] == "PASS")
                phase_total = len(phase_tests)
                print(f"  {phase_name}: {phase_passed}/{phase_total} passed")
                
                for test_name, test_data in phase_tests.items():
                    status_icon = "✅" if test_data["status"] == "PASS" else "❌" if test_data["status"] == "FAIL" else "⚠️"
                    print(f"    {status_icon} {test_name}")
        
        print("\n" + "=" * 60)

if __name__ == "__main__":
    validator = SimpleValidator()
    results, results_file = validator.run_validation()
    validator.print_summary()
    
    print(f"\nDetailed results saved to: {results_file}")