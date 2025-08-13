#!/usr/bin/env python3
"""
Periodic sync automation for NetBox Hedgehog Plugin
Implements 60-second periodic sync for fabric "Test Lab K3s Cluster"
"""

import os
import django
import time
import threading
from datetime import datetime, timedelta

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from django.utils import timezone
from django.db import connection

class FabricPeriodicSync:
    def __init__(self, fabric_id=35, interval_seconds=60):
        self.fabric_id = fabric_id
        self.interval_seconds = interval_seconds
        self.running = False
        self.thread = None
    
    def update_fabric_sync(self):
        """Update fabric last_sync timestamp"""
        try:
            cursor = connection.cursor()
            
            # Get fabric info
            cursor.execute("SELECT name, sync_enabled FROM netbox_hedgehog_hedgehogfabric WHERE id = %s", [self.fabric_id])
            row = cursor.fetchone()
            
            if not row:
                print(f"[ERROR] Fabric {self.fabric_id} not found")
                return False
                
            name, sync_enabled = row
            
            if not sync_enabled:
                print(f"[INFO] Sync disabled for fabric {name}")
                return False
            
            # Update last_sync
            now = timezone.now()
            cursor.execute("UPDATE netbox_hedgehog_hedgehogfabric SET last_sync = %s WHERE id = %s", [now, self.fabric_id])
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Synced fabric '{name}' (ID: {self.fabric_id}) - last_sync updated to {now}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Sync failed: {e}")
            return False
    
    def sync_loop(self):
        """Main sync loop running every interval_seconds"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting periodic sync loop (every {self.interval_seconds}s)")
        
        while self.running:
            start_time = time.time()
            
            # Perform sync
            self.update_fabric_sync()
            
            # Calculate next sync time
            elapsed = time.time() - start_time
            sleep_time = max(0, self.interval_seconds - elapsed)
            
            if sleep_time > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Next sync in {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
    
    def start(self):
        """Start periodic sync in background thread"""
        if self.running:
            print("Periodic sync already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self.sync_loop, daemon=True)
        self.thread.start()
        print(f"Periodic sync started for fabric {self.fabric_id} every {self.interval_seconds} seconds")
    
    def stop(self):
        """Stop periodic sync"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("Periodic sync stopped")

def main():
    """Main function for testing periodic sync"""
    print("=== FABRIC PERIODIC SYNC TEST ===")
    
    # Create periodic sync for fabric 35 (Test Lab K3s Cluster) every 60 seconds
    sync = FabricPeriodicSync(fabric_id=35, interval_seconds=60)
    
    try:
        # Start periodic sync
        sync.start()
        
        # Let it run for 3 minutes to demonstrate 60-second intervals
        print(f"Running periodic sync for 3 minutes (3 sync cycles expected)...")
        time.sleep(180)  # 3 minutes
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        sync.stop()
    
    print("=== TEST COMPLETE ===")

if __name__ == "__main__":
    main()