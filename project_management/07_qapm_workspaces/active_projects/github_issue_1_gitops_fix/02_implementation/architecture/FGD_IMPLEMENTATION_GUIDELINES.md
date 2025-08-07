# FGD Sync Implementation Guidelines

**Document Version**: 1.0  
**Created**: 2025-08-02  
**Author**: FGD System Architecture Analyst (Agent ID: fgd_architecture_analyst_001)  
**Purpose**: Comprehensive implementation guidelines for the FGD Synchronization System

## Overview

This document provides detailed implementation guidelines, coding standards, patterns, and best practices for developing the FGD Synchronization System. These guidelines ensure consistent, maintainable, and production-ready code across all modules.

## Development Standards

### Code Organization

```python
# Directory Structure for FGD Module
netbox_hedgehog/
├── fgd_sync/                          # Main FGD package
│   ├── __init__.py
│   ├── apps.py                        # Django app configuration
│   ├── exceptions.py                  # Custom exceptions
│   ├── config.py                      # Configuration management
│   │
│   ├── core/                          # Core framework
│   │   ├── __init__.py
│   │   ├── base.py                    # Base classes
│   │   ├── utils.py                   # Common utilities
│   │   └── constants.py               # System constants
│   │
│   ├── orchestration/                 # Orchestration layer
│   │   ├── __init__.py
│   │   ├── orchestrator.py            # Main orchestrator
│   │   ├── workflow.py                # Workflow management
│   │   └── stages.py                  # Workflow stages
│   │
│   ├── events/                        # Event system
│   │   ├── __init__.py
│   │   ├── bus.py                     # Event bus implementation
│   │   ├── handlers.py                # Event handlers
│   │   └── schemas.py                 # Event schemas
│   │
│   ├── state/                         # State management
│   │   ├── __init__.py
│   │   ├── manager.py                 # State manager
│   │   ├── locks.py                   # Lock management
│   │   └── models.py                  # State models
│   │
│   ├── directory/                     # Directory management
│   │   ├── __init__.py
│   │   ├── manager.py                 # Directory manager
│   │   ├── validator.py               # Structure validator
│   │   └── repair.py                  # Auto-repair logic
│   │
│   ├── ingestion/                     # File ingestion
│   │   ├── __init__.py
│   │   ├── pipeline.py                # Main pipeline
│   │   ├── processors.py              # File processors
│   │   ├── validators.py              # Content validators
│   │   └── normalizers.py             # YAML normalizers
│   │
│   ├── github/                        # GitHub integration
│   │   ├── __init__.py
│   │   ├── client.py                  # GitHub client
│   │   ├── webhooks.py                # Webhook handlers
│   │   └── sync.py                    # GitHub sync logic
│   │
│   ├── monitoring/                    # Monitoring & health
│   │   ├── __init__.py
│   │   ├── health.py                  # Health checks
│   │   ├── metrics.py                 # Metrics collection
│   │   └── alerts.py                  # Alert handling
│   │
│   ├── recovery/                      # Error recovery
│   │   ├── __init__.py
│   │   ├── handlers.py                # Error handlers
│   │   ├── retry.py                   # Retry logic
│   │   └── circuit_breaker.py         # Circuit breaker
│   │
│   ├── integration/                   # HNP integration
│   │   ├── __init__.py
│   │   ├── bridge.py                  # HNP bridge
│   │   ├── signals.py                 # Django signals
│   │   └── tasks.py                   # Celery tasks
│   │
│   ├── api/                          # REST API
│   │   ├── __init__.py
│   │   ├── views.py                   # API views
│   │   ├── serializers.py             # DRF serializers
│   │   └── urls.py                    # URL patterns
│   │
│   ├── management/                    # Management commands
│   │   └── commands/
│   │       ├── fgd_init.py           # Initialize FGD system
│   │       ├── fgd_sync.py           # Manual sync command
│   │       └── fgd_health.py         # Health check command
│   │
│   ├── tests/                        # Test package
│   │   ├── __init__.py
│   │   ├── conftest.py               # pytest configuration
│   │   ├── factories.py              # Test factories
│   │   ├── fixtures/                 # Test fixtures
│   │   ├── unit/                     # Unit tests
│   │   ├── integration/              # Integration tests
│   │   └── performance/              # Performance tests
│   │
│   └── migrations/                   # Database migrations
       ├── __init__.py
       └── 0001_initial.py
```

