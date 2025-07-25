#!/usr/bin/env python3
"""
Configuration System for Demo Validation Tests

Provides centralized configuration for:
- Test selection and filtering
- Timeout management
- Environment configuration  
- Parallel execution options
- Performance thresholds
"""

import os
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TestConfig:
    """Configuration for test execution"""
    
    # Performance settings
    max_workers: int = 4
    timeout_per_test: int = 30
    max_total_duration: int = 120  # 2 minutes
    max_page_load_time: float = 2.0
    
    # Environment settings
    netbox_url: str = "http://localhost:8000"
    netbox_token: Optional[str] = None
    skip_auth: bool = False
    
    # Test selection
    test_modules: Optional[List[str]] = None
    exclude_modules: Optional[List[str]] = None
    test_tags: Optional[List[str]] = None
    
    # Execution options
    parallel_suites: bool = True
    parallel_tests: bool = True
    fail_fast: bool = False
    keep_test_db: bool = True
    
    # Output options
    verbose: bool = False
    quiet: bool = False
    show_timings: bool = True
    show_errors: bool = True
    
    # Demo-specific settings
    demo_mode: bool = False  # Optimized for demo scenarios
    quick_mode: bool = False  # Run only essential tests
    smoke_test_only: bool = False  # Run basic connectivity tests only


