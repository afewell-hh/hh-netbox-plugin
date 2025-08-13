#!/usr/bin/env python3
"""
London School TDD: Failing Test Execution Script

This script runs the failing tests that expose current sync issues.
These tests MUST FAIL initially to demonstrate the exact problems.

Run this script to see the current sync failures exposed through TDD.
"""

import os
import sys
import django
import subprocess
import json
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()


def run_test_category(test_file, description, expected_to_fail=True):
    """
    Run a specific test category and capture results.
    
    Args:
        test_file: Name of the test file to run
        description: Human-readable description of what's being tested
        expected_to_fail: Whether these tests are expected to fail initially
    """
    print(f"\n{'=' * 80}")
    print(f"RUNNING: {description}")
    print(f"FILE: {test_file}")
    print(f"EXPECTED TO {'FAIL' if expected_to_fail else 'PASS'}")
    print(f"{'=' * 80}")
    
    # Construct pytest command
    test_path = project_root / "tests" / "tdd_sync_london_school" / test_file
    cmd = [
        sys.executable, "-m", "pytest",
        str(test_path),
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--no-header",  # No pytest header
        "--show-capture=no"  # Don't show captured output
    ]
    
    # Run the test
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=300  # 5 minute timeout
        )
        
        # Parse results
        output = result.stdout + result.stderr
        return_code = result.returncode
        
        # Display results
        print(f"Return Code: {return_code}")
        if expected_to_fail and return_code != 0:
            print("✅ EXPECTED FAILURE - Tests correctly expose current issues")
        elif not expected_to_fail and return_code == 0:
            print("✅ EXPECTED SUCCESS - Tests pass as expected")
        elif expected_to_fail and return_code == 0:
            print("⚠️  UNEXPECTED SUCCESS - Tests should be failing but passed")
        else:
            print("❌ UNEXPECTED FAILURE - Tests should be passing but failed")
        
        print(f"\nOutput:\n{output}")
        
        return {
            'test_file': test_file,
            'description': description,
            'return_code': return_code,
            'output': output,
            'expected_to_fail': expected_to_fail,
            'result_matches_expectation': (expected_to_fail and return_code != 0) or (not expected_to_fail and return_code == 0)
        }
        
    except subprocess.TimeoutExpired:
        print("❌ TEST TIMEOUT - Tests took too long to execute")
        return {
            'test_file': test_file,
            'description': description,
            'return_code': -1,
            'output': 'TIMEOUT',
            'expected_to_fail': expected_to_fail,
            'result_matches_expectation': False
        }
    except Exception as e:
        print(f"❌ EXECUTION ERROR - {str(e)}")
        return {
            'test_file': test_file,
            'description': description,
            'return_code': -2,
            'output': str(e),
            'expected_to_fail': expected_to_fail,
            'result_matches_expectation': False
        }


def analyze_failure_patterns(results):
    """Analyze test results to identify patterns in failures."""
    print(f"\n{'=' * 80}")
    print("FAILURE PATTERN ANALYSIS")
    print(f"{'=' * 80}")
    
    # Count failures by category
    failure_categories = {}
    total_tests = len(results)
    failed_tests = 0
    expected_failures = 0
    unexpected_results = 0
    
    for result in results:
        category = result['description'].split(':')[0] if ':' in result['description'] else 'Other'
        
        if result['return_code'] != 0:
            failed_tests += 1
            if result['expected_to_fail']:
                expected_failures += 1
            else:
                unexpected_results += 1
        else:
            if result['expected_to_fail']:
                unexpected_results += 1
        
        # Categorize failures
        if category not in failure_categories:
            failure_categories[category] = {'failed': 0, 'total': 0}
        
        failure_categories[category]['total'] += 1
        if result['return_code'] != 0:
            failure_categories[category]['failed'] += 1
    
    print(f"Total test categories: {total_tests}")
    print(f"Failed categories: {failed_tests}")
    print(f"Expected failures: {expected_failures}")
    print(f"Unexpected results: {unexpected_results}")
    
    print(f"\nFailure breakdown by category:")
    for category, counts in failure_categories.items():
        failure_rate = (counts['failed'] / counts['total']) * 100 if counts['total'] > 0 else 0
        print(f"  {category}: {counts['failed']}/{counts['total']} ({failure_rate:.1f}%)")
    
    # Identify common failure patterns in output
    print(f"\nCommon failure patterns:")
    error_patterns = {}
    
    for result in results:
        if result['return_code'] != 0:
            output = result['output'].lower()
            
            # Look for common error indicators
            patterns = [
                ('connection', ['connection', 'refused', 'timeout']),
                ('authentication', ['unauthorized', 'permission', 'forbidden']),
                ('api_missing', ['404', 'not found', 'no such endpoint']),
                ('json_parse', ['json', 'parse', 'invalid json']),
                ('sync_disabled', ['sync', 'disabled', 'not enabled']),
                ('missing_config', ['configuration', 'config', 'missing']),
                ('import_error', ['import', 'module', 'cannot import'])
            ]
            
            for pattern_name, keywords in patterns:
                if any(keyword in output for keyword in keywords):
                    if pattern_name not in error_patterns:
                        error_patterns[pattern_name] = 0
                    error_patterns[pattern_name] += 1
    
    for pattern, count in sorted(error_patterns.items(), key=lambda x: x[1], reverse=True):
        print(f"  {pattern}: {count} occurrences")
    
    return {
        'total_tests': total_tests,
        'failed_tests': failed_tests,
        'expected_failures': expected_failures,
        'unexpected_results': unexpected_results,
        'failure_categories': failure_categories,
        'error_patterns': error_patterns
    }