### Coding Standards

#### Python Code Style

```python
# Follow PEP 8 with these specific guidelines:

# 1. Import Organization
from __future__ import annotations  # Enable forward references

# Standard library imports
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union

# Third-party imports
import yaml
from django.db import models
from django.utils import timezone

# Local imports
from netbox_hedgehog.fgd_sync.core.base import BaseFGDComponent
from netbox_hedgehog.fgd_sync.exceptions import FGDSyncError

# 2. Class Definition Standards
class SyncOrchestrator(BaseFGDComponent):
    """
    Central orchestration engine for FGD synchronization.
    
    This class coordinates all sync operations across components,
    implementing the State Machine pattern for workflow management.
    
    Attributes:
        fabric: The HedgehogFabric instance being synchronized
        state_manager: Manages sync state transitions
        event_bus: Handles event publishing and subscription
        
    Example:
        orchestrator = SyncOrchestrator(fabric)
        sync_id = await orchestrator.start_sync(
            fabric_id=123,
            trigger='manual'
        )
    """
    
    def __init__(self, fabric: HedgehogFabric) -> None:
        """Initialize orchestrator with fabric instance."""
        super().__init__()
        self.fabric = fabric
        self.state_manager = StateManager(fabric)
        self.event_bus = EventBus()
        self._setup_logging()
    
    async def start_sync(
        self, 
        fabric_id: int, 
        trigger: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start sync operation for fabric.
        
        Args:
            fabric_id: ID of the fabric to sync
            trigger: Trigger type ('manual', 'webhook', etc.)
            options: Optional sync configuration
            
        Returns:
            Unique sync operation ID
            
        Raises:
            FGDSyncError: If sync cannot be started
            FGDValidationError: If parameters are invalid
        """
        options = options or {}
        
        # Validate parameters
        self._validate_sync_parameters(fabric_id, trigger, options)
        
        # Check if sync already in progress
        if await self._is_sync_in_progress(fabric_id):
            raise FGDSyncError(
                f"Sync already in progress for fabric {fabric_id}",
                error_code="FGD_3001"
            )
        
        # Generate correlation ID for tracking
        correlation_id = self.generate_correlation_id()
        
        # Create sync context
        sync_context = SyncContext(
            sync_id=str(uuid.uuid4()),
            fabric_id=fabric_id,
            trigger=trigger,
            options=options,
            correlation_id=correlation_id
        )
        
        # Start async workflow
        asyncio.create_task(self._execute_sync_workflow(sync_context))
        
        return sync_context.sync_id

# 3. Error Handling Patterns
class FGDExceptionHandler:
    """Centralized exception handling with recovery strategies."""
    
    @staticmethod
    def handle_with_recovery(func):
        """Decorator for automatic error handling and recovery."""
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except FGDTransientError as e:
                # Retry transient errors
                logger.warning(f"Transient error: {e}, retrying...")
                return await FGDExceptionHandler._retry_with_backoff(
                    func, args, kwargs
                )
            except FGDValidationError as e:
                # Log validation errors and re-raise
                logger.error(f"Validation error: {e}")
                raise
            except Exception as e:
                # Convert unexpected errors to FGD errors
                logger.exception(f"Unexpected error in {func.__name__}: {e}")
                raise FGDInternalError(
                    f"Internal error: {str(e)}",
                    original_error=e
                )
        return wrapper

# 4. Async/Await Patterns
class AsyncPatterns:
    """Examples of proper async/await usage in FGD system."""
    
    async def process_files_concurrently(
        self, 
        files: List[Path]
    ) -> List[FileResult]:
        """Process multiple files concurrently with controlled parallelism."""
        semaphore = asyncio.Semaphore(4)  # Limit concurrent operations
        
        async def process_with_semaphore(file_path: Path) -> FileResult:
            async with semaphore:
                return await self.process_single_file(file_path)
        
        # Create tasks for concurrent execution
        tasks = [
            process_with_semaphore(file_path) 
            for file_path in files
        ]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in results
        file_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                file_results.append(
                    FileResult(
                        file_path=files[i],
                        status='failed',
                        error=str(result)
                    )
                )
            else:
                file_results.append(result)
        
        return file_results
```

