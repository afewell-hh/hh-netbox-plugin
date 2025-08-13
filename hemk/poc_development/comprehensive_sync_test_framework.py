#!/usr/bin/env python3
"""
Comprehensive Sync Testing Framework
Automated testing of all sync functionality components
"""

import asyncio
import json
import time
import requests
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync_test_framework.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Test result data structure"""
    test_name: str
    status: str
    duration: float
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

class ComprehensiveSyncTester:
    """Main testing orchestrator class"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.k8s_url = "https://vlab-art.l.hhdev.io:6443"
        self.results: List[TestResult] = []
        self.test_session_id = f"sync_test_{int(time.time())}"
        
    def log_result(self, result: TestResult):
        """Log and store test result"""
        self.results.append(result)
        status_icon = "✅" if result.status == "PASS" else "❌"
        logger.info(f"{status_icon} {result.test_name}: {result.status} ({result.duration:.2f}s)")
        if result.error_message:
            logger.error(f"   Error: {result.error_message}")
    
    async def test_manual_sync_gui(self) -> TestResult:
        """Test manual sync through web interface"""
        start_time = time.time()
        test_name = "Manual Sync GUI Test"
        
        try:
            # First check if sync button exists and is accessible
            response = requests.get(f"{self.base_url}/plugins/netbox-hedgehog/fabric/35/", timeout=10)
            
            if response.status_code != 200:
                raise Exception(f"Fabric page not accessible: {response.status_code}")
            
            # Check for sync button in HTML
            if 'sync-button' not in response.text and 'Sync with Kubernetes' not in response.text:
                raise Exception("Sync button not found in fabric page")
            
            # Simulate sync button click via API endpoint
            sync_response = requests.post(
                f"{self.base_url}/plugins/netbox-hedgehog/fabric/35/sync/",
                headers={'X-Requested-With': 'XMLHttpRequest'},
                timeout=30
            )
            
            details = {
                "page_status": response.status_code,
                "sync_response_status": sync_response.status_code,
                "sync_response_text": sync_response.text[:500]  # First 500 chars
            }
            
            if sync_response.status_code == 200:
                return TestResult(test_name, "PASS", time.time() - start_time, details=details)
            else:
                error_msg = f"Sync request failed: {sync_response.status_code} - {sync_response.text}"
                return TestResult(test_name, "FAIL", time.time() - start_time, error_msg, details)
                
        except Exception as e:
            return TestResult(test_name, "FAIL", time.time() - start_time, str(e))
    
    async def test_periodic_sync_scheduler(self) -> TestResult:
        """Test periodic sync scheduler functionality"""
        start_time = time.time()
        test_name = "Periodic Sync Scheduler Test"
        
        try:
            # Check RQ scheduler status
            rq_status = subprocess.run(
                ['docker', 'exec', 'b05eb5eff181', 'python', 'manage.py', 'rqscheduler', '--dry-run'],
                capture_output=True, text=True, timeout=15
            )
            
            # Check for periodic job in RQ queue
            rq_jobs = subprocess.run(
                ['docker', 'exec', 'b05eb5eff181', 'python', '-c', 
                 'from django_rq import get_scheduler; s = get_scheduler(); jobs = list(s.get_jobs()); print(len(jobs))'],
                capture_output=True, text=True, timeout=10
            )
            
            details = {
                "rq_scheduler_output": rq_status.stdout[:300],
                "rq_scheduler_error": rq_status.stderr[:300],
                "scheduled_jobs_count": rq_jobs.stdout.strip() if rq_jobs.returncode == 0 else "ERROR"
            }
            
            # Check if periodic job is scheduled
            if "hedgehog_periodic_sync" in rq_status.stdout or int(rq_jobs.stdout.strip() or "0") > 0:
                return TestResult(test_name, "PASS", time.time() - start_time, details=details)
            else:
                error_msg = "Periodic sync job not found in RQ scheduler"
                return TestResult(test_name, "FAIL", time.time() - start_time, error_msg, details)
                
        except Exception as e:
            return TestResult(test_name, "FAIL", time.time() - start_time, str(e))
    
    async def test_kubernetes_integration(self) -> TestResult:
        """Test Kubernetes API integration"""
        start_time = time.time()
        test_name = "Kubernetes Integration Test"
        
        try:
            # Test Kubernetes connection using kubectl from container
            k8s_test = subprocess.run([
                'docker', 'exec', 'b05eb5eff181', 'python', '-c',
                '''
import os
from kubernetes import client, config
try:
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    result = v1.list_namespace(limit=1)
    print(f"SUCCESS: Connected to K8s, found {len(result.items)} namespace(s)")
except Exception as e:
    print(f"ERROR: {e}")
                '''
            ], capture_output=True, text=True, timeout=20)
            
            details = {
                "k8s_test_output": k8s_test.stdout.strip(),
                "k8s_test_error": k8s_test.stderr.strip(),
                "return_code": k8s_test.returncode
            }
            
            if k8s_test.returncode == 0 and "SUCCESS" in k8s_test.stdout:
                return TestResult(test_name, "PASS", time.time() - start_time, details=details)
            else:
                error_msg = f"K8s connection failed: {k8s_test.stderr or k8s_test.stdout}"
                return TestResult(test_name, "FAIL", time.time() - start_time, error_msg, details)
                
        except Exception as e:
            return TestResult(test_name, "FAIL", time.time() - start_time, str(e))
    
    async def test_end_to_end_workflow(self) -> TestResult:
        """Test complete end-to-end sync workflow"""
        start_time = time.time()
        test_name = "End-to-End Workflow Test"
        
        try:
            # Capture initial state
            initial_state = requests.get(f"{self.base_url}/plugins/netbox-hedgehog/fabric/35/", timeout=10)
            
            # Execute sync
            sync_response = requests.post(
                f"{self.base_url}/plugins/netbox-hedgehog/fabric/35/sync/",
                headers={'X-Requested-With': 'XMLHttpRequest'},
                timeout=45
            )
            
            # Wait a moment for async processing
            await asyncio.sleep(2)
            
            # Capture final state
            final_state = requests.get(f"{self.base_url}/plugins/netbox-hedgehog/fabric/35/", timeout=10)
            
            details = {
                "initial_status": initial_state.status_code,
                "sync_status": sync_response.status_code,
                "final_status": final_state.status_code,
                "sync_response": sync_response.text[:200],
                "workflow_duration": time.time() - start_time
            }
            
            # Check for successful workflow completion
            success_indicators = [
                sync_response.status_code in [200, 202],
                final_state.status_code == 200,
                "error" not in sync_response.text.lower() or "success" in sync_response.text.lower()
            ]
            
            if all(success_indicators):
                return TestResult(test_name, "PASS", time.time() - start_time, details=details)
            else:
                error_msg = "E2E workflow failed validation checks"
                return TestResult(test_name, "FAIL", time.time() - start_time, error_msg, details)
                
        except Exception as e:
            return TestResult(test_name, "FAIL", time.time() - start_time, str(e))
    
    async def test_error_handling(self) -> TestResult:
        """Test error handling and recovery"""
        start_time = time.time()
        test_name = "Error Handling Test"
        
        try:
            # Test invalid fabric ID
            invalid_response = requests.post(
                f"{self.base_url}/plugins/netbox-hedgehog/fabric/99999/sync/",
                headers={'X-Requested-With': 'XMLHttpRequest'},
                timeout=10
            )
            
            # Test malformed request
            malformed_response = requests.post(
                f"{self.base_url}/plugins/netbox-hedgehog/fabric/35/sync/",
                headers={'Content-Type': 'invalid/type'},
                timeout=10
            )
            
            details = {
                "invalid_fabric_status": invalid_response.status_code,
                "invalid_fabric_response": invalid_response.text[:200],
                "malformed_request_status": malformed_response.status_code,
                "malformed_request_response": malformed_response.text[:200]
            }
            
            # Error handling should return appropriate error codes
            if invalid_response.status_code in [404, 400] and malformed_response.status_code in [400, 415]:
                return TestResult(test_name, "PASS", time.time() - start_time, details=details)
            else:
                error_msg = "Error handling not working as expected"
                return TestResult(test_name, "FAIL", time.time() - start_time, error_msg, details)
                
        except Exception as e:
            return TestResult(test_name, "FAIL", time.time() - start_time, str(e))
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Execute all tests in parallel"""
        logger.info(f"🚀 Starting comprehensive sync test framework - Session: {self.test_session_id}")
        
        # Run tests in parallel
        test_tasks = [
            self.test_manual_sync_gui(),
            self.test_periodic_sync_scheduler(),
            self.test_kubernetes_integration(),
            self.test_end_to_end_workflow(),
            self.test_error_handling()
        ]
        
        # Execute tests concurrently
        results = await asyncio.gather(*test_tasks, return_exceptions=True)
        
        # Log results
        for result in results:
            if isinstance(result, TestResult):
                self.log_result(result)
            else:
                error_result = TestResult("Unknown Test", "ERROR", 0, str(result))
                self.log_result(error_result)
        
        # Generate summary report
        summary = self.generate_summary_report()
        
        # Save detailed results
        self.save_results()
        
        return summary
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate comprehensive test summary"""
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r.status == "PASS"])
        failed_tests = len([r for r in self.results if r.status == "FAIL"])
        error_tests = len([r for r in self.results if r.status == "ERROR"])
        
        summary = {
            "session_id": self.test_session_id,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests,
                "pass_rate": (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            },
            "test_results": [asdict(result) for result in self.results],
            "recommendations": self.generate_recommendations()
        }
        
        return summary
    
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        failed_tests = [r for r in self.results if r.status == "FAIL"]
        
        for test in failed_tests:
            if "Manual Sync" in test.test_name:
                recommendations.append("Check Django URL routing and view configuration for manual sync endpoint")
                recommendations.append("Verify CSRF token handling for AJAX requests")
            
            if "Periodic Sync" in test.test_name:
                recommendations.append("Verify RQ scheduler is running with correct job configuration")
                recommendations.append("Check Django-RQ settings and Redis connection")
            
            if "Kubernetes" in test.test_name:
                recommendations.append("Verify Kubernetes authentication configuration")
                recommendations.append("Check network connectivity to K8s cluster")
            
            if "End-to-End" in test.test_name:
                recommendations.append("Review complete sync workflow for async processing issues")
                recommendations.append("Check for missing error handling in sync operations")
        
        if not recommendations:
            recommendations.append("All tests passed - sync functionality is working correctly")
        
        return list(set(recommendations))  # Remove duplicates
    
    def save_results(self):
        """Save test results to file"""
        results_file = f"sync_test_results_{self.test_session_id}.json"
        summary = self.generate_summary_report()
        
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"📊 Test results saved to: {results_file}")

async def main():
    """Main test execution function"""
    tester = ComprehensiveSyncTester()
    
    try:
        summary = await tester.run_all_tests()
        
        # Display results
        print("\n" + "="*80)
        print("🧪 COMPREHENSIVE SYNC TEST RESULTS")
        print("="*80)
        print(f"📋 Session ID: {summary['session_id']}")
        print(f"📅 Timestamp: {summary['timestamp']}")
        print(f"✅ Passed: {summary['summary']['passed']}")
        print(f"❌ Failed: {summary['summary']['failed']}")
        print(f"⚠️  Errors: {summary['summary']['errors']}")
        print(f"📊 Pass Rate: {summary['summary']['pass_rate']:.1f}%")
        
        if summary['recommendations']:
            print("\n🔧 RECOMMENDATIONS:")
            for i, rec in enumerate(summary['recommendations'], 1):
                print(f"   {i}. {rec}")
        
        print("="*80)
        
        return summary
        
    except Exception as e:
        logger.error(f"Test framework execution failed: {e}")
        return {"error": str(e), "status": "FRAMEWORK_ERROR"}

if __name__ == "__main__":
    asyncio.run(main())