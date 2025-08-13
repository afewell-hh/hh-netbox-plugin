# RQ-Based Periodic Sync Architecture Specification

## Executive Summary

**CRITICAL DISCOVERY**: The current system uses Celery, but NetBox's standard is RQ (Redis Queue). This specification designs a complete RQ-based periodic sync system that replaces the existing Celery implementation and addresses the observed 60-second timing issue.

## 1. Current System Analysis

### 1.1 Existing Implementation Issues
- **Celery Mismatch**: Current system uses Celery (`netbox_hedgehog/celery.py`) but NetBox uses RQ
- **Timing Issues**: User observed 60-second interval inconsistencies
- **Integration Problems**: Celery doesn't integrate with NetBox's background task system
- **Non-functional State**: Celery-based scheduler completely non-functional in NetBox environment

### 1.2 NetBox RQ Integration Patterns
Based on research and NetBox documentation:
- NetBox uses `django-rq` with Redis backend
- Background tasks use `JobRunner` class (NetBox v4.2+)  
- System jobs use `@system_job()` decorator for periodic tasks
- Three default queues: `high`, `default`, `low`
- Plugins can define custom queues via `PluginConfig.queues`

## 2. RQ-Based Architecture Design

### 2.1 Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    RQ PERIODIC SYNC SYSTEM                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐    ┌─────────────────┐               │
│  │  RQ Scheduler    │───▶│   Job Queue     │               │
│  │  (60s intervals) │    │   (Redis)       │               │
│  └──────────────────┘    └─────────────────┘               │
│                                   │                         │
│                           ┌───────▼────────┐                │
│                           │  RQ Workers     │                │
│                           │  (Background)   │                │
│                           └───────┬────────┘                │
│                                   │                         │
│  ┌────────────────────────────────▼────────────────────────┐│
│  │              SYNC EXECUTION PIPELINE                   ││
│  │                                                        ││
│  │  Fabric Sync Job → K8s API Call → Status Update       ││
│  │       │                  │            │                ││
│  │       ├─ Git Sync        ├─ CRD Sync  ├─ DB Update     ││
│  │       ├─ Validation      ├─ Watch     ├─ Cache Update  ││
│  │       └─ Health Check    └─ Metrics   └─ Event Log     ││
│  └────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 2.2 File Structure Specification

```
netbox_hedgehog/
├── jobs/                          # NEW: RQ Job implementations
│   ├── __init__.py
│   ├── fabric_sync_jobs.py        # Main sync job definitions
│   ├── scheduler_jobs.py          # Periodic scheduler jobs
│   └── monitoring_jobs.py         # Health and metric jobs
│
├── rq_tasks/                      # REPLACE: tasks/ directory
│   ├── __init__.py               # RQ task registration
│   ├── sync_runner.py            # Sync execution logic
│   ├── k8s_operations.py         # Kubernetes API operations
│   ├── git_operations.py         # Git sync operations
│   └── status_updater.py         # Status and metadata updates
│
├── schedulers/                    # NEW: Scheduler management
│   ├── __init__.py
│   ├── rq_scheduler.py           # RQ-based periodic scheduler
│   ├── job_orchestrator.py      # Job coordination logic
│   └── timer_manager.py          # Precise timing management
│
├── plugin_config.py              # MODIFIED: Add RQ queues
└── apps.py                       # MODIFIED: RQ integration
```

## 3. Technical Implementation Specifications

### 3.1 RQ Queue Configuration

```python
# In plugin_config.py (NetBoxPlugin subclass)
class NetBoxHedgehogConfig(PluginConfig):
    name = 'netbox_hedgehog'
    # ... existing config ...
    
    # Define custom RQ queues for fabric sync
    queues = [
        'hedgehog_sync',      # Main sync operations
        'hedgehog_schedule',  # Scheduling and orchestration  
        'hedgehog_monitor',   # Monitoring and health checks
    ]
```

### 3.2 RQ JobRunner Implementation

```python
# jobs/fabric_sync_jobs.py
from netbox.jobs import JobRunner
from django_rq import job
import django_rq

class FabricPeriodicSyncJob(JobRunner):
    """RQ job for periodic fabric synchronization"""
    
    class Meta:
        name = "Fabric Periodic Sync"
        description = "Synchronize fabric state with Kubernetes cluster"
        
    def run(self, fabric_id: int, sync_type: str = "full"):
        """Execute fabric sync job"""
        # Implementation details in Section 3.3
        pass

# System job decorator for periodic scheduling
from netbox.jobs import system_job

@system_job(interval=1)  # 1 minute interval
def fabric_sync_scheduler():
    """Master scheduler for fabric sync jobs (RQ implementation)"""
    # Implementation details in Section 3.4
    pass
```