#### Type Hints and Documentation

```python
# Comprehensive type hinting example
from typing import (
    Dict, List, Optional, Union, Any, Callable, 
    TypeVar, Generic, Protocol, Literal
)

T = TypeVar('T')

class ProcessorProtocol(Protocol):
    """Protocol for file processors."""
    
    async def process(self, content: str) -> Dict[str, Any]:
        """Process file content."""
        ...

class GenericProcessor(Generic[T]):
    """Generic processor for type-safe operations."""
    
    def __init__(self, processor_type: type[T]) -> None:
        self.processor_type = processor_type
    
    async def process_typed(self, item: T) -> ProcessResult[T]:
        """Process item with type safety."""
        ...

# Function with comprehensive type hints
async def process_sync_operation(
    fabric_id: int,
    trigger: Literal['manual', 'webhook', 'scheduled'],
    options: Optional[Dict[str, Union[str, int, bool]]] = None,
    processor: Optional[ProcessorProtocol] = None
) -> Union[SyncResult, SyncError]:
    """
    Process sync operation with full type safety.
    
    Args:
        fabric_id: Unique identifier for the fabric
        trigger: Type of sync trigger
        options: Optional configuration parameters
        processor: Optional custom processor
        
    Returns:
        SyncResult on success, SyncError on failure
        
    Raises:
        ValueError: If fabric_id is invalid
        FGDSyncError: If sync operation fails
    """
    pass
```

### Testing Requirements

#### Unit Testing Standards

```python
# test_sync_orchestrator.py
import pytest
from unittest.mock import AsyncMock, Mock, patch
from netbox_hedgehog.fgd_sync.orchestration.orchestrator import SyncOrchestrator
from netbox_hedgehog.fgd_sync.exceptions import FGDSyncError

class TestSyncOrchestrator:
    """Test suite for SyncOrchestrator."""
    
    @pytest.fixture
    def mock_fabric(self):
        """Create mock fabric for testing."""
        fabric = Mock()
        fabric.id = 123
        fabric.name = "test-fabric"
        fabric.git_repository = Mock()
        return fabric
    
    @pytest.fixture
    def orchestrator(self, mock_fabric):
        """Create orchestrator instance for testing."""
        with patch('netbox_hedgehog.fgd_sync.orchestration.orchestrator.StateManager'):
            return SyncOrchestrator(mock_fabric)
    
    @pytest.mark.asyncio
    async def test_start_sync_success(self, orchestrator, mock_fabric):
        """Test successful sync initiation."""
        # Arrange
        with patch.object(orchestrator, '_is_sync_in_progress', return_value=False):
            with patch.object(orchestrator, '_execute_sync_workflow') as mock_execute:
                # Act
                sync_id = await orchestrator.start_sync(
                    fabric_id=123,
                    trigger='manual'
                )
                
                # Assert
                assert sync_id is not None
                assert len(sync_id) == 36  # UUID format
                mock_execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_sync_already_in_progress(self, orchestrator):
        """Test sync rejection when already in progress."""
        # Arrange
        with patch.object(orchestrator, '_is_sync_in_progress', return_value=True):
            # Act & Assert
            with pytest.raises(FGDSyncError) as exc_info:
                await orchestrator.start_sync(fabric_id=123, trigger='manual')
            
            assert exc_info.value.error_code == "FGD_3001"
    
    @pytest.mark.parametrize("trigger,expected_valid", [
        ('manual', True),
        ('webhook', True),
        ('scheduled', True),
        ('invalid', False),
    ])
    def test_validate_sync_parameters(
        self, 
        orchestrator, 
        trigger, 
        expected_valid
    ):
        """Test parameter validation with various inputs."""
        if expected_valid:
            orchestrator._validate_sync_parameters(123, trigger, {})
        else:
            with pytest.raises(FGDValidationError):
                orchestrator._validate_sync_parameters(123, trigger, {})
```

