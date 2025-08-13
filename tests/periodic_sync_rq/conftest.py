"""
Test Configuration for RQ-based Periodic Sync Tests

This configuration file sets up the testing environment for
RQ-based periodic sync functionality tests.

CRITICAL: All test configurations here MUST FAIL initially because
the RQ-based periodic sync system doesn't exist yet.
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import override_settings
from django.utils import timezone
from django.db import transaction
import django_rq
from rq import Queue, Worker
from rq.job import Job
import redis
import time

from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.choices import FabricStatusChoices, SyncStatusChoices, ConnectionStatusChoices


# Test RQ Configuration - This WILL FAIL because the queues don't exist
TEST_RQ_QUEUES = {
    'default': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 15,  # Use separate DB for tests
        'PASSWORD': '',
        'DEFAULT_TIMEOUT': 360,
        'CONNECTION_KWARGS': {
            'decode_responses': True,
        },
    },
    # Hedgehog-specific test queues
    'hedgehog_sync': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 15,
        'PASSWORD': '',
        'DEFAULT_TIMEOUT': 360,
        'CONNECTION_KWARGS': {
            'decode_responses': True,
        },
    },
    'hedgehog_git': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 15,
        'PASSWORD': '',
        'DEFAULT_TIMEOUT': 360,
        'CONNECTION_KWARGS': {
            'decode_responses': True,
        },
    },
    'hedgehog_fabric': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 15,
        'PASSWORD': '',
        'DEFAULT_TIMEOUT': 360,
        'CONNECTION_KWARGS': {
            'decode_responses': True,
        },
    },
}


@pytest.fixture(scope='session')
def rq_test_settings():
    """
    Test settings for RQ-based periodic sync tests.
    
    WILL FAIL: These settings reference non-existent RQ configurations.
    """
    return override_settings(
        RQ_QUEUES=TEST_RQ_QUEUES,
        # Hedgehog RQ-specific settings (don't exist yet)
        HEDGEHOG_RQ_ENABLED=True,
        HEDGEHOG_SYNC_QUEUE='hedgehog_sync',
        HEDGEHOG_GIT_QUEUE='hedgehog_git',
        HEDGEHOG_FABRIC_QUEUE='hedgehog_fabric',
        # Test-specific settings
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        # Disable real Kubernetes connections in tests
        HEDGEHOG_K8S_TEST_MODE=True,
        # Fast test intervals
        HEDGEHOG_MIN_SYNC_INTERVAL=5,  # 5 seconds for tests
        HEDGEHOG_MAX_SYNC_INTERVAL=300,  # 5 minutes for tests
    )


@pytest.fixture
def test_fabric():
    """
    Create test fabric for RQ periodic sync tests.
    
    This fixture provides a standard fabric configuration that
    matches the user's reported setup (60-second interval).
    """
    fabric = HedgehogFabric.objects.create(
        name="test-rq-fabric",
        kubernetes_server="https://test-rq-k8s.example.com:6443",
        kubernetes_token="test-rq-token",
        kubernetes_ca_cert="test-ca-cert",
        kubernetes_namespace="default",
        sync_enabled=True,
        sync_interval=60,  # User's reported configuration
        status=FabricStatusChoices.ACTIVE,
        sync_status=SyncStatusChoices.NEVER_SYNCED,
        connection_status=ConnectionStatusChoices.UNKNOWN
    )
    
    yield fabric
    
    # Cleanup
    fabric.delete()


@pytest.fixture
def test_fabric_fast_sync():
    """
    Create test fabric with fast sync interval for quick testing.
    
    Uses 5-second interval for tests that need quick cycles.
    """
    fabric = HedgehogFabric.objects.create(
        name="test-fast-sync-fabric",
        kubernetes_server="https://test-fast-k8s.example.com:6443",
        kubernetes_token="test-fast-token",
        sync_enabled=True,
        sync_interval=5,  # Fast interval for testing
        status=FabricStatusChoices.ACTIVE,
        sync_status=SyncStatusChoices.NEVER_SYNCED
    )
    
    yield fabric
    fabric.delete()


@pytest.fixture
def test_fabric_disabled_sync():
    """
    Create test fabric with sync disabled.
    
    For testing that disabled fabrics are not scheduled.
    """
    fabric = HedgehogFabric.objects.create(
        name="test-disabled-sync-fabric",
        kubernetes_server="https://test-disabled-k8s.example.com:6443",
        sync_enabled=False,  # Explicitly disabled
        sync_interval=60,
        status=FabricStatusChoices.ACTIVE,
        sync_status=SyncStatusChoices.NEVER_SYNCED
    )
    
    yield fabric
    fabric.delete()


@pytest.fixture
def clean_rq_queues():
    """
    Clean RQ queues before and after tests.
    
    WILL FAIL: Queue cleaning functions don't exist yet.
    """
    from netbox_hedgehog.rq_tasks.queue_manager import clear_all_hedgehog_queues
    
    # This import will FAIL - queue_manager doesn't exist
    # Clean queues before test
    clear_all_hedgehog_queues()
    
    yield
    
    # Clean queues after test
    clear_all_hedgehog_queues()


@pytest.fixture
def mock_kubernetes_api():
    """
    Mock Kubernetes API for testing sync operations.
    
    Provides predictable responses for testing sync logic.
    """
    mock_api = MagicMock()
    
    # Mock successful CRD fetch
    mock_api.fetch_crds_from_kubernetes.return_value = {
        'success': True,
        'resources': {
            'VPC': [
                {
                    'metadata': {'name': 'test-vpc', 'namespace': 'default'},
                    'spec': {'subnet': '10.0.0.0/16'},
                    'status': {'phase': 'Active'}
                }
            ],
            'Connection': [
                {
                    'metadata': {'name': 'test-connection', 'namespace': 'default'},
                    'spec': {'type': 'external'},
                    'status': {'phase': 'Connected'}
                }
            ]
        },
        'errors': []
    }
    
    # Mock connection test
    mock_api.test_connection.return_value = {
        'success': True,
        'message': 'Connection successful'
    }
    
    with patch('netbox_hedgehog.utils.kubernetes.KubernetesSync', return_value=mock_api):
        yield mock_api


@pytest.fixture
def mock_git_operations():
    """
    Mock Git operations for testing GitOps sync.
    
    Provides predictable Git responses for sync testing.
    """
    mock_git = MagicMock()
    
    # Mock successful Git clone/pull
    mock_git.clone_repository.return_value = {
        'success': True,
        'commit_sha': 'abc123def456',
        'branch': 'main',
        'files_found': ['fabric1.yaml', 'fabric2.yaml']
    }
    
    # Mock YAML file parsing
    mock_git.parse_yaml_files.return_value = {
        'success': True,
        'resources': [
            {
                'kind': 'VPC',
                'metadata': {'name': 'git-vpc'},
                'spec': {'subnet': '192.168.0.0/16'}
            }
        ]
    }
    
    with patch('netbox_hedgehog.utils.git_sync.GitOperations', return_value=mock_git):
        yield mock_git


@pytest.fixture
def rq_scheduler_mock():
    """
    Mock RQ Scheduler for testing periodic job scheduling.
    
    WILL FAIL: RQ Scheduler integration doesn't exist yet.
    """
    from netbox_hedgehog.rq_scheduler import HedgehogRQScheduler
    
    # This import will FAIL - RQ scheduler doesn't exist
    with patch('netbox_hedgehog.rq_scheduler.HedgehogRQScheduler') as mock_scheduler:
        scheduler_instance = Mock()
        
        # Mock scheduling methods
        scheduler_instance.schedule_periodic_fabric_sync.return_value = Mock(
            id='test-job-id',
            scheduled_for=timezone.now() + timedelta(seconds=60),
            func_name='netbox_hedgehog.rq_tasks.fabric_sync_task'
        )
        
        scheduler_instance.cancel_fabric_sync.return_value = True
        
        scheduler_instance.get_fabric_jobs.return_value = []
        
        mock_scheduler.return_value = scheduler_instance
        
        yield scheduler_instance


@pytest.fixture
def timing_validator():
    """
    Utility for validating sync timing in tests.
    
    Provides helpers for checking execution timing precision.
    """
    class TimingValidator:
        def __init__(self):
            self.execution_times = []
            self.start_time = None
        
        def start_timing(self):
            """Start timing measurement."""
            self.start_time = timezone.now()
            self.execution_times = []
        
        def record_execution(self, fabric):
            """Record a sync execution time."""
            if fabric.last_sync:
                elapsed = (fabric.last_sync - self.start_time).total_seconds()
                self.execution_times.append((fabric.last_sync, elapsed))
        
        def validate_interval_precision(self, expected_interval, tolerance=5):
            """Validate that executions occurred at expected intervals."""
            if len(self.execution_times) < 2:
                return False, "Need at least 2 executions to validate intervals"
            
            for i in range(1, len(self.execution_times)):
                actual_interval = self.execution_times[i][1] - self.execution_times[i-1][1]
                diff = abs(actual_interval - expected_interval)
                
                if diff > tolerance:
                    return False, f"Interval {i} off by {diff}s (expected {expected_interval}s ± {tolerance}s)"
            
            return True, "All intervals within tolerance"
        
        def validate_first_execution_timing(self, expected_delay, tolerance=5):
            """Validate that first execution occurred at expected time."""
            if not self.execution_times:
                return False, "No executions recorded"
            
            first_execution_delay = self.execution_times[0][1]
            diff = abs(first_execution_delay - expected_delay)
            
            if diff > tolerance:
                return False, f"First execution off by {diff}s (expected {expected_delay}s ± {tolerance}s)"
            
            return True, f"First execution timing within tolerance: {first_execution_delay}s"
        
        def get_execution_summary(self):
            """Get summary of recorded execution times."""
            if not self.execution_times:
                return "No executions recorded"
            
            intervals = []
            if len(self.execution_times) > 1:
                for i in range(1, len(self.execution_times)):
                    interval = self.execution_times[i][1] - self.execution_times[i-1][1]
                    intervals.append(interval)
            
            return {
                'total_executions': len(self.execution_times),
                'first_execution_at': self.execution_times[0][1] if self.execution_times else None,
                'intervals': intervals,
                'average_interval': sum(intervals) / len(intervals) if intervals else None,
                'timing_start': self.start_time
            }
    
    return TimingValidator()


@pytest.fixture
def rq_test_worker():
    """
    Create RQ worker for testing job execution.
    
    WILL FAIL: Worker configuration for Hedgehog tasks doesn't exist.
    """
    from netbox_hedgehog.rq_tasks.worker_config import create_hedgehog_test_worker
    
    # This import will FAIL - worker config doesn't exist
    worker = create_hedgehog_test_worker(
        queues=['hedgehog_sync', 'hedgehog_git', 'hedgehog_fabric'],
        test_mode=True
    )
    
    yield worker
    
    # Cleanup worker
    worker.stop()


@pytest.fixture
def sync_execution_monitor():
    """
    Monitor for tracking sync execution in tests.
    
    Provides utilities for monitoring fabric sync state changes.
    """
    class SyncExecutionMonitor:
        def __init__(self):
            self.state_changes = []
            self.monitoring = False
        
        def start_monitoring(self, fabric):
            """Start monitoring fabric sync state changes."""
            self.fabric = fabric
            self.monitoring = True
            self.state_changes = []
            self.initial_state = {
                'sync_status': fabric.sync_status,
                'last_sync': fabric.last_sync,
                'connection_status': fabric.connection_status,
                'recorded_at': timezone.now()
            }
        
        def check_for_changes(self):
            """Check for state changes and record them."""
            if not self.monitoring:
                return
            
            self.fabric.refresh_from_db()
            current_state = {
                'sync_status': self.fabric.sync_status,
                'last_sync': self.fabric.last_sync,
                'connection_status': self.fabric.connection_status,
                'recorded_at': timezone.now()
            }
            
            # Check if state changed from last recorded state
            last_state = self.state_changes[-1] if self.state_changes else self.initial_state
            
            if (current_state['sync_status'] != last_state['sync_status'] or
                current_state['last_sync'] != last_state['last_sync'] or
                current_state['connection_status'] != last_state['connection_status']):
                
                self.state_changes.append(current_state)
        
        def wait_for_state_change(self, max_wait_seconds=60, check_interval=1):
            """Wait for sync state to change."""
            start_time = time.time()
            
            while time.time() - start_time < max_wait_seconds:
                self.check_for_changes()
                if self.state_changes:
                    return True
                time.sleep(check_interval)
            
            return False
        
        def wait_for_sync_completion(self, max_wait_seconds=120):
            """Wait for sync to complete (reach non-syncing state)."""
            start_time = time.time()
            
            while time.time() - start_time < max_wait_seconds:
                self.check_for_changes()
                self.fabric.refresh_from_db()
                
                if self.fabric.sync_status != SyncStatusChoices.SYNCING:
                    return True
                
                time.sleep(1)
            
            return False
        
        def get_state_transition_summary(self):
            """Get summary of state transitions observed."""
            if not self.state_changes:
                return {
                    'transitions': 0,
                    'initial_state': self.initial_state,
                    'final_state': self.initial_state,
                    'transition_sequence': []
                }
            
            return {
                'transitions': len(self.state_changes),
                'initial_state': self.initial_state,
                'final_state': self.state_changes[-1],
                'transition_sequence': [
                    {
                        'from': self.initial_state if i == 0 else self.state_changes[i-1],
                        'to': change,
                        'duration': (change['recorded_at'] - 
                                   (self.initial_state['recorded_at'] if i == 0 
                                    else self.state_changes[i-1]['recorded_at'])).total_seconds()
                    }
                    for i, change in enumerate(self.state_changes)
                ]
            }
    
    return SyncExecutionMonitor()


# Test markers for different test categories
pytest.mark.rq_integration = pytest.mark.rq_integration
pytest.mark.timing_precision = pytest.mark.timing_precision
pytest.mark.state_transitions = pytest.mark.state_transitions
pytest.mark.error_handling = pytest.mark.error_handling
pytest.mark.netbox_integration = pytest.mark.netbox_integration


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "rq_integration: RQ integration tests")
    config.addinivalue_line("markers", "timing_precision: Timing precision tests")
    config.addinivalue_line("markers", "state_transitions: State transition tests")
    config.addinivalue_line("markers", "error_handling: Error handling tests")
    config.addinivalue_line("markers", "netbox_integration: NetBox integration tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")
    config.addinivalue_line("markers", "requires_redis: Tests requiring Redis connection")