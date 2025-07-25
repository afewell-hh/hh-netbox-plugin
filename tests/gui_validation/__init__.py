"""
GUI Validation Test Framework for Hedgehog NetBox Plugin

This package contains the lightweight test framework designed for demo validation.
It provides fast, agent-friendly testing with clear pass/fail reporting.

Key Components:
- test_runner.py: Core test execution framework
- base_test.py: Base test class with NetBox client utilities  
- config.py: Configuration management system
- run_demo_tests.py: Agent-friendly CLI interface (in project root)

Usage:
    # From project root
    python run_demo_tests.py                # Run all tests
    python run_demo_tests.py --quick        # Run essential tests only
    python run_demo_tests.py --check-env    # Check environment
    
    # Direct framework usage
    from tests.gui_validation.test_runner import LightweightTestRunner
    runner = LightweightTestRunner()
    success = runner.run_all_tests()
"""

__version__ = "1.0.0"
__author__ = "Test Architecture Specialist"

# Export main classes for easy importing
from .test_runner import LightweightTestRunner, TestResult, TestSuite
from .base_test import DemoValidationTestCase, NetBoxTestClient, QuickSmokeTest
from .config import TestConfig, ConfigManager, get_default_config

__all__ = [
    'LightweightTestRunner',
    'TestResult', 
    'TestSuite',
    'DemoValidationTestCase',
    'NetBoxTestClient',
    'QuickSmokeTest',
    'TestConfig',
    'ConfigManager',
    'get_default_config'
]