#### Integration Testing Patterns

```python
# test_integration_full_sync.py
import pytest
from django.test import TransactionTestCase
from netbox_hedgehog.models import HedgehogFabric
from netbox_hedgehog.fgd_sync.integration.bridge import HNPBridge

class FGDIntegrationTest(TransactionTestCase):
    """Integration test for complete FGD sync workflow."""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self, tmp_path):
        """Setup isolated test environment."""
        # Create test directory structure
        self.test_repo_path = tmp_path / "test-repo"
        self.test_repo_path.mkdir()
        
        # Create sample YAML files
        raw_dir = self.test_repo_path / "gitops" / "raw"
        raw_dir.mkdir(parents=True)
        
        sample_vpc = raw_dir / "test-vpc.yaml"
        sample_vpc.write_text("""
apiVersion: fabric.githedgehog.com/v1alpha2
kind: VPC
metadata:
  name: test-vpc
  namespace: default
spec:
  ipv4Namespace: default
  vlanNamespace: default
        """.strip())
    
    @pytest.mark.asyncio
    async def test_complete_sync_workflow(self):
        """Test complete sync from fabric creation to file ingestion."""
        # Create test fabric with git repository
        fabric = HedgehogFabric.objects.create(
            name="test-fabric",
            asn=65001,
            # Configure git repository...
        )
        
        # Initialize FGD system
        bridge = HNPBridge()
        await bridge.initialize_fabric_fgd(fabric)
        
        # Trigger sync
        orchestrator = SyncOrchestrator(fabric)
        sync_id = await orchestrator.start_sync(
            fabric_id=fabric.id,
            trigger='test'
        )
        
        # Wait for completion
        status = await self.wait_for_sync_completion(sync_id, timeout=30)
        
        # Verify results
        assert status.state == SyncState.COMPLETED
        assert status.files_processed > 0
        assert len(status.errors) == 0
        
        # Verify database records created
        from netbox_hedgehog.models import HedgehogResource
        vpc_resource = HedgehogResource.objects.filter(
            fabric=fabric,
            kind='VPC',
            name='test-vpc'
        ).first()
        
        assert vpc_resource is not None
        assert vpc_resource.desired_spec is not None
```

#### Performance Testing

```python
# test_performance.py
import pytest
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

class TestFGDPerformance:
    """Performance tests for FGD system."""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_sync_performance(self):
        """Test performance with multiple concurrent syncs."""
        num_fabrics = 50
        fabrics = [self.create_test_fabric(i) for i in range(num_fabrics)]
        
        start_time = time.time()
        
        # Start concurrent syncs
        tasks = [
            SyncOrchestrator(fabric).start_sync(
                fabric_id=fabric.id,
                trigger='performance_test'
            )
            for fabric in fabrics
        ]
        
        sync_ids = await asyncio.gather(*tasks)
        
        # Wait for all syncs to complete
        completion_tasks = [
            self.wait_for_sync_completion(sync_id)
            for sync_id in sync_ids
        ]
        
        results = await asyncio.gather(*completion_tasks)
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Performance assertions
        assert total_duration < 60  # Should complete within 1 minute
        assert all(r.state == SyncState.COMPLETED for r in results)
        
        # Log performance metrics
        avg_duration = total_duration / num_fabrics
        print(f"Processed {num_fabrics} syncs in {total_duration:.2f}s")
        print(f"Average sync duration: {avg_duration:.2f}s")
    
    @pytest.mark.performance
    def test_file_processing_throughput(self):
        """Test file processing throughput."""
        # Create large number of test files
        test_files = self.create_test_files(count=1000)
        
        start_time = time.time()
        
        pipeline = FileIngestionPipeline(self.test_fabric)
        results = asyncio.run(pipeline.process_files(test_files))
        
        end_time = time.time()
        
        duration = end_time - start_time
        throughput = len(test_files) / duration
        
        # Performance assertions
        assert throughput > 50  # Files per second
        assert all(r.status == 'success' for r in results)
```

