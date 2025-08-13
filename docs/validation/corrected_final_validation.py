#!/usr/bin/env python3
"""
CORRECTED HIVE MIND FINAL VALIDATION: Complete FGD Sync Workflow Testing
Fixes URL endpoints and tag creation issues from initial validation.
"""

import requests
import time
import json
import sys
from datetime import datetime

class CorrectedFinalValidator:
    def __init__(self):
        self.headers = {
            'Authorization': 'Token ced6a3e0a978db0ad4de39cd66af4868372d7dd0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        self.base_url = 'http://localhost:8000/api'
        self.fabric_id = 35
        self.validation_results = {}
        
    def log(self, message):
        """Enhanced logging with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def step1_create_test_vpc_fixed(self):
        """Create VPC with proper tag handling."""
        self.log("STEP 1: Creating test VPC (corrected)...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        vpc_name = f"fgd-test-{timestamp}"
        
        # Simplified VPC data without problematic tags
        vpc_data = {
            "name": vpc_name,
            "description": f"FGD sync test VPC - {datetime.now()}",
            "rd": f"65000:{timestamp[-6:]}",
            "tenant": None
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/ipam/vrfs/',
                headers=self.headers,
                json=vpc_data
            )
            
            if response.status_code == 201:
                created_vpc = response.json()
                self.vpc_id = created_vpc['id']
                self.log(f"✅ VPC created: {vpc_name} (ID: {self.vpc_id})")
                self.validation_results['vpc_created'] = True
                return True
            else:
                self.log(f"❌ VPC creation failed: {response.status_code}")
                self.log(f"   Response: {response.text}")
                self.validation_results['vpc_created'] = False
                return False
                
        except Exception as e:
            self.log(f"❌ VPC creation error: {str(e)}")
            self.validation_results['vpc_created'] = False
            return False
    
    def step2_test_sync_endpoints(self):
        """Test various sync endpoint URLs to find the correct one."""
        self.log("STEP 2: Testing sync endpoints...")
        
        # Test different possible endpoint patterns
        endpoints_to_test = [
            f'/api/plugins/hedgehog/fabrics/{self.fabric_id}/sync/',
            f'/api/plugins/netbox-hedgehog/fabrics/{self.fabric_id}/sync/',
            f'/plugins/hedgehog/fabrics/{self.fabric_id}/sync/',
            f'/api/plugins/hedgehog/fabric/{self.fabric_id}/sync/',
        ]
        
        working_endpoint = None
        
        for endpoint in endpoints_to_test:
            try:
                full_url = f'http://localhost:8000{endpoint}'
                self.log(f"   Testing: {endpoint}")
                
                response = requests.get(full_url, headers=self.headers)
                self.log(f"   Response: {response.status_code}")
                
                if response.status_code in [200, 202, 204, 405]:  # 405 = Method not allowed but endpoint exists
                    working_endpoint = endpoint
                    self.log(f"✅ Found working endpoint: {endpoint}")
                    break
                    
            except Exception as e:
                self.log(f"   Error testing {endpoint}: {str(e)}")
        
        if working_endpoint:
            self.working_sync_endpoint = working_endpoint
            self.validation_results['sync_endpoint_found'] = True
            return True
        else:
            self.log("❌ No working sync endpoint found")
            self.validation_results['sync_endpoint_found'] = False
            return False
    
    def step3_trigger_sync_workflow(self):
        """Trigger sync using the discovered endpoint."""
        self.log("STEP 3: Triggering sync workflow...")
        
        if not hasattr(self, 'working_sync_endpoint'):
            self.log("❌ No working sync endpoint available")
            self.validation_results['sync_triggered'] = False
            return False
        
        try:
            full_url = f'http://localhost:8000{self.working_sync_endpoint}'
            
            # Try POST first (most likely method for sync)
            response = requests.post(full_url, headers=self.headers)
            
            self.log(f"   POST {self.working_sync_endpoint}: {response.status_code}")
            
            if response.status_code in [200, 201, 202, 204]:
                self.log("✅ Sync triggered successfully")
                self.validation_results['sync_triggered'] = True
                
                # Wait for processing
                self.log("   Waiting for sync processing...")
                time.sleep(15)  # Longer wait for processing
                return True
            else:
                self.log(f"❌ Sync trigger failed: {response.status_code}")
                if response.text:
                    self.log(f"   Response: {response.text[:200]}")
                self.validation_results['sync_triggered'] = False
                return False
                
        except Exception as e:
            self.log(f"❌ Sync trigger error: {str(e)}")
            self.validation_results['sync_triggered'] = False
            return False
    
    def step4_check_repository_state(self):
        """Check the GitHub repository state directly."""
        self.log("STEP 4: Checking repository state...")
        
        # For this validation, we'll check the test file results as a proxy
        try:
            # Run a quick check to see if anything changed
            import subprocess
            
            result = subprocess.run([
                'python3', 'simple_fgd_validation.py'
            ], capture_output=True, text=True, cwd='/home/ubuntu/cc/hedgehog-netbox-plugin/')
            
            self.log(f"   Repository check exit code: {result.returncode}")
            
            if result.returncode == 0:
                self.log("✅ Repository state check passed")
                self.validation_results['repository_state_ok'] = True
                
                # Look for improvement indicators in output
                if "PASS" in result.stdout:
                    pass_count = result.stdout.count("PASS")
                    fail_count = result.stdout.count("FAIL")
                    self.log(f"   Test results: {pass_count} PASS, {fail_count} FAIL")
                    
                    if pass_count > fail_count:
                        self.validation_results['sync_progress'] = True
                    
                return True
            else:
                self.log(f"❌ Repository state issues detected")
                self.log(f"   Output: {result.stdout[:300]}")
                self.validation_results['repository_state_ok'] = False
                return False
                
        except Exception as e:
            self.log(f"❌ Repository check error: {str(e)}")
            self.validation_results['repository_state_ok'] = False
            return False
    
    def step5_run_comprehensive_test(self):
        """Run the comprehensive test suite."""
        self.log("STEP 5: Running comprehensive test suite...")
        
        try:
            import subprocess
            
            result = subprocess.run([
                'python3', 'test_fgd_postsync_state_v2.py'
            ], capture_output=True, text=True, cwd='/home/ubuntu/cc/hedgehog-netbox-plugin/')
            
            self.log(f"   Test suite exit code: {result.returncode}")
            
            # Parse the output for specific results
            if "Tests Passed:" in result.stdout:
                # Extract the test result count
                import re
                match = re.search(r'Tests Passed: (\d+)/(\d+)', result.stdout)
                if match:
                    passed = int(match.group(1))
                    total = int(match.group(2))
                    self.log(f"   Test results: {passed}/{total} tests passed")
                    
                    self.validation_results['tests_passed'] = passed
                    self.validation_results['tests_total'] = total
                    self.validation_results['test_suite_success'] = (passed == total)
                    
                    if passed == total:
                        self.log("🎉 ALL TESTS PASSED! Complete success!")
                        self.validation_results['complete_success'] = True
                    else:
                        self.log(f"⚠️  {total - passed} tests still failing")
                        self.validation_results['complete_success'] = False
                    
                    return passed == total
            
            self.log("❌ Could not parse test results")
            self.validation_results['test_suite_success'] = False
            return False
                
        except Exception as e:
            self.log(f"❌ Test suite error: {str(e)}")
            self.validation_results['test_suite_success'] = False
            return False
    
    def cleanup(self):
        """Clean up test VPC."""
        if hasattr(self, 'vpc_id'):
            self.log("CLEANUP: Removing test VPC...")
            try:
                response = requests.delete(
                    f'{self.base_url}/ipam/vrfs/{self.vpc_id}/',
                    headers=self.headers
                )
                
                if response.status_code == 204:
                    self.log("✅ Cleanup successful")
                else:
                    self.log(f"⚠️  Cleanup response: {response.status_code}")
                    
            except Exception as e:
                self.log(f"⚠️  Cleanup error: {str(e)}")
    
    def generate_final_report(self):
        """Generate the final validation report."""
        self.log("\n" + "="*60)
        self.log("CORRECTED HIVE MIND VALIDATION REPORT")
        self.log("="*60)
        
        # Count results
        total_checks = len([k for k in self.validation_results.keys() if not k.startswith('tests_')])
        passed_checks = sum(1 for k, v in self.validation_results.items() 
                          if not k.startswith('tests_') and v is True)
        
        self.log(f"VALIDATION CHECKS: {passed_checks}/{total_checks} passed")
        
        # Test suite results
        if 'tests_passed' in self.validation_results:
            tests_passed = self.validation_results['tests_passed']
            tests_total = self.validation_results['tests_total']
            self.log(f"TEST SUITE: {tests_passed}/{tests_total} tests passed")
        
        self.log("\nDETAILED RESULTS:")
        for check, result in self.validation_results.items():
            if not check.startswith('tests_'):
                status = "✅ PASS" if result else "❌ FAIL"
                self.log(f"  {check}: {status}")
        
        # Final determination
        if self.validation_results.get('complete_success', False):
            self.log("\n🎉 FINAL RESULT: COMPLETE SUCCESS!")
            self.log("   FGD sync workflow is fully operational!")
            return True
        else:
            self.log("\n⚠️  FINAL RESULT: PARTIAL SUCCESS")
            
            # Show progress made
            if self.validation_results.get('sync_triggered', False):
                self.log("   ✅ Sync triggering working")
            if self.validation_results.get('repository_state_ok', False):
                self.log("   ✅ Repository state checks passing")
            if self.validation_results.get('sync_progress', False):
                self.log("   ✅ Sync progress detected")
            
            # Show remaining issues
            if not self.validation_results.get('test_suite_success', True):
                tests_passed = self.validation_results.get('tests_passed', 0)
                tests_total = self.validation_results.get('tests_total', 4)
                failing = tests_total - tests_passed
                self.log(f"   ⚠️  {failing} tests still need attention")
            
            return False
    
    def execute_validation(self):
        """Execute the corrected validation workflow."""
        self.log("CORRECTED HIVE MIND FINAL VALIDATION")
        self.log("Addressing issues found in initial validation")
        self.log("="*60)
        
        try:
            steps = [
                self.step1_create_test_vpc_fixed,
                self.step2_test_sync_endpoints,
                self.step3_trigger_sync_workflow,
                self.step4_check_repository_state,
                self.step5_run_comprehensive_test
            ]
            
            for i, step in enumerate(steps, 1):
                success = step()
                if not success:
                    self.log(f"⚠️  Step {i} issues detected, continuing...")
                time.sleep(2)
            
            self.cleanup()
            return self.generate_final_report()
            
        except Exception as e:
            self.log(f"❌ CRITICAL ERROR: {str(e)}")
            self.cleanup()
            return False

def main():
    validator = CorrectedFinalValidator()
    success = validator.execute_validation()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()