### 3.3 Sync Execution Pipeline

```python
class SyncExecutionPipeline:
    """Coordinated sync execution with precise timing"""
    
    def __init__(self, fabric_id: int):
        self.fabric_id = fabric_id
        self.fabric = HedgehogFabric.objects.get(id=fabric_id)
        self.start_time = timezone.now()
        
    def execute_sync(self) -> Dict[str, Any]:
        """Execute complete sync pipeline with timing accuracy"""
        
        # Step 1: Pre-sync validation (< 5s)
        validation_result = self._validate_fabric_readiness()
        if not validation_result['success']:
            return self._handle_validation_failure(validation_result)
        
        # Step 2: Kubernetes API sync (< 20s)
        k8s_result = self._sync_kubernetes_state()
        
        # Step 3: Git sync if configured (< 15s) 
        git_result = self._sync_git_repository()
        
        # Step 4: Status reconciliation (< 10s)
        status_result = self._update_fabric_status()
        
        # Step 5: Post-sync cleanup (< 10s)
        cleanup_result = self._cleanup_and_finalize()
        
        # Total target: < 60s for complete sync cycle
        return self._build_sync_result([
            validation_result, k8s_result, git_result,
            status_result, cleanup_result
        ])
```

### 3.4 RQ Scheduler Implementation

```python
# schedulers/rq_scheduler.py
from django_rq import get_scheduler
from rq_scheduler import Scheduler
from datetime import datetime, timedelta

class RQFabricSyncScheduler:
    """RQ-based periodic sync scheduler replacing Celery"""
    
    def __init__(self):
        self.scheduler = get_scheduler('hedgehog_schedule')
        self.job_registry = {}
        
    def schedule_fabric_sync(self, fabric_id: int, interval: int = 60):
        """Schedule periodic sync for a fabric"""
        
        job_id = f"fabric_sync_{fabric_id}"
        
        # Cancel existing job if present
        self._cancel_fabric_sync(fabric_id)
        
        # Schedule new periodic job
        job = self.scheduler.schedule(
            scheduled_time=datetime.utcnow(),
            func='netbox_hedgehog.jobs.fabric_sync_jobs.execute_fabric_sync',
            args=[fabric_id],
            interval=interval,
            repeat=None,  # Repeat indefinitely
            job_id=job_id,
            queue_name='hedgehog_sync'
        )
        
        self.job_registry[fabric_id] = job_id
        
        logger.info(f"Scheduled fabric {fabric_id} sync every {interval}s")
        return job_id
    
    def reschedule_all_fabrics(self):
        """Reschedule all eligible fabrics (called by system job)"""
        
        eligible_fabrics = HedgehogFabric.objects.filter(
            scheduler_enabled=True,
            sync_enabled=True
        )
        
        scheduled_count = 0
        for fabric in eligible_fabrics:
            try:
                self.schedule_fabric_sync(
                    fabric_id=fabric.id,
                    interval=fabric.sync_interval or 60
                )
                scheduled_count += 1
            except Exception as e:
                logger.error(f"Failed to schedule fabric {fabric.id}: {e}")
        
        logger.info(f"Rescheduled {scheduled_count} fabrics")
        return scheduled_count
```

## 4. Timing Architecture Solution

### 4.1 60-Second Interval Precision

**PROBLEM IDENTIFIED**: Current Celery beat scheduler has timing drift and inconsistencies.

**RQ SOLUTION**:

```python
class PrecisionTimingManager:
    """Manages precise 60-second intervals using RQ scheduler"""
    
    def __init__(self):
        self.base_time = self._calculate_base_time()
        
    def _calculate_base_time(self) -> datetime:
        """Calculate aligned base time for 60-second intervals"""
        now = datetime.utcnow()
        # Align to next minute boundary  
        return now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    
    def schedule_fabric_with_offset(self, fabric_id: int, offset_seconds: int = 0):
        """Schedule fabric sync with precise timing and offset"""
        
        scheduled_time = self.base_time + timedelta(seconds=offset_seconds)
        
        # Use RQ scheduler for precise timing
        job = get_scheduler('hedgehog_sync').schedule(
            scheduled_time=scheduled_time,
            func=execute_fabric_sync_job,
            args=[fabric_id],
            interval=60,  # Exactly 60 seconds
            job_id=f"precision_sync_{fabric_id}"
        )
        
        return job

def execute_fabric_sync_job(fabric_id: int):
    """Precisely timed fabric sync execution"""
    
    # Update "last_sync" BEFORE sync starts (prevents timing drift)
    fabric = HedgehogFabric.objects.get(id=fabric_id)
    fabric.last_sync = timezone.now()
    fabric.save(update_fields=['last_sync'])
    
    # Execute actual sync
    sync_result = SyncExecutionPipeline(fabric_id).execute_sync()
    
    # Update final status (preserves precise timing)
    fabric.sync_status = 'synced' if sync_result['success'] else 'error'
    fabric.save(update_fields=['sync_status'])
    
    return sync_result
```

