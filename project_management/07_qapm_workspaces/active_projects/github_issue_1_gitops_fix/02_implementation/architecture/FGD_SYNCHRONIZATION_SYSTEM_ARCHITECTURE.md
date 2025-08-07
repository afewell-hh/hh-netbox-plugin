# FGD Synchronization System Architecture

**Document Version**: 1.0  
**Created**: 2025-08-02  
**Author**: FGD System Architecture Analyst (Agent ID: fgd_architecture_analyst_001)  
**Purpose**: Comprehensive architectural design for the Fabric GitOps Directory (FGD) synchronization system

## Executive Summary

This document presents a complete architectural design for the HNP Fabric GitOps Directory (FGD) synchronization system. The architecture addresses the critical failure identified in Issue #1 where pre-existing YAML files are not being ingested during fabric creation and synchronization. The design incorporates industry best practices from ArgoCD, Flux CD, and distributed systems principles to create a robust, scalable, and production-ready solution.

### Key Design Principles

1. **Event-Driven Architecture**: Asynchronous processing with comprehensive event handling
2. **Eventual Consistency**: Distributed system patterns for reliable state synchronization
3. **Modular Design**: Independent components with clear interfaces and boundaries
4. **Error Resilience**: Comprehensive error handling with automatic recovery mechanisms
5. **Observable System**: Built-in monitoring, logging, and health checking capabilities

## Current State Analysis

### Identified Problems

Based on code analysis, the current implementation has several critical gaps:

1. **Integration Failure**: The `GitOpsOnboardingService` and `GitOpsIngestionService` exist but are not properly integrated into the fabric creation workflow
2. **Missing Triggers**: No automatic triggering of file ingestion after directory initialization
3. **Incomplete Pipeline**: The bidirectional sync components are implemented but not connected
4. **Race Conditions**: No proper handling of concurrent access to directories
5. **Limited Error Recovery**: Basic error handling without retry mechanisms

### Root Cause Analysis

The primary issue is architectural: the system lacks a unified orchestration layer to coordinate the various GitOps components. Individual services exist in isolation without proper event-driven integration.

## Proposed Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FGD Synchronization System                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐   │
│  │   Event Bus     │◄───┤ Sync Orchestrator ├───►│  State Manager   │   │
│  │  (Django/Redis) │    │    (Core Engine)  │    │  (PostgreSQL)    │   │
│  └────────┬────────┘    └──────────┬────────┘    └──────────────────┘   │
│           │                         │                                     │
│  ┌────────▼────────────────────────▼─────────────────────────────┐      │
│  │                    Processing Pipeline                          │      │
│  ├─────────────────┬─────────────────┬────────────────────────────┤      │
│  │ Directory       │ File Ingestion  │ GitHub Sync              │      │
│  │ Manager         │ Pipeline        │ Client                   │      │
│  │                 │                 │                          │      │
│  │ • Structure     │ • YAML Parser   │ • API Integration       │      │
│  │ • Validation    │ • Normalizer    │ • Change Detection      │      │
│  │ • Initialization│ • Validator     │ • Commit Management     │      │
│  └─────────────────┴─────────────────┴────────────────────────────┘      │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │                    Supporting Services                          │      │
│  ├─────────────────┬─────────────────┬────────────────────────────┤      │
│  │ Health Monitor  │ Error Handler   │ Audit Logger            │      │
│  │                 │                 │                          │      │
│  │ • Liveness     │ • Retry Logic   │ • Operation Tracking    │      │
│  │ • Readiness    │ • Recovery      │ • Change History        │      │
│  │ • Metrics      │ • Alerting      │ • Compliance            │      │
│  └─────────────────┴─────────────────┴────────────────────────────┘      │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Sync Orchestrator (New Component)

The central coordination engine that manages the entire synchronization lifecycle.

**Responsibilities**:
- Coordinate all sync operations across components
- Manage sync state and workflow transitions
- Handle event routing and processing
- Implement retry and recovery logic

**Key Features**:
```python
class SyncOrchestrator:
    """
    Central orchestration engine for FGD synchronization.
    Implements the State Machine pattern for sync workflows.
    """
    
    def __init__(self, fabric):
        self.fabric = fabric
        self.state_manager = StateManager(fabric)
        self.event_bus = EventBus()
        self.processing_pipeline = ProcessingPipeline(fabric)
        
    async def orchestrate_sync(self, trigger_type: str):
        """Main orchestration method"""
        # 1. Initialize sync context
        sync_context = self.initialize_sync_context(trigger_type)
        
        # 2. Validate prerequisites
        if not await self.validate_prerequisites(sync_context):
            return self.handle_validation_failure(sync_context)
        
        # 3. Execute sync workflow
        try:
            # Stage 1: Directory validation and repair
            await self.execute_directory_stage(sync_context)
            
            # Stage 2: File discovery and processing
            await self.execute_ingestion_stage(sync_context)
            
            # Stage 3: GitHub synchronization
            await self.execute_github_stage(sync_context)
            
            # Stage 4: State reconciliation
            await self.execute_reconciliation_stage(sync_context)
            
            # Stage 5: Notification and cleanup
            await self.execute_completion_stage(sync_context)
            
        except Exception as e:
            await self.handle_sync_failure(sync_context, e)
```

