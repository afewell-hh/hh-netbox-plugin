"""
WebSocket Authentication Middleware
Handles authentication for WebSocket connections
"""

import logging
from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


class WebSocketAuthMiddleware(BaseMiddleware):
    """
    Middleware to authenticate WebSocket connections using session authentication.
    Falls back to token authentication if session auth fails.
    """
    
    def __init__(self, inner):
        super().__init__(inner)
    
    async def __call__(self, scope, receive, send):
        # Only handle WebSocket connections
        if scope['type'] != 'websocket':
            return await super().__call__(scope, receive, send)
        
        # Try to authenticate the user
        scope['user'] = await self.authenticate_user(scope)
        
        return await super().__call__(scope, receive, send)
    
    async def authenticate_user(self, scope):
        """Authenticate user from WebSocket scope"""
        try:
            # Method 1: Session authentication (preferred)
            user = await self.authenticate_via_session(scope)
            if user and user.is_authenticated:
                logger.debug(f"WebSocket authenticated via session: {user.username}")
                return user
            
            # Method 2: Token authentication (fallback)
            user = await self.authenticate_via_token(scope)
            if user and user.is_authenticated:
                logger.debug(f"WebSocket authenticated via token: {user.username}")
                return user
            
            # Method 3: Query parameter authentication (for development)
            user = await self.authenticate_via_query_params(scope)
            if user and user.is_authenticated:
                logger.debug(f"WebSocket authenticated via query params: {user.username}")
                return user
            
            logger.warning("WebSocket authentication failed - no valid credentials")
            return AnonymousUser()
            
        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
            return AnonymousUser()
    
    @database_sync_to_async
    def authenticate_via_session(self, scope):
        """Authenticate using Django session"""
        try:
            # Get session key from cookies
            cookies = {}
            for header_name, header_value in scope.get('headers', []):
                if header_name == b'cookie':
                    cookie_header = header_value.decode()
                    for cookie in cookie_header.split(';'):
                        if '=' in cookie:
                            key, value = cookie.strip().split('=', 1)
                            cookies[key] = value
            
            session_key = cookies.get('sessionid')
            if not session_key:
                return AnonymousUser()
            
            # Get session
            try:
                session = Session.objects.get(session_key=session_key)
                if session.expire_date < timezone.now():
                    return AnonymousUser()
                
                session_data = session.get_decoded()
                user_id = session_data.get('_auth_user_id')
                
                if user_id:
                    user = User.objects.get(id=user_id)
                    return user
                    
            except (Session.DoesNotExist, User.DoesNotExist):
                pass
            
            return AnonymousUser()
            
        except Exception as e:
            logger.error(f"Session authentication failed: {e}")
            return AnonymousUser()
    
    @database_sync_to_async
    def authenticate_via_token(self, scope):
        """Authenticate using API token"""
        try:
            # Get token from headers
            token = None
            for header_name, header_value in scope.get('headers', []):
                if header_name == b'authorization':
                    auth_header = header_value.decode()
                    if auth_header.startswith('Bearer '):
                        token = auth_header[7:]  # Remove 'Bearer ' prefix
                    elif auth_header.startswith('Token '):
                        token = auth_header[6:]  # Remove 'Token ' prefix
            
            if not token:
                # Try to get token from query parameters
                query_string = scope.get('query_string', b'').decode()
                query_params = parse_qs(query_string)
                token_list = query_params.get('token', [])
                if token_list:
                    token = token_list[0]
            
            if not token:
                return AnonymousUser()
            
            # Validate token (implement your token validation logic)
            # For now, this is a placeholder
            # In production, you'd validate against your token storage
            
            return AnonymousUser()  # Placeholder until token auth is implemented
            
        except Exception as e:
            logger.error(f"Token authentication failed: {e}")
            return AnonymousUser()
    
    @database_sync_to_async
    def authenticate_via_query_params(self, scope):
        """Authenticate using query parameters (development only)"""
        try:
            # Parse query string for user_id (development/testing only)
            query_string = scope.get('query_string', b'').decode()
            query_params = parse_qs(query_string)
            
            # Check for development authentication
            user_id_list = query_params.get('dev_user_id', [])
            if user_id_list and hasattr(User, '_development_mode'):
                # Only allow in development mode
                try:
                    user_id = int(user_id_list[0])
                    user = User.objects.get(id=user_id)
                    return user
                except (ValueError, User.DoesNotExist):
                    pass
            
            return AnonymousUser()
            
        except Exception as e:
            logger.error(f"Query param authentication failed: {e}")
            return AnonymousUser()


class WebSocketPermissionMiddleware(BaseMiddleware):
    """
    Middleware to check permissions for WebSocket connections.
    Ensures users have appropriate access to resources.
    """
    
    async def __call__(self, scope, receive, send):
        # Only handle WebSocket connections
        if scope['type'] != 'websocket':
            return await super().__call__(scope, receive, send)
        
        # Check if user has required permissions
        if not await self.check_permissions(scope):
            # Close connection with permission denied code
            await send({
                'type': 'websocket.close',
                'code': 4003
            })
            return
        
        return await super().__call__(scope, receive, send)
    
    async def check_permissions(self, scope):
        """Check if user has permission to access the WebSocket endpoint"""
        try:
            user = scope.get('user')
            if not user or not user.is_authenticated:
                logger.warning("WebSocket permission denied: User not authenticated")
                return False
            
            # Get route information
            route_name = scope.get('route', {}).get('name', '')
            path = scope.get('path', '')
            
            # Check fabric-specific permissions
            if 'fabric' in path:
                fabric_id = scope.get('url_route', {}).get('kwargs', {}).get('fabric_id')
                if fabric_id:
                    has_access = await self.check_fabric_access(user, fabric_id)
                    if not has_access:
                        logger.warning(f"User {user.id} denied access to fabric {fabric_id}")
                        return False
            
            # Check system-level permissions
            if 'system' in path or route_name == 'system_notifications':
                if not user.is_staff:
                    logger.warning(f"User {user.id} denied access to system notifications (not staff)")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return False
    
    @database_sync_to_async
    def check_fabric_access(self, user, fabric_id):
        """Check if user has access to a specific fabric"""
        try:
            # For now, allow all authenticated users access to all fabrics
            # In production, implement proper RBAC
            return True
            
        except Exception as e:
            logger.error(f"Fabric access check failed: {e}")
            return False


# Combined middleware stack
def get_websocket_application():
    """Get WebSocket application with authentication middleware"""
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator
    from django.urls import path
    from .fabric_consumer import FabricConsumer, SystemConsumer
    
    websocket_urlpatterns = [
        path('ws/fabric/<int:fabric_id>/', FabricConsumer.as_asgi(), name='fabric_websocket'),
        path('ws/system/', SystemConsumer.as_asgi(), name='system_websocket'),
    ]
    
    application = ProtocolTypeRouter({
        'websocket': AllowedHostsOriginValidator(
            WebSocketAuthMiddleware(
                WebSocketPermissionMiddleware(
                    URLRouter(websocket_urlpatterns)
                )
            )
        ),
    })
    
    return application