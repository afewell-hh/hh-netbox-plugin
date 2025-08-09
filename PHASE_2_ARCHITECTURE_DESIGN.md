# Phase 2: Backend Integration & Core Functionality - Architecture Design

## Executive Summary

This document provides a comprehensive architectural design for Phase 2 implementation, focusing on **Periodic Sync Scheduler**, **Status Synchronization**, **Backend Integration**, and **Core Functionality** enhancements. The design leverages existing Celery infrastructure while introducing micro-task architecture for agent productivity.

## Current Architecture Analysis

### Existing Infrastructure Strengths
1. **Robust Celery Task System**: Well-structured async task processing with specialized queues
2. **Event-Driven Architecture**: Comprehensive event service with WebSocket integration
3. **Sophisticated Fabric Model**: Rich domain model with GitOps and Kubernetes integration
4. **Service Layer Pattern**: Clean separation with application services
5. **Progress Tracking**: Real-time sync progress with event publishing

### Identified Integration Gaps
1. **Inconsistent Status Synchronization** across fabric/repository components
2. **Manual Scheduling** - no automated periodic sync orchestration
3. **Limited Backend Coordination** between Git and Kubernetes sync operations
4. **Status Propagation Delays** in complex multi-fabric scenarios

## Phase 2 Architecture Design

### 1. Enhanced Periodic Sync Scheduler

#### 1.1 Multi-Tier Scheduling Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Celery Beat Scheduler                       │
├─────────────────────────────────────────────────────────────┤
│  Master Scheduler (every 60s)                              │
│  ├── check_fabric_sync_schedules                          │
│  ├── health_monitor_scheduler                             │
│  └── status_sync_orchestrator (NEW)                       │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                Fabric-Specific Schedulers                  │
├─────────────────────────────────────────────────────────────┤
│  Per-Fabric Sync Jobs (dynamic intervals)                  │
│  ├── git_sync_fabric                                      │
│  ├── kubernetes_sync_fabric (NEW)                         │
│  ├── status_reconciliation_fabric (NEW)                   │
│  └── drift_detection_fabric (NEW)                         │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              Micro-Task Decomposition                      │
├─────────────────────────────────────────────────────────────┤
│  Agent-Optimized Sub-Tasks (<30s each)                     │
│  ├── validate_git_connectivity                            │
│  ├── fetch_repository_changes                             │
│  ├── process_crd_batch (50 CRDs)                          │
│  ├── kubernetes_resource_sync                             │
│  └── update_fabric_status_atomic                          │
└─────────────────────────────────────────────────────────────┘
```

#### 1.2 Implementation Details

**Enhanced Scheduler Task** (`netbox_hedgehog/tasks/sync_scheduler.py`):
```python
@shared_task(name='netbox_hedgehog.tasks.status_sync_orchestrator')
def status_sync_orchestrator() -> Dict[str, Any]:
    """
    Master orchestrator for coordinated sync operations
    Ensures consistent status across all fabric components
    """
    fabrics = HedgehogFabric.objects.filter(sync_enabled=True)
    orchestration_results = []
    
    for fabric in fabrics:
        # Micro-task coordination
        sync_plan = create_fabric_sync_plan(fabric)
        execution_result = execute_coordinated_sync(fabric, sync_plan)
        orchestration_results.append(execution_result)
    
    return {
        'fabrics_processed': len(orchestration_results),
        'successful_syncs': sum(1 for r in orchestration_results if r['success']),
        'coordination_errors': [r for r in orchestration_results if not r['success']]
    }
```

### 2. Status Synchronization Framework

#### 2.1 Unified Status Model

```
┌─────────────────────────────────────────────────────────────┐
│                   Fabric Status Hub                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Git Status  │  │ K8s Status  │  │Sync Status  │        │
│  │ ├─ commit   │  │ ├─ connect  │  │ ├─ progress │        │
│  │ ├─ branch   │  │ ├─ health   │  │ ├─ errors   │        │
│  │ └─ sync     │  │ └─ watch    │  │ └─ drift    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
├─────────────────────────────────────────────────────────────┤
│                Status Reconciliation Engine                │
│  ├── Cross-component validation                           │
│  ├── Status conflict resolution                           │
│  ├── Real-time status propagation                         │
│  └── Health score calculation                             │
└─────────────────────────────────────────────────────────────┘
```

#### 2.2 Status Synchronization Service

**New Service** (`netbox_hedgehog/application/services/status_sync_service.py`):
```python
class StatusSynchronizationService:
    """
    Coordinates status updates across Git, Kubernetes, and Sync subsystems
    Ensures consistent status representation across the entire system
    """
    
    async def reconcile_fabric_status(self, fabric: HedgehogFabric) -> StatusReconciliationResult:
        """
        Perform comprehensive status reconciliation for a fabric
        """
        # Micro-task 1: Gather current statuses
        current_states = await self.gather_current_states(fabric)
        
        # Micro-task 2: Detect status conflicts
        conflicts = await self.detect_status_conflicts(current_states)
        
        # Micro-task 3: Resolve conflicts with business rules
        resolved_status = await self.resolve_status_conflicts(conflicts)
        
        # Micro-task 4: Propagate resolved status
        await self.propagate_status_updates(fabric, resolved_status)
        
        return StatusReconciliationResult(
            fabric_id=fabric.id,
            previous_states=current_states,
            resolved_status=resolved_status,
            conflicts_resolved=len(conflicts)
        )
