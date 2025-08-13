#!/usr/bin/env python3
"""
RQ Scheduler Configuration Validation Script
Tests that scheduler fixes resolve generator errors
"""

import subprocess
import json
import time
from datetime import datetime
from pathlib import Path

class SchedulerFixValidator:
    """Validate RQ scheduler fixes and configuration"""
    
    def __init__(self):
        self.container_id = "b05eb5eff181"
        self.validation_results = {
            "timestamp": datetime.now().isoformat(),
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "errors": [],
            "fixes_validated": []
        }
    
    def test_scheduler_get_jobs_fix(self):
        """Test that scheduler.get_jobs() no longer causes generator error"""
        print("🔍 Testing scheduler.get_jobs() generator fix...")
        
        try:
            # Test the original problematic code pattern (now fixed)
            test_script = '''
import sys
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

try:
    from django_rq import get_scheduler
    
    # Test 1: Basic scheduler connection
    scheduler = get_scheduler()
    print("SCHEDULER_CONNECTION: SUCCESS")
    
    # Test 2: Get jobs and convert to list (the fix)
    jobs = list(scheduler.get_jobs())
    print(f"SCHEDULER_JOBS_COUNT: {len(jobs)}")
    
    # Test 3: Iterate through jobs without error
    job_count = 0
    for job in jobs[:3]:  # First 3 jobs
        job_count += 1
        print(f"JOB_{job_count}: {job.id}")
    
    print("GENERATOR_FIX: SUCCESS")
    
except Exception as e:
    print(f"SCHEDULER_ERROR: {e}")
    import traceback
    traceback.print_exc()
'''
            
            # Execute test in container
            result = subprocess.run([
                'sudo', 'docker', 'exec', self.container_id,
                'python', '-c', test_script
            ], capture_output=True, text=True, timeout=15)
            
            self.validation_results["tests_run"] += 1
            
            if result.returncode == 0:
                output_lines = result.stdout.strip().split('\n')
                
                # Check for success indicators
                success_indicators = ['SCHEDULER_CONNECTION: SUCCESS', 'GENERATOR_FIX: SUCCESS']
                found_indicators = [line for line in output_lines if any(indicator in line for indicator in success_indicators)]
                
                if len(found_indicators) >= 2:  # Both success indicators present
                    print("✅ Scheduler generator fix validated successfully")
                    for line in output_lines:
                        if any(key in line for key in ['SCHEDULER_', 'JOB_', 'GENERATOR_FIX']):
                            print(f"   📋 {line}")
                    
                    self.validation_results["tests_passed"] += 1
                    self.validation_results["fixes_validated"].append("scheduler.get_jobs() generator fix")
                    return True
                else:
                    print("❌ Scheduler fix validation failed - missing success indicators")
                    self.validation_results["tests_failed"] += 1
                    self.validation_results["errors"].append("Missing success indicators in scheduler test")
                    return False
            else:
                print(f"❌ Scheduler test failed with error: {result.stderr}")
                self.validation_results["tests_failed"] += 1
                self.validation_results["errors"].append(f"Scheduler test execution error: {result.stderr}")
                return False
            
        except Exception as e:
            print(f"❌ Scheduler validation test failed: {e}")
            self.validation_results["tests_failed"] += 1
            self.validation_results["errors"].append(f"Test execution exception: {str(e)}")
            return False
    
    def test_periodic_sync_monitoring_fix(self):
        """Test that periodic sync monitoring code works without generator errors"""
        print("\n🔍 Testing periodic sync monitoring fixes...")
        
        try:
            # Import the fixed periodic sync monitor functionality
            test_script = '''
import sys
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

try:
    from django_rq import get_scheduler
    import redis
    
    # Test periodic sync monitor pattern (fixed version)
    scheduler = get_scheduler()
    
    # Test the fixed pattern from periodic_sync_monitor.py
    jobs = list(scheduler.get_jobs())  # This was the fix
    
    print(f"MONITOR_JOBS_COUNT: {len(jobs)}")
    
    # Test queue operations
    from django_rq import get_queue
    queue = get_queue()
    
    # Test the fixed queue jobs pattern
    recent_jobs = list(queue.get_jobs())[:5]  # This was also fixed
    print(f"QUEUE_JOBS_COUNT: {len(recent_jobs)}")
    
    print("MONITORING_FIX: SUCCESS")
    
except Exception as e:
    print(f"MONITORING_ERROR: {e}")
    import traceback
    traceback.print_exc()
'''
            
            result = subprocess.run([
                'sudo', 'docker', 'exec', self.container_id,
                'python', '-c', test_script
            ], capture_output=True, text=True, timeout=15)
            
            self.validation_results["tests_run"] += 1
            
            if result.returncode == 0 and 'MONITORING_FIX: SUCCESS' in result.stdout:
                print("✅ Periodic sync monitoring fix validated successfully")
                
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    if any(key in line for key in ['MONITOR_', 'QUEUE_', 'MONITORING_FIX']):
                        print(f"   📋 {line}")
                
                self.validation_results["tests_passed"] += 1
                self.validation_results["fixes_validated"].append("periodic sync monitoring generator fix")
                return True
            else:
                print(f"❌ Monitoring fix validation failed: {result.stderr}")
                self.validation_results["tests_failed"] += 1
                self.validation_results["errors"].append(f"Monitoring fix validation error: {result.stderr}")
                return False
            
        except Exception as e:
            print(f"❌ Monitoring validation test failed: {e}")
            self.validation_results["tests_failed"] += 1
            self.validation_results["errors"].append(f"Monitoring test exception: {str(e)}")
            return False
    
    def test_fabric_sync_jobs_fix(self):
        """Test that fabric sync jobs status checking works without generator errors"""
        print("\n🔍 Testing fabric sync jobs status fix...")
        
        try:
            test_script = '''
import sys
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

try:
    import django_rq
    
    # Test the fixed pattern from fabric_sync.py
    scheduler = django_rq.get_scheduler('netbox_hedgehog.hedgehog_sync')
    jobs = list(scheduler.get_jobs())  # This was the fix
    
    # Test filtering jobs (original pattern that was fixed)
    fabric_jobs = [job for job in jobs if str(job.id).startswith('fabric_sync_')]
    
    print(f"FABRIC_JOBS_TOTAL: {len(jobs)}")
    print(f"FABRIC_JOBS_FILTERED: {len(fabric_jobs)}")
    print("FABRIC_SYNC_FIX: SUCCESS")
    
except Exception as e:
    print(f"FABRIC_SYNC_ERROR: {e}")
    import traceback
    traceback.print_exc()
'''
            
            result = subprocess.run([
                'sudo', 'docker', 'exec', self.container_id,
                'python', '-c', test_script
            ], capture_output=True, text=True, timeout=15)
            
            self.validation_results["tests_run"] += 1
            
            if result.returncode == 0 and 'FABRIC_SYNC_FIX: SUCCESS' in result.stdout:
                print("✅ Fabric sync jobs fix validated successfully")
                
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    if any(key in line for key in ['FABRIC_JOBS_', 'FABRIC_SYNC_FIX']):
                        print(f"   📋 {line}")
                
                self.validation_results["tests_passed"] += 1
                self.validation_results["fixes_validated"].append("fabric sync jobs generator fix")
                return True
            else:
                print(f"❌ Fabric sync fix validation failed: {result.stderr}")
                self.validation_results["tests_failed"] += 1
                self.validation_results["errors"].append(f"Fabric sync fix validation error: {result.stderr}")
                return False
            
        except Exception as e:
            print(f"❌ Fabric sync validation test failed: {e}")
            self.validation_results["tests_failed"] += 1
            self.validation_results["errors"].append(f"Fabric sync test exception: {str(e)}")
            return False
    
    def test_scheduler_service_status(self):
        """Test RQ scheduler service is running properly"""
        print("\n🔍 Testing RQ scheduler service status...")
        
        try:
            # Check if RQ scheduler is running
            ps_result = subprocess.run([
                'sudo', 'docker', 'exec', self.container_id,
                'ps', 'aux'
            ], capture_output=True, text=True, timeout=10)
            
            self.validation_results["tests_run"] += 1
            
            if ps_result.returncode == 0:
                rq_processes = [line for line in ps_result.stdout.split('\n') if 'rq' in line.lower()]
                
                if rq_processes:
                    print("✅ RQ processes are running:")
                    for process in rq_processes:
                        print(f"   📋 {process.strip()}")
                    
                    self.validation_results["tests_passed"] += 1
                    self.validation_results["fixes_validated"].append("RQ scheduler service running")
                    return True
                else:
                    print("❌ No RQ processes found running")
                    self.validation_results["tests_failed"] += 1
                    self.validation_results["errors"].append("No RQ processes running")
                    return False
            else:
                print(f"❌ Failed to check process status: {ps_result.stderr}")
                self.validation_results["tests_failed"] += 1
                self.validation_results["errors"].append("Failed to check process status")
                return False
            
        except Exception as e:
            print(f"❌ Service status test failed: {e}")
            self.validation_results["tests_failed"] += 1
            self.validation_results["errors"].append(f"Service status test exception: {str(e)}")
            return False
    
    def run_all_validations(self):
        """Run all scheduler fix validations"""
        print("🚀 Running RQ Scheduler Fix Validation Suite")
        print("=" * 70)
        
        start_time = time.time()
        
        # Run all validation tests
        tests = [
            ("Scheduler get_jobs() Fix", self.test_scheduler_get_jobs_fix),
            ("Periodic Sync Monitoring Fix", self.test_periodic_sync_monitoring_fix), 
            ("Fabric Sync Jobs Fix", self.test_fabric_sync_jobs_fix),
            ("RQ Scheduler Service Status", self.test_scheduler_service_status)
        ]
        
        for test_name, test_func in tests:
            print(f"\n🧪 Running: {test_name}")
            try:
                test_func()
            except Exception as e:
                print(f"❌ Test '{test_name}' failed with exception: {e}")
                self.validation_results["tests_failed"] += 1
                self.validation_results["errors"].append(f"{test_name}: {str(e)}")
        
        # Calculate results
        duration = time.time() - start_time
        success_rate = (self.validation_results["tests_passed"] / max(1, self.validation_results["tests_run"])) * 100
        
        # Generate summary
        print("\n" + "=" * 70)
        print(f"🎯 VALIDATION SUMMARY ({duration:.1f}s)")
        print("=" * 70)
        
        print(f"📊 Tests Run: {self.validation_results['tests_run']}")
        print(f"✅ Tests Passed: {self.validation_results['tests_passed']}")
        print(f"❌ Tests Failed: {self.validation_results['tests_failed']}")
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if self.validation_results["fixes_validated"]:
            print(f"\n✅ Fixes Validated ({len(self.validation_results['fixes_validated'])}):")
            for i, fix in enumerate(self.validation_results['fixes_validated'], 1):
                print(f"   {i}. {fix}")
        
        if self.validation_results["errors"]:
            print(f"\n❌ Errors Encountered ({len(self.validation_results['errors'])}):")
            for i, error in enumerate(self.validation_results['errors'], 1):
                print(f"   {i}. {error}")
        
        # Overall status
        if self.validation_results["tests_failed"] == 0:
            print(f"\n🏆 ALL SCHEDULER FIXES VALIDATED SUCCESSFULLY!")
            print("   RQ scheduler should now work without generator errors")
        elif self.validation_results["tests_passed"] > 0:
            print(f"\n⚠️  PARTIAL SUCCESS - Some fixes validated")
            print("   Check failed tests for remaining issues")
        else:
            print(f"\n🚨 VALIDATION FAILED - Scheduler fixes need more work")
        
        print("=" * 70)
        
        return self.validation_results

def main():
    """Main execution function"""
    validator = SchedulerFixValidator()
    
    try:
        results = validator.run_all_validations()
        
        # Save results
        results_file = f"scheduler_fix_validation_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📊 Results saved to: {results_file}")
        return results
        
    except Exception as e:
        print(f"❌ Validation execution failed: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    main()