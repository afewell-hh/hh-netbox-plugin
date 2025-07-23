"""
API Token Manager for GitOps Operations

This module provides advanced API token management with expiration,
rotation, scoped permissions, and comprehensive audit logging.
"""

import secrets
import string
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, asdict
from enum import Enum
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()


class TokenScope(Enum):
    """API token scopes"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    FABRIC_SPECIFIC = "fabric_specific"
    CREDENTIAL_MANAGEMENT = "credential_management"


class TokenStatus(Enum):
    """API token status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


@dataclass
class TokenPermissions:
    """Token permission configuration"""
    scopes: Set[TokenScope]
    fabric_ids: Optional[Set[int]] = None
    permissions: Optional[Set[str]] = None
    rate_limit_override: Optional[int] = None
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'scopes': [scope.value for scope in self.scopes],
            'fabric_ids': list(self.fabric_ids) if self.fabric_ids else None,
            'permissions': list(self.permissions) if self.permissions else None,
            'rate_limit_override': self.rate_limit_override,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenPermissions':
        return cls(
            scopes={TokenScope(scope) for scope in data.get('scopes', [])},
            fabric_ids=set(data['fabric_ids']) if data.get('fabric_ids') else None,
            permissions=set(data['permissions']) if data.get('permissions') else None,
            rate_limit_override=data.get('rate_limit_override'),
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None
        )


@dataclass
class TokenInfo:
    """API token information"""
    token_id: str
    user_id: int
    username: str
    name: str
    permissions: TokenPermissions
    status: TokenStatus
    created_at: datetime
    last_used: Optional[datetime] = None
    use_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'token_id': self.token_id,
            'user_id': self.user_id,
            'username': self.username,
            'name': self.name,
            'permissions': self.permissions.to_dict(),
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'use_count': self.use_count
        }


@dataclass
class TokenValidationResult:
    """Token validation result"""
    valid: bool
    token_info: Optional[TokenInfo] = None
    error: Optional[str] = None
    missing_permissions: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'token_info': self.token_info.to_dict() if self.token_info else None,
            'error': self.error,
            'missing_permissions': self.missing_permissions or []
        }