### Integration Patterns

#### Django Integration

```python
# Django app configuration
# apps.py
from django.apps import AppConfig
from django.db.models.signals import post_save, post_delete

class FGDSyncConfig(AppConfig):
    """Django app configuration for FGD sync system."""
    
    name = 'netbox_hedgehog.fgd_sync'
    verbose_name = 'FGD Synchronization'
    
    def ready(self):
        """Initialize FGD system when Django starts."""
        # Import signal handlers
        from . import signals
        
        # Register signal handlers
        from netbox_hedgehog.models import HedgehogFabric
        post_save.connect(
            signals.handle_fabric_created,
            sender=HedgehogFabric
        )
        post_delete.connect(
            signals.handle_fabric_deleted,
            sender=HedgehogFabric
        )
        
        # Initialize FGD services
        from .core.initialization import initialize_fgd_system
        initialize_fgd_system()
        
        # Register health checks
        from .monitoring.health import register_health_checks
        register_health_checks()

# Signal handlers
# signals.py
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from netbox_hedgehog.models import HedgehogFabric
from .integration.tasks import trigger_fgd_initialization

logger = logging.getLogger(__name__)

@receiver(post_save, sender=HedgehogFabric)
def handle_fabric_created(sender, instance, created, **kwargs):
    """Handle fabric creation signal."""
    if created and instance.git_repository:
        logger.info(f"Triggering FGD initialization for fabric {instance.name}")
        
        # Use transaction.on_commit to ensure fabric is saved
        from django.db import transaction
        transaction.on_commit(
            lambda: trigger_fgd_initialization.delay(
                fabric_id=instance.id,
                trigger='fabric_created'
            )
        )

@receiver(post_delete, sender=HedgehogFabric)
def handle_fabric_deleted(sender, instance, **kwargs):
    """Handle fabric deletion signal."""
    logger.info(f"Cleaning up FGD resources for fabric {instance.name}")
    
    from .integration.tasks import cleanup_fgd_resources
    cleanup_fgd_resources.delay(fabric_id=instance.id)
```

#### Celery Integration

```python
# Celery tasks
# tasks.py
from celery import shared_task
from celery.exceptions import Retry
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True
)
def trigger_fgd_initialization(self, fabric_id: int, trigger: str = 'scheduled'):
    """
    Celery task to trigger FGD initialization.
    
    Args:
        fabric_id: ID of the fabric to initialize
        trigger: Trigger type for the operation
    """
    try:
        from netbox_hedgehog.models import HedgehogFabric
        from .orchestration.orchestrator import SyncOrchestrator
        
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        orchestrator = SyncOrchestrator(fabric)
        
        # Run sync in async context
        import asyncio
        sync_id = asyncio.run(
            orchestrator.start_sync(
                fabric_id=fabric_id,
                trigger=trigger
            )
        )
        
        logger.info(f"FGD initialization started for fabric {fabric.name}: {sync_id}")
        
        return {
            'success': True,
            'sync_id': str(sync_id),
            'fabric_id': fabric_id
        }
        
    except Exception as e:
        logger.error(f"FGD initialization failed for fabric {fabric_id}: {e}")
        
        # Don't retry certain errors
        if isinstance(e, (FGDValidationError, FGDConfigurationError)):
            raise
        
        # Retry transient errors
        raise self.retry(exc=e)

@shared_task
def periodic_fgd_health_check():
    """Periodic health check for FGD system."""
    from .monitoring.health import FGDHealthChecker
    
    checker = FGDHealthChecker()
    health_status = asyncio.run(checker.check_system_health())
    
    if not health_status.healthy:
        logger.warning(f"FGD system health check failed: {health_status.issues}")
        
        # Send alerts for critical issues
        from .monitoring.alerts import send_health_alert
        send_health_alert(health_status)
    
    return health_status.to_dict()
```

