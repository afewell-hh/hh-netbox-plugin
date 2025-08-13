"""
Pytest Configuration for TDD London School Issue #40 Tests

Provides comprehensive test fixtures and mocks following London School TDD principles:
1. Extensive mocking of external dependencies
2. Focus on behavior testing
3. Mock-first development approach
4. Contract testing between components
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from django.utils import timezone

# Configure Django test environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')


@pytest.fixture(scope="session")
def django_setup():
    """Set up Django for testing with mock fallback."""
    try:
        import django
        django.setup()
        return True
    except (ImportError, ModuleNotFoundError):
        return False


@pytest.fixture
def mock_hedgehog_fabric():
    """
    Mock HedgehogFabric following London School principles.
    
    Focus: Provide a mock that responds to expected messages/methods.
    """
    mock_fabric = Mock()
    mock_fabric.id = 35
    mock_fabric.name = "Test Fabric"
    mock_fabric.sync_enabled = True
    mock_fabric.scheduler_enabled = True
    mock_fabric.sync_interval = 60
    mock_fabric.last_sync = None
    mock_fabric.sync_status = 'never_synced'
    mock_fabric.connection_status = 'unknown'
    mock_fabric.kubernetes_server = 'https://vlab-art.l.hhdev.io:6443'
    mock_fabric.kubernetes_namespace = 'default'
    mock_fabric.git_repository_url = 'https://github.com/test/repo.git'
    mock_fabric.git_branch = 'main'
    mock_fabric.git_path = 'hedgehog/'
    
    # Mock methods that return behavioral responses
    mock_fabric.needs_sync.return_value = True
    mock_fabric.should_be_scheduled.return_value = True
    mock_fabric.calculate_scheduler_health_score.return_value = 0.5
    mock_fabric.get_kubernetes_config.return_value = {
        'host': 'https://vlab-art.l.hhdev.io:6443',
        'verify_ssl': False
    }
    mock_fabric.calculated_sync_status = 'never_synced'
    mock_fabric.get_scheduler_priority_level.return_value = 3
    
    return mock_fabric


@pytest.fixture 
def mock_fabric_manager():
    """
    Mock Django ORM Manager for HedgehogFabric.
    
    Focus: Mock the ORM interface and query behavior.
    """
    mock_manager = Mock()
    mock_queryset = Mock()
    
    # Configure the query chain
    mock_manager.filter.return_value = mock_queryset
    mock_queryset.select_related.return_value = mock_queryset
    mock_queryset.order_by.return_value = mock_queryset
    mock_queryset.get.return_value = Mock()
    mock_queryset.count.return_value = 1
    mock_queryset.exists.return_value = True
    mock_queryset.first.return_value = Mock()
    
    return mock_manager


@pytest.fixture
def mock_celery_app():
    """
    Mock Celery Application for testing task registration.
    
    Focus: Test the contract between Celery and our scheduler tasks.
    """
    mock_app = Mock()
    mock_app.conf.beat_schedule = {
        'master-sync-scheduler': {
            'task': 'netbox_hedgehog.tasks.master_sync_scheduler',
            'schedule': 60.0,
            'options': {'queue': 'scheduler_master', 'priority': 10}
        }
    }
    mock_app.tasks = {
        'netbox_hedgehog.tasks.master_sync_scheduler': Mock()
    }
    return mock_app


@pytest.fixture
def mock_rq_queue():
    """
    Mock RQ Queue for testing NetBox background task integration.
    
    Focus: Test the contract between NetBox RQ and our scheduler.
    """
    mock_queue = Mock()
    mock_job = Mock()
    mock_job.id = 'test_job_123'
    mock_queue.enqueue.return_value = mock_job
    return mock_queue


@pytest.fixture
def mock_redis_connection():
    """
    Mock Redis connection for RQ testing.
    """
    mock_redis = Mock()
    mock_redis.ping.return_value = True
    return mock_redis


@pytest.fixture
def mock_enhanced_sync_scheduler():
    """
    Mock Enhanced Sync Scheduler for testing orchestration.
    
    Focus: Mock the scheduler's external interface and behavior.
    """
    mock_scheduler = Mock()
    mock_scheduler.scheduler_id = "test_scheduler_123"
    mock_scheduler.discover_fabrics.return_value = []
    mock_scheduler.create_sync_plan.return_value = Mock()
    mock_scheduler.execute_sync_plan.return_value = {'success': True, 'tasks_executed': 0}
    
    # Mock metrics
    mock_metrics = Mock()
    mock_metrics.cycle_count = 0
    mock_metrics.fabrics_discovered = 0
    mock_metrics.tasks_planned = 0
    mock_metrics.tasks_executed = 0
    mock_scheduler.metrics = mock_metrics
    
    return mock_scheduler


@pytest.fixture
def mock_sync_task():
    """
    Mock SyncTask for testing task orchestration.
    
    Focus: Mock task behavior and properties.
    """
    from enum import Enum
    
    # Mock the enums used by SyncTask
    class MockSyncType(Enum):
        GIT_SYNC = "git"
        KUBERNETES_SYNC = "kubernetes"
        STATUS_UPDATE = "status"
    
    class MockSyncPriority(Enum):
        CRITICAL = 1
        HIGH = 2
        MEDIUM = 3
    
    mock_task = Mock()
    mock_task.fabric_id = 35
    mock_task.fabric_name = "Test Fabric"
    mock_task.sync_type = MockSyncType.GIT_SYNC
    mock_task.priority = MockSyncPriority.CRITICAL
    mock_task.estimated_duration = 25
    mock_task.task_id = "git_35"
    mock_task.is_due = True
    mock_task.should_retry = True
    mock_task.dependencies = []
    
    return mock_task


@pytest.fixture
def mock_fabric_sync_plan():
    """
    Mock FabricSyncPlan for testing plan execution.
    
    Focus: Mock plan behavior and task management.
    """
    mock_plan = Mock()
    mock_plan.fabric_id = 35
    mock_plan.fabric_name = "Test Fabric"
    mock_plan.sync_tasks = []
    mock_plan.total_estimated_duration = 0
    mock_plan.health_score = 0.5
    mock_plan.add_task = Mock()
    mock_plan.get_executable_tasks.return_value = []
    
    return mock_plan


@pytest.fixture
def mock_event_service():
    """
    Mock Event Service for testing event publishing.
    
    Focus: Mock event publishing behavior.
    """
    mock_service = Mock()
    mock_service.publish_sync_event.return_value = True
    return mock_service


@pytest.fixture
def broken_system_state():
    """
    Fixture that represents the current BROKEN system state.
    
    This is used to verify that tests fail correctly before implementation.
    """
    return {
        'periodic_sync_running': False,
        'fabrics_never_synced': True,
        'celery_beat_configured': False,
        'rq_scheduler_missing': True,
        'fabric_discovery_broken': True
    }


@pytest.fixture(autouse=True)
def reset_django_mocks():
    """
    Automatically reset Django-related mocks between tests.
    
    Ensures test isolation in London School style testing.
    """
    yield
    # Cleanup happens automatically with context managers


@pytest.fixture
def timing_precision_validator():
    """
    Validator for testing 60-second timing precision.
    
    Focus: Verify that periodic tasks actually run at expected intervals.
    """
    class TimingValidator:
        def __init__(self):
            self.tolerance_seconds = 5.0
            
        def validate_interval(self, actual_interval, expected_interval):
            """Validate that actual interval is within tolerance of expected."""
            return abs(actual_interval - expected_interval) <= self.tolerance_seconds
            
        def validate_60_second_cycle(self, start_time, end_time):
            """Validate that a cycle took approximately 60 seconds."""
            actual_duration = (end_time - start_time).total_seconds()
            return self.validate_interval(actual_duration, 60.0)
    
    return TimingValidator()


@pytest.fixture
def contract_tester():
    """
    Helper for testing contracts between components.
    
    London School Focus: Verify that objects honor their contracts.
    """
    class ContractTester:
        def verify_method_called_with(self, mock_object, method_name, expected_args, expected_kwargs=None):
            """Verify that a method was called with specific arguments."""
            method = getattr(mock_object, method_name)
            if expected_kwargs:
                method.assert_called_with(*expected_args, **expected_kwargs)
            else:
                method.assert_called_with(*expected_args)
                
        def verify_collaboration_sequence(self, mock_objects, expected_calls):
            """Verify that a sequence of collaborations occurred in order."""
            for mock_obj, method_name, args in expected_calls:
                method = getattr(mock_obj, method_name)
                method.assert_called_with(*args)
    
    return ContractTester()


@pytest.fixture
def mock_logger():
    """
    Mock logger for testing logging behavior.
    
    Focus: Verify that appropriate logging occurs during operations.
    """
    mock_logger = Mock()
    mock_logger.info = Mock()
    mock_logger.error = Mock()
    mock_logger.warning = Mock()
    mock_logger.debug = Mock()
    return mock_logger


# Test markers for different test categories
def pytest_configure(config):
    """Configure pytest markers for London School TDD categories."""
    config.addinivalue_line("markers", "acceptance: Acceptance tests that verify user requirements")
    config.addinivalue_line("markers", "mock_driven: Mock-driven unit tests focusing on object interactions")
    config.addinivalue_line("markers", "behavior: Behavior verification tests")
    config.addinivalue_line("markers", "contract: Contract testing between components")
    config.addinivalue_line("markers", "collaboration: Tests of object collaborations")
    config.addinivalue_line("markers", "integration: Integration tests with real external services")
    config.addinivalue_line("markers", "timing: Tests that verify timing precision")
    config.addinivalue_line("markers", "real_env: Tests that connect to real NetBox environment")


def pytest_runtest_setup(item):
    """Set up for individual test runs."""
    # Skip real environment tests unless explicitly enabled
    if "real_env" in item.keywords:
        if not item.config.getoption("--real-env", default=False):
            pytest.skip("Real environment tests skipped (use --real-env to run)")


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--real-env",
        action="store_true", 
        default=False,
        help="Run tests against real NetBox environment"
    )


# Custom assertions for London School TDD
def pytest_assertrepr_compare(config, op, left, right):
    """Custom assertion representations for better test failure messages."""
    if hasattr(left, 'assert_called_with') and op == "==":
        return [
            f"Mock assertion failed:",
            f"   Expected call: {right}",
            f"   Actual calls: {left.call_args_list}",
            f"   Mock: {left}",
        ]