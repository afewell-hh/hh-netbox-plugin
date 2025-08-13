"""
Django management command for Hedgehog fabric sync operations.

This command provides manual control over the RQ-based periodic sync system.
"""

import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.jobs.fabric_sync import FabricSyncJob, FabricSyncScheduler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manage Hedgehog fabric sync operations'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='action', help='Available actions')

        # Bootstrap command
        bootstrap_parser = subparsers.add_parser('bootstrap', help='Bootstrap sync schedules for all fabrics')
        bootstrap_parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-bootstrap even if schedules exist'
        )

        # Status command
        status_parser = subparsers.add_parser('status', help='Show sync status for all fabrics')
        status_parser.add_argument(
            '--fabric',
            type=str,
            help='Show status for specific fabric name'
        )

        # Test sync command
        test_parser = subparsers.add_parser('test-sync', help='Test sync for a specific fabric')
        test_parser.add_argument(
            'fabric_name',
            type=str,
            help='Name of fabric to test sync'
        )

        # Schedule command
        schedule_parser = subparsers.add_parser('schedule', help='Show scheduled jobs')
        
        # Trigger command
        trigger_parser = subparsers.add_parser('trigger', help='Manually trigger sync for fabric')
        trigger_parser.add_argument(
            'fabric_name',
            type=str,
            help='Name of fabric to trigger sync'
        )

    def handle(self, *args, **options):
        action = options.get('action')
        
        if not action:
            self.print_help('manage.py', 'hedgehog_sync')
            return

        try:
            if action == 'bootstrap':
                self.handle_bootstrap(options)
            elif action == 'status':
                self.handle_status(options)
            elif action == 'test-sync':
                self.handle_test_sync(options)
            elif action == 'schedule':
                self.handle_schedule(options)
            elif action == 'trigger':
                self.handle_trigger(options)
            else:
                raise CommandError(f"Unknown action: {action}")

        except Exception as e:
            raise CommandError(f"Command failed: {e}")

    def handle_bootstrap(self, options):
        """Bootstrap sync schedules for all fabrics."""
        self.stdout.write("Bootstrapping fabric sync schedules...")
        
        result = FabricSyncScheduler.bootstrap_all_fabric_schedules()
        
        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Successfully bootstrapped sync schedules for {result['fabrics_scheduled']} fabrics"
                )
            )
            if result['errors'] > 0:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  {result['errors']} fabrics had scheduling errors")
                )
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Failed to bootstrap sync schedules: {result.get('error', 'Unknown error')}")
            )

    def handle_status(self, options):
        """Show sync status for fabrics."""
        fabric_name = options.get('fabric')
        
        if fabric_name:
            try:
                fabric = HedgehogFabric.objects.get(name=fabric_name)
                self._print_fabric_status(fabric)
            except HedgehogFabric.DoesNotExist:
                raise CommandError(f"Fabric '{fabric_name}' not found")
        else:
            fabrics = HedgehogFabric.objects.all().order_by('name')
            if not fabrics:
                self.stdout.write("No fabrics found")
                return
                
            self.stdout.write(f"\n📊 Fabric Sync Status ({fabrics.count()} fabrics)")
            self.stdout.write("=" * 80)
            
            for fabric in fabrics:
                self._print_fabric_status(fabric, brief=True)

    def _print_fabric_status(self, fabric, brief=False):
        """Print detailed status for a single fabric."""
        sync_status = fabric.calculated_sync_status
        status_color = {
            'in_sync': self.style.SUCCESS,
            'never_synced': self.style.WARNING,
            'out_of_sync': self.style.ERROR,
            'error': self.style.ERROR,
            'not_configured': self.style.NOTICE,
            'disabled': self.style.NOTICE
        }.get(sync_status, self.style.NOTICE)
        
        if brief:
            last_sync_str = fabric.last_sync.strftime("%Y-%m-%d %H:%M:%S") if fabric.last_sync else "Never"
            self.stdout.write(
                f"  {fabric.name:<20} | "
                f"{status_color(sync_status.upper()):<15} | "
                f"Interval: {fabric.sync_interval:>4}s | "
                f"Last: {last_sync_str}"
            )
        else:
            self.stdout.write(f"\n🏗️  Fabric: {fabric.name}")
            self.stdout.write(f"   Status: {status_color(sync_status.upper())}")
            self.stdout.write(f"   Enabled: {'Yes' if fabric.sync_enabled else 'No'}")
            self.stdout.write(f"   Interval: {fabric.sync_interval} seconds")
            self.stdout.write(f"   Last Sync: {fabric.last_sync or 'Never'}")
            if fabric.sync_error:
                self.stdout.write(f"   Error: {self.style.ERROR(fabric.sync_error[:100])}")
            if fabric.kubernetes_server:
                self.stdout.write(f"   K8s Server: {fabric.kubernetes_server}")

    def handle_test_sync(self, options):
        """Test sync for a specific fabric."""
        fabric_name = options['fabric_name']
        
        try:
            fabric = HedgehogFabric.objects.get(name=fabric_name)
        except HedgehogFabric.DoesNotExist:
            raise CommandError(f"Fabric '{fabric_name}' not found")
        
        self.stdout.write(f"🧪 Testing sync for fabric '{fabric.name}'...")
        
        # Check if fabric needs sync
        needs_sync = fabric.needs_sync()
        self.stdout.write(f"   Needs Sync: {'Yes' if needs_sync else 'No'}")
        
        if not fabric.sync_enabled:
            self.stdout.write(self.style.WARNING("   ⚠️  Sync is disabled for this fabric"))
            return
            
        if fabric.sync_interval <= 0:
            self.stdout.write(self.style.WARNING("   ⚠️  Sync interval is 0 or negative"))
            return
        
        # Execute sync job
        self.stdout.write("   Executing sync job...")
        start_time = timezone.now()
        
        result = FabricSyncJob.execute_fabric_sync(fabric.id)
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(f"   ✅ Sync completed successfully in {duration:.1f}s")
            )
            self.stdout.write(f"   Message: {result.get('message', 'No message')}")
            if 'next_sync_scheduled' in result:
                self.stdout.write("   Next sync scheduled: Yes")
        else:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Sync failed after {duration:.1f}s")
            )
            self.stdout.write(f"   Error: {result.get('error', 'Unknown error')}")

    def handle_schedule(self, options):
        """Show scheduled jobs status."""
        self.stdout.write("📅 Scheduled Fabric Sync Jobs")
        self.stdout.write("=" * 50)
        
        result = FabricSyncScheduler.get_scheduled_jobs_status()
        
        if result['success']:
            jobs = result.get('job_details', [])
            if not jobs:
                self.stdout.write("No scheduled jobs found")
                return
                
            for job in jobs:
                next_run = job.get('next_run')
                if next_run:
                    next_run_dt = datetime.fromisoformat(next_run.replace('Z', '+00:00'))
                    time_until = next_run_dt - datetime.now(next_run_dt.tzinfo)
                    
                    if time_until.total_seconds() > 0:
                        time_str = f"in {int(time_until.total_seconds())}s"
                    else:
                        time_str = f"{abs(int(time_until.total_seconds()))}s overdue"
                else:
                    time_str = "Not scheduled"
                
                self.stdout.write(
                    f"  {job['fabric_name']:<20} | "
                    f"Every {job['sync_interval']:>3}s | "
                    f"Next: {time_str}"
                )
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Failed to get scheduled jobs: {result.get('error', 'Unknown error')}")
            )

    def handle_trigger(self, options):
        """Manually trigger sync for a fabric."""
        fabric_name = options['fabric_name']
        
        try:
            fabric = HedgehogFabric.objects.get(name=fabric_name)
        except HedgehogFabric.DoesNotExist:
            raise CommandError(f"Fabric '{fabric_name}' not found")
        
        self.stdout.write(f"🚀 Manually triggering sync for fabric '{fabric.name}'...")
        
        # Execute sync job immediately
        result = FabricSyncJob.execute_fabric_sync(fabric.id)
        
        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Sync triggered successfully")
            )
            self.stdout.write(f"   Duration: {result.get('duration', 0):.1f}s")
            self.stdout.write(f"   Message: {result.get('message', 'No message')}")
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Sync trigger failed")
            )
            self.stdout.write(f"   Error: {result.get('error', 'Unknown error')}")