### Performance Requirements

#### Response Time Targets

```python
# Performance monitoring decorators
import time
import logging
from functools import wraps

def monitor_performance(target_duration: float = None):
    """Decorator to monitor and log performance."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                
                # Log performance
                logger.info(
                    f"{func.__name__} completed in {duration:.3f}s",
                    extra={
                        'function': func.__name__,
                        'duration': duration,
                        'target_duration': target_duration
                    }
                )
                
                # Alert if exceeding target
                if target_duration and duration > target_duration:
                    logger.warning(
                        f"{func.__name__} exceeded target duration: "
                        f"{duration:.3f}s > {target_duration}s"
                    )
                
                # Record metrics
                from .monitoring.metrics import record_performance_metric
                record_performance_metric(func.__name__, duration)
        
        return wrapper
    return decorator

# Usage example
class SyncOrchestrator:
    @monitor_performance(target_duration=30.0)
    async def start_sync(self, fabric_id: int, trigger: str):
        """Start sync with performance monitoring."""
        # Implementation...
```

#### Caching Strategy

```python
# Multi-level caching implementation
from django.core.cache import cache
import redis
import json
from typing import Optional, Callable, Any

class FGDCache:
    """Multi-level cache for FGD operations."""
    
    def __init__(self):
        self.memory_cache = {}  # L1 cache
        self.redis_client = redis.Redis(...)  # L2 cache
        # Django cache as L3 (database cache)
    
    async def get_or_compute(
        self, 
        key: str, 
        compute_func: Callable,
        ttl: int = 300,
        use_memory: bool = True
    ) -> Any:
        """Multi-level cache with compute function."""
        # L1: Memory cache
        if use_memory and key in self.memory_cache:
            return self.memory_cache[key]
        
        # L2: Redis cache
        redis_value = await self.redis_client.get(f"fgd:{key}")
        if redis_value:
            value = json.loads(redis_value)
            if use_memory:
                self.memory_cache[key] = value
            return value
        
        # L3: Django cache
        django_value = cache.get(f"fgd:{key}")
        if django_value:
            # Promote to higher cache levels
            await self._promote_to_redis(key, django_value, ttl)
            if use_memory:
                self.memory_cache[key] = django_value
            return django_value
        
        # Compute and cache
        value = await compute_func()
        await self._cache_at_all_levels(key, value, ttl, use_memory)
        return value
    
    async def _cache_at_all_levels(
        self, 
        key: str, 
        value: Any, 
        ttl: int,
        use_memory: bool
    ):
        """Cache value at all levels."""
        # L1: Memory cache
        if use_memory:
            self.memory_cache[key] = value
        
        # L2: Redis cache
        await self.redis_client.setex(
            f"fgd:{key}",
            ttl,
            json.dumps(value)
        )
        
        # L3: Django cache
        cache.set(f"fgd:{key}", value, ttl)
```

### Security Guidelines

#### Input Validation

