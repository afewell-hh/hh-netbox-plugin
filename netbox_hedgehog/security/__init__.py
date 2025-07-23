"""
NetBox Hedgehog Security Framework

This package provides comprehensive security features for the GitOps system:
- Encrypted credential storage and management
- Role-based access control (RBAC) for GitOps operations
- Security audit logging and monitoring
- API security enhancements
- Compliance and policy enforcement
"""

__version__ = "1.0.0"
__author__ = "Hedgehog Security Team"

# Core security components
from .credential_manager import SecureCredentialManager
from .rbac import GitOpsPermissions, GitOpsRoleManager
from .audit_logger import SecurityAuditLogger
from .token_manager import APITokenManager

# Security mixins and decorators
from .decorators import require_gitops_permission, fabric_access_required
from .mixins import GitOpsPermissionMixin

__all__ = [
    'SecureCredentialManager',
    'GitOpsPermissions', 
    'GitOpsRoleManager',
    'SecurityAuditLogger',
    'APITokenManager',
    'require_gitops_permission',
    'fabric_access_required',
    'GitOpsPermissionMixin',
]