"""
Role-Based Access Control (RBAC) System for GitOps Operations

This module provides comprehensive RBAC functionality including:
- GitOps-specific permissions and roles
- Fabric-level access control
- Permission inheritance and delegation
- Role management and assignment
"""

import logging
from typing import Dict, List, Set, Optional, Any
from enum import Enum
from dataclasses import dataclass
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class GitOpsPermissions:
    """
    Define GitOps-specific permissions and roles.
    
    This class centralizes all permission definitions for GitOps operations,
    providing a clear hierarchy and structure for access control.
    """
    
    # Fabric-level permissions
    VIEW_FABRIC = 'netbox_hedgehog.view_fabric'
    EDIT_FABRIC = 'netbox_hedgehog.edit_fabric'
    DELETE_FABRIC = 'netbox_hedgehog.delete_fabric'
    SYNC_FABRIC = 'netbox_hedgehog.sync_fabric'
    MANAGE_FABRIC_GITOPS = 'netbox_hedgehog.manage_fabric_gitops'
    
    # Git repository permissions
    VIEW_GIT_REPOSITORY = 'netbox_hedgehog.view_git_repository'
    EDIT_GIT_REPOSITORY = 'netbox_hedgehog.edit_git_repository'
    DELETE_GIT_REPOSITORY = 'netbox_hedgehog.delete_git_repository'
    TEST_GIT_CONNECTION = 'netbox_hedgehog.test_git_connection'
    
    # File management permissions
    UPLOAD_FILES = 'netbox_hedgehog.upload_files'
    EDIT_MANAGED_FILES = 'netbox_hedgehog.edit_managed_files'
    ACCESS_RAW_FILES = 'netbox_hedgehog.access_raw_files'
    DELETE_FILES = 'netbox_hedgehog.delete_files'
    ARCHIVE_FILES = 'netbox_hedgehog.archive_files'
    
    # GitOps operations permissions
    INIT_GITOPS = 'netbox_hedgehog.init_gitops'
    INGEST_RAW_FILES = 'netbox_hedgehog.ingest_raw_files'
    MANAGE_WATCHERS = 'netbox_hedgehog.manage_watchers'
    TRIGGER_SYNC = 'netbox_hedgehog.trigger_sync'
    
    # Credential management permissions
    VIEW_CREDENTIALS = 'netbox_hedgehog.view_credentials'
    MANAGE_CREDENTIALS = 'netbox_hedgehog.manage_credentials'
    ROTATE_CREDENTIALS = 'netbox_hedgehog.rotate_credentials'
    BACKUP_CREDENTIALS = 'netbox_hedgehog.backup_credentials'
    
    # Administrative permissions
    VIEW_AUDIT_LOGS = 'netbox_hedgehog.view_audit_logs'
    MANAGE_SECURITY_SETTINGS = 'netbox_hedgehog.manage_security_settings'
    ADMIN_GITOPS = 'netbox_hedgehog.admin_gitops'
    MANAGE_ROLES = 'netbox_hedgehog.manage_roles'
    
    # API permissions
    API_READ_ACCESS = 'netbox_hedgehog.api_read_access'
    API_WRITE_ACCESS = 'netbox_hedgehog.api_write_access'
    API_ADMIN_ACCESS = 'netbox_hedgehog.api_admin_access'
    
    # All permissions grouped by category
    FABRIC_PERMISSIONS = [
        VIEW_FABRIC, EDIT_FABRIC, DELETE_FABRIC, SYNC_FABRIC, MANAGE_FABRIC_GITOPS
    ]
    
    GIT_PERMISSIONS = [
        VIEW_GIT_REPOSITORY, EDIT_GIT_REPOSITORY, DELETE_GIT_REPOSITORY, TEST_GIT_CONNECTION
    ]
    
    FILE_PERMISSIONS = [
        UPLOAD_FILES, EDIT_MANAGED_FILES, ACCESS_RAW_FILES, DELETE_FILES, ARCHIVE_FILES
    ]
    
    GITOPS_PERMISSIONS = [
        INIT_GITOPS, INGEST_RAW_FILES, MANAGE_WATCHERS, TRIGGER_SYNC
    ]
    
    CREDENTIAL_PERMISSIONS = [
        VIEW_CREDENTIALS, MANAGE_CREDENTIALS, ROTATE_CREDENTIALS, BACKUP_CREDENTIALS
    ]
    
    ADMIN_PERMISSIONS = [
        VIEW_AUDIT_LOGS, MANAGE_SECURITY_SETTINGS, ADMIN_GITOPS, MANAGE_ROLES
    ]
    
    API_PERMISSIONS = [
        API_READ_ACCESS, API_WRITE_ACCESS, API_ADMIN_ACCESS
    ]
    
    ALL_PERMISSIONS = (
        FABRIC_PERMISSIONS + GIT_PERMISSIONS + FILE_PERMISSIONS + 
        GITOPS_PERMISSIONS + CREDENTIAL_PERMISSIONS + ADMIN_PERMISSIONS + API_PERMISSIONS
    )