### 4.2 Startup and Recovery Strategy

```python
class SchedulerRecoveryManager:
    """Handles scheduler startup and failure recovery"""
    
    def initialize_scheduler_system(self):
        """Initialize scheduler system on NetBox startup"""
        
        # Clear stale jobs from previous runs
        self._cleanup_stale_jobs()
        
        # Reschedule all eligible fabrics
        scheduler = RQFabricSyncScheduler()
        scheduled_count = scheduler.reschedule_all_fabrics()
        
        logger.info(f"Scheduler initialized: {scheduled_count} fabrics scheduled")
        
    def _cleanup_stale_jobs(self):
        """Clean up stale jobs from previous runs"""
        scheduler = get_scheduler('hedgehog_schedule')
        
        # Cancel all existing hedgehog jobs
        for job in scheduler.get_jobs():
            if job.id and job.id.startswith('fabric_sync_'):
                scheduler.cancel(job)
                
        logger.info("Cleaned up stale scheduler jobs")
```

## 5. Data Flow and State Management

### 5.1 Database Transaction Boundaries

```python
from django.db import transaction

class TransactionalSyncRunner:
    """Ensures atomic database operations during sync"""
    
    @transaction.atomic
    def update_fabric_state(self, fabric_id: int, sync_data: dict):
        """Atomically update fabric state"""
        
        fabric = HedgehogFabric.objects.select_for_update().get(id=fabric_id)
        
        # Update all sync-related fields in single transaction
        fabric.last_sync = timezone.now()
        fabric.sync_status = sync_data.get('status', 'synced')
        fabric.cached_crd_count = sync_data.get('crd_count', 0)
        fabric.connection_status = sync_data.get('connection_status', 'connected')
        
        fabric.save(update_fields=[
            'last_sync', 'sync_status', 'cached_crd_count', 'connection_status'
        ])
        
        return fabric
```

### 5.2 Concurrent Access Protection

```python
from django.core.cache import cache
import redis_lock

class ConcurrencyManager:
    """Prevents concurrent sync operations on same fabric"""
    
    def __init__(self, fabric_id: int):
        self.fabric_id = fabric_id
        self.lock_key = f"fabric_sync_lock_{fabric_id}"
        
    def acquire_sync_lock(self, timeout: int = 300) -> bool:
        """Acquire exclusive sync lock for fabric"""
        
        return cache.add(self.lock_key, True, timeout=timeout)
        
    def release_sync_lock(self):
        """Release sync lock"""
        cache.delete(self.lock_key)
        
    def with_sync_lock(self, func, *args, **kwargs):
        """Execute function with sync lock"""
        
        if not self.acquire_sync_lock():
            raise SyncLockError(f"Fabric {self.fabric_id} sync already in progress")
        
        try:
            return func(*args, **kwargs)
        finally:
            self.release_sync_lock()
```

## 6. Error Handling and Recovery

### 6.1 RQ Job Error Handling

```python
from rq import Worker
from rq.job import Job

class RQSyncJobHandler:
    """Custom RQ job error handling for sync operations"""
    
    @staticmethod
    def handle_job_failure(job: Job, exception: Exception, traceback: str, worker: Worker):
        """Handle RQ job failures with fabric-specific recovery"""
        
        # Extract fabric_id from job args
        fabric_id = job.args[0] if job.args else None
        
        if fabric_id:
            fabric = HedgehogFabric.objects.get(id=fabric_id)
            
            # Update fabric error state
            fabric.sync_status = 'error'
            fabric.sync_error = str(exception)
            fabric.save(update_fields=['sync_status', 'sync_error'])
            
            # Implement retry logic based on error type
            if isinstance(exception, (ConnectionError, TimeoutError)):
                # Retry with exponential backoff
                retry_delay = min(60 * (job.retry_count + 1), 300)  # Max 5 minutes
                
                get_scheduler('hedgehog_sync').schedule(
                    scheduled_time=datetime.utcnow() + timedelta(seconds=retry_delay),
                    func=job.func_name,
                    args=job.args,
                    job_id=f"retry_{job.id}_{job.retry_count + 1}"
                )
```

