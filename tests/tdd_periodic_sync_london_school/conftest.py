"""
Test configuration and fixtures for London School TDD periodic sync tests.

These fixtures provide comprehensive mocking infrastructure for isolating
units under test and verifying interactions between collaborating objects.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from django.utils import timezone
from freezegun import freeze_time


@pytest.fixture
def mock_django_rq():
    """Mock django_rq module with all scheduler functionality."""
    with patch('netbox_hedgehog.jobs.fabric_sync.django_rq') as mock_rq:
        # Mock scheduler
        mock_scheduler = Mock()
        mock_scheduler.schedule = Mock()
        mock_scheduler.cancel = Mock()
        mock_scheduler.get_jobs = Mock(return_value=[])
        
        # Mock queue
        mock_queue = Mock()
        mock_queue.enqueue = Mock()
        mock_queue.enqueue_in = Mock()
        
        # Configure django_rq mocks
        mock_rq.get_scheduler.return_value = mock_scheduler
        mock_rq.get_queue.return_value = mock_queue
        
        yield {
            'django_rq': mock_rq,
            'scheduler': mock_scheduler,
            'queue': mock_queue
        }


@pytest.fixture
def mock_rq_scheduler_available():
    """Mock RQ_SCHEDULER_AVAILABLE flag to True."""
    with patch('netbox_hedgehog.jobs.fabric_sync.RQ_SCHEDULER_AVAILABLE', True):
        yield True


@pytest.fixture
def mock_rq_scheduler_unavailable():
    """Mock RQ_SCHEDULER_AVAILABLE flag to False (testing broken scenario)."""
    with patch('netbox_hedgehog.jobs.fabric_sync.RQ_SCHEDULER_AVAILABLE', False):
        yield False


@pytest.fixture
def mock_hedgehog_fabric():
    """Mock HedgehogFabric model with all necessary methods."""
    with patch('netbox_hedgehog.jobs.fabric_sync.HedgehogFabric') as mock_model:
        # Create mock fabric instance
        mock_fabric = Mock()
        mock_fabric.id = 1
        mock_fabric.name = 'test-fabric'
        mock_fabric.sync_enabled = True
        mock_fabric.sync_interval = 60
        mock_fabric.last_sync = None
        mock_fabric.sync_status = 'never_synced'
        mock_fabric.sync_error = ''
        mock_fabric.kubernetes_server = 'https://test-cluster'
        mock_fabric.git_repository_url = 'https://test-git'
        mock_fabric.cached_crd_count = 0
        mock_fabric.vpcs_count = 5
        mock_fabric.connections_count = 3
        mock_fabric.scheduler_enabled = True
        
        # Mock methods
        mock_fabric.needs_sync.return_value = True
        mock_fabric.refresh_from_db = Mock()
        mock_fabric.save = Mock()
        
        # Configure model manager
        mock_model.objects.get.return_value = mock_fabric
        mock_model.objects.select_for_update.return_value.get.return_value = mock_fabric
        mock_model.objects.filter.return_value = [mock_fabric]
        mock_model.DoesNotExist = Exception
        
        yield {
            'model': mock_model,
            'instance': mock_fabric
        }


@pytest.fixture
def mock_transaction():
    """Mock Django transaction.atomic context manager."""
    with patch('netbox_hedgehog.jobs.fabric_sync.transaction') as mock_tx:
        # Create a mock context manager
        mock_atomic = MagicMock()
        mock_atomic.__enter__ = Mock(return_value=mock_atomic)
        mock_atomic.__exit__ = Mock(return_value=None)
        mock_tx.atomic.return_value = mock_atomic
        
        yield mock_tx


@pytest.fixture
def mock_current_time():
    """Provide controlled time for testing timing behavior."""
    fixed_time = datetime(2025, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
    with freeze_time(fixed_time) as frozen_time:
        yield frozen_time


@pytest.fixture
def mock_rq_job():
    """Mock RQ job context for testing job execution."""
    with patch('netbox_hedgehog.jobs.fabric_sync.get_current_job') as mock_get_job:
        mock_job = Mock()
        mock_job.id = 'test-job-123'
        mock_get_job.return_value = mock_job
        
        yield mock_job


@pytest.fixture
def mock_logger():
    """Mock logger to verify logging behavior."""
    with patch('netbox_hedgehog.jobs.fabric_sync.logger') as mock_log:
        yield mock_log


@pytest.fixture
def mock_sync_choices():
    """Mock sync status choices."""
    with patch('netbox_hedgehog.jobs.fabric_sync.SyncStatusChoices') as mock_choices:
        mock_choices.SYNCING = 'syncing'
        mock_choices.SYNCED = 'synced'
        mock_choices.ERROR = 'error'
        mock_choices.NEVER_SYNCED = 'never_synced'
        
        yield mock_choices


@pytest.fixture
def timer_precision_clock():
    """High-precision timer for testing exact timing behavior."""
    class TimerClock:
        def __init__(self):
            self.current_time = datetime(2025, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
            self.calls = []
            
        def advance_seconds(self, seconds):
            """Advance clock by exact number of seconds."""
            self.current_time += timedelta(seconds=seconds)
            
        def now(self):
            """Return current time and record the call."""
            self.calls.append(self.current_time)
            return self.current_time
            
        def get_call_timestamps(self):
            """Return all timestamp calls for verification."""
            return self.calls.copy()
    
    return TimerClock()


@pytest.fixture
def fabric_sync_contract_mocks():
    """
    Comprehensive mock setup for testing FabricSyncJob contracts.
    
    This fixture establishes the complete mock environment needed to test
    the interactions between FabricSyncJob and its collaborators.
    """
    mocks = {}
    
    # Mock all external dependencies
    with patch('netbox_hedgehog.jobs.fabric_sync.django_rq') as mock_rq, \
         patch('netbox_hedgehog.jobs.fabric_sync.HedgehogFabric') as mock_fabric_model, \
         patch('netbox_hedgehog.jobs.fabric_sync.transaction') as mock_tx, \
         patch('netbox_hedgehog.jobs.fabric_sync.timezone') as mock_tz, \
         patch('netbox_hedgehog.jobs.fabric_sync.logger') as mock_log, \
         patch('netbox_hedgehog.jobs.fabric_sync.get_current_job') as mock_job:
        
        # Configure timezone mock
        fixed_time = datetime(2025, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
        mock_tz.now.return_value = fixed_time
        
        # Configure fabric model mock
        mock_fabric = Mock()
        mock_fabric.id = 1
        mock_fabric.name = 'test-fabric'
        mock_fabric.sync_enabled = True
        mock_fabric.sync_interval = 60
        mock_fabric.last_sync = None
        mock_fabric.needs_sync.return_value = True
        mock_fabric.save = Mock()
        mock_fabric.refresh_from_db = Mock()
        
        mock_fabric_model.objects.select_for_update.return_value.get.return_value = mock_fabric
        mock_fabric_model.objects.get.return_value = mock_fabric
        
        # Configure transaction mock
        mock_atomic = MagicMock()
        mock_tx.atomic.return_value = mock_atomic
        
        # Configure RQ mocks
        mock_scheduler = Mock()
        mock_rq.get_scheduler.return_value = mock_scheduler
        
        # Configure job mock
        mock_current_job = Mock()
        mock_current_job.id = 'job-123'
        mock_job.return_value = mock_current_job
        
        mocks.update({
            'django_rq': mock_rq,
            'scheduler': mock_scheduler,
            'fabric_model': mock_fabric_model,
            'fabric': mock_fabric,
            'transaction': mock_tx,
            'timezone': mock_tz,
            'logger': mock_log,
            'job': mock_current_job
        })
        
        yield mocks