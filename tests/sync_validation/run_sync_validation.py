#!/usr/bin/env python3
"""
Sync Validation Test Runner
Runs comprehensive sync functionality tests and generates a consolidated report.
"""

import os
import sys
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

class SyncValidationRunner:
    """Orchestrates all sync validation tests"""
    
    def __init__(self, fabric_id=35, base_url="http://localhost:8000"):
        self.fabric_id = fabric_id
        self.base_url = base_url
        self.test_dir = Path(__file__).parent
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'fabric_id': fabric_id,
            'base_url': base_url,
            'test_suites': {},
            'summary': {},
            'diagnosis': []
        }
    
    def run_test_script(self, script_name, description):
        """Run a test script and capture results"""
        print(f"\n{'='*60}")
        print(f"🧪 Running {description}")
        print(f"Script: {script_name}")
        print('='*60)
        
        script_path = self.test_dir / script_name
        
        if not script_path.exists():
            print(f"❌ Script not found: {script_path}")
            return None
        
        try:
            # Run the test script
            cmd = [
                sys.executable, str(script_path),
                '--fabric-id', str(self.fabric_id),
                '--base-url', self.base_url
            ]
            
            start_time = time.time()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            end_time = time.time()
            
            # Capture output
            execution_time = end_time - start_time
            
            print(f"Exit code: {result.returncode}")
            print(f"Execution time: {execution_time:.2f} seconds")
            
            if result.stdout:
                print("STDOUT:")
                print(result.stdout)
            
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
            
            # Try to find and load the results file
            results_data = None
            results_pattern = f"*test_results_*.json"
            
            # Look for the most recent results file
            results_files = list(self.test_dir.glob(results_pattern))
            if results_files:
                latest_file = max(results_files, key=lambda f: f.stat().st_mtime)
                try:
                    with open(latest_file, 'r') as f:
                        results_data = json.load(f)
                    print(f"📄 Results loaded from: {latest_file}")
                except Exception as e:
                    print(f"⚠️  Could not load results file: {e}")
            
            test_result = {
                'script': script_name,
                'description': description,
                'exit_code': result.returncode,
                'execution_time': execution_time,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'results_data': results_data,
                'success': result.returncode == 0
            }
            
            self.results['test_suites'][script_name] = test_result
            return test_result
            
        except subprocess.TimeoutExpired:
            print(f"❌ Test timed out after 5 minutes")
            test_result = {
                'script': script_name,
                'description': description,
                'error': 'Timeout after 5 minutes',
                'success': False
            }
            self.results['test_suites'][script_name] = test_result
            return test_result
            
        except Exception as e:
            print(f"❌ Error running test: {e}")
            test_result = {
                'script': script_name,
                'description': description,
                'error': str(e),
                'success': False
            }
            self.results['test_suites'][script_name] = test_result
            return test_result
    
    def analyze_results(self):
        """Analyze test results and generate diagnosis"""
        print(f"\n{'='*60}")
        print("📊 ANALYSIS AND DIAGNOSIS")
        print('='*60)
        
        # Count test results
        total_suites = len(self.results['test_suites'])
        successful_suites = sum(1 for suite in self.results['test_suites'].values() if suite['success'])
        failed_suites = total_suites - successful_suites
        
        self.results['summary'] = {
            'total_test_suites': total_suites,
            'successful_suites': successful_suites,
            'failed_suites': failed_suites,
            'success_rate': (successful_suites / total_suites * 100) if total_suites > 0 else 0
        }
        
        print(f"Test Suites: {total_suites}")
        print(f"Successful: {successful_suites} ✅")
        print(f"Failed: {failed_suites} ❌")
        print(f"Success Rate: {self.results['summary']['success_rate']:.1f}%")
        
        # Analyze common issues across test suites
        auth_issues = []
        redirect_issues = []
        csrf_issues = []
        ajax_issues = []
        
        for suite_name, suite_result in self.results['test_suites'].items():
            if not suite_result['success']:
                # Check for authentication issues
                if 'login' in suite_result.get('stderr', '').lower() or 'authentication' in suite_result.get('stderr', '').lower():
                    auth_issues.append(suite_name)
                
                # Check for redirect issues
                if 'redirect' in suite_result.get('stdout', '').lower():
                    redirect_issues.append(suite_name)
                
                # Check for CSRF issues
                if 'csrf' in suite_result.get('stderr', '').lower():
                    csrf_issues.append(suite_name)
                
                # Check for AJAX issues
                if 'ajax' in suite_result.get('stderr', '').lower() or 'xmlhttprequest' in suite_result.get('stderr', '').lower():
                    ajax_issues.append(suite_name)
        
        # Generate diagnosis
        diagnosis = []
        
        if len(auth_issues) >= 2:
            diagnosis.append({
                'issue': 'Authentication Failure',
                'severity': 'HIGH',
                'description': 'Multiple test suites are failing due to authentication issues',
                'affected_suites': auth_issues,
                'recommendation': 'Check user permissions and login credentials'
            })
        
        if len(redirect_issues) >= 2:
            diagnosis.append({
                'issue': 'Redirect Loop',
                'severity': 'HIGH',
                'description': 'AJAX requests are being redirected to login page',
                'affected_suites': redirect_issues,
                'recommendation': 'Check session middleware and AJAX authentication handling'
            })
        
        if len(csrf_issues) >= 1:
            diagnosis.append({
                'issue': 'CSRF Token Issues',
                'severity': 'MEDIUM',
                'description': 'CSRF token validation may be failing',
                'affected_suites': csrf_issues,
                'recommendation': 'Verify CSRF token extraction and submission'
            })
        
        if len(ajax_issues) >= 1:
            diagnosis.append({
                'issue': 'AJAX Request Issues',
                'severity': 'MEDIUM',
                'description': 'AJAX requests are not being handled properly',
                'affected_suites': ajax_issues,
                'recommendation': 'Check AJAX headers and content-type handling'
            })
        
        self.results['diagnosis'] = diagnosis
        
        # Print diagnosis
        if diagnosis:
            print(f"\n🔍 IDENTIFIED ISSUES:")
            for issue in diagnosis:
                severity_icon = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(issue['severity'], '⚪')
                print(f"\n{severity_icon} {issue['issue']} ({issue['severity']})")
                print(f"   Description: {issue['description']}")
                print(f"   Affected: {', '.join(issue['affected_suites'])}")
                print(f"   Recommendation: {issue['recommendation']}")
        else:
            print("\n✅ No common issues identified")
        
        return diagnosis
    
    def run_all_tests(self):
        """Run all sync validation tests"""
        print("🚀 Starting Comprehensive Sync Validation")
        print(f"Target Fabric ID: {self.fabric_id}")
        print(f"Base URL: {self.base_url}")
        print(f"Test Directory: {self.test_dir}")
        
        # Define test suites to run
        test_suites = [
            ('comprehensive_sync_test.py', 'Comprehensive Django-based Testing'),
            ('curl_sync_test.py', 'Raw HTTP/curl-based Testing'),
            ('browser_sync_test.py', 'Browser Automation Testing')
        ]
        
        # Run each test suite
        for script, description in test_suites:
            self.run_test_script(script, description)
        
        # Analyze results
        self.analyze_results()
        
        return self.results
    
    def save_consolidated_report(self, filename=None):
        """Save consolidated test report"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.test_dir / f"sync_validation_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\n💾 Consolidated report saved to: {filename}")
        
        # Also create a human-readable summary
        summary_file = filename.with_suffix('.txt')
        with open(summary_file, 'w') as f:
            f.write("SYNC VALIDATION REPORT\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Timestamp: {self.results['timestamp']}\n")
            f.write(f"Fabric ID: {self.fabric_id}\n")
            f.write(f"Base URL: {self.base_url}\n\n")
            
            f.write("SUMMARY\n")
            f.write("-" * 30 + "\n")
            summary = self.results['summary']
            f.write(f"Total Test Suites: {summary['total_test_suites']}\n")
            f.write(f"Successful: {summary['successful_suites']}\n")
            f.write(f"Failed: {summary['failed_suites']}\n")
            f.write(f"Success Rate: {summary['success_rate']:.1f}%\n\n")
            
            if self.results['diagnosis']:
                f.write("IDENTIFIED ISSUES\n")
                f.write("-" * 30 + "\n")
                for issue in self.results['diagnosis']:
                    f.write(f"\n{issue['issue']} ({issue['severity']})\n")
                    f.write(f"Description: {issue['description']}\n")
                    f.write(f"Affected: {', '.join(issue['affected_suites'])}\n")
                    f.write(f"Recommendation: {issue['recommendation']}\n")
            else:
                f.write("No common issues identified.\n")
        
        print(f"📝 Human-readable summary saved to: {summary_file}")
        
        return filename

def main():
    """Main test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Comprehensive Sync Validation Test Runner')
    parser.add_argument('--fabric-id', type=int, default=35, help='Fabric ID to test')
    parser.add_argument('--base-url', default='http://localhost:8000', help='Base URL')
    parser.add_argument('--output', help='Output file for consolidated report')
    
    args = parser.parse_args()
    
    # Check if we're in the right environment
    try:
        import django
        print(f"✅ Django available: {django.get_version()}")
    except ImportError:
        print("❌ Django not available - some tests may fail")
    
    # Run validation
    runner = SyncValidationRunner(fabric_id=args.fabric_id, base_url=args.base_url)
    results = runner.run_all_tests()
    
    # Save consolidated report
    report_file = runner.save_consolidated_report(args.output)
    
    # Final status
    failed_suites = results['summary']['failed_suites']
    
    print(f"\n{'='*60}")
    print("🏁 SYNC VALIDATION COMPLETE")
    print(f"Report: {report_file}")
    print(f"Status: {'✅ PASS' if failed_suites == 0 else f'❌ FAIL ({failed_suites} suites failed)'}")
    print('='*60)
    
    return failed_suites

if __name__ == '__main__':
    import sys
    sys.exit(main())