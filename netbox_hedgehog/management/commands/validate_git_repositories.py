"""
Management command for validating git repositories
Provides CLI interface for health monitoring and validation
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q

from netbox_hedgehog.models import GitRepository
from netbox_hedgehog.utils.git_health_monitor import GitHealthMonitor, HealthStatus


class Command(BaseCommand):
    help = 'Validate git repositories with comprehensive health checks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--repository-id',
            type=int,
            help='Specific repository ID to validate'
        )
        
        parser.add_argument(
            '--repository-name',
            type=str,
            help='Repository name pattern to match'
        )
        
        parser.add_argument(
            '--all',
            action='store_true',
            help='Validate all repositories'
        )
        
        parser.add_argument(
            '--failed-only',
            action='store_true',
            help='Only validate repositories with failed status'
        )
        
        parser.add_argument(
            '--stale-only',
            action='store_true',
            help='Only validate repositories not checked in last 24 hours'
        )
        
        parser.add_argument(
            '--check-branches',
            nargs='+',
            help='Check specific branches availability'
        )
        
        parser.add_argument(
            '--check-directories',
            nargs='+',
            help='Validate specific directories exist'
        )
        
        parser.add_argument(
            '--monitor-changes',
            action='store_true',
            help='Monitor repository for recent changes'
        )
        
        parser.add_argument(
            '--full-report',
            action='store_true',
            help='Generate full health report'
        )
        
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results as JSON'
        )
        
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to fix common issues'
        )
    
    def handle(self, *args, **options):
        # Get repositories to validate
        repositories = self._get_repositories(options)
        
        if not repositories:
            raise CommandError("No repositories found matching criteria")
        
        self.stdout.write(
            self.style.SUCCESS(f"Found {len(repositories)} repositories to validate")
        )
        
        # Run validation
        results = []
        for repo in repositories:
            self.stdout.write(f"\nValidating repository: {repo.name} (ID: {repo.id})")
            result = self._validate_repository(repo, options)
            results.append(result)
        
        # Output results
        if options['json']:
            self._output_json(results)
        else:
            self._output_human_readable(results)
        
        # Summary
        if not options['json']:
            self._print_summary(results)
    
    def _get_repositories(self, options) -> List[GitRepository]:
        """Get repositories based on command options"""
        query = GitRepository.objects.all()
        
        if options['repository_id']:
            query = query.filter(id=options['repository_id'])
        
        elif options['repository_name']:
            query = query.filter(name__icontains=options['repository_name'])
        
        elif options['failed_only']:
            query = query.filter(connection_status='failed')
        
        elif options['stale_only']:
            stale_date = timezone.now() - timedelta(hours=24)
            query = query.filter(
                Q(last_validated__lt=stale_date) | Q(last_validated__isnull=True)
            )
        
        elif not options['all']:
            raise CommandError(
                "Please specify --all, --repository-id, --repository-name, "
                "--failed-only, or --stale-only"
            )
        
        return list(query)
    
    def _validate_repository(self, repo: GitRepository, options) -> dict:
        """Validate a single repository"""
        monitor = GitHealthMonitor(repo)
        result = {
            'repository_id': repo.id,
            'repository_name': repo.name,
            'repository_url': repo.url,
            'timestamp': timezone.now().isoformat(),
            'checks': {}
        }
        
        # Run async checks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Basic health check
            if options['full_report'] or not any([
                options['check_branches'],
                options['check_directories'],
                options['monitor_changes']
            ]):
                self.stdout.write("  Running periodic health check...")
                health_check = loop.run_until_complete(
                    monitor.periodic_health_check()
                )
                result['checks']['health'] = health_check.to_dict()
                self._print_health_status(health_check)
            
            # Access validation
            self.stdout.write("  Validating repository access...")
            access_result = loop.run_until_complete(
                monitor.validate_repository_access()
            )
            result['checks']['access'] = {
                'result': access_result.result,
                'message': access_result.message,
                'details': access_result.details
            }
            self._print_validation_result("Access", access_result)
            
            # Branch checking
            if options['check_branches']:
                self.stdout.write(f"  Checking branches: {options['check_branches']}")
                branch_result = loop.run_until_complete(
                    monitor.check_branch_availability(options['check_branches'])
                )
                result['checks']['branches'] = branch_result.to_dict()
                self._print_branch_result(branch_result)
            
            # Directory validation
            if options['check_directories']:
                self.stdout.write(f"  Validating directories: {options['check_directories']}")
                dir_result = loop.run_until_complete(
                    monitor.validate_directory_structure(options['check_directories'])
                )
                result['checks']['directories'] = dir_result.to_dict()
                self._print_directory_result(dir_result)
            
            # Change monitoring
            if options['monitor_changes']:
                self.stdout.write("  Monitoring for changes...")
                change_result = loop.run_until_complete(
                    monitor.monitor_repository_changes()
                )
                result['checks']['changes'] = change_result.to_dict()
                self._print_change_result(change_result)
            
            # Generate full report if requested
            if options['full_report']:
                self.stdout.write("  Generating comprehensive health report...")
                report = monitor.generate_health_report()
                result['health_report'] = report.to_dict()
                self._print_health_report(report)
            
            # Attempt fixes if requested
            if options['fix']:
                self.stdout.write("  Attempting to fix issues...")
                fix_results = self._attempt_fixes(repo, result)
                result['fixes'] = fix_results
        
        finally:
            loop.close()
        
        return result
    
    def _print_health_status(self, health_check):
        """Print health check status"""
        status_colors = {
            HealthStatus.HEALTHY: self.style.SUCCESS,
            HealthStatus.DEGRADED: self.style.WARNING,
            HealthStatus.UNHEALTHY: self.style.ERROR,
            HealthStatus.CRITICAL: self.style.ERROR
        }
        
        color_func = status_colors.get(health_check.status, self.style.WARNING)
        self.stdout.write(
            f"    Status: {color_func(health_check.status.upper())}"
        )
        self.stdout.write(f"    Message: {health_check.message}")
        self.stdout.write(f"    Duration: {health_check.duration_ms}ms")
    
    def _print_validation_result(self, name: str, result):
        """Print validation result"""
        result_colors = {
            'passed': self.style.SUCCESS,
            'warning': self.style.WARNING,
            'failed': self.style.ERROR
        }
        
        color_func = result_colors.get(result.result, self.style.WARNING)
        self.stdout.write(
            f"    {name}: {color_func(result.result.upper())} - {result.message}"
        )
    
    def _print_branch_result(self, result):
        """Print branch check result"""
        self.stdout.write(f"    Available branches: {', '.join(result.available_branches)}")
        if result.missing_branches:
            self.stdout.write(
                self.style.WARNING(
                    f"    Missing branches: {', '.join(result.missing_branches)}"
                )
            )
        self.stdout.write(f"    Current commit: {result.current_commit[:8]}")
    
    def _print_directory_result(self, result):
        """Print directory validation result"""
        if result.valid_directories:
            self.stdout.write(
                self.style.SUCCESS(
                    f"    Valid directories: {', '.join(result.valid_directories)}"
                )
            )
        
        if result.missing_directories:
            self.stdout.write(
                self.style.WARNING(
                    f"    Missing directories: {', '.join(result.missing_directories)}"
                )
            )
        
        if result.crd_files_found:
            for directory, files in result.crd_files_found.items():
                self.stdout.write(
                    f"    CRDs in {directory}: {len(files)} file(s)"
                )
        
        if result.validation_errors:
            for error in result.validation_errors:
                self.stdout.write(self.style.ERROR(f"    Error: {error}"))
    
    def _print_change_result(self, result):
        """Print change detection result"""
        if result.has_changes:
            self.stdout.write(
                self.style.WARNING(
                    f"    Changes detected: {result.commits_since_last_check} new commits"
                )
            )
            
            if result.new_commits:
                self.stdout.write("    Recent commits:")
                for commit in result.new_commits[:5]:
                    self.stdout.write(
                        f"      {commit['sha']}: {commit['message']} "
                        f"({commit['author']})"
                    )
        else:
            self.stdout.write(self.style.SUCCESS("    No changes detected"))
    
    def _print_health_report(self, report):
        """Print comprehensive health report"""
        self.stdout.write("\n  === HEALTH REPORT ===")
        self.stdout.write(f"  Overall Status: {report.overall_status.upper()}")
        
        if report.performance_metrics:
            self.stdout.write("\n  Performance Metrics:")
            for key, value in report.performance_metrics.items():
                self.stdout.write(f"    {key}: {value}")
        
        if report.recommendations:
            self.stdout.write("\n  Recommendations:")
            for rec in report.recommendations:
                self.stdout.write(f"    - {rec}")
    
    def _attempt_fixes(self, repo: GitRepository, validation_result: dict) -> dict:
        """Attempt to fix common issues"""
        fixes = {
            'attempted': [],
            'successful': [],
            'failed': []
        }
        
        # Check if connection failed
        health_check = validation_result.get('checks', {}).get('health', {})
        if health_check.get('status') in ['unhealthy', 'critical']:
            fixes['attempted'].append('connection_test')
            
            # Try to reconnect
            self.stdout.write("    Attempting connection test...")
            try:
                test_result = repo.test_connection()
                if test_result.get('success'):
                    fixes['successful'].append('connection_test')
                    self.stdout.write(
                        self.style.SUCCESS("    ✓ Connection test successful")
                    )
                else:
                    fixes['failed'].append({
                        'fix': 'connection_test',
                        'error': test_result.get('error', 'Unknown error')
                    })
            except Exception as e:
                fixes['failed'].append({
                    'fix': 'connection_test',
                    'error': str(e)
                })
        
        # Update fabric count if needed
        fixes['attempted'].append('fabric_count_update')
        try:
            old_count = repo.fabric_count
            new_count = repo.update_fabric_count()
            if old_count != new_count:
                fixes['successful'].append('fabric_count_update')
                self.stdout.write(
                    self.style.SUCCESS(
                        f"    ✓ Updated fabric count: {old_count} → {new_count}"
                    )
                )
            else:
                self.stdout.write("    Fabric count already accurate")
        except Exception as e:
            fixes['failed'].append({
                'fix': 'fabric_count_update',
                'error': str(e)
            })
        
        return fixes
    
    def _output_json(self, results: List[dict]):
        """Output results as JSON"""
        output = {
            'validation_run': {
                'timestamp': timezone.now().isoformat(),
                'repository_count': len(results)
            },
            'results': results
        }
        
        self.stdout.write(json.dumps(output, indent=2))
    
    def _output_human_readable(self, results: List[dict]):
        """Output human-readable results (already printed during validation)"""
        pass  # Results are printed as we go
    
    def _print_summary(self, results: List[dict]):
        """Print validation summary"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("VALIDATION SUMMARY"))
        self.stdout.write("="*60)
        
        total = len(results)
        healthy = sum(
            1 for r in results
            if r.get('checks', {}).get('health', {}).get('status') == 'healthy'
        )
        degraded = sum(
            1 for r in results
            if r.get('checks', {}).get('health', {}).get('status') == 'degraded'
        )
        unhealthy = sum(
            1 for r in results
            if r.get('checks', {}).get('health', {}).get('status') in ['unhealthy', 'critical']
        )
        
        self.stdout.write(f"Total repositories validated: {total}")
        self.stdout.write(
            self.style.SUCCESS(f"  Healthy: {healthy}")
        )
        if degraded > 0:
            self.stdout.write(
                self.style.WARNING(f"  Degraded: {degraded}")
            )
        if unhealthy > 0:
            self.stdout.write(
                self.style.ERROR(f"  Unhealthy: {unhealthy}")
            )
        
        # Check for specific issues
        access_failures = sum(
            1 for r in results
            if r.get('checks', {}).get('access', {}).get('result') == 'failed'
        )
        
        if access_failures > 0:
            self.stdout.write(
                self.style.ERROR(
                    f"\n{access_failures} repositories have access issues"
                )
            )
        
        # Fixes summary
        total_fixes_attempted = sum(
            len(r.get('fixes', {}).get('attempted', []))
            for r in results if 'fixes' in r
        )
        total_fixes_successful = sum(
            len(r.get('fixes', {}).get('successful', []))
            for r in results if 'fixes' in r
        )
        
        if total_fixes_attempted > 0:
            self.stdout.write(
                f"\nFixes attempted: {total_fixes_attempted}, "
                f"Successful: {total_fixes_successful}"
            )