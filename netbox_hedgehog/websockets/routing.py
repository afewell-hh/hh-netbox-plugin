"""
WebSocket Routing Configuration
Defines URL patterns for WebSocket connections
"""

from django.urls import path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from .fabric_consumer import FabricConsumer, SystemConsumer
from .middleware import WebSocketAuthMiddleware, WebSocketPermissionMiddleware


# WebSocket URL patterns
websocket_urlpatterns = [
    # Fabric-specific WebSocket connections
    path('ws/fabric/<int:fabric_id>/', FabricConsumer.as_asgi(), name='fabric_websocket'),
    
    # System-wide notifications
    path('ws/system/', SystemConsumer.as_asgi(), name='system_websocket'),
    
    # Health check endpoint
    path('ws/health/', FabricConsumer.as_asgi(), name='websocket_health'),
]


# Main WebSocket application with middleware stack
application = ProtocolTypeRouter({
    'websocket': AllowedHostsOriginValidator(
        WebSocketAuthMiddleware(
            WebSocketPermissionMiddleware(
                URLRouter(websocket_urlpatterns)
            )
        )
    ),
})


# Alternative application for testing without authentication
test_application = ProtocolTypeRouter({
    'websocket': AllowedHostsOriginValidator(
        URLRouter(websocket_urlpatterns)
    ),
})


def get_asgi_application(testing=False):
    """
    Get ASGI application with appropriate configuration.
    
    Args:
        testing: If True, return application without authentication middleware
    
    Returns:
        ASGI application
    """
    if testing:
        return test_application
    return application