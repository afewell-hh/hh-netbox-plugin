"""
Celery tasks for Git synchronization operations
Optimized for <30 second sync times with progress tracking
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import timedelta
from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from ..application.services.git_service import GitService
from ..application.services.event_service import EventService
from ..models.fabric import HedgehogFabric
from ..domain.interfaces.event_service_interface import EventPriority

logger = logging.getLogger('netbox_hedgehog.performance')

@shared_task(bind=True, name='netbox_hedgehog.tasks.git_sync_fabric')
def git_sync_fabric(self, fabric_id: int, force: bool = False) -> Dict[str, Any]:
    """
    Perform Git sync for a fabric with real-time progress tracking
    Target: <30 seconds for large repositories
    """
    start_time = time.time()
    fabric = None
    event_service = EventService()
    
    try:
        # Get fabric and validate
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        logger.info(f"Starting Git sync for fabric {fabric.name} [{fabric_id}]")
        
        # Publish start event
        event_service.publish_sync_event(
            fabric_id=fabric_id,
            event_type='started',
            progress=0,
            message=f"Starting Git sync for {fabric.name}"
        )
        
        # Initialize git service
        git_service = GitService()
        
        # Check if sync is already in progress
        sync_key = f"git_sync_in_progress_{fabric_id}"
        if cache.get(sync_key) and not force:
            return {
                'success': False,
                'message': 'Sync already in progress',
                'duration': 0
            }
        
        # Mark sync as in progress
        cache.set(sync_key, True, timeout=1800)  # 30 minutes timeout
        
        try:
            # Progress: 10% - Repository preparation
            event_service.publish_sync_event(
                fabric_id=fabric_id,
                event_type='progress',
                progress=10,
                message="Preparing repository access"
            )
            
            # Prepare repository with timeout
            repo_result = git_service.prepare_repository(
                fabric=fabric,
                timeout=10  # 10 second timeout for repo prep
            )
            
            if not repo_result.success:
                raise Exception(f"Repository preparation failed: {repo_result.message}")
            
            # Progress: 30% - Fetching changes
            event_service.publish_sync_event(
                fabric_id=fabric_id,
                event_type='progress',
                progress=30,
                message="Fetching latest changes"
            )
            
            # Fetch with progress callback
            fetch_result = git_service.fetch_changes(
                fabric=fabric,
                progress_callback=lambda pct, msg: _publish_progress(
                    event_service, fabric_id, 30 + (pct * 0.4), msg
                )
            )
            
            if not fetch_result.success:
                raise Exception(f"Fetch failed: {fetch_result.message}")
            
            # Progress: 70% - Processing CRDs
            event_service.publish_sync_event(
                fabric_id=fabric_id,
                event_type='progress',
                progress=70,
                message="Processing CRDs"
            )
            
            # Process CRDs with batching for performance
            crd_result = git_service.process_crds_batch(
                fabric=fabric,
                batch_size=50,  # Process 50 CRDs at a time
                progress_callback=lambda pct, msg: _publish_progress(
                    event_service, fabric_id, 70 + (pct * 0.25), msg
                )
            )
            
            if not crd_result.success:
                raise Exception(f"CRD processing failed: {crd_result.message}")
            
            # Progress: 95% - Finalizing
            event_service.publish_sync_event(
                fabric_id=fabric_id,
                event_type='progress',
                progress=95,
                message="Finalizing sync"
            )
            
            # Update fabric status
            with transaction.atomic():
                fabric.sync_status = 'synced'
                fabric.last_sync = timezone.now()
                fabric.save(update_fields=['sync_status', 'last_sync'])
            
            # Clear cache to force refresh
            cache.delete_many([
                f"fabric_crds_{fabric_id}",
                f"fabric_status_{fabric_id}",
                f"fabric_metrics_{fabric_id}"
            ])
            
            duration = time.time() - start_time
            
            # Progress: 100% - Complete
            event_service.publish_sync_event(
                fabric_id=fabric_id,
                event_type='completed',
                progress=100,
                message=f"Sync completed in {duration:.1f}s",
                data={
                    'duration': duration,
                    'crds_processed': crd_result.data.get('count', 0),
                    'changes_detected': crd_result.data.get('changes', 0)
                }
            )
            
            logger.info(f"Git sync completed for fabric {fabric.name} in {duration:.2f}s")
            
            return {
                'success': True,
                'message': f"Sync completed successfully in {duration:.1f}s",
                'duration': duration,
                'crds_processed': crd_result.data.get('count', 0)
            }
            
        finally:
            # Always clear the in-progress flag
            cache.delete(sync_key)
            
    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        
        logger.error(f"Git sync failed for fabric {fabric_id}: {error_msg}")
        
        # Publish failure event
        event_service.publish_sync_event(
            fabric_id=fabric_id,
            event_type='failed',
            progress=0,
            message=f"Sync failed: {error_msg}",
            data={'error': error_msg, 'duration': duration}
        )
        
        return {
            'success': False,
            'message': f"Sync failed: {error_msg}",
            'duration': duration
        }

@shared_task(name='netbox_hedgehog.tasks.git_sync_all_fabrics')
def git_sync_all_fabrics(force: bool = False) -> Dict[str, Any]:
    """
    Sync all active fabrics in parallel
    Uses Celery group for concurrent execution
    """
    from celery import group
    
    active_fabrics = HedgehogFabric.objects.filter(
        status='active',
        git_repository_url__isnull=False
    ).values_list('id', flat=True)
    
    if not active_fabrics:
        return {'success': True, 'message': 'No active fabrics to sync', 'count': 0}
    
    # Create parallel sync jobs
    job = group(git_sync_fabric.s(fabric_id, force) for fabric_id in active_fabrics)
    result = job.apply_async()
    
    logger.info(f"Started parallel Git sync for {len(active_fabrics)} fabrics")
    
    return {
        'success': True,
        'message': f"Started sync for {len(active_fabrics)} fabrics",
        'count': len(active_fabrics),
        'job_id': result.id
    }

@shared_task(name='netbox_hedgehog.tasks.git_validate_repository')
def git_validate_repository(fabric_id: int) -> Dict[str, Any]:
    """
    Validate Git repository configuration and connectivity
    Fast validation task for immediate feedback
    """
    try:
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        git_service = GitService()
        
        # Quick connectivity test
        validation_result = git_service.validate_repository(fabric)
        
        # Cache validation result
        cache.set(
            f"git_validation_{fabric_id}",
            validation_result.to_dict(),
            timeout=300  # 5 minutes
        )
        
        return {
            'success': validation_result.success,
            'message': validation_result.message,
            'fabric_id': fabric_id,
            'details': validation_result.data
        }
        
    except Exception as e:
        logger.error(f"Git validation failed for fabric {fabric_id}: {e}")
        return {
            'success': False,
            'message': f"Validation failed: {str(e)}",
            'fabric_id': fabric_id
        }

def _publish_progress(event_service: EventService, fabric_id: int, 
                          progress: float, message: str):
    """Helper to publish progress events"""
    event_service.publish_sync_event(
        fabric_id=fabric_id,
        event_type='progress',
        progress=int(progress),
        message=message
    )

@shared_task(name='netbox_hedgehog.tasks.check_fabric_sync_schedules')
def check_fabric_sync_schedules() -> Dict[str, Any]:
    """
    Check all enabled fabrics for sync_interval timing and trigger syncs when due.
    Runs every 60 seconds via Celery Beat.
    """
    fabrics_needing_sync = []
    
    try:
        # Get all enabled fabrics
        enabled_fabrics = HedgehogFabric.objects.filter(sync_enabled=True)
        
        for fabric in enabled_fabrics:
            if should_sync_now(fabric):
                # Trigger sync using existing task
                git_sync_fabric.delay(fabric.id)
                fabrics_needing_sync.append(fabric.id)
                
    except Exception as e:
        # Log error but don't crash scheduler
        logger.error(f"Error in periodic sync scheduler: {e}")
        return {'error': str(e), 'synced_fabrics': []}
    
    return {
        'synced_fabrics': fabrics_needing_sync,
        'total_checked': enabled_fabrics.count() if 'enabled_fabrics' in locals() else 0,
        'timestamp': timezone.now().isoformat()
    }

def should_sync_now(fabric) -> bool:
    """Determine if fabric needs sync based on interval timing"""
    if not fabric.last_sync:
        # Never synced - sync immediately
        return True
        
    interval = timedelta(seconds=fabric.sync_interval or 300)  # Default 5 minutes
    time_since_last = timezone.now() - fabric.last_sync
    
    return time_since_last >= interval