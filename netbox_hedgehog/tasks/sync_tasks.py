"""
Hedgehog NetBox Plugin - RQ Sync Tasks
Enhanced periodic sync with RQ-based task scheduling
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from django_rq import job
from django.utils import timezone
from django.db import transaction
from netbox_hedgehog.models import HedgehogFabric

logger = logging.getLogger(__name__)

@job('default', timeout=300)
def master_sync_scheduler():
    """
    Master sync scheduler - runs every 60 seconds to orchestrate fabric syncing.
    
    This is the main scheduler that:
    1. Identifies fabrics that need syncing
    2. Queues individual fabric sync tasks
    3. Tracks scheduler metrics and performance
    
    Returns:
        Dict with scheduler execution results
    """
    start_time = timezone.now()
    results = {
        'scheduler_run_id': f"scheduler_{start_time.strftime('%Y%m%d_%H%M%S')}",
        'start_time': start_time,
        'fabrics_processed': 0,
        'fabrics_queued': 0,
        'fabrics_skipped': 0,
        'errors': []
    }
    
    try:
        logger.info("🕐 Master sync scheduler starting...")
        
        # Get all fabrics that are enabled for scheduling
        fabrics = HedgehogFabric.objects.filter(
            sync_enabled=True,
            scheduler_enabled=True  # New field for enhanced scheduler
        )
        
        logger.info(f"📋 Found {fabrics.count()} enabled fabrics")
        
        for fabric in fabrics:
            results['fabrics_processed'] += 1
            
            try:
                # Check if fabric needs sync based on interval and last sync
                if fabric.needs_sync():
                    # Queue individual fabric sync task
                    sync_fabric_task.delay(fabric.id)
                    results['fabrics_queued'] += 1
                    
                    logger.info(f"⚡ Queued sync for fabric: {fabric.name}")
                    
                    # Update fabric's last scheduler run
                    fabric.last_scheduler_run = timezone.now()
                    fabric.save(update_fields=['last_scheduler_run'])
                    
                else:
                    results['fabrics_skipped'] += 1
                    logger.debug(f"⏭️ Skipped fabric {fabric.name} - not due for sync")
                    
            except Exception as e:
                error_msg = f"Error processing fabric {fabric.name}: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        results['end_time'] = timezone.now()
        results['duration_seconds'] = (results['end_time'] - start_time).total_seconds()
        
        logger.info(f"✅ Master scheduler completed: {results['fabrics_queued']} queued, {results['fabrics_skipped']} skipped")
        
        return results
        
    except Exception as e:
        error_msg = f"Master scheduler failed: {str(e)}"
        results['errors'].append(error_msg)
        results['end_time'] = timezone.now()
        logger.error(error_msg)
        
        return results

@job('default', timeout=600)
def sync_fabric_task(fabric_id: int):
    """
    Individual fabric sync task - performs actual Kubernetes sync for a single fabric.
    
    Args:
        fabric_id: ID of the fabric to sync
        
    Returns:
        Dict with sync results
    """
    start_time = timezone.now()
    results = {
        'task_id': f"sync_{fabric_id}_{start_time.strftime('%Y%m%d_%H%M%S')}",
        'fabric_id': fabric_id,
        'start_time': start_time,
        'success': False,
        'sync_type': 'kubernetes',
        'errors': []
    }
    
    try:
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        logger.info(f"🔄 Starting sync for fabric: {fabric.name}")
        
        # Add task to fabric's active tasks list
        fabric.add_active_sync_task(results['task_id'], 'kubernetes_sync', 300)
        
        # Import here to avoid circular imports
        from netbox_hedgehog.utils.kubernetes import KubernetesSync
        
        # Create sync client and execute sync
        k8s_sync = KubernetesSync(fabric)
        sync_result = k8s_sync.sync_all_crds()
        
        results['sync_result'] = sync_result
        results['success'] = sync_result.get('success', False)
        
        if results['success']:
            # Update fabric sync status
            with transaction.atomic():
                fabric.refresh_from_db()
                fabric.last_sync = timezone.now()
                fabric.sync_status = 'in_sync'
                fabric.sync_error = ''
                fabric.save(update_fields=['last_sync', 'sync_status', 'sync_error'])
            
            logger.info(f"✅ Sync completed successfully for fabric: {fabric.name}")
        else:
            # Handle sync failure
            error_msg = sync_result.get('error', 'Unknown sync error')
            results['errors'].append(error_msg)
            
            with transaction.atomic():
                fabric.refresh_from_db()
                fabric.sync_status = 'error'
                fabric.sync_error = error_msg
                fabric.save(update_fields=['sync_status', 'sync_error'])
            
            logger.error(f"❌ Sync failed for fabric {fabric.name}: {error_msg}")
        
        # Remove task from active tasks
        fabric.remove_active_sync_task(results['task_id'], results['success'])
        
        results['end_time'] = timezone.now()
        results['duration_seconds'] = (results['end_time'] - start_time).total_seconds()
        
        return results
        
    except HedgehogFabric.DoesNotExist:
        error_msg = f"Fabric with ID {fabric_id} not found"
        results['errors'].append(error_msg)
        logger.error(error_msg)
        
        results['end_time'] = timezone.now()
        return results
        
    except Exception as e:
        error_msg = f"Sync task failed for fabric ID {fabric_id}: {str(e)}"
        results['errors'].append(error_msg)
        logger.error(error_msg)
        
        # Try to update fabric error status
        try:
            fabric = HedgehogFabric.objects.get(id=fabric_id)
            fabric.sync_status = 'error'
            fabric.sync_error = error_msg
            fabric.save(update_fields=['sync_status', 'sync_error'])
            fabric.remove_active_sync_task(results['task_id'], False)
        except:
            pass  # Don't fail the task if we can't update status
        
        results['end_time'] = timezone.now()
        return results

@job('default', timeout=120)  
def collect_performance_metrics():
    """
    Collect performance metrics for the enhanced scheduler.
    
    Returns:
        Dict with collected metrics
    """
    start_time = timezone.now()
    
    try:
        metrics = {
            'collection_time': start_time,
            'scheduler_metrics': {},
            'fabric_metrics': {},
            'queue_metrics': {}
        }
        
        # Collect fabric-level metrics
        fabrics = HedgehogFabric.objects.all()
        
        total_fabrics = fabrics.count()
        enabled_fabrics = fabrics.filter(sync_enabled=True).count()
        scheduler_enabled_fabrics = fabrics.filter(scheduler_enabled=True).count()
        
        # Sync status breakdown
        status_counts = {}
        for fabric in fabrics:
            status = fabric.calculated_sync_status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        metrics['fabric_metrics'] = {
            'total_fabrics': total_fabrics,
            'sync_enabled': enabled_fabrics,
            'scheduler_enabled': scheduler_enabled_fabrics,
            'status_breakdown': status_counts
        }
        
        # Health score metrics
        health_scores = [fabric.calculate_scheduler_health_score() for fabric in fabrics]
        if health_scores:
            metrics['fabric_metrics']['health_scores'] = {
                'average': sum(health_scores) / len(health_scores),
                'min': min(health_scores),
                'max': max(health_scores)
            }
        
        logger.info(f"📊 Performance metrics collected: {enabled_fabrics}/{total_fabrics} enabled fabrics")
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to collect performance metrics: {str(e)}")
        return {
            'collection_time': start_time,
            'error': str(e)
        }

@job('default', timeout=60)
def check_kubernetes_health():
    """
    Check health of Kubernetes connections for all fabrics.
    
    Returns:
        Dict with health check results
    """
    start_time = timezone.now()
    health_results = {
        'check_time': start_time,
        'fabrics_checked': 0,
        'healthy_fabrics': 0,
        'unhealthy_fabrics': 0,
        'fabric_details': []
    }
    
    try:
        fabrics = HedgehogFabric.objects.filter(sync_enabled=True)
        
        for fabric in fabrics:
            health_results['fabrics_checked'] += 1
            
            try:
                # Import here to avoid circular imports
                from netbox_hedgehog.utils.kubernetes import KubernetesSync
                
                k8s_sync = KubernetesSync(fabric)
                connection_test = k8s_sync.test_connection()
                
                if connection_test.get('success', False):
                    health_results['healthy_fabrics'] += 1
                    fabric.connection_status = 'connected'
                    fabric.connection_error = ''
                else:
                    health_results['unhealthy_fabrics'] += 1
                    fabric.connection_status = 'error'
                    fabric.connection_error = connection_test.get('error', 'Connection test failed')
                
                fabric.save(update_fields=['connection_status', 'connection_error'])
                
                health_results['fabric_details'].append({
                    'fabric_name': fabric.name,
                    'fabric_id': fabric.id,
                    'healthy': connection_test.get('success', False),
                    'error': connection_test.get('error')
                })
                
            except Exception as e:
                health_results['unhealthy_fabrics'] += 1
                logger.error(f"Health check failed for fabric {fabric.name}: {str(e)}")
                
                health_results['fabric_details'].append({
                    'fabric_name': fabric.name,
                    'fabric_id': fabric.id,
                    'healthy': False,
                    'error': str(e)
                })
        
        logger.info(f"🏥 Health check completed: {health_results['healthy_fabrics']}/{health_results['fabrics_checked']} healthy")
        
        return health_results
        
    except Exception as e:
        logger.error(f"Kubernetes health check failed: {str(e)}")
        health_results['error'] = str(e)
        return health_results
