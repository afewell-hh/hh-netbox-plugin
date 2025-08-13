"""
RQ-based Periodic Fabric Sync Jobs

This module implements NetBox-compatible RQ jobs for periodic fabric synchronization.
Replaces the Celery-based sync_scheduler.py with RQ system that actually works in NetBox.

Architecture:
- NetBox uses RQ (Redis Queue) for background tasks, not Celery
- Periodic jobs scheduled using django-rq-scheduler
- Each fabric gets its own scheduled sync job based on sync_interval
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from rq import get_current_job
import django_rq

from ..models.fabric import HedgehogFabric
from ..choices import SyncStatusChoices

logger = logging.getLogger('netbox_hedgehog.fabric_sync')

# Import necessary modules for proper sync operations
try:
    from rq_scheduler import Scheduler
    RQ_SCHEDULER_AVAILABLE = True
except ImportError:
    RQ_SCHEDULER_AVAILABLE = False
    logger.warning("rq_scheduler not available - periodic scheduling disabled")

class FabricSyncJob:
    """RQ Job class for periodic fabric synchronization"""
    
    @staticmethod
    def execute_fabric_sync(fabric_id: int) -> Dict[str, Any]:
        """
        Execute periodic sync for a specific fabric
        
        This is the main RQ job function that gets called by the scheduler
        """
        start_time = time.time()
        job = get_current_job()
        job_id = job.id if job else 'no-job'
        
        logger.info(f"Starting fabric sync job {job_id} for fabric {fabric_id}")
        
        try:
            with transaction.atomic():
                # Get fabric with lock to prevent concurrent syncs
                fabric = HedgehogFabric.objects.select_for_update().get(id=fabric_id)
                
                # Check if sync is still needed (another job might have run)
                if not fabric.needs_sync():
                    logger.info(f"Fabric {fabric.name} no longer needs sync, skipping")
                    return {
                        'success': True,
                        'message': 'Sync not needed',
                        'fabric_id': fabric_id,
                        'duration': time.time() - start_time
                    }
                
                # Update last_sync BEFORE starting (prevents timing issues)
                fabric.last_sync = timezone.now()
                fabric.sync_status = SyncStatusChoices.SYNCING
                fabric.save(update_fields=['last_sync', 'sync_status'])
                
                logger.info(f"Updated last_sync for fabric {fabric.name} at {fabric.last_sync}")
            
            # Perform the actual sync operations (outside transaction to allow rollback)
            sync_result = FabricSyncJob._perform_sync_operations(fabric)
            
            # Update final status
            with transaction.atomic():
                fabric.refresh_from_db()
                if sync_result['success']:
                    fabric.sync_status = SyncStatusChoices.IN_SYNC
                    fabric.sync_error = ''
                else:
                    fabric.sync_status = SyncStatusChoices.ERROR
                    fabric.sync_error = sync_result.get('error', 'Unknown sync error')
                
                fabric.save(update_fields=['sync_status', 'sync_error'])
            
            duration = time.time() - start_time
            
            # Schedule next sync
            FabricSyncJob._schedule_next_sync(fabric)
            
            result = {
                'success': sync_result['success'],
                'message': sync_result.get('message', 'Sync completed'),
                'fabric_id': fabric_id,
                'fabric_name': fabric.name,
                'duration': duration,
                'sync_timestamp': fabric.last_sync.isoformat(),
                'next_sync_scheduled': True
            }
            
            logger.info(f"Fabric sync job completed for {fabric.name}: {result}")
            return result
            
        except HedgehogFabric.DoesNotExist:
            logger.error(f"Fabric {fabric_id} not found for sync job")
            return {
                'success': False,
                'error': f'Fabric {fabric_id} not found',
                'duration': time.time() - start_time
            }
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Fabric sync job failed for fabric {fabric_id}: {e}")
            
            # Try to update error status
            try:
                fabric = HedgehogFabric.objects.get(id=fabric_id)
                fabric.sync_status = SyncStatusChoices.ERROR
                fabric.sync_error = str(e)
                fabric.save(update_fields=['sync_status', 'sync_error'])
            except:
                pass  # Don't fail if we can't update status
            
            return {
                'success': False,
                'error': str(e),
                'fabric_id': fabric_id,
                'duration': duration
            }
    
    @staticmethod
    def _perform_sync_operations(fabric: HedgehogFabric) -> Dict[str, Any]:
        """
        Perform the actual sync operations
        
        Args:
            fabric: The fabric to sync
            
        Returns:
            Dict with success status and any error messages
        """
        try:
            # Execute actual Kubernetes synchronization
            if fabric.kubernetes_server:
                logger.info(f"Executing K8s sync for fabric {fabric.name}")
                from ..utils.kubernetes import KubernetesSync
                k8s_sync = KubernetesSync(fabric)
                sync_result = k8s_sync.sync_all_crds()
                
                if not sync_result.get('success', False):
                    return {
                        'success': False,
                        'error': sync_result.get('error', 'Kubernetes sync failed'),
                        'details': sync_result
                    }
                    
            # Test Git operations (placeholder for future implementation)
            if fabric.git_repository_url:
                logger.info(f"Git operations not yet implemented for fabric {fabric.name}")
                # Git sync implementation will be added in future release
            
            # Update CRD counts (this will work with current data)
            fabric.refresh_from_db()
            fabric.cached_crd_count = fabric.vpcs_count + fabric.connections_count
            fabric.cached_vpc_count = fabric.vpcs_count  
            fabric.cached_connection_count = fabric.connections_count
            fabric.save(update_fields=['cached_crd_count', 'cached_vpc_count', 'cached_connection_count'])
            
            return {
                'success': True,
                'message': f'Sync completed successfully for fabric {fabric.name}',
                'resources_synced': fabric.cached_crd_count
            }
            
        except Exception as e:
            logger.error(f"Sync operations failed for fabric {fabric.name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _schedule_next_sync(fabric: HedgehogFabric) -> None:
        """
        Schedule the next sync job for this fabric
        
        Args:
            fabric: The fabric to schedule sync for
        """
        try:
            if not fabric.sync_enabled or fabric.sync_interval <= 0:
                logger.info(f"Sync disabled for fabric {fabric.name}, not scheduling next sync")
                return
                
            if not RQ_SCHEDULER_AVAILABLE:
                logger.warning(f"RQ Scheduler not available - cannot schedule next sync for fabric {fabric.name}")
                return
            
            # Get RQ scheduler (use default queue since netbox_hedgehog.hedgehog_sync doesn't exist)
            scheduler = django_rq.get_scheduler('default')
            
            # Calculate next run time
            next_run = timezone.now() + timedelta(seconds=fabric.sync_interval)
            
            # Cancel any existing scheduled job for this fabric
            job_id = f"fabric_sync_{fabric.id}"
            try:
                scheduler.cancel(job_id)
            except:
                pass  # Job might not exist
            
            # Schedule new job (rq-scheduler doesn't support job_id parameter)
            job = scheduler.schedule(
                scheduled_time=next_run,
                func=FabricSyncJob.execute_fabric_sync,
                args=[fabric.id],
                queue_name='default'
            )
            
            logger.info(f"Scheduled next sync for fabric {fabric.name} at {next_run} (interval: {fabric.sync_interval}s)")
            
        except Exception as e:
            logger.error(f"Failed to schedule next sync for fabric {fabric.name}: {e}")

class FabricSyncScheduler:
    """Management class for fabric sync scheduling"""
    
    @staticmethod
    def bootstrap_all_fabric_schedules() -> Dict[str, Any]:
        """
        Bootstrap sync schedules for all sync-enabled fabrics
        
        This should be called during plugin initialization to set up
        all the periodic sync jobs.
        """
        try:
            if not RQ_SCHEDULER_AVAILABLE:
                return {
                    'success': False,
                    'error': 'RQ Scheduler not available - install django-rq-scheduler',
                    'fabrics_scheduled': 0
                }
            
            scheduler = django_rq.get_scheduler('default')
            scheduled_count = 0
            error_count = 0
            
            # Get all sync-enabled fabrics
            fabrics = HedgehogFabric.objects.filter(
                sync_enabled=True,
                sync_interval__gt=0
            )
            
            logger.info(f"Bootstrapping sync schedules for {fabrics.count()} fabrics")
            
            for fabric in fabrics:
                try:
                    # Cancel any existing job
                    job_id = f"fabric_sync_{fabric.id}"
                    try:
                        scheduler.cancel(job_id)
                    except:
                        pass
                    
                    # Schedule first sync (immediate if never synced, or based on last_sync)
                    if fabric.last_sync is None:
                        # Never synced - schedule immediately
                        next_run = timezone.now() + timedelta(seconds=5)
                        logger.info(f"Scheduling immediate sync for never-synced fabric {fabric.name}")
                    else:
                        # Calculate when next sync should run based on last_sync + interval
                        next_run = fabric.last_sync + timedelta(seconds=fabric.sync_interval)
                        if next_run <= timezone.now():
                            # Overdue - schedule soon
                            next_run = timezone.now() + timedelta(seconds=10)
                            logger.info(f"Scheduling overdue sync for fabric {fabric.name}")
                        else:
                            logger.info(f"Scheduling next sync for fabric {fabric.name} at {next_run}")
                    
                    # Schedule the job (rq-scheduler doesn't support job_id parameter)
                    job = scheduler.schedule(
                        scheduled_time=next_run,
                        func=FabricSyncJob.execute_fabric_sync,
                        args=[fabric.id],
                        queue_name='default'
                    )
                    
                    scheduled_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to schedule sync for fabric {fabric.name}: {e}")
                    error_count += 1
            
            return {
                'success': True,
                'message': f'Bootstrapped sync schedules for {scheduled_count} fabrics',
                'fabrics_scheduled': scheduled_count,
                'errors': error_count,
                'total_fabrics': fabrics.count()
            }
            
        except Exception as e:
            logger.error(f"Failed to bootstrap fabric sync schedules: {e}")
            return {
                'success': False,
                'error': str(e),
                'fabrics_scheduled': 0
            }
    
    @staticmethod
    def get_scheduled_jobs_status() -> Dict[str, Any]:
        """
        Get status of all scheduled fabric sync jobs
        
        Returns information about currently scheduled jobs for monitoring
        """
        try:
            scheduler = django_rq.get_scheduler('default')
            jobs = list(scheduler.get_jobs())  # Convert generator to list for len() operation
            
            fabric_jobs = [job for job in jobs if job.id.startswith('fabric_sync_')]
            
            job_details = []
            for job in fabric_jobs:
                try:
                    fabric_id = int(job.id.split('_')[-1])
                    fabric = HedgehogFabric.objects.get(id=fabric_id)
                    
                    job_details.append({
                        'fabric_id': fabric_id,
                        'fabric_name': fabric.name,
                        'job_id': job.id,
                        'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                        'sync_interval': fabric.sync_interval,
                        'last_sync': fabric.last_sync.isoformat() if fabric.last_sync else None,
                        'sync_status': fabric.sync_status
                    })
                except Exception as e:
                    logger.error(f"Error getting job details for {job.id}: {e}")
            
            return {
                'success': True,
                'total_jobs': len(fabric_jobs),
                'job_details': job_details
            }
            
        except Exception as e:
            logger.error(f"Failed to get scheduled jobs status: {e}")
            return {
                'success': False,
                'error': str(e),
                'total_jobs': 0
            }
    
    @staticmethod
    def manually_trigger_sync(fabric_id: int) -> Dict[str, Any]:
        """
        Manually trigger a sync for a specific fabric (for testing/debugging)
        
        Args:
            fabric_id: ID of the fabric to sync
            
        Returns:
            Dict with operation result
        """
        try:
            fabric = HedgehogFabric.objects.get(id=fabric_id)
            
            # Execute sync directly
            result = FabricSyncJob.execute_fabric_sync(fabric_id)
            
            logger.info(f"Manual sync triggered for fabric {fabric.name}: {result}")
            return result
            
        except HedgehogFabric.DoesNotExist:
            return {
                'success': False,
                'error': f'Fabric {fabric_id} not found'
            }
        except Exception as e:
            logger.error(f"Failed to manually trigger sync for fabric {fabric_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def start_periodic_sync_for_fabric(fabric_id: int) -> Dict[str, Any]:
        """
        Start periodic sync for a specific fabric
        
        Args:
            fabric_id: ID of the fabric to start periodic sync for
            
        Returns:
            Dict with operation result
        """
        try:
            fabric = HedgehogFabric.objects.get(id=fabric_id)
            
            if not fabric.sync_enabled:
                return {
                    'success': False,
                    'error': f'Sync is disabled for fabric {fabric.name}'
                }
                
            if fabric.sync_interval <= 0:
                return {
                    'success': False,
                    'error': f'Invalid sync interval ({fabric.sync_interval}s) for fabric {fabric.name}'
                }
            
            # Schedule the sync
            FabricSyncJob._schedule_next_sync(fabric)
            
            return {
                'success': True,
                'message': f'Periodic sync started for fabric {fabric.name}',
                'fabric_name': fabric.name,
                'sync_interval': fabric.sync_interval
            }
            
        except HedgehogFabric.DoesNotExist:
            return {
                'success': False,
                'error': f'Fabric {fabric_id} not found'
            }
        except Exception as e:
            logger.error(f"Failed to start periodic sync for fabric {fabric_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Convenience functions for easy access

def execute_fabric_sync_rq(fabric_id: int) -> Dict[str, Any]:
    """
    RQ job function wrapper for fabric sync execution
    This is the actual function that gets queued by RQ
    """
    return FabricSyncJob.execute_fabric_sync(fabric_id)


def queue_fabric_sync(fabric_id: int, delay: int = 0) -> Dict[str, Any]:
    """
    Queue a fabric sync job for immediate or delayed execution
    
    Args:
        fabric_id: ID of the fabric to sync
        delay: Delay in seconds before execution (default: immediate)
        
    Returns:
        Dict with queue operation result
    """
    try:
        queue = django_rq.get_queue('default')
        
        if delay > 0:
            # Schedule with delay
            job = queue.enqueue_in(
                timedelta(seconds=delay),
                execute_fabric_sync_rq,
                fabric_id,
                job_id=f"manual_sync_{fabric_id}_{int(time.time())}"
            )
        else:
            # Execute immediately
            job = queue.enqueue(
                execute_fabric_sync_rq,
                fabric_id,
                job_id=f"manual_sync_{fabric_id}_{int(time.time())}"
            )
        
        return {
            'success': True,
            'message': f'Fabric sync job queued',
            'job_id': job.id,
            'fabric_id': fabric_id,
            'delay': delay
        }
        
    except Exception as e:
        logger.error(f"Failed to queue fabric sync job for fabric {fabric_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'fabric_id': fabric_id
        }