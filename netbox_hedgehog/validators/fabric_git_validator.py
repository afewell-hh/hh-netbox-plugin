"""
Fabric-Specific Git Validation
Implements validation logic specific to fabric git configuration requirements
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from django.core.exceptions import ValidationError

from ..models import HedgehogFabric, GitRepository
from ..utils.gitops_directory_validator import GitOpsDirectoryValidator

logger = logging.getLogger(__name__)


@dataclass
class FabricValidationResult:
    """Result of fabric-specific git validation"""
    is_valid: bool
    message: str
    details: Dict[str, Any] = None
    errors: List[str] = None
    warnings: List[str] = None
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.recommendations is None:
            self.recommendations = []


class FabricGitValidator:
    """
    Fabric-specific git configuration validator.
    
    Validates git repository assignments and configurations specifically
    for fabric requirements, including directory conflicts, repository
    sharing constraints, and operational considerations.
    """
    
    def __init__(self):
        self.logger = logger
    
    def validate_fabric_git_configuration(
        self,
        fabric: HedgehogFabric,
        git_repository_id: Optional[int] = None,
        gitops_directory: Optional[str] = None
    ) -> FabricValidationResult:
        """
        Validate complete fabric git configuration.
        
        Args:
            fabric: Fabric instance to validate
            git_repository_id: Optional git repository ID (for updates)
            gitops_directory: Optional gitops directory (for updates)
            
        Returns:
            FabricValidationResult with validation status and details
        """
        try:
            errors = []
            warnings = []
            recommendations = []
            details = {}
            
            # Use current values if not provided
            effective_repo_id = git_repository_id or (fabric.git_repository.id if fabric.git_repository else None)
            effective_directory = gitops_directory or fabric.gitops_directory
            
            if not effective_repo_id:
                return FabricValidationResult(
                    is_valid=True,
                    message="No git repository configured - validation skipped",
                    details={'validation_skipped': True, 'reason': 'no_git_repository'}
                )
            
            # Get git repository
            try:
                git_repository = GitRepository.objects.get(id=effective_repo_id)
                details['git_repository'] = {
                    'id': git_repository.id,
                    'name': git_repository.name,
                    'url': git_repository.url,
                    'provider': git_repository.provider,
                    'connection_status': git_repository.connection_status
                }
            except GitRepository.DoesNotExist:
                errors.append(f"Git repository with ID {effective_repo_id} not found")
                return FabricValidationResult(
                    is_valid=False,
                    message="Git repository validation failed",
                    errors=errors,
                    details=details
                )
            
            # Validate repository accessibility
            repo_validation = self._validate_repository_accessibility(fabric, git_repository)
            if not repo_validation.is_valid:
                errors.extend(repo_validation.errors)
                warnings.extend(repo_validation.warnings)
            
            # Validate directory configuration
            if effective_directory:
                directory_validation = self._validate_directory_configuration(
                    fabric, git_repository, effective_directory
                )
                if not directory_validation.is_valid:
                    errors.extend(directory_validation.errors)
                warnings.extend(directory_validation.warnings)
                details['directory_validation'] = directory_validation.details
            
            # Validate repository sharing constraints
            sharing_validation = self._validate_repository_sharing(
                fabric, git_repository, effective_directory
            )
            if not sharing_validation.is_valid:
                errors.extend(sharing_validation.errors)
            warnings.extend(sharing_validation.warnings)
            recommendations.extend(sharing_validation.recommendations)
            details['sharing_validation'] = sharing_validation.details
            
            # Validate operational requirements
            operational_validation = self._validate_operational_requirements(fabric, git_repository)
            warnings.extend(operational_validation.warnings)
            recommendations.extend(operational_validation.recommendations)
            details['operational_validation'] = operational_validation.details
            
            # Validate fabric-specific constraints
            fabric_validation = self._validate_fabric_constraints(fabric, git_repository, effective_directory)
            if not fabric_validation.is_valid:
                errors.extend(fabric_validation.errors)
            warnings.extend(fabric_validation.warnings)
            details['fabric_constraints'] = fabric_validation.details
            
            is_valid = len(errors) == 0
            
            return FabricValidationResult(
                is_valid=is_valid,
                message="Fabric git configuration validation passed" if is_valid else f"Validation failed with {len(errors)} errors",
                details=details,
                errors=errors,
                warnings=warnings,
                recommendations=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Fabric git validation failed: {e}")
            return FabricValidationResult(
                is_valid=False,
                message="Validation failed due to error",
                errors=[str(e)],
                details={'exception_type': type(e).__name__}
            )
    
    def _validate_repository_accessibility(
        self,
        fabric: HedgehogFabric,
        git_repository: GitRepository
    ) -> FabricValidationResult:
        """Validate repository accessibility and connection status"""
        errors = []
        warnings = []
        details = {}
        
        # Check connection status
        if git_repository.connection_status == 'failed':
            errors.append("Git repository connection is in failed state")
            details['connection_issue'] = git_repository.validation_error
        elif git_repository.connection_status == 'pending':
            warnings.append("Git repository connection has not been tested")
        elif git_repository.connection_status == 'testing':
            warnings.append("Git repository connection test is in progress")
        
        # Check last validation time
        if git_repository.last_validated:
            from django.utils import timezone
            from datetime import timedelta
            
            time_since_validation = timezone.now() - git_repository.last_validated
            if time_since_validation > timedelta(days=7):
                warnings.append(f"Git repository was last validated {time_since_validation.days} days ago")
        else:
            warnings.append("Git repository has never been validated")
        
        # Check for credentials
        if not git_repository.encrypted_credentials:
            warnings.append("Git repository has no stored credentials")
        
        details['connection_status'] = git_repository.connection_status
        details['last_validated'] = git_repository.last_validated.isoformat() if git_repository.last_validated else None
        details['has_credentials'] = bool(git_repository.encrypted_credentials)
        
        return FabricValidationResult(
            is_valid=len(errors) == 0,
            message="Repository accessibility validation passed" if len(errors) == 0 else "Repository accessibility issues found",
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def _validate_directory_configuration(
        self,
        fabric: HedgehogFabric,
        git_repository: GitRepository,
        directory: str
    ) -> FabricValidationResult:
        """Validate directory configuration and conflicts"""
        errors = []
        warnings = []
        details = {}
        
        try:
            # Use GitOpsDirectoryValidator for core validation
            validator = GitOpsDirectoryValidator()
            result = validator.validate_gitops_directory_assignment(
                git_repository.id, directory, exclude_fabric_id=fabric.id
            )
            
            if not result.is_valid:
                errors.extend(result.errors)
            
            details['directory_conflicts'] = result.conflicts if hasattr(result, 'conflicts') else []
            details['directory_suggestions'] = result.suggestions
            details['normalized_path'] = result.normalized_path if hasattr(result, 'normalized_path') else directory
            
            # Additional fabric-specific directory validation
            if directory == '/':
                warnings.append("Using root directory may cause conflicts with other fabrics")
            
            if not directory.startswith('/'):
                errors.append("GitOps directory must be an absolute path starting with '/'")
            
            if '..' in directory:
                errors.append("GitOps directory cannot contain '..' path segments")
            
            # Check for common problematic patterns
            problematic_patterns = ['.git', '__pycache__', '.DS_Store', 'node_modules']
            for pattern in problematic_patterns:
                if pattern in directory:
                    warnings.append(f"Directory path contains '{pattern}' which may cause issues")
            
        except Exception as e:
            errors.append(f"Directory validation failed: {str(e)}")
        
        details['directory_path'] = directory
        
        return FabricValidationResult(
            is_valid=len(errors) == 0,
            message="Directory configuration validation passed" if len(errors) == 0 else "Directory configuration issues found",
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def _validate_repository_sharing(
        self,
        fabric: HedgehogFabric,
        git_repository: GitRepository,
        directory: str
    ) -> FabricValidationResult:
        """Validate repository sharing constraints and best practices"""
        errors = []
        warnings = []
        recommendations = []
        details = {}
        
        # Get other fabrics using this repository
        other_fabrics = HedgehogFabric.objects.filter(
            git_repository=git_repository
        ).exclude(id=fabric.id)
        
        fabric_count = other_fabrics.count()
        details['shared_with_fabrics'] = fabric_count
        details['sharing_fabrics'] = []
        
        if fabric_count > 0:
            # Repository is shared
            warnings.append(f"Git repository is shared with {fabric_count} other fabric(s)")
            
            for other_fabric in other_fabrics:
                fabric_info = {
                    'id': other_fabric.id,
                    'name': other_fabric.name,
                    'directory': other_fabric.gitops_directory,
                    'status': other_fabric.status
                }
                details['sharing_fabrics'].append(fabric_info)
                
                # Check for directory conflicts
                if other_fabric.gitops_directory == directory:
                    errors.append(f"Directory '{directory}' is already used by fabric '{other_fabric.name}'")
                
                # Check for nested directories (potential conflicts)
                if directory.startswith(other_fabric.gitops_directory.rstrip('/') + '/'):
                    warnings.append(f"Directory is nested under fabric '{other_fabric.name}' directory")
                elif other_fabric.gitops_directory.startswith(directory.rstrip('/') + '/'):
                    warnings.append(f"Fabric '{other_fabric.name}' directory is nested under this directory")
            
            # Recommendations for shared repositories
            recommendations.extend([
                "Consider using descriptive directory names to avoid conflicts",
                "Ensure directory permissions are appropriate for shared access",
                "Monitor changes to avoid conflicts between fabrics"
            ])
        
        # Repository utilization analysis
        total_capacity = git_repository.fabric_count if git_repository.fabric_count > 0 else 1
        utilization_percentage = (fabric_count / total_capacity) * 100
        
        if utilization_percentage > 80:
            warnings.append("Repository is heavily utilized - consider performance implications")
        
        details['utilization_percentage'] = utilization_percentage
        
        return FabricValidationResult(
            is_valid=len(errors) == 0,
            message="Repository sharing validation passed" if len(errors) == 0 else "Repository sharing conflicts detected",
            errors=errors,
            warnings=warnings,
            recommendations=recommendations,
            details=details
        )
    
    def _validate_operational_requirements(
        self,
        fabric: HedgehogFabric,
        git_repository: GitRepository
    ) -> FabricValidationResult:
        """Validate operational requirements and best practices"""
        warnings = []
        recommendations = []
        details = {}
        
        # Check GitOps tool compatibility
        gitops_tool = fabric.gitops_tool
        details['gitops_tool'] = gitops_tool
        
        if gitops_tool == 'manual':
            recommendations.append("Consider configuring a GitOps tool (ArgoCD, Flux) for automated deployments")
        elif gitops_tool in ['argocd', 'flux']:
            if not fabric.gitops_app_name:
                warnings.append(f"{gitops_tool} is configured but no application name is set")
        
        # Check sync configuration
        if not fabric.sync_enabled:
            warnings.append("Sync is disabled - fabric will not automatically update from Kubernetes")
        elif fabric.sync_interval < 60:
            warnings.append("Sync interval is very short - may cause high load")
        elif fabric.sync_interval > 3600:
            warnings.append("Sync interval is very long - changes may not be detected promptly")
        
        # Check credential health if available
        try:
            from ..utils.credential_manager import CredentialManager
            credential_manager = CredentialManager()
            credential_health = credential_manager.get_credential_health(git_repository)
            
            if credential_health.get('rotation_due'):
                age_days = credential_health.get('age_days', 0)
                if age_days > 365:
                    warnings.append(f"Git repository credentials are {age_days} days old - rotation recommended")
                elif age_days > 180:
                    recommendations.append("Consider rotating git repository credentials")
        except Exception as e:
            self.logger.debug(f"Credential health check failed: {e}")
        
        # Repository provider-specific recommendations
        provider = git_repository.provider
        if provider == 'github':
            recommendations.append("Consider using GitHub App authentication for better security")
        elif provider == 'gitlab':
            recommendations.append("Consider using GitLab Deploy Keys for repository-specific access")
        elif provider == 'generic':
            recommendations.append("Specify the git provider for optimized configuration")
        
        details['sync_configuration'] = {
            'enabled': fabric.sync_enabled,
            'interval': fabric.sync_interval,
            'auto_sync': fabric.auto_sync_enabled,
            'prune': fabric.prune_enabled,
            'self_heal': fabric.self_heal_enabled
        }
        
        return FabricValidationResult(
            is_valid=True,  # Operational validation doesn't fail, only warns/recommends
            message="Operational requirements validation completed",
            warnings=warnings,
            recommendations=recommendations,
            details=details
        )
    
    def _validate_fabric_constraints(
        self,
        fabric: HedgehogFabric,
        git_repository: GitRepository,
        directory: str
    ) -> FabricValidationResult:
        """Validate fabric-specific constraints"""
        errors = []
        warnings = []
        details = {}
        
        # Check fabric status constraints
        if fabric.status == 'retired' and git_repository.connection_status == 'connected':
            warnings.append("Retired fabric still has active git repository connection")
        
        # Check namespace compatibility
        k8s_namespace = fabric.kubernetes_namespace
        if k8s_namespace and directory:
            # Ensure directory doesn't conflict with namespace name
            if directory.strip('/').lower() == k8s_namespace.lower():
                warnings.append("GitOps directory name matches Kubernetes namespace - may cause confusion")
        
        # Check for fabric naming consistency
        fabric_name_normalized = fabric.name.lower().replace(' ', '-')
        directory_name = directory.strip('/').split('/')[-1] if directory.strip('/') else ''
        
        if directory_name and directory_name != fabric_name_normalized:
            recommendations = [f"Consider using directory name that matches fabric name: '/{fabric_name_normalized}/'"]
        else:
            recommendations = []
        
        # Validate fabric configuration completeness
        config_completeness = {
            'has_kubernetes_config': bool(fabric.kubernetes_server),
            'has_git_config': bool(git_repository),
            'has_gitops_directory': bool(directory and directory != '/'),
            'has_gitops_tool': fabric.gitops_tool != 'manual',
            'sync_enabled': fabric.sync_enabled
        }
        
        complete_items = sum(config_completeness.values())
        total_items = len(config_completeness)
        completeness_percentage = (complete_items / total_items) * 100
        
        if completeness_percentage < 80:
            warnings.append(f"Fabric configuration is {completeness_percentage:.0f}% complete")
        
        details['fabric_status'] = fabric.status
        details['configuration_completeness'] = config_completeness
        details['completeness_percentage'] = completeness_percentage
        
        return FabricValidationResult(
            is_valid=len(errors) == 0,
            message="Fabric constraints validation passed" if len(errors) == 0 else "Fabric constraint violations found",
            errors=errors,
            warnings=warnings,
            recommendations=recommendations,
            details=details
        )