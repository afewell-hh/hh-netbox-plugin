"""
Unified Fabric Creation Workflow
Implements unified fabric creation workflow using GitRepository architecture
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from ..models import HedgehogFabric, GitRepository
from ..utils.gitops_directory_validator import GitOpsDirectoryValidator
from ..utils.git_health_monitor import GitHealthMonitor
from ..utils.credential_manager import CredentialManager

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validation operations"""
    is_valid: bool
    message: str
    errors: list = None
    warnings: list = None
    details: dict = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.details is None:
            self.details = {}


@dataclass
class CreationResult:
    """Result of fabric creation operations"""
    success: bool
    fabric: Optional[HedgehogFabric] = None
    error: Optional[str] = None
    details: Dict[str, Any] = None
    rollback_performed: bool = False
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class IntegrationResult:
    """Result of git integration setup"""
    success: bool
    message: str
    health_status: dict = None
    credential_status: dict = None
    directory_validation: dict = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.health_status is None:
            self.health_status = {}
        if self.credential_status is None:
            self.credential_status = {}
        if self.directory_validation is None:
            self.directory_validation = {}


class UnifiedFabricCreationWorkflow:
    """
    Unified fabric creation workflow using GitRepository architecture.
    
    This class implements the consolidated fabric creation process that eliminates
    dual pathways by integrating GitRepository selection and validation into a
    single, comprehensive workflow.
    """
    
    def __init__(self, user: User):
        """
        Initialize workflow for specific user.
        
        Args:
            user: User creating the fabric
        """
        self.user = user
        self.logger = logging.getLogger(f"{__name__}.{user.username}")
    
    def validate_fabric_configuration(self, fabric_data: Dict) -> ValidationResult:
        """
        Validate fabric configuration before creation.
        
        Args:
            fabric_data: Fabric configuration dictionary
            
        Returns:
            ValidationResult with validation status and details
        """
        try:
            errors = []
            warnings = []
            details = {}
            
            # Required field validation
            if not fabric_data.get('name'):
                errors.append("Fabric name is required")
            
            # Name uniqueness validation
            if fabric_data.get('name'):
                if HedgehogFabric.objects.filter(name=fabric_data['name']).exists():
                    errors.append(f"Fabric with name '{fabric_data['name']}' already exists")
            
            # Kubernetes configuration validation
            k8s_server = fabric_data.get('kubernetes_server')
            if k8s_server and not k8s_server.startswith(('http://', 'https://')):
                errors.append("Kubernetes server URL must start with http:// or https://")
            
            # Namespace validation
            k8s_namespace = fabric_data.get('kubernetes_namespace', 'default')
            if not k8s_namespace.replace('-', '').replace('_', '').isalnum():
                errors.append("Kubernetes namespace contains invalid characters")
            
            # Status validation
            valid_statuses = ['planned', 'active', 'maintenance', 'retired']
            if fabric_data.get('status') and fabric_data['status'] not in valid_statuses:
                warnings.append(f"Status '{fabric_data['status']}' is not a standard status")
            
            details['validation_checks'] = {
                'name_check': 'passed' if fabric_data.get('name') else 'failed',
                'uniqueness_check': 'passed' if not HedgehogFabric.objects.filter(
                    name=fabric_data.get('name', '')
                ).exists() else 'failed',
                'kubernetes_config': 'passed' if not k8s_server or k8s_server.startswith(
                    ('http://', 'https://')
                ) else 'failed',
                'namespace_format': 'passed' if k8s_namespace.replace(
                    '-', ''
                ).replace('_', '').isalnum() else 'failed'
            }
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                message='Validation passed' if len(errors) == 0 else f'{len(errors)} validation errors found',
                errors=errors,
                warnings=warnings,
                details=details
            )
            
        except Exception as e:
            self.logger.error(f"Fabric configuration validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                message='Validation failed due to error',
                errors=[str(e)]
            )
    
    def create_fabric_with_git_repository(
        self, 
        fabric_data: Dict, 
        git_repo_id: int, 
        directory: str
    ) -> CreationResult:
        """
        Create fabric with existing GitRepository selection and directory validation.
        
        Args:
            fabric_data: Fabric configuration dictionary
            git_repo_id: ID of existing GitRepository
            directory: GitOps directory path within repository
            
        Returns:
            CreationResult with creation status and fabric instance
        """
        try:
            # Validate fabric configuration
            fabric_validation = self.validate_fabric_configuration(fabric_data)
            if not fabric_validation.is_valid:
                return CreationResult(
                    success=False,
                    error='Fabric configuration validation failed',
                    details={
                        'validation_errors': fabric_validation.errors,
                        'validation_warnings': fabric_validation.warnings
                    }
                )
            
            # Get and validate git repository
            try:
                git_repository = GitRepository.objects.get(
                    id=git_repo_id,
                    created_by=self.user
                )
            except GitRepository.DoesNotExist:
                return CreationResult(
                    success=False,
                    error='Git repository not found or access denied'
                )
            
            # Validate directory assignment
            directory_validation = self.validate_gitops_directory_assignment(
                git_repo_id, directory
            )
            if not directory_validation.is_valid:
                return CreationResult(
                    success=False,
                    error='GitOps directory validation failed',
                    details={
                        'directory_errors': directory_validation.errors,
                        'directory_suggestions': directory_validation.details.get('suggestions', [])
                    }
                )
            
            # Create fabric with transaction rollback support
            with transaction.atomic():
                # Prepare fabric data
                fabric_data_clean = {
                    'name': fabric_data['name'],
                    'description': fabric_data.get('description', ''),
                    'status': fabric_data.get('status', 'planned'),
                    'kubernetes_server': fabric_data.get('kubernetes_server', ''),
                    'kubernetes_token': fabric_data.get('kubernetes_token', ''),
                    'kubernetes_ca_cert': fabric_data.get('kubernetes_ca_cert', ''),
                    'kubernetes_namespace': fabric_data.get('kubernetes_namespace', 'default'),
                    'sync_enabled': fabric_data.get('sync_enabled', True),
                    'sync_interval': fabric_data.get('sync_interval', 300),
                    # New architecture fields
                    'git_repository': git_repository,
                    'gitops_directory': directory,
                    # GitOps configuration
                    'gitops_tool': fabric_data.get('gitops_tool', 'manual'),
                    'auto_sync_enabled': fabric_data.get('auto_sync_enabled', True),
                    'prune_enabled': fabric_data.get('prune_enabled', False),
                    'self_heal_enabled': fabric_data.get('self_heal_enabled', True)
                }
                
                # Create fabric
                fabric = HedgehogFabric.objects.create(**fabric_data_clean)
                
                # Update git repository fabric count
                git_repository.update_fabric_count()
                
                # Setup git integration
                integration_result = self.setup_fabric_git_integration(fabric)
                
                if not integration_result.success:
                    # Log warning but don't fail creation
                    self.logger.warning(
                        f"Git integration setup failed for fabric {fabric.id}: "
                        f"{integration_result.error}"
                    )
                
                return CreationResult(
                    success=True,
                    fabric=fabric,
                    details={
                        'fabric_id': fabric.id,
                        'fabric_name': fabric.name,
                        'git_repository_id': git_repository.id,
                        'git_repository_name': git_repository.name,
                        'gitops_directory': directory,
                        'integration_status': integration_result.success,
                        'integration_details': integration_result.__dict__,
                        'validation_warnings': fabric_validation.warnings
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Fabric creation failed: {e}")
            return CreationResult(
                success=False,
                error=str(e),
                details={'exception_type': type(e).__name__}
            )
    
    def create_fabric_with_new_repository(
        self, 
        fabric_data: Dict, 
        git_config: Dict
    ) -> CreationResult:
        """
        Create fabric with new GitRepository creation and setup.
        
        Args:
            fabric_data: Fabric configuration dictionary
            git_config: Git repository configuration
            
        Returns:
            CreationResult with creation status and fabric instance
        """
        try:
            # Validate fabric configuration
            fabric_validation = self.validate_fabric_configuration(fabric_data)
            if not fabric_validation.is_valid:
                return CreationResult(
                    success=False,
                    error='Fabric configuration validation failed',
                    details={
                        'validation_errors': fabric_validation.errors,
                        'validation_warnings': fabric_validation.warnings
                    }
                )
            
            # Validate git configuration
            git_validation = self._validate_git_configuration(git_config)
            if not git_validation.is_valid:
                return CreationResult(
                    success=False,
                    error='Git configuration validation failed',
                    details={
                        'git_errors': git_validation.errors,
                        'git_warnings': git_validation.warnings
                    }
                )
            
            # Create with transaction rollback support
            with transaction.atomic():
                # Create git repository first
                git_repository_data = {
                    'name': git_config['name'],
                    'url': git_config['url'],
                    'provider': git_config.get('provider', 'generic'),
                    'authentication_type': git_config.get('authentication_type', 'token'),
                    'description': git_config.get('description', f"Repository for {fabric_data['name']}"),
                    'default_branch': git_config.get('default_branch', 'main'),
                    'is_private': git_config.get('is_private', True),
                    'validate_ssl': git_config.get('validate_ssl', True),
                    'timeout_seconds': git_config.get('timeout_seconds', 30),
                    'created_by': self.user
                }
                
                git_repository = GitRepository.objects.create(**git_repository_data)
                
                # Set credentials if provided
                if git_config.get('credentials'):
                    git_repository.set_credentials(git_config['credentials'])
                    git_repository.save()
                
                # Test connection if credentials provided
                if git_config.get('credentials') and git_config.get('test_connection', True):
                    connection_result = git_repository.test_connection()
                    if not connection_result['success']:
                        self.logger.warning(
                            f"Initial connection test failed for repository {git_repository.id}: "
                            f"{connection_result.get('error', 'Unknown error')}"
                        )
                
                # Create fabric with new repository
                directory = git_config.get('gitops_directory', '/')
                creation_result = self.create_fabric_with_git_repository(
                    fabric_data, git_repository.id, directory
                )
                
                if not creation_result.success:
                    # Delete the git repository if fabric creation fails
                    git_repository.delete()
                    return creation_result
                
                # Update result details
                creation_result.details.update({
                    'created_git_repository': True,
                    'git_repository_id': git_repository.id,
                    'git_repository_name': git_repository.name,
                    'connection_test_performed': git_config.get('test_connection', True),
                    'connection_test_result': connection_result if git_config.get('credentials') else None
                })
                
                return creation_result
                
        except Exception as e:
            self.logger.error(f"Fabric creation with new repository failed: {e}")
            return CreationResult(
                success=False,
                error=str(e),
                details={'exception_type': type(e).__name__}
            )
    
    def validate_gitops_directory_assignment(
        self, 
        git_repo_id: int, 
        directory: str
    ) -> ValidationResult:
        """
        Validate GitOps directory assignment for conflicts.
        
        Args:
            git_repo_id: Git repository ID
            directory: Directory path to validate
            
        Returns:
            ValidationResult with validation status and suggestions
        """
        try:
            validator = GitOpsDirectoryValidator()
            result = validator.validate_gitops_directory_assignment(git_repo_id, directory)
            
            return ValidationResult(
                is_valid=result.is_valid,
                message=result.message if hasattr(result, 'message') else (
                    'Directory validation passed' if result.is_valid else 'Directory conflicts detected'
                ),
                errors=result.errors,
                warnings=result.warnings if hasattr(result, 'warnings') else [],
                details={
                    'conflicts': result.conflicts if hasattr(result, 'conflicts') else [],
                    'suggestions': result.suggestions,
                    'normalized_path': result.normalized_path if hasattr(result, 'normalized_path') else directory
                }
            )
            
        except Exception as e:
            self.logger.error(f"Directory validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                message='Directory validation failed due to error',
                errors=[str(e)]
            )
    
    def setup_fabric_git_integration(self, fabric: HedgehogFabric) -> IntegrationResult:
        """
        Setup git integration for newly created fabric WITH GitOps directory initialization.
        
        This method now includes GitOps directory initialization to enable upstream GitHub
        changes that external GitOps tools (ArgoCD/Flux) can detect and sync.
        
        Args:
            fabric: Fabric instance to setup integration for
            
        Returns:
            IntegrationResult with integration status and GitOps initialization details
        """
        try:
            if not fabric.git_repository:
                return IntegrationResult(
                    success=False,
                    message='No git repository configured for fabric',
                    error='Git repository not assigned to fabric'
                )
            
            # Perform health check
            try:
                monitor = GitHealthMonitor(fabric.git_repository)
                health_report = monitor.generate_health_report()
                health_status = health_report.to_dict()
            except Exception as e:
                self.logger.warning(f"Health check failed during integration setup: {e}")
                health_status = {'error': str(e), 'status': 'unknown'}
            
            # Check credential health
            try:
                credential_manager = CredentialManager()
                credential_health = credential_manager.get_credential_health(fabric.git_repository)
                credential_status = credential_health
            except Exception as e:
                self.logger.warning(f"Credential health check failed: {e}")
                credential_status = {'error': str(e), 'healthy': False}
            
            # Validate directory assignment
            try:
                validator = GitOpsDirectoryValidator()
                directory_result = validator.validate_gitops_directory_assignment(
                    fabric.git_repository.id, 
                    fabric.gitops_directory,
                    exclude_fabric_id=fabric.id
                )
                directory_validation = {
                    'valid': directory_result.is_valid,
                    'errors': directory_result.errors,
                    'suggestions': directory_result.suggestions
                }
            except Exception as e:
                self.logger.warning(f"Directory validation failed during integration: {e}")
                directory_validation = {'error': str(e), 'valid': False}
            
            # INTEGRATION FIX: Initialize GitOps directory structure
            gitops_initialization = {'attempted': False, 'success': False}
            
            if fabric.git_repository and fabric.gitops_directory and directory_validation.get('valid', False):
                try:
                    self.logger.info(f"Initializing GitOps directory structure for fabric {fabric.name}")
                    
                    # Import GitOpsDirectoryManager for directory initialization
                    from ..services.bidirectional_sync.gitops_directory_manager import GitOpsDirectoryManager
                    
                    # Initialize GitOps directory using existing implementation
                    manager = GitOpsDirectoryManager(fabric)
                    init_result = manager.initialize_directory_structure(force=False)
                    
                    gitops_initialization = {
                        'attempted': True,
                        'success': init_result.success,
                        'message': init_result.message,
                        'directories_created': init_result.directories_created,
                        'errors': init_result.errors,
                        'warnings': init_result.warnings
                    }
                    
                    if init_result.success:
                        # Update fabric GitOps initialization status
                        fabric.gitops_initialized = True
                        fabric.gitops_directory_status = 'initialized'
                        fabric.directory_init_error = ''
                        fabric.last_directory_sync = timezone.now()
                        fabric.save(update_fields=[
                            'gitops_initialized', 
                            'gitops_directory_status', 
                            'directory_init_error',
                            'last_directory_sync'
                        ])
                        
                        self.logger.info(f"GitOps directory initialized successfully for fabric {fabric.id}")
                    else:
                        # Update fabric with error status but don't fail creation
                        fabric.gitops_directory_status = 'error'
                        fabric.directory_init_error = '; '.join(init_result.errors)
                        fabric.save(update_fields=['gitops_directory_status', 'directory_init_error'])
                        
                        self.logger.warning(f"GitOps directory initialization had errors for fabric {fabric.id}: {init_result.errors}")
                    
                except Exception as e:
                    error_msg = f"GitOps directory initialization failed for fabric {fabric.id}: {str(e)}"
                    self.logger.error(error_msg)
                    
                    gitops_initialization = {
                        'attempted': True,
                        'success': False,
                        'error': str(e)
                    }
                    
                    # Update fabric with error status but don't fail creation
                    try:
                        fabric.gitops_directory_status = 'error'
                        fabric.directory_init_error = str(e)
                        fabric.save(update_fields=['gitops_directory_status', 'directory_init_error'])
                    except Exception:
                        # If fabric fields don't exist yet, just log and continue
                        self.logger.warning(f"Could not update GitOps status fields for fabric {fabric.id}")
            else:
                self.logger.info(f"Skipping GitOps initialization for fabric {fabric.id} - prerequisites not met")
                gitops_initialization = {
                    'attempted': False,
                    'success': False,
                    'reason': 'Prerequisites not met (repository, directory, or validation failed)'
                }
            
            # Update fabric timestamps
            fabric.last_git_sync = timezone.now()
            fabric.save(update_fields=['last_git_sync'])
            
            integration_success = (
                health_status.get('status') != 'critical' and
                credential_status.get('healthy', False) and
                directory_validation.get('valid', False)
            )
            
            # Note: We don't require GitOps initialization success for integration success
            # This maintains backward compatibility and prevents fabric creation failures
            
            success_message = 'Git integration setup completed'
            if gitops_initialization.get('success'):
                success_message += ' with GitOps directory initialization'
            elif gitops_initialization.get('attempted'):
                success_message += ' (GitOps initialization had warnings)'
            
            return IntegrationResult(
                success=integration_success,
                message=success_message,
                health_status=health_status,
                credential_status=credential_status,
                directory_validation=directory_validation
            )
            
        except Exception as e:
            self.logger.error(f"Git integration setup failed: {e}")
            return IntegrationResult(
                success=False,
                message='Git integration setup failed',
                error=str(e)
            )
    
    def _validate_git_configuration(self, git_config: Dict) -> ValidationResult:
        """
        Validate git repository configuration.
        
        Args:
            git_config: Git configuration dictionary
            
        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        
        # Required fields
        if not git_config.get('name'):
            errors.append("Git repository name is required")
        
        if not git_config.get('url'):
            errors.append("Git repository URL is required")
        
        # URL format validation
        url = git_config.get('url', '')
        if url and not (url.startswith('https://') or url.startswith('git@')):
            errors.append("Git URL must start with 'https://' or 'git@'")
        
        # Authentication validation
        auth_type = git_config.get('authentication_type', 'token')
        credentials = git_config.get('credentials', {})
        
        if auth_type == 'token' and not credentials.get('token'):
            errors.append("Token is required for token authentication")
        elif auth_type == 'basic':
            if not credentials.get('username') or not credentials.get('password'):
                errors.append("Username and password are required for basic authentication")
        elif auth_type == 'ssh_key' and not credentials.get('private_key'):
            errors.append("Private key is required for SSH key authentication")
        
        # Name uniqueness (for this user)
        if git_config.get('name'):
            existing = GitRepository.objects.filter(
                name=git_config['name'],
                created_by=self.user
            ).exists()
            if existing:
                errors.append(f"Git repository name '{git_config['name']}' already exists for this user")
        
        # URL uniqueness (for this user)
        if git_config.get('url'):
            existing = GitRepository.objects.filter(
                url=git_config['url'],
                created_by=self.user
            ).exists()
            if existing:
                warnings.append(f"Git repository URL already exists for this user")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            message='Git configuration valid' if len(errors) == 0 else f'{len(errors)} validation errors found',
            errors=errors,
            warnings=warnings
        )