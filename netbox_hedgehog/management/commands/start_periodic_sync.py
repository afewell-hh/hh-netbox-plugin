"""
Django management command to start periodic sync for NetBox Hedgehog Plugin

This command allows manual control of the RQ-based periodic sync system.
"""

import json
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from netbox_hedgehog.jobs.fabric_sync import FabricSyncScheduler, FabricSyncJob
from netbox_hedgehog.models.fabric import HedgehogFabric

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Start periodic sync for Hedgehog fabrics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fabric-id',
            type=int,
            help='ID of specific fabric to start sync for (otherwise all)'
        )
        parser.add_argument(
            '--bootstrap',
            action='store_true',
            help='Bootstrap all fabric schedules from scratch'
        )
        parser.add_argument(
            '--manual-trigger',
            action='store_true',
            help='Manually trigger one sync execution (for testing)'
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show status of scheduled jobs'
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results in JSON format'
        )

    def handle(self, *args, **options):
        fabric_id = options.get('fabric_id')
        bootstrap = options['bootstrap']
        manual_trigger = options['manual_trigger']
        show_status = options['status']
        output_json = options['json']

        try:
            # Show status of scheduled jobs
            if show_status:
                self.handle_status(output_json)
                return

            # Bootstrap all fabric schedules
            if bootstrap:
                self.handle_bootstrap(output_json)
                return

            # Manual trigger for testing
            if manual_trigger:
                self.handle_manual_trigger(fabric_id, output_json)
                return

            # Start periodic sync for specific fabric or all fabrics
            if fabric_id:
                result = self.start_single_fabric_sync(fabric_id)
            else:
                result = self.start_all_fabric_syncs()

            if output_json:
                self.stdout.write(json.dumps(result, indent=2, default=str))
            else:
                if result['success']:
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ {result['message']}")
                    )
                    if 'fabrics_started' in result:
                        self.stdout.write(f"  - Fabrics started: {result['fabrics_started']}")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"❌ {result.get('error', 'Unknown error')}")
                    )

        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }

            if output_json:
                self.stdout.write(json.dumps(error_result, indent=2))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Command failed: {e}"))

            logger.error(f"start_periodic_sync command failed: {e}")
            raise

    def handle_status(self, output_json: bool):
        """Handle status command"""
        result = FabricSyncScheduler.get_scheduled_jobs_status()

        if output_json:
            self.stdout.write(json.dumps(result, indent=2, default=str))
        else:
            if result['success']:
                self.stdout.write(f"📊 Scheduled Jobs Status:")
                self.stdout.write(f"  - Total scheduled jobs: {result['total_jobs']}")
                
                if result['total_jobs'] > 0:
                    self.stdout.write("  - Job details:")
                    for job in result.get('job_details', []):
                        next_run = job.get('next_run', 'Unknown')
                        interval = job.get('sync_interval', 'Unknown')
                        self.stdout.write(f"    • {job['fabric_name']}: next run {next_run} (interval: {interval}s)")
                else:
                    self.stdout.write("  - No scheduled jobs found")
            else:
                self.stdout.write(self.style.ERROR(f"❌ Status check failed: {result.get('error', 'Unknown error')}"))

    def handle_bootstrap(self, output_json: bool):
        """Handle bootstrap command"""
        self.stdout.write("🚀 Bootstrapping all fabric sync schedules...")
        result = FabricSyncScheduler.bootstrap_all_fabric_schedules()

        if output_json:
            self.stdout.write(json.dumps(result, indent=2, default=str))
        else:
            if result['success']:
                self.stdout.write(self.style.SUCCESS(f"✅ {result['message']}"))
                self.stdout.write(f"  - Total fabrics: {result['total_fabrics']}")
                self.stdout.write(f"  - Successfully scheduled: {result['fabrics_scheduled']}")
                if result['errors'] > 0:
                    self.stdout.write(f"  - Errors: {result['errors']}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ Bootstrap failed: {result.get('error', 'Unknown error')}"))

    def handle_manual_trigger(self, fabric_id: int, output_json: bool):
        """Handle manual trigger command"""
        if not fabric_id:
            # Find first available fabric
            try:
                fabric = HedgehogFabric.objects.filter(sync_enabled=True).first()
                if not fabric:
                    raise Exception("No sync-enabled fabrics found")
                fabric_id = fabric.id
            except Exception as e:
                raise Exception(f"Failed to find fabric for manual trigger: {e}")

        self.stdout.write(f"🔄 Manually triggering sync for fabric {fabric_id}...")
        result = FabricSyncScheduler.manually_trigger_sync(fabric_id)

        if output_json:
            self.stdout.write(json.dumps(result, indent=2, default=str))
        else:
            if result['success']:
                self.stdout.write(self.style.SUCCESS(f"✅ Manual sync completed for fabric {result.get('fabric_name', fabric_id)}"))
                self.stdout.write(f"  - Duration: {result.get('duration', 'Unknown')}s")
                self.stdout.write(f"  - Sync timestamp: {result.get('sync_timestamp', 'Unknown')}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ Manual sync failed: {result.get('error', 'Unknown error')}"))

    def start_single_fabric_sync(self, fabric_id: int) -> dict:
        """Start periodic sync for a single fabric"""
        try:
            result = FabricSyncScheduler.start_periodic_sync_for_fabric(fabric_id)
            
            if result['success']:
                return {
                    'success': True,
                    'message': f"Started periodic sync for fabric {result['fabric_name']}",
                    'fabric_id': fabric_id,
                    'fabric_name': result['fabric_name'],
                    'sync_interval': result['sync_interval']
                }
            else:
                return result

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'fabric_id': fabric_id
            }

    def start_all_fabric_syncs(self) -> dict:
        """Start periodic sync for all enabled fabrics"""
        try:
            # Get all sync-enabled fabrics
            fabrics = HedgehogFabric.objects.filter(
                sync_enabled=True,
                sync_interval__gt=0
            )

            if not fabrics.exists():
                return {
                    'success': True,
                    'message': 'No sync-enabled fabrics found',
                    'fabrics_started': 0
                }

            started_count = 0
            errors = []

            for fabric in fabrics:
                try:
                    result = FabricSyncScheduler.start_periodic_sync_for_fabric(fabric.id)
                    if result['success']:
                        started_count += 1
                    else:
                        errors.append(f"{fabric.name}: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    errors.append(f"{fabric.name}: {str(e)}")

            return {
                'success': True,
                'message': f'Started periodic sync for {started_count} fabrics',
                'fabrics_started': started_count,
                'total_fabrics': fabrics.count(),
                'errors': errors if errors else None
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }