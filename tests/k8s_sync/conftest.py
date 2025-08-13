"""
Pytest configuration for K8s Sync TDD Test Suite

Configures test environment, fixtures, and markers for comprehensive
Kubernetes synchronization testing following London School TDD principles.
"""

import pytest
import os
import django
from django.conf import settings
from django.test import override_settings
from unittest.mock import patch

# Configure Django for testing
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()


def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line("markers", "integration: integration tests requiring external services")
    config.addinivalue_line("markers", "k8s_cluster: tests requiring real Kubernetes cluster")
    config.addinivalue_line("markers", "performance: performance and load testing")
    config.addinivalue_line("markers", "slow: slow-running tests")
    config.addinivalue_line("markers", "gui: GUI validation tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add slow marker to performance tests
        if "performance" in item.nodeid:
            item.add_marker(pytest.mark.slow)
        
        # Add integration marker to integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Add gui marker to GUI tests
        if "gui" in item.nodeid:
            item.add_marker(pytest.mark.gui)


@pytest.fixture(scope="session", autouse=True)
def django_test_setup():
    """Set up Django test environment."""
    # Configure test database settings
    test_settings = override_settings(
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        # Disable migrations for faster testing
        MIGRATION_MODULES={
            'netbox_hedgehog': None,
        },
        # Test-specific settings
        DEBUG=True,
        TESTING=True,
        # Disable external services during testing
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
    )
    
    with test_settings:
        # Create test database tables
        from django.core.management import call_command
        call_command('migrate', verbosity=0, interactive=False)
        yield


@pytest.fixture
def mock_k8s_client():
    """Provide mock K8s client for testing."""
    from .mocks.k8s_client_mocks import K8sMockScenarios
    
    mock_client = K8sMockScenarios.healthy_cluster()
    
    with patch('netbox_hedgehog.utils.k8s_client.K8sClient') as mock_client_class:
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def test_fabric():
    """Provide a test fabric instance."""
    from .utils.test_factories import create_fabric_with_state
    
    fabric = create_fabric_with_state('in_sync')
    yield fabric
    fabric.delete()


@pytest.fixture
def test_scenarios():
    """Provide complete set of test fabric scenarios."""
    from .utils.test_factories import create_test_sync_scenarios
    
    scenarios = create_test_sync_scenarios()
    yield scenarios
    
    # Cleanup
    for fabric in scenarios.values():
        fabric.delete()


@pytest.fixture
def timing_validator():
    """Provide timing validator for precision tests."""
    from .utils.timing_helpers import TimingValidator
    
    return TimingValidator(tolerance_seconds=5.0)


@pytest.fixture
def gui_validator():
    """Provide GUI validator for HTML validation tests."""
    from .utils.gui_validators import GUIStateValidator
    
    return GUIStateValidator()


@pytest.fixture(scope="session")
def k8s_cluster_config():
    """Provide K8s cluster configuration for integration tests."""
    return {
        'cluster_url': 'https://vlab-art.l.hhdev.io:6443',
        'service_account': 'hnp-sync',
        'namespace': 'default'
    }


@pytest.fixture
def performance_monitor():
    """Provide performance monitoring context."""
    import time
    import psutil
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.start_memory = None
            self.metrics = {}
        
        def start(self):
            self.start_time = time.perf_counter()
            self.start_memory = psutil.Process().memory_info().rss
        
        def stop(self):
            if self.start_time:
                self.metrics['duration'] = time.perf_counter() - self.start_time
            if self.start_memory:
                self.metrics['memory_growth'] = psutil.Process().memory_info().rss - self.start_memory
            return self.metrics
    
    return PerformanceMonitor()


def pytest_runtest_setup(item):
    """Set up individual test runs."""
    # Skip integration tests unless explicitly requested
    if "integration" in item.keywords:
        if not item.config.getoption("--integration", default=False):
            pytest.skip("Integration tests skipped (use --integration to run)")
    
    # Skip performance tests unless explicitly requested
    if "performance" in item.keywords:
        if not item.config.getoption("--performance", default=False):
            pytest.skip("Performance tests skipped (use --performance to run)")


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests"
    )
    parser.addoption(
        "--performance", 
        action="store_true",
        default=False,
        help="Run performance tests"
    )
    parser.addoption(
        "--k8s-cluster",
        action="store",
        default="https://vlab-art.l.hhdev.io:6443",
        help="Kubernetes cluster URL for integration tests"
    )


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks between tests."""
    yield
    # Cleanup happens automatically with patch context managers


@pytest.fixture
def capture_test_output():
    """Capture test output for analysis."""
    import io
    import sys
    from contextlib import redirect_stdout, redirect_stderr
    
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    class OutputCapture:
        def __enter__(self):
            self.stdout_redirect = redirect_stdout(stdout_capture)
            self.stderr_redirect = redirect_stderr(stderr_capture)
            self.stdout_redirect.__enter__()
            self.stderr_redirect.__enter__()
            return self
        
        def __exit__(self, *args):
            self.stdout_redirect.__exit__(*args)
            self.stderr_redirect.__exit__(*args)
        
        @property
        def stdout(self):
            return stdout_capture.getvalue()
        
        @property
        def stderr(self):
            return stderr_capture.getvalue()
    
    return OutputCapture()


# Test data fixtures
@pytest.fixture
def sample_crd_data():
    """Provide sample CRD data for testing."""
    return {
        'vpc_crd': {
            'apiVersion': 'hedgehog.githedgehog.com/v1alpha2',
            'kind': 'VPC',
            'metadata': {
                'name': 'test-vpc',
                'namespace': 'default'
            },
            'spec': {
                'subnet': '10.0.0.0/24'
            }
        },
        'connection_crd': {
            'apiVersion': 'hedgehog.githedgehog.com/v1alpha2', 
            'kind': 'Connection',
            'metadata': {
                'name': 'test-connection',
                'namespace': 'default'
            },
            'spec': {
                'spine': 'spine-1',
                'leaf': 'leaf-1'
            }
        }
    }


# Custom assertions
def pytest_assertrepr_compare(config, op, left, right):
    """Custom assertion representations for better test failure messages."""
    if op == "==" and hasattr(left, 'calculated_sync_status') and isinstance(right, str):
        return [
            f"Sync state assertion failed:",
            f"   Expected state: {right}",
            f"   Actual state: {left.calculated_sync_status}",
            f"   Fabric: {left.name}",
            f"   Server: {left.kubernetes_server}",
            f"   Enabled: {left.sync_enabled}",
            f"   Last sync: {left.last_sync}",
        ]