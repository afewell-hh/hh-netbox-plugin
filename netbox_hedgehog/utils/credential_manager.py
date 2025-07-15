"""
Credential Lifecycle Management for Git Repositories
Provides rotation, validation, and lifecycle tracking capabilities
"""

import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from ..models import GitRepository
from ..choices import GitAuthenticationTypeChoices

logger = logging.getLogger('netbox_hedgehog.credential_manager')


class CredentialStrength(str, Enum):
    """Credential strength levels"""
    STRONG = 'strong'
    MODERATE = 'moderate'
    WEAK = 'weak'
    INVALID = 'invalid'


class RotationStatus(str, Enum):
    """Credential rotation status"""
    SUCCESS = 'success'
    FAILED = 'failed'
    PENDING = 'pending'
    ROLLBACK = 'rollback'


@dataclass
class RotationResult:
    """Result of credential rotation operation"""
    status: RotationStatus
    message: str
    old_credential_backup: Optional[Dict[str, Any]]
    timestamp: datetime
    rollback_available: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'rollback_available': self.rollback_available
        }


@dataclass
class ValidationResult:
    """Result of credential validation"""
    is_valid: bool
    strength: CredentialStrength
    issues: List[str]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CredentialHealthStatus:
    """Health status of credentials"""
    age_days: int
    last_validated: Optional[datetime]
    last_rotated: Optional[datetime]
    rotation_due: bool
    health_score: int  # 0-100
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'age_days': self.age_days,
            'last_validated': self.last_validated.isoformat() if self.last_validated else None,
            'last_rotated': self.last_rotated.isoformat() if self.last_rotated else None,
            'rotation_due': self.rotation_due,
            'health_score': self.health_score,
            'recommendations': self.recommendations
        }


@dataclass
class PermissionScopeResult:
    """Result of permission scope validation"""
    read_access: bool
    write_access: bool
    admin_access: bool
    specific_permissions: List[str]
    missing_permissions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CredentialBackup:
    """Backup of credentials for rollback"""
    repository_id: int
    encrypted_credentials: str
    authentication_type: str
    backed_up_at: datetime
    backup_reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'repository_id': self.repository_id,
            'authentication_type': self.authentication_type,
            'backed_up_at': self.backed_up_at.isoformat(),
            'backup_reason': self.backup_reason
        }


