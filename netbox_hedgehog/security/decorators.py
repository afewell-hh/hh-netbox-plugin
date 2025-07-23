"""
Security Decorators and Mixins for GitOps Operations

This module provides decorators and mixins for enforcing security policies
and permissions throughout the GitOps system.
"""

import functools
import logging
from typing import Callable, Any, Optional, Union
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def require_gitops_permission(permission: str, fabric_param: str = 'fabric_id'):
    """
    Decorator for GitOps permission checking.
    
    Args:
        permission: Required permission name
        fabric_param: Parameter name containing fabric ID (optional)
    
    Usage:
        @require_gitops_permission('netbox_hedgehog.sync_fabric')
        def my_view(request, fabric_id):
            # Function body
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(request_or_self, *args, **kwargs):
            # Handle both function-based and class-based views
            if hasattr(request_or_self, 'request'):
                # Class-based view
                request = request_or_self.request
                view_self = request_or_self
            else:
                # Function-based view
                request = request_or_self
                view_self = None
            
            # Check if user is authenticated
            if not request.user.is_authenticated:
                return _handle_permission_denied(
                    request, 
                    "Authentication required", 
                    view_self
                )
            
            try:
                from .rbac import GitOpsRoleManager
                from .audit_logger import SecurityAuditLogger
                
                role_manager = GitOpsRoleManager()
                audit_logger = SecurityAuditLogger()
                
                # Get fabric if specified
                fabric = None
                if fabric_param in kwargs:
                    fabric_id = kwargs[fabric_param]
                    try:
                        from django.apps import apps
                        HedgehogFabric = apps.get_model('netbox_hedgehog', 'HedgehogFabric')
                        fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
                    except Exception as e:
                        logger.error(f"Failed to get fabric {fabric_id}: {str(e)}")
                        return _handle_permission_denied(
                            request,
                            f"Fabric not found: {fabric_id}",
                            view_self
                        )
                
                # Check permission
                permission_result = role_manager.check_permission(
                    request.user, 
                    permission, 
                    fabric
                )
                
                # Audit log the permission check
                audit_logger.log_permission_check(
                    user=request.user,
                    permission=permission,
                    granted=permission_result.granted,
                    fabric=fabric,
                    details=f"Permission check for {func.__name__}",
                    request=request
                )
                
                if not permission_result.granted:
                    return _handle_permission_denied(
                        request,
                        f"Permission denied: {permission}",
                        view_self,
                        fabric=fabric
                    )
                
                # Permission granted, execute function
                return func(request_or_self, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Permission check failed in decorator: {str(e)}")
                return _handle_permission_denied(
                    request,
                    f"Permission check error: {str(e)}",
                    view_self
                )
        
        return wrapper
    return decorator


def fabric_access_required(action: str, fabric_param: str = 'fabric_id'):
    """
    Decorator for fabric-specific access control.
    
    Args:
        action: The action being performed (for audit logging)
        fabric_param: Parameter name containing fabric ID
    
    Usage:
        @fabric_access_required('sync', 'fabric_id')
        def sync_fabric_view(request, fabric_id):
            # Function body
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(request_or_self, *args, **kwargs):
            # Handle both function-based and class-based views
            if hasattr(request_or_self, 'request'):
                request = request_or_self.request
                view_self = request_or_self
            else:
                request = request_or_self
                view_self = None
            
            # Check authentication
            if not request.user.is_authenticated:
                return _handle_permission_denied(
                    request,
                    "Authentication required",
                    view_self
                )
            
            try:
                from .rbac import FabricAccessManager
                from .audit_logger import SecurityAuditLogger
                
                access_manager = FabricAccessManager()
                audit_logger = SecurityAuditLogger()
                
                # Get fabric
                fabric = None
                if fabric_param in kwargs:
                    fabric_id = kwargs[fabric_param]
                    try:
                        from django.apps import apps
                        HedgehogFabric = apps.get_model('netbox_hedgehog', 'HedgehogFabric')
                        fabric = get_object_or_404(HedgehogFabric, id=fabric_id)
                    except Exception as e:
                        logger.error(f"Failed to get fabric {fabric_id}: {str(e)}")
                        audit_logger.log_security_violation(
                            user=request.user,
                            violation_type='invalid_fabric_access',
                            attempted_action=action,
                            reason=f"Fabric not found: {fabric_id}",
                            request=request
                        )
                        return _handle_permission_denied(
                            request,
                            f"Fabric not found: {fabric_id}",
                            view_self
                        )
                
                # Determine required permission based on action
                permission_map = {
                    'view': 'netbox_hedgehog.view_fabric',
                    'edit': 'netbox_hedgehog.edit_fabric',
                    'sync': 'netbox_hedgehog.sync_fabric',
                    'delete': 'netbox_hedgehog.delete_fabric',
                    'manage_gitops': 'netbox_hedgehog.manage_fabric_gitops',
                }
                
                required_permission = permission_map.get(action, 'netbox_hedgehog.view_fabric')
                
                # Check fabric access
                access_result = access_manager.check_fabric_access(
                    request.user,
                    fabric,
                    required_permission
                )
                
                # Audit log the access check
                audit_logger.log_permission_check(
                    user=request.user,
                    permission=required_permission,
                    granted=access_result.granted,
                    fabric=fabric,
                    details=f"Fabric access check for action: {action}",
                    request=request
                )
                
                if not access_result.granted:
                    audit_logger.log_security_violation(
                        user=request.user,
                        violation_type='unauthorized_fabric_access',
                        attempted_action=action,
                        reason=access_result.reason,
                        fabric=fabric,
                        request=request
                    )
                    return _handle_permission_denied(
                        request,
                        f"Access denied to fabric {fabric.name}: {access_result.reason}",
                        view_self,
                        fabric=fabric
                    )
                
                # Access granted, execute function
                return func(request_or_self, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Fabric access check failed: {str(e)}")
                return _handle_permission_denied(
                    request,
                    f"Access check error: {str(e)}",
                    view_self
                )
        
        return wrapper
    return decorator


def audit_api_access(operation: str = "api_access"):
    """
    Decorator to audit API access events.
    
    Args:
        operation: Description of the API operation
    
    Usage:
        @audit_api_access("fabric_sync_api")
        def api_view(request):
            # Function body
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(request_or_self, *args, **kwargs):
            # Handle both function-based and class-based views
            if hasattr(request_or_self, 'request'):
                request = request_or_self.request
            else:
                request = request_or_self
            
            start_time = timezone.now()
            success = True
            response_code = 200
            
            try:
                # Execute the function
                result = func(request_or_self, *args, **kwargs)
                
                # Extract response code if available
                if hasattr(result, 'status_code'):
                    response_code = result.status_code
                    success = 200 <= response_code < 400
                elif isinstance(result, dict) and 'success' in result:
                    success = result['success']
                    response_code = 200 if success else 400
                
                return result
                
            except Exception as e:
                success = False
                response_code = 500
                logger.error(f"API operation {operation} failed: {str(e)}")
                raise
                
            finally:
                # Audit log the API access
                try:
                    from .audit_logger import SecurityAuditLogger
                    
                    audit_logger = SecurityAuditLogger()
                    
                    # Get fabric context if available
                    fabric = None
                    if 'fabric_id' in kwargs:
                        try:
                            from django.apps import apps
                            HedgehogFabric = apps.get_model('netbox_hedgehog', 'HedgehogFabric')
                            fabric = HedgehogFabric.objects.get(id=kwargs['fabric_id'])
                        except:
                            pass
                    
                    audit_logger.log_api_access(
                        user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                        endpoint=request.path if hasattr(request, 'path') else func.__name__,
                        method=request.method if hasattr(request, 'method') else 'UNKNOWN',
                        success=success,
                        response_code=response_code,
                        fabric=fabric,
                        request=request
                    )
                    
                except Exception as audit_error:
                    logger.error(f"Failed to audit log API access: {str(audit_error)}")
        
        return wrapper
    return decorator


def rate_limit(
    max_requests: int = 100, 
    time_window: int = 3600,  # 1 hour in seconds
    key_func: Optional[Callable] = None
):
    """
    Decorator for rate limiting API requests.
    
    Args:
        max_requests: Maximum requests allowed in time window
        time_window: Time window in seconds
        key_func: Function to generate rate limit key (defaults to user-based)
    
    Usage:
        @rate_limit(max_requests=50, time_window=3600)
        def api_view(request):
            # Function body
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(request_or_self, *args, **kwargs):
            # Handle both function-based and class-based views
            if hasattr(request_or_self, 'request'):
                request = request_or_self.request
                view_self = request_or_self
            else:
                request = request_or_self
                view_self = None
            
            try:
                from .rate_limiting import GitOpsRateLimiter
                
                rate_limiter = GitOpsRateLimiter()
                
                # Generate rate limit key
                if key_func:
                    rate_key = key_func(request)
                else:
                    rate_key = f"user:{request.user.id}" if request.user.is_authenticated else f"ip:{_get_client_ip(request)}"
                
                # Check rate limit
                is_allowed, current_count, reset_time = rate_limiter.check_rate_limit(
                    key=rate_key,
                    max_requests=max_requests,
                    time_window=time_window
                )
                
                if not is_allowed:
                    # Log rate limit violation
                    from .audit_logger import SecurityAuditLogger
                    audit_logger = SecurityAuditLogger()
                    audit_logger.log_security_violation(
                        user=request.user if request.user.is_authenticated else None,
                        violation_type='rate_limit_exceeded',
                        attempted_action=func.__name__,
                        reason=f"Rate limit exceeded: {current_count}/{max_requests} requests",
                        additional_context={'reset_time': reset_time.isoformat()},
                        request=request
                    )
                    
                    return _handle_rate_limit_exceeded(
                        request,
                        current_count,
                        max_requests,
                        reset_time,
                        view_self
                    )
                
                # Record the request
                rate_limiter.record_request(rate_key)
                
                # Execute function
                return func(request_or_self, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Rate limiting check failed: {str(e)}")
                # Allow request to proceed if rate limiting fails
                return func(request_or_self, *args, **kwargs)
        
        return wrapper
    return decorator


def _handle_permission_denied(
    request: HttpRequest,
    message: str,
    view_self: Optional[Any] = None,
    fabric: Optional[Any] = None
) -> Union[HttpResponse, JsonResponse, Response]:
    """
    Handle permission denied responses consistently.
    
    Args:
        request: HTTP request
        message: Error message
        view_self: View instance (for class-based views)
        fabric: Optional fabric context
        
    Returns:
        Appropriate error response
    """
    try:
        from .audit_logger import SecurityAuditLogger
        
        audit_logger = SecurityAuditLogger()
        audit_logger.log_security_violation(
            user=request.user if request.user.is_authenticated else None,
            violation_type='permission_denied',
            attempted_action=request.path,
            reason=message,
            fabric=fabric,
            request=request
        )
        
    except Exception as e:
        logger.error(f"Failed to audit log permission denial: {str(e)}")
    
    # Return appropriate response type
    if hasattr(view_self, 'format_kwarg') or 'api' in request.path:
        # REST API view
        return Response(
            {
                'success': False,
                'error': 'Permission denied',
                'message': message,
                'fabric_id': fabric.id if fabric else None
            },
            status=status.HTTP_403_FORBIDDEN
        )
    elif request.headers.get('Accept', '').startswith('application/json'):
        # JSON request
        return JsonResponse(
            {
                'success': False,
                'error': 'Permission denied',
                'message': message,
                'fabric_id': fabric.id if fabric else None
            },
            status=403
        )
    else:
        # Regular HTTP request
        raise PermissionDenied(message)


def _handle_rate_limit_exceeded(
    request: HttpRequest,
    current_count: int,
    max_requests: int,
    reset_time: Any,
    view_self: Optional[Any] = None
) -> Union[HttpResponse, JsonResponse, Response]:
    """
    Handle rate limit exceeded responses.
    
    Args:
        request: HTTP request
        current_count: Current request count
        max_requests: Maximum allowed requests
        reset_time: When rate limit resets
        view_self: View instance (for class-based views)
        
    Returns:
        Rate limit error response
    """
    message = f"Rate limit exceeded: {current_count}/{max_requests} requests"
    
    # Return appropriate response type
    if hasattr(view_self, 'format_kwarg') or 'api' in request.path:
        # REST API view
        return Response(
            {
                'success': False,
                'error': 'Rate limit exceeded',
                'message': message,
                'rate_limit': {
                    'current': current_count,
                    'limit': max_requests,
                    'reset_time': reset_time.isoformat() if reset_time else None
                }
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    elif request.headers.get('Accept', '').startswith('application/json'):
        # JSON request
        return JsonResponse(
            {
                'success': False,
                'error': 'Rate limit exceeded',
                'message': message,
                'rate_limit': {
                    'current': current_count,
                    'limit': max_requests,
                    'reset_time': reset_time.isoformat() if reset_time else None
                }
            },
            status=429
        )
    else:
        # Regular HTTP request - return simple error
        from django.http import HttpResponseTooManyRequests
        return HttpResponseTooManyRequests(message)


def _get_client_ip(request: HttpRequest) -> str:
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


# Convenience decorators combining common patterns

def secure_gitops_api(permission: str, fabric_param: str = 'fabric_id'):
    """
    Combined decorator for secure API endpoints.
    
    Combines authentication, permission checking, and audit logging.
    """
    def decorator(func: Callable) -> Callable:
        # Apply decorators in reverse order (innermost first)
        func = audit_api_access(f"api_{func.__name__}")(func)
        func = require_gitops_permission(permission, fabric_param)(func)
        func = login_required(func)
        return func
    return decorator


def secure_fabric_operation(action: str, fabric_param: str = 'fabric_id', max_requests: int = 50):
    """
    Combined decorator for fabric operations.
    
    Combines authentication, fabric access control, rate limiting, and audit logging.
    """
    def decorator(func: Callable) -> Callable:
        # Apply decorators in reverse order (innermost first)
        func = audit_api_access(f"fabric_{action}")(func)
        func = rate_limit(max_requests=max_requests)(func)
        func = fabric_access_required(action, fabric_param)(func)
        func = login_required(func)
        return func
    return decorator