```

### 3. Backend Integration Architecture

#### 3.1 Enhanced Integration Patterns

```
┌─────────────────────────────────────────────────────────────┐
│                NetBox-Kubernetes Bridge                     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐               │
│  │   Git Service   │◄──►│  K8s Service    │               │
│  │ ├─ Repository   │    │ ├─ Cluster API  │               │
│  │ ├─ Branch Sync  │    │ ├─ CRD Watch    │               │
│  │ └─ Validation   │    │ └─ Health Check │               │
│  └─────────────────┘    └─────────────────┘               │
│          │                       │                        │
│          ▼                       ▼                        │
│  ┌─────────────────────────────────────────────────────┐  │
│  │          Integration Coordinator                    │  │
│  │  ├── Bidirectional sync orchestration             │  │
│  │  ├── Conflict resolution strategies               │  │
│  │  ├── Transaction coordination                     │  │
│  │  └── Event correlation                            │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

#### 3.2 Integration Coordinator Service

**New Service** (`netbox_hedgehog/application/services/integration_coordinator.py`):
```python
class IntegrationCoordinator:
    """
    Orchestrates complex interactions between NetBox, Git, and Kubernetes
    Implements saga pattern for distributed transaction management
    """
    
    def __init__(self):
        self.git_service = GitService()
        self.k8s_service = KubernetesService()
        self.event_service = EventService()
    
    async def execute_coordinated_sync(self, fabric: HedgehogFabric, 
                                     sync_plan: SyncPlan) -> CoordinatedSyncResult:
        """
        Execute multi-step sync operation with rollback capability
        Implements SPARC methodology for agent productivity
        """
        saga = SyncSaga(fabric, sync_plan)
        
        try:
            # Step 1: Pre-sync validation (Agent Micro-task: 5-10s)
            validation_result = await saga.execute_step(
                'validate_prerequisites', 
                self._validate_sync_prerequisites
            )
            
            # Step 2: Git sync with progress tracking (Agent Micro-task: 10-20s)
            git_result = await saga.execute_step(
                'git_sync',
                lambda: self.git_service.sync_with_progress_tracking(fabric)
            )
            
            # Step 3: Kubernetes sync (Agent Micro-task: 10-15s)
            k8s_result = await saga.execute_step(
                'kubernetes_sync',
                lambda: self.k8s_service.sync_cluster_state(fabric)
            )
            
            # Step 4: Status reconciliation (Agent Micro-task: 5-10s)
            status_result = await saga.execute_step(
                'status_reconciliation',
                lambda: self.reconcile_post_sync_status(fabric, git_result, k8s_result)
            )
            
            return saga.complete_successfully()
            
        except Exception as e:
            # Execute compensating actions
            await saga.rollback()
            raise CoordinatedSyncException(f"Sync coordination failed: {e}")
```

### 4. Core Functionality Enhancements

#### 4.1 Reliability Patterns

**Circuit Breaker Pattern** for external dependencies:
```python
class KubernetesCircuitBreaker:
    """
    Prevents cascade failures when Kubernetes cluster is unhealthy
    """
    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
```

**Retry with Exponential Backoff**:
```python
@retry_with_exponential_backoff(
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0,
    exceptions=(KubernetesConnectionError, GitConnectionError)
)
async def resilient_sync_operation(fabric: HedgehogFabric):
    """
    Resilient sync operation with intelligent retry logic
    """
```

#### 4.2 Performance Optimizations