class GitOpsRoles:
    """
    Predefined GitOps roles with their associated permissions.
    """
    
    # Role definitions
    VIEWER = 'gitops_viewer'
    EDITOR = 'gitops_editor'
    OPERATOR = 'gitops_operator'
    ADMIN = 'gitops_admin'
    SECURITY_ADMIN = 'gitops_security_admin'
    
    # Role to permissions mapping
    ROLE_PERMISSIONS = {
        VIEWER: [
            GitOpsPermissions.VIEW_FABRIC,
            GitOpsPermissions.VIEW_GIT_REPOSITORY,
            GitOpsPermissions.API_READ_ACCESS,
        ],
        
        EDITOR: [
            GitOpsPermissions.VIEW_FABRIC,
            GitOpsPermissions.EDIT_FABRIC,
            GitOpsPermissions.VIEW_GIT_REPOSITORY,
            GitOpsPermissions.EDIT_GIT_REPOSITORY,
            GitOpsPermissions.UPLOAD_FILES,
            GitOpsPermissions.EDIT_MANAGED_FILES,
            GitOpsPermissions.API_READ_ACCESS,
            GitOpsPermissions.API_WRITE_ACCESS,
        ],
        
        OPERATOR: [
            GitOpsPermissions.VIEW_FABRIC,
            GitOpsPermissions.EDIT_FABRIC,
            GitOpsPermissions.SYNC_FABRIC,
            GitOpsPermissions.MANAGE_FABRIC_GITOPS,
            GitOpsPermissions.VIEW_GIT_REPOSITORY,
            GitOpsPermissions.EDIT_GIT_REPOSITORY,
            GitOpsPermissions.TEST_GIT_CONNECTION,
            GitOpsPermissions.UPLOAD_FILES,
            GitOpsPermissions.EDIT_MANAGED_FILES,
            GitOpsPermissions.ACCESS_RAW_FILES,
            GitOpsPermissions.INIT_GITOPS,
            GitOpsPermissions.INGEST_RAW_FILES,
            GitOpsPermissions.MANAGE_WATCHERS,
            GitOpsPermissions.TRIGGER_SYNC,
            GitOpsPermissions.API_READ_ACCESS,
            GitOpsPermissions.API_WRITE_ACCESS,
        ],
        
        ADMIN: [
            # All operator permissions plus admin capabilities
            *ROLE_PERMISSIONS[OPERATOR],
            GitOpsPermissions.DELETE_FABRIC,
            GitOpsPermissions.DELETE_GIT_REPOSITORY,
            GitOpsPermissions.DELETE_FILES,
            GitOpsPermissions.ARCHIVE_FILES,
            GitOpsPermissions.VIEW_CREDENTIALS,
            GitOpsPermissions.MANAGE_CREDENTIALS,
            GitOpsPermissions.VIEW_AUDIT_LOGS,
            GitOpsPermissions.ADMIN_GITOPS,
            GitOpsPermissions.MANAGE_ROLES,
            GitOpsPermissions.API_ADMIN_ACCESS,
        ],
        
        SECURITY_ADMIN: [
            # Security-focused permissions
            GitOpsPermissions.VIEW_FABRIC,
            GitOpsPermissions.VIEW_GIT_REPOSITORY,
            GitOpsPermissions.VIEW_CREDENTIALS,
            GitOpsPermissions.MANAGE_CREDENTIALS,
            GitOpsPermissions.ROTATE_CREDENTIALS,
            GitOpsPermissions.BACKUP_CREDENTIALS,
            GitOpsPermissions.VIEW_AUDIT_LOGS,
            GitOpsPermissions.MANAGE_SECURITY_SETTINGS,
            GitOpsPermissions.MANAGE_ROLES,
            GitOpsPermissions.API_READ_ACCESS,
        ]
    }
    
    # Role descriptions
    ROLE_DESCRIPTIONS = {
        VIEWER: "Can view fabrics and repositories but cannot make changes",
        EDITOR: "Can edit fabrics and repositories, upload files",
        OPERATOR: "Can perform all GitOps operations including sync and automation",
        ADMIN: "Full administrative access to all GitOps functionality",
        SECURITY_ADMIN: "Specialized role for security and credential management"
    }