#### 2. Event-Driven Integration Layer

Implements asynchronous, event-driven communication between components.

**Event Types**:
- `FABRIC_CREATED`: Triggered when new fabric is created
- `DIRECTORY_INITIALIZED`: GitOps directory structure ready
- `FILES_DISCOVERED`: New files found in raw/ directory
- `INGESTION_COMPLETED`: Files successfully processed
- `SYNC_FAILED`: Sync operation failed with error details

**Implementation**:
```python
class EventBus:
    """
    Centralized event bus for component communication.
    Uses Django signals + Redis for distributed events.
    """
    
    def __init__(self):
        self.redis_client = redis.Redis(...)
        self.handlers = defaultdict(list)
        
    async def publish(self, event_type: str, payload: dict):
        """Publish event to all subscribers"""
        event = Event(
            type=event_type,
            payload=payload,
            timestamp=timezone.now(),
            correlation_id=generate_correlation_id()
        )
        
        # Local handlers (Django signals)
        await self._notify_local_handlers(event)
        
        # Distributed handlers (Redis pub/sub)
        await self._publish_to_redis(event)
        
    async def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to specific event types"""
        self.handlers[event_type].append(handler)
```

#### 3. Enhanced Directory Manager

Builds upon existing `GitOpsDirectoryManager` with additional capabilities.

**Enhancements**:
- Atomic directory operations with rollback
- Concurrent access handling with file locking
- Directory health monitoring and auto-repair
- Change detection and incremental sync

```python
class EnhancedDirectoryManager(GitOpsDirectoryManager):
    """
    Production-ready directory management with advanced features.
    """
    
    def __init__(self, fabric):
        super().__init__(fabric)
        self.lock_manager = LockManager()
        self.health_monitor = DirectoryHealthMonitor()
        
    async def ensure_directory_structure(self):
        """Ensure directory structure with automatic repair"""
        async with self.lock_manager.acquire_lock(self.fabric.id):
            # 1. Validate existing structure
            validation_result = await self.validate_structure()
            
            # 2. Auto-repair if needed
            if not validation_result.is_valid:
                repair_result = await self.repair_structure(validation_result)
                
            # 3. Initialize if new
            if not await self.is_initialized():
                init_result = await self.initialize_structure()
                
            # 4. Verify health
            health_status = await self.health_monitor.check_health()
            
            return StructureResult(
                valid=health_status.is_healthy,
                repairs_made=repair_result.repairs if repair_result else [],
                initialized=init_result.success if init_result else False
            )
```

#### 4. Robust File Ingestion Pipeline

Enhanced version of `FileIngestionPipeline` with production features.

**Key Improvements**:
- Parallel file processing with worker pool
- Transactional processing with rollback
- Content validation and schema checking
- Incremental processing with checkpointing

```python
class RobustIngestionPipeline(FileIngestionPipeline):
    """
    Production-ready file ingestion with advanced features.
    """
    
    def __init__(self, fabric):
        super().__init__(fabric)
        self.worker_pool = ThreadPoolExecutor(max_workers=4)
        self.checkpoint_manager = CheckpointManager()
        
    async def process_raw_directory(self):
        """Process with checkpointing and parallel execution"""
        # 1. Resume from last checkpoint if available
        checkpoint = await self.checkpoint_manager.get_last_checkpoint()
        
        # 2. Discover files (skip already processed)
        files_to_process = await self.discover_pending_files(checkpoint)
        
        # 3. Process in parallel with progress tracking
        async with self.worker_pool:
            tasks = []
            for file_batch in self.batch_files(files_to_process):
                task = self.process_file_batch(file_batch)
                tasks.append(task)
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        # 4. Handle results and update checkpoint
        await self.consolidate_results(results)
        await self.checkpoint_manager.save_checkpoint()
```

#### 5. State Management System

Centralized state management for sync operations.