```python
# Comprehensive input validation
from pydantic import BaseModel, validator, Field
from typing import List, Optional

class SyncRequestModel(BaseModel):
    """Validated sync request model."""
    
    fabric_id: int = Field(..., gt=0, description="Fabric ID must be positive")
    trigger: str = Field(..., regex=r'^(manual|webhook|scheduled)$')
    options: Optional[dict] = Field(default_factory=dict)
    force_refresh: bool = Field(default=False)
    
    @validator('options')
    def validate_options(cls, v):
        """Validate options dictionary."""
        if not isinstance(v, dict):
            raise ValueError("Options must be a dictionary")
        
        # Validate allowed option keys
        allowed_keys = {
            'force_refresh', 'validate_only', 'include_github_sync',
            'batch_size', 'timeout_seconds'
        }
        
        invalid_keys = set(v.keys()) - allowed_keys
        if invalid_keys:
            raise ValueError(f"Invalid options: {invalid_keys}")
        
        return v
    
    @validator('fabric_id')
    def fabric_must_exist(cls, v):
        """Validate fabric exists."""
        from netbox_hedgehog.models import HedgehogFabric
        
        try:
            HedgehogFabric.objects.get(id=v)
        except HedgehogFabric.DoesNotExist:
            raise ValueError(f"Fabric {v} does not exist")
        
        return v

# Usage in views
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class FGDSyncView(APIView):
    """API view for FGD sync operations."""
    
    def post(self, request, fabric_id):
        """Trigger sync operation."""
        try:
            # Validate input
            sync_request = SyncRequestModel(
                fabric_id=fabric_id,
                **request.data
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process request...
```

#### Access Control

```python
# Role-based access control
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from functools import wraps

def require_fgd_permission(permission: str):
    """Decorator to require specific FGD permission."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check user is authenticated
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            # Check specific permission
            if not request.user.has_perm(f'netbox_hedgehog.{permission}'):
                raise PermissionDenied(f"Permission required: {permission}")
            
            # Check fabric-specific permissions if fabric_id provided
            fabric_id = kwargs.get('fabric_id')
            if fabric_id:
                fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
                if not request.user.has_perm(permission, fabric):
                    raise PermissionDenied(
                        f"Permission denied for fabric {fabric.name}"
                    )
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# Usage
@require_fgd_permission('trigger_fgd_sync')
def trigger_sync_view(request, fabric_id):
    """View to trigger sync (requires permission)."""
    pass
```

## Deployment Guidelines

### Environment Configuration

```python
# settings.py additions for FGD
import os
from django.core.exceptions import ImproperlyConfigured

# FGD Configuration
FGD_ENABLED = os.environ.get('HEDGEHOG_FGD_ENABLED', 'false').lower() == 'true'

if FGD_ENABLED:
    # Redis configuration for event bus
    FGD_REDIS_URL = os.environ.get(
        'HEDGEHOG_FGD_REDIS_URL',
        'redis://localhost:6379/1'
    )
    
    # Performance settings
    FGD_BATCH_SIZE = int(os.environ.get('HEDGEHOG_FGD_BATCH_SIZE', '50'))
    FGD_WORKER_POOL_SIZE = int(os.environ.get('HEDGEHOG_FGD_WORKER_POOL_SIZE', '4'))
    FGD_SYNC_TIMEOUT = int(os.environ.get('HEDGEHOG_FGD_SYNC_TIMEOUT', '300'))
    
    # GitHub integration
    FGD_GITHUB_WEBHOOK_SECRET = os.environ.get('HEDGEHOG_FGD_GITHUB_WEBHOOK_SECRET')
    
    # Monitoring
    FGD_METRICS_ENABLED = os.environ.get(
        'HEDGEHOG_FGD_METRICS_ENABLED', 
        'true'
    ).lower() == 'true'
    
    # Add FGD to installed apps
    INSTALLED_APPS += ['netbox_hedgehog.fgd_sync']
    
    # Celery configuration for FGD tasks
    CELERY_BEAT_SCHEDULE = {
        'fgd-health-check': {
            'task': 'netbox_hedgehog.fgd_sync.tasks.periodic_fgd_health_check',
            'schedule': 60.0,  # Every minute
        },
    }

# Validation
if FGD_ENABLED and not FGD_REDIS_URL:
    raise ImproperlyConfigured(
        "FGD is enabled but HEDGEHOG_FGD_REDIS_URL is not configured"
    )
```

