"""
Legacy Architecture Migration Manager
Manages migration from legacy git configuration to new GitRepository architecture
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User

from ..models import HedgehogFabric, GitRepository
from ..utils.git_health_monitor import GitHealthMonitor
from ..utils.credential_manager import CredentialManager

logger = logging.getLogger(__name__)


@dataclass
class MigrationAnalysis:
    """Analysis of migration candidates and requirements"""
    total_fabrics: int
    migration_candidates: int
    already_migrated: int
    no_git_config: int
    migration_possible: bool
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    estimated_duration_minutes: int = 0


@dataclass
class MigrationResult:
    """Result of fabric migration operation"""
    success: bool
    fabric_id: int
    fabric_name: str
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    git_repository_id: Optional[int] = None
    git_repository_name: Optional[str] = None
    rollback_available: bool = False
    migration_time_seconds: float = 0


@dataclass
class BulkMigrationResult:
    """Result of bulk migration operation"""
    total_attempted: int
    successful_migrations: int
    failed_migrations: int
    results: List[MigrationResult] = field(default_factory=list)
    total_time_seconds: float = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of migration validation"""
    is_valid: bool
    fabric_id: int
    fabric_name: str
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    git_repository_status: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RollbackResult:
    """Result of migration rollback operation"""
    success: bool
    fabric_id: int
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationReport:
    """Comprehensive migration report"""
    generated_at: str
    analysis: MigrationAnalysis
    migrations_performed: List[MigrationResult] = field(default_factory=list)
    validation_results: List[ValidationResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


class LegacyArchitectureMigrationManager:
    """
    Manages migration from legacy to new GitRepository architecture.
    
    Provides comprehensive migration capabilities including analysis,
    individual and bulk migration, validation, and rollback support.
    """
    
    def __init__(self):
        self.logger = logger
    
    def analyze_migration_candidates(self) -> MigrationAnalysis:
        """
        Analyze fabrics for migration candidates and requirements.
        
        Returns:
            MigrationAnalysis with candidate information and recommendations
        """
        try:
            fabrics = HedgehogFabric.objects.all()
            total_fabrics = fabrics.count()
            
            candidates = []
            already_migrated = 0
            no_git_config = 0
            issues = []
            warnings = []
            
            for fabric in fabrics:
                if fabric.git_repository:
                    # Already using new architecture
                    already_migrated += 1
                    continue
                
                if not fabric.git_repository_url:
                    # No git configuration
                    no_git_config += 1
                    continue
                
                # Potential migration candidate
                candidate_info = self._analyze_fabric_for_migration(fabric)
                candidates.append(candidate_info)
                
                if candidate_info.get('issues'):
                    issues.extend(candidate_info['issues'])
                if candidate_info.get('warnings'):
                    warnings.extend(candidate_info['warnings'])
            
            migration_candidates = len(candidates)
            migration_possible = migration_candidates > 0 and len(issues) == 0
            
            # Estimate migration duration (2-5 minutes per fabric)
            base_time = migration_candidates * 3  # 3 minutes average per fabric
            complexity_factor = 1.0
            
            # Adjust for complexity
            for candidate in candidates:
                if candidate.get('has_credentials'):
                    complexity_factor += 0.2
                if candidate.get('multiple_paths'):
                    complexity_factor += 0.3
            
            estimated_duration = int(base_time * complexity_factor)
            
            return MigrationAnalysis(
                total_fabrics=total_fabrics,
                migration_candidates=migration_candidates,
                already_migrated=already_migrated,
                no_git_config=no_git_config,
                migration_possible=migration_possible,
                candidates=candidates,
                issues=issues,
                warnings=warnings,
                estimated_duration_minutes=estimated_duration
            )
            
        except Exception as e:
            self.logger.error(f"Migration analysis failed: {e}")
            return MigrationAnalysis(
                total_fabrics=0,
                migration_candidates=0,
                already_migrated=0,
                no_git_config=0,
                migration_possible=False,
                issues=[str(e)]
            )
    
    def migrate_fabric_configuration(self, fabric_id: int) -> MigrationResult:
        """
        Migrate individual fabric from legacy to new architecture.
        
        Args:
            fabric_id: ID of fabric to migrate
            
        Returns:
            MigrationResult with migration status and details
        """
        start_time = timezone.now()
        
        try:
            # Get fabric
            try:
                fabric = HedgehogFabric.objects.get(id=fabric_id)
            except HedgehogFabric.DoesNotExist:
                return MigrationResult(
                    success=False,
                    fabric_id=fabric_id,
                    fabric_name="Unknown",
                    error="Fabric not found"
                )
            
            # Check if already migrated
            if fabric.git_repository:
                return MigrationResult(
                    success=False,
                    fabric_id=fabric.id,
                    fabric_name=fabric.name,
                    error="Fabric already uses new GitRepository architecture"
                )
            
            # Check if has legacy configuration
            if not fabric.git_repository_url:
                return MigrationResult(
                    success=False,
                    fabric_id=fabric.id,
                    fabric_name=fabric.name,
                    error="No legacy git configuration found"
                )
            
            # Perform migration with transaction
            with transaction.atomic():
                # Create backup of current state
                backup_data = self._create_migration_backup(fabric)
                
                # Extract legacy configuration
                legacy_config = {
                    'url': fabric.git_repository_url,
                    'branch': fabric.git_branch,
                    'path': fabric.git_path,
                    'username': fabric.git_username,
                    'token': fabric.git_token
                }
                
                # Create or find existing GitRepository
                git_repository = self._create_or_find_git_repository(fabric, legacy_config)
                
                # Update fabric to use new architecture
                original_gitops_directory = fabric.gitops_directory
                
                fabric.git_repository = git_repository
                fabric.gitops_directory = legacy_config['path'] or '/'
                
                # Clear legacy fields (but keep for rollback)
                # Note: We'll keep legacy fields until migration is validated
                
                fabric.save()
                
                # Update git repository fabric count
                git_repository.update_fabric_count()
                
                # Validate migration
                validation_result = self._validate_migrated_fabric(fabric)
                
                migration_time = (timezone.now() - start_time).total_seconds()
                
                result = MigrationResult(
                    success=True,
                    fabric_id=fabric.id,
                    fabric_name=fabric.name,
                    details={
                        'legacy_config': legacy_config,
                        'new_git_repository_id': git_repository.id,
                        'new_git_repository_name': git_repository.name,
                        'gitops_directory': fabric.gitops_directory,
                        'validation_result': validation_result.__dict__,
                        'backup_data': backup_data,
                        'migration_timestamp': timezone.now().isoformat()
                    },
                    git_repository_id=git_repository.id,
                    git_repository_name=git_repository.name,
                    rollback_available=True,
                    migration_time_seconds=migration_time
                )
                
                self.logger.info(f"Successfully migrated fabric {fabric.name} (ID: {fabric.id})")
                return result
                
        except Exception as e:
            migration_time = (timezone.now() - start_time).total_seconds()
            self.logger.error(f"Migration failed for fabric {fabric_id}: {e}")
            
            return MigrationResult(
                success=False,
                fabric_id=fabric_id,
                fabric_name=getattr(fabric, 'name', 'Unknown') if 'fabric' in locals() else 'Unknown',
                error=str(e),
                migration_time_seconds=migration_time
            )
    
    def bulk_migrate_fabrics(self, fabric_ids: List[int]) -> BulkMigrationResult:
        """
        Migrate multiple fabrics in bulk with comprehensive error handling.
        
        Args:
            fabric_ids: List of fabric IDs to migrate
            
        Returns:
            BulkMigrationResult with overall status and individual results
        """
        start_time = timezone.now()
        results = []
        errors = []
        
        successful_migrations = 0
        failed_migrations = 0
        
        self.logger.info(f"Starting bulk migration of {len(fabric_ids)} fabrics")
        
        for fabric_id in fabric_ids:
            try:
                result = self.migrate_fabric_configuration(fabric_id)
                results.append(result)
                
                if result.success:
                    successful_migrations += 1
                    self.logger.info(f"Migration successful for fabric {result.fabric_name} ({fabric_id})")
                else:
                    failed_migrations += 1
                    self.logger.warning(f"Migration failed for fabric {result.fabric_name} ({fabric_id}): {result.error}")
                    
            except Exception as e:
                failed_migrations += 1
                error_msg = f"Bulk migration error for fabric {fabric_id}: {str(e)}"
                errors.append(error_msg)
                self.logger.error(error_msg)
                
                # Create failure result
                results.append(MigrationResult(
                    success=False,
                    fabric_id=fabric_id,
                    fabric_name="Unknown",
                    error=str(e)
                ))
        
        total_time = (timezone.now() - start_time).total_seconds()
        
        self.logger.info(
            f"Bulk migration completed: {successful_migrations} successful, "
            f"{failed_migrations} failed, {total_time:.2f} seconds"
        )
        
        return BulkMigrationResult(
            total_attempted=len(fabric_ids),
            successful_migrations=successful_migrations,
            failed_migrations=failed_migrations,
            results=results,
            total_time_seconds=total_time,
            errors=errors
        )
    
    def validate_migration_success(self, fabric_id: int) -> ValidationResult:
        """
        Validate that migration was successful and fabric is operational.
        
        Args:
            fabric_id: ID of migrated fabric to validate
            
        Returns:
            ValidationResult with validation status and details
        """
        try:
            fabric = HedgehogFabric.objects.get(id=fabric_id)
            
            issues = []
            warnings = []
            git_repository_status = {}
            
            # Check that fabric uses new architecture
            if not fabric.git_repository:
                issues.append("Fabric does not have git repository assigned")
            else:
                git_repository = fabric.git_repository
                
                # Test git repository connection
                try:
                    connection_result = git_repository.test_connection()
                    git_repository_status['connection_test'] = connection_result
                    
                    if not connection_result['success']:
                        issues.append(f"Git repository connection failed: {connection_result.get('error', 'Unknown error')}")
                except Exception as e:
                    issues.append(f"Git repository connection test failed: {str(e)}")
                
                # Check credential health
                try:
                    credential_manager = CredentialManager()
                    credential_health = credential_manager.get_credential_health(git_repository)
                    git_repository_status['credential_health'] = credential_health
                    
                    if not credential_health.get('healthy', False):
                        warnings.append("Git repository credentials may need attention")
                except Exception as e:
                    warnings.append(f"Credential health check failed: {str(e)}")
                
                # Check health monitoring
                try:
                    monitor = GitHealthMonitor(git_repository)
                    health_report = monitor.generate_health_report()
                    git_repository_status['health_report'] = health_report.to_dict()
                    
                    if health_report.overall_status == 'critical':
                        issues.append("Git repository health status is critical")
                    elif health_report.overall_status in ['unhealthy', 'degraded']:
                        warnings.append(f"Git repository health status is {health_report.overall_status}")
                except Exception as e:
                    warnings.append(f"Health monitoring check failed: {str(e)}")
            
            # Check gitops directory configuration
            if not fabric.gitops_directory or fabric.gitops_directory == '/':
                warnings.append("GitOps directory is root path - may cause conflicts")
            
            # Check for legacy configuration cleanup
            if fabric.git_repository_url:
                warnings.append("Legacy git configuration still present - consider cleanup")
            
            is_valid = len(issues) == 0
            
            return ValidationResult(
                is_valid=is_valid,
                fabric_id=fabric.id,
                fabric_name=fabric.name,
                issues=issues,
                warnings=warnings,
                git_repository_status=git_repository_status
            )
            
        except HedgehogFabric.DoesNotExist:
            return ValidationResult(
                is_valid=False,
                fabric_id=fabric_id,
                fabric_name="Not Found",
                issues=["Fabric not found"]
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                fabric_id=fabric_id,
                fabric_name="Unknown",
                issues=[str(e)]
            )
    
    def rollback_fabric_migration(self, fabric_id: int) -> RollbackResult:
        """
        Rollback fabric migration to legacy architecture.
        
        Args:
            fabric_id: ID of fabric to rollback
            
        Returns:
            RollbackResult with rollback status
        """
        try:
            fabric = HedgehogFabric.objects.get(id=fabric_id)
            
            if not fabric.git_repository:
                return RollbackResult(
                    success=False,
                    fabric_id=fabric.id,
                    error="Fabric is not using new GitRepository architecture"
                )
            
            # Check if legacy configuration is still available
            if not fabric.git_repository_url:
                return RollbackResult(
                    success=False,
                    fabric_id=fabric.id,
                    error="No legacy configuration available for rollback"
                )
            
            with transaction.atomic():
                # Store git repository for cleanup decision
                git_repository = fabric.git_repository
                
                # Restore legacy configuration
                fabric.git_repository = None
                fabric.gitops_directory = fabric.git_path or '/'
                fabric.save()
                
                # Update git repository fabric count
                git_repository.update_fabric_count()
                
                # Optionally clean up git repository if no longer used
                if git_repository.fabric_count == 0:
                    git_repository_name = git_repository.name
                    git_repository.delete()
                    cleanup_performed = True
                else:
                    git_repository_name = git_repository.name
                    cleanup_performed = False
                
                self.logger.info(f"Rolled back fabric {fabric.name} (ID: {fabric.id})")
                
                return RollbackResult(
                    success=True,
                    fabric_id=fabric.id,
                    details={
                        'git_repository_name': git_repository_name,
                        'git_repository_cleaned_up': cleanup_performed,
                        'restored_legacy_config': {
                            'url': fabric.git_repository_url,
                            'branch': fabric.git_branch,
                            'path': fabric.git_path
                        }
                    }
                )
                
        except HedgehogFabric.DoesNotExist:
            return RollbackResult(
                success=False,
                fabric_id=fabric_id,
                error="Fabric not found"
            )
        except Exception as e:
            self.logger.error(f"Rollback failed for fabric {fabric_id}: {e}")
            return RollbackResult(
                success=False,
                fabric_id=fabric_id,
                error=str(e)
            )
    
    def generate_migration_report(self) -> MigrationReport:
        """
        Generate comprehensive migration report.
        
        Returns:
            MigrationReport with analysis and recommendations
        """
        try:
            # Get migration analysis
            analysis = self.analyze_migration_candidates()
            
            # Get validation results for migrated fabrics
            validation_results = []
            migrated_fabrics = HedgehogFabric.objects.filter(git_repository__isnull=False)
            
            for fabric in migrated_fabrics:
                validation_result = self.validate_migration_success(fabric.id)
                validation_results.append(validation_result)
            
            # Generate summary
            total_migrated = len(validation_results)
            valid_migrations = sum(1 for result in validation_results if result.is_valid)
            
            summary = {
                'total_fabrics': analysis.total_fabrics,
                'migration_candidates': analysis.migration_candidates,
                'already_migrated': analysis.already_migrated,
                'migration_completion_rate': (analysis.already_migrated / analysis.total_fabrics * 100) if analysis.total_fabrics > 0 else 0,
                'valid_migrations': valid_migrations,
                'migration_success_rate': (valid_migrations / total_migrated * 100) if total_migrated > 0 else 0,
                'issues_found': sum(len(result.issues) for result in validation_results),
                'warnings_found': sum(len(result.warnings) for result in validation_results)
            }
            
            return MigrationReport(
                generated_at=timezone.now().isoformat(),
                analysis=analysis,
                validation_results=validation_results,
                summary=summary
            )
            
        except Exception as e:
            self.logger.error(f"Migration report generation failed: {e}")
            return MigrationReport(
                generated_at=timezone.now().isoformat(),
                analysis=MigrationAnalysis(
                    total_fabrics=0,
                    migration_candidates=0,
                    already_migrated=0,
                    no_git_config=0,
                    migration_possible=False,
                    issues=[str(e)]
                )
            )
    
    def _analyze_fabric_for_migration(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Analyze individual fabric for migration requirements"""
        info = {
            'fabric_id': fabric.id,
            'fabric_name': fabric.name,
            'fabric_status': fabric.status,
            'git_url': fabric.git_repository_url,
            'git_branch': fabric.git_branch,
            'git_path': fabric.git_path,
            'has_credentials': bool(fabric.git_username or fabric.git_token),
            'migration_complexity': 'simple',
            'issues': [],
            'warnings': [],
            'recommendations': []
        }
        
        # Check for potential issues
        if not fabric.git_repository_url.startswith(('https://', 'git@')):
            info['issues'].append("Invalid git URL format")
        
        if not fabric.git_branch:
            info['warnings'].append("No git branch specified - will use 'main'")
        
        if not fabric.git_path:
            info['warnings'].append("No git path specified - will use root directory")
        
        if not (fabric.git_username or fabric.git_token):
            info['warnings'].append("No credentials found - will need manual configuration")
            info['migration_complexity'] = 'complex'
        
        # Check for existing GitRepository with same URL
        existing_repo = GitRepository.objects.filter(url=fabric.git_repository_url).first()
        if existing_repo:
            info['existing_git_repository'] = {
                'id': existing_repo.id,
                'name': existing_repo.name,
                'created_by': existing_repo.created_by.username
            }
            info['recommendations'].append("Can reuse existing GitRepository")
        
        return info
    
    def _create_migration_backup(self, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Create backup of fabric state before migration"""
        return {
            'fabric_id': fabric.id,
            'git_repository_url': fabric.git_repository_url,
            'git_branch': fabric.git_branch,
            'git_path': fabric.git_path,
            'git_username': fabric.git_username,
            'git_token': fabric.git_token,
            'gitops_directory': fabric.gitops_directory,
            'backup_timestamp': timezone.now().isoformat()
        }
    
    def _create_or_find_git_repository(
        self, 
        fabric: HedgehogFabric, 
        legacy_config: Dict[str, Any]
    ) -> GitRepository:
        """Create new GitRepository or find existing one"""
        
        # Check for existing repository with same URL
        existing_repo = GitRepository.objects.filter(url=legacy_config['url']).first()
        
        if existing_repo:
            self.logger.info(f"Reusing existing GitRepository {existing_repo.name} for fabric {fabric.name}")
            return existing_repo
        
        # Create new GitRepository
        repo_data = {
            'name': f"{fabric.name} Repository",
            'url': legacy_config['url'],
            'provider': self._detect_git_provider(legacy_config['url']),
            'authentication_type': 'token' if legacy_config['token'] else 'basic',
            'description': f"Migrated from fabric {fabric.name}",
            'default_branch': legacy_config['branch'] or 'main',
            'is_private': True,  # Assume private for safety
            'created_by': fabric.created_by if hasattr(fabric, 'created_by') else User.objects.first()
        }
        
        git_repository = GitRepository.objects.create(**repo_data)
        
        # Set credentials if available
        credentials = {}
        if legacy_config['token']:
            credentials['token'] = legacy_config['token']
        elif legacy_config['username']:
            credentials['username'] = legacy_config['username']
            # Note: legacy password not available, will need manual configuration
        
        if credentials:
            git_repository.set_credentials(credentials)
            git_repository.save()
        
        self.logger.info(f"Created new GitRepository {git_repository.name} for fabric {fabric.name}")
        return git_repository
    
    def _detect_git_provider(self, url: str) -> str:
        """Detect git provider from URL"""
        if 'github.com' in url:
            return 'github'
        elif 'gitlab.com' in url:
            return 'gitlab'
        elif 'bitbucket.org' in url:
            return 'bitbucket'
        else:
            return 'generic'
    
    def _validate_migrated_fabric(self, fabric: HedgehogFabric) -> ValidationResult:
        """Validate fabric after migration"""
        return self.validate_migration_success(fabric.id)