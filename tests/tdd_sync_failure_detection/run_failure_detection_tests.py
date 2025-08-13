#!/usr/bin/env python3
"""
TDD Test Runner: Sync Failure Detection Suite

This script runs all the TDD tests designed to detect sync system failures.
These tests are EXPECTED to fail when the sync system is broken.

Usage:
    python run_failure_detection_tests.py
    
The script will:
1. Run all TDD tests
2. Report which tests fail (expected)
3. Analyze failures to identify specific problems
4. Generate a report of detected issues

CRITICAL: If ALL tests pass, either:
- The sync system is actually working, or
- The tests are wrong and need to be rewritten
"""

import os
import sys
import django
import subprocess
import json
from datetime import datetime
import logging

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')

try:
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SyncFailureDetector:
    """
    Runs TDD tests to detect sync system failures
    """
    
    def __init__(self):
        self.test_directory = '/home/ubuntu/cc/hedgehog-netbox-plugin/tests/tdd_sync_failure_detection'
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'test_files': [],
            'summary': {
                'total_tests': 0,
                'failed_tests': 0,
                'passed_tests': 0,
                'skipped_tests': 0
            },
            'detected_issues': [],
            'recommendations': []
        }
    
    def run_all_tests(self):
        """Run all TDD failure detection tests"""
        logger.info("🔍 Starting Sync Failure Detection Test Suite")
        logger.info("=" * 80)
        
        # Find all test files
        test_files = [
            'test_user_sync_workflow.py',
            'test_sync_api_integration.py', 
            'test_javascript_sync_buttons.py',
            'test_sync_status_display.py'
        ]
        
        all_passed = True
        total_failures = 0
        
        for test_file in test_files:
            test_path = os.path.join(self.test_directory, test_file)
            
            if os.path.exists(test_path):
                logger.info(f"\n🧪 Running {test_file}")
                logger.info("-" * 60)
                
                result = self.run_single_test_file(test_path)
                self.results['test_files'].append(result)
                
                if result['failed'] > 0:
                    all_passed = False
                    total_failures += result['failed']
                
                # Update summary
                self.results['summary']['total_tests'] += result['total']
                self.results['summary']['failed_tests'] += result['failed'] 
                self.results['summary']['passed_tests'] += result['passed']
                self.results['summary']['skipped_tests'] += result['skipped']
                
            else:
                logger.warning(f"⚠️ Test file not found: {test_path}")
        
        # Analyze results
        self.analyze_test_results()
        
        # Print summary
        self.print_summary(all_passed, total_failures)
        
        # Save detailed results
        self.save_results()
        
        return self.results
    
    def run_single_test_file(self, test_path):
        """Run a single test file and parse results"""
        result = {
            'file': os.path.basename(test_path),
            'total': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'failures': [],
            'errors': []
        }
        
        try:
            # Run pytest on the specific file
            cmd = [
                sys.executable, '-m', 'pytest',
                test_path,
                '-v',
                '--tb=short',
                '--json-report',
                '--json-report-file=/tmp/test_report.json',
                '--disable-warnings'
            ]
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.test_directory
            )
            
            # Parse pytest JSON output if available
            try:
                with open('/tmp/test_report.json', 'r') as f:
                    pytest_data = json.load(f)
                    
                result['total'] = pytest_data['summary']['total']
                result['passed'] = pytest_data['summary'].get('passed', 0)
                result['failed'] = pytest_data['summary'].get('failed', 0)  
                result['skipped'] = pytest_data['summary'].get('skipped', 0)
                
                # Extract failure details
                for test in pytest_data.get('tests', []):
                    if test['outcome'] == 'failed':
                        result['failures'].append({
                            'name': test['nodeid'],
                            'message': test.get('call', {}).get('longrepr', 'No error message')
                        })
                        
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                # Fallback to parsing stdout
                self.parse_pytest_output(process.stdout, process.stderr, result)
            
            logger.info(f"✅ Completed: {result['passed']} passed, {result['failed']} failed, {result['skipped']} skipped")
            
            # Show some failure details
            if result['failures']:
                logger.info(f"📋 Sample failures from {result['file']}:")
                for failure in result['failures'][:3]:  # Show first 3 failures
                    logger.info(f"   - {failure['name']}")
                    if len(failure['message']) > 100:
                        logger.info(f"     {failure['message'][:100]}...")
                    else:
                        logger.info(f"     {failure['message']}")
            
        except Exception as e:
            logger.error(f"❌ Error running {test_path}: {e}")
            result['errors'].append(str(e))
        
        return result
    
    def parse_pytest_output(self, stdout, stderr, result):
        """Parse pytest output when JSON report isn't available"""
        output = stdout + stderr
        
        # Look for test result summary
        import re
        
        # Pattern for pytest summary line like "3 failed, 2 passed, 1 skipped in 5.43s"
        summary_pattern = r'(\d+)\s+failed.*?(\d+)\s+passed.*?(\d+)\s+skipped'
        match = re.search(summary_pattern, output)
        
        if match:
            result['failed'] = int(match.group(1))
            result['passed'] = int(match.group(2)) 
            result['skipped'] = int(match.group(3))
            result['total'] = result['failed'] + result['passed'] + result['skipped']
        
        # Extract failure messages
        failure_pattern = r'FAILED.*?::(.*?)\s*-\s*(.*?)(?=\n\n|\n[A-Z]|$)'
        failures = re.findall(failure_pattern, output, re.DOTALL)
        
        for test_name, error_msg in failures:
            result['failures'].append({
                'name': test_name.strip(),
                'message': error_msg.strip()[:200]  # Limit message length
            })
    
    def analyze_test_results(self):
        """Analyze test results to identify specific sync system issues"""
        logger.info("\n🔬 Analyzing Test Results for Sync System Issues")
        logger.info("-" * 60)
        
        issues = []
        recommendations = []
        
        for test_file_result in self.results['test_files']:
            file_name = test_file_result['file']
            failures = test_file_result['failures']
            
            # Analyze failures by test file type
            if 'user_sync_workflow' in file_name:
                issues.extend(self.analyze_workflow_failures(failures))
                
            elif 'sync_api_integration' in file_name:
                issues.extend(self.analyze_api_failures(failures))
                
            elif 'javascript_sync_buttons' in file_name:
                issues.extend(self.analyze_javascript_failures(failures))
                
            elif 'sync_status_display' in file_name:
                issues.extend(self.analyze_status_display_failures(failures))
        
        # Generate recommendations based on detected issues
        recommendations = self.generate_recommendations(issues)
        
        self.results['detected_issues'] = issues
        self.results['recommendations'] = recommendations
        
        # Print analysis
        if issues:
            logger.info(f"🚨 Detected {len(issues)} sync system issues:")
            for i, issue in enumerate(issues, 1):
                logger.info(f"   {i}. {issue['category']}: {issue['description']}")
        else:
            logger.info("✅ No specific sync issues detected in test failures")
        
        if recommendations:
            logger.info(f"\n💡 Recommendations ({len(recommendations)}):")
            for i, rec in enumerate(recommendations, 1):
                logger.info(f"   {i}. {rec}")
    
    def analyze_workflow_failures(self, failures):
        """Analyze user workflow test failures"""
        issues = []
        
        for failure in failures:
            name = failure['name'].lower()
            message = failure['message'].lower()
            
            if 'login' in name and 'access' in name:
                issues.append({
                    'category': 'Authentication',
                    'description': 'User login or page access failing',
                    'severity': 'high',
                    'test': failure['name']
                })
            
            elif 'sync_button' in name or 'click' in name:
                issues.append({
                    'category': 'UI Functionality', 
                    'description': 'Sync buttons not working or missing',
                    'severity': 'critical',
                    'test': failure['name']
                })
            
            elif 'status' in name:
                issues.append({
                    'category': 'Status Display',
                    'description': 'Sync status not updating or displaying correctly', 
                    'severity': 'high',
                    'test': failure['name']
                })
        
        return issues
    
    def analyze_api_failures(self, failures):
        """Analyze API integration test failures"""
        issues = []
        
        for failure in failures:
            name = failure['name'].lower()
            message = failure['message'].lower()
            
            if 'authentication' in name:
                issues.append({
                    'category': 'API Security',
                    'description': 'API authentication or authorization failing',
                    'severity': 'high', 
                    'test': failure['name']
                })
            
            elif 'broken_connection' in name or 'connection' in message:
                issues.append({
                    'category': 'Connectivity',
                    'description': 'API not handling connection failures properly',
                    'severity': 'critical',
                    'test': failure['name']
                })
            
            elif 'json' in message or 'response' in message:
                issues.append({
                    'category': 'API Response',
                    'description': 'API returning invalid or malformed responses',
                    'severity': 'high',
                    'test': failure['name']
                })
        
        return issues
    
    def analyze_javascript_failures(self, failures):
        """Analyze JavaScript/browser test failures"""
        issues = []
        
        for failure in failures:
            name = failure['name'].lower()
            message = failure['message'].lower()
            
            if 'javascript' in message or 'js' in message:
                issues.append({
                    'category': 'JavaScript Errors',
                    'description': 'JavaScript console errors during sync operations',
                    'severity': 'critical',
                    'test': failure['name']
                })
            
            elif 'button' in name and 'click' in name:
                issues.append({
                    'category': 'Button Functionality',
                    'description': 'Sync buttons not responding to clicks',
                    'severity': 'critical',
                    'test': failure['name']
                })
            
            elif 'csrf' in name:
                issues.append({
                    'category': 'CSRF Protection',
                    'description': 'CSRF token handling broken in JavaScript',
                    'severity': 'high',
                    'test': failure['name']
                })
        
        return issues
    
    def analyze_status_display_failures(self, failures):
        """Analyze status display test failures"""
        issues = []
        
        for failure in failures:
            name = failure['name'].lower()
            message = failure['message'].lower()
            
            if 'out_of_sync' in name or 'in_sync' in name:
                issues.append({
                    'category': 'Status Accuracy',
                    'description': 'Sync status display not matching actual system state',
                    'severity': 'critical',
                    'test': failure['name']
                })
            
            elif 'error' in name and 'visible' in name:
                issues.append({
                    'category': 'Error Visibility',
                    'description': 'Error messages not visible to users',
                    'severity': 'high', 
                    'test': failure['name']
                })
            
            elif 'consistency' in name:
                issues.append({
                    'category': 'Status Consistency',
                    'description': 'Status inconsistent between different pages/APIs',
                    'severity': 'high',
                    'test': failure['name']
                })
        
        return issues
    
    def generate_recommendations(self, issues):
        """Generate actionable recommendations based on detected issues"""
        recommendations = []
        
        categories = set(issue['category'] for issue in issues)
        
        if 'JavaScript Errors' in categories:
            recommendations.append(
                "Fix JavaScript console errors - check browser dev tools for specific errors"
            )
        
        if 'Button Functionality' in categories:
            recommendations.append(
                "Verify sync button click handlers are properly attached and working"
            )
        
        if 'API Response' in categories:
            recommendations.append(
                "Fix API endpoints to return proper JSON responses with correct error handling"
            )
        
        if 'Connectivity' in categories:
            recommendations.append(
                "Implement proper connection testing and error handling for Kubernetes/Git connections"
            )
        
        if 'Status Accuracy' in categories:
            recommendations.append(
                "Ensure sync status in database matches actual system state and UI display"
            )
        
        if 'Authentication' in categories:
            recommendations.append(
                "Fix authentication flows for sync operations and proper permission checks"
            )
        
        # General recommendations
        critical_issues = [issue for issue in issues if issue['severity'] == 'critical']
        if critical_issues:
            recommendations.append(
                f"CRITICAL: Address {len(critical_issues)} critical sync failures immediately"
            )
        
        return recommendations
    
    def print_summary(self, all_passed, total_failures):
        """Print test execution summary"""
        logger.info("\n" + "=" * 80)
        logger.info("🎯 TDD SYNC FAILURE DETECTION SUMMARY")
        logger.info("=" * 80)
        
        summary = self.results['summary']
        logger.info(f"📊 Test Results:")
        logger.info(f"   Total Tests: {summary['total_tests']}")
        logger.info(f"   ✅ Passed: {summary['passed_tests']}")
        logger.info(f"   ❌ Failed: {summary['failed_tests']}")
        logger.info(f"   ⏭️  Skipped: {summary['skipped_tests']}")
        
        if all_passed:
            logger.warning("\n🚨 WARNING: ALL TESTS PASSED!")
            logger.warning("This means either:")
            logger.warning("  1. The sync system is actually working correctly, OR")
            logger.warning("  2. The TDD tests are not properly detecting failures")
            logger.warning("  3. Please verify the sync system manually")
        else:
            logger.info(f"\n✅ SUCCESS: Detected {total_failures} test failures as expected")
            logger.info("This confirms the TDD tests are properly detecting sync system issues")
        
        issues = self.results['detected_issues']
        if issues:
            critical_count = len([i for i in issues if i['severity'] == 'critical'])
            high_count = len([i for i in issues if i['severity'] == 'high'])
            
            logger.info(f"\n🔍 Issue Analysis:")
            logger.info(f"   🚨 Critical Issues: {critical_count}")
            logger.info(f"   ⚠️  High Priority: {high_count}")
            logger.info(f"   📋 Total Issues: {len(issues)}")
    
    def save_results(self):
        """Save detailed results to file"""
        results_file = os.path.join(self.test_directory, 'failure_detection_results.json')
        
        try:
            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            
            logger.info(f"\n💾 Detailed results saved to: {results_file}")
            
        except Exception as e:
            logger.error(f"❌ Could not save results: {e}")


def main():
    """Main execution function"""
    print("🚀 Starting TDD Sync Failure Detection Test Suite")
    print("=" * 80)
    
    detector = SyncFailureDetector()
    results = detector.run_all_tests()
    
    # Exit code based on results
    if results['summary']['failed_tests'] > 0:
        print(f"\n✅ SUCCESS: TDD tests detected {results['summary']['failed_tests']} failures in the sync system")
        sys.exit(0)  # Success - failures were detected as expected
    else:
        print("\n⚠️ WARNING: No test failures detected - sync system may actually be working")
        sys.exit(1)  # Warning - need to verify if system is actually working


if __name__ == '__main__':
    main()