"""
Management command to ingest raw YAML files from the raw/ directory.

Usage:
    python manage.py ingest_raw_files --fabric <fabric_name>
    python manage.py ingest_raw_files --all
    python manage.py ingest_raw_files --fabric <fabric_name> --file <specific_file>
    python manage.py ingest_raw_files --fabric <fabric_name> --watch
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.services.gitops_ingestion_service import GitOpsIngestionService
from netbox_hedgehog.services.raw_directory_watcher import RawDirectoryWatcher
import time
import signal
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ingest raw YAML files from the raw/ directory into managed structure'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.watchers = {}
        self.watch_mode = False
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fabric',
            type=str,
            help='Name of the fabric to process (required unless --all is used)'
        )
        
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all fabrics with initialized GitOps structure'
        )
        
        parser.add_argument(
            '--file',
            type=str,
            help='Process a specific file (requires --fabric)'
        )
        
        parser.add_argument(
            '--watch',
            action='store_true',
            help='Watch for new files and process them automatically'
        )
        
        parser.add_argument(
            '--scan-interval',
            type=int,
            default=30,
            help='Scan interval in seconds for watch mode (default: 30)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Process files even if they appear to be already processed'
        )
        
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show ingestion status for fabrics'
        )
    
    def handle(self, *args, **options):
        """Main command handler."""
        self.verbosity = options['verbosity']
        
        try:
            # Handle status request
            if options['status']:
                self._show_status(options)
                return
            
            # Handle watch mode
            if options['watch']:
                self._handle_watch_mode(options)
                return
            
            # Handle single file processing
            if options['file']:
                self._handle_single_file(options)
                return
            
            # Handle batch processing
            self._handle_batch_processing(options)
            
        except KeyboardInterrupt:
            if self.watch_mode:
                self.stdout.write('\nStopping watchers...')
                self._stop_all_watchers()
            self.stdout.write('\nOperation cancelled by user')
            sys.exit(0)
        except Exception as e:
            raise CommandError(f'Command failed: {str(e)}')
    
    def _handle_watch_mode(self, options):
        """Handle watch mode for continuous file processing."""
        self.watch_mode = True
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Get fabrics to watch
        fabrics = self._get_fabrics_to_process(options)
        
        if not fabrics:
            raise CommandError('No fabrics found to watch')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting watchers for {len(fabrics)} fabric(s)'
            )
        )
        
        # Start watchers
        for fabric in fabrics:
            try:
                watcher = RawDirectoryWatcher(fabric)
                
                # Register callbacks for verbose output
                if self.verbosity >= 2:
                    watcher.register_callbacks(
                        on_files_detected=self._on_files_detected,
                        on_processing_complete=self._on_processing_complete,
                        on_error=self._on_error
                    )
                
                result = watcher.start_watching(options['scan_interval'])
                
                if result['success']:
                    self.watchers[fabric.id] = watcher
                    self.stdout.write(f'✓ Started watcher for {fabric.name}')
                else:
                    self.stderr.write(f'✗ Failed to start watcher for {fabric.name}: {result.get("error")}')
                    
            except Exception as e:
                self.stderr.write(f'✗ Error starting watcher for {fabric.name}: {str(e)}')
        
        if not self.watchers:
            raise CommandError('No watchers could be started')
        
        # Keep running until interrupted
        self.stdout.write('\nPress Ctrl+C to stop watching...\n')
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self._stop_all_watchers()
    
    def _handle_single_file(self, options):
        """Handle processing of a single file."""
        if not options['fabric']:
            raise CommandError('--fabric is required when using --file')
        
        fabric = self._get_fabric_by_name(options['fabric'])
        file_path = Path(options['file'])
        
        if not file_path.exists():
            raise CommandError(f'File not found: {file_path}')
        
        self.stdout.write(f'Processing file: {file_path}')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN: Would process file'))
            return
        
        try:
            service = GitOpsIngestionService(fabric)
            result = service.process_single_file(file_path)
            
            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Successfully processed {file_path}'
                    )
                )
                
                if self.verbosity >= 2:
                    self.stdout.write(f'  Documents extracted: {result.get("documents_extracted", 0)}')
                    if result.get('files_created'):
                        for file_info in result['files_created']:
                            self.stdout.write(f'  Created: {file_info["managed_file"]}')
            else:
                self.stderr.write(
                    self.style.ERROR(
                        f'✗ Failed to process {file_path}: {result.get("error")}'
                    )
                )
                
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f'✗ Error processing {file_path}: {str(e)}')
            )
            sys.exit(1)
    
    def _handle_batch_processing(self, options):
        """Handle batch processing of all raw directories."""
        fabrics = self._get_fabrics_to_process(options)
        
        if not fabrics:
            raise CommandError('No fabrics found to process')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Processing raw directories for {len(fabrics)} fabric(s)'
            )
        )
        
        total_success = 0
        total_errors = 0
        
        for fabric in fabrics:
            try:
                result = self._process_fabric_raw_directory(fabric, options)
                
                if result['success']:
                    total_success += 1
                    self._report_processing_success(fabric, result)
                else:
                    total_errors += 1
                    self._report_processing_error(fabric, result)
                    
            except Exception as e:
                total_errors += 1
                self.stderr.write(
                    self.style.ERROR(
                        f'✗ Unexpected error processing fabric {fabric.name}: {str(e)}'
                    )
                )
        
        # Summary
        self._print_processing_summary(total_success, total_errors)
        
        if total_errors > 0:
            sys.exit(1)
    
    def _show_status(self, options):
        """Show ingestion status for fabrics."""
        fabrics = self._get_fabrics_to_process(options)
        
        if not fabrics:
            raise CommandError('No fabrics found')
        
        self.stdout.write('GitOps Ingestion Status:\n')
        
        for fabric in fabrics:
            try:
                service = GitOpsIngestionService(fabric)
                status = service.get_ingestion_status()
                
                self.stdout.write(f'Fabric: {fabric.name}')
                self.stdout.write(f'  Raw files pending: {status["raw_files_pending"]}')
                self.stdout.write(f'  Managed files: {status["managed_files_count"]}')
                self.stdout.write(f'  Last ingestion: {status["last_ingestion"] or "Never"}')
                
                if status['paths']['raw_directory']:
                    self.stdout.write(f'  Raw directory: {status["paths"]["raw_directory"]}')
                if status['paths']['managed_directory']:
                    self.stdout.write(f'  Managed directory: {status["paths"]["managed_directory"]}')
                
                self.stdout.write('')
                
            except Exception as e:
                self.stderr.write(f'✗ Error getting status for {fabric.name}: {str(e)}')
    
    def _get_fabrics_to_process(self, options):
        """Determine which fabrics to process based on command options."""
        if options['all']:
            # Only process fabrics with initialized GitOps structure
            return HedgehogFabric.objects.filter(gitops_initialized=True)
        elif options['fabric']:
            fabric = self._get_fabric_by_name(options['fabric'])
            return [fabric]
        else:
            raise CommandError('Either --fabric or --all must be specified')
    
    def _get_fabric_by_name(self, fabric_name):
        """Get fabric by name with error handling."""
        try:
            return HedgehogFabric.objects.get(name=fabric_name)
        except HedgehogFabric.DoesNotExist:
            raise CommandError(f'Fabric "{fabric_name}" not found')
    
    def _process_fabric_raw_directory(self, fabric, options):
        """Process the raw directory for a single fabric."""
        if self.verbosity >= 2:
            self.stdout.write(f'Processing fabric: {fabric.name}')
        
        # Check if GitOps is initialized
        if not getattr(fabric, 'gitops_initialized', False):
            return {
                'success': False,
                'error': 'GitOps structure not initialized (run init_gitops first)'
            }
        
        if options['dry_run']:
            return {
                'success': True,
                'message': 'Would process raw directory (dry run)',
                'dry_run': True
            }
        
        try:
            service = GitOpsIngestionService(fabric)
            result = service.process_raw_directory()
            
            if self.verbosity >= 3:
                if result.get('files_processed'):
                    self.stdout.write(f'  Files processed: {len(result["files_processed"])}')
                if result.get('documents_extracted'):
                    self.stdout.write(f'  Documents extracted: {len(result["documents_extracted"])}')
            
            return result
            
        except Exception as e:
            logger.error(f'Raw directory processing failed for fabric {fabric.name}: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
    
    def _report_processing_success(self, fabric, result):
        """Report successful processing."""
        if result.get('dry_run'):
            self.stdout.write(
                self.style.WARNING(f'✓ {fabric.name}: {result["message"]}')
            )
        else:
            message = result.get('message', 'Processing completed')
            self.stdout.write(
                self.style.SUCCESS(f'✓ {fabric.name}: {message}')
            )
    
    def _report_processing_error(self, fabric, result):
        """Report failed processing."""
        error_msg = result.get('error', 'Unknown error')
        self.stderr.write(
            self.style.ERROR(f'✗ {fabric.name}: {error_msg}')
        )
        
        # Show detailed errors if available
        if 'errors' in result and self.verbosity >= 2:
            for error in result['errors']:
                self.stderr.write(f'    • {error}')
    
    def _print_processing_summary(self, success_count, error_count):
        """Print processing summary."""
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write('Processing Summary:')
        self.stdout.write(f'  Successful: {success_count}')
        self.stdout.write(f'  Errors: {error_count}')
        self.stdout.write(f'  Total: {success_count + error_count}')
        
        if error_count == 0:
            self.stdout.write(
                self.style.SUCCESS('\n✓ All fabrics processed successfully!')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'\n✗ {error_count} fabric(s) had errors')
            )
    
    def _stop_all_watchers(self):
        """Stop all running watchers."""
        for fabric_id, watcher in self.watchers.items():
            try:
                result = watcher.stop_watching()
                if self.verbosity >= 1:
                    self.stdout.write(f'Stopped watcher for fabric ID {fabric_id}')
            except Exception as e:
                if self.verbosity >= 1:
                    self.stderr.write(f'Error stopping watcher for fabric ID {fabric_id}: {str(e)}')
        
        self.watchers.clear()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        if self.watch_mode:
            self.stdout.write('\nReceived shutdown signal, stopping watchers...')
            self._stop_all_watchers()
        sys.exit(0)
    
    # Watcher callback methods
    def _on_files_detected(self, files):
        """Callback when files are detected."""
        self.stdout.write(f'Files detected: {[str(f) for f in files]}')
    
    def _on_processing_complete(self, result):
        """Callback when processing completes."""
        if result.get('successful_files', 0) > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Processed {result["successful_files"]} files successfully'
                )
            )
        if result.get('failed_files', 0) > 0:
            self.stderr.write(
                self.style.ERROR(
                    f'✗ Failed to process {result["failed_files"]} files'
                )
            )
    
    def _on_error(self, error):
        """Callback when an error occurs."""
        self.stderr.write(self.style.ERROR(f'Watcher error: {error}'))