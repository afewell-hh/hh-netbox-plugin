"""
Management command to initialize GitOps file management structure for fabrics.

Usage:
    python manage.py init_gitops --fabric <fabric_name>
    python manage.py init_gitops --all
    python manage.py init_gitops --fabric <fabric_name> --force
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.services.gitops_onboarding_service import GitOpsOnboardingService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize GitOps file management structure for Hedgehog fabrics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fabric',
            type=str,
            help='Name of the fabric to initialize (required unless --all is used)'
        )
        
        parser.add_argument(
            '--all',
            action='store_true',
            help='Initialize GitOps structure for all fabrics'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force initialization even if already initialized'
        )
        
        parser.add_argument(
            '--base-directory',
            type=str,
            help='Override base directory path (for testing)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only validate existing structure without initializing'
        )
    
    def handle(self, *args, **options):
        """Main command handler."""
        self.verbosity = options['verbosity']
        
        try:
            # Determine which fabrics to process
            fabrics = self._get_fabrics_to_process(options)
            
            if not fabrics:
                raise CommandError('No fabrics found to process')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Processing {len(fabrics)} fabric(s) for GitOps initialization'
                )
            )
            
            # Process each fabric
            total_success = 0
            total_errors = 0
            
            for fabric in fabrics:
                try:
                    if options['validate_only']:
                        result = self._validate_fabric_structure(fabric)
                    else:
                        result = self._initialize_fabric(fabric, options)
                    
                    if result['success']:
                        total_success += 1
                        self._report_success(fabric, result)
                    else:
                        total_errors += 1
                        self._report_error(fabric, result)
                        
                except Exception as e:
                    total_errors += 1
                    self.stderr.write(
                        self.style.ERROR(
                            f'Unexpected error processing fabric {fabric.name}: {str(e)}'
                        )
                    )
            
            # Summary
            self._print_summary(total_success, total_errors, options['validate_only'])
            
            # Exit with error code if any failures
            if total_errors > 0:
                exit(1)
                
        except Exception as e:
            raise CommandError(f'Command failed: {str(e)}')
    
    def _get_fabrics_to_process(self, options):
        """Determine which fabrics to process based on command options."""
        if options['all']:
            return HedgehogFabric.objects.all()
        elif options['fabric']:
            try:
                fabric = HedgehogFabric.objects.get(name=options['fabric'])
                return [fabric]
            except HedgehogFabric.DoesNotExist:
                raise CommandError(f'Fabric "{options["fabric"]}" not found')
        else:
            raise CommandError('Either --fabric or --all must be specified')
    
    def _initialize_fabric(self, fabric, options):
        """Initialize GitOps structure for a single fabric."""
        if self.verbosity >= 2:
            self.stdout.write(f'Processing fabric: {fabric.name}')
        
        # Check if already initialized
        if hasattr(fabric, 'gitops_initialized') and fabric.gitops_initialized and not options['force']:
            return {
                'success': True,
                'message': 'GitOps structure already initialized (use --force to reinitialize)',
                'skipped': True
            }
        
        # Dry run check
        if options['dry_run']:
            return {
                'success': True,
                'message': 'Would initialize GitOps structure (dry run)',
                'dry_run': True
            }
        
        # Initialize using GitOpsOnboardingService
        try:
            service = GitOpsOnboardingService(fabric)
            result = service.initialize_gitops_structure(options.get('base_directory'))
            
            if self.verbosity >= 3 and result.get('directories_created'):
                self.stdout.write(f'  Created directories: {len(result["directories_created"])}')
            if self.verbosity >= 3 and result.get('files_migrated'):
                self.stdout.write(f'  Migrated files: {len(result["files_migrated"])}')
            
            return result
            
        except Exception as e:
            logger.error(f'GitOps initialization failed for fabric {fabric.name}: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
    
    def _validate_fabric_structure(self, fabric):
        """Validate existing GitOps structure for a fabric."""
        if self.verbosity >= 2:
            self.stdout.write(f'Validating fabric: {fabric.name}')
        
        try:
            service = GitOpsOnboardingService(fabric)
            validation_result = service.validate_structure()
            
            return {
                'success': validation_result['valid'],
                'validation_result': validation_result,
                'message': f'Validation {"passed" if validation_result["valid"] else "failed"}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Validation error: {str(e)}'
            }
    
    def _report_success(self, fabric, result):
        """Report successful initialization or validation."""
        if result.get('skipped'):
            self.stdout.write(
                self.style.WARNING(f'✓ {fabric.name}: {result["message"]}')
            )
        elif result.get('dry_run'):
            self.stdout.write(
                self.style.WARNING(f'✓ {fabric.name}: {result["message"]}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✓ {fabric.name}: {result.get("message", "Success")}')
            )
        
        # Show validation details if available
        if 'validation_result' in result and self.verbosity >= 2:
            validation = result['validation_result']
            for check in validation.get('checks', []):
                self.stdout.write(f'    {check}')
            for warning in validation.get('warnings', []):
                self.stdout.write(self.style.WARNING(f'    {warning}'))
    
    def _report_error(self, fabric, result):
        """Report failed initialization or validation."""
        error_msg = result.get('error', 'Unknown error')
        self.stderr.write(
            self.style.ERROR(f'✗ {fabric.name}: {error_msg}')
        )
        
        # Show validation errors if available
        if 'validation_result' in result and self.verbosity >= 1:
            validation = result['validation_result']
            for error in validation.get('errors', []):
                self.stderr.write(f'    {error}')
        
        # Show detailed errors if available
        if 'errors' in result and self.verbosity >= 2:
            for error in result['errors']:
                self.stderr.write(f'    • {error}')
    
    def _print_summary(self, success_count, error_count, validate_only):
        """Print command execution summary."""
        operation = "Validation" if validate_only else "Initialization"
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(f'{operation} Summary:')
        self.stdout.write(f'  Successful: {success_count}')
        self.stdout.write(f'  Errors: {error_count}')
        self.stdout.write(f'  Total: {success_count + error_count}')
        
        if error_count == 0:
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ All fabrics processed successfully!')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'\n✗ {error_count} fabric(s) had errors')
            )