### Database Migrations

```python
# Migration for FGD models
from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    """Add FGD sync models."""
    
    dependencies = [
        ('netbox_hedgehog', '0021_bidirectional_sync_extensions'),
    ]
    
    operations = [
        # Sync operation tracking
        migrations.CreateModel(
            name='FGDSyncOperation',
            fields=[
                ('sync_id', models.UUIDField(
                    primary_key=True, 
                    default=uuid.uuid4,
                    help_text='Unique sync operation identifier'
                )),
                ('fabric', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='netbox_hedgehog.hedgehogfabric',
                    help_text='Fabric being synchronized'
                )),
                ('trigger', models.CharField(
                    max_length=50,
                    choices=[
                        ('manual', 'Manual'),
                        ('webhook', 'Webhook'),
                        ('scheduled', 'Scheduled'),
                        ('fabric_created', 'Fabric Created')
                    ],
                    help_text='What triggered this sync'
                )),
                ('state', models.CharField(
                    max_length=50,
                    default='pending',
                    help_text='Current sync state'
                )),
                ('started_at', models.DateTimeField(
                    auto_now_add=True,
                    help_text='When sync was started'
                )),
                ('completed_at', models.DateTimeField(
                    null=True, blank=True,
                    help_text='When sync completed'
                )),
                ('current_stage', models.CharField(
                    max_length=100, blank=True,
                    help_text='Current workflow stage'
                )),
                ('stages_data', models.JSONField(
                    default=dict,
                    help_text='Stage execution data'
                )),
                ('files_processed', models.IntegerField(
                    default=0,
                    help_text='Number of files processed'
                )),
                ('files_created', models.IntegerField(
                    default=0,
                    help_text='Number of files created'
                )),
                ('errors', models.JSONField(
                    default=list,
                    help_text='List of errors encountered'
                )),
                ('warnings', models.JSONField(
                    default=list,
                    help_text='List of warnings encountered'
                )),
                ('correlation_id', models.CharField(
                    max_length=100, unique=True,
                    help_text='Correlation ID for tracking'
                )),
                ('options', models.JSONField(
                    default=dict,
                    help_text='Sync operation options'
                )),
            ],
            options={
                'db_table': 'netbox_hedgehog_fgd_sync_operation',
                'ordering': ['-started_at'],
            },
        ),
        
        # Add indexes for performance
        migrations.AddIndex(
            model_name='fgdsyncOperation',
            index=models.Index(
                fields=['fabric', '-started_at'],
                name='fgd_sync_fabric_time_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='fgdsyncOperation',
            index=models.Index(
                fields=['state'],
                name='fgd_sync_state_idx'
            ),
        ),
        
        # Extend fabric model
        migrations.AddField(
            model_name='hedgehogfabric',
            name='gitops_initialized',
            field=models.BooleanField(
                default=False,
                help_text='Whether FGD system is initialized'
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='last_sync_id',
            field=models.UUIDField(
                null=True, blank=True,
                help_text='ID of last sync operation'
            ),
        ),
    ]
```

## Conclusion

These implementation guidelines provide a comprehensive framework for developing the FGD Synchronization System with:

- **Consistent Code Quality**: Through standardized patterns and practices
- **Production Readiness**: With comprehensive error handling and monitoring
- **Maintainability**: Through clear organization and documentation
- **Performance**: With optimization patterns and caching strategies
- **Security**: With proper validation and access controls
- **Testability**: With comprehensive testing patterns and fixtures

Following these guidelines ensures that all modules integrate seamlessly and meet production quality standards.