### 6.2 Health Check and Monitoring

```python
@system_job(interval=5)  # Every 5 minutes
def rq_scheduler_health_check():
    """Monitor RQ scheduler health and recover if needed"""
    
    scheduler = get_scheduler('hedgehog_schedule')
    
    # Check if scheduler is responsive
    if not scheduler.connection.ping():
        logger.error("RQ scheduler Redis connection lost")
        return {'status': 'error', 'message': 'Redis connection lost'}
    
    # Count active sync jobs
    active_jobs = len([job for job in scheduler.get_jobs() 
                       if job.id and job.id.startswith('fabric_sync_')])
    
    # Count expected jobs (enabled fabrics)
    expected_jobs = HedgehogFabric.objects.filter(
        scheduler_enabled=True, sync_enabled=True
    ).count()
    
    # Recover missing jobs if needed
    if active_jobs < expected_jobs:
        logger.warning(f"Missing sync jobs: {active_jobs}/{expected_jobs}")
        recovery_manager = SchedulerRecoveryManager()
        recovery_manager.initialize_scheduler_system()
    
    return {
        'status': 'healthy',
        'active_jobs': active_jobs,
        'expected_jobs': expected_jobs
    }
```

## 7. Integration with NetBox Patterns

### 7.1 Django Management Command

```python
# management/commands/rq_sync_scheduler.py
from django.core.management.base import BaseCommand
from netbox_hedgehog.schedulers.rq_scheduler import RQFabricSyncScheduler

class Command(BaseCommand):
    """Management command to control RQ-based fabric sync scheduler"""
    
    help = 'Manage RQ-based fabric sync scheduler'
    
    def add_arguments(self, parser):
        parser.add_argument('action', choices=['start', 'stop', 'status', 'reschedule'])
        parser.add_argument('--fabric-id', type=int, help='Specific fabric ID')
    
    def handle(self, *args, **options):
        scheduler = RQFabricSyncScheduler()
        
        if options['action'] == 'start':
            count = scheduler.reschedule_all_fabrics()
            self.stdout.write(f"Started scheduler for {count} fabrics")
            
        elif options['action'] == 'status':
            status = scheduler.get_scheduler_status()
            self.stdout.write(f"Scheduler status: {status}")
```

### 7.2 Admin Interface Integration

```python
# admin.py additions for RQ scheduler monitoring
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse

class HedgehogFabricAdmin(admin.ModelAdmin):
    """Enhanced admin with RQ scheduler controls"""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:fabric_id>/schedule-sync/',
                self.admin_site.admin_view(self.schedule_sync_view),
                name='hedgehogfabric_schedule_sync'
            ),
        ]
        return custom_urls + urls
    
    def schedule_sync_view(self, request, fabric_id):
        """Admin action to manually schedule fabric sync"""
        
        scheduler = RQFabricSyncScheduler()
        job_id = scheduler.schedule_fabric_sync(fabric_id)
        
        return JsonResponse({
            'success': True,
            'job_id': job_id,
            'message': f'Scheduled sync for fabric {fabric_id}'
        })
```

## 8. Testing and Validation Strategy

### 8.1 TDD Test Compatibility

```python
# tests/test_rq_scheduler.py
from django.test import TestCase
from django_rq import get_scheduler
from netbox_hedgehog.jobs.fabric_sync_jobs import FabricPeriodicSyncJob

class RQSchedulerTestCase(TestCase):
    """Test cases for RQ-based scheduler (compatible with existing TDD tests)"""
    
    def test_60_second_timing_precision(self):
        """Verify 60-second interval precision (addresses user's timing issue)"""
        
        scheduler = RQFabricSyncScheduler()
        fabric = self.create_test_fabric()
        
        # Schedule sync job
        job_id = scheduler.schedule_fabric_sync(fabric.id, interval=60)
        
        # Verify job scheduled with correct interval
        rq_scheduler = get_scheduler('hedgehog_schedule') 
        job = rq_scheduler.get_job(job_id)
        
        self.assertEqual(job.meta.get('interval'), 60)
        self.assertIsNotNone(job.scheduled_time)
    
    def test_fabric_sync_execution(self):
        """Test actual fabric sync execution via RQ job"""
        
        fabric = self.create_test_fabric()
        
        # Execute sync job directly
        job = FabricPeriodicSyncJob()
        result = job.run(fabric.id)
        
        # Verify sync completed and status updated
        fabric.refresh_from_db()
        self.assertEqual(fabric.sync_status, 'synced')
        self.assertIsNotNone(fabric.last_sync)
```

