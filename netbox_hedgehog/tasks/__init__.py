"""
Celery tasks package for HNP (Hedgehog NetBox Plugin)

Phase 2 Enhanced Periodic Sync Scheduler Tasks:
- Master Sync Scheduler with 60-second cycles  
- Fabric discovery and planning
- Micro-task architecture for sync operations
- Comprehensive error handling and recovery
"""

# Phase 2 Enhanced Scheduler Tasks
from .sync_scheduler import (
    master_sync_scheduler,
    update_fabric_status,
    kubernetes_sync_fabric,
    detect_fabric_drift,
    get_scheduler_metrics,
    reset_scheduler_metrics
)

# Git Sync Tasks (Existing + Enhanced)
from .git_sync_tasks import (
    git_sync_fabric,
    git_sync_all_fabrics,
    git_validate_repository,
    check_fabric_sync_schedules
)

# Cache Tasks (Existing)
from .cache_tasks import (
    refresh_fabric_cache,
    refresh_all_fabric_caches,
    warm_cache_for_fabric,
    cache_health_check
)

__all__ = [
    # Phase 2 Enhanced Scheduler Tasks
    'master_sync_scheduler',
    'update_fabric_status',
    'kubernetes_sync_fabric',
    'detect_fabric_drift',
    'get_scheduler_metrics',
    'reset_scheduler_metrics',
    
    # Git Sync Tasks
    'git_sync_fabric',
    'git_sync_all_fabrics',
    'git_validate_repository', 
    'check_fabric_sync_schedules',
    
    # Cache Tasks
    'refresh_fabric_cache',
    'refresh_all_fabric_caches',
    'warm_cache_for_fabric',
    'cache_health_check',
]