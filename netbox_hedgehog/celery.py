"""
Celery configuration for HNP background processing
High-performance async task processing for git sync, Kubernetes operations
"""

import os
from celery import Celery
from django.conf import settings

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

app = Celery('hedgehog_netbox_plugin')

# Load configuration from Django settings with 'CELERY_' prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all Django apps
app.autodiscover_tasks()

# Configure task routes for optimal performance
app.conf.update(
    # Task routing for queue specialization - Enhanced for Phase 2 Scheduler
    task_routes={
        # Master Scheduler (Priority Queue)
        'netbox_hedgehog.tasks.master_sync_scheduler': {'queue': 'scheduler_master', 'priority': 10},
        
        # Git Operations (Optimized for concurrent Git operations)
        'netbox_hedgehog.tasks.git_sync_fabric': {'queue': 'sync_git', 'priority': 8},
        'netbox_hedgehog.tasks.git_validate_repository': {'queue': 'sync_git', 'priority': 6},
        'netbox_hedgehog.tasks.git_sync_all_fabrics': {'queue': 'sync_orchestration', 'priority': 7},
        
        # Kubernetes Operations (Optimized for K8s API calls)
        'netbox_hedgehog.tasks.kubernetes_sync_fabric': {'queue': 'sync_kubernetes', 'priority': 8},
        'netbox_hedgehog.tasks.kubernetes_watch_fabric': {'queue': 'sync_kubernetes', 'priority': 6},
        'netbox_hedgehog.tasks.detect_fabric_drift': {'queue': 'sync_kubernetes', 'priority': 5},
        
        # Micro-tasks (Fast execution queue)
        'netbox_hedgehog.tasks.update_fabric_status': {'queue': 'sync_micro', 'priority': 9},
        'netbox_hedgehog.tasks.refresh_fabric_cache': {'queue': 'sync_micro', 'priority': 7},
        
        # Orchestration Tasks (Coordination queue)
        'netbox_hedgehog.tasks.check_fabric_sync_schedules': {'queue': 'sync_orchestration', 'priority': 6},
        'netbox_hedgehog.tasks.get_scheduler_metrics': {'queue': 'sync_orchestration', 'priority': 4},
        'netbox_hedgehog.tasks.reset_scheduler_metrics': {'queue': 'sync_orchestration', 'priority': 3},
        
        # Legacy/Other Tasks (Backward compatibility)
        'netbox_hedgehog.tasks.process_crd_events': {'queue': 'events'},
        'netbox_hedgehog.tasks.validate_fabric_config': {'queue': 'validation'},
    },
    
    # Worker optimization - Enhanced for Phase 2 Scheduler
    worker_prefetch_multiplier=3,  # Increased for better throughput
    task_acks_late=True,
    worker_disable_rate_limits=True,
    worker_max_tasks_per_child=1000,  # Prevent memory leaks
    
    # Task priority support
    task_inherit_parent_priority=True,
    task_default_priority=5,
    worker_hijack_root_logger=False,
    
    # Result backend optimization
    result_expires=1800,  # 30 minutes (shorter for faster cleanup)
    result_compression='gzip',
    result_persistent=True,  # Persist results for orchestration
    
    # Monitoring and visibility
    task_send_sent_event=True,
    task_track_started=True,
    
    # Error handling
    task_reject_on_worker_lost=True,
    task_acks_on_failure_or_timeout=True,
    task_soft_time_limit=25,  # 25 seconds soft limit for micro-tasks
    task_time_limit=35,       # 35 seconds hard limit
    
    # Enhanced routing and concurrency
    task_routes_priorities=True,  # Enable priority routing
    worker_pool_restarts=True,    # Enable pool restarts for reliability
)

# Queue configurations - Phase 2 Enhanced Scheduler Queues
app.conf.task_create_missing_queues = True
app.conf.task_queue_max_priority = 10

# Define specialized queues with concurrency settings for optimal performance
SCHEDULER_QUEUE_CONFIG = {
    # Master Scheduler Queue (Single worker, highest priority)
    'scheduler_master': {
        'exchange': 'scheduler_master',
        'routing_key': 'scheduler_master',
        'concurrency': 1,      # Single master scheduler instance
        'priority': 10
    },
    
    # Git Sync Queue (Optimized for Git operations)
    'sync_git': {
        'exchange': 'sync_git', 
        'routing_key': 'sync_git',
        'concurrency': 4,      # Multiple Git operations in parallel
        'priority': 8
    },
    
    # Kubernetes Sync Queue (Optimized for K8s API calls)
    'sync_kubernetes': {
        'exchange': 'sync_kubernetes',
        'routing_key': 'sync_kubernetes', 
        'concurrency': 3,      # K8s API rate limiting consideration
        'priority': 8
    },
    
    # Micro-tasks Queue (Fast execution, high concurrency)
    'sync_micro': {
        'exchange': 'sync_micro',
        'routing_key': 'sync_micro',
        'concurrency': 8,      # High concurrency for fast tasks
        'priority': 9
    },
    
    # Orchestration Queue (Coordination tasks)
    'sync_orchestration': {
        'exchange': 'sync_orchestration',
        'routing_key': 'sync_orchestration',
        'concurrency': 2,      # Limited orchestration tasks
        'priority': 6
    }
}

