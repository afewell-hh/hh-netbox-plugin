"""
Security Mixins for GitOps Views

This module provides mixins for class-based views to enforce security policies
and permissions consistently across the GitOps system.
"""

import logging
from typing import Any, Dict, Optional, List
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


class GitOpsSecurityMixin:
    """
    Base security mixin for all GitOps views.
    
    Provides common security functionality including audit logging,
    user context, and error handling.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.security_logger = self._get_security_logger()
    
    def _get_security_logger(self):
        """Get security audit logger instance"""
        try:
            from .audit_logger import SecurityAuditLogger
            return SecurityAuditLogger()
        except ImportError:
            return None
    
    def get_user_context(self) -> Dict[str, Any]:
        """Get current user context for security logging"""
        user = getattr(self.request, 'user', None)
        return {
            'user_id': user.id if user and user.is_authenticated else None,
            'username': user.username if user and user.is_authenticated else 'anonymous',
            'is_authenticated': user.is_authenticated if user else False,
            'is_staff': user.is_staff if user and user.is_authenticated else False,
            'is_superuser': user.is_superuser if user and user.is_authenticated else False,
            'groups': list(user.groups.values_list('name', flat=True)) if user and user.is_authenticated else []
        }
    
    def log_security_event(
        self, 
        event_type: str, 
        action: str, 
        success: bool = True, 
        details: Dict[str, Any] = None,
        fabric=None
    ):
        """Log security event with user context"""
        if self.security_logger:
            try:
                user = getattr(self.request, 'user', None)
                if user and user.is_authenticated:
                    if event_type == 'permission_check':
                        self.security_logger.log_permission_check(
                            user=user,
                            permission=action,
                            granted=success,
                            fabric=fabric,
                            details=str(details or {}),
                            request=self.request
                        )
                    elif event_type == 'file_operation':
                        self.security_logger.log_file_operation(
                            user=user,
                            fabric=fabric,
                            file_path=details.get('file_path', 'unknown'),
                            operation=action,
                            success=success,
                            details=details,
                            request=self.request
                        )
                    elif event_type == 'api_access':
                        self.security_logger.log_api_access(
                            user=user,
                            endpoint=self.request.path,
                            method=self.request.method,
                            success=success,
                            response_code=200 if success else 403,
                            fabric=fabric,
                            request_data=details,
                            request=self.request
                        )
            except Exception as e:
                logger.error(f"Failed to log security event: {str(e)}")
    
    def handle_security_violation(
        self, 
        violation_type: str, 
        attempted_action: str, 
        reason: str,
        fabric=None
    ):
        """Handle security policy violations"""
        if self.security_logger:
            try:
                user = getattr(self.request, 'user', None)
                self.security_logger.log_security_violation(
                    user=user,
                    violation_type=violation_type,
                    attempted_action=attempted_action,
                    reason=reason,
                    fabric=fabric,
                    request=self.request
                )
            except Exception as e:
                logger.error(f"Failed to log security violation: {str(e)}")


class GitOpsPermissionMixin(GitOpsSecurityMixin):
    """
    Mixin for views requiring GitOps permissions.
    
    Provides permission checking with audit logging and consistent error handling.
    """
    
    gitops_permission_required = None
    fabric_permission_required = None
    fabric_url_kwarg = 'fabric_id'
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to check permissions"""
        # Check authentication first
        if not request.user.is_authenticated:
            self.handle_security_violation(
                violation_type='unauthenticated_access',
                attempted_action=self.__class__.__name__,
                reason='User not authenticated'
            )
            return self.handle_no_permission()
        
        # Check GitOps permissions
        if not self.check_gitops_permissions(request, *args, **kwargs):
            return self.handle_no_permission()
        
        return super().dispatch(request, *args, **kwargs)
    
    def check_gitops_permissions(self, request, *args, **kwargs) -> bool:
        """
        Check user has required GitOps permissions.
        
        Returns:
            True if user has required permissions
        """
        try:
            from .rbac import GitOpsRoleManager, FabricAccessManager
            
            role_manager = GitOpsRoleManager()
            
            # Get fabric if specified
            fabric = self.get_fabric_object(kwargs) if self.fabric_url_kwarg in kwargs else None
            
            # Check general GitOps permission
            if self.gitops_permission_required:
                permission_result = role_manager.check_permission(
                    request.user,
                    self.gitops_permission_required,
                    fabric
                )
                
                self.log_security_event(
                    event_type='permission_check',
                    action=self.gitops_permission_required,
                    success=permission_result.granted,
                    fabric=fabric
                )
                
                if not permission_result.granted:
                    self.handle_security_violation(
                        violation_type='permission_denied',
                        attempted_action=self.gitops_permission_required,
                        reason=permission_result.reason,
                        fabric=fabric
                    )
                    return False
            
            # Check fabric-specific permission
            if self.fabric_permission_required and fabric:
                access_manager = FabricAccessManager()
                access_result = access_manager.check_fabric_access(
                    request.user,
                    fabric,
                    self.fabric_permission_required
                )
                
                self.log_security_event(
                    event_type='permission_check',
                    action=self.fabric_permission_required,
                    success=access_result.granted,
                    fabric=fabric
                )
                
                if not access_result.granted:
                    self.handle_security_violation(
                        violation_type='fabric_access_denied',
                        attempted_action=self.fabric_permission_required,
                        reason=access_result.reason,
                        fabric=fabric
                    )
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Permission check failed: {str(e)}")
            self.handle_security_violation(
                violation_type='permission_check_error',
                attempted_action='permission_validation',
                reason=str(e)
            )
            return False
    
    def get_fabric_object(self, kwargs):
        """Get fabric object from URL kwargs"""
        try:
            fabric_id = kwargs.get(self.fabric_url_kwarg)
            if fabric_id:
                from django.apps import apps
                HedgehogFabric = apps.get_model('netbox_hedgehog', 'HedgehogFabric')
                return get_object_or_404(HedgehogFabric, id=fabric_id)
        except Exception as e:
            logger.error(f"Failed to get fabric object: {str(e)}")
        return None
    
    def handle_no_permission(self):
        """Handle permission denied cases"""
        # Return appropriate response based on request type
        if hasattr(self, 'format_kwarg') or 'api' in self.request.path:
            # REST API view
            return Response(
                {
                    'success': False,
                    'error': 'Permission denied',
                    'message': 'You do not have permission to access this resource'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        elif self.request.headers.get('Accept', '').startswith('application/json'):
            # JSON request
            return JsonResponse(
                {
                    'success': False,
                    'error': 'Permission denied',
                    'message': 'You do not have permission to access this resource'
                },
                status=403
            )
        else:
            # Regular HTTP request
            raise PermissionDenied('You do not have permission to access this resource')


class GitOpsFabricMixin(GitOpsPermissionMixin):
    """
    Mixin for views that operate on specific fabrics.
    
    Provides fabric context and fabric-specific permission checking.
    """
    
    fabric_url_kwarg = 'fabric_id'
    fabric_permission_map = {
        'GET': 'netbox_hedgehog.view_fabric',
        'POST': 'netbox_hedgehog.edit_fabric',
        'PUT': 'netbox_hedgehog.edit_fabric',
        'PATCH': 'netbox_hedgehog.edit_fabric',
        'DELETE': 'netbox_hedgehog.delete_fabric',
    }
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to set fabric permission based on HTTP method"""
        # Set fabric permission based on HTTP method
        self.fabric_permission_required = self.fabric_permission_map.get(
            request.method,
            'netbox_hedgehog.view_fabric'
        )
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_fabric(self):
        """Get fabric object for this view"""
        if not hasattr(self, '_fabric'):
            self._fabric = self.get_fabric_object(self.kwargs)
        return self._fabric
    
    def get_context_data(self, **kwargs):
        """Add fabric to context data"""
        context = super().get_context_data(**kwargs)
        context['fabric'] = self.get_fabric()
        return context


class GitOpsAPISecurityMixin(GitOpsSecurityMixin):
    """
    Security mixin specifically for API views.
    
    Provides API-specific security features including rate limiting
    and structured error responses.
    """
    
    permission_classes = [IsAuthenticated]
    rate_limit_requests = 100
    rate_limit_window = 3600  # 1 hour
    
    def initial(self, request, *args, **kwargs):
        """Override initial to add security checks"""
        super().initial(request, *args, **kwargs)
        
        # Check rate limiting
        if not self.check_rate_limit(request):
            from rest_framework.exceptions import Throttled
            raise Throttled(detail="Rate limit exceeded")
        
        # Log API access
        self.log_security_event(
            event_type='api_access',
            action=f"{request.method} {request.path}",
            success=True,
            details={'endpoint': request.path, 'method': request.method}
        )
    
    def check_rate_limit(self, request) -> bool:
        """Check API rate limiting"""
        try:
            from .rate_limiting import GitOpsRateLimiter
            
            rate_limiter = GitOpsRateLimiter()
            rate_key = f"api_user:{request.user.id}"
            
            is_allowed, current_count, reset_time = rate_limiter.check_rate_limit(
                key=rate_key,
                max_requests=self.rate_limit_requests,
                time_window=self.rate_limit_window
            )
            
            if not is_allowed:
                self.handle_security_violation(
                    violation_type='api_rate_limit_exceeded',
                    attempted_action=f"{request.method} {request.path}",
                    reason=f"Rate limit exceeded: {current_count}/{self.rate_limit_requests}"
                )
                return False
            
            # Record the request
            rate_limiter.record_request(rate_key)
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {str(e)}")
            # Allow request if rate limiting fails
            return True
    
    def handle_exception(self, exc):
        """Override exception handling to log security events"""
        try:
            # Log the exception as a security event
            self.log_security_event(
                event_type='api_access',
                action=f"{self.request.method} {self.request.path}",
                success=False,
                details={'error': str(exc), 'exception_type': type(exc).__name__}
            )
        except Exception as log_error:
            logger.error(f"Failed to log API exception: {str(log_error)}")
        
        return super().handle_exception(exc)


class GitOpsCredentialMixin(GitOpsPermissionMixin):
    """
    Mixin for views that handle credential operations.
    
    Provides enhanced security for credential-related operations with
    comprehensive audit logging.
    """
    
    gitops_permission_required = 'netbox_hedgehog.view_credentials'
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to check credential permissions"""
        # Set permission based on operation type
        if request.method in ['POST', 'PUT', 'PATCH']:
            self.gitops_permission_required = 'netbox_hedgehog.manage_credentials'
        elif request.method == 'DELETE':
            self.gitops_permission_required = 'netbox_hedgehog.manage_credentials'
        
        return super().dispatch(request, *args, **kwargs)
    
    def log_credential_operation(
        self, 
        repository, 
        operation: str, 
        success: bool = True,
        details: str = ""
    ):
        """Log credential-specific operations"""
        if self.security_logger:
            try:
                self.security_logger.log_credential_access(
                    user=self.request.user,
                    repository=repository,
                    action=operation,
                    details=details,
                    request=self.request
                )
            except Exception as e:
                logger.error(f"Failed to log credential operation: {str(e)}")
    
    def handle_credential_error(self, repository, operation: str, error: str):
        """Handle credential operation errors with security logging"""
        self.log_credential_operation(
            repository=repository,
            operation=f"{operation}_failed",
            success=False,
            details=error
        )
        
        self.handle_security_violation(
            violation_type='credential_operation_failed',
            attempted_action=operation,
            reason=error
        )


class GitOpsFileOperationMixin(GitOpsPermissionMixin):
    """
    Mixin for views that handle file operations.
    
    Provides security for file upload, edit, and delete operations
    with comprehensive audit logging.
    """
    
    gitops_permission_required = 'netbox_hedgehog.upload_files'
    allowed_file_extensions = {'.yaml', '.yml', '.json'}
    max_file_size = 10 * 1024 * 1024  # 10MB
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to check file operation permissions"""
        # Set permission based on operation type
        if request.method == 'POST' and 'upload' in request.path:
            self.gitops_permission_required = 'netbox_hedgehog.upload_files'
        elif request.method in ['PUT', 'PATCH']:
            self.gitops_permission_required = 'netbox_hedgehog.edit_managed_files'
        elif request.method == 'DELETE':
            self.gitops_permission_required = 'netbox_hedgehog.delete_files'
        
        return super().dispatch(request, *args, **kwargs)
    
    def validate_file_upload(self, file_obj) -> Dict[str, Any]:
        """
        Validate file upload with security checks.
        
        Returns:
            Validation result dictionary
        """
        try:
            import os
            
            # Check file extension
            file_ext = os.path.splitext(file_obj.name)[1].lower()
            if file_ext not in self.allowed_file_extensions:
                return {
                    'valid': False,
                    'error': f'Invalid file extension: {file_ext}. Allowed: {", ".join(self.allowed_file_extensions)}'
                }
            
            # Check file size
            if file_obj.size > self.max_file_size:
                return {
                    'valid': False,
                    'error': f'File too large: {file_obj.size} bytes. Maximum: {self.max_file_size} bytes'
                }
            
            # Basic content validation for YAML/JSON files
            try:
                content = file_obj.read().decode('utf-8')
                file_obj.seek(0)  # Reset file pointer
                
                if file_ext in ['.yaml', '.yml']:
                    import yaml
                    yaml.safe_load(content)
                elif file_ext == '.json':
                    import json
                    json.loads(content)
                
            except Exception as parse_error:
                return {
                    'valid': False,
                    'error': f'Invalid file format: {str(parse_error)}'
                }
            
            return {'valid': True}
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'File validation failed: {str(e)}'
            }
    
    def log_file_operation(
        self, 
        fabric, 
        file_path: str, 
        operation: str,
        success: bool = True,
        details: Dict[str, Any] = None
    ):
        """Log file operations with security context"""
        self.log_security_event(
            event_type='file_operation',
            action=operation,
            success=success,
            details={
                'file_path': file_path,
                **(details or {})
            },
            fabric=fabric
        )


class GitOpsAdminMixin(GitOpsPermissionMixin):
    """
    Mixin for administrative GitOps views.
    
    Provides enhanced security for administrative operations with
    comprehensive audit logging and additional permission checks.
    """
    
    gitops_permission_required = 'netbox_hedgehog.admin_gitops'
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch with additional admin checks"""
        # Additional checks for admin operations
        if not self.check_admin_permissions(request):
            return self.handle_no_permission()
        
        return super().dispatch(request, *args, **kwargs)
    
    def check_admin_permissions(self, request) -> bool:
        """Additional permission checks for admin operations"""
        # Check if user is staff (additional security layer)
        if not request.user.is_staff:
            self.handle_security_violation(
                violation_type='admin_access_denied',
                attempted_action='admin_operation',
                reason='User is not staff member'
            )
            return False
        
        return True
    
    def log_admin_operation(
        self, 
        operation: str, 
        target: str = None,
        success: bool = True,
        details: Dict[str, Any] = None
    ):
        """Log administrative operations"""
        self.log_security_event(
            event_type='configuration_change',
            action=operation,
            success=success,
            details={
                'target': target,
                'admin_operation': True,
                **(details or {})
            }
        )