class APITokenManager:
    """
    Advanced API token management with expiration and rotation.
    
    Features:
    - Scoped permissions for different API operations
    - Token expiration and automatic rotation
    - Fabric-specific access tokens
    - Comprehensive audit logging
    - Rate limiting integration
    - Token usage analytics
    """
    
    TOKEN_PREFIX = "hnp_"
    TOKEN_LENGTH = 40
    TOKEN_ID_LENGTH = 16
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def create_gitops_token(
        self,
        user: User,
        name: str,
        permissions: TokenPermissions,
        expires_in_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create scoped GitOps API token.
        
        Args:
            user: User creating the token
            name: Token name/description
            permissions: Token permissions configuration
            expires_in_days: Token expiration in days (optional)
            
        Returns:
            Token creation result with token value
        """
        try:
            with transaction.atomic():
                # Generate token ID and value
                token_id = self._generate_token_id()
                token_value = self._generate_token_value()
                token_hash = self._hash_token(token_value)
                
                # Set expiration if specified
                expires_at = None
                if expires_in_days:
                    expires_at = timezone.now() + timedelta(days=expires_in_days)
                    permissions.expires_at = expires_at
                
                # Create token record (this would typically be stored in database)
                token_info = TokenInfo(
                    token_id=token_id,
                    user_id=user.id,
                    username=user.username,
                    name=name,
                    permissions=permissions,
                    status=TokenStatus.ACTIVE,
                    created_at=timezone.now()
                )
                
                # Store token (placeholder - would use actual database)
                self._store_token(token_hash, token_info)
                
                # Audit log token creation
                self._audit_token_action(
                    user=user,
                    action='token_created',
                    token_id=token_id,
                    details=f"Created token '{name}' with scopes: {[s.value for s in permissions.scopes]}"
                )
                
                self.logger.info(f"Created API token {token_id} for user {user.username}")
                
                return {
                    'success': True,
                    'token': f"{self.TOKEN_PREFIX}{token_value}",
                    'token_id': token_id,
                    'token_info': token_info.to_dict(),
                    'expires_at': expires_at.isoformat() if expires_at else None,
                    'created_at': timezone.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to create API token: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_token_permissions(
        self,
        token: str,
        required_permissions: List[str],
        fabric_id: Optional[int] = None
    ) -> TokenValidationResult:
        """
        Validate token has required permissions.
        
        Args:
            token: API token to validate
            required_permissions: List of required permissions
            fabric_id: Optional fabric ID for fabric-specific tokens
            
        Returns:
            TokenValidationResult
        """
        try:
            # Extract and validate token format
            if not token.startswith(self.TOKEN_PREFIX):
                return TokenValidationResult(
                    valid=False,
                    error="Invalid token format"
                )
            
            token_value = token[len(self.TOKEN_PREFIX):]
            token_hash = self._hash_token(token_value)
            
            # Get token info
            token_info = self._get_token_info(token_hash)
            if not token_info:
                return TokenValidationResult(
                    valid=False,
                    error="Token not found"
                )
            
            # Check token status
            if token_info.status != TokenStatus.ACTIVE:
                return TokenValidationResult(
                    valid=False,
                    error=f"Token is {token_info.status.value}",
                    token_info=token_info
                )
            
            # Check expiration
            if token_info.permissions.expires_at and timezone.now() > token_info.permissions.expires_at:
                # Update token status to expired
                token_info.status = TokenStatus.EXPIRED
                self._update_token_status(token_hash, TokenStatus.EXPIRED)
                
                return TokenValidationResult(
                    valid=False,
                    error="Token has expired",
                    token_info=token_info
                )
            
            # Check fabric-specific access
            if fabric_id and token_info.permissions.fabric_ids:
                if fabric_id not in token_info.permissions.fabric_ids:
                    return TokenValidationResult(
                        valid=False,
                        error=f"Token does not have access to fabric {fabric_id}",
                        token_info=token_info
                    )
            
            # Check permissions
            missing_permissions = []
            
            # Check scope-based permissions
            required_scopes = self._permissions_to_scopes(required_permissions)
            if not required_scopes.issubset(token_info.permissions.scopes):
                missing_scopes = required_scopes - token_info.permissions.scopes
                missing_permissions.extend([f"scope:{scope.value}" for scope in missing_scopes])
            
            # Check specific permissions
            if token_info.permissions.permissions:
                missing_perms = set(required_permissions) - token_info.permissions.permissions
                missing_permissions.extend(missing_perms)
            else:
                # If no specific permissions, check against scopes
                if not self._scopes_satisfy_permissions(token_info.permissions.scopes, required_permissions):
                    missing_permissions.extend(required_permissions)
            
            if missing_permissions:
                return TokenValidationResult(
                    valid=False,
                    error="Insufficient permissions",
                    token_info=token_info,
                    missing_permissions=missing_permissions
                )
            
            # Update token usage
            self._update_token_usage(token_hash)
            
            # Audit log token usage
            try:
                user = User.objects.get(id=token_info.user_id)
                self._audit_token_action(
                    user=user,
                    action='token_used',
                    token_id=token_info.token_id,
                    details=f"Token used for permissions: {required_permissions}"
                )
            except User.DoesNotExist:
                pass
            
            return TokenValidationResult(
                valid=True,
                token_info=token_info
            )
            
        except Exception as e:
            self.logger.error(f"Token validation failed: {str(e)}")
            return TokenValidationResult(
                valid=False,
                error=f"Validation error: {str(e)}"
            )
    
    def rotate_expired_tokens(self) -> Dict[str, Any]:
        """
        Rotate tokens nearing expiration.
        
        Returns:
            Rotation result summary
        """
        try:
            # This would query database for tokens expiring soon
            # For now, return placeholder result
            
            rotated_count = 0
            failed_count = 0
            errors = []
            
            # In real implementation, would:
            # 1. Find tokens expiring within warning period
            # 2. Generate new tokens
            # 3. Notify users
            # 4. Mark old tokens for revocation
            
            self.logger.info(f"Token rotation completed: {rotated_count} rotated, {failed_count} failed")
            
            return {
                'success': True,
                'rotated_count': rotated_count,
                'failed_count': failed_count,
                'errors': errors,
                'rotation_time': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Token rotation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'rotation_time': timezone.now().isoformat()
            }
    
    def revoke_token(self, token_id: str, user: User, reason: str = "Manual revocation") -> Dict[str, Any]:
        """
        Revoke an API token.
        
        Args:
            token_id: Token ID to revoke
            user: User revoking the token
            reason: Reason for revocation
            
        Returns:
            Revocation result
        """
        try:
            # Find and revoke token
            token_info = self._get_token_info_by_id(token_id)
            if not token_info:
                return {
                    'success': False,
                    'error': 'Token not found'
                }
            
            # Check if user can revoke this token
            if token_info.user_id != user.id and not user.is_staff:
                return {
                    'success': False,
                    'error': 'Permission denied: Cannot revoke token belonging to another user'
                }
            
            # Update token status
            self._update_token_status_by_id(token_id, TokenStatus.REVOKED)
            
            # Audit log token revocation
            self._audit_token_action(
                user=user,
                action='token_revoked',
                token_id=token_id,
                details=f"Token revoked. Reason: {reason}"
            )
            
            self.logger.info(f"Revoked API token {token_id} for user {user.username}")
            
            return {
                'success': True,
                'token_id': token_id,
                'revoked_at': timezone.now().isoformat(),
                'reason': reason
            }
            
        except Exception as e:
            self.logger.error(f"Failed to revoke token {token_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_user_tokens(self, user: User) -> List[Dict[str, Any]]:
        """
        List all tokens for a user.
        
        Args:
            user: User to list tokens for
            
        Returns:
            List of token information (without token values)
        """
        try:
            # This would query database for user's tokens
            # For now, return placeholder
            
            tokens = []  # Would contain actual user tokens
            
            return [
                {
                    **token_info.to_dict(),
                    'token_value': None  # Never return actual token value
                }
                for token_info in tokens
            ]
            
        except Exception as e:
            self.logger.error(f"Failed to list tokens for user {user.username}: {str(e)}")
            return []
    
    def get_token_analytics(self, token_id: str) -> Dict[str, Any]:
        """
        Get analytics for a specific token.
        
        Args:
            token_id: Token ID to analyze
            
        Returns:
            Token analytics data
        """
        try:
            token_info = self._get_token_info_by_id(token_id)
            if not token_info:
                return {
                    'error': 'Token not found'
                }
            
            # In real implementation, would gather usage statistics
            analytics = {
                'token_id': token_id,
                'total_requests': token_info.use_count,
                'last_used': token_info.last_used.isoformat() if token_info.last_used else None,
                'status': token_info.status.value,
                'created_at': token_info.created_at.isoformat(),
                'days_active': (timezone.now() - token_info.created_at).days,
                'expires_at': token_info.permissions.expires_at.isoformat() if token_info.permissions.expires_at else None,
                'scopes': [scope.value for scope in token_info.permissions.scopes],
                'fabric_count': len(token_info.permissions.fabric_ids) if token_info.permissions.fabric_ids else 0
            }
            
            return analytics
            
        except Exception as e:
            self.logger.error(f"Failed to get token analytics: {str(e)}")
            return {
                'error': str(e)
            }
    
    def _generate_token_id(self) -> str:
        """Generate unique token ID"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(self.TOKEN_ID_LENGTH))
    
    def _generate_token_value(self) -> str:
        """Generate secure token value"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(self.TOKEN_LENGTH))
    
    def _hash_token(self, token_value: str) -> str:
        """Hash token value for secure storage"""
        salt = getattr(settings, 'SECRET_KEY', 'default_salt')
        return hashlib.sha256(f"{salt}:{token_value}".encode()).hexdigest()
    
    def _permissions_to_scopes(self, permissions: List[str]) -> Set[TokenScope]:
        """Convert permissions to required scopes"""
        scopes = set()
        
        for permission in permissions:
            if any(write_perm in permission.lower() for write_perm in ['edit', 'create', 'delete', 'manage']):
                scopes.add(TokenScope.WRITE)
            elif 'admin' in permission.lower():
                scopes.add(TokenScope.ADMIN)
            elif 'credential' in permission.lower():
                scopes.add(TokenScope.CREDENTIAL_MANAGEMENT)
            else:
                scopes.add(TokenScope.READ)
        
        return scopes
    
    def _scopes_satisfy_permissions(self, token_scopes: Set[TokenScope], required_permissions: List[str]) -> bool:
        """Check if token scopes satisfy required permissions"""
        # Admin scope satisfies all permissions
        if TokenScope.ADMIN in token_scopes:
            return True
        
        # Check specific scope requirements
        for permission in required_permissions:
            if any(write_perm in permission.lower() for write_perm in ['edit', 'create', 'delete', 'manage']):
                if TokenScope.WRITE not in token_scopes:
                    return False
            elif 'credential' in permission.lower():
                if TokenScope.CREDENTIAL_MANAGEMENT not in token_scopes:
                    return False
            elif TokenScope.READ not in token_scopes:
                return False
        
        return True
    
    def _store_token(self, token_hash: str, token_info: TokenInfo) -> None:
        """Store token information (placeholder for database storage)"""
        # In real implementation, this would store in database
        pass
    
    def _get_token_info(self, token_hash: str) -> Optional[TokenInfo]:
        """Get token information by hash (placeholder for database query)"""
        # In real implementation, this would query database
        return None
    
    def _get_token_info_by_id(self, token_id: str) -> Optional[TokenInfo]:
        """Get token information by ID (placeholder for database query)"""
        # In real implementation, this would query database
        return None
    
    def _update_token_status(self, token_hash: str, status: TokenStatus) -> None:
        """Update token status (placeholder for database update)"""
        # In real implementation, this would update database
        pass
    
    def _update_token_status_by_id(self, token_id: str, status: TokenStatus) -> None:
        """Update token status by ID (placeholder for database update)"""
        # In real implementation, this would update database
        pass
    
    def _update_token_usage(self, token_hash: str) -> None:
        """Update token usage statistics (placeholder for database update)"""
        # In real implementation, this would update database
        pass
    
    def _audit_token_action(self, user: User, action: str, token_id: str, details: str) -> None:
        """Audit log token-related actions"""
        try:
            from .audit_logger import SecurityAuditLogger
            
            audit_logger = SecurityAuditLogger()
            # Log as API access event with token context
            audit_logger.log_api_access(
                user=user,
                endpoint='token_management',
                method=action,
                success=True,
                response_code=200,
                request_data={
                    'token_id': token_id,
                    'action': action,
                    'details': details
                }
            )
        except ImportError:
            self.logger.info(f"TOKEN_AUDIT: {action} - Token {token_id} - User {user.username} - {details}")
        except Exception as e:
            self.logger.error(f"Failed to audit log token action: {str(e)}")


# Convenience functions for common token operations

def create_fabric_token(user: User, fabric_id: int, name: str, expires_in_days: int = 90) -> Dict[str, Any]:
    """Create a fabric-specific access token"""
    manager = APITokenManager()
    
    permissions = TokenPermissions(
        scopes={TokenScope.READ, TokenScope.WRITE},
        fabric_ids={fabric_id}
    )
    
    return manager.create_gitops_token(
        user=user,
        name=name,
        permissions=permissions,
        expires_in_days=expires_in_days
    )


def create_readonly_token(user: User, name: str, expires_in_days: int = 365) -> Dict[str, Any]:
    """Create a read-only access token"""
    manager = APITokenManager()
    
    permissions = TokenPermissions(
        scopes={TokenScope.READ}
    )
    
    return manager.create_gitops_token(
        user=user,
        name=name,
        permissions=permissions,
        expires_in_days=expires_in_days
    )


def create_admin_token(user: User, name: str, expires_in_days: int = 30) -> Dict[str, Any]:
    """Create an administrative access token"""
    manager = APITokenManager()
    
    permissions = TokenPermissions(
        scopes={TokenScope.ADMIN, TokenScope.CREDENTIAL_MANAGEMENT}
    )
    
    return manager.create_gitops_token(
        user=user,
        name=name,
        permissions=permissions,
        expires_in_days=expires_in_days
    )