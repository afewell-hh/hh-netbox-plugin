"""
Status Sync Tasks - Phase 2 Unified Status Synchronization Framework

Celery tasks for real-time status propagation, consistency validation,
and automated status synchronization across all fabric components.

Architecture:
- Real-time status propagation with <5 second delay target
- Automated consistency validation and correction
- Batch status processing for performance optimization
- Integration with event-driven architecture
"""

import logging
import time
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from celery import shared_task, group, chord
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone as django_timezone

from ..models.fabric import HedgehogFabric
from ..services.status_sync_service import get_status_sync_service, StatusUpdateRequest
from ..tasks.status_reconciliation import (
    StatusReconciliationService, StatusType, StatusState, reconcile_fabric_status
)
from ..application.services.event_service import EventService
from ..domain.interfaces.event_service_interface import EventPriority

logger = logging.getLogger('netbox_hedgehog.status_sync_tasks')
performance_logger = logging.getLogger('netbox_hedgehog.performance')

@shared_task(bind=True, name='netbox_hedgehog.tasks.propagate_status_update')
def propagate_status_update(self, fabric_id: int, status_type: str, new_state: str, 
                          message: str = "", metadata: Optional[Dict[str, Any]] = None,
                          priority: str = "normal") -> Dict[str, Any]:
    """
    Real-time status update propagation task
    Target: <5 second propagation delay
    """
    start_time = time.time()
    
    try:
        # Convert string parameters back to enum types
        status_type_enum = StatusType(status_type)
        state_enum = StatusState(new_state)
        priority_enum = EventPriority(priority)
        
        # Create status update request
        request = StatusUpdateRequest(
            fabric_id=fabric_id,
            status_type=status_type_enum,
            new_state=state_enum,
            message=message,
            metadata=metadata or {},
            source="propagation_task",
            priority=priority_enum
        )
        
        # Get status sync service and process update
        status_sync_service = get_status_sync_service()
        
        # Run async update in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(status_sync_service.update_status(request))
            propagation_delay = time.time() - start_time
            
            # Log performance metrics
            if propagation_delay > 5.0:  # Target is <5 seconds
                performance_logger.warning(
                    f"Status propagation exceeded target delay: {propagation_delay:.2f}s for fabric {fabric_id}"
                )
            else:
                performance_logger.debug(
                    f"Status propagated in {propagation_delay:.2f}s for fabric {fabric_id}"
                )
            
            return {
                'success': result['success'],
                'message': result.get('message', 'Status propagated'),
                'propagation_delay': propagation_delay,
                'fabric_id': fabric_id,
                'status_type': status_type,
                'new_state': new_state
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        propagation_delay = time.time() - start_time
        logger.error(f"Status propagation failed for fabric {fabric_id}: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'propagation_delay': propagation_delay,
            'fabric_id': fabric_id
        }

@shared_task(bind=True, name='netbox_hedgehog.tasks.batch_propagate_status_updates')
def batch_propagate_status_updates(self, update_requests: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Batch process multiple status updates for performance optimization
    """
    start_time = time.time()
    
    try:
        if not update_requests:
            return {
                'success': True,
                'message': 'No updates to process',
                'batch_size': 0,
                'execution_time': 0.0
            }
        
        # Convert dict requests to StatusUpdateRequest objects
        status_requests = []
        for req_dict in update_requests:
            try:
                request = StatusUpdateRequest(
                    fabric_id=req_dict['fabric_id'],
                    status_type=StatusType(req_dict['status_type']),
                    new_state=StatusState(req_dict['new_state']),
                    message=req_dict.get('message', ''),
                    metadata=req_dict.get('metadata', {}),
                    source=req_dict.get('source', 'batch_task'),
                    priority=EventPriority(req_dict.get('priority', 'normal'))
                )
                status_requests.append(request)
            except Exception as e:
                logger.error(f"Failed to parse status update request: {e}")
        
        if not status_requests:
            return {
                'success': False,
                'error': 'No valid requests to process',
                'batch_size': len(update_requests)
            }
        
        # Process batch update
        status_sync_service = get_status_sync_service()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                status_sync_service.batch_update_status(status_requests)
            )
            
            execution_time = time.time() - start_time
            
            # Update performance metrics
            avg_delay = execution_time / len(status_requests)
            if avg_delay > 1.0:  # Target is <1 second per update in batch
                performance_logger.warning(
                    f"Batch status update average delay: {avg_delay:.2f}s per update"
                )
            
            return {
                'success': result['success'],
                'message': result.get('message', 'Batch status updates completed'),
                'batch_size': len(status_requests),
                'successful_updates': result.get('successful_fabrics', 0),
                'execution_time': execution_time,
                'avg_delay_per_update': avg_delay
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Batch status update failed: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'batch_size': len(update_requests),
            'execution_time': execution_time
        }

@shared_task(bind=True, name='netbox_hedgehog.tasks.validate_fabric_status_consistency')
def validate_fabric_status_consistency(self, fabric_id: int, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Validate status consistency for a specific fabric
    """
    start_time = time.time()
    
    try:
        status_sync_service = get_status_sync_service()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            validation_result = loop.run_until_complete(
                status_sync_service.validate_status_consistency(fabric_id, force_refresh)
            )
            
            execution_time = time.time() - start_time
            
            # If inconsistencies found, trigger reconciliation
            if not validation_result.is_consistent:
                logger.warning(
                    f"Status inconsistencies detected for fabric {fabric_id}: "
                    f"{len(validation_result.inconsistencies)} issues"
                )
                
                # Queue reconciliation task for high-priority inconsistencies
                if len(validation_result.inconsistencies) > 2:
                    reconcile_fabric_status.delay(fabric_id)
                    logger.info(f"Queued reconciliation for fabric {fabric_id}")
            
            return {
                'success': True,
                'fabric_id': fabric_id,
                'is_consistent': validation_result.is_consistent,
                'inconsistencies_count': len(validation_result.inconsistencies),
                'recommendations_count': len(validation_result.recommendations),
                'execution_time': execution_time,
                'inconsistencies': validation_result.inconsistencies[:5],  # Limit for response size
                'recommendations': validation_result.recommendations[:3]
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Status consistency validation failed for fabric {fabric_id}: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'fabric_id': fabric_id,
            'execution_time': execution_time
        }

@shared_task(name='netbox_hedgehog.tasks.validate_all_fabric_status_consistency')
def validate_all_fabric_status_consistency(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Validate status consistency for all active fabrics
    """
    start_time = time.time()
    
    try:
        # Get all active fabrics
        active_fabrics = HedgehogFabric.objects.filter(
            status__in=['active', 'planned'],
            sync_enabled=True
        ).values_list('id', flat=True)
        
        if not active_fabrics:
            return {
                'success': True,
                'message': 'No active fabrics to validate',
                'fabrics_count': 0,
                'execution_time': time.time() - start_time
            }
        
        # Create validation tasks for each fabric
        validation_jobs = []
        for fabric_id in active_fabrics:
            job = validate_fabric_status_consistency.delay(fabric_id, force_refresh)
            validation_jobs.append(job.id)
        
        execution_time = time.time() - start_time
        
        return {
            'success': True,
            'message': f'Queued consistency validation for {len(active_fabrics)} fabrics',
            'fabrics_count': len(active_fabrics),
            'validation_jobs': validation_jobs,
            'execution_time': execution_time
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Failed to validate all fabric status consistency: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'execution_time': execution_time
        }

@shared_task(bind=True, name='netbox_hedgehog.tasks.real_time_status_monitor')
def real_time_status_monitor(self, monitoring_duration: int = 300) -> Dict[str, Any]:
    """
    Real-time status monitoring task
    Monitors status changes and triggers reconciliation when needed
    """
    start_time = time.time()
    monitoring_end = start_time + monitoring_duration
    
    try:
        status_sync_service = get_status_sync_service()
        event_service = EventService()
        
        monitoring_stats = {
            'status_updates_detected': 0,
            'reconciliations_triggered': 0,
            'consistency_checks': 0,
            'errors_detected': 0
        }
        
        logger.info(f"Starting real-time status monitoring for {monitoring_duration} seconds")
        
        # Monitor status changes in real-time
        while time.time() < monitoring_end:
            try:
                # Get active fabrics that might need monitoring
                active_fabrics = list(HedgehogFabric.objects.filter(
                    status__in=['active', 'planned'],
                    sync_enabled=True
                ).values_list('id', 'name', 'sync_status', 'connection_status')[:20])  # Limit for performance
                
                for fabric_id, fabric_name, sync_status, connection_status in active_fabrics:
                    try:
                        # Quick consistency check
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        try:
                            validation_result = loop.run_until_complete(
                                status_sync_service.validate_status_consistency(fabric_id)
                            )
                            
                            monitoring_stats['consistency_checks'] += 1
                            
                            # If inconsistencies detected, trigger reconciliation
                            if not validation_result.is_consistent:
                                logger.debug(f"Inconsistencies detected for fabric {fabric_name}")
                                reconcile_fabric_status.delay(fabric_id)
                                monitoring_stats['reconciliations_triggered'] += 1
                            
                            # Check for error states
                            if sync_status == 'error' or connection_status == 'error':
                                monitoring_stats['errors_detected'] += 1
                            
                        finally:
                            loop.close()
                            
                    except Exception as e:
                        logger.debug(f"Monitoring check failed for fabric {fabric_name}: {e}")
                
                # Sleep between monitoring cycles
                time.sleep(10)  # 10 second intervals
                
            except Exception as e:
                logger.error(f"Status monitoring cycle failed: {e}")
                time.sleep(5)  # Shorter sleep on errors
        
        execution_time = time.time() - start_time
        
        logger.info(f"Real-time status monitoring completed: {monitoring_stats}")
        
        return {
            'success': True,
            'message': f'Status monitoring completed after {execution_time:.1f}s',
            'monitoring_duration': execution_time,
            'stats': monitoring_stats
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Real-time status monitoring failed: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'execution_time': execution_time
        }

@shared_task(name='netbox_hedgehog.tasks.cleanup_stale_status_data')
def cleanup_stale_status_data(max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Cleanup stale status data and cache entries
    """
    start_time = time.time()
    
    try:
        cutoff_time = django_timezone.now() - timedelta(hours=max_age_hours)
        cleanup_stats = {
            'cache_keys_cleared': 0,
            'stale_fabrics_updated': 0
        }
        
        # Clean up stale cache entries
        cache_patterns = [
            'status_update_*',
            'last_update_*',
            'fabric_status_*',
            'validation_result_*'
        ]
        
        # Note: Redis-specific cache cleanup would need specific implementation
        # For now, we'll focus on fabric status updates
        
        # Update stale fabric status
        stale_fabrics = HedgehogFabric.objects.filter(
            modified__lt=cutoff_time,
            sync_status__in=['syncing', 'stale']
        )
        
        for fabric in stale_fabrics:
            try:
                # Update to stale status if appropriate
                if fabric.sync_status == 'syncing':
                    fabric.sync_status = 'stale'
                    fabric.save(update_fields=['sync_status'])
                    cleanup_stats['stale_fabrics_updated'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to update stale fabric {fabric.id}: {e}")
        
        execution_time = time.time() - start_time
        
        return {
            'success': True,
            'message': f'Cleanup completed in {execution_time:.1f}s',
            'execution_time': execution_time,
            'stats': cleanup_stats
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Status data cleanup failed: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'execution_time': execution_time
        }

@shared_task(name='netbox_hedgehog.tasks.get_status_sync_performance_metrics')
def get_status_sync_performance_metrics() -> Dict[str, Any]:
    """
    Get comprehensive performance metrics for status synchronization
    """
    try:
        status_sync_service = get_status_sync_service()
        sync_metrics = status_sync_service.get_sync_metrics()
        
        # Add fabric status distribution
        fabric_status_distribution = {}
        try:
            for status in ['synced', 'syncing', 'error', 'never_synced', 'stale']:
                count = HedgehogFabric.objects.filter(sync_status=status).count()
                fabric_status_distribution[status] = count
        except Exception as e:
            logger.error(f"Failed to get fabric status distribution: {e}")
        
        # Add connection status distribution
        connection_status_distribution = {}
        try:
            for status in ['connected', 'error', 'unknown']:
                count = HedgehogFabric.objects.filter(connection_status=status).count()
                connection_status_distribution[status] = count
        except Exception as e:
            logger.error(f"Failed to get connection status distribution: {e}")
        
        return {
            'success': True,
            'sync_metrics': sync_metrics,
            'fabric_status_distribution': fabric_status_distribution,
            'connection_status_distribution': connection_status_distribution,
            'last_updated': django_timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get status sync performance metrics: {e}")
        return {
            'success': False,
            'error': str(e),
            'last_updated': django_timezone.now().isoformat()
        }

# Periodic tasks configuration helper
def setup_periodic_status_sync_tasks():
    """
    Setup periodic tasks for status synchronization
    Called during application initialization
    """
    try:
        from django_celery_beat.models import PeriodicTask, IntervalSchedule
        
        # Create interval schedules
        every_5_minutes, _ = IntervalSchedule.objects.get_or_create(
            every=5, period=IntervalSchedule.MINUTES
        )
        every_15_minutes, _ = IntervalSchedule.objects.get_or_create(
            every=15, period=IntervalSchedule.MINUTES
        )
        every_hour, _ = IntervalSchedule.objects.get_or_create(
            every=1, period=IntervalSchedule.HOURS
        )
        
        # Status consistency validation (every 15 minutes)
        PeriodicTask.objects.get_or_create(
            name='Validate All Fabric Status Consistency',
            defaults={
                'task': 'netbox_hedgehog.tasks.validate_all_fabric_status_consistency',
                'interval': every_15_minutes,
                'args': json.dumps([False]),  # force_refresh=False
                'enabled': True,
            }
        )
        
        # Cleanup stale status data (every hour)
        PeriodicTask.objects.get_or_create(
            name='Cleanup Stale Status Data',
            defaults={
                'task': 'netbox_hedgehog.tasks.cleanup_stale_status_data',
                'interval': every_hour,
                'args': json.dumps([24]),  # max_age_hours=24
                'enabled': True,
            }
        )
        
        logger.info("Periodic status sync tasks configured successfully")
        
    except Exception as e:
        logger.error(f"Failed to setup periodic status sync tasks: {e}")

# Helper function to convert status enums to strings for Celery serialization
def create_status_update_dict(fabric_id: int, status_type: StatusType, new_state: StatusState,
                            message: str = "", metadata: Optional[Dict[str, Any]] = None,
                            priority: EventPriority = EventPriority.NORMAL) -> Dict[str, Any]:
    """
    Helper function to create serializable status update dictionary for Celery tasks
    """
    return {
        'fabric_id': fabric_id,
        'status_type': status_type.value,
        'new_state': new_state.value,
        'message': message,
        'metadata': metadata or {},
        'priority': priority.value,
        'source': 'helper_function'
    }