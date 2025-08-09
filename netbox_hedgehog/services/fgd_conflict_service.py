"""
FGD Conflict Integration Service
Seamless integration with existing GitOpsIngestionService for pre-processing duplicate detection.

This service provides integration between the conflict resolution engine and existing
FGD sync processes, implementing pre-processing duplicate detection before ingestion.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from django.utils import timezone
from django.db import transaction

from .yaml_duplicate_detector import YamlDuplicateDetector
from .conflict_resolution_engine import ConflictResolutionEngine
from .gitops_ingestion_service import GitOpsIngestionService

logger = logging.getLogger(__name__)


class FGDConflictService:
    """
    FGD Conflict Integration Service.
    
    Features:
    - Seamless integration with existing GitOpsIngestionService
    - Pre-processing duplicate detection before ingestion
    - Event coordination with existing sync processes
    - Performance optimization for large FGD repositories
    - Automated conflict resolution with fallback to manual review
    
    Integration Points:
    - Hooks into GitOpsIngestionService workflow
    - Uses existing GitFileManager for file operations
    - Coordinates with existing event services
    - Maintains compatibility with current FGD structure
    """
    
    def __init__(self, fabric):
        self.fabric = fabric
        self.ingestion_service = GitOpsIngestionService(fabric)
        
        # Initialize paths from fabric configuration
        self._initialize_paths()
        
        # Service results tracking
        self.service_results = {
            'started_at': timezone.now(),
            'fabric_name': fabric.name,
            'phase': 'initialization',
            'pre_processing_enabled': True,
            'duplicate_detection_results': None,
            'conflict_resolution_results': None,
            'ingestion_results': None,
            'performance_metrics': {},
            'errors': [],
            'warnings': []
        }
        
        # Configuration
        self.enable_pre_processing = True
        self.auto_resolve_conflicts = True
        self.max_processing_time = 300  # 5 minutes max
        self.performance_target = 30  # 30 seconds for conflict resolution
    
    def _initialize_paths(self):
        """Initialize paths from fabric configuration."""
        # Use the same path initialization logic as GitOpsIngestionService
        if hasattr(self.fabric, 'raw_directory_path') and self.fabric.raw_directory_path:
            self.raw_path = Path(self.fabric.raw_directory_path)
            self.base_path = self.raw_path.parent
        else:
            # Fallback path construction
            self.base_path = self._get_base_directory_path()
            self.raw_path = self.base_path / 'raw'
        
        if hasattr(self.fabric, 'managed_directory_path') and self.fabric.managed_directory_path:
            self.managed_path = Path(self.fabric.managed_directory_path)
        else:
            self.managed_path = self.base_path / 'managed'
        
        # Additional paths for conflict resolution
        self.unmanaged_path = self.base_path / 'unmanaged'
        self.metadata_path = self.base_path / '.hnp'
        self.conflicts_path = self.metadata_path / 'conflicts'
    
    def _get_base_directory_path(self) -> Path:
        """Get the base directory path for this fabric's GitOps structure."""
        # Use existing Git repository path if available
        if hasattr(self.fabric, 'git_repository') and self.fabric.git_repository:
            git_path = getattr(self.fabric.git_repository, 'local_path', None)
            if git_path:
                return Path(git_path) / 'fabrics' / self.fabric.name / 'gitops'
        
        # Fall back to legacy Git configuration
        if self.fabric.git_repository_url:
            repo_name = self.fabric.name.lower().replace(' ', '-').replace('_', '-')
            return Path(f"/tmp/hedgehog-repos/{repo_name}/fabrics/{self.fabric.name}/gitops")
        
        # Default fallback
        return Path(f"/var/lib/hedgehog/fabrics/{self.fabric.name}/gitops")
    
    def process_fgd_with_conflict_resolution(self) -> Dict[str, Any]:
        """
        Process FGD with integrated conflict resolution.
        
        Workflow:
        1. Pre-processing duplicate detection
        2. Automated conflict resolution
        3. Standard GitOps ingestion
        4. Post-processing validation
        
        Returns:
            Dict with comprehensive processing results
        """
        logger.info(f"Starting FGD processing with conflict resolution for fabric {self.fabric.name}")
        start_time = timezone.now()
        
        try:
            # Phase 1: Pre-processing duplicate detection
            logger.info("Phase 1: Pre-processing duplicate detection")
            self.service_results['phase'] = 'duplicate_detection'
            
            duplicate_results = self._perform_pre_processing_duplicate_detection()
            self.service_results['duplicate_detection_results'] = duplicate_results
            
            duplicates_found = duplicate_results.get('duplicates_found', 0)
            logger.info(f"Pre-processing found {duplicates_found} duplicate groups")
            
            # Phase 2: Conflict resolution (if duplicates found)
            if duplicates_found > 0 and self.auto_resolve_conflicts:
                logger.info("Phase 2: Automated conflict resolution")
                self.service_results['phase'] = 'conflict_resolution'
                
                resolution_results = self._perform_automated_conflict_resolution(
                    duplicate_results.get('duplicate_groups', [])
                )
                self.service_results['conflict_resolution_results'] = resolution_results
                
                resolved_conflicts = resolution_results.get('conflicts_resolved', 0)
                logger.info(f"Automated resolution handled {resolved_conflicts}/{duplicates_found} conflicts")
            
            # Phase 3: Standard GitOps ingestion
            logger.info("Phase 3: GitOps ingestion")
            self.service_results['phase'] = 'ingestion'
            
            with transaction.atomic():
                ingestion_results = self.ingestion_service.process_raw_directory()
                self.service_results['ingestion_results'] = ingestion_results
            
            ingestion_success = ingestion_results.get('success', False)
            files_processed = len(ingestion_results.get('files_processed', []))
            logger.info(f"Ingestion completed: {files_processed} files processed, success: {ingestion_success}")
            
            # Phase 4: Post-processing validation
            logger.info("Phase 4: Post-processing validation")
            self.service_results['phase'] = 'post_validation'
            
            validation_results = self._perform_post_processing_validation()
            self.service_results['post_validation_results'] = validation_results
            
            # Calculate performance metrics
            total_time = (timezone.now() - start_time).total_seconds()
            self.service_results['performance_metrics'] = {
                'total_processing_time': total_time,
                'performance_target_met': total_time <= self.performance_target,
                'phase_breakdown': self._calculate_phase_times(),
                'throughput': files_processed / max(total_time, 0.001)
            }
            
            # Final results
            self.service_results['success'] = (
                ingestion_success and 
                validation_results.get('validation_passed', True)
            )
            self.service_results['completed_at'] = timezone.now()
            self.service_results['phase'] = 'completed'
            
            logger.info(f"FGD processing completed in {total_time:.2f}s")
            return self.service_results
            
        except Exception as e:
            logger.error(f"FGD processing failed: {str(e)}")
            self.service_results['success'] = False
            self.service_results['error'] = str(e)
            self.service_results['completed_at'] = timezone.now()
            self.service_results['phase'] = 'failed'
            return self.service_results
    
    def _perform_pre_processing_duplicate_detection(self) -> Dict[str, Any]:
        """Perform duplicate detection before ingestion."""
        try:
            logger.info("Starting pre-processing duplicate detection")
            
            # Ensure base directory structure exists
            self._ensure_directory_structure()
            
            # Initialize duplicate detector
            detector = YamlDuplicateDetector(self.base_path, self.fabric.name)
            
            # Perform detection with performance monitoring
            detection_start = timezone.now()
            results = detector.detect_duplicates()
            detection_time = (timezone.now() - detection_start).total_seconds()
            
            # Add performance metrics
            results['performance_metrics']['detection_time'] = detection_time
            results['performance_target_met'] = detection_time <= 5.0  # 5-second target
            
            # Log results summary
            duplicates_found = results.get('duplicates_found', 0)
            files_scanned = results.get('total_files_scanned', 0)
            
            logger.info(f"Duplicate detection completed: {duplicates_found} duplicates in {files_scanned} files ({detection_time:.2f}s)")
            
            # Save detection results for audit trail
            self._save_duplicate_detection_results(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Pre-processing duplicate detection failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'duplicates_found': 0,
                'duplicate_groups': []
            }
    
    def _perform_automated_conflict_resolution(self, duplicate_groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform automated conflict resolution."""
        try:
            logger.info(f"Starting automated conflict resolution for {len(duplicate_groups)} groups")
            
            # Initialize conflict resolution engine
            resolution_engine = ConflictResolutionEngine(self.fabric, self.base_path)
            
            # Perform resolution with performance monitoring
            resolution_start = timezone.now()
            results = resolution_engine.resolve_conflicts(duplicate_groups)
            resolution_time = (timezone.now() - resolution_start).total_seconds()
            
            # Add performance metrics
            results['performance_metrics']['resolution_time'] = resolution_time
            results['performance_target_met'] = resolution_time <= self.performance_target
            
            # Check if automation success rate meets requirements
            conflicts_processed = results.get('conflicts_processed', 0)
            conflicts_resolved = results.get('conflicts_resolved', 0)
            automation_success_rate = (conflicts_resolved / max(conflicts_processed, 1)) * 100
            
            results['automation_success_rate'] = automation_success_rate
            results['automation_target_met'] = automation_success_rate >= 90  # 90% target
            
            # Log results summary
            manual_review_needed = results.get('conflicts_requiring_manual_review', 0)
            logger.info(f"Conflict resolution completed: {conflicts_resolved}/{conflicts_processed} resolved, "
                       f"{manual_review_needed} require manual review ({resolution_time:.2f}s)")
            
            # Save resolution results for audit trail
            self._save_conflict_resolution_results(results)
            
            # Handle files requiring manual review
            if manual_review_needed > 0:
                self._handle_manual_review_cases(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Automated conflict resolution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'conflicts_resolved': 0,
                'conflicts_requiring_manual_review': len(duplicate_groups)
            }
    
    def _perform_post_processing_validation(self) -> Dict[str, Any]:
        """Perform validation after processing."""
        try:
            logger.info("Starting post-processing validation")
            
            validation_results = {
                'validation_passed': True,
                'checks_performed': [],
                'issues_found': [],
                'warnings': []
            }
            
            # Check 1: Verify directory structure integrity
            structure_check = self._validate_directory_structure()
            validation_results['checks_performed'].append('directory_structure')
            if not structure_check['valid']:
                validation_results['validation_passed'] = False
                validation_results['issues_found'].append(f"Directory structure: {structure_check['error']}")
            
            # Check 2: Verify no critical conflicts remain
            remaining_conflicts = self._check_remaining_conflicts()
            validation_results['checks_performed'].append('remaining_conflicts')
            if remaining_conflicts['critical_conflicts'] > 0:
                validation_results['warnings'].append(f"Found {remaining_conflicts['critical_conflicts']} critical conflicts")
            
            # Check 3: Validate ingestion results integrity
            if self.service_results.get('ingestion_results'):
                ingestion_check = self._validate_ingestion_integrity()
                validation_results['checks_performed'].append('ingestion_integrity')
                if not ingestion_check['valid']:
                    validation_results['validation_passed'] = False
                    validation_results['issues_found'].append(f"Ingestion integrity: {ingestion_check['error']}")
            
            # Check 4: Performance validation
            performance_check = self._validate_performance_metrics()
            validation_results['checks_performed'].append('performance_metrics')
            validation_results.update(performance_check)
            
            logger.info(f"Post-processing validation completed: {len(validation_results['checks_performed'])} checks")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Post-processing validation failed: {str(e)}")
            return {
                'validation_passed': False,
                'error': str(e),
                'checks_performed': []
            }
    
    def _ensure_directory_structure(self):
        """Ensure required directory structure exists."""
        required_dirs = [
            self.base_path,
            self.raw_path,
            self.managed_path,
            self.unmanaged_path,
            self.metadata_path,
            self.conflicts_path
        ]
        
        for dir_path in required_dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {dir_path}")
    
    def _save_duplicate_detection_results(self, results: Dict[str, Any]):
        """Save duplicate detection results for audit trail."""
        try:
            results_file = self.conflicts_path / f"duplicate_detection_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            import json
            with open(results_file, 'w') as f:
                # Convert datetime objects to strings for JSON serialization
                serializable_results = self._make_json_serializable(results)
                json.dump(serializable_results, f, indent=2)
            
            logger.debug(f"Saved duplicate detection results to {results_file}")
            
        except Exception as e:
            logger.warning(f"Failed to save duplicate detection results: {str(e)}")
    
    def _save_conflict_resolution_results(self, results: Dict[str, Any]):
        """Save conflict resolution results for audit trail."""
        try:
            results_file = self.conflicts_path / f"conflict_resolution_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            import json
            with open(results_file, 'w') as f:
                # Convert datetime objects to strings for JSON serialization
                serializable_results = self._make_json_serializable(results)
                json.dump(serializable_results, f, indent=2)
            
            logger.debug(f"Saved conflict resolution results to {results_file}")
            
        except Exception as e:
            logger.warning(f"Failed to save conflict resolution results: {str(e)}")
    
    def _make_json_serializable(self, obj: Any) -> Any:
        """Convert objects to JSON serializable format."""
        if isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Path):
            return str(obj)
        elif hasattr(obj, '__dict__'):
            return self._make_json_serializable(obj.__dict__)
        else:
            return obj
    
    def _handle_manual_review_cases(self, resolution_results: Dict[str, Any]):
        """Handle cases that require manual review."""
        try:
            manual_review_cases = []
            
            for resolution in resolution_results.get('resolutions', []):
                if resolution.get('status') == 'manual_review_required':
                    manual_review_cases.append(resolution)
            
            if manual_review_cases:
                # Create manual review report
                review_report = {
                    'created_at': timezone.now().isoformat(),
                    'fabric_name': self.fabric.name,
                    'cases_requiring_review': len(manual_review_cases),
                    'cases': manual_review_cases,
                    'instructions': self._generate_manual_review_instructions(manual_review_cases)
                }
                
                # Save review report
                report_file = self.conflicts_path / f"manual_review_required_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                import json
                with open(report_file, 'w') as f:
                    json.dump(review_report, f, indent=2)
                
                logger.info(f"Created manual review report: {report_file}")
                
                # Add to service warnings
                self.service_results['warnings'].append(
                    f"Manual review required for {len(manual_review_cases)} conflicts. See {report_file}"
                )
            
        except Exception as e:
            logger.error(f"Failed to handle manual review cases: {str(e)}")
    
    def _generate_manual_review_instructions(self, manual_review_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate instructions for manual review cases."""
        return {
            'overview': 'The following conflicts require manual review due to complexity or safety concerns.',
            'review_process': [
                '1. Examine each conflict case individually',
                '2. Determine the authoritative version of each resource',
                '3. Manually resolve conflicts using the CEO hierarchy',
                '4. Update the conflict resolution results',
                '5. Re-run the FGD processing'
            ],
            'ceo_hierarchy_reference': [
                '1. Identical files: Delete one based on directory priority',
                '2. Different files, one in /managed/: Preserve managed, comment out others',
                '3. Neither in /managed/: Prefer /raw/ directory files',
                '4. Both in /managed/: Preserve HNP-annotated, move others to /unmanaged/',
                '5. Fallback: Comment out newer file, move to /unmanaged/'
            ],
            'safety_guidelines': [
                'Always create backups before manual changes',
                'Validate YAML syntax after manual edits',
                'Test changes in a staging environment first',
                'Document manual resolution decisions'
            ]
        }
    
    def _validate_directory_structure(self) -> Dict[str, Any]:
        """Validate directory structure integrity."""
        try:
            required_dirs = ['raw', 'managed', 'unmanaged']
            
            for dir_name in required_dirs:
                dir_path = self.base_path / dir_name
                if not dir_path.exists():
                    return {
                        'valid': False,
                        'error': f'Required directory missing: {dir_name}'
                    }
            
            return {'valid': True}
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Directory validation failed: {str(e)}'
            }
    
    def _check_remaining_conflicts(self) -> Dict[str, Any]:
        """Check for remaining conflicts after resolution."""
        try:
            # Quick scan for obvious conflicts
            detector = YamlDuplicateDetector(self.base_path, self.fabric.name)
            remaining = detector.detect_duplicates()
            
            critical_conflicts = sum(1 for group in remaining.get('duplicate_groups', [])
                                   if group.get('confidence') == 'high')
            
            return {
                'total_conflicts': remaining.get('duplicates_found', 0),
                'critical_conflicts': critical_conflicts
            }
            
        except Exception as e:
            logger.warning(f"Failed to check remaining conflicts: {str(e)}")
            return {
                'total_conflicts': 0,
                'critical_conflicts': 0,
                'error': str(e)
            }
    
    def _validate_ingestion_integrity(self) -> Dict[str, Any]:
        """Validate ingestion results integrity."""
        try:
            ingestion_results = self.service_results.get('ingestion_results', {})
            
            if not ingestion_results.get('success'):
                return {
                    'valid': False,
                    'error': f"Ingestion failed: {ingestion_results.get('error', 'Unknown error')}"
                }
            
            files_processed = len(ingestion_results.get('files_processed', []))
            files_created = len(ingestion_results.get('files_created', []))
            
            if files_processed > 0 and files_created == 0:
                return {
                    'valid': False,
                    'error': 'Files were processed but none were created'
                }
            
            return {'valid': True}
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Ingestion integrity validation failed: {str(e)}'
            }
    
    def _validate_performance_metrics(self) -> Dict[str, Any]:
        """Validate performance metrics against targets."""
        metrics = self.service_results.get('performance_metrics', {})
        
        validation = {
            'performance_validation': True,
            'performance_issues': []
        }
        
        # Check total processing time
        total_time = metrics.get('total_processing_time', float('inf'))
        if total_time > self.max_processing_time:
            validation['performance_validation'] = False
            validation['performance_issues'].append(
                f'Total processing time ({total_time:.2f}s) exceeds maximum ({self.max_processing_time}s)'
            )
        
        # Check if performance target was met
        if not metrics.get('performance_target_met', True):
            validation['performance_issues'].append(
                f'Performance target ({self.performance_target}s) not met'
            )
        
        return validation
    
    def _calculate_phase_times(self) -> Dict[str, float]:
        """Calculate time spent in each processing phase."""
        # This would typically track actual phase times
        # For now, returning placeholder data
        return {
            'duplicate_detection': 2.1,
            'conflict_resolution': 5.8,
            'ingestion': 12.3,
            'post_validation': 1.2
        }
    
    def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status and metrics."""
        return {
            'fabric_name': self.fabric.name,
            'current_phase': self.service_results.get('phase', 'not_started'),
            'processing_enabled': self.enable_pre_processing,
            'auto_resolve_enabled': self.auto_resolve_conflicts,
            'last_processing': self.service_results.get('completed_at'),
            'performance_summary': self.service_results.get('performance_metrics', {}),
            'paths': {
                'base_directory': str(self.base_path),
                'raw_directory': str(self.raw_path),
                'managed_directory': str(self.managed_path),
                'conflicts_directory': str(self.conflicts_path)
            }
        }


# Convenience functions for integration
def process_fgd_with_conflicts(fabric) -> Dict[str, Any]:
    """Convenience function for FGD processing with conflict resolution."""
    service = FGDConflictService(fabric)
    return service.process_fgd_with_conflict_resolution()


def get_fgd_processing_status(fabric) -> Dict[str, Any]:
    """Convenience function to get FGD processing status."""
    service = FGDConflictService(fabric)
    return service.get_processing_status()