**State Model**:
```python
class SyncState(Enum):
    PENDING = "pending"
    INITIALIZING = "initializing"
    DISCOVERING = "discovering"
    PROCESSING = "processing"
    SYNCING = "syncing"
    RECONCILING = "reconciling"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class StateManager:
    """
    Manages sync state with persistence and recovery.
    """
    
    def __init__(self, fabric):
        self.fabric = fabric
        self.current_state = SyncState.PENDING
        self.state_history = []
        
    async def transition_to(self, new_state: SyncState, context: dict):
        """State transition with validation and persistence"""
        # 1. Validate transition is allowed
        if not self.is_valid_transition(self.current_state, new_state):
            raise InvalidStateTransition(...)
            
        # 2. Persist state change
        state_record = SyncStateRecord(
            fabric=self.fabric,
            from_state=self.current_state,
            to_state=new_state,
            context=context,
            timestamp=timezone.now()
        )
        await state_record.asave()
        
        # 3. Update current state
        self.current_state = new_state
        self.state_history.append(state_record)
        
        # 4. Emit state change event
        await self.emit_state_change_event(state_record)
```

### Integration Points

#### 1. Fabric Creation Integration

```python
# In HedgehogFabric.save() method
def save(self, *args, **kwargs):
    is_new = self.pk is None
    super().save(*args, **kwargs)
    
    if is_new and self.git_repository:
        # Trigger async FGD initialization
        transaction.on_commit(
            lambda: trigger_fgd_initialization.delay(self.id)
        )

# Celery task
@shared_task
def trigger_fgd_initialization(fabric_id):
    fabric = HedgehogFabric.objects.get(id=fabric_id)
    orchestrator = SyncOrchestrator(fabric)
    
    # Run full initialization and sync
    asyncio.run(orchestrator.orchestrate_sync('fabric_creation'))
```

#### 2. Manual Sync Trigger

```python
# In sync view
async def trigger_gitops_sync(request, fabric_id):
    fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
    orchestrator = SyncOrchestrator(fabric)
    
    # Check if sync already in progress
    if await orchestrator.is_sync_in_progress():
        return JsonResponse({
            'success': False,
            'error': 'Sync already in progress'
        })
    
    # Trigger sync asynchronously
    sync_id = await orchestrator.orchestrate_sync('manual_trigger')
    
    return JsonResponse({
        'success': True,
        'sync_id': sync_id,
        'status_url': f'/api/sync-status/{sync_id}/'
    })
```

#### 3. GitHub Webhook Integration

```python
# Webhook handler
async def handle_github_webhook(request):
    payload = json.loads(request.body)
    
    # Identify affected fabrics
    affected_fabrics = await identify_affected_fabrics(payload)
    
    for fabric in affected_fabrics:
        orchestrator = SyncOrchestrator(fabric)
        await orchestrator.orchestrate_sync('github_webhook')
```

### Error Handling Strategy

#### 1. Retry Mechanism

```python
class RetryPolicy:
    """Configurable retry policy with exponential backoff"""
    
    def __init__(self):
        self.max_retries = 3
        self.initial_delay = 1.0  # seconds
        self.max_delay = 60.0
        self.exponential_base = 2
        
    def calculate_delay(self, attempt: int) -> float:
        delay = self.initial_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)

class ErrorHandler:
    """Comprehensive error handling with recovery"""
    
    async def handle_error(self, error: Exception, context: dict):
        # 1. Classify error
        error_type = self.classify_error(error)
        
        # 2. Determine if retryable
        if self.is_retryable(error_type):
            return await self.schedule_retry(context)
            
        # 3. Execute recovery action
        recovery_action = self.get_recovery_action(error_type)
        if recovery_action:
            return await recovery_action(context)
            
        # 4. Escalate if unrecoverable
        return await self.escalate_error(error, context)
```

#### 2. Circuit Breaker Pattern

```python
class CircuitBreaker:
    """Prevent cascading failures with circuit breaker"""
    
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        
    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if self.should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError("Circuit breaker is open")
                
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
```

### Performance Optimization

#### 1. Caching Strategy

```python
class SyncCache:
    """Multi-level caching for sync operations"""
    
    def __init__(self):
        self.memory_cache = {}  # In-memory cache
        self.redis_cache = redis.Redis(...)  # Distributed cache
        
    async def get_or_compute(self, key: str, compute_func: Callable):
        # 1. Check memory cache
        if key in self.memory_cache:
            return self.memory_cache[key]
            
        # 2. Check Redis cache
        redis_value = await self.redis_cache.get(key)
        if redis_value:
            value = json.loads(redis_value)
            self.memory_cache[key] = value
            return value
            
        # 3. Compute and cache
        value = await compute_func()
        await self.cache_value(key, value)
        return value
```

#### 2. Batch Processing

```python
class BatchProcessor:
    """Efficient batch processing for file operations"""
    
    def __init__(self, batch_size=50):
        self.batch_size = batch_size
        
    async def process_files(self, files: List[Path]):
        batches = [
            files[i:i + self.batch_size]
            for i in range(0, len(files), self.batch_size)
        ]
        
        results = []
        for batch in batches:
            batch_results = await self.process_batch(batch)
            results.extend(batch_results)
            
            # Allow other operations between batches
            await asyncio.sleep(0.1)
            
        return results
```

### Monitoring and Observability

#### 1. Health Checks

```python
class FGDHealthCheck:
    """Comprehensive health checking for FGD system"""
    
    async def check_health(self) -> HealthStatus:
        checks = {
            'directory_structure': self.check_directory_health(),
            'github_connectivity': self.check_github_health(),
            'database_consistency': self.check_database_health(),
            'sync_queue': self.check_sync_queue_health(),
            'worker_pool': self.check_worker_health()
        }
        
        results = await asyncio.gather(*checks.values())
        
        return HealthStatus(
            healthy=all(r.healthy for r in results),
            checks=dict(zip(checks.keys(), results)),
            timestamp=timezone.now()
        )
```

#### 2. Metrics Collection

```python
class MetricsCollector:
    """Collect and expose metrics for monitoring"""
    
    def __init__(self):
        self.metrics = {
            'sync_duration': Histogram('fgd_sync_duration_seconds'),
            'files_processed': Counter('fgd_files_processed_total'),
            'sync_failures': Counter('fgd_sync_failures_total'),
            'active_syncs': Gauge('fgd_active_syncs')
        }
        
    def record_sync_duration(self, duration: float, labels: dict):
        self.metrics['sync_duration'].labels(**labels).observe(duration)
```

### Security Considerations

#### 1. Access Control

```python
class FGDAccessControl:
    """Role-based access control for FGD operations"""
    
    def check_permission(self, user, fabric, operation):
        # Check user has appropriate permissions
        if operation == 'sync':
            return user.has_perm('netbox_hedgehog.sync_fabric')
        elif operation == 'configure':
            return user.has_perm('netbox_hedgehog.change_fabric')
```

#### 2. Audit Trail

```python
class AuditLogger:
    """Comprehensive audit logging for compliance"""
    
    async def log_operation(self, operation: str, context: dict):
        audit_record = FGDAuditRecord(
            operation=operation,
            user=context.get('user'),
            fabric=context.get('fabric'),
            timestamp=timezone.now(),
            details=self.sanitize_details(context),
            ip_address=context.get('ip_address')
        )
        await audit_record.asave()
```

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1-2)
- Implement SyncOrchestrator framework
- Create EventBus for component communication  
- Enhance StateManager with persistence
- Set up monitoring infrastructure

### Phase 2: Component Enhancement (Week 2-3)
- Enhance DirectoryManager with locking and health checks
- Upgrade FileIngestionPipeline with parallel processing
- Improve GitHubSyncClient with retry logic
- Implement comprehensive error handling

### Phase 3: Integration (Week 3-4)
- Integrate with fabric creation workflow
- Connect manual sync triggers
- Implement webhook handlers
- Add progress tracking UI

### Phase 4: Production Hardening (Week 4-5)
- Add circuit breakers and rate limiting
- Implement comprehensive caching
- Set up performance monitoring
- Create operational dashboards

### Phase 5: Testing and Validation (Week 5-6)
- Unit tests for all components
- Integration tests for workflows
- Performance testing under load
- Chaos engineering tests

## Success Criteria

1. **Functional Requirements**
   - Pre-existing YAML files are automatically ingested during fabric creation
   - Directory structure is validated and auto-repaired
   - Invalid files are properly moved to unmanaged/
   - Sync operations are idempotent and recoverable

2. **Performance Requirements**
   - Sync operations complete within 30 seconds for typical workloads
   - Support for 100+ concurrent fabric syncs
   - Sub-second response time for sync status queries

3. **Reliability Requirements**
   - 99.9% success rate for sync operations
   - Automatic recovery from transient failures
   - Zero data loss during sync operations
   - Graceful degradation under high load

4. **Operational Requirements**
   - Comprehensive logging and monitoring
   - Clear error messages with remediation steps
   - Audit trail for all operations
   - Health check endpoints for monitoring

## Conclusion

This architecture provides a comprehensive, production-ready solution for the FGD synchronization system. By incorporating industry best practices from ArgoCD, Flux CD, and distributed systems principles, the design ensures reliable, scalable, and maintainable GitOps operations for HNP.

The modular architecture enables independent development and testing of components while the event-driven design ensures loose coupling and high cohesion. The comprehensive error handling and monitoring capabilities provide the operational excellence required for carrier-grade reliability.