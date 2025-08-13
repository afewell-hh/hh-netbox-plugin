"""
Simple RQ sync jobs for NetBox Hedgehog Plugin
"""

import os
import django
from datetime import datetime

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.utils import timezone
from django.db import connection

def update_fabric_sync(fabric_id):
    """
    Simple RQ job to update fabric last_sync timestamp.
    This proves that RQ can execute jobs and update the database.
    """
    print(f"[{datetime.now()}] Starting sync job for fabric {fabric_id}")
    
    # Direct database update
    cursor = connection.cursor()
    
    # Get current fabric state
    cursor.execute("SELECT name, sync_enabled, sync_interval, last_sync FROM netbox_hedgehog_hedgehogfabric WHERE id = %s", [fabric_id])
    row = cursor.fetchone()
    
    if not row:
        return {
            'success': False,
            'error': f'Fabric {fabric_id} not found'
        }
    
    name, sync_enabled, sync_interval, last_sync = row
    print(f"  Found fabric: {name}")
    print(f"  sync_enabled: {sync_enabled}")
    print(f"  sync_interval: {sync_interval}")
    print(f"  BEFORE - last_sync: {last_sync}")
    
    # Update last_sync timestamp
    now = timezone.now()
    cursor.execute("UPDATE netbox_hedgehog_hedgehogfabric SET last_sync = %s WHERE id = %s", [now, fabric_id])
    
    print(f"  AFTER - last_sync: {now}")
    print(f"[{datetime.now()}] Sync job completed for fabric {fabric_id}")
    
    return {
        'success': True,
        'fabric_id': fabric_id,
        'fabric_name': name,
        'sync_timestamp': now.isoformat(),
        'message': f'Successfully updated last_sync for fabric {name}',
        'previous_last_sync': str(last_sync) if last_sync else None
    }

def schedule_periodic_sync(fabric_id, interval_seconds=60):
    """
    Schedule a periodic sync job for a fabric.
    """
    import django_rq
    from datetime import timedelta
    
    print(f"[{datetime.now()}] Scheduling periodic sync for fabric {fabric_id} every {interval_seconds} seconds")
    
    try:
        scheduler = django_rq.get_scheduler('default')
        
        # Cancel any existing job for this fabric
        job_id = f"fabric_sync_{fabric_id}"
        try:
            scheduler.cancel(job_id)
            print(f"  Cancelled previous job {job_id}")
        except:
            pass
        
        # Schedule new periodic job
        next_run = timezone.now() + timedelta(seconds=interval_seconds)
        job = scheduler.schedule(
            scheduled_time=next_run,
            func=update_fabric_sync,
            args=[fabric_id],
            job_id=job_id,
            interval=interval_seconds
        )
        
        print(f"  Scheduled job {job_id} for {next_run}")
        return {
            'success': True,
            'job_id': job_id,
            'next_run': next_run.isoformat(),
            'interval': interval_seconds
        }
        
    except Exception as e:
        print(f"  ERROR scheduling job: {e}")
        return {
            'success': False,
            'error': str(e)
        }