## 9. Migration Strategy from Celery

### 9.1 Migration Steps

1. **Phase 1**: Implement RQ jobs alongside existing Celery (dual system)
2. **Phase 2**: Migrate scheduler to use RQ jobs
3. **Phase 3**: Remove Celery configuration and tasks
4. **Phase 4**: Update documentation and deployment procedures

### 9.2 Migration Script

```python
# management/commands/migrate_celery_to_rq.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    """Migrate from Celery to RQ-based scheduling"""
    
    def handle(self, *args, **options):
        # Step 1: Stop Celery scheduler
        self.stdout.write("Stopping Celery beat scheduler...")
        
        # Step 2: Initialize RQ scheduler
        self.stdout.write("Initializing RQ scheduler...")
        recovery_manager = SchedulerRecoveryManager()
        recovery_manager.initialize_scheduler_system()
        
        # Step 3: Validate migration
        scheduler = RQFabricSyncScheduler()
        status = scheduler.get_scheduler_status()
        
        self.stdout.write(f"Migration completed: {status}")
```

## 10. Performance and Monitoring

### 10.1 Performance Requirements

- **Scheduler Precision**: < 1 second timing variance
- **Sync Job Execution**: < 60 seconds per fabric
- **Database Update**: < 5 seconds per fabric
- **Recovery Time**: < 30 seconds for failed jobs
- **Scalability**: Support 100+ fabrics with 60-second intervals

### 10.2 Monitoring Integration

```python
# monitoring/rq_metrics.py
class RQSchedulerMetrics:
    """Collect and expose RQ scheduler metrics"""
    
    def get_scheduler_metrics(self) -> Dict[str, Any]:
        """Get comprehensive scheduler metrics"""
        
        return {
            'active_jobs': self._count_active_jobs(),
            'failed_jobs': self._count_failed_jobs(),
            'avg_execution_time': self._calculate_avg_execution_time(),
            'timing_accuracy': self._measure_timing_accuracy(),
            'fabric_health_score': self._calculate_fabric_health_score()
        }
```

## 11. Deployment Configuration

### 11.1 RQ Worker Configuration

```bash
# Docker/systemd service for RQ workers
python manage.py rqworker hedgehog_sync hedgehog_schedule hedgehog_monitor --with-scheduler
```

### 11.2 Redis Configuration

```python
# NetBox configuration.py additions
RQ_QUEUES = {
    'hedgehog_sync': {
        'HOST': 'redis',
        'PORT': 6379,
        'DB': 1,  # Separate DB for fabric sync
        'DEFAULT_TIMEOUT': 300,  # 5 minutes
    },
    'hedgehog_schedule': {
        'HOST': 'redis', 
        'PORT': 6379,
        'DB': 2,  # Separate DB for scheduling
        'DEFAULT_TIMEOUT': 60,   # 1 minute
    }
}
```

## 12. Conclusion and Next Steps

### 12.1 Architecture Benefits

1. **NetBox Compatibility**: Full integration with NetBox's RQ system
2. **Timing Precision**: Addresses user's 60-second interval issue
3. **Scalability**: Supports multiple fabrics with independent scheduling
4. **Error Resilience**: Comprehensive error handling and recovery
5. **Monitoring**: Built-in health checks and performance metrics
6. **Testing**: Compatible with existing TDD test framework

### 12.2 Implementation Roadmap

1. **Week 1**: Implement basic RQ jobs and scheduler
2. **Week 2**: Add timing precision and error handling
3. **Week 3**: Migrate from Celery to RQ
4. **Week 4**: Testing, validation, and documentation

### 12.3 Critical Success Factors

- **Precise Timing**: Must resolve 60-second interval inconsistencies
- **NetBox Integration**: Must follow NetBox plugin patterns exactly
- **Backward Compatibility**: Must work with existing fabric models
- **Test Compatibility**: Must work with existing TDD test suite
- **Production Ready**: Must handle failures gracefully

---

This specification provides the complete architectural foundation for implementing an RQ-based periodic sync system that replaces the non-functional Celery implementation and addresses the user's timing issues while following NetBox best practices.