#!/usr/bin/env python3
"""
Database audit script for fabric ID 35 sync status investigation.
This simulates Django shell access to investigate periodic sync timer execution.
"""

import os
import sys
import django
from datetime import datetime, timezone
import json

# Add the project root to Python path
sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')

# Set up Django environment (simulate NetBox environment)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox_hedgehog.settings')

try:
    django.setup()
except Exception as e:
    print(f"Django setup failed (expected in plugin context): {e}")
    # Continue anyway as this is expected for a NetBox plugin

def simulate_fabric_query():
    """
    Simulate querying fabric ID 35 from the database.
    Returns database state evidence for sync investigation.
    """
    try:
        # Try direct import approach
        from netbox_hedgehog.models import HedgehogFabric
        
        print("=== DATABASE STATE AUDIT: FABRIC ID 35 ===")
        print(f"Audit Time: {datetime.now(timezone.utc)}")
        print()
        
        # Query fabric ID 35
        try:
            fabric = HedgehogFabric.objects.get(id=35)
            
            print("✅ FABRIC 35 FOUND IN DATABASE")
            print(f"Name: {fabric.name}")
            print(f"ID: {fabric.id}")
            print()
            
            print("=== SYNC CONFIGURATION ===")
            print(f"sync_enabled: {fabric.sync_enabled}")
            print(f"sync_interval: {fabric.sync_interval} seconds")
            print(f"kubernetes_server: {repr(fabric.kubernetes_server)}")
            print(f"kubernetes_namespace: {fabric.kubernetes_namespace}")
            print()
            
            print("=== SYNC STATUS EVIDENCE ===")
            print(f"sync_status (raw): {repr(fabric.sync_status)}")
            print(f"last_sync (raw): {repr(fabric.last_sync)}")
            print(f"sync_error (raw): {repr(fabric.sync_error)}")
            print(f"connection_error (raw): {repr(fabric.connection_error)}")
            print()
            
            # Check calculated sync status
            try:
                calc_status = fabric.calculated_sync_status
                calc_display = fabric.calculated_sync_status_display
                print(f"calculated_sync_status: {calc_status}")
                print(f"calculated_sync_status_display: {calc_display}")
            except Exception as e:
                print(f"Error getting calculated sync status: {e}")
            print()
            
            print("=== SCHEDULER ARTIFACTS SEARCH ===")
            # Check for Celery Beat or scheduler evidence
            scheduler_evidence = {
                'watch_enabled': fabric.watch_enabled,
                'watch_status': fabric.watch_status,
                'watch_started_at': fabric.watch_started_at,
                'watch_last_event': fabric.watch_last_event,
                'watch_event_count': fabric.watch_event_count,
                'watch_error_message': fabric.watch_error_message
            }
            
            for key, value in scheduler_evidence.items():
                print(f"{key}: {repr(value)}")
            print()
            
            # Check timestamps for analysis
            print("=== TIMESTAMP ANALYSIS ===")
            now = datetime.now(timezone.utc)
            print(f"Current time: {now}")
            print(f"Fabric created: {fabric.created}")
            print(f"Fabric last_updated: {fabric.last_updated}")
            
            if fabric.last_sync:
                time_since_sync = now - fabric.last_sync
                print(f"Time since last sync: {time_since_sync}")
                print(f"Seconds since last sync: {time_since_sync.total_seconds()}")
                print(f"Is overdue? {time_since_sync.total_seconds() > fabric.sync_interval if fabric.sync_interval > 0 else 'N/A'}")
            else:
                print("last_sync: NULL - NEVER SYNCED CONFIRMED")
            print()
            
            print("=== SYNC EXECUTION EVIDENCE ===")
            # Look for any signs of sync attempts or periodic execution
            sync_evidence = {
                'Should be scheduled': fabric.should_be_scheduled() if hasattr(fabric, 'should_be_scheduled') else 'Method not available',
                'Kubernetes config available': bool(fabric.get_kubernetes_config()),
                'Sync configuration valid': fabric.sync_enabled and fabric.sync_interval > 0 and fabric.kubernetes_server
            }
            
            for key, value in sync_evidence.items():
                print(f"{key}: {value}")
            print()
            
            # Store complete audit results
            audit_results = {
                'fabric_id': fabric.id,
                'fabric_name': fabric.name,
                'audit_timestamp': now.isoformat(),
                'sync_config': {
                    'sync_enabled': fabric.sync_enabled,
                    'sync_interval': fabric.sync_interval,
                    'kubernetes_server': fabric.kubernetes_server,
                    'kubernetes_namespace': fabric.kubernetes_namespace
                },
                'sync_status': {
                    'sync_status_raw': fabric.sync_status,
                    'last_sync_raw': fabric.last_sync.isoformat() if fabric.last_sync else None,
                    'sync_error_raw': fabric.sync_error,
                    'connection_error_raw': fabric.connection_error,
                    'calculated_sync_status': calc_status if 'calc_status' in locals() else 'Error calculating',
                    'calculated_sync_status_display': calc_display if 'calc_display' in locals() else 'Error calculating'
                },
                'scheduler_evidence': scheduler_evidence,
                'timestamp_analysis': {
                    'created': fabric.created.isoformat(),
                    'last_updated': fabric.last_updated.isoformat(),
                    'last_sync': fabric.last_sync.isoformat() if fabric.last_sync else None,
                    'never_synced_confirmed': fabric.last_sync is None,
                    'seconds_since_sync': time_since_sync.total_seconds() if fabric.last_sync else None,
                    'is_overdue': time_since_sync.total_seconds() > fabric.sync_interval if fabric.last_sync and fabric.sync_interval > 0 else None
                },
                'sync_evidence': sync_evidence
            }
            
            # Write audit results to file
            audit_file = f"/home/ubuntu/cc/hedgehog-netbox-plugin/fabric35_database_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(audit_file, 'w') as f:
                json.dump(audit_results, f, indent=2, default=str)
            
            print(f"=== AUDIT RESULTS SAVED ===")
            print(f"Complete audit results saved to: {audit_file}")
            print()
            
            print("=== CRITICAL FINDINGS ===")
            findings = []
            
            if fabric.last_sync is None:
                findings.append("❌ CONFIRMED: last_sync is NULL - fabric has NEVER been synced")
            
            if not fabric.sync_enabled:
                findings.append("❌ Sync is DISABLED for this fabric")
            elif fabric.sync_interval <= 0:
                findings.append("❌ Sync interval is 0 or negative - periodic sync disabled")
            elif not fabric.kubernetes_server:
                findings.append("❌ No kubernetes_server configured - cannot sync")
            else:
                findings.append("✅ Sync configuration appears valid")
                
            if fabric.watch_status != 'active':
                findings.append(f"❌ Watch status is '{fabric.watch_status}' - not actively monitoring")
                
            if fabric.watch_event_count == 0:
                findings.append("❌ Zero watch events recorded - no Kubernetes activity detected")
            
            for finding in findings:
                print(finding)
            
            print()
            print("=== DATABASE STATE AUDIT COMPLETE ===")
            
            return audit_results
            
        except Exception as e:
            if "DoesNotExist" in str(e):
                print("❌ FABRIC ID 35 NOT FOUND IN DATABASE")
                print(f"Error: {e}")
                
                # Try to list all fabrics
                try:
                    all_fabrics = HedgehogFabric.objects.all()
                    print(f"\n=== AVAILABLE FABRICS ===")
                    for fabric in all_fabrics:
                        print(f"ID: {fabric.id}, Name: {fabric.name}")
                except Exception as list_error:
                    print(f"Error listing fabrics: {list_error}")
            else:
                print(f"❌ ERROR QUERYING FABRIC: {e}")
            
            return None
            
    except ImportError as e:
        print(f"❌ IMPORT ERROR: {e}")
        print("Cannot access NetBox plugin models in this context")
        return None

if __name__ == "__main__":
    audit_results = simulate_fabric_query()
    if audit_results:
        print(f"Database audit completed successfully")
    else:
        print(f"Database audit failed - check fabric configuration")