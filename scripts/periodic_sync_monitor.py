#!/usr/bin/env python3
"""
Periodic Sync Monitor
Real-time monitoring script to validate periodic sync execution
"""

import time
import sys
import os
from datetime import datetime

# Add Django settings
sys.path.append('/opt/netbox/netbox')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

import django
django.setup()

from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.jobs.fabric_sync import FabricSyncScheduler
from django.utils import timezone

def monitor_periodic_sync(fabric_id=35, duration_seconds=120, check_interval=5):
    """Monitor periodic sync execution over specified duration"""
    
    print(f"🔍 PERIODIC SYNC MONITORING")
    print(f"=" * 60)
    print(f"Fabric ID: {fabric_id}")
    print(f"Duration: {duration_seconds} seconds")
    print(f"Check interval: {check_interval} seconds")
    print(f"Start time: {timezone.now()}")
    print()
    
    start_time = time.time()
    check_count = 0
    sync_events = []
    last_sync_time = None
    
    while time.time() - start_time < duration_seconds:
        check_count += 1
        current_time = timezone.now()
        
        try:
            # Get current fabric state
            fabric = HedgehogFabric.objects.get(id=fabric_id)
            
            # Check if sync timestamp changed
            sync_changed = last_sync_time != fabric.last_sync
            if sync_changed and last_sync_time is not None:
                sync_events.append({
                    'check': check_count,
                    'time': current_time,
                    'last_sync': fabric.last_sync,
                    'sync_status': fabric.sync_status,
                    'calculated_status': fabric.calculated_sync_status
                })
                print(f"🎉 SYNC EVENT DETECTED!")
                print(f"   Check #{check_count} at {current_time.strftime('%H:%M:%S')}")
                print(f"   New last_sync: {fabric.last_sync}")
                print(f"   sync_status: {fabric.sync_status}")
                print(f"   calculated_status: {fabric.calculated_sync_status}")
                print()
            
            # Update tracking
            last_sync_time = fabric.last_sync
            
            # Status report
            print(f"Check #{check_count} ({current_time.strftime('%H:%M:%S')}):")
            print(f"  last_sync: {fabric.last_sync}")
            print(f"  sync_status: {fabric.sync_status}")
            print(f"  needs_sync(): {fabric.needs_sync()}")
            print(f"  calculated_status: {fabric.calculated_sync_status}")
            print(f"  sync_interval: {fabric.sync_interval}s")
            
            if fabric.last_sync:
                time_since = (current_time - fabric.last_sync).total_seconds()
                print(f"  time_since_sync: {time_since:.1f}s")
            
            print()
            
        except Exception as e:
            print(f"❌ Error during check #{check_count}: {e}")
            print()
        
        time.sleep(check_interval)
    
    # Final report
    print(f"📊 MONITORING COMPLETE")
    print(f"=" * 60)
    print(f"Total checks: {check_count}")
    print(f"Sync events detected: {len(sync_events)}")
    print(f"Duration: {duration_seconds} seconds")
    
    if sync_events:
        print(f"\n🎉 SYNC EVENTS:")
        for i, event in enumerate(sync_events, 1):
            print(f"  Event #{i}: Check #{event['check']} at {event['time'].strftime('%H:%M:%S')}")
            print(f"    last_sync: {event['last_sync']}")
            print(f"    status: {event['sync_status']} → {event['calculated_status']}")
    else:
        print(f"\n❌ NO SYNC EVENTS DETECTED")
        print(f"   This indicates periodic sync is NOT working")
    
    return {
        'total_checks': check_count,
        'sync_events': len(sync_events),
        'events': sync_events,
        'success': len(sync_events) > 0
    }

if __name__ == "__main__":
    # Monitor for 2 minutes (should see 4 syncs at 30-second intervals)
    result = monitor_periodic_sync(fabric_id=35, duration_seconds=120, check_interval=5)
    
    print(f"\n🏁 FINAL RESULT:")
    print(f"   Periodic sync working: {'✅ YES' if result['success'] else '❌ NO'}")
    print(f"   Events detected: {result['sync_events']}")
    
    sys.exit(0 if result['success'] else 1)