@dataclass
class ThoroughTestResult:
    """Result of thorough credential testing"""
    all_tests_passed: bool
    connection_test: Dict[str, Any]
    permission_test: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CredentialManager:
    """Manages credential lifecycle for git repositories"""
    
    # Credential age thresholds (in days)
    ROTATION_RECOMMENDED_DAYS = 90
    ROTATION_REQUIRED_DAYS = 180
    ROTATION_CRITICAL_DAYS = 365
    
    def __init__(self):
        self.logger = logger
        self._backup_storage: Dict[int, List[CredentialBackup]] = {}
    
    def rotate_credentials(
        self,
        repository: GitRepository,
        new_credentials: Dict[str, Any],
        rotation_reason: str = "Scheduled rotation"
    ) -> RotationResult:
        """
        Rotate credentials with validation and rollback capability.
        
        Args:
            repository: GitRepository instance
            new_credentials: New credentials to set
            rotation_reason: Reason for rotation
            
        Returns:
            RotationResult with operation status
        """
        try:
            # Create backup of current credentials
            backup = self._create_credential_backup(repository, rotation_reason)
            
            # Validate new credentials format
            validation_result = self._validate_credential_format(
                new_credentials,
                repository.authentication_type
            )
            
            if not validation_result.is_valid:
                return RotationResult(
                    status=RotationStatus.FAILED,
                    message=f"Invalid credential format: {', '.join(validation_result.issues)}",
                    old_credential_backup=backup.to_dict() if backup else None,
                    timestamp=timezone.now(),
                    rollback_available=False
                )
            
            # Store old credentials for rollback
            old_credentials = repository.get_credentials()
            old_connection_status = repository.connection_status
            
            # Apply new credentials
            with transaction.atomic():
                repository.set_credentials(new_credentials)
                repository.save()
                
                # Test new credentials
                test_result = repository.test_connection()
                
                if not test_result.get('success'):
                    # Rollback on failure
                    raise ValidationError(
                        f"Connection test failed with new credentials: {test_result.get('error')}"
                    )
                
                # Update credential metadata
                self._update_credential_metadata(repository, 'rotation')
                
                # Store successful backup
                self._store_backup(backup)
                
                return RotationResult(
                    status=RotationStatus.SUCCESS,
                    message="Credentials rotated successfully",
                    old_credential_backup=backup.to_dict(),
                    timestamp=timezone.now(),
                    rollback_available=True
                )
                
        except ValidationError as e:
            # Rollback to old credentials
            repository.set_credentials(old_credentials)
            repository.connection_status = old_connection_status
            repository.save()
            
            return RotationResult(
                status=RotationStatus.ROLLBACK,
                message=f"Rotation failed, rolled back: {str(e)}",
                old_credential_backup=None,
                timestamp=timezone.now(),
                rollback_available=False
            )
            
        except Exception as e:
            self.logger.error(f"Credential rotation error: {str(e)}")
            return RotationResult(
                status=RotationStatus.FAILED,
                message=f"Unexpected error during rotation: {str(e)}",
                old_credential_backup=None,
                timestamp=timezone.now(),
                rollback_available=False
            )
    
    def validate_credential_strength(
        self,
        repository: GitRepository
    ) -> ValidationResult:
        """
        Validate credential strength and security requirements.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            ValidationResult with strength assessment
        """
        credentials = repository.get_credentials()
        auth_type = repository.authentication_type
        
        if not credentials:
            return ValidationResult(
                is_valid=False,
                strength=CredentialStrength.INVALID,
                issues=["No credentials configured"],
                recommendations=["Configure authentication credentials"]
            )
        
        if auth_type == GitAuthenticationTypeChoices.TOKEN:
            return self._validate_token_strength(credentials.get('token', ''))
        elif auth_type == GitAuthenticationTypeChoices.SSH_KEY:
            return self._validate_ssh_key_strength(
                credentials.get('private_key', ''),
                credentials.get('passphrase', '')
            )
        elif auth_type == GitAuthenticationTypeChoices.BASIC:
            return self._validate_basic_auth_strength(
                credentials.get('username', ''),
                credentials.get('password', '')
            )
        elif auth_type == GitAuthenticationTypeChoices.OAUTH:
            return self._validate_oauth_strength(credentials)
        else:
            return ValidationResult(
                is_valid=False,
                strength=CredentialStrength.INVALID,
                issues=[f"Unknown authentication type: {auth_type}"],
                recommendations=["Update to supported authentication type"]
            )
    
    def schedule_credential_rotation(
        self,
        repository: GitRepository,
        rotation_date: datetime,
        notification_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Schedule credential rotation for a future date.
        
        Args:
            repository: GitRepository instance
            rotation_date: When to rotate credentials
            notification_email: Optional email for notifications
            
        Returns:
            Dictionary with scheduling details
        """
        # Store rotation schedule in repository metadata
        # In a real implementation, this would use a task scheduler
        metadata = {
            'rotation_scheduled': rotation_date.isoformat(),
            'notification_email': notification_email,
            'scheduled_at': timezone.now().isoformat()
        }
        
        # Store in repository description or custom field
        current_desc = repository.description or ''
        if 'ROTATION_SCHEDULE:' in current_desc:
            # Update existing schedule
            import re
            pattern = r'ROTATION_SCHEDULE:\{.*?\}'
            new_schedule = f'ROTATION_SCHEDULE:{json.dumps(metadata)}'
            repository.description = re.sub(pattern, new_schedule, current_desc)
        else:
            # Add new schedule
            repository.description = f"{current_desc}\n\nROTATION_SCHEDULE:{json.dumps(metadata)}"
        
        repository.save()
        
        return {
            'scheduled': True,
            'rotation_date': rotation_date.isoformat(),
            'repository_id': repository.id,
            'notification_configured': bool(notification_email)
        }
    
    def get_credential_health(
        self,
        repository: GitRepository
    ) -> CredentialHealthStatus:
        """
        Get comprehensive credential health status.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            CredentialHealthStatus with health metrics
        """
        # Get credential metadata
        metadata = self._get_credential_metadata(repository)
        
        # Calculate age
        created_date = metadata.get('created_date', repository.created)
        age_days = (timezone.now() - created_date).days
        
        # Get last rotation date
        last_rotated = metadata.get('last_rotated')
        
        # Calculate rotation due
        rotation_due = age_days > self.ROTATION_RECOMMENDED_DAYS
        rotation_overdue = age_days > self.ROTATION_REQUIRED_DAYS
        rotation_critical = age_days > self.ROTATION_CRITICAL_DAYS
        
        # Calculate health score (0-100)
        health_score = 100
        
        # Deduct for age
        if rotation_critical:
            health_score -= 50
        elif rotation_overdue:
            health_score -= 30
        elif rotation_due:
            health_score -= 15
        
        # Deduct for validation status
        if repository.connection_status != 'connected':
            health_score -= 20
        
        # Deduct for missing validations
        if not repository.last_validated:
            health_score -= 10
        elif (timezone.now() - repository.last_validated).days > 7:
            health_score -= 5
        
        # Generate recommendations
        recommendations = []
        
        if rotation_critical:
            recommendations.append("CRITICAL: Credentials are over 1 year old - rotate immediately")
        elif rotation_overdue:
            recommendations.append("Credentials are overdue for rotation (>180 days)")
        elif rotation_due:
            recommendations.append("Consider rotating credentials (>90 days old)")
        
        if repository.connection_status != 'connected':
            recommendations.append("Validate credentials - connection is not working")
        
        validation_result = self.validate_credential_strength(repository)
        if validation_result.strength == CredentialStrength.WEAK:
            recommendations.append("Credential strength is weak - consider using stronger credentials")
        
        return CredentialHealthStatus(
            age_days=age_days,
            last_validated=repository.last_validated,
            last_rotated=last_rotated,
            rotation_due=rotation_due,
            health_score=max(0, health_score),
            recommendations=recommendations
        )
    
    def backup_credentials(
        self,
        repository: GitRepository,
        backup_reason: str = "Manual backup"
    ) -> CredentialBackup:
        """
        Create a backup of current credentials.
        
        Args:
            repository: GitRepository instance
            backup_reason: Reason for backup
            
        Returns:
            CredentialBackup instance
        """
        backup = self._create_credential_backup(repository, backup_reason)
        self._store_backup(backup)
        return backup
    
    def restore_credentials(
        self,
        repository: GitRepository,
        backup: CredentialBackup
    ) -> 'RestoreResult':
        """
        Restore credentials from backup.
        
        Args:
            repository: GitRepository instance
            backup: CredentialBackup to restore
            
        Returns:
            RestoreResult with operation status
        """
        try:
            # Validate backup matches repository
            if backup.repository_id != repository.id:
                return RestoreResult(
                    success=False,
                    message="Backup does not match repository",
                    restored_from=backup.backed_up_at
                )
            
            # Store current state for potential rollback
            current_creds = repository.encrypted_credentials
            current_auth_type = repository.authentication_type
            
            with transaction.atomic():
                # Restore credentials
                repository.encrypted_credentials = backup.encrypted_credentials
                repository.authentication_type = backup.authentication_type
                repository.save()
                
                # Test restored credentials
                test_result = repository.test_connection()
                
                if not test_result.get('success'):
                    raise ValidationError(
                        f"Restored credentials failed validation: {test_result.get('error')}"
                    )
                
                # Update metadata
                self._update_credential_metadata(repository, 'restore')
                
                return RestoreResult(
                    success=True,
                    message="Credentials restored successfully",
                    restored_from=backup.backed_up_at
                )
                
        except Exception as e:
            # Rollback on failure
            repository.encrypted_credentials = current_creds
            repository.authentication_type = current_auth_type
            repository.save()
            
            return RestoreResult(
                success=False,
                message=f"Restore failed: {str(e)}",
                restored_from=backup.backed_up_at
            )
    
    def test_credentials_thoroughly(
        self,
        repository: GitRepository
    ) -> ThoroughTestResult:
        """
        Perform thorough credential testing including permissions.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            ThoroughTestResult with comprehensive test results
        """
        start_time = timezone.now()
        recommendations = []
        
        # Basic connection test
        connection_test = repository.test_connection()
        connection_passed = connection_test.get('success', False)
        
        # Permission testing
        permission_test = {
            'read_access': False,
            'write_access': False,
            'error': None
        }
        
        if connection_passed:
            # Test read permissions
            try:
                import tempfile
                import git
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Clone with depth 1 to test read
                    clone_result = repository.clone_repository(
                        temp_dir,
                        branch=repository.default_branch
                    )
                    
                    if clone_result.get('success'):
                        permission_test['read_access'] = True
                        
                        # For write test, we'd need to actually push
                        # This is a heuristic based on auth type
                        if repository.authentication_type in ['token', 'ssh_key']:
                            permission_test['write_access'] = True
                            recommendations.append(
                                "Write access assumed based on authentication type"
                            )
                    
            except Exception as e:
                permission_test['error'] = str(e)
        
        # Calculate performance metrics
        duration_ms = int((timezone.now() - start_time).total_seconds() * 1000)
        performance_metrics = {
            'total_duration_ms': duration_ms,
            'connection_test_ms': connection_test.get('duration_ms', 0)
        }
        
        # Generate recommendations
        if not connection_passed:
            recommendations.append("Fix connection issues before testing permissions")
        
        if permission_test['read_access'] and not permission_test['write_access']:
            recommendations.append("Consider upgrading credentials for write access")
        
        if duration_ms > 5000:
            recommendations.append("Performance is slow - consider using SSH keys")
        
        # Determine overall result
        all_tests_passed = (
            connection_passed and
            permission_test['read_access']
        )
        
        return ThoroughTestResult(
            all_tests_passed=all_tests_passed,
            connection_test=connection_test,
            permission_test=permission_test,
            performance_metrics=performance_metrics,
            recommendations=recommendations
        )
    
    def validate_permission_scope(
        self,
        repository: GitRepository
    ) -> PermissionScopeResult:
        """
        Validate the permission scope of credentials.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            PermissionScopeResult with permission details
        """
        # Start with basic assumptions
        read_access = False
        write_access = False
        admin_access = False
        specific_permissions = []
        missing_permissions = []
        
        # Test connection first
        if repository.connection_status != 'connected':
            test_result = repository.test_connection()
            if not test_result.get('success'):
                missing_permissions.append("basic_connection")
                return PermissionScopeResult(
                    read_access=False,
                    write_access=False,
                    admin_access=False,
                    specific_permissions=[],
                    missing_permissions=missing_permissions
                )
        
        # Based on authentication type, infer permissions
        auth_type = repository.authentication_type
        
        if auth_type == GitAuthenticationTypeChoices.TOKEN:
            # Personal access tokens usually have specific scopes
            read_access = True
            specific_permissions.append("repo:read")
            
            # Most tokens allow push
            write_access = True
            specific_permissions.append("repo:write")
            
            # Check provider-specific patterns
            if repository.provider == 'github':
                credentials = repository.get_credentials()
                token = credentials.get('token', '')
                
                # GitHub classic tokens start with ghp_
                # Fine-grained tokens start with github_pat_
                if token.startswith('ghp_'):
                    specific_permissions.append("classic_token")
                elif token.startswith('github_pat_'):
                    specific_permissions.append("fine_grained_token")
        
        elif auth_type == GitAuthenticationTypeChoices.SSH_KEY:
            # SSH keys typically have full access
            read_access = True
            write_access = True
            specific_permissions.extend(["ssh:read", "ssh:write"])
            
            # Deploy keys might have restrictions
            credentials = repository.get_credentials()
            if 'deploy' in credentials.get('key_name', '').lower():
                write_access = False
                specific_permissions.append("deploy_key_readonly")
                missing_permissions.append("deploy_key_write")
        
        elif auth_type == GitAuthenticationTypeChoices.BASIC:
            # Basic auth usually has full access if valid
            read_access = True
            write_access = True
            specific_permissions.extend(["basic:read", "basic:write"])
        
        # Check for GitOps-specific requirements
        gitops_permissions = [
            "branch_protection_bypass",
            "webhook_management",
            "deployment_status"
        ]
        
        # For GitOps, we typically need these permissions
        if write_access:
            specific_permissions.append("gitops:ready")
        else:
            missing_permissions.extend(gitops_permissions)
        
        return PermissionScopeResult(
            read_access=read_access,
            write_access=write_access,
            admin_access=admin_access,
            specific_permissions=specific_permissions,
            missing_permissions=missing_permissions
        )
    
    # Private helper methods
    
    def _create_credential_backup(
        self,
        repository: GitRepository,
        reason: str
    ) -> CredentialBackup:
        """Create a backup of current credentials"""
        return CredentialBackup(
            repository_id=repository.id,
            encrypted_credentials=repository.encrypted_credentials,
            authentication_type=repository.authentication_type,
            backed_up_at=timezone.now(),
            backup_reason=reason
        )
    
    def _store_backup(self, backup: CredentialBackup) -> None:
        """Store backup in memory (in production, use persistent storage)"""
        repo_id = backup.repository_id
        if repo_id not in self._backup_storage:
            self._backup_storage[repo_id] = []
        
        # Keep last 10 backups
        self._backup_storage[repo_id].append(backup)
        self._backup_storage[repo_id] = self._backup_storage[repo_id][-10:]
    
    def _validate_credential_format(
        self,
        credentials: Dict[str, Any],
        auth_type: str
    ) -> ValidationResult:
        """Validate credential format for given auth type"""
        issues = []
        recommendations = []
        
        if auth_type == GitAuthenticationTypeChoices.TOKEN:
            token = credentials.get('token', '')
            if not token:
                issues.append("Token is required")
            elif len(token) < 20:
                issues.append("Token appears too short")
            
        elif auth_type == GitAuthenticationTypeChoices.SSH_KEY:
            private_key = credentials.get('private_key', '')
            if not private_key:
                issues.append("Private key is required")
            elif not private_key.startswith('-----BEGIN'):
                issues.append("Invalid private key format")
            
        elif auth_type == GitAuthenticationTypeChoices.BASIC:
            username = credentials.get('username', '')
            password = credentials.get('password', '')
            if not username:
                issues.append("Username is required")
            if not password:
                issues.append("Password is required")
        
        is_valid = len(issues) == 0
        strength = CredentialStrength.STRONG if is_valid else CredentialStrength.INVALID
        
        return ValidationResult(
            is_valid=is_valid,
            strength=strength,
            issues=issues,
            recommendations=recommendations
        )
    
    def _validate_token_strength(self, token: str) -> ValidationResult:
        """Validate token strength"""
        issues = []
        recommendations = []
        
        if not token:
            return ValidationResult(
                is_valid=False,
                strength=CredentialStrength.INVALID,
                issues=["No token configured"],
                recommendations=["Configure a personal access token"]
            )
        
        # Check token patterns
        strength = CredentialStrength.MODERATE
        
        # GitHub tokens
        if token.startswith('ghp_') or token.startswith('github_pat_'):
            if len(token) >= 40:
                strength = CredentialStrength.STRONG
            recommendations.append("GitHub token detected - ensure it has required scopes")
        
        # GitLab tokens
        elif token.startswith('glpat-'):
            if len(token) >= 20:
                strength = CredentialStrength.STRONG
            recommendations.append("GitLab token detected - ensure it has api scope")
        
        # Generic token checks
        else:
            if len(token) < 20:
                strength = CredentialStrength.WEAK
                issues.append("Token length is short")
                recommendations.append("Use a longer, more secure token")
            elif len(token) >= 32:
                strength = CredentialStrength.STRONG
        
        # Check for common weak patterns
        if token.lower() in ['password', 'token', 'secret', 'admin']:
            strength = CredentialStrength.WEAK
            issues.append("Token appears to be a placeholder")
            recommendations.append("Replace with actual access token")
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            strength=strength,
            issues=issues,
            recommendations=recommendations
        )
    
    def _validate_ssh_key_strength(
        self,
        private_key: str,
        passphrase: str
    ) -> ValidationResult:
        """Validate SSH key strength"""
        issues = []
        recommendations = []
        strength = CredentialStrength.STRONG
        
        if not private_key:
            return ValidationResult(
                is_valid=False,
                strength=CredentialStrength.INVALID,
                issues=["No SSH key configured"],
                recommendations=["Generate and configure an SSH key pair"]
            )
        
        # Check key format
        if 'BEGIN RSA PRIVATE KEY' in private_key:
            recommendations.append("Consider using ED25519 keys for better security")
        elif 'BEGIN OPENSSH PRIVATE KEY' in private_key:
            # Modern format
            pass
        elif 'BEGIN EC PRIVATE KEY' in private_key:
            # ECDSA key
            pass
        else:
            issues.append("Unrecognized private key format")
            strength = CredentialStrength.WEAK
        
        # Check for passphrase
        if not passphrase:
            strength = CredentialStrength.MODERATE
            recommendations.append("Consider adding a passphrase to your SSH key")
        
        # Check key size (simplified check)
        key_lines = private_key.strip().split('\n')
        if len(key_lines) < 20:
            strength = CredentialStrength.WEAK
            issues.append("SSH key appears too short")
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            strength=strength,
            issues=issues,
            recommendations=recommendations
        )
    
    def _validate_basic_auth_strength(
        self,
        username: str,
        password: str
    ) -> ValidationResult:
        """Validate basic auth credentials strength"""
        issues = []
        recommendations = []
        
        if not username or not password:
            return ValidationResult(
                is_valid=False,
                strength=CredentialStrength.INVALID,
                issues=["Username and password are required"],
                recommendations=["Configure both username and password"]
            )
        
        # Password strength checks
        strength = CredentialStrength.MODERATE
        
        if len(password) < 8:
            strength = CredentialStrength.WEAK
            issues.append("Password is too short (minimum 8 characters)")
        
        if password.lower() == password:
            recommendations.append("Use mixed case in password")
        
        if not any(c.isdigit() for c in password):
            recommendations.append("Include numbers in password")
        
        if not any(c in '!@#$%^&*()_+-=' for c in password):
            recommendations.append("Include special characters in password")
        
        # Check for common weak passwords
        weak_passwords = ['password', '12345678', 'admin', 'root', 'test']
        if password.lower() in weak_passwords:
            strength = CredentialStrength.WEAK
            issues.append("Password is too common")
        
        if len(password) >= 12 and any(c.isupper() for c in password) and \
           any(c.isdigit() for c in password) and any(c in '!@#$%^&*()_+-=' for c in password):
            strength = CredentialStrength.STRONG
        
        # Basic auth deprecation warning
        recommendations.append(
            "Consider using token-based authentication instead of basic auth"
        )
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            strength=strength,
            issues=issues,
            recommendations=recommendations
        )
    
    def _validate_oauth_strength(self, credentials: Dict[str, Any]) -> ValidationResult:
        """Validate OAuth credentials"""
        issues = []
        recommendations = []
        
        required_fields = ['access_token']
        for field in required_fields:
            if not credentials.get(field):
                issues.append(f"OAuth {field} is required")
        
        if credentials.get('refresh_token'):
            recommendations.append("Refresh token present - ensure automatic renewal is configured")
        else:
            recommendations.append("No refresh token - access token will need manual renewal")
        
        strength = CredentialStrength.STRONG if not issues else CredentialStrength.INVALID
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            strength=strength,
            issues=issues,
            recommendations=recommendations
        )
    
    def _get_credential_metadata(self, repository: GitRepository) -> Dict[str, Any]:
        """Get credential metadata from repository"""
        # In a real implementation, this would be stored in a separate field
        # For now, we'll parse from description or use defaults
        metadata = {
            'created_date': repository.created,
            'last_rotated': None,
            'rotation_count': 0
        }
        
        # Try to parse from description
        if repository.description and 'CREDENTIAL_METADATA:' in repository.description:
            try:
                import re
                match = re.search(r'CREDENTIAL_METADATA:\{.*?\}', repository.description)
                if match:
                    json_str = match.group(0).replace('CREDENTIAL_METADATA:', '')
                    stored_metadata = json.loads(json_str)
                    metadata.update(stored_metadata)
                    
                    # Parse dates
                    for date_field in ['created_date', 'last_rotated']:
                        if date_field in metadata and metadata[date_field]:
                            metadata[date_field] = datetime.fromisoformat(
                                metadata[date_field]
                            )
            except Exception:
                pass
        
        return metadata
    
    def _update_credential_metadata(
        self,
        repository: GitRepository,
        operation: str
    ) -> None:
        """Update credential metadata after operation"""
        metadata = self._get_credential_metadata(repository)
        
        if operation == 'rotation':
            metadata['last_rotated'] = timezone.now().isoformat()
            metadata['rotation_count'] = metadata.get('rotation_count', 0) + 1
        elif operation == 'restore':
            metadata['last_restored'] = timezone.now().isoformat()
        
        # Store in description
        metadata_str = json.dumps({
            k: v.isoformat() if isinstance(v, datetime) else v
            for k, v in metadata.items()
        })
        
        current_desc = repository.description or ''
        if 'CREDENTIAL_METADATA:' in current_desc:
            # Update existing
            import re
            pattern = r'CREDENTIAL_METADATA:\{.*?\}'
            new_metadata = f'CREDENTIAL_METADATA:{metadata_str}'
            repository.description = re.sub(pattern, new_metadata, current_desc)
        else:
            # Add new
            repository.description = f"{current_desc}\n\nCREDENTIAL_METADATA:{metadata_str}"
        
        repository.save()


@dataclass
class RestoreResult:
    """Result of credential restore operation"""
    success: bool
    message: str
    restored_from: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'restored_from': self.restored_from.isoformat()
        }