class ConfigManager:
    """Manages test configuration from multiple sources"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self._config = TestConfig()
        self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration from multiple sources in priority order"""
        # 1. Load from config file if specified
        if self.config_file:
            self._load_from_file(self.config_file)
        
        # 2. Load from environment variables
        self._load_from_environment()
        
        # 3. Load from default config file if it exists
        default_config = Path(__file__).parent / 'test_config.json'
        if default_config.exists():
            self._load_from_file(str(default_config))
    
    def _load_from_file(self, config_file: str):
        """Load configuration from JSON file"""
        try:
            import json
            with open(config_file, 'r') as f:
                file_config = json.load(f)
            
            # Update config with file values
            for key, value in file_config.items():
                if hasattr(self._config, key):
                    setattr(self._config, key, value)
        except Exception as e:
            print(f"⚠️  Warning: Could not load config file {config_file}: {e}")
    
    def _load_from_environment(self):
        """Load configuration from environment variables"""
        env_mappings = {
            'DEMO_TEST_MAX_WORKERS': ('max_workers', int),
            'DEMO_TEST_TIMEOUT': ('timeout_per_test', int),
            'DEMO_TEST_MAX_DURATION': ('max_total_duration', int),
            'DEMO_TEST_PAGE_TIMEOUT': ('max_page_load_time', float),
            'NETBOX_URL': ('netbox_url', str),
            'NETBOX_TOKEN': ('netbox_token', str),
            'DEMO_TEST_PARALLEL': ('parallel_suites', lambda x: x.lower() == 'true'),
            'DEMO_TEST_VERBOSE': ('verbose', lambda x: x.lower() == 'true'),
            'DEMO_TEST_QUICK': ('quick_mode', lambda x: x.lower() == 'true'),
            'DEMO_TEST_DEMO_MODE': ('demo_mode', lambda x: x.lower() == 'true'),
        }
        
        for env_var, (attr_name, converter) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    converted_value = converter(value)
                    setattr(self._config, attr_name, converted_value)
                except (ValueError, TypeError) as e:
                    print(f"⚠️  Warning: Invalid value for {env_var}: {value} ({e})")
    
    def get_config(self) -> TestConfig:
        """Get the current configuration"""
        return self._config
    
    def update_config(self, **kwargs):
        """Update configuration with provided values"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
            else:
                print(f"⚠️  Warning: Unknown config option: {key}")
    
    def get_quick_test_modules(self) -> List[str]:
        """Get modules for quick testing mode"""
        return [
            'tests.gui_validation.test_smoke',
            'tests.gui_validation.test_navigation', 
            'tests.gui_validation.test_demo_elements'
        ]
    
    def get_demo_test_modules(self) -> List[str]:
        """Get modules optimized for demo scenarios"""
        return [
            'tests.gui_validation.test_smoke',
            'tests.gui_validation.test_navigation',
            'tests.gui_validation.test_demo_elements',
            'tests.gui_validation.test_fabric_management',
            'tests.gui_validation.test_crd_operations'
        ]
    
    def get_all_test_modules(self) -> List[str]:
        """Get all available test modules"""
        # This would be populated by test discovery
        return [
            'tests.gui_validation.test_smoke',
            'tests.gui_validation.test_navigation',
            'tests.gui_validation.test_demo_elements',
            'tests.gui_validation.test_fabric_management',
            'tests.gui_validation.test_crd_operations',
            'tests.gui_validation.test_gitops_integration',
            'tests.gui_validation.test_performance'
        ]
    
    def apply_demo_optimizations(self):
        """Apply optimizations for demo scenarios"""
        self._config.demo_mode = True
        self._config.fail_fast = True
        self._config.max_total_duration = 90  # Shorter for demos
        self._config.timeout_per_test = 20    # Faster individual tests
        self._config.verbose = False          # Less noise
        self._config.show_timings = True      # But show performance
    
    def apply_quick_optimizations(self):
        """Apply optimizations for quick testing"""
        self._config.quick_mode = True
        self._config.max_workers = 2          # Less parallelism for stability
        self._config.timeout_per_test = 15    # Quick tests
        self._config.max_total_duration = 45  # Very fast
        self._config.fail_fast = True         # Stop on first failure
    
    def validate_config(self) -> List[str]:
        """
        Validate configuration and return list of warnings/errors.
        
        Returns:
            List of validation messages (empty if all good)
        """
        issues = []
        
        # Validate performance settings
        if self._config.max_workers < 1:
            issues.append("max_workers must be at least 1")
        
        if self._config.timeout_per_test < 5:
            issues.append("timeout_per_test should be at least 5 seconds")
        
        if self._config.max_total_duration < 30:
            issues.append("max_total_duration should be at least 30 seconds")
        
        # Validate URL format
        if not self._config.netbox_url.startswith(('http://', 'https://')):
            issues.append("netbox_url should start with http:// or https://")
        
        # Check for conflicting options
        if self._config.quick_mode and self._config.verbose:
            issues.append("quick_mode and verbose may conflict (quick mode prefers minimal output)")
        
        if self._config.smoke_test_only and self._config.test_modules:
            issues.append("smoke_test_only conflicts with specific test_modules")
        
        return issues
    
    def print_config_summary(self):
        """Print current configuration summary"""
        print("⚙️  TEST CONFIGURATION")
        print("=" * 40)
        
        config = self._config
        
        print(f"Performance:")
        print(f"  • Max workers: {config.max_workers}")
        print(f"  • Timeout per test: {config.timeout_per_test}s")
        print(f"  • Max total duration: {config.max_total_duration}s")
        print(f"  • Max page load time: {config.max_page_load_time}s")
        
        print(f"\nEnvironment:")
        print(f"  • NetBox URL: {config.netbox_url}")
        print(f"  • Authentication: {'Token' if config.netbox_token else 'Anonymous'}")
        
        print(f"\nExecution:")
        print(f"  • Parallel suites: {config.parallel_suites}")
        print(f"  • Parallel tests: {config.parallel_tests}")
        print(f"  • Fail fast: {config.fail_fast}")
        
        print(f"\nMode:")
        if config.smoke_test_only:
            print(f"  • Mode: Smoke test only")
        elif config.quick_mode:
            print(f"  • Mode: Quick testing")
        elif config.demo_mode:
            print(f"  • Mode: Demo optimized")
        else:
            print(f"  • Mode: Full testing")
        
        # Validate and show issues
        issues = self.validate_config()
        if issues:
            print(f"\n⚠️  Configuration Issues:")
            for issue in issues:
                print(f"  • {issue}")


# Predefined configurations for common scenarios

def get_quick_config() -> TestConfig:
    """Get configuration optimized for quick testing"""
    config = TestConfig()
    config.quick_mode = True
    config.max_workers = 2
    config.timeout_per_test = 15
    config.max_total_duration = 45
    config.fail_fast = True
    config.verbose = False
    return config


def get_demo_config() -> TestConfig:
    """Get configuration optimized for demo scenarios"""
    config = TestConfig()
    config.demo_mode = True
    config.max_workers = 3
    config.timeout_per_test = 20
    config.max_total_duration = 90
    config.fail_fast = True
    config.show_timings = True
    config.verbose = False
    return config


def get_comprehensive_config() -> TestConfig:
    """Get configuration for comprehensive testing"""
    config = TestConfig()
    config.max_workers = 4
    config.timeout_per_test = 30
    config.max_total_duration = 120
    config.fail_fast = False
    config.verbose = True
    config.show_timings = True
    config.show_errors = True
    return config


def get_smoke_config() -> TestConfig:
    """Get configuration for smoke testing only"""
    config = TestConfig()
    config.smoke_test_only = True
    config.max_workers = 1
    config.timeout_per_test = 10
    config.max_total_duration = 30
    config.fail_fast = True
    config.verbose = False
    return config


# Default configuration manager instance
default_config_manager = ConfigManager()


def get_default_config() -> TestConfig:
    """Get the default configuration"""
    return default_config_manager.get_config()


if __name__ == '__main__':
    # Demo the configuration system
    manager = ConfigManager()
    manager.print_config_summary()