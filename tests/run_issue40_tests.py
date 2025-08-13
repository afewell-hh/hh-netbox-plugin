#!/usr/bin/env python3
"""
Test Runner for Issue #40 - Comprehensive TDD Test Suite

This script runs all Issue #40 tests to verify the sync status display problems
and guide implementation fixes.

EXPECTED RESULT: Many tests WILL FAIL with current implementation
This is intentional - TDD approach where tests drive development.

Test Categories:
1. Unit Tests - Status calculation logic
2. Template Tests - Status indicator rendering  
3. Integration Tests - Component interactions
4. Performance Tests - Calculation and rendering speed
5. GUI Tests - User-visible behavior with Playwright
6. Service Mock Tests - Service layer interactions
"""

import os
import sys
import subprocess
import argparse
import time
from pathlib import Path


class Issue40TestRunner:
    """Test runner for Issue #40 comprehensive test suite"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_modules = [
            'tests.test_issue40_status_calculation',
            'tests.test_issue40_template_rendering', 
            'tests.test_issue40_integration',
            'tests.test_issue40_performance',
            'tests.test_issue40_gui_playwright',
            'tests.test_issue40_service_mocks'
        ]
        
        self.results = {}
        
    def run_django_tests(self, module_name, verbose=False):
        """Run Django tests for a specific module"""
        print(f"\n{'='*60}")
        print(f"Running {module_name}")
        print(f"{'='*60}")
        
        cmd = [
            sys.executable, 'manage.py', 'test',
            module_name,
            '--keepdb',  # Keep test database for speed
        ]
        
        if verbose:
            cmd.append('-v')
            cmd.append('2')
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd, 
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per test module
            )
            
            duration = time.time() - start_time
            
            self.results[module_name] = {
                'returncode': result.returncode,
                'duration': duration,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }
            
            # Print results
            if result.returncode == 0:
                print(f"✅ PASSED in {duration:.2f}s")
            else:
                print(f"❌ FAILED in {duration:.2f}s")
                
            if verbose or result.returncode != 0:
                print("\nSTDOUT:")
                print(result.stdout)
                if result.stderr:
                    print("\nSTDERR:")
                    print(result.stderr)
                    
        except subprocess.TimeoutExpired:
            print(f"⏰ TIMEOUT after 5 minutes")
            self.results[module_name] = {
                'returncode': -1,
                'duration': 300,
                'error': 'timeout',
                'success': False
            }
        except Exception as e:
            print(f"💥 ERROR: {e}")
            self.results[module_name] = {
                'returncode': -1,
                'duration': 0,
                'error': str(e),
                'success': False
            }
    
    def run_playwright_tests(self, verbose=False):
        """Run Playwright GUI tests separately"""
        print(f"\n{'='*60}")
        print("Running Playwright GUI Tests")
        print("NOTE: These require a running Django server and Playwright setup")
        print(f"{'='*60}")
        
        # Check if Playwright is available
        try:
            subprocess.run(['playwright', '--version'], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  Playwright not available - skipping GUI tests")
            print("Install with: pip install playwright && playwright install")
            return
        
        # Run Playwright tests
        cmd = [
            sys.executable, '-m', 'pytest',
            'tests/test_issue40_gui_playwright.py',
            '-v' if verbose else '-q',
            '--tb=short'
        ]
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True, 
                text=True,
                timeout=600  # 10 minutes for GUI tests
            )
            
            duration = time.time() - start_time
            
            self.results['playwright_tests'] = {
                'returncode': result.returncode,
                'duration': duration,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }
            
            if result.returncode == 0:
                print(f"✅ PLAYWRIGHT PASSED in {duration:.2f}s")
            else:
                print(f"❌ PLAYWRIGHT FAILED in {duration:.2f}s")
                
            if verbose or result.returncode != 0:
                print(result.stdout)
                if result.stderr:
                    print(result.stderr)
                    
        except Exception as e:
            print(f"💥 PLAYWRIGHT ERROR: {e}")
            self.results['playwright_tests'] = {
                'returncode': -1,
                'duration': 0,
                'error': str(e),
                'success': False
            }
    
    def print_summary(self):
        """Print comprehensive test summary"""
        print(f"\n{'='*80}")
        print("ISSUE #40 TEST SUITE SUMMARY")
        print(f"{'='*80}")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results.values() if r['success'])
        failed_tests = total_tests - passed_tests
        total_duration = sum(r.get('duration', 0) for r in self.results.values())
        
        print(f"Total Test Modules: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Total Duration: {total_duration:.2f}s")
        print()
        
        # Expected failures message
        if failed_tests > 0:
            print("🎯 EXPECTED RESULT: Some tests SHOULD FAIL with current implementation")
            print("   This is TDD - tests drive development by failing first!")
            print()
        
        # Detailed results
        print("DETAILED RESULTS:")
        print("-" * 80)
        
        for module, result in self.results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL" 
            duration = result.get('duration', 0)
            print(f"{status:<8} {module:<45} ({duration:.2f}s)")
            
            if not result['success'] and 'error' in result:
                print(f"         Error: {result['error']}")
        
        print("-" * 80)
        print()
        
        # Analysis and next steps
        self.print_analysis()
    
    def print_analysis(self):
        """Print test failure analysis and next steps"""
        print("FAILURE ANALYSIS:")
        print("-" * 40)
        
        # Expected failure patterns
        expected_failures = {
            'test_issue40_template_rendering': [
                "Template missing 'not_configured' status handling",
                "Template missing 'disabled' status handling", 
                "Status indicator template needs updates"
            ],
            'test_issue40_gui_playwright': [
                "User cannot see 'Not Configured' status",
                "User cannot see 'Sync Disabled' status",
                "GUI lacks proper status indicators"
            ],
            'test_issue40_integration': [
                "Components not integrated for new statuses",
                "Views not displaying calculated statuses",
                "Status changes not reflected in UI"
            ]
        }
        
        for module, failures in expected_failures.items():
            if module in self.results and not self.results[module]['success']:
                print(f"\n{module}:")
                for failure in failures:
                    print(f"  • {failure}")
        
        print("\nNEXT STEPS TO FIX ISSUE #40:")
        print("-" * 40)
        print("1. Update status_indicator.html template:")
        print("   - Add handling for 'not_configured' status")
        print("   - Add handling for 'disabled' status")
        print("   - Ensure proper CSS classes and icons")
        print()
        print("2. Verify template integration:")
        print("   - Check status_bar.html includes calculated_sync_status")
        print("   - Test all status types render correctly")
        print()
        print("3. Update views and templates:")
        print("   - Ensure fabric views use calculated_sync_status")
        print("   - Add proper error handling for status edge cases")
        print()
        print("4. Run tests again after fixes:")
        print("   - python tests/run_issue40_tests.py")
        print("   - All tests should pass after implementation")
        print()
        
        # Files that likely need changes
        print("FILES LIKELY NEEDING CHANGES:")
        print("-" * 40)
        files_to_fix = [
            "netbox_hedgehog/templates/netbox_hedgehog/components/fabric/status_indicator.html",
            "netbox_hedgehog/templates/netbox_hedgehog/components/fabric/status_bar.html",
            "netbox_hedgehog/views/fabric_views.py",
            "netbox_hedgehog/static/netbox_hedgehog/css/fabric-status.css"
        ]
        
        for file_path in files_to_fix:
            print(f"  • {file_path}")
    
    def run_all(self, verbose=False, skip_gui=False):
        """Run all Issue #40 tests"""
        print("🧪 ISSUE #40 - Comprehensive TDD Test Suite")
        print("=" * 60)
        print("Testing sync status display problems")
        print("Expected: Many tests WILL FAIL - this drives development!")
        print("=" * 60)
        
        # Run Django tests
        for module in self.test_modules:
            if module == 'tests.test_issue40_gui_playwright' and skip_gui:
                print(f"\n⏭️  Skipping {module} (--skip-gui)")
                continue
                
            self.run_django_tests(module, verbose)
        
        # Run Playwright tests separately if not skipped
        if not skip_gui:
            self.run_playwright_tests(verbose)
        
        # Print comprehensive summary
        self.print_summary()
        
        # Return overall success status
        return all(result['success'] for result in self.results.values())


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run Issue #40 TDD Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python tests/run_issue40_tests.py                    # Run all tests
  python tests/run_issue40_tests.py --verbose          # Verbose output
  python tests/run_issue40_tests.py --skip-gui         # Skip Playwright tests
  python tests/run_issue40_tests.py -v --skip-gui      # Verbose, no GUI tests
        """
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose test output'
    )
    
    parser.add_argument(
        '--skip-gui',
        action='store_true', 
        help='Skip Playwright GUI tests'
    )
    
    args = parser.parse_args()
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Run tests
    runner = Issue40TestRunner()
    success = runner.run_all(verbose=args.verbose, skip_gui=args.skip_gui)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()