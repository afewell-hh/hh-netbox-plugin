"""
Event Service Implementation
Central event bus for real-time event processing and distribution
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db import transaction

from ...domain.interfaces.event_service_interface import (
    EventServiceInterface, WebSocketServiceInterface,
    RealtimeEvent, EventSubscription, EventStats, EventCategory, EventPriority
)

logger = logging.getLogger(__name__)


class EventService(EventServiceInterface):
    """
    Central event service for real-time event processing and distribution.
    Integrates with Django Channels for WebSocket communication.
    """
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
        self._subscriptions: Dict[str, EventSubscription] = {}
        self._event_filters: Dict[int, List[Callable]] = defaultdict(list)
        self._recent_events: List[RealtimeEvent] = []
        self._max_recent_events = 1000
        self._stats = {
            'total_events': 0,
            'events_by_category': defaultdict(int),
            'events_by_priority': defaultdict(int),
            'processing_errors': 0,
            'last_event_time': None
        }
        
    async def publish_event(self, event: RealtimeEvent) -> bool:
        """Publish an event to all subscribers"""
        try:
            # Store event in recent events
            self._store_recent_event(event)
            
            # Update statistics
            self._update_stats(event)
            
            # Process subscriptions
            await self._process_subscriptions(event)
            
            # Send to WebSocket clients
            await self._send_to_websockets(event)
            
            # Cache event for retrieval
            await self._cache_event(event)
            
            logger.debug(f"Published event: {event.event_type} for fabric {event.fabric_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            self._stats['processing_errors'] += 1
            return False
    
    async def publish_fabric_event(self, fabric_id: int, event_type: str, data: Dict[str, Any], 
                                  priority: EventPriority = EventPriority.NORMAL) -> bool:
        """Publish a fabric-specific event"""
        event = RealtimeEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            category=EventCategory.FABRIC_STATUS,
            priority=priority,
            timestamp=datetime.now(timezone.utc),
            fabric_id=fabric_id,
            user_id=None,
            data=data,
            metadata={
                'source': 'fabric_service',
                'fabric_id': fabric_id
            }
        )
        
        return await self.publish_event(event)
    
    async def publish_crd_event(self, fabric_id: int, crd_type: str, crd_name: str, 
                               event_type: str, data: Dict[str, Any]) -> bool:
        """Publish a CRD lifecycle event"""
        event = RealtimeEvent(
            event_id=str(uuid.uuid4()),
            event_type=f"crd_{event_type}",
            category=EventCategory.CRD_LIFECYCLE,
            priority=EventPriority.NORMAL,
            timestamp=datetime.now(timezone.utc),
            fabric_id=fabric_id,
            user_id=None,
            data={
                'crd_type': crd_type,
                'crd_name': crd_name,
                'event_type': event_type,
                **data
            },
            metadata={
                'source': 'kubernetes_watch',
                'crd_type': crd_type,
                'crd_name': crd_name
            }
        )
        
        return await self.publish_event(event)
    
    async def publish_sync_event(self, fabric_id: int, event_type: str, progress: int, 
                                message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """Publish a Git sync progress event"""
        event_data = {
            'event_type': event_type,
            'progress': progress,
            'message': message,
            **(data or {})
        }
        
        # Determine priority based on event type
        priority = EventPriority.HIGH if event_type in ['failed', 'error'] else EventPriority.NORMAL
        
        event = RealtimeEvent(
            event_id=str(uuid.uuid4()),
            event_type=f"sync_{event_type}",
            category=EventCategory.GIT_SYNC,
            priority=priority,
            timestamp=datetime.now(timezone.utc),
            fabric_id=fabric_id,
            user_id=None,
            data=event_data,
            metadata={
                'source': 'git_sync_service',
                'progress': progress
            }
        )
        
        return await self.publish_event(event)
    
    def subscribe(self, subscription: EventSubscription) -> str:
        """Subscribe to events with filtering"""
        subscription_id = str(uuid.uuid4())
        self._subscriptions[subscription_id] = subscription
        
        logger.info(f"New event subscription: {subscription_id} for {subscription.event_types}")
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events"""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            logger.info(f"Removed event subscription: {subscription_id}")
            return True
        return False
    
    async def get_recent_events(self, fabric_id: Optional[int] = None, 
                               limit: int = 100, 
                               categories: Optional[List[EventCategory]] = None) -> List[RealtimeEvent]:
        """Get recent events with optional filtering"""
        filtered_events = self._recent_events
        
        # Filter by fabric
        if fabric_id is not None:
            filtered_events = [e for e in filtered_events if e.fabric_id == fabric_id]
        
        # Filter by categories
        if categories:
            filtered_events = [e for e in filtered_events if e.category in categories]
        
        # Sort by timestamp and limit
        filtered_events.sort(key=lambda e: e.timestamp, reverse=True)
        return filtered_events[:limit]
    
    async def get_event_stats(self, fabric_id: Optional[int] = None, 
                             since: Optional[datetime] = None) -> EventStats:
        """Get event processing statistics"""
        # For fabric-specific stats, filter recent events
        if fabric_id is not None:
            fabric_events = [e for e in self._recent_events if e.fabric_id == fabric_id]
            if since:
                fabric_events = [e for e in fabric_events if e.timestamp >= since]
            
            stats = EventStats(
                total_events=len(fabric_events),
                events_by_category={cat.value: 0 for cat in EventCategory},
                events_by_priority={pri.value: 0 for pri in EventPriority},
                processing_time_avg=0.0,  # Would need to track processing times
                errors=0,  # Would need to track errors per fabric
                subscribers=len([s for s in self._subscriptions.values() 
                               if not s.fabric_ids or fabric_id in s.fabric_ids])
            )
            
            # Count by category and priority
            for event in fabric_events:
                stats.events_by_category[event.category.value] += 1
                stats.events_by_priority[event.priority.value] += 1
            
            return stats
        
        # Global stats
        return EventStats(
            total_events=self._stats['total_events'],
            events_by_category=dict(self._stats['events_by_category']),
            events_by_priority=dict(self._stats['events_by_priority']),
            processing_time_avg=0.0,
            errors=self._stats['processing_errors'],
            subscribers=len(self._subscriptions)
        )
    
    async def create_event_filter(self, fabric_id: int, 
                                 filter_config: Dict[str, Any]) -> str:
        """Create a reusable event filter"""
        filter_id = str(uuid.uuid4())
        
        # Create filter function based on config
        def event_filter(event: RealtimeEvent) -> bool:
            # Example filter logic - can be expanded
            if 'event_types' in filter_config:
                if event.event_type not in filter_config['event_types']:
                    return False
            
            if 'categories' in filter_config:
                if event.category.value not in filter_config['categories']:
                    return False
            
            if 'priority_min' in filter_config:
                priority_order = {'low': 0, 'normal': 1, 'high': 2, 'critical': 3}
                if priority_order.get(event.priority.value, 0) < priority_order.get(filter_config['priority_min'], 0):
                    return False
            
            return True
        
        self._event_filters[fabric_id].append(event_filter)
        
        # Store filter config for management
        cache.set(f"event_filter_{filter_id}", {
            'fabric_id': fabric_id,
            'config': filter_config,
            'created_at': datetime.now(timezone.utc).isoformat()
        }, timeout=86400)  # 24 hours
        
        logger.info(f"Created event filter {filter_id} for fabric {fabric_id}")
        return filter_id
    
    async def broadcast_to_fabric_users(self, fabric_id: int, event: RealtimeEvent) -> int:
        """Broadcast event to all users with access to fabric"""
        if not self.channel_layer:
            logger.warning("No channel layer available for broadcasting")
            return 0
        
        try:
            # Send to fabric group
            await self.channel_layer.group_send(
                f"fabric_{fabric_id}",
                {
                    'type': self._get_websocket_handler_name(event),
                    'data': event.to_dict()
                }
            )
            
            logger.debug(f"Broadcast event {event.event_type} to fabric {fabric_id} users")
            return 1  # Would need to track actual connection count
            
        except Exception as e:
            logger.error(f"Failed to broadcast to fabric {fabric_id}: {e}")
            return 0
    
    # Helper methods
    
    def _store_recent_event(self, event: RealtimeEvent):
        """Store event in recent events list"""
        self._recent_events.append(event)
        
        # Maintain size limit
        if len(self._recent_events) > self._max_recent_events:
            self._recent_events = self._recent_events[-self._max_recent_events:]
    
    def _update_stats(self, event: RealtimeEvent):
        """Update event statistics"""
        self._stats['total_events'] += 1
        self._stats['events_by_category'][event.category.value] += 1
        self._stats['events_by_priority'][event.priority.value] += 1
        self._stats['last_event_time'] = event.timestamp.isoformat()
    
    async def _process_subscriptions(self, event: RealtimeEvent):
        """Process event against all subscriptions"""
        for subscription_id, subscription in self._subscriptions.items():
            try:
                if self._matches_subscription(event, subscription):
                    # Call subscription callback
                    if subscription.callback:
                        await subscription.callback(event)
            except Exception as e:
                logger.error(f"Subscription {subscription_id} callback failed: {e}")
    
    def _matches_subscription(self, event: RealtimeEvent, subscription: EventSubscription) -> bool:
        """Check if event matches subscription criteria"""
        # Check event types
        if subscription.event_types and event.event_type not in subscription.event_types:
            return False
        
        # Check categories
        if subscription.categories and event.category not in subscription.categories:
            return False
        
        # Check fabric IDs
        if subscription.fabric_ids and event.fabric_id not in subscription.fabric_ids:
            return False
        
        # Check user ID
        if subscription.user_id and event.user_id != subscription.user_id:
            return False
        
        # Apply custom filter
        if subscription.filter_func:
            try:
                if not subscription.filter_func(event):
                    return False
            except Exception as e:
                logger.error(f"Subscription filter failed: {e}")
                return False
        
        return True
    
    async def _send_to_websockets(self, event: RealtimeEvent):
        """Send event to WebSocket clients"""
        if not self.channel_layer:
            return
        
        try:
            # Send to specific fabric group if fabric_id is set
            if event.fabric_id:
                await self.broadcast_to_fabric_users(event.fabric_id, event)
            
            # Send to system-wide notifications for high priority events
            if event.priority in [EventPriority.HIGH, EventPriority.CRITICAL]:
                await self.channel_layer.group_send(
                    "system_notifications",
                    {
                        'type': 'system_notification',
                        'data': event.to_dict()
                    }
                )
            
        except Exception as e:
            logger.error(f"Failed to send event to WebSockets: {e}")
    
    def _get_websocket_handler_name(self, event: RealtimeEvent) -> str:
        """Get WebSocket handler name based on event type"""
        if event.category == EventCategory.FABRIC_STATUS:
            return 'fabric_status_update'
        elif event.category == EventCategory.CRD_LIFECYCLE:
            return 'crd_event'
        elif event.category == EventCategory.GIT_SYNC:
            return 'sync_progress'
        elif event.category == EventCategory.VALIDATION:
            return 'validation_result'
        elif event.event_type.startswith('watch_'):
            return 'watch_status_change'
        else:
            return 'system_notification'
    
    async def _cache_event(self, event: RealtimeEvent):
        """Cache event for retrieval"""
        try:
            # Cache with TTL for recent event retrieval
            cache_key = f"event_{event.event_id}"
            cache.set(cache_key, event.to_dict(), timeout=3600)  # 1 hour
            
            # Add to fabric event list
            if event.fabric_id:
                fabric_events_key = f"fabric_events_{event.fabric_id}"
                recent_events = cache.get(fabric_events_key, [])
                recent_events.append(event.event_id)
                
                # Keep only recent events
                if len(recent_events) > 100:
                    recent_events = recent_events[-100:]
                
                cache.set(fabric_events_key, recent_events, timeout=3600)
                
        except Exception as e:
            logger.error(f"Failed to cache event: {e}")


