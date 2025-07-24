#!/usr/bin/env python3
"""
HNP End-to-End Testing Framework Runner

Comprehensive test runner for all HNP GUI functionality tests.
This script runs the complete test suite and provides detailed reporting.

Usage:
    python run_hnp_tests.py                    # Run all tests
    python run_hnp_tests.py --gui-only         # Run only GUI tests
    python run_hnp_tests.py --api-only         # Run only API tests
    python run_hnp_tests.py --quick            # Run quick test subset
    python run_hnp_tests.py --verbose          # Verbose output
"""

import os
import sys
import django
import argparse
import time
import subprocess
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

def setup_django():
    """Initialize Django for testing."""
    try:
        django.setup()
        return True
    except Exception as e:
        print(f"❌ Failed to setup Django: {e}")
        return False

def check_prerequisites():
    """Check that all prerequisites are met for testing."""
    print("🔍 Checking prerequisites...")
    
    checks = {
        'Django setup': setup_django(),
        'NetBox token': check_netbox_token(),
        'Container running': check_container_running(),
        'Database access': check_database_access(),
        'HCKC cluster': check_hckc_cluster()
    }
    
    print("\n📋 Prerequisites Check:")
    for check_name, status in checks.items():
        status_icon = "✅" if status else "⚠️"
        print(f"  {status_icon} {check_name}")
    
    return checks

def check_netbox_token():
    """Check if NetBox token is available."""
    token_path = '/home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox.token'
    return os.path.exists(token_path)

def check_container_running():
    """Check if NetBox container is running."""
    try:
        result = subprocess.run(
            ['sudo', 'docker', 'ps', '--filter', 'name=netbox-docker-netbox-1', '--format', '{{.Names}}'],
            capture_output=True, text=True, timeout=10
        )
        return 'netbox-docker-netbox-1' in result.stdout
    except:
        return False

def check_database_access():
    """Check if database is accessible."""
    try:
        from netbox_hedgehog.models.fabric import HedgehogFabric
        HedgehogFabric.objects.count()
        return True
    except:
        return False

def check_hckc_cluster():
    """Check if HCKC cluster is accessible."""
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'nodes'],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except:
        return False

def run_test_suite(test_modules, verbosity=1, failfast=True):
    """
    Run the specified test modules.
    
    Args:
        test_modules: List of test module names
        verbosity: Django test verbosity level
        failfast: Stop on first failure
        
    Returns:
        Dictionary with test results
    """
    from django.test.runner import DiscoverRunner
    
    print(f"\n🧪 Running {len(test_modules)} test modules...")
    print(f"📝 Modules: {', '.join(test_modules)}")
    
    # Configure test runner
    test_runner = DiscoverRunner(
        verbosity=verbosity,
        interactive=False,
        failfast=failfast,
        keepdb=True  # Keep test database for faster subsequent runs
    )
    
    start_time = time.time()
    
    try:
        failures = test_runner.run_tests(test_modules)
        end_time = time.time()
        
        return {
            'success': failures == 0,
            'failures': failures,
            'duration': end_time - start_time,
            'modules': test_modules
        }
    except Exception as e:
        end_time = time.time()
        return {
            'success': False,
            'failures': -1,
            'error': str(e),
            'duration': end_time - start_time,
            'modules': test_modules
        }

def run_gui_tests(verbosity=1):
    """Run GUI integration tests."""
    test_modules = [
        'netbox_hedgehog.tests.test_gui_integration',
        'netbox_hedgehog.tests.test_templates'
    ]
    return run_test_suite(test_modules, verbosity)

def run_api_tests(verbosity=1):
    """Run API endpoint tests."""
    test_modules = [
        'netbox_hedgehog.tests.test_api_endpoints'
    ]
    return run_test_suite(test_modules, verbosity)

def run_workflow_tests(verbosity=1):
    """Run end-to-end workflow tests."""
    test_modules = [
        'netbox_hedgehog.tests.test_e2e_workflows'
    ]
    return run_test_suite(test_modules, verbosity)

def run_all_tests(verbosity=1):
    """Run complete test suite."""
    test_modules = [
        'netbox_hedgehog.tests.test_gui_integration',
        'netbox_hedgehog.tests.test_api_endpoints',
        'netbox_hedgehog.tests.test_templates',
        'netbox_hedgehog.tests.test_e2e_workflows'
    ]
    return run_test_suite(test_modules, verbosity)

def run_quick_tests(verbosity=1):
    """Run quick subset of tests for fast feedback."""
    test_modules = [
        'netbox_hedgehog.tests.test_gui_integration.GUIIntegrationTests.test_homepage_loads_successfully',
        'netbox_hedgehog.tests.test_gui_integration.GUIIntegrationTests.test_all_cr_list_pages_load_successfully',
        'netbox_hedgehog.tests.test_api_endpoints.APIEndpointTests.test_all_cr_list_endpoints',
        'netbox_hedgehog.tests.test_templates.TemplateRenderingTests.test_overview_template_renders'
    ]
    return run_test_suite(test_modules, verbosity)