@dataclass
class FabricPermissionContext:
    """Context for fabric-specific permission checks"""
    fabric_id: int
    fabric_name: str
    user_id: int
    user_groups: List[str]
    requested_permission: str
    additional_context: Dict[str, Any] = None


@dataclass
class PermissionCheckResult:
    """Result of a permission check"""
    granted: bool
    reason: str
    fabric_id: Optional[int] = None
    permission: Optional[str] = None
    user_id: Optional[int] = None
    checked_at: Optional[timezone.datetime] = None


class GitOpsRoleManager:
    """
    Manage GitOps roles and their permissions.
    
    This class handles role creation, assignment, and permission management
    for the GitOps system.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def ensure_permissions_exist(self) -> Dict[str, bool]:
        """
        Ensure all GitOps permissions exist in the database.
        
        Returns:
            Dict mapping permission names to creation status
        """
        results = {}
        
        try:
            # Get content types for our models
            fabric_ct = ContentType.objects.get_for_model(
                self._get_fabric_model()
            )
            git_repo_ct = ContentType.objects.get_for_model(
                self._get_git_repository_model()
            )
            
            # Permission definitions with their content types
            permission_defs = [
                # Fabric permissions
                ('view_fabric', 'Can view fabric', fabric_ct),
                ('edit_fabric', 'Can edit fabric', fabric_ct),
                ('delete_fabric', 'Can delete fabric', fabric_ct),
                ('sync_fabric', 'Can sync fabric', fabric_ct),
                ('manage_fabric_gitops', 'Can manage fabric GitOps', fabric_ct),
                
                # Git repository permissions
                ('view_git_repository', 'Can view git repository', git_repo_ct),
                ('edit_git_repository', 'Can edit git repository', git_repo_ct),
                ('delete_git_repository', 'Can delete git repository', git_repo_ct),
                ('test_git_connection', 'Can test git connection', git_repo_ct),
                
                # Custom GitOps permissions (using fabric as base content type)
                ('upload_files', 'Can upload files', fabric_ct),
                ('edit_managed_files', 'Can edit managed files', fabric_ct),
                ('access_raw_files', 'Can access raw files', fabric_ct),
                ('delete_files', 'Can delete files', fabric_ct),
                ('archive_files', 'Can archive files', fabric_ct),
                ('init_gitops', 'Can initialize GitOps', fabric_ct),
                ('ingest_raw_files', 'Can ingest raw files', fabric_ct),
                ('manage_watchers', 'Can manage watchers', fabric_ct),
                ('trigger_sync', 'Can trigger sync', fabric_ct),
                ('view_credentials', 'Can view credentials', fabric_ct),
                ('manage_credentials', 'Can manage credentials', fabric_ct),
                ('rotate_credentials', 'Can rotate credentials', fabric_ct),
                ('backup_credentials', 'Can backup credentials', fabric_ct),
                ('view_audit_logs', 'Can view audit logs', fabric_ct),
                ('manage_security_settings', 'Can manage security settings', fabric_ct),
                ('admin_gitops', 'Can administer GitOps', fabric_ct),
                ('manage_roles', 'Can manage roles', fabric_ct),
                ('api_read_access', 'Can read via API', fabric_ct),
                ('api_write_access', 'Can write via API', fabric_ct),
                ('api_admin_access', 'Can admin via API', fabric_ct),
            ]
            
            for codename, name, content_type in permission_defs:
                permission, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=content_type,
                    defaults={'name': name}
                )
                results[f"{content_type.app_label}.{codename}"] = created
                
                if created:
                    self.logger.info(f"Created permission: {name}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to ensure permissions exist: {str(e)}")
            return {}
    
    def create_role_groups(self) -> Dict[str, bool]:
        """
        Create Django groups for GitOps roles.
        
        Returns:
            Dict mapping role names to creation status
        """
        results = {}
        
        try:
            with transaction.atomic():
                for role_name, permissions in GitOpsRoles.ROLE_PERMISSIONS.items():
                    group, created = Group.objects.get_or_create(
                        name=role_name,
                        defaults={'name': role_name}
                    )
                    
                    if created or not group.permissions.exists():
                        # Add permissions to group
                        permission_objects = []
                        for perm_name in permissions:
                            try:
                                app_label, codename = perm_name.split('.', 1)
                                permission = Permission.objects.get(
                                    content_type__app_label=app_label,
                                    codename=codename
                                )
                                permission_objects.append(permission)
                            except Permission.DoesNotExist:
                                self.logger.warning(f"Permission not found: {perm_name}")
                        
                        group.permissions.set(permission_objects)
                        self.logger.info(f"Updated permissions for role: {role_name}")
                    
                    results[role_name] = created
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to create role groups: {str(e)}")
            return {}
    
    def assign_user_to_role(self, user: User, role_name: str) -> bool:
        """
        Assign a user to a GitOps role.
        
        Args:
            user: User to assign
            role_name: Role to assign
            
        Returns:
            True if assignment successful
        """
        try:
            if role_name not in GitOpsRoles.ROLE_PERMISSIONS:
                raise ValueError(f"Invalid role: {role_name}")
            
            group = Group.objects.get(name=role_name)
            user.groups.add(group)
            
            # Audit log the role assignment
            self._audit_role_action(
                user=user,
                action='role_assigned',
                details=f"User assigned to role: {role_name}"
            )
            
            self.logger.info(f"Assigned user {user.username} to role {role_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to assign user {user.username} to role {role_name}: {str(e)}")
            return False
    
    def remove_user_from_role(self, user: User, role_name: str) -> bool:
        """
        Remove a user from a GitOps role.
        
        Args:
            user: User to remove
            role_name: Role to remove from
            
        Returns:
            True if removal successful
        """
        try:
            if role_name not in GitOpsRoles.ROLE_PERMISSIONS:
                raise ValueError(f"Invalid role: {role_name}")
            
            group = Group.objects.get(name=role_name)
            user.groups.remove(group)
            
            # Audit log the role removal
            self._audit_role_action(
                user=user,
                action='role_removed',
                details=f"User removed from role: {role_name}"
            )
            
            self.logger.info(f"Removed user {user.username} from role {role_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove user {user.username} from role {role_name}: {str(e)}")
            return False
    
    def get_user_roles(self, user: User) -> List[str]:
        """
        Get all GitOps roles for a user.
        
        Args:
            user: User to check
            
        Returns:
            List of role names
        """
        try:
            gitops_groups = user.groups.filter(
                name__in=GitOpsRoles.ROLE_PERMISSIONS.keys()
            )
            return [group.name for group in gitops_groups]
        except Exception as e:
            self.logger.error(f"Failed to get roles for user {user.username}: {str(e)}")
            return []
    
    def get_user_permissions(self, user: User) -> Set[str]:
        """
        Get all GitOps permissions for a user.
        
        Args:
            user: User to check
            
        Returns:
            Set of permission names
        """
        try:
            permissions = set()
            
            # Get permissions from roles (groups)
            for role in self.get_user_roles(user):
                permissions.update(GitOpsRoles.ROLE_PERMISSIONS.get(role, []))
            
            # Get direct permissions
            user_permissions = user.user_permissions.filter(
                content_type__app_label='netbox_hedgehog'
            )
            for perm in user_permissions:
                permissions.add(f"{perm.content_type.app_label}.{perm.codename}")
            
            return permissions
            
        except Exception as e:
            self.logger.error(f"Failed to get permissions for user {user.username}: {str(e)}")
            return set()
    
    def check_permission(self, user: User, permission: str, fabric=None) -> PermissionCheckResult:
        """
        Check if user has a specific permission.
        
        Args:
            user: User to check
            permission: Permission to check
            fabric: Optional fabric for context
            
        Returns:
            PermissionCheckResult
        """
        try:
            checked_at = timezone.now()
            
            # Check if user has the permission
            user_permissions = self.get_user_permissions(user)
            has_permission = permission in user_permissions
            
            # Additional fabric-specific checks could go here
            if fabric and has_permission:
                # Fabric-level permission logic could be added here
                pass
            
            reason = "Permission granted" if has_permission else "Permission denied"
            
            # Audit log the permission check
            self._audit_permission_check(
                user=user,
                permission=permission,
                granted=has_permission,
                fabric=fabric
            )
            
            return PermissionCheckResult(
                granted=has_permission,
                reason=reason,
                fabric_id=fabric.id if fabric else None,
                permission=permission,
                user_id=user.id,
                checked_at=checked_at
            )
            
        except Exception as e:
            self.logger.error(f"Permission check failed for user {user.username}: {str(e)}")
            return PermissionCheckResult(
                granted=False,
                reason=f"Permission check error: {str(e)}",
                permission=permission,
                user_id=user.id,
                checked_at=timezone.now()
            )
    
    def get_role_summary(self) -> Dict[str, Any]:
        """
        Get summary of all roles and their usage.
        
        Returns:
            Role summary dictionary
        """
        try:
            summary = {
                'roles': {},
                'total_users': User.objects.count(),
                'users_with_gitops_roles': 0
            }
            
            gitops_users = set()
            
            for role_name in GitOpsRoles.ROLE_PERMISSIONS.keys():
                try:
                    group = Group.objects.get(name=role_name)
                    user_count = group.user_set.count()
                    users = list(group.user_set.values_list('username', flat=True))
                    gitops_users.update(users)
                    
                    summary['roles'][role_name] = {
                        'description': GitOpsRoles.ROLE_DESCRIPTIONS.get(role_name, ''),
                        'permission_count': len(GitOpsRoles.ROLE_PERMISSIONS[role_name]),
                        'user_count': user_count,
                        'users': users
                    }
                except Group.DoesNotExist:
                    summary['roles'][role_name] = {
                        'description': GitOpsRoles.ROLE_DESCRIPTIONS.get(role_name, ''),
                        'permission_count': len(GitOpsRoles.ROLE_PERMISSIONS[role_name]),
                        'user_count': 0,
                        'users': [],
                        'status': 'not_created'
                    }
            
            summary['users_with_gitops_roles'] = len(gitops_users)
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to get role summary: {str(e)}")
            return {'error': str(e)}
    
    def initialize_rbac_system(self) -> Dict[str, Any]:
        """
        Initialize the complete RBAC system.
        
        Returns:
            Initialization result
        """
        try:
            self.logger.info("Initializing GitOps RBAC system...")
            
            # Step 1: Ensure permissions exist
            permission_results = self.ensure_permissions_exist()
            permissions_created = sum(1 for created in permission_results.values() if created)
            
            # Step 2: Create role groups
            role_results = self.create_role_groups()
            roles_created = sum(1 for created in role_results.values() if created)
            
            # Step 3: Get summary
            summary = self.get_role_summary()
            
            self.logger.info(f"RBAC initialization complete. Created {permissions_created} permissions, {roles_created} roles")
            
            return {
                'success': True,
                'permissions_created': permissions_created,
                'roles_created': roles_created,
                'permission_results': permission_results,
                'role_results': role_results,
                'summary': summary,
                'initialized_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"RBAC initialization failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'initialized_at': timezone.now().isoformat()
            }
    
    def _get_fabric_model(self):
        """Get the HedgehogFabric model"""
        from django.apps import apps
        return apps.get_model('netbox_hedgehog', 'HedgehogFabric')
    
    def _get_git_repository_model(self):
        """Get the GitRepository model"""
        from django.apps import apps
        return apps.get_model('netbox_hedgehog', 'GitRepository')
    
    def _audit_role_action(self, user: User, action: str, details: str) -> None:
        """Audit log role-related actions"""
        try:
            from .audit_logger import SecurityAuditLogger
            
            audit_logger = SecurityAuditLogger()
            audit_logger.log_permission_check(
                user=user,
                permission=action,
                granted=True,
                details=details
            )
        except ImportError:
            self.logger.info(f"ROLE_AUDIT: {action} - User {user.username} - {details}")
        except Exception as e:
            self.logger.error(f"Failed to audit log role action: {str(e)}")
    
    def _audit_permission_check(self, user: User, permission: str, granted: bool, fabric=None) -> None:
        """Audit log permission checks"""
        try:
            from .audit_logger import SecurityAuditLogger
            
            audit_logger = SecurityAuditLogger()
            audit_logger.log_permission_check(
                user=user,
                permission=permission,
                granted=granted,
                fabric=fabric
            )
        except ImportError:
            fabric_info = f" (Fabric: {fabric.name})" if fabric else ""
            self.logger.info(f"PERMISSION_AUDIT: {permission} - User {user.username} - {'GRANTED' if granted else 'DENIED'}{fabric_info}")
        except Exception as e:
            self.logger.error(f"Failed to audit log permission check: {str(e)}")


class FabricAccessManager:
    """
    Manage fabric-specific access control.
    
    This class handles permissions that are specific to individual fabrics,
    allowing for fine-grained access control at the fabric level.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.role_manager = GitOpsRoleManager()
    
    def check_fabric_access(self, user: User, fabric, permission: str) -> PermissionCheckResult:
        """
        Check if user has access to specific fabric with given permission.
        
        Args:
            user: User to check
            fabric: Fabric instance
            permission: Permission to check
            
        Returns:
            PermissionCheckResult
        """
        try:
            # First check if user has the general permission
            general_check = self.role_manager.check_permission(user, permission, fabric)
            
            if not general_check.granted:
                return general_check
            
            # Additional fabric-specific checks could go here
            # For example: fabric ownership, team membership, etc.
            
            # For now, if user has general permission, they have fabric access
            return PermissionCheckResult(
                granted=True,
                reason=f"User has {permission} permission for fabric {fabric.name}",
                fabric_id=fabric.id,
                permission=permission,
                user_id=user.id,
                checked_at=timezone.now()
            )
            
        except Exception as e:
            self.logger.error(f"Fabric access check failed: {str(e)}")
            return PermissionCheckResult(
                granted=False,
                reason=f"Access check error: {str(e)}",
                fabric_id=fabric.id,
                permission=permission,
                user_id=user.id,
                checked_at=timezone.now()
            )
    
    def get_accessible_fabrics(self, user: User, permission: str = None) -> List[Any]:
        """
        Get list of fabrics accessible to user.
        
        Args:
            user: User to check
            permission: Optional specific permission to filter by
            
        Returns:
            List of accessible fabric instances
        """
        try:
            from django.apps import apps
            HedgehogFabric = apps.get_model('netbox_hedgehog', 'HedgehogFabric')
            
            # For now, return all fabrics if user has any GitOps permissions
            user_permissions = self.role_manager.get_user_permissions(user)
            
            if not user_permissions:
                return []
            
            # If specific permission required, check for it
            if permission and permission not in user_permissions:
                return []
            
            # Return all fabrics (in a more complex implementation, 
            # this would filter based on fabric-specific permissions)
            return list(HedgehogFabric.objects.all())
            
        except Exception as e:
            self.logger.error(f"Failed to get accessible fabrics for user {user.username}: {str(e)}")
            return []