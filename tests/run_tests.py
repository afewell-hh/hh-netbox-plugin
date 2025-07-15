#!/usr/bin/env python3
"""
Test runner for GitOps Backend Architecture tests
Week 1 comprehensive test suite for GitRepository model, API, and migration
"""

import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

def setup_django():
    """Setup Django for testing"""
    django.setup()

def run_tests():
    """Run the test suite"""
    from django.test.runner import DiscoverRunner
    
    test_runner = DiscoverRunner(verbosity=2, interactive=True)
    
    # Define test modules to run
    test_modules = [
        'tests.test_git_repository_model',
        'tests.test_git_repository_api',
        'tests.test_git_repository_migration',
    ]
    
    print("=" * 80)
    print("GitOps Backend Architecture - Week 1 Test Suite")
    print("=" * 80)
    print(f"Running tests for modules: {', '.join(test_modules)}")
    print()
    
    failures = test_runner.run_tests(test_modules)
    
    if failures:
        print(f"\n❌ {failures} test(s) failed")
        return 1
    else:
        print("\n✅ All tests passed!")
        return 0

def run_specific_test(test_name):
    """Run a specific test class or method"""
    from django.test.runner import DiscoverRunner
    
    test_runner = DiscoverRunner(verbosity=2, interactive=True)
    
    print(f"Running specific test: {test_name}")
    failures = test_runner.run_tests([test_name])
    
    return 0 if not failures else 1

def main():
    """Main entry point"""
    setup_django()
    
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        return run_specific_test(test_name)
    else:
        # Run all tests
        return run_tests()

if __name__ == '__main__':
    sys.exit(main())