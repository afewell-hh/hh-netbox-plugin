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
    # Task routing for queue specialization
    task_routes={
        'netbox_hedgehog.tasks.git_sync_fabric': {'queue': 'git_sync'},
        'netbox_hedgehog.tasks.kubernetes_watch_fabric': {'queue': 'kubernetes'},
        'netbox_hedgehog.tasks.refresh_fabric_cache': {'queue': 'cache_refresh'},
        'netbox_hedgehog.tasks.process_crd_events': {'queue': 'events'},
        'netbox_hedgehog.tasks.validate_fabric_config': {'queue': 'validation'},
        'netbox_hedgehog.tasks.update_fabric_status': {'queue': 'status_updates'},
    },
    
    # Worker optimization
    worker_prefetch_multiplier=2,
    task_acks_late=True,
    worker_disable_rate_limits=True,
    
    # Task priority support
    task_inherit_parent_priority=True,
    task_default_priority=5,
    worker_hijack_root_logger=False,
    
    # Result backend optimization
    result_expires=3600,  # 1 hour
    result_compression='gzip',
    
    # Monitoring and visibility
    task_send_sent_event=True,
    task_track_started=True,
    
    # Error handling
    task_reject_on_worker_lost=True,
    task_acks_on_failure_or_timeout=True,
)

# Queue configurations
app.conf.task_create_missing_queues = True
app.conf.task_queue_max_priority = 10

# Performance monitoring
@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery performance"""
    print(f'Request: {self.request!r}')

# Beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Refresh fabric caches every 5 minutes
    'refresh-fabric-caches': {
        'task': 'netbox_hedgehog.tasks.refresh_all_fabric_caches',
        'schedule': 300.0,  # 5 minutes
        'options': {'queue': 'cache_refresh', 'priority': 3}
    },
    
    # Health check for Kubernetes connections every 2 minutes
    'kubernetes-health-check': {
        'task': 'netbox_hedgehog.tasks.check_kubernetes_health',
        'schedule': 120.0,  # 2 minutes
        'options': {'queue': 'kubernetes', 'priority': 7}
    },
    
    # Clean up old events every hour
    'cleanup-old-events': {
        'task': 'netbox_hedgehog.tasks.cleanup_old_events',
        'schedule': 3600.0,  # 1 hour
        'options': {'queue': 'cache_refresh', 'priority': 2}
    },
    
    # Performance metrics collection every minute
    'collect-performance-metrics': {
        'task': 'netbox_hedgehog.tasks.collect_performance_metrics',
        'schedule': 60.0,  # 1 minute
        'options': {'queue': 'status_updates', 'priority': 4}
    },
    
    # Check fabric sync intervals every minute
    'check-fabric-sync-intervals': {
        'task': 'netbox_hedgehog.tasks.check_fabric_sync_schedules',
        'schedule': 60.0,  # Check every minute
        'options': {'queue': 'git_sync', 'priority': 6}
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