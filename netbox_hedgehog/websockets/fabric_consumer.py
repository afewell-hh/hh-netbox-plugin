"""
Fabric WebSocket Consumer
Handles real-time WebSocket connections for fabric updates
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.apps import apps

from ..domain.interfaces.event_service_interface import (
    RealtimeEvent, EventCategory, EventPriority
)

logger = logging.getLogger(__name__)


class FabricConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time fabric updates.
    Handles connections, authentication, and message routing.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fabric_id: Optional[int] = None
        self.user: Optional[User] = None
        self.user_id: Optional[int] = None
        self.group_name: str = ""
        self.fabric_group_name: str = ""
        
    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Extract fabric ID from URL
            self.fabric_id = int(self.scope['url_route']['kwargs']['fabric_id'])
            
            # Get user from scope (set by authentication middleware)
            self.user = self.scope.get('user')
            if not self.user or not self.user.is_authenticated:
                logger.warning(f"Unauthenticated WebSocket connection attempt for fabric {self.fabric_id}")
                await self.close(code=4001)
                return
            
            self.user_id = self.user.id
            
            # Validate user access to fabric
            has_access = await self.validate_fabric_access()
            if not has_access:
                logger.warning(f"User {self.user_id} denied access to fabric {self.fabric_id}")
                await self.close(code=4003)
                return
            
            # Create group names for message routing
            self.fabric_group_name = f"fabric_{self.fabric_id}"
            self.group_name = f"fabric_{self.fabric_id}_user_{self.user_id}"
            
            # Join fabric group for broadcast messages
            await self.channel_layer.group_add(
                self.fabric_group_name,
                self.channel_name
            )
            
            # Join user-specific group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            # Accept connection
            await self.accept()
            
            logger.info(f"WebSocket connected: User {self.user_id} to fabric {self.fabric_id}")
            
            # Send initial fabric status
            await self.send_initial_status()
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Leave groups
            if self.fabric_group_name:
                await self.channel_layer.group_discard(
                    self.fabric_group_name,
                    self.channel_name
                )
            
            if self.group_name:
                await self.channel_layer.group_discard(
                    self.group_name,
                    self.channel_name
                )
            
            logger.info(f"WebSocket disconnected: User {self.user_id} from fabric {self.fabric_id} (code: {close_code})")
            
        except Exception as e:
            logger.error(f"WebSocket disconnect error: {e}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                await self.send_message('pong', {'timestamp': datetime.now().isoformat()})
            
            elif message_type == 'subscribe_events':
                await self.handle_event_subscription(data.get('events', []))
            
            elif message_type == 'get_status':
                await self.send_fabric_status()
            
            elif message_type == 'trigger_sync':
                await self.handle_sync_trigger(data.get('params', {}))
            
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received from user {self.user_id}")
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send_error(f"Message handling error: {str(e)}")
    
    # Message handlers for different event types
    
    async def fabric_status_update(self, event):
        """Handle fabric status update events"""
        await self.send_message('fabric_status', event['data'])
    
    async def crd_event(self, event):
        """Handle CRD lifecycle events"""
        await self.send_message('crd_event', event['data'])
    
    async def sync_progress(self, event):
        """Handle Git sync progress events"""
        await self.send_message('sync_progress', event['data'])
    
    async def validation_result(self, event):
        """Handle validation result events"""
        await self.send_message('validation_result', event['data'])
    
    async def watch_status_change(self, event):
        """Handle watch status change events"""
        await self.send_message('watch_status', event['data'])
    
    async def system_notification(self, event):
        """Handle system-wide notifications"""
        await self.send_message('notification', event['data'])
    
    # Helper methods
    
    async def send_message(self, message_type: str, data: Dict[str, Any]):
        """Send a structured message to the WebSocket client"""
        message = {
            'type': message_type,
            'timestamp': datetime.now().isoformat(),
            'fabric_id': self.fabric_id,
            'data': data
        }
        
        await self.send(text_data=json.dumps(message))
    
    async def send_error(self, error_message: str):
        """Send an error message to the client"""
        await self.send_message('error', {'message': error_message})
    
    async def send_initial_status(self):
        """Send initial fabric status when client connects"""
        try:
            fabric = await self.get_fabric()
            if fabric:
                status_data = {
                    'fabric_name': fabric.name,
                    'status': fabric.status,
                    'connection_status': fabric.connection_status,
                    'sync_status': fabric.sync_status,
                    'watch_status': fabric.watch_status,
                    'last_sync': fabric.last_sync.isoformat() if fabric.last_sync else None,
                    'crd_count': fabric.crd_count,
                    'active_crd_count': fabric.active_crd_count,
                    'watch_statistics': fabric.get_watch_statistics()
                }
                
                await self.send_message('initial_status', status_data)
                
        except Exception as e:
            logger.error(f"Failed to send initial status: {e}")
            await self.send_error("Failed to load initial fabric status")
    
    async def send_fabric_status(self):
        """Send current fabric status on request"""
        try:
            fabric = await self.get_fabric()
            if fabric:
                # Get comprehensive status
                status_data = await self.get_comprehensive_fabric_status(fabric)
                await self.send_message('fabric_status', status_data)
                
        except Exception as e:
            logger.error(f"Failed to send fabric status: {e}")
            await self.send_error("Failed to get fabric status")
    
    async def handle_event_subscription(self, event_types: list):
        """Handle client event subscription requests"""
        try:
            # For now, all connected clients get all events for their fabric
            # In future, this could be used for fine-grained filtering
            await self.send_message('subscription_confirmed', {
                'subscribed_events': event_types,
                'message': 'Subscribed to fabric events'
            })
            
        except Exception as e:
            logger.error(f"Failed to handle event subscription: {e}")
            await self.send_error("Failed to process subscription")
    
    async def handle_sync_trigger(self, params: Dict[str, Any]):
        """Handle client-triggered sync operations"""
        try:
            fabric = await self.get_fabric()
            if not fabric:
                await self.send_error("Fabric not found")
                return
            
            # Check user permissions for sync operations
            if not await self.can_trigger_sync():
                await self.send_error("Insufficient permissions to trigger sync")
                return
            
            # Trigger sync operation (implement based on your sync service)
            await self.send_message('sync_triggered', {
                'message': 'Sync operation started',
                'params': params
            })
            
            # TODO: Actually trigger the sync operation
            # This would integrate with your GitSyncService
            
        except Exception as e:
            logger.error(f"Failed to handle sync trigger: {e}")
            await self.send_error("Failed to trigger sync")
    
    @database_sync_to_async
    def validate_fabric_access(self) -> bool:
        """Validate that user has access to the fabric"""
        try:
            HedgehogFabric = apps.get_model('netbox_hedgehog', 'HedgehogFabric')
            fabric = HedgehogFabric.objects.get(pk=self.fabric_id)
            
            # For now, any authenticated user can view fabrics
            # In production, implement proper RBAC
            return True
            
        except Exception as e:
            logger.error(f"Fabric access validation failed: {e}")
            return False
    
    @database_sync_to_async
    def get_fabric(self):
        """Get fabric model instance"""
        try:
            HedgehogFabric = apps.get_model('netbox_hedgehog', 'HedgehogFabric')
            return HedgehogFabric.objects.get(pk=self.fabric_id)
        except Exception as e:
            logger.error(f"Failed to get fabric {self.fabric_id}: {e}")
            return None
    
    @database_sync_to_async
    def can_trigger_sync(self) -> bool:
        """Check if user can trigger sync operations"""
        # Implement permission check
        # For now, allow all authenticated users
        return self.user and self.user.is_authenticated
    
    async def get_comprehensive_fabric_status(self, fabric) -> Dict[str, Any]:
        """Get comprehensive fabric status data"""
        # This would integrate with your service layer to get real-time status
        return {
            'fabric_name': fabric.name,
            'fabric_id': fabric.pk,
            'status': fabric.status,
            'connection_status': fabric.connection_status,
            'sync_status': fabric.sync_status,
            'watch_status': fabric.watch_status,
            'last_sync': fabric.last_sync.isoformat() if fabric.last_sync else None,
            'crd_count': fabric.crd_count,
            'active_crd_count': fabric.active_crd_count,
            'error_crd_count': fabric.error_crd_count,
            'watch_statistics': fabric.get_watch_statistics(),
            'gitops_summary': fabric.get_gitops_summary(),
            'kubernetes_config': {
                'server': fabric.kubernetes_server,
                'namespace': fabric.kubernetes_namespace,
                'configured': bool(fabric.kubernetes_server)
            }
        }


class SystemConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for system-wide notifications.
    Handles global events and admin notifications.
    """
    
    async def connect(self):
        """Handle system WebSocket connection"""
        try:
            # Check if user is authenticated and has admin privileges
            user = self.scope.get('user')
            if not user or not user.is_authenticated or not user.is_staff:
                await self.close(code=4003)
                return
            
            # Join system notifications group
            await self.channel_layer.group_add(
                "system_notifications",
                self.channel_name
            )
            
            await self.accept()
            logger.info(f"System WebSocket connected for user {user.id}")
            
        except Exception as e:
            logger.error(f"System WebSocket connection failed: {e}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Handle system WebSocket disconnection"""
        await self.channel_layer.group_discard(
            "system_notifications",
            self.channel_name
        )
    
    async def system_notification(self, event):
        """Handle system-wide notifications"""
        await self.send(text_data=json.dumps({
            'type': 'system_notification',
            'timestamp': datetime.now().isoformat(),
            'data': event['data']
        }))