# Apply queue-specific configurations
for queue_name, config in SCHEDULER_QUEUE_CONFIG.items():
    # Set prefetch multiplier based on queue type
    if queue_name == 'sync_micro':
        app.conf.task_annotations = app.conf.get('task_annotations', {})
        app.conf.task_annotations.update({
            f'*:{queue_name}': {
                'rate_limit': '100/s',  # High rate limit for micro-tasks
                'time_limit': 30,       # 30 second limit
                'soft_time_limit': 25   # 25 second soft limit
            }
        })
    elif queue_name == 'scheduler_master':
        app.conf.task_annotations = app.conf.get('task_annotations', {})
        app.conf.task_annotations.update({
            f'*:{queue_name}': {
                'rate_limit': '1/m',    # One scheduler run per minute
                'time_limit': 90,       # 90 second limit for full cycle
                'soft_time_limit': 75   # 75 second soft limit
            }
        })

# Performance monitoring
@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery performance"""
    print(f'Request: {self.request!r}')

# Beat schedule for periodic tasks - Enhanced Phase 2 Scheduler
app.conf.beat_schedule = {
    # MASTER SYNC SCHEDULER - Phase 2 Core (60-second cycle)
    'master-sync-scheduler': {
        'task': 'netbox_hedgehog.tasks.master_sync_scheduler',
        'schedule': 60.0,  # Master 60-second cycle
        'options': {'queue': 'scheduler_master', 'priority': 10}
    },
    
    # Legacy fabric sync checker (fallback - now runs less frequently)
    'check-fabric-sync-intervals': {
        'task': 'netbox_hedgehog.tasks.check_fabric_sync_schedules',
        'schedule': 300.0,  # Every 5 minutes (reduced from 60s)
        'options': {'queue': 'sync_orchestration', 'priority': 6}
    },
    
    # Performance metrics collection
    'collect-performance-metrics': {
        'task': 'netbox_hedgehog.tasks.collect_performance_metrics',
        'schedule': 60.0,  # 1 minute
        'options': {'queue': 'sync_micro', 'priority': 4}
    },
    
    # Health check for Kubernetes connections
    'kubernetes-health-check': {
        'task': 'netbox_hedgehog.tasks.check_kubernetes_health',
        'schedule': 180.0,  # 3 minutes (reduced frequency)
        'options': {'queue': 'sync_kubernetes', 'priority': 7}
    },
    
    # Cache maintenance (less frequent due to smarter caching)
    'refresh-fabric-caches': {
        'task': 'netbox_hedgehog.tasks.refresh_all_fabric_caches',
        'schedule': 900.0,  # 15 minutes (reduced from 5 minutes)
        'options': {'queue': 'sync_micro', 'priority': 3}
    },
    
    # Clean up old events every hour
    'cleanup-old-events': {
        'task': 'netbox_hedgehog.tasks.cleanup_old_events',
        'schedule': 3600.0,  # 1 hour
        'options': {'queue': 'sync_micro', 'priority': 2}
    },
    
    # Scheduler metrics collection for monitoring
    'collect-scheduler-metrics': {
        'task': 'netbox_hedgehog.tasks.get_scheduler_metrics',
        'schedule': 300.0,  # 5 minutes
        'options': {'queue': 'sync_orchestration', 'priority': 4}
    },
}

app.conf.timezone = 'UTC'

# Signal handlers for performance monitoring
from celery.signals import task_prerun, task_postrun, task_failure
import time
import logging

logger = logging.getLogger('netbox_hedgehog.performance')

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Log task start for performance monitoring"""
    logger.info(f"Task {task.name} [{task_id}] starting")

@task_postrun.connect  
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Log task completion for performance monitoring"""
    logger.info(f"Task {task.name} [{task_id}] completed with state: {state}")

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Log task failures for monitoring"""
    logger.error(f"Task {sender.name} [{task_id}] failed: {exception}")