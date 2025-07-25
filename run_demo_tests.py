#!/usr/bin/env python3
"""
Agent-Friendly CLI for Demo Validation Tests

This is the main entry point for agents to run demo validation tests.
Designed for single command execution with clear pass/fail output.

Usage:
    python run_demo_tests.py                    # Run all demo tests
    python run_demo_tests.py --quick            # Run essential tests only
    python run_demo_tests.py --verbose          # Detailed output
    python run_demo_tests.py --check-env        # Check environment only
    python run_demo_tests.py --list-tests       # List available tests

Exit Codes:
    0: All tests passed - safe to proceed with demo
    1: Tests failed - DO NOT proceed with demo
    2: Environment issues - check setup
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import our test runner
try:
    from tests.gui_validation.test_runner import LightweightTestRunner
    from tests.gui_validation.base_test import NetBoxTestClient
except ImportError as e:
    print(f"❌ Error importing test framework: {e}")
    print("💡 Make sure you're running from the project root directory")
    sys.exit(2)


def check_environment() -> bool:
    """
    Check if the environment is ready for demo testing.
    
    Returns:
        True if environment is ready, False otherwise
    """
    print("🔍 ENVIRONMENT CHECK")
    print("=" * 40)
    
    checks = []
    
    # Check NetBox container
    print("🐳 Checking NetBox Docker container...")
    try:
        result = subprocess.run(
            ['sudo', 'docker', 'ps', '--filter', 'name=netbox-docker-netbox-1', '--format', '{{.Names}}'],
            capture_output=True, text=True, timeout=10
        )
        container_running = 'netbox-docker-netbox-1' in result.stdout
        status = "✅ Running" if container_running else "❌ Not running"
        print(f"   {status}")
        checks.append(("Docker container", container_running))
    except Exception as e:
        print(f"   ❌ Error checking container: {e}")
        checks.append(("Docker container", False))
    
    # Check NetBox accessibility
    print("🌐 Checking NetBox web interface...")
    try:
        client = NetBoxTestClient()
        response = client.get('/')
        netbox_accessible = response.status_code in [200, 301, 302]
        status = "✅ Accessible" if netbox_accessible else f"❌ Status {response.status_code}"
        print(f"   {status}")
        checks.append(("NetBox web interface", netbox_accessible))
    except Exception as e:
        print(f"   ❌ Error: {e}")
        checks.append(("NetBox web interface", False))
    
    # Check plugin accessibility
    print("🔌 Checking Hedgehog plugin...")
    try:
        client = NetBoxTestClient()
        response = client.get('/plugins/hedgehog/')
        plugin_accessible = response.status_code in [200, 301, 302]
        status = "✅ Accessible" if plugin_accessible else f"❌ Status {response.status_code}"
        print(f"   {status}")
        checks.append(("Hedgehog plugin", plugin_accessible))
    except Exception as e:
        print(f"   ❌ Error: {e}")
        checks.append(("Hedgehog plugin", False))
    
    # Check authentication token
    print("🔑 Checking authentication...")
    token_locations = [
        Path(project_root) / 'gitignore' / 'netbox.token',
        Path.home() / '.netbox_token'
    ]
    
    token_found = False
    for token_file in token_locations:
        if token_file.exists():
            token_found = True
            break
    
    # Also check environment variable
    if os.getenv('NETBOX_TOKEN'):
        token_found = True
    
    status = "✅ Available" if token_found else "⚠️  Not found (tests may use anonymous access)"
    print(f"   {status}")
    checks.append(("Authentication token", token_found))
    
    # Check Kubernetes cluster (optional)
    print("☸️  Checking Kubernetes cluster...")
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'nodes'],
            capture_output=True, text=True, timeout=10
        )
        k8s_accessible = result.returncode == 0
        status = "✅ Accessible" if k8s_accessible else "⚠️  Not accessible (optional)"
        print(f"   {status}")
        checks.append(("Kubernetes cluster", k8s_accessible))
    except Exception:
        print("   ⚠️  Not accessible (optional)")
        checks.append(("Kubernetes cluster", False))
    
    # Summary
    print("\n📋 ENVIRONMENT SUMMARY:")
    critical_checks = ["Docker container", "NetBox web interface", "Hedgehog plugin"]
    critical_passed = all(passed for name, passed in checks if name in critical_checks)
    
    for name, passed in checks:
        icon = "✅" if passed else ("❌" if name in critical_checks else "⚠️")
        criticality = " (critical)" if name in critical_checks else " (optional)" if name == "Kubernetes cluster" else ""
        print(f"  {icon} {name}{criticality}")
    
    if critical_passed:
        print("\n🎯 Environment ready for demo testing!")
        return True
    else:
        print("\n⚠️  Environment not ready - fix critical issues before testing")
        return False


def list_available_tests() -> None:
    """List all available test modules"""
    print("📋 AVAILABLE DEMO TESTS")
    print("=" * 40)
    
    runner = LightweightTestRunner()
    test_modules = runner.discover_tests()
    
    if not test_modules:
        print("⚠️  No test modules found")
        return
    
    print(f"Found {len(test_modules)} test modules:\n")
    
    for i, module_name in enumerate(test_modules, 1):
        # Try to get module description
        try:
            module = runner.load_test_module(module_name)
            description = getattr(module, '__doc__', '').strip().split('\n')[0] if module else ""
            if not description:
                description = "Demo validation tests"
        except:
            description = "Demo validation tests"
        
        print(f"{i:2d}. {module_name}")
        print(f"     {description}")
    
    print(f"\n💡 Run specific modules with: --modules {' '.join(test_modules[:2])}")


def run_quick_tests() -> bool:
    """Run essential tests only (< 30 seconds)"""
    print("⚡ QUICK DEMO VALIDATION")
    print("=" * 40)
    print("Running essential tests only for fast feedback...\n")
    
    # Quick test modules - these should be the most important ones
    quick_modules = [
        'tests.gui_validation.test_smoke',         # Basic connectivity
        'tests.gui_validation.test_navigation',    # Key pages load
        'tests.gui_validation.test_demo_elements'  # Demo-critical features
    ]
    
    runner = LightweightTestRunner(max_workers=2, timeout_per_test=10)
    
    # Only run modules that actually exist
    existing_modules = runner.discover_tests()
    quick_modules = [m for m in quick_modules if m in existing_modules]
    
    if not quick_modules:
        print("⚠️  No quick test modules found - running all discovered tests")
        return runner.run_all_tests()
    
    return runner.run_all_tests(test_modules=quick_modules, parallel_suites=True)


def run_full_tests(parallel: bool = True, verbose: bool = False) -> bool:
    """Run complete demo validation suite"""
    print("🎯 FULL DEMO VALIDATION")
    print("=" * 40)
    print("Running complete test suite for comprehensive validation...\n")
    
    runner = LightweightTestRunner(max_workers=4, timeout_per_test=30)
    success = runner.run_all_tests(parallel_suites=parallel)
    
    # Print detailed report
    runner.print_summary(verbose=verbose)
    
    return success


def restart_netbox_container() -> bool:
    """Restart NetBox container if needed"""
    print("🔄 CONTAINER RESTART")
    print("=" * 40)
    
    try:
        print("Restarting NetBox container...")
        subprocess.run(['sudo', 'docker', 'restart', 'netbox-docker-netbox-1'], 
                      check=True, timeout=60)
        print("✅ Container restarted successfully")
        
        print("⏳ Waiting for container to be ready...")
        import time
        time.sleep(30)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to restart container: {e}")
        return False
    except Exception as e:
        print(f"❌ Error during restart: {e}")
        return False


def main():
    """Main entry point for agent-friendly CLI"""
    parser = argparse.ArgumentParser(
        description='Agent-Friendly Demo Validation Test Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_demo_tests.py                 # Run all demo tests
  python run_demo_tests.py --quick         # Run essential tests only  
  python run_demo_tests.py --check-env     # Check environment readiness
  python run_demo_tests.py --list-tests    # List available tests
  python run_demo_tests.py --restart       # Restart container first
  python run_demo_tests.py --verbose       # Detailed output

Exit Codes:
  0: All tests passed - SAFE to proceed with demo
  1: Tests failed - DO NOT proceed with demo  
  2: Environment issues - check setup first
        """
    )
    
    parser.add_argument('--quick', action='store_true',
                       help='Run essential tests only (< 30 seconds)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Detailed output including error details')
    parser.add_argument('--check-env', action='store_true',
                       help='Check environment readiness only')
    parser.add_argument('--list-tests', action='store_true',
                       help='List available test modules')
    parser.add_argument('--restart', action='store_true',
                       help='Restart NetBox container before testing')
    parser.add_argument('--no-parallel', action='store_true',
                       help='Disable parallel test execution')
    parser.add_argument('--modules', nargs='+',
                       help='Run specific test modules only')
    
    args = parser.parse_args()
    
    # Print header
    print("🎯 HEDGEHOG DEMO VALIDATION TESTS")
    print("=" * 50)
    print(f"🕐 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Handle special commands first
    if args.list_tests:
        list_available_tests()
        return 0
    
    if args.check_env:
        env_ready = check_environment()
        return 0 if env_ready else 2
    
    if args.restart:
        if not restart_netbox_container():
            return 2
        print()
    
    # Check environment before running tests
    print("🔍 Pre-flight environment check...")
    env_ready = check_environment()
    if not env_ready:
        print("\n❌ Environment not ready for testing")
        print("💡 Fix critical issues or use --restart to restart container")
        return 2
    
    print()
    
    # Run tests based on arguments
    try:
        if args.quick:
            success = run_quick_tests()
        elif args.modules:
            print(f"🔧 CUSTOM TEST SELECTION")
            print("=" * 40)
            print(f"Running modules: {', '.join(args.modules)}\n")
            
            runner = LightweightTestRunner()
            success = runner.run_all_tests(
                test_modules=args.modules,
                parallel_suites=not args.no_parallel
            )
            runner.print_summary(verbose=args.verbose)
        else:
            success = run_full_tests(
                parallel=not args.no_parallel,
                verbose=args.verbose
            )
        
        # Final verdict for agents
        print("\n" + "=" * 60)
        if success:
            print("🎉 DEMO VALIDATION: ✅ PASSED")
            print("🚀 AGENT INSTRUCTION: SAFE to proceed with demo tasks")
            print("✨ All demo workflows validated successfully")
        else:
            print("🚨 DEMO VALIDATION: ❌ FAILED") 
            print("🛑 AGENT INSTRUCTION: DO NOT proceed with demo")
            print("🔧 Fix failing tests before attempting demo")
        
        print(f"🏁 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2


if __name__ == '__main__':
    sys.exit(main())