def generate_test_report(results_list):
    """Generate comprehensive test report."""
    print("\n" + "="*80)
    print("🎯 HNP END-TO-END TESTING FRAMEWORK RESULTS")
    print("="*80)
    
    total_duration = sum(r['duration'] for r in results_list)
    total_failures = sum(r['failures'] for r in results_list if r['failures'] >= 0)
    overall_success = all(r['success'] for r in results_list)
    
    # Overall status
    status_icon = "✅" if overall_success else "❌"
    print(f"\n{status_icon} OVERALL STATUS: {'PASSED' if overall_success else 'FAILED'}")
    print(f"⏱️  Total Duration: {total_duration:.2f} seconds")
    print(f"💥 Total Failures: {total_failures}")
    
    # Detailed results
    print(f"\n📊 DETAILED RESULTS:")
    for i, result in enumerate(results_list, 1):
        status = "✅ PASSED" if result['success'] else "❌ FAILED"
        duration = result['duration']
        failures = result['failures']
        
        print(f"  {i}. {status} ({duration:.2f}s, {failures} failures)")
        for module in result['modules']:
            print(f"     • {module}")
        
        if not result['success'] and 'error' in result:
            print(f"     ⚠️  Error: {result['error']}")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    if overall_success:
        print("  • All tests passed! GUI functionality is working correctly.")
        print("  • Consider running tests regularly to catch regressions.")
        print("  • Add new tests when implementing new features.")
    else:
        print("  • Review test failures and fix underlying issues.")
        print("  • Run individual test modules to isolate problems.")
        print("  • Check container logs: sudo docker logs netbox-docker-netbox-1 --tail 50")
        print("  • Restart container if needed: sudo docker restart netbox-docker-netbox-1")
    
    # Next steps
    print(f"\n🚀 NEXT STEPS:")
    if overall_success:
        print("  • ✅ GUI functionality verified - safe to report success")
        print("  • ✅ System is ready for production use")
        print("  • ✅ Future agents can rely on this testing framework")
    else:
        print("  • 🔧 Fix failing tests before reporting success")
        print("  • 🔍 Investigate root causes of failures")
        print("  • 🔁 Re-run tests after fixes")
    
    return overall_success

def restart_container_if_needed():
    """Restart NetBox container if tests are failing due to container issues."""
    print("🔄 Checking if container restart is needed...")
    
    if not check_container_running():
        print("⚠️  Container not running - attempting restart...")
        try:
            subprocess.run(['sudo', 'docker', 'restart', 'netbox-docker-netbox-1'], 
                         check=True, timeout=60)
            print("✅ Container restarted successfully")
            
            # Wait for container to be ready
            print("⏳ Waiting for container to be ready...")
            time.sleep(30)
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to restart container: {e}")
            return False
    
    return True

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="HNP End-to-End Testing Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_hnp_tests.py                    # Run all tests
  python run_hnp_tests.py --gui-only         # Run only GUI tests  
  python run_hnp_tests.py --quick            # Run quick test subset
  python run_hnp_tests.py --verbose          # Verbose output
  python run_hnp_tests.py --restart          # Restart container first
        """
    )
    
    parser.add_argument('--gui-only', action='store_true',
                       help='Run only GUI integration tests')
    parser.add_argument('--api-only', action='store_true',
                       help='Run only API endpoint tests')
    parser.add_argument('--workflow-only', action='store_true',
                       help='Run only end-to-end workflow tests')
    parser.add_argument('--quick', action='store_true',
                       help='Run quick subset of tests')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose test output')
    parser.add_argument('--restart', action='store_true',
                       help='Restart NetBox container before testing')
    parser.add_argument('--skip-prereq', action='store_true',
                       help='Skip prerequisite checks')
    
    args = parser.parse_args()
    
    print("🎯 HNP END-TO-END TESTING FRAMEWORK")
    print("="*50)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Restart container if requested
    if args.restart:
        if not restart_container_if_needed():
            print("❌ Container restart failed - aborting tests")
            return 1
    
    # Check prerequisites
    if not args.skip_prereq:
        prereq_results = check_prerequisites()
        if not prereq_results['Django setup']:
            print("❌ Django setup failed - cannot continue")
            return 1
    
    # Determine verbosity
    verbosity = 2 if args.verbose else 1
    
    # Run appropriate test suite
    results = []
    
    if args.gui_only:
        print("\n🖥️  Running GUI tests only...")
        results.append(run_gui_tests(verbosity))
    elif args.api_only:
        print("\n🔌 Running API tests only...")
        results.append(run_api_tests(verbosity))
    elif args.workflow_only:
        print("\n🔄 Running workflow tests only...")
        results.append(run_workflow_tests(verbosity))
    elif args.quick:
        print("\n⚡ Running quick test subset...")
        results.append(run_quick_tests(verbosity))
    else:
        print("\n🎯 Running complete test suite...")
        
        # Run tests in logical sequence
        print("\n1️⃣ Running GUI Integration Tests...")
        results.append(run_gui_tests(verbosity))
        
        print("\n2️⃣ Running API Endpoint Tests...")
        results.append(run_api_tests(verbosity))
        
        print("\n3️⃣ Running Template Rendering Tests...")
        template_result = run_test_suite(['netbox_hedgehog.tests.test_templates'], verbosity)
        results.append(template_result)
        
        print("\n4️⃣ Running End-to-End Workflow Tests...")
        results.append(run_workflow_tests(verbosity))
    
    # Generate final report
    success = generate_test_report(results)
    
    print(f"\n🏁 Testing completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())