class WebSocketService(WebSocketServiceInterface):
    """
    WebSocket service for real-time communication.
    Works with EventService to send events to connected clients.
    """
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    async def send_to_user(self, user_id: int, event: RealtimeEvent) -> bool:
        """Send event to specific user"""
        if not self.channel_layer:
            return False
        
        try:
            # Send to user-specific group across all their fabric connections
            await self.channel_layer.group_send(
                f"user_{user_id}",
                {
                    'type': 'system_notification',
                    'data': event.to_dict()
                }
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to user {user_id}: {e}")
            return False
    
    async def send_to_fabric_watchers(self, fabric_id: int, event: RealtimeEvent) -> int:
        """Send event to all users watching a fabric"""
        if not self.channel_layer:
            return 0
        
        try:
            await self.channel_layer.group_send(
                f"fabric_{fabric_id}",
                {
                    'type': self._get_handler_name(event),
                    'data': event.to_dict()
                }
            )
            return 1  # Would need connection tracking for actual count
            
        except Exception as e:
            logger.error(f"Failed to send to fabric {fabric_id} watchers: {e}")
            return 0
    
    async def broadcast_system_event(self, event: RealtimeEvent) -> int:
        """Broadcast system-wide event"""
        if not self.channel_layer:
            return 0
        
        try:
            await self.channel_layer.group_send(
                "system_notifications",
                {
                    'type': 'system_notification',
                    'data': event.to_dict()
                }
            )
            return 1
            
        except Exception as e:
            logger.error(f"Failed to broadcast system event: {e}")
            return 0
    
    def get_active_connections(self, fabric_id: Optional[int] = None) -> int:
        """Get count of active WebSocket connections"""
        # This would require connection tracking in Redis or similar
        # For now, return 0 as placeholder
        return 0
    
    async def validate_user_access(self, user_id: int, fabric_id: int) -> bool:
        """Validate user access to fabric events"""
        # Implement your RBAC logic here
        # For now, allow all authenticated users
        return True
    
    def _get_handler_name(self, event: RealtimeEvent) -> str:
        """Get WebSocket handler name for event"""
        if event.category == EventCategory.FABRIC_STATUS:
            return 'fabric_status_update'
        elif event.category == EventCategory.CRD_LIFECYCLE:
            return 'crd_event'
        elif event.category == EventCategory.GIT_SYNC:
            return 'sync_progress'
        else:
            return 'system_notification'