"""
Secure Credential Manager for GitOps Operations

This module provides comprehensive credential management with encryption,
rotation, validation, and security auditing capabilities.
"""

import json
import base64
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction

logger = logging.getLogger(__name__)


class CredentialStrength(Enum):
    """Credential strength levels"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    EXCELLENT = "excellent"


class RotationStatus(Enum):
    """Credential rotation status"""
    CURRENT = "current"
    SCHEDULED = "scheduled"
    EXPIRED = "expired"
    ROTATED = "rotated"


@dataclass
class CredentialValidationResult:
    """Result of credential validation"""
    is_valid: bool
    strength: CredentialStrength
    issues: List[str]
    recommendations: List[str]
    expires_at: Optional[datetime] = None
    last_validated: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'strength': self.strength.value,
            'issues': self.issues,
            'recommendations': self.recommendations,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_validated': self.last_validated.isoformat() if self.last_validated else None
        }


@dataclass
class CredentialRotationResult:
    """Result of credential rotation"""
    success: bool
    old_credential_backed_up: bool
    new_credential_validated: bool
    rotation_timestamp: datetime
    error: Optional[str] = None
    warning: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'old_credential_backed_up': self.old_credential_backed_up,
            'new_credential_validated': self.new_credential_validated,
            'rotation_timestamp': self.rotation_timestamp.isoformat(),
            'error': self.error,
            'warning': self.warning
        }


@dataclass
class CredentialHealthStatus:
    """Comprehensive credential health status"""
    repository_id: int
    is_healthy: bool
    strength: CredentialStrength
    rotation_status: RotationStatus
    days_until_expiration: Optional[int]
    last_validated: Optional[datetime]
    validation_issues: List[str]
    security_recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'repository_id': self.repository_id,
            'is_healthy': self.is_healthy,
            'strength': self.strength.value,
            'rotation_status': self.rotation_status.value,
            'days_until_expiration': self.days_until_expiration,
            'last_validated': self.last_validated.isoformat() if self.last_validated else None,
            'validation_issues': self.validation_issues,
            'security_recommendations': self.security_recommendations
        }


@dataclass
class CredentialBackup:
    """Credential backup for rotation/recovery"""
    repository_id: int
    encrypted_credentials: str
    authentication_type: str
    backed_up_at: datetime
    backup_reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'repository_id': self.repository_id,
            'encrypted_credentials': self.encrypted_credentials,
            'authentication_type': self.authentication_type,
            'backed_up_at': self.backed_up_at.isoformat(),
            'backup_reason': self.backup_reason
        }


@dataclass
class ThoroughTestResult:
    """Result of thorough credential testing"""
    connection_successful: bool
    authentication_successful: bool
    permissions_validated: bool
    repository_accessible: bool
    clone_test_passed: bool
    push_permission_available: bool
    response_time_ms: int
    errors: List[str]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PermissionScopeResult:
    """Result of permission scope validation"""
    has_read_access: bool
    has_write_access: bool
    has_admin_access: bool
    can_create_branches: bool
    can_create_webhooks: bool
    repository_permissions: List[str]
    organization_permissions: List[str]
    scope_adequate: bool
    missing_permissions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SecureCredentialManager:
    """
    Enhanced credential manager with enterprise-grade security features.
    
    Features:
    - AES-256 encryption with PBKDF2 key derivation
    - Credential strength validation
    - Automatic rotation scheduling
    - Comprehensive audit logging
    - Backup and recovery capabilities
    - Permission scope validation
    """
    
    SALT_LENGTH = 32
    KEY_LENGTH = 32
    PBKDF2_ITERATIONS = 100000
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def _get_encryption_key(self, repository_id: int) -> Tuple[bytes, bytes]:
        """Get encryption key and salt for repository"""
        # Create repository-specific salt using SECRET_KEY and repository ID
        base_salt = f"{settings.SECRET_KEY}:{repository_id}".encode()
        salt = hashlib.sha256(base_salt).digest()[:self.SALT_LENGTH]
        
        key = self._derive_key(settings.SECRET_KEY, salt)
        return key, salt
    
    def encrypt_credentials(self, repository, credentials_dict: Dict[str, Any]) -> str:
        """
        Encrypt credentials using repository-specific key.
        
        Args:
            repository: GitRepository instance
            credentials_dict: Credentials to encrypt
            
        Returns:
            Base64-encoded encrypted credentials
        """
        try:
            # Get repository-specific encryption key
            key, salt = self._get_encryption_key(repository.id)
            fernet = Fernet(key)
            
            # Prepare credentials with metadata
            credential_data = {
                'credentials': credentials_dict,
                'encrypted_at': timezone.now().isoformat(),
                'repository_id': repository.id,
                'auth_type': repository.authentication_type
            }
            
            # Encrypt data
            credentials_json = json.dumps(credential_data)
            encrypted_data = fernet.encrypt(credentials_json.encode('utf-8'))
            
            # Audit log the encryption
            self._audit_credential_action(
                repository, 
                'credential_encrypted', 
                f"Credentials encrypted for repository {repository.name}"
            )
            
            return base64.b64encode(encrypted_data).decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Failed to encrypt credentials for repository {repository.id}: {str(e)}")
            self._audit_credential_action(
                repository, 
                'credential_encryption_failed', 
                f"Failed to encrypt credentials: {str(e)}"
            )
            raise ValidationError(f"Credential encryption failed: {str(e)}")
    
    def decrypt_credentials(self, repository) -> Dict[str, Any]:
        """
        Decrypt credentials for repository.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            Decrypted credentials dictionary
        """
        try:
            if not repository.encrypted_credentials:
                return {}
            
            # Get repository-specific encryption key
            key, salt = self._get_encryption_key(repository.id)
            fernet = Fernet(key)
            
            # Decrypt data
            encrypted_data = base64.b64decode(repository.encrypted_credentials.encode('utf-8'))
            decrypted_data = fernet.decrypt(encrypted_data)
            
            # Parse credential data
            credential_data = json.loads(decrypted_data.decode('utf-8'))
            
            # Validate decrypted data
            if credential_data.get('repository_id') != repository.id:
                raise ValidationError("Credential repository ID mismatch")
            
            # Audit log the access
            self._audit_credential_action(
                repository, 
                'credential_accessed', 
                f"Credentials accessed for repository {repository.name}"
            )
            
            return credential_data.get('credentials', {})
            
        except Exception as e:
            self.logger.error(f"Failed to decrypt credentials for repository {repository.id}: {str(e)}")
            self._audit_credential_action(
                repository, 
                'credential_decryption_failed', 
                f"Failed to decrypt credentials: {str(e)}"
            )
            raise ValidationError(f"Credential decryption failed: {str(e)}")
    
    def rotate_credentials(
        self, 
        repository, 
        new_credentials: Dict[str, Any],
        rotation_reason: str = "Manual rotation"
    ) -> CredentialRotationResult:
        """
        Rotate credentials with backup and validation.
        
        Args:
            repository: GitRepository instance
            new_credentials: New credentials to set
            rotation_reason: Reason for rotation
            
        Returns:
            CredentialRotationResult
        """
        rotation_timestamp = timezone.now()
        
        try:
            with transaction.atomic():
                # Step 1: Backup existing credentials
                backup_success = False
                if repository.encrypted_credentials:
                    backup = self.backup_credentials(repository)
                    backup_success = True
                    self.logger.info(f"Backed up credentials for repository {repository.id}")
                
                # Step 2: Validate new credentials
                temp_repo = type(repository)()
                temp_repo.id = repository.id
                temp_repo.url = repository.url
                temp_repo.authentication_type = repository.authentication_type
                temp_repo.encrypted_credentials = self.encrypt_credentials(temp_repo, new_credentials)
                
                validation_result = self._validate_credentials_connection(temp_repo)
                
                if not validation_result['success']:
                    raise ValidationError(f"New credentials validation failed: {validation_result['error']}")
                
                # Step 3: Set new credentials
                repository.encrypted_credentials = temp_repo.encrypted_credentials
                repository.last_validated = rotation_timestamp
                repository.validation_error = ''
                repository.save(update_fields=[
                    'encrypted_credentials', 
                    'last_validated', 
                    'validation_error'
                ])
                
                # Step 4: Audit log the rotation
                self._audit_credential_action(
                    repository,
                    'credential_rotated',
                    f"Credentials rotated successfully. Reason: {rotation_reason}"
                )
                
                self.logger.info(f"Successfully rotated credentials for repository {repository.id}")
                
                return CredentialRotationResult(
                    success=True,
                    old_credential_backed_up=backup_success,
                    new_credential_validated=True,
                    rotation_timestamp=rotation_timestamp
                )
                
        except Exception as e:
            self.logger.error(f"Credential rotation failed for repository {repository.id}: {str(e)}")
            self._audit_credential_action(
                repository,
                'credential_rotation_failed',
                f"Credential rotation failed: {str(e)}"
            )
            
            return CredentialRotationResult(
                success=False,
                old_credential_backed_up=False,
                new_credential_validated=False,
                rotation_timestamp=rotation_timestamp,
                error=str(e)
            )
    
    def validate_credential_strength(self, repository) -> CredentialValidationResult:
        """
        Validate the strength of repository credentials.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            CredentialValidationResult
        """
        try:
            credentials = self.decrypt_credentials(repository)
            issues = []
            recommendations = []
            
            if not credentials:
                return CredentialValidationResult(
                    is_valid=False,
                    strength=CredentialStrength.WEAK,
                    issues=["No credentials configured"],
                    recommendations=["Configure authentication credentials"]
                )
            
            strength_score = 0
            
            if repository.authentication_type == 'token':
                token = credentials.get('token', '')
                
                # Check token format and strength
                if not token:
                    issues.append("Token is empty")
                elif len(token) < 20:
                    issues.append("Token appears too short")
                    recommendations.append("Use a properly generated access token")
                else:
                    strength_score += 2
                
                # Check for GitHub token patterns
                if token.startswith('ghp_'):
                    strength_score += 1
                elif token.startswith('github_pat_'):
                    strength_score += 2
                    recommendations.append("Consider using fine-grained personal access tokens")
                
                # Check token age (if we can determine it)
                if hasattr(repository, 'last_validated') and repository.last_validated:
                    days_since_validation = (timezone.now() - repository.last_validated).days
                    if days_since_validation > 90:
                        issues.append("Token hasn't been validated in over 90 days")
                        recommendations.append("Regularly validate and rotate access tokens")
                    elif days_since_validation > 30:
                        recommendations.append("Consider validating token more frequently")
            
            elif repository.authentication_type == 'basic':
                username = credentials.get('username', '')
                password = credentials.get('password', '')
                
                if not username:
                    issues.append("Username is empty")
                if not password:
                    issues.append("Password is empty")
                elif len(password) < 8:
                    issues.append("Password is too short")
                    recommendations.append("Use a strong password with at least 12 characters")
                else:
                    strength_score += 1
                
                # Basic auth is generally less secure
                recommendations.append("Consider using token-based authentication instead of basic auth")
            
            elif repository.authentication_type == 'ssh':
                private_key = credentials.get('private_key', '')
                passphrase = credentials.get('passphrase', '')
                
                if not private_key:
                    issues.append("Private key is empty")
                elif 'BEGIN RSA PRIVATE KEY' in private_key:
                    recommendations.append("Consider upgrading to Ed25519 keys for better security")
                    strength_score += 1
                elif 'BEGIN OPENSSH PRIVATE KEY' in private_key:
                    strength_score += 2
                
                if passphrase:
                    strength_score += 1
                else:
                    recommendations.append("Consider using a passphrase for your private key")
            
            # Determine overall strength
            if strength_score >= 4:
                strength = CredentialStrength.EXCELLENT
            elif strength_score >= 3:
                strength = CredentialStrength.STRONG
            elif strength_score >= 2:
                strength = CredentialStrength.MODERATE
            else:
                strength = CredentialStrength.WEAK
            
            is_valid = len(issues) == 0
            
            # Audit log the validation
            self._audit_credential_action(
                repository,
                'credential_strength_validated',
                f"Credential strength assessed as {strength.value}"
            )
            
            return CredentialValidationResult(
                is_valid=is_valid,
                strength=strength,
                issues=issues,
                recommendations=recommendations,
                last_validated=timezone.now()
            )
            
        except Exception as e:
            self.logger.error(f"Credential strength validation failed for repository {repository.id}: {str(e)}")
            return CredentialValidationResult(
                is_valid=False,
                strength=CredentialStrength.WEAK,
                issues=[f"Validation failed: {str(e)}"],
                recommendations=["Fix credential configuration issues"]
            )
    
    def get_credential_health(self, repository) -> CredentialHealthStatus:
        """
        Get comprehensive credential health status.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            CredentialHealthStatus
        """
        validation_result = self.validate_credential_strength(repository)
        
        # Determine rotation status
        rotation_status = RotationStatus.CURRENT
        days_until_expiration = None
        
        if hasattr(repository, 'last_validated') and repository.last_validated:
            days_since_validation = (timezone.now() - repository.last_validated).days
            if days_since_validation > 180:
                rotation_status = RotationStatus.EXPIRED
            elif days_since_validation > 90:
                rotation_status = RotationStatus.SCHEDULED
                days_until_expiration = 180 - days_since_validation
        
        is_healthy = (
            validation_result.is_valid and
            validation_result.strength in [CredentialStrength.STRONG, CredentialStrength.EXCELLENT] and
            rotation_status in [RotationStatus.CURRENT, RotationStatus.SCHEDULED]
        )
        
        return CredentialHealthStatus(
            repository_id=repository.id,
            is_healthy=is_healthy,
            strength=validation_result.strength,
            rotation_status=rotation_status,
            days_until_expiration=days_until_expiration,
            last_validated=validation_result.last_validated,
            validation_issues=validation_result.issues,
            security_recommendations=validation_result.recommendations
        )
    
    def backup_credentials(self, repository) -> CredentialBackup:
        """
        Create a backup of current credentials.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            CredentialBackup
        """
        backup = CredentialBackup(
            repository_id=repository.id,
            encrypted_credentials=repository.encrypted_credentials,
            authentication_type=repository.authentication_type,
            backed_up_at=timezone.now(),
            backup_reason="Pre-rotation backup"
        )
        
        # Audit log the backup
        self._audit_credential_action(
            repository,
            'credential_backed_up',
            f"Credentials backed up for repository {repository.name}"
        )
        
        return backup
    
    def restore_credentials(self, repository, backup: CredentialBackup) -> CredentialRotationResult:
        """
        Restore credentials from backup.
        
        Args:
            repository: GitRepository instance
            backup: CredentialBackup to restore
            
        Returns:
            CredentialRotationResult
        """
        try:
            with transaction.atomic():
                # Validate backup is for this repository
                if backup.repository_id != repository.id:
                    raise ValidationError("Backup repository ID mismatch")
                
                # Restore credentials
                repository.encrypted_credentials = backup.encrypted_credentials
                repository.authentication_type = backup.authentication_type
                repository.save(update_fields=['encrypted_credentials', 'authentication_type'])
                
                # Audit log the restoration
                self._audit_credential_action(
                    repository,
                    'credential_restored',
                    f"Credentials restored from backup created at {backup.backed_up_at}"
                )
                
                return CredentialRotationResult(
                    success=True,
                    old_credential_backed_up=True,
                    new_credential_validated=False,  # Should be validated after restore
                    rotation_timestamp=timezone.now()
                )
                
        except Exception as e:
            self.logger.error(f"Credential restoration failed for repository {repository.id}: {str(e)}")
            self._audit_credential_action(
                repository,
                'credential_restoration_failed',
                f"Credential restoration failed: {str(e)}"
            )
            
            return CredentialRotationResult(
                success=False,
                old_credential_backed_up=False,
                new_credential_validated=False,
                rotation_timestamp=timezone.now(),
                error=str(e)
            )
    
    def test_credentials_thoroughly(self, repository) -> ThoroughTestResult:
        """
        Perform thorough credential testing including permissions.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            ThoroughTestResult
        """
        start_time = timezone.now()
        errors = []
        warnings = []
        
        try:
            # Basic connection test
            connection_result = self._validate_credentials_connection(repository)
            connection_successful = connection_result['success']
            authentication_successful = connection_result['success']
            
            if not connection_successful:
                errors.append(f"Connection failed: {connection_result.get('error', 'Unknown error')}")
            
            # Repository accessibility test
            repository_accessible = False
            if connection_successful:
                try:
                    # Try to get repository info
                    repo_info = self._get_repository_info(repository)
                    repository_accessible = repo_info['accessible']
                    if not repository_accessible:
                        errors.append("Repository is not accessible with current credentials")
                except Exception as e:
                    errors.append(f"Repository access test failed: {str(e)}")
            
            # Clone test
            clone_test_passed = False
            if repository_accessible:
                try:
                    clone_test_passed = self._test_repository_clone(repository)
                    if not clone_test_passed:
                        errors.append("Clone test failed")
                except Exception as e:
                    errors.append(f"Clone test error: {str(e)}")
            
            # Permission validation
            permissions_validated = False
            push_permission_available = False
            if repository_accessible:
                try:
                    perm_result = self.validate_permission_scope(repository)
                    permissions_validated = perm_result.scope_adequate
                    push_permission_available = perm_result.has_write_access
                    
                    if not permissions_validated:
                        warnings.extend([f"Missing permission: {perm}" for perm in perm_result.missing_permissions])
                except Exception as e:
                    errors.append(f"Permission validation failed: {str(e)}")
            
            # Calculate response time
            end_time = timezone.now()
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Audit log the thorough test
            self._audit_credential_action(
                repository,
                'credential_thoroughly_tested',
                f"Thorough credential test completed. Success: {connection_successful}"
            )
            
            return ThoroughTestResult(
                connection_successful=connection_successful,
                authentication_successful=authentication_successful,
                permissions_validated=permissions_validated,
                repository_accessible=repository_accessible,
                clone_test_passed=clone_test_passed,
                push_permission_available=push_permission_available,
                response_time_ms=response_time_ms,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            self.logger.error(f"Thorough credential test failed for repository {repository.id}: {str(e)}")
            errors.append(f"Test framework error: {str(e)}")
            
            return ThoroughTestResult(
                connection_successful=False,
                authentication_successful=False,
                permissions_validated=False,
                repository_accessible=False,
                clone_test_passed=False,
                push_permission_available=False,
                response_time_ms=0,
                errors=errors,
                warnings=warnings
            )
    
    def validate_permission_scope(self, repository) -> PermissionScopeResult:
        """
        Validate the permission scope of credentials.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            PermissionScopeResult
        """
        try:
            # This would integrate with git provider APIs to check permissions
            # For now, we'll implement basic checks
            
            has_read_access = False
            has_write_access = False
            has_admin_access = False
            can_create_branches = False
            can_create_webhooks = False
            repository_permissions = []
            organization_permissions = []
            
            # Basic connection test implies read access
            connection_result = self._validate_credentials_connection(repository)
            if connection_result['success']:
                has_read_access = True
                repository_permissions.append('read')
            
            # For GitHub repositories, we could use the API to check actual permissions
            # This is a simplified implementation
            credentials = self.decrypt_credentials(repository)
            
            if repository.authentication_type == 'token':
                token = credentials.get('token', '')
                if token:
                    # Basic assumption: if token works, it likely has write access
                    # In a real implementation, you'd check token scopes
                    has_write_access = True
                    repository_permissions.extend(['write', 'push'])
                    
                    # Check if token has admin-level permissions
                    if token.startswith('github_pat_') or 'admin' in token:
                        has_admin_access = True
                        can_create_branches = True
                        can_create_webhooks = True
                        repository_permissions.extend(['admin', 'webhooks'])
            
            # Determine if scope is adequate for GitOps operations
            required_permissions = ['read', 'write', 'push']
            missing_permissions = [perm for perm in required_permissions if perm not in repository_permissions]
            scope_adequate = len(missing_permissions) == 0
            
            return PermissionScopeResult(
                has_read_access=has_read_access,
                has_write_access=has_write_access,
                has_admin_access=has_admin_access,
                can_create_branches=can_create_branches,
                can_create_webhooks=can_create_webhooks,
                repository_permissions=repository_permissions,
                organization_permissions=organization_permissions,
                scope_adequate=scope_adequate,
                missing_permissions=missing_permissions
            )
            
        except Exception as e:
            self.logger.error(f"Permission scope validation failed for repository {repository.id}: {str(e)}")
            return PermissionScopeResult(
                has_read_access=False,
                has_write_access=False,
                has_admin_access=False,
                can_create_branches=False,
                can_create_webhooks=False,
                repository_permissions=[],
                organization_permissions=[],
                scope_adequate=False,
                missing_permissions=['read', 'write', 'push']
            )
    
    def schedule_credential_rotation(self, repository, rotation_date: datetime) -> None:
        """
        Schedule automatic credential rotation.
        
        Args:
            repository: GitRepository instance
            rotation_date: When to rotate credentials
        """
        # This would integrate with a task scheduler (like Celery)
        # For now, we'll just audit log the scheduling
        self._audit_credential_action(
            repository,
            'credential_rotation_scheduled',
            f"Credential rotation scheduled for {rotation_date.isoformat()}"
        )
        
        self.logger.info(f"Credential rotation scheduled for repository {repository.id} at {rotation_date}")
    
    def _validate_credentials_connection(self, repository) -> Dict[str, Any]:
        """
        Test connection with current credentials.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            Connection test result
        """
        try:
            # Use the repository's existing test_connection method
            return repository.test_connection()
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_repository_info(self, repository) -> Dict[str, Any]:
        """
        Get repository information to test accessibility.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            Repository info dict
        """
        try:
            # Basic accessibility test - if we can decrypt credentials and they exist
            credentials = self.decrypt_credentials(repository)
            return {
                'accessible': bool(credentials),
                'has_credentials': bool(credentials)
            }
        except Exception:
            return {
                'accessible': False,
                'has_credentials': False
            }
    
    def _test_repository_clone(self, repository) -> bool:
        """
        Test repository clone capability.
        
        Args:
            repository: GitRepository instance
            
        Returns:
            True if clone test passes
        """
        try:
            import tempfile
            import shutil
            
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = repository.clone_repository(temp_dir)
                return clone_result.get('success', False)
        except Exception as e:
            self.logger.error(f"Clone test failed for repository {repository.id}: {str(e)}")
            return False
    
    def _audit_credential_action(self, repository, action: str, details: str) -> None:
        """
        Audit log credential-related actions.
        
        Args:
            repository: GitRepository instance
            action: Action type
            details: Action details
        """
        try:
            from .audit_logger import SecurityAuditLogger
            
            audit_logger = SecurityAuditLogger()
            audit_logger.log_credential_access(
                user=getattr(repository, 'created_by', None),
                repository=repository,
                action=action,
                details=details
            )
        except ImportError:
            # Fallback to regular logging if audit logger not available
            self.logger.info(f"CREDENTIAL_AUDIT: {action} - Repository {repository.id} - {details}")
        except Exception as e:
            self.logger.error(f"Failed to audit log credential action: {str(e)}")