def generate_failure_report(results, analysis):
    """Generate a comprehensive failure report."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_test_categories': analysis['total_tests'],
            'failed_categories': analysis['failed_tests'],
            'expected_failures': analysis['expected_failures'],
            'unexpected_results': analysis['unexpected_results'],
            'success_rate': ((analysis['total_tests'] - analysis['failed_tests']) / analysis['total_tests']) * 100 if analysis['total_tests'] > 0 else 0
        },
        'detailed_results': results,
        'failure_analysis': analysis
    }
    
    # Save report to file
    report_file = project_root / "tests" / "tdd_sync_london_school" / "failure_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed failure report saved to: {report_file}")
    return report


def main():
    """Main execution function."""
    print("🔍 London School TDD: Exposing Sync Failures Through Tests")
    print("=" * 80)
    print("This script runs tests that SHOULD FAIL to expose current sync issues.")
    print("Each failure reveals a specific problem that needs to be fixed.")
    print("Once the sync functionality is properly implemented, these tests should pass.")
    
    # Define test categories to run
    test_categories = [
        {
            'file': 'test_sync_failures_exposed.py',
            'description': 'Sync Failures: Manual sync button, periodic sync, API endpoints',
            'expected_to_fail': True
        },
        {
            'file': 'test_kubernetes_mock_contracts.py', 
            'description': 'Kubernetes Contracts: Client behavior and error handling',
            'expected_to_fail': False  # These should pass as they test mocks
        },
        {
            'file': 'test_sync_orchestration.py',
            'description': 'Sync Orchestration: Component coordination and workflow',
            'expected_to_fail': True
        },
        {
            'file': 'test_ui_integration_mocks.py',
            'description': 'UI Integration: Frontend/backend conversation',
            'expected_to_fail': True
        }
    ]
    
    # Run each test category
    results = []
    for test_config in test_categories:
        result = run_test_category(
            test_config['file'],
            test_config['description'], 
            test_config['expected_to_fail']
        )
        results.append(result)
    
    # Analyze results
    analysis = analyze_failure_patterns(results)
    
    # Generate comprehensive report
    report = generate_failure_report(results, analysis)
    
    # Summary
    print(f"\n{'=' * 80}")
    print("EXECUTION SUMMARY")
    print(f"{'=' * 80}")
    print(f"Test Categories Executed: {len(results)}")
    print(f"Expected Failures: {analysis['expected_failures']}")
    print(f"Unexpected Results: {analysis['unexpected_results']}")
    
    if analysis['expected_failures'] > 0:
        print(f"\n✅ SUCCESS: {analysis['expected_failures']} test categories correctly expose sync issues")
        print("These failures reveal the exact problems that need to be fixed.")
    
    if analysis['unexpected_results'] > 0:
        print(f"\n⚠️  WARNING: {analysis['unexpected_results']} test categories had unexpected results")
        print("Review the detailed output to understand why.")
    
    # Next steps
    print(f"\n📋 NEXT STEPS:")
    print("1. Review the failure report to understand specific issues")
    print("2. Implement fixes for each failing test")  
    print("3. Re-run tests to verify fixes")
    print("4. All tests should pass once sync functionality is complete")
    
    # Exit with appropriate code
    if analysis['unexpected_results'] > 0:
        sys.exit(1)  # Unexpected results
    else:
        sys.exit(0)  # Expected behavior


if __name__ == '__main__':
    main()