**Batch Processing Architecture**:
```python
class BatchProcessor:
    """
    Optimizes CRD processing through intelligent batching
    Agent-friendly: each batch <30s processing time
    """
    
    async def process_crds_in_batches(self, fabric: HedgehogFabric, 
                                    crds: List[Dict], batch_size=50):
        """
        Process CRDs in optimized batches with progress tracking
        """
        batches = self.create_optimized_batches(crds, batch_size)
        results = []
        
        for i, batch in enumerate(batches):
            batch_result = await self.process_single_batch(fabric, batch)
            
            # Progress reporting for agent visibility
            progress = int((i + 1) / len(batches) * 100)
            await self.event_service.publish_sync_event(
                fabric_id=fabric.id,
                event_type='batch_progress',
                progress=progress,
                message=f"Processed batch {i+1}/{len(batches)}"
            )
            
            results.append(batch_result)
        
        return BatchProcessingResult(batches=results, total_processed=len(crds))
```

### 5. File Structure and Implementation Plan

#### 5.1 New Files to Create

```
netbox_hedgehog/
├── tasks/
│   ├── sync_scheduler.py           # Enhanced periodic scheduler
│   ├── status_reconciliation.py    # Status sync tasks
│   └── batch_processing.py         # Optimized batch operations
├── application/services/
│   ├── status_sync_service.py      # Status synchronization
│   ├── integration_coordinator.py  # Backend coordination
│   └── batch_processor_service.py  # Batch processing logic
├── domain/
│   ├── sync_saga.py               # Saga pattern implementation
│   └── circuit_breaker.py         # Reliability patterns
└── utils/
    ├── sync_planning.py           # Sync plan generation
    └── performance_monitor.py     # Performance tracking
```

#### 5.2 Files to Modify

```
MODIFY: netbox_hedgehog/celery.py
- Add new task routes for status sync operations
- Configure batch processing queues
- Add performance monitoring beat schedules

MODIFY: netbox_hedgehog/tasks/git_sync_tasks.py
- Integrate with status synchronization service
- Add coordinator service integration
- Enhance progress tracking with micro-task boundaries

MODIFY: netbox_hedgehog/models/fabric.py
- Add status reconciliation fields
- Add sync plan tracking
- Add performance metrics fields

MODIFY: netbox_hedgehog/application/services/event_service.py
- Add status synchronization event types
- Add batch processing progress events
- Add coordinator events
```

### 6. Implementation Sequence for Sub-Agent Orchestration

#### Phase 2.1: Foundation (Week 1)
1. **Status Synchronization Service** - Core status reconciliation logic
2. **Enhanced Scheduler Tasks** - Periodic sync orchestrator
3. **Circuit Breaker Patterns** - Reliability infrastructure

#### Phase 2.2: Integration (Week 2)
1. **Integration Coordinator** - Saga pattern implementation
2. **Batch Processor Service** - Performance optimization
3. **Sync Planning Module** - Intelligent sync orchestration

#### Phase 2.3: Optimization (Week 3)
1. **Performance Monitoring** - Agent productivity metrics
2. **Status Propagation** - Real-time status updates
3. **Error Recovery** - Automated recovery workflows

### 7. Success Criteria and Measurements

#### 7.1 Quantitative Metrics
- **Sync Reliability**: >95% successful scheduled syncs
- **Status Consistency**: <5s status propagation delay
- **Agent Productivity**: >80% tasks completed within 30s
- **System Resilience**: <1% cascade failure rate

#### 7.2 Qualitative Indicators
- **Status Accuracy**: Consistent status across all components
- **User Experience**: Real-time feedback during sync operations
- **System Stability**: Graceful handling of external service failures
- **Maintainability**: Clear separation of concerns, testable components

### 8. Technology Stack Alignment

#### 8.1 Existing Infrastructure Utilization
- **Celery**: Enhanced with new task types and queues
- **Django Channels**: Extended for real-time status updates  
- **Redis**: Enhanced caching for status synchronization
- **PostgreSQL**: New tables for sync planning and status tracking

#### 8.2 SPARC Methodology Integration
- **Specification**: Clear micro-task boundaries (<30s)
- **Planning**: Detailed sync plan generation
- **Architecture**: Service-oriented, event-driven design
- **Review**: Built-in performance monitoring and health checks
- **Code**: Agent-optimized implementation patterns

## Conclusion

This Phase 2 architecture design provides a robust, scalable foundation for Backend Integration & Core Functionality. The design emphasizes:

1. **Agent Productivity** through micro-task decomposition
2. **System Reliability** via circuit breaker and saga patterns
3. **Status Consistency** through unified synchronization
4. **Performance Optimization** via intelligent batching

The implementation plan ensures incremental delivery with measurable progress, leveraging existing infrastructure